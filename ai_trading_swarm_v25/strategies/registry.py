from __future__ import annotations

from typing import Dict, Type, Any

from .base import Strategy, StrategyConfig
from .btc_breakout_v1 import BTCBreakoutStrategyV1


STRATEGY_REGISTRY: Dict[str, Type[Strategy]] = {
    "btc_breakout_v1": BTCBreakoutStrategyV1,
}


def create_strategy(
    strategy_id: str,
    pair: str,
    timeframe: str,
    params: Dict[str, Any] | None = None,
) -> Strategy:
    if params is None:
        params = {}

    cls = STRATEGY_REGISTRY.get(strategy_id)
    if cls is None:
        raise ValueError(f"Unknown strategy_id: {strategy_id}")

    cfg = StrategyConfig(
        id=strategy_id,
        pair=pair,
        timeframe=timeframe,
        params=params,
    )
    return cls(cfg)
