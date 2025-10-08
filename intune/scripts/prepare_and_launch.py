"""Utility CLI that prepares the environment and runs the assistant."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import fields, is_dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

if __package__ in {None, ""}:  # pragma: no cover - executed only when run as a script
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

from intune.app import create_app, handle_transcript
from intune.core.config import AppConfig, load_app_config
from intune.core.logger import configure_logging, logger


OPTIONAL_DEPENDENCIES: Tuple[Tuple[str, str], ...] = (
    ("sounddevice", "захват микрофона"),
    ("faster_whisper", "офлайн распознавание речи"),
    ("llama_cpp", "генерация ответов локальной LLM"),
    ("chromadb", "RAG-поиск по базе знаний"),
    ("PySide6", "оверлейный интерфейс"),
)


def _dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        result: Dict[str, Any] = {}
        for field in fields(value):
            result[field.name] = _dataclass_to_dict(getattr(value, field.name))
        return result
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: _dataclass_to_dict(item) for key, item in value.items()}
    return value


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _check_dependencies() -> None:
    missing: list[str] = []
    for module_name, description in OPTIONAL_DEPENDENCIES:
        try:
            import_module(module_name)
        except Exception:
            missing.append(f"{module_name} ({description})")
    if missing:
        warning = "\n".join(f"  - {item}" for item in missing)
        logger.warning(
            "Не установлены дополнительные зависимости:\n%s\n"
            "Некоторые функции будут работать в режиме заглушек.",
            warning,
        )
    else:
        logger.info("Все опциональные зависимости найдены")


def _prepare_filesystem(config: AppConfig) -> None:
    asr_path = config.asr.model_path.expanduser()
    llm_path = config.llm.model_path.expanduser()
    rag_index = config.rag.index_path.expanduser()
    cache_dir = config.storage.cache_dir.expanduser()
    sqlite_path = config.storage.sqlite_path.expanduser()

    for directory in (asr_path, llm_path, rag_index, cache_dir):
        if directory.suffix:
            _ensure_parent(directory)
        else:
            _ensure_directory(directory)

    _ensure_parent(sqlite_path)
    if not sqlite_path.exists():
        sqlite_path.touch()


def _ensure_history_schema(config: AppConfig) -> None:
    try:
        from intune.infra.storage.sqlite import SQLiteHistoryRepository
    except Exception as exc:  # pragma: no cover - sqlite входит в стандартную библиотеку
        logger.error("Не удалось инициализировать хранилище истории: %s", exc)
        return
    SQLiteHistoryRepository(config.storage.sqlite_path)


def _write_default_config(path: Path, config: AppConfig) -> None:
    data = _dataclass_to_dict(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf8")
    logger.info("Создан файл конфигурации по умолчанию: %s", path)


def _load_or_create_config(path: Path | None) -> Tuple[AppConfig, Path | None]:
    if path is None:
        return AppConfig(), None
    expanded = path.expanduser()
    if expanded.exists():
        return load_app_config(expanded), expanded
    config = AppConfig()
    _write_default_config(expanded, config)
    return config, expanded


def _prepare_environment(config: AppConfig) -> None:
    _prepare_filesystem(config)
    _ensure_history_schema(config)
    _check_dependencies()


def run(audio: Path | None, config_path: Path | None, mode: str, sample_rate: int) -> None:
    context = create_app(config_path)
    if audio is None:
        logger.info("Подготовка завершена. Аудиофайл не указан — запуск пропущен.")
        return
    data = audio.read_bytes()
    handle_transcript(context, data, sample_rate, mode)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Подготовка и запуск прототипа InTune")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.local.json"),
        help="Путь к конфигурации. Будет создан с настройками по умолчанию, если отсутствует.",
    )
    parser.add_argument(
        "--audio",
        type=Path,
        help="Путь к PCM16 WAV/RAW файлу для демонстрационного запуска",
    )
    parser.add_argument("--mode", type=str, default="Short", help="Режим генерации ответа")
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16_000,
        help="Частота дискретизации аудиофайла",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Только подготовка окружения без запуска пайплайна",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    configure_logging()
    config, resolved_config_path = _load_or_create_config(args.config)
    _prepare_environment(config)

    if args.prepare_only:
        logger.info("Запуск пайплайна пропущен по запросу пользователя")
        return 0

    run(args.audio, resolved_config_path, args.mode, args.sample_rate)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
