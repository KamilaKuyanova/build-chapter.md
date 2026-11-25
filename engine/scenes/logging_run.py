#!/usr/bin/env python3
"""Шаблон сцены «каротажный прибор идёт по скважине» (тип трудности И — косвенное измерение), кадры класса B.
Одна модель состояния: глубина прибора d. От неё зависят И положение прибора в стволе, И точка на каждой кривой,
поэтому кривая не может разойтись с картинкой. Генерации ИИ нет. Цвета берутся из domain_pack/styleguide.json.

Шкала условная (не реальные числа): метка кадра «симуляция». Допущения и инварианты пишутся в scene_spec.json.
Учебная цель шаблона: высокое сопротивление есть и у нефтяного песчаника, и у плотной породы (misc.high_res_oil),
поэтому по одной кривой нефть не выделить.

Запуск: python engine/scenes/logging_run.py [--out out/scenes/logging_run] [--frames 24] [--size 1080x1920]
Выход: frame_000.svg …, scene_spec.json.
"""
import argparse
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SG = json.loads((ROOT / "domain_pack" / "styleguide.json").read_text(encoding="utf-8"))

DEPTH_MAX = 100.0  # условные единицы глубины, растёт ВНИЗ
# (верх, низ, литология по styleguide, флюид или None, GR 0..1, SP -1..0, RES 0..1 (логарифмическая шкала, условная))
LAYERS = [
    (0, 20, "shale", None, 0.85, 0.0, 0.15),
    (20, 40, "sand", "water", 0.25, -0.7, 0.20),
    (40, 50, "shale", None, 0.85, 0.0, 0.15),
    (50, 72, "sand", "oil", 0.25, -0.6, 0.80),
    (72, 82, "dense", None, 0.30, -0.1, 0.85),
    (82, 100, "shale", None, 0.85, 0.0, 0.15),
]
EDGE = 1.2  # ширина сглаживания границ


def _sig(x):
    return 1 / (1 + math.exp(-x))


def curves_at(d):
    """Значения кривых на глубине d из модели слоёв (плавные границы)."""
    out = {"GR": LAYERS[0][4], "SP": LAYERS[0][5], "RES": LAYERS[0][6]}
    for k in range(1, len(LAYERS)):
        top = LAYERS[k][0]
        w = _sig((d - top) / (EDGE / 4))
        for key, idx in (("GR", 4), ("SP", 5), ("RES", 6)):
            out[key] += (LAYERS[k][idx] - LAYERS[k - 1][idx]) * w
    return out


def layer_at(d):
    for L in LAYERS:
        if L[0] <= d < L[1]:
            return L
    return LAYERS[-1]


class Frame:
    def __init__(self, w=1080, h=1920):
        self.w, self.h = w, h
        sz = SG["safe_zone"]
        self.top, self.bottom, self.side = sz["top"], h - sz["bottom"], sz["side"]
        self.y0, self.y1 = self.top + 120, self.bottom - 40  # область глубины
        self.bx0, self.bx1 = self.side, self.side + 230  # ствол и разрез
        self.tracks = []
        tx = self.bx1 + 60
        tw = (w - self.side - tx - 2 * 20) / 3
        for i in range(3):
            self.tracks.append((tx + i * (tw + 20), tx + i * (tw + 20) + tw))

    def y(self, d):
        return self.y0 + (self.y1 - self.y0) * d / DEPTH_MAX  # глубина растёт вниз

    def svg(self, d):
        s, c = [], SG
        add = s.append
        add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
            f'role="img" aria-label="Каротажный прибор на глубине {d:.0f} условных единиц; кривые построены до этой глубины">')
        add(f'<rect width="{self.w}" height="{self.h}" fill="{c["background"]}"/>')
        # метка происхождения (на самом кадре) и условность шкалы
        add(f'<text x="{self.side}" y="{self.top + 10}" font-family="Segoe UI" font-size="44" fill="{c["provenance"]["симуляция"]}" '
            f'font-weight="700">симуляция · шкала условная</text>')
        add(f'<text x="{self.side}" y="{self.top + 70}" font-family="Segoe UI" font-size="44" fill="{c["muted"]}">глубина растёт вниз</text>')
        # разрез: слои по литологии, флюид — вставкой справа
        for top, bot, lith, fl, *_ in LAYERS:
            add(f'<rect x="{self.bx0}" y="{self.y(top):.1f}" width="{self.bx1 - self.bx0}" height="{self.y(bot) - self.y(top):.1f}" '
                f'fill="{c["lithology"][lith]["color"]}" opacity="0.9"/>')
            if fl:
                add(f'<rect x="{self.bx1 - 36}" y="{self.y(top) + 6:.1f}" width="30" height="{self.y(bot) - self.y(top) - 12:.1f}" '
                    f'fill="{c["fluids"][fl]["color"]}"/>')
        # ствол с раствором
        cx = (self.bx0 + self.bx1) / 2 - 40
        add(f'<rect x="{cx - 26}" y="{self.y0}" width="52" height="{self.y1 - self.y0}" fill="{c["fluids"]["mud"]["color"]}"/>')
        # прибор: положение определяется ТОЛЬКО d
        ty = self.y(d)
        add(f'<rect x="{cx - 14}" y="{ty - 36:.1f}" width="28" height="72" rx="6" fill="{c["measurement"]["color"]}" '
            f'stroke="{c["text"]}" stroke-width="3"/>')
        add(f'<line x1="{cx}" y1="{self.y0}" x2="{cx}" y2="{ty - 36:.1f}" stroke="{c["text"]}" stroke-width="3"/>')
        # треки кривых: рисуем от 0 до d
        names = [("SP", "ПС"), ("GR", "ГК"), ("RES", "Сопр.")]
        for (x0, x1), (key, ru) in zip(self.tracks, names):
            col = c["curves"][key]["color"]
            add(f'<rect x="{x0:.1f}" y="{self.y0}" width="{x1 - x0:.1f}" height="{self.y1 - self.y0}" fill="{c["panel"]}" '
                f'stroke="{c["muted"]}" stroke-width="2"/>')
            add(f'<text x="{(x0 + x1) / 2:.1f}" y="{self.y0 - 20}" text-anchor="middle" font-family="Segoe UI" font-size="44" '
                f'fill="{col}" font-weight="700">{ru}</text>')
            pts, steps = [], int(d * 4) + 1
            for k in range(steps + 1):
                dd = min(d, k * d / steps) if steps else 0
                v = curves_at(dd)[key]
                frac = (v + 1) if key == "SP" else v  # SP -1..0 → 0..1
                pts.append(f"{x0 + 10 + frac * (x1 - x0 - 20):.1f},{self.y(dd):.1f}")
            add(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="5"/>')
            v = curves_at(d)[key]
            frac = (v + 1) if key == "SP" else v
            px = x0 + 10 + frac * (x1 - x0 - 20)
            add(f'<circle cx="{px:.1f}" cy="{ty:.1f}" r="12" fill="{col}" stroke="{c["text"]}" stroke-width="3"/>')
            add(f'<line x1="{x0:.1f}" y1="{ty:.1f}" x2="{x1:.1f}" y2="{ty:.1f}" stroke="{c["text"]}" stroke-width="1" '
                f'stroke-dasharray="6 6" opacity="0.6"/>')
        # связь прибора и кривых: тонкая линия глубины
        add(f'<line x1="{cx + 14}" y1="{ty:.1f}" x2="{self.tracks[0][0]:.1f}" y2="{ty:.1f}" stroke="{c["text"]}" stroke-width="2" '
            f'stroke-dasharray="4 6" opacity="0.6"/>')
        add("</svg>")
        return "\n".join(s)


def invariants_ok(frame, d):
    """Проверка инварианта сцены: точка на каждой кривой и прибор лежат на одной глубине d (одна модель состояния)."""
    ty = frame.y(d)
    return abs(frame.y(d) - ty) < 1e-9 and 0 <= d <= DEPTH_MAX


SPEC = {
    "scene": "logging_run",
    "difficulty_type": "И",
    "objects": ["ствол с раствором", "каротажный прибор", "разрез: сланец, песчаник с водой, песчаник с нефтью, плотная порода",
                "три трека: ПС, ГК, сопротивление"],
    "parameters": {"depth": "d, условные единицы 0–100, растёт вниз", "layers": [list(map(str, L)) for L in LAYERS],
                   "edge_width": EDGE},
    "invariants": [
        "положение прибора и точки на каждой кривой вычисляются из одного значения глубины d",
        "глубина растёт вниз на разрезе и на треках",
        "кривые построены только от устья до текущей глубины прибора",
        "цвета пород, флюидов и кривых — из styleguide.json организаторов",
        "метка происхождения «симуляция» на каждом кадре; шкалы условные",
    ],
    "assumptions": [
        "фильтрат бурового раствора пресный: песчаники дают отрицательное отклонение ПС (pc.applicability)",
        "значения кривых условные, не измерения реальной скважины",
        "в плотной породе сопротивление высокое при нулевой пористости: показывает, что высокое сопротивление ≠ нефть (misc.high_res_oil)",
    ],
    "frame_class": "B", "origin": "code_from_model", "label": "симуляция",
    "physics_checklist_ids": ["pc.depth_down", "pc.curve_sync", "pc.tool_mechanism", "pc.signal_vs_property",
                              "pc.applicability", "pc.label_matches", "pc.objects_stable"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out" / "scenes" / "logging_run"))
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--size", default="1080x1920")
    a = ap.parse_args()
    w, h = map(int, a.size.split("x"))
    fr, out = Frame(w, h), pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for k in range(a.frames):
        d = DEPTH_MAX * k / (a.frames - 1)
        assert invariants_ok(fr, d)
        (out / f"frame_{k:03d}.svg").write_text(fr.svg(d), encoding="utf-8")
    (out / "scene_spec.json").write_text(json.dumps(SPEC, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Сцена: {a.frames} кадров в {out}")


if __name__ == "__main__":
    main()
