"""Configuration helpers for the Interview Copilot core."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


def _resolve_path(value: str | Path | None, *, base: Path) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path


@dataclass(slots=True)
class AudioSettings:
    """Audio capture configuration."""

    device_name: str = "System Default"
    auto_reconnect: bool = True
    sample_rate: int = 16_000
    block_ms: int = 20
    channels: int = 1
    monitor_interval: float = 1.0


@dataclass(slots=True)
class VadSettings:
    """Voice activity detection configuration."""

    aggressiveness: int = 2
    silence_sec: float = 0.8


@dataclass(slots=True)
class SttSettings:
    """Speech-to-text settings."""

    model: str = "medium"
    use_gpu: bool = True
    language: str = "auto"


@dataclass(slots=True)
class OllamaSettings:
    """Parameters for talking to the local Ollama server."""

    model: str = "qwen2.5:7b-instruct"
    timeout_sec: int = 120
    host: str = "http://127.0.0.1:11434"


@dataclass(slots=True)
class OverlaySettings:
    """Overlay window defaults."""

    x: int = 20
    y: int = 20
    width: int = 640
    height: int = 180
    opacity: float = 1.0


@dataclass(slots=True)
class RagSettings:
    """Retrieval configuration."""

    top_k: int = 5
    db_path: Path = Path("./data/knowledge.db")
    index_path: Path = Path("./data/index.faiss")
    embed_model: str = "bge-small-ru-en"


@dataclass(slots=True)
class LoggingSettings:
    """Logging configuration for the python core."""

    level: str = "info"
    path: Optional[Path] = None


@dataclass(slots=True)
class AppConfig:
    """Root configuration container."""

    audio: AudioSettings = field(default_factory=AudioSettings)
    vad: VadSettings = field(default_factory=VadSettings)
    stt: SttSettings = field(default_factory=SttSettings)
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    rag: RagSettings = field(default_factory=RagSettings)
    profile: str = "frontend"
    logging: LoggingSettings = field(default_factory=LoggingSettings)

    @classmethod
    def load(cls, path: str | Path) -> "AppConfig":
        config_path = Path(path)
        with config_path.open("r", encoding="utf-8") as fh:
            payload: Dict[str, Any] = json.load(fh)

        base = config_path.parent
        rag_data = payload.get("rag", {})
        rag_data.setdefault("db_path", "./data/knowledge.db")
        rag_data.setdefault("index_path", "./data/index.faiss")
        rag = RagSettings(
            top_k=rag_data.get("top_k", 5),
            db_path=_resolve_path(rag_data.get("db_path"), base=base) or Path("./data/knowledge.db"),
            index_path=_resolve_path(rag_data.get("index_path"), base=base) or Path("./data/index.faiss"),
            embed_model=rag_data.get("embed_model", "bge-small-ru-en"),
        )

        logging_data = payload.get("logging", {})
        logging_cfg = LoggingSettings(
            level=logging_data.get("level", "info"),
            path=_resolve_path(logging_data.get("path"), base=base),
        )

        return cls(
            audio=AudioSettings(**payload.get("audio", {})),
            vad=VadSettings(**payload.get("vad", {})),
            stt=SttSettings(**payload.get("stt", {})),
            ollama=OllamaSettings(**payload.get("ollama", {})),
            overlay=OverlaySettings(**payload.get("overlay", {})),
            rag=rag,
            profile=payload.get("profile", "frontend"),
            logging=logging_cfg,
        )

    def dump(self) -> Dict[str, Any]:
        """Return a JSON serialisable dict."""

        return {
            "audio": vars(self.audio),
            "vad": vars(self.vad),
            "stt": vars(self.stt),
            "ollama": vars(self.ollama),
            "overlay": vars(self.overlay),
            "rag": {
                "top_k": self.rag.top_k,
                "db_path": str(self.rag.db_path),
                "index_path": str(self.rag.index_path),
                "embed_model": self.rag.embed_model,
            },
            "profile": self.profile,
            "logging": {
                "level": self.logging.level,
                "path": str(self.logging.path) if self.logging.path else None,
            },
        }

    def update_from_payload(self, payload: Dict[str, Any]) -> None:
        """Update current config in-place from a partial payload."""

        if "audio" in payload:
            for key, value in payload["audio"].items():
                setattr(self.audio, key, value)
        if "vad" in payload:
            for key, value in payload["vad"].items():
                setattr(self.vad, key, value)
        if "stt" in payload:
            for key, value in payload["stt"].items():
                setattr(self.stt, key, value)
        if "ollama" in payload:
            for key, value in payload["ollama"].items():
                setattr(self.ollama, key, value)
        if "overlay" in payload:
            for key, value in payload["overlay"].items():
                setattr(self.overlay, key, value)
        if "rag" in payload:
            for key, value in payload["rag"].items():
                setattr(self.rag, key, value)
        if "profile" in payload:
            self.profile = payload["profile"]
        if "logging" in payload:
            for key, value in payload["logging"].items():
                setattr(self.logging, key, value)

        rag = self.rag
        rag.db_path = Path(rag.db_path)
        rag.index_path = Path(rag.index_path)
        if self.logging.path is not None:
            self.logging.path = Path(self.logging.path)
