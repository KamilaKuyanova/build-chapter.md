"""Процедура специалиста по шагам, с накоплением (Пр — процедура).
Модель состояния: номер текущего шага k (непрерывно). Пройденные шаги остаются на экране с галочкой, текущий раскрыт,
будущие приглушены; полоса прогресса. Параметры: steps [{name, detail, input?, output?}]. beat: k [от, до], card."""
from canvas import SG, caption, card, color, current, font, header, layout, new, rgb, text, track, wrap

NAME, TYPE = "step_procedure", "Пр"
STATE = "номер шага k; пройденные шаги накапливаются"
EXAMPLE = {"title": "Как выделить коллектор по диаграммам",
           "steps": [{"name": "Границы пластов", "detail": "по кривым определяют кровлю и подошву", "input": "диаграммы"},
                     {"name": "Литология", "detail": "по набору признаков определяют породу"},
                     {"name": "Коллектор", "detail": "выделяют пласты с признаками проницаемости"},
                     {"name": "Насыщение", "detail": "оценивают по сопротивлению и пористости", "output": "нефть / вода"}]}


def spec(params):
    return {"scene": NAME, "difficulty_type": TYPE, "state_model": STATE,
            "objects": ["шаги: " + " → ".join(s["name"] for s in params["steps"])], "parameters": params,
            "invariants": ["шаги идут в порядке книги", "пройденный шаг не исчезает", "вход и выход шага подписаны"],
            "assumptions": params.get("assumptions", ["процедура упрощена до ключевых шагов главы"]),
            "frame_class": "B", "origin": "code_from_model", "label": "схема"}


def render(t, beats, params, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    steps = params["steps"]
    k = max(0.0, min(len(steps) - 1, track(beats, t, "k", 0.0)))
    cur = int(round(k))
    header(dr, L, params.get("title", ""), params.get("source_note"), "схема")
    x0 = L["main"][0]
    x1 = L["side"][2]
    y0, y1 = L["main"][1], L["side"][3] if L["vertical"] else L["main"][3]
    # прогресс
    dr.rounded_rectangle([x0, y0, x1, y0 + 20], radius=10, fill=rgb(SG["panel"]))
    dr.rounded_rectangle([x0, y0, x0 + (x1 - x0) * (k + 1) / len(steps), y0 + 20], radius=10, fill=rgb(color("measurement")))
    y = y0 + 60
    row_h = (y1 - y - 20) / len(steps)
    for i, s in enumerate(steps):
        active, done = i == cur, i < k - 0.02
        h = row_h - 16
        dr.rounded_rectangle([x0, y, x1, y + h], radius=18, fill=rgb(SG["panel"]),
                             outline=rgb(color("measurement") if active else SG["muted"]), width=5 if active else 2)
        dr.ellipse([x0 + 20, y + 20, x0 + 84, y + 84], fill=rgb(color("measurement") if (done or active) else SG["background"]))
        if done:   # галочка рисуется линиями: в шрифте может не быть знака ✓
            dr.line([(x0 + 36, y + 53), (x0 + 48, y + 66), (x0 + 70, y + 38)], fill=rgb(SG["background"]), width=7, joint="curve")
        else:
            text(dr, (x0 + 52, y + 52), str(i + 1), 40, True, SG["background"] if active else SG["muted"], anchor="mm")
        text(dr, (x0 + 110, y + 26), s["name"], 46, True, SG["text"] if (done or active) else SG["muted"])
        if active or (L["vertical"] is False and done):
            yy = y + 86
            for ln in wrap(s["detail"], 40, x1 - x0 - 140)[: max(1, int((h - 90) // 48))]:
                text(dr, (x0 + 110, yy), ln, 40, fill=SG["text"] if active else SG["muted"])
                yy += 48
            io = " · ".join(v for v in (("вход: " + s["input"]) if s.get("input") else "",
                                        ("выход: " + s["output"]) if s.get("output") else "") if v)
            if io and active and yy + 44 < y + h:
                text(dr, (x0 + 110, yy), io, 38, True, color("measurement"))
        y += row_h
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.1, H * 0.22, W * 0.9, H * 0.72), c[0], c[1:], 46, color("measurement"))
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im
