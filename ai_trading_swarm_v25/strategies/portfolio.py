from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from loguru import logger


@dataclass
class StrategyAllocation:
    strategy_id: str
    weight: float


class StrategyPortfolioPlanner:
    def __init__(self):
        pass

    def plan_portfolio(
        self,
        approved_strategies: List[str],
        sentiment: float,
        confidence: float,
    ) -> List[StrategyAllocation]:
        if not approved_strategies:
            logger.warning("[PortfolioPlanner] No approved strategies given.")
            return []

        n = len(approved_strategies)
        base_weight = 1.0 / max(n, 1)

        tilt = sentiment * confidence  # simple scalar

        weights: Dict[str, float] = {sid: base_weight for sid in approved_strategies}

        if n >= 2 and abs(tilt) > 0.1:
            mid = n // 2
            if tilt > 0:
                for i, sid in enumerate(approved_strategies):
                    if i < mid:
                        weights[sid] *= 1.2
                    else:
                        weights[sid] *= 0.8
            else:
                for i, sid in enumerate(approved_strategies):
                    if i >= mid:
                        weights[sid] *= 1.2
                    else:
                        weights[sid] *= 0.8

        total = sum(weights.values())
        if total > 0:
            for sid in weights:
                weights[sid] /= total

        allocs = [StrategyAllocation(strategy_id=sid, weight=w) for sid, w in weights.items()]
        logger.info(
            "[PortfolioPlanner] Planned portfolio: "
            + ", ".join(f"{a.strategy_id}={a.weight:.2f}" for a in allocs)
        )
        return allocs
