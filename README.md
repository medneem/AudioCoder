# AudioCoder

Портативный аудиоконвертер для Windows 10/11 x64 на Python 3.13 + CustomTkinter. Основан по структуре, версионности и релизной схеме на [FlacSplitter](https://github.com/medneem/FlacSplitter).

## Возможности MVP

- Открытие аудиофайла (FLAC, MP3, WAV, APE, AAC/M4A, OGG, Opus и другие форматы, поддерживаемые установленным FFmpeg).
- Определение кодека, длительности, частоты дискретизации и числа каналов через FFprobe.
- **CTkRangeSlider** с двумя ползунками: выбор начала и конца аудиофрагмента с временными метками.
- Конвертация в **FLAC / MP3 / WAV / Opus**. Для MP3 доступен выбор битрейта: 128/192/256/320 kbit/s.
- Фоновая обработка (интерфейс не блокируется), прогресс, отмена.
- Имя результата: `<исходное имя>_converted.<формат>` в исходной или выбранной папке.
- Исходные файлы не изменяются; существующие выходные файлы не перезаписываются.
- Настройки сохраняются в `config.json` возле исходников или EXE (UTF-8, в том числе русские пути).

**Важно:** обрезка использует декодирование/перекодирование FFmpeg, а не побайтовое копирование. Lossless-источник в FLAC/WAV сохраняет аудио без потерь, MP3/Opus — с потерями. WAV экспортируется как PCM 24-bit. Обложки и дополнительные дорожки в MVP не копируются. Waveform и пакетная конвертация пока не реализованы.

## Разработка (Windows)

Требуется Python 3.13. FFmpeg **и FFprobe** должны находиться возле `main.py` либо в PATH.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python main.py
python -m unittest discover -s tests -v
```

CTkRangeSlider 0.3 включён как исходный код в `vendor/CTkRangeSlider`. Он использует внутренний API CustomTkinter 5.2.x, поэтому версия CustomTkinter зафиксирована. Новую 6.x необходимо отдельно проверить на совместимость.

## Архитектура

```text
main.py                        — запуск GUI
audiocoder/
  ui.py                        — CustomTkinter UI, события, фоновые worker threads
  selection.py                 — выбор и проверка диапазона
  media.py                     — FFprobe, метаданные и поиск инструментов
  converter.py                 — FFmpeg и безопасная финализация результата
  settings.py                  — переносимые настройки JSON
vendor/CTkRangeSlider/         — неизменённые upstream исходники виджета + лицензия
tests/                         — unittest (логика, GUI smoke, FFmpeg integration)
scripts/stamp_version.py       — version.py и Windows VERSIONINFO
scripts/build_icon.py          — генерация PNG / Windows ICO
.github/workflows/build-windows.yml
```

GUI не вызывает FFmpeg в основном потоке. Файлы-результаты сначала создаются под случайным временным именем в целевой папке. После успешного завершения применяется атомарное создание конечного имени без замены существующего файла (hard link), затем временный файл удаляется. Если файловая система не поддерживает hard links, будет ошибка; в этой версии небезопасного fallback с перезаписью нет.

## Версии и релизы

- В исходниках: `0.1.0-dev`.
- GitHub Actions на каждом запуске выставляет `0.1.<github.run_number>` и штампует Windows VERSIONINFO.
- В PR: запускаются тесты и собирается ZIP-артефакт.
- При push в `main`: после успешной сборки автоматически создаются тег `v0.1.N` и GitHub Release с `AudioCoder-v0.1.N-windows-x64.zip`.
- Архив содержит `AudioCoder.exe`, `ffmpeg.exe`, `ffprobe.exe`, иконку, `VERSION.txt` и тексты лицензий.

## Тесты

`python -m unittest discover -s tests -v`: покрыты границы фрагментов, формирование CLI аргументов, ошибки, защита от перезаписи, отмена, JSON-конфиг, FFprobe, GUI smoke и реальная конвертация короткого тестового сигнала через FFmpeg. Интеграционный тест пропускается, если FFmpeg/FFprobe недоступны. Windows CI устанавливает их перед тестами.

## Лицензия

Исходный код — MIT. Лицензии зависимостей и FFmpeg описаны в [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
