"""Faster-Whisper based implementation of the speech transcriber."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ...core.events import TranscriptSegment
from ...domain.asr.base import SpeechTranscriber

try:  # pragma: no cover
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover
    WhisperModel = None  # type: ignore


@dataclass(slots=True)
class FasterWhisperConfig:
    model_path: str
    language: Optional[str]
    beam_size: int
    max_alternatives: int
    use_cuda: bool


class FasterWhisperTranscriber(SpeechTranscriber):
    def __init__(self, config: FasterWhisperConfig) -> None:
        self._config = config
        self._model = None
        if WhisperModel is not None:
            device = "cuda" if config.use_cuda else "cpu"
            try:
                self._model = WhisperModel(config.model_path, device=device)
            except Exception:
                self._model = None

    def transcribe(self, audio: bytes, sample_rate: int) -> TranscriptSegment:
        if self._model is None:
            return TranscriptSegment(
                text="", language=self._config.language or "unknown", start=datetime.utcnow(), duration_ms=0, confidence=0.0
            )
        segments, info = self._model.transcribe(
            audio,
            language=self._config.language,
            beam_size=self._config.beam_size,
            best_of=self._config.max_alternatives,
        )
        text = " ".join(segment.text for segment in segments)
        return TranscriptSegment(
            text=text.strip(),
            language=info.language or self._config.language or "unknown",
            start=datetime.utcnow(),
            duration_ms=int(info.duration * 1000),
            confidence=float(info.avg_logprob or 0.0),
        )


__all__ = ["FasterWhisperConfig", "FasterWhisperTranscriber"]
