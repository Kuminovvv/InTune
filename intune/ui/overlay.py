"""Overlay UI skeleton using PySide6 when available."""

from __future__ import annotations

from dataclasses import dataclass

try:  # pragma: no cover
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None  # type: ignore


@dataclass(slots=True)
class OverlayConfig:
    transparency: float
    always_on_top: bool
    click_through: bool


class OverlayWindow:
    def __init__(self, config: OverlayConfig) -> None:
        if QtWidgets is None:
            raise RuntimeError("PySide6 не установлен")
        self._config = config
        self._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self._window = QtWidgets.QWidget()
        self._setup_window()

    def _setup_window(self) -> None:
        self._window.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        if self._config.always_on_top:
            self._window.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self._window.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._window.setWindowOpacity(self._config.transparency)
        layout = QtWidgets.QVBoxLayout(self._window)
        layout.addWidget(QtWidgets.QLabel("InTune Assistant"))
        self._window.resize(400, 200)

    def show(self) -> None:
        self._window.show()
        self._app.exec()


__all__ = ["OverlayConfig", "OverlayWindow"]
