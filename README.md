# Глава → курс (хакатон)

Конвейер: **глава (md) → учебный слой (JSON) → маршрутизация → курс и ролики**. Курс собирается только из слоя. Форматы официальные (`schema/official/`). Требования ТЗ: `TZ-checklist.md`.

## Посмотреть курс

```
pip install -r requirements.txt
python run.py course latyshova      # потом открыть out/latyshova/index.html
```

Для слоя и проверки хватает Python 3.10+. Для анимаций и роликов ещё нужны Node.js, Edge и FFmpeg. Видео в git не хранится, поэтому первая сборка главы рисует анимации заново (около 5 минут), следующие идут секунды. Ролики собираются отдельно: `python run.py rebuild latyshova video`. Курс открывается без интернета и сервера.

## Готовые слои

| Глава | Узлов | Где |
| --- | --- | --- |
| Латышова, гл. V §17–20 | 45 | `data/latyshova/` |
| Басниев, гл. XXIII и XXIV §1 | 48 | `data/basniev/` |
| Кузнецов, гл. 10 §10.1–10.4 | 41 | `data/kuznetsov/` |

В каждой папке `layer.json`, `routing.json`, `coverage.json`, `tasks.json`, `illustrations.json`; `step_id` — это id узла.

## Часть А: слой

1. Положите в `input/` папку `books md` с главами. Папка `input/` в git не попадает: главы публиковать нельзя.
2. `python run.py units all` — нарезка на единицы.
3. `python run.py next <глава>` пишет промпт порции в `work/<глава>/prompts/NN.md`, ответ модели (JSON) кладут в `work/<глава>/answers/NN.json`. Повторять, пока порции не кончатся.
4. `python run.py build <глава>` — слой, маршрутизация, покрытие, проверка.
5. `python run.py course <глава>` — слой в `data/<глава>/`, курс в `out/<глава>/index.html`.
6. Чужой пакет с закладками: `python run.py review <package.json>`, ответы в `work/review_<пакет>/answers/`, затем `python run.py review-build <package.json>`.

Модель заменяема: движок только пишет промпты и читает JSON. Сейчас отвечает Claude в Claude Code, API-ключ не нужен.

## Задания

`python run.py tasks <глава>` пишет промпт `work/<глава>/tasks_prompt.md`, ответ модели кладут в `work/<глава>/tasks_answer.json`, `python run.py tasks-build <глава>` собирает `data/<глава>/tasks.json` и проверяет ключи: неверный вариант не может быть верным утверждением главы, расчёт пересчитывается, порядок не выдан подписями. `engine/gen_tasks_offline.py` — запасной путь без модели: он перезаписывает `tasks.json`, а его ключи эту проверку не проходят.

## Часть Б: курс, задания, ролики

```
python engine/validate_layer.py --dir data/latyshova          # схемы организаторов + правила ТЗ
python engine/gen_exercises.py --dir data/latyshova           # tasks.json через Claude API (нужен ключ)
python engine/build_course.py --dir data/latyshova --out out/latyshova --strict
python engine/llm_client.py --ping                            # проверка связи с Claude API
```

## Что где

| Папка | Что внутри |
| --- | --- |
| `engine/units.py`, `nodes.py`, `route.py`, `check.py`, `review.py`, `schema.py` | Нарезка, извлечение узлов, маршрутизация, проверка слоя, проверка чужого пакета |
| `engine/build_course.py`, `template.html`, `validate_layer.py`, `nodetext.py` | Сборщик курса и проверка его входов |
| `engine/gen_exercises.py`, `llm_client.py` | Задания через Claude API |
| `engine/scenes/`, `engine/video/` | Сцены, озвучка, субтитры, проверка паспорта ролика |
| `domain_pack/` | Доменный пакет геологии; другой домен — `domains/<домен>/` |
| `prompts/` | Промпты модели |
| `data/book_index/` | Индексы анализов книг (не сверено со страницами) |
| `data_selftest/` | Самотест шаблона, вымышленный контент |
| `chapters.json` | Главы: файл, страницы PDF, границы. Без `parts` берётся весь файл |
| `work/`, `out/` | Сгенерированное, в git не попадает |

## Проверки

```
python -m unittest tests.test_engine
python tests/selfcheck_chapters.py
python tests/test_offline.py            # нужны пакеты из requirements.txt
python tests/make_selftest.py
```

## Договорённости

- Единица главы: `p095.03`, третья единица на стр. 95.
- Описания рисунков в md написаны нейросетью (`figure_ai`), цитировать их как автора нельзя.
- Наши поля сверх схемы: `node.units`, `title_novice`, `glossary`, `video_scores`, `formulas`, `tables`, `layers.*.paras` (абзацы со страницами), `worked_examples[].number`, `layer.uncovered`.
- `error` в проверке — факт, `suspect` — подозрение на искажение смысла.
- Правка слоя: меняем ответ в `work/<глава>/answers/`, затем `build` и `course`. `data/<глава>/layer.json` руками не правим.
- Ручная правка на тесте — строка в `manual_edits.csv` и коммит: `python run.py log <глава> <файл> <минуты> <людей> <прогон> "<что>" "<почему>"`.
- После заморозки (тег) код, промпты и доменный пакет не меняются.
- Книги, сканы, видео и папка `хакатон/` в git не кладём.

## Часть Б одной командой

```
python run_b.py <глава|all> [--videos] [--no-anim] [--strict]
```

Из `data/<глава>/layer.json` собирает задания, перерисованные рисунки книги, анимации видеоузлов без ролика, иллюстрации,
отчёт о покрытии шаблонами и курс `out/<глава>/index.html`; пишет строку в `metrics.csv`. После правки факта в слое —
та же команда (с `--videos` пересобираются и ролики главы: страница шага и ролик одной командой).

## Ролики

Подача сделана по примерам организаторов 01–06 (разбор: `domain_pack/video_style.md`): вопрос в первом кадре, один непрерывный мир, движение камеры, лупа, кривая рядом с механизмом, итог и вопрос на перенос.

```
python run.py video <глава> <узел> short     # промпт сценария, ответ в work/<глава>/video_answer.json
python run.py video-build <глава> preview    # проверка сценария и кадры-превью в out/video/<id>/
python run.py video-build <глава>            # ролик, субтитры, паспорт, запись в курс
python run.py rebuild <глава> video          # слой, задания, ролики и курс после правки факта
python run.py anims <глава>                  # промпт живых анимаций видеоузлов, потом anims-build
python tests/preview_scenes.py               # показ сцен бурения и разреза во времени
```

Кадры рисует установленный Edge (`engine/video/web`), пакеты Python для этого не нужны: достаточно Node и FFmpeg. Сцены: `log_run` прибор и кривые, `pressure` давление вокруг скважины, `wellbore` бурение, `strata` разрез во времени, `curve` формула и пласт под ней, `plan` вид сверху. Если утверждение слоя поправили, фраза ролика заменяется его новым текстом.

## Озвучка

Готовая дорожка проверяется локальным распознаванием речи: `python engine/video/asr.py videos/<id>` (делается и само при сборке). Модель ставится один раз: `python engine/video/asr.py --download`.

Порядок голосов серии: `domain_pack/voices.json`, берётся первый сработавший (`engine/video/tts.py`: ElevenLabs, Piper, голоса Windows).

Основной голос — ElevenLabs (`"voice": "elevenlabs:<voice_id>"` в `videos/<ролик>/video.json`, ключ в `ELEVENLABS_API_KEY`,
наружу уходит только текст сценария), запасной — локальный Microsoft Pavel. Если облако отказало, вся серия
переозвучивается запасным голосом. Выбрать голос: `python engine/video/elevenlabs_voices.py`.
