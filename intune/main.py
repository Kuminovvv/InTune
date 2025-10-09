"""Command line entry point for manual testing."""

from __future__ import annotations

import argparse
from pathlib import Path

from .app import create_app, handle_transcript
from .core.logger import logger


def main() -> None:
    parser = argparse.ArgumentParser(description="InTune assistant prototype")
    parser.add_argument("audio", type=Path, help="Путь к PCM16 wav-файлу для демонстрации")
    parser.add_argument("--config", type=Path, help="Путь к конфигурации", default=None)
    parser.add_argument("--mode", type=str, default="Short", help="Режим ответа LLM")
    args = parser.parse_args()

    context = create_app(args.config)
    data = args.audio.read_bytes()
    sample_rate = 16_000
    handle_transcript(context, data, sample_rate, args.mode)
    logger.info("Обработка завершена")


if __name__ == "__main__":  # pragma: no cover
    main()
