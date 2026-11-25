# Манифест конвейера

Команда: ЗАПОЛНИТЬ
Тег заморозки: ЗАПОЛНИТЬ

## Как работает конвейер

1. **Учебный слой (часть А).** `python run.py next <глава>` режет главу на порции и пишет промпт `work/<глава>/prompts/NN.md`;
   модель Claude отвечает в `work/<глава>/answers/NN.json` (сейчас это сессия Claude Code, без ключа API);
   `python run.py build <глава>` собирает `data/<глава>/layer.json` и маршрутизацию, проверяет покрытие.
2. **Курс (часть Б).** `python run.py course <глава>` (внутри `run_b.py`) **без модели**, детерминированно из слоя:
   задания (`gen_tasks_offline.py`), перерисованные рисунки книги (`figures/redraw.py`; кривые каротажных диаграмм и палеток
   один раз оцифрованы по скану `figures/trace_log.py` и хранятся в `data/<глава>/figures/*.json`), схемы шагов, анимации узлов
   по шаблонам, проверка покрытия шаблонами, офлайн-курс `out/<глава>/index.html`, строка в `metrics.csv`.
3. **Ролики.** `python run_b.py <глава> --videos`: озвучка, таймлайн, кадры, звук −16 LUFS, субтитры, проверка
   распознаванием речи, паспорт (`videos/<id>/passport.json`, читаемый `passport.md`).
4. **Модуль проверки (часть А).** `python run.py review <пакет>` → промпты → ответы Claude → `python run.py review-build`.

Каждый шаг проверяется по схемам организаторов (`schema/official`) и правилам ТЗ (`engine/validate_layer.py`,
`engine/video/passport_check.py`); при нарушении сборка останавливается (`--strict`).

## Модели

| Этап | Модель | Версия | Где работает | Что уходит наружу | Как заменить |
| --- | --- | --- | --- | --- | --- |
| Учебный слой | Claude (Anthropic) через Claude Code: промпт-файл → ответ-файл | Claude Opus 5.5 (`claude-opus-5-5`) | облако Anthropic | текст порции главы | любая модель отвечает на те же `prompts/NN.md`; с ключом — `engine/llm_client.py` (`ANTHROPIC_API_KEY`, `LLM_MODEL`) |
| Курс, задания, рисунки, анимации | нет модели (код по слою) | — | локально | ничего | — |
| Модуль проверки | Claude через Claude Code (как слой) | Claude Opus 5.5 | облако Anthropic | текст пакета проверки | как слой |
| Озвучка (основная) | ElevenLabs, eleven_multilingual_v2 | голос Daniel (onwK4e9ZLuTAKqWW03F9) | облако | только текст сценария | `voice` в `videos/<id>/video.json` (`elevenlabs:<voice_id>`); использование разрешено организаторами |
| Озвучка (запасная) | Microsoft Pavel (Windows OneCore, ru-RU) | системный голос Windows 11 | локально | ничего | при отказе основной вся серия переозвучивается запасным голосом |
| Проверка озвучки | Whisper small (faster-whisper 1.2.1, CPU int8) | веса Systran/faster-whisper-small | локально | ничего | `ASR_MODEL` |
| Иллюстрации и кадры роликов | нет (детерминированная графика кодом) | — | локально | ничего | — |

Ключи (`ELEVENLABS_API_KEY`, при наличии `ANTHROPIC_API_KEY`) — только переменные окружения, в репозиторий не кладутся.
Главы, книги и ролики не публикуются и в git не попадают (`.gitignore`).

## Инструменты

| Инструмент | Версия | Для чего | Данные наружу |
| --- | --- | --- | --- |
| Python | 3.13 | конвейер, сборка курса | нет |
| jsonschema | 4.26.0 | проверка форматов организаторов | нет |
| Pillow | 12.0.0 | кадры роликов, перенос текста по ширине | нет |
| FFmpeg (imageio-ffmpeg) | 9.0.2 | сборка видео, громкость −16 LUFS (ebur128), субтитры | нет |
| num2words | 0.5 | числа словами для озвучки | нет |
| PyMuPDF | 1.26 | страницы книги для оцифровки рисунков (`engine/figures/trace_log.py`) | нет |
| NumPy | 2.x | оцифровка кривых по скану | нет |
| faster-whisper | 1.2.1 (ctranslate2 4.9.1) | распознавание речи, WER и замер синхрона озвучки | нет |
| anthropic (SDK) | 2.14.0 | только при работе с ключом API | да, см. модели |

## Запуск

```
python run.py course <глава>          # курс части Б из готового слоя
python run_b.py all --videos --strict # все главы + ролики
python engine/video/passport_md.py videos/latyshova_short videos/basniev_long
```
