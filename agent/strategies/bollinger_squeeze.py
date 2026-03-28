"""
Strategy 6: Bollinger Band Squeeze
Detect low volatility squeeze, then trade the breakout.
Best in: RANGING→VOLATILE transition markets.
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class BollingerSqueeze(BaseStrategy):

    def __init__(self):
        super().__init__("bollinger_squeeze")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 25:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        p = self.params

        price = float(latest["close"])
        bb_upper = latest.get("bb_upper")
        bb_lower = latest.get("bb_lower")
        bb_middle = latest.get("bb_middle")
        bb_bandwidth = latest.get("bb_bandwidth")
        rsi = latest.get("rsi")
        prev_rsi = prev.get("rsi")
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)

        if any(v is None or pd.isna(v) for v in [bb_upper, bb_lower, bb_middle, bb_bandwidth, rsi]):
            return self._hold_signal(symbol, "Missing Bollinger Band indicators")

        bb_upper = float(bb_upper)
        bb_lower = float(bb_lower)
        bb_middle = float(bb_middle)
        bb_bandwidth = float(bb_bandwidth)
        rsi = float(rsi)
        prev_rsi = float(prev_rsi) if prev_rsi is not None and not pd.isna(prev_rsi) else rsi
        atr = float(latest.get("atr", 0) or 0)

        indicators = {
            "price": round(price, 2),
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_bandwidth": round(bb_bandwidth, 4),
            "rsi": round(rsi, 2),
            "volume_ratio": round(volume_ratio, 2),
            "atr": round(atr, 4),
        }

        # Check for squeeze (low bandwidth)
        is_squeeze = bb_bandwidth < p["squeeze_bandwidth_threshold"]

        # Check if previous bars were also in squeeze (confirming a buildup)
        recent_bandwidths = []
        for i in range(-5, 0):
            if abs(i) <= len(df):
                bw = df.iloc[i].get("bb_bandwidth")
                if bw is not None and not pd.isna(bw):
                    recent_bandwidths.append(float(bw))

        squeeze_bars = sum(1 for bw in recent_bandwidths if bw < p["squeeze_bandwidth_threshold"])

        if not is_squeeze and squeeze_bars < 3:
            return self._hold_signal(symbol, f"No squeeze (bandwidth={bb_bandwidth:.4f})")

        # ===== LONG: Breakout above upper band =====
        if price > bb_upper and volume_ratio >= p["min_volume_spike"]:
            rsi_rising = rsi > prev_rsi

            if not rsi_rising:
                return self._hold_signal(symbol, "Breakout above BB but RSI not rising")

            stop_loss = bb_lower
            take_profit = price + (bb_bandwidth * bb_middle * 2)  # 2x bandwidth

            confidence = 0.6
            if squeeze_bars >= 4:
                confidence += 0.1  # Strong squeeze buildup
            if volume_ratio > 3.0:
                confidence += 0.1

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"BB squeeze breakout UP, bandwidth={bb_bandwidth:.3f}, volume {volume_ratio:.1f}x",
                indicators=indicators,
            )

        # ===== SHORT: Breakdown below lower band =====
        if price < bb_lower and volume_ratio >= p["min_volume_spike"]:
            rsi_falling = rsi < prev_rsi

            if not rsi_falling:
                return self._hold_signal(symbol, "Breakdown below BB but RSI not falling")

            stop_loss = bb_upper
            take_profit = price - (bb_bandwidth * bb_middle * 2)

            confidence = 0.6
            if squeeze_bars >= 4:
                confidence += 0.1
            if volume_ratio > 3.0:
                confidence += 0.1

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"BB squeeze breakout DOWN, bandwidth={bb_bandwidth:.3f}, volume {volume_ratio:.1f}x",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "Squeeze detected but no breakout yet")
