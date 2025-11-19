from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from lab.storage import (
    init_db,
    get_strategies_summary,
    get_backtests_for_strategy,
    set_strategy_status,
)


class LabOrchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = config.get("lab", {})
        init_db()

    def _evaluate_single(self, strat: Dict[str, Any]) -> str:
        sid = strat["id"]
        bt_rows = get_backtests_for_strategy(sid)

        min_bt = int(self.thresholds.get("min_backtests", 1))
        min_trades = int(self.thresholds.get("min_trades", 30))
        min_sharpe = float(self.thresholds.get("min_sharpe", 1.0))
        max_dd = float(self.thresholds.get("max_drawdown", 0.3))
        min_ret = float(self.thresholds.get("min_total_return", 0.1))
        min_pf = float(self.thresholds.get("min_profit_factor", 1.3))

        if len(bt_rows) < min_bt:
            logger.info(f"{sid}: insufficient backtests ({len(bt_rows)}/{min_bt})")
            return "insufficient_data"

        latest = bt_rows[0]

        total_return = latest["total_return"]
        max_drawdown = latest["max_drawdown"]
        sharpe = latest["sharpe"]
        win_rate = latest["win_rate"]
        pf = latest["profit_factor"]
        num_trades = latest["num_trades"]

        if num_trades < min_trades:
            logger.info(f"{sid}: insufficient trades ({num_trades}/{min_trades})")
            return "insufficient_data"

        if (
            total_return >= min_ret
            and max_drawdown >= -max_dd
            and sharpe >= min_sharpe
            and pf >= min_pf
        ):
            logger.success(
                f"{sid}: APPROVED (ret={total_return:.2%}, DD={max_drawdown:.2%}, "
                f"Sharpe={sharpe:.2f}, PF={pf:.2f}, trades={num_trades})"
            )
            return "approved"

        if total_return < 0 or pf < 1.0:
            logger.warning(
                f"{sid}: REJECTED (ret={total_return:.2%}, PF={pf:.2f})"
            )
            return "rejected"

        logger.info(
            f"{sid}: remains EXPERIMENTAL (ret={total_return:.2%}, DD={max_drawdown:.2%}, "
            f"Sharpe={sharpe:.2f}, PF={pf:.2f}, trades={num_trades})"
        )
        return "experimental"

    def evaluate_all(self) -> None:
        strategies = get_strategies_summary()
        logger.info(f"Evaluating {len(strategies)} strategies against lab thresholds.")
        for s in strategies:
            new_status = self._evaluate_single(s)
            set_strategy_status(s["id"], new_status)
