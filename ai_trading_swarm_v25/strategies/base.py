from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List

import pandas as pd


class SignalType(Enum):
    ENTRY_LONG = auto()
    EXIT_LONG = auto()
    ENTRY_SHORT = auto()
    EXIT_SHORT = auto()


@dataclass
class Signal:
    timestamp: pd.Timestamp
    signal_type: SignalType
    price: float
    size_fraction: float
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    id: str
    pair: str
    timeframe: str
    params: Dict[str, Any] = field(default_factory=dict)


class Strategy:
    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg
        self.id = cfg.id
        self.pair = cfg.pair
        self.timeframe = cfg.timeframe
        self.params = cfg.params

    def prepare(self, candles: pd.DataFrame) -> pd.DataFrame:
        return candles

    def generate_signals(self, candles: pd.DataFrame) -> List[Signal]:
        raise NotImplementedError
