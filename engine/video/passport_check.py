#!/usr/bin/env python3
"""Проверка паспорта ролика: официальная passport.schema + правила ТЗ (до рендера).
Запуск: python engine/video/passport_check.py passport.json --format short|long [--layer data/current/layer.json]
Коды выхода: 0 — нарушений нет, 2 — есть."""
import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine"))
import speech  # noqa: E402
import validate_layer  # noqa: E402

HOOK = re.compile(r"\?|^(почему|зачем|как|что если|а если|представьте)", re.I)


def check(p, fmt, layer=None):
    errs = validate_layer.schema_errors(p, "passport.schema.json", "паспорт")
    sc = p.get("script", [])
    if not sc:
        return errs + ["паспорт: пустой сценарий"]
    dur = sc[-1]["t_end"]
    if fmt == "short" and not 40 <= dur <= 90:
        errs.append(f"шортс {dur:.0f} с: норма 40–75, максимум 90")
    elif fmt == "short" and dur > 75:
        errs.append(f"шортс {dur:.0f} с: больше 75 с (допустимо до 90, но выше нормы)")
    if fmt == "long" and not 90 <= dur <= 180:
        errs.append(f"разбор {dur:.0f} с: нужно 1,5–3 минуты (90–180 с)")
    # крючок в первые 3 с (О)
    if sc[0]["t_start"] > 0.5 or not HOOK.search(sc[0]["text"].strip()):
        errs.append("(О) крючок: сценарий должен начинаться в первые 0,5 с с вопроса/парадокса, а не с определения")
    claims = {s["claim_id"] for s in p.get("sources", [])}
    layer_claims = {c["id"] for n in (layer or {}).get("nodes", []) for c in n.get("claims", [])}
    prev_end = 0
    for i, ph in enumerate(sc, 1):
        w = speech.words(ph["text"])
        if w > 18:
            errs.append(f"(О) фраза {i}: {w} слов (максимум 15–18)")
        if ph["t_end"] <= ph["t_start"] or ph["t_start"] < prev_end - 0.01:
            errs.append(f"фраза {i}: времена пересекаются или идут назад")
        prev_end = ph["t_end"]
        if not ph.get("is_analogy") and not ph.get("claim_id"):
            errs.append(f"(О) фраза {i}: нет claim_id (голос не говорит больше источника)")
        if ph.get("claim_id"):
            if ph["claim_id"] not in claims:
                errs.append(f"фраза {i}: claim {ph['claim_id']} нет в таблице источников")
            if layer and ph["claim_id"] not in layer_claims:
                errs.append(f"фраза {i}: claim {ph['claim_id']} не найден в слое")
    for s in p.get("sources", []):
        if not s.get("page_or_dataset") or s["page_or_dataset"].upper() in ("TBD", "?"):
            errs.append(f"источник {s['claim_id']}: не указана страница или датасет")
    errs += [f"(О) {m}" for m in speech.first_mention_issues(sc)]
    rate = speech.wpm(sc)
    if not 110 <= rate <= 150:
        errs.append(f"темп {rate:.0f} слов/мин по слотам: нужно 110–150")
    a = p.get("audio_check", {})
    for key, (lo, hi, label) in {"lufs": (-17, -15, "громкость −16 LUFS"), "asr_wer": (0, 0.10, "ошибок распознавания ≤10%"),
                                 "sync_max_s": (0, 0.5, "рассинхрон ≤0,5 с")}.items():
        v = a.get(key)
        if v is None:
            errs.append(f"audio_check.{key}: не заполнено ({label})")
        elif not lo <= v <= hi:
            errs.append(f"audio_check.{key}={v}: нужно {label}")
    if not a.get("fallback_voice"):
        errs.append("audio_check: нет запасного голоса (fallback_voice)")
    fr = p.get("frames", [])
    if not fr:
        errs.append("нет кадров")
    for f in fr:
        if f["class"] in ("A", "B") and f["label"] not in ("реальные данные", "симуляция", "схема"):
            errs.append(f"кадр t={f['t']}: метка происхождения обязательна")
    if not p.get("exaggerations"):
        errs.append("(О) exaggerations пуст: назовите, что преувеличено и во сколько (или «нет преувеличений» явной записью)")
    for ex in p.get("exaggerations", []):
        if not re.search(r"\d|раз|×|нет преувеличений", ex, re.I):
            errs.append(f"преувеличение «{ex}»: назовите число (во сколько раз)")
    for k in ("prediction_question", "transfer_question", "data_it_bridge"):
        if not p.get(k, "").strip():
            errs.append(f"(О) {k}: не заполнено")
    # чек-лист физики: все pc.* отвечены, «нет» — только с оговоркой
    pcs = [c["id"] for c in validate_layer.load_json(ROOT / "domain_pack" / "physics_checklist.json")]
    got = {x["item"]: x for x in p.get("physics_checklist", [])}
    for cid in pcs:
        if cid not in got:
            errs.append(f"физика: не отвечен пункт {cid}")
    for k, x in got.items():
        if k not in pcs:
            errs.append(f"физика: неизвестный пункт {k}")
        elif x["answer"] == "нет" and not x.get("note"):
            errs.append(f"КРИТИЧНО/значимо: {k} = «нет» без оговорки в ролике")
    return errs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("passport")
    ap.add_argument("--format", choices=["short", "long"], required=True)
    ap.add_argument("--layer")
    a = ap.parse_args()
    pp = validate_layer.load_json(a.passport)
    ly = validate_layer.load_json(a.layer) if a.layer else None
    errs = check(pp, a.format, ly)
    print(f"Паспорт {a.passport} ({a.format})")
    for e in errs:
        print("  ! " + e)
    print("OK" if not errs else f"Нарушений: {len(errs)}")
    sys.exit(0 if not errs else 2)
