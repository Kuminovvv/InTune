"""Audio capture utilities for Interview Copilot."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import platform
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

    devices: List[str] = []
    host_apis = sd.query_hostapis()
    for device in sd.query_devices():
        if predicate and not predicate(device):
            continue
        max_output = device.get("max_output_channels", 0)
        if max_output <= 0:
            continue
        name = device.get("name", "")
        host_name = host_apis[device.get("hostapi", 0)].get("name", "")
        if "loopback" in name.lower():
            devices.append(name)
            continue
        if platform.system().lower() == "windows" and host_name.lower().startswith("wasapi"):
            devices.append(name)
        elif platform.system().lower() != "windows":
            devices.append(name)
    return sorted(dict.fromkeys(devices))


@dataclass(slots=True)
class AudioConfig:
    """Audio capture configuration."""

    device_name: str = "System Default"
    sample_rate: int = 16_000
    block_ms: int = 20
    channels: int = 1
    dtype: str = "int16"
    auto_reconnect: bool = True
    monitor_interval: float = 1.0

    @property
    def block_size(self) -> int:
        return int(self.sample_rate * self.block_ms / 1000)


class AudioCapturer:
    """Capture loopback audio and expose frames through an asyncio queue."""

    def __init__(self, config: AudioConfig):
        self._config = config
        self._queue: "queue.Queue[Optional[CapturedFrame]]" = queue.Queue(maxsize=64)
        self._stream: Optional[sd.RawInputStream] = None
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self._monitor_stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._active_device_signature: Optional[str] = None
        self._last_default_signature: Optional[str] = self._current_default_output_signature()
        self._active_channels = max(1, config.channels)

    @property
    def config(self) -> AudioConfig:
        return self._config

    def _extra_settings(self, device_index: Optional[int]) -> Optional[sd.WasapiSettings]:  # type: ignore[name-defined]
        if platform.system().lower() != "windows":
            return None

        try:
            if device_index is None:
                info = sd.query_devices(None, "output")
            else:
                info = sd.query_devices(device_index)
        except Exception:  # noqa: BLE001
            logger.debug("Failed to inspect audio device for WASAPI support", exc_info=True)
            return None

        host_index = info.get("hostapi", 0)
        try:
            host_name = sd.query_hostapis()[host_index].get("name", "")
        except Exception:  # noqa: BLE001
            host_name = ""

        if "wasapi" not in host_name.lower():
            logger.debug("Audio host '%s' does not support WASAPI loopback", host_name)
            return None

        try:
            settings = sd.WasapiSettings()  # type: ignore[attr-defined]
        except AttributeError:
            logger.debug("sounddevice.WasapiSettings is not available; falling back to default settings")
            return None
        except TypeError:
            # Some sounddevice builds expose WasapiSettings but without a public constructor.
            logger.debug("sounddevice.WasapiSettings cannot be constructed; falling back to default settings")
            return None

        try:
            settings.loopback = True  # type: ignore[attr-defined]
        except AttributeError:
            logger.debug("sounddevice.WasapiSettings.loopback attribute missing; using default settings")
            return None
        return settings

    def _preferred_device_index(self, device_name: str) -> Optional[int]:
        try:
            devices = list(sd.query_devices())
            host_apis = sd.query_hostapis()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to enumerate audio devices when selecting preferred host", exc_info=True)
            return None

        matching_indices: List[int] = []
        for idx, device in enumerate(devices):
            if device.get("name") == device_name:
                matching_indices.append(idx)

        if not matching_indices:
            return None

        if platform.system().lower() == "windows":
            for idx in matching_indices:
                host_name = host_apis[devices[idx].get("hostapi", 0)].get("name", "")
                if "wasapi" in host_name.lower():
                    return idx

        return matching_indices[0]

    def _effective_channels(self, device_index: Optional[int], extra: Optional[sd.WasapiSettings]) -> int:  # type: ignore[name-defined]
        desired = max(1, self._config.channels)

        info: Optional[dict]
        try:
            if device_index is None:
                info = sd.query_devices(None, "output")
            else:
                info = sd.query_devices(device_index)
        except Exception:  # noqa: BLE001
            info = None

        if not info:
            return desired

        max_input = int(info.get("max_input_channels", 0) or 0)
        max_output = int(info.get("max_output_channels", 0) or 0)

        if extra is not None and max_output > 0:
            return max(1, max_output)

        if max_input > 0:
            return max(1, min(desired, max_input))

        if extra is None and max_output > 0:
            raise RuntimeError(
                "Selected audio device does not expose input channels and does not support WASAPI loopback"
            )

        return desired

    def _device_signature(self, device_index: Optional[int]) -> Optional[str]:
        if device_index is None:
            return self._current_default_output_signature()
        try:
            info = sd.query_devices(device_index)
        except Exception:  # noqa: BLE001
            return None
        host = sd.query_hostapis()[info.get("hostapi", 0)].get("name", "")
        return f"{info.get('name', 'unknown')}|{host}"

    def _current_default_output_signature(self) -> Optional[str]:
        try:
            info = sd.query_devices(None, "output")
        except Exception:  # noqa: BLE001
            return None
        host = sd.query_hostapis()[info.get("hostapi", 0)].get("name", "")
        return f"{info.get('name', 'default')}|{host}"

    def _resolve_device_index(self) -> Optional[int]:
        if self._config.device_name == "System Default":
            try:
                default_info = sd.query_devices(None, "output")
            except Exception:  # noqa: BLE001
                default_info = None
            if default_info:
                default_name = default_info.get("name")
                if default_name:
                    preferred = self._preferred_device_index(default_name)
                    if preferred is not None:
                        return preferred
            output_index = sd.default.device[1]
            if output_index is None or output_index < 0:
                return None
            return int(output_index)
        for idx, device in enumerate(sd.query_devices()):
            if device.get("name") == self._config.device_name:
                preferred = self._preferred_device_index(device.get("name", ""))
                if preferred is not None:
                    return preferred
                return idx
        logger.warning("Requested device '%s' not found, falling back to system default", self._config.device_name)
        return None

    def _open_stream(self) -> None:
        device_index = self._resolve_device_index()
        extra = self._extra_settings(device_index)
        channels = self._effective_channels(device_index, extra)
        self._active_channels = channels
        self._active_device_signature = self._device_signature(device_index)
        logger.info("Starting audio capture from %s", self._active_device_signature or "System Default")
        self._stream = sd.RawInputStream(
            samplerate=self._config.sample_rate,
            blocksize=self._config.block_size,
            device=device_index,
            channels=channels,
            dtype=self._config.dtype,
            callback=self._on_audio,
            finished_callback=self._on_stream_finished,
            extra_settings=extra,
        )
        self._stream.start()

    def _close_stream(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
        finally:
            self._stream.close()
            self._stream = None
            self._active_channels = max(1, self._config.channels)

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._shutdown.clear()
            self._queue = queue.Queue(maxsize=64)
            self._open_stream()
            self._start_monitor_if_needed()

    def stop(self) -> None:
        with self._lock:
            if self._stream is None and not self._monitor_thread:
                return
            self._shutdown.set()
            self._stop_monitor()
            self._close_stream()
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass

    def reconnect(self) -> None:
        with self._lock:
            if self._stream is None:
                return
            logger.info("Reinitialising audio capture stream after device change")
            self._close_stream()
            try:
                self._open_stream()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to restart audio stream")
                raise

    def _start_monitor_if_needed(self) -> None:
        if not self._config.auto_reconnect or self._config.device_name != "System Default":
            return
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, name="audio-monitor", daemon=True)
        self._monitor_thread.start()

    def _stop_monitor(self) -> None:
        if not self._monitor_thread:
            return
        self._monitor_stop.set()
        self._monitor_thread.join(timeout=1.0)
        self._monitor_thread = None
        self._monitor_stop.clear()

    def _monitor_loop(self) -> None:
        self._last_default_signature = self._current_default_output_signature()
        while not self._monitor_stop.wait(self._config.monitor_interval):
            current = self._current_default_output_signature()
            if not current or current == self._last_default_signature:
                continue
            logger.info("Detected default output change: %s -> %s", self._last_default_signature, current)
            self._last_default_signature = current
            try:
                self.reconnect()
            except Exception:  # noqa: BLE001
                logger.exception("Auto-reconnect failed")

    @staticmethod
    def _downmix_to_mono(data: bytes, channels: int) -> bytes:
        if channels <= 1 or not data:
            return data
        array = np.frombuffer(data, dtype=np.int16)
        if array.size == 0:
            return b""
        try:
            reshaped = array.reshape(-1, channels)
        except ValueError:
            usable = (array.size // channels) * channels
            if usable == 0:
                return b""
            reshaped = array[:usable].reshape(-1, channels)
        mono = reshaped.astype(np.int32).mean(axis=1)
        mono = np.clip(mono, -32768, 32767).astype(np.int16)
        return mono.tobytes()

    def _on_audio(self, indata: bytes, frames: int, _time: sd.CallbackFlags, status: sd.CallbackFlags) -> None:  # type: ignore[override]
        if status:
            logger.debug("Audio callback status: %s", status)
        pcm = self._downmix_to_mono(bytes(indata), self._active_channels)
        if not pcm:
            return
        frame = CapturedFrame(data=pcm, timestamp=time.monotonic())
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            try:
                _ = self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                logger.warning("Audio frame queue overflow; dropping frame")

    def _on_stream_finished(self) -> None:
        logger.debug("Audio stream finished")

    async def frames(self) -> AsyncIterator[CapturedFrame]:
        loop = asyncio.get_running_loop()
        while not self._shutdown.is_set():
            item = await loop.run_in_executor(None, self._queue.get)
            if item is None:
                if self._shutdown.is_set():
                    break
                continue
            yield item

    def test_capture(self, duration: float = 2.0, *, play_tone: bool = True) -> List[AudioMetrics]:
        """Measure RMS/peak levels for the specified duration."""

        frames: List[AudioMetrics] = []
        block_size = self._config.block_size
        device_index = self._resolve_device_index()
        extra = self._extra_settings(device_index)
        channels = self._effective_channels(device_index, extra)
        start_time = time.monotonic()
        with contextlib.ExitStack() as stack:
            stream = stack.enter_context(
                sd.RawInputStream(
                    samplerate=self._config.sample_rate,
                    blocksize=block_size,
                    device=device_index,
                    channels=channels,
                    dtype=self._config.dtype,
                    extra_settings=extra,
                )
            )
            stream.start()
            if play_tone:
                tone = self.generate_test_tone(duration=duration)
                sd.play(tone, samplerate=self._config.sample_rate, blocking=False)
            try:
                while time.monotonic() - start_time < duration:
                    data, _ = stream.read(block_size)
                    pcm = self._downmix_to_mono(bytes(data), channels)
                    if not pcm:
                        continue
                    array = np.frombuffer(pcm, dtype=np.int16)
                    rms = float(np.sqrt(np.mean(np.square(array.astype(np.float32))))) / 32768.0
                    peak = float(np.max(np.abs(array))) / 32768.0
                    frames.append(AudioMetrics(rms=rms, peak=peak))
            finally:
                if play_tone:
                    sd.stop()
        return frames

    def generate_test_tone(self, frequency: float = 440.0, duration: float = 1.0) -> np.ndarray:
        """Generate a sine wave to be used for the Test Capture UI widget."""

        t = np.linspace(0, duration, int(self._config.sample_rate * duration), False)
        tone = 0.2 * np.sin(2 * math.pi * frequency * t)
        return tone.astype(np.float32)


__all__ = [
    "AudioCapturer",
    "AudioConfig",
    "AudioMetrics",
    "CapturedFrame",
    "list_output_devices",
]
