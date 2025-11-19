from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger


@dataclass
class MemoryExample:
    timestamp: str
    sentiment: float
    confidence: float
    risk_level: str
    pnl: Optional[float]
    features: List[float]


@dataclass
class MemoryStats:
    count: int
    with_pnl: int
    win_rate: Optional[float]
    avg_pnl: Optional[float]


class AgentMemory:
    """
    Per-agent decision log for learning / performance tracking.
    """

    def __init__(self, db_path: str, agent_id: str):
        self.db_path = Path(db_path)
        self.agent_id = agent_id
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path.as_posix(), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                features TEXT NOT NULL,
                sentiment REAL NOT NULL,
                confidence REAL NOT NULL,
                risk_level TEXT NOT NULL,
                pnl REAL
            )
            """
        )
        self._conn.commit()
        logger.info(f"AgentMemory initialized for {agent_id} @ {self.db_path}")

    def log_decision(
        self,
        features_vec: List[float],
        sentiment: float,
        confidence: float,
        risk_level: str,
        pnl: Optional[float] = None,
    ) -> int:
        ts = datetime.utcnow().isoformat()
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO decisions (timestamp, agent_id, features, sentiment, confidence, risk_level, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                self.agent_id,
                json.dumps(features_vec),
                float(sentiment),
                float(confidence),
                risk_level,
                pnl,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_recent_examples(self, limit: int = 500) -> List[MemoryExample]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT timestamp, features, sentiment, confidence, risk_level, pnl
            FROM decisions
            WHERE agent_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (self.agent_id, limit),
        )
        rows = cur.fetchall()
        examples: List[MemoryExample] = []
        for r in rows:
            try:
                feats = json.loads(r["features"])
            except Exception:
                feats = []
            examples.append(
                MemoryExample(
                    timestamp=r["timestamp"],
                    sentiment=float(r["sentiment"]),
                    confidence=float(r["confidence"]),
                    risk_level=str(r["risk_level"]),
                    pnl=float(r["pnl"]) if r["pnl"] is not None else None,
                    features=feats,
                )
            )
        return examples

    def get_stats(self, lookback: int = 200) -> MemoryStats:
        examples = self.get_recent_examples(limit=lookback)
        with_pnl = [e for e in examples if e.pnl is not None]
        if not with_pnl:
            return MemoryStats(count=len(examples), with_pnl=0, win_rate=None, avg_pnl=None)
        wins = [e for e in with_pnl if e.pnl > 0]
        win_rate = len(wins) / len(with_pnl) if with_pnl else None
        avg_pnl = sum(e.pnl for e in with_pnl) / len(with_pnl) if with_pnl else None
        return MemoryStats(
            count=len(examples),
            with_pnl=len(with_pnl),
            win_rate=win_rate,
            avg_pnl=avg_pnl,
        )

    def get_similar_examples(
        self,
        features_vec: List[float],
        top_k: int = 5,
        search_limit: int = 300,
    ) -> List[Tuple[MemoryExample, float]]:
        if not features_vec:
            return []

        examples = self.get_recent_examples(limit=search_limit)
        if not examples:
            return []

        q = np.array(features_vec, dtype=float)
        if np.linalg.norm(q) == 0:
            return []

        scored: List[Tuple[MemoryExample, float]] = []
        for ex in examples:
            if not ex.features:
                continue
            v = np.array(ex.features, dtype=float)
            norm_v = np.linalg.norm(v)
            if norm_v == 0:
                continue
            sim = float(np.dot(q, v) / (np.linalg.norm(q) * norm_v))
            scored.append((ex, sim))

        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]
