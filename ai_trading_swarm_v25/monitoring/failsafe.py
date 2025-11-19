import asyncio
from typing import Any, Dict

from loguru import logger
import psutil

from state.global_state import get_global_state


class FailsafeMonitor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cfg = config["failsafe"]
        self.state = get_global_state(config)

    async def start(self):
        interval = self.cfg.get("check_interval_seconds", 15)
        while True:
            try:
                await self._check_once()
            except Exception as e:
                logger.error(f"[Failsafe] error: {e}")
            await asyncio.sleep(interval)

    async def _check_once(self):
        ram = psutil.virtual_memory()
        ram_pct = ram.percent
        if ram_pct > self.cfg.get("max_ram_usage_pct", 92):
            logger.error(f"[Failsafe] RAM {ram_pct:.1f}% > limit; pausing trading.")
            self.state.is_trading_paused = True
            return

        max_dd = self.cfg.get("max_daily_loss_pct", 0.05)
        init_cap = self.state.config["trading"]["initial_capital"]
        if self.state.daily_pnl < -max_dd * init_cap:
            logger.error(
                f"[Failsafe] daily PnL {self.state.daily_pnl:.2f} < -{max_dd*100:.1f}% of capital; pausing."
            )
            self.state.is_trading_paused = True
