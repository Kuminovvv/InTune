"""Client for talking to the local Ollama instance."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import httpx

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = """
System:
Ты — ассистент кандидата на техническом собеседовании. Отвечай кратко, структурно, по делу. Используй контекст из базы знаний (если релевантен). Избегай воды.

User:
Вопрос интервьюера:
"""{question}"""

Контекст:
{context}

Требуемый формат:
- краткое резюме ответа
- 3–6 пунктов (список)
- при необходимости — мини-пример кода (до 20 строк)
"""
""".strip()


@dataclass(slots=True)
class OllamaConfig:
    host: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:7b-instruct"
    timeout_sec: int = 120


class OllamaClient:
    """Async Ollama HTTP client."""

    def __init__(self, config: OllamaConfig):
        self._config = config
        self._client = httpx.AsyncClient(base_url=config.host, timeout=config.timeout_sec)

    async def generate(
        self,
        question: str,
        context_chunks: Iterable[str],
        mode: str = "default",
    ) -> str:
        """Generate an answer from Ollama."""

        context = "\n".join(f"{idx + 1}) {chunk}" for idx, chunk in enumerate(context_chunks)) or "1) (нет релевантных фрагментов)"
        if mode == "shorten":
            instructions = "Сделай подсказку короче и структурнее."
        elif mode == "code":
            instructions = "Добавь мини-пример кода по теме."
        else:
            instructions = ""
        prompt = PROMPT_TEMPLATE.format(question=question, context=context)
        if instructions:
            prompt = f"{prompt}\n\nДополнительные требования: {instructions}"
        payload = {"model": self._config.model, "prompt": prompt, "stream": False}
        logger.debug("Sending prompt to Ollama (%s, mode=%s)", self._config.model, mode)
        response = await self._client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["OllamaClient", "OllamaConfig"]
