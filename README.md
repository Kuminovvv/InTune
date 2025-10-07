# Interview Copilot (InTune)

Локальный ассистент для подготовки и прохождения технических собеседований. В составе репозитория:

* **Python-core** — аудиозахват (WASAPI loopback), VAD + STT, RAG и генерация подсказок через Ollama;
* **Electron UI** — оверлей подсказок, окно настроек, глобальные хоткеи, системный трей и управление пайплайном.

## Структура

```
app/
  python_core/      # конвейер обработки звука и генерации ответов
  electron/         # Electron + React (overlay + settings)
config.json         # общая конфигурация приложения
package.json        # npm workspaces (корневая точка входа)
```

## Быстрый старт

1. Установите Python 3.10+ и Node.js 18+.
2. Создайте и активируйте виртуальное окружение Python.
3. Установите зависимости Python-core:

   ```bash
   pip install -r app/python_core/requirements.txt
   ```

4. Установите зависимости Electron UI (npm workspaces):

   ```bash
   npm install
   ```

5. Убедитесь, что установлен [Ollama](https://ollama.com/) и скачана модель `qwen2.5:7b-instruct`:

   ```bash
   ollama run qwen2.5:7b-instruct
   ```

6. Запустите приложение (Python-core + Electron UI) **одной командой** из корня репозитория:

   ```bash
   npm run dev
   ```

   Скрипт поднимет Vite dev-server, запустит Electron и автоматически стартует Python-core. UI подключается к `ws://127.0.0.1:8765` и управляет пайплайном через JSON-протокол.

## Возможности

* **Аудио**: захват системного звука через WASAPI loopback, автоматическое переподключение при смене устройства по умолчанию, тестовый тон и метрики (VU-meter) для проверки захвата.
* **VAD + STT**: разбиение аудио на фразы паузами ≥0.8 c, вывод частичных транскриптов в реальном времени и окончательный текст на модели `faster-whisper`.
* **RAG**: импорт файлов/папок в локальную базу (SQLite + FAISS), обновление индекса через `reindex`, фильтрация по профилю, эмбеддинги `bge-small-ru-en`.
* **LLM**: генерация подсказок через локальный Ollama (`qwen2.5:7b-instruct`) с режимами default/shorten/code.
* **Electron UI**:
  * overlay-окно (frameless, always-on-top) с подсказками, статусом и последней транскрипцией;
  * окно Settings с настройкой аудио, STT, Ollama, overlay, профилей и RAG;
  * глобальные хоткеи (`Ctrl+Space`, `Ctrl+R`, `Ctrl+Q`) и системный трей для быстрого управления;
  * одна команда `npm run dev` для запуска всего стека.

## Основные команды WebSocket протокола

```jsonc
// Electron -> Python
{ "type": "start_listen" }
{ "type": "stop_listen" }
{ "type": "shorten_last" }
{ "type": "code_hint" }
{ "type": "reindex", "paths": ["C:/cv.pdf", "C:/projects"] }
{ "type": "set_config", "payload": { ... } }

// Python -> Electron
{ "type": "status", "state": "ready|listening|thinking|reindex", "msg": "" }
{ "type": "partial_transcript", "text": "..." }
{ "type": "answer", "question": "...", "hint": "..." }
{ "type": "error", "stage": "audio|stt|rag|llm|protocol", "msg": "..." }
{ "type": "reindex_done", "docs": 128 }
```

## Конфигурация

Все параметры вынесены в `config.json` и соответствуют требованиям ТЗ: выбор аудио устройства, язык распознавания, модель Ollama, настройки окна оверлея и параметры RAG. Изменения, внесённые через окно Settings, сразу сохраняются в файл и применяются Python-core.

## Ограничения

* Код рассчитан на Windows (WASAPI loopback), но может работать и на других ОС при замене устройств.
* Для импорта DOCX используется пакет `python-docx`.
