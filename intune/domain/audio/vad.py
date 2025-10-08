"""Simple energy-based voice activity detector."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence


@dataclass(slots=True)
class VADConfig:
    aggressiveness: int
    threshold: float


class EnergyVAD:
    """Naive voice activity detector used as a fallback implementation."""

    def __init__(self, config: VADConfig) -> None:
        self._config = config

    def is_speech(self, frame: Sequence[float]) -> bool:
        if not frame:
            return False
        energy = mean(abs(sample) for sample in frame)
        limit = self._config.threshold / max(self._config.aggressiveness, 1)
        return energy >= limit


__all__ = ["VADConfig", "EnergyVAD"]
