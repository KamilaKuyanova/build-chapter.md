"""Конвейер «глава → курс». Нужен только Python 3.10+, сторонних библиотек нет.

  python run.py add <глава> <файл.md> [ru|en] [домен]   новая глава из готового md-фрагмента
  python run.py status <глава>                    что сделано и какой шаг следующий
  python run.py units [глава|train|control|all]   нарезать на единицы  -> work/<глава>/units.json
  python run.py check <глава>                     проверить work/<глава>/layer.json, таблица покрытия
  python run.py next <глава>                      следующая порция -> prompts/NN.md, ответ модели -> answers/NN.json
  python run.py build <глава>                     ответы -> layer.json, routing.json, проверка
  python run.py tasks <глава>                     промпт заданий -> work/<глава>/tasks_prompt.md
  python run.py tasks-build <глава>               work/<глава>/tasks_answer.json -> data/<глава>/tasks.json, проверка ключей
  python run.py domain <глава>                    промпт доменного пакета -> work/<глава>/domain_prompt.md
  python run.py domain-build <глава>              work/<глава>/domain_answer.json -> domains/<домен>/
  python run.py rebuild <глава>                   слой, задания и курс заново одной командой
  python run.py course <глава>                    слой -> data/<глава>/, курс -> out/<глава>/index.html
  python run.py review <package.json>             промпты проверки чужого пакета -> work/review_<пакет>/
  python run.py review-build <package.json>       ответы -> work/review_<пакет>/review.json
  python run.py log <глава> <файл> <минуты> <людей> <прогон> "<что>" "<почему>"   ручная правка
"""
import csv
import datetime
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

from engine import nodes as nodes_mod, review as review_mod, route as route_mod, tasks as tasks_mod
from engine import domain as domain_mod
from engine.check import check_layer
from engine.schema import validate
from engine.units import build_units, needs_cover

ROOT = Path(__file__).resolve().parent
JOURNAL = ROOT / "manual_edits.csv"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def schemas():
    return {p.name.split(".")[0]: load(p) for p in (ROOT / "schema").rglob("*.schema.json")}


def domain_dir(domain):
    """geology — domain_pack/, для другого домена отдельная папка domains/<домен>/."""
    return ROOT / "domain_pack" if domain == "geology" else ROOT / "domains" / domain


def misconceptions(domain):
    return {x["id"] for x in misc_list(domain)}


def chapter_specs(which):
    cfg = load(ROOT / "chapters.json")
    specs = [c for c in cfg["chapters"] if which in ("all", c["id"], c["set"])]
    if not specs:
        sys.exit(f"Нет главы «{which}». Есть: " + ", ".join(c["id"] for c in cfg["chapters"]))
    return ROOT / cfg["books_dir"], specs


def cmd_units(which="all"):
    books, specs = chapter_specs(which)
    for spec in specs:
        path = books / spec["book"]
        if not path.exists():
            sys.exit(f"Нет файла {path}. Положите папку «books md» в input/ (см. README).")
        units = build_units(path.read_text(encoding="utf-8-sig"), spec)
        save(ROOT / "work" / spec["id"] / "units.json", units)
        kinds = Counter(u["type"] for u in units)
        bad = [u["id"] for u in units if u.get("ocr_suspect")]
        print(f"{spec['id']}: стр. {units[0]['page']}-{units[-1]['page']}, единиц {len(units)}, "
              f"к покрытию {sum(map(needs_cover, units))}")
        print("   " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
        leak = [u["id"] for u in units if u["origin"] == "author"
                and any(mark in u["text"] for mark in ("━━━", "KEYWORDS:", "[нрзб"))]
        if leak:
            print("   ВНИМАНИЕ, описание рисунка попало в текст автора: " + ", ".join(leak))
        if bad:
            print("   распознано с ошибками, сверить со сканом: " + ", ".join(bad))


def cmd_check(chapter):
    work = ROOT / "work" / chapter
    for name in ("units.json", "layer.json"):
        if not (work / name).exists():
            sys.exit(f"Нет {work / name}")
    _, (spec,) = chapter_specs(chapter)
    report, cov = check_layer(load(work / "units.json"), load(work / "layer.json"), schemas(),
                              misconceptions(spec.get("domain", "geology")))
    save(work / "check.json", report)
    levels = Counter(r["level"] for r in report)
    for r in report:
        page = f" стр. {r['page']}" if r["page"] else ""
        fix = f" -> {r['fix']}" if r["fix"] else ""
        print(f"[{r['level']}] {r['code']} {r['where']}{page}: {r['message']}{fix}")
    print(f"Итог: ошибок {levels['error']}, сомнений {levels['suspect']}", end="")
    if cov:
        save(work / "coverage.json", cov)
        done = sum(1 for r in cov["rows"] if r["node_ids"] or r["reason"])
        print(f", покрытие {done}/{len(cov['rows'])}", end="")
    print()
    return 1 if levels["error"] else 0


def misc_list(domain):
    path = domain_dir(domain) / "misconceptions.json"
    return load(path) if path.exists() else []


def answers_in(folder):
    out = []
    for path in sorted(folder.glob("*.json")):
        try:
            out.append(nodes_mod.parse_answer(path.read_text(encoding="utf-8-sig")))
        except ValueError as e:
            sys.exit(f"{path.name}: ответ не читается как JSON: {e}")
    return out


def cmd_next(chapter):
    work = ROOT / "work" / chapter
    if not (work / "units.json").exists():
        cmd_units(chapter)
    _, (spec,) = chapter_specs(chapter)
    units = load(work / "units.json")
    parts = nodes_mod.chunks(units)
    (work / "answers").mkdir(exist_ok=True)
    done = answers_in(work / "answers")
    if len(done) >= len(parts):
        print(f"Все {len(parts)} порций готовы: python run.py build {chapter}")
        return
    layer = nodes_mod.Builder(spec, units).layer(done, "")
    brief = "\n".join(f"- {m['id']}: {m['text']}" for m in misc_list(spec.get("domain", "geology")))
    n = len(done) + 1
    text = nodes_mod.prompt((ROOT / "prompts" / "nodes.md").read_text(encoding="utf-8"),
                            "Заблуждения:\n" + brief, spec, n, len(parts), parts[n - 1], layer["nodes"])
    path = work / "prompts" / f"{n:02d}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Порция {n} из {len(parts)}: {path.relative_to(ROOT)}, ответ в work/{chapter}/answers/{n:02d}.json")


def cmd_build(chapter):
    work = ROOT / "work" / chapter
    _, (spec,) = chapter_specs(chapter)
    builder = nodes_mod.Builder(spec, load(work / "units.json"))
    layer = builder.layer(answers_in(work / "answers"), "Claude, ответы в work/answers")
    save(work / "layer.json", layer)
    routing = route_mod.route(layer)
    for err in validate(routing, schemas()["routing"]):
        print("[error] ROUTING", err)
    save(work / "routing.json", routing)
    for p in builder.problems:
        print("[error] BUILD", p)
    print("Форматы: " + ", ".join(f"{k} {v}" for k, v in Counter(
        r["format"] for r in routing["routes"]).most_common()))
    return cmd_check(chapter) or bool(builder.problems)


def backup(chapter, name):
    """Ответы модели храним и в data/<глава>/answers: work/ в git не входит."""
    src, dst = ROOT / "work" / chapter / name, ROOT / "data" / chapter / "answers" / name
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8-sig"), encoding="utf-8")


def restore(chapter):
    """На чужом компьютере work/ пуста: берём ответы из data/<глава>/answers."""
    saved, work = ROOT / "data" / chapter / "answers", ROOT / "work" / chapter
    if not saved.exists():
        return
    for path in saved.glob("*.json"):
        dst = (work / path.name) if path.name.startswith(("tasks", "domain")) else (work / "answers" / path.name)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def cmd_add(chapter, file, lang="ru", domain="geology"):
    """Новая глава: файл копируется в input/new, запись — в chapters.json. Код не меняется."""
    src = Path(file).resolve()
    dst = ROOT / "input" / "new" / src.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src != dst:
        dst.write_text(src.read_text(encoding="utf-8-sig"), encoding="utf-8")
    cfg = load(ROOT / "chapters.json")
    cfg["chapters"] = [c for c in cfg["chapters"] if c["id"] != chapter]
    title = next((l.strip("# *") for l in dst.read_text(encoding="utf-8").splitlines() if l.startswith("#")), src.stem)
    cfg["chapters"].append({"id": chapter, "set": "test", "lang": lang, "domain": domain,
                            "book": f"../new/{src.name}", "title": title})
    save(ROOT / "chapters.json", cfg)
    cmd_units(chapter)


def cmd_status(chapter):
    work, data = ROOT / "work" / chapter, ROOT / "data" / chapter
    _, (spec,) = chapter_specs(chapter)
    have = lambda p: "есть" if p.exists() else "НЕТ"
    parts = len(nodes_mod.chunks(load(work / "units.json"))) if (work / "units.json").exists() else 0
    done = len(list((work / "answers").glob("*.json"))) if (work / "answers").exists() else 0
    print(f"{chapter}: {spec['title']} | язык {spec.get('lang', 'ru')}, домен {spec.get('domain', 'geology')}")
    print(f"  порций слоя: {done} из {parts}; layer.json {have(work / 'layer.json')}")
    tasks = len(load(data / "tasks.json")["tasks"]) if (data / "tasks.json").exists() else 0
    pics = len(load(data / "illustrations.json")["illustrations"]) if (data / "illustrations.json").exists() else 0
    print(f"  заданий {tasks}, иллюстраций {pics}, курс {have(ROOT / 'out' / chapter / 'index.html')}")
    step = (f"run.py units {chapter}" if not parts else f"run.py next {chapter}" if done < parts
            else f"run.py build {chapter}" if not (work / "layer.json").exists()
            else f"run.py tasks {chapter}" if not tasks else f"run.py rebuild {chapter}")
    print("  дальше: python " + step)


def cmd_domain(chapter):
    _, (spec,) = chapter_specs(chapter)
    name, work = spec.get("domain", "geology"), ROOT / "work" / chapter
    text = domain_mod.prompt((ROOT / "prompts" / "domain.md").read_text(encoding="utf-8"), name, spec["title"],
                             domain_dir(name), load(work / "units.json"))
    (work / "domain_prompt.md").write_text(text, encoding="utf-8")
    (work / "domain_started.txt").write_text(datetime.datetime.now().isoformat(timespec="minutes"), encoding="utf-8")
    print(f"work/{chapter}/domain_prompt.md, ответ в work/{chapter}/domain_answer.json. Время пошло.")


def cmd_domain_build(chapter):
    _, (spec,) = chapter_specs(chapter)
    name, work = spec.get("domain", "geology"), ROOT / "work" / chapter
    answer = nodes_mod.parse_answer((work / "domain_answer.json").read_text(encoding="utf-8-sig"))
    added, errors = domain_mod.merge(domain_dir(name), answer, {u["page"] for u in load(work / "units.json")})
    for err in errors:
        print("[error]", err)
    print(f"domains/{name}: добавлено " + (", ".join(f"{k} {v}" for k, v in added.items()) or "ничего"))
    started = work / "domain_started.txt"
    if started.exists():
        spent = datetime.datetime.now() - datetime.datetime.fromisoformat(started.read_text(encoding="utf-8").strip())
        log = ROOT / "domains" / "time_log.csv"
        new = not log.exists()
        log.parent.mkdir(exist_ok=True)
        with open(log, "a", newline="", encoding="utf-8") as f:
            out = csv.writer(f)
            if new:
                out.writerow(["time", "domain", "chapter", "minutes"])
            out.writerow([datetime.datetime.now().isoformat(timespec="minutes"), name, chapter, round(spent.total_seconds() / 60)])
        print(f"Время на пакет: {round(spent.total_seconds() / 60)} мин, записано в domains/time_log.csv")
    backup(chapter, "domain_answer.json")
    return 1 if errors else 0


def cmd_rebuild(chapter):
    if not (ROOT / "work" / chapter / "units.json").exists():
        cmd_units(chapter)
    restore(chapter)
    bad = cmd_build(chapter)
    if (ROOT / "work" / chapter / "tasks_answer.json").exists():
        bad = cmd_tasks_build(chapter) or bad
    return cmd_course(chapter) or bad


def cmd_tasks(chapter):
    work = ROOT / "work" / chapter
    text = tasks_mod.prompt((ROOT / "prompts" / "tasks.md").read_text(encoding="utf-8"), load(work / "layer.json"))
    (work / "tasks_prompt.md").write_text(text, encoding="utf-8")
    print(f"work/{chapter}/tasks_prompt.md, ответ в work/{chapter}/tasks_answer.json")


def cmd_tasks_build(chapter):
    work = ROOT / "work" / chapter
    _, (spec,) = chapter_specs(chapter)
    layer = load(work / "layer.json")
    answer = nodes_mod.parse_answer((work / "tasks_answer.json").read_text(encoding="utf-8-sig"))
    doc, problems = tasks_mod.build(layer, answer)
    found = [("error", "сборка", p) for p in problems]
    found += [("error", "схема", e) for e in validate(doc, schemas()["task"])]
    found += tasks_mod.check(layer, doc, misconceptions(spec.get("domain", "geology")))
    for level, tid, message in found:
        print(f"[{level}] {tid}: {message}")
    save(ROOT / "data" / chapter / "tasks.json", doc)
    backup(chapter, "tasks_answer.json")
    levels = Counter(x[0] for x in found)
    print(f"Заданий {len(doc['tasks'])}: " + ", ".join(f"{k} {v}" for k, v in Counter(
        t["type"] for t in doc["tasks"]).most_common())
        + f"; на шагов {len({t['step_id'] for t in doc['tasks']})}; ошибок {levels['error']}, сомнений {levels['suspect']}")
    return 1 if levels["error"] else 0


def cmd_course(chapter, *flags):
    """Слой кладём в data/<глава>/, рядом ждём tasks.json и illustrations.json от части Б."""
    work, data = ROOT / "work" / chapter, ROOT / "data" / chapter
    _, (spec,) = chapter_specs(chapter)
    for name in ("layer.json", "routing.json", "coverage.json"):
        if (work / name).exists():
            save(data / name, load(work / name))
    for path in sorted((work / "answers").glob("*.json")):
        dst = data / "answers" / path.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(path.read_text(encoding="utf-8-sig"), encoding="utf-8")
    for name, key in (("tasks.json", "tasks"), ("illustrations.json", "illustrations")):
        if not (data / name).exists():
            save(data / name, {"chapter": chapter, key: []})
    return subprocess.run([sys.executable, str(ROOT / "engine" / "build_course.py"), "--dir", str(data),
                           "--out", str(ROOT / "out" / chapter), "--title", spec["title"], *flags],
                          env={**os.environ, "COURSE_DOMAIN_DIR": domain_dir(spec.get("domain", "geology"))
                               .relative_to(ROOT).as_posix()}).returncode


def review_setup(package_path, domain):
    package_path = Path(package_path).resolve()
    package = load(package_path)
    for err in validate(package, schemas()["review_package"]):
        print("[error] PACKAGE", err)
    chapter = package_path.parent / package["chapter_file"]
    if not chapter.exists():
        chapter = ROOT / "input" / package["chapter_file"]
    spec = {"id": package["chapter"], "lang": package.get("language", "ru")}
    units = build_units(chapter.read_text(encoding="utf-8-sig"), spec)
    return package, units, ROOT / "work" / f"review_{package['package_id']}", package_path.parent


def cmd_review(package_path, domain="geology"):
    package, units, work, folder = review_setup(package_path, domain)
    checklist = load(domain_dir(domain) / "physics_checklist.json")
    template = (ROOT / "prompts" / "review.md").read_text(encoding="utf-8")
    groups = review_mod.batches(package)
    for i, items in enumerate(groups, 1):
        text = review_mod.prompt(template, package, units, items, checklist, misc_list(domain),
                                 i == len(groups), folder)
        path = work / "prompts" / f"{i:02d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (work / "answers").mkdir(exist_ok=True)
    print(f"Промптов {len(groups)} в {(work / 'prompts').relative_to(ROOT)}, ответы NN.json в answers/")


def cmd_review_build(package_path, domain="geology"):
    package, units, work, _ = review_setup(package_path, domain)
    out, dropped = review_mod.assemble(package, units, answers_in(work / "answers"), "build-chapter")
    for err in validate(out, schemas()["review_output"]):
        print("[error] OUTPUT", err)
    save(work / "review.json", out)
    for target, why in dropped:
        print(f"отброшено {target}: {why}")
    print(f"Замечаний {len(out['remarks'])}: {(work / 'review.json').relative_to(ROOT)}")

def cmd_log(chapter, file, minutes, people, run_no, what, why):
    new = not JOURNAL.exists()
    with open(JOURNAL, "a", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        if new:
            out.writerow("time,chapter,file,what_changed,person_minutes,people,run_no,reason".split(","))
        out.writerow([datetime.datetime.now().isoformat(timespec="minutes"), chapter, file, what,
                      float(minutes), int(people), int(run_no), why])
    print("Записано в manual_edits.csv")


COMMANDS = {"units": cmd_units, "next": cmd_next, "build": cmd_build, "check": cmd_check, "course": cmd_course, "add": cmd_add, "status": cmd_status, "rebuild": cmd_rebuild,
            "domain": cmd_domain, "domain-build": cmd_domain_build,
            "tasks": cmd_tasks, "tasks-build": cmd_tasks_build,
            "review": cmd_review, "review-build": cmd_review_build, "log": cmd_log}

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    try:
        sys.exit(COMMANDS[sys.argv[1]](*sys.argv[2:]))
    except (TypeError, ValueError) as e:
        sys.exit(f"Ошибка: {e}\n{__doc__}")
