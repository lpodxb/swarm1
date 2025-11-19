from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MarketRegime:
    regime: str = "unknown"
    updated_at: datetime = field(default_factory=datetime.utcnow)
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GlobalState:
    config: Dict[str, Any]
    is_trading_paused: bool = False
    market_regime: MarketRegime = field(default_factory=MarketRegime)
    alt_data_snapshot: Optional[Dict[str, Any]] = None
    trades_executed: int = 0
    trades_rejected: int = 0
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    consensus_history: List[Dict[str, Any]] = field(default_factory=list)
    trades_history: List[Dict[str, Any]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def set_alt_data_snapshot(self, snapshot: Dict[str, Any]) -> None:
        async with self._lock:
            self.alt_data_snapshot = snapshot

    def update_market_regime(self, regime: str, **features: Any) -> None:
        self.market_regime.regime = regime
        self.market_regime.updated_at = datetime.utcnow()
        self.market_regime.features = features

    def record_trade(self, trade: Dict[str, Any]) -> None:
        self.trades_history.append(trade)
        self.trades_executed += 1
        pnl = float(trade.get("pnl", 0.0))
        self.daily_pnl += pnl
        self.equity_curve.append(
            {
                "time": trade.get("time", datetime.utcnow().isoformat()),
                "daily_pnl": self.daily_pnl,
            }
        )


_global_state: Optional[GlobalState] = None


def get_global_state(config: Optional[Dict[str, Any]] = None) -> GlobalState:
    global _global_state
    if _global_state is None:
        if config is None:
            raise RuntimeError("GlobalState not initialized and no config provided.")
        _global_state = GlobalState(config=config)
    return _global_state
