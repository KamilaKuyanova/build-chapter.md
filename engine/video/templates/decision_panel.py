"""Решение по правилу с неопределённостью (Н — неопределённость, решение).
Модель состояния: номер случая c и показ погрешности. Шкала признака разбита правилом на зоны; у случая есть значение
и диапазон погрешности (штриховка цветом uncertainty); если диапазон задевает две зоны — вывод «неоднозначно».
Параметры: x_name, x_unit, x_range, zones [{from, to, label, color}], cases [{name, x, sigma}]. beat: case (индекс),
band (0/1 — показать погрешность), card."""
from canvas import SG, caption, card, color, current, header, layout, new, rgb, text, track, wrap

NAME, TYPE = "decision_panel", "Н"
STATE = "номер случая c и видимость диапазона погрешности; вывод — функция положения диапазона относительно зон правила"
EXAMPLE = {"title": "Критическое сопротивление: нефть или вода", "x_name": "сопротивление пласта", "x_unit": "Ом·м",
           "x_range": [0, 20], "zones": [{"from": 0, "to": 6, "label": "вода", "color": "fluids.water"},
                                         {"from": 6, "to": 9, "label": "двухфазное, неоднозначно", "color": "uncertainty"},
                                         {"from": 9, "to": 20, "label": "нефть", "color": "fluids.oil"}],
           "cases": [{"name": "пласт 1", "x": 3, "sigma": 1}, {"name": "пласт 2", "x": 8.5, "sigma": 1.5},
                     {"name": "пласт 3", "x": 14, "sigma": 1.5}]}


def spec(params):
    return {"scene": NAME, "difficulty_type": TYPE, "state_model": STATE,
            "objects": ["шкала: " + params["x_name"], "зоны правила: " + ", ".join(z["label"] for z in params["zones"]),
                        "случаи: " + ", ".join(c["name"] for c in params["cases"])], "parameters": params,
            "invariants": ["зоны правила не меняются между кадрами", "неопределённость — диапазон, а не одна линия",
                           "вывод «неоднозначно», если диапазон задевает больше одной зоны"],
            "assumptions": params.get("assumptions", ["границы зон и погрешности — из главы"]),
            "frame_class": "B", "origin": "code_from_model", "label": "схема"}


def verdict(params, c, with_band):
    lo, hi = (c["x"] - c["sigma"], c["x"] + c["sigma"]) if with_band else (c["x"], c["x"])
    hits = [z["label"] for z in params["zones"] if z["from"] <= hi and z["to"] >= lo]
    return hits[0] if len(hits) == 1 else "неоднозначно: " + " / ".join(hits)


def render(t, beats, params, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    ci = int(round(track(beats, t, "case", 0)))
    with_band = track(beats, t, "band", 1) > 0.5
    header(dr, L, params.get("title", ""), params.get("source_note"), "схема")
    x0, x1 = L["main"][0], L["side"][2]
    y0 = L["main"][1]
    a, bb = params["x_range"]

    def xs(v):
        return x0 + 30 + (x1 - x0 - 60) * (v - a) / (bb - a)
    ly = y0 + 200
    for z in params["zones"]:
        dr.rectangle([xs(z["from"]), ly - 50, xs(z["to"]), ly + 50], fill=rgb(color(z["color"]), 200))
        lines = wrap(z["label"], 36, xs(z["to"]) - xs(z["from"]) - 10, True)[:2]
        for i, ln in enumerate(lines):
            text(dr, ((xs(z["from"]) + xs(z["to"])) / 2, ly - 100 - (len(lines) - i) * 40), ln, 36, True, anchor="ma")
    for k in range(6):
        v = a + (bb - a) * k / 5
        text(dr, (xs(v), ly + 62), f"{v:g}".replace(".", ","), 36, fill=SG["muted"], anchor="ma")
    text(dr, (x1 - 30, ly + 110), f"{params['x_name']}, {params['x_unit']}", 38, fill=SG["muted"], anchor="ra")
    cases = params["cases"][: ci + 1]
    vy = ly + 210
    for j, c in enumerate(cases):
        active = j == ci
        cy = ly
        if with_band and active:
            dr.rectangle([xs(c["x"] - c["sigma"]), cy - 60, xs(c["x"] + c["sigma"]), cy + 60], outline=rgb(SG["text"]), width=3)
            for hx in range(int(xs(c["x"] - c["sigma"])), int(xs(c["x"] + c["sigma"])), 16):
                dr.line([hx, cy + 60, hx + 30, cy - 60], fill=rgb(color("uncertainty"), 160), width=2)
        if active:
            dr.polygon([(xs(c["x"]) - 18, cy - 80), (xs(c["x"]) + 18, cy - 80), (xs(c["x"]), cy - 50)], fill=rgb(SG["text"]))
        vd = verdict(params, c, with_band)
        col = SG["text"] if active else SG["muted"]
        size = 44 if active else 38
        line = f"{c['name']}: {str(c['x']).replace('.', ',')} ± {str(c['sigma']).replace('.', ',')} → {vd}"
        for ln in wrap(line, size, x1 - x0 - 60, active):
            text(dr, (x0 + 30, vy), ln, size, active, col)
            vy += size + 12
        vy += 14
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.1, H * 0.22, W * 0.9, H * 0.72), c[0], c[1:], 46, color("measurement"))
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im
