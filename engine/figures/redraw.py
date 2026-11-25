#!/usr/bin/env python3
"""Перерисовка рисунков книги кодом (ТЗ: «рисунок книги, на котором держится пример или задача, перерисовывается кодом
по скану с подписью «перерисовано по рис. N, стр. M»; вставлять рисунки книги нельзя»).

Рисунок описывается JSON-файлом data/<глава>/figures/<id>.json:
  панели (panels) с осями x/y (linear | log | piecewise — неравномерная шкала, как на скане), кривые, заливки областей
  между кривыми, вертикальные/горизонтальные линии, подписи, точки примеров книги. Координаты — в единицах осей
  или в пикселях скана (units: "px" + calibration), тогда они переводятся по калибровке.
Выход: data/<глава>/illustrations/<id>.svg + запись для illustrations.json (figures_extra.json) для шагов-примеров.
Запуск: python engine/figures/redraw.py --dir data/latyshova"""
import argparse
import html
import json
import math
import pathlib
import sys as _sys_d  # noqa: E402
_sys_d.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
import domain  # noqa: E402  доменный пакет по имени домена (DOMAIN)

ROOT = pathlib.Path(__file__).resolve().parents[2]
SG = domain.load("styleguide.json")


def col(key):
    if key.startswith("#"):
        return key
    node = SG
    for p in key.split("."):
        node = node[p]
    return node["color"] if isinstance(node, dict) else node


FONT = 29  # при ширине рисунка 640 и экране 390 px (358 px под картинку) подпись 29 -> 16,2 px


def esc(s):
    return html.escape(str(s), quote=True)


class Axis:
    def __init__(self, a, lo_px, hi_px, calib=None, invert=False):
        self.a, self.lo, self.hi, self.inv = a, lo_px, hi_px, invert
        self.kind = a.get("scale", "linear")
        self.calib = calib

    def frac(self, v):
        r = self.a["range"]
        if self.kind == "log":
            f = (math.log10(v) - math.log10(r[0])) / (math.log10(r[1]) - math.log10(r[0]))
        elif self.kind == "piecewise":  # неравномерная шкала: [[значение, доля 0..1], …]
            pts = self.a["positions"]
            f = pts[-1][1]
            for (v0, f0), (v1, f1) in zip(pts, pts[1:]):
                if v <= v1 or (v1, f1) == tuple(pts[-1]):
                    f = f0 + (f1 - f0) * (v - v0) / (v1 - v0)
                    break
        else:
            f = (v - r[0]) / (r[1] - r[0])
        return f

    def px(self, v):
        f = self.frac(v)
        return self.hi - f * (self.hi - self.lo) if self.inv else self.lo + f * (self.hi - self.lo)


def from_scan(pt, cal):
    """Пиксели скана -> единицы осей по калибровке: x и y — пары [[значение, пиксель]…]; log — логарифмическая ось."""
    out = []
    for key, p in zip(("x", "y"), pt):
        c = cal[key]
        pairs = c["pairs"]
        for (v0, p0), (v1, p1) in zip(pairs, pairs[1:]):
            if min(p0, p1) <= p <= max(p0, p1) or (v1, p1) == tuple(pairs[-1]):
                t = (p - p0) / (p1 - p0)
                if c.get("log"):
                    out.append(10 ** (math.log10(v0) + t * (math.log10(v1) - math.log10(v0))))
                else:
                    out.append(v0 + t * (v1 - v0))
                break
    return out


def dash(style):
    return {"dashed": ' stroke-dasharray="14 9"', "dashdot": ' stroke-dasharray="18 7 4 7"', "dotted": ' stroke-dasharray="3 7"'}.get(style, "")


class Labels:
    """Ставит подписи так, чтобы они не выходили за край и не накрывали друг друга (сдвиг вниз или вверх на строку)."""

    def __init__(self, x0, x1, y0, y1):
        self.x0, self.x1, self.y0, self.y1, self.boxes = x0, x1, y0, y1, []

    def put(self, x, y, text, fill, anchor="middle", weight=700):
        w = len(str(text)) * FONT * 0.56
        left = x - w / 2 if anchor == "middle" else x if anchor == "start" else x - w
        base, row, best = left, FONT + 4, None
        for dx, dy in ((0, 0), (0, row), (0, -row), (0.5 * w, 0), (-0.5 * w, 0), (w + 10, 0), (0, 2 * row), (0, -2 * row), (w, -row), (-w, -row), (w, row)):
            left = min(max(base + dx, self.x0), self.x1 - w)
            box = (left, y + dy - FONT * 0.8, left + w, y + dy + FONT * 0.2)
            if not (self.y0 <= box[1] and box[3] <= self.y1) and dy:
                continue
            if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in self.boxes):
                best = (left, dy, box)
                break
        left, dy, box = best or (min(max(base, self.x0), self.x1 - w), 0, (base, y - FONT, base + w, y))
        self.boxes.append(box)
        return (f'<text x="{left:.1f}" y="{y + dy:.1f}" font-size="{FONT}" font-weight="{weight}" fill="{fill}" '
                f'stroke="{SG["background"]}" stroke-width="6" stroke-linejoin="round" paint-order="stroke">{esc(text)}</text>')


def panel_svg(P, box, cal):
    x0, y0, x1, y1 = box
    end = any(c.get("label") and not c.get("label_at") for c in P.get("curves", []))
    gx0, gy0, gx1, gy1 = x0 + 66, y0 + 56, x1 - (62 if end else 22), y1 - 92
    lab = Labels(x0 + 2, x1 - 2, gy0 - 10, gy1)
    X = Axis(P["x"], gx0, gx1)
    Y = Axis(P["y"], gy0, gy1, invert=True)
    conv = (lambda p: from_scan(p, cal)) if P.get("units") == "px" else (lambda p: p)
    curves = {c["id"]: [conv(p) for p in c["points"]] for c in P.get("curves", [])}
    s = [f'<rect x="{gx0}" y="{gy0}" width="{gx1 - gx0}" height="{gy1 - gy0}" fill="{SG["panel"]}" stroke="{SG["muted"]}"/>']
    # заливки между кривыми (по общей сетке x)
    for f in P.get("fills", []):
        a, b = curves[f["upper"]], curves.get(f["lower"]) if f.get("lower") else None
        lo_x = max(f.get("x", [-1e9])[0], a[0][0], b[0][0] if b else -1e9)
        hi_x = min(f.get("x", [0, 1e9])[1], a[-1][0], b[-1][0] if b else 1e9)

        def interp_px(cv, x):
            """y кривой в пикселях: интерполяция в пространстве шкал (верно и для логарифмических/неравномерных осей)."""
            for (xa, ya), (xb, yb) in zip(cv, cv[1:]):
                if xa <= x <= xb:
                    fa, fb, fx = X.frac(xa), X.frac(xb), X.frac(x)
                    t = (fx - fa) / (fb - fa) if fb != fa else 0
                    return Y.px(ya) + (Y.px(yb) - Y.px(ya)) * t
            return Y.px(cv[-1][1])
        xs = [lo_x + (hi_x - lo_x) * i / 120 for i in range(121)]
        top = [(X.px(x), interp_px(a, x)) for x in xs]
        bot = [(X.px(x), interp_px(b, x) if b else Y.px(P["y"]["range"][0])) for x in xs[::-1]]
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in top + bot)
        s.append(f'<polygon points="{pts}" fill="{col(f["color"])}" fill-opacity="{f.get("opacity", 0.35)}"/>')
        if f.get("label"):
            lx = X.px(f["label_at"][0])
            ly = Y.px(f["label_at"][1])
            s.append(lab.put(lx, ly, f["label"], SG["text"]))
    # сетка и подписи осей
    last = -1e9
    for v in P["x"].get("ticks", []):   # подписи, которые налезли бы на соседнюю, пропускаются (засечка остаётся)
        px = X.px(v)
        wide = len(str(v)) * FONT * 0.56 + 8
        show = px - last >= wide
        last = px if show else last
        s.append(f'<line x1="{px:.1f}" y1="{gy1}" x2="{px:.1f}" y2="{gy1 + 8}" stroke="{SG["muted"]}"/>')
        if show:
            s.append(f'<text x="{px:.1f}" y="{gy1 + 38}" font-size="{FONT}" fill="{SG["muted"]}" text-anchor="middle">{esc(str(v).replace(".", ","))}</text>')
    last = 1e9
    for v in P["y"].get("ticks", []):
        py = Y.px(v)
        show = last - py >= FONT
        last = py if show else last
        s.append(f'<line x1="{gx0 - 8}" y1="{py:.1f}" x2="{gx1}" y2="{py:.1f}" stroke="{SG["muted"]}" stroke-opacity="0.25"/>')
        if show:
            s.append(f'<text x="{gx0 - 10}" y="{py + 10:.1f}" font-size="{FONT}" fill="{SG["muted"]}" text-anchor="end">{esc(str(v).replace(".", ","))}</text>')
    s.append(f'<text x="{gx1}" y="{gy1 + 78}" font-size="{FONT}" fill="{SG["text"]}" text-anchor="end">{esc(P["x"]["label"])}</text>')
    s.append(f'<text x="{x0 + 4}" y="{gy0 - 20}" font-size="{FONT}" fill="{SG["text"]}">{esc(P["y"]["label"])}</text>')
    for ln in P.get("vlines", []):
        px = X.px(ln["x"])
        ya, yb = (Y.px(ln["y"][0]), Y.px(ln["y"][1])) if ln.get("y") else (gy0, gy1)
        s.append(f'<line x1="{px:.1f}" y1="{ya:.1f}" x2="{px:.1f}" y2="{yb:.1f}" stroke="{col(ln.get("color", "muted"))}" stroke-width="2.5"{dash(ln.get("style", "dashed"))}/>')
        if ln.get("label"):
            s.append(lab.put(px, gy1 - 10, ln["label"], SG["text"], weight=400))
    for ln in P.get("hlines", []):
        py = Y.px(ln["y"])
        xa, xb = (X.px(ln["x"][0]), X.px(ln["x"][1])) if ln.get("x") else (gx0, gx1)
        s.append(f'<line x1="{xa:.1f}" y1="{py:.1f}" x2="{xb:.1f}" y2="{py:.1f}" stroke="{SG["muted"]}" stroke-width="2.5"{dash("dashed")}/>')
        if ln.get("label"):
            s.append(lab.put(gx0 + 8, py - 8, ln["label"], SG["text"], "start", 400))
    later = []
    for c in P.get("curves", []):
        pts = " ".join(f"{X.px(x):.1f},{Y.px(y):.1f}" for x, y in curves[c["id"]])
        s.append(f'<polyline points="{pts}" fill="none" stroke="{col(c.get("color", "text"))}" stroke-width="{c.get("width", 4)}" '
                 f'stroke-linejoin="round"{dash(c.get("style"))}/>')
        if c.get("label"):
            later.append((c.get("label_at") or curves[c["id"]][-1], c["label"], col(c.get("color", "text"))))
    for p in P.get("points", []):
        px, py = X.px(p["x"]), Y.px(p["y"])
        s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="10" fill="{col("measurement")}" stroke="{SG["background"]}" stroke-width="3"/>')
        s.append(lab.put(px + 16, py - 12, p["label"], col("measurement"), "start"))
    for (x, y), text, color in later:
        s.append(lab.put(X.px(x) + 6, Y.px(y) - 6, text, color, "start"))
    for t in P.get("texts", []):
        s.append(lab.put(X.px(t["x"]), Y.px(t["y"]), t["text"], col(t.get("color", "text"))))
    return "".join(s)


def head_svg(s, F, label, W):
    """Заголовок, метка, источник; возвращает нижний край."""
    s.append(f'<rect x="20" y="18" width="{30 + len(label) * 17}" height="44" rx="8" fill="{SG["provenance"][label]}"/>')
    s.append(f'<text x="35" y="50" font-size="29" font-weight="600" fill="#FFFFFF">{esc(label)}</text>')
    y = 104
    for ln in wrap_px(F["title"], W - 40, 34):
        s.append(f'<text x="20" y="{y}" font-size="34" font-weight="700" fill="{SG["text"]}">{esc(ln)}</text>')
        y += 42
    for ln in wrap_px(F["source"], W - 40, 29):
        s.append(f'<text x="20" y="{y}" font-size="29" fill="{SG["muted"]}">{esc(ln)}</text>')
        y += 36
    return y


def note_svg(s, text, y, W):
    for ln in wrap_px(text, W - 40, 29) if text else []:
        s.append(f'<text x="20" y="{y}" font-size="29" fill="{SG["muted"]}">{esc(ln)}</text>')
        y += 36
    return y


def finish_svg(s, F, W, H):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}" style="max-width:100%;height:auto" '
            f'role="img" aria-label="{esc(F["alt"])}" font-family="Segoe UI, sans-serif">'
            f'<rect width="{W}" height="{H:.0f}" fill="{SG["background"]}"/>' + "".join(s) + "</svg>")


def figure_svg(F):
    W, s = 640, []
    y = head_svg(s, F, "схема", W) + 8
    for lg in F.get("legend", []):
        s.append(f'<rect x="20" y="{y - 20}" width="34" height="24" fill="{col(lg["color"])}" fill-opacity="{lg.get("opacity", 0.6)}"/>')
        for ln in wrap_px(lg["text"], W - 100, 29):
            s.append(f'<text x="68" y="{y}" font-size="29" fill="{SG["text"]}">{esc(ln)}</text>')
            y += 36
    for P in F["panels"]:
        h = max(560, min(760, P.get("height", 620)))
        s.append(panel_svg(P, (8, y, W - 8, y + h), F.get("calibration")))
        y += h + 10
    return finish_svg(s, F, W, note_svg(s, F.get("note", ""), y + 30, W) + 10)


def wrap_px(text, width, size):
    """Перенос по ширине в пикселях (оценка ширины символа Segoe UI ≈ 0,55 кегля)."""
    import textwrap
    return textwrap.wrap(text, width=max(8, int(width / (size * 0.55))), break_long_words=False) or [""]


def joined(ink, grid, span):
    """Кривая, разорванная стёртой линией сетки, сшивается: концы по обе стороны одной линии, рядом по глубине и по ширине.
    Другие разрывы (штриховые и точечные линии книги) не трогаются."""
    parts = [list(p) for p in ink if len(p) > 1]
    for g in grid:
        ups = [p for p in parts if -0.012 * span <= max(p[0][1], p[-1][1]) - g <= 0.004 * span]
        downs = [p for p in parts if -0.004 * span <= min(p[0][1], p[-1][1]) - g <= 0.012 * span]
        pairs = []
        for u in ups:
            eu = u[0] if u[0][1] > u[-1][1] else u[-1]
            for d in downs:
                ed = d[0] if d[0][1] < d[-1][1] else d[-1]
                if u is not d and ed[1] >= eu[1] and abs(ed[0] - eu[0]) <= 0.05:
                    pairs.append((abs(ed[0] - eu[0]), id(u), id(d), u, d))
        seen = set()
        for _, iu, idn, u, d in sorted(pairs, key=lambda q: q[0]):
            if iu in seen or idn in seen or not any(x is u for x in parts) or not any(x is d for x in parts):
                continue
            seen |= {iu, idn}
            first = u if u[-1][1] >= u[0][1] else u[::-1]
            second = d if d[0][1] <= d[-1][1] else d[::-1]
            parts = [x for x in parts if x is not u and x is not d] + [first + second]
    return parts


def log_svg(F):
    """Каротажная диаграмма книги: кривые — оцифровка скана (trace_log.py), шкалы — из шапки рисунка.
    Раскладка для телефона: ширина 640, по 1–2 дорожки в ряд, у каждого ряда своя шкала глубин; в шапке номер дорожки и шкала,
    под рядом — расшифровка номеров. Ряды одной панели имеют общий интервал глубин, поэтому их можно сопоставлять."""
    W, s, DEPTH, PAD = 640, [], 92, 20
    label, axis = F.get("label", "реальные данные"), F.get("depth_axis", True)
    y = head_svg(s, F, label, W) + 10
    panels, stack = F["scan"]["panels"], F.get("layout") == "stack"
    many = len(panels) > 1
    base = panels[0]["tracks"]
    if stack and len(base) == 1:   # одна дорожка, несколько участков: расшифровка один раз сверху
        y = note_svg(s, f'{base[0]["title"]}. {base[0].get("scale", "")}', y + 20, W) + 4
    elif stack:
        y += 26
        for k, T in enumerate(base, 1):
            for i, ln in enumerate(wrap_px(f'{T["title"].replace(chr(173), "").rstrip(".")}. {T.get("scale", "")}', W - 2 * PAD - 60, 29)):
                if i == 0:
                    s.append(f'<text x="{PAD}" y="{y}" font-size="29" font-weight="700" fill="{SG["measurement"]["color"]}">{k}</text>')
                s.append(f'<text x="{PAD + 50}" y="{y}" font-size="29" fill="{SG["text"]}">{esc(ln)}</text>')
                y += 36
        y += 4
    n = 0
    for pi, P in enumerate(panels):
        tracks = P["tracks"]
        d0, d1 = P["depth_range"]
        span = d1 - d0
        if many and stack:
            s.append(f'<text x="{PAD}" y="{y + 30}" font-size="30" font-weight="700" fill="{SG["text"]}">'
                     f'{"участок " + "абвгд"[pi]}{f": {d0:.0f}–{d1:.0f} м" if axis else ""}</text>')
            y += 44
        rows, cur = [], []
        per = 3 if len(tracks) >= 6 else 2
        for T in tracks:   # широкая дорожка с несколькими кривыми занимает ряд целиком, узкие идут по две-три
            if T.get("skip_trace") and not cur and rows and len(rows[-1]) < per:   # столбец значений — рядом со своей кривой
                rows[-1].append(T)
                continue
            cur.append(T)
            if len(cur) == per or (T["x"][1] - T["x"][0]) > 0.42 * (tracks[-1]["x"][1] - tracks[0]["x"][0]):
                rows.append(cur)
                cur = []
        if cur:
            rows.append(cur)
        fixed = [r for r in rows]
        for row in fixed:
            src = sum(T["x"][1] - T["x"][0] for T in row)
            room = W - 2 * PAD - DEPTH - 12 * (len(row) - 1)
            share = [0.22 if T.get("skip_trace") and len(row) > 1 else max(0.3, (T["x"][1] - T["x"][0]) / src) if len(row) > 1 else 1 for T in row]
            widths = [room * k / sum(share) for k in share]
            nt = max([len(T.get("ticks") or base[i].get("ticks", []) if len(tracks) == len(base) else T.get("ticks", [])) for i, T in enumerate(row)] + [0])
            solo = stack and len(base) == 1
            head = (14 if solo else 52) + 40 * nt
            h = (420 if stack else 720) if span > 12 or not stack else 330
            yb = y + head
            Y = lambda d: yb + (d - d0) / span * h  # noqa: E731
            s.append(f'<rect x="{PAD}" y="{yb:.0f}" width="{DEPTH}" height="{h}" fill="{SG["panel"]}" stroke="{SG["muted"]}"/>')
            s.append(f'<text x="{PAD}" y="{yb - 12:.0f}" font-size="29" fill="{SG["muted"]}">{"м" if axis else "пласт"}</text>')
            step = next(q for q in (1, 2, 5, 10, 20, 50, 100) if span / q <= h / 60)
            dd = math.ceil(d0 / step) * step if axis else d1 + 1
            while dd <= d1:
                if yb + 24 < Y(dd) < yb + h - 8:
                    s.append(f'<line x1="{PAD + DEPTH - 10}" y1="{Y(dd):.1f}" x2="{PAD + DEPTH}" y2="{Y(dd):.1f}" stroke="{SG["muted"]}" stroke-width="2"/>')
                    s.append(f'<text x="{PAD + DEPTH - 14}" y="{Y(dd) + 10:.1f}" font-size="{FONT}" fill="{SG["text"]}" text-anchor="end">{dd:g}</text>')
                dd += step
            x, legend = PAD + DEPTH, []
            for T, tw in zip(row, widths):
                ti = tracks.index(T)
                n = ti + 1 if stack else n + 1
                Tick = T.get("ticks") or (base[ti].get("ticks", []) if ti < len(base) else [])
                title, scale = T["title"].replace("\u00ad", "").rstrip("."), T.get("scale", "") or (base[ti].get("scale", "") if ti < len(base) else "")
                legend.append((n, f"{title}. {scale}".strip()))
                if not solo:
                    s.append(f'<rect x="{x:.1f}" y="{y + 4:.0f}" width="46" height="42" rx="8" fill="{SG["measurement"]["color"]}"/>')
                    s.append(f'<text x="{x + 23:.1f}" y="{y + 36:.0f}" font-size="30" font-weight="700" fill="#10151B" text-anchor="middle">{n}</text>')
                for r, line in enumerate(Tick[::-1]):
                    yy = yb - 8 - 40 * r
                    s.append(f'<line x1="{x:.1f}" y1="{yy:.1f}" x2="{x + tw:.1f}" y2="{yy:.1f}" stroke="{SG["muted"]}" stroke-opacity="0.6"/>')
                    last = -1e9
                    for fx, txt in line["at"]:
                        px, half = x + fx * tw, len(txt) * 29 * 0.27
                        left = min(max(px - half, x + 2), x + tw - 2 * half)
                        s.append(f'<line x1="{px:.1f}" y1="{yy - 6:.1f}" x2="{px:.1f}" y2="{yy + 5:.1f}" stroke="{SG["muted"]}" stroke-width="2"/>')
                        if left - last >= 8 and left >= x:
                            s.append(f'<text x="{left:.1f}" y="{yy - 9:.1f}" font-size="29" fill="{SG["text"]}">{esc(txt)}</text>')
                            last = left + 2 * half
                s.append(f'<rect x="{x:.1f}" y="{yb:.0f}" width="{tw:.1f}" height="{h}" fill="{SG["panel"]}" stroke="{SG["muted"]}"/>')
                for g in P.get("grid", []):
                    s.append(f'<line x1="{x:.1f}" y1="{Y(g):.1f}" x2="{x + tw:.1f}" y2="{Y(g):.1f}" stroke="{SG["muted"]}" stroke-opacity="0.35"/>')
                for fx in (base[ti].get("vgrid", []) if ti < len(base) else []):
                    s.append(f'<line x1="{x + fx * tw:.1f}" y1="{yb:.0f}" x2="{x + fx * tw:.1f}" y2="{yb + h:.0f}" stroke="{SG["muted"]}" stroke-opacity="0.3"/>')
                for a_, b_, txt in T.get("values", []):
                    for q in (a_, b_):
                        s.append(f'<line x1="{x:.1f}" y1="{Y(q):.1f}" x2="{x + tw:.1f}" y2="{Y(q):.1f}" stroke="{SG["text"]}" stroke-opacity="0.7"/>')
                    s.append(f'<text x="{x + tw / 2:.1f}" y="{(Y(a_) + Y(b_)) / 2 + 10:.1f}" font-size="{FONT}" fill="{SG["text"]}" text-anchor="middle">{esc(txt)}</text>')
                path = ["M" + " L".join(f"{x + fx * tw:.1f} {Y(dv):.1f}" for fx, dv in pl) for pl in joined(T.get("ink", []), P.get("grid", []), span)]
                if path:
                    s.append(f'<path d="{" ".join(path)}" fill="none" stroke="{SG["text"]}" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>')
                x += tw + 12
            y = yb + h + 40
            if not stack:
                for k, txt in legend:
                    for i, ln in enumerate(wrap_px(txt, W - 2 * PAD - 60, 29)):
                        if i == 0:
                            s.append(f'<text x="{PAD}" y="{y}" font-size="29" font-weight="700" fill="{SG["measurement"]["color"]}">{k}</text>')
                        s.append(f'<text x="{PAD + 50}" y="{y}" font-size="29" fill="{SG["text"]}">{esc(ln)}</text>')
                        y += 36
            y += 14
    return finish_svg(s, F, W, note_svg(s, F.get("note", ""), y + 16, W) + 10)


FIG_RE = __import__("re").compile(r"рис\.\s*((?:\d+\s*[а-я]?\s*(?:,|и)?\s*)+)")


def fig_numbers(x):
    """Номера рисунков, на которые ссылается задача или пример: поле figure и текст («рис. 14, 58», «рис. 67 и 76»)."""
    import re
    s = " ".join(str(x.get(k) or "") for k in ("figure", "text", "condition"))
    out = set()
    for m in FIG_RE.finditer(s):
        out |= set(re.findall(r"\d+", m.group(1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    layer = json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))
    (d / "illustrations").mkdir(exist_ok=True)
    extra = {}
    for fp in sorted((d / "figures").glob("*.json")):
        F = json.loads(fp.read_text(encoding="utf-8"))
        (d / "illustrations" / f"{F['id']}.svg").write_text(log_svg(F) if F.get("kind") == "log" else figure_svg(F), encoding="utf-8")
        num = __import__("re").findall(r"\d+", F["figure"])[0]
        steps = [n for n in layer["nodes"] if any(num in fig_numbers(x)
                                                  for x in n.get("worked_examples", []) + n.get("book_tasks", []))]
        for n in steps:
            extra.setdefault(n["id"], []).append({
                "id": f"{n['id']}.{F['id']}", "file": f"illustrations/{F['id']}.svg", "frame_class": "A",
                "origin": "redrawn_from_book", "label": F.get("label", "реальные данные" if F.get("kind") == "log" else "схема"),
                "caption": F["caption"], "alt": F["alt"],
                "source": F["source"], "claim_ids": [c["id"] for c in n["claims"]][:3], "prompt": None})
        print(f"{F['id']}: {F['figure']} -> шаги {[n['id'] for n in steps]}")
    (d / "figures_extra.json").write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
