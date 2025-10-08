"""Adapter for local LLM execution with fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ...core.events import AssistantResponse, Intent, RetrievedContext, TranscriptSegment

try:  # pragma: no cover - optional dependency
    from llama_cpp import Llama
except Exception:  # pragma: no cover
    Llama = None  # type: ignore


@dataclass(slots=True)
class LLMRuntimeConfig:
    model_path: str
    context_window: int
    temperature: float
    max_tokens: int


class LocalLLM:
    """Light wrapper around llama.cpp with a templated fallback."""

    def __init__(self, config: LLMRuntimeConfig) -> None:
        self._config = config
        self._llama = None
        if Llama is not None:
            try:
                self._llama = Llama(
                    model_path=str(config.model_path),
                    n_ctx=config.context_window,
                    temperature=config.temperature,
                )
            except Exception:
                self._llama = None

    def respond(
        self,
        transcript: TranscriptSegment,
        intents: Sequence[Intent],
        context: Sequence[RetrievedContext],
        mode: str,
    ) -> AssistantResponse:
        prompt = self._build_prompt(transcript, intents, context, mode)
        if self._llama is None:
            return self._fallback(prompt, mode)
        completion = self._llama(
            prompt=prompt,
            max_tokens=self._config.max_tokens,
            stop=["</response>"]
        )
        text = completion["choices"][0]["text"].strip()
        short, long = self._split_response(text)
        return AssistantResponse(mode=mode, short_form=short, long_form=long, metadata=["llama.cpp"])

    def _build_prompt(
        self,
        transcript: TranscriptSegment,
        intents: Sequence[Intent],
        context: Sequence[RetrievedContext],
        mode: str,
    ) -> str:
        context_text = "\n".join(f"[{c.score:.3f}] {c.content}" for c in context)
        intent_text = ", ".join(f"{i.label}:{i.confidence:.2f}" for i in intents) or "none"
        return (
            "<system>You are an interview co-pilot that answers briefly and precisely.</system>\n"
            f"<mode>{mode}</mode>\n"
            f"<intents>{intent_text}</intents>\n"
            f"<context>{context_text}</context>\n"
            f"<transcript>{transcript.text}</transcript>\n"
            "<response>"
        )

    def _fallback(self, prompt: str, mode: str) -> AssistantResponse:
        short = ["LLM не инициализирован", "Проверьте путь к модели"]
        long = (
            "Локальная модель не загружена. "
            "Убедитесь, что библиотека llama-cpp-python установлена и путь к весам корректен."
        )
        return AssistantResponse(mode=mode, short_form=short, long_form=long, metadata=["fallback"])

    @staticmethod
    def _split_response(text: str) -> tuple[list[str], str]:
        lines = [line.strip("-* ") for line in text.splitlines() if line.strip()]
        if not lines:
            return ["Пустой ответ"], ""
        if len(lines) == 1:
            return [lines[0]], lines[0]
        return lines[:2], "\n".join(lines)


__all__ = ["LLMRuntimeConfig", "LocalLLM"]
