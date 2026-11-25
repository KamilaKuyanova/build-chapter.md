"""Узлы: промпты для модели и сборка её коротких ответов в слой по node.schema.json.

Модель не переписывает цитаты, страницы и задачи: она указывает единицу и первые слова,
а дословный текст и страницу подставляет сборка. Так модель не может ошибиться в цитате.
"""
import json
import re

from .textnorm import norm_quote
from .units import needs_cover

CHUNK = 9000  # знаков текста автора в одной порции
KIND = {"o": "observation", "i": "inference", "a": "assumption"}
SOURCE_KIND = {"formula": "formula", "table": "table", "table_caption": "table", "task": "task",
               "figure": "figure_caption", "figure_desc": "figure_description_model"}
VIDEO = ("time", "invisible", "scale", "counterintuitive", "cause_effect")


def chunks(units):
    """Порции главы: режем по заголовкам и абзацам, описание рисунка не отрываем от страницы."""
    out, cur, size = [], [], 0
    for u in units:
        if u["origin"] == "service":
            continue
        cost = len(u["text"]) if u["origin"] == "author" else 0
        torn = bool(cur) and not re.search(r"[.!?:;»)\]|$]\s*$", cur[-1]["text"]) and u["text"][:1].islower()
        heavy = size + cost > CHUNK and not torn
        if cur and (heavy or (u["type"] == "heading" and size > CHUNK * 0.6)):
            out.append(cur)
            cur, size = [], 0
        cur.append(u)
        size += cost
    if cur:
        out.append(cur)
    tail = sum(len(u["text"]) for u in out[-1] if u["origin"] == "author")
    if len(out) > 1 and tail < CHUNK * 0.25:
        last = out.pop()
        out[-1] = out[-1] + last
    # заголовок в конце порции относится к следующей
    for i in range(len(out) - 1):
        while len(out[i]) > 1 and out[i][-1]["type"] == "heading":
            out[i + 1].insert(0, out[i].pop())
    return out


def show(unit):
    mark = {"figure_ai": " ОПИСАНИЕ РИСУНКА НЕЙРОСЕТЬЮ, не автор"}.get(unit["origin"], "")
    ocr = " РАСПОЗНАНО С ОШИБКАМИ" if unit.get("ocr_suspect") else ""
    return f"[{unit['id']} {unit['type']}{mark}{ocr}]\n{unit['text']}\n"


def prompt(template, domain_brief, spec, part, total, chunk, done_nodes):
    known = [f"- {n['id']}: {n['title']}; термины: {', '.join(n['terms_introduced']) or 'нет'}"
             for n in done_nodes]
    fill = {"TITLE": spec["title"], "PREFIX": spec["id"], "PART": f"{part} из {total}",
            "DOMAIN": domain_brief, "KNOWN": "\n".join(known) or "пока нет",
            "COVER": " ".join(u["id"] for u in chunk if needs_cover(u)),
            "TEXT": "\n".join(map(show, chunk))}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fill[m.group(1)], template)


def sentence(text, start, end=None):
    """Дословный кусок единицы: от слов start до слов end или до конца предложения."""
    i = text.find(start)
    if i < 0:
        return None
    if end:
        j = text.find(end, i)
        return text[i:j + len(end)] if j >= 0 else None
    m = re.compile(r"(?<!\b[А-ЯA-Z])(?<!рис)(?<!табл)(?<!см)(?:[.!?](?=\s*$|\s*\n|\s+[А-ЯЁA-Z«\"(\\$])|;(?=\s*\n\s*[-•*]))").search(text, i + len(start))
    return text[i:m.end()] if m else text[i:]


def locate(units, uid, start, end=None):
    """Единица и дословный кусок. Если модель ошиблась номером единицы, ищем те же слова по главе."""
    first = units.get(uid)
    pool = [first] if first else []
    pool += sorted((u for u in units.values() if u is not first and u["origin"] == "author"),
                   key=lambda u: abs(u["page"] - (first["page"] if first else 0)))
    for u in pool:
        quote = sentence(u["text"], start, end)
        if quote:
            return u, quote
    return first, None


def hoist_terms(nodes):
    """Определение термина переезжает в первый узел, где термин встретился: новичок не увидит его раньше объяснения."""
    texts = [norm_quote(" ".join(n["layers"][k]["text"] for k in ("topic", "main", "mechanism", "practice", "nuances")))
             for n in nodes]
    for i, node in enumerate(nodes):
        for g in list(node["glossary"]):
            word = re.compile(rf"(?<!\w){re.escape(norm_quote(g['term']))}(?!\w)")
            first = next((j for j in range(i) if word.search(texts[j])), None)
            if first is None:
                continue
            node["glossary"].remove(g)
            node["terms_introduced"].remove(g["term"])
            if g["term"] not in nodes[first]["terms_introduced"]:
                nodes[first]["glossary"].append(g)
                nodes[first]["terms_introduced"].append(g["term"])


def ids_of(x):
    """Единицы через пробел или списком — модель пишет и так, и так."""
    return x.split() if isinstance(x, str) else list(x or [])


class Builder:
    def __init__(self, spec, units):
        self.spec, self.units = spec, {u["id"]: u for u in units}
        self.by_number = {(u["type"], u["number"]): u for u in units if u.get("number")}
        self.problems = []

    def full(self, slug):
        prefix = self.spec["id"] + "."
        return slug if slug.startswith(prefix) else prefix + slug

    def para(self, p, where):
        text, ids = p[0], ids_of(p[1])
        pages = [self.units[i]["page"] for i in ids if i in self.units]
        self.problems += [f"{where}: нет единицы {i}" for i in ids if i not in self.units]
        return {"text": text, "units": ids, "page_pdf": pages[0] if pages else None,
                "pages": sorted(set(pages)), "by_model": True}

    def claim(self, c, cid):
        uid, start, *end = c["q"]
        unit, quote = locate(self.units, uid, start, end[0] if end else None)
        if not quote:
            self.problems.append(f"{cid}: в {uid} нет слов «{start}»")
            return None
        out = {"id": cid, "text": c["t"], "kind": KIND[c["k"]], "page_pdf": unit["page"],
               "page_print": None, "quote": quote.strip(), "unit": unit["id"],
               "source_kind": SOURCE_KIND.get(unit["type"], "text"), "by_model": True}
        if unit["origin"] == "figure_ai" or unit.get("ocr_suspect"):
            out["needs_scan"] = True
        return out

    def node(self, a, order):
        a = {"data": ["", "", []], "video": [0] * len(VIDEO), **{k: v for k, v in a.items() if v is not None}}
        nid = self.full(a["id"])
        field = lambda text: {"text": text, "by_model": True}
        layers, units = {"topic": field(a["topic"]), "main": field(a["main"])}, set()
        for key in ("mechanism", "practice", "nuances"):
            paras = [self.para(p, f"{nid}.{key}") for p in a.get(key, [])]
            layers[key] = {"text": "\n\n".join(p["text"] for p in paras), "by_model": True, "paras": paras}
        layers["deeper"] = [{**self.para(p, f"{nid}.deeper")} for p in a.get("deeper", [])]
        for p in [p for k in ("mechanism", "practice", "nuances") for p in layers[k]["paras"]] + layers["deeper"]:
            units.update(p["units"])
        claims = [self.claim(c, f"{nid}#c{i}") for i, c in enumerate(a["claims"], 1)]
        claims = [c for c in claims if c]
        units.update(c["unit"] for c in claims)
        examples, tasks = [], []
        for e in a.get("examples", []):
            u = self.by_number.get(("example", str(e["n"])))
            if not u:
                self.problems.append(f"{nid}: нет примера {e['n']}")
                continue
            own = [u["id"], *ids_of(e.get("units"))]
            units.update(own)
            examples.append({"number": str(e["n"]), "page_pdf": u["page"], "condition": e["condition"],
                             "steps": e["steps"], "result": e["result"], "figure": e.get("figure"),
                             "units": own})
        for t in a.get("tasks", []):
            number, figure, more = ((t if isinstance(t, list) else [t]) + [None, None])[:3]
            rest = [i for i in ids_of(more) if i in self.units]
            u = self.by_number.get(("task", str(number)))
            if not u:
                self.problems.append(f"{nid}: нет задачи {number}")
                continue
            units.update([u["id"], *rest])
            tasks.append({"number": str(number), "page_pdf": u["page"], "figure": figure,
                          "text": " ".join([re.sub(r"^\d+\.\s*", "", u["text"]),
                                            *(self.units[i]["text"] for i in rest)]),
                          "ocr_suspect": bool(u.get("ocr_suspect"))})
        formulas, tables = [], []
        for uid, meaning, variables in a.get("formulas", []):
            u = self.units.get(uid)
            if not u:
                self.problems.append(f"{nid}: нет единицы формулы {uid}")
                continue
            units.add(uid)
            formulas.append({"unit": uid, "page_pdf": u["page"], "latex": u["text"], "meaning": meaning,
                             "variables": [{"symbol": v[0], "meaning": v[1], "unit": (v + [None])[2]}
                                           for v in variables], "by_model": True})
        for title, ids, *fixes in a.get("tables", []):
            ids = ids_of(ids)
            own = [self.units[i] for i in ids if i in self.units]
            self.problems += [f"{nid}: нет единицы таблицы {i}" for i in ids if i not in self.units]
            if own:
                units.update(u["id"] for u in own)
                tables.append({"title": title, "units": ids, "page_pdf": own[0]["page"],
                               "markdown": "\n".join(u["text"] for u in own if u["type"] == "table"),
                               "ocr_fixes": fixes[0] if fixes else []})
        units.update(ids_of(a.get("units")))
        known = [self.units[i] for i in units if i in self.units]
        lens, misc = a.get("lens"), a.get("misc")
        return {
            "id": nid, "order": order, "title": a["title"], "title_novice": a["novice"],
            "why_here": field(a["why"]), "threshold": bool(a.get("threshold")),
            "difficulty": {"primary": a["diff"][0], "secondary": (a["diff"] + [None])[1]},
            "pages": sorted({u["page"] for u in known}), "units": sorted(i for i in units if i in self.units),
            "layers": layers, "claims": claims,
            "links": [{"type": k, "target": t if k in ("refutes_misconception",) or t.startswith("data.")
                       else self.full(t)} for k, t in a.get("links", [])],
            "misconception": {"ref": misc[0], "text": misc[1], "by_model": True} if misc else None,
            "data_meaning": {"from_chapter": field(a["data"][0]), "breaks": field(a["data"][1]),
                             "hypotheses": [{**field(h), "hypothesis": True} for h in a["data"][2]]},
            "it_analogy": {"text": a["analogy"][0], "breaks_where": a["analogy"][1], "by_model": True},
            "now_practice": {**field(a["now"]), "hypothesis": True} if a.get("now") else None,
            "inefficiency_lens": {**lens, "by_model": True} if lens else None,
            "terms_introduced": [t[0] for t in a.get("terms", [])], "terms_used": [],
            "glossary": [{"term": t[0], "definition": t[1], "by_model": True} for t in a.get("terms", [])],
            "needs_scan": [{"page": self.units[c["unit"]]["page"], "what": c["id"]}
                           for c in claims if c.get("needs_scan")]
            + [{"page": self.units[i]["page"], "what": w} for i, w in a.get("scan", []) if i in self.units],
            "decision_on_data": a.get("decision"), "worked_examples": examples, "book_tasks": tasks,
            "formulas": formulas, "tables": tables,
            "video_scores": dict(zip(VIDEO, a["video"])),
        }

    def layer(self, answers, generated_by):
        nodes, uncovered = [], []
        for ans in answers:
            for a in ans["nodes"]:
                try:
                    nodes.append(self.node(a, len(nodes) + 1))
                except (KeyError, TypeError, IndexError, ValueError, AttributeError) as e:
                    self.problems.append(f"узел {a.get('id', '?')} не собран: {type(e).__name__} {e}. Проверить поля этого узла")
            uncovered += [{"unit": u, "reason": r} for ids, r in ans.get("uncovered", []) for u in ids_of(ids)]
        hoist_terms(nodes)
        return {"chapter": self.spec["id"], "source": self.spec["book"], "generated_by": generated_by,
                "nodes": nodes, "uncovered": uncovered}


def parse_answer(text):
    """JSON из ответа модели: терпим обёртку ```json и слова вокруг."""
    i, j = text.find("{"), text.rfind("}")
    if i < 0:
        raise ValueError("в ответе нет JSON")
    return json.loads(text[i:j + 1])
