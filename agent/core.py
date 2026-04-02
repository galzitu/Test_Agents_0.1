"""
Core - The main trading loop.

Flow each tick:
1. Check market hours → if closed, sleep
2. If should_close_all → close everything
3. Check open positions for SL/TP hits
4. Detect market condition (trending/ranging/volatile)
5. Select active strategies for current session + condition
6. For each active strategy + each watchlist symbol → generate signal
7. Filter: only BUY/SELL signals with confidence > threshold
8. Execute trades through risk manager
9. Sleep until next check interval
"""

import logging
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from agent.config import (
    INITIAL_CAPITAL, STRATEGIES_CONFIG_DIR, LOGS_DIR, ensure_directories
)
from agent.market_hours import MarketHours
from agent.market_condition import MarketConditionDetector
from agent.market_data import (
    AlpacaClient, IndicatorCalculator, Screener
)
from agent.memory import Memory
from agent.health import HealthMonitor
from agent.strategies.selector import StrategySelector
from agent.strategies.base import SignalType
from agent.scorer import StrategyScorer
from agent.allocator import CapitalAllocator
from agent.risk_manager import RiskManager
from agent.trader import Trader
from agent.telegram_bot import TelegramNotifier
from agent.strategies.orb import OpeningRangeBreakout

logger = logging.getLogger(__name__)


class TradingAgent:
    """
    The main autonomous trading agent.

    Runs a loop during market hours:
    - Opening (09:30-10:30): Check every 30 sec
    - Mid-Day (10:30-14:30): Check every 5 min
    - Power Hour (14:30-16:00): Check every 2 min
    - 15:50: Close everything
    """

    # Minimum confidence to act on a signal
    MIN_CONFIDENCE = 0.45

    def __init__(self):
        """Initialize all components."""
        ensure_directories()

        # Core components
        self.market_hours = MarketHours()
        self.client = AlpacaClient()
        self.memory = Memory()
        self.health = HealthMonitor(self.memory)
        self.condition_detector = MarketConditionDetector()
        self.indicator_calc = IndicatorCalculator()
        self.screener = Screener(self.client)

        # Strategy management
        self.selector = StrategySelector()
        self.scorer = StrategyScorer(self.memory)
        self.allocator = CapitalAllocator()

        # Notifications
        self.notifier = TelegramNotifier()

        # Risk + execution
        self.risk_manager = RiskManager(self.memory, self.market_hours)
        self.trader = Trader(
            self.client, self.memory, self.risk_manager,
            self.scorer, self.allocator, self.notifier
        )

        # State
        self._running = False
        self._current_allocation = self._load_allocation()
        self._watchlist = Screener.DEFAULT_WATCHLIST
        self._daily_conditions_seen = set()
        self._orb_range_date = None
        self._was_market_open = False  # Track market open→close transition
        self._daily_summary_saved_date = None  # Prevent double-save
        # Persist last alert key across restarts to avoid duplicate notifications
        self._health_alert_file = LOGS_DIR / "last_health_alert.txt"
        self._last_health_alert = (
            self._health_alert_file.read_text().strip()
            if self._health_alert_file.exists() else ""
        )

        # Tick diagnostics — exposed to dashboard
        self._last_tick_info = {
            "timestamp": None,
            "session": None,
            "market_condition": None,
            "active_strategies": [],
            "symbols_scanned": 0,
            "signals_generated": 0,
            "signals_above_threshold": 0,
            "trades_executed": 0,
            "reason_no_trade": None,
            "tick_duration_s": 0,
        }

        logger.info("Trading Agent initialized")

    def _load_allocation(self) -> dict[str, float]:
        """Load current allocation from file, or use defaults."""
        alloc_path = STRATEGIES_CONFIG_DIR / "allocation.json"
        if alloc_path.exists():
            try:
                with open(alloc_path) as f:
                    data = json.load(f)
                return data.get("allocation", {})
            except Exception:
                pass

        # Default: equal allocation for all strategies
        strategies = list(self.selector.all_strategies.keys())
        if strategies:
            equal = round(1.0 / len(strategies), 4)
            return {name: equal for name in strategies}
        return {}

    # ============================================================
    # Main Loop
    # ============================================================

    def run(self):
        """
        Main entry point - runs the trading loop.
        Blocks until stopped or market closes.
        """
        self._running = True
        self.health.record_heartbeat("agent", "starting", {"phase": "startup"})
        logger.info("=" * 60)
        logger.info("TRADING AGENT STARTING")
        logger.info("=" * 60)

        try:
            # Show initial status (may fail if Alpaca API unreachable)
            self._log_startup_info()
        except Exception as e:
            logger.error(f"Startup info failed (non-fatal, continuing): {e}", exc_info=True)

        try:
            self.notifier.notify_daily_start(self.get_full_status())
        except Exception as e:
            logger.error(f"Telegram startup notification failed (non-fatal): {e}", exc_info=True)

        try:
            self.health.record_heartbeat("agent", "running", {"phase": "main_loop_entered"})
            logger.info("Entering main trading loop...")
            while self._running:
                self._tick()
        except KeyboardInterrupt:
            logger.info("Agent stopped by user (Ctrl+C)")
        except Exception as e:
            logger.error(f"Agent crashed: {e}", exc_info=True)
        finally:
            self._shutdown()

    def stop(self):
        """Stop the agent gracefully."""
        logger.info("Agent stop requested")
        self._running = False

    def _tick(self):
        """One iteration of the main loop."""
        status = self.market_hours.get_status()
        session = self.market_hours.get_current_session()
        self.health.record_heartbeat(
            "agent",
            "running",
            {
                "market_open": status["is_market_open"],
                "session": session.name if session else "closed",
            },
        )

        # ---- Market closed ----
        if not status["is_market_open"]:
            # Detect market open→close transition: save daily summary
            today_str = self.market_hours.today_et().isoformat()
            if self._was_market_open and self._daily_summary_saved_date != today_str:
                logger.info("Market just closed — saving daily summary")
                self._save_daily_summary()
                self._daily_summary_saved_date = today_str
                self._was_market_open = False

            self._last_tick_info["reason_no_trade"] = "Market closed"
            self._last_tick_info["timestamp"] = datetime.now().isoformat()
            self._last_tick_info["health"] = self.health.run_checks(
                self.market_hours, self.client
            )
            self._maybe_alert_health(self._last_tick_info["health"])
            next_sess = self.market_hours.get_next_trading_session_info()
            next_info = (
                f"סשן הבא: {next_sess['name']} ({next_sess['day_label']}) "
                f"{next_sess['start_et']}-{next_sess['end_et']} ET "
                f"/ {next_sess['start_ist']}-{next_sess['end_ist']} IST"
            )
            if status.get("time_until_open"):
                logger.info(
                    f"Market closed. Next open in {status['time_until_open']}. "
                    f"{next_info}. Sleeping 60s..."
                )
            else:
                logger.info(f"Market closed. {next_info}. Sleeping 60s...")
            time.sleep(60)
            return

        # ---- Market is open — track it ----
        self._was_market_open = True

        # ---- Close all positions at EOD ----
        if self.market_hours.should_close_all():
            self._last_tick_info["reason_no_trade"] = "EOD close time"
            self._last_tick_info["timestamp"] = datetime.now().isoformat()
            logger.warning("EOD CLOSE TIME - Closing all positions!")
            self.trader.close_all_positions(reason="eod")
            today_str = self.market_hours.today_et().isoformat()
            if self._daily_summary_saved_date != today_str:
                self._save_daily_summary()
                self._daily_summary_saved_date = today_str
            time.sleep(60)
            return

        # ---- Daily loss limit check ----
        portfolio_value = self.trader.get_portfolio_value()
        if self.risk_manager.is_daily_loss_limit_hit(portfolio_value):
            self._last_tick_info["reason_no_trade"] = "Daily loss limit hit"
            self._last_tick_info["timestamp"] = datetime.now().isoformat()
            logger.warning("DAILY LOSS LIMIT HIT - Agent paused!")
            self.notifier.notify_risk_alert(
                f"Daily loss limit hit! P&L: ${self.memory.get_today_pnl():.2f}"
            )
            self.trader.close_all_positions(reason="daily_loss_limit")
            time.sleep(300)  # Check every 5 min
            return

        # ---- Check open positions for SL/TP ----
        positions_to_close = self.trader.check_open_positions()
        for pos in positions_to_close:
            self.trader.close_position(
                pos["trade"], pos["current_price"], pos["reason"]
            )

        # ---- Can we open new positions? ----
        if not self.market_hours.can_open_new_positions():
            self._last_tick_info["reason_no_trade"] = "Too close to market close"
            self._last_tick_info["timestamp"] = datetime.now().isoformat()
            logger.info("Too close to market close for new positions")
            time.sleep(30)
            return

        if not session or not session.trading_allowed:
            self._last_tick_info["reason_no_trade"] = f"Session '{session.name if session else 'none'}' - trading not allowed"
            self._last_tick_info["timestamp"] = datetime.now().isoformat()
            interval = self.market_hours.get_check_interval()
            logger.debug(f"Session {session.name if session else 'none'}: no trading. Sleep {interval}s")
            time.sleep(interval)
            return

        # ---- Trading logic ----
        self._trading_tick(session.name, portfolio_value)
        self._save_tick_info()

        # ---- Sleep until next check ----
        interval = session.check_interval
        logger.debug(f"Session: {session.name}, next check in {interval}s")
        time.sleep(interval)

    def _trading_tick(self, session_name: str, portfolio_value: float):
        """
        One trading iteration:
        1. Detect market condition
        2. Select active strategies
        3. Generate signals for watchlist
        4. Execute best signals
        """
        tick_start = datetime.now()
        tick_id = f"tick-{tick_start.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        diag = self._last_tick_info
        diag["tick_id"] = tick_id
        diag["timestamp"] = tick_start.isoformat()
        diag["session"] = session_name
        diag["reason_no_trade"] = None
        diag["signals_generated"] = 0
        diag["signals_above_threshold"] = 0
        diag["trades_executed"] = 0
        diag["symbols_scanned"] = 0

        # 1. Get market data for reference symbol (SPY)
        try:
            ref_df = self.client.get_bars("SPY", "5Min", limit=100)
            ref_df = self.indicator_calc.add_all_indicators(ref_df)
            snapshot = self.indicator_calc.get_market_snapshot(ref_df)
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            diag["reason_no_trade"] = f"Failed to get SPY data: {e}"
            self.memory.save_signal_audit(
                tick_id=tick_id,
                signal_id="",
                strategy="system",
                symbol="SPY",
                stage="tick",
                decision="error",
                reason=str(e),
                market_context={"session": session_name},
            )
            return

        # 2. Detect market condition
        condition = self.condition_detector.detect(snapshot)
        self._daily_conditions_seen.add(condition.value)
        diag["market_condition"] = condition.value
        logger.info(f"Market condition: {condition.value}")

        # 3. Get indicator values for strategy activation
        indicators = self.indicator_calc.get_latest_indicators(ref_df)

        # 4. Select active strategies
        active_strategies = self.selector.get_active_strategies(
            session_name, condition.value, indicators
        )
        diag["active_strategies"] = [s.name for s in active_strategies] if active_strategies else []

        if not active_strategies:
            diag["reason_no_trade"] = (
                f"No strategies active for session={session_name}, "
                f"condition={condition.value}"
            )
            logger.info(f"No active strategies for current conditions "
                        f"(session={session_name}, condition={condition.value})")
            self.memory.save_signal_audit(
                tick_id=tick_id,
                signal_id="",
                strategy="system",
                symbol="*",
                stage="selector",
                decision="no_active_strategies",
                reason=diag["reason_no_trade"],
                market_context={
                    "session": session_name,
                    "market_condition": condition.value,
                },
            )
            return

        # 5. For each strategy + symbol → generate signals
        signals = []
        total_signals_raw = 0
        hold_count = 0
        low_conf_count = 0
        hold_reasons = {}  # Track hold reasons per strategy
        self._prepare_intraday_strategy_state(session_name, active_strategies)
        for strategy in active_strategies:
            timeframe = strategy.timeframe
            strategy_holds = []
            for symbol in self._watchlist:
                diag["symbols_scanned"] += 1
                try:
                    df = self.client.get_bars(symbol, timeframe, limit=100)
                    df = self.indicator_calc.add_all_indicators(df)

                    signal = strategy.generate_signal(df, symbol)
                    signal.tick_id = tick_id
                    signal.signal_id = self._build_signal_id(
                        tick_id, strategy.name, symbol
                    )
                    total_signals_raw += 1

                    if signal.type == SignalType.HOLD:
                        hold_count += 1
                        strategy_holds.append(f"{symbol}:{signal.reason}")
                        self._audit_signal(
                            signal,
                            stage="signal_generated",
                            decision="hold",
                            reason=signal.reason,
                            market_context={
                                "session": session_name,
                                "market_condition": condition.value,
                            },
                        )
                    elif signal.confidence < self.MIN_CONFIDENCE:
                        low_conf_count += 1
                        self._audit_signal(
                            signal,
                            stage="confidence_filter",
                            decision="rejected",
                            reason=(
                                f"confidence {signal.confidence:.2f} "
                                f"< {self.MIN_CONFIDENCE:.2f}"
                            ),
                            market_context={
                                "session": session_name,
                                "market_condition": condition.value,
                            },
                        )
                        logger.info(
                            f"Low confidence: {strategy.name} {signal.type.value} "
                            f"{symbol} conf={signal.confidence:.2f} < {self.MIN_CONFIDENCE}"
                        )
                    else:
                        self._audit_signal(
                            signal,
                            stage="confidence_filter",
                            decision="accepted",
                            reason="passed confidence threshold",
                            market_context={
                                "session": session_name,
                                "market_condition": condition.value,
                            },
                        )
                        signals.append(signal)
                        logger.info(
                            f"Signal: {signal.strategy} {signal.type.value} "
                            f"{signal.symbol} conf={signal.confidence:.2f}"
                        )

                except Exception as e:
                    logger.debug(f"Error processing {symbol} with {strategy.name}: {e}")

            # Log hold reason summary per strategy
            if strategy_holds:
                # Count reasons
                reason_counts = {}
                for h in strategy_holds:
                    reason = h.split(":", 1)[1] if ":" in h else h
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                hold_reasons[strategy.name] = reason_counts
                top_reasons = sorted(reason_counts.items(), key=lambda x: -x[1])[:3]
                logger.info(
                    f"  {strategy.name}: {len(strategy_holds)} HOLD - "
                    f"reasons: {', '.join(f'{r}({c})' for r, c in top_reasons)}"
                )
        diag["hold_reasons"] = hold_reasons

        diag["signals_generated"] = total_signals_raw
        diag["signals_above_threshold"] = len(signals)

        if not signals:
            reason = (
                f"All {total_signals_raw} signals filtered: "
                f"{hold_count} HOLD, {low_conf_count} low confidence (<{self.MIN_CONFIDENCE})"
            )
            diag["reason_no_trade"] = reason
            logger.info(f"No actionable signals: {reason}")
            return

        # 6. Sort by confidence (highest first)
        signals.sort(key=lambda s: s.confidence, reverse=True)

        # 7. Execute (risk manager will block if limits hit)
        executed = 0
        rejected_reasons = []
        for signal in signals:
            result = self.trader.execute_signal(
                signal, self._current_allocation, session_name, condition.value
            )
            if result.get("status") == "executed":
                executed += 1
                self._audit_signal(
                    signal,
                    stage="execution",
                    decision="executed",
                    reason="order submitted",
                    market_context={
                        "session": session_name,
                        "market_condition": condition.value,
                    },
                    payload=result.get("trade"),
                )
                # Reload allocation after each trade
                self._current_allocation = self._load_allocation()
            else:
                reason = result.get("reason", "blocked")
                rejected_reasons.append(
                    f"{signal.strategy}/{signal.symbol}: {reason}"
                )
                self._audit_signal(
                    signal,
                    stage=result.get("stage", "execution"),
                    decision=result.get("status", "blocked"),
                    reason=reason,
                    market_context={
                        "session": session_name,
                        "market_condition": condition.value,
                    },
                )

        diag["trades_executed"] = executed
        diag["health"] = self.health.run_checks(self.market_hours, self.client)
        self._maybe_alert_health(diag["health"])
        if executed == 0 and rejected_reasons:
            diag["reason_no_trade"] = (
                f"{len(signals)} signals passed filter but execution "
                f"blocked all: {', '.join(rejected_reasons[:5])}"
            )

        tick_duration = (datetime.now() - tick_start).total_seconds()
        diag["tick_duration_s"] = round(tick_duration, 1)
        logger.info(
            f"Tick complete: {total_signals_raw} raw signals, "
            f"{len(signals)} above threshold, {executed} executed "
            f"({tick_duration:.1f}s)"
        )

    def _build_signal_id(self, tick_id: str, strategy_name: str, symbol: str) -> str:
        return f"{tick_id}:{strategy_name}:{symbol}"

    def _audit_signal(self, signal, stage: str, decision: str, reason: str,
                      market_context: Optional[dict] = None,
                      payload: Optional[dict] = None):
        self.memory.save_signal_audit(
            tick_id=getattr(signal, "tick_id", ""),
            signal_id=getattr(signal, "signal_id", ""),
            strategy=signal.strategy,
            symbol=signal.symbol,
            stage=stage,
            decision=decision,
            reason=reason,
            confidence=signal.confidence,
            market_context=market_context,
            payload=payload or signal.to_dict(),
        )

    def _maybe_alert_health(self, health: dict):
        issues = []
        if not health.get("db_writable", True):
            issues.append("DB not writable")
        if not health.get("disk_ok", True):
            issues.append("Disk space below threshold")
        # Only alert about Alpaca when market is open — unreachable outside hours is normal
        if health.get("alpaca_reachable") is False and health.get("market_open", False):
            issues.append("Alpaca unreachable")
        if not health.get("agent_heartbeat_fresh", True):
            issues.append("Agent heartbeat stale")

        systemd = health.get("systemd", {})
        for service, state in systemd.items():
            if state not in {"active", "unavailable"}:
                issues.append(f"{service} is {state}")

        alert_key = " | ".join(issues)
        if issues and alert_key != self._last_health_alert:
            self.notifier.notify_system_alert(
                "SYSTEM HEALTH ALERT",
                "\n".join(f"- {issue}" for issue in issues),
            )
            self._last_health_alert = alert_key
            self._health_alert_file.write_text(alert_key)
        elif not issues:
            self._last_health_alert = ""
            self._health_alert_file.write_text("")

    def _prepare_intraday_strategy_state(self, session_name: str, active_strategies: list):
        """Prepare stateful strategies like ORB before signal generation."""
        today = self.market_hours.today_et().isoformat()
        if self._orb_range_date != today:
            orb = self.selector.get_strategy("Opening_Range_Breakout")
            if isinstance(orb, OpeningRangeBreakout):
                orb.reset_range()
            self._orb_range_date = today

        if session_name != "opening":
            return

        now_et = self.market_hours.now_et().time()
        if now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 45):
            return

        for strategy in active_strategies:
            if not isinstance(strategy, OpeningRangeBreakout):
                continue

            for symbol in self._watchlist:
                if strategy.has_range(symbol):
                    continue
                try:
                    df_1min = self.client.get_bars(symbol, "1Min", limit=strategy.params["range_minutes"])
                    strategy.set_opening_range(symbol, df_1min)
                except Exception as e:
                    logger.debug(f"Failed to prepare ORB range for {symbol}: {e}")

    def _save_tick_info(self):
        """Save last tick diagnostics to a JSON file for the dashboard."""
        try:
            tick_file = LOGS_DIR / "last_tick.json"
            with open(tick_file, "w") as f:
                json.dump(self._last_tick_info, f, default=str)
        except Exception:
            pass  # Non-critical

    # ============================================================
    # Daily Summary
    # ============================================================

    def _save_daily_summary(self):
        """Save end-of-day summary to memory. Always saves, even with 0 trades."""
        try:
            today_trades = self.memory.get_today_trades()

            closed = [t for t in today_trades if t["status"] == "closed"]
            wins = [t for t in closed if t.get("pnl", 0) and t["pnl"] > 0]
            losses = [t for t in closed if t.get("pnl", 0) and t["pnl"] <= 0]
            pnls = [t["pnl"] for t in closed if t.get("pnl") is not None]

            strategies_used = list(set(t["strategy"] for t in today_trades))

            # Build notes for zero-trade days
            notes = ""
            if not today_trades:
                diag = self._last_tick_info or {}
                notes = (
                    f"Zero trades. Last reason: {diag.get('reason_no_trade', 'unknown')}. "
                    f"Conditions seen: {list(self._daily_conditions_seen) or ['none']}"
                )

            summary = {
                "total_trades": len(today_trades),
                "wins": len(wins),
                "losses": len(losses),
                "total_pnl": sum(pnls) if pnls else 0,
                "total_pnl_pct": 0,  # Will be calculated based on portfolio
                "best_trade_pnl": max(pnls) if pnls else 0,
                "worst_trade_pnl": min(pnls) if pnls else 0,
                "strategies_used": strategies_used,
                "market_conditions": list(self._daily_conditions_seen),
                "notes": notes,
            }

            self.memory.save_daily_summary(summary)
            pruned = self.memory.prune_signal_audit()
            self.memory.export_learnings_md()
            self.memory.export_strategy_performance_md()

            # Send Telegram daily summary
            self.notifier.notify_daily_summary(summary)

            logger.info(
                f"Daily summary saved: {len(today_trades)} trades, "
                f"P&L: ${summary['total_pnl']:.2f}, pruned audit rows: {pruned}"
            )

        except Exception as e:
            logger.error(f"Failed to save daily summary: {e}")

    # ============================================================
    # Startup / Shutdown
    # ============================================================

    def _log_startup_info(self):
        """Log startup information."""
        try:
            account = self.client.get_account()
            logger.info(f"Account equity: ${account['equity']:.2f}")
            logger.info(f"Buying power: ${account['buying_power']:.2f}")
        except Exception as e:
            logger.warning(f"Could not get account info: {e}")

        market_status = self.market_hours.get_status()
        logger.info(f"Time: {market_status['time_et']} ({market_status['time_ist']})")
        logger.info(f"Market open: {market_status['is_market_open']}")
        logger.info(f"Session: {market_status['current_session']}")
        logger.info(f"Strategies: {list(self.selector.all_strategies.keys())}")
        logger.info(f"Allocation: {self._current_allocation}")
        logger.info(f"Watchlist: {self._watchlist}")

    def _shutdown(self):
        """Clean shutdown - save daily summary and close positions if needed."""
        logger.info("Agent shutting down...")

        # Close all positions if market is still open
        if self.market_hours.is_market_open():
            open_trades = self.memory.get_open_trades()
            if open_trades:
                logger.warning(
                    f"Shutting down with {len(open_trades)} open positions! "
                    f"Closing all..."
                )
                self.trader.close_all_positions(reason="agent_shutdown")

        # Save daily summary
        self._save_daily_summary()
        self.health.record_heartbeat("agent", "stopped", {"phase": "shutdown"})

        logger.info("Agent shutdown complete")

    # ============================================================
    # Manual Controls
    # ============================================================

    def pause(self):
        """Pause trading (close all positions)."""
        logger.info("PAUSE requested - closing all positions")
        self.trader.close_all_positions(reason="manual_pause")
        self._running = False

    def get_full_status(self) -> dict:
        """Get complete agent status."""
        return {
            "market": self.market_hours.get_status(),
            "trading": self.trader.get_status(),
            "risk": self.risk_manager.get_status(self.trader.get_portfolio_value()),
            "strategies": self.selector.get_status(),
            "allocation": self._current_allocation,
            "last_tick": self._last_tick_info,
        }
