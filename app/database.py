"""SQLite 持久化层：随应用启动自动建表。"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/data/phase_allocations.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS allocations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    devices       TEXT    NOT NULL,
    capacities    TEXT    NOT NULL,
    feasible      INTEGER NOT NULL,
    assignments   TEXT,
    phase_loads   TEXT,
    load_diff     INTEGER,
    message       TEXT
);
"""


def init_db(db_path: str = DB_PATH) -> None:
    """创建数据目录与表结构；容器启动时幂等执行一次。"""
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript(_SCHEMA)


@contextmanager
def get_conn(db_path: str = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_allocation(record: dict) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO allocations
                (devices, capacities, feasible, assignments, phase_loads, load_diff, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                json.dumps(record["devices"], ensure_ascii=False),
                json.dumps(record["capacities"], ensure_ascii=False),
                1 if record["feasible"] else 0,
                json.dumps(record.get("assignments"), ensure_ascii=False)
                if record.get("assignments") is not None
                else None,
                json.dumps(record.get("phase_loads"), ensure_ascii=False)
                if record.get("phase_loads") is not None
                else None,
                record.get("load_diff"),
                record.get("message"),
            ),
        )
        return int(cursor.lastrowid)


def _row_to_dict(row: sqlite3.Row, *, detail: bool) -> dict:
    base = {
        "id": row["id"],
        "created_at": row["created_at"],
        "feasible": bool(row["feasible"]),
        "load_diff": row["load_diff"],
    }
    if detail:
        base.update(
            {
                "devices": json.loads(row["devices"]),
                "capacities": json.loads(row["capacities"]),
                "assignments": json.loads(row["assignments"])
                if row["assignments"] is not None
                else None,
                "phase_loads": json.loads(row["phase_loads"])
                if row["phase_loads"] is not None
                else None,
                "message": row["message"],
            }
        )
    else:
        base["message"] = row["message"]
    return base


def list_allocations(limit: int = 50, offset: int = 0) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM allocations ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(row, detail=False) for row in rows]


def count_allocations() -> int:
    with get_conn() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM allocations").fetchone()[0])


def get_allocation(allocation_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM allocations WHERE id = ?", (allocation_id,)
        ).fetchone()
        return _row_to_dict(row, detail=True) if row is not None else None
