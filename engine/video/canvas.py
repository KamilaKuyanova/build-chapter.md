"""Общие средства рисования кадров (Pillow). Цвета — из domain_pack/styleguide.json, шрифт Segoe UI.
Правила стайлгайда: подписи не мельче 44 px на кадре 1080 px; безопасная зона 9:16 — 220 сверху, 380 снизу, 70 по бокам;
метка происхождения на каждом кадре."""
import json
import pathlib
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(ROOT / "engine"))
import domain  # noqa: E402

SG = domain.load("styleguide.json")


def preset(name):
    """Параметры-образец шаблона из доменного пакета (templates/<имя>.json): движок не хранит предметных примеров."""
    return domain.load(f"templates/{name}.json")
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
    return textwrap.wrap(s, width=max(8, int(width_px / avg)), break_long_words=False)


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


def track(beats, t, key, default=0.0, log=False):
    """Модель состояния из сценария: у фразы beat[key] = [от, до] — значение плавно идёт за время фразы и держится после."""
    import math
    v = default
    for b in beats:
        rng = (b.get("beat") or {}).get(key)
        if rng is None:
            continue
        if not isinstance(rng, (list, tuple)):
            rng = [rng, rng]
        if t >= b["t_end"]:
            v = rng[1]
        elif t >= b["t_start"]:
            p = (t - b["t_start"]) / max(0.01, b["t_end"] - b["t_start"])
            if log and rng[0] > 0 and rng[1] > 0:
                v = math.exp(math.log(rng[0]) + (math.log(rng[1]) - math.log(rng[0])) * p)
            else:
                p = p * p * (3 - 2 * p)
                v = rng[0] + (rng[1] - rng[0]) * p
            break
        else:
            break
    return v


def current(beats, t):
    cur = None
    for b in beats:
        if b["t_start"] - 0.05 <= t:
            cur = b
    return cur or beats[0]


def layout(W, H):
    """Области кадра: шапка, основная, вторая (синхронный вид), низ под подпись. 9:16 — столбиком, 16:9 — рядом."""
    if H > W:
        sz = SG["safe_zone"]
        top, bot, side = sz["top"], sz["bottom"], sz["side"]
        head = (side, top - 20, W - side, top + 140)
        body_y0, body_y1 = top + 170, H - bot - 170
        mid = body_y0 + (body_y1 - body_y0) * 0.55
        return {"head": head, "main": (side, body_y0, W - side, mid - 20), "side": (side, mid + 20, W - side, body_y1),
                "caption_bottom": bot, "caption_size": 48, "vertical": True}
    return {"head": (60, 20, W - 60, 150), "main": (60, 170, W * 0.42, H - 150), "side": (W * 0.42 + 40, 170, W - 60, H - 150),
            "caption_bottom": 40, "caption_size": 46, "vertical": False}


def header(d, L, title, note=None, label="симуляция"):
    x0, y0, x1, y1 = L["head"]
    provenance(d, x0, y0 + 10, label)
    size = 48 if not L["vertical"] else 44
    for i, ln in enumerate(wrap(title, size, x1 - x0, True)[:2]):
        d.text((x0, y0 + 66 + i * (size + 8)), ln, font=font(size, True), fill=rgb(SG["text"]))
    if note:
        if L["vertical"]:   # в 9:16 источник — под меткой, справа, мелкой строкой не налезая на заголовок
            d.text((x1, y0 + 14), note[:60], font=font(30), fill=rgb(SG["muted"]), anchor="ra")
        else:
            d.text((x1, y0 + 14), note, font=font(38), fill=rgb(SG["muted"]), anchor="ra")


def color(key):
    """Цвет по ключу стайлгайда: 'lithology.sand', 'fluids.oil', 'curves.GR', 'measurement', 'uncertainty' или #hex."""
    if key.startswith("#"):
        return key
    node = SG
    for part in key.split("."):
        node = node[part]
    return node["color"] if isinstance(node, dict) else node


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
