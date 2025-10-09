"""Rule-based intent detector to bootstrap the assistant."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence

from ...core.events import Intent, TranscriptSegment


@dataclass(slots=True)
class IntentRule:
    label: str
    pattern: re.Pattern[str]
    confidence: float


class RegexIntentDetector:
    """Detects interview related intents using configurable regex rules."""

    def __init__(self, rules: Sequence[IntentRule]) -> None:
        self._rules = list(rules)

    def detect(self, transcript: TranscriptSegment) -> Sequence[Intent]:
        intents: List[Intent] = []
        for rule in self._rules:
            if rule.pattern.search(transcript.text):
                intents.append(
                    Intent(
                        label=rule.label,
                        confidence=rule.confidence,
                        utterance=transcript.text,
                    )
                )
        return intents


DEFAULT_RULES = [
    IntentRule("candidate_question", re.compile(r"(?:как|что|почему)[^?]*\?", re.IGNORECASE), 0.6),
    IntentRule("salary_discussion", re.compile(r"(?:зарплат|compensation)", re.IGNORECASE), 0.5),
]


__all__ = ["IntentRule", "RegexIntentDetector", "DEFAULT_RULES"]
