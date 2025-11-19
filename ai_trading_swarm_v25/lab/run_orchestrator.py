from __future__ import annotations

from loguru import logger

from configs.config_loader import ConfigLoader
from lab.orchestrator import LabOrchestrator
from lab.storage import get_strategies_summary, init_db


def main():
    cfg = ConfigLoader("configs/config.yaml").load()
    init_db()
    orchestrator = LabOrchestrator(cfg)
    orchestrator.evaluate_all()

    items = get_strategies_summary()
    logger.info("==== Lab Strategy Status ====")
    for s in items:
        logger.info(
            f"{s['id']} [{s['pair']} {s['timeframe']}] "
            f"status={s['status']} "
            f"ret={s['total_return'] if s['total_return'] is not None else 'n/a'} "
            f"DD={s['max_drawdown'] if s['max_drawdown'] is not None else 'n/a'} "
            f"Sharpe={s['sharpe'] if s['sharpe'] is not None else 'n/a'} "
            f"PF={s['profit_factor'] if s['profit_factor'] is not None else 'n/a'} "
            f"trades={s['num_trades'] if s['num_trades'] is not None else 'n/a'}"
        )


if __name__ == "__main__":
    main()
