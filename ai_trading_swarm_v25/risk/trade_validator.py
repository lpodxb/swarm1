from typing import Any, Dict
from loguru import logger


class TradeValidator:
    """
    Basic trade validator to protect against oversized trades,
    slippage, spread, and daily loss conditions if needed.
    """

    def __init__(self, config: Dict[str, Any]):
        self.cfg = config["trade_validator"]

    async def validate(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        symbol = trade.get("symbol", "")
        position_frac = float(trade.get("position_frac", 0.0))

        # Reject obviously invalid sizes
        if position_frac <= 0:
            return {"valid": False, "reason": "position_frac <= 0"}

        # Hard safety cap (for dry run; can be adjusted later)
        if position_frac > 0.2:
            logger.warning(
                f"[TradeValidator] Rejecting trade: {symbol} frac={position_frac:.2f} too large"
            )
            return {"valid": False, "reason": "position_frac too large (>20%)"}

        logger.debug(f"[TradeValidator] Approving {symbol} trade @ {position_frac:.2%}")
        return {"valid": True, "reason": "ok"}
