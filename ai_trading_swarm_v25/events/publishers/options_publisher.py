import asyncio
from loguru import logger

from events.event_bus import Event, event_bus
from state.global_state import get_global_state
from options.flow_analyzer import OptionsFlowAnalyzer


class OptionsPublisher:
    def __init__(self, config: dict):
        self.config = config
        self.engine = OptionsFlowAnalyzer(config)
        self.state = get_global_state(config)

    async def start(self):
        while True:
            try:
                signal = await self.engine.get_options_signal(asset="BTC")
                await event_bus.publish(Event(type="options_update", payload=signal))
                alt = self.state.alt_data_snapshot or {}
                alt["options"] = signal
                await self.state.set_alt_data_snapshot(alt)
            except Exception as e:
                logger.error(f"[OptionsPublisher] {e}")
            await asyncio.sleep(60)
