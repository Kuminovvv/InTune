"""Global hotkey integration using the keyboard library."""

from __future__ import annotations

import logging
from typing import Callable, List

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Register and manage global hotkeys for the application."""

    def __init__(self, toggle_overlay: Callable[[], None], shorten: Callable[[], None], code_hint: Callable[[], None]):
        self._toggle_overlay = toggle_overlay
        self._shorten = shorten
        self._code_hint = code_hint
        self._handles: List[int] = []
        self._active = False

    def start(self) -> None:
        try:
            import keyboard  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Global hotkeys disabled: %s", exc)
            return
        if self._active:
            return
        self._handles.append(keyboard.add_hotkey("ctrl+space", self._toggle_overlay))
        self._handles.append(keyboard.add_hotkey("ctrl+r", self._shorten))
        self._handles.append(keyboard.add_hotkey("ctrl+q", self._code_hint))
        self._active = True
        logger.info("Global hotkeys registered")

    def stop(self) -> None:
        if not self._active:
            return
        try:
            import keyboard  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001
            return
        for handle in self._handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:  # noqa: BLE001
                pass
        self._handles.clear()
        self._active = False
        logger.info("Global hotkeys unregistered")


__all__ = ["HotkeyManager"]
