# Доменный пакет: drilling

Создан 2026-11-25T16:41 командой `python engine/domain_build.py --new drilling`.

Что сделать для нового домена (время записывается в `pack_build_log.csv`, человеко-минуты — в колонку person_minutes):
1. `misconceptions.json` и `physics_checklist.json` — оставить применимые к домену, добавить свои (`misc.*`, `pc.*`).
2. `pronunciation.md`, `stress_dictionary.md` — добавить аббревиатуры и термины домена.
3. `templates/<шаблон>.json` — параметры-образцы шаблонов сцен для домена (без них берутся образцы геологии).
4. Собрать глоссарий, ИТ-мосты и листы опечаток из слоя главы: `DOMAIN=drilling python engine/domain_build.py --domain drilling --chapters data/<глава>`.
