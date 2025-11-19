from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import pandas as pd
from loguru import logger

from strategies.base import Strategy, SignalType
from strategies.registry import create_strategy
from strategies.portfolio import StrategyAllocation
from context.pair_context import PairContext


@dataclass
class ProposedTrade:
    symbol: str
    side: str
    position_frac: float
    strategy_id: str
    meta: Dict[str, Any] = field(default_factory=dict)


class StrategyExecutionEngine:
    def __init__(self):
        pass

    def _instantiate_strategies_for_context(
        self,
        ctx: PairContext,
        strategy_ids: List[str],
    ) -> List[Strategy]:
        strategies: List[Strategy] = []
        for sid in strategy_ids:
            try:
                strat = create_strategy(
                    strategy_id=sid,
                    pair=ctx.symbol,
                    timeframe=ctx.timeframe,
                    params={},
                )
                strategies.append(strat)
            except Exception as e:
                logger.error(
                    f"[StrategyExecutor] Failed to instantiate strategy {sid} "
                    f"for {ctx.symbol} {ctx.timeframe}: {e}"
                )
        return strategies

    def generate_trades_for_context(
        self,
        ctx: PairContext,
        candles: pd.DataFrame,
        allocations: List[StrategyAllocation],
    ) -> List[ProposedTrade]:
        if not allocations:
            logger.info(f"[StrategyExecutor] No allocations for {ctx.symbol}, no trades.")
            return []

        weight_map = {a.strategy_id: a.weight for a in allocations}
        strategy_ids = list(weight_map.keys())
        strategies = self._instantiate_strategies_for_context(ctx, strategy_ids)
        if not strategies:
            logger.warning(f"[StrategyExecutor] No strategies instantiated for {ctx.symbol}.")
            return []

        df = candles.copy().sort_index()
        proposed_trades: List[ProposedTrade] = []

        for strat in strategies:
            sid = strat.id
            w = weight_map.get(sid, 0.0)
            if w <= 0:
                continue

            try:
                signals = strat.generate_signals(df)
            except Exception as e:
                logger.error(f"[StrategyExecutor] Strategy {sid} failed: {e}")
                continue

            if not signals:
                continue

            last_sig = signals[-1]
            if last_sig.signal_type == SignalType.ENTRY_LONG:
                side = "buy"
                position_frac = last_sig.size_fraction * w
            elif last_sig.signal_type == SignalType.EXIT_LONG:
                side = "sell"
                position_frac = last_sig.size_fraction * w if last_sig.size_fraction > 0 else w
            else:
                continue

            proposed_trades.append(
                ProposedTrade(
                    symbol=ctx.symbol,
                    side=side,
                    position_frac=position_frac,
                    strategy_id=sid,
                    meta={
                        "reason": last_sig.meta.get("reason", ""),
                        "timeframe": ctx.timeframe,
                        "weight": w,
                    },
                )
            )

        logger.info(
            f"[StrategyExecutor] Generated {len(proposed_trades)} proposed trades for {ctx.symbol}."
        )
        return proposed_trades
