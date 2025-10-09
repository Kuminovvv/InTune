"""Audio capture helpers using sounddevice when available."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterator, Optional

import array

from ...core.events import AudioSegment
from ...domain.audio.vad import EnergyVAD, VADConfig

try:  # pragma: no cover
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None  # type: ignore


@dataclass(slots=True)
class MicrophoneConfig:
    device: Optional[str]
    sample_rate: int
    chunk_duration_ms: int
    vad_aggressiveness: int


class MicrophoneListener:
    """Listens to microphone input and yields speech segments."""

    def __init__(self, config: MicrophoneConfig, vad_threshold: float = 50.0) -> None:
        self._config = config
        self._vad = EnergyVAD(VADConfig(config.vad_aggressiveness, vad_threshold))

    def listen(self) -> Iterator[AudioSegment]:
        if sd is None:
            raise RuntimeError("sounddevice не установлен")
        frame_length = int(self._config.sample_rate * (self._config.chunk_duration_ms / 1000))
        buffer = array.array("h")
        with sd.InputStream(
            device=self._config.device,
            channels=1,
            samplerate=self._config.sample_rate,
            dtype="int16",
            blocksize=frame_length,
        ) as stream:
            while True:
                frames, _overflow = stream.read(frame_length)
                column = frames[:, 0]  # type: ignore[index]
                frame = array.array("h", column.tolist())
                if not self._vad.is_speech(frame):
                    buffer.clear()
                    continue
                buffer.extend(frame)
                timestamp = datetime.utcnow()
                yield AudioSegment(
                    samples=buffer.tobytes(),
                    sample_rate=self._config.sample_rate,
                    start=timestamp,
                    duration_ms=self._config.chunk_duration_ms,
                    source="microphone",
                )
                buffer.clear()


__all__ = ["MicrophoneConfig", "MicrophoneListener"]
