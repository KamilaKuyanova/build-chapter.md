"""python -m unittest discover tests   Текст главы здесь выдуманный, из книг ничего не взято."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.check import check_layer  # noqa: E402
from engine.textnorm import norm_quote, numbers  # noqa: E402
from engine.units import build_units, needs_cover  # noqa: E402

BOOK = """<!-- page 7 -->
Чужая глава.
<!-- page 8 -->
# Глава 1

Мокрый песок обычно темнее сухого при 15 % влажности, и это видно сразу после дож-
<!-- page 9 -->
дя на любом пляже.

$$
V = 2,5 \\cdot 10^{-3}
$$

----
━━━ FORMAT 6: XY PLOT ━━━
Кривая плавно растёт слева направо до 77 единиц.
KEYWORDS: песок
----

Рис. 1. Цвет песка

Пример 1. Найти цвет песка при 15 % влажности.

Решение. Песок тёмный.

# Задачи

1. Назвать цвет сухого песка.
2. Назвать цвет мокрого песка.

9
<!-- page 10 -->
# Глава 2
"""
SPEC = {"id": "t", "lang": "ru", "parts": [{"pages": [8, 10], "start": "^# Глава 1", "stop": "^# Глава 2"}]}
SCHEMAS = {"node": json.loads((ROOT / "schema" / "official" / "node.schema.json").read_text(encoding="utf-8"))}
UNITS = build_units(BOOK, SPEC)


def uid(kind, n=0):
    return [u["id"] for u in UNITS if u["type"] == kind][n]


def make_layer():
    field = lambda text: {"text": text, "by_model": True}
    units = [uid("paragraph", i) for i in range(3)] + [uid("formula"), uid("figure")]
    node = {
        "id": "t.wet_sand", "order": 1, "title": "Мокрый песок темнее", "why_here": field("Первый узел"),
        "difficulty": {"primary": "М", "secondary": None}, "threshold": False, "pages": [8, 9], "units": units,
        "layers": {"topic": field("Цвет песка"), "main": field("Мокрый песок обычно темнее при 15 %."),
                   "mechanism": field("Влага меняет цвет."), "practice": field("Смотрят на цвет."),
                   "nuances": field("Это видно после дождя на любом пляже."), "deeper": []},
        "claims": [{"id": "t.wet_sand#c1", "kind": "observation", "text": "Мокрый песок обычно темнее сухого",
                    "quote": "Мокрый песок обычно темнее сухого", "page_pdf": 8, "source_kind": "text",
                    "by_model": True}],
        "links": [], "data_meaning": {"from_chapter": field("Цвет — признак влажности"),
                                      "breaks": field("Другой песок"), "hypotheses": []},
        "it_analogy": {"text": "Признак", "breaks_where": "У песка причина физическая", "by_model": True},
        "terms_introduced": [], "misconception": {"ref": "misc.sand", "text": "Песок не темнеет", "by_model": True},
        "decision_on_data": {"features": ["цвет"], "rule": "тёмный — мокрый", "conclusion": "мокрый"},
        "worked_examples": [{"number": "1", "page_pdf": 9, "condition": "влажность 15 %", "steps": ["смотрим"],
                             "result": "тёмный"}],
        "book_tasks": [{"number": str(i), "page_pdf": 9, "text": "Цвет"} for i in (1, 2)],
    }
    return {"chapter": "t", "source": "t.md", "nodes": [node], "uncovered": []}

class Units(unittest.TestCase):
    def test_bounds_and_types(self):
        kinds = [u["type"] for u in UNITS]
        self.assertNotIn("Чужая", " ".join(u["text"] for u in UNITS))
        self.assertEqual(kinds.count("task"), 2)
        for k in ("formula", "figure", "figure_desc", "example", "service"):
            self.assertEqual(kinds.count(k), 1, k)

    def test_figure_ai_is_not_author(self):
        fig = next(u for u in UNITS if u["type"] == "figure_desc")
        self.assertEqual(fig["origin"], "figure_ai")
        self.assertFalse(needs_cover(fig))

    def test_garbled(self):
        bad = BOOK.replace("1. Назвать цвет сухого песка.", "1. OchoBbIBaacb pe3yIbTaTax peHHeHH npeIbIyIeH 3aJaH BbIHcJIHTb")
        self.assertEqual([u["type"] for u in build_units(bad, SPEC) if u.get("ocr_suspect")], ["task"])
        self.assertFalse(any(u.get("ocr_suspect") for u in UNITS))

    def test_figure_without_closing_fence(self):
        units = build_units(BOOK.replace("KEYWORDS: песок\n----\n", "KEYWORDS: песок\n"), SPEC)
        self.assertEqual([u["type"] for u in units].count("task"), 2)
        self.assertEqual([u["type"] for u in units].count("example"), 1)

    def test_numbered_steps_after_tasks_are_not_tasks(self):
        units = build_units(BOOK.replace("\n9\n", "\nПорядок работы.\n\n1. Взять песок.\n\n9\n"), SPEC)
        self.assertEqual([u["type"] for u in units].count("task"), 2)

    def test_less_than_is_not_a_tag(self):
        self.assertEqual(norm_quote("если a < b и c > d, то да"), "если a < b и c > d, то да")

    def test_shared_fence(self):
        two = BOOK.replace("KEYWORDS: песок", "----\n━━━ FORMAT 13: LEGEND ━━━\nШтриховка.\nKEYWORDS: песок")
        units = build_units(two, SPEC)
        self.assertEqual(sum(u["type"] == "figure_desc" for u in units), 2)
        self.assertFalse(any("Штриховка" in u["text"] for u in units if u["origin"] == "author"))


EN_BOOK = """<!-- page 3 -->
# 2.1 Kick Detection

An increase in pit volume usually indicates an influx, e.g. gas, when the pumps run at 1,250 psi
(see Fig. 2.4). The driller should not ignore it.

Figure 2.4. Pit volume versus time.

Example 2.1. Estimate the gain for 85.5 bbl.

# Problems

1. Define a kick.
2. What does a pit gain mean?
"""


class English(unittest.TestCase):
    def test_english_chapter(self):
        from engine.check import Source, Report, check_numbers, check_quote
        from engine.nodes import locate
        units = build_units(EN_BOOK, {"id": "en", "lang": "en"})
        kinds = [u["type"] for u in units]
        for k, n in (("task", 2), ("figure", 1), ("example", 1), ("paragraph", 1)):
            self.assertEqual(kinds.count(k), n, k)
        self.assertFalse(any(u.get("ocr_suspect") for u in units))
        src, rep, p = Source(units), Report(), units[kinds.index("paragraph")]
        unit, quote = locate(src.units, p["id"], "An increase in pit volume")
        self.assertTrue(quote.endswith("(see Fig. 2.4)."))
        check_quote(src, quote, 3, "x", rep)
        check_numbers(src, "Давление насосов 1250 psi", [p["id"]], "x", 3, rep)
        self.assertEqual(rep, [])
        check_numbers(src, "Давление насосов 1251 psi", [p["id"]], "x", 3, rep)
        self.assertEqual(len(rep), 1)


class Norm(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(numbers("4—8 см³, 2,50 и 10⁻¹⁵"), {"4", "8", "3", "2.5", "10", "15"})

    def test_quote(self):
        self.assertEqual(norm_quote("**Рост**  — «да»"), norm_quote("рост – “да”"))


class Check(unittest.TestCase):
    def codes(self, change=lambda layer, node: None):
        layer = make_layer()
        change(layer, layer["nodes"][0])
        report, _ = check_layer(UNITS, layer, SCHEMAS, {"misc.sand"})
        return [r["code"] for r in report]

    def test_clean(self):
        self.assertEqual(self.codes(), [])

    def test_seeded_errors(self):
        c = lambda n: n["claims"][0]
        link = lambda kind, to: lambda l, n: n["links"].append({"type": kind, "target": to})
        cases = {
            "QUOTE_NOT_FOUND": lambda l, n: c(n).update(quote="Мокрый песок светлее сухого"),
            "QUOTE_WRONG_PAGE": lambda l, n: c(n).update(page_pdf=10),
            "QUOTE_NOT_VERBATIM": lambda l, n: c(n).update(quote="**Мокрый** песок обычно темнее"),
            "QUOTE_OVER_PAGES": lambda l, n: c(n).update(quote="видно сразу после дождя на любом"),
            "QUOTE_FROM_FIGURE_AI": lambda l, n: c(n).update(quote="Кривая плавно растёт слева направо"),
            "QUOTE_TOO_SHORT": lambda l, n: c(n).update(quote="Мокрый песок"),
            "FIGURE_NEEDS_SCAN": lambda l, n: c(n).update(source_kind="figure_description_model"),
            "NUMBER_NOT_IN_SOURCE": lambda l, n: c(n).update(text="Мокрый песок обычно темнее при 51 %"),
            "NOT_COVERED": lambda l, n: n["book_tasks"].pop(),
            "BAD_REASON": lambda l, n: (n["units"].remove(uid("formula")), l["uncovered"].append(
                {"unit": uid("formula"), "reason": "Непоказуемо"})),
            "UNIT_UNKNOWN": lambda l, n: n["units"].append("p999.01"),
            "TASK_UNKNOWN": lambda l, n: n["book_tasks"][0].update(number="77"),
            "TASK_PAGE": lambda l, n: n["book_tasks"][0].update(page_pdf=8),
            "CLAIM_ID": lambda l, n: c(n).update(id="t.other#c1"),
            "OVERGENERALIZED": lambda l, n: c(n).update(text="Мокрый песок всегда темнее сухого"),
            "HEDGE_LOST": lambda l, n: c(n).update(text="Мокрый песок темнее сухого"),
            "NEGATION": lambda l, n: c(n).update(text="Мокрый песок обычно не темнее сухого"),
            "LINK_UNKNOWN": link("example_of", "t.x"),
            "MISC_UNKNOWN": link("refutes_misconception", "misc.none"),
            "ANALOGY_WITHOUT_LIMIT": lambda l, n: n["it_analogy"].update(breaks_where="нет"),
            "NO_DECISION": lambda l, n: n.update(decision_on_data=None),
            "SCHEMA": lambda l, n: n.pop("links"),
        }
        for code, change in cases.items():
            with self.subTest(code):
                self.assertIn(code, self.codes(change))

    def test_order(self):
        def f(layer, n):
            m = copy.deepcopy(n)
            m.update(id="t.second", order=2, terms_introduced=["влага"])
            m["claims"][0]["id"] = "t.second#c1"
            n["links"] = [{"type": "prerequisite", "target": "t.second"}]
            layer["nodes"].append(m)
        self.assertLessEqual({"PREREQ_AFTER", "TERM_BEFORE_DEFINED"}, set(self.codes(f)))

    def test_coverage_matches_schema(self):
        from engine.schema import validate
        _, cov = check_layer(UNITS, make_layer(), SCHEMAS)
        schema = json.loads((ROOT / "schema" / "official" / "coverage.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate(cov, schema), [])


class Nodes(unittest.TestCase):
    def test_sentence_and_locate(self):
        from engine.nodes import locate, sentence
        self.assertEqual(sentence("Раз. Два (см. рис. 5) и три. Четыре.", "Два"), "Два (см. рис. 5) и три.")
        self.assertIsNone(sentence("Раз.", "Нет"))
        by_id = {u["id"]: u for u in UNITS}
        unit, quote = locate(by_id, uid("formula"), "Мокрый песок")
        self.assertEqual((unit["page"], quote[:12]), (8, "Мокрый песок"))
        self.assertIsNone(locate(by_id, uid("formula"), "Кривая плавно")[1])

    def test_chunks_lose_nothing(self):
        from engine.nodes import chunks
        got = [u["id"] for c in chunks(UNITS) for u in c]
        self.assertEqual(got, [u["id"] for u in UNITS if u["origin"] != "service"])

    def test_terms_move_to_first_use(self):
        from engine.nodes import hoist_terms
        make = lambda text, terms: {"layers": {k: {"text": text if k == "main" else ""} for k in (
            "topic", "main", "mechanism", "practice", "nuances")}, "terms_introduced": list(terms),
            "glossary": [{"term": t, "definition": "о"} for t in terms]}
        nodes = [make("Здесь есть Влага и пляж.", []), make("Песок.", []), make("Влага, соль.", ["влага", "соль"])]
        hoist_terms(nodes)
        self.assertEqual([n["terms_introduced"] for n in nodes], [["влага"], [], ["соль"]])

    def test_small_tail_joins_last_chunk(self):
        from engine.nodes import CHUNK, chunks
        unit = lambda i, n: {"id": f"p001.{i:02d}", "page": 1, "type": "paragraph", "origin": "author", "text": "Я" * n + "."}
        units = [unit(i, CHUNK // 2) for i in range(1, 8)] + [unit(9, 100)]
        parts = chunks(units)
        self.assertEqual([u["id"] for c in parts for u in c], [u["id"] for u in units])
        self.assertGreater(len(parts), 2)

    def test_routing_matches_schema(self):
        from engine.route import route
        from engine.schema import validate
        layer = make_layer()
        layer["nodes"][0]["video_scores"] = dict.fromkeys(
            ("time", "invisible", "scale", "counterintuitive", "cause_effect"), 1)
        schema = json.loads((ROOT / "schema" / "official" / "routing.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate(route(layer), schema), [])


class Review(unittest.TestCase):
    def test_bad_remarks_are_dropped(self):
        from engine.review import assemble
        item = {"id": "C1", "type": "claim", "text": "", "page_pdf": 8, "quote": ""}
        pack = {"package_id": "x", "items": [item], "frames": []}
        good = {"target": "C1", "category": "other", "severity": "minor", "problem": "п", "fix": "и",
                "q": [uid("paragraph"), "Мокрый песок"]}
        out, dropped = assemble(pack, UNITS, [{"remarks": [{**good, "target": "C9"}, {**good, "q": ["p008.01", "Нет слов"]},
                                                           good, good]}], "t")
        self.assertEqual([(r["target"], r["page_pdf"]) for r in out["remarks"]], [("C1", 8)])
        self.assertEqual(len(dropped), 3)


class Formulas(unittest.TestCase):
    def test_builder_takes_formula_and_table(self):
        from engine.nodes import Builder
        b = Builder({"id": "t", "book": "t.md"}, UNITS)
        a = {"id": "x", "title": "Песок", "novice": "Про мокрый песок", "why": "так", "diff": ["Ф"], "topic": "т",
             "main": "м", "claims": [], "data": ["", "", []], "analogy": ["", ""], "video": [0] * 5,
             "formulas": [[uid("formula"), "объём", [["V", "объём"]]]],
             "tables": [["Таблица 1", "p999.01"]]}
        n = b.node(a, 1)
        self.assertEqual(n["formulas"][0]["variables"], [{"symbol": "V", "meaning": "объём", "unit": None}])
        self.assertIn(uid("formula"), n["units"])
        self.assertEqual(n["tables"], [])
        self.assertIn("p999.01", b.problems[0])


if __name__ == "__main__":
    unittest.main()