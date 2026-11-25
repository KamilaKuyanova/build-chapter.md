#!/usr/bin/env python3
"""Шаг «решение на данных» на открытом датасете (ТЗ: «признаки → правило → вывод … задание на открытых данных»).

Вход: data/<глава>/datasets/*.json (срез открытых данных, см. engine/datasets/volve_extract.py) и описание практикума
data/<глава>/datasets/<id>.practicum.json: к какому шагу он относится, какие утверждения шага — правило.
Выход:
  - иллюстрация класса A «реальные данные» (кривые — код из данных, без генерации): illustrations/<id>.svg + data_extra.json;
  - задания kind="data" в tasks.json: для каждой зоны «что это за пласт?» (ключ — официальная интерпретация владельца данных)
    и задание на признаки, отличающие нефть от воды; пояснение называет числа зоны.
Запуск: python engine/data_practicum.py --dir data/latyshova (в run_b.py — после шага «задания»)."""
import argparse
import html
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import domain  # noqa: E402

SG = domain.load("styleguide.json")
CLASSES = {"clay": "Глина", "oil": "Коллектор, насыщенный нефтью", "water": "Коллектор, насыщенный водой",
           "tight": "Плотная порода (неколлектор)"}


def esc(s):
    return html.escape(str(s), quote=True)


def num(x, nd=2):
    s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def classify(k):
    """Класс зоны по интерпретации владельца данных (CPI): глинистость, флаг коллектора, водонасыщенность, пористость."""
    if k["SAND_FLAG"] >= 0.5:
        return "oil" if k["SW"] < 0.5 else "water"
    if k["VSH"] >= 0.4:
        return "clay"
    return "tight"


def svg(D):
    """Узкий кадр под телефон (ширина 420, шрифт ≥ 19: на экране 390 px подписи не мельче 16 px)."""
    import textwrap
    W, FS = 420, 19
    tracks = [("GR", "ГК, API", "lin", (0, 150), SG["curves"]["GR"]["color"]),
              ("RT", "Сопротивление, Ом·м", "log", (0.2, 200), SG["curves"]["RES"]["color"]),
              ("RHOB", "Плотность, г/см³", "lin", (1.95, 2.95), SG["curves"]["DENSITY"]["color"]),
              ("NPHI", "Нейтронная пористость", "lin", (0.45, -0.15), SG["curves"]["NEUTRON"]["color"])]
    wrap = lambda t, fs: textwrap.wrap(t, width=int((W - 30) / (fs * 0.55)))  # noqa: E731
    title = wrap(f"Интерпретируй сам: скважина {D['well']}, Volve", 23)
    legend = [f"{name}: {num(rng[0])}…{num(rng[1])}" + (" (лог.)" if kind == "log" else "")
              for key, name, kind, rng, color in tracks]
    y = 34
    head = []
    for ln in title:
        head.append(f'<text x="15" y="{y}" font-size="23" font-weight="700" fill="{SG["text"]}">{esc(ln)}</text>')
        y += 29
    head.append(f'<text x="15" y="{y}" font-size="{FS}" font-weight="700" fill="{SG["provenance"]["реальные данные"]}">реальные данные</text>')
    y += 30
    for (key, name, kind, rng, color), ln in zip(tracks, legend):
        head.append(f'<line x1="15" y1="{y - 6}" x2="37" y2="{y - 6}" stroke="{color}" stroke-width="4"/>')
        head.append(f'<text x="44" y="{y}" font-size="{FS}" fill="{SG["text"]}">{esc(ln)}</text>')
        y += 26
    top, H = y + 14, 900
    x0, dw = 10, 58
    tw = (W - x0 - dw - 10) / 3
    d0, d1 = D["interval"]
    Y = lambda d: top + (d - d0) / (d1 - d0) * H  # noqa: E731
    foot = wrap("Зоны А–Г подсвечены без ответа. Ключ — официальная интерпретация Equinor (CPI), числа не исправлялись. "
                f"Источник: {D['source']}. Лицензия: {D['licence']}.", FS)
    total = top + H + 20 + 25 * len(foot)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {total}" width="{W}" height="{total}" '
           f'style="max-width:100%;height:auto" role="img" aria-label="Каротаж скважины {esc(D["well"])} {d0}–{d1} м: ГК, '
           f'сопротивление, плотность и нейтронная пористость; зоны А–Г для самостоятельной интерпретации" '
           f'font-family="Segoe UI, sans-serif">', f'<rect width="{W}" height="{total}" fill="{SG["background"]}"/>'] + head
    for i in range(3):
        tx = x0 + dw + i * tw
        out.append(f'<rect x="{tx:.1f}" y="{top}" width="{tw:.1f}" height="{H}" fill="{SG["panel"]}" stroke="{SG["muted"]}"/>')
        if i == 1:
            for v in (2, 20):
                px = tx + (math.log10(v) - math.log10(0.2)) / 3 * tw
                out.append(f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{top + H}" stroke="{SG["muted"]}" stroke-opacity="0.3"/>')
    for d in range(int(math.ceil(d0 / 20) * 20), int(d1) + 1, 20):
        out.append(f'<text x="{x0 + dw - 6}" y="{Y(d) + 7:.1f}" font-size="{FS}" fill="{SG["text"]}" text-anchor="end">{d}</text>')
        out.append(f'<line x1="{x0 + dw}" y1="{Y(d):.1f}" x2="{W - 10}" y2="{Y(d):.1f}" stroke="{SG["muted"]}" stroke-opacity="0.25"/>')
    out.append(f'<text x="{x0}" y="{top - 6}" font-size="{FS}" fill="{SG["muted"]}">м</text>')
    for z in D["zones"]:
        out.append(f'<rect x="{x0 + dw}" y="{Y(z["from"]):.1f}" width="{3 * tw:.1f}" height="{Y(z["to"]) - Y(z["from"]):.1f}" '
                   f'fill="{SG["text"]}" fill-opacity="0.10" stroke="{SG["text"]}" stroke-opacity="0.55" stroke-dasharray="6 5"/>')
        out.append(f'<text x="{x0 + dw + 3 * tw - 6:.1f}" y="{(Y(z["from"]) + Y(z["to"])) / 2 + 9:.1f}" font-size="26" '
                   f'font-weight="700" fill="{SG["text"]}" text-anchor="end">{z["label"]}</text>')
    for i, (key, name, kind, rng, color) in zip((0, 1, 2, 2), tracks):
        tx = x0 + dw + i * tw
        lo, hi = rng
        pts, segs = [], []
        for d, v in zip(D["depth"], D["curves"][key]):
            if v is None or (kind == "log" and v <= 0):
                if pts:
                    segs.append(pts)
                pts = []
                continue
            f = (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) if kind == "log" else (v - lo) / (hi - lo)
            pts.append(f"{tx + min(1.0, max(0.0, f)) * tw:.1f},{Y(d):.1f}")
        if pts:
            segs.append(pts)
        for p_ in segs:
            out.append(f'<polyline points="{" ".join(p_)}" fill="none" stroke="{color}" stroke-width="2"/>')
    for k, ln in enumerate(foot):
        out.append(f'<text x="15" y="{top + H + 32 + 25 * k}" font-size="{FS}" fill="{SG["muted"]}">{esc(ln)}</text>')
    out.append("</svg>")
    return "".join(out)


def tasks_for(D, P):
    zs = []
    for z in D["zones"]:
        c = classify(z["key"])
        k, lg = z["key"], z["logs"]
        facts = (f"ГК {num(lg['GR'], 0)} API, сопротивление {num(lg['RT'], 1)} Ом·м, плотность {num(lg['RHOB'])} г/см³; "
                 f"по интерпретации Equinor: глинистость {num(k['VSH'])}, пористость {num(k['PHIF'])}, водонасыщенность {num(k['SW'])}")
        zs.append((z, c, facts))
    opts = [("o1", "clay"), ("o2", "oil"), ("o3", "water"), ("o4", "tight")]
    out = []
    for z, c, facts in zs:
        rule = P["rule_claims"][c]
        out.append({
            "id": f"{P['step_id']}.data.{z['label']}", "type": "single", "step_id": P["step_id"], "claim_ids": [rule["claim_id"]],
            "kind": "data",
            "prompt": f"Скважина {D['well']} (Volve), зона {z['label']}, {z['from']}–{z['to']} м: что это за пласт? "
                      f"Сравните показания кривых с таблицей признаков.",
            "options": [{"id": o, "text": CLASSES[cl], "misconception": ("misc.high_res_oil" if cl == "oil" and c == "tight" else None)}
                        for o, cl in opts],
            "answer": dict((cl, o) for o, cl in opts)[c],
            "explanation": f"{CLASSES[c]}: {facts}." + (" " + P["notes"][c] if P.get("notes", {}).get(c) else ""),
            "evidence": rule["evidence"]})
    oil = next(z for z, c, _ in zs if c == "oil")
    wat = next(z for z, c, _ in zs if c == "water")
    out.append({
        "id": f"{P['step_id']}.data.oil_vs_water", "type": "multiple", "step_id": P["step_id"],
        "claim_ids": [P["rule_claims"]["oil"]["claim_id"]], "kind": "data",
        "prompt": f"Зоны {oil['label']} и {wat['label']} — обе коллекторы. Какие показания отличают нефть от воды в этой скважине?",
        "options": [{"id": "o1", "text": f"Сопротивление: в зоне {oil['label']} ≈ {num(oil['logs']['RT'], 0)} Ом·м, "
                                         f"в зоне {wat['label']} ≈ {num(wat['logs']['RT'], 1)} Ом·м", "misconception": None},
                    {"id": "o2", "text": "Само по себе низкое значение ГК", "misconception": "misc.gr_measures_clay"},
                    {"id": "o3", "text": "Водонасыщенность по интерпретации: "
                                         f"{num(oil['key']['SW'])} против {num(wat['key']['SW'])}", "misconception": None},
                    {"id": "o4", "text": "Высокое сопротивление само по себе, без проверки, что это коллектор",
                     "misconception": "misc.high_res_oil"}],
        "answer": ["o1", "o3"],
        "explanation": "Нефть отличает от воды сопротивление коллектора и рассчитанная по нему водонасыщенность; "
                       "сначала по ГК и плотности убеждаемся, что это коллектор.",
        "evidence": P["rule_claims"]["oil"]["evidence"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    extra, added = {}, 0
    for pp in sorted((d / "datasets").glob("*.practicum.json")) if (d / "datasets").exists() else []:
        P = json.loads(pp.read_text(encoding="utf-8"))
        D = json.loads((d / "datasets" / f"{P['dataset']}.json").read_text(encoding="utf-8"))
        (d / "illustrations").mkdir(exist_ok=True)
        (d / "illustrations" / f"{D['id']}.svg").write_text(svg(D), encoding="utf-8")
        extra.setdefault(P["step_id"], []).append({
            "id": f"{P['step_id']}.{D['id']}", "file": f"illustrations/{D['id']}.svg", "frame_class": "A",
            "origin": "code_from_data", "label": "реальные данные",
            "caption": f"Практикум на открытых данных: {D['title']}. Определите зоны А–Г по таблице признаков (задания ниже).",
            "alt": f"Каротаж скважины {D['well']}: ГК, сопротивление, плотность и нейтронная пористость, зоны А–Г",
            "source": D["source"], "claim_ids": [r["claim_id"] for r in P["rule_claims"].values()][:3], "prompt": None})
        tp = d / "tasks.json"
        T = json.loads(tp.read_text(encoding="utf-8"))
        new = tasks_for(D, P)
        ids = {t["id"] for t in new}
        T["tasks"] = [t for t in T["tasks"] if t["id"] not in ids] + new
        tp.write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
        added += len(new)
    (d / "data_extra.json").write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{d.name}: практикумов на данных {len(extra)}, заданий на данных {added}")


if __name__ == "__main__":
    main()
