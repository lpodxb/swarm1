from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from loguru import logger

from lab.selection import get_approved_strategies_for_pair


@dataclass
class PairContext:
    symbol: str
    timeframe: str
    enabled: bool = True
    base_asset: str = ""
    quote_asset: str = ""
    approved_strategies: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def refresh_approved_strategies(self) -> None:
        self.approved_strategies = get_approved_strategies_for_pair(
            self.symbol, self.timeframe
        )
        if not self.approved_strategies:
            logger.warning(
                f"[PairContext] {self.symbol} {self.timeframe}: no approved strategies found."
            )
        else:
            logger.info(
                f"[PairContext] {self.symbol} {self.timeframe}: "
                f"approved strategies = {self.approved_strategies}"
            )


def _split_symbol(symbol: str) -> tuple[str, str]:
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
        return base, quote
    return symbol, ""


def build_contexts_from_config(config: Dict[str, Any]) -> List[PairContext]:
    contexts: List[PairContext] = []
    pairs_cfg = config.get("pairs") or []
    enabled_pairs = [p for p in pairs_cfg if p.get("enabled", True)]

    if enabled_pairs:
        for p in enabled_pairs:
            symbol = p["symbol"]
            timeframe = p.get("timeframe", config["trading"].get("timeframe", "15m"))
            base, quote = _split_symbol(symbol)
            ctx = PairContext(
                symbol=symbol,
                timeframe=timeframe,
                enabled=True,
                base_asset=base,
                quote_asset=quote,
            )
            ctx.refresh_approved_strategies()
            contexts.append(ctx)
    else:
        base = config["trading"].get("primary_asset", "BTC")
        quote = config["trading"].get("base_currency", "USDT")
        timeframe = config["trading"].get("timeframe", "15m")
        symbol = f"{base}/{quote}"
        ctx = PairContext(
            symbol=symbol,
            timeframe=timeframe,
            enabled=True,
            base_asset=base,
            quote_asset=quote,
        )
        ctx.refresh_approved_strategies()
        contexts.append(ctx)

    logger.info(f"[Context] Built {len(contexts)} pair contexts from config.")
    return contexts
