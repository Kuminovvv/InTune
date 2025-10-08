"""Abstract base classes for speech recognition."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...core.events import TranscriptSegment


class SpeechTranscriber(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes, sample_rate: int) -> TranscriptSegment:
        """Transcribe a chunk of PCM16 audio."""


__all__ = ["SpeechTranscriber"]
