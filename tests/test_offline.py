#!/usr/bin/env python3
"""Офлайн-проверки без ключа API: официальный пример слоя валиден; самотест собирается; генератор заданий принимает
хороший ответ «модели» и отбрасывает плохие (выдуманное число, evidence не из текста). Запуск: python tests/test_offline.py"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
import gen_exercises  # noqa: E402
import validate_layer  # noqa: E402

fails = []


def check(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# 1. официальный пример слоя проходит официальную схему
ex = validate_layer.load_json(ROOT / "schema" / "official" / "example_layer.json")
check("example_layer.json по схеме", not validate_layer.schema_errors(ex, "node.schema.json", "example"))

# 2. самотест: сборка в строгом режиме
subprocess.run([sys.executable, str(ROOT / "tests" / "make_selftest.py")], check=True, capture_output=True)
r = subprocess.run([sys.executable, str(ROOT / "engine" / "build_course.py"), "--dir", str(ROOT / "data_selftest"),
                    "--out", str(ROOT / "out" / "selftest"), "--strict"], capture_output=True, text=True, encoding="utf-8")
check("самотест собирается (--strict)", r.returncode == 0)

# 3. генератор заданий с подставной «моделью»
layer = validate_layer.load_json(ROOT / "data_selftest" / "layer.json")
node = layer["nodes"][0]
miscs = [{"id": "misc.log_is_rock", "text": "x"}]
good = {"type": "single", "prompt": "Сколько будет два плюс три?", "claim_id": node["claims"][0]["id"],
        "options": [{"text": "четыре", "misconception": ""}, {"text": "пять", "misconception": ""},
                    {"text": "шесть", "misconception": "misc.log_is_rock"}],
        "answer_indexes": [1], "gap_words": [], "answer_number": 0, "tolerance": 0, "unit": "",
        "evidence": "Два плюс три равно пяти.", "kind": "recall", "explanation": "Так в тексте."}
t, why = gen_exercises.convert(node, good, 1, {"misc.log_is_rock"})
check("хорошее задание принято", t is not None and t["answer"] == "o2" and t["options"][2]["misconception"])
bad_ev = dict(good, evidence="Выдуманная фраза, которой нет в тексте.")
check("evidence не из текста отброшен", gen_exercises.convert(node, bad_ev, 1, set())[0] is None)
bad_num = dict(good, prompt="Сколько будет 777 плюс три?")
check("выдуманное число отброшено", gen_exercises.convert(node, bad_num, 1, set())[0] is None)
bad_claim = dict(good, claim_id="нет#c9")
check("несуществующий claim отброшен", gen_exercises.convert(node, bad_claim, 1, set())[0] is None)

# 4. сцена «каротаж»: кадры корректны, кривые согласованы с моделью слоёв
sys.path.insert(0, str(ROOT / "engine" / "scenes"))
import logging_run  # noqa: E402
import xml.dom.minidom  # noqa: E402
fr = logging_run.Frame()
svg = fr.svg(60)
xml.dom.minidom.parseString(svg)
check("кадр сцены — корректный SVG с меткой «симуляция»", "симуляция" in svg)
c60, c77 = logging_run.curves_at(60), logging_run.curves_at(77)
check("нефть и плотная порода обе дают высокое сопротивление", c60["RES"] > 0.7 and c77["RES"] > 0.7)
check("плотная порода без отклонения ПС, песчаник с отклонением", abs(c77["SP"]) < 0.2 and c60["SP"] < -0.4)
check("глубина растёт вниз", fr.y(80) > fr.y(20))

print("ИТОГО:", "всё хорошо" if not fails else f"провалено {len(fails)}")
sys.exit(1 if fails else 0)
