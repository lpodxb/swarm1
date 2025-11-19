from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from loguru import logger

from strategies.registry import create_strategy
from backtesting.engine import BacktestEngine
from lab.storage import init_db, upsert_strategy, record_backtest


def load_candles(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "timestamp" not in df.columns:
        raise ValueError("CSV must contain a 'timestamp' column.")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    return df[["open", "high", "low", "close", "volume"]]


def main():
    parser = argparse.ArgumentParser(description="Run backtest for a strategy.")
    parser.add_argument("--strategy_id", type=str, required=True)
    parser.add_argument("--pair", type=str, default="BTC/USDT")
    parser.add_argument("--timeframe", type=str, default="15m")
    parser.add_argument("--csv", type=str, required=True)
    parser.add_argument("--initial_capital", type=float, default=10_000.0)

    args = parser.parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    init_db()
    candles = load_candles(csv_path)
    strat = create_strategy(args.strategy_id, pair=args.pair, timeframe=args.timeframe)
    upsert_strategy(strat.id, args.pair, args.timeframe, strat.params)

    engine = BacktestEngine(initial_capital=args.initial_capital)
    result = engine.run(strat, candles)

    m = result.metrics
    logger.info("==== Backtest Metrics ====")
    logger.info(f"Total Return: {m.total_return:.2%}")
    logger.info(f"Max Drawdown: {m.max_drawdown:.2%}")
    logger.info(f"Sharpe: {m.sharpe:.2f}")
    logger.info(f"Win Rate: {m.win_rate:.2%}")
    logger.info(f"Profit Factor: {m.profit_factor:.2f}")
    logger.info(f"Trades: {m.num_trades}")

    equity_path = csv_path.parent / f"equity_{args.strategy_id}.csv"
    trades_path = csv_path.parent / f"trades_{args.strategy_id}.csv"
    result.equity_curve.to_csv(equity_path, header=["equity"])
    pd.DataFrame(
        [
            {
                "entry_time": t.entry_time,
                "entry_price": t.entry_price,
                "exit_time": t.exit_time,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "return_pct": t.return_pct,
            }
            for t in result.trades
        ]
    ).to_csv(trades_path, index=False)

    metrics_dict = {
        "total_return": m.total_return,
        "max_drawdown": m.max_drawdown,
        "sharpe": m.sharpe,
        "win_rate": m.win_rate,
        "profit_factor": m.profit_factor,
        "num_trades": m.num_trades,
    }
    sample_start = candles.index[0].isoformat()
    sample_end = candles.index[-1].isoformat()
    record_backtest(
        strategy_id=strat.id,
        sample_start=sample_start,
        sample_end=sample_end,
        initial_capital=args.initial_capital,
        metrics=metrics_dict,
        equity_path=str(equity_path),
        trades_path=str(trades_path),
    )


if __name__ == "__main__":
    main()
