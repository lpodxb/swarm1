from __future__ import annotations

import asyncio

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from state.global_state import get_global_state

try:
    from nautilus_trader.application import Application, ApplicationConfig
    from nautilus_trader.config import load as load_nautilus_config
    from nautilus_trader.core.uuid import UUID4
    from nautilus_trader.model.enums import OrderSide, TimeInForce
    from nautilus_trader.model.identifiers import InstrumentId, PositionId
    from nautilus_trader.model.orders import MarketOrder

    NAUTILUS_AVAILABLE = True
except ImportError:
    NAUTILUS_AVAILABLE = False

# Do NOT initialize global state here.
# It will be provided when main_v2_5 creates the ExecutionEngine.
_global_state = None


@dataclass
class Position:
    position_id: str
    symbol: str
    side: str
    qty: float
    entry_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class ExecutionEngine:
    """
    Execution engine with safe dry-run default, Nautilus-backed when available.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.nautilus_config_path: str = config["trading"].get(
            "nautilus_config_path", "configs/nautilus_binance_testnet.yaml"
        )
        self.initial_capital: float = float(config["trading"].get("initial_capital", 10_000))
        self.base_currency: str = config["trading"].get("base_currency", "USDT")
        self.testnet: bool = bool(config["trading"].get("testnet", True))

        self._app: Optional["Application"] = None
        self._app_task: Optional[asyncio.Task] = None
        self._positions: Dict[str, Position] = {}
        self._lock = asyncio.Lock()
        self._use_nautilus: bool = False

        logger.info(
            f"ExecutionEngine initialized (Nautilus available={NAUTILUS_AVAILABLE}, "
            f"testnet={self.testnet}, config={self.nautilus_config_path})"
        )

    async def start(self) -> None:
        async with self._lock:
            if self._app is not None or self._use_nautilus:
                return

            if not NAUTILUS_AVAILABLE:
                logger.warning("Nautilus not installed; ExecutionEngine running in dry-run mode.")
                self._use_nautilus = False
                return

            try:
                logger.info("Starting Nautilus Trader application for ExecutionEngine...")
                nautilus_cfg: ApplicationConfig = load_nautilus_config(self.naultilus_config_path)
                self._app = Application(nautilus_cfg)
                self._app_task = asyncio.create_task(self._app.run(), name="nautilus_app")
                await asyncio.sleep(3.0)
                self._use_nautilus = True
                logger.success("Nautilus Trader started; using live execution.")
            except Exception as exc:
                logger.error(f"Failed to start Nautilus: {exc}. Falling back to dry-run.")
                self._app = None
                self._app_task = None
                self._use_nautilus = False

    async def stop(self) -> None:
        async with self._lock:
            if not self._use_naultilus or self._app is None:
                return
            logger.warning("Stopping Nautilus Trader application (ExecutionEngine.stop)...")
            try:
                await self._app.stop()
            except Exception as exc:
                logger.error(f"Error stopping Nautilus app: {exc}")
            if self._app_task:
                self._app_task.cancel()
                with contextlib.suppress(Exception):
                    await self._app_task
            self._app = None
            self._app_task = None
            self._use_naultilus = False
            logger.info("ExecutionEngine fully stopped.")

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        async with self._lock:
            result = []
            for pos in self._positions.values():
                result.append(
                    {
                        "asset": pos.symbol.split("/")[0],
                        "symbol": pos.symbol,
                        "side": pos.side,
                        "size": pos.qty / self.initial_capital,
                        "qty": pos.qty,
                        "entry_price": pos.entry_price,
                        "unrealized_pnl": pos.unrealized_pnl,
                        "realized_pnl": pos.realized_pnl,
                        "opened_at": pos.opened_at.isoformat(),
                        "updated_at": pos.updated_at.isoformat(),
                    }
                )
            return result

    # ... (keep the dry-run and Nautilus execution methods we already wrote)
