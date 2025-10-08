"""Application bootstrap for the all-Python Interview Copilot."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from app.python_core.config import AppConfig

from .controller import CopilotController
from .hotkeys import HotkeyManager
from .windows import OverlayWindow, SettingsWindow

logger = logging.getLogger(__name__)


class TrayIcon(QtWidgets.QSystemTrayIcon):
    """Minimal system tray for quick access to actions."""

    def __init__(
        self,
        overlay: OverlayWindow,
        settings: SettingsWindow,
        controller: CopilotController,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        icon = self._make_icon()
        super().__init__(icon, parent)
        self._overlay = overlay
        self._settings = settings
        self._controller = controller
        self._listening = False

        menu = QtWidgets.QMenu(parent)
        self.toggle_overlay_action = menu.addAction("Показать/скрыть оверлей", overlay.toggle_visibility)
        self.toggle_listen_action = menu.addAction("Начать слушать", self._toggle_listen)
        menu.addSeparator()
        menu.addAction("Настройки", settings.show)
        menu.addSeparator()
        menu.addAction("Выход", QtWidgets.QApplication.quit)
        self.setContextMenu(menu)

    def _make_icon(self) -> QtGui.QIcon:
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtGui.QColor("#4338ca"))
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtCore.Qt.white)
        painter.setFont(QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold))
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "IC")
        painter.end()
        return QtGui.QIcon(pixmap)

    def set_listening(self, listening: bool) -> None:
        self._listening = listening
        self.toggle_listen_action.setText("Стоп" if listening else "Начать слушать")

    def _toggle_listen(self) -> None:
        if self._listening:
            self._controller.stop_listen()
        else:
            self._controller.start_listen()


def ensure_config(path: Path) -> AppConfig:
    if not path.exists():
        config = AppConfig()
        path.write_text(json.dumps(config.dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        return config
    return AppConfig.load(path)


def run(config_path: Path | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = QtWidgets.QApplication(sys.argv)
    config_file = config_path or Path("config.json")
    config = ensure_config(config_file)

    controller = CopilotController(config_file)
    controller.start()

    overlay = OverlayWindow(controller)
    overlay.apply_overlay_config(config)

    settings = SettingsWindow(controller, config, overlay)
    overlay.attach_settings_window(settings)

    tray = TrayIcon(overlay, settings, controller)
    tray.show()

    hotkeys = HotkeyManager(overlay.toggle_visibility, controller.shorten_last, controller.code_hint)
    hotkeys.start()

    controller.statusChanged.connect(lambda state, message: tray.set_listening(state == "listening"))
    controller.statusChanged.connect(overlay.update_status)
    controller.partialTranscript.connect(overlay.update_partial)
    controller.answerReceived.connect(overlay.update_answer)
    controller.errorOccurred.connect(overlay.show_error)

    def on_config(payload: dict) -> None:
        cfg = AppConfig()
        cfg.update_from_payload(payload)
        overlay.apply_overlay_config(cfg)

    controller.configUpdated.connect(on_config)

    overlay.show()

    def cleanup() -> None:
        hotkeys.stop()
        tray.hide()
        controller.shutdown()

    app.aboutToQuit.connect(cleanup)
    return app.exec()


def main() -> None:
    run()


__all__ = ["run", "main"]
