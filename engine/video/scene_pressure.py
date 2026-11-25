"""Сцена «волна давления в упругом пласте» для разбора 16:9 (класс B, метка «симуляция»).
Модель: основная формула теории упругого режима (Басниев и др., стр. 491):
    Δp(r, t) = A · E1( r² / (4·κ·t) ),  E1 — интегральная показательная функция.
κ берётся из диапазона книги 0,1–5 м²/с (стр. 481). A — относительная единица (кадр не утверждает абсолютных МПа).
Три синхронных вида из одной модели: вид сверху (истинный масштаб, шкала в метрах), Δp(r) вдоль луча, Δp(t) в соседней
скважине на r0. Время модели t_model(t_video) задаётся сценарием (beat "tm": [от, до] в секундах модели, логарифмически).
beat "kappas": [κ…] — сравнение нескольких κ на графике Δp(t)."""
import math

from canvas import SG, card, caption, font, mix, new, provenance, rgb, text

W, H = 1920, 1080
R_MAX = 400.0   # м, радиус вида сверху
R0 = 200.0      # м, соседняя скважина
KAPPA = 1.0     # м²/с
T_MAX = 6 * 3600.0
GAMMA = 0.5772156649


def E1(x):
    if x <= 0:
        return 50.0
    if x <= 1.0:
        # ряд: E1 = -γ - ln x + Σ_{k≥1} (-1)^{k+1} x^k / (k·k!)
        s = -GAMMA - math.log(x)
        ser, fact, xp = 0.0, 1.0, 1.0
        for k in range(1, 40):
            fact *= k
            xp *= x
            ser += ((-1) ** (k + 1)) * xp / (k * fact)
        return s + ser
    # Abramowitz–Stegun 5.1.56 (x ≥ 1)
    a = (x * x + 2.334733 * x + 0.250621) / (x * x + 3.330657 * x + 1.681534)
    return a * math.exp(-x) / x


def dp(r, t, kappa=KAPPA):
    if t <= 0:
        return 0.0
    return E1(r * r / (4 * kappa * t))


def tmodel(beats, t):
    tm = 1.0
    for b in beats:
        rng = (b.get("beat") or {}).get("tm")
        if not rng:
            continue
        if t >= b["t_end"]:
            tm = rng[1]
        elif t >= b["t_start"]:
            p = (t - b["t_start"]) / max(0.01, b["t_end"] - b["t_start"])
            tm = math.exp(math.log(max(rng[0], 1)) + (math.log(max(rng[1], 1)) - math.log(max(rng[0], 1))) * p)
            break
        else:
            break
    return tm


def current(beats, t):
    cur = None
    for b in beats:
        if b["t_start"] - 0.05 <= t:
            cur = b
    return cur or beats[0]


def fmt_time(s):
    if s < 60:
        return f"{s:.0f} с"
    if s < 3600:
        return f"{s / 60:.0f} мин"
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h} ч {m:02d} мин"


SPEC = {
    "scene": "pressure_wave",
    "difficulty_type": "Ф",
    "objects": ["добывающая скважина", "соседняя (наблюдательная) скважина на 200 м", "однородный пласт, вид сверху",
                "график падения давления вдоль луча", "график падения давления в соседней скважине во времени"],
    "parameters": {"kappa_m2_s": KAPPA, "kappa_compare": [0.1, 5.0], "r_view_m": R_MAX, "r_observation_m": R0,
                   "t_model_max_s": T_MAX, "pressure_units": "относительные (E1), абсолютных МПа кадр не утверждает"},
    "invariants": [
        "все три вида вычисляются из одной формулы Δp = A·E1(r²/4κt) при одном и том же времени t",
        "вид сверху в истинном масштабе, линейка 100 м",
        "падение давления монотонно убывает с расстоянием и растёт со временем",
        "давление от высокого к низкому: к скважине",
    ],
    "assumptions": [
        "однородный бесконечный пласт, точечный сток с постоянным дебитом (условия основной формулы, стр. 491)",
        "однофазная упругая жидкость; давление выше давления насыщения (стр. 474)",
        "κ = 1 м²/с из типичного диапазона 0,1–5 м²/с (стр. 481)",
    ],
    "frame_class": "B", "origin": "code_from_model", "label": "симуляция",
}

PCOL = SG["curves"]["PRESSURE"]["color"]
DPMAX = 6.0  # ось Δp в относительных единицах (E1)
NEIGH_MAX = 1.0  # ось графика соседней скважины (те же единицы, крупнее)


def plan(dr, cx, cy, rad, tm):
    # кольца от внешнего к внутреннему; цвет — величина падения давления
    n = 90
    for i in range(n, 0, -1):
        r = R_MAX * i / n
        v = min(1.0, dp(r, tm) / 3.0)
        col = mix(SG["panel"], PCOL, v)
        rr = rad * i / n
        dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
    dr.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=rgb(SG["muted"]), width=2)
    dr.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=rgb(SG["text"]))
    text(dr, (cx - 20, cy - 30), "скважина", 44, True, anchor="rs")
    ox = cx + rad * R0 / R_MAX
    dr.ellipse([ox - 11, cy - 11, ox + 11, cy + 11], fill=rgb(SG["measurement"]["color"]))
    text(dr, (ox, cy + 30), "соседняя, 200 м", 44, True, SG["measurement"]["color"], anchor="ma")
    # масштабная линейка 100 м (истинный масштаб)
    sx0, sy = cx - rad, cy + rad + 50
    sx1 = sx0 + rad * 100 / R_MAX
    dr.line([sx0, sy, sx1, sy], fill=rgb(SG["text"]), width=5)
    text(dr, (sx1 + 14, sy - 26), "100 м · истинный масштаб", 40, fill=SG["muted"])


def axes(dr, box, xlab, ylab):
    x0, y0, x1, y1 = box
    dr.rectangle(box, fill=rgb(SG["panel"]))
    dr.line([x0 + 70, y1 - 96, x1 - 30, y1 - 96], fill=rgb(SG["muted"]), width=3)
    dr.line([x0 + 70, y0 + 20, x0 + 70, y1 - 96], fill=rgb(SG["muted"]), width=3)
    text(dr, (x1 - 30, y1 - 10), xlab, 36, fill=SG["muted"], anchor="rd")
    text(dr, (x0 + 80, y0 + 14), ylab, 36, fill=SG["muted"])
    return x0 + 70, y0 + 64, x1 - 30, y1 - 96   # область данных


def render(t, beats):
    im, dr = new(W, H)
    b = current(beats, t)
    beat = b.get("beat") or {}
    tm = tmodel(beats, t)
    provenance(dr, 60, 30)
    text(dr, (60, 86), f"после пуска скважины: {fmt_time(tm)}", 48, True)
    text(dr, (W - 60, 34), "κ = 1 м²/с · основная формула упругого режима, стр. 491", 40,
         fill=SG["muted"], anchor="ra")
    # вид сверху
    plan(dr, 400, 510, 270, tm)
    # Δp(r)
    ax = axes(dr, (800, 160, 1860, 520), "расстояние от скважины, м", "падение давления, отн. ед.")
    gx0, gy0, gx1, gy1 = ax
    pts = []
    for i in range(201):
        r = 2 + (R_MAX - 2) * i / 200
        v = min(DPMAX, dp(r, tm))
        pts.append((gx0 + (gx1 - gx0) * r / R_MAX, gy1 - (gy1 - gy0) * v / DPMAX))
    dr.line(pts, fill=rgb(PCOL), width=6, joint="curve")
    rx = gx0 + (gx1 - gx0) * R0 / R_MAX
    dr.line([rx, gy0, rx, gy1], fill=rgb(SG["measurement"]["color"], 160), width=3)
    for r in (0, 100, 200, 300, 400):
        text(dr, (gx0 + (gx1 - gx0) * r / R_MAX, gy1 + 8), str(r), 36, fill=SG["muted"], anchor="ma")
    # Δp(t) в соседней скважине (лог. время)
    ax2 = axes(dr, (800, 550, 1860, 900), "время после пуска (логарифмическая шкала)", "соседняя скважина, падение")
    hx0, hy0, hx1, hy1 = ax2
    lt0, lt1 = math.log(60), math.log(T_MAX)

    def xt(s):
        return hx0 + (hx1 - hx0) * (math.log(max(s, 60)) - lt0) / (lt1 - lt0)
    for lab, s in (("1 мин", 60), ("10 мин", 600), ("1 ч", 3600), ("6 ч", T_MAX)):
        text(dr, (xt(s), hy1 + 8), lab, 36, fill=SG["muted"], anchor="ma")
    kappas = beat.get("kappas") or [KAPPA]
    nmax = beat.get("neigh_max", NEIGH_MAX if len(kappas) == 1 else 2.0)
    # κ = 1 всегда цветом давления (как во всём ролике); сравнительные κ — нейтральными цветами стайлгайда
    shade = {KAPPA: PCOL, 0.1: SG["uncertainty"]["color"], 5.0: SG["fluids"]["filtrate"]["color"]}
    for j, kap in enumerate(kappas):
        col = shade.get(kap, SG["muted"])
        pts = []
        for i in range(161):
            s = math.exp(lt0 + (lt1 - lt0) * i / 160)
            if s > tm and kap == KAPPA:
                break
            v = min(nmax, dp(R0, s, kap))
            pts.append((xt(s), hy1 - (hy1 - hy0) * v / nmax))
        if len(pts) > 1:
            dr.line(pts, fill=rgb(col), width=6, joint="curve")
        if len(kappas) > 1:
            text(dr, (hx0 + 20, hy0 + 10 + j * 44), f"κ = {str(kap).replace('.', ',')} м²/с", 36, True, col)
    dr.line([xt(tm), hy0, xt(tm), hy1], fill=rgb(SG["text"], 120), width=2)
    if beat.get("card"):
        c = beat["card"]
        card(dr, (420, 220, 1500, 860), c[0], c[1:], 46, PCOL)
    caption(dr, W, H, b.get("on_screen", ""), 40, 46)
    return im
