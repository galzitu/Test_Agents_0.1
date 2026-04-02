"""
Backtester - Simulates the trading agent on historical data.

Runs the actual strategy code bar-by-bar on historical OHLCV data,
applying realistic risk management (stop loss, take profit, EOD close).

Usage:
    python -m agent.backtest --days 30
    python -m agent.backtest --start 2025-01-01 --end 2025-03-01
    python -m agent.backtest --strategy rsi_macd --days 60
"""

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
import math

import pandas as pd
import numpy as np

from agent.config import LOGS_DIR, STRATEGIES_CONFIG_DIR, INITIAL_CAPITAL
from agent.market_data import AlpacaClient, IndicatorCalculator
from agent.market_condition import MarketConditionDetector
from agent.market_hours import MarketHours
from agent.strategies.selector import StrategySelector
from agent.strategies.base import SignalType

logger = logging.getLogger(__name__)

# Default symbols for backtest
DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

EOD_CLOSE_HOUR = 15
EOD_CLOSE_MIN = 50


# ============================================================
# Data Classes
# ============================================================

@dataclass
class BacktestTrade:
    """A simulated trade in the backtest."""
    trade_id: int
    strategy: str
    symbol: str
    side: str               # "long" or "short"
    entry_time: datetime
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    session: str = ""
    market_condition: str = ""
    confidence: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_price is None

    def close(self, exit_time: datetime, exit_price: float, reason: str):
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        if self.side == "long":
            self.pnl = (exit_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity
        cost = self.entry_price * self.quantity
        self.pnl_pct = (self.pnl / cost) * 100 if cost > 0 else 0


@dataclass
class DaySummary:
    """Summary stats for one backtest day."""
    date: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    starting_capital: float = 0.0
    ending_capital: float = 0.0
    max_drawdown_day: float = 0.0
    sessions: dict = field(default_factory=dict)
    conditions: list = field(default_factory=list)


@dataclass
class BacktestResults:
    """Complete backtest results."""
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    trades: list[BacktestTrade] = field(default_factory=list)
    daily: list[DaySummary] = field(default_factory=list)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def closed_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if not t.is_open]

    @property
    def wins(self) -> int:
        return sum(1 for t in self.closed_trades if t.pnl > 0)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.closed_trades if t.pnl <= 0)

    @property
    def win_rate(self) -> float:
        ct = len(self.closed_trades)
        return self.wins / ct if ct > 0 else 0.0

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.closed_trades)

    @property
    def total_return_pct(self) -> float:
        return (self.total_pnl / self.initial_capital) * 100

    @property
    def avg_win(self) -> float:
        w = [t.pnl for t in self.closed_trades if t.pnl > 0]
        return sum(w) / len(w) if w else 0

    @property
    def avg_loss(self) -> float:
        l = [t.pnl for t in self.closed_trades if t.pnl <= 0]
        return sum(l) / len(l) if l else 0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl for t in self.closed_trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.closed_trades if t.pnl < 0))
        return gross_win / gross_loss if gross_loss > 0 else float("inf")

    @property
    def max_drawdown(self) -> float:
        """Max peak-to-trough drawdown in dollars."""
        equity = self.initial_capital
        peak = equity
        max_dd = 0.0
        for t in sorted(self.closed_trades, key=lambda x: x.exit_time or datetime.min):
            equity += t.pnl
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def sharpe_ratio(self) -> float:
        """Simplified daily Sharpe ratio."""
        if not self.daily:
            return 0.0
        daily_pnl = [d.total_pnl for d in self.daily if d.total_trades > 0]
        if len(daily_pnl) < 2:
            return 0.0
        mean = sum(daily_pnl) / len(daily_pnl)
        variance = sum((x - mean) ** 2 for x in daily_pnl) / len(daily_pnl)
        std = math.sqrt(variance)
        return (mean / std) * math.sqrt(252) if std > 0 else 0.0

    def by_strategy(self) -> dict:
        """Performance stats grouped by strategy."""
        result = {}
        for t in self.closed_trades:
            s = t.strategy
            if s not in result:
                result[s] = {"trades": 0, "wins": 0, "pnl": 0.0, "pnl_pct_sum": 0.0}
            result[s]["trades"] += 1
            if t.pnl > 0:
                result[s]["wins"] += 1
            result[s]["pnl"] += t.pnl
            result[s]["pnl_pct_sum"] += t.pnl_pct
        for s, v in result.items():
            v["win_rate"] = v["wins"] / v["trades"] if v["trades"] > 0 else 0
            v["avg_pnl_pct"] = v["pnl_pct_sum"] / v["trades"] if v["trades"] > 0 else 0
        return result

    def by_session(self) -> dict:
        """Performance grouped by trading session."""
        result = {}
        for t in self.closed_trades:
            s = t.session or "unknown"
            if s not in result:
                result[s] = {"trades": 0, "wins": 0, "pnl": 0.0}
            result[s]["trades"] += 1
            if t.pnl > 0:
                result[s]["wins"] += 1
            result[s]["pnl"] += t.pnl
        for s, v in result.items():
            v["win_rate"] = v["wins"] / v["trades"] if v["trades"] > 0 else 0
        return result


# ============================================================
# Backtester Engine
# ============================================================

class Backtester:
    """
    Simulates the trading agent on historical data.

    Key design:
    - Uses real strategy code (no duplication)
    - Bar-by-bar simulation
    - Realistic stop loss / take profit
    - EOD force close at 15:50
    - Risk management: max 3 positions, max 5% per trade
    - Capital tracking with compounding
    """

    MIN_CONFIDENCE = 0.5
    MAX_POSITIONS = 3
    POSITION_SIZE_PCT = 0.03      # 3% per trade (conservative)
    MAX_POSITION_PCT = 0.05       # 5% max per position
    MAX_DAILY_LOSS_PCT = 0.03     # 3% daily loss limit
    COMMISSION_PER_SHARE = 0.0    # Alpaca is commission-free

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.client = AlpacaClient()
        self.indicator_calc = IndicatorCalculator()
        self.condition_detector = MarketConditionDetector()
        self.market_hours = MarketHours()
        self.selector = StrategySelector()
        self._trade_id_counter = 0

    def _next_trade_id(self) -> int:
        self._trade_id_counter += 1
        return self._trade_id_counter

    def run(
        self,
        start_date: date,
        end_date: date,
        symbols: list[str] = None,
        strategy_filter: Optional[str] = None,
    ) -> BacktestResults:
        """
        Run the full backtest for a date range.

        Args:
            start_date: First date to simulate
            end_date: Last date to simulate (inclusive)
            symbols: List of symbols to trade (default: DEFAULT_SYMBOLS)
            strategy_filter: Only use this strategy (None = all)
        """
        symbols = symbols or DEFAULT_SYMBOLS
        logger.info(f"Starting backtest: {start_date} → {end_date}")
        logger.info(f"Symbols: {symbols}")
        logger.info(f"Capital: ${self.initial_capital:,.0f}")

        results = BacktestResults(
            start_date=str(start_date),
            end_date=str(end_date),
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital,
        )

        # Fetch all data upfront (more efficient than per-day fetching)
        logger.info("Fetching historical data...")
        data_cache = self._fetch_all_data(symbols, start_date, end_date)

        capital = self.initial_capital
        trading_days = self._get_trading_days(start_date, end_date)
        logger.info(f"Trading days to simulate: {len(trading_days)}")

        for trading_day in trading_days:
            day_summary, day_trades, capital = self._simulate_day(
                trading_day, symbols, data_cache, capital, strategy_filter
            )
            results.daily.append(day_summary)
            results.trades.extend(day_trades)

            pnl_str = f"+${day_summary.total_pnl:.0f}" if day_summary.total_pnl >= 0 else f"-${abs(day_summary.total_pnl):.0f}"
            logger.info(
                f"{trading_day}: {day_summary.total_trades} trades, "
                f"{day_summary.wins}W/{day_summary.losses}L, "
                f"P&L: {pnl_str}, Capital: ${capital:,.0f}"
            )

        results.final_capital = capital
        return results

    def _fetch_all_data(
        self, symbols: list[str], start_date: date, end_date: date
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch 5-minute bars for all symbols over the full date range.
        Returns dict: symbol → DataFrame with all bars.
        """
        data_cache = {}

        # Add 5 extra days for indicator warmup
        fetch_start = start_date - timedelta(days=7)

        for symbol in symbols:
            try:
                logger.debug(f"Fetching {symbol}...")
                df = self._fetch_symbol_history(symbol, fetch_start, end_date)
                if df is not None and len(df) > 30:
                    df = self.indicator_calc.add_all_indicators(df)
                    data_cache[symbol] = df
                    logger.debug(f"{symbol}: {len(df)} bars")
                else:
                    logger.warning(f"{symbol}: insufficient data, skipping")
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")

        logger.info(f"Data fetched for {len(data_cache)}/{len(symbols)} symbols")
        return data_cache

    def _fetch_symbol_history(
        self, symbol: str, start_date: date, end_date: date
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV bars for a symbol over a date range."""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute * 5,
                start=datetime.combine(start_date, datetime.min.time()),
                end=datetime.combine(end_date, datetime.max.time()),
                adjustment="raw",
            )
            bars = self.client.data.get_stock_bars(request)
            df = bars.df

            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol, level=0)

            df = df.reset_index()
            df = df.rename(columns={"timestamp": "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.sort_values("timestamp")
            return df
        except Exception as e:
            logger.warning(f"Error fetching history for {symbol}: {e}")
            return None

    def _get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """Get list of trading days (skip weekends)."""
        days = []
        current = start_date
        while current <= end_date:
            # Skip weekends (basic check; doesn't skip holidays)
            if current.weekday() < 5:  # Mon=0, Fri=4
                days.append(current)
            current += timedelta(days=1)
        return days

    def _get_session_for_time(self, t: datetime) -> str:
        """Map a timestamp to a trading session."""
        hour = t.hour
        minute = t.minute
        total_min = hour * 60 + minute

        if total_min < 9 * 60 + 30:
            return "pre_market"
        elif total_min < 10 * 60 + 30:
            return "opening"
        elif total_min < 14 * 60 + 30:
            return "midday"
        elif total_min < 16 * 60:
            return "power_hour"
        else:
            return "post_market"

    def _simulate_day(
        self,
        trading_day: date,
        symbols: list[str],
        data_cache: dict[str, pd.DataFrame],
        starting_capital: float,
        strategy_filter: Optional[str],
    ) -> tuple[DaySummary, list[BacktestTrade], float]:
        """
        Simulate one trading day bar by bar.
        Returns (day_summary, trades, ending_capital).
        """
        summary = DaySummary(
            date=str(trading_day),
            starting_capital=starting_capital,
        )
        day_trades: list[BacktestTrade] = []
        open_positions: list[BacktestTrade] = []
        capital = starting_capital
        daily_loss_limit = starting_capital * self.MAX_DAILY_LOSS_PCT
        daily_pnl = 0.0
        eod_time = trading_day.replace if False else None  # Will compute below

        # Get all 5-min bars for this day, for SPY (market condition reference)
        spy_day_bars = self._filter_day_bars(data_cache.get("SPY"), trading_day)
        if spy_day_bars is None or len(spy_day_bars) < 5:
            summary.ending_capital = capital
            return summary, day_trades, capital

        # Get unique bar timestamps for this day
        all_timestamps = sorted(spy_day_bars["timestamp"].unique())

        # Keep only market hours (9:30 - 16:00 ET)
        market_timestamps = [
            t for t in all_timestamps
            if (t.hour > 9 or (t.hour == 9 and t.minute >= 30))
            and (t.hour < 16)
        ]

        conditions_seen = set()

        for bar_time in market_timestamps:
            # ---- EOD close ----
            if bar_time.hour > EOD_CLOSE_HOUR or (
                bar_time.hour == EOD_CLOSE_HOUR and bar_time.minute >= EOD_CLOSE_MIN
            ):
                for pos in list(open_positions):
                    exit_price = self._get_bar_close(data_cache.get(pos.symbol), bar_time)
                    if exit_price:
                        pos.close(bar_time, exit_price, "eod")
                        pnl = pos.pnl
                        daily_pnl += pnl
                        capital += pnl
                        open_positions.remove(pos)
                break

            # ---- Daily loss limit ----
            if daily_pnl < -daily_loss_limit:
                # Close all and stop trading today
                for pos in list(open_positions):
                    exit_price = self._get_bar_close(data_cache.get(pos.symbol), bar_time)
                    if exit_price:
                        pos.close(bar_time, exit_price, "daily_loss_limit")
                        daily_pnl += pos.pnl
                        capital += pos.pnl
                        open_positions.remove(pos)
                break

            # ---- Check SL/TP for open positions ----
            for pos in list(open_positions):
                symbol_bars = data_cache.get(pos.symbol)
                bar = self._get_bar_at(symbol_bars, bar_time)
                if bar is None:
                    continue

                if pos.side == "long":
                    if bar["low"] <= pos.stop_loss:
                        pos.close(bar_time, pos.stop_loss, "stop_loss")
                        daily_pnl += pos.pnl
                        capital += pos.pnl
                        open_positions.remove(pos)
                    elif bar["high"] >= pos.take_profit:
                        pos.close(bar_time, pos.take_profit, "take_profit")
                        daily_pnl += pos.pnl
                        capital += pos.pnl
                        open_positions.remove(pos)
                else:  # short
                    if bar["high"] >= pos.stop_loss:
                        pos.close(bar_time, pos.stop_loss, "stop_loss")
                        daily_pnl += pos.pnl
                        capital += pos.pnl
                        open_positions.remove(pos)
                    elif bar["low"] <= pos.take_profit:
                        pos.close(bar_time, pos.take_profit, "take_profit")
                        daily_pnl += pos.pnl
                        capital += pos.pnl
                        open_positions.remove(pos)

            # ---- Skip if max positions reached ----
            if len(open_positions) >= self.MAX_POSITIONS:
                continue

            # ---- Session check ----
            session = self._get_session_for_time(bar_time)
            if session not in ("opening", "midday", "power_hour"):
                continue

            # ---- Market condition (from SPY data up to this bar) ----
            spy_slice = self._get_bars_up_to(data_cache.get("SPY"), bar_time, 100)
            if spy_slice is None or len(spy_slice) < 30:
                continue

            try:
                snapshot = self.indicator_calc.get_market_snapshot(spy_slice)
                condition = self.condition_detector.detect(snapshot)
                conditions_seen.add(condition.value)
                indicators = self.indicator_calc.get_latest_indicators(spy_slice)
            except Exception as e:
                logger.debug(f"Condition detection error at {bar_time}: {e}")
                continue

            # ---- Select active strategies ----
            active_strategies = self.selector.get_active_strategies(
                session, condition.value, indicators
            )
            if not active_strategies:
                continue

            # Filter by strategy name if specified
            if strategy_filter:
                active_strategies = [
                    s for s in active_strategies
                    if strategy_filter.lower() in s.name.lower()
                ]

            # ---- Generate signals for each symbol ----
            for strategy in active_strategies:
                for symbol in symbols:
                    if symbol == "SPY" and session == "midday":
                        continue  # SPY too slow in midday

                    symbol_bars = data_cache.get(symbol)
                    if symbol_bars is None:
                        continue

                    # Already in this symbol today?
                    if any(p.symbol == symbol for p in open_positions):
                        continue

                    bar_slice = self._get_bars_up_to(symbol_bars, bar_time, 100)
                    if bar_slice is None or len(bar_slice) < 30:
                        continue

                    try:
                        signal = strategy.generate_signal(bar_slice, symbol)
                    except Exception as e:
                        logger.debug(f"Strategy error {strategy.name} {symbol}: {e}")
                        continue

                    if signal.type == SignalType.HOLD:
                        continue
                    if signal.confidence < self.MIN_CONFIDENCE:
                        continue

                    # ---- Position sizing ----
                    position_value = capital * self.POSITION_SIZE_PCT
                    price = signal.entry_price
                    if price <= 0:
                        continue
                    quantity = int(position_value / price)
                    if quantity < 1:
                        continue

                    # ---- Max position check ----
                    if (quantity * price) > (capital * self.MAX_POSITION_PCT):
                        quantity = int((capital * self.MAX_POSITION_PCT) / price)

                    if quantity < 1:
                        continue

                    # ---- Open trade ----
                    trade = BacktestTrade(
                        trade_id=self._next_trade_id(),
                        strategy=strategy.name,
                        symbol=symbol,
                        side="long" if signal.type == SignalType.BUY else "short",
                        entry_time=bar_time,
                        entry_price=price,
                        quantity=quantity,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        session=session,
                        market_condition=condition.value,
                        confidence=signal.confidence,
                    )
                    open_positions.append(trade)
                    day_trades.append(trade)

                    if len(open_positions) >= self.MAX_POSITIONS:
                        break
                else:
                    continue
                break

        # Close any remaining positions at end of data
        for pos in list(open_positions):
            last_bars = data_cache.get(pos.symbol)
            if last_bars is not None:
                day_close_bars = self._filter_day_bars(last_bars, trading_day)
                if day_close_bars is not None and len(day_close_bars) > 0:
                    last_close = float(day_close_bars.iloc[-1]["close"])
                    pos.close(day_close_bars.iloc[-1]["timestamp"], last_close, "eod_fallback")
                    daily_pnl += pos.pnl
                    capital += pos.pnl

        # Build day summary
        closed_today = [t for t in day_trades if not t.is_open]
        summary.total_trades = len(day_trades)
        summary.wins = sum(1 for t in closed_today if t.pnl > 0)
        summary.losses = sum(1 for t in closed_today if t.pnl <= 0)
        summary.total_pnl = sum(t.pnl for t in closed_today)
        summary.ending_capital = capital
        summary.conditions = list(conditions_seen)

        return summary, day_trades, capital

    def _filter_day_bars(
        self, df: Optional[pd.DataFrame], trading_day: date
    ) -> Optional[pd.DataFrame]:
        """Filter DataFrame to only rows for a specific day (in ET / UTC-5)."""
        if df is None or len(df) == 0:
            return None
        mask = df["timestamp"].apply(
            lambda t: t.date() == trading_day
            if hasattr(t, "date") else False
        )
        result = df[mask].copy()
        return result if len(result) > 0 else None

    def _get_bars_up_to(
        self, df: Optional[pd.DataFrame], bar_time: datetime, limit: int
    ) -> Optional[pd.DataFrame]:
        """Get the last `limit` bars up to (and including) bar_time."""
        if df is None or len(df) == 0:
            return None
        mask = df["timestamp"] <= bar_time
        filtered = df[mask]
        if len(filtered) == 0:
            return None
        return filtered.tail(limit).reset_index(drop=True)

    def _get_bar_at(
        self, df: Optional[pd.DataFrame], bar_time: datetime
    ) -> Optional[dict]:
        """Get the OHLCV bar at a specific timestamp."""
        if df is None:
            return None
        mask = df["timestamp"] == bar_time
        rows = df[mask]
        if len(rows) == 0:
            return None
        row = rows.iloc[0]
        return {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
        }

    def _get_bar_close(
        self, df: Optional[pd.DataFrame], bar_time: datetime
    ) -> Optional[float]:
        """Get close price at or just before bar_time."""
        if df is None:
            return None
        mask = df["timestamp"] <= bar_time
        rows = df[mask]
        if len(rows) == 0:
            return None
        return float(rows.iloc[-1]["close"])


# ============================================================
# Report Generator
# ============================================================

def print_report(results: BacktestResults):
    """Print a formatted backtest report to console."""
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  BACKTEST RESULTS: {results.start_date} → {results.end_date}")
    print(sep)
    print(f"  Initial Capital:   ${results.initial_capital:>12,.2f}")
    print(f"  Final Capital:     ${results.final_capital:>12,.2f}")
    pnl = results.total_pnl
    pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
    print(f"  Total P&L:         {pnl_str:>13}")
    print(f"  Total Return:      {results.total_return_pct:>+12.2f}%")
    print(f"  Max Drawdown:      ${results.max_drawdown:>12,.2f}")
    print(f"  Sharpe Ratio:      {results.sharpe_ratio:>12.2f}")
    print()
    print(f"  Total Trades:      {results.total_trades:>12}")
    print(f"  Closed Trades:     {len(results.closed_trades):>12}")
    print(f"  Win Rate:          {results.win_rate:>12.1%}")
    print(f"  Avg Win:           ${results.avg_win:>12,.2f}")
    print(f"  Avg Loss:          ${results.avg_loss:>12,.2f}")
    print(f"  Profit Factor:     {results.profit_factor:>12.2f}")

    print(f"\n{sep}")
    print("  BY STRATEGY")
    print(sep)
    by_strat = results.by_strategy()
    if by_strat:
        for name, v in sorted(by_strat.items(), key=lambda x: -x[1]["pnl"]):
            pnl_s = f"+${v['pnl']:,.0f}" if v["pnl"] >= 0 else f"-${abs(v['pnl']):,.0f}"
            print(
                f"  {name:<35} {v['trades']:>4} trades  "
                f"{v['win_rate']:>5.1%} WR  {pnl_s:>10}"
            )
    else:
        print("  No trades")

    print(f"\n{sep}")
    print("  BY SESSION")
    print(sep)
    by_sess = results.by_session()
    if by_sess:
        for sess, v in sorted(by_sess.items(), key=lambda x: -x[1]["pnl"]):
            pnl_s = f"+${v['pnl']:,.0f}" if v["pnl"] >= 0 else f"-${abs(v['pnl']):,.0f}"
            print(
                f"  {sess:<20} {v['trades']:>4} trades  "
                f"{v['win_rate']:>5.1%} WR  {pnl_s:>10}"
            )

    print(f"\n{sep}")
    print("  DAILY P&L")
    print(sep)
    for d in results.daily:
        if d.total_trades > 0:
            bar = "█" * min(int(abs(d.total_pnl) / 50), 20)
            sign = "+" if d.total_pnl >= 0 else "-"
            print(
                f"  {d.date}  {d.wins:>2}W/{d.losses:>2}L  "
                f"{sign}${abs(d.total_pnl):>7,.0f}  {bar}"
            )

    print(f"\n{sep}\n")


def save_report(results: BacktestResults, output_dir: Path = None) -> Path:
    """Save backtest results to CSV + JSON."""
    output_dir = output_dir or LOGS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = output_dir / f"backtest_{timestamp}"

    # Save trades CSV
    trades_data = []
    for t in results.closed_trades:
        trades_data.append({
            "trade_id": t.trade_id,
            "strategy": t.strategy,
            "symbol": t.symbol,
            "side": t.side,
            "entry_time": str(t.entry_time),
            "exit_time": str(t.exit_time),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl": round(t.pnl, 2),
            "pnl_pct": round(t.pnl_pct, 4),
            "exit_reason": t.exit_reason,
            "session": t.session,
            "condition": t.market_condition,
            "confidence": round(t.confidence, 3),
        })

    if trades_data:
        df = pd.DataFrame(trades_data)
        csv_path = Path(str(base) + "_trades.csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"Trades saved: {csv_path}")

    # Save summary JSON
    summary = {
        "start_date": results.start_date,
        "end_date": results.end_date,
        "initial_capital": results.initial_capital,
        "final_capital": round(results.final_capital, 2),
        "total_pnl": round(results.total_pnl, 2),
        "total_return_pct": round(results.total_return_pct, 4),
        "total_trades": results.total_trades,
        "win_rate": round(results.win_rate, 4),
        "avg_win": round(results.avg_win, 2),
        "avg_loss": round(results.avg_loss, 2),
        "profit_factor": round(results.profit_factor, 3),
        "max_drawdown": round(results.max_drawdown, 2),
        "sharpe_ratio": round(results.sharpe_ratio, 3),
        "by_strategy": results.by_strategy(),
        "by_session": results.by_session(),
        "daily": [
            {
                "date": d.date,
                "trades": d.total_trades,
                "wins": d.wins,
                "losses": d.losses,
                "pnl": round(d.total_pnl, 2),
            }
            for d in results.daily
        ],
    }

    json_path = Path(str(base) + "_summary.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Summary saved: {json_path}")

    return json_path


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Run backtest on trading agent strategies")
    parser.add_argument("--days", type=int, default=30, help="Number of trading days to backtest")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--strategy", type=str, help="Filter to one strategy name")
    parser.add_argument(
        "--symbols", type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated symbols"
    )
    parser.add_argument("--capital", type=float, default=INITIAL_CAPITAL, help="Starting capital")
    parser.add_argument("--save", action="store_true", help="Save results to CSV/JSON")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    today = date.today()
    end_date = date.fromisoformat(args.end) if args.end else today - timedelta(days=1)
    if args.start:
        start_date = date.fromisoformat(args.start)
    else:
        start_date = end_date - timedelta(days=args.days)

    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    backtester = Backtester(initial_capital=args.capital)
    results = backtester.run(
        start_date=start_date,
        end_date=end_date,
        symbols=symbols,
        strategy_filter=args.strategy,
    )

    print_report(results)

    if args.save:
        path = save_report(results)
        print(f"Results saved to: {path}")


if __name__ == "__main__":
    main()
