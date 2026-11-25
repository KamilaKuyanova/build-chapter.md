#!/usr/bin/env python3
"""Проверка входов курса по ОФИЦИАЛЬНЫМ схемам организаторов (schema/official) + правила ТЗ поверх схем.

Файлы: layer.json (node.schema), tasks.json (task.schema), illustrations.json (illustration.schema),
       routing.json (routing.schema, необязательно).
Запуск: python engine/validate_layer.py [--dir data/current]
Возвращает коды: 0 — всё хорошо, 2 — есть нарушения.

Что проверяется помимо схемы (ТЗ): уникальные id; claim.id начинается с id узла; связи ведут на существующий узел
или misc.*/data.*; misc.* есть в доменном пакете; термин не используется раньше узла, где введён; у задания ответ есть
в тексте шага (evidence — дословный фрагмент); пять типов; ≥15 заданий, ≥4 типов; ≥1 иллюстрация на шаг;
метки и происхождение иллюстраций согласованы; есть шаг «решение на данных».
"""
import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nodetext  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schema" / "official"
PACK = ROOT / os.environ.get("COURSE_DOMAIN_DIR", "domain_pack")


def load_json(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8-sig"))


def schema_errors(data, schema_name, label):
    import schema as mini  # engine/schema.py, без сторонних библиотек
    return [f"{label}: {x[:200]}" for x in mini.validate(data, load_json(SCHEMAS / schema_name))]


def misconception_ids():
    return {m["id"] for m in load_json(PACK / "misconceptions.json")}


def check_layer(layer):
    errs, nodes = [], layer.get("nodes", [])
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        errs.append("слой: повторяются id узлов")
    orders = sorted(n.get("order", 0) for n in nodes)
    if orders != list(range(1, len(nodes) + 1)):
        errs.append("слой: order должен идти 1..N без пропусков")
    miscs, introduced = misconception_ids(), set()
    for n in sorted(nodes, key=lambda x: x.get("order", 0)):
        nid = n.get("id")
        for c in n.get("claims", []):
            if not str(c.get("id", "")).startswith(nid + "#"):
                errs.append(f"[{nid}] claim {c.get('id')}: id должен начинаться с «{nid}#»")
        for l in n.get("links", []):
            t = l.get("target", "")
            if t.startswith("misc."):
                if t not in miscs:
                    errs.append(f"[{nid}] связь на неизвестное заблуждение {t}")
            elif not t.startswith("data.") and t not in ids:
                errs.append(f"[{nid}] связь на несуществующий узел {t}")
        mc = n.get("misconception")
        if isinstance(mc, dict) and mc.get("ref") and mc["ref"] not in miscs:
            errs.append(f"[{nid}] misconception.ref {mc['ref']} нет в доменном пакете")
        for term in n.get("terms_used", []):
            if term not in introduced and term not in n.get("terms_introduced", []):
                errs.append(f"[{nid}] термин «{term}» использован раньше узла, где он введён")
        introduced |= set(n.get("terms_introduced", []))
        it = n.get("it_analogy") or {}
        if it.get("text") and not it.get("breaks_where"):
            errs.append(f"[{nid}] у ИТ-аналогии не названа граница")
        if n.get("needs_scan"):
            errs.append(f"[{nid}] ПРЕДУПРЕЖДЕНИЕ needs_scan: {[x.get('what') for x in n['needs_scan']]} (нужны сканы страниц)")
    if not any(n.get("decision_on_data") for n in nodes):
        errs.append("слой: нет шага «решение на данных» (decision_on_data)")
    return errs


def check_tasks(tasks, layer):
    errs, nodes = [], {n["id"]: n for n in layer.get("nodes", [])}
    lst = tasks.get("tasks", [])
    miscs = misconception_ids()
    if len(lst) < 15:
        errs.append(f"задания: {len(lst)} < 15 на главу")
    types = {t.get("type") for t in lst}
    if len(types) < 4:
        errs.append(f"задания: типов {len(types)} < 4 из 5 (есть {sorted(x for x in types if x)})")
    seen = set()
    for t in lst:
        tid, sid = t.get("id"), t.get("step_id")
        if tid in seen:
            errs.append(f"задание {tid}: повторяется id")
        seen.add(tid)
        node = nodes.get(sid)
        if not node:
            errs.append(f"задание {tid}: step_id {sid} не найден")
            continue
        claim_ids = {c["id"] for c in node.get("claims", [])}
        for c in t.get("claim_ids", []):
            if c not in claim_ids:
                errs.append(f"задание {tid}: claim {c} нет в узле {sid}")
        text = nodetext.node_text(node)
        opts = {o["id"] for o in t.get("options", [])}
        ty, a = t.get("type"), t.get("answer")
        if ty == "single" and (not isinstance(a, str) or a not in opts):
            errs.append(f"задание {tid}: ключ single должен быть id варианта")
        if ty == "multiple" and not (isinstance(a, list) and len(a) >= 2 and set(a) <= opts):
            errs.append(f"задание {tid}: ключ multiple — список ≥2 id вариантов")
        if ty == "order" and not (isinstance(a, list) and len(a) >= 3 and set(a) == opts):
            errs.append(f"задание {tid}: ключ order — все id вариантов в верном порядке (≥3)")
        if ty == "gap":
            if not (isinstance(a, list) and a):
                errs.append(f"задание {tid}: ключ gap — список слов")
            else:
                for w in a:
                    if not nodetext.in_text(str(w), text):
                        errs.append(f"задание {tid}: слово «{w}» отсутствует в тексте шага {sid}")
            if "{{1}}" not in t.get("prompt", ""):
                errs.append(f"задание {tid}: в prompt нет пропуска {{{{1}}}}")
        if ty == "calc" and not isinstance(a, (int, float)):
            errs.append(f"задание {tid}: ключ calc — число")
        if ty in ("single", "multiple", "order", "calc"):
            ev = t.get("evidence")
            if not ev:
                errs.append(f"задание {tid}: нет evidence (дословный фрагмент текста шага с ответом)")
            elif not nodetext.in_text(ev, text):
                errs.append(f"задание {tid}: evidence не найден в тексте шага {sid}")
        for o in t.get("options", []):
            m = o.get("misconception")
            if m and m not in miscs:
                errs.append(f"задание {tid}: вариант {o['id']} ссылается на неизвестное заблуждение {m}")
    return errs


def check_illustrations(ill, layer):
    errs, nodes = [], {n["id"] for n in layer.get("nodes", [])}
    per_step = {}
    for i in ill.get("illustrations", []):
        iid, o, c, lab = i.get("id"), i.get("origin"), i.get("frame_class"), i.get("label")
        per_step.setdefault(i.get("step_id"), []).append(i)
        if i.get("step_id") not in nodes:
            errs.append(f"иллюстрация {iid}: step_id {i.get('step_id')} не найден")
        if c in ("A", "B") and o == "ai_generated":
            errs.append(f"иллюстрация {iid}: класс {c} нельзя генерировать (только расчёт/данные)")
        if c in ("A", "B") and not lab:
            errs.append(f"иллюстрация {iid}: у класса {c} нужна метка происхождения")
        if o == "code_from_data" and lab not in (None, "реальные данные"):
            errs.append(f"иллюстрация {iid}: code_from_data → метка «реальные данные»")
        if o == "code_from_model" and lab not in (None, "симуляция", "схема"):
            errs.append(f"иллюстрация {iid}: code_from_model → метка «симуляция» или «схема»")
        if o == "redrawn_from_book" and "перерисовано по рис." not in (i.get("source") or ""):
            errs.append(f"иллюстрация {iid}: нужна подпись источника «перерисовано по рис. N, стр. M»")
        if o == "photo" and not i.get("source"):
            errs.append(f"иллюстрация {iid}: у фото укажите источник")
        if o == "ai_generated":
            for bad in ("керн", "шлиф", "график", "кривая", "разрез", "схема недр"):
                if bad in (i.get("prompt") or "").lower():
                    errs.append(f"иллюстрация {iid}: в промпте запрещённый объект «{bad}»")
    for nid in nodes:
        if nid not in per_step:
            errs.append(f"шаг {nid}: нет иллюстрации (нужна минимум одна на шаг)")
    if not any(i.get("frame_class") in ("A", "B") for i in ill.get("illustrations", [])):
        errs.append("иллюстрации: нет ни одной класса A или B (нужна по одной на часть главы)")
    return errs


def validate_dir(d):
    d = pathlib.Path(d)
    errs = []
    layer = tasks = ill = None
    for name, schema, var in (("layer.json", "node.schema.json", "layer"), ("tasks.json", "task.schema.json", "tasks"),
                              ("illustrations.json", "illustration.schema.json", "ill"),
                              ("routing.json", "routing.schema.json", "routing")):
        p = d / name
        if not p.exists():
            if name != "routing.json":
                errs.append(f"нет файла {p}")
            continue
        try:
            data = load_json(p)
        except Exception as ex:
            errs.append(f"{name}: не JSON ({ex})")
            continue
        errs += schema_errors(data, schema, name)
        if var == "layer":
            layer = data
        elif var == "tasks":
            tasks = data
        elif var == "ill":
            ill = data
    if layer and not any(e.startswith("layer.json") for e in errs):
        errs += check_layer(layer)
        if tasks:
            errs += check_tasks(tasks, layer)
        if ill:
            errs += check_illustrations(ill, layer)
    return layer, tasks, ill, errs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "data" / "current"))
    a = ap.parse_args()
    _, _, _, errs = validate_dir(a.dir)
    print(f"Проверка {a.dir}")
    for e in errs:
        print("  ! " + e)
    print("OK" if not errs else f"Нарушений: {len(errs)}")
    sys.exit(0 if not errs else 2)
