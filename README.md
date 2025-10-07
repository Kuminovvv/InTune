# Interview Copilot (InTune)

Локальный ассистент для подготовки и прохождения технических собеседований. Python-core реализует аудиозахват, распознавание речи, работу с базой знаний и генерацию подсказок через Ollama в полном соответствии с ТЗ.

## Структура

```
app/
  python_core/
    audio.py         # захват системного звука через WASAPI loopback с авто-переподключением
    stt.py           # интеграция с faster-whisper
    rag.py           # хранение знаний (SQLite + FAISS)
    llm.py           # клиент для Ollama
    ingestion.py     # импорт файлов и проектов
    orchestrator.py  # сборка конвейера, VAD, partial transcript и режимы подсказок
    server.py        # WebSocket протокол для Electron-части
    main.py          # CLI-обёртка
    requirements.txt
config.json
```

## Быстрый старт

1. Создайте и активируйте виртуальное окружение Python 3.10+.
2. Установите зависимости:

   ```bash
   pip install -r app/python_core/requirements.txt
   ```

3. Убедитесь, что установлен [Ollama](https://ollama.com/) и скачана модель `qwen2.5:7b-instruct`:

   ```bash
   ollama run qwen2.5:7b-instruct
   ```

4. Запустите Python-core:

   ```bash
   python -m app.python_core.main --config config.json
   ```

5. Electron-клиент подключается к `ws://127.0.0.1:8765` и управляет подсказками через JSON-протокол.

## Возможности Python-core

* **Аудио**: захват системного звука через WASAPI loopback, автоматическое переподключение при смене устройства по умолчанию, тестовый тон и метрики (VU-meter) для проверки захвата.
* **VAD + STT**: разбиение аудио на фразы паузами ≥0.8 c, вывод частичных транскриптов в реальном времени и окончательный текст на модели `faster-whisper`.
* **RAG**: импорт файлов/папок в локальную базу (SQLite + FAISS), обновление индекса через `reindex`, фильтрация по профилю, эмбеддинги `bge-small-ru-en`.
* **LLM**: генерация подсказок через локальный Ollama (`qwen2.5:7b-instruct`) с режимами default/shorten/code.
* **WebSocket API**: управление запуском, спец-режимами подсказок и состоянием конвейера, сообщения об ошибках на каждом этапе.

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

Все параметры вынесены в `config.json` и соответствуют требованиям ТЗ: выбор аудио устройства, язык распознавания, модель Ollama, настройки окна оверлея и параметры RAG.

## Ограничения

* Код рассчитан на Windows (WASAPI loopback), но может работать и на других ОС при замене устройств.
* Для импорта DOCX используется пакет `python-docx`.
* Интеграция с Electron в этом репозитории не включена; сервер предоставляет WebSocket API для будущего клиента.
