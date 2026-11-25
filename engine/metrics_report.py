#!/usr/bin/env python3
"""Метрики стоимости (ТЗ: «стоимость узла и минуты видео: деньги, человеко-минуты, минуты ментора»).

Источники: data/<глава>/layer.json (узлы), videos/*/passport.json (ролики), manual_edits.csv (журнал ручных правок
`python run.py log ...`; строка с «ментор» в reason — минуты ментора), metrics.csv (токены части А, если записаны).
Деньги: модель в части Б не вызывается (0); озвучка ElevenLabs считается по символам сценария,
цена за 1000 символов — переменная ELEVENLABS_USD_PER_1K (0 на бесплатном тарифе).
Пишет строки stage=video в metrics.csv и сводку metrics.md."""
import csv
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEAD = ["chapter", "stage", "nodes", "llm_tokens_in", "llm_tokens_out", "money_usd", "person_minutes",
        "mentor_minutes", "video_seconds", "manual_share"]


def journal():
    p = ROOT / "manual_edits.csv"
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def minutes(rows, pred):
    person = sum(float(r.get("person_minutes") or 0) * max(1, int(r.get("people") or 1)) for r in rows
                 if pred(r) and "ментор" not in (r.get("reason") or "").lower())
    mentor = sum(float(r.get("person_minutes") or 0) for r in rows if pred(r) and "ментор" in (r.get("reason") or "").lower())
    return person, mentor


def main():
    usd_1k = float(os.environ.get("ELEVENLABS_USD_PER_1K", "0") or 0)
    j = journal()
    p = ROOT / "metrics.csv"
    rows = list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []
    rows = [r for r in rows if r.get("stage") != "video"]
    videos = []
    for pp in sorted((ROOT / "videos").glob("*/passport.json")):
        ps = json.loads(pp.read_text(encoding="utf-8"))
        vid = ps["video_id"]
        chars = sum(len(s["text"]) for s in ps["script"])
        eleven = str(ps["audio_check"].get("voice", "")).lower().startswith(("elevenlabs", "daniel")) or \
            "eleven" in json.dumps(ps["audio_check"], ensure_ascii=False).lower()
        money = chars / 1000 * usd_1k if eleven else 0.0
        person, mentor = minutes(j, lambda r, v=vid: v in (r.get("file") or "") or v in (r.get("what_changed") or ""))
        ch = ps["node_card"].get("chapter") or ps["node_id"].split(".")[0]
        videos.append(dict(id=vid, chapter=ch, sec=float(ps.get("duration_sec") or 0), chars=chars, money=money,
                           person=person, mentor=mentor, voice=ps["audio_check"].get("voice")))
        rows.append(dict(chapter=ch, stage="video", nodes="1", llm_tokens_in="0", llm_tokens_out="0", money_usd=f"{money:.2f}",
                         person_minutes=f"{person:g}", mentor_minutes=f"{mentor:g}", video_seconds=f"{ps.get('duration_sec', 0):.0f}",
                         manual_share=""))
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, HEAD)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["chapter"], r["stage"])))

    L = ["# Метрики стоимости", "",
         "Пересчитывается командой `python engine/metrics_report.py` (вызывается в конце `run_b.py`).",
         "Человеко-минуты и минуты ментора — из журнала `manual_edits.csv` (`python run.py log ...`; минуты ментора — строки, "
         "где в причине написано «ментор»). Деньги части Б: модель не вызывается, графика и анимации — код, 0 $.", "",
         "## Узел курса", "", "| Глава | Узлов | Деньги, $ | $ на узел | Человеко-мин | Мин на узел | Мин ментора | Заданий | Анимаций |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for d in sorted((ROOT / "data").glob("*/layer.json")):
        ch = d.parent.name
        n = len(json.loads(d.read_text(encoding="utf-8-sig"))["nodes"])
        mrow = [r for r in rows if r["chapter"] == ch and r["stage"] != "video"]
        money = sum(float(r.get("money_usd") or 0) for r in mrow)
        person, mentor = minutes(j, lambda r, c=ch: r.get("chapter") == c and "videos/" not in (r.get("file") or ""))
        tasks = d.parent / "tasks.json"
        nt = len(json.loads(tasks.read_text(encoding="utf-8")).get("tasks", [])) if tasks.exists() else 0
        anim = d.parent / "anim_extra.json"
        na = len(json.loads(anim.read_text(encoding="utf-8"))) if anim.exists() else 0
        L.append(f"| {ch} | {n} | {money:.2f} | {money / n:.3f} | {person:g} | {person / n:.2f} | {mentor:g} | {nt} | {na} |")
    L += ["", "## Минута видео", "", "| Ролик | Глава | Длительность, с | Символов озвучки | Деньги, $ | $ за минуту | "
          "Человеко-мин | Мин за минуту видео | Мин ментора | Голос |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for v in videos:
        m = v["sec"] / 60 or 1
        L.append(f"| {v['id']} | {v['chapter']} | {v['sec']:.0f} | {v['chars']} | {v['money']:.2f} | {v['money'] / m:.2f} | "
                 f"{v['person']:g} | {v['person'] / m:.1f} | {v['mentor']:g} | {v['voice']} |")
    L += ["", f"Цена ElevenLabs за 1000 символов: {usd_1k:g} $ (переменная `ELEVENLABS_USD_PER_1K`).",
          "Анимации узлов (без озвучки) — 0 $ и 0 человеко-минут: генерируются кодом из слоя.", ""]
    (ROOT / "metrics.md").write_text("\n".join(L), encoding="utf-8")
    print("metrics.md, metrics.csv: роликов", len(videos))


if __name__ == "__main__":
    main()
