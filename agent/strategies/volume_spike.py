"""
Strategy 4: Volume Spike Momentum
Trade when volume spikes 3x+ average with strong candle.
Best in: VOLATILE markets, Opening & Power Hour sessions.
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class VolumeSpikeMomentum(BaseStrategy):

    def __init__(self):
        super().__init__("volume_spike")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 20:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        p = self.params

        price = float(latest["close"])
        open_price = float(latest["open"])
        high = float(latest["high"])
        low = float(latest["low"])
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)
        atr = float(latest.get("atr", 0) or 0)
        ema_9 = latest.get("ema_9")

        if ema_9 is None or pd.isna(ema_9):
            return self._hold_signal(symbol, "Missing EMA(9)")

        ema_9 = float(ema_9)

        # Calculate candle body
        candle_body = abs(price - open_price)
        candle_body_pct = candle_body / price if price > 0 else 0
        is_green = price > open_price
        is_red = price < open_price

        # Check for exhaustion (price already moved a lot)
        recent_move = 0
        if len(df) >= 12:
            price_1h_ago = float(df.iloc[-12]["close"])
            recent_move = abs(price - price_1h_ago) / price_1h_ago

        indicators = {
            "price": round(price, 2),
            "volume_ratio": round(volume_ratio, 2),
            "ema_9": round(ema_9, 2),
            "candle_body_pct": round(candle_body_pct, 4),
            "is_green": is_green,
            "recent_move_pct": round(recent_move, 4),
            "atr": round(atr, 4),
        }

        # Skip if exhaustion detected (big move already happened)
        if recent_move > 0.03:
            return self._hold_signal(symbol, f"Possible exhaustion, recent move {recent_move:.1%}")

        # Volume spike required
        if volume_ratio < p["volume_spike_mult"]:
            return self._hold_signal(symbol, f"No volume spike ({volume_ratio:.1f}x)")

        # Strong candle required
        if candle_body_pct < p["min_candle_body_pct"]:
            return self._hold_signal(symbol, "Candle body too small")

        # ===== LONG: Green spike candle above EMA(9) =====
        if is_green and price > ema_9:
            stop_loss = low  # Low of spike candle
            take_profit = price * (1 + p["take_profit_pct"])

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=0.6,
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Volume spike {volume_ratio:.1f}x, green candle above EMA(9)",
                indicators=indicators,
            )

        # ===== SHORT: Red spike candle below EMA(9) =====
        if is_red and price < ema_9:
            stop_loss = high  # High of spike candle
            take_profit = price * (1 - p["take_profit_pct"])

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=0.6,
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Volume spike {volume_ratio:.1f}x, red candle below EMA(9)",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "Volume spike but no direction confirmation")
