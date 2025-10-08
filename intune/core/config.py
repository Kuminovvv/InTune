"""Application configuration models and loader.

This module defines structured configuration objects for the InTune
assistant.  The configuration is intentionally explicit and flat to avoid
surprises and keep defaults easy to reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import json

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - yaml is optional
    yaml = None  # type: ignore


@dataclass(slots=True)
class AudioInputConfig:
    """Parameters that control microphone/loopback capture."""

    device: Optional[str] = None
    sample_rate: int = 16_000
    chunk_duration_ms: int = 30
    enable_loopback: bool = False
    vad_aggressiveness: int = 2


@dataclass(slots=True)
class ASRConfig:
    """Settings for the offline speech recogniser."""

    model_path: Path = Path("models/faster-whisper-small")
    language: Optional[str] = None
    beam_size: int = 5
    max_alternatives: int = 1
    use_cuda: bool = False


@dataclass(slots=True)
class LLMConfig:
    """Local LLM runtime configuration."""

    model_path: Path = Path("models/llm/llama-7b-q4")
    context_window: int = 2_048
    temperature: float = 0.7
    max_tokens: int = 384
    profile: str = "general"


@dataclass(slots=True)
class RAGConfig:
    """Configuration for the retrieval augmented generation layer."""

    index_path: Path = Path("indexes/default")
    top_k: int = 4
    embedding_model: str = "intfloat/e5-base-v2"
    chunk_size: int = 512
    chunk_overlap: int = 64


@dataclass(slots=True)
class StorageConfig:
    """Configuration of local storage and encryption."""

    sqlite_path: Path = Path("storage/history.sqlite3")
    cache_dir: Path = Path("storage/cache")
    encryption_key_path: Path = Path("storage/key.bin")


@dataclass(slots=True)
class PrivacyConfig:
    """Privacy related toggles."""

    offline_only: bool = True
    enable_panic_shortcut: bool = True
    panic_hotkey: str = "Ctrl+Shift+Delete"


@dataclass(slots=True)
class UIConfig:
    """Overlay and hotkey configuration."""

    transparency: float = 0.85
    always_on_top: bool = True
    click_through: bool = True
    toggle_hotkey: str = "Ctrl+Alt+Space"
    restart_hotkey: str = "Ctrl+Alt+R"
    star_hotkey: str = "Ctrl+Alt+S"
    code_only_hotkey: str = "Ctrl+Alt+C"


@dataclass(slots=True)
class AppConfig:
    """Top level configuration object."""

    audio: AudioInputConfig = field(default_factory=AudioInputConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def _load_from_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML не установлен, чтение YAML невозможно")
    with path.open("r", encoding="utf8") as stream:
        data = yaml.safe_load(stream) or {}
        if not isinstance(data, dict):
            raise ValueError("Файл конфигурации должен содержать словарь")
        return data


def _load_from_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf8") as stream:
        data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError("JSON конфигурация должна содержать словарь")
        return data


def _merge_dataclass(instance: Any, values: Dict[str, Any]) -> None:
    for field_name, field_value in values.items():
        if not hasattr(instance, field_name):
            raise ValueError(f"Неизвестный параметр конфигурации: {field_name}")
        attr = getattr(instance, field_name)
        if is_dataclass(attr) and isinstance(field_value, dict):
            _merge_dataclass(attr, field_value)
        else:
            if isinstance(attr, Path):
                setattr(instance, field_name, Path(field_value))
            else:
                setattr(instance, field_name, field_value)


def load_app_config(path: Optional[Path] = None) -> AppConfig:
    """Load configuration from JSON or YAML.

    Parameters
    ----------
    path:
        Путь к файлу конфигурации.  Если не указан, используются значения
        по умолчанию.
    """

    config = AppConfig()
    if path is None:
        return config
    resolved = path.expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"Конфигурация не найдена: {resolved}")
    if resolved.suffix.lower() in {".yaml", ".yml"}:
        values = _load_from_yaml(resolved)
    elif resolved.suffix.lower() == ".json":
        values = _load_from_json(resolved)
    else:
        raise ValueError("Поддерживаются только JSON и YAML конфигурации")
    _merge_dataclass(config, values)
    return config


__all__ = [
    "AudioInputConfig",
    "ASRConfig",
    "LLMConfig",
    "RAGConfig",
    "StorageConfig",
    "PrivacyConfig",
    "UIConfig",
    "AppConfig",
    "load_app_config",
]
