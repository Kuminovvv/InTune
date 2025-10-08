"""Controller bridging Qt UI with the Interview Copilot core."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from app.python_core.config import AppConfig
from app.python_core.orchestrator import CopilotCallbacks, InterviewCopilot

logger = logging.getLogger(__name__)

CommandPayload = Tuple[str, Dict[str, Any], Future[Any]]


class CopilotController(QObject):
    """Threaded orchestrator wrapper for the Qt interface."""

    statusChanged = Signal(str, str)
    partialTranscript = Signal(str)
    answerReceived = Signal(str, str)
    errorOccurred = Signal(str, str)
    reindexFinished = Signal(int)
    configUpdated = Signal(dict)
    coreReady = Signal()

    def __init__(self, config_path: Path):
        super().__init__()
        self._config_path = config_path
        self._config = AppConfig.load(config_path)
        self._config_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run_loop, name="copilot-core", daemon=True)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._command_queue: Optional[asyncio.Queue[CommandPayload]] = None
        self._loop_ready = threading.Event()
        self._pending: List[CommandPayload] = []
        self._pending_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._thread.start()

    def shutdown(self) -> None:
        if not self._thread.is_alive():
            return
        if not self._loop_ready.wait(timeout=0.1):
            # Core still initialising; thread is daemon so it will exit with the process.
            return
        future = self._submit("shutdown")
        try:
            future.result(timeout=5.0)
        finally:
            self._thread.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Public API for the UI
    # ------------------------------------------------------------------
    def start_listen(self) -> None:
        self._submit("start_listen")

    def stop_listen(self) -> None:
        self._submit("stop_listen")

    def shorten_last(self) -> None:
        self._submit("shorten_last")

    def code_hint(self) -> None:
        self._submit("code_hint")

    def reindex(self, paths: Iterable[str]) -> Future[Any]:
        return self._submit("reindex", {"paths": list(paths)})

    def update_config(self, payload: Dict[str, Any]) -> Future[Any]:
        return self._submit("set_config", {"payload": payload})

    def current_config(self) -> AppConfig:
        with self._config_lock:
            return copy.deepcopy(self._config)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        asyncio.run(self._async_main())

    async def _async_main(self) -> None:
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue[CommandPayload] = asyncio.Queue()
        self._command_queue = queue

        async def on_answer(question: str, hint: str) -> None:
            self.answerReceived.emit(question, hint)

        async def on_partial(text: str) -> None:
            self.partialTranscript.emit(text)

        async def on_state(state: str, message: str) -> None:
            self.statusChanged.emit(state, message)

        async def on_error(stage: str, msg: str) -> None:
            self.errorOccurred.emit(stage, msg)

        callbacks = CopilotCallbacks(
            on_answer=on_answer,
            on_partial=on_partial,
            on_state=on_state,
            on_error=on_error,
        )
        try:
            copilot = InterviewCopilot(self.current_config(), callbacks)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to initialise copilot core")
            self.errorOccurred.emit("init", str(exc))
            self._loop_ready.set()
            self.coreReady.emit()
            return

        self._loop_ready.set()
        self.coreReady.emit()
        with self._pending_lock:
            pending = list(self._pending)
            self._pending.clear()
        for item in pending:
            await queue.put(item)

        await asyncio.sleep(0)
        self.statusChanged.emit("ready", "")
        logger.info("Copilot core thread started")

        while True:
            command, payload, result_future = await queue.get()
            try:
                if command == "shutdown":
                    await copilot.shutdown()
                    result_future.set_result(True)
                    break
                result = await self._execute_command(copilot, command, payload)
                if not result_future.done():
                    result_future.set_result(result)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Command %s failed", command)
                if not result_future.done():
                    result_future.set_exception(exc)
        logger.info("Copilot core thread stopping")

    async def _execute_command(
        self, copilot: InterviewCopilot, command: str, payload: Dict[str, Any]
    ) -> Any:
        if command == "start_listen":
            await copilot.start()
            return None
        if command == "stop_listen":
            await copilot.stop()
            return None
        if command == "shorten_last":
            await copilot.shorten_last()
            return None
        if command == "code_hint":
            await copilot.code_hint()
            return None
        if command == "reindex":
            count = await copilot.reindex(payload.get("paths", []))
            self.reindexFinished.emit(int(count))
            return count
        if command == "set_config":
            update_payload = payload.get("payload", {})
            await copilot.update_config(update_payload)
            with self._config_lock:
                self._config.update_from_payload(update_payload)
                serialized = self._config.dump()
            self._write_config(serialized)
            self.configUpdated.emit(serialized)
            return serialized
        raise ValueError(f"Unknown command: {command}")

    def _write_config(self, payload: Dict[str, Any]) -> None:
        try:
            self._config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist configuration to %s", self._config_path)

    def _submit(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Future[Any]:
        result: Future[Any] = Future()
        payload = payload or {}

        if not self._loop_ready.is_set() or self._loop is None or self._command_queue is None:
            with self._pending_lock:
                if not self._loop_ready.is_set() or self._loop is None or self._command_queue is None:
                    self._pending.append((command, payload, result))
                    return result

        async def enqueue() -> None:
            assert self._command_queue is not None
            await self._command_queue.put((command, payload, result))

        asyncio.run_coroutine_threadsafe(enqueue(), self._loop)
        return result


__all__ = ["CopilotController"]
