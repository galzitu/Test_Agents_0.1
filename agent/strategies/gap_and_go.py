"""
Strategy 7: Gap & Go
Trade stocks that gap up/down at market open and continue in the gap direction.
Best in: Opening session, any market condition with high volume.
"""

import logging
import pandas as pd

from agent.strategies.base import BaseStrategy, Signal, SignalType

logger = logging.getLogger(__name__)


class GapAndGo(BaseStrategy):

    def __init__(self):
        super().__init__("gap_and_go")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < 10:
            return self._hold_signal(symbol, "Not enough data")

        latest = df.iloc[-1]
        p = self.params

        price = float(latest["close"])
        open_price = float(latest["open"])
        volume_ratio = float(latest.get("volume_ratio", 0) or 0)
        rsi = latest.get("rsi")
        atr = float(latest.get("atr", 0) or 0)
        ema_9 = latest.get("ema_9")
        vwap = latest.get("vwap")

        if any(v is None or pd.isna(v) for v in [rsi, ema_9]):
            return self._hold_signal(symbol, "Missing indicators")

        rsi = float(rsi)
        ema_9 = float(ema_9)

        # Calculate gap from previous close
        if len(df) < 2:
            return self._hold_signal(symbol, "Need prev bar")

        prev_close = float(df.iloc[-2]["close"])
        gap_pct = (open_price - prev_close) / prev_close if prev_close > 0 else 0

        indicators = {
            "price": round(price, 2),
            "gap_pct": round(gap_pct, 4),
            "volume_ratio": round(volume_ratio, 2),
            "rsi": round(rsi, 2),
            "ema_9": round(ema_9, 2),
        }

        min_gap = p["min_gap_pct"]
        min_vol = p["min_volume_ratio"]

        # ===== GAP UP & GO LONG =====
        if (gap_pct > min_gap
                and price > open_price  # Price continuing above open (momentum)
                and price > ema_9       # Above EMA confirms direction
                and volume_ratio >= min_vol
                and rsi < 75):          # Not extremely overbought

            stop_loss = min(open_price, prev_close) * (1 - p["stop_loss_pct"])
            take_profit = price + (price - stop_loss) * p["take_profit_mult"]

            confidence = 0.55
            if gap_pct > 0.02:
                confidence += 0.1
            if volume_ratio > 2.0:
                confidence += 0.1
            if vwap is not None and not pd.isna(vwap) and price > float(vwap):
                confidence += 0.05

            return Signal(
                type=SignalType.BUY,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Gap up {gap_pct:.1%}, price above open+EMA9, vol {volume_ratio:.1f}x",
                indicators=indicators,
            )

        # ===== GAP DOWN & GO SHORT =====
        if (gap_pct < -min_gap
                and price < open_price  # Price continuing below open
                and price < ema_9       # Below EMA confirms direction
                and volume_ratio >= min_vol
                and rsi > 25):          # Not extremely oversold

            stop_loss = max(open_price, prev_close) * (1 + p["stop_loss_pct"])
            take_profit = price - (stop_loss - price) * p["take_profit_mult"]

            confidence = 0.55
            if gap_pct < -0.02:
                confidence += 0.1
            if volume_ratio > 2.0:
                confidence += 0.1
            if vwap is not None and not pd.isna(vwap) and price < float(vwap):
                confidence += 0.05

            return Signal(
                type=SignalType.SELL,
                strategy=self.name,
                symbol=symbol,
                confidence=min(confidence, 1.0),
                entry_price=price,
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                reason=f"Gap down {gap_pct:.1%}, price below open+EMA9, vol {volume_ratio:.1f}x",
                indicators=indicators,
            )

        return self._hold_signal(symbol, "No gap & go signal")
