from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger

from journal.storage import init_db, insert_entry, fetch_recent


class JournalEngine:
    """
    Wrapper for writing structured journal entries:
    - trades (with consensus/meta)
    - regime snapshots
    - info / error notes
    """

    def __init__(self):
        init_db()
        logger.info("JournalEngine initialized.")

    def log_trade(
        self,
        symbol: str,
        timeframe: str,
        trade: Dict[str, Any],
        consensus: Dict[str, Any],
    ) -> None:
        payload = {
            "event": "trade",
            "trade": trade,
            "consensus": {
                "sentiment": consensus.get("sentiment"),
                "confidence": consensus.get("confidence"),
                "direction": consensus.get("direction"),
                "meta": consensus.get("meta", {}),
            },
        }
        insert_entry("trade", symbol, timeframe, payload)

    def log_regime(
        self,
        symbol: str,
        timeframe: str,
        regime: str,
        features: Dict[str, Any],
    ) -> None:
        payload = {
            "event": "regime",
            "regime": regime,
            "features": features,
        }
        insert_entry("regime", symbol, timeframe, payload)

    def log_info(
        self,
        symbol: str | None,
        timeframe: str | None,
        message: str,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        insert_entry(
            "info",
            symbol,
            timeframe,
            {"message": message, "extra": extra or {}},
        )

    def log_error(
        self,
        symbol: str | None,
        timeframe: str | None,
        message: str,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        insert_entry(
            "error",
            symbol,
            timeframe,
            {"message": message, "extra": extra or {}},
        )


def get_recent_entries(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Convenience for API/UI: returns list[dict] from the DB.
    """
    return [r.__dict__ for r in fetch_recent(limit)]
