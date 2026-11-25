"""Маршрутизация: формат узла по типу трудности и критериям видеоёмкости (routing.schema.json)."""
NAMES = {"time": "изменение во времени", "invisible": "невидимое становится видимым",
         "scale": "скачок масштаба", "counterintuitive": "контринтуитивность",
         "cause_effect": "причина и следствие"}
TYPE = {"М": "механизм, процесс", "В": "в геологическое время", "И": "косвенное измерение",
        "Ф": "формализм, модель", "П": "пространство", "Пр": "процедура",
        "Н": "неопределённость, решение", "Р": "распознавание"}
# формат без видео -> чем закрыть узел
BASE = {"М": "интерактив", "В": "интерактив", "И": "интерактив", "Ф": "интерактив", "П": "интерактив",
        "Пр": "практикум на данных", "Н": "практикум на данных", "Р": "карточки"}
TEMPLATE = {"М": "process_state", "В": "time_evolution", "И": "tool_and_curve", "Ф": "formula_explorer",
            "П": "section_views", "Пр": "step_procedure", "Н": "decision_panel", "Р": "compare_signs"}
VIDEO_MIN = 4  # сумма баллов, с которой узел видеоёмкий


def route_node(node):
    first, second = node["difficulty"]["primary"], node["difficulty"].get("secondary")
    scores = node["video_scores"]
    total = sum(scores.values())
    strong = [NAMES[k] for k, v in scores.items() if v == 2] or [NAMES[k] for k, v in scores.items() if v]
    base = BASE[first]
    if total >= VIDEO_MIN and max(scores.values()) == 2:
        long = node.get("decision_on_data") or {first, second} & {"Н", "Пр"}
        fmt, extra = ("длинное видео" if long else "шортс"), base
        why = f"{TYPE[first]}; видеоёмкость {total} из 10: {', '.join(strong)}"
    elif node.get("decision_on_data"):
        fmt, extra = "практикум на данных", base if base != "практикум на данных" else "карточки"
        why = f"{TYPE[first]}; есть признаки, правило и вывод, видеоёмкость {total} из 10"
    elif total <= 1 and first not in ("Ф", "П", "Пр"):
        fmt, extra = ("карточки" if first == "Р" else "текст"), "карточки" if first != "Р" else "текст"
        why = f"{TYPE[first]}; движение ничего не добавит, видеоёмкость {total} из 10"
    else:
        fmt, extra = base, "текст"
        why = f"{TYPE[first]}; видеоёмкость {total} из 10, для ролика мало"
    moving = fmt in ("шортс", "длинное видео", "интерактив")
    return {"node_id": node["id"], "format": fmt, "secondary_format": extra, "video_scores": scores,
            "hook_short": False, "template": TEMPLATE[first] if moving else None, "why": why}


def route(layer):
    return {"chapter": layer["chapter"], "routes": [route_node(n) for n in layer["nodes"]]}
