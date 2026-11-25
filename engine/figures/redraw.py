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


def panel_svg(P, box, cal):
    x0, y0, x1, y1 = box
    gx0, gy0, gx1, gy1 = x0 + 90, y0 + 50, x1 - 30, y1 - 70
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
            s.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="26" font-weight="700" fill="{SG["text"]}" text-anchor="middle">{esc(f["label"])}</text>')
    # сетка и подписи осей
    for v in P["x"].get("ticks", []):
        px = X.px(v)
        s.append(f'<line x1="{px:.1f}" y1="{gy1}" x2="{px:.1f}" y2="{gy1 + 8}" stroke="{SG["muted"]}"/>')
        s.append(f'<text x="{px:.1f}" y="{gy1 + 32}" font-size="22" fill="{SG["muted"]}" text-anchor="middle">{esc(str(v).replace(".", ","))}</text>')
    for v in P["y"].get("ticks", []):
        py = Y.px(v)
        s.append(f'<line x1="{gx0 - 8}" y1="{py:.1f}" x2="{gx1}" y2="{py:.1f}" stroke="{SG["muted"]}" stroke-opacity="0.25"/>')
        s.append(f'<text x="{gx0 - 12}" y="{py + 7:.1f}" font-size="22" fill="{SG["muted"]}" text-anchor="end">{esc(str(v).replace(".", ","))}</text>')
    s.append(f'<text x="{gx1}" y="{gy1 + 62}" font-size="24" fill="{SG["text"]}" text-anchor="end">{esc(P["x"]["label"])}</text>')
    s.append(f'<text x="{gx0 - 80}" y="{gy0 - 18}" font-size="24" fill="{SG["text"]}">{esc(P["y"]["label"])}</text>')
    for ln in P.get("vlines", []):
        px = X.px(ln["x"])
        ya, yb = (Y.px(ln["y"][0]), Y.px(ln["y"][1])) if ln.get("y") else (gy0, gy1)
        s.append(f'<line x1="{px:.1f}" y1="{ya:.1f}" x2="{px:.1f}" y2="{yb:.1f}" stroke="{col(ln.get("color", "muted"))}" stroke-width="2.5"{dash(ln.get("style", "dashed"))}/>')
        if ln.get("label"):
            s.append(f'<text x="{px:.1f}" y="{gy1 - 10}" font-size="22" fill="{SG["text"]}" text-anchor="middle">{esc(ln["label"])}</text>')
    for ln in P.get("hlines", []):
        py = Y.px(ln["y"])
        xa, xb = (X.px(ln["x"][0]), X.px(ln["x"][1])) if ln.get("x") else (gx0, gx1)
        s.append(f'<line x1="{xa:.1f}" y1="{py:.1f}" x2="{xb:.1f}" y2="{py:.1f}" stroke="{SG["muted"]}" stroke-width="2.5"{dash("dashed")}/>')
        if ln.get("label"):
            s.append(f'<text x="{gx0 + 8}" y="{py - 8:.1f}" font-size="22" fill="{SG["text"]}">{esc(ln["label"])}</text>')
    for c in P.get("curves", []):
        pts = " ".join(f"{X.px(x):.1f},{Y.px(y):.1f}" for x, y in curves[c["id"]])
        s.append(f'<polyline points="{pts}" fill="none" stroke="{col(c.get("color", "text"))}" stroke-width="{c.get("width", 4)}" '
                 f'stroke-linejoin="round"{dash(c.get("style"))}/>')
        if c.get("label"):
            x, y = c.get("label_at") or curves[c["id"]][-1]
            s.append(f'<text x="{X.px(x) + 6:.1f}" y="{Y.px(y) - 6:.1f}" font-size="22" font-weight="700" fill="{col(c.get("color", "text"))}">{esc(c["label"])}</text>')
    for t in P.get("texts", []):
        s.append(f'<text x="{X.px(t["x"]):.1f}" y="{Y.px(t["y"]):.1f}" font-size="{t.get("size", 24)}" font-weight="700" '
                 f'fill="{col(t.get("color", "text"))}" text-anchor="middle">{esc(t["text"])}</text>')
    for p in P.get("points", []):
        px, py = X.px(p["x"]), Y.px(p["y"])
        s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="{col("measurement")}" stroke="{SG["background"]}" stroke-width="3"/>')
        s.append(f'<text x="{px + 14:.1f}" y="{py - 12:.1f}" font-size="22" font-weight="700" fill="{col("measurement")}">{esc(p["label"])}</text>')
    return "".join(s)


def figure_svg(F):
    W = F.get("width", 1100)
    heights = [p.get("height", 620) for p in F["panels"]]
    head = 120 + 32 * len(F.get("legend", []))
    import textwrap
    note_lines = textwrap.wrap(F.get("note", ""), width=int(W / 11)) if F.get("note") else []
    H = head + sum(heights) + 40 + 28 * len(note_lines)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="max-width:100%;height:auto" '
         f'role="img" aria-label="{esc(F["alt"])}" font-family="Segoe UI, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="{SG["background"]}"/>',
         f'<text x="30" y="44" font-size="30" font-weight="700" fill="{SG["text"]}">{esc(F["title"])}</text>',
         f'<text x="{W - 30}" y="82" font-size="24" font-weight="700" fill="{SG["provenance"]["схема"]}" text-anchor="end">схема</text>',
         f'<text x="30" y="82" font-size="22" fill="{SG["muted"]}">{esc(F["source"])}</text>']
    for i, lg in enumerate(F.get("legend", [])):
        y = 116 + i * 32
        s.append(f'<rect x="30" y="{y - 18}" width="34" height="20" fill="{col(lg["color"])}" fill-opacity="{lg.get("opacity", 0.6)}"/>')
        s.append(f'<text x="76" y="{y}" font-size="22" fill="{SG["text"]}">{esc(lg["text"])}</text>')
    y = head
    for P, h in zip(F["panels"], heights):
        s.append(panel_svg(P, (20, y, W - 20, y + h), F.get("calibration")))
        y += h
    for i, ln in enumerate(note_lines):
        s.append(f'<text x="30" y="{H - 20 - 28 * (len(note_lines) - 1 - i)}" font-size="20" fill="{SG["muted"]}">{esc(ln)}</text>')
    s.append("</svg>")
    return "".join(s)


def wrap_px(text, width, size):
    """Перенос по ширине в пикселях (оценка ширины символа Segoe UI ≈ 0,55 кегля)."""
    import textwrap
    return textwrap.wrap(text, width=max(8, int(width / (size * 0.55))), break_long_words=False) or [""]


def log_svg(F):
    """Каротажная диаграмма книги: панели с дорожками; кривые — оцифровка скана (trace_log.py), шкалы — из шапки рисунка.
    layout "side" — панели рядом (у каждой своя шкала глубин), "stack" — участки одного ствола друг под другом (общая шапка).
    Дорожка: ink (кривые), values ([[от, до, "текст"]] — значения в интервалах, как столбец ρп), ticks (строки шкалы)."""
    W = F.get("width", 1100)
    S = F["scan"]
    P_ = S["panels"]
    stack = F.get("layout") == "stack"
    DEPTH_W, GAP = 64, 18
    BODY_H = F.get("body_height", 860)
    cols = [P_[0]] if stack else P_
    src_w = [P["tracks"][-1]["x"][1] - P["tracks"][0]["x"][0] for P in cols]
    k = (W - 40 - len(cols) * DEPTH_W - GAP * (len(cols) - 1)) / sum(src_w)

    def head_parts(T, tw):
        hl = wrap_px(T["title"], tw - 10, 15)[:3]
        sl = wrap_px(T.get("scale", ""), tw - 10, 13)[:4] if T.get("scale") else []
        return hl, sl, T.get("ticks", [])
    need = [head_parts(T, (T["x"][1] - T["x"][0]) * k) for P in cols for T in P["tracks"]]
    HEAD = max([110] + [24 + 18 * len(h) + 16 * len(sl) + 22 * len(t) for h, sl, t in need])
    top = 100
    note = wrap_px(F.get("note", ""), W - 60, 18) if F.get("note") else []
    spans = [P["depth_range"][1] - P["depth_range"][0] for P in P_]
    seg_gap = 16
    H = top + HEAD + BODY_H + (seg_gap * (len(P_) - 1) if stack else 0) + 50 + 24 * len(note)
    label = F.get("label", "реальные данные")
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="max-width:100%;height:auto" '
         f'role="img" aria-label="{esc(F["alt"])}" font-family="Segoe UI, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="{SG["background"]}"/>']
    for i, ln in enumerate(wrap_px(F["title"], W - 230, 26)[:2]):
        s.append(f'<text x="24" y="{36 + 30 * i}" font-size="26" font-weight="700" fill="{SG["text"]}">{esc(ln)}</text>')
    s.append(f'<text x="{W - 24}" y="36" font-size="22" font-weight="700" fill="{SG["provenance"][label]}" text-anchor="end">{esc(label)}</text>')
    s.append(f'<text x="24" y="{top - 8}" font-size="18" fill="{SG["muted"]}">{esc(F["source"])}</text>')

    def header(x, P):
        s.append(f'<text x="{x - DEPTH_W / 2}" y="{top + HEAD - 12}" font-size="15" fill="{SG["muted"]}" text-anchor="middle">'
                 f'{"глубина, м" if F.get("depth_axis", True) else "пласты"}</text>')
        for T in P["tracks"]:
            tw = (T["x"][1] - T["x"][0]) * k
            hl, sl, rows = head_parts(T, tw)
            s.append(f'<rect x="{x:.1f}" y="{top}" width="{tw:.1f}" height="{HEAD - 6}" fill="none" stroke="{SG["muted"]}" stroke-opacity="0.5"/>')
            for i, ln in enumerate(hl):
                s.append(f'<text x="{x + 5:.1f}" y="{top + 19 + 18 * i}" font-size="15" font-weight="700" fill="{SG["text"]}">{esc(ln)}</text>')
            for i, ln in enumerate(sl):
                s.append(f'<text x="{x + 5:.1f}" y="{top + 21 + 18 * len(hl) + 16 * i}" font-size="13" fill="{SG["muted"]}">{esc(ln)}</text>')
            for r, row in enumerate(rows[::-1]):   # строки шкалы — внизу шапки, как в книге
                yy = top + HEAD - 12 - 22 * r
                s.append(f'<line x1="{x:.1f}" y1="{yy:.1f}" x2="{x + tw:.1f}" y2="{yy:.1f}" stroke="{SG["muted"]}" stroke-opacity="0.6"/>')
                for fx, txt in row["at"]:
                    px = x + fx * tw
                    s.append(f'<line x1="{px:.1f}" y1="{yy - 4:.1f}" x2="{px:.1f}" y2="{yy + 4:.1f}" stroke="{SG["muted"]}"/>')
                    s.append(f'<text x="{px:.1f}" y="{yy - 6:.1f}" font-size="12" fill="{SG["text"]}" text-anchor="middle">{esc(txt)}</text>')
            x += tw

    def body(x, P, yb0, h):
        d0, d1 = P["depth_range"]
        Y = lambda d: yb0 + (d - d0) / (d1 - d0) * h  # noqa: E731
        s.append(f'<rect x="{x - DEPTH_W}" y="{yb0:.1f}" width="{DEPTH_W}" height="{h:.1f}" fill="{SG["panel"]}" stroke="{SG["muted"]}"/>')
        span = d1 - d0
        step = 10 if span * 860 / max(h, 1) > 25 else (5 if span * 860 / max(h, 1) > 8 else 1)
        dd = math.ceil(d0 / step) * step if F.get("depth_axis", True) else d1 + 1   # в книге нет шкалы глубин
        while dd <= d1:
            s.append(f'<line x1="{x - 10}" y1="{Y(dd):.1f}" x2="{x}" y2="{Y(dd):.1f}" stroke="{SG["muted"]}"/>')
            s.append(f'<text x="{x - 14}" y="{Y(dd) + 6:.1f}" font-size="17" fill="{SG["text"]}" text-anchor="end">{dd:g}</text>')
            dd += step
        cols_t = cols[0]["tracks"] if stack else P["tracks"]
        for T, TC in zip(P["tracks"], cols_t):
            tw = (TC["x"][1] - TC["x"][0]) * k
            s.append(f'<rect x="{x:.1f}" y="{yb0:.1f}" width="{tw:.1f}" height="{h:.1f}" fill="{SG["panel"]}" stroke="{SG["muted"]}"/>')
            for g in P.get("grid", []):
                s.append(f'<line x1="{x:.1f}" y1="{Y(g):.1f}" x2="{x + tw:.1f}" y2="{Y(g):.1f}" stroke="{SG["muted"]}" stroke-opacity="0.45"/>')
            for fx in TC.get("vgrid", []):   # вертикальная сетка дорожки, как в книге
                s.append(f'<line x1="{x + fx * tw:.1f}" y1="{yb0:.1f}" x2="{x + fx * tw:.1f}" y2="{yb0 + h:.1f}" stroke="{SG["muted"]}" stroke-opacity="0.35"/>')
            for a_, b_, txt in T.get("values", []):
                s.append(f'<line x1="{x:.1f}" y1="{Y(a_):.1f}" x2="{x + tw:.1f}" y2="{Y(a_):.1f}" stroke="{SG["text"]}" stroke-opacity="0.7"/>')
                s.append(f'<line x1="{x:.1f}" y1="{Y(b_):.1f}" x2="{x + tw:.1f}" y2="{Y(b_):.1f}" stroke="{SG["text"]}" stroke-opacity="0.7"/>')
                s.append(f'<text x="{x + tw / 2:.1f}" y="{(Y(a_) + Y(b_)) / 2 + 6:.1f}" font-size="16" fill="{SG["text"]}" text-anchor="middle">{esc(txt)}</text>')
            path = []
            for pl in T.get("ink", []):
                path.append("M" + " L".join(f"{x + fx * tw:.1f} {Y(dv):.1f}" for fx, dv in pl))
            if path:
                s.append(f'<path d="{" ".join(path)}" fill="none" stroke="{SG["text"]}" stroke-width="1.6" stroke-linejoin="round" '
                         f'stroke-linecap="round"/>')
            x += tw

    y0 = top + HEAD
    if stack:
        header(20 + DEPTH_W, P_[0])
        yy = y0
        for P, sp in zip(P_, spans):
            h = BODY_H * sp / sum(spans)
            body(20 + DEPTH_W, P, yy, h)
            yy += h + seg_gap
        y_end = yy - seg_gap
    else:
        x = 20
        for P, sw in zip(P_, src_w):
            header(x + DEPTH_W, P)
            body(x + DEPTH_W, P, y0, BODY_H)
            x += DEPTH_W + sw * k + GAP
        y_end = y0 + BODY_H
    for i, ln in enumerate(note):
        s.append(f'<text x="24" y="{y_end + 34 + 24 * i}" font-size="18" fill="{SG["muted"]}">{esc(ln)}</text>')
    s.append("</svg>")
    return "".join(s)


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
