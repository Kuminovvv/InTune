"""Main orchestration layer tying together audio, STT, RAG and the LLM."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable, Deque, Iterable, Optional

import webrtcvad

from .audio import AudioCapturer, AudioConfig
from .config import AppConfig
from .llm import OllamaClient, OllamaConfig
from .rag import KnowledgeStore
from .stt import SpeechToTextEngine, SttConfig

logger = logging.getLogger(__name__)


AnswerCallback = Callable[[str, str], Awaitable[None]]
PartialCallback = Callable[[str], Awaitable[None]]
StateCallback = Callable[[str, str], Awaitable[None]]
ErrorCallback = Callable[[str, str], Awaitable[None]]


@dataclass(slots=True)
class CopilotCallbacks:
    on_answer: AnswerCallback
    on_partial: PartialCallback
    on_state: StateCallback
    on_error: ErrorCallback


class InterviewCopilot:
    """Coordinates the end-to-end audio-to-hint pipeline."""

    def __init__(self, config: AppConfig, callbacks: CopilotCallbacks):
        self._config = config
        self._callbacks = callbacks
        self._audio = AudioCapturer(AudioConfig(**vars(config.audio)))
        self._vad = webrtcvad.Vad(config.vad.aggressiveness)
        self._stt = SpeechToTextEngine(SttConfig(**vars(config.stt)))
        self._ollama = OllamaClient(OllamaConfig(**vars(config.ollama)))
        self._rag = KnowledgeStore(config.rag.db_path, config.rag.index_path, config.rag.embed_model)
        self._running = False
        self._consumer_task: Optional[asyncio.Task[None]] = None
        self._buffer: Deque[bytes] = deque()
        self._last_transcript: str = ""
        self._partial_task: Optional[asyncio.Task[None]] = None
        self._last_partial_timestamp: float = 0.0
        block_ms = max(1, self._config.audio.block_ms)
        self._frame_duration = block_ms / 1000.0
        self._max_buffer_frames = max(1, int(15.0 / self._frame_duration))
        self._partial_interval = 0.6

    @property
    def profile(self) -> str:
        return self._config.profile

    def set_profile(self, profile: str) -> None:
        self._config.profile = profile

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._buffer.clear()
        self._last_partial_timestamp = 0.0
        await self._callbacks.on_state("listening", "")
        self._audio.start()
        loop = asyncio.get_running_loop()
        self._consumer_task = loop.create_task(self._consume_frames())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._cancel_partial_task()
        if self._consumer_task:
            self._consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer_task
        self._audio.stop()
        await self._callbacks.on_state("ready", "")

    async def _consume_frames(self) -> None:
        silence_duration = 0.0
        frame_duration = self._frame_duration
        try:
            async for frame in self._audio.frames():
                if not self._running:
                    break
                is_speech = self._vad.is_speech(frame.data, self._config.audio.sample_rate)
                if is_speech:
                    self._buffer.append(frame.data)
                    if len(self._buffer) > self._max_buffer_frames:
                        self._buffer.popleft()
                    silence_duration = 0.0
                    await self._maybe_emit_partial()
                else:
                    if not self._buffer:
                        continue
                    silence_duration += frame_duration
                    if silence_duration >= self._config.vad.silence_sec:
                        await self._process_buffer()
                        self._buffer.clear()
                        silence_duration = 0.0
                        await self._callbacks.on_state("listening", "")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Audio consumer failed")
            await self._callbacks.on_error("audio", str(exc))
            await self._callbacks.on_state("ready", "")

    async def _process_buffer(self) -> None:
        pcm = b"".join(self._buffer)
        await self._cancel_partial_task()
        try:
            transcript = await self._stt.transcribe(pcm, self._config.audio.sample_rate)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Speech-to-text failure")
            await self._callbacks.on_error("stt", str(exc))
            await self._callbacks.on_state("ready", "")
            return
        if not transcript:
            return
        self._last_transcript = transcript
        await self._callbacks.on_partial(transcript)
        await self._callbacks.on_state("thinking", transcript)
        try:
            hits = self._rag.search(transcript, self._config.rag.top_k, self.profile)
        except Exception as exc:  # noqa: BLE001
            logger.exception("RAG search failure")
            await self._callbacks.on_error("rag", str(exc))
            hits = []
        try:
            hint = await self._ollama.generate(transcript, [chunk.text for chunk in hits], mode="default")
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM generation failure")
            await self._callbacks.on_error("llm", str(exc))
            await self._callbacks.on_state("ready", "")
            return
        await self._callbacks.on_answer(transcript, hint)
        await self._callbacks.on_state("ready", "")

    async def _maybe_emit_partial(self) -> None:
        now = time.monotonic()
        if now - self._last_partial_timestamp < self._partial_interval:
            return
        if self._partial_task and not self._partial_task.done():
            return
        pcm = b"".join(self._buffer)
        if not pcm:
            return
        loop = asyncio.get_running_loop()
        self._partial_task = loop.create_task(self._emit_partial(pcm))

    async def _emit_partial(self, pcm: bytes) -> None:
        try:
            transcript = await self._stt.transcribe(pcm, self._config.audio.sample_rate)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Partial transcription failed")
            await self._callbacks.on_error("stt", str(exc))
            return
        if transcript:
            await self._callbacks.on_partial(transcript)
            self._last_partial_timestamp = time.monotonic()

    async def _cancel_partial_task(self) -> None:
        if not self._partial_task:
            return
        task = self._partial_task
        self._partial_task = None
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def shorten_last(self) -> None:
        if not self._last_transcript:
            return
        try:
            hits = self._rag.search(self._last_transcript, self._config.rag.top_k, self.profile)
        except Exception as exc:  # noqa: BLE001
            logger.exception("RAG search failure")
            await self._callbacks.on_error("rag", str(exc))
            hits = []
        try:
            hint = await self._ollama.generate(self._last_transcript, [chunk.text for chunk in hits], mode="shorten")
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM generation failure")
            await self._callbacks.on_error("llm", str(exc))
            return
        await self._callbacks.on_answer(self._last_transcript, hint)

    async def code_hint(self) -> None:
        if not self._last_transcript:
            return
        try:
            hits = self._rag.search(self._last_transcript, self._config.rag.top_k, self.profile)
        except Exception as exc:  # noqa: BLE001
            logger.exception("RAG search failure")
            await self._callbacks.on_error("rag", str(exc))
            hits = []
        try:
            hint = await self._ollama.generate(self._last_transcript, [chunk.text for chunk in hits], mode="code")
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM generation failure")
            await self._callbacks.on_error("llm", str(exc))
            return
        await self._callbacks.on_answer(self._last_transcript, hint)

    async def reindex(self, paths: Iterable[str]) -> int:
        from . import ingestion

        await self._callbacks.on_state("reindex", "")
        try:
            chunks = await ingestion.build_chunks(paths, self.profile, self._config.rag.embed_model)
            self._rag.replace_all(chunks)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Reindex failed")
            await self._callbacks.on_error("rag", str(exc))
            await self._callbacks.on_state("ready", "")
            raise
        await self._callbacks.on_state("ready", f"Добавлено документов: {len(chunks)}")
        return len(chunks)

    async def update_config(self, payload: dict) -> None:
        audio_changed = "audio" in payload
        rag_changed = "rag" in payload and any(
            key in payload["rag"] for key in ("db_path", "index_path", "embed_model")
        )
        self._config.update_from_payload(payload)
        self._vad = webrtcvad.Vad(self._config.vad.aggressiveness)
        if audio_changed:
            was_running = self._running
            if was_running:
                await self.stop()
            self._audio = AudioCapturer(AudioConfig(**vars(self._config.audio)))
            if was_running:
                await self.start()
        if rag_changed:
            self._rag = KnowledgeStore(self._config.rag.db_path, self._config.rag.index_path, self._config.rag.embed_model)

    async def shutdown(self) -> None:
        await self.stop()
        await self._ollama.close()


__all__ = ["InterviewCopilot", "CopilotCallbacks"]
