import asyncio
from loguru import logger

from events.event_bus import Event, event_bus
from state.global_state import get_global_state


class FundingRateEngine:
    def __init__(self, config: dict):
        self.config = config
        self.state = get_global_state(config)

    async def start(self):
        while True:
            try:
                data = {
                    "funding_rate": 0.0001,
                    "long_short_ratio": 1.0,
                }
                await event_bus.publish(Event(type="funding_update", payload=data))
                alt = self.state.alt_data_snapshot or {}
                alt["funding"] = data
                await self.state.set_alt_data_snapshot(alt)
            except Exception as e:
                logger.error(f"[FundingRateEngine] {e}")
            await asyncio.sleep(300)
