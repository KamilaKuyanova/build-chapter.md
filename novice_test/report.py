#!/usr/bin/env python3
"""Отчёт проверки на новичках: novice_test/results/*.json (выгрузка из курса) + novice_test/videos.csv -> novice_test/report.md.
Решаемость считается по первой попытке (ТЗ: «новички решают ≥ 80 % задач по курсу»)."""
import csv
import collections
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def main():
    files = sorted((HERE / "results").glob("*.json")) if (HERE / "results").exists() else []
    by_course = collections.defaultdict(lambda: {"testers": set(), "n": 0, "ok": 0, "types": collections.Counter(),
                                                 "types_ok": collections.Counter(), "tasks": collections.defaultdict(list)})
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        c = by_course[d["course"]]
        c["testers"].add(d.get("tester", f.stem))
        for tid, a in d.get("answers", {}).items():
            c["n"] += 1
            c["ok"] += 1 if a.get("first") else 0
            c["types"][a.get("type")] += 1
            c["types_ok"][a.get("type")] += 1 if a.get("first") else 0
            c["tasks"][tid].append(bool(a.get("first")))
    lines = ["# Проверка на новичках", ""]
    if not files:
        lines.append("Пока нет файлов в `novice_test/results/`.")
    for course, c in by_course.items():
        share = 100 * c["ok"] / c["n"] if c["n"] else 0
        lines += [f"## {course}", "", f"Тестирующих: {len(c['testers'])}; заданий решено: {c['n']}; с первой попытки: "
                  f"**{share:.0f} %** (цель ТЗ ≥ 80 %) — {'достигнуто' if share >= 80 else 'НЕ достигнуто'}.", "",
                  "| Тип | Решено с первой попытки |", "| --- | --- |"]
        lines += [f"| {t} | {100 * c['types_ok'][t] / n:.0f} % из {n} |" for t, n in c["types"].most_common()]
        hard = [(tid, r) for tid, r in c["tasks"].items() if len(r) >= 1 and sum(r) / len(r) < 0.5]
        lines += ["", f"Трудные задания (ошибалось больше половины): {len(hard)}", ""]
        lines += [f"- `{tid}`: {sum(r)} из {len(r)}" for tid, r in sorted(hard)]
        lines.append("")
    vp = HERE / "videos.csv"
    rows = list(csv.DictReader(open(vp, encoding="utf-8"))) if vp.exists() else []
    if rows:
        lines += ["## Ролики", "", "| Ролик | Зрителей | Предсказание | Перенос | Понятность (1–5) |", "| --- | --- | --- | --- | --- |"]
        for v in sorted({r["video"] for r in rows}):
            rs = [r for r in rows if r["video"] == v]
            avg = lambda k: sum(float(r[k] or 0) for r in rs) / len(rs)  # noqa: E731
            lines.append(f"| {v} | {len(rs)} | {100 * avg('prediction_correct'):.0f} % | {100 * avg('transfer_correct'):.0f} % | "
                         f"{avg('understood_1to5'):.1f} |")
        lines += ["", "Что было непонятно:"] + [f"- {r['video']}: {r['confusing']}" for r in rows if r.get("confusing")]
    (HERE / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
