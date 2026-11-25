"""Переходник: официальный слой (node.schema.json) -> шаги для сборщика курса build_course.py.

Задания (task.schema.json) и иллюстрации (illustration.schema.json) подхватываются, если они есть.
"""
DIFFICULTY = {"М": "mechanism", "В": "geo_time", "И": "indirect_measurement", "Ф": "formalism",
              "П": "space", "Пр": "procedure", "Н": "uncertainty", "Р": "recognition"}
KIND = {"observation": "observation", "inference": "conclusion", "assumption": "assumption"}
FORMAT = {"шортс": "short_9x16", "длинное видео": "explainer_16x9", "интерактив": "interactive",
          "практикум на данных": "data_practicum", "карточки": "cards", "текст": "text"}
TASK = {"single": "single", "multiple": "multi", "order": "order", "gap": "fill", "calc": "calc"}


def paras(field, pages):
    """Абзацы слоя со страницами; если разбивки нет, один абзац со страницами узла."""
    if "paras" in field:
        return [{"text": p["text"], "pages": p["pages"]} for p in field["paras"] if p["pages"]]
    return [{"text": field["text"], "pages": pages}] if field["text"].strip() and pages else []


def exercise(t):
    kind, options = TASK[t["type"]], t.get("options") or []
    ids = [o["id"] for o in options]
    texts = {o["id"]: o["text"] for o in options}
    out = {"id": t["id"], "type": kind, "question": t["prompt"], "claim_id": t["claim_ids"][0],
           "explanation": t["explanation"]}
    answer = t["answer"]
    if kind == "single":
        out.update(options=[o["text"] for o in options], answer=ids.index(answer))
    elif kind == "multi":
        out.update(options=[o["text"] for o in options], answer=[ids.index(a) for a in answer])
    elif kind == "order":  # сборщик ждёт варианты в верном порядке и перемешивает сам
        out.update(options=[texts[a] for a in answer])
    elif kind == "fill":
        for i in range(1, len(answer) + 1):
            out["question"] = out["question"].replace("{{%d}}" % i, "____")
        out["answer"] = [", ".join(map(str, answer))]
        if len(answer) > 1:
            out["question"] += " (ответы через запятую)"
    else:
        out.update(answer=answer, tolerance=t.get("tolerance") or 0)
        if t.get("unit"):
            out["unit"] = t["unit"]
    return out


def illustration(x, folder):
    return {"file": str(folder / x["file"]), "alt": x["alt"], "class": x["frame_class"],
            "label": x.get("label") or "", "generated": x["origin"] == "ai_generated",
            "caption": x["caption"] + (f" {x['source']}" if x.get("source") else ""),
            "redrawn_from_book": x["origin"] == "redrawn_from_book"}


def step(node, route, tasks, pictures, folder, node_ids):
    layers, data = node["layers"], node["data_meaning"]
    claims = [{"id": c["id"], "kind": KIND[c["kind"]], "text": c["text"], "quote": c["quote"],
               "page": c["page_pdf"], "by_model": c["by_model"],
               "origin": "model" if c["source_kind"] == "figure_description_model" else "author"}
              for c in node["claims"]]
    core = {"essence": {"text": layers["main"]["text"], "claims": [claims[0]["id"]], "pages": node["pages"]}}
    for key in ("mechanism", "practice", "nuances"):
        found = paras(layers[key], node["pages"])
        if found:
            core[key] = found
    deeper = [p for d in layers["deeper"] for p in paras({"paras": [d]} if d.get("pages") else d, node["pages"])]
    if deeper:
        core["deeper"] = deeper
    out = {"id": node["id"], "order": node["order"], "title": node.get("title_novice") or node["title"],
           "book_title": node["title"], "why_before": node["why_here"]["text"],
           "difficulty": {"primary": DIFFICULTY[node["difficulty"]["primary"]]},
           "source_units": node.get("units", []), "core": core, "claims": claims,
           "terms": [{"term": t["term"], "definition": t["definition"]} for t in node.get("glossary", [])],
           "data_meaning": data["from_chapter"]["text"] + " Где ломается: " + data["breaks"]["text"],
           "hypotheses": [h["text"] for h in data["hypotheses"]],
           "it_analogy": {"analogy": node["it_analogy"]["text"], "breaks_where": node["it_analogy"]["breaks_where"]},
           "links": [{"to": x["target"], "type": "example" if x["type"] == "example_of" else x["type"]}
                     for x in node["links"] if x["target"] in node_ids],
           "worked_examples": [{"condition": x["condition"], "steps": x["steps"], "result": x["result"],
                                "page": x["page_pdf"]} for x in node.get("worked_examples", [])],
           "book_problems": [{"number": x["number"], "text": x["text"], "page": x["page_pdf"],
                              **({"figure": x["figure"]} if x.get("figure") else {})}
                             for x in node.get("book_tasks", [])],
           "route": {"format": FORMAT[route["format"]], "why": route["why"]} if route else {},
           "illustrations": [illustration(x, folder) for x in pictures
                             if node["id"] in (x["step_id"], x.get("node_id"))],
           "exercises": [exercise(t) for t in tasks if t["step_id"] == node["id"]]}
    if node["difficulty"].get("secondary"):
        out["difficulty"]["secondary"] = DIFFICULTY[node["difficulty"]["secondary"]]
    if node.get("misconception"):
        out["misconception"] = node["misconception"]["text"]
    if node.get("now_practice"):
        out["current_practice"] = node["now_practice"]["text"]
    d = node.get("decision_on_data")
    if d:
        out["data_step"] = True
        out["data_solution"] = {"features": d["features"], "rule": d["rule"], "conclusion": d["conclusion"],
                                "breaks": d.get("counterexample", "")}
    return out


def steps(layer, routing, tasks, pictures, folder):
    routes = {r["node_id"]: r for r in routing["routes"]}
    ids = {n["id"] for n in layer["nodes"]}
    return [step(n, routes.get(n["id"]), tasks, pictures, folder, ids) for n in layer["nodes"]]
