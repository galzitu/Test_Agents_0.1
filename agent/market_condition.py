"""
Market Condition Detector - Identifies current market state.
No AI involved - pure math based on technical indicators.

States:
  TRENDING_UP   - Strong upward trend (ADX > 25, price > EMA21)
  TRENDING_DOWN - Strong downward trend (ADX > 25, price < EMA21)
  RANGING       - No clear trend (ADX < 20, normal volatility)
  VOLATILE      - High volatility (ATR > 1.5x average)
  LOW_VOLUME    - Low activity (volume < 50% avg) → DO NOT TRADE
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

from agent.config import MarketConditionConfig as MCConfig

logger = logging.getLogger(__name__)


class MarketState(Enum):
    """Possible market conditions."""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    LOW_VOLUME = "LOW_VOLUME"
    UNKNOWN = "UNKNOWN"


@dataclass
class MarketSnapshot:
    """
    A snapshot of market indicators needed for condition detection.
    This is what market_data.py will provide.
    """
    # Trend indicators
    adx: float                    # ADX(14) - trend strength (0-100)
    ema_9: float                  # EMA(9) current value
    ema_21: float                 # EMA(21) current value
    current_price: float          # Last price

    # Volatility indicators
    atr: float                    # ATR(14) current
    atr_avg_20: float             # 20-period average ATR

    # Volume indicators
    current_volume: float         # Current period volume
    avg_volume_20: float          # 20-period average volume

    @property
    def atr_ratio(self) -> float:
        """ATR compared to its average. >1 = more volatile than usual."""
        if self.atr_avg_20 == 0:
            return 1.0
        return self.atr / self.atr_avg_20

    @property
    def volume_ratio(self) -> float:
        """Volume compared to average. >1 = more active than usual."""
        if self.avg_volume_20 == 0:
            return 1.0
        return self.current_volume / self.avg_volume_20

    @property
    def is_price_above_ema21(self) -> bool:
        return self.current_price > self.ema_21

    @property
    def is_ema9_above_ema21(self) -> bool:
        return self.ema_9 > self.ema_21


class MarketConditionDetector:
    """
    Detects current market condition based on technical indicators.

    Detection order matters:
    1. LOW_VOLUME check first (safety - don't trade!)
    2. VOLATILE check (unusual activity)
    3. TRENDING check (ADX-based)
    4. RANGING (default when nothing else triggers)
    """

    def detect(self, snapshot: MarketSnapshot) -> MarketState:
        """
        Analyze market snapshot and return the current condition.

        Args:
            snapshot: MarketSnapshot with all needed indicators

        Returns:
            MarketState enum value
        """
        # 1. LOW VOLUME - Safety first! Don't trade in dead market
        if snapshot.volume_ratio < MCConfig.VOLUME_LOW_RATIO:
            logger.warning(
                f"LOW VOLUME detected: volume_ratio={snapshot.volume_ratio:.2f} "
                f"(threshold: {MCConfig.VOLUME_LOW_RATIO})"
            )
            return MarketState.LOW_VOLUME

        # 2. VOLATILE - High ATR relative to average
        if snapshot.atr_ratio > MCConfig.ATR_VOLATILE_RATIO:
            logger.info(
                f"VOLATILE market: ATR_ratio={snapshot.atr_ratio:.2f} "
                f"(threshold: {MCConfig.ATR_VOLATILE_RATIO})"
            )
            return MarketState.VOLATILE

        # 3. TRENDING - Strong ADX with directional EMAs
        if snapshot.adx > MCConfig.ADX_TREND_THRESHOLD:
            if snapshot.is_price_above_ema21 and snapshot.is_ema9_above_ema21:
                logger.info(
                    f"TRENDING UP: ADX={snapshot.adx:.1f}, "
                    f"price={snapshot.current_price:.2f} > EMA21={snapshot.ema_21:.2f}"
                )
                return MarketState.TRENDING_UP
            elif not snapshot.is_price_above_ema21 and not snapshot.is_ema9_above_ema21:
                logger.info(
                    f"TRENDING DOWN: ADX={snapshot.adx:.1f}, "
                    f"price={snapshot.current_price:.2f} < EMA21={snapshot.ema_21:.2f}"
                )
                return MarketState.TRENDING_DOWN

        # 4. RANGING - Default state (low ADX, normal volatility)
        if snapshot.adx < MCConfig.ADX_RANGING_THRESHOLD:
            logger.info(
                f"RANGING market: ADX={snapshot.adx:.1f} "
                f"(threshold: {MCConfig.ADX_RANGING_THRESHOLD})"
            )
            return MarketState.RANGING

        # 5. Borderline - ADX between 20-25, check EMA direction to decide
        if snapshot.is_ema9_above_ema21 and snapshot.is_price_above_ema21:
            logger.info(
                f"Borderline market (ADX={snapshot.adx:.1f}), EMA points UP → treating as TRENDING_UP"
            )
            return MarketState.TRENDING_UP
        elif not snapshot.is_ema9_above_ema21 and not snapshot.is_price_above_ema21:
            logger.info(
                f"Borderline market (ADX={snapshot.adx:.1f}), EMA points DOWN → treating as TRENDING_DOWN"
            )
            return MarketState.TRENDING_DOWN
        else:
            logger.info(
                f"Borderline market (ADX={snapshot.adx:.1f}), EMAs mixed → treating as RANGING"
            )
            return MarketState.RANGING

    def should_trade(self, state: MarketState) -> bool:
        """Should the agent trade in this market condition?"""
        return state != MarketState.LOW_VOLUME

    def get_summary(self, snapshot: MarketSnapshot) -> dict:
        """Get a full market condition summary."""
        state = self.detect(snapshot)
        return {
            "state": state.value,
            "should_trade": self.should_trade(state),
            "adx": round(snapshot.adx, 1),
            "atr_ratio": round(snapshot.atr_ratio, 2),
            "volume_ratio": round(snapshot.volume_ratio, 2),
            "price_vs_ema21": "above" if snapshot.is_price_above_ema21 else "below",
            "ema9_vs_ema21": "above" if snapshot.is_ema9_above_ema21 else "below",
        }


# Convenience instance
detector = MarketConditionDetector()


if __name__ == "__main__":
    # Quick test with mock data
    snapshot = MarketSnapshot(
        adx=30.5,
        ema_9=180.50,
        ema_21=178.20,
        current_price=181.00,
        atr=2.5,
        atr_avg_20=2.0,
        current_volume=5_000_000,
        avg_volume_20=4_000_000,
    )

    d = MarketConditionDetector()
    state = d.detect(snapshot)
    print(f"Market condition: {state.value}")
    print(f"Should trade: {d.should_trade(state)}")
    print(f"Summary: {d.get_summary(snapshot)}")
