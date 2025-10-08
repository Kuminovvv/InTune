"""Domain layer wrapper over the Q/A history storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from ...core.events import AssistantResponse, TranscriptSegment


@dataclass(slots=True)
class HistoryItem:
    created_at: datetime
    transcript: TranscriptSegment
    response: AssistantResponse


class HistoryRepository:
    """Interface used by the application service layer."""

    def add(self, item: HistoryItem) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def find_recent(self, limit: int) -> Sequence[HistoryItem]:  # pragma: no cover - interface
        raise NotImplementedError


__all__ = ["HistoryItem", "HistoryRepository"]
