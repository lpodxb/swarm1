from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

DB_PATH = Path("data/lab.db")


@dataclass
class StrategySummary:
    id: str
    pair: str
    timeframe: str
    params: Dict[str, Any]
    status: str
    last_run_at: Optional[str]
    total_return: Optional[float]
    max_drawdown: Optional[float]
    sharpe: Optional[float]
    win_rate: Optional[float]
    profit_factor: Optional[float]
    num_trades: Optional[int]
    num_backtests: int


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS strategies (
            id TEXT PRIMARY KEY,
            pair TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            params TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS backtests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id TEXT NOT NULL,
            run_at TEXT NOT NULL,
            sample_start TEXT NOT NULL,
            sample_end TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            total_return REAL NOT NULL,
            max_drawdown REAL NOT NULL,
            sharpe REAL NOT NULL,
            win_rate REAL NOT NULL,
            profit_factor REAL NOT NULL,
            num_trades INTEGER NOT NULL,
            equity_path TEXT,
            trades_path TEXT,
            FOREIGN KEY(strategy_id) REFERENCES strategies(id)
        )
        """
    )
    conn.commit()

    cur.execute("PRAGMA table_info(strategies)")
    cols = [row["name"] for row in cur.fetchall()]
    if "status" not in cols:
        logger.info('Adding "status" column to strategies table (default=experimental)')
        cur.execute(
            """
            ALTER TABLE strategies
            ADD COLUMN status TEXT NOT NULL DEFAULT 'experimental'
            """
        )
        conn.commit()

    conn.close()
    logger.info(f"Lab DB initialized at {DB_PATH}")


def upsert_strategy(strategy_id: str, pair: str, timeframe: str, params: Dict[str, Any]) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    params_json = json.dumps(params or {})

    cur.execute("SELECT status FROM strategies WHERE id = ?", (strategy_id,))
    row = cur.fetchone()
    if row is not None:
        status = row["status"]
    else:
        status = "experimental"

    cur.execute(
        """
        INSERT INTO strategies (id, pair, timeframe, params, created_at, updated_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            pair=excluded.pair,
            timeframe=excluded.timeframe,
            params=excluded.params,
            updated_at=excluded.updated_at
        """,
        (strategy_id, pair, timeframe, params_json, now, now, status),
    )
    conn.commit()
    conn.close()


def record_backtest(
    strategy_id: str,
    sample_start: str,
    sample_end: str,
    initial_capital: float,
    metrics: Dict[str, float],
    equity_path: Optional[str] = None,
    trades_path: Optional[str] = None,
) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        """
        INSERT INTO backtests (
            strategy_id,
            run_at,
            sample_start,
            sample_end,
            initial_capital,
            total_return,
            max_drawdown,
            sharpe,
            win_rate,
            profit_factor,
            num_trades,
            equity_path,
            trades_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            strategy_id,
            now,
            sample_start,
            sample_end,
            float(initial_capital),
            float(metrics["total_return"]),
            float(metrics["max_drawdown"]),
            float(metrics["sharpe"]),
            float(metrics["win_rate"]),
            float(metrics["profit_factor"]),
            int(metrics["num_trades"]),
            equity_path,
            trades_path,
        ),
    )
    conn.commit()
    conn.close()


def set_strategy_status(strategy_id: str, status: str) -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE strategies SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.utcnow().isoformat(), strategy_id),
    )
    conn.commit()
    conn.close()


def get_backtests_for_strategy(strategy_id: str) -> List[sqlite3.Row]:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM backtests
        WHERE strategy_id = ?
        ORDER BY run_at DESC
        """,
        (strategy_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_strategies_summary() -> List[Dict[str, Any]]:
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM strategies")
    strat_rows = cur.fetchall()
    strategies = {row["id"]: row for row in strat_rows}

    cur.execute(
        """
        SELECT * FROM backtests
        ORDER BY run_at DESC
        """
    )
    bt_rows = cur.fetchall()
    conn.close()

    latest_bt: Dict[str, sqlite3.Row] = {}
    bt_counts: Dict[str, int] = {}

    for row in bt_rows:
        sid = row["strategy_id"]
        bt_counts[sid] = bt_counts.get(sid, 0) + 1
        if sid not in latest_bt:
            latest_bt[sid] = row

    summaries: List[StrategySummary] = []
    for sid, srow in strategies.items():
        params = json.loads(srow["params"]) if srow["params"] else {}
        status = srow["status"] if "status" in srow.keys() else "experimental"
        bt = latest_bt.get(sid)
        if bt is None:
            summaries.append(
                StrategySummary(
                    id=sid,
                    pair=srow["pair"],
                    timeframe=srow["timeframe"],
                    params=params,
                    status=status,
                    last_run_at=None,
                    total_return=None,
                    max_drawdown=None,
                    sharpe=None,
                    win_rate=None,
                    profit_factor=None,
                    num_trades=None,
                    num_backtests=bt_counts.get(sid, 0),
                )
            )
        else:
            summaries.append(
                StrategySummary(
                    id=sid,
                    pair=srow["pair"],
                    timeframe=srow["timeframe"],
                    params=params,
                    status=status,
                    last_run_at=bt["run_at"],
                    total_return=bt["total_return"],
                    max_drawdown=bt["max_drawdown"],
                    sharpe=bt["sharpe"],
                    win_rate=bt["win_rate"],
                    profit_factor=bt["profit_factor"],
                    num_trades=bt["num_trades"],
                    num_backtests=bt_counts.get(sid, 0),
                )
            )

    return [s.__dict__ for s in summaries]


def get_strategy(strategy_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)
