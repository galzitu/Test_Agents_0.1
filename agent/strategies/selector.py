"""
Strategy Selector - Picks which strategies are active right now.
Based on: current session, market condition, activation conditions.
"""

import logging
from typing import Optional

from agent.strategies.base import BaseStrategy
from agent.strategies.rsi_macd import RSIMACDMomentum
from agent.strategies.orb import OpeningRangeBreakout
from agent.strategies.vwap_reversion import VWAPMeanReversion
from agent.strategies.volume_spike import VolumeSpikeMomentum
from agent.strategies.ema_cross import EMACrossover
from agent.strategies.bollinger_squeeze import BollingerSqueeze
from agent.strategies.gap_and_go import GapAndGo
from agent.strategies.red_green_reversal import RedGreenReversal
from agent.strategies.price_action_scalp import PriceActionScalp

logger = logging.getLogger(__name__)


class StrategySelector:
    """
    Manages all strategies and selects which ones are active.

    The selector:
    1. Loads all strategies at startup
    2. Each tick: checks which are active (session + market condition)
    3. Returns only active strategies for signal generation
    """

    def __init__(self):
        """Initialize all strategies."""
        self.all_strategies: dict[str, BaseStrategy] = {}
        self._load_strategies()

    def _load_strategies(self):
        """Load and register all strategies."""
        strategies = [
            RSIMACDMomentum(),
            OpeningRangeBreakout(),
            VWAPMeanReversion(),
            VolumeSpikeMomentum(),
            EMACrossover(),
            BollingerSqueeze(),
            GapAndGo(),
            RedGreenReversal(),
            PriceActionScalp(),
        ]

        for strategy in strategies:
            self.all_strategies[strategy.name] = strategy
            logger.info(f"Loaded strategy: {strategy.name} (enabled={strategy.enabled})")

        logger.info(f"Total strategies loaded: {len(self.all_strategies)}")

    def get_active_strategies(self, session: str, market_condition: str,
                              indicators: Optional[dict] = None
                              ) -> list[BaseStrategy]:
        """
        Get strategies that should be active right now.

        Args:
            session: Current session (opening, midday, power_hour)
            market_condition: Current state (TRENDING_UP, RANGING, etc.)
            indicators: Optional dict with current indicator values

        Returns:
            List of active strategy instances
        """
        active = []

        for name, strategy in self.all_strategies.items():
            if strategy.is_active(session, market_condition, indicators):
                active.append(strategy)
                logger.debug(f"  Active: {name}")
            else:
                logger.debug(f"  Inactive: {name}")

        logger.info(
            f"Active strategies for {session}/{market_condition}: "
            f"{[s.name for s in active]} ({len(active)}/{len(self.all_strategies)})"
        )

        return active

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Get a specific strategy by name."""
        return self.all_strategies.get(name)

    def reload_all_configs(self):
        """Reload all strategy configs from disk (after Claude Coach updates)."""
        for strategy in self.all_strategies.values():
            strategy.reload_config()
        logger.info("All strategy configs reloaded")

    def get_status(self) -> dict:
        """Get status of all strategies."""
        return {
            name: {
                "enabled": s.enabled,
                "sessions": s.activation_conditions.get("sessions", []),
                "market_conditions": s.activation_conditions.get("market_conditions", []),
            }
            for name, s in self.all_strategies.items()
        }
