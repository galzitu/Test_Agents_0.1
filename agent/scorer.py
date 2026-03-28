"""
Strategy Scorer - Calculates scores based on real trading performance.

Inspired by the GT-Score (Golden Ticket Score) research paper which showed
98% improvement in strategy generalization vs standard Sharpe/Sortino.

Score Components (100 points total):
  - Win Rate:          30% weight (was 40%)
  - Profit Factor:     25% weight (was 35%)
  - Risk/Reward:       20% weight (was 25%)
  - Consistency:       15% weight (NEW — penalizes outlier-dependent strategies)
  - Max Drawdown:      10% weight (NEW — survivability measure)

Only reliable after 30+ trades.
"""

import json
import math
import logging
from pathlib import Path

from agent.config import ScoringConfig, STRATEGIES_CONFIG_DIR
from agent.memory import Memory

logger = logging.getLogger(__name__)


class StrategyScorer:
    """
    Scores strategies 0-100 based on actual trading results.

    GT-Score Principle: A strategy that wins 55% with consistent small
    gains is better than one that wins 30% with occasional huge wins.
    The consistency and drawdown components enforce this.

    Rules:
    - Under 30 trades: score = 50 (neutral, trial period)
    - Under 50 trades: can't disable
    - Recalculated after every closed trade
    """

    # Score weights (total = 100)
    W_WIN_RATE = 30
    W_PROFIT_FACTOR = 25
    W_RISK_REWARD = 20
    W_CONSISTENCY = 15
    W_MAX_DRAWDOWN = 10

    def __init__(self, memory: Memory):
        self.memory = memory
        self.config = ScoringConfig

    def get_all_strategy_names(self) -> list[str]:
        """Load all strategy display names from strategy config files."""
        names = []
        for path in sorted(STRATEGIES_CONFIG_DIR.glob("*.json")):
            if path.name in {"scores.json", "allocation.json"}:
                continue
            try:
                with open(path) as f:
                    config = json.load(f)
                if config.get("name"):
                    names.append(config["name"])
            except Exception as e:
                logger.warning(f"Failed to load strategy name from {path}: {e}")
        return names

    def calculate_score(self, strategy_name: str) -> dict:
        """
        Calculate score for a strategy based on all its closed trades.
        Returns dict with score + all metrics.
        """
        perf = self.memory.get_strategy_performance(strategy_name)

        total = perf["total_trades"]
        if total == 0:
            return {
                "strategy": strategy_name,
                "score": self.config.DEFAULT_SCORE,
                "total_trades": 0,
                "status": "new",
                "message": "No trades yet",
            }

        if total < self.config.MIN_TRADES_FOR_SCORE:
            return {
                "strategy": strategy_name,
                "score": self.config.DEFAULT_SCORE,
                "total_trades": total,
                "status": "trial",
                "message": f"Trial period ({total}/{self.config.MIN_TRADES_FOR_SCORE} trades)",
                "win_rate": perf["win_rate"],
                "profit_factor": perf["profit_factor"],
                "avg_risk_reward": perf["avg_risk_reward"],
            }

        # === Calculate GT-Score inspired metrics ===
        win_rate = perf["win_rate"]
        profit_factor = perf["profit_factor"]
        avg_rr = perf["avg_risk_reward"]

        # 1. Win Rate component (0-30)
        win_rate_score = win_rate * self.W_WIN_RATE

        # 2. Profit Factor component (0-25)
        # PF > 2.0 is excellent; cap at 3.0
        pf_score = min(profit_factor / 3.0, 1.0) * self.W_PROFIT_FACTOR

        # 3. Risk/Reward component (0-20)
        # R:R > 2.0 is target; cap at 3.0
        rr_score = min(avg_rr / 3.0, 1.0) * self.W_RISK_REWARD

        # 4. Consistency component (0-15) — NEW (GT-Score r² inspired)
        # Measures how consistent the P&L is. A strategy that makes
        # $10, $12, $8, $11 is better than one making -$50, +$200, -$80, +$100
        consistency = self._calculate_consistency(strategy_name)
        consistency_score = consistency * self.W_CONSISTENCY

        # 5. Max Drawdown penalty (0-10) — NEW
        # Lower drawdown = higher score
        max_dd = perf.get("max_drawdown_pct", 0)
        # max_dd is 0-1 (percentage). 0% drawdown = full 10 points
        # 10%+ drawdown = 0 points
        dd_score = max(0, 1.0 - (abs(max_dd) / 0.10)) * self.W_MAX_DRAWDOWN

        final_score = round(win_rate_score + pf_score + rr_score +
                            consistency_score + dd_score)
        final_score = max(0, min(100, final_score))

        # Determine status
        if final_score >= 70:
            status = "strong"
        elif final_score >= 50:
            status = "decent"
        elif final_score >= 30:
            status = "weak"
        else:
            status = "failing"

        return {
            "strategy": strategy_name,
            "score": final_score,
            "total_trades": total,
            "status": status,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_risk_reward": avg_rr,
            "consistency": round(consistency, 3),
            "max_drawdown_pct": round(max_dd, 4),
            "breakdown": {
                "win_rate_score": round(win_rate_score, 1),
                "profit_factor_score": round(pf_score, 1),
                "risk_reward_score": round(rr_score, 1),
                "consistency_score": round(consistency_score, 1),
                "drawdown_score": round(dd_score, 1),
            },
        }

    def _calculate_consistency(self, strategy_name: str) -> float:
        """
        Calculate consistency of a strategy's returns (0.0 to 1.0).

        Inspired by GT-Score's r² component: penalizes strategies that
        rely on a few outlier wins. Uses coefficient of variation of P&Ls.

        Returns: 0.0 (wildly inconsistent) to 1.0 (perfectly consistent)
        """
        trades = self.memory.get_trades_by_strategy(strategy_name, last_n=100)
        pnls = [t.get("pnl", 0) for t in trades if t.get("pnl") is not None]

        if len(pnls) < 5:
            return 0.5  # Not enough data, neutral

        mean_pnl = sum(pnls) / len(pnls)
        if mean_pnl == 0:
            return 0.3  # Breakeven = low consistency score

        # Standard deviation of P&Ls
        variance = sum((p - mean_pnl) ** 2 for p in pnls) / len(pnls)
        std_pnl = math.sqrt(variance)

        # Coefficient of variation (lower = more consistent)
        cv = std_pnl / abs(mean_pnl) if mean_pnl != 0 else 10.0

        # Map CV to 0-1 score: CV=0 → 1.0, CV≥3 → 0.0
        consistency = max(0.0, min(1.0, 1.0 - (cv / 3.0)))

        return consistency

    def update_scores(self, strategy_names: list[str]) -> dict[str, dict]:
        """
        Recalculate scores for multiple strategies.
        Saves to scores.json and database.
        """
        results = {}

        for name in strategy_names:
            result = self.calculate_score(name)
            results[name] = result

            # Save to database
            self.memory.save_score(
                strategy=name,
                score=result["score"],
                total_trades=result["total_trades"],
                win_rate=result.get("win_rate", 0),
                profit_factor=result.get("profit_factor", 0),
                avg_risk_reward=result.get("avg_risk_reward", 0),
                allocation_pct=0,  # Will be set by allocator
                reason=result.get("status", ""),
            )

        # Save to scores.json
        self._save_scores_json(results)
        return results

    def _save_scores_json(self, results: dict):
        """Save current scores to strategies_config/scores.json."""
        from datetime import datetime

        scores_path = STRATEGIES_CONFIG_DIR / "scores.json"
        data = {
            "last_updated": datetime.now().isoformat(),
            "scoring_version": "2.0-gt-score-inspired",
            "scores": {name: r["score"] for name, r in results.items()},
            "details": {
                name: {
                    "score": r["score"],
                    "status": r.get("status", "?"),
                    "total_trades": r["total_trades"],
                    "win_rate": r.get("win_rate", 0),
                    "consistency": r.get("consistency", 0),
                    "breakdown": r.get("breakdown", {}),
                }
                for name, r in results.items()
            },
        }

        with open(scores_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Scores saved to {scores_path}")
