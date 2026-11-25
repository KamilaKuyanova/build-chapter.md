"""Накопление и преобразование толщи во времени (В — геологическое время).
Модель состояния: время T. Слои откладываются в своих интервалах времени (молодые ложатся на старые), величина
(например, пористость) — кусочно-линейная функция T. Параметры: t_name, t_unit, t_range [начало, конец] (в прошлом → к нам),
layers [{t_from, t_to, name, color, thick}], quantity {name, unit, color, points [[T, v]…], range}, events [{t, name}].
beat: T [от, до], card."""
from canvas import SG, caption, card, color, current, header, layout, new, rgb, text, track, wrap

NAME, TYPE = "time_evolution", "В"
STATE = "время T; толщина каждого слоя и величина — функции T"
EXAMPLE = {
    "title": "Риф растёт, поры зарастают", "t_name": "время", "t_unit": "условные этапы", "t_range": [0, 10],
    "layers": [{"t_from": 0, "t_to": 3, "name": "основание", "color": "lithology.limestone", "thick": 2},
               {"t_from": 3, "t_to": 7, "name": "рифовый известняк", "color": "lithology.reef", "thick": 5},
               {"t_from": 7, "t_to": 10, "name": "покрышка", "color": "lithology.shale", "thick": 2}],
    "quantity": {"name": "пористость рифа", "unit": "условно", "color": "curves.NEUTRON", "range": [0, 1],
                 "points": [[3, 0.9], [7, 0.7], [10, 0.3]]},
    "events": [{"t": 3, "name": "начало роста"}, {"t": 7, "name": "погружение"}],
}


def spec(params):
    return {"scene": NAME, "difficulty_type": TYPE, "state_model": STATE,
            "objects": ["разрез: " + ", ".join(l["name"] for l in params["layers"]), "шкала времени",
                        params["quantity"]["name"] if params.get("quantity") else "без величины"],
            "parameters": params,
            "invariants": ["молодые слои лежат на старых", "слой растёт только в своём интервале времени",
                           "разрез и график величины показывают одно и то же время T"],
            "assumptions": params.get("assumptions", ["мощности и время условные; показан порядок событий"]),
            "frame_class": "B", "origin": "code_from_model", "label": "схема"}


def qval(q, T):
    pts = sorted(q["points"])
    if T <= pts[0][0]:
        return pts[0][1]
    for (a, va), (b2, vb) in zip(pts, pts[1:]):
        if a <= T <= b2:
            return va + (vb - va) * (T - a) / (b2 - a)
    return pts[-1][1]


def render(t, beats, params, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    t0, t1 = params["t_range"]
    T = max(t0, min(t1, track(beats, t, "T", t0)))
    header(dr, L, params.get("title", ""), params.get("source_note"), "схема")
    x0, y0, x1, y1 = L["main"]
    total = sum(l["thick"] for l in params["layers"])
    scale = (y1 - y0 - 60) / total
    base = y1 - 20
    cx0, cx1 = x0 + 40, x1 - 40
    for l in params["layers"]:          # снизу вверх: старые внизу
        f = 0 if T <= l["t_from"] else min(1, (T - l["t_from"]) / max(1e-9, l["t_to"] - l["t_from"]))
        h = l["thick"] * scale * f
        if h > 0.5:
            dr.rectangle([cx0, base - h, cx1, base], fill=rgb(color(l["color"])))
            if h > 50:
                dr.rounded_rectangle([cx0 + 10, base - h / 2 - 28, cx0 + 30 + len(l["name"]) * 23, base - h / 2 + 28], radius=10,
                                     fill=rgb(SG["background"], 200))
                text(dr, (cx0 + 20, base - h / 2), l["name"], 40, True, anchor="lm")
        base -= l["thick"] * scale * f
    dr.rectangle([cx0, y0, cx1, y1 - 20], outline=rgb(SG["muted"]), width=2)
    # шкала времени и величина
    sx0, sy0, sx1, sy1 = L["side"]
    dr.rectangle([sx0, sy0, sx1, sy1], fill=rgb(SG["panel"]))
    gx0, gx1, gy0, gy1 = sx0 + 50, sx1 - 40, sy0 + 80, sy1 - 110

    def xt(v):
        return gx0 + (gx1 - gx0) * (v - t0) / (t1 - t0)
    dr.line([gx0, gy1, gx1, gy1], fill=rgb(SG["muted"]), width=3)
    text(dr, (gx1, gy1 + 50), f"{params['t_name']}, {params['t_unit']} →", 36, fill=SG["muted"], anchor="ra")
    for ev in params.get("events", []):
        if ev["t"] <= T:
            dr.line([xt(ev["t"]), gy0, xt(ev["t"]), gy1], fill=rgb(SG["muted"], 150), width=2)
            text(dr, (xt(ev["t"]) + 8, gy0), wrap(ev["name"], 34, 260)[0], 34, fill=SG["muted"])
    q = params.get("quantity")
    if q:
        lo, hi = q["range"]
        text(dr, (sx0 + 30, sy0 + 20), q["name"] + (f", {q['unit']}" if q.get("unit") else ""), 38, True, color(q["color"]))
        start = min(p[0] for p in q["points"])
        pts = []
        for i in range(121):
            tv = start + (T - start) * i / 120
            if T < start:
                break
            pts.append((xt(tv), gy1 - (gy1 - gy0) * (qval(q, tv) - lo) / (hi - lo)))
        if len(pts) > 1:
            dr.line(pts, fill=rgb(color(q["color"])), width=7, joint="curve")
            dr.ellipse([pts[-1][0] - 11, pts[-1][1] - 11, pts[-1][0] + 11, pts[-1][1] + 11], fill=rgb(color(q["color"])))
    dr.line([xt(T), gy0, xt(T), gy1], fill=rgb(SG["text"], 140), width=3)
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.1, H * 0.22, W * 0.9, H * 0.72), c[0], c[1:], 46, color("measurement"))
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im
