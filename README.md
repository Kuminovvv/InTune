# Interview Copilot (InTune)

Локальный ассистент для подготовки и прохождения технических собеседований. Python-core реализует аудиозахват, распознавание речи, работу с базой знаний и генерацию подсказок через Ollama.

## Структура

```
app/
  python_core/
    audio.py         # захват системного звука через WASAPI loopback
    stt.py           # интеграция с faster-whisper
    rag.py           # хранение знаний (SQLite + FAISS)
    llm.py           # клиент для Ollama
    ingestion.py     # импорт файлов и проектов
    orchestrator.py  # сборка конвейера
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

## Конфигурация

Все параметры вынесены в `config.json` и соответствуют требованиям ТЗ: выбор аудио устройства, язык распознавания, модель Ollama, настройки окна оверлея и параметры RAG.

## Ограничения

* Код рассчитан на Windows (WASAPI loopback), но может работать и на других ОС при замене устройств.
* Для импорта DOCX используется пакет `python-docx`.
* Интеграция с Electron в этом репозитории не включена; сервер предоставляет WebSocket API для будущего клиента.
