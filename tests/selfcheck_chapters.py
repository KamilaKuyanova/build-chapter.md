"""Самопроверка на настоящих главах: python tests/selfcheck_chapters.py

Каждая фраза автора берётся как цитата. Верные обязаны пройти без тревог,
испорченные (чужое число, чужая страница, описание рисунка) обязаны быть найдены.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from engine.check import Report, Source, check_numbers, check_quote  # noqa: E402
from engine.textnorm import norm_quote, numbers, words  # noqa: E402


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[А-ЯA-Z])", text) if len(words(s)) >= 6]


def codes(fn, *args):
    report = Report()
    fn(*args, report)
    return [r["code"] for r in report]


for path in sorted(ROOT.glob("work/*/units.json")):
    units = json.loads(path.read_text(encoding="utf-8"))
    src = Source(units)
    pages = sorted(src.author)
    total = false_alarm = wrong_page = page_hit = num = num_hit = fig = fig_hit = 0
    for u in units:
        for s in sentences(u["text"]):
            if u["origin"] == "figure_ai":
                if not src.find(norm_quote(s)):
                    fig += 1
                    fig_hit += bool(codes(check_quote, src, s, u["page"], "x"))
            if u["origin"] != "author" or u["type"] not in ("paragraph", "example", "task"):
                continue
            total += 1
            bad = codes(check_quote, src, s, u["page"], "x")
            bad += codes(lambda t, r: check_numbers(src, t, [u["id"]], "x", u["page"], r), s)
            if bad:
                false_alarm += 1
                print("  ложная тревога", u["id"], bad, s[:90])
            far = next((p for p in pages if abs(p - u["page"]) > 2 and p not in src.find(norm_quote(s))), None)
            if far and len(src.find(norm_quote(s))) == 1:
                wrong_page += 1
                page_hit += "QUOTE_WRONG_PAGE" in codes(check_quote, src, s, far, "x")
            if numbers(s):
                num += 1
                broken = re.sub(r"\d+", lambda m: m.group(0) + "7", s, count=1)
                if numbers(broken) - numbers(u["text"]):
                    num_hit += "NUMBER_NOT_IN_SOURCE" in codes(
                        lambda t, r: check_numbers(src, t, [u["id"]], "x", u["page"], r), broken)
                else:
                    num -= 1
    print(f"{path.parent.name}: фраз {total}, ложных тревог {false_alarm}; чужая страница {page_hit}/{wrong_page}; "
          f"чужое число {num_hit}/{num}; описание рисунка вместо автора {fig_hit}/{fig}")
