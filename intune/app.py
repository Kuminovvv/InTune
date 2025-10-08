"""Application bootstrap for the InTune assistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .core.config import AppConfig, load_app_config
from .core.logger import configure_logging, logger
from .core.pipeline import InterviewAssistant, PipelineDependencies
from .domain.intent.detector import DEFAULT_RULES, RegexIntentDetector
from .domain.llm.engine import LLMRuntimeConfig, LocalLLM
from .domain.rag.retriever import KnowledgeBaseRetriever, RetrieverConfig
from .domain.qa.history import HistoryItem
from .infra.asr.faster_whisper import FasterWhisperConfig, FasterWhisperTranscriber
from .infra.storage.sqlite import SQLiteHistoryRepository


@dataclass(slots=True)
class AppContext:
    config: AppConfig
    assistant: InterviewAssistant
    history: SQLiteHistoryRepository


def create_app(config_path: Optional[Path] = None) -> AppContext:
    config = load_app_config(config_path)
    configure_logging()

    transcriber = FasterWhisperTranscriber(
        FasterWhisperConfig(
            model_path=str(config.asr.model_path),
            language=config.asr.language,
            beam_size=config.asr.beam_size,
            max_alternatives=config.asr.max_alternatives,
            use_cuda=config.asr.use_cuda,
        )
    )
    intent_detector = RegexIntentDetector(DEFAULT_RULES)
    retriever = KnowledgeBaseRetriever(
        RetrieverConfig(index_path=config.rag.index_path, top_k=config.rag.top_k)
    )
    llm = LocalLLM(
        LLMRuntimeConfig(
            model_path=str(config.llm.model_path),
            context_window=config.llm.context_window,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
    )
    assistant = InterviewAssistant(
        PipelineDependencies(
            transcriber=transcriber,
            intent_detector=intent_detector,
            retriever=retriever,
            llm=llm,
        )
    )
    history = SQLiteHistoryRepository(config.storage.sqlite_path)
    logger.info("Приложение инициализировано")
    return AppContext(config=config, assistant=assistant, history=history)


def handle_transcript(context: AppContext, audio: bytes, sample_rate: int, mode: str = "Short") -> None:
    transcript, response = context.assistant.handle_audio(audio, sample_rate, mode)
    history_item = HistoryItem(created_at=datetime.utcnow(), transcript=transcript, response=response)
    context.history.add(history_item)
    logger.info("Ответ сохранён в журнал")


__all__ = ["AppContext", "create_app", "handle_transcript"]
