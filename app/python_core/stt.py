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
        self._lock = asyncio.Lock()
        self._model = self._initialise_model(config.use_gpu)

    def _initialise_model(self, use_gpu: bool) -> WhisperModel:
        """Create a Whisper model, falling back to CPU if GPU init fails."""

        device = "cuda" if use_gpu else "cpu"
        compute_type = "float16" if use_gpu else "int8"
        try:
            return WhisperModel(self._config.model, device=device, compute_type=compute_type)
        except Exception as exc:  # pragma: no cover - hardware specific
            if not use_gpu:
                raise
            logger.warning(
                "Failed to initialise faster-whisper on GPU, falling back to CPU: %s",
                exc,
            )
            self._config.use_gpu = False
            return self._initialise_model(False)

    def _ensure_cpu_model(self) -> None:
        """Switch execution to CPU, reusing the helper for model creation."""

        if self._config.use_gpu:
            logger.warning("GPU inference failed, switching faster-whisper to CPU")
        self._config.use_gpu = False
        self._model = self._initialise_model(False)

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

            def _run_transcribe() -> list:
                return list(
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
                )

            try:
                result = await loop.run_in_executor(None, _run_transcribe)
            except (RuntimeError, ValueError) as exc:
                if not self._config.use_gpu:
                    raise
                logger.warning(
                    "faster-whisper GPU inference failed (%s); retrying on CPU", exc
                )
                self._ensure_cpu_model()
                result = await loop.run_in_executor(None, _run_transcribe)
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
