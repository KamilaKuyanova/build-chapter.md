"""Задания курса: промпт для модели, сборка коротких ответов в task.schema.json и проверка ключей.

Модель пишет верные варианты первыми, программа сама перемешивает и ставит ключ.
Неверный вариант обязан быть неверным: утверждение из другого шага им быть не может.
"""
import ast
import operator
import random
import re

from .check import stems
from .nodetext import in_text, node_text
from .textnorm import numbers, words

MIN_TASKS, MIN_TYPES = 15, 4
KINDS = ("recall", "understanding", "transfer", "data")
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg}


def calc(expr):
    """Арифметика без eval: числа, + - * / ** и скобки."""
    def walk(n):
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](walk(n.left), walk(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](walk(n.operand))
        raise ValueError(f"недопустимое выражение: {expr}")
    return walk(ast.parse(expr, mode="eval"))


def digest(layer):
    """Слой для промпта: всё, на чём можно построить задание."""
    out = []
    for n in layer["nodes"]:
        out.append(f"## {n['id']} | {n.get('title_novice') or n['title']}")
        out.append("суть: " + n["layers"]["main"]["text"])
        out += [f"c{i}: {c['text']}" for i, c in enumerate(n["claims"], 1)]
        if n.get("misconception"):
            out.append(f"заблуждение ({n['misconception']['ref']}): {n['misconception']['text']}")
        d = n.get("decision_on_data")
        if d:
            out.append(f"решение: признаки {d['features']}; правило: {d['rule']}; вывод: {d['conclusion']}; "
                       f"контрпример: {d.get('counterexample', '')}")
        for e in n.get("worked_examples", []):
            out.append(f"пример {e.get('number', '')}: {e['condition']} -> {e['result']}")
    return "\n".join(out)


def prompt(template, layer):
    fill = {"LAYER": digest(layer), "N": str(max(18, round(len(layer["nodes"]) * 0.45)))}
    return re.sub(r"\{\{(LAYER|N)\}\}", lambda m: fill[m.group(1)], template)


def build(layer, answer):
    nodes = {n["id"]: n for n in layer["nodes"]}
    prefix = layer["chapter"] + "."
    tasks, problems, count = [], [], {}
    for a in answer["tasks"]:
        sid = a["s"] if a["s"] in nodes else prefix + a["s"]
        node = nodes.get(sid)
        if not node:
            problems.append(f"нет шага {a['s']}")
            continue
        count[sid] = count.get(sid, 0) + 1
        tid = f"{sid}.t{count[sid]}"
        claims = [c for i, c in enumerate(node["claims"], 1) if i in a["c"]]
        if len(claims) != len(a["c"]):
            problems.append(f"{tid}: нет утверждения из {a['c']}")
            continue
        t = {"id": tid, "type": a["t"], "step_id": sid, "claim_ids": [c["id"] for c in claims], "prompt": a["q"],
             "explanation": a["e"], "kind": a["k"], "evidence": a.get("ev") or claims[0]["text"]}
        opts = [(o if isinstance(o, list) else [o, None]) for o in a.get("o", [])]
        n_right = {"single": 1, "multiple": a.get("n", 0), "order": len(opts)}.get(a["t"], 0)
        numbered = [{"id": "", "text": o[0], "misconception": o[1]} for o in opts]
        right = numbered[:n_right]
        shuffled = numbered[:]
        rng = random.Random(tid)
        for _ in range(20):
            rng.shuffle(shuffled)
            if a["t"] != "order" or shuffled != numbered:
                break
        for i, o in enumerate(shuffled, 1):
            o["id"] = f"o{i}"
        if opts:
            t["options"] = shuffled
        if a["t"] == "single":
            t["answer"] = right[0]["id"]
        elif a["t"] in ("multiple", "order"):
            t["answer"] = [o["id"] for o in right]
        elif a["t"] == "gap":
            t["answer"] = a["a"]
        else:
            t.update(answer=a["a"], tolerance=a.get("tol", 0), unit=a.get("u"))
            if abs(calc(a["f"]) - a["a"]) > max(a.get("tol", 0), 1e-9):
                problems.append(f"{tid}: ответ {a['a']} не сходится с расчётом {a['f']} = {calc(a['f'])}")
        tasks.append(t)
    return {"chapter": layer["chapter"], "tasks": tasks}, problems


def similar(a, b):
    """Доля слов варианта, которые есть в утверждении."""
    x, y = stems(a), stems(b)
    return len(x & y) / len(x) if x else 0


def check(layer, doc, misconceptions=()):
    """error — ключ или задание негодны; suspect — посмотреть глазами."""
    nodes = {n["id"]: n for n in layer["nodes"]}
    claims = [c["text"] for n in layer["nodes"] for c in n["claims"]]
    out, longest = [], 0
    err = lambda tid, msg, level="error": out.append((level, tid, msg))
    lst = doc["tasks"]
    if len(lst) < MIN_TASKS:
        err("задания", f"{len(lst)} < {MIN_TASKS}")
    if len({t["type"] for t in lst}) < MIN_TYPES:
        err("задания", f"типов меньше {MIN_TYPES}")
    seen = set()
    for t in lst:
        tid, node, opts = t["id"], nodes.get(t["step_id"]), t.get("options") or []
        if not node:
            err(tid, f"нет шага {t['step_id']}")
            continue
        text = node_text(node)
        if t["prompt"] in seen:
            err(tid, "такой вопрос уже есть")
        seen.add(t["prompt"])
        if "…" in t["prompt"] + "".join(o["text"] for o in opts):
            err(tid, "текст обрезан многоточием")
        if re.search(r"верн[оы] для шага|в этом шаге сказано", t["prompt"]):
            err(tid, "вопрос о том, из какого шага фраза, а не о смысле")
        if len({o["text"] for o in opts}) != len(opts):
            err(tid, "одинаковые варианты")
        if t.get("evidence") and not in_text(t["evidence"], text):
            err(tid, "evidence не найден в тексте шага")
        if not t["explanation"].strip():
            err(tid, "нет пояснения")
        right = t["answer"] if isinstance(t["answer"], list) else [t["answer"]]
        wrong = [o for o in opts if o["id"] not in right] if t["type"] in ("single", "multiple") else []
        for o in wrong:
            if any(o["text"].rstrip(". ") == c.rstrip(". ") for c in claims):
                err(tid, f"«неверный» вариант — верное утверждение главы: {o['text'][:60]}")
            elif len(stems(o["text"])) >= 5 and any(similar(o["text"], c) >= 0.9 for c in claims):
                err(tid, f"неверный вариант почти совпадает с утверждением: {o['text'][:60]}", "suspect")
            if o.get("misconception") and misconceptions and o["misconception"] not in misconceptions:
                err(tid, f"нет заблуждения {o['misconception']}")
        if t["type"] == "single":
            if len(opts) < 3:
                err(tid, "меньше трёх вариантов")
            size = {o["id"]: len(o["text"]) for o in opts}
            longest += bool(opts) and size[right[0]] == max(size.values())
        if t["type"] == "multiple" and not (2 <= len(right) < len(opts)):
            err(tid, "нужно от двух верных и хотя бы один неверный")
        if t["type"] == "order":
            if len(opts) < 3:
                err(tid, "в порядке меньше трёх шагов")
            if any(re.match(r"(Признак|Правило|Вывод|Шаг \d|\d)[ .:)]", o["text"]) for o in opts):
                err(tid, "подпись варианта выдаёт порядок")
        if t["type"] == "gap":
            if len(re.findall(r"\{\{\d+\}\}", t["prompt"])) != len(t["answer"]):
                err(tid, "число пропусков не равно числу ответов")
            for w in t["answer"]:
                if re.search(r"[–—]|\s", str(w)):
                    err(tid, f"«{w}» нельзя проверить точным сравнением: тире или пробел")
                if not in_text(str(w), text):
                    err(tid, f"слова «{w}» нет в тексте шага")
        if t["type"] == "calc" and not isinstance(t["answer"], (int, float)):
            err(tid, "ключ расчёта — не число")
        good = [o["text"] for o in opts if o["id"] in right] if t["type"] in ("single", "multiple") else []
        strange = numbers(" ".join(good)) - numbers(text, loose=True) - numbers(t["prompt"])
        if strange:
            err(tid, f"в верном варианте числа, которых нет в шаге: {sorted(strange)}")
    single = [t for t in lst if t["type"] == "single"]
    if single and longest / len(single) > 0.6:
        err("задания", f"верный вариант самый длинный в {longest} из {len(single)}: ответ угадывается", "suspect")
    return out
