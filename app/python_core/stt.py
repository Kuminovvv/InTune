"""Speech-to-text utilities backed by faster-whisper."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Iterable

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SttConfig:
    model: str = "medium"
    use_gpu: bool = True
    language: str = "auto"
    beam_size: int = 5
    vad_filter: bool = True


class SpeechToTextEngine:
    """Wrapper around faster-whisper for streaming transcription."""

    def __init__(self, config: SttConfig):
        self._config = config
        device = "cuda" if config.use_gpu else "cpu"
        compute_type = "float16" if config.use_gpu else "int8"
        try:
            self._model = WhisperModel(config.model, device=device, compute_type=compute_type)
        except Exception as exc:  # pragma: no cover - hardware specific
            if not config.use_gpu:
                raise
            logger.warning(
                "Failed to initialise faster-whisper on GPU, falling back to CPU: %s",
                exc,
            )
            self._config.use_gpu = False
            self._model = WhisperModel(config.model, device="cpu", compute_type="int8")
        self._lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._config.model

    async def transcribe(self, pcm16: bytes, sample_rate: int) -> str:
        """Transcribe a PCM16 buffer into text."""

        if not pcm16:
            return ""
        loop = asyncio.get_running_loop()
        async with self._lock:
            audio = np.frombuffer(pcm16, np.int16).astype(np.float32) / 32768.0
            result = await loop.run_in_executor(
                None,
                lambda: list(
                    self._model.transcribe(
                        audio,
                        beam_size=self._config.beam_size,
                        language=None if self._config.language == "auto" else self._config.language,
                        vad_filter=self._config.vad_filter,
                        temperature=0.0,
                        compression_ratio_threshold=2.4,
                        log_prob_threshold=-1.0,
                        initial_prompt=None,
                    )
                ),
            )
        if not result:
            return ""
        transcript = " ".join(segment.text.strip() for segment in result if segment.text)
        return transcript.strip()

    async def stream_transcribe(self, chunks: Iterable[bytes], sample_rate: int) -> AsyncIterator[str]:
        """Transcribe chunks sequentially yielding intermediate results."""

        buffer = b"".join(chunks)
        text = await self.transcribe(buffer, sample_rate)
        if text:
            yield text


__all__ = ["SpeechToTextEngine", "SttConfig"]
