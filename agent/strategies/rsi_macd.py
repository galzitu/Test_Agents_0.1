"""
Strategy 1: RSI + MACD Momentum
Buy when RSI oversold + MACD bullish crossover + volume confirmation.
Best in: TRENDING markets, Opening & Power Hour sessions.
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class RSIMACDMomentum(BaseStrategy):

    def __init__(self):
        super().__init__("rsi_macd")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 30:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        p = self.params

        rsi = latest.get("rsi")
        macd = latest.get("macd")
        macd_signal = latest.get("macd_signal")
        prev_macd = prev.get("macd")
        prev_macd_signal = prev.get("macd_signal")
        volume_ratio = latest.get("volume_ratio", 0)
        atr = latest.get("atr", 0)
        price = latest["close"]

        # Need all indicators
        if any(v is None or pd.isna(v) for v in [rsi, macd, macd_signal, prev_macd, prev_macd_signal]):
            return self._hold_signal(symbol, "Missing indicators")

        indicators = {
            "rsi": round(float(rsi), 2),
            "macd": round(float(macd), 4),
            "macd_signal": round(float(macd_signal), 4),
            "volume_ratio": round(float(volume_ratio), 2),
            "atr": round(float(atr), 4),
        }

        # ===== LONG SIGNAL =====
        rsi_oversold = rsi < p["rsi_oversold"]
        macd_cross_up = (macd > macd_signal) and (prev_macd <= prev_macd_signal)
        volume_ok = volume_ratio >= p["min_volume_ratio"]

        if rsi_oversold and macd_cross_up and volume_ok:
            stop_loss = price - (atr * p["stop_loss_atr_mult"])
            take_profit = price + (atr * p["take_profit_atr_mult"])

            confidence = 0.6
            if rsi < 25:
                confidence += 0.1
            if volume_ratio > 2.0:
                confidence += 0.1

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"RSI oversold ({rsi:.0f}) + MACD bullish cross + volume {volume_ratio:.1f}x",
                indicators=indicators,
            )

        # ===== SHORT SIGNAL =====
        rsi_overbought = rsi > p["rsi_overbought"]
        macd_cross_down = (macd < macd_signal) and (prev_macd >= prev_macd_signal)

        if rsi_overbought and macd_cross_down and volume_ok:
            stop_loss = price + (atr * p["stop_loss_atr_mult"])
            take_profit = price - (atr * p["take_profit_atr_mult"])

            confidence = 0.6
            if rsi > 75:
                confidence += 0.1
            if volume_ratio > 2.0:
                confidence += 0.1

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"RSI overbought ({rsi:.0f}) + MACD bearish cross + volume {volume_ratio:.1f}x",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "No RSI+MACD signal")
