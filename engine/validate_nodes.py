#!/usr/bin/env python3
"""Валидатор шагов курса по schema/course_step.schema.json (без внешних библиотек; поддержан нужный поднабор JSON Schema).
Кроме формы проверяет ссылки: claims в абзацах существуют, exercises.claim_id существует, links.to существует.
Запуск: python engine/validate_nodes.py [data/nodes]
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "course_step.schema.json").read_text(encoding="utf-8"))

TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
         "boolean": bool, "null": type(None)}


def is_type(v, t):
    if t == "integer" and isinstance(v, bool):
        return False
    if t == "number" and isinstance(v, bool):
        return False
    return isinstance(v, TYPES[t])


def resolve(ref):
    node = SCHEMA
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def check(v, s, path, errs):
    if "$ref" in s:
        return check(v, resolve(s["$ref"]), path, errs)
    if "oneOf" in s:
        for alt in s["oneOf"]:
            sub = []
            check(v, alt, path, sub)
            if not sub:
                return
        errs.append(f"{path}: не подходит ни под один вариант")
        return
    t = s.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(is_type(v, x) for x in ts):
            errs.append(f"{path}: ожидался тип {'/'.join(ts)}, получено {type(v).__name__}")
            return
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: значение {v!r} не из {s['enum']}")
    if isinstance(v, str) and len(v) < s.get("minLength", 0):
        errs.append(f"{path}: слишком короткая строка")
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                errs.append(f"{path}: нет обязательного поля «{k}»")
        for k, sub in s.get("properties", {}).items():
            if k in v:
                check(v[k], sub, f"{path}.{k}", errs)
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            errs.append(f"{path}: нужно минимум {s['minItems']} элементов")
        if "items" in s:
            for i, x in enumerate(v):
                check(x, s["items"], f"{path}[{i}]", errs)


def refs(nodes):
    errs = []
    ids = {n.get("id") for n in nodes}
    for n in nodes:
        nid = n.get("id")
        cl = {c.get("id") for c in n.get("claims", []) if isinstance(c, dict)}
        for k, p in (n.get("core") or {}).items():
            if isinstance(p, dict):
                for c in p.get("claims", []):
                    if c not in cl:
                        errs.append(f"[{nid}] core.{k}: ссылка на несуществующее утверждение {c}")
        for x in n.get("exercises", []):
            if x.get("claim_id") not in cl:
                errs.append(f"[{nid}] задание {x.get('id')}: claim_id {x.get('claim_id')} не найден")
        for l in n.get("links", []):
            if l.get("to") not in ids:
                errs.append(f"[{nid}] связь на несуществующий узел {l.get('to')}")
    return errs


def validate_dir(d):
    nodes, errs = [], []
    for p in sorted(pathlib.Path(d).glob("*.json")):
        try:
            n = json.loads(p.read_text(encoding="utf-8"))
        except Exception as ex:
            errs.append(f"{p.name}: не JSON ({ex})")
            continue
        nodes.append(n)
        local = []
        check(n, SCHEMA, p.name, local)
        errs += local
    errs += refs(nodes)
    return nodes, errs


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "nodes")
    nodes, errs = validate_dir(d)
    print(f"Проверено узлов: {len(nodes)} в {d}")
    for e in errs:
        print("  ! " + e)
    print("OK" if not errs else f"Ошибок схемы: {len(errs)}")
    sys.exit(0 if not errs else 2)
