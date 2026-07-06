"""SQLite persistence for the story-time event log (S1, book scale).

Uses the standard-library ``sqlite3`` — no new dependency. This is the first
SQLite-backed store in the analyzer (the roadmap's "storage → SQLite" step for
book scale); it persists a `WorldEvent` list as a queryable table so a long
story's history survives across runs and can be queried ("what happened in
chapter 4?") without reloading the whole analysis. Materialized-state views and a
chunk-level incremental cache build on this table later in S1.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .schemas import WorldEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_events (
    seq         INTEGER PRIMARY KEY,
    section_id  TEXT NOT NULL,
    kind        TEXT NOT NULL,
    entity_kind TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    note        TEXT
)
"""


def _connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute(_SCHEMA)
    return conn


def save_events(path: str | Path, events: list[WorldEvent]) -> None:
    """Persist ``events`` to ``path``, replacing any existing log there."""
    conn = _connect(path)
    try:
        conn.execute("DELETE FROM world_events")
        conn.executemany(
            "INSERT INTO world_events VALUES (?, ?, ?, ?, ?, ?)",
            [(e.seq, e.section_id, e.kind, e.entity_kind, e.entity_id, e.note) for e in events],
        )
        conn.commit()
    finally:
        conn.close()


def load_events(path: str | Path, *, section_id: str | None = None) -> list[WorldEvent]:
    """Load the event log, optionally filtered to one section (a story-time query)."""
    conn = _connect(path)
    try:
        sql = "SELECT seq, section_id, kind, entity_kind, entity_id, note FROM world_events"
        params: tuple = ()
        if section_id is not None:
            sql += " WHERE section_id = ?"
            params = (section_id,)
        sql += " ORDER BY seq"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        WorldEvent(seq=r[0], section_id=r[1], kind=r[2], entity_kind=r[3], entity_id=r[4], note=r[5])
        for r in rows
    ]
