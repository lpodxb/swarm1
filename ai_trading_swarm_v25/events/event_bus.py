import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List
from loguru import logger


@dataclass
class Event:
    type: str
    payload: Dict[str, Any]


class EventBus:
    """
    Simple async event bus used by publishers and internal components.
    """

    def __init__(self):
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers: Dict[str, List[Callable[[Event], Any]]] = {}
        self.processed_events: int = 0
        self.dropped_events: int = 0

    def subscribe(self, event_type: str, handler: Callable[[Event], Any]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: Event) -> None:
        await self._queue.put(event)

    async def run(self):
        logger.info("EventBus running...")
        while True:
            try:
                event = await self._queue.get()
                handlers = self._subscribers.get(event.type, [])

                for h in handlers:
                    try:
                        res = h(event)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        logger.error(f"Event handler error for {event.type}: {e}")

                self.processed_events += 1

            except Exception as e:
                logger.error(f"EventBus error: {e}")


# THIS MUST EXIST — THIS IS WHAT main_v2_5 IMPORTS
event_bus = EventBus()
