from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from loguru import logger

from .base import Signal, SignalType, Strategy, StrategyConfig


@dataclass
class BTCBreakoutParams:
    lookback: int = 40
    atr_period: int = 14
    atr_mult: float = 1.5
    risk_fraction: float = 0.02
    allow_short: bool = False


class BTCBreakoutStrategyV1(Strategy):
    def __init__(self, cfg: StrategyConfig):
        super().__init__(cfg)
        self.params_obj = BTCBreakoutParams(**cfg.params)

    def prepare(self, candles: pd.DataFrame) -> pd.DataFrame:
        df = candles.copy()
        p = self.params_obj

        df["hh"] = df["high"].rolling(p.lookback).max()
        df["ll"] = df["low"].rolling(p.lookback).min()
        df["mid"] = (df["hh"] + df["ll"]) / 2.0

        prev_close = df["close"].shift(1)
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - prev_close).abs()
        tr3 = (df["low"] - prev_close).abs()
        df["tr"] = np.nanmax(np.vstack([tr1.values, tr2.values, tr3.values]), axis=0)
        df["atr"] = df["tr"].rolling(p.atr_period).mean()

        df["range"] = df["hh"] - df["ll"]
        df["range_atr_ratio"] = df["range"] / (df["atr"] + 1e-9)

        return df

    def generate_signals(self, candles: pd.DataFrame) -> List[Signal]:
        df = self.prepare(candles)
        p = self.params_obj

        signals: List[Signal] = []
        in_long = False

        for ts, row in df.iterrows():
            price = float(row["close"])
            hh = row["hh"]
            ll = row["ll"]
            mid = row["mid"]
            ratio = row["range_atr_ratio"]

            if np.isnan(hh) or np.isnan(ll) or np.isnan(ratio):
                continue

            if ratio < p.atr_mult:
                continue

            if not in_long:
                if price > hh:
                    signals.append(
                        Signal(
                            timestamp=ts,
                            signal_type=SignalType.ENTRY_LONG,
                            price=price,
                            size_fraction=p.risk_fraction,
                            meta={
                                "reason": "breakout_up",
                                "hh": float(hh),
                                "ll": float(ll),
                                "mid": float(mid),
                                "range_atr_ratio": float(ratio),
                            },
                        )
                    )
                    in_long = True
            else:
                if price < mid or price < ll:
                    signals.append(
                        Signal(
                            timestamp=ts,
                            signal_type=SignalType.EXIT_LONG,
                            price=price,
                            size_fraction=0.0,
                            meta={
                                "reason": "exit_breakdown",
                                "hh": float(hh),
                                "ll": float(ll),
                                "mid": float(mid),
                                "range_atr_ratio": float(ratio),
                            },
                        )
                    )
                    in_long = False

        logger.info(f"{self.id}: generated {len(signals)} signals.")
        return signals
