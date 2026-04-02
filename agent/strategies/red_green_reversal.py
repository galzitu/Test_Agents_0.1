"""
Strategy 8: Red-to-Green / Green-to-Red Reversal
Detects when a stock reverses its daily direction — opens red, turns green (or vice versa).
This is one of the most common day trading patterns.
Best in: Opening session, any market condition.
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class RedGreenReversal(BaseStrategy):

    def __init__(self):
        super().__init__("red_green_reversal")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 10:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        p = self.params

        price = float(latest["close"])
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)
        rsi = latest.get("rsi")
        atr = float(latest.get("atr", 0) or 0)

        if any(v is None or pd.isna(v) for v in [rsi]):
            return self._hold_signal(symbol, "Missing RSI")

        rsi = float(rsi)

        # Need previous day's close to determine red/green
        if len(df) < 3:
            return self._hold_signal(symbol, "Need more data")

        # Use the day's first bar as reference for prev close
        prev_close = float(df.iloc[-3]["close"])
        current_vs_prev = (price - prev_close) / prev_close if prev_close > 0 else 0
        prev_bar_vs_prev = (float(prev["close"]) - prev_close) / prev_close if prev_close > 0 else 0

        indicators = {
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "current_change": round(current_vs_prev, 4),
            "prev_bar_change": round(prev_bar_vs_prev, 4),
            "volume_ratio": round(volume_ratio, 2),
            "rsi": round(rsi, 2),
        }

        min_vol = p["min_volume_ratio"]
        min_move = p["min_reversal_pct"]

        # ===== RED TO GREEN (LONG) =====
        # Previous bar was red (below prev close), current bar turned green
        if (prev_bar_vs_prev < -min_move   # Was red
                and current_vs_prev > 0     # Now green
                and volume_ratio >= min_vol
                and rsi > 30 and rsi < 65): # Not extreme

            stop_loss = float(prev["low"]) * (1 - p["stop_loss_pct"])
            take_profit = price + (price - stop_loss) * p["take_profit_mult"]

            confidence = 0.55
            if abs(prev_bar_vs_prev) > 0.01:  # Bigger reversal
                confidence += 0.1
            if volume_ratio > 1.5:
                confidence += 0.1

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Red→Green reversal ({prev_bar_vs_prev:.1%}→{current_vs_prev:.1%}), vol {volume_ratio:.1f}x",
                indicators=indicators,
            )

        # ===== GREEN TO RED (SHORT) =====
        if (prev_bar_vs_prev > min_move    # Was green
                and current_vs_prev < 0     # Now red
                and volume_ratio >= min_vol
                and rsi > 35 and rsi < 70): # Not extreme

            stop_loss = float(prev["high"]) * (1 + p["stop_loss_pct"])
            take_profit = price - (stop_loss - price) * p["take_profit_mult"]

            confidence = 0.55
            if abs(prev_bar_vs_prev) > 0.01:
                confidence += 0.1
            if volume_ratio > 1.5:
                confidence += 0.1

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Green→Red reversal ({prev_bar_vs_prev:.1%}→{current_vs_prev:.1%}), vol {volume_ratio:.1f}x",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "No reversal signal")
