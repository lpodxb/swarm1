from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

DB_PATH = Path("data/journal.db")


@dataclass
class JournalRow:
    timestamp: str
    entry_type: str
    context_symbol: Optional[str]
    context_timeframe: Optional[str]
    payload: Dict[str, Any] = field(default_factory=dict)


def _get_conn() -> sqlite3.Connection:
    """
    Open a SQLite connection to the journal DB.
    Ensures the directory exists and uses row_factory for dict-like access.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Create the journal table if it does not exist.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            context_symbol TEXT,
            context_timeframe TEXT,
            payload TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    logger.info(f"Journal DB initialized at {DB_PATH}")


def insert_entry(
    entry_type: str,
    context_symbol: Optional[str],
    context_timeframe: Optional[str],
    payload: Dict[str, Any],
) -> None:
    """
    Insert a single journal row.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO journal (timestamp, entry_type, context_symbol, context_timeframe, payload)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            datetime.utcnow().isoformat(),
            entry_type,
            context_symbol,
            context_timeframe,
            json.dumps(payload or {}),
        ),
    )
    conn.commit()
    conn.close()


def fetch_recent(limit: int = 100) -> List[JournalRow]:
    """
    Fetch the most recent N journal entries.
    """
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM journal
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    result: List[JournalRow] = []
    for r in rows:
        try:
            payload = json.loads(r["payload"] or "{}")
        except Exception:
            payload = {}
        result.append(
            JournalRow(
                timestamp=r["timestamp"],
                entry_type=r["entry_type"],
                context_symbol=r["context_symbol"],
                context_timeframe=r["context_timeframe"],
                payload=payload,
            )
        )
    return result
