#!/usr/bin/env python3
"""Иллюстрации курса кодом из текста шага (часть Б, формат illustration.schema организаторов).
Класс B (процессы/логика), origin=code_from_model, метка «схема». Генерации ИИ нет, новых фактов нет:
в схеме только текст самого шага и его страницы. Цвета из domain_pack/styleguide.json.

Для каждого шага: «механизм → практика → нюансы»; для шагов с decision_on_data ещё «признак → правило → вывод».
Запуск: python engine/gen_illustrations.py --dir data/latyshova [--extra file.json]
  --extra: готовые иллюстрации (например, кадры сцены каротажа) вида {step_id: [{file,frame_class,origin,label,caption,alt,...}]}"""
import argparse
import html
import json
import pathlib
import re
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nodetext  # noqa: E402
import domain  # noqa: E402  доменный пакет по имени домена (DOMAIN)

SG = domain.load("styleguide.json")

W, H = 1280, 720


def esc(s):
    return html.escape(s, quote=True)


def short(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def lines(txt, width, maxl):
    ls = textwrap.wrap(txt, width=width) or [""]
    if len(ls) > maxl:
        ls = ls[:maxl]
        ls[-1] = ls[-1].rstrip(".,;: ") + "…"
    return ls


def box(x, y, w, h, head, body, color):
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{SG["panel"]}" stroke="{color}" stroke-width="3"/>',
         f'<text x="{x + 20}" y="{y + 44}" font-family="Segoe UI" font-size="30" font-weight="700" fill="{color}">{esc(head)}</text>']
    for k, ln in enumerate(lines(body, 31, 10)):
        s.append(f'<text x="{x + 20}" y="{y + 90 + k * 34}" font-family="Segoe UI" font-size="24" fill="{SG["text"]}">{esc(ln)}</text>')
    return "".join(s)


def arrow(x, y):
    return f'<polygon points="{x},{y - 18} {x + 26},{y} {x},{y + 18}" fill="{SG["muted"]}"/>'


def frame(title, boxes, foot, ytop=170):
    n = len(boxes)
    gap = 44
    bw = (W - 80 - gap * (n - 1)) / n
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="max-width:100%;height:auto">',
         f'<rect width="{W}" height="{H}" fill="{SG["background"]}"/>']
    for k, ln in enumerate(lines(title, 56, 2)):
        s.append(f'<text x="40" y="{64 + k * 46}" font-family="Segoe UI" font-size="40" font-weight="700" fill="{SG["text"]}">{esc(ln)}</text>')
    s.append(f'<text x="{W - 40}" y="40" text-anchor="end" font-family="Segoe UI" font-size="26" font-weight="700" '
             f'fill="{SG["provenance"]["схема"]}">схема</text>')
    for k, (head, body, color) in enumerate(boxes):
        x = 40 + k * (bw + gap)
        s.append(box(x, ytop, bw, 470, head, body, color))
        if k < n - 1:
            s.append(arrow(x + bw + 9, ytop + 235))
    s.append(f'<text x="40" y="{H - 24}" font-family="Segoe UI" font-size="24" fill="{SG["muted"]}">{esc(foot)}</text>')
    s.append("</svg>")
    return "".join(s)


def ftext(f):
    return nodetext._f(f)


def step_diagram(node):
    ly = node["layers"]
    parts = [("Механизм", ftext(ly.get("mechanism")), SG["curves"]["GR"]["color"]),
             ("Практика", ftext(ly.get("practice")), SG["curves"]["SP"]["color"]),
             ("Нюансы", ftext(ly.get("nuances")), SG["curves"]["RES"]["color"])]
    parts = [(h, short(t, 260), c) for (h, t, c) in parts if t.strip()]
    if len(parts) < 2:
        main = ftext(ly.get("main"))
        parts = [("Суть", short(main, 260), SG["curves"]["GR"]["color"])] + parts
    pages = ", ".join(str(p) for p in node.get("pages", [])[:4])
    title = node.get("title_novice") or node["title"]
    return frame(title, parts, f"по тексту главы · стр. {pages}" if pages else "по тексту главы")


def decision_diagram(node):
    d = node["decision_on_data"]
    parts = [("Признаки", short("; ".join(d["features"]), 250), SG["curves"]["RES"]["color"]),
             ("Правило", short(d["rule"], 250), SG["curves"]["SP"]["color"]),
             ("Вывод", short(d["conclusion"], 250), SG["curves"]["GR"]["color"])]
    title = "Решение на данных: " + (node.get("title_novice") or node["title"])
    pages = ", ".join(str(p) for p in node.get("pages", [])[:4])
    return frame(title, parts, f"признаки → правило → вывод · стр. {pages}" if pages else "признаки → правило → вывод")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--extra", action="append")
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    layer = json.loads((d / "layer.json").read_text(encoding="utf-8-sig"))
    out = d / "illustrations"
    out.mkdir(exist_ok=True)
    extra = {}
    for ex_path in a.extra or []:   # несколько списков: ролики (media_extra), перерисованные рисунки (figures_extra)
        for k, v in json.loads(pathlib.Path(ex_path).read_text(encoding="utf-8")).items():
            extra.setdefault(k, []).extend(v)
    ills = []
    for n in sorted(layer["nodes"], key=lambda x: x["order"]):
        nid, cl = n["id"], [c["id"] for c in n["claims"]][:3]
        title = n.get("title_novice") or n["title"]
        (out / f"{nid}.svg").write_text(step_diagram(n), encoding="utf-8")
        ills.append({"id": f"{nid}.i1", "step_id": nid, "node_id": nid, "file": f"illustrations/{nid}.svg", "frame_class": "B",
                     "origin": "code_from_model", "label": "схема",
                     "caption": f"Схема шага «{title}»: механизм, практика, нюансы — по тексту главы.",
                     "alt": f"Схема шага «{title}»: три блока — механизм, практика и нюансы, стрелки слева направо",
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
