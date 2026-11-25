"""Тело в пространстве: план и разрез из одной геометрии (П — пространство).
Модель состояния: положение секущей линии y на плане и вертикальное преувеличение ve. Разрез по линии вычисляется из
той же формы тела. Формы: dome (купол: z = h·(1 − (x/a)² − (y/b)²)), lens (линза, симметрична вверх и вниз),
channel (русло вдоль y: z = h·(1 − (x/a)²) при |y| ≤ b). Параметры: body {shape, a_m, b_m, h_m, name, color}, host {name, color}.
beat: y [от, до] в долях полуоси (−1…1), ve [от, до] (1 — истинный масштаб), card."""
from canvas import preset, SG, caption, card, color, current, header, layout, new, rgb, text, track

NAME, TYPE = "section_views", "П"
STATE = "положение секущей линии y и вертикальное преувеличение ve; план и разрез — из одной формы тела"
EXAMPLE = preset(NAME)  # параметры-образец — в доменном пакете: templates/<шаблон>.json


def spec(params):
    bd = params["body"]
    return {"scene": NAME, "difficulty_type": TYPE, "state_model": STATE,
            "objects": [f"{bd['name']} ({bd['shape']}), {bd['a_m']}×{bd['b_m']} м в плане, {bd['h_m']} м высотой",
                        "план с секущей линией", "разрез по линии"],
            "parameters": params,
            "invariants": ["разрез вычисляется из той же формы, что и план", "вертикальное преувеличение подписано числом",
                           "хотя бы один кадр в истинном масштабе (ve = 1)"],
            "assumptions": params.get("assumptions", ["форма тела упрощена до гладкой поверхности"]),
            "frame_class": "B", "origin": "code_from_model", "label": "схема"}


def thickness(bd, x, y):
    a, b, h = bd["a_m"], bd["b_m"], bd["h_m"]
    if bd["shape"] == "channel":
        return h * max(0.0, 1 - (x / a) ** 2) if abs(y) <= b else 0.0
    return h * max(0.0, 1 - (x / a) ** 2 - (y / b) ** 2)


def render(t, beats, params, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    bd, host = params["body"], params["host"]
    yc = track(beats, t, "y", 0.0) * bd["b_m"]
    ve = max(1.0, track(beats, t, "ve", 10.0))
    header(dr, L, params.get("title", ""), params.get("source_note"), "схема")
    # план (истинный масштаб в плане)
    x0, y0, x1, y1 = L["main"]
    span_x, span_y = bd["a_m"] * 1.3, bd["b_m"] * 1.3
    k = min((x1 - x0) / (2 * span_x), (y1 - y0 - 80) / (2 * span_y))
    cx, cy = (x0 + x1) / 2, y0 + (y1 - y0 - 80) / 2
    dr.rectangle([cx - span_x * k, cy - span_y * k, cx + span_x * k, cy + span_y * k], fill=rgb(color(host["color"])))
    if bd["shape"] == "channel":
        dr.rectangle([cx - bd["a_m"] * k, cy - bd["b_m"] * k, cx + bd["a_m"] * k, cy + bd["b_m"] * k], fill=rgb(color(bd["color"])))
    else:
        for i in range(12, 0, -1):     # изолинии толщины
            f = i / 12
            dr.ellipse([cx - bd["a_m"] * k * f, cy - bd["b_m"] * k * f, cx + bd["a_m"] * k * f, cy + bd["b_m"] * k * f],
                       fill=rgb(color(bd["color"])) if i == 12 else None, outline=rgb(SG["background"], 90), width=2)
    ly = cy + yc * k
    dr.line([cx - span_x * k, ly, cx + span_x * k, ly], fill=rgb(color("measurement")), width=6)
    text(dr, (cx + span_x * k - 10, ly - 12), "линия разреза", 36, True, color("measurement"), anchor="rs")
    bar = 500 if bd["a_m"] > 800 else 100
    dr.line([cx - span_x * k, y1 - 40, cx - span_x * k + bar * k, y1 - 40], fill=rgb(SG["text"]), width=5)
    text(dr, (cx - span_x * k + bar * k + 14, y1 - 64), f"{bar} м · план в истинном масштабе", 36, fill=SG["muted"])
    # разрез по линии
    sx0, sy0, sx1, sy1 = L["side"]
    dr.rectangle([sx0, sy0, sx1, sy1], fill=rgb(SG["panel"]))
    kx = (sx1 - sx0 - 60) / (2 * span_x)
    kz = kx * ve
    zbase = sy0 + (sy1 - sy0) * (0.75 if bd["shape"] != "lens" else 0.55)
    dr.rectangle([sx0 + 30, sy0 + 90, sx1 - 30, sy1 - 30], fill=rgb(color(host["color"])))
    pts_top, pts_bot = [], []
    for i in range(241):
        x = -span_x + 2 * span_x * i / 240
        z = thickness(bd, x, yc)
        px = sx0 + 30 + (x + span_x) * kx
        if bd["shape"] == "lens":
            pts_top.append((px, zbase - z / 2 * kz))
            pts_bot.append((px, zbase + z / 2 * kz))
        else:
            pts_top.append((px, zbase - z * kz))
            pts_bot.append((px, zbase))
    poly = pts_top + pts_bot[::-1]
    if len(poly) > 2:
        dr.polygon(poly, fill=rgb(color(bd["color"])))
    true_scale = round(ve) <= 1
    label = "разрез · истинный масштаб" if true_scale else f"разрез · по вертикали ×{round(ve)}"
    text(dr, (sx0 + 30, sy0 + 20), label, 40, True, SG["text"] if true_scale else color("measurement"))
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.1, H * 0.22, W * 0.9, H * 0.72), c[0], c[1:], 46, color("measurement"))
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im
