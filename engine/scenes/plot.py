"""График из расчёта в SVG: крупные подписи, читается на телефоне (390 px). Цвета из стайлгайда."""
import html
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SG = json.loads((ROOT / "domain_pack" / "styleguide.json").read_text(encoding="utf-8"))
W, FONT = 640, 30  # при ширине 358 px подпись 30 -> 16.8 px
INK, MUTED, PANEL = SG["text"], SG["muted"], SG["panel"]
MAIN, SECOND = SG["curves"]["PRESSURE"]["color"], SG["curves"]["RES"]["color"]


def esc(s):
    return html.escape(str(s), quote=True)


def text(x, y, s, size=FONT, fill=INK, anchor="start", weight=400, rotate=None):
    r = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate is not None else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="Segoe UI,system-ui,sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{r}>{esc(s)}</text>')


def wrap(s, width):
    out, line = [], ""
    for w in s.split():
        if line and len(line) + 1 + len(w) > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    return out + [line] if line else out


def mix(a, b, k):
    """Цвет между a и b: для одной величины в разные моменты времени (один тон, разная светлота)."""
    pa, pb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * k):02X}" for x, y in zip(pa, pb))


def fmt(v):
    return f"{v:g}".replace(".", ",").replace("-", "−")


def chart(title, series, xlab, ylab, note, label="симуляция", xticks=None, yticks=None, xlog=False, marks=()):
    """series: [(подпись, [(x, y)…], цвет, пунктир)], подпись стоит у конца линии или в легенде."""
    fx = (lambda v: math.log10(v)) if xlog else (lambda v: v)
    xs = [fx(x) for _, p, *_ in series for x, _ in p]
    ys = [y for _, p, *_ in series for _, y in p]
    x0, x1, y0, y1 = min(xs), max(xs), min(0, min(ys)), max(ys) * 1.06
    heads, notes = wrap(title, 29), wrap(note, 40)
    xticks = [v for v in xticks or [] if x0 <= fx(v) <= x1]
    yticks = [v for v in yticks or [] if y0 <= v <= y1]
    legend = len(series) > 1
    top = 84 + 40 * len(heads) + (44 * len(series) if legend else 0) + 62
    ph, left, right = 340, 100, 30
    bottom = top + ph
    H = bottom + 100 + 34 * len(notes) + 16
    px = lambda v: left + (fx(v) - x0) / (x1 - x0) * (W - left - right)
    py = lambda v: bottom - (v - y0) / (y1 - y0) * ph
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'style="max-width:100%;height:auto"><rect width="{W}" height="{H}" rx="14" fill="{PANEL}"/>']
    s.append(f'<rect x="24" y="22" width="{30 + len(label) * 17}" height="44" rx="8" fill="{SG["provenance"][label]}"/>')
    s.append(text(39, 54, label, 28, "#FFFFFF", weight=600))
    y = 84 + 24
    for ln in heads:
        s.append(text(24, y, ln, 34, weight=700))
        y += 40
    if legend:
        for name, _, color, dash in series:
            d = ' stroke-dasharray="10 8"' if dash else ""
            s.append(f'<line x1="24" y1="{y + 2}" x2="70" y2="{y + 2}" stroke="{color}" stroke-width="5"{d}/>')
            s.append(text(84, y + 12, name))
            y += 44
    s.append(text(24, top - 24, ylab, 28, MUTED))
    for v in yticks or []:
        s.append(f'<line x1="{left}" y1="{py(v):.1f}" x2="{W - right}" y2="{py(v):.1f}" stroke="{MUTED}" stroke-opacity=".25"/>')
        s.append(text(left - 12, py(v) + 10, fmt(v), 28, MUTED, "end"))
    for v in xticks or []:
        s.append(text(px(v), bottom + 40, fmt(v), 28, MUTED, "middle"))
    s.append(f'<line x1="{left}" y1="{bottom}" x2="{W - right}" y2="{bottom}" stroke="{MUTED}" stroke-width="2"/>')
    s.append(text(W - right, bottom + 82, xlab, 28, MUTED, "end"))
    for _, pts, color, dash in series:
        d = ' stroke-dasharray="10 8"' if dash else ""
        path = " ".join(f"{'M' if i == 0 else 'L'}{px(x):.1f},{py(v):.1f}" for i, (x, v) in enumerate(pts))
        s.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="5" stroke-linejoin="round"{d}/>')
    for x, v, name, anchor in marks:
        s.append(f'<circle cx="{px(x):.1f}" cy="{py(v):.1f}" r="9" fill="{INK}" stroke="{PANEL}" stroke-width="3"/>')
        s.append(text(px(x) + (14 if anchor == "start" else -14), py(v) - 14, name, 28, INK, anchor))
    for i, ln in enumerate(notes):
        s.append(text(24, bottom + 124 + 34 * i, ln, 28, MUTED))
    return "".join(s) + "</svg>"
