"""Проверка JSON по схеме без сторонних библиотек (нужное подмножество JSON Schema).

Лишние поля разрешены: так сказано в README схем организаторов.
"""
import re

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[name])


def validate(value, schema, root=None, path="$"):
    root = root or schema
    if "$ref" in schema:
        target = root
        for key in schema["$ref"].lstrip("#/").split("/"):
            target = target[key]
        return validate(value, target, root, path)
    errors = []
    for word in ("anyOf", "oneOf"):
        if word in schema:
            tries = [validate(value, s, root, path) for s in schema[word]]
            if all(tries):
                errors += min(tries, key=len)
    for sub in schema.get("allOf", []):
        errors += validate(value, sub, root, path)
    if "if" in schema and not validate(value, schema["if"], root, path):
        errors += validate(value, schema.get("then", {}), root, path)
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: ожидалось {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} не из списка {schema['enum']}")
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is(value, n) for n in names):
            return errors + [f"{path}: нужен тип {'/'.join(names)}"]
    if isinstance(value, dict):
        errors += [f"{path}: нет поля «{k}»" for k in schema.get("required", []) if k not in value]
        for key, item in value.items():
            if key in schema.get("properties", {}):
                errors += validate(item, schema["properties"][key], root, f"{path}.{key}")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: список слишком короткий")
        if "items" in schema:
            for i, item in enumerate(value):
                errors += validate(item, schema["items"], root, f"{path}[{i}]")
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: текст слишком короткий")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} не подходит под {schema['pattern']}")
    elif _is(value, "number"):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            errors.append(f"{path}: {value} вне допустимого диапазона")
    return errors
