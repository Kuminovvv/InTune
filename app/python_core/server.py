"""WebSocket server exposing the Interview Copilot pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol

from .config import AppConfig
from .orchestrator import CopilotCallbacks, InterviewCopilot

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765


class CopilotServer:
    """Simple WebSocket JSON protocol wrapper."""

    def __init__(self, app_config: AppConfig, server_config: ServerConfig = ServerConfig()):
        self._config = app_config
        self._server_config = server_config
        self._copilot: Optional[InterviewCopilot] = None
        self._server: Optional[websockets.server.Serve] = None
        self._active_socket: Optional[WebSocketServerProtocol] = None

    async def _send(self, ws: WebSocketServerProtocol, payload: Dict[str, Any]) -> None:
        await ws.send(json.dumps(payload, ensure_ascii=False))

    async def _handler(self, websocket: WebSocketServerProtocol) -> None:
        logger.info("Renderer connected from %s", websocket.remote_address)
        self._active_socket = websocket

        async def on_answer(question: str, hint: str) -> None:
            await self._send(websocket, {"type": "answer", "question": question, "hint": hint})

        async def on_partial(text: str) -> None:
            await self._send(websocket, {"type": "partial_transcript", "text": text})

        async def on_state(state: str, message: str) -> None:
            await self._send(websocket, {"type": "status", "state": state, "msg": message})

        async def on_error(stage: str, msg: str) -> None:
            await self._send(websocket, {"type": "error", "stage": stage, "msg": msg})

        callbacks = CopilotCallbacks(on_answer=on_answer, on_partial=on_partial, on_state=on_state, on_error=on_error)
        self._copilot = InterviewCopilot(self._config, callbacks)
        await on_state("ready", "")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    await on_error("protocol", "Invalid JSON payload")
                    continue
                await self._dispatch(data)
        finally:
            if self._copilot:
                await self._copilot.shutdown()
            self._copilot = None
            self._active_socket = None
            logger.info("Renderer disconnected")

    async def _dispatch(self, payload: Dict[str, Any]) -> None:
        if not self._copilot:
            return
        action = payload.get("type")
        try:
            if action == "start_listen":
                await self._copilot.start()
            elif action == "stop_listen":
                await self._copilot.stop()
            elif action == "shorten_last":
                await self._copilot.shorten_last()
            elif action == "code_hint":
                await self._copilot.code_hint()
            elif action == "reindex":
                paths = payload.get("paths", [])
                count = await self._copilot.reindex(paths)
                await self._send_notification("reindex_done", {"docs": count})
            elif action == "set_config":
                await self._copilot.update_config(payload.get("payload", {}))
            else:
                logger.warning("Unknown action: %s", action)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process action %s", action)
            await self._send_notification("error", {"stage": action or "unknown", "msg": str(exc)})

    async def _send_notification(self, event_type: str, payload: Dict[str, Any]) -> None:
        if not self._active_socket:
            return
        await self._active_socket.send(json.dumps({"type": event_type, **payload}, ensure_ascii=False))

    async def start(self) -> None:
        logger.info("Starting WebSocket server on %s:%s", self._server_config.host, self._server_config.port)
        self._server = await websockets.serve(self._handler, self._server_config.host, self._server_config.port)

    async def wait_closed(self) -> None:
        if self._server is None:
            return
        await self._server.wait_closed()

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()


__all__ = ["CopilotServer", "ServerConfig"]
