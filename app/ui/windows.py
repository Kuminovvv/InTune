"""Qt widgets composing the Interview Copilot desktop UI."""

from __future__ import annotations

import threading
from typing import Dict, Iterable

from PySide6 import QtCore, QtGui, QtWidgets

from app.python_core.audio import AudioCapturer, AudioConfig, list_output_devices
from app.python_core.config import AppConfig

from .controller import CopilotController


class OverlayWindow(QtWidgets.QMainWindow):
    """Compact always-on-top overlay with latest transcript and hint."""

    def __init__(self, controller: CopilotController, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self._is_listening = False
        self._settings_window: SettingsWindow | None = None

        self.setWindowTitle("Interview Copilot")
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(20, 20, 20, 230))
        palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
        self.setPalette(palette)

        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self.status_label = QtWidgets.QLabel("Готов слушать…", self)
        font = self.status_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)

        self.partial_label = QtWidgets.QLabel("", self)
        self.partial_label.setWordWrap(True)
        self.partial_label.setStyleSheet("color: #a0a0a0")
        layout.addWidget(self.partial_label)

        self.hint_edit = QtWidgets.QTextEdit(self)
        self.hint_edit.setReadOnly(True)
        self.hint_edit.setMinimumHeight(80)
        layout.addWidget(self.hint_edit)

        button_row = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("Начать", self)
        self.start_button.clicked.connect(self._on_toggle_listen)
        button_row.addWidget(self.start_button)

        self.shorten_button = QtWidgets.QPushButton("Сжать", self)
        self.shorten_button.clicked.connect(controller.shorten_last)
        button_row.addWidget(self.shorten_button)

        self.code_button = QtWidgets.QPushButton("Код", self)
        self.code_button.clicked.connect(controller.code_hint)
        button_row.addWidget(self.code_button)

        self.settings_button = QtWidgets.QPushButton("Настройки", self)
        button_row.addWidget(self.settings_button)

        layout.addLayout(button_row)
        self.setCentralWidget(central)

    # ------------------------------------------------------------------
    def attach_settings_window(self, window: "SettingsWindow") -> None:
        self._settings_window = window
        self.settings_button.clicked.connect(window.show)

    def apply_overlay_config(self, config: AppConfig) -> None:
        self.setGeometry(config.overlay.x, config.overlay.y, config.overlay.width, config.overlay.height)
        self.setWindowOpacity(config.overlay.opacity)

    # ------------------------------------------------------------------
    # Controller callbacks
    # ------------------------------------------------------------------
    def update_status(self, state: str, message: str) -> None:
        mapping = {
            "ready": "Готов слушать…",
            "listening": "Слушаю собеседника…",
            "thinking": "Формирую подсказку…",
            "reindex": "Обновляю базу знаний…",
            "error": "Произошла ошибка",
        }
        self.status_label.setText(mapping.get(state, state))
        if state == "listening":
            self._is_listening = True
            self.start_button.setText("Стоп")
        elif state in {"ready", "error"}:
            self._is_listening = False
            self.start_button.setText("Начать")
        if message:
            self.partial_label.setText(message)

    def update_partial(self, text: str) -> None:
        self.partial_label.setText(text)

    def update_answer(self, question: str, hint: str) -> None:
        self.hint_edit.setPlainText(hint)
        self.partial_label.setText(question)

    def show_error(self, stage: str, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, "Ошибка", f"{stage}: {message}")

    # ------------------------------------------------------------------
    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def _on_toggle_listen(self) -> None:
        if self._is_listening:
            self._controller.stop_listen()
        else:
            self._controller.start_listen()


class SettingsWindow(QtWidgets.QDialog):
    """Configuration and knowledge management window."""

    def __init__(self, controller: CopilotController, config: AppConfig, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Interview Copilot — Настройки")
        self.resize(640, 520)
        self._controller = controller
        self._config = config
        self._test_thread: threading.Thread | None = None

        main_layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget(self)
        main_layout.addWidget(self.tabs)

        self.audio_tab = self._build_audio_tab()
        self.speech_tab = self._build_speech_tab()
        self.llm_tab = self._build_llm_tab()
        self.overlay_tab = self._build_overlay_tab()
        self.knowledge_tab = self._build_knowledge_tab()
        self.profile_tab = self._build_profile_tab()

        self.tabs.addTab(self.audio_tab, "Аудио")
        self.tabs.addTab(self.speech_tab, "Речь")
        self.tabs.addTab(self.llm_tab, "LLM")
        self.tabs.addTab(self.overlay_tab, "Оверлей")
        self.tabs.addTab(self.knowledge_tab, "Знания")
        self.tabs.addTab(self.profile_tab, "Профили")

        self.status_bar = QtWidgets.QLabel("", self)
        main_layout.addWidget(self.status_bar)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Close, self)
        buttons.accepted.connect(self._save_config)
        buttons.rejected.connect(self.close)
        main_layout.addWidget(buttons)

        controller.configUpdated.connect(self._on_config_updated)

        self._load_from_config(config)

    # ------------------------------------------------------------------
    def _build_audio_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(widget)

        form = QtWidgets.QFormLayout()
        self.device_combo = QtWidgets.QComboBox(widget)
        self.refresh_devices()
        form.addRow("Loopback-устройство", self.device_combo)

        self.auto_reconnect = QtWidgets.QCheckBox("Автопереподключение", widget)
        form.addRow("Автоматически переподключаться", self.auto_reconnect)

        layout.addLayout(form)

        buttons = QtWidgets.QHBoxLayout()
        refresh_button = QtWidgets.QPushButton("Обновить устройства", widget)
        refresh_button.clicked.connect(self.refresh_devices)
        buttons.addWidget(refresh_button)

        self.test_button = QtWidgets.QPushButton("Test Capture", widget)
        self.test_button.clicked.connect(self._on_test_capture)
        buttons.addWidget(self.test_button)

        layout.addLayout(buttons)

        self.test_result = QtWidgets.QLabel("", widget)
        self.test_result.setWordWrap(True)
        layout.addWidget(self.test_result)

        layout.addStretch(1)
        return widget

    def _build_speech_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(widget)

        self.language_combo = QtWidgets.QComboBox(widget)
        self.language_combo.addItems(["auto", "ru", "en"])
        form.addRow("Язык", self.language_combo)

        self.vad_aggr = QtWidgets.QSpinBox(widget)
        self.vad_aggr.setRange(0, 3)
        form.addRow("VAD агрессивность", self.vad_aggr)

        self.silence_spin = QtWidgets.QDoubleSpinBox(widget)
        self.silence_spin.setRange(0.1, 3.0)
        self.silence_spin.setSingleStep(0.1)
        form.addRow("Таймаут тишины (сек)", self.silence_spin)

        return widget

    def _build_llm_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(widget)

        self.model_edit = QtWidgets.QLineEdit(widget)
        form.addRow("Модель Ollama", self.model_edit)

        self.timeout_spin = QtWidgets.QSpinBox(widget)
        self.timeout_spin.setRange(10, 600)
        self.timeout_spin.setSuffix(" сек")
        form.addRow("Таймаут", self.timeout_spin)

        return widget

    def _build_overlay_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(widget)

        self.overlay_x = QtWidgets.QSpinBox(widget)
        self.overlay_x.setRange(0, 4000)
        form.addRow("Позиция X", self.overlay_x)

        self.overlay_y = QtWidgets.QSpinBox(widget)
        self.overlay_y.setRange(0, 4000)
        form.addRow("Позиция Y", self.overlay_y)

        self.overlay_width = QtWidgets.QSpinBox(widget)
        self.overlay_width.setRange(200, 2000)
        form.addRow("Ширина", self.overlay_width)

        self.overlay_height = QtWidgets.QSpinBox(widget)
        self.overlay_height.setRange(120, 2000)
        form.addRow("Высота", self.overlay_height)

        self.overlay_opacity = QtWidgets.QDoubleSpinBox(widget)
        self.overlay_opacity.setRange(0.2, 1.0)
        self.overlay_opacity.setSingleStep(0.05)
        form.addRow("Непрозрачность", self.overlay_opacity)

        return widget

    def _build_knowledge_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(widget)

        form = QtWidgets.QFormLayout()
        self.top_k_spin = QtWidgets.QSpinBox(widget)
        self.top_k_spin.setRange(1, 20)
        form.addRow("Top-k", self.top_k_spin)
        layout.addLayout(form)

        button_row = QtWidgets.QHBoxLayout()
        import_files = QtWidgets.QPushButton("Импорт файлов", widget)
        import_files.clicked.connect(self._import_files)
        button_row.addWidget(import_files)

        import_folder = QtWidgets.QPushButton("Импорт папки", widget)
        import_folder.clicked.connect(self._import_folder)
        button_row.addWidget(import_folder)

        layout.addLayout(button_row)
        layout.addStretch(1)
        return widget

    def _build_profile_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(widget)
        self.profile_combo = QtWidgets.QComboBox(widget)
        self.profile_combo.addItems(["frontend", "backend", "system design"])
        layout.addWidget(self.profile_combo)
        layout.addStretch(1)
        return widget

    # ------------------------------------------------------------------
    def refresh_devices(self) -> None:
        devices = ["System Default"] + list_output_devices()
        current = self.device_combo.currentText() if hasattr(self, "device_combo") else None
        self.device_combo.clear()
        self.device_combo.addItems(devices)
        if current and current in devices:
            self.device_combo.setCurrentText(current)

    def _load_from_config(self, config: AppConfig) -> None:
        self.device_combo.setCurrentText(config.audio.device_name)
        self.auto_reconnect.setChecked(config.audio.auto_reconnect)
        self.language_combo.setCurrentText(config.stt.language)
        self.vad_aggr.setValue(config.vad.aggressiveness)
        self.silence_spin.setValue(config.vad.silence_sec)
        self.model_edit.setText(config.ollama.model)
        self.timeout_spin.setValue(config.ollama.timeout_sec)
        self.overlay_x.setValue(config.overlay.x)
        self.overlay_y.setValue(config.overlay.y)
        self.overlay_width.setValue(config.overlay.width)
        self.overlay_height.setValue(config.overlay.height)
        self.overlay_opacity.setValue(config.overlay.opacity)
        self.top_k_spin.setValue(config.rag.top_k)
        index = self.profile_combo.findText(config.profile)
        if index >= 0:
            self.profile_combo.setCurrentIndex(index)

    def _collect_payload(self) -> Dict[str, Dict[str, object] | str]:
        return {
            "audio": {
                "device_name": self.device_combo.currentText(),
                "auto_reconnect": self.auto_reconnect.isChecked(),
            },
            "vad": {
                "aggressiveness": int(self.vad_aggr.value()),
                "silence_sec": float(self.silence_spin.value()),
            },
            "stt": {
                "language": self.language_combo.currentText(),
            },
            "ollama": {
                "model": self.model_edit.text(),
                "timeout_sec": int(self.timeout_spin.value()),
            },
            "overlay": {
                "x": int(self.overlay_x.value()),
                "y": int(self.overlay_y.value()),
                "width": int(self.overlay_width.value()),
                "height": int(self.overlay_height.value()),
                "opacity": float(self.overlay_opacity.value()),
            },
            "rag": {
                "top_k": int(self.top_k_spin.value()),
            },
            "profile": self.profile_combo.currentText(),
        }

    def _save_config(self) -> None:
        payload = self._collect_payload()
        future = self._controller.update_config(payload)
        try:
            future.result(timeout=5)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить конфигурацию: {exc}")
            return
        self.status_bar.setText("Настройки сохранены")

    def _on_config_updated(self, payload: Dict[str, object]) -> None:
        config = AppConfig()
        config.update_from_payload(payload)
        self._config = config
        self._load_from_config(config)

    # ------------------------------------------------------------------
    def _on_test_capture(self) -> None:
        if self._test_thread and self._test_thread.is_alive():
            return
        config = self._controller.current_config()
        config.audio.device_name = self.device_combo.currentText()
        config.audio.auto_reconnect = self.auto_reconnect.isChecked()

        def worker() -> None:
            try:
                capture = AudioCapturer(AudioConfig(**vars(config.audio)))
                metrics = capture.test_capture(duration=2.0)
            except Exception as exc:  # noqa: BLE001
                QtCore.QTimer.singleShot(
                    0, lambda: QtWidgets.QMessageBox.critical(self, "Ошибка", f"Test Capture: {exc}")
                )
                return
            if not metrics:
                text = "Сигнал не обнаружен"
            else:
                last = metrics[-1]
                text = f"RMS: {last.rms:.2f}, Peak: {last.peak:.2f}"
            QtCore.QTimer.singleShot(0, lambda: self.test_result.setText(text))

        self.test_result.setText("Измерение…")
        self._test_thread = threading.Thread(target=worker, daemon=True)
        self._test_thread.start()

    # ------------------------------------------------------------------
    def _import_files(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Выберите файлы знаний")
        if paths:
            self._trigger_reindex(paths)

    def _import_folder(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку")
        if path:
            self._trigger_reindex([path])

    def _trigger_reindex(self, paths: Iterable[str]) -> None:
        future = self._controller.reindex(paths)
        self.status_bar.setText("Переиндексация…")

        def wait() -> None:
            try:
                count = future.result()
            except Exception as exc:  # noqa: BLE001
                QtCore.QTimer.singleShot(
                    0, lambda: QtWidgets.QMessageBox.critical(self, "Ошибка", f"Индексирование: {exc}")
                )
                return
            QtCore.QTimer.singleShot(0, lambda: self.status_bar.setText(f"Добавлено документов: {count}"))

        threading.Thread(target=wait, daemon=True).start()


__all__ = ["OverlayWindow", "SettingsWindow"]
