"""
Strategy 5: EMA Crossover (9/21)
Buy when EMA(9) crosses above EMA(21), sell when crosses below.
WARNING: High false signal rate (57-76%) - must use RSI + volume filters!
Best in: TRENDING markets. Starts with LOW score (40).
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class EMACrossover(BaseStrategy):

    def __init__(self):
        super().__init__("ema_cross")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 25:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        p = self.params

        price = float(latest["close"])
        ema_9 = latest.get("ema_9")
        ema_21 = latest.get("ema_21")
        prev_ema_9 = prev.get("ema_9")
        prev_ema_21 = prev.get("ema_21")
        rsi = latest.get("rsi")
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)
        adx = latest.get("adx", 0)
        atr = float(latest.get("atr", 0) or 0)

        if any(v is None or pd.isna(v) for v in [ema_9, ema_21, prev_ema_9, prev_ema_21, rsi]):
            return self._hold_signal(symbol, "Missing indicators")

        ema_9, ema_21 = float(ema_9), float(ema_21)
        prev_ema_9, prev_ema_21 = float(prev_ema_9), float(prev_ema_21)
        rsi = float(rsi)
        adx = float(adx) if not pd.isna(adx) else 0

        indicators = {
            "ema_9": round(ema_9, 2),
            "ema_21": round(ema_21, 2),
            "rsi": round(rsi, 2),
            "adx": round(adx, 2),
            "volume_ratio": round(volume_ratio, 2),
            "atr": round(atr, 4),
        }

        # Crossover detection
        cross_up = (ema_9 > ema_21) and (prev_ema_9 <= prev_ema_21)
        cross_down = (ema_9 < ema_21) and (prev_ema_9 >= prev_ema_21)

        # Volume filter
        volume_ok = volume_ratio >= p["min_volume_ratio"]

        # ===== LONG: EMA(9) crosses above EMA(21) =====
        if cross_up and volume_ok:
            # RSI filter: don't buy if already overbought
            if rsi > p["rsi_filter_high"]:
                return self._hold_signal(symbol, f"EMA cross up but RSI too high ({rsi:.0f})")

            # ATR-based stop (research-proven) with EMA(21) as floor
            atr_mult = p.get("stop_loss_atr_mult", 1.5)
            if atr > 0:
                stop_loss = max(price - (atr * atr_mult), ema_21)
            else:
                stop_loss = ema_21  # Fallback: slow EMA
            take_profit = price + (atr * p.get("take_profit_atr_mult", 2.5)) if atr > 0 else price * (1 + p["take_profit_pct"])

            confidence = 0.5  # Low base confidence (high false signal rate)
            if adx > 25:
                confidence += 0.1  # Better in trending
            if volume_ratio > 1.5:
                confidence += 0.05

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"EMA(9) crossed above EMA(21), RSI={rsi:.0f}, ADX={adx:.0f}",
                indicators=indicators,
            )

        # ===== SHORT: EMA(9) crosses below EMA(21) =====
        if cross_down and volume_ok:
            if rsi < p["rsi_filter_low"]:
                return self._hold_signal(symbol, f"EMA cross down but RSI too low ({rsi:.0f})")

            # ATR-based stop (research-proven) with EMA(21) as ceiling
            atr_mult = p.get("stop_loss_atr_mult", 1.5)
            if atr > 0:
                stop_loss = min(price + (atr * atr_mult), ema_21)
            else:
                stop_loss = ema_21
            take_profit = price - (atr * p.get("take_profit_atr_mult", 2.5)) if atr > 0 else price * (1 - p["take_profit_pct"])

            confidence = 0.5
            if adx > 25:
                confidence += 0.1
            if volume_ratio > 1.5:
                confidence += 0.05

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"EMA(9) crossed below EMA(21), RSI={rsi:.0f}, ADX={adx:.0f}",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "No EMA crossover")
