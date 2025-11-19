from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import pandas as pd
from loguru import logger

from strategies.base import Strategy, SignalType
from backtesting.metrics import compute_metrics, BacktestMetrics


@dataclass
class TradeRecord:
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    pnl: float
    return_pct: float
    meta: Dict[str, Any]


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: List[TradeRecord]
    metrics: BacktestMetrics


class BacktestEngine:
    def __init__(self, initial_capital: float = 10_000.0):
        self.initial_capital = initial_capital

    def run(self, strategy: Strategy, candles: pd.DataFrame) -> BacktestResult:
        df = candles.copy().sort_index()
        signals = strategy.generate_signals(df)

        equity_curve = pd.Series(index=df.index, dtype=float)
        equity_curve.iloc[0] = self.initial_capital

        in_position = False
        position_size = 0.0
        entry_price = 0.0
        entry_time: Optional[pd.Timestamp] = None
        capital = self.initial_capital

        trades: List[TradeRecord] = []
        trade_returns: List[float] = []

        sig_idx = 0
        signals_sorted = sorted(signals, key=lambda s: s.timestamp)

        for ts in df.index:
            price = float(df.loc[ts, "close"])

            while sig_idx < len(signals_sorted) and signals_sorted[sig_idx].timestamp <= ts:
                sig = signals_sorted[sig_idx]
                sig_idx += 1

                if sig.signal_type == SignalType.ENTRY_LONG and not in_position:
                    risk_frac = sig.size_fraction
                    if risk_frac <= 0:
                        continue
                    position_size = (capital * risk_frac) / price
                    entry_price = price
                    entry_time = sig.timestamp
                    in_position = True

                elif sig.signal_type == SignalType.EXIT_LONG and in_position:
                    exit_price = price
                    exit_time = sig.timestamp
                    pnl = position_size * (exit_price - entry_price)
                    capital += pnl
                    ret_pct = pnl / max(1e-9, self.initial_capital)

                    trades.append(
                        TradeRecord(
                            entry_time=entry_time,
                            entry_price=entry_price,
                            exit_time=exit_time,
                            exit_price=exit_price,
                            pnl=pnl,
                            return_pct=ret_pct,
                            meta={"strategy_id": strategy.id},
                        )
                    )
                    trade_returns.append(ret_pct)
                    position_size = 0.0
                    in_position = False

            if in_position:
                unrealized_pnl = position_size * (price - entry_price)
                equity_curve.loc[ts] = capital + unrealized_pnl
            else:
                equity_curve.loc[ts] = capital

        if in_position and position_size > 0.0:
            last_ts = df.index[-1]
            last_price = float(df["close"].iloc[-1])
            pnl = position_size * (last_price - entry_price)
            capital += pnl
            ret_pct = pnl / max(1e-9, self.initial_capital)

            trades.append(
                TradeRecord(
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=last_ts,
                    exit_price=last_price,
                    pnl=pnl,
                    return_pct=ret_pct,
                    meta={"strategy_id": strategy.id, "forced_exit": True},
                )
            )
            trade_returns.append(ret_pct)
            equity_curve.iloc[-1] = capital

        metrics = compute_metrics(equity_curve, trade_returns)
        logger.info(
            f"Backtest {strategy.id} done: "
            f"total_return={metrics.total_return:.2%}, "
            f"max_dd={metrics.max_drawdown:.2%}, "
            f"sharpe={metrics.sharpe:.2f}, "
            f"win_rate={metrics.win_rate:.2%}, "
            f"PF={metrics.profit_factor:.2f}, "
            f"trades={metrics.num_trades}"
        )

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
        )
