#!/usr/bin/env python3
"""Генератор заданий (часть Б) на Claude API -> tasks.json в формате task.schema организаторов.

Код, а не модель, проверяет правила ТЗ: ≥15 заданий и ≥4 типов из 5; claim_ids и step_id существуют; ответ есть в тексте шага
(evidence — дословный фрагмент шага; для gap слова ответа входят в текст); числа в вопросе/вариантах есть в тексте шага;
неверные варианты single могут ссылаться на заблуждения из доменного пакета (misc.*).
Запуск: python engine/gen_exercises.py [--dir data/current] [--per-node 4] [--rounds 2]  (читает layer.json, пишет tasks.json)
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nodetext  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TYPES = ["single", "multiple", "order", "gap", "calc"]
NUM = re.compile(r"\d+(?:[.,]\d+)?")

SCHEMA = {
    "type": "object",
    "properties": {"tasks": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": TYPES},
            "prompt": {"type": "string"},
            "options": {"type": "array", "items": {"type": "object", "properties": {
                "text": {"type": "string"}, "misconception": {"type": "string"}},
                "required": ["text", "misconception"], "additionalProperties": False}},
            "answer_indexes": {"type": "array", "items": {"type": "integer"}},
            "gap_words": {"type": "array", "items": {"type": "string"}},
            "answer_number": {"type": "number"},
            "tolerance": {"type": "number"},
            "unit": {"type": "string"},
            "claim_id": {"type": "string"},
            "evidence": {"type": "string"},
            "kind": {"type": "string", "enum": ["recall", "understanding", "transfer", "data"]},
            "explanation": {"type": "string"}},
        "required": ["type", "prompt", "options", "answer_indexes", "gap_words", "answer_number", "tolerance", "unit",
                     "claim_id", "evidence", "kind", "explanation"],
        "additionalProperties": False}}},
    "required": ["tasks"], "additionalProperties": False}

SYSTEM = ("Ты составляешь проверочные задания к шагу курса для новичка без геологического образования. "
          "Используй ТОЛЬКО текст шага; ничего не выдумывай и не добавляй чисел, которых в нём нет. "
          "Каждое задание опирается на одно утверждение (claim_id) и содержит evidence: ДОСЛОВНЫЙ фрагмент текста шага "
          "(скопируй без изменений), из которого следует ответ. Пояснение — одна короткая фраза. Фразы до 20 слов. "
          "Неверные варианты делай правдоподобными; если вариант повторяет типичное заблуждение из списка — укажи его id в "
          "misconception, иначе пустую строку.")

RULES = """Поля по типам (ненужные поля заполни пустыми значениями: [] , "" , 0):
- single: options 3–4, answer_indexes = [индекс верного].
- multiple: options 4–5, answer_indexes = индексы всех верных (минимум 2).
- order: options — шаги В ПРАВИЛЬНОМ порядке (минимум 3); answer_indexes = [].
- gap: в prompt пропуск {{1}} (при нескольких {{2}}...); gap_words — слова из текста шага по порядку; options = [].
- calc: расчёт по числам и формуле из текста шага; answer_number, tolerance, unit; options = []."""


def build_prompt(node, miscs, need_types, count, feedback=None):
    claims = "\n".join(f"- {c['id']}: {c['text']}" for c in node["claims"])
    ms = "\n".join(f"- {m['id']}: {m['text']}" for m in miscs)
    fb = f"\nОшибки прошлой попытки (исправь): {feedback}" if feedback else ""
    return (f"Текст шага:\n\"\"\"\n{nodetext.node_text(node)}\n\"\"\"\n\nУтверждения (claim_id):\n{claims}\n\n"
            f"Типичные заблуждения (id для неверных вариантов):\n{ms}\n\n{RULES}\n\n"
            f"Составь {count} заданий. Желательные типы: {', '.join(need_types)}. "
            f"Тип, для которого в тексте нет материала (например, нет чисел для calc), не составляй.{fb}")


def convert(node, raw, idx, miscs):
    """Ответ модели -> задание по task.schema. Возвращает (task|None, причина|None)."""
    text, ty = nodetext.node_text(node), raw.get("type")
    if raw.get("claim_id") not in {c["id"] for c in node["claims"]}:
        return None, f"claim_id {raw.get('claim_id')} не найден"
    if not raw.get("explanation"):
        return None, "нет пояснения"
    opts = [{"id": f"o{i + 1}", "text": o["text"], "misconception": (o.get("misconception") or None)
             if (o.get("misconception") in miscs) else None} for i, o in enumerate(raw.get("options") or [])]
    t = {"id": f"{node['id']}.t{idx}", "type": ty, "step_id": node["id"], "claim_ids": [raw["claim_id"]],
         "prompt": raw["prompt"], "explanation": raw["explanation"], "kind": raw.get("kind", "recall"),
         "evidence": raw.get("evidence", "")}
    ai = raw.get("answer_indexes") or []
    if ty in ("single", "multiple", "order", "calc") and not nodetext.in_text(t["evidence"], text):
        return None, "evidence не является дословным фрагментом текста шага"
    if ty == "single":
        if not (3 <= len(opts) <= 5 and len(ai) == 1 and 0 <= ai[0] < len(opts)):
            return None, "single: 3–5 вариантов и один верный"
        t.update(options=opts, answer=opts[ai[0]]["id"])
    elif ty == "multiple":
        if not (4 <= len(opts) <= 6 and len(set(ai)) >= 2 and all(0 <= i < len(opts) for i in ai)):
            return None, "multiple: 4–6 вариантов, минимум 2 верных"
        t.update(options=opts, answer=[opts[i]["id"] for i in sorted(set(ai))])
    elif ty == "order":
        if len(opts) < 3:
            return None, "order: минимум 3 шага"
        t.update(options=opts, answer=[o["id"] for o in opts])
    elif ty == "gap":
        w = raw.get("gap_words") or []
        if "{{1}}" not in raw["prompt"] or not w or not all(nodetext.in_text(x, text) for x in w):
            return None, "gap: нужен пропуск {{1}} и слова из текста шага"
        t.update(answer=w)
        t.pop("evidence")
    elif ty == "calc":
        t.update(answer=raw.get("answer_number"), tolerance=raw.get("tolerance") or 0.01, unit=raw.get("unit") or "")
    else:
        return None, "неизвестный тип"
    nt = nodetext.norm(text)
    for n in NUM.findall(raw["prompt"] + " " + " ".join(o["text"] for o in opts)):
        if nodetext.norm(n) not in nt:
            return None, f"число {n} отсутствует в тексте шага"
    return t, None


def gen_for_node(node, miscs, per_node, rounds, llm):
    good, feedback, ids = [], None, {m["id"] for m in miscs}
    for _ in range(rounds + 1):
        have = {t["type"] for t in good}
        need = [t for t in TYPES if t not in have] or TYPES
        out = llm(build_prompt(node, miscs, need, max(1, per_node - len(good)), feedback), SCHEMA, SYSTEM)
        bad = []
        for raw in out.get("tasks", []):
            t, why = convert(node, raw, len(good) + 1, ids)
            if t:
                good.append(t)
            else:
                bad.append(why)
        if len(good) >= per_node:
            break
        feedback = "; ".join(sorted(set(bad))) or "добавь недостающие задания"
    return good


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "data" / "current"))
    ap.add_argument("--per-node", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=2)
    a = ap.parse_args()
    import llm_client
    d = pathlib.Path(a.dir)
    layer = json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))
    miscs = json.loads((ROOT / "domain_pack" / "misconceptions.json").read_text(encoding="utf-8-sig"))
    tasks = []
    for n in sorted(layer["nodes"], key=lambda x: x["order"]):
        t = gen_for_node(n, miscs, a.per_node, a.rounds, llm_client.generate_json)
        tasks += t
        print(f"  {n['id']}: {len(t)} заданий")
    types = {t["type"] for t in tasks}
    (d / "tasks.json").write_text(json.dumps({"chapter": layer["chapter"], "tasks": tasks}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    print(f"Итого: {len(tasks)} заданий, типов {len(types)}")
    if len(tasks) < 15 or len(types) < 4:
        print("  ! ТЗ: нужно ≥15 заданий и ≥4 типов на главу — повысьте --per-node")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
