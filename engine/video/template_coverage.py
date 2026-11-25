#!/usr/bin/env python3
"""Отчёт о покрытии шаблонами сцен (ТЗ, часть 5): по каждому видеоёмкому узлу главы — какой шаблон с какой моделью
состояния его закрывает, или «нужен новый». Видеоёмкий узел: формат «шортс»/«длинное видео» в маршрутизации или
сумма критериев видеоёмкости ≥ 6 с хотя бы одним критерием 2 (как в engine/route.py).
Выход: data/<глава>/template_coverage.json и .md. Запуск: python engine/video/template_coverage.py --dir data/latyshova"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine"))
import templates  # noqa: E402

try:
    from route import TEMPLATE, VIDEO_MIN
except ImportError:  # маршрутизатор части А недоступен — те же правила
    TEMPLATE = {"М": "process_state", "В": "time_evolution", "И": "tool_and_curve", "Ф": "formula_explorer",
                "П": "section_views", "Пр": "step_procedure", "Н": "decision_panel", "Р": "compare_signs"}
    VIDEO_MIN = 6

# что шаблону нужно от узла, чтобы ролик собрался без ручной доводки (проверяется по слою)
NEEDS = {
    "process_state": ("стадии процесса и величины, которые меняются", lambda n: len(n["claims"]) >= 2),
    "time_evolution": ("последовательность событий во времени", lambda n: len(n["claims"]) >= 2),
    "tool_and_curve": ("отклики прибора на породы/флюиды", lambda n: any(k in json.dumps(n, ensure_ascii=False).lower()
                                                                          for k in ("сопротивлен", "кривая", "диаграмм", "прибор", "гк", "пс"))),
    "formula_explorer": ("формула главы с параметром", lambda n: bool(n.get("formulas")) or "формул" in json.dumps(n, ensure_ascii=False)),
    "section_views": ("форма и размеры тела", lambda n: True),
    "step_procedure": ("шаги процедуры по порядку", lambda n: bool(n.get("worked_examples")) or len(n["claims"]) >= 3),
    "decision_panel": ("правило с порогами и случаи", lambda n: bool(n.get("decision_on_data"))),
    "compare_signs": ("признаки и варианты", lambda n: bool(n.get("decision_on_data")) or len(n["claims"]) >= 3),
}


def videos_by_node():
    out = {}
    for p in (ROOT / "videos").glob("*/video.json"):
        v = json.loads(p.read_text(encoding="utf-8"))
        out[v["node_id"]] = {"video_id": v["video_id"], "template": v.get("template"), "format": v["format"]}
    return out


def build(d):
    d = pathlib.Path(d)
    layer = json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))
    routes = {r["node_id"]: r for r in json.loads((d / "routing.json").read_text(encoding="utf-8-sig"))["routes"]}
    made = videos_by_node()
    anim_p = d / "anim_extra.json"
    anims = set(json.loads(anim_p.read_text(encoding="utf-8"))) if anim_p.exists() else set()
    rows = []
    for n in sorted(layer["nodes"], key=lambda x: x["order"]):
        r = routes.get(n["id"], {})
        sc = r.get("video_scores") or n.get("video_scores") or {}
        video_worthy = r.get("format") in ("шортс", "длинное видео") or (sum(sc.values()) >= VIDEO_MIN and max(sc.values() or [0]) == 2)
        if not video_worthy and n["id"] not in made:
            continue
        typ = n["difficulty"]["primary"]
        name = (made.get(n["id"]) or {}).get("template") or r.get("template") or TEMPLATE.get(typ)
        row = {"node_id": n["id"], "title": n.get("title_novice") or n["title"], "type": typ,
               "secondary": n["difficulty"].get("secondary"), "format": r.get("format"), "video_scores": sum(sc.values())}
        if name in templates.NAMES:
            m = templates.load(name)
            need, ok = NEEDS[name]
            row.update(template=name, state_model=m.STATE, needs=need,
                       status="закрывает" if ok(n) else "закрывает, но нужно дописать параметры по главе",
                       video=made.get(n["id"]))
        else:
            row.update(template=None, state_model=None, needs=None, status="нужен новый шаблон", video=made.get(n["id"]))
        row["animation_in_course"] = n["id"] in anims   # ТЗ: видеоузел без ролика закрывается в курсе анимацией
        rows.append(row)
    return {"chapter": layer["chapter"], "templates": templates.registry(), "rows": rows,
            "summary": {"video_nodes": len(rows), "covered": sum(1 for r in rows if r["template"]),
                        "need_new": sum(1 for r in rows if not r["template"]),
                        "videos_made": sum(1 for r in rows if r["video"]),
                        "animations_in_course": sum(1 for r in rows if r.get("animation_in_course")),
                        "uncovered_in_course": sum(1 for r in rows if not r["video"] and not r.get("animation_in_course"))}}


def to_md(rep):
    s = rep["summary"]
    lines = [f"# Покрытие шаблонами сцен: {rep['chapter']}", "",
             f"Видеоёмких узлов: {s['video_nodes']}; закрыто шаблонами: {s['covered']}; нужен новый: {s['need_new']}; "
             f"роликов собрано: {s['videos_made']}; закрыто в курсе анимацией: {s['animations_in_course']}; "
             f"не закрыто ничем: {s['uncovered_in_course']}.", "",
             "| Узел | Тип | Формат | Шаблон | Модель состояния | Статус | Ролик / анимация |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rep["rows"]:
        v = r["video"]["video_id"] if r["video"] else ("анимация в курсе" if r.get("animation_in_course") else "—")
        lines.append(f"| {r['title']} (`{r['node_id']}`) | {r['type']}{'/' + r['secondary'] if r['secondary'] else ''} | "
                     f"{r['format'] or '—'} | {r['template'] or '—'} | {r['state_model'] or '—'} | {r['status']} | {v} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    rep = build(a.dir)
    d = pathlib.Path(a.dir)
    (d / "template_coverage.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "template_coverage.md").write_text(to_md(rep), encoding="utf-8")
    s = rep["summary"]
    print(f"{rep['chapter']}: видеоёмких {s['video_nodes']}, закрыто шаблонами {s['covered']}, нужен новый {s['need_new']}, "
          f"роликов {s['videos_made']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
