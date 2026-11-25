"""python -m unittest discover tests   Текст главы здесь выдуманный, из книг ничего не взято."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "engine" / "video"))

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


class EnglishMeaning(unittest.TestCase):
    """Русский текст узла по английской цитате."""
    def codes(self, text, quote):
        from engine.check import meaning_suspects
        return {c for c, _ in meaning_suspects(text, quote)}

    def test_planted_errors(self):
        may = "Unless the pressure is bled off, the weakest rock may eventually be fractured."
        self.assertEqual(self.codes("Если давление не стравить, слабая порода может разорваться.", may), set())
        self.assertLessEqual({"HEDGE_LOST", "OVERGENERALIZED", "CONDITION_LOST"}, self.codes("Слабая порода всегда рвётся.", may))
        high = "The pressure on bottom is higher while circulating than with the pumps off."
        self.assertIn("POLARITY", self.codes("При циркуляции давление на забое ниже.", high))
        self.assertEqual(self.codes("При циркуляции давление на забое выше.", high), set())
        self.assertIn("NEGATION", self.codes("Диаметр важен.", "It doesn't depend on the hole diameter."))
        self.assertEqual(self.codes("Самый надёжный признак — прирост.", "The most reliable sign is a pit gain."), set())

    def test_formula_is_not_english(self):
        self.assertEqual(self.codes("Формула верна, когда t мало.", r"$$p = q t 	ag{1}$$"), set())

    def test_demo_chapter(self):
        text = (Path(__file__).parent / "demo_drilling_en.md").read_text(encoding="utf-8")
        units = build_units(text, {"id": "demo", "lang": "en"})
        count = lambda k: sum(u["type"] == k for u in units)
        self.assertEqual((count("formula"), count("example"), count("task"), count("table")), (3, 2, 3, 1))
        self.assertTrue(any(u["origin"] == "figure_ai" for u in units))

    def test_sentence_abbreviations(self):
        from engine.nodes import sentence
        self.assertEqual(sentence("As in Fig. A the mud, Eq. B, rises. Then it falls.", "As in"), "As in Fig. A the mud, Eq. B, rises.")


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

    def test_builder_survives_sloppy_answer(self):
        """null вместо пустого поля, единицы списком, битый узел — не повод ронять сборку всей главы."""
        from engine.nodes import Builder, sentence
        b = Builder({"id": "x", "book": "К"}, UNITS)
        good = {"id": "a", "title": "т", "novice": "н", "why": "п", "diff": ["М"], "topic": "о", "main": "с", "mechanism": [["абзац", [uid("formula")]]],
                "practice": None, "claims": [], "links": None, "misc": None, "data": ["", "", []], "analogy": ["", ""], "units": None, "terms": None, "video": None}
        layer = b.layer([{"nodes": [good, {"id": "b"}]}], "тест")
        self.assertEqual([n["id"] for n in layer["nodes"]], ["x.a"])
        self.assertTrue(any("узел b не собран" in p for p in b.problems))
        self.assertEqual(sentence("Раз два.\n- Три часто.", "Раз"), "Раз два.")
        self.assertEqual(sentence("- раз;\n- два.", "раз"), "раз;")

    def test_unknown_link_and_missing_analogy(self):
        from engine.nodes import Builder
        b = Builder({"id": "x", "book": "К"}, UNITS)
        n = b.node({"id": "a", "title": "т", "novice": "н", "why": "п", "diff": ["М"], "topic": "о", "main": "с", "claims": [],
                    "links": [["contrasts_with", "b"], ["prerequisite", "c"]], "analogy": None}, 1)
        self.assertEqual(n["links"], [{"type": "prerequisite", "target": "x.c"}])
        self.assertTrue(any("contrasts_with" in p for p in b.problems))
        self.assertEqual(n["it_analogy"]["text"], "")

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


class ReviewHints(unittest.TestCase):
    def test_analogy_without_limit(self):
        from engine.check import Source
        from engine.review import hints
        item = {"id": "A01", "type": "analogy", "text": "Раствор как очередь.", "breaks_where": None}
        self.assertTrue(any(h.startswith("ANALOGY") for h in hints(Source(UNITS), item, {})))


class Path_(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "engine"))
        import build_course
        self.b = build_course

    def nodes(self, n):
        return [{"id": f"n{i:02}", "title": f"Шаг {i}", "title_novice": f"Шаг {i}", "claims": [{"unit": f"p001.{i:02}"}], "units": []} for i in range(n)]

    def test_parts_by_headings(self):
        rows = [{"unit_id": f"p001.{i:02}", "kind": "heading", "excerpt": t} for i, t in ((0, "# § 1. ВВЕДЕНИЕ В ТЕМУ"), (4, "## § 2. Вторая часть"), (6, "# Задачи"))]
        parts = self.b.chapter_parts(self.nodes(9), rows)
        self.assertEqual([(p["mark"], p["title"], len(p["nodes"])) for p in parts], [("§1", "Введение в тему", 4), ("§2", "Вторая часть", 5)])

    def test_parts_without_headings_and_long_part(self):
        parts = self.b.chapter_parts(self.nodes(20), [])
        self.assertEqual([len(p["nodes"]) for p in parts], [8, 8, 4])
        long = self.b.chapter_parts(self.nodes(32), [{"unit_id": "p001.00", "kind": "heading", "excerpt": "# 1.1 Один"}, {"unit_id": "p001.30", "kind": "heading", "excerpt": "# 1.2 Два"}])
        self.assertEqual(sum(len(p["nodes"]) for p in long), 32)
        self.assertTrue(all(len(p["nodes"]) <= 14 for p in long))


class TermHelp(unittest.TestCase):
    def test_words_do_not_give_the_answer_away(self):
        sys.path.insert(0, str(ROOT / "engine"))
        import build_course as b
        gl = {"водоотдача": "сколько жидкости раствор отдаёт в породу", "биостром": "пласт из остатков организмов", "вторая фаза": "начинается, когда граница достигла края пласта"}
        one = {"type": "single", "prompt": "Что будет при высокой водоотдаче?", "answer": "a", "options": [{"id": "a", "text": "Толстая корка"}]}
        self.assertEqual([t for t, _ in b.term_help(one, gl)], ["водоотдача"])
        two = {"type": "single", "prompt": "Это биостром?", "answer": "a", "options": [{"id": "a", "text": "Биостром"}]}
        self.assertEqual(b.term_help(two, gl), [])
        three = {"type": "single", "prompt": "Когда начинается вторая фаза?", "answer": "a", "options": [{"id": "a", "text": "Граница достигла края пласта"}]}
        self.assertEqual(b.term_help(three, gl), [])


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


class Domain(unittest.TestCase):
    def test_colors_reach_styleguide(self):
        import tempfile
        from engine.domain_fill import merge
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "styleguide.json").write_text("{}", encoding="utf-8")
            merge(folder, {"colors": [{"name": "kick", "color": "#E74C3C", "why": "газ"}, {"name": "bad", "color": "red"}]}, set())
            style = json.loads((folder / "styleguide.json").read_text(encoding="utf-8"))
            self.assertEqual(style["domain"], {"kick": {"color": "#E74C3C", "ru": "газ"}})

    def test_merge_adds_and_checks(self):
        import tempfile
        from engine.domain_fill import merge, rows
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "x"
            ans = {"glossary": [{"ru": "Раствор", "note": "жидкость", "page": 9}, {"ru": "Шлам", "note": "о", "page": 99}],
                   "misconceptions": [{"id": "misc.a", "text": "т"}, {"id": "b", "text": "т"}],
                   "it_bridges": [{"term": "x", "analogy": "а"}]}
            added, errors = merge(folder, ans, {8, 9})
            self.assertEqual(added, {"glossary": 1, "misconceptions": 1})
            self.assertEqual(len(errors), 3)
            self.assertEqual(merge(folder, ans, {8, 9})[0], {})
            self.assertEqual([x["id"] for x in rows(folder, "misconceptions")], ["misc.a"])


class Pictures(unittest.TestCase):
    def test_text_readable_on_phone(self):
        """На экране 390 px картинке достаётся около 358 px: подпись в ней не мельче 16 px."""
        import re
        small = []
        for p in (ROOT / "data").glob("*/illustrations/*.svg"):
            s = p.read_text(encoding="utf-8")
            width = float(re.search(r'viewBox="0 0 ([0-9.]+)', s).group(1))
            sizes = [float(x) for x in re.findall(r'font-size="([0-9.]+)"', s)]
            if sizes and min(sizes) * 358 / width < 16:
                small.append(f"{p.name}: {min(sizes) * 358 / width:.1f} px")
        self.assertEqual(small, [])

    def test_grid_gap_is_joined(self):
        sys.path.append(str(ROOT / "engine" / "figures"))
        sys.path.append(str(ROOT / "engine"))
        import redraw
        ink = [[[.5, 90], [.5, 99.8]], [[.51, 100.2], [.6, 110]], [[.1, 95], [.1, 96]], [[.1, 97], [.1, 98]]]
        self.assertEqual(len(redraw.joined(ink, [100], 50)), 3)   # сшита линия у сетки, штрихи книги остались штрихами


class Video(unittest.TestCase):
    LAYER = {"nodes": [{"id": "x.a", "claims": [{"id": "x.a#c1", "text": "Мокрый песок темнее при 15 % влажности.", "quote": "при 15 % влажности"}]}]}

    def doc(self, **k):
        line = "Мокрый песок темнее сухого, и это видно каждому на любом пляже после дождя"
        script = [{"text": "Почему мокрый песок темнее?", "claim_id": "x.a#c1", "beat": {"head": "Почему *темнее?*"}}]
        script += [{"text": line, "claim_id": "x.a#c1", "beat": {"head": "Темнее"}} for _ in range(6)]
        script += [{"text": "Что будет дальше?", "claim_id": "x.a#c1", "prediction": True, "beat": {"head": "Что дальше?"}},
                   {"text": "А в ваших данных?", "claim_id": "x.a#c1", "beat": {"head": "А у вас?"}}]
        d = {"video_id": "v", "chapter": "x", "node_id": "x.a", "format": "short", "scene": "log_run", "script": script, "params": {"depth": 1},
             "exaggerations": ["нет преувеличений"], "prediction_question": "?", "transfer_question": "?", "data_it_bridge": "мост",
             "physics": {"pc.depth_down": ["да", "x"]}}
        d.update(k)
        return d

    def test_good_script(self):
        import plan
        errors, warn = plan.check(self.doc(), self.LAYER)
        self.assertEqual((errors, warn), ([], []))

    def test_bad_script(self):
        import plan
        d = self.doc()
        d["script"][0]["text"] = "Песок темнее."
        d["script"][1]["text"] = "слово " * 19
        d["script"][2] = {"text": "При 40 процентах песок чёрный", "claim_id": "x.a#c1", "beat": {"head": "κ = 5"}}
        d["script"][3]["claim_id"] = "x.a#c9"
        errors, warn = plan.check(d, self.LAYER)
        for part in ("не вопрос", "максимум 18", "греческая", "нет утверждения x.a#c9"):
            self.assertTrue(any(part in e for e in errors), part)
        self.assertTrue(any("40" in w for w in warn))

    def test_live_animation_checked(self):
        import live_anim
        ok = {"bases": {"b": {"scene": "curve", "params": {"assumptions": ["условно"]}}},
              "nodes": {"x.a": {"base": "b", "what": "песок", "script": [{"head": "Сухой *песок*", "claim": "c1", "beat": {}}, {"head": "Мокрый темнее", "claim": "c1", "beat": {}}]}}}
        self.assertEqual(live_anim.check(ok, self.LAYER), [])
        bad = copy.deepcopy(ok)
        bad["nodes"]["x.a"]["script"][0] = {"head": "κ = 5", "claim": "c7", "beat": {}}
        bad["nodes"]["x.a"]["params"] = {"assumptions": []}
        errs = " ".join(live_anim.check(bad, self.LAYER))
        for part in ("нет утверждения c7", "формула", "допущения"):
            self.assertIn(part, errs)

    def test_asr_compares_words(self):
        import asr
        errs, diff = asr.align(asr.norm("Плотный известняк, 2 раза!"), asr.norm("плотный известник два раза"))
        self.assertEqual((errs, diff), (1, [("известняк", "известник")]))

    def test_changed_claim_replaces_phrase(self):
        import make_video
        spec = {"script": [{"text": "Старый текст", "claim_id": "x.a#c1"}], "claims_at": {"x.a#c1": "Старое утверждение"}}
        make_video.follow_layer(spec, {"x.a#c1": {"text": "Новое утверждение"}}, Path("."))
        self.assertEqual(spec["script"][0]["text"], "Новое утверждение")


class Math(unittest.TestCase):
    def ok(self, tex, *parts):
        import xml.etree.ElementTree as ET
        from engine.mathml import convert
        got = convert(tex)
        self.assertTrue(got.startswith("<math"), got)
        ET.fromstring(got)
        for p in parts:
            self.assertIn(p, got)

    def test_formulas(self):
        self.ok(r"$$\frac{\partial p}{\partial t} = \kappa \frac{\partial^2 p}{\partial x^2}. \quad (23.19)$$", "<mfrac>", "κ")
        self.ok(r"\[ \eta_ {\mathrm{np}} ^ {*} = \mathrm{Q} ^ {*} / \Delta p \tag {1.1} \]", "<msubsup>", "(1.1)")
        self.ok(r"$p = \left[ 1 - e^{-x^2/4} \right] \sqrt{2t}$", "<msqrt>")
        self.ok(r"$$\begin{aligned} a &= b; \\ c &= 2,5 \end{aligned}$$", "<mtable", "<mn>2,5</mn>")
        self.ok(r"$\int_0^{\infty} \rho \, dp \geqslant 0$", "∫", "≥")

    def test_broken_stays_code(self):
        from engine.mathml import convert, rich
        self.assertEqual(convert(r"$\frac{1}{$"), r"<code>\frac{1}{</code>")
        self.assertEqual(convert(r"$\неведома$")[:6], "<code>")
        self.assertEqual(rich("a < b"), "a &lt; b")
        self.assertIn("<math", rich(r"где \( k_{n} \) и <b>"))
        self.assertIn("&lt;b&gt;", rich(r"где \( k_{n} \) и <b>"))


class Tasks(unittest.TestCase):
    def make(self, **change):
        from engine import tasks
        base = {"s": "wet_sand", "c": [1], "t": "single", "k": "understanding", "q": "Что с песком?",
                "o": ["Мокрый темнее", "Мокрый светлее", "Цвет не меняется"], "e": "Влага."}
        doc, problems = tasks.build(make_layer(), {"tasks": [{**base, **change}]})
        return doc, problems, [m for _, i, m in tasks.check(make_layer(), doc) if i != "задания"]

    def test_good(self):
        doc, problems, bad = self.make()
        t = doc["tasks"][0]
        self.assertEqual((problems, bad), ([], []))
        self.assertEqual(next(o["text"] for o in t["options"] if o["id"] == t["answer"]), "Мокрый темнее")

    def test_bad_keys_are_found(self):
        for change, part in (({"o": ["Нет", "Мокрый песок обычно темнее сухого", "Да"]}, "верное утверждение"),
                             ({"q": "Что верно для шага?"}, "из какого шага"),
                             ({"o": ["Мокрый темнее…", "Б", "В"]}, "многоточием"),
                             ({"o": ["При 99 % темнее", "Б", "В"]}, "числа, которых нет"),
                             ({"t": "order", "o": ["Признак: а", "Правило: б", "Вывод: в"]}, "выдаёт порядок"),
                             ({"t": "gap", "q": "Песок {{1}}", "a": ["зелёный"], "o": []}, "нет в тексте"),
                             ({"t": "multiple", "n": 1}, "от двух верных"),
                             ({"ev": "чего нет"}, "evidence")):
            with self.subTest(part):
                self.assertTrue(any(part in m for m in self.make(**change)[2]), self.make(**change)[2])

    def test_calc_is_recomputed(self):
        ok = {"t": "calc", "o": [], "a": 9, "f": "13.5-4.5", "u": "м"}
        self.assertEqual(self.make(**ok)[1], [])
        self.assertTrue(self.make(**{**ok, "a": 8})[1])
        with self.assertRaises(ValueError):
            self.make(**{**ok, "f": "__import__('os')"})


if __name__ == "__main__":
    unittest.main()