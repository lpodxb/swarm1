from datetime import datetime
from typing import Any, Dict

from loguru import logger


class TelegramScraper:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("TelegramScraper initialized (stub).")

    async def get_telegram_summary(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "signal": 0.0,
            "message_count": 0,
            "avg_urgency": 0.0,
            "messages": [],
        }
