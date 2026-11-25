#!/usr/bin/env python3
"""Иллюстрации курса кодом из текста шага (часть Б, формат illustration.schema организаторов).
Класс B, origin=code_from_model, метка «схема». Генерации ИИ нет, новых фактов нет. Цвета из domain_pack/styleguide.json.

Для каждого шага: место в главе по связям слоя; для шагов с decision_on_data ещё «признаки → правило → вывод».
Запуск: python engine/gen_illustrations.py --dir data/latyshova [--extra file.json]
  --extra: готовые иллюстрации (например, кадры сцены каротажа) вида {step_id: [{file,frame_class,origin,label,caption,alt,...}]}"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nodetext  # noqa: E402
import domain  # noqa: E402  доменный пакет по имени домена (DOMAIN)

SG = domain.load("styleguide.json")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "scenes"))
from plot import FONT, INK, MUTED, PANEL, text, wrap  # noqa: E402

W = 640  # при ширине 358 px подпись 30 -> 16.8 px, на телефоне читается


def head(title, label="схема"):
    s = [f'<rect x="24" y="22" width="{30 + len(label) * 17}" height="44" rx="8" fill="{SG["provenance"][label]}"/>',
         text(39, 54, label, 28, "#FFFFFF", weight=600)]
    y = 108
    for ln in wrap(title, 29):
        s.append(text(24, y, ln, 34, weight=700))
        y += 40
    return s, y


def finish(s, y, foot):
    for ln in wrap(foot, 40):
        s.append(text(24, y + 34, ln, 28, MUTED))
        y += 34
    H = int(y + 26)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'style="max-width:100%;height:auto"><rect width="{W}" height="{H}" rx="14" fill="{PANEL}"/>' + "".join(s) + "</svg>")


def box(s, y, body, color, title=None, strong=False):
    """Блок во всю ширину; возвращает нижний край."""
    lines_ = wrap(body, 32)
    h = 28 + 38 * len(lines_) + (42 if title else 0)
    fill = color if strong else SG["background"]
    s.append(f'<rect x="24" y="{y}" width="{W - 48}" height="{h}" rx="12" fill="{fill}" stroke="{color}" stroke-width="3"/>')
    ty = y + 42
    if title:
        s.append(text(46, ty, title, 28, color, weight=700))
        ty += 42
    for ln in lines_:
        s.append(text(46, ty, ln, FONT, "#0F1419" if strong else INK, weight=700 if strong else 400))
        ty += 38
    return y + h


def down(s, y):
    s.append(f'<polygon points="{W / 2 - 16},{y + 8} {W / 2 + 16},{y + 8} {W / 2},{y + 30}" fill="{MUTED}"/>')
    return y + 38


def name(n):
    return n.get("title_novice") or n["title"]


def pages_of(node):
    p = node.get("pages", [])
    return "стр. " + ", ".join(map(str, p[:4])) if p else "по тексту главы"


def step_diagram(node, nodes):
    """Место шага в главе: на что опирается и куда ведёт. Строится из связей слоя, текста главы не пересказывает."""
    by_id = {n["id"]: n for n in nodes}
    before = [by_id[l["target"]] for l in node.get("links", []) if l["type"] == "prerequisite" and l["target"] in by_id]
    after = [n for n in nodes if any(l["type"] == "prerequisite" and l["target"] == node["id"] for l in n.get("links", []))]
    blue, gold, green = SG["fluids"]["water"]["color"], SG["curves"]["RES"]["color"], SG["curves"]["GR"]["color"]
    s, y = head("Место шага в главе")
    if before:
        s.append(text(24, y + 14, "опирается на", 28, MUTED))
        y += 30
        for n in before[:3]:
            y = box(s, y, name(n), blue) + 12
        y = down(s, y - 12)
    y = box(s, y + (0 if before else 10), name(node), gold, strong=True)
    if after:
        y = down(s, y)
        s.append(text(24, y + 18, "ведёт к", 28, MUTED))
        y += 34
        for n in after[:3]:
            y = box(s, y, name(n), green) + 12
    return finish(s, y, f"построено из связей шагов · {pages_of(node)}")


def decision_diagram(node):
    d = node["decision_on_data"]
    gold, red, green = SG["curves"]["RES"]["color"], SG["fluids"]["gas"]["color"], SG["curves"]["GR"]["color"]
    s, y = head("Решение на данных")
    y = box(s, y + 6, "; ".join(d["features"]), gold, "Признаки")
    y = box(s, down(s, y), d["rule"], SG["fluids"]["water"]["color"], "Правило")
    y = box(s, down(s, y), d["conclusion"], green, "Вывод")
    if d.get("counterexample"):
        y = box(s, y + 16, d["counterexample"], red, "Но бывает иначе")
    return finish(s, y, pages_of(node))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--extra", action="append")
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    layer = json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))
    out = d / "illustrations"
    out.mkdir(exist_ok=True)
    extra = {}  # ролики, перерисованные рисунки, расчётные сцены и анимации подхватываются сами; --extra — сверх этого
    auto = [d / f for f in ("media_extra.json", "figures_extra.json", "extra_illustrations.json", "anim_extra.json")]
    for path in [p for p in auto if p.exists()] + [pathlib.Path(p) for p in a.extra or []]:
        for k, v in json.loads(path.read_text(encoding="utf-8")).items():
            have = {x["file"] for x in extra.setdefault(k, [])}
            extra[k] += [x for x in v if x["file"] not in have]
    ills = []
    for n in sorted(layer["nodes"], key=lambda x: x["order"]):
        nid, cl = n["id"], [c["id"] for c in n["claims"]][:3]
        title = n.get("title_novice") or n["title"]
        (out / f"{nid}.svg").write_text(step_diagram(n, layer["nodes"]), encoding="utf-8")
        ills.append({"id": f"{nid}.i1", "step_id": nid, "node_id": nid, "file": f"illustrations/{nid}.svg", "frame_class": "B",
                     "origin": "code_from_model", "label": "схема",
                     "caption": f"Место шага «{title}» в главе: на что опирается и куда ведёт.",
                     "alt": f"Схема: предыдущие шаги, шаг «{title}» и следующие шаги, стрелки сверху вниз",
                     "source": None, "claim_ids": cl, "prompt": None})
        if n.get("decision_on_data"):
            (out / f"{nid}.decision.svg").write_text(decision_diagram(n), encoding="utf-8")
            ills.append({"id": f"{nid}.i2", "step_id": nid, "node_id": nid, "file": f"illustrations/{nid}.decision.svg",
                         "frame_class": "B", "origin": "code_from_model", "label": "схема",
                         "caption": f"Решение на данных в шаге «{title}»: признаки, правило, вывод.",
                         "alt": f"Схема «признаки, правило, вывод» для шага «{title}»", "source": None, "claim_ids": cl, "prompt": None})
        for e in extra.get(nid, []):
            ills.append(e | {"id": e.get("id") or f"{nid}.x{len(ills)}", "step_id": nid, "node_id": nid})
    (d / "illustrations.json").write_text(json.dumps({"chapter": layer["chapter"], "illustrations": ills}, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print(f"{d.name}: иллюстраций {len(ills)} (файлов в {out})")


if __name__ == "__main__":
    main()
