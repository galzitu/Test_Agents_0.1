"""
Trader - Executes trades via Alpaca API.
Handles: order submission, position tracking, trade closing.
Every order goes through RiskManager first.
"""

import logging
from datetime import datetime
from typing import Optional

from agent.config import RiskLimits, ExecutionConfig, SHADOW_MODE
from agent.market_data import AlpacaClient
from agent.memory import Memory
from agent.risk_manager import RiskManager
from agent.strategies.base import Signal, SignalType
from agent.scorer import StrategyScorer
from agent.allocator import CapitalAllocator
from agent.telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)


class Trader:
    """
    Executes trades via Alpaca and manages open positions.

    Flow:
    1. Receives signal from strategy
    2. RiskManager validates the signal
    3. Calculates position size
    4. Submits order to Alpaca
    5. Saves trade to Memory (SQLite)
    6. On close: updates scores + allocation
    """

    def __init__(self, client: AlpacaClient, memory: Memory,
                 risk_manager: RiskManager, scorer: StrategyScorer,
                 allocator: CapitalAllocator,
                 notifier: Optional[TelegramNotifier] = None):
        self.client = client
        self.memory = memory
        self.risk_manager = risk_manager
        self.scorer = scorer
        self.allocator = allocator
        self.notifier = notifier or TelegramNotifier()

    def get_portfolio_value(self) -> float:
        """Get current portfolio value from Alpaca."""
        try:
            account = self.client.get_account()
            return account["portfolio_value"]
        except Exception as e:
            logger.error(f"Failed to get portfolio value: {e}")
            from agent.config import INITIAL_CAPITAL
            return INITIAL_CAPITAL

    def get_open_position_count(self) -> int:
        """Get number of open positions from our DB (accurate, real-time)."""
        try:
            return len(self.memory.get_open_trades())
        except Exception as e:
            logger.error(f"Failed to get open position count from DB: {e}")
            return 0

    def has_open_position_for_symbol(self, symbol: str) -> bool:
        """Check if we already have an open position for this symbol."""
        try:
            open_trades = self.memory.get_open_trades()
            return any(t["symbol"] == symbol for t in open_trades)
        except Exception as e:
            logger.error(f"Failed to check open position for {symbol}: {e}")
            return False

    def _blocked(self, signal: Signal, reason: str, stage: str) -> dict:
        return {
            "status": "blocked",
            "stage": stage,
            "reason": reason,
            "symbol": signal.symbol,
            "strategy": signal.strategy,
            "signal_id": getattr(signal, "signal_id", ""),
            "tick_id": getattr(signal, "tick_id", ""),
        }

    def execute_signal(self, signal: Signal, allocation: dict[str, float],
                       session: str = "", market_condition: str = "") -> dict:
        """
        Execute a trading signal (the main entry point).

        Args:
            signal: Signal from a strategy
            allocation: Current capital allocation dict
            session: Current session name

        Returns:
            Dict with execution status and optional trade payload
        """
        if signal.type == SignalType.HOLD:
            return self._blocked(signal, "HOLD signal, no trade needed", "signal")

        # Guard: no duplicate positions on the same symbol
        if self.has_open_position_for_symbol(signal.symbol):
            reason = f"already have open position for {signal.symbol}"
            logger.info("Trade blocked: %s", reason)
            return self._blocked(signal, reason, "dedupe")

        if self._is_in_signal_cooldown(signal):
            reason = (
                f"cooldown active for {signal.strategy}/{signal.symbol} "
                f"({ExecutionConfig.SIGNAL_COOLDOWN_MINUTES}m)"
            )
            logger.info("Trade blocked: %s", reason)
            return self._blocked(signal, reason, "cooldown")

        stale_check = self._check_signal_freshness(signal, session)
        if stale_check:
            logger.info("Trade blocked: %s", stale_check)
            return self._blocked(signal, stale_check, "freshness")

        microstructure_check = self._check_market_microstructure(signal)
        if microstructure_check:
            logger.info("Trade blocked: %s", microstructure_check)
            return self._blocked(signal, microstructure_check, "microstructure")

        portfolio_value = self.get_portfolio_value()
        open_positions = self.get_open_position_count()

        # Step 1: Risk check
        risk_result = self.risk_manager.check_signal(
            signal, portfolio_value, open_positions, session
        )

        if not risk_result:
            logger.info(f"Trade blocked by risk manager: {risk_result.reason}")
            return self._blocked(signal, risk_result.reason, "risk")

        # Step 2: Calculate position size
        alloc_pct = allocation.get(signal.strategy, 0.05)  # Default 5%
        position = self.risk_manager.calculate_position_size(
            signal, portfolio_value, alloc_pct, session
        )

        if position["shares"] <= 0:
            logger.warning(f"Position size is 0 for {signal.symbol}")
            return self._blocked(signal, "position size is 0", "position_sizing")

        if SHADOW_MODE:
            return {
                "status": "shadow",
                "stage": "shadow_mode",
                "reason": "shadow mode enabled - order not submitted",
                "signal_id": getattr(signal, "signal_id", ""),
                "tick_id": getattr(signal, "tick_id", ""),
                "trade": {
                    "strategy": signal.strategy,
                    "symbol": signal.symbol,
                    "side": "long" if signal.type == SignalType.BUY else "short",
                    "entry_price": signal.entry_price,
                    "quantity": position["shares"],
                    "position_pct": position["position_pct"],
                },
            }

        # Step 3: Submit order
        order = self._submit_order(signal, position["shares"])
        if not order:
            return self._blocked(signal, "order submission failed", "broker")

        # Step 4: Save to memory
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "strategy": signal.strategy,
            "symbol": signal.symbol,
            "side": "long" if signal.type == SignalType.BUY else "short",
            "entry_price": signal.entry_price,
            "quantity": position["shares"],
            "status": "open",
            "session": session,
            "market_condition": market_condition,
            "entry_reason": signal.reason,
            "indicators_at_entry": signal.indicators,
            "stop_loss_price": signal.stop_loss,
            "take_profit_price": signal.take_profit,
            "position_pct": position["position_pct"],
            "alpaca_order_id": order.get("id", ""),
            "signal_id": getattr(signal, "signal_id", ""),
            "tick_id": getattr(signal, "tick_id", ""),
            "status_detail": "submitted",
            "last_updated_at": datetime.now().isoformat(),
        }

        try:
            trade_id = self.memory.save_trade(trade_data)
            trade_data["trade_id"] = trade_id

            logger.info(
                f"TRADE OPENED #{trade_id}: {signal.strategy} "
                f"{signal.type.value} {position['shares']} {signal.symbol} "
                f"@ ${signal.entry_price:.2f} "
                f"(SL=${signal.stop_loss:.2f}, TP=${signal.take_profit:.2f})"
            )

            # Send Telegram notification
            self.notifier.notify_trade_opened(trade_data)

            return {
                "status": "executed",
                "trade": trade_data,
                "signal_id": getattr(signal, "signal_id", ""),
                "tick_id": getattr(signal, "tick_id", ""),
            }
        except Exception as e:
            logger.error(
                f"CRITICAL: Trade executed in Alpaca (order #{order.get('id')}) "
                f"but FAILED to save to database: {e}",
                exc_info=True
            )
            return self._blocked(
                signal,
                f"CRITICAL: Order submitted to Alpaca but DB save failed: {e}",
                "db_save_failure"
            )

    def _is_in_signal_cooldown(self, signal: Signal) -> bool:
        recent_trades = self.memory.get_recent_trades(
            signal.strategy,
            signal.symbol,
            since_minutes=ExecutionConfig.SIGNAL_COOLDOWN_MINUTES,
        )
        return any(trade.get("status") in {"open", "closed"} for trade in recent_trades)

    def _check_signal_freshness(self, signal: Signal, session: str) -> str:
        try:
            quote = self.client.get_latest_quote(signal.symbol)
        except Exception as exc:
            return f"latest quote unavailable: {exc}"

        mid = (quote["bid"] + quote["ask"]) / 2
        if mid <= 0 or signal.entry_price <= 0:
            return ""

        atr = float(signal.indicators.get("atr", 0) or 0)
        atr_pct = atr / signal.entry_price if signal.entry_price else 0
        base_thresholds = {
            "opening": ExecutionConfig.STALE_SIGNAL_OPENING_PCT,
            "midday": ExecutionConfig.STALE_SIGNAL_MIDDAY_PCT,
            "power_hour": ExecutionConfig.STALE_SIGNAL_POWER_HOUR_PCT,
        }
        threshold = base_thresholds.get(session, ExecutionConfig.STALE_SIGNAL_MIDDAY_PCT)
        threshold += atr_pct * ExecutionConfig.STALE_SIGNAL_ATR_MULTIPLIER

        move_pct = abs(mid - signal.entry_price) / signal.entry_price
        if move_pct > threshold:
            return (
                f"signal stale: market moved {move_pct:.2%} "
                f"> allowed {threshold:.2%}"
            )
        return ""

    def _check_market_microstructure(self, signal: Signal) -> str:
        try:
            quote = self.client.get_latest_quote(signal.symbol)
        except Exception as exc:
            return f"quote unavailable: {exc}"

        spread_pct = float(quote.get("spread_pct", 0) or 0)
        if spread_pct > ExecutionConfig.MAX_SPREAD_PCT:
            return (
                f"spread too wide: {spread_pct:.2%} "
                f"> {ExecutionConfig.MAX_SPREAD_PCT:.2%}"
            )

        bar_volume = float(signal.indicators.get("volume", 0) or 0)
        dollar_volume = bar_volume * signal.entry_price
        if dollar_volume and dollar_volume < ExecutionConfig.MIN_DOLLAR_VOLUME:
            return (
                f"dollar volume too low: ${dollar_volume:,.0f} "
                f"< ${ExecutionConfig.MIN_DOLLAR_VOLUME:,.0f}"
            )

        mid = (quote["bid"] + quote["ask"]) / 2
        slippage_pct = abs(mid - signal.entry_price) / signal.entry_price if signal.entry_price else 0
        if slippage_pct > ExecutionConfig.MAX_SLIPPAGE_PCT:
            return (
                f"slippage too high: {slippage_pct:.2%} "
                f"> {ExecutionConfig.MAX_SLIPPAGE_PCT:.2%}"
            )
        return ""

    def _submit_order(self, signal: Signal, shares: int) -> Optional[dict]:
        """
        Submit an order to Alpaca.

        Uses market orders for simplicity and speed.
        Sets bracket order with stop loss and take profit.
        """
        try:
            from alpaca.trading.requests import (
                MarketOrderRequest,
                OrderSide,
                TimeInForce,
            )

            side = OrderSide.BUY if signal.type == SignalType.BUY else OrderSide.SELL

            # Simple market order (we manage SL/TP ourselves for more control)
            order_data = MarketOrderRequest(
                symbol=signal.symbol,
                qty=shares,
                side=side,
                time_in_force=TimeInForce.DAY,
            )

            order = self.client.trading.submit_order(order_data)

            logger.info(
                f"Order submitted: {order.id} {side.value} {shares} {signal.symbol}"
            )

            return {
                "id": str(order.id),
                "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
                "symbol": order.symbol,
                "qty": shares,
                "side": side.value,
            }

        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            return None

    # ============================================================
    # Position Management
    # ============================================================

    def check_open_positions(self) -> list[dict]:
        """
        Check all open positions for stop loss / take profit hits.
        Returns list of positions that need to be closed.
        """
        open_trades = self.memory.get_open_trades()
        positions_to_close = []

        for trade in open_trades:
            symbol = trade["symbol"]
            try:
                # Get current price
                quote = self.client.get_latest_quote(symbol)
                current_price = (quote["bid"] + quote["ask"]) / 2  # Mid price

                stop_loss = trade.get("stop_loss_price", 0)
                take_profit = trade.get("take_profit_price", 0)
                side = trade.get("side", "long")

                close_reason = None

                if side == "long":
                    if stop_loss > 0 and current_price <= stop_loss:
                        close_reason = "stop_loss"
                    elif take_profit > 0 and current_price >= take_profit:
                        close_reason = "take_profit"
                else:  # short
                    if stop_loss > 0 and current_price >= stop_loss:
                        close_reason = "stop_loss"
                    elif take_profit > 0 and current_price <= take_profit:
                        close_reason = "take_profit"

                if close_reason:
                    positions_to_close.append({
                        "trade": trade,
                        "current_price": current_price,
                        "reason": close_reason,
                    })

            except Exception as e:
                logger.error(f"Error checking position {symbol}: {e}")

        return positions_to_close

    def close_position(self, trade: dict, exit_price: float,
                       exit_reason: str) -> Optional[dict]:
        """
        Close a specific position.

        Args:
            trade: The trade record from memory
            exit_price: Current price
            exit_reason: Why we're closing (stop_loss, take_profit, signal, eod)

        Returns:
            Updated trade record, or None on failure
        """
        symbol = trade["symbol"]
        qty = trade["quantity"]
        side = trade.get("side", "long")

        try:
            from alpaca.trading.requests import (
                MarketOrderRequest,
                OrderSide,
                TimeInForce,
            )

            # Close = opposite side
            close_side = OrderSide.SELL if side == "long" else OrderSide.BUY

            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=int(abs(qty)),
                side=close_side,
                time_in_force=TimeInForce.DAY,
            )

            order = self.client.trading.submit_order(order_data)

            # Calculate P&L
            entry_price = trade["entry_price"]
            if side == "long":
                pnl = (exit_price - entry_price) * qty
            else:
                pnl = (entry_price - exit_price) * qty

            pnl_pct = pnl / (entry_price * qty) if entry_price * qty > 0 else 0

            # Calculate hold time
            entry_time = datetime.fromisoformat(trade["timestamp"])
            hold_minutes = (datetime.now() - entry_time).total_seconds() / 60

            # Update in memory
            try:
                self.memory.close_trade(
                    trade_id=trade["id"],
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 4),
                    hold_minutes=round(hold_minutes, 1),
                )
            except Exception as db_error:
                logger.error(
                    f"CRITICAL: Trade closed in Alpaca (order #{order.id}) "
                    f"for {symbol} but FAILED to update database: {db_error}",
                    exc_info=True
                )
                # Re-raise so caller knows about the DB failure
                raise

            emoji = "✅" if pnl > 0 else "❌"
            logger.info(
                f"{emoji} TRADE CLOSED #{trade['id']}: {trade['strategy']} "
                f"{symbol} | {exit_reason} | P&L: ${pnl:.2f} ({pnl_pct:.2%}) | "
                f"Hold: {hold_minutes:.0f}min"
            )

            # Update scores after every closed trade
            self._update_scores_after_close(trade["strategy"])

            # Send Telegram notification
            close_result = {
                "trade_id": trade["id"],
                "symbol": symbol,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 4),
                "exit_reason": exit_reason,
                "hold_minutes": round(hold_minutes, 1),
            }
            self.notifier.notify_trade_closed(close_result)

            return close_result

        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}", exc_info=True)
            return None

    def close_all_positions(self, reason: str = "eod") -> list[dict]:
        """
        Close ALL open positions. Used for:
        - End of day (15:50 ET)
        - Daily loss limit hit
        - Manual stop

        Returns list of closed trade results.
        """
        results = []
        open_trades = self.memory.get_open_trades()

        if not open_trades:
            logger.info("No open positions to close")
            return results

        logger.warning(f"CLOSING ALL {len(open_trades)} POSITIONS: {reason}")

        for trade in open_trades:
            try:
                # Get current price
                quote = self.client.get_latest_quote(trade["symbol"])
                current_price = (quote["bid"] + quote["ask"]) / 2

                result = self.close_position(trade, current_price, reason)
                if result:
                    results.append(result)

            except Exception as e:
                logger.error(f"Failed to close {trade['symbol']}: {e}")
                # Try Alpaca's close-all as fallback
                try:
                    self.client.trading.close_all_positions(cancel_orders=True)
                    logger.info("Used Alpaca close_all_positions as fallback")
                except Exception as e2:
                    logger.error(f"Fallback close failed too: {e2}")

        total_pnl = sum(r.get("pnl", 0) for r in results)
        logger.info(
            f"Closed {len(results)} positions. Total P&L: ${total_pnl:.2f}"
        )

        # Send Telegram summary
        if results:
            self.notifier.notify_all_closed(results, reason)

        return results

    def _update_scores_after_close(self, strategy_name: str):
        """Update strategy scores after a trade is closed."""
        try:
            all_strategies = self.scorer.get_all_strategy_names()
            if strategy_name not in all_strategies:
                all_strategies.append(strategy_name)

            # Recalculate scores
            scores_result = self.scorer.update_scores(all_strategies)

            # Recalculate allocation
            scores = {name: r["score"] for name, r in scores_result.items()}
            allocation = self.allocator.allocate(scores)
            self.allocator.save_allocation(allocation, scores)

            logger.info(f"Scores updated after closing {strategy_name} trade")

        except Exception as e:
            logger.error(f"Failed to update scores: {e}")

    # ============================================================
    # Status
    # ============================================================

    def get_status(self) -> dict:
        """Get current trading status."""
        try:
            account = self.client.get_account()
            positions = self.client.get_positions()
            account_connected = True
        except Exception:
            from agent.config import INITIAL_CAPITAL
            account = {
                "portfolio_value": INITIAL_CAPITAL,
                "cash": INITIAL_CAPITAL,
                "buying_power": INITIAL_CAPITAL,
            }
            positions = []
            account_connected = False

        open_trades = self.memory.get_open_trades()
        today_pnl = self.memory.get_today_pnl()
        today_trades = self.memory.get_today_trade_count()

        return {
            "portfolio_value": account.get("portfolio_value", 0),
            "cash": account.get("cash", 0),
            "buying_power": account.get("buying_power", 0),
            "open_positions": len(positions),
            "open_trades_in_memory": len(open_trades),
            "today_pnl": round(today_pnl, 2),
            "today_trade_count": today_trades,
            "account_connected": account_connected,
        }
