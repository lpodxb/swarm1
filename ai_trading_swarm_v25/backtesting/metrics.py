from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass
class BacktestMetrics:
    total_return: float
    max_drawdown: float
    sharpe: float
    win_rate: float
    profit_factor: float
    num_trades: int


def compute_metrics(
    equity_curve: pd.Series,
    trade_returns: List[float],
) -> BacktestMetrics:
    returns = equity_curve.pct_change().dropna()
    if len(returns) == 0:
        sharpe = 0.0
    else:
        sharpe = float(np.sqrt(252) * returns.mean() / (returns.std() + 1e-9))

    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    max_drawdown = float(drawdown.min() if len(drawdown) else 0.0)

    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r <= 0]
    num_trades = len(trade_returns)
    win_rate = len(wins) / num_trades if num_trades > 0 else 0.0

    gross_profit = sum(wins)
    gross_loss = -sum(losses) if losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    return BacktestMetrics(
        total_return=total_return,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        win_rate=win_rate,
        profit_factor=profit_factor,
        num_trades=num_trades,
    )
