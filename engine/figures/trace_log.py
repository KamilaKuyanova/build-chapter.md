#!/usr/bin/env python3
"""Оцифровка каротажных диаграмм книги по скану (для перерисовки кодом, ТЗ: рисунки книги не вставляются).

Описание рисунка — data/<глава>/figures/<id>.json c "kind": "log" и разделом "scan":
  {"book": "Латышова", "page": 105, "dpi": 200,
   "panels": [{"bbox": [x0, y0, x1, y1],              # область панели на странице, пиксели при dpi
               "body": [y_top, y_bot],                # тело диаграммы (под шапкой)
               "depth_ticks": [[y_px, глубина], ...],  # подписи глубин (читаются глазами)
               "tracks": [{"x": [x0, x1], "title": "...", "scale": "..."}],
               "mask": [[x0, y0, x1, y1], ...]}]}      # надписи внутри дорожек, которые не трассировать

  python engine/figures/trace_log.py detect data/latyshova/figures/fig76.json   # линии сетки -> картинка-подсказка
  python engine/figures/trace_log.py trace  data/latyshova/figures/fig76.json   # кривые -> "ink" в том же JSON

Трассировка: тёмные пиксели дорожки без линий сетки -> отрезки по строкам -> цепочки -> упрощение (Рамер — Дуглас — Пекер).
Кривые хранятся в единицах рисунка: x — доля ширины дорожки (шкала дорожки подписана в шапке), y — глубина, м.
Скан нужен только для оцифровки; книга в репозиторий не кладётся."""
import glob
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "out" / "trace"


def page_gray(book, page, dpi):
    import pymupdf
    pdf = glob.glob(str(ROOT / "хакатон" / "книги" / f"{book}*.pdf"))[0]
    pix = pymupdf.open(pdf)[page - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(np.int16)


def dark_mask(g, delta=70):
    bg = np.percentile(g, 75)
    return g < bg - delta


def lines(mask, axis, frac):
    """Индексы строк/столбцов, где доля тёмного выше frac, сгруппированные в линии -> [(центр, от, до)]."""
    share = mask.mean(axis=axis)
    idx = np.where(share > frac)[0]
    out, start = [], None
    for k, i in enumerate(idx):
        if start is None:
            start = i
        if k == len(idx) - 1 or idx[k + 1] != i + 1:
            out.append(((start + i) // 2, start, i))
            start = None
    return out


def detect(spec_path):
    from PIL import Image, ImageDraw
    F = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    S = F["scan"]
    g = page_gray(S["book"], S["page"], S["dpi"])
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for pi, P in enumerate(S["panels"]):
        x0, y0, x1, y1 = P["bbox"]
        m = dark_mask(g[y0:y1, x0:x1])
        vl = lines(m, 0, 0.45)
        hl = lines(m, 1, 0.45)
        print(f"панель {pi}: вертикальные x = {[x0 + c for c, _, _ in vl]}")
        print(f"          горизонтальные y = {[y0 + c for c, _, _ in hl]}")
        im = Image.fromarray(g[y0:y1, x0:x1].clip(0, 255).astype(np.uint8)).convert("RGB")
        d = ImageDraw.Draw(im)
        for c, _, _ in vl:
            d.line([(c, 0), (c, im.height)], fill=(220, 0, 0), width=1)
            d.text((c + 2, 2), str(x0 + c), fill=(220, 0, 0))
        for c, _, _ in hl:
            d.line([(0, c), (im.width, c)], fill=(0, 0, 220), width=1)
            d.text((2, c + 2), str(y0 + c), fill=(0, 0, 220))
        for k in range(0, im.height, 50):   # линейки по y и x для чтения координат
            d.text((im.width - 40, k), str(y0 + k), fill=(0, 140, 0))
        for k in range(0, im.width, 25):
            d.line([(k, 0), (k, 6 if k % 50 else 12)], fill=(0, 140, 0))
            if k % 50 == 0:
                d.text((k + 1, 12), str(x0 + k), fill=(0, 140, 0))
        z = min(1.6, 1500 / max(im.width, im.height))
        im = im.resize((int(im.width * z), int(im.height * z)))
        im.save(SCRATCH / f"{F['id']}_p{pi}.png")
        print(f"          подсказка: {SCRATCH / (F['id'] + f'_p{pi}.png')}")


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0], float), np.array(pts[-1], float)
    ab = b - a
    n = np.hypot(*ab) or 1.0
    d = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / n for p in pts[1:-1]]
    k = int(np.argmax(d)) + 1
    if d[k - 1] > eps:
        return rdp(pts[:k + 1], eps)[:-1] + rdp(pts[k:], eps)
    return [pts[0], pts[-1]]


def _runs(row):
    d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0] - 1))


def trace_track(m):
    """Бинарная дорожка (строки = глубина) -> список полилиний в пикселях (x, y)."""
    H, W = m.shape
    # толщина штриха скана: медиана ширины прогонов; горизонтальный участок — прогон заметно шире штриха
    widths = [int(b - a) for y in range(H) for a, b in _runs(m[y])]
    wide = max(7, 2.2 * float(np.median(widths))) if widths else 7
    prev = []          # прогоны прошлой строки: (a, b, id цепочки)
    chains = {}
    nid = 0
    for y in range(H):
        row = m[y]
        runs, x = [], 0
        while x < W:
            if row[x]:
                a = x
                while x < W and row[x]:
                    x += 1
                runs.append((a, x - 1))
            x += 1
        cur = []
        used = set()
        for a, b in runs:
            c = (a + b) / 2
            # продолжение цепочки: прогон прошлой строки, перекрывающийся (с допуском 1 px), ещё не занятый
            best = None
            for pa, pb, cid in prev:
                if pa - 1 <= b and a <= pb + 1 and cid not in used:
                    best = cid
                    break
            if best is None:
                nid += 1
                best = nid
                chains[best] = []
            used.add(best)
            if b - a >= wide:   # горизонтальный участок кривой (выброс): оба конца
                last = chains[best][-1] if chains[best] else None
                ends = [(a, y), (b, y)]
                if last and abs(last[0] - b) < abs(last[0] - a):
                    ends.reverse()
                chains[best] += ends
            else:
                chains[best].append((c, y))
            cur.append((a, b, best))
        prev = cur
    out = []
    for pts in chains.values():
        if len(pts) >= 3 or (len(pts) == 2 and abs(pts[0][0] - pts[1][0]) > 3):
            out.append(rdp(pts, 0.8))
    return out


def trace(spec_path):
    sp = pathlib.Path(spec_path)
    F = json.loads(sp.read_text(encoding="utf-8"))
    S = F["scan"]
    g = page_gray(S["book"], S["page"], S["dpi"])
    total = 0
    for P in S["panels"]:
        x0, y0, x1, y1 = P["bbox"]
        m = dark_mask(g, S.get("dark", 70))
        bt, bb = P["body"]
        # линии сетки не трассируются: стираются строки/столбцы сетки (±2 px), найденные по телу диаграммы
        sub = m[bt:bb, x0:x1].copy()
        # вертикальные линии сетки стираются только там, где они есть в книге: границы дорожек и их вертикальная сетка
        # (vgrid); вертикальные участки кривых в других местах остаются
        grid_x = [x for T in P["tracks"] for x in T["x"]] + [T["x"][0] + f * (T["x"][1] - T["x"][0])
                                                             for T in P["tracks"] for f in T.get("vgrid", [])]
        for c, a, b in (lines(sub, 0, 0.5) if P.get("vlines", True) else []):
            if any(abs(x0 + c - gx) <= 6 for gx in grid_x):
                sub[:, max(0, a - 2):b + 3] = False
        for c, a, b in lines(sub, 1, 0.45):
            sub[max(0, a - 2):b + 3, :] = False
        m[bt:bb, x0:x1] = sub
        for mx0, my0, mx1, my1 in P.get("mask", []):
            m[my0:my1, mx0:mx1] = False
        ticks = sorted(P["depth_ticks"])
        (ya, da), (yb, db) = ticks[0], ticks[-1]

        def depth(y):
            return da + (y - ya) * (db - da) / (yb - ya)
        for T in P["tracks"]:
            if T.get("skip_trace"):   # столбец значений по интервалам, а не кривая
                T.pop("ink", None)
                continue
            tx0, tx1 = T["x"]
            pad = 5
            part = m[bt + 2 * pad:bb - pad, tx0 + pad:tx1 - pad]   # сверху больше: засечки шкалы под шапкой
            polys = trace_track(part)
            w = (tx1 - tx0)
            T["ink"] = [[[round((px + pad) / w, 4), round(depth(py + bt + 2 * pad), 2)] for px, py in pl] for pl in polys]
            total += sum(len(p) for p in T["ink"])
        P["depth_range"] = [round(depth(bt), 2), round(depth(bb), 2)]
        P["grid"] = [round(depth(y0 + c), 2) for c, _, _ in lines(dark_mask(g[y0:y1, x0:x1]), 1, 0.45)
                     if bt < y0 + c < bb]
    sp.write_text(json.dumps(F, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{F['id']}: точек кривых {total}, файл {sp.stat().st_size // 1024} КБ")


def trace_chart(spec_path):
    """Палетка (график) книги: кривые внутри поля графика -> кривые в единицах осей (panels[0].curves для redraw.figure_svg).
    Скан бывает чуть повёрнут и перекошен, поэтому поле графика сначала выпрямляется аффинно по трём точкам
    p00 (x0, y0), p10 (x1, y0), p01 (x0, y1); в выпрямленном поле линии сетки — строки и столбцы, они стираются;
    кривые — функции x, поэтому трассировка идёт по столбцам. Надписи убираются масками и порогом длины кривой."""
    sp = pathlib.Path(spec_path)
    F = json.loads(sp.read_text(encoding="utf-8"))
    S, C = F["scan"], F["scan"]["chart"]
    g = page_gray(S["book"], S["page"], S["dpi"])
    m = dark_mask(g, S.get("dark", 70))
    for mx0, my0, mx1, my1 in C.get("mask", []):
        m[my0:my1, mx0:mx1] = False
    p00, p10, p01 = (np.array(C[n], float) for n in ("p00", "p10", "p01"))
    A = np.column_stack([p10 - p00, p01 - p00])
    Ainv = np.linalg.inv(A)
    ur, vr = C.get("u_range", [0, 1]), C.get("v_range", [0, 1])
    RW, RH = C.get("res", [1000, 800])
    us = np.linspace(ur[0], ur[1], RW)
    vs = np.linspace(vr[1], vr[0], RH)          # строка 0 — верх графика
    U, V = np.meshgrid(us, vs)
    X = p00[0] + A[0, 0] * U + A[0, 1] * V
    Y = p00[1] + A[1, 0] * U + A[1, 1] * V
    Xi, Yi = np.clip(np.rint(X).astype(int), 0, m.shape[1] - 1), np.clip(np.rint(Y).astype(int), 0, m.shape[0] - 1)
    r = m[Yi, Xi]
    for c, a_, b_ in lines(r, 0, C.get("grid_share", 0.45)):
        r[:, max(0, a_ - 2):b_ + 3] = False
    for c, a_, b_ in lines(r, 1, C.get("grid_share", 0.45)):
        r[max(0, a_ - 2):b_ + 3, :] = False
    strips = C.get("strips", 8)   # сетка скана слегка изогнута: горизонтали ищутся по вертикальным полосам
    for k in range(strips):
        c0, c1 = k * RW // strips, (k + 1) * RW // strips
        for c, a_, b_ in lines(r[:, c0:c1], 1, 0.5):
            r[max(0, a_ - 2):b_ + 3, c0:c1] = False
    band = C.get("band", 7)    # горизонтальная сетка скана волнистая: стирается полоса вокруг известных значений сетки
    for gv in C.get("hgrid_v", []):
        row = int(round((vr[1] - gv) / (vr[1] - vr[0]) * (RH - 1)))
        r[max(0, row - band):row + band + 1, :] = False
    ax, ay = C["x"], C["y"]

    def to_data(u, v):
        xv = ax["v0"] * (ax["v1"] / ax["v0"]) ** u if ax.get("log") else ax["v0"] + u * (ax["v1"] - ax["v0"])
        yv = ay["v0"] * (ay["v1"] / ay["v0"]) ** v if ay.get("log") else ay["v0"] + v * (ay["v1"] - ay["v0"])
        return [round(float(xv), 4), round(float(yv), 4)]
    curves = []
    pieces = [sorted(((p[1], p[0]) for p in pl)) for pl in trace_track(r.T.copy())]   # (столбец, строка) графика
    pieces = [q for q in pieces if len(q) >= 2]
    pieces.sort(key=lambda q: q[0][0])
    joined = []          # склейка кусков одной кривой через стёртые полосы сетки: конец к началу, по продолжению наклона
    for q in pieces:
        best, bd = None, C.get("join", 40)
        for J in joined:
            (c1, r1), (c0, r0) = J[-1], J[max(0, len(J) - 6)]
            dc = q[0][0] - c1
            if dc < -2:
                continue
            slope = (r1 - r0) / (c1 - c0) if c1 != c0 else 0
            d = abs(q[0][1] - (r1 + slope * dc)) + 0.3 * abs(dc)
            if d < bd:
                best, bd = J, d
        if best is not None:
            best += q
        else:
            joined.append(list(q))
    for J in joined:
        byc = {}
        for c, rw in J:                          # кривая — функция x: одна точка на столбец (медиана), без «штриховки»
            byc.setdefault(int(round(c)), []).append(rw)
        cs = sorted(byc)
        J = rdp([(c, float(np.median(byc[c]))) for c in cs], 0.8)
        cols, rows = [p[0] for p in J], [p[1] for p in J]
        pl = list(zip(rows, cols))
        if max(cols) - min(cols) < C.get("min_extent", 60):
            continue
        pts = sorted((to_data(us[int(round(c))], vs[int(round(rw))]) for rw, c in zip(rows, cols)), key=lambda q: q[0])
        if max(rows) - min(rows) < C.get("min_rise", 0) * RH:   # плоский обрывок — остаток сетки, а не кривая
            continue
        curves.append({"id": f"ink{len(curves)}", "points": pts, "width": 3})
    P = F["panels"][0]
    P["curves"] = curves
    P["texts"] = []
    for t in C.get("labels", []):
        u, v = Ainv @ (np.array(t["px"], float) - p00)
        P["texts"].append(dict(t, **dict(zip(("x", "y"), to_data(u, v)))))
    sp.write_text(json.dumps(F, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{F['id']}: кривых {len(curves)}, точек {sum(len(c['points']) for c in curves)}")
    from PIL import Image
    SCRATCH.mkdir(parents=True, exist_ok=True)
    Image.fromarray((~r * 255).astype(np.uint8)).save(SCRATCH / f"{F['id']}_rect.png")


if __name__ == "__main__":
    {"detect": detect, "trace": trace, "chart": trace_chart}[sys.argv[1]](sys.argv[2])
