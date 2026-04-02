"""
Capital Allocator - Distributes budget between strategies based on scores.
Higher score = more capital. Score-weighted proportional allocation.
"""

import json
import logging
from datetime import datetime

from agent.config import ScoringConfig, STRATEGIES_CONFIG_DIR

logger = logging.getLogger(__name__)


class CapitalAllocator:
    """
    Allocates capital to strategies proportionally to their scores.

    Method: score-weighted proportional
      Each strategy gets: its_score / sum_of_all_scores

    Constraints:
      - Max 35% per strategy
      - Min 5% per strategy (unless disabled)

    Example:
      RSI_MACD:  score=72 → 72/287 = 25.1%
      ORB:       score=65 → 65/287 = 22.6%
      VWAP:      score=45 → 45/287 = 15.7%
      VolSpike:  score=55 → 55/287 = 19.2%
      EMA_Cross: score=50 → 50/287 = 17.4%
    """

    def __init__(self):
        self.config = ScoringConfig

    def allocate(self, scores: dict[str, float],
                 disabled: list[str] = None) -> dict[str, float]:
        """
        Calculate capital allocation for each strategy.

        Args:
            scores: {strategy_name: score} dict
            disabled: List of disabled strategy names

        Returns:
            {strategy_name: allocation_pct} dict (values sum to ~1.0)
        """
        disabled = disabled or []

        # Filter out disabled strategies
        active_scores = {
            name: score for name, score in scores.items()
            if name not in disabled and score > 0
        }

        if not active_scores:
            logger.warning("No active strategies to allocate!")
            return {}

        total_weight = sum(active_scores.values())
        if total_weight == 0:
            # Equal allocation if all scores are 0
            equal = 1.0 / len(active_scores)
            return {name: equal for name in active_scores}

        # Score-weighted allocation
        allocation = {}
        for name, score in active_scores.items():
            raw_pct = score / total_weight
            # Clamp to min/max
            clamped = max(
                self.config.MIN_ALLOCATION_PCT,
                min(self.config.MAX_ALLOCATION_PCT, raw_pct)
            )
            allocation[name] = clamped

        # Normalize to sum = 1.0
        total = sum(allocation.values())
        if total > 0:
            allocation = {
                name: round(pct / total, 4)
                for name, pct in allocation.items()
            }

        return allocation

    def save_allocation(self, allocation: dict[str, float], scores: dict[str, float]):
        """Save current allocation to strategies_config/allocation.json."""
        alloc_path = STRATEGIES_CONFIG_DIR / "allocation.json"

        data = {
            "last_updated": datetime.now().isoformat(),
            "allocation": {k: round(v, 4) for k, v in allocation.items()},
            "based_on_scores": scores,
        }

        with open(alloc_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Allocation saved: {allocation}")

    def get_position_budget(self, strategy_name: str,
                            allocation: dict[str, float],
                            total_capital: float) -> float:
        """
        Calculate how much capital a strategy can use for a single trade.

        Args:
            strategy_name: Name of the strategy
            allocation: Current allocation dict
            total_capital: Total portfolio value

        Returns:
            Maximum dollar amount for this strategy's next trade
        """
        alloc_pct = allocation.get(strategy_name, 0)
        return total_capital * alloc_pct
