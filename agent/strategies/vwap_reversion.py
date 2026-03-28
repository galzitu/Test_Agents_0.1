"""
Strategy 3: VWAP Mean Reversion
Buy when price is far below VWAP, sell when far above.
CRITICAL: Only works in RANGING markets (ADX < 25). FAILS in trending!
Best in: RANGING markets, Mid-Day session.
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class VWAPMeanReversion(BaseStrategy):

    def __init__(self):
        super().__init__("vwap_reversion")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 20:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        p = self.params

        price = float(latest["close"])
        vwap = latest.get("vwap")
        rsi = latest.get("rsi")
        adx = latest.get("adx", 50)
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)

        if any(v is None or pd.isna(v) for v in [vwap, rsi]):
            return self._hold_signal(symbol, "Missing VWAP or RSI")

        vwap = float(vwap)
        rsi = float(rsi)
        adx = float(adx) if not pd.isna(adx) else 50
        atr = float(latest.get("atr", 0) or 0)

        # Safety: Don't trade in strong trending market
        if adx > 30:
            return self._hold_signal(symbol, f"ADX too high ({adx:.0f}), market trending")

        deviation_pct = (price - vwap) / vwap if vwap > 0 else 0

        indicators = {
            "price": round(price, 2),
            "vwap": round(vwap, 2),
            "deviation_pct": round(deviation_pct, 4),
            "rsi": round(rsi, 2),
            "adx": round(adx, 2),
            "volume_ratio": round(volume_ratio, 2),
            "atr": round(atr, 4),
        }

        # ===== LONG: Price far below VWAP =====
        if (deviation_pct < -p["deviation_pct"]
                and rsi < p["rsi_confirm_long"]
                and volume_ratio >= p["min_volume_ratio"]):

            recent_low = float(df.tail(10)["low"].min())
            stop_loss = recent_low * (1 - p["stop_loss_pct"])
            take_profit = vwap  # Target: return to VWAP

            confidence = 0.6
            if deviation_pct < -0.015:
                confidence += 0.1
            if rsi < 30:
                confidence += 0.1

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Price {deviation_pct:.2%} below VWAP, RSI={rsi:.0f}, ranging market",
                indicators=indicators,
            )

        # ===== SHORT: Price far above VWAP =====
        if (deviation_pct > p["deviation_pct"]
                and rsi > p["rsi_confirm_short"]
                and volume_ratio >= p["min_volume_ratio"]):

            recent_high = float(df.tail(10)["high"].max())
            stop_loss = recent_high * (1 + p["stop_loss_pct"])
            take_profit = vwap  # Target: return to VWAP

            confidence = 0.6
            if deviation_pct > 0.015:
                confidence += 0.1
            if rsi > 70:
                confidence += 0.1

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Price {deviation_pct:.2%} above VWAP, RSI={rsi:.0f}, ranging market",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "No VWAP reversion signal")
