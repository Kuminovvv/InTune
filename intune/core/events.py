"""Typed event objects that travel through the pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Sequence


@dataclass(slots=True)
class AudioSegment:
    """Raw audio chunk captured from microphone or system."""

    samples: bytes
    sample_rate: int
    start: datetime
    duration_ms: int
    source: str


@dataclass(slots=True)
class TranscriptSegment:
    """ASR output for a chunk of speech."""

    text: str
    language: str
    start: datetime
    duration_ms: int
    confidence: float


@dataclass(slots=True)
class Intent:
    """Detected intent within the recognised transcript."""

    label: str
    confidence: float
    utterance: str


@dataclass(slots=True)
class RetrievedContext:
    """Represents a retrieved knowledge fragment."""

    source_path: Path
    score: float
    content: str


@dataclass(slots=True)
class AssistantResponse:
    """Structured LLM response with multiple formats."""

    mode: str
    short_form: List[str]
    long_form: str
    metadata: Sequence[str]


__all__ = [
    "AudioSegment",
    "TranscriptSegment",
    "Intent",
    "RetrievedContext",
    "AssistantResponse",
]
