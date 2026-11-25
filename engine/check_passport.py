#!/usr/bin/env python3
"""Проверка паспорта ролика по правилам ТЗ (до рендера). Использование: python engine/check_passport.py passport.json [--strict-physics]

Выдаёт список нарушений: (О)-обязательные и обычные. Код выхода 0 только если обязательных нарушений нет.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ORIGIN = {"реальные данные", "симуляция", "схема"}
errors, notes = [], []


def err(m):
    errors.append(m)


def note(m):
    notes.append(m)


def words(s):
    return len(s.split())


def main(path, strict_physics=False):
    p = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    fmt, dur = p.get("format"), p.get("duration_sec", 0)
    # (О) два формата
    if fmt == "short_9x16":
        if not 40 <= dur <= 75:
            (note if dur <= 90 and dur > 75 else err)(f"шортс {dur} с: норма 40–75, максимум 90")
    elif fmt == "explainer_16x9":
        if not 90 <= dur <= 180:
            err(f"разбор {dur} с: норма 1,5–3 минуты (90–180 с)")
    else:
        err("format: только short_9x16 или explainer_16x9 (ровно два формата)")

    frames = {f["id"]: f for f in p.get("frames", [])}
    if not frames:
        err("нет кадров")
    for f in frames.values():
        if f.get("class") not in ("A", "B", "C", "D"):
            err(f"кадр {f['id']}: нет класса A–D")
        if f.get("origin_label") not in ORIGIN:
            err(f"(О) кадр {f['id']}: метка происхождения должна быть из {sorted(ORIGIN)}")
        if f.get("class") in ("A", "B") and f.get("generated"):
            err(f"кадр {f['id']}: класс {f['class']} нельзя генерировать (только расчёт/данные)")
        if f.get("class") == "C" and f.get("generated") and f.get("synthetic_core_or_thin_section"):
            err(f"кадр {f['id']}: синтетические керн и шлифы запрещены")
    if not any(f.get("scale_true") for f in frames.values()):
        err("нет кадра в истинном масштабе (без вертикального преувеличения)")

    # крючок в первые 3 с (О)
    first = [f for f in frames.values() if f.get("t_start", 1) == 0]
    if not first or not any("крючок" in (f.get("note", "").lower()) for f in first):
        err("(О) крючок в первые 3 секунды: у кадра с t_start=0 в note должно быть слово «крючок»")

    # озвучка
    claims = {s.get("claim_id") for s in p.get("sources", [])}
    script = p.get("script", [])
    total_words = 0
    for i, ph in enumerate(script):
        w = words(ph.get("text", ""))
        total_words += w
        if w > 18:
            err(f"(О) фраза {i + 1}: {w} слов (максимум 15–18)")
        if ph.get("kind") != "analogy" and not ph.get("claim_id"):
            err(f"(О) фраза {i + 1}: нет claim_id (голос не говорит больше источника)")
        if ph.get("claim_id") and ph["claim_id"] not in claims:
            err(f"фраза {i + 1}: claim {ph['claim_id']} нет в таблице источников")
        if ph.get("frame") not in frames:
            err(f"фраза {i + 1}: нет такого кадра {ph.get('frame')}")
        if any(c.isdigit() for c in ph.get("text", "")):
            err(f"фраза {i + 1}: числа в сценарии для озвучки пишутся словами")
    for s in p.get("sources", []):
        if s.get("page") is None and not s.get("dataset"):
            err(f"источник {s.get('claim_id')}: нужна страница или датасет")
    a = p.get("audio", {})
    if not 110 <= a.get("wpm", 0) <= 150:
        err(f"темп {a.get('wpm')} слов/мин: нужно 110–150")
    if abs(a.get("lufs", 0) - (-16)) > 1:
        err(f"громкость {a.get('lufs')} LUFS: нужно около −16")
    if a.get("sync_max_offset_sec", 9) > 0.5:
        err(f"(О) рассинхрон {a.get('sync_max_offset_sec')} с > 0,5 с")
    if a.get("asr_word_error_rate", 1) > 0.10:
        err(f"распознавание дорожки: ошибок {a.get('asr_word_error_rate'):.0%} > 10%")
    if not a.get("fallback_voice"):
        err("нет запасного голоса")
    if not p.get("subtitles"):
        err("(О) нужны субтитры")

    # честность
    ex = [x for x in p.get("exaggerations", []) if x.get("what")]
    if not ex:
        err("(О) список преувеличений пуст: назовите, что преувеличено и во сколько (или явно укажите, что преувеличений нет)")
    for x in ex:
        if not x.get("factor") or not x.get("label_on_screen"):
            err(f"преувеличение «{x.get('what')}»: нужны число и подпись на экране")
    q = p.get("questions", {})
    if not q.get("prediction") or not q.get("transfer"):
        err("(О) нужны вопрос-предсказание и вопрос на перенос")
    if q.get("pause_before_answer_sec", 0) < 1.0:
        err("пауза перед ответом на предсказание ≥1–1,5 с")
    if not p.get("data_bridge"):
        err("нет моста «где здесь данные и ИТ»")
    if not p.get("scene_spec", {}).get("invariants"):
        err("спецификация сцены без инвариантов")
    if not p.get("reproducible_from_spec"):
        err("ролик должен пересобираться из спецификации")

    # физика
    ck = json.loads((ROOT / "domain_pack" / "physics_checklist.json").read_text(encoding="utf-8"))
    review = p.get("physics_review", {})
    need = [f"{g['id']}:{i}" for g in ck["groups"] for i in range(1, len(g["checks"]) + 1)]
    missing = [k for k in need if k not in review]
    if missing:
        (err if strict_physics else note)(f"физика: не отмечено {len(missing)} из {len(need)} пунктов чек-листа")
    for k, v in review.items():
        if k.startswith("_"):
            continue
        if k not in need:
            err(f"физика: неизвестный пункт {k}")
        elif v.get("answer") == "no" and not v.get("caveat"):
            err(f"КРИТИЧНО/значимо: пункт {k} = «нет» без оговорки в ролике")
    mr = json.loads((ROOT / "domain_pack" / "misconceptions.json").read_text(encoding="utf-8"))["items"]
    ids = {m["id"] for m in mr}
    for m in p.get("misconceptions_reinforced", []):
        err(f"КРИТИЧЕСКАЯ ОШИБКА: закреплено заблуждение {m} (ролик получает 0)")
        if m not in ids:
            err(f"неизвестный id заблуждения {m}")
    nt = p.get("novice_test", {})
    if nt.get("people", 0) == 0:
        note("не проверено на новичках (желательно до финала)")

    print(f"Паспорт: {path}")
    for n in notes:
        print("  · " + n)
    for e_ in errors:
        print("  ! " + e_)
    print(f"Итого нарушений: {len(errors)}")
    return 0 if not errors else 2


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(sys.argv[1], "--strict-physics" in sys.argv))
