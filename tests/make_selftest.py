#!/usr/bin/env python3
"""Самотест ШАБЛОНА курса в официальных форматах (не контент главы). Нейтральное школьное содержимое, вымышленные
цитаты и страницы: проверяет вёрстку и правила сборщика. Пишет data_selftest/ (в сдачу не входит)."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data_selftest"
D.mkdir(exist_ok=True)
CH = "selftest_ch1"

(D / "chart.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 160" role="img" aria-label="График">'
    '<rect width="320" height="160" fill="#1A2129"/><polyline fill="none" stroke="#F1C40F" stroke-width="3" '
    'points="20,130 80,100 140,80 200,50 260,30"/><text x="20" y="150" font-size="12" fill="#ECEFF4">время</text></svg>',
    encoding="utf-8")


def fld(t, **kw):
    d = {"text": t, "by_model": False}
    d.update(kw)
    return d


def node(order, nid, title, intro_terms, used, decision=False):
    cid = f"{nid}#c1"
    n = {
        "id": nid, "order": order, "title": title, "why_here": fld("Порядок самотеста."),
        "difficulty": {"primary": "П", "secondary": None}, "threshold": False, "pages": [10 + order],
        "layers": {"topic": fld("Тема самотеста"), "main": fld("Суть самотеста: сложение двух чисел.", claim_ids=[cid]),
                   "mechanism": fld("Мы складываем 2 и 3, получаем 5.", claim_ids=[cid]),
                   "practice": fld("Сумму 5 используют в примерах.", claim_ids=[cid]),
                   "nuances": fld("Порядок слагаемых не важен.", claim_ids=[cid]), "deeper": []},
        "claims": [{"id": cid, "text": "Два плюс три равно пяти.", "kind": "observation", "page_pdf": 10 + order,
                    "page_print": None, "quote": "Два плюс три равно пяти.", "source_kind": "text", "by_model": False}],
        "links": [] if order == 1 else [{"type": "prerequisite", "target": "selftest.a"}],
        "misconception": {"ref": "misc.log_is_rock", "text": "Кривая — не порода.", "by_model": False},
        "data_meaning": {"from_chapter": fld("Число в данных — отклик, а не сама величина."),
                         "breaks": fld("Если шум велик, сумма неточна."), "hypotheses": []},
        "it_analogy": {"text": "Сумма как агрегат в SQL.", "breaks_where": "SQL не знает физических единиц.", "by_model": False},
        "now_practice": None, "inefficiency_lens": None,
        "terms_introduced": intro_terms, "terms_used": used, "needs_scan": [],
        "decision_on_data": ({"features": ["значение растёт"], "rule": "рост значит положительный тренд",
                              "conclusion": "тренд положительный", "counterexample": "шум"} if decision else None),
        "worked_examples": [{"page_pdf": 10 + order, "condition": "Сложить 2 и 3.", "steps": ["Берём 2", "Прибавляем 3"], "result": "5"}],
        "book_tasks": [{"number": "1", "page_pdf": 10 + order, "text": "Сложить 4 и 4.", "figure": None}],
    }
    return n


layer = {"chapter": CH, "source": "selftest.md", "generated_by": "самотест",
         "nodes": [node(1, "selftest.a", "Самотест: сложение", ["сумма"], []),
                   node(2, "selftest.b", "Самотест: решение на данных", ["тренд"], ["сумма"], decision=True)]}

EV = "Два плюс три равно пяти."


def task(i, nid, ty, prompt, **kw):
    t = {"id": f"{nid}.t{i}", "type": ty, "step_id": nid, "claim_ids": [f"{nid}#c1"], "prompt": prompt,
         "explanation": "Пояснение в одну фразу.", "kind": "recall", "evidence": EV}
    t.update(kw)
    return t


def tasks_for(nid):
    o = lambda *ts: [{"id": f"o{i}", "text": s, "misconception": None} for i, s in enumerate(ts, 1)]
    return [
        task(1, nid, "single", "Сколько будет два плюс три?", options=o("четыре", "пять", "шесть"), answer="o2"),
        task(2, nid, "single", "Что верно про сумму?", options=o("она равна пяти", "она равна семи"), answer="o1"),
        task(3, nid, "multiple", "Что входит в сумму?", options=o("два", "три", "семь", "девять"), answer=["o1", "o2"]),
        task(4, nid, "multiple", "Выберите верные.", options=o("пять", "равно", "тысяча"), answer=["o1", "o2"]),
        task(5, nid, "order", "Расставьте по порядку.", options=o("Берём 2", "Прибавляем 3", "Получаем 5"), answer=["o1", "o2", "o3"],
             evidence="Берём 2 Прибавляем 3"),
        task(6, nid, "gap", "Два плюс три равно {{1}}.", answer=["пяти"]),
        task(7, nid, "calc", "Сколько будет 2 + 3?", answer=5, tolerance=0.01, unit="", evidence="получаем 5"),
        task(8, nid, "calc", "Сложите 2 и 3.", answer=5, tolerance=0.01, unit="", evidence="получаем 5"),
    ]


tasks = {"chapter": CH, "tasks": tasks_for("selftest.a") + tasks_for("selftest.b")}
ill = {"chapter": CH, "illustrations": [
    {"id": f"i{k}", "step_id": nid, "file": "chart.svg", "frame_class": "A", "origin": "code_from_data",
     "label": "реальные данные", "caption": "Линия растёт слева направо.", "alt": "Линия растёт слева направо", "source": "самотест",
     "claim_ids": [f"{nid}#c1"]} for k, nid in enumerate(["selftest.a", "selftest.b"], 1)]}
routing = {"chapter": CH, "routes": [
    {"node_id": nid, "format": "текст", "video_scores": {"time": 0, "invisible": 0, "scale": 0, "counterintuitive": 0, "cause_effect": 0},
     "why": "самотест"} for nid in ("selftest.a", "selftest.b")]}
for name, data in (("layer", layer), ("tasks", tasks), ("illustrations", ill), ("routing", routing)):
    (D / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print("Самотест сгенерирован:", D)
