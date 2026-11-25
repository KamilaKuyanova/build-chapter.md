"""Процесс как смена состояний с измеримыми величинами (М — механизм, процесс).
Модель состояния: непрерывный номер стадии s ∈ [0, N−1]. Цепочка «причина → следствие» и графики величин считаются из s,
между стадиями величины интерполируются. Параметры: stages [{name, note, values{ключ: число}}],
quantities [{key, name, color, range, unit}]. beat: s [от, до], card [заголовок, строки]."""
from canvas import SG, caption, card, color, current, font, header, layout, mix, new, rgb, text, track, wrap

NAME, TYPE = "process_state", "М"
STATE = "номер стадии процесса s (непрерывно); величины — функции s"
EXAMPLE = {
    "title": "Проникновение фильтрата в пласт",
    "stages": [{"name": "вскрытие", "note": "раствор под давлением контактирует с пластом", "values": {"inv": 0.0, "cake": 0.0}},
               {"name": "фильтрация", "note": "фильтрат уходит в поры, растёт зона проникновения", "values": {"inv": 0.6, "cake": 0.3}},
               {"name": "корка", "note": "глинистая корка тормозит фильтрацию", "values": {"inv": 0.8, "cake": 0.9}}],
    "quantities": [{"key": "inv", "name": "зона проникновения", "color": "fluids.filtrate", "range": [0, 1]},
                   {"key": "cake", "name": "толщина корки", "color": "fluids.mud", "range": [0, 1]}],
}


def spec(params):
    return {"scene": NAME, "difficulty_type": TYPE, "state_model": STATE,
            "objects": ["стадии: " + " → ".join(s["name"] for s in params["stages"]),
                        "величины: " + ", ".join(q["name"] for q in params["quantities"])],
            "parameters": params,
            "invariants": ["стадии идут только в порядке причина → следствие", "величины меняются непрерывно между стадиями",
                           "все виды считаются из одного значения s"],
            "assumptions": params.get("assumptions", ["значения величин условные, показано направление изменения"]),
            "frame_class": "B", "origin": "code_from_model", "label": "схема"}


def interp(params, key, s):
    st = params["stages"]
    i = min(int(s), len(st) - 2) if len(st) > 1 else 0
    f = s - i
    if len(st) == 1:
        return st[0]["values"][key]
    return st[i]["values"][key] + (st[i + 1]["values"][key] - st[i]["values"][key]) * min(1, max(0, f))


def render(t, beats, params, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    st = params["stages"]
    s = max(0.0, min(len(st) - 1, track(beats, t, "s", 0.0)))
    header(dr, L, params.get("title", ""), params.get("source_note"), "схема")
    x0, y0, x1, y1 = L["main"]
    n = len(st)
    # цепочка стадий
    cy = y0 + 90
    xs = [x0 + 70 + (x1 - x0 - 140) * k / max(1, n - 1) for k in range(n)]
    for k in range(n - 1):
        dr.line([xs[k] + 40, cy, xs[k + 1] - 40, cy], fill=rgb(SG["muted"]), width=5)
        dr.polygon([(xs[k + 1] - 40, cy - 14), (xs[k + 1] - 16, cy), (xs[k + 1] - 40, cy + 14)], fill=rgb(SG["muted"]))
    for k, x in enumerate(xs):
        done = s >= k - 0.02
        fill = color("measurement") if abs(s - k) < 0.5 else (mix(SG["panel"], color("measurement"), 0.35) if done else SG["panel"])
        dr.ellipse([x - 38, cy - 38, x + 38, cy + 38], fill=rgb(fill) if isinstance(fill, str) else fill,
                   outline=rgb(SG["text"]), width=3)
        text(dr, (x, cy), str(k + 1), 44, True, SG["background"] if abs(s - k) < 0.5 else SG["text"], anchor="mm")
        for j, ln in enumerate(wrap(st[k]["name"], 40, (x1 - x0) / max(1, n) - 10, True)[:2]):
            text(dr, (x, cy + 60 + j * 46), ln, 40, True, SG["text"] if done else SG["muted"], anchor="ma")
    px = xs[0] + (xs[-1] - xs[0]) * s / max(1, n - 1)
    dr.polygon([(px - 18, cy - 70), (px + 18, cy - 70), (px, cy - 46)], fill=rgb(SG["text"]))
    k = int(round(s))
    yy = cy + 180
    for ln in wrap(st[k]["note"], 44, x1 - x0 - 20)[:4]:
        text(dr, (x0 + 10, yy), ln, 44)
        yy += 56
    # величины как функции стадии
    sx0, sy0, sx1, sy1 = L["side"]
    dr.rectangle([sx0, sy0, sx1, sy1], fill=rgb(SG["panel"]))
    qs = params["quantities"]
    gx0, gx1 = sx0 + 40, sx1 - 40
    gy0, gy1 = sy0 + 70 + 46 * len(qs), sy1 - 60
    for j, q in enumerate(qs):
        text(dr, (sx0 + 30, sy0 + 20 + j * 46), "— " + q["name"] + (f", {q['unit']}" if q.get("unit") else ""), 38, True, color(q["color"]))
        lo, hi = q["range"]
        pts = []
        steps = max(2, int(s * 40))
        for i in range(steps + 1):
            ss = s * i / steps
            v = interp(params, q["key"], ss)
            pts.append((gx0 + (gx1 - gx0) * ss / max(1, n - 1), gy1 - (gy1 - gy0) * (v - lo) / (hi - lo)))
        if len(pts) > 1:
            dr.line(pts, fill=rgb(color(q["color"])), width=7, joint="curve")
        dr.ellipse([pts[-1][0] - 11, pts[-1][1] - 11, pts[-1][0] + 11, pts[-1][1] + 11], fill=rgb(color(q["color"])))
    dr.line([gx0, gy1, gx1, gy1], fill=rgb(SG["muted"]), width=3)
    for k2 in range(n):
        text(dr, (gx0 + (gx1 - gx0) * k2 / max(1, n - 1), gy1 + 8), str(k2 + 1), 36, fill=SG["muted"], anchor="ma")
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.1, H * 0.22, W * 0.9, H * 0.72), c[0], c[1:], 46, color("measurement"))
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im
