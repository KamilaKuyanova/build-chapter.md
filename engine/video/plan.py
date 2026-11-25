"""Ролик на назначенный узел: промпт сценария и проверка ответа до рендера (python run.py video / video-build).

Сцены не знают предмета: они описаны в engine/video/web/scene_*.json (когда подходит, параметры, ключи фраз).
check() ловит то, что дорого найти после рендера: фразу без утверждения, число не из утверждения, длинную фразу,
формулу на экране, пропущенный вопрос-предсказание."""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "engine"))
import domain  # noqa: E402
import speech  # noqa: E402

LENGTH = {"short": ("шортс 9:16, 45–75 секунд", "90–130"), "long": ("разбор 16:9, 1,5–3 минуты", "190–300")}
WORDS_NUM = {"один": 1, "одна": 1, "одно": 1, "одной": 1, "одну": 1, "два": 2, "две": 2, "двух": 2, "двумя": 2, "три": 3, "трёх": 3, "четыре": 4,
             "пять": 5, "пяти": 5, "шесть": 6, "шести": 6, "семь": 7, "семи": 7, "восемь": 8, "девять": 9, "десять": 10, "десяти": 10,
             "двенадцать": 12, "пятнадцать": 15, "двадцать": 20, "двадцати": 20, "тридцать": 30, "тридцати": 30, "сорок": 40, "пятьдесят": 50,
             "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100, "ста": 100, "двести": 200, "двухстах": 200,
             "триста": 300, "четыреста": 400, "пятьсот": 500, "тысяча": 1000, "тысячи": 1000, "тысяч": 1000}


def scenes():
    out = {}
    for p in sorted((HERE / "web").glob("scene_*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        if s.get("when"):
            out[p.stem[6:]] = s
    return out


def all_claims(layer):
    return {c["id"]: c for n in layer["nodes"] for c in n["claims"]}


def card(layer, node):
    ids = [node["id"]] + [l["target"] for l in node.get("links", []) if l["type"] == "prerequisite"]
    out = [f"Название: {node.get('title_novice') or node['title']}. Тип трудности: {node['difficulty']}. Страницы: {node['pages']}."]
    m = node.get("misconception") or {}
    if m.get("text"):
        out.append(f"Заблуждение узла ({m.get('ref')}): {m['text']}")
    for k in ("main", "mechanism", "practice", "nuances"):
        v = node["layers"].get(k) or {}
        if v.get("text"):
            out.append(f"\n[{k}] {v['text']}")
    dd = node.get("decision_on_data")
    if dd:
        out.append("\nРешение на данных: " + json.dumps(dd, ensure_ascii=False))
    for x in node.get("worked_examples", []):
        out.append("\nПример автора: " + json.dumps({k: x.get(k) for k in ("statement", "steps", "result")}, ensure_ascii=False))
    out.append("\nУтверждения (узел и то, на что он опирается):")
    kind = {"observation": "наблюдение", "inference": "вывод", "assumption": "допущение"}
    for n in layer["nodes"]:
        if n["id"] in ids:
            out += [f"- `{c['id']}` стр. {c['page_pdf']}, {kind.get(c['kind'], c['kind'])}: {c['text']} — «{c['quote'][:220]}»" for c in n["claims"]]
            out += [f"  термин «{g['term']}»: {g['definition']}" for g in n.get("glossary", [])]
    return "\n".join(out)


def prompt(template, chapter, layer, node_id, fmt):
    node = next((n for n in layer["nodes"] if n["id"] in (node_id, f"{chapter}.{node_id}")), None)
    if not node:
        raise SystemExit(f"нет узла {node_id}. Есть: " + ", ".join(n["id"] for n in layer["nodes"]))
    node_id = node["id"]
    sg = domain.load("styleguide.json")
    colors = [f"{g}.{k} ({v['ru']})" for g in ("lithology", "fluids", "curves", "domain") for k, v in sg.get(g, {}).items()]
    cat = []
    for name, s in scenes().items():
        cat.append(f"### `{name}`\nКогда: {s['when']}\nПараметры: {s['params_doc']}\nКлючи фразы (`beat`): {s['beat_doc']}\n"
                   f"Инварианты: {'; '.join(s['invariants'])}\nОбразец: `{s['example']}`\n")
    example = "videos/latyshova_signs/video.json" if fmt == "short" else "videos/basniev_response/video.json"
    fill = {"CHAPTER": chapter, "NODE": node_id, "FORMAT": fmt, "LENGTH": LENGTH[fmt][0], "WORDS": LENGTH[fmt][1], "SCENES": "\n".join(cat),
            "CARD": card(layer, node), "MISC": "\n".join(f"- {m['id']}: {m['text']}" for m in domain.load("misconceptions.json")),
            "PC": "\n".join(f"- {p['id']}: {p['item']}" for p in domain.load("physics_checklist.json")), "COLORS": ", ".join(colors),
            "EXAMPLE": json.dumps(json.loads((ROOT / example).read_text(encoding="utf-8")), ensure_ascii=False)}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fill[m.group(1)], template)


def anims_prompt(template, chapter, layer, routes):
    """Промпт живых анимаций: видеоузлы главы с утверждениями и каталог сцен."""
    sg, made = domain.load("styleguide.json"), set()
    for p in (ROOT / "data").glob("*/media_extra.json"):   # узлы, у которых ролик уже стоит в курсе
        made |= set(json.loads(p.read_text(encoding="utf-8")))
    rows = []
    for n in sorted(layer["nodes"], key=lambda x: x["order"]):
        r = routes.get(n["id"], {})
        sc = r.get("video_scores") or n.get("video_scores") or {}
        video = r.get("format") in ("шортс", "длинное видео") or (sum(sc.values()) >= 6 and max(sc.values() or [0]) == 2)
        if not video or n["id"] in made:
            continue
        kind = {"observation": "наблюдение", "inference": "вывод", "assumption": "допущение"}
        rows.append(f"### `{n['id']}` {n.get('title_novice') or n['title']} (тип {n['difficulty']['primary']}, {r.get('format')}, стр. {n['pages'][:3]})\n"
                    + "\n".join(f"- {c['id'].split('#')[1]} ({kind.get(c['kind'], c['kind'])}): {c['text']}" for c in n["claims"]))
    cat = [f"### `{k}`\nКогда: {s['when']}\nПараметры: {s['params_doc']}\nКлючи кадра (`beat`): {s['beat_doc']}\n" for k, s in scenes().items()]
    ex = json.loads((ROOT / "data" / "kuznetsov" / "anim_scenes.json").read_text(encoding="utf-8"))
    keep = ("kuznetsov.trap_height_single", "kuznetsov.secondary_porosity", "kuznetsov.group_atoll")
    bas = json.loads((ROOT / "data" / "basniev" / "anim_scenes.json").read_text(encoding="utf-8"))
    ex = {"bases": {k: ex["bases"][k] for k in ("trap", "reef", "atoll")}, "nodes": {k: ex["nodes"][k] for k in keep}}
    ex["bases"]["gal"] = bas["bases"]["gal"]
    ex["nodes"]["basniev.erf_solution"] = bas["nodes"]["basniev.erf_solution"]
    fill = {"CHAPTER": chapter, "SCENES": "\n".join(cat), "NODES": "\n\n".join(rows) or "видеоузлов без ролика нет",
            "COLORS": ", ".join(f"{g}.{k} ({v['ru']})" for g in ("lithology", "fluids", "curves", "domain") for k, v in sg.get(g, {}).items()),
            "EXAMPLE": json.dumps(ex, ensure_ascii=False)}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: fill[m.group(1)], template), len(rows)


def numbers(text):
    """Числа фразы: цифрами и словами («одна десятая» → 0.1 не разбираем, берём части)."""
    t = text.lower().replace(",", ".")
    out = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)}
    return out | {float(WORDS_NUM[w]) for w in re.findall(r"[а-яё]+", t) if w in WORDS_NUM}


def check(doc, layer, fmt=None):
    errs, warn = [], []
    need = ("video_id", "chapter", "node_id", "format", "scene", "script", "params", "exaggerations", "prediction_question",
            "transfer_question", "data_it_bridge", "physics")
    errs += [f"нет поля {k}" for k in need if not doc.get(k)]
    if errs:
        return errs, warn
    claims, cat = all_claims(layer), scenes()
    if doc["node_id"] not in {n["id"] for n in layer["nodes"]}:
        errs.append(f"узла {doc['node_id']} нет в слое")
    if doc["scene"] not in cat:
        errs.append(f"сцены {doc['scene']} нет; есть: {', '.join(cat)}")
    if fmt and doc["format"] != fmt:
        errs.append(f"формат {doc['format']}, а просили {fmt}")
    sc, misc = doc["script"], {m["id"] for m in domain.load("misconceptions.json")}
    del misc
    if not (sc[0]["text"].strip().endswith("?") or "?" in sc[0]["text"]):
        errs.append("первая фраза не вопрос: нужен крючок")
    if sum(1 for s in sc if s.get("prediction")) != 1:
        errs.append("нужна ровно одна фраза с prediction: true")
    if "?" not in sc[-1]["text"]:
        errs.append("последняя фраза должна быть вопросом на перенос")
    for i, s in enumerate(sc, 1):
        w = speech.words(s["text"])
        if w > 18:
            errs.append(f"фраза {i}: {w} слов, максимум 18")
        cid = s.get("claim_id")
        if not cid and not s.get("is_analogy"):
            errs.append(f"фраза {i}: нет claim_id")
        if cid and cid not in claims:
            errs.append(f"фраза {i}: нет утверждения {cid}")
        head = (s.get("beat") or {}).get("head") or s.get("on_screen") or ""
        if len(head.split()) > 8:
            errs.append(f"фраза {i}: на экране больше 8 слов")
        if re.search(r"[α-ωΑ-Ω=^]", head):
            errs.append(f"фраза {i}: на экране формула или греческая буква")
        if cid in claims and "?" not in s["text"]:
            c = claims[cid]
            lost = numbers(s["text"]) - numbers(c["text"] + " " + c["quote"]) - {1.0, 2.0, 3.0}
            if lost:
                warn.append(f"фраза {i}: числа {sorted(lost)} не видны в утверждении {cid}, проверить")
    total = sum(speech.words(s["text"]) for s in sc)
    lo, hi = (80, 150) if doc["format"] == "short" else (170, 330)
    if not lo <= total <= hi:
        errs.append(f"{total} слов в сценарии, нужно {lo}–{hi}")
    pcs = {p["id"] for p in domain.load("physics_checklist.json")}
    errs += [f"physics: нет пункта {k}" for k in doc["physics"] if k not in pcs]
    for e in doc["exaggerations"]:
        if not re.search(r"\d|раз|нет преувеличений", e):
            errs.append(f"преувеличение без числа: {e}")
    return errs, warn
