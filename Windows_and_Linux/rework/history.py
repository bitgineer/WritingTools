"""Local rewrite history.

A small SQLite database stores the option, the original, the revision, and
the counts. Nothing leaves the device. The store is intentionally boring so
the window can search it and the user can delete any row or clear it all.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from rework.model import Rework

SCHEMA = """
CREATE TABLE IF NOT EXISTS reworks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    option TEXT NOT NULL,
    original TEXT NOT NULL,
    revised TEXT NOT NULL,
    changed_words INTEGER NOT NULL,
    removed_words INTEGER NOT NULL,
    added_words INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reworks_id ON reworks(id DESC);
"""


@dataclass(frozen=True)
class HistoryEntry:
    id: int
    created_at: str
    option: str
    original: str
    revised: str
    changed_words: int
    removed_words: int
    added_words: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "HistoryEntry":
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            option=row["option"],
            original=row["original"],
            revised=row["revised"],
            changed_words=row["changed_words"],
            removed_words=row["removed_words"],
            added_words=row["added_words"],
        )


class HistoryStore:
    def __init__(self, path: str | Path, limit: int = 500):
        self.path = Path(path)
        self.limit = max(0, int(limit))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(SCHEMA)

    def add(self, rework: Rework) -> int:
        stats = rework.diff.stats
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reworks
                    (created_at, option, original, revised,
                     changed_words, removed_words, added_words)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    rework.option,
                    rework.original,
                    rework.revised,
                    stats.changed_words,
                    stats.removed_words,
                    stats.added_words,
                ),
            )
            entry_id = int(cursor.lastrowid)
            if self.limit:
                connection.execute(
                    """
                    DELETE FROM reworks
                    WHERE id NOT IN (
                        SELECT id FROM reworks ORDER BY id DESC LIMIT ?
                    )
                    """,
                    (self.limit,),
                )
        return entry_id

    def entries(self, query: str = "", limit: int = 200) -> list[HistoryEntry]:
        query = query.strip()
        with self._connection() as connection:
            if query:
                like = f"%{query}%"
                rows = connection.execute(
                    """
                    SELECT * FROM reworks
                    WHERE option LIKE ? COLLATE NOCASE
                       OR original LIKE ? COLLATE NOCASE
                       OR revised LIKE ? COLLATE NOCASE
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (like, like, like, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM reworks ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [HistoryEntry.from_row(row) for row in rows]

    def get(self, entry_id: int) -> HistoryEntry | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM reworks WHERE id = ?", (entry_id,)
            ).fetchone()
        return HistoryEntry.from_row(row) if row else None

    def delete(self, entry_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM reworks WHERE id = ?", (entry_id,)
            )
            return cursor.rowcount > 0

    def clear(self) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM reworks")

    def count(self) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM reworks").fetchone()
        return int(row["total"])
