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

# 5. озвучка и паспорт ролика
sys.path.insert(0, str(ROOT / "engine" / "video"))
import speech  # noqa: E402
import passport_check  # noqa: E402
sp = speech.prepare_for_speech("Каротаж: ГК равен 2,5, а сопротивление — 16 Ом·м.")
check("озвучка: аббревиатуры и числа словами, ударения", "гэ ка" in sp and "две целых пять десятых" in sp
      and "шестнадцать" in sp and "́" in sp)
check("субтитры SRT формируются", "00:00:00,000 --> 00:00:06,500" in speech.subtitles_srt(
    [{"t_start": 0, "t_end": 6.5, "text": "Привет"}]))

PH = ["Почему высокое сопротивление пласта ещё не доказывает нефть в породе?",
      "Гамма-каротаж, ГК, показывает естественное излучение самой породы, а не отражение прибора.",
      "Нефть плохо проводит ток, поэтому сопротивление нефтеносного песчаника заметно выше.",
      "Плотная порода без пор тоже проводит ток плохо и даёт высокое сопротивление.",
      "Значит, по одной кривой сопротивления нефть от плотной породы отличить нельзя.",
      "Смотрим вместе кривую потенциала собственной поляризации против этих же пластов.",
      "Песчаник даёт отклонение кривой потенциала, а плотная порода почти не даёт его.",
      "Выводы делают по комплексу методов, а не по одной кривой сопротивления.",
      "Какой ещё признак поможет отличить нефтеносный пласт от плотной породы?"]
pcs = [c["id"] for c in validate_layer.load_json(ROOT / "domain_pack" / "physics_checklist.json")]
pp = {"video_id": "v1", "node_id": "n1", "node_card": {},
      "script": [{"t_start": i * 5.5, "t_end": i * 5.5 + 5.0, "text": t, "claim_id": "n1#c1"} for i, t in enumerate(PH)],
      "sources": [{"claim_id": "n1#c1", "page_or_dataset": "стр. 95"}], "scene_spec": "scene_spec.json",
      "frames": [{"t": 0, "class": "B", "label": "симуляция"}], "exaggerations": ["нет преувеличений"],
      "prediction_question": "Что покажет кривая в плотной породе?", "transfer_question": "Как отличить нефть в вашем наборе данных?",
      "data_it_bridge": "Один признак даёт ложные срабатывания в классификаторе.",
      "physics_checklist": [{"item": i, "answer": "да"} for i in pcs],
      "audio_check": {"lufs": -16.0, "asr_wer": 0.05, "sync_max_s": 0.3, "fallback_voice": "ru-RU-SvetlanaNeural"}}
errs = passport_check.check(pp, "short")
check("хороший паспорт проходит (проверка): " + "; ".join(errs[:2]), not errs)
bad = json.loads(json.dumps(pp))
bad["script"][2]["text"] = "слово " * 20
bad["script"][3]["claim_id"] = None
bad["physics_checklist"][0] = {"item": pcs[0], "answer": "нет"}
e2 = " | ".join(passport_check.check(bad, "short"))
check("плохой паспорт: длинная фраза, нет claim_id, «нет» без оговорки", "слов (максимум" in e2 and "нет claim_id" in e2 and "без оговорки" in e2)

# 6. сцена давления: интегральная показательная функция против табличных значений (Абрамовиц–Стиган)
sys.path.insert(0, str(ROOT / 'engine' / 'video'))
from templates import formula_explorer as scene_pressure  # noqa: E402
tab = {0.1: 1.8229, 0.5: 0.5598, 1.0: 0.2194, 2.0: 0.04890, 5.0: 0.001148}
check("E1(x) совпадает с таблицей до 0,5%", all(abs(scene_pressure.E1(x) - v) / v < 0.005 for x, v in tab.items()))
check("давление падает с расстоянием и растёт со временем",
      scene_pressure.dp(50, 3600, 1.0) > scene_pressure.dp(200, 3600, 1.0) and scene_pressure.dp(200, 7200, 1.0) > scene_pressure.dp(200, 3600, 1.0))
for vid in ("latyshova_short", "basniev_long"):
    pp_path = ROOT / "videos" / vid / "passport.json"
    if pp_path.exists():
        pp = validate_layer.load_json(pp_path)
        e3 = [x for x in passport_check.check(pp, pp["format"]) if "asr_wer" not in x]
        check(f"паспорт {vid}: нарушений нет (кроме ещё не подключённого ASR)", not e3)

# 7. перерисованная палетка рис. 69: точки примеров 46 и 47 попадают в области, совпадающие с ответами книги (стр. 98)
sys.path.insert(0, str(ROOT / "engine" / "figures"))
import redraw  # noqa: E402
F = validate_layer.load_json(ROOT / "data" / "latyshova" / "figures" / "fig69.json")
P0, cal = F["panels"][0], F["calibration"]
X = redraw.Axis(P0["x"], 0, 1)
cv = {c["id"]: [redraw.from_scan(p, cal) for p in c["points"]] for c in P0["curves"]}


def y_on(curve, x):
    import math
    for (xa, ya), (xb, yb) in zip(curve, curve[1:]):
        if xa <= x <= xb:
            t = (X.frac(x) - X.frac(xa)) / (X.frac(xb) - X.frac(xa))
            return 10 ** (math.log10(ya) + t * (math.log10(yb) - math.log10(ya)))
    return None


def region(kp, rho):
    if kp < P0["vlines"][0]["x"]:
        return "А"
    if rho >= y_on(cv["c3u"], kp):
        return "I"
    return "II" if rho >= y_on(cv["c3l"], kp) else "III"


answers = {(25, 20): "I", (15, 10): "А", (20, 10): "I", (25, 10): "II"}   # пример 46; пример 47 а, б, в
got = {k: region(*k) for k in answers}
check(f"рис. 69: примеры 46–47 по оцифровке совпадают с ответами книги {got}", got == answers)

print("ИТОГО:", "всё хорошо" if not fails else f"провалено {len(fails)}")
sys.exit(1 if fails else 0)
