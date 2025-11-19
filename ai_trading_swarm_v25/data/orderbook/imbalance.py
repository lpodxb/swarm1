import asyncio
from loguru import logger

from events.event_bus import Event, event_bus
from state.global_state import get_global_state


class OrderbookImbalanceEngine:
    def __init__(self, config: dict):
        self.config = config
        self.state = get_global_state(config)

    async def start(self):
        while True:
            try:
                snapshot = {
                    "imbalance": 0.0,
                    "spread_bps": 2.0,
                    "depth_usd": 1_000_000.0,
                }
                await event_bus.publish(Event(type="orderbook_update", payload=snapshot))
                alt = self.state.alt_data_snapshot or {}
                alt["orderbook"] = snapshot
                await self.state.set_alt_data_snapshot(alt)
            except Exception as e:
                logger.error(f"[OrderbookImbalanceEngine] {e}")
            await asyncio.sleep(15)
