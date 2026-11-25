"""Модуль проверки чужого пакета: вход review_package, выход review_output.

Машина сама сверяет цитаты, страницы и числа и готовит подсказки. Решение об ошибке смысла
принимает модель по тексту страницы, а сборка не пропускает замечание без страницы и цитаты.
"""
import re

from .check import Report, Source, check_quote, meaning_suspects
from .nodes import locate, show
from .textnorm import norm_quote, numbers

BATCH = 14
CATEGORIES = ("overgeneralization", "sign_flip", "measured_vs_inferred", "lost_condition",
              "missing_caveat", "wrong_scaling", "wrong_mechanism", "outdated_as_current",
              "analogy_without_limit", "frame_error", "other")


SEVERITY = {"major": "significant", "medium": "significant", "high": "critical", "low": "minor"}


def hints(src, item, claims):
    """Подсказки машины по элементу пакета."""
    out = []
    base = claims.get(item.get("claim_ref")) if item["type"] == "script_line" else item
    quote, page = (base or {}).get("quote"), (base or {}).get("page_pdf")
    if item["type"] == "claim" and quote:
        rep = Report()
        check_quote(src, quote, page, item["id"], rep)
        out += [f"{r['code']}: {r['message']}" for r in rep]
    if item["type"] == "analogy" and len((item.get("breaks_where") or "").split()) < 3:
        out.append("ANALOGY: не названо, где аналогия ломается")
    if quote and page:
        have = numbers(quote) | numbers("\n".join(src.author.get(page, [])))
        extra = sorted(numbers(item["text"]) - have)
        if extra:
            out.append("NUMBER: на странице нет чисел " + ", ".join(extra))
        out += [f"{code}: {msg}" for code, msg in meaning_suspects(item["text"], quote)]
    return out


def batches(package):
    items = package["items"]
    claims = [i for i in items if i["type"] == "claim"]
    out = [claims[i:i + BATCH] for i in range(0, len(claims), BATCH)]
    rest = [i for i in items if i["type"] != "claim"]
    if rest or package["frames"]:
        out.append(rest)
    return out


def prompt(template, package, units, items, checklist, misconceptions, with_frames, package_dir):
    src = Source(units)
    claims = {i["id"]: i for i in package["items"] if i["type"] == "claim"}
    pages, lines = set(), []
    for it in items:
        ref = claims.get(it.get("claim_ref"))
        pages.add(it.get("page_pdf") or (ref or {}).get("page_pdf"))
        lines.append(f"### {it['id']} ({it['type']})")
        for key in ("text", "kind", "page_pdf", "quote", "breaks_where", "on_screen", "spec_path"):
            if it.get(key) is not None:
                lines.append(f"{key}: {it[key]}")
        if ref:
            lines.append(f"опирается на {ref['id']} (стр. {ref['page_pdf']}): {ref['text']} | цитата: {ref['quote']}")
        for h in hints(src, it, claims):
            lines.append(f"подсказка машины: {h}")
    if with_frames:
        for f in package["frames"]:
            lines.append(f"### {f['id']} (кадр) файл: {(package_dir / f['file']).as_posix()}")
            lines += [f"{k}: {f[k]}" for k in ("t", "frame_class", "label", "shows", "plaque") if f.get(k) is not None]
        for s in package["scenes"]:
            lines.append(f"### Спецификация сцены {s['video_id']} (контекст)\n{s['spec']}")
    pages.discard(None)
    near = {q for p in pages for q in (p - 1, p, p + 1)}
    text = [show(u) for u in units if u["page"] in near and u["origin"] in ("author", "figure_ai")]
    fill = {"CHECKLIST": "\n".join(f"- {c['id']}: {c['item']}" for c in checklist),
            "MISC": "\n".join(f"- {m['text']}" for m in misconceptions),
            "ITEMS": "\n".join(lines), "TEXT": "\n".join(text), "CATEGORIES": ", ".join(CATEGORIES)}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fill[m.group(1)], template)


def assemble(package, units, answers, team):
    """Ответ по схеме; замечания без страницы, цитаты или с чужой целью отбрасываются с объяснением."""
    src = Source(units)
    by_id = {u["id"]: u for u in units}
    targets = {i["id"] for i in package["items"]} | {f["id"] for f in package["frames"]}
    remarks, dropped, seen = [], [], set()
    for ans in answers:
        for r in ans["remarks"]:
            why = None
            uid, start, *end = r.get("q") or [None, ""]
            unit, quote = locate(by_id, uid, start, end[0] if end else None) if start else (None, None)
            if r["target"] not in targets:
                why = "нет такой цели"
            elif r["target"] in seen:
                why = "вторая ремарка на ту же цель"
            elif r["category"] not in CATEGORIES:
                why = "неизвестная категория"
            elif not r.get("fix", "").strip():
                why = "нет исправления"
            elif not quote or not src.find(norm_quote(quote)):
                why = f"цитата не найдена: {r.get('q')}"
            if why:
                dropped.append((r["target"], why))
                continue
            seen.add(r["target"])
            remarks.append({"target": r["target"], "category": r["category"], "severity": SEVERITY.get(r["severity"], r["severity"]),
                            "problem": r["problem"], "fix": r["fix"], "page_pdf": unit["page"],
                            "quote": quote.strip()})
    return {"package_id": package["package_id"], "team": team, "remarks": remarks}, dropped
