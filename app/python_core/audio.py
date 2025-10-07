"""Audio capture utilities built on top of sounddevice."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import queue
import threading
import time
from dataclasses import dataclass
from typing import AsyncIterator, Callable, List, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CapturedFrame:
    """PCM16 audio frame accompanied with timing metadata."""

    data: bytes
    timestamp: float


@dataclass(slots=True)
class AudioMetrics:
    """Measurements produced during the test capture routine."""

    rms: float
    peak: float


DevicePredicate = Callable[[dict], bool]


def list_output_devices(predicate: Optional[DevicePredicate] = None) -> List[str]:
    """Return device names that are suitable for loopback capture."""

    devices = []
    for device in sd.query_devices():
        name = device.get("name", "")
        host = sd.query_hostapis()[device.get("hostapi", 0)].get("name", "")
        loopback = "loopback" in name.lower()
        is_output = device.get("max_output_channels", 0) > 0
        if predicate and not predicate(device):
            continue
        if loopback or (host.lower().startswith("wasapi") and is_output):
            devices.append(name)
    return sorted(set(devices))


@dataclass(slots=True)
class AudioConfig:
    """Audio capture configuration."""

    device_name: str = "System Default"
    sample_rate: int = 16_000
    block_ms: int = 20
    channels: int = 1
    dtype: str = "int16"
    auto_reconnect: bool = True

    @property
    def block_size(self) -> int:
        return int(self.sample_rate * self.block_ms / 1000)


class AudioCapturer:
    """Capture loopback audio and expose frames through an asyncio queue."""

    def __init__(self, config: AudioConfig):
        self._config = config
        self._queue: "queue.Queue[CapturedFrame]" = queue.Queue(maxsize=32)
        self._stream: Optional[sd.RawInputStream] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._device_index: Optional[int] = None

    @property
    def config(self) -> AudioConfig:
        return self._config

    def _resolve_device_index(self) -> Optional[int]:
        if self._config.device_name == "System Default":
            return None
        for idx, device in enumerate(sd.query_devices()):
            if device.get("name") == self._config.device_name:
                return idx
        logger.warning("Requested device '%s' not found, falling back to default", self._config.device_name)
        return None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._device_index = self._resolve_device_index()
            logger.info("Starting audio capture from %s", self._config.device_name)
            self._stop_event.clear()
            self._stream = sd.RawInputStream(
                samplerate=self._config.sample_rate,
                blocksize=self._config.block_size,
                device=self._device_index,
                channels=self._config.channels,
                dtype=self._config.dtype,
                callback=self._on_audio,
                finished_callback=self._on_stop,
            )
            self._stream.start()

    def stop(self) -> None:
        with self._lock:
            if self._stream is None:
                return
            logger.info("Stopping audio capture")
            self._stop_event.set()
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _on_audio(self, indata: bytes, frames: int, _time: sd.CallbackFlags, status: sd.CallbackFlags) -> None:  # type: ignore[override]
        if status:
            logger.debug("Audio callback status: %s", status)
        frame = CapturedFrame(data=bytes(indata), timestamp=time.monotonic())
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            logger.warning("Audio frame queue overflow, dropping frame")

    def _on_stop(self) -> None:
        logger.debug("Audio stream finished")

    async def frames(self) -> AsyncIterator[CapturedFrame]:
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            frame = await loop.run_in_executor(None, self._queue.get)
            yield frame

    def test_capture(self, duration: float = 2.0) -> List[AudioMetrics]:
        """Measure RMS/peak levels for the specified duration."""

        frames: List[AudioMetrics] = []
        deadline = time.monotonic() + duration
        with contextlib.ExitStack() as stack:
            device_index = self._resolve_device_index()
            stream = stack.enter_context(
                sd.InputStream(
                    samplerate=self._config.sample_rate,
                    blocksize=self._config.block_size,
                    device=device_index,
                    channels=self._config.channels,
                    dtype=self._config.dtype,
                )
            )
            while time.monotonic() < deadline:
                data, _ = stream.read(self._config.block_size)
                arr = np.frombuffer(data, dtype=np.int16)
                if arr.size == 0:
                    continue
                rms = float(np.sqrt(np.mean(np.square(arr)))) / 32768.0
                peak = float(np.max(np.abs(arr))) / 32768.0
                frames.append(AudioMetrics(rms=rms, peak=peak))
        return frames

    def generate_test_tone(self, frequency: float = 440.0, duration: float = 1.0) -> np.ndarray:
        """Generate a sine wave to be used for the Test Capture UI widget."""

        t = np.linspace(0, duration, int(self._config.sample_rate * duration), False)
        tone = 0.2 * np.sin(2 * math.pi * frequency * t)
        return tone.astype(np.float32)

    def reconnect(self) -> None:
        """Reconnect to the audio device, used when Windows changes defaults."""

        logger.info("Reconnecting audio capture stream")
        self.stop()
        self.start()


__all__ = [
    "AudioCapturer",
    "AudioConfig",
    "AudioMetrics",
    "CapturedFrame",
    "list_output_devices",
]
