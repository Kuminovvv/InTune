"""Main orchestration layer tying together audio, STT, RAG and the LLM."""

from __future__ import annotations

import asyncio
import contextlib
import logging
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

    @property
    def profile(self) -> str:
        return self._config.profile

    def set_profile(self, profile: str) -> None:
        self._config.profile = profile

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self._callbacks.on_state("listening", "")
        self._audio.start()
        loop = asyncio.get_running_loop()
        self._consumer_task = loop.create_task(self._consume_frames())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer_task
        self._audio.stop()
        await self._callbacks.on_state("ready", "")

    async def _consume_frames(self) -> None:
        silence_duration = 0.0
        sample_rate = self._config.audio.sample_rate
        frame_duration = self._config.audio.block_ms / 1000.0
        async for frame in self._audio.frames():
            if not self._running:
                break
            is_speech = self._vad.is_speech(frame.data, sample_rate)
            if is_speech:
                self._buffer.append(frame.data)
                silence_duration = 0.0
            else:
                silence_duration += frame_duration
                if silence_duration >= self._config.vad.silence_sec and self._buffer:
                    await self._process_buffer()
                    self._buffer.clear()

    async def _process_buffer(self) -> None:
        pcm = b"".join(self._buffer)
        transcript = await self._stt.transcribe(pcm, self._config.audio.sample_rate)
        if not transcript:
            return
        self._last_transcript = transcript
        await self._callbacks.on_partial(transcript)
        await self._callbacks.on_state("thinking", transcript)
        hits = self._rag.search(transcript, self._config.rag.top_k, self.profile)
        hint = await self._ollama.generate(transcript, [chunk.text for chunk in hits], mode="default")
        await self._callbacks.on_answer(transcript, hint)
        await self._callbacks.on_state("ready", "")

    async def shorten_last(self) -> None:
        if not self._last_transcript:
            return
        hits = self._rag.search(self._last_transcript, self._config.rag.top_k, self.profile)
        hint = await self._ollama.generate(self._last_transcript, [chunk.text for chunk in hits], mode="shorten")
        await self._callbacks.on_answer(self._last_transcript, hint)

    async def code_hint(self) -> None:
        if not self._last_transcript:
            return
        hits = self._rag.search(self._last_transcript, self._config.rag.top_k, self.profile)
        hint = await self._ollama.generate(self._last_transcript, [chunk.text for chunk in hits], mode="code")
        await self._callbacks.on_answer(self._last_transcript, hint)

    async def reindex(self, paths: Iterable[str]) -> int:
        from . import ingestion

        await self._callbacks.on_state("reindex", "")
        chunks = await ingestion.build_chunks(paths, self.profile, self._config.rag.embed_model)
        self._rag.reset_index()
        self._rag.add_documents(chunks)
        await self._callbacks.on_state("ready", f"Добавлено документов: {len(chunks)}")
        return len(chunks)

    async def update_config(self, payload: dict) -> None:
        audio_changed = "audio" in payload
        self._config.update_from_payload(payload)
        self._vad = webrtcvad.Vad(self._config.vad.aggressiveness)
        if audio_changed:
            was_running = self._running
            if was_running:
                await self.stop()
            self._audio = AudioCapturer(AudioConfig(**vars(self._config.audio)))
            if was_running:
                await self.start()

    async def shutdown(self) -> None:
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._consumer_task
        self._audio.stop()
        await self._ollama.close()


__all__ = ["InterviewCopilot", "CopilotCallbacks"]
