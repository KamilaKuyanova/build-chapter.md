"""Прибор идёт вдоль разреза и пишет кривые (И — косвенное измерение).
Модель состояния: положение прибора d. От d зависят и прибор в кадре, и текущие точки всех кривых.
Параметры: layers [{top, bot, name, color, fluid?, fluid_color?, values{кривая: число}}], curves [{key, name, color, range}],
depth_max, scale_note. beat: d [от, до], hl [кривые], band [верх, низ], labels (подписать пройденные слои), card [заголовок, строки]."""
import math

from canvas import SG, caption, card, color, current, font, new, provenance, rgb, text, track

NAME, TYPE = "tool_and_curve", "И"
STATE = "положение прибора d (глубина/расстояние); кривые — функции разреза, вычисленные до d"
EDGE = 1.2
EXAMPLE = {
    "depth_max": 100, "scale_note": ["глубина растёт вниз · шкала условная", "не в масштабе: ствол шире ≈ в 20 раз"],
    "curves": [{"key": "SP", "name": "ПС", "color": "curves.SP", "range": [-1, 0]},
               {"key": "GR", "name": "ГК", "color": "curves.GR", "range": [0, 1]},
               {"key": "RES", "name": "Сопр.", "color": "curves.RES", "range": [0, 1]}],
    "layers": [
        {"top": 0, "bot": 20, "name": "глина", "color": "lithology.shale", "values": {"GR": 0.85, "SP": 0.0, "RES": 0.15}},
        {"top": 20, "bot": 40, "name": "песчаник", "color": "lithology.sand", "fluid": "вода", "fluid_color": "fluids.water",
         "values": {"GR": 0.25, "SP": -0.7, "RES": 0.2}},
        {"top": 40, "bot": 50, "name": "глина", "color": "lithology.shale", "values": {"GR": 0.85, "SP": 0.0, "RES": 0.15}},
        {"top": 50, "bot": 72, "name": "песчаник", "color": "lithology.sand", "fluid": "нефть", "fluid_color": "fluids.oil",
         "values": {"GR": 0.25, "SP": -0.6, "RES": 0.8}},
        {"top": 72, "bot": 82, "name": "плотная", "color": "lithology.dense", "values": {"GR": 0.3, "SP": -0.1, "RES": 0.85}},
        {"top": 82, "bot": 100, "name": "глина", "color": "lithology.shale", "values": {"GR": 0.85, "SP": 0.0, "RES": 0.15}}],
}


def value_at(params, key, d):
    L = params["layers"]
    v = L[0]["values"][key]
    for k in range(1, len(L)):
        w = 1 / (1 + math.exp(-(d - L[k]["top"]) / (EDGE / 4)))
        v += (L[k]["values"][key] - L[k - 1]["values"][key]) * w
    return v


def spec(params):
    return {"scene": NAME, "difficulty_type": TYPE, "state_model": STATE,
            "objects": ["ствол", "прибор", "разрез: " + ", ".join(l["name"] + (f" ({l['fluid']})" if l.get("fluid") else "")
                                                                 for l in params["layers"]),
                        "треки: " + ", ".join(c["name"] for c in params["curves"])],
            "parameters": {"layers": params["layers"], "curves": params["curves"], "depth_max": params["depth_max"]},
            "invariants": ["прибор и точки всех кривых вычисляются из одного значения d",
                           "глубина растёт вниз на разрезе и треках", "кривые построены только до текущего положения прибора",
                           "цвета из стайлгайда", "метка «симуляция» на каждом кадре; шкалы условные"],
            "assumptions": params.get("assumptions", ["значения кривых условные, не измерения реальной скважины"]),
            "frame_class": "B", "origin": "code_from_model", "label": "симуляция"}


def render(t, beats, params, W, H):
    im, dr = new(W, H)
    sz = SG["safe_zone"]
    top, bot, side = (sz["top"], sz["bottom"], sz["side"]) if H > W else (40, 40, 60)
    dmax = params["depth_max"]
    Y0, Y1 = top + 200, H - bot - (260 if H > W else 150)
    BX0, BX1 = side, side + (250 if H > W else 330)
    curves = params["curves"]
    tx = BX1 + 50
    tw = (W - side - tx - (len(curves) - 1) * 18) / len(curves)
    tracks = [(tx + i * (tw + 18), tx + i * (tw + 18) + tw) for i in range(len(curves))]

    def y_of(d):
        return Y0 + (Y1 - Y0) * d / dmax

    def x_of(k, v):
        lo, hi = curves[k]["range"]
        x0, x1 = tracks[k]
        return x0 + 14 + (v - lo) / (hi - lo) * (x1 - x0 - 28)
    d = track(beats, t, "d", 0.0)
    b = current(beats, t)
    beat = b.get("beat") or {}
    provenance(dr, side, top - 10)
    for i, ln in enumerate(params.get("scale_note", [])):
        text(dr, (side, top + 46 + i * 48), ln, 40, fill=SG["muted"])
    for L in params["layers"]:
        dr.rectangle([BX0, y_of(L["top"]), BX1, y_of(L["bot"])], fill=rgb(color(L["color"])))
        if L.get("fluid_color"):
            dr.rectangle([BX1 - 40, y_of(L["top"]) + 6, BX1 - 8, y_of(L["bot"]) - 6], fill=rgb(color(L["fluid_color"])))
    band = beat.get("band")
    if band:
        dr.rectangle([BX0 - 6, y_of(band[0]), W - side + 4, y_of(band[1])], outline=rgb(color("measurement")), width=5)
    cx = (BX0 + BX1) / 2 - 30
    dr.rectangle([cx - 28, Y0, cx + 28, Y1], fill=rgb(color("fluids.mud")))
    ty = y_of(min(d, dmax * 0.96))
    dr.line([cx, Y0, cx, ty - 40], fill=rgb(SG["text"]), width=4)
    dr.rounded_rectangle([cx - 16, ty - 40, cx + 16, ty + 40], radius=8, fill=rgb(color("measurement")), outline=rgb(SG["text"]), width=3)
    hl = set(beat.get("hl", []))
    for k, c in enumerate(curves):
        x0, x1 = tracks[k]
        col = color(c["color"])
        dr.rectangle([x0, Y0, x1, Y1], fill=rgb(SG["panel"]), outline=rgb(col if c["key"] in hl else SG["muted"]),
                     width=6 if c["key"] in hl else 2)
        text(dr, ((x0 + x1) / 2, Y0 - 16), c["name"], 46, True, col, anchor="ms")
        n = max(2, int(d * 3))
        pts = [(x_of(k, value_at(params, c["key"], d * i / n)), y_of(d * i / n)) for i in range(n + 1)]
        if d > 0.2:
            dr.line(pts, fill=rgb(col), width=7, joint="curve")
        px = x_of(k, value_at(params, c["key"], d))
        dr.ellipse([px - 13, ty - 13, px + 13, ty + 13], fill=rgb(col), outline=rgb(SG["text"]), width=3)
    dr.line([cx + 16, ty, tracks[-1][1], ty], fill=rgb(SG["text"], 110), width=2)
    if beat.get("labels"):
        for L in params["layers"]:
            if d >= (L["top"] + L["bot"]) / 2:
                rows = [L["name"]] + ([L["fluid"]] if L.get("fluid") else [])
                f = font(44, True)
                ym = (y_of(L["top"]) + y_of(L["bot"])) / 2 - (len(rows) - 1) * 26
                tw2 = max(f.getlength(r) for r in rows)
                dr.rounded_rectangle([BX0 + 4, ym - 30, BX0 + 4 + tw2 + 20, ym + 30 + (len(rows) - 1) * 52], radius=10,
                                     fill=rgb(SG["background"], 215))
                for k, r in enumerate(rows):
                    dr.text((BX0 + 14, ym + k * 52), r, font=f, fill=rgb(SG["text"]), anchor="lm")
    if beat.get("card"):
        c = beat["card"]
        card(dr, (tracks[0][0] - 10, Y0 + 20, W - side + 10, Y1 - 20), c[0], c[1:], 44, color("measurement"))
    caption(dr, W, H, b.get("on_screen", ""), bot if H > W else 40, 48 if H > W else 46)
    return im
