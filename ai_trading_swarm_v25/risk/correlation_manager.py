from typing import Any, Dict, List
from loguru import logger


class CorrelationRiskManager:
    """
    Placeholder correlation manager.
    Always allows trades for now (no multi-asset correlation model yet).
    """

    def __init__(self, config: Dict[str, Any]):
        rm = config["trading"]["risk_management"]
        self.threshold = rm.get("correlation_threshold", 0.85)
        self.max_exposure = rm.get("max_correlated_exposure", 0.08)

    async def check_trade_allowed(
        self,
        proposed_asset: str,
        proposed_size: float,
        open_positions: List[Dict[str, Any]],
    ) -> bool:
        logger.debug(
            f"[CorrelationManager] Allowing {proposed_asset} trade size={proposed_size:.4f}"
        )
        return True
