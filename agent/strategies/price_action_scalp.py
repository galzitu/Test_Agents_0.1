"""
Strategy 9: Price Action Scalp
Simple scalping based on candlestick patterns + volume.
Looks for strong candles with volume confirmation for quick entries.
Best in: Any session, any market condition.
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class PriceActionScalp(BaseStrategy):

    def __init__(self):
        super().__init__("price_action_scalp")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 10:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3] if len(df) >= 3 else prev
        p = self.params

        price = float(latest["close"])
        open_ = float(latest["open"])
        high = float(latest["high"])
        low = float(latest["low"])
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)
        atr = float(latest.get("atr", 0) or 0)
        ema_9 = latest.get("ema_9")
        ema_21 = latest.get("ema_21")

        if any(v is None or pd.isna(v) for v in [ema_9, ema_21]) or atr == 0:
            return self._hold_signal(symbol, "Missing indicators")

        ema_9 = float(ema_9)
        ema_21 = float(ema_21)

        # Candle metrics
        body = abs(price - open_)
        candle_range = high - low if high > low else 0.01
        body_ratio = body / candle_range  # How much of candle is body vs wick
        is_bullish = price > open_
        is_bearish = price < open_

        # Previous candles
        prev_close = float(prev["close"])
        prev_open = float(prev["open"])
        prev_bearish = prev_close < prev_open
        prev_bullish = prev_close > prev_open

        prev2_close = float(prev2["close"])
        prev2_open = float(prev2["open"])

        indicators = {
            "price": round(price, 2),
            "body_ratio": round(body_ratio, 2),
            "volume_ratio": round(volume_ratio, 2),
            "ema_9": round(ema_9, 2),
            "ema_21": round(ema_21, 2),
            "atr": round(atr, 4),
        }

        min_body = p["min_body_ratio"]
        min_vol = p["min_volume_ratio"]

        # ===== BULLISH ENGULFING + VOLUME = BUY =====
        # Current candle is bullish, bigger than previous bearish candle, with volume
        if (is_bullish
                and prev_bearish
                and body_ratio >= min_body
                and price > prev_open               # Engulfs previous candle
                and open_ <= prev_close              # Opens at or below prev close
                and volume_ratio >= min_vol
                and price > ema_21):                 # Above longer EMA (trend filter)

            stop_loss = low - (atr * p["stop_loss_atr_mult"])
            take_profit = price + (atr * p["take_profit_atr_mult"])

            confidence = 0.5
            if body_ratio > 0.7:  # Very strong candle
                confidence += 0.1
            if volume_ratio > 1.5:
                confidence += 0.1
            if price > ema_9:  # Also above fast EMA
                confidence += 0.05

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Bullish engulfing, body={body_ratio:.0%}, vol {volume_ratio:.1f}x, above EMA21",
                indicators=indicators,
            )

        # ===== BEARISH ENGULFING + VOLUME = SELL =====
        if (is_bearish
                and prev_bullish
                and body_ratio >= min_body
                and price < prev_open               # Engulfs previous candle
                and open_ >= prev_close              # Opens at or above prev close
                and volume_ratio >= min_vol
                and price < ema_21):                 # Below longer EMA (trend filter)

            stop_loss = high + (atr * p["stop_loss_atr_mult"])
            take_profit = price - (atr * p["take_profit_atr_mult"])

            confidence = 0.5
            if body_ratio > 0.7:
                confidence += 0.1
            if volume_ratio > 1.5:
                confidence += 0.1
            if price < ema_9:
                confidence += 0.05

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Bearish engulfing, body={body_ratio:.0%}, vol {volume_ratio:.1f}x, below EMA21",
                indicators=indicators,
            )

        # ===== THREE BAR PLAY (reversal after pullback) =====
        # 3 bars: big move, small pullback, continuation in original direction
        prev2_bullish = prev2_close > prev2_open
        prev2_bearish = prev2_close < prev2_open
        prev_body = abs(prev_close - prev_open)
        prev2_body = abs(prev2_close - prev2_open)

        # Bullish 3-bar: big green, small red pullback, green continuation
        if (prev2_bullish
                and prev_bearish
                and is_bullish
                and prev_body < prev2_body * 0.5     # Pullback smaller than initial move
                and price > prev2_close               # New high above first bar
                and volume_ratio >= min_vol):

            stop_loss = min(low, float(prev["low"])) - (atr * 0.5)
            take_profit = price + (atr * p["take_profit_atr_mult"])

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=0.55,
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"3-bar bullish play, vol {volume_ratio:.1f}x",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "No price action signal")
