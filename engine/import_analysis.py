#!/usr/bin/env python3
"""Импорт «анализов книг» организаторов (20-блочные JSON) в проект.

Анализ — ОПОРА для структурирования, а не источник истины: термины, числа и страницы из него
помечаются «не сверено» и обязаны быть подтверждены цитатой со страницы главы (ТЗ: «всё по странице»).

Вход : data/analysis/*.md|*.json  (файлы с JSON внутри; выданы организаторами, в git не кладутся)
Выход: data/book_index/<slug>.json   — оглавление со страницами, зависимости глав, определения,
                                       методы, эмпирические параметры (с оговорками), слабые разделы
       domain_pack/glossary.json     — добавляет термины (status=from_analysis_unverified), ничего не затирает
       domain_pack/legacy_notes.json — устаревшие разделы: для нюанса «как это делается сейчас» и пометки «исторический прибор»
Запуск: python engine/import_analysis.py [--src data/analysis] [--dst .]
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
               "u", "f", "kh", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
UNVERIFIED = "из анализа организаторов; НЕ сверено со страницей"


def slug(name):
    base = re.split(r"[_\s-]", pathlib.Path(name).stem.strip())[0].lower()
    s = "".join(TR.get(c, c) for c in base)
    return re.sub(r"[^a-z0-9]+", "", s) or "book"


def load(path):
    t = pathlib.Path(path).read_text(encoding="utf-8").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    return json.loads(t)


def g(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def index_one(a, fname):
    return {
        "source_file": fname,
        "status": UNVERIFIED,
        "meta": {k: g(a, "meta", k) for k in ("title", "authors", "year", "total_pages_approx", "language")},
        "toc": [{"level": t.get("level"), "number": t.get("number"), "title": t.get("title"),
                 "page_or_location": t.get("page_or_location")} for t in a.get("table_of_contents", [])],
        "chapter_dependencies": {
            "reading_mode": g(a, "chapter_dependencies", "reading_mode"),
            "standalone_chapters": g(a, "chapter_dependencies", "standalone_chapters", default=[]),
            "dependency_chains": g(a, "chapter_dependencies", "dependency_chains", default=[]),
            "notation_defined_in": g(a, "chapter_dependencies", "notation_defined_in"),
        },
        "key_definitions": [{"term": d.get("term"), "en": d.get("term_en_equivalent"), "chapter": d.get("chapter"),
                             "quality": d.get("quality"), "school_note": d.get("school_note"), "note": d.get("note")}
                            for d in a.get("key_definitions", [])],
        "named_methods_and_models": [{k: m.get(k) for k in ("name", "type", "chapter", "description",
                                                            "canonical_status", "note")}
                                     for m in a.get("named_methods_and_models", [])],
        "empirical_parameters": [{k: p.get(k) for k in ("parameter", "value_or_formula", "units_as_printed",
                                                        "validity_domain", "chapter", "citation_safety", "caution")}
                                 for p in a.get("empirical_correlations_and_parameters", [])],
        "weak_sections": [{k: w.get(k) for k in ("chapter", "issue_type", "description", "impact")}
                          for w in a.get("misleading_or_weak_sections", [])],
        "prerequisites": g(a, "prerequisites_and_context", default={}),
        "school_note": g(a, "meta", "school_and_standards", "school_note"),
    }


def merge_glossary(path, new_terms):
    gl = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"terms": []}
    have = {(t.get("ru") or "").lower() for t in gl.get("terms", [])}
    added = 0
    for t in new_terms:
        key = (t["term"] or "").lower()
        if key and key not in have:
            gl["terms"].append({"ru": t["term"], "abbr": None, "en": t.get("en"), "page": None,
                                "chapter": t.get("chapter"), "note": t.get("note"),
                                "status": "from_analysis_unverified"})
            have.add(key)
            added += 1
    path.write_text(json.dumps(gl, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "data" / "analysis"))
    ap.add_argument("--dst", default=str(ROOT))
    a = ap.parse_args()
    src, dst = pathlib.Path(a.src), pathlib.Path(a.dst)
    files = sorted(p for p in src.glob("*") if p.suffix.lower() in (".md", ".json"))
    if not files:
        print(f"В {src} нет файлов анализов. Скачайте папку «analysis books» с Диска и положите сюда.")
        return 1
    (dst / "data" / "book_index").mkdir(parents=True, exist_ok=True)
    (dst / "domain_pack").mkdir(parents=True, exist_ok=True)
    legacy, added_total, bad = [], 0, 0
    for f in files:
        try:
            an = load(f)
        except Exception as ex:  # не JSON — пропускаем, но говорим
            print(f"  ! {f.name}: не JSON ({ex})")
            bad += 1
            continue
        idx = index_one(an, f.name)
        s = slug(f.name)
        (dst / "data" / "book_index" / f"{s}.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
        added_total += merge_glossary(dst / "domain_pack" / "glossary.json", idx["key_definitions"])
        for w in idx["weak_sections"]:
            legacy.append({"book": s, **w, "status": UNVERIFIED})
        print(f"  {f.name} -> book_index/{s}.json: оглавление {len(idx['toc'])}, определений {len(idx['key_definitions'])}, "
              f"параметров {len(idx['empirical_parameters'])}, слабых разделов {len(idx['weak_sections'])}")
    (dst / "domain_pack" / "legacy_notes.json").write_text(
        json.dumps({"_note": "Устаревшее/слабое в книгах: для «как это делается сейчас» и пометки «исторический прибор». Сверять с главой.",
                    "items": legacy}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Готово: книг {len(files) - bad}, новых терминов в глоссарии {added_total}, записей legacy {len(legacy)}")
    return 0 if not bad else 2


if __name__ == "__main__":
    sys.exit(main())
