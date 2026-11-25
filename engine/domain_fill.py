"""Доменный пакет: промпт по главе и раскладка ответа в файлы domains/<домен>/."""
import json
import re

FILES = {"glossary": "glossary.json", "misconceptions": "misconceptions.json",
         "physics_checklist": "physics_checklist.json", "it_bridges": "it_bridges.json",
         "pronunciation": "pronunciation.json", "colors": "colors.json", "scenes": "scenes.json"}
NEED = {"glossary": ("ru", "note"), "misconceptions": ("id", "text"), "physics_checklist": ("id", "item"),
        "it_bridges": ("term", "analogy", "breaks"), "pronunciation": ("term", "say"),
        "colors": ("name", "color"), "scenes": ("type", "template")}
KEY = {"glossary": "ru", "misconceptions": "id", "physics_checklist": "id", "it_bridges": "term",
       "pronunciation": "term", "colors": "name", "scenes": "type"}


def rows(folder, part):
    path = folder / FILES[part]
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, list) else data.get("terms", [])


def prompt(template, domain, title, folder, units):
    text = "\n".join(f"[стр. {u['page']}] {u['text']}" for u in units if u["origin"] == "author")
    fill = {"DOMAIN": domain, "TITLE": title, "TEXT": text,
            "MISC": ", ".join(x["id"] for x in rows(folder, "misconceptions")) or "нет",
            "PC": ", ".join(x["id"] for x in rows(folder, "physics_checklist")) or "нет"}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fill[m.group(1)], template)


def paint(folder, colors):
    """Цвета домена видны сценам как domain.<имя>."""
    path = folder / "styleguide.json"
    if not path.exists():
        return
    style = json.loads(path.read_text(encoding="utf-8-sig"))
    for c in colors:
        if c.get("name") and re.fullmatch(r"#[0-9A-Fa-f]{6}", c.get("color") or ""):
            style.setdefault("domain", {}).setdefault(c["name"], {"color": c["color"], "ru": c.get("why") or c["name"]})
    path.write_text(json.dumps(style, ensure_ascii=False, indent=1), encoding="utf-8")


def merge(folder, answer, pages):
    """Добавить ответ к пакету, ничего не затирая. Возвращает (что добавлено, ошибки)."""
    added, errors = {}, []
    folder.mkdir(parents=True, exist_ok=True)
    for part, fields in NEED.items():
        have = rows(folder, part)
        known = {str(x[KEY[part]]).casefold() for x in have}
        for x in answer.get(part, []):
            missing = [f for f in fields if not x.get(f)]
            if missing:
                errors.append(f"{part}: нет {missing} в {x}")
            elif part == "glossary" and x.get("page") and x["page"] not in pages:
                errors.append(f"glossary: «{x['ru']}» — стр. {x['page']} не из этой главы")
            elif part == "misconceptions" and not x["id"].startswith("misc."):
                errors.append(f"misconceptions: id должен начинаться с misc.: {x['id']}")
            elif part == "physics_checklist" and not x["id"].startswith("pc."):
                errors.append(f"physics_checklist: id должен начинаться с pc.: {x['id']}")
            elif str(x[KEY[part]]).casefold() not in known:
                have.append(x)
                known.add(str(x[KEY[part]]).casefold())
                added[part] = added.get(part, 0) + 1
        if part == "colors":
            paint(folder, answer.get(part, []))
        (folder / FILES[part]).write_text(json.dumps(have, ensure_ascii=False, indent=1), encoding="utf-8")
    return added, errors
