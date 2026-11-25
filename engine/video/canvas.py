"""Общие средства рисования кадров (Pillow). Цвета — из domain_pack/styleguide.json, шрифт Segoe UI.
Правила стайлгайда: подписи не мельче 44 px на кадре 1080 px; безопасная зона 9:16 — 220 сверху, 380 снизу, 70 по бокам;
метка происхождения на каждом кадре."""
import json
import pathlib
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
SG = json.loads((ROOT / "domain_pack" / "styleguide.json").read_text(encoding="utf-8"))
FONT_DIR = pathlib.Path("C:/Windows/Fonts")
_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        name = "segoeuib.ttf" if bold else "segoeui.ttf"
        try:
            _cache[key] = ImageFont.truetype(str(FONT_DIR / name), size)
        except OSError:
            _cache[key] = ImageFont.load_default(size)
    return _cache[key]


def rgb(hexcol, alpha=None):
    h = hexcol.lstrip("#")
    c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return c + (alpha,) if alpha is not None else c


def mix(a, b, t):
    a, b = rgb(a) if isinstance(a, str) else a, rgb(b) if isinstance(b, str) else b
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def new(w, h):
    im = Image.new("RGB", (w, h), rgb(SG["background"]))
    return im, ImageDraw.Draw(im, "RGBA")


def text(d, xy, s, size=44, bold=False, fill=None, anchor="la"):
    d.text(xy, s, font=font(size, bold), fill=rgb(fill or SG["text"]), anchor=anchor)


def wrap(s, size, width_px, bold=False):
    f = font(size, bold)
    avg = f.getlength("абвгдежзик") / 10
    return textwrap.wrap(s, width=max(8, int(width_px / avg)))


def caption(d, w, h, s, safe_bottom, size=48):
    """Крупная подпись (ключевые слова, ≤8 слов) над нижней безопасной зоной."""
    if not s:
        return
    lines = wrap(s, size, w - 2 * 90, bold=True)[:2]
    y = h - safe_bottom - 30 - len(lines) * (size + 14)
    for ln in lines:
        f = font(size, True)
        tw = f.getlength(ln)
        x = (w - tw) / 2
        d.rounded_rectangle([x - 26, y - 14, x + tw + 26, y + size + 24], radius=16, fill=rgb(SG["panel"], 235))
        d.text((x, y + size / 2 + 5), ln, font=f, fill=rgb(SG["text"]), anchor="lm")
        y += size + 40


def provenance(d, x, y, label="симуляция", size=44):
    d.text((x, y), label, font=font(size, True), fill=rgb(SG["provenance"][label]))


def card(d, box, title, lines, size=46, accent=None):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=24, fill=rgb(SG["panel"], 245), outline=rgb(accent or SG["muted"]), width=4)
    y = y0 + 30
    for ln in wrap(title, size + 6, x1 - x0 - 60, True):
        d.text((x0 + 30, y), ln, font=font(size + 6, True), fill=rgb(accent or SG["text"]))
        y += size + 16
    y += 10
    for s in lines:
        for ln in wrap(s, size, x1 - x0 - 60):
            d.text((x0 + 30, y), ln, font=font(size), fill=rgb(SG["text"]))
            y += size + 12
        y += 8
