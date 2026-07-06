"""Chunk-level incremental cache (S1, book scale).

Re-analyzing a novel where you edited one chapter shouldn't re-run the LLM on all
forty. This caches each chapter's `WorldDiff` so unchanged chapters are reused.

Correctness hinges on the key: a chapter's extraction depends on **both** its text
*and* the entities established before it (the chunked Lector is handed
entities-so-far to resolve recurring characters). So the key is a hash of
``chapter_text + entities_so_far``. Consequences, which are the right ones:

- Edit the *last* chapter → only it misses; every earlier chapter's text and
  incoming context are unchanged, so they hit. One re-extraction.
- Edit an *early* chapter → it misses, its diff changes, which changes the
  entities-so-far for every later chapter, so they miss too. The edit correctly
  cascades to everything downstream that depends on it.

Backed by stdlib ``sqlite3`` (shared with the event store); no new dependency. The
cache is global (not under a per-text key), so an unchanged chapter hits even
after edits elsewhere in the book, and across re-runs.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .schemas import WorldDiff

_SCHEMA = "CREATE TABLE IF NOT EXISTS chapter_diffs (key TEXT PRIMARY KEY, diff_json TEXT NOT NULL)"


def chapter_key(chapter_text: str, entities_so_far: str) -> str:
    return hashlib.sha256(f"{chapter_text}\x00{entities_so_far}".encode("utf-8")).hexdigest()[:16]


@dataclass
class ChunkCache:
    conn: sqlite3.Connection

    @classmethod
    def open(cls, base_dir: str | Path) -> "ChunkCache":
        base = Path(base_dir)
        base.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(base / "chunks.sqlite"))
        conn.execute(_SCHEMA)
        return cls(conn=conn)

    def get(self, key: str) -> WorldDiff | None:
        row = self.conn.execute("SELECT diff_json FROM chapter_diffs WHERE key = ?", (key,)).fetchone()
        return WorldDiff.model_validate_json(row[0]) if row else None

    def put(self, key: str, diff: WorldDiff) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO chapter_diffs (key, diff_json) VALUES (?, ?)",
            (key, diff.model_dump_json()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
