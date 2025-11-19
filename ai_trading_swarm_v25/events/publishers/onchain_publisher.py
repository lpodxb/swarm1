import asyncio
from loguru import logger

from events.event_bus import Event, event_bus
from state.global_state import get_global_state
from onchain.whale_tracker import OnChainIntelEngine


class OnChainPublisher:
    def __init__(self, config: dict):
        self.config = config
        self.engine = OnChainIntelEngine(config)
        self.state = get_global_state(config)

    async def start(self):
        while True:
            try:
                summary = await self.engine.get_onchain_summary()
                await event_bus.publish(Event(type="onchain_update", payload=summary))
                alt = self.state.alt_data_snapshot or {}
                alt["onchain"] = summary
                await self.state.set_alt_data_snapshot(alt)
            except Exception as e:
                logger.error(f"[OnChainPublisher] {e}")
            await asyncio.sleep(60)
