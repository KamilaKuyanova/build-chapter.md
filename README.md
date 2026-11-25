# Глава → курс (хакатон)

Конвейер: **глава (md) → учебный слой (JSON) → маршрутизация → курс и ролики**. Курс собирается только из слоя, вручную не верстается. Требования ТЗ: `TZ-checklist.md`. Нужен только Python 3.10+, сторонних библиотек нет.

## Запуск

1. Положите в `input/` папку `books md` с главами и `пакет_вводных` в `input/org/`. Папка `input/` в репозиторий не попадает: главы публиковать нельзя.
2. Нарежьте главы: `python run.py units all`
3. Слой: `python run.py next <глава>` пишет промпт очередной порции в `work/<глава>/prompts/NN.md`. Ответ модели (JSON) сохраните в `work/<глава>/answers/NN.json` и повторяйте, пока порции не кончатся.
4. Сборка слоя и проверка: `python run.py build <глава>` даёт `layer.json`, `routing.json`, `coverage.json`, `check.json`.
5. Курс: `python run.py course <глава>` собирает `out/<глава>/index.html`. Откройте файл в браузере, сервер не нужен. С `--strict` сборка падает при нарушениях ТЗ.
6. Проверка чужого пакета: `python run.py review <package.json>`, ответы в `work/review_<пакет>/answers/`, затем `python run.py review-build <package.json>`.

Модель заменяема: движок только пишет промпты и читает JSON. Сейчас отвечает Claude в Claude Code, API-ключ не нужен. Порции одной главы идут по порядку: следующая знает термины предыдущих.

## Форматы

Официальные схемы организаторов лежат в `schema/` без изменений. Учебный слой хранится только по `node.schema.json`.

`schema/course_step.schema.json` — внутренний вход сборщика курса. Шаги делает `engine/to_course.py`, руками их не пишут.

Что подхватывает `course`, если файл есть:

| Файл | Схема |
| --- | --- |
| `work/<глава>/tasks.json` | `task.schema.json`; `step_id` — id узла |
| `work/<глава>/illustrations.json` | `illustration.schema.json`; `file` — путь от `work/<глава>/` |

## Что где

| Папка | Что внутри |
| --- | --- |
| `engine/units.py`, `nodes.py`, `route.py`, `check.py`, `review.py` | Нарезка, извлечение узлов, маршрутизация, проверка слоя, проверка чужого пакета |
| `engine/to_course.py`, `build_course.py`, `template.html`, `validate_nodes.py` | Переходник и сборщик курса |
| `engine/check_passport.py`, `templates/` | Паспорт ролика и его проверка до рендера |
| `engine/import_analysis.py`, `data/book_index/` | Анализы книг: `data/analysis/` (не в git) → индексы, глоссарий, `legacy_notes.json` |
| `prompts/` | Промпты модели |
| `domains/geology/` | Официальные заготовки: заблуждения `misc.*`, чек-лист `pc.*`, стайлгайд |
| `domain_pack/` | Доменный пакет: глоссарий, ударения, стайлгайд, нюансы «как сейчас» |
| `chapters.json` | Главы: файл, страницы PDF, границы. Без `parts` берётся весь файл |
| `data/nodes/` | Заглушка, не из книги |
| `manifest.json`, `metrics.csv` | Инструменты и модели с версиями; метрики |
| `work/`, `out/` | Всё сгенерированное, в репозиторий не попадает |

## Проверки

```
python -m unittest discover tests           # движок
python tests/selfcheck_chapters.py          # цитаты и числа на настоящих главах
python tests/make_selftest.py               # самотест шаблона (вымышленный контент)
python engine/build_course.py --nodes data_selftest/nodes --out out/selftest --strict
python engine/check_passport.py templates/video_passport.template.json
```

## Договорённости

- Единица главы: `p095.03`, третья единица на стр. 95.
- Описания рисунков в md написаны нейросетью. Они помечены `figure_ai`, цитировать их как автора нельзя.
- Наши поля сверх схемы: `node.units`, `node.title_novice`, `node.glossary`, `node.video_scores`, `layers.*.paras`, `worked_examples[].number`, `layer.uncovered`.
- `error` в проверке — факт, `suspect` — подозрение на искажение смысла, решает смысловая проверка.
- Ручная правка на тесте — строка в журнале и коммит: `python run.py log <глава> <файл> <минуты> <людей> <прогон> "<что>" "<почему>"` (официальный формат `manual_edits.csv`).
- После заморозки (тег) код, промпты и доменный пакет не меняются.
- Главы и ролики не публиковать, никаких общих ссылок.

## Осталось свести

- Дубли `domains/geology/` и `domain_pack/`: заблуждения и чек-лист физики есть в обоих, id разные (`misc.*` и `m01`). Слой ссылается на официальные `misc.*`.
- `manual_edits_log.csv` — старый формат журнала, официальный `manual_edits.csv`.
- Паспорт ролика: шаблон в `templates/` сверить с официальной `passport.schema.json`.