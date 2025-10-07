"""Entry point to launch the python core WebSocket server."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .config import AppConfig
from .server import CopilotServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interview Copilot Python Core")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="Path to config.json")
    parser.add_argument("--log-level", type=str, default=None, help="Override log level")
    return parser.parse_args()


async def amain() -> None:
    args = parse_args()
    config = AppConfig.load(args.config)
    log_level = args.log_level or config.logging.level
    logging.basicConfig(level=log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = CopilotServer(config)
    await server.start()
    await server.wait_closed()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
