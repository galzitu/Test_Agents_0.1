"""
Strategy 2: Opening Range Breakout (ORB)
Wait for first 15 minutes to establish range, then trade breakouts.
Best in: VOLATILE markets, Opening session ONLY.
"""

import logging
from datetime import time
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class OpeningRangeBreakout(BaseStrategy):

    def __init__(self):
        super().__init__("orb")
        self._ranges = {}

    def reset_range(self, symbol: str | None = None):
        """Reset at start of each trading day."""
        if symbol:
            self._ranges.pop(symbol, None)
        else:
            self._ranges.clear()

    def has_range(self, symbol: str) -> bool:
        """Check whether a symbol already has an opening range."""
        return symbol in self._ranges

    def set_opening_range(self, symbol: str, df_1min: pd.DataFrame):
        """
        Calculate the opening range from first 15 minutes of 1-min data.
        Call this after 09:45 ET with 1-min bars from 09:30-09:45.
        """
        p = self.params
        range_minutes = p["range_minutes"]

        if len(df_1min) < range_minutes:
            logger.warning(f"ORB: Not enough 1-min bars ({len(df_1min)}/{range_minutes})")
            return

        # Use first N minutes
        range_data = df_1min.head(range_minutes)
        range_high = float(range_data["high"].max())
        range_low = float(range_data["low"].min())

        range_size = range_high - range_low
        midpoint = (range_high + range_low) / 2
        range_pct = range_size / midpoint if midpoint > 0 else 0

        # Validate range
        if range_pct < p["min_range_pct"]:
            logger.info(f"ORB {symbol}: Range too narrow ({range_pct:.3%}), skipping")
        elif range_pct > p["max_range_pct"]:
            logger.info(f"ORB {symbol}: Range too wide ({range_pct:.3%}), skipping")
        else:
            self._ranges[symbol] = {
                "high": range_high,
                "low": range_low,
            }
            logger.info(
                f"ORB {symbol}: Range set - High={range_high:.2f}, "
                f"Low={range_low:.2f}, Size={range_pct:.2%}"
            )

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if symbol not in self._ranges:
            return self._hold_signal(symbol, "Opening range not set")

        if len(df) < 5:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        p = self.params
        price = float(latest["close"])
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)
        atr = float(latest.get("atr", 0) or 0)

        range_high = self._ranges[symbol]["high"]
        range_low = self._ranges[symbol]["low"]
        range_size = range_high - range_low
        buffer = price * p["breakout_buffer_pct"]

        indicators = {
            "price": round(price, 2),
            "range_high": round(range_high, 2),
            "range_low": round(range_low, 2),
            "range_size": round(range_size, 2),
            "volume_ratio": round(volume_ratio, 2),
            "atr": round(atr, 4),
        }

        # ===== LONG: Breakout above range =====
        if price > (range_high + buffer) and volume_ratio >= p["min_volume_ratio"]:
            stop_loss = range_low
            take_profit = range_high + (range_size * p["take_profit_mult"])

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=0.65,
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Breakout above range ({range_high:.2f}), volume {volume_ratio:.1f}x",
                indicators=indicators,
            )

        # ===== SHORT: Breakdown below range =====
        if price < (range_low - buffer) and volume_ratio >= p["min_volume_ratio"]:
            stop_loss = range_high
            take_profit = range_low - (range_size * p["take_profit_mult"])

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=0.65,
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Breakdown below range ({range_low:.2f}), volume {volume_ratio:.1f}x",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "Price within opening range")
