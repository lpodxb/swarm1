from typing import Any, Dict, Optional
from loguru import logger


class KellyPositionSizer:
    def __init__(self, config: Dict[str, Any]):
        rm = config["trading"]["risk_management"]
        self.kelly_fraction = rm.get("kelly_fraction", 0.25)
        self.max_position = rm.get("max_position_size", 0.05)

        # You can extend this later with pair-specific stats, risk tiers, etc.

    def calculate_position_size(
        self,
        consensus: Dict[str, Any],
        backtest_stats: Optional[Dict[str, float]] = None,
    ) -> float:
        if backtest_stats is None:
            backtest_stats = {"win_rate": 0.55, "avg_win": 0.03, "avg_loss": 0.02}

        try:
            p = backtest_stats["win_rate"]
            avg_win = backtest_stats["avg_win"]
            avg_loss = abs(backtest_stats["avg_loss"])
            if avg_loss == 0:
                return self.max_position * 0.5

            b = avg_win / avg_loss
            q = 1 - p
            kelly = (p * b - q) / b

            position_size = kelly * self.kelly_fraction
            confidence = float(consensus.get("confidence", 0.7))
            position_size *= confidence

            final_size = min(max(position_size, 0.0), self.max_position)
            logger.info(f"Kelly position size: {final_size:.4f}")
            return final_size
        except Exception as e:
            logger.error(f"Kelly calculation error: {e}")
            return self.max_position * 0.5

    def get_backtest_stats(self, strategy_id: str) -> Dict[str, float]:
        # TODO: later: load from lab DB per strategy/pair
        return {
            "win_rate": 0.58,
            "avg_win": 0.035,
            "avg_loss": 0.018,
        }
