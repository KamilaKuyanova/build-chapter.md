#!/usr/bin/env python3
"""Сборка доменного пакета из учебных слоёв глав (структура — по шаблону организаторов domain_pack_template.md).

Генерирует в пакете домена (DOMAIN / --domain):
  glossary.md            термины RU/EN: термин, определение из слоя, западный аналог, где введён, страница, кто написал
  it_bridges.md          ИТ-аналогии узлов и где они ломаются
  errata/<глава>.md      листы опечаток распознавания: места needs_scan со страницами (сверить со сканом)
  templates/registry.json  шаблоны сцен по типам трудности и их модели состояния (+ templates/<шаблон>.json — параметры-образцы)
  pack_build_log.csv     время сборки пакета (для отчёта по сдвигу: «сколько времени занял пакет»)
Запуск: python engine/domain_build.py --domain geology --chapters data/latyshova data/basniev data/kuznetsov
        python engine/domain_build.py --new drilling      # заготовка пакета нового домена
"""
import argparse
import csv
import datetime
import json
import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "engine" / "video"))
import domain  # noqa: E402


def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def layers(chapters):
    for d in chapters:
        p = pathlib.Path(d) / "layer.json"
        if p.exists():
            yield pathlib.Path(d).name, json.loads(p.read_text(encoding="utf-8-sig"))


def build(dom, chapters):
    t0 = time.time()
    pack = domain.pack_dir(dom)
    pack.mkdir(parents=True, exist_ok=True)
    en = {}
    gp = domain.path("glossary.json", dom)
    if gp.exists():
        for t in json.loads(gp.read_text(encoding="utf-8")).get("terms", []):
            if t.get("ru") and t.get("en"):
                en[t["ru"].lower()] = t["en"]
    model_en = set()
    ge = domain.path("glossary_en.json", dom)
    if ge.exists():   # аналоги — перевод модели, в глоссарии помечаются «(перевод модели, сверить)»
        for ru, e in json.loads(ge.read_text(encoding="utf-8"))["terms"].items():
            if ru not in en:
                en[ru] = e
                model_en.add(ru)
    terms, bridges, n_err = {}, [], 0
    (pack / "errata").mkdir(exist_ok=True)
    for ch, ly in layers(chapters):
        err_rows = []
        for n in sorted(ly["nodes"], key=lambda x: x["order"]):
            pages = ", ".join(str(p) for p in n.get("pages", [])[:3])
            for g in n.get("glossary", []):
                key = g["term"].lower()
                if key not in terms:
                    terms[key] = {"term": g["term"], "def": g.get("definition", ""), "en": en.get(key, ""),
                                  "where": f"{ch}: {n.get('title_novice') or n['title']}", "pages": pages,
                                  "by": "модель (по тексту главы)" if g.get("by_model") else "книга"}
            for t in n.get("terms_introduced", []):
                terms.setdefault(t.lower(), {"term": t, "def": "", "en": en.get(t.lower(), ""),
                                             "where": f"{ch}: {n.get('title_novice') or n['title']}", "pages": pages, "by": "—"})
            it = n.get("it_analogy") or {}
            if it.get("text"):
                bridges.append((ch, n.get("title_novice") or n["title"], it["text"], it.get("breaks_where", ""), pages))
            for s in n.get("needs_scan", []):
                err_rows.append((s.get("page"), s.get("what"), n["id"]))
        if err_rows or True:
            lines = [f"# Лист опечаток распознавания: {ch}", "",
                     "Места, где md главы мог исказить текст при распознавании. Сверить со сканом страницы; исправление — в ответах слоя, не в layer.json.", "",
                     "| Стр. PDF | Что проверить | Узел | Статус |", "| --- | --- | --- | --- |"]
            lines += [f"| {p} | {md_escape(w)} | `{nid}` | не сверено |" for p, w, nid in sorted(err_rows, key=lambda r: (r[0] or 0))]
            (pack / "errata" / f"{ch}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
            n_err += len(err_rows)
    g = ["# Глоссарий RU/EN", "", "Собран из учебных слоёв глав. Определение «модель» написано моделью по тексту главы и сверено со страницей узла.", "",
         "| Термин | Определение | Западный аналог | Где введён | Стр. PDF | Кто написал |", "| --- | --- | --- | --- | --- | --- |"]
    for t in sorted(terms.values(), key=lambda x: x["term"].lower()):
        if t["en"] and t["term"].lower() in model_en:
            t["en"] += " (перевод модели, сверить)"
        g.append(f"| {md_escape(t['term'])} | {md_escape(t['def'])} | {md_escape(t['en'])} | {md_escape(t['where'])} | {t['pages']} | {t['by']} |")
    (pack / "glossary.md").write_text("\n".join(g) + "\n", encoding="utf-8")
    b = ["# ИТ-мосты", "", "Аналогии из узлов слоя и где каждая перестаёт работать (граница обязательна).", "",
         "| Глава | Понятие | ИТ-аналогия | Где ломается | Стр. PDF |", "| --- | --- | --- | --- | --- |"]
    b += [f"| {c} | {md_escape(t)} | {md_escape(a)} | {md_escape(w)} | {p} |" for c, t, a, w, p in bridges]
    (pack / "it_bridges.md").write_text("\n".join(b) + "\n", encoding="utf-8")
    import templates
    (pack / "templates").mkdir(exist_ok=True)
    (pack / "templates" / "registry.json").write_text(json.dumps(templates.registry(), ensure_ascii=False, indent=1), encoding="utf-8")
    secs = round(time.time() - t0, 1)
    log = pack / "pack_build_log.csv"
    new = not log.exists()
    with open(log, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "domain", "chapters", "machine_seconds", "terms", "it_bridges", "errata_rows", "person_minutes"])
        w.writerow([datetime.datetime.now().isoformat(timespec="minutes"), dom, " ".join(pathlib.Path(c).name for c in chapters),
                    secs, len(terms), len(bridges), n_err, ""])
    print(f"пакет {dom}: терминов {len(terms)}, ИТ-мостов {len(bridges)}, строк опечаток {n_err}, {secs} с -> {pack}")


def new_domain(dom):
    """Заготовка пакета нового домена: общие файлы копируются как основа, предметное собирается из слоя главы сдвига."""
    pack = domain.pack_dir(dom)
    if pack.exists():
        raise SystemExit(f"пакет {pack} уже есть")
    src = domain.pack_dir("geology")
    pack.mkdir(parents=True)
    for f in ("misconceptions.json", "physics_checklist.json", "styleguide.json", "pronunciation.md", "stress_dictionary.md"):
        shutil.copyfile(src / f, pack / f)
    (pack / "templates").mkdir()
    (pack / "README.md").write_text(
        f"# Доменный пакет: {dom}\n\nСоздан {datetime.datetime.now().isoformat(timespec='minutes')} командой `python engine/domain_build.py --new {dom}`.\n\n"
        "Что сделать для нового домена (время записывается в `pack_build_log.csv`, человеко-минуты — в колонку person_minutes):\n"
        "1. `misconceptions.json` и `physics_checklist.json` — оставить применимые к домену, добавить свои (`misc.*`, `pc.*`).\n"
        "2. `pronunciation.md`, `stress_dictionary.md` — добавить аббревиатуры и термины домена.\n"
        "3. `templates/<шаблон>.json` — параметры-образцы шаблонов сцен для домена (без них берутся образцы геологии).\n"
        f"4. Собрать глоссарий, ИТ-мосты и листы опечаток из слоя главы: `DOMAIN={dom} python engine/domain_build.py --domain {dom} --chapters data/<глава>`.\n",
        encoding="utf-8")
    print(f"заготовка пакета {dom}: {pack}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default=domain.name())
    ap.add_argument("--chapters", nargs="*", default=[])
    ap.add_argument("--new")
    a = ap.parse_args()
    if a.new:
        new_domain(a.new)
    else:
        build(a.domain, a.chapters)


if __name__ == "__main__":
    main()
