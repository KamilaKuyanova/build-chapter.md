#!/usr/bin/env python3
"""Часть Б одной командой: учебный слой главы (data/<глава>/layer.json от части А) -> весь демо-курс.

  python run_b.py <глава|all> [--videos] [--no-anim] [--strict]

Шаги: задания (из слоя, без API) -> перерисованные рисунки книги (если есть data/<глава>/figures) -> анимации видеоузлов
без ролика -> [ролики главы из videos/*/video.json, с --videos] -> иллюстрации -> отчёт о покрытии шаблонами ->
курс out/<глава>/index.html (+ проверка схем организаторов и правил ТЗ) -> строка в metrics.csv.
Пересборка после правки факта в слое: та же команда; с --videos пересобираются и ролики главы."""
import argparse
import csv
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
PY = sys.executable


def step(name, args, optional=False):
    t = time.time()
    r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dt = time.time() - t
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    print(f"  {'OK ' if r.returncode in (0, 2) else 'ERR'} {name:<22} {dt:6.1f} с  {tail[:110]}")
    if r.returncode not in (0, 2) and optional and "ModuleNotFoundError" in r.stderr:
        print("      пропущено: нет пакета (pip install -r requirements.txt)")
        return r
    if r.returncode not in (0, 2):
        print(r.stderr[-1500:])
        raise SystemExit(f"шаг «{name}» упал")
    return r


def metrics_row(chapter, stage, nodes, video_seconds):
    p = ROOT / "metrics.csv"
    rows = list(csv.reader(open(p, encoding="utf-8"))) if p.exists() else []
    head = rows[0] if rows else ["chapter", "stage", "nodes", "llm_tokens_in", "llm_tokens_out", "money_usd", "person_minutes",
                                 "mentor_minutes", "video_seconds", "manual_share"]
    body = [r for r in rows[1:] if r and not (r[0] == chapter and r[1] == stage)]
    # человеко-минуты и доля ручного труда заполняются по журналу manual_edits.csv; модель в части Б не вызывается
    minutes = sum(float(r.get("person_minutes") or 0) for r in csv.DictReader(open(ROOT / "manual_edits.csv", encoding="utf-8"))
                  if r.get("chapter") == chapter) if (ROOT / "manual_edits.csv").exists() else 0
    body.append([chapter, stage, str(nodes), "0", "0", "0", f"{minutes:g}", "", f"{video_seconds:.0f}", ""])
    with open(p, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows([head] + body)


def routes_with_videos(d, vids):
    """Маршрутизация части А + сделанные ролики: формат и шаблон узла совпадают с тем, что реально есть в курсе."""
    p = d / "routing.json"
    if not p.exists():
        return
    r = json.loads(p.read_text(encoding="utf-8-sig"))
    by = {x["node_id"]: x for x in r.get("routes", [])}
    changed = False
    for v in vids:
        pp = ROOT / "videos" / v["video_id"] / "passport.json"
        x = by.get(v["node_id"])
        tpl = v.get('template') or v.get('scene')
        if not x or not pp.exists():
            continue
        fmt = "шортс" if json.loads(pp.read_text(encoding="utf-8")).get("format") == "short" else "длинное видео"
        note = f"сделан ролик {v['video_id']} ({fmt}, шаблон {tpl})"
        if fmt in (x["format"], x.get("secondary_format")) and x.get("template") == tpl and note in x["why"]:
            continue
        if x["format"] in ("шортс", "длинное видео"):
            x["format"] = fmt          # ролик заменяет запланированный ролик другого формата
        else:
            x["secondary_format"] = fmt  # основной формат (практикум, интерактив) остаётся, ролик — вторым
        x["template"] = tpl
        x["why"] = x["why"].split("; сделан ролик")[0] + "; " + note
        changed = True
    if changed:
        p.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


def chapter(ch, a):
    d = ROOT / "data" / ch
    if not (d / "layer.json").exists():
        raise SystemExit(f"нет слоя {d / 'layer.json'} — сначала часть А: python run.py course {ch}")
    print(f"== {ch}")
    t0 = time.time()
    if (d / "answers" / "tasks_answer.json").exists():   # задания по ответу модели с проверкой ключей; офлайн-генератор их не затирает
        step("задания", ["run.py", "tasks-build", ch])
    else:
        step("задания (запасной путь)", ["engine/gen_tasks_offline.py", "--dir", str(d)])
    if (d / "figures").exists():
        step("рисунки книги", ["engine/figures/redraw.py", "--dir", str(d)], optional=True)
    vids = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "videos").glob("*/video.json")]
    media = d / "media_extra.json"
    used = {pathlib.Path(x["file"]).stem for r in json.loads(media.read_text(encoding="utf-8")).values() for x in r} if media.exists() else set()
    vids = [v for v in vids if v["chapter"] == ch and (not used or v["video_id"] in used)]   # только ролики, стоящие в курсе
    if a.videos:
        for v in vids:
            step(f"ролик {v['video_id']}", ["engine/video/make_video.py", f"videos/{v['video_id']}"])
    routes_with_videos(d, vids)
    if not a.no_anim:
        step("анимации", ["engine/video/make_animations.py", "--dir", str(d)], optional=True)
    extra = []
    for f in ("media_extra.json", "figures_extra.json", "anim_extra.json"):
        if (d / f).exists():
            extra += ["--extra", str(d / f)]
    step("иллюстрации", ["engine/gen_illustrations.py", "--dir", str(d)] + extra)
    step("покрытие шаблонами", ["engine/video/template_coverage.py", "--dir", str(d)], optional=True)
    title = []
    if (ROOT / "chapters.json").exists():   # заголовок курса — из описания главы части А
        spec = [c for c in json.loads((ROOT / "chapters.json").read_text(encoding="utf-8"))["chapters"] if c["id"] == ch]
        if spec and spec[0].get("title"):
            title = ["--title", spec[0]["title"]]
    r = step("курс", ["engine/build_course.py", "--dir", str(d), "--out", str(ROOT / "out" / ch)] + title +
             (["--strict"] if a.strict else []))
    problems = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("!") and "needs_scan" not in ln]
    scans = sum(1 for ln in r.stdout.splitlines() if "needs_scan" in ln)
    nodes = len(json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))["nodes"])
    vsec = sum(json.loads((ROOT / "videos" / v["video_id"] / "passport.json").read_text(encoding="utf-8")).get("duration_sec", 0)
               for v in vids if (ROOT / "videos" / v["video_id"] / "passport.json").exists())
    metrics_row(ch, "course", nodes, vsec)
    print(f"  итог: {time.time() - t0:.0f} с; нарушений правил ТЗ: {len(problems)}; мест для сверки со сканами: {scans}; "
          f"курс: out/{ch}/index.html")
    for p in problems[:10]:
        print("   " + p.strip())
    return len(problems)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter", help="имя главы (папка data/<глава>) или all")
    ap.add_argument("--videos", action="store_true", help="пересобрать и ролики этой главы")
    ap.add_argument("--no-anim", action="store_true", help="без анимаций (быстрее)")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    chs = [p.parent.name for p in sorted((ROOT / "data").glob("*/layer.json"))] if a.chapter == "all" else [a.chapter]
    bad = sum(chapter(c, a) for c in chs)
    step("метрики стоимости", ["engine/metrics_report.py"])
    sys.exit(2 if (a.strict and bad) else 0)


if __name__ == "__main__":
    main()
