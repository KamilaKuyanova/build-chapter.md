"""Сцена «каротаж» для шортса 9:16 (кадры класса B, метка «симуляция»).
Одна модель состояния: глубина прибора d(t). От неё зависят и положение прибора, и точки кривых
(модель слоёв — engine/scenes/logging_run.py, та же, что в SVG-шаблоне). Генерации ИИ нет.

beat у фразы сценария: {"d": [от, до]} — прибор идёт с глубины «от» до «до» за время фразы;
"hl": ["GR","RES"] — подсветить треки; "band": [верх, низ] — подсветить интервал; "card": [заголовок, строки…]."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scenes"))
import logging_run as M  # noqa: E402
from canvas import SG, card, caption, font, mix, new, provenance, rgb, text  # noqa: E402

SPEC = M.SPEC
W, H = 1080, 1920
TOP, BOT, SIDE = SG["safe_zone"]["top"], SG["safe_zone"]["bottom"], SG["safe_zone"]["side"]
Y0, Y1 = TOP + 200, H - BOT - 260        # область глубины (над подписью)
BX0, BX1 = SIDE, SIDE + 250              # разрез
TRACKS = []
_tx = BX1 + 50
_tw = (W - SIDE - _tx - 2 * 18) / 3
for _i in range(3):
    TRACKS.append((_tx + _i * (_tw + 18), _tx + _i * (_tw + 18) + _tw))
NAMES = [("SP", "ПС"), ("GR", "ГК"), ("RES", "Сопр.")]


def y_of(d):
    return Y0 + (Y1 - Y0) * d / M.DEPTH_MAX


def x_of(track, key, v):
    x0, x1 = TRACKS[track]
    frac = (v + 1) if key == "SP" else v
    return x0 + 14 + frac * (x1 - x0 - 28)


def depth_at(beats, t):
    """Глубина прибора из сценария: линейно внутри фразы, держится между фразами."""
    d = 0.0
    for b in beats:
        rng = (b.get("beat") or {}).get("d")
        if not rng:
            continue
        if t >= b["t_end"]:
            d = rng[1]
        elif t >= b["t_start"]:
            p = (t - b["t_start"]) / max(0.01, b["t_end"] - b["t_start"])
            p = p * p * (3 - 2 * p)
            d = rng[0] + (rng[1] - rng[0]) * p
            break
        else:
            break
    return d


def current(beats, t):
    cur = None
    for b in beats:
        if b["t_start"] - 0.05 <= t:
            cur = b
    return cur or beats[0]


def render(t, beats):
    im, dr = new(W, H)
    d = depth_at(beats, t)
    b = current(beats, t)
    beat = b.get("beat") or {}
    provenance(dr, SIDE, TOP - 10)
    text(dr, (SIDE, TOP + 46), "глубина растёт вниз · шкала условная", 40, fill=SG["muted"])
    text(dr, (SIDE, TOP + 94), "не в масштабе: ствол шире ≈ в 20 раз", 40, fill=SG["muted"])
    # разрез
    for top, bot, lith, fl, *_ in M.LAYERS:
        dr.rectangle([BX0, y_of(top), BX1, y_of(bot)], fill=rgb(SG["lithology"][lith]["color"]))
        if fl:
            dr.rectangle([BX1 - 40, y_of(top) + 6, BX1 - 8, y_of(bot) - 6], fill=rgb(SG["fluids"][fl]["color"]))
    band = beat.get("band")
    if band:
        dr.rectangle([BX0 - 6, y_of(band[0]), W - SIDE + 4, y_of(band[1])], outline=rgb(SG["measurement"]["color"]), width=5)
    cx = (BX0 + BX1) / 2 - 30
    dr.rectangle([cx - 28, Y0, cx + 28, Y1], fill=rgb(SG["fluids"]["mud"]["color"]))
    ty = y_of(d)
    dr.line([cx, Y0, cx, ty - 40], fill=rgb(SG["text"]), width=4)
    dr.rounded_rectangle([cx - 16, ty - 40, cx + 16, ty + 40], radius=8, fill=rgb(SG["measurement"]["color"]),
                         outline=rgb(SG["text"]), width=3)
    # треки
    hl = set(beat.get("hl", []))
    for k, (key, ru) in enumerate(NAMES):
        x0, x1 = TRACKS[k]
        col = SG["curves"][key]["color"]
        dr.rectangle([x0, Y0, x1, Y1], fill=rgb(SG["panel"]),
                     outline=rgb(col if key in hl else SG["muted"]), width=6 if key in hl else 2)
        text(dr, ((x0 + x1) / 2, Y0 - 16), ru, 46, True, col, anchor="ms")
        pts, n = [], max(2, int(d * 3))
        for i in range(n + 1):
            dd = d * i / n
            pts.append((x_of(k, key, M.curves_at(dd)[key]), y_of(dd)))
        if d > 0.2:
            dr.line(pts, fill=rgb(col), width=7, joint="curve")
        px, py = x_of(k, key, M.curves_at(d)[key]), ty
        dr.ellipse([px - 13, py - 13, px + 13, py + 13], fill=rgb(col), outline=rgb(SG["text"]), width=3)
    dr.line([cx + 16, ty, TRACKS[2][1], ty], fill=rgb(SG["text"], 110), width=2)
    # подписи пород, если пройдены
    if beat.get("labels"):
        short_fl = {"water": "вода", "oil": "нефть"}
        for top, bot, lith, fl, *_ in M.LAYERS:
            if d >= (top + bot) / 2:
                rows = [SG["lithology"][lith]["ru"].split()[0]] + ([short_fl.get(fl, "")] if fl else [])
                f = font(44, True)
                ym = (y_of(top) + y_of(bot)) / 2 - (len(rows) - 1) * 26
                tw = max(f.getlength(r) for r in rows)
                dr.rounded_rectangle([BX0 + 4, ym - 30, BX0 + 4 + tw + 20, ym + 30 + (len(rows) - 1) * 52], radius=10,
                                     fill=rgb(SG["background"], 215))
                for k, r in enumerate(rows):
                    dr.text((BX0 + 14, ym + k * 52), r, font=f, fill=rgb(SG["text"]), anchor="lm")
    if beat.get("card"):
        c = beat["card"]
        card(dr, (TRACKS[0][0] - 10, Y0 + 20, W - SIDE + 10, Y1 - 20), c[0], c[1:], 44, SG["measurement"]["color"])
    caption(dr, W, H, b.get("on_screen", ""), BOT)
    return im
