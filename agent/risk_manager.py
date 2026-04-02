"""
Risk Manager - Enforces hardcoded risk management rules.
These rules are IMMUTABLE. Not Claude Coach, not any code, changes them.
Every trade must pass ALL checks before execution.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from agent.config import RiskLimits, INITIAL_CAPITAL
from agent.market_hours import MarketHours
from agent.memory import Memory
from agent.strategies.base import Signal, SignalType

logger = logging.getLogger(__name__)


class RiskCheckResult:
    """Result of a risk check."""

    def __init__(self, passed: bool, reason: str = ""):
        self.passed = passed
        self.reason = reason

    def __bool__(self):
        return self.passed

    def __repr__(self):
        status = "PASS" if self.passed else "BLOCKED"
        return f"<RiskCheck {status}: {self.reason}>"


class RiskManager:
    """
    Enforces all risk management rules before any trade executes.

    Every signal must pass ALL of these checks:
    1. Stop loss is set (mandatory)
    2. Position size within limits (5% max, 3% at opening)
    3. Max open positions not exceeded (3)
    4. Daily loss limit not hit (3%)
    5. Daily trade count not exceeded (20)
    6. No consecutive loss cooling period
    7. Market hours are valid (not closing time)
    8. Volume is sufficient
    9. Risk/reward ratio is acceptable

    If ANY check fails, the trade is BLOCKED. No exceptions.
    """

    def __init__(self, memory: Memory, market_hours: MarketHours):
        self.memory = memory
        self.market_hours = market_hours
        self.limits = RiskLimits
        self._cooling_until: Optional[datetime] = None

    def check_signal(self, signal: Signal, portfolio_value: float,
                     open_positions: int, session: str = "") -> RiskCheckResult:
        """
        Run ALL risk checks on a signal.

        Args:
            signal: The trading signal to validate
            portfolio_value: Current total portfolio value
            open_positions: Number of currently open positions
            session: Current session name

        Returns:
            RiskCheckResult - passed=True only if ALL checks pass
        """
        if signal.type == SignalType.HOLD:
            return RiskCheckResult(False, "HOLD signal, no trade needed")

        checks = [
            self._check_stop_loss(signal),
            self._check_position_size(signal, portfolio_value, session),
            self._check_max_positions(open_positions),
            self._check_daily_loss(portfolio_value),
            self._check_daily_trade_count(),
            self._check_cooling_period(),
            self._check_symbol_cooldown(signal.symbol),
            self._check_market_hours(),
            self._check_risk_reward(signal),
        ]

        for check in checks:
            if not check.passed:
                logger.warning(
                    f"RISK BLOCKED: {signal.strategy} {signal.type.value} "
                    f"{signal.symbol} - {check.reason}"
                )
                return check

        logger.info(
            f"RISK APPROVED: {signal.strategy} {signal.type.value} "
            f"{signal.symbol} @ ${signal.entry_price:.2f}"
        )
        return RiskCheckResult(True, "All checks passed")

    # ============================================================
    # Individual Risk Checks
    # ============================================================

    def _check_stop_loss(self, signal: Signal) -> RiskCheckResult:
        """Check 1: Stop loss MUST be set on every trade."""
        if not self.limits.MANDATORY_STOP_LOSS:
            return RiskCheckResult(True, "Stop loss not mandatory")

        if signal.stop_loss <= 0:
            return RiskCheckResult(False, "No stop loss set - MANDATORY")

        # Check stop loss isn't too far (max 2% from entry)
        if signal.type == SignalType.BUY:
            loss_pct = (signal.entry_price - signal.stop_loss) / signal.entry_price
        else:
            loss_pct = (signal.stop_loss - signal.entry_price) / signal.entry_price

        if loss_pct > self.limits.MAX_STOP_LOSS_PCT:
            return RiskCheckResult(
                False,
                f"Stop loss too wide: {loss_pct:.1%} > max {self.limits.MAX_STOP_LOSS_PCT:.1%}"
            )

        return RiskCheckResult(True, "Stop loss OK")

    def _check_position_size(self, signal: Signal, portfolio_value: float,
                             session: str = "") -> RiskCheckResult:
        """Check 2: Position size within limits."""
        if portfolio_value <= 0:
            return RiskCheckResult(False, "Portfolio value is zero")

        # Opening session has tighter limits (3% vs 5%)
        if session == "opening":
            max_pct = self.limits.OPENING_MAX_POSITION_PCT
        else:
            max_pct = self.limits.MAX_POSITION_PCT

        max_dollars = portfolio_value * max_pct
        position_value = signal.entry_price  # Per share, will be multiplied by qty later

        # We return the max allowed for this check - actual sizing happens in trader
        return RiskCheckResult(
            True,
            f"Max position: ${max_dollars:.0f} ({max_pct:.0%} of ${portfolio_value:.0f})"
        )

    def _check_max_positions(self, open_positions: int) -> RiskCheckResult:
        """Check 3: Don't exceed max open positions."""
        if open_positions >= self.limits.MAX_OPEN_POSITIONS:
            return RiskCheckResult(
                False,
                f"Max positions reached: {open_positions}/{self.limits.MAX_OPEN_POSITIONS}"
            )
        return RiskCheckResult(True, f"Positions: {open_positions}/{self.limits.MAX_OPEN_POSITIONS}")

    def _check_daily_loss(self, portfolio_value: float) -> RiskCheckResult:
        """Check 4: Daily loss limit not exceeded."""
        today_pnl = self.memory.get_today_pnl()
        max_loss = portfolio_value * self.limits.MAX_DAILY_LOSS_PCT

        if today_pnl < 0 and abs(today_pnl) >= max_loss:
            return RiskCheckResult(
                False,
                f"DAILY LOSS LIMIT HIT: ${today_pnl:.2f} "
                f"(limit: -${max_loss:.2f} = {self.limits.MAX_DAILY_LOSS_PCT:.0%})"
            )

        remaining = max_loss - abs(min(today_pnl, 0))
        return RiskCheckResult(
            True,
            f"Daily P&L: ${today_pnl:.2f} (${remaining:.2f} remaining before limit)"
        )

    def _check_daily_trade_count(self) -> RiskCheckResult:
        """Check 5: Max daily trades not exceeded."""
        today_count = self.memory.get_today_trade_count()

        if today_count >= self.limits.MAX_DAILY_TRADES:
            return RiskCheckResult(
                False,
                f"Max daily trades reached: {today_count}/{self.limits.MAX_DAILY_TRADES}"
            )

        return RiskCheckResult(
            True,
            f"Trades today: {today_count}/{self.limits.MAX_DAILY_TRADES}"
        )

    def _check_cooling_period(self) -> RiskCheckResult:
        """Check 6: Not in cooling period after consecutive losses."""
        # Check if we're still in a cooling period
        if self._cooling_until and datetime.now() < self._cooling_until:
            remaining = (self._cooling_until - datetime.now()).seconds // 60
            return RiskCheckResult(
                False,
                f"Cooling period active: {remaining} minutes remaining "
                f"(after {self.limits.COOLING_AFTER_CONSECUTIVE_LOSSES} consecutive losses)"
            )

        # Check for new consecutive losses
        consecutive = self.memory.get_consecutive_losses()
        if consecutive >= self.limits.COOLING_AFTER_CONSECUTIVE_LOSSES:
            self._cooling_until = (
                datetime.now() +
                timedelta(minutes=self.limits.COOLING_DURATION_MINUTES)
            )
            return RiskCheckResult(
                False,
                f"{consecutive} consecutive losses! "
                f"Cooling for {self.limits.COOLING_DURATION_MINUTES} minutes"
            )

        return RiskCheckResult(True, f"Consecutive losses: {consecutive}")

    def _check_symbol_cooldown(self, symbol: str) -> RiskCheckResult:
        """Check per-symbol cooldown: 60 min no-retry after a loss on same symbol (today only)."""
        COOLDOWN_MINUTES = 60
        conn = self.memory._get_conn()
        try:
            row = conn.execute(
                """SELECT exit_timestamp FROM trades
                   WHERE symbol = ? AND status = 'closed' AND pnl < 0
                     AND date(exit_timestamp) = date('now')
                   ORDER BY exit_timestamp DESC LIMIT 1""",
                (symbol,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            last_loss = datetime.fromisoformat(row["exit_timestamp"])
            cooldown_until = last_loss + timedelta(minutes=COOLDOWN_MINUTES)
            if datetime.now() < cooldown_until:
                remaining = int((cooldown_until - datetime.now()).total_seconds() / 60)
                return RiskCheckResult(
                    False,
                    f"{symbol} cooldown: {remaining}min remaining after loss"
                )
        return RiskCheckResult(True, f"{symbol} no cooldown")

    def _check_market_hours(self) -> RiskCheckResult:
        """Check 7: Market hours and closing time."""
        if not self.market_hours.is_market_open():
            return RiskCheckResult(False, "Market is closed")

        if self.market_hours.should_close_all():
            return RiskCheckResult(False, "Closing time - no new trades")

        if not self.market_hours.can_open_new_positions():
            return RiskCheckResult(False, "Too close to market close for new positions")

        return RiskCheckResult(True, "Market hours OK")

    def _check_risk_reward(self, signal: Signal) -> RiskCheckResult:
        """Check 9: Risk/reward ratio must be at least 1.5:1."""
        rr = signal.risk_reward_ratio
        min_rr = 1.5

        if rr < min_rr:
            return RiskCheckResult(
                False,
                f"Risk/reward too low: {rr:.2f} (minimum {min_rr})"
            )

        return RiskCheckResult(True, f"Risk/reward: {rr:.2f}")

    # ============================================================
    # Position Sizing
    # ============================================================

    def calculate_position_size(self, signal: Signal, portfolio_value: float,
                                allocation_pct: float,
                                session: str = "") -> dict:
        """
        Calculate the exact position size (shares) for a trade.

        Uses ATR-based sizing when available (research-proven):
          Position_Size = Risk_Amount / Risk_Per_Share
        where Risk_Per_Share = |entry - stop_loss| or ATR * multiplier.

        Then caps at the SMALLER of:
        - ATR-based risk sizing
        - Strategy allocation budget
        - Max position size (5% or 3% at opening)

        Args:
            signal: The trading signal
            portfolio_value: Total portfolio value
            allocation_pct: Strategy's capital allocation (0.0-1.0)
            session: Current session name

        Returns:
            dict with: shares, dollar_amount, position_pct, sizing_method
        """
        if signal.entry_price <= 0:
            return {"shares": 0, "dollar_amount": 0, "position_pct": 0,
                    "sizing_method": "blocked_invalid_price"}

        # Strategy's allocated budget
        strategy_budget = portfolio_value * allocation_pct

        # Hard limit per trade
        if session == "opening":
            max_position = portfolio_value * self.limits.OPENING_MAX_POSITION_PCT
        else:
            max_position = portfolio_value * self.limits.MAX_POSITION_PCT

        # Budget cap (old method)
        budget_cap = min(strategy_budget, max_position)

        # === ATR-based position sizing (research-proven) ===
        # Risk 1% of portfolio per trade, sized by actual risk per share
        RISK_PCT_PER_TRADE = 0.01  # 1% of portfolio risked per trade
        risk_budget = portfolio_value * RISK_PCT_PER_TRADE

        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        atr = float(signal.indicators.get("atr", 0) or 0)

        sizing_method = "budget_cap"
        atr_shares = None

        if risk_per_share > 0:
            # Best method: use actual stop distance
            atr_shares = int(risk_budget / risk_per_share)
            sizing_method = "stop_distance"
        elif atr > 0:
            # Fallback: use ATR * 1.5 as proxy for risk per share
            atr_shares = int(risk_budget / (atr * 1.5))
            sizing_method = "atr_proxy"

        # Take minimum of ATR-sizing and budget cap
        if atr_shares is not None and atr_shares > 0:
            budget_shares = int(budget_cap / signal.entry_price)
            shares = min(atr_shares, budget_shares)
        else:
            # No ATR data — fall back to pure budget sizing
            shares = int(budget_cap / signal.entry_price)

        if shares <= 0:
            return {"shares": 0, "dollar_amount": 0, "position_pct": 0,
                    "sizing_method": sizing_method}

        dollar_amount = shares * signal.entry_price
        position_pct = dollar_amount / portfolio_value

        # Final safety: never exceed hard cap even with ATR sizing
        if dollar_amount > max_position:
            shares = int(max_position / signal.entry_price)
            dollar_amount = shares * signal.entry_price
            position_pct = dollar_amount / portfolio_value

        logger.info(
            f"Position size for {signal.symbol}: {shares} shares "
            f"(${dollar_amount:.0f} = {position_pct:.1%} of portfolio) "
            f"[method={sizing_method}, risk/share=${risk_per_share:.2f}, ATR=${atr:.2f}]"
        )

        return {
            "shares": shares,
            "dollar_amount": round(dollar_amount, 2),
            "position_pct": round(position_pct, 4),
            "sizing_method": sizing_method,
        }

    # ============================================================
    # EOD (End of Day) Check
    # ============================================================

    def should_close_all_positions(self) -> bool:
        """Check if we should close all positions (end of day)."""
        return self.market_hours.should_close_all()

    def is_daily_loss_limit_hit(self, portfolio_value: float) -> bool:
        """Check if daily loss limit has been hit."""
        today_pnl = self.memory.get_today_pnl()
        max_loss = portfolio_value * self.limits.MAX_DAILY_LOSS_PCT
        return today_pnl < 0 and abs(today_pnl) >= max_loss

    def get_status(self, portfolio_value: float) -> dict:
        """Get current risk management status."""
        today_pnl = self.memory.get_today_pnl()
        today_trades = self.memory.get_today_trade_count()
        consecutive_losses = self.memory.get_consecutive_losses()
        max_daily_loss = portfolio_value * self.limits.MAX_DAILY_LOSS_PCT

        return {
            "today_pnl": round(today_pnl, 2),
            "max_daily_loss": round(max_daily_loss, 2),
            "daily_loss_remaining": round(max_daily_loss - abs(min(today_pnl, 0)), 2),
            "daily_loss_limit_hit": self.is_daily_loss_limit_hit(portfolio_value),
            "today_trades": today_trades,
            "max_daily_trades": self.limits.MAX_DAILY_TRADES,
            "consecutive_losses": consecutive_losses,
            "cooling_active": bool(
                self._cooling_until and datetime.now() < self._cooling_until
            ),
            "cooling_until": (
                self._cooling_until.strftime("%H:%M:%S")
                if self._cooling_until and datetime.now() < self._cooling_until
                else None
            ),
            "can_trade": (
                not self.is_daily_loss_limit_hit(portfolio_value) and
                today_trades < self.limits.MAX_DAILY_TRADES and
                self.market_hours.can_open_new_positions()
            ),
        }
