#!/usr/bin/env python3
"""Самотест ШАБЛОНА курса (не контент главы!).

Генерирует data_selftest/nodes/*.json с нейтральным школьным содержимым (не геология),
чтобы проверить: 15+ заданий, все 5 типов, шаг «решение на данных», иллюстрация с alt,
«стр. N» у абзацев. Цитаты и страницы здесь вымышленные: это проверка вёрстки и правил
сборщика, а не материал для жюри. Папка data_selftest не используется в сдаче.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "data_selftest" / "nodes"
D.mkdir(parents=True, exist_ok=True)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 160" role="img" aria-label="Линейный график">
<rect width="320" height="160" fill="#ffffff" stroke="#999"/>
<polyline fill="none" stroke="#1f5f8b" stroke-width="3" points="20,130 80,100 140,80 200,50 260,30"/>
<text x="20" y="150" font-size="12" fill="#333">время</text></svg>"""
(D / "chart.svg").write_text(SVG, encoding="utf-8")


def claims(prefix):
    return [{"id": f"{prefix}{i}", "kind": k, "text": t, "quote": "Вымышленная цитата для самотеста",
             "page": 10 + i, "origin": "author"}
            for i, (k, t) in enumerate([("observation", "Наблюдение самотеста"),
                                        ("conclusion", "Вывод самотеста"),
                                        ("assumption", "Допущение самотеста")], start=1)]


def node(nid, order, title, prefix, exercises, data=False):
    n = {
        "_selftest": True, "id": nid, "order": order, "title": title, "book_title": "Самотест шаблона",
        "difficulty": {"primary": "procedure"},
        "core": {
            "essence": {"text": "Суть: проверяем, что шаблон показывает страницу у каждого абзаца.", "claims": [prefix + "1"]},
            "mechanism": {"text": "Механизм самотеста: текст берётся из узла, а не из вёрстки вручную.", "claims": [prefix + "1"]},
            "practice": {"text": "Практика: сборщик помечает абзацы без источника красным.", "claims": [prefix + "2"]},
            "nuances": {"text": "Нюанс: страница у утверждения обязательна.", "claims": [prefix + "3"]},
        },
        "claims": claims(prefix),
        "misconception": "Заблуждение самотеста: страницы можно не указывать",
        "data_meaning": "Для данных: без страницы утверждение нельзя проверить.",
        "it_analogy": {"analogy": "Ссылка на источник — как комментарий с адресом в коде.", "breaks_where": "Страница книги не заменяет проверку смысла."},
        "worked_examples": [{"condition": "Условие самотеста: 2 + 3", "steps": ["Складываем", "Получаем 5"], "result": "5", "page": 11}],
        "book_problems": [{"number": "1", "text": "Задача самотеста", "figure": "рис. 1", "page": 12}],
        "links": [] if order == 1 else [{"to": "selftest.01", "type": "prerequisite"}],
        "illustrations": [{"file": "chart.svg", "alt": "Линия растёт слева направо", "class": "A", "label": "схема",
                            "caption": "Схема самотеста, нарисована кодом."}],
        "exercises": exercises,
    }
    if data:
        n["data_step"] = True
        n["data_solution"] = {"task": "Решение на данных (самотест).", "features": ["Значение растёт со временем"],
                              "rule": "Если значение растёт, тренд положительный.", "conclusion": "Тренд положительный.",
                              "breaks": "Один шумный отсчёт может обмануть."}
    return n


def ex(i, t, prefix, **kw):
    d = {"id": f"{prefix}e{i}", "type": t, "claim_id": prefix + "1", "explanation": "Пояснение в одну фразу."}
    d.update(kw)
    return d


def exs(prefix):
    return [
        ex(1, "single", prefix, question="2+2?", options=["3", "4", "5"], answer=1),
        ex(2, "single", prefix, question="Столица России?", options=["Москва", "Казань"], answer=0),
        ex(3, "multi", prefix, question="Чётные числа?", options=["2", "3", "4"], answer=[0, 2]),
        ex(4, "multi", prefix, question="Цвета радуги?", options=["красный", "чёрный", "синий"], answer=[0, 2]),
        ex(5, "order", prefix, question="Расставьте по возрастанию", options=["1", "2", "3", "4"]),
        ex(6, "fill", prefix, question="Вода кипит при ___ °C (при норм. давлении)", answer=["100"]),
        ex(7, "calc", prefix, question="Сколько будет 12 / 4?", answer=3, tolerance=0.01, unit=""),
        ex(8, "calc", prefix, question="Сколько будет 2.5 * 2?", answer=5, tolerance=0.01, unit=""),
    ]


for i, (nid, title, p, data) in enumerate([("selftest.01", "Самотест: источник у абзаца", "a", False),
                                           ("selftest.02", "Самотест: решение на данных", "b", True)], start=1):
    (D / f"{nid}.node.json").write_text(
        json.dumps(node(nid, i, title, p, exs(p), data), ensure_ascii=False, indent=2), encoding="utf-8")
print("Самотест сгенерирован:", D)
