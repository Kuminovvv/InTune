"""SQLite based persistence for Q/A history."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Generator, Sequence

from ...core.events import AssistantResponse, TranscriptSegment
from ...domain.qa.history import HistoryItem, HistoryRepository


class SQLiteHistoryRepository(HistoryRepository):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    language TEXT NOT NULL,
                    response_short TEXT NOT NULL,
                    response_long TEXT NOT NULL,
                    mode TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
        finally:
            conn.close()

    def add(self, item: HistoryItem) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history (created_at, transcript, language, response_short, response_long, mode)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.created_at.isoformat(),
                    item.transcript.text,
                    item.transcript.language,
                    "\n".join(item.response.short_form),
                    item.response.long_form,
                    item.response.mode,
                ),
            )
            conn.commit()

    def find_recent(self, limit: int) -> Sequence[HistoryItem]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT created_at, transcript, language, response_short, response_long, mode "
                "FROM history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
        items: list[HistoryItem] = []
        for created_at, transcript, language, response_short, response_long, mode in rows:
            items.append(
                HistoryItem(
                    created_at=datetime.fromisoformat(created_at),
                    transcript=TranscriptSegment(
                        text=transcript,
                        language=language,
                        start=datetime.fromisoformat(created_at),
                        duration_ms=0,
                        confidence=1.0,
                    ),
                    response=AssistantResponse(
                        mode=mode,
                        short_form=response_short.splitlines(),
                        long_form=response_long,
                        metadata=["sqlite"],
                    ),
                )
            )
        return items


__all__ = ["SQLiteHistoryRepository"]
