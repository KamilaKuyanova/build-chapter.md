"""Формула как управляемая модель: синхронные виды из одного расчёта (Ф — формализм, модель).
Модели:
- radial_diffusion: Δp(r,t) = A·E1(r²/4κt) (основная формула упругого режима); вид сверху в истинном масштабе, профиль Δp(r)
  и кривая Δp(t) в наблюдательной точке r_obs. Состояние — время t (beat tm, логарифмически); beat kappas — сравнение κ.
- expression: y = f(x; p) по формуле из параметров; состояние — параметр p (beat p), след прошлых значений остаётся бледным."""
import math

from canvas import preset, SG, caption, card, color, current, font, layout, mix, new, provenance, rgb, text, track

NAME, TYPE = "formula_explorer", "Ф"
STATE = "время модели t (radial_diffusion) или параметр формулы p (expression); все виды считаются из одного значения"
GAMMA = 0.5772156649
EXAMPLE = preset(NAME)  # параметры-образец — в доменном пакете: templates/<шаблон>.json
EXAMPLE_EXPR = preset(NAME + ".expression")

SAFE = {k: getattr(math, k) for k in ("exp", "log", "log10", "sqrt", "sin", "cos", "tan", "atan", "pi", "e", "erf", "erfc", "tanh")}


def E1(x):
    if x <= 0:
        return 50.0
    if x <= 1.0:
        s, ser, fact, xp = -GAMMA - math.log(x), 0.0, 1.0, 1.0
        for k in range(1, 40):
            fact *= k
            xp *= x
            ser += ((-1) ** (k + 1)) * xp / (k * fact)
        return s + ser
    a = (x * x + 2.334733 * x + 0.250621) / (x * x + 3.330657 * x + 1.681534)
    return a * math.exp(-x) / x


def dp(r, t, kappa):
    return 0.0 if t <= 0 else E1(r * r / (4 * kappa * t))


def spec(params):
    if params["model"] == "radial_diffusion":
        return {"scene": NAME, "model": "radial_diffusion", "difficulty_type": TYPE, "state_model": STATE,
                "objects": ["скважина", f"наблюдательная точка на {params['r_obs']:.0f} м", "вид сверху", "профиль Δp(r)", "кривая Δp(t)"],
                "parameters": {k: params[k] for k in ("kappa", "r_view", "r_obs", "t_max")},
                "invariants": ["три вида из одной формулы при одном времени t", "вид сверху в истинном масштабе, линейка 100 м",
                               "падение давления убывает с расстоянием и растёт со временем"],
                "assumptions": params.get("assumptions", ["однородный бесконечный пласт, точечный сток с постоянным дебитом",
                                                          "давление в относительных единицах"]),
                "frame_class": "B", "origin": "code_from_model", "label": "симуляция"}
    return {"scene": NAME, "model": "expression", "difficulty_type": TYPE, "state_model": STATE,
            "objects": ["график " + params["formula_text"]], "parameters": params,
            "invariants": ["кривая вычисляется по формуле при текущем значении параметра", "оси и единицы подписаны"],
            "assumptions": params.get("assumptions", ["формула и её область применимости — из главы"]),
            "frame_class": "B", "origin": "code_from_model", "label": "схема"}


def fmt_time(s):
    if s < 60:
        return f"{s:.0f} с"
    if s < 3600:
        return f"{s / 60:.0f} мин"
    return f"{int(s // 3600)} ч {int(s % 3600 // 60):02d} мин"


def axes(dr, box, xlab, ylab):
    x0, y0, x1, y1 = box
    dr.rectangle(box, fill=rgb(SG["panel"]))
    dr.line([x0 + 70, y1 - 96, x1 - 30, y1 - 96], fill=rgb(SG["muted"]), width=3)
    dr.line([x0 + 70, y0 + 20, x0 + 70, y1 - 96], fill=rgb(SG["muted"]), width=3)
    text(dr, (x1 - 30, y1 - 10), xlab, 36, fill=SG["muted"], anchor="rd")
    text(dr, (x0 + 80, y0 + 14), ylab, 36, fill=SG["muted"])
    return x0 + 70, y0 + 64, x1 - 30, y1 - 96


def render_radial(t, beats, P, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    tm = track(beats, t, "tm", 1.0, log=True)
    K, RV, R0, TMAX = P["kappa"], P["r_view"], P["r_obs"], P["t_max"]
    PCOL = color("curves.PRESSURE")
    hx0, hy0, hx1, hy1 = L["head"]
    provenance(dr, hx0, hy0 + 10)
    text(dr, (hx0, hy0 + 66), f"после пуска скважины: {fmt_time(tm)}", 48 if not L["vertical"] else 44, True)
    if P.get("source_note"):
        if L["vertical"]:
            text(dr, (hx0, hy0 + 124), P["source_note"], 32, fill=SG["muted"])
        else:
            text(dr, (hx1, hy0 + 14), P["source_note"], 40, fill=SG["muted"], anchor="ra")
    if L["vertical"]:   # 9:16: вид сверху компактнее, графикам больше места
        bx0, by0, bx1, by1 = L["main"][0], L["main"][1] + 20, L["side"][2], L["side"][3]
        cut = by0 + (by1 - by0) * 0.46
        L = dict(L, main=(bx0, by0, bx1, cut), side=(bx0, cut + 30, bx1, by1))
    # вид сверху
    mx0, my0, mx1, my1 = L["main"]
    rad = min(mx1 - mx0, my1 - my0 - (120 if not L["vertical"] else 80)) / 2 - 10
    cx, cy = (mx0 + mx1) / 2, my0 + rad + 20
    for i in range(90, 0, -1):
        r = RV * i / 90
        v = min(1.0, dp(r, tm, K) / 3.0)
        rr = rad * i / 90
        dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=mix(SG["panel"], PCOL, v))
    dr.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=rgb(SG["muted"]), width=2)
    dr.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=rgb(SG["text"]))
    text(dr, (cx - 20, cy - 30), "скважина", 44, True, anchor="rs")
    ox = cx + rad * R0 / RV
    dr.ellipse([ox - 11, cy - 11, ox + 11, cy + 11], fill=rgb(color("measurement")))
    text(dr, (ox, cy + 30), f"соседняя, {R0:.0f} м", 44, True, color("measurement"), anchor="ma")
    sx0, sy = cx - rad, cy + rad + 50
    dr.line([sx0, sy, sx0 + rad * 100 / RV, sy], fill=rgb(SG["text"]), width=5)
    text(dr, (sx0 + rad * 100 / RV + 14, sy - 26), "100 м · истинный масштаб", 40, fill=SG["muted"])
    # синхронные графики
    sx0_, sy0_, sx1_, sy1_ = L["side"]
    mid = (sy0_ + sy1_) / 2
    gx0, gy0, gx1, gy1 = axes(dr, (sx0_, sy0_, sx1_, mid - 15), "расстояние от скважины, м", "падение давления, отн. ед.")
    pts = []
    for i in range(201):
        r = 2 + (RV - 2) * i / 200
        pts.append((gx0 + (gx1 - gx0) * r / RV, gy1 - (gy1 - gy0) * min(6.0, dp(r, tm, K)) / 6.0))
    dr.line(pts, fill=rgb(PCOL), width=6, joint="curve")
    rx = gx0 + (gx1 - gx0) * R0 / RV
    dr.line([rx, gy0, rx, gy1], fill=rgb(color("measurement"), 160), width=3)
    for r in range(0, int(RV) + 1, int(RV // 4)):
        text(dr, (gx0 + (gx1 - gx0) * r / RV, gy1 + 8), str(r), 36, fill=SG["muted"], anchor="ma")
    ax0, ay0, ax1, ay1 = axes(dr, (sx0_, mid + 15, sx1_, sy1_), "время после пуска (логарифмическая шкала)", "соседняя точка, падение")
    lt0, lt1 = math.log(60), math.log(TMAX)

    def xt(s):
        return ax0 + (ax1 - ax0) * (math.log(max(s, 60)) - lt0) / (lt1 - lt0)
    for lab, s in (("1 мин", 60), ("10 мин", 600), ("1 ч", 3600), (fmt_time(TMAX).replace(" 00 мин", ""), TMAX)):
        text(dr, (xt(s), ay1 + 8), lab, 36, fill=SG["muted"], anchor="ma")
    kappas = beat.get("kappas") or [K]
    nmax = beat.get("neigh_max", 1.0 if len(kappas) == 1 else 2.0)
    shade = {K: PCOL}
    others = [color("uncertainty"), color("fluids.filtrate"), SG["muted"]]
    for j, kap in enumerate(kappas):
        col = shade.get(kap) or others[j % 3]
        pts = []
        for i in range(161):
            s = math.exp(lt0 + (lt1 - lt0) * i / 160)
            if s > tm and kap == K:
                break
            pts.append((xt(s), ay1 - (ay1 - ay0) * min(nmax, dp(R0, s, kap)) / nmax))
        if len(pts) > 1:
            dr.line(pts, fill=rgb(col), width=6, joint="curve")
        if len(kappas) > 1:
            text(dr, (ax0 + 20, ay0 + 10 + j * 44), f"κ = {str(kap).replace('.', ',')} м²/с", 36, True, col)
    dr.line([xt(tm), ay0, xt(tm), ay1], fill=rgb(SG["text"], 120), width=2)
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.22, H * 0.2, W * 0.78, H * 0.8), c[0], c[1:], 46, PCOL)
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im


def render_expr(t, beats, P, W, H):
    im, dr = new(W, H)
    L = layout(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    p = track(beats, t, "p", P.get("p0", 1.0))
    hx0, hy0, hx1, hy1 = L["head"]
    provenance(dr, hx0, hy0 + 10, "схема")
    text(dr, (hx0, hy0 + 66), f"{P['formula_text']},  {P['p_name']} = {p:.3g} {P.get('p_unit', '')}".replace(".", ","), 48, True)
    if P.get("source_note"):
        text(dr, (hx1, hy0 + 14), P["source_note"], 38, fill=SG["muted"], anchor="ra")
    box = (L["main"][0], L["main"][1], L["side"][2], L["side"][3])
    gx0, gy0, gx1, gy1 = axes(dr, box, P["x_label"], P["y_label"])
    (xa, xb), (ya, yb) = P["x_range"], P["y_range"]
    code = compile(P["expr"], "<formula>", "eval")

    def curve(pv, col, w):
        pts = []
        for i in range(301):
            x = xa + (xb - xa) * i / 300
            try:
                y = eval(code, {"__builtins__": {}}, dict(SAFE, x=x, p=pv))
            except (ValueError, ZeroDivisionError, OverflowError):
                continue
            yy = gy1 - (gy1 - gy0) * (min(max(y, ya), yb) - ya) / (yb - ya)
            pts.append((gx0 + (gx1 - gx0) * i / 300, yy))
        if len(pts) > 1:
            dr.line(pts, fill=rgb(col), width=w, joint="curve")
    for pv in beat.get("ghosts", []):
        curve(pv, color("uncertainty"), 3)
    curve(p, color("curves.PRESSURE"), 7)
    for k in range(5):
        xv = xa + (xb - xa) * k / 4
        text(dr, (gx0 + (gx1 - gx0) * k / 4, gy1 + 8), f"{xv:g}".replace(".", ","), 36, fill=SG["muted"], anchor="ma")
    if beat.get("card"):
        c = beat["card"]
        card(dr, (W * 0.22, H * 0.2, W * 0.78, H * 0.8), c[0], c[1:], 46, color("curves.PRESSURE"))
    caption(dr, W, H, b.get("on_screen", ""), L["caption_bottom"], L["caption_size"])
    return im


def render(t, beats, params, W, H):
    return (render_radial if params["model"] == "radial_diffusion" else render_expr)(t, beats, params, W, H)
