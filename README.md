# Глава → курс (хакатон), часть Б: курс, задания, ролики, доменный пакет

Форматы — ОФИЦИАЛЬНЫЕ (пакет вводных организаторов), копия схем в `schema/official/`. Требования ТЗ: `TZ-checklist.md`.
Модель: только Claude API (`engine/llm_client.py`), ключ в `ANTHROPIC_API_KEY`, не в репозитории.

## Установка
```
pip install -r requirements.txt
```

## Входы курса (`data/current/`)
`layer.json` (учебный слой, делает часть А), `tasks.json`, `illustrations.json`, `routing.json` (необязательно).

## Команды
```
python engine/validate_layer.py --dir data/current           # схемы организаторов + правила ТЗ
python engine/gen_exercises.py --dir data/current            # tasks.json через Claude (нужен ключ)
python engine/build_course.py --dir data/current --strict    # out/course/index.html (офлайн)
python tests/test_offline.py                                 # проверки без ключа API
python engine/llm_client.py --ping                           # проверка связи с Claude
```

## Папки
- `engine/` — сборщик курса, валидатор, генератор заданий, клиент Claude (движок не знает геологии)
- `domain_pack/` — доменный пакет отдельно от кода: заблуждения `misc.*`, чек-лист `pc.*`, стайлгайд, ударения, портреты, глоссарий
- `data/book_index/` — индексы анализов книг (не сверено со страницами)
- `data_selftest/` — самотест шаблона (вымышленный контент, в сдачу не входит)
- `manual_edits.csv`, `metrics.csv`, `MANIFEST.md` — шаблоны сдачи

## Правила
1. Ручная правка = строка в `manual_edits.csv` (person_minutes, run_no) + коммит.
2. После заморозки (тег) код, промпты и доменный пакет не меняются.
3. Книги, сканы, видео и папка «хакатон» в git не попадают (`.gitignore`).
