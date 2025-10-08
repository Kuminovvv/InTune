"""High level orchestration of the assistant workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, Sequence

from .events import AssistantResponse, Intent, RetrievedContext, TranscriptSegment


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, sample_rate: int) -> TranscriptSegment:
        ...


class IntentDetector(Protocol):
    def detect(self, transcript: TranscriptSegment) -> Sequence[Intent]:
        ...


class Retriever(Protocol):
    def retrieve(self, query: str) -> Sequence[RetrievedContext]:
        ...


class LLM(Protocol):
    def respond(
        self,
        transcript: TranscriptSegment,
        intents: Sequence[Intent],
        context: Sequence[RetrievedContext],
        mode: str,
    ) -> AssistantResponse:
        ...


@dataclass(slots=True)
class PipelineDependencies:
    transcriber: Transcriber
    intent_detector: IntentDetector
    retriever: Retriever
    llm: LLM


class InterviewAssistant:
    """Coordinates ASR, intent detection, retrieval and response generation."""

    def __init__(self, deps: PipelineDependencies) -> None:
        self._deps = deps

    def handle_audio(
        self, audio: bytes, sample_rate: int, mode: str = "Short"
    ) -> tuple[TranscriptSegment, AssistantResponse]:
        transcript = self._deps.transcriber.transcribe(audio, sample_rate)
        intents = list(self._deps.intent_detector.detect(transcript))
        if intents:
            contexts = self._collect_contexts(intents, transcript)
        else:
            contexts = self._deps.retriever.retrieve(transcript.text)
        response = self._deps.llm.respond(transcript, intents, contexts, mode)
        return transcript, response

    def _collect_contexts(
        self, intents: Sequence[Intent], transcript: TranscriptSegment
    ) -> Sequence[RetrievedContext]:
        contexts: List[RetrievedContext] = []
        seen: set[str] = set()
        for intent in intents:
            query = f"{intent.label}: {intent.utterance}"
            for item in self._deps.retriever.retrieve(query):
                key = f"{item.source_path}::{item.score:.3f}"
                if key in seen:
                    continue
                contexts.append(item)
                seen.add(key)
        if not contexts:
            contexts = list(self._deps.retriever.retrieve(transcript.text))
        return contexts


__all__ = ["PipelineDependencies", "InterviewAssistant"]
