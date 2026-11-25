"""Проверка учебного слоя (node.schema.json) по тексту главы.

error   — факт, проверенный машиной: цитата, страница, число, покрытие, порядок.
suspect — подозрение на искажение смысла, его разбирает смысловая проверка.

Наши поля сверх схемы: node.units — единицы главы, пересказанные в узле;
layer.uncovered — [{unit, reason}] для единиц без узла.
"""
import re

from . import schema as jsonschema
from .textnorm import norm_quote, numbers, words
from .units import kind, needs_cover

STRONG = {"всегда", "никогда", "любой", "любая", "любое", "любые", "все", "всех", "обязательно",
          "полностью", "исключительно", "always", "never", "any", "all", "only", "every", "must"}
HEDGE_RU = {"обычно", "часто", "нередко", "иногда", "возможно", "может", "могут", "большинстве",
            "большинства", "преимущественно", "примерно", "приблизительно"}
HEDGE_EN = {"usually", "often", "may", "might", "generally", "typically", "sometimes", "approximately", "could",
            "about", "commonly", "probably", "possibly", "likely", "mostly", "most", "nearly", "almost", "roughly",
            "rarely", "seldom", "normally", "frequently", "largely", "mainly", "perhaps", "tend", "tends", "some"}
# перевод оговорки на русский шире списка, по которому ищем потерю в русской цитате
SOFT_RU = HEDGE_RU | {"около", "почти", "большинство", "большая", "некоторые", "некоторых", "вероятно", "редко", "бывает",
                      "бывают", "способен", "способны", "порядка", "правило", "главным", "основном", "чаще", "порой", "мало"}
CONDITION_RU = {"если", "когда", "условии", "условиях", "только", "кроме", "исключением"}
CONDITION_EN = {"if", "when", "unless", "provided", "except", "until", "whenever", "assuming"}
WHEN_RU = CONDITION_RU | {"при", "пока", "иначе", "после", "без", "где"}
NEG_RU = {"не", "нет", "нельзя", "без"}
NEG_EN = {"not", "no", "cannot", "never", "nor", "neither", "without", "none"}
OPPOSITES = [("увелич", "уменьш"), ("повыш", "пониж"), ("выше", "ниже"), ("больше", "меньше"),
             ("раст", "пада"), ("возраст", "убыва"), ("высок", "низк"), ("положительн", "отрицательн"),
             ("increas", "decreas"), ("higher", "lower"), ("above", "below"), ("positive", "negative"),
             ("rise", "fall"), ("greater", "smaller")]
# русский текст по английской цитате: слева и справа — противоположные смыслы на обоих языках
ACROSS = [(("увелич", "повыш", "возраст", "растет", "растут", "вырос", "рост"), ("уменьш", "пониж", "сниж", "падает", "падают", "убыва", "упал"),
           ("increas", "rise", "rising", "grow"), ("decreas", "fall", "declin", "reduc", "drop", "diminish")),
          (("выше", "больше", "тяжелее", "быстрее"), ("ниже", "меньше", "легче", "медленнее"),
           ("higher", "greater", "above", "more", "larger", "heavier", "faster", "exceed"), ("lower", "less", "below", "smaller", "lighter", "slower")),
          (("высок",), ("низк",), ("high",), ("low",)),
          (("положительн",), ("отрицательн",), ("positive",), ("negative",)),
          (("вверх",), ("вниз",), ("upward", "updip"), ("downward", "downdip")),
          (("крупн", "грубе"), ("мелк",), ("coars",), ("fine", "fining")),
          (("быстр",), ("медлен",), ("fast", "rapid", "quick"), ("slow",)),
          (("толст", "мощн"), ("тонк",), ("thick",), ("thin",))]
LAYERS = ("topic", "main", "mechanism", "practice", "nuances")
THIN = 0.2  # доля слов единицы, ниже которой считаем, что её сжали до общих слов


REF = re.compile(r"\(\d+\.\d+\)")


class Report(list):
    def add(self, level, code, where, message, page=None, fix=None):
        self.append({"level": level, "code": code, "where": where, "message": message,
                     "page": page, "fix": fix})


def strict(text):
    """Сверка как в README схем: без пробелов, переносов строк и регистра."""
    return re.sub(r"\s+", "", text).casefold()


class Source:
    """Текст главы по страницам: отдельно автор, отдельно описания рисунков."""

    def __init__(self, units):
        self.units = {u["id"]: u for u in units}
        self.author, self.figure = {}, {}
        self.refs = {m for u in units if u["origin"] == "author" for m in REF.findall(u["text"])}
        for u in units:
            if u["origin"] == "author":
                self.author.setdefault(u["page"], []).append(u["text"])
            elif u["origin"] == "figure_ai":
                self.figure.setdefault(u["page"], []).append(u["text"])
        self.strict = {p: strict("".join(t)) for p, t in self.author.items()}
        self.author_norm = {p: norm_quote("\n".join(t)) for p, t in self.author.items()}
        self.figure_norm = {p: norm_quote("\n".join(t)) for p, t in self.figure.items()}

    def spread(self, page):
        """Страница вместе со следующей: фраза может переходить через границу."""
        return norm_quote("\n".join(self.author.get(page, []) + self.author.get(page + 1, [])))

    def find(self, quote):
        pages = [p for p, t in sorted(self.author_norm.items()) if quote in t]
        return pages or [p for p in sorted(self.author_norm) if quote in self.spread(p)]

    def units_of_quote(self, quote, page):
        q = norm_quote(quote)
        return [u["id"] for u in self.units.values() if u["origin"] == "author"
                and u["page"] == page and q in norm_quote(u["text"])]


def check_quote(src, quote, page, where, report):
    q = norm_quote(quote)
    if len(words(q)) < 3 and not re.search(r"[=\\]", quote):
        report.add("error", "QUOTE_TOO_SHORT", where, "цитата короче трёх слов", page)
    elif strict(quote) in src.strict.get(page, ""):
        return
    elif q in src.author_norm.get(page, ""):
        report.add("error", "QUOTE_NOT_VERBATIM", where,
                   "цитата отличается знаками или разметкой, сверка её не найдёт", page,
                   "скопировать из md дословно")
    elif src.find(q):
        found = src.find(q)[0]
        if found in (page, page - 1) and q not in src.author_norm.get(found, ""):
            report.add("error", "QUOTE_OVER_PAGES", where, "цитата переходит через границу страниц",
                       page, "взять часть с одной страницы")
        else:
            report.add("error", "QUOTE_WRONG_PAGE", where,
                       f"цитата есть в главе, но не на стр. {page}", found, f"указать стр. {found}")
    elif any(q in t for t in src.figure_norm.values()):
        report.add("error", "QUOTE_FROM_FIGURE_AI", where,
                   "это описание рисунка нейросетью, а не слова автора", page)
    else:
        report.add("error", "QUOTE_NOT_FOUND", where, f"цитаты нет в главе: «{quote[:80]}»", page)


def check_numbers(src, text, unit_ids, where, page, report):
    base = set()
    for uid in unit_ids:
        unit = src.units.get(uid)
        if unit:
            base |= numbers(unit["text"], loose=True)
            if unit["type"] == "figure":  # подписи осей есть только в описании рисунка
                base |= numbers("\n".join(src.figure.get(unit["page"], [])))
    text = REF.sub(lambda m: " " if m.group(0) in src.refs else m.group(0), text)
    extra = sorted(numbers(text) - base)
    if extra:
        report.add("error", "NUMBER_NOT_IN_SOURCE", where,
                   "чисел нет в исходных единицах: " + ", ".join(extra), page)


def meaning_suspects(text, quote):
    """Дешёвые признаки искажения смысла. Это подсказки, а не приговор."""
    out, said = [], set(words(text))
    quote = re.sub(r"n['’]t\b", " not", quote)
    quoted = set(words(quote))
    english = not re.search("[а-яё]", quote.casefold()) and len(re.findall(r"\b[a-z]{3,}\b", re.sub(r"\$[^$]*\$", "", quote))) > 2
    translated = english and bool(re.search("[а-яё]", text.casefold()))
    has = lambda bag, stems: any(w.startswith(stems) for w in bag)
    soft, when = (SOFT_RU, WHEN_RU) if translated else (HEDGE_RU | HEDGE_EN, CONDITION_RU | CONDITION_EN)
    strong = quoted & STRONG or english and quoted & {"entire", "whole", "each", "completely"}
    if said & STRONG and not strong:
        out.append(("OVERGENERALIZED", f"«{', '.join(sorted(said & STRONG))}» нет в цитате"))
    hedges = quoted & (HEDGE_EN if english else HEDGE_RU)
    if not re.search(r"\bmost (?:of|\w+s)\b", quote.casefold()):
        hedges = hedges - {"most"}  # «the most reliable» — превосходная степень
    if hedges and not said & soft:
        out.append(("HEDGE_LOST", f"потеряна оговорка «{', '.join(sorted(hedges))}»"))
    conditions = quoted & (CONDITION_EN if english else CONDITION_RU)
    if conditions and not said & when:
        out.append(("CONDITION_LOST", f"потеряно условие «{', '.join(sorted(conditions))}»"))
    for a, b in OPPOSITES:
        for x, y in ((a, b), (b, a)):
            if has(said, x) and not has(said, y) and has(quoted, y) and not has(quoted, x):
                out.append(("POLARITY", f"в тексте «{x}…», в цитате «{y}…»"))
    for up, down, up_en, down_en in ACROSS if translated else []:
        for mine, other, theirs, anti in ((up, down, up_en, down_en), (down, up, down_en, up_en)):
            if has(said, mine) and not has(said, other) and has(quoted, anti) and not has(quoted, theirs):
                out.append(("POLARITY", f"в тексте «{mine[0]}…», в цитате «{anti[0]}…»"))
    neg_said = bool(said & (NEG_RU | NEG_EN)) or "unless" in said
    if neg_said != bool(quoted & (NEG_RU | NEG_EN)) and not (neg_said and "unless" in quoted):
        out.append(("NEGATION", "отрицание есть только в тексте или только в цитате"))
    return out


def node_units(src, node):
    """Единицы, на которых стоит узел: явные, из цитат, из примеров и задач книги."""
    out = set(node.get("units", []))
    for c in node["claims"]:
        out.update(src.units_of_quote(c["quote"], c["page_pdf"]))
    numbered = {(u["type"], u.get("number")): u["id"] for u in src.units.values() if u.get("number")}
    for t in node.get("book_tasks", []):
        out.add(numbered.get(("task", str(t["number"]))))
    for e in node.get("worked_examples", []):
        out.add(numbered.get(("example", str(e.get("number")))))
    out.discard(None)
    return out


def node_text(node):
    parts = [node["layers"][k]["text"] for k in LAYERS]
    parts += [d["text"] for d in node["layers"]["deeper"]]
    parts += [c["text"] + " " + c["quote"] for c in node["claims"]]
    for e in node.get("worked_examples", []):
        parts += [e["condition"], *e["steps"], e["result"]]
    parts += [t["text"] for t in node.get("book_tasks", [])]
    return "\n".join(parts)


def stems(text):
    return {w[:6] for w in words(text) if len(w) > 4}


def check_node(src, node, misconceptions, report):
    nid, units = node["id"], node_units(src, node)
    for uid in node.get("units", []):
        if uid not in src.units:
            report.add("error", "UNIT_UNKNOWN", nid, f"нет единицы {uid}")
    for c in node["claims"]:
        where = c["id"]
        if not c["id"].startswith(nid + "#"):
            report.add("error", "CLAIM_ID", where, f"id утверждения должен начинаться с {nid}#")
        if c["source_kind"] == "figure_description_model":
            if not c.get("needs_scan"):
                report.add("error", "FIGURE_NEEDS_SCAN", where,
                           "опора на описание рисунка нейросетью без needs_scan", c["page_pdf"])
        else:
            check_quote(src, c["quote"], c["page_pdf"], where, report)
        own = src.units_of_quote(c["quote"], c["page_pdf"]) or \
            [u for u in units if src.units.get(u, {}).get("page") == c["page_pdf"]]
        check_numbers(src, c["text"], own, where, c["page_pdf"], report)
        for code, message in meaning_suspects(c["text"], c["quote"]):
            report.add("suspect", code, where, message, c["page_pdf"])
        for uid in own:
            if src.units.get(uid, {}).get("ocr_suspect"):
                report.add("suspect", "OCR_SUSPECT", where, f"{uid} распознан с ошибками", c["page_pdf"])
    for key in LAYERS:
        layer = node["layers"][key]
        for i, p in enumerate(layer.get("paras") or [layer]):
            check_numbers(src, p["text"], p.get("units") or units, f"{nid}.layers.{key}[{i}]",
                          p.get("page_pdf"), report)
    for i, d in enumerate(node["layers"]["deeper"]):
        check_numbers(src, d["text"], d.get("units") or units, f"{nid}.layers.deeper[{i}]",
                      d.get("page_pdf"), report)
    data, decision = node["data_meaning"], node.get("decision_on_data") or {}
    for name, text in [("data_meaning.from_chapter", data["from_chapter"]["text"]),
                       ("data_meaning.breaks", data["breaks"]["text"]),
                       ("decision_on_data", " ".join([*decision.get("features", []), decision.get("rule", ""),
                                                      decision.get("conclusion", ""),
                                                      decision.get("counterexample") or ""]))]:
        check_numbers(src, text, units, f"{nid}.{name}", None, report)
    if len(words(node["title"])) and not 3 <= len((node.get("title_novice") or "a b c").split()) <= 7:
        report.add("error", "TITLE_LENGTH", nid, "заголовок для новичка должен быть 3–7 слов")
    for i, e in enumerate(node.get("worked_examples", [])):
        page_units = [u["id"] for u in src.units.values() if u["origin"] == "author"
                      and u["page"] in (e["page_pdf"], e["page_pdf"] + 1)]
        check_numbers(src, " ".join([e["condition"], *e["steps"], e["result"]]), page_units,
                      f"{nid}.worked_examples[{i}]", e["page_pdf"], report)
    for t in node.get("book_tasks", []):
        unit = next((u for u in src.units.values() if u["type"] == "task"
                     and u["number"] == str(t["number"])), None)
        where = f"{nid}.book_tasks[{t['number']}]"
        if not unit:
            report.add("error", "TASK_UNKNOWN", where, "такой задачи в главе нет", t["page_pdf"])
        elif unit["page"] != t["page_pdf"]:
            report.add("error", "TASK_PAGE", where, f"задача на стр. {unit['page']}", unit["page"],
                       f"указать стр. {unit['page']}")
        elif unit.get("ocr_suspect"):
            report.add("suspect", "OCR_SUSPECT", where, "задача распознана с ошибками, сверить со сканом",
                       t["page_pdf"])
    said = stems(node_text(node))
    for uid in sorted(units):
        unit = src.units.get(uid)
        if unit and kind(unit) in ("paragraph", "worked_example") and re.search("[а-яё]{3}", unit["text"]):
            want = stems(unit["text"])
            if len(want) >= 12 and len(want & said) / len(want) < THIN:
                report.add("suspect", "UNIT_THIN", nid, f"{uid} назван, но почти не пересказан", unit["page"])
    mis = node.get("misconception")
    if mis and mis["ref"] and misconceptions and mis["ref"] not in misconceptions:
        report.add("error", "MISC_UNKNOWN", nid, f"нет заблуждения {mis['ref']}")
    if not node["it_analogy"]["text"]:
        report.add("error", "ANALOGY_MISSING", nid, "нет ИТ-аналогии, схема её требует")
    elif len(words(node["it_analogy"]["breaks_where"])) < 3:
        report.add("error", "ANALOGY_WITHOUT_LIMIT", nid, "у аналогии не названа граница")


def check_graph(nodes, misconceptions, report):
    order = {n["id"]: n["order"] for n in nodes}
    if len(order) != len(nodes):
        report.add("error", "NODE_DUPLICATE", "nodes", "повторяются id узлов")
    if len(set(order.values())) != len(nodes):
        report.add("error", "ORDER_DUPLICATE", "nodes", "повторяется порядковый номер")
    seen = set()
    for n in nodes:
        for c in n["claims"]:
            if c["id"] in seen:
                report.add("error", "CLAIM_DUPLICATE", n["id"], f"повторяется {c['id']}")
            seen.add(c["id"])
        for link in n["links"]:
            to = link["target"]
            if link["type"] == "refutes_misconception":
                if misconceptions and to not in misconceptions:
                    report.add("error", "MISC_UNKNOWN", n["id"], f"нет заблуждения {to}")
            elif link["type"] == "to_data":
                if not to.startswith("data.") and to not in order:
                    report.add("error", "LINK_UNKNOWN", n["id"], f"нет узла или датасета {to}")
            elif to not in order:
                report.add("error", "LINK_UNKNOWN", n["id"], f"нет узла {to}")
            elif link["type"] == "prerequisite" and order[to] >= n["order"]:
                report.add("error", "PREREQ_AFTER", n["id"], f"предпосылка {to} стоит не раньше узла")
    if not any(n.get("decision_on_data") for n in nodes):
        report.add("error", "NO_DECISION", "nodes", "в главе нет узла «решение на данных»")


def check_terms(nodes, report):
    """Термин не должен появляться раньше узла, где он объяснён."""
    home = {}
    for n in sorted(nodes, key=lambda x: x["order"]):
        for t in n["terms_introduced"]:
            home.setdefault(norm_quote(t), n)
    for n in nodes:
        text = norm_quote(" ".join(n["layers"][k]["text"] for k in LAYERS))
        used = {norm_quote(t) for t in n.get("terms_used", [])}
        for term, first in home.items():
            if first["order"] > n["order"] and (
                    term in used or re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text)):
                report.add("error", "TERM_BEFORE_DEFINED", n["id"],
                           f"термин «{term}» объяснён позже, в {first['id']}")


def coverage(src, layer):
    by_unit = {}
    for n in layer["nodes"]:
        for uid in node_units(src, n):
            by_unit.setdefault(uid, []).append(n["id"])
    skipped = {x["unit"]: x["reason"] for x in layer.get("uncovered", [])}
    rows = []
    for u in src.units.values():
        if u["origin"] != "author":
            continue
        reason = skipped.get(u["id"])
        if u["type"] == "heading" and not reason:
            reason = "заголовок: отражён в порядке и названиях узлов"
        nodes = by_unit.get(u["id"], [])
        rows.append({"unit_id": u["id"], "kind": kind(u), "page_pdf": u["page"],
                     "excerpt": " ".join(u["text"].split()[:12]), "node_ids": nodes,
                     "reason": None if nodes else reason})
    return {"chapter": layer["chapter"], "rows": rows}


def check_layer(units, layer, schemas, misconceptions=()):
    report = Report()
    for err in jsonschema.validate(layer, schemas["node"]):
        report.add("error", "SCHEMA", "layer", err)
    if report:
        return report, None
    src = Source(units)
    for node in layer["nodes"]:
        check_node(src, node, misconceptions, report)
    check_graph(layer["nodes"], misconceptions, report)
    check_terms(layer["nodes"], report)
    cov = coverage(src, layer)
    for row in cov["rows"]:
        if not row["node_ids"] and not (row["reason"] or "").strip():
            report.add("error", "NOT_COVERED", row["unit_id"], f"{row['kind']} не попал ни в один узел",
                       row["page_pdf"])
        elif "непоказуем" in (row["reason"] or "").casefold():
            report.add("error", "BAD_REASON", row["unit_id"], "«непоказуемо» — не причина", row["page_pdf"])
    for x in layer.get("uncovered", []):
        if x["unit"] not in src.units or not needs_cover(src.units[x["unit"]]):
            report.add("error", "UNIT_UNKNOWN", "uncovered", f"нет единицы {x['unit']}")
    return report, cov
