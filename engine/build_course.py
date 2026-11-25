#!/usr/bin/env python3
"""Сборщик демо-курса (часть Б). Входы в ОФИЦИАЛЬНЫХ форматах: layer.json, tasks.json, illustrations.json [, routing.json].
Выход: out/course/index.html (один файл, офлайн, без сервера) + assets/.
Запуск: python engine/build_course.py [--dir data/current] [--out out/course] [--strict]
--strict: ненулевой код выхода при любых нарушениях правил ТЗ (проверка engine/validate_layer.py)."""
import argparse
import html
import json
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nodetext  # noqa: E402
from mathml import convert, rich  # noqa: E402
import validate_layer  # noqa: E402
import domain  # noqa: E402  доменный пакет по имени домена (DOMAIN)

ROOT = pathlib.Path(__file__).resolve().parent.parent
WARN = []
KINDS = {"observation": "наблюдение", "inference": "вывод", "assumption": "допущение"}
FMT_LABEL = {"шортс": "ролик-шортс", "длинное видео": "ролик-разбор", "интерактив": "интерактив",
             "практикум на данных": "практикум на данных", "карточки": "карточки", "текст": "текст"}


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def warn(m):
    WARN.append(m)


def claim_map(node):
    return {c["id"]: c for c in node.get("claims", [])}


def page_tag(node, field=None):
    """«стр. N» у абзаца: по claim_ids поля, иначе по страницам узла. Нет страницы = нарушение ТЗ."""
    pages = list(field.get("pages") or []) if isinstance(field, dict) else []
    cm = claim_map(node)
    for cid in (field or {}).get("claim_ids", []) if isinstance(field, dict) else []:
        if cid in cm:
            pages.append(cm[cid]["page_pdf"])
    if not pages:
        pages = list(node.get("pages", []))
    if not pages:
        warn(f"[{node['id']}] абзац без страницы источника")
        return '<span class="src bad">стр. ? </span>'
    return f'<span class="src">стр. {e(", ".join(str(p) for p in sorted(set(pages))))}</span>'


def who(f):
    return '<span class="tag">модель</span>' if isinstance(f, dict) and f.get("by_model") else '<span class="tag">автор</span>'


def fld(node, f, cls=""):
    if not f or not isinstance(f, dict) or not f.get("text"):
        return ""
    hyp = ' <span class="tag hyp">гипотеза</span>' if f.get("hypothesis") else ""
    return f'<p class="{cls}">{rich(f["text"])}{hyp} {who(f)} {page_tag(node, f)}</p>'


def fld_paras(node, f, title=""):
    """Слой поля по абзацам, у каждого своя страница; без разбивки — одним абзацем."""
    if not isinstance(f, dict):
        return ""
    body = "".join(fld(node, p) for p in f.get("paras") or [f])
    return f"<h4>{e(title)}</h4>{body}" if body else ""


def render_formulas(node):
    out = []
    for f in node.get("formulas", []):
        rows = "".join(f'<li><b>{rich(v["symbol"])}</b> — {e(v["meaning"])}'
                       f'{", " + e(v["unit"]) if v.get("unit") else ""}</li>' for v in f["variables"])
        out.append(f'<div class="formula">{convert(f["latex"], block=True)}<p>{rich(f["meaning"])} {who(f)} '
                   f'<span class="src">стр. {e(f["page_pdf"])}</span></p><ul>{rows}</ul></div>')
    return "".join(out)


def render_tables(node):
    out = []
    for t in node.get("tables", []):
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in t["markdown"].splitlines()
                if r.strip().startswith("|")]
        rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
        body = "".join("<tr>" + "".join(f"<{'td' if i else 'th'}>{rich(c)}</{'td' if i else 'th'}>" for c in r) + "</tr>"
                       for i, r in enumerate(rows))
        fixes = "".join(f"<li>{e(x)}</li>" for x in t.get("ocr_fixes", []))
        out.append(f'<h4>{e(t["title"])} <span class="src">стр. {e(t["page_pdf"])}</span></h4>'
                   f'<div style="overflow-x:auto"><table>{body}</table></div>'
                   f'{"<p>Исправления распознавания:</p><ul>" + fixes + "</ul>" if fixes else ""}')
    return "".join(out)


def novice(node):
    return node.get("title_novice") or node["title"]


def block(title, body, cls=""):
    return f"<section class='blk {cls}'><h3>{e(title)}</h3>{body}</section>" if body.strip() else ""


def minutes(node):
    return max(1, round(len(nodetext.node_text(node).split()) / 120))


def render_claims(node):
    items = []
    for c in node.get("claims", []):
        who_ = "модель" if c["source_kind"] == "figure_description_model" else "автор"
        mine = ' <span class="tag">пересказ модели</span>' if c.get("by_model") else ""
        pr = f" (печ. {c['page_print']})" if c.get("page_print") else ""
        items.append(f'<li><b>{e(KINDS.get(c["kind"], c["kind"]))}.</b> {rich(c["text"])}{mine}'
                     f'<blockquote>«{rich(c["quote"])}» — {who_}, <span class="src">стр. {c["page_pdf"]}{e(pr)}</span></blockquote></li>')
    return "<ul class='claims'>" + "".join(items) + "</ul>"


def render_examples(node):
    out = []
    for x in node.get("worked_examples", []):
        steps = "".join(f"<li>{e(s)}</li>" for s in x.get("steps", []))
        fig = f" Рисунок: {e(x['figure'])}." if x.get("figure") else ""
        out.append(f'<div class="ex"><p><b>Условие.</b> {e(x["condition"])}</p><ol>{steps}</ol>'
                   f'<p><b>Итог.</b> {e(x["result"])}{fig} <span class="src">стр. {x["page_pdf"]}</span></p></div>')
    return "".join(out)


def render_book_tasks(node):
    return "".join(f'<p><b>Задача {e(t["number"])}.</b> {rich(t["text"])}'
                   f'{" Рисунок: " + e(t["figure"]) + "." if t.get("figure") else ""} '
                   f'<span class="src">стр. {t["page_pdf"]}</span></p>' for t in node.get("book_tasks", []))


def render_decision(node):
    d = node.get("decision_on_data")
    if not d:
        return ""
    feats = "".join(f"<li>{e(x)}</li>" for x in d["features"])
    cx = f'<b>Контрпример</b><span>{e(d["counterexample"])}</span>' if d.get("counterexample") else ""
    return (f'<div class="kv"><b>Признаки</b><ul>{feats}</ul><b>Правило</b><span>{e(d["rule"])}</span>'
            f'<b>Вывод</b><span>{e(d["conclusion"])}</span>{cx}</div>')


def render_data_meaning(node):
    dm = node.get("data_meaning") or {}
    out = fld(node, dm.get("from_chapter")) + fld(node, dm.get("breaks"))
    for h in dm.get("hypotheses", []):
        out += fld(node, h)
    return out


def render_terms(node, glossary):
    out = []
    own = {g["term"].lower(): g["definition"] for g in node.get("glossary", [])}
    for t in node.get("terms_introduced", []):
        g = own.get(t.lower()) or glossary.get(t.lower())
        out.append(f"<li><b>{e(t)}</b>{' — ' + e(g) if g else ''}</li>")
    return "<ul>" + "".join(out) + "</ul>" if out else ""


def render_illustrations(node, ills):
    out = []
    for i in ills:
        fname = pathlib.Path(i["file"]).name
        lab = f' · {e(i["label"])}' if i.get("label") else ""
        src = f' · {e(i["source"])}' if i.get("source") else ""
        if fname.lower().endswith(".mp4") and fname.startswith("anim_"):   # анимация логики шага: без звука, петлёй
            media = (f'<video autoplay muted loop playsinline controls preload="metadata" src="assets/{e(fname)}" '
                     f'aria-label="{e(i["alt"])}" style="max-width:100%"></video>')
        elif fname.lower().endswith(".mp4"):
            vtt = pathlib.Path(fname).with_suffix(".vtt").name
            media = (f'<video controls preload="metadata" playsinline src="assets/{e(fname)}" aria-label="{e(i["alt"])}" '
                     f'style="max-width:100%;max-height:80vh"><track kind="subtitles" srclang="ru" label="Русские субтитры" '
                     f'src="assets/{e(vtt)}"></video>')
        else:
            media = f'<img src="assets/{e(fname)}" alt="{e(i["alt"])}" loading="lazy">'
        out.append(f'<figure>{media}'
                   f'<figcaption>{e(i["caption"])} <span class="tag">класс {e(i["frame_class"])}{lab}{src}</span></figcaption></figure>')
    return "".join(out)


def render_quizzes(tasks):
    return "".join(f'<div class="quiz" data-ex=\'{e(json.dumps(t, ensure_ascii=False))}\'></div>' for t in tasks)


def render_step(node, i, total, tasks, ills, route, glossary, part=1):
    ly = node.get("layers", {})
    mc = node.get("misconception") if isinstance(node.get("misconception"), dict) else None
    ana = node.get("it_analogy") or {}
    ana_html = ""
    if ana.get("text"):
        ana_html = (f'<p>{e(ana["text"])} {who(ana)}</p><p><b>Где аналогия не работает:</b> {e(ana["breaks_where"])}</p>')
    how = "".join(fld_paras(node, ly.get(k), name) for k, name in (
        ("mechanism", "Механизм"), ("practice", "Как делает специалист"), ("nuances", "Нюансы")))
    deeper = "".join(fld(node, d) for d in ly.get("deeper", []))
    now = fld(node, node.get("now_practice"))
    lens = node.get("inefficiency_lens")
    lens_html = ""
    if lens:
        lens_html = ('<div class="kv">' + "".join(f"<b>{l}</b><span>{e(lens[k])}</span>" for k, l in (
            ("inputs", "Входные данные"), ("manual_steps", "Ручные шаги"), ("judgment_points", "Точки суждения"),
            ("time", "Время"), ("typical_errors", "Типичные ошибки"))) + "</div>")
    meta = f"Часть {part} · шаг {i} из {total} · ≈{minutes(node)} мин"
    if route:
        meta += f" · формат: {e(FMT_LABEL.get(route['format'], route['format']))}"
    ess = ly.get("main")
    nc = len(node.get("claims", []))
    claims_html = (f'<details><summary>{nc} {plural(nc, "цитата", "цитаты", "цитат")} автора со страницами</summary>' + render_claims(node) + "</details>") if nc else ""
    nav = (f'<nav class="stepnav"><a href="#/step/{e(node["id"])}-prev">← Назад</a> '
           f'<button class="done" data-done="{e(node["id"])}">Отметить пройденным</button> '
           f'<a href="#/step/{e(node["id"])}-next">Дальше →</a></nav>')
    return f"""
<article class="view step" id="step-{e(node['id'])}" data-id="{e(node['id'])}" hidden>
  <p class="lab meta">{meta}</p>
  <h2>{e(novice(node))}</h2>
  <p class="meta">{e(node['title'])}. {e(nodetext._f(ly.get('topic')))}</p>
  {block('Почему этот шаг здесь', fld(node, node.get('why_here')))}
  {block('Суть', fld(node, ess, 'essence'), 'ess')}
  {block('Как это работает', how)}
  {block('Глубже', deeper)}
  {block('Разбор примеров из главы', render_examples(node))}
  {block('Формулы', render_formulas(node))}
  {block('Таблицы книги', render_tables(node))}
  {block('Частая ошибка', '<p>' + e(mc['text']) + '</p>' if mc else '', 'err')}
  {block('Что это значит для данных', render_data_meaning(node))}
  {block('Решение на данных', render_decision(node), 'dec')}
  {block('Аналогия', ana_html)}
  {block('Как это делается сейчас', now)}
  {block('Линза неэффективности', lens_html)}
  {block('Новые понятия', render_terms(node, glossary))}
  {block('Источник', claims_html, 'srcs')}
  {block('Задачи из книги', render_book_tasks(node))}
  {block('Иллюстрации', render_illustrations(node, ills), 'ill')}
  {block('Проверь себя', render_quizzes(tasks), 'test')}
  {nav}
</article>"""


def sentence_case(t):
    return t[:1] + t[1:].lower() if t.isupper() else t


def first_unit(n):
    return next((c["unit"] for c in n.get("claims", []) if c.get("unit")), min(n.get("units") or [""]))


def short(t, n=62):
    """Заголовок книги бывает на три строки: режем по слову."""
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(" ,.:;") + "…"


def chapter_parts(nodes, rows):
    """Части пути — разделы главы по её заголовкам; если заголовков нет, группы по восемь шагов."""
    heads, subs = [], []
    for r in rows:
        if r.get("kind") != "heading":
            continue
        t = re.sub(r"\s+", " ", r["excerpt"].lstrip("# ").strip())
        m = re.match(r"^(§\s*\d+(?:\.\d+)*|\d+(?:\.\d+)+)\.?\s*(.*)$", t)
        if m and m.group(2):
            heads.append((r["unit_id"], m.group(1).replace("§ ", "§"), short(sentence_case(m.group(2).rstrip(".")))))
        elif len(t.split()) > 1 and not re.match(r"(?i)глава|chapter|problems|задачи", t):
            subs.append((r["unit_id"], short(sentence_case(t.rstrip(".")))))
    parts, cur = [], -1
    for n in nodes:
        first = first_unit(n)
        k = max((i for i, h in enumerate(heads) if h[0] <= first), default=0) if heads else -1
        if not parts or k > cur:   # назад по главе часть не возвращаем: порядок шагов задаёт граф
            cur = max(k, cur)
            parts.append({"mark": heads[k][1] if heads else "", "title": heads[k][2] if heads else "", "nodes": []})
        parts[-1]["nodes"].append(n)
    if len(parts) < 2:
        parts = [{"mark": "", "title": "", "nodes": nodes[i:i + 8]} for i in range(0, len(nodes), 8)]
    i = 1
    while i < len(parts):   # часть из одного шага присоединяем к предыдущей
        if len(parts[i]["nodes"]) < 2:
            parts[i - 1]["nodes"] += parts.pop(i)["nodes"]
        else:
            i += 1
    out = []
    for p in parts:   # длинный раздел режем по подзаголовкам, а потом поровну
        pieces, done = [{**p, "nodes": []}], set()
        for n in p["nodes"]:
            s = max((h for h in subs if h[0] <= first_unit(n) and heads and h[0] > first_unit(p["nodes"][0])), default=None)
            if len(p["nodes"]) > 14 and s and s not in done and len(pieces[-1]["nodes"]) > 2:
                done.add(s)
                pieces.append({"mark": p["mark"], "title": s[1], "nodes": []})
            pieces[-1]["nodes"].append(n)
        for q in pieces:
            k = max(1, -(-len(q["nodes"]) // 14))
            size = -(-len(q["nodes"]) // k)
            out += [{**q, "title": q["title"] + (f" ({i + 1} из {k})" if k > 1 else ""), "nodes": q["nodes"][i * size:(i + 1) * size]} for i in range(k)]
    parts = out
    for p in parts:
        p["title"] = p["title"] or f'{novice(p["nodes"][0])} — {novice(p["nodes"][-1])}'
    return parts


ICONS = {  # значок на верхней пластине шага
    "видео": '<path d="M-7 -8 9 0 -7 8z" fill="currentColor"/>',
    "практикум на данных": '<path d="M-9 8V1M-3 8V-3M3 8V-7M9 8V-1" stroke="currentColor" stroke-width="3.4" fill="none"/>',
    "карточки": '<path d="M-9 -4h12v10H-9zM-4 -4v-4H9V3H4" stroke="currentColor" stroke-width="2.4" fill="none"/>',
    "интерактив": '<path d="M-9 -4H9M-9 4H9" stroke="currentColor" stroke-width="2.4"/><circle cx="-2" cy="-4" r="3.6" fill="currentColor"/><circle cx="4" cy="4" r="3.6" fill="currentColor"/>',
    "текст": '<path d="M-9 -6H9M-9 0H9M-9 6H3" stroke="currentColor" stroke-width="2.6"/>'}
TRAIL = (.17, .30, .70, .83, .70, .30)   # где стоит шаг по ширине тропы


def plural(n, one, few, many):
    return many if 10 < n % 100 < 20 else one if n % 10 == 1 else few if 1 < n % 10 < 5 else many


def plate(y, k):
    return (f'<g class="pl p{k}"><path class="sd" d="M4 {y + 23}v8L48 {y + 54}v-8z"/><path class="sr" d="M92 {y + 23}v8L48 {y + 54}v-8z"/>'
            f'<path class="tp" d="M48 {y} 92 {y + 23} 48 {y + 46} 4 {y + 23}z"/></g>')


def render_path(nodes, parts, tasks, routing, title):
    out, at = [], 0
    for k, p in enumerate(parts):
        items = []
        for n in p["nodes"]:
            x = TRAIL[at % len(TRAIL)]
            at += 1
            fmt = (routing.get(n["id"]) or {}).get("format", "текст")
            icon = ICONS.get("видео" if fmt in ("шортс", "длинное видео") else fmt, ICONS["текст"])
            nt = len(tasks.get(n["id"], []))
            key = '<em class="key">ключевой шаг</em>' if n.get("threshold") else ""
            info = f'≈{minutes(n)} мин' + (f' · {nt} {plural(nt, "задание", "задания", "заданий")}' if nt else "")
            items.append(
                f'<li class="nd {"lft" if x < .5 else "rgt"}" style="--x:{x}" data-node="{e(n["id"])}">'
                f'<a href="#/step/{e(n["id"])}" aria-label="Шаг {at}. {e(novice(n))}"><span class="disc"><svg viewBox="0 0 96 88" aria-hidden="true">'
                f'{plate(28, 1)}{plate(14, 2)}{plate(0, 3)}<g class="ic" transform="translate(48 23)">{icon}</g>'
                f'<path class="ck" d="M36 23l9 8 16-17"/></svg><i class="br a"></i><i class="br b"></i><i class="br c"></i><i class="br d"></i></span>'
                f'<span class="cap"><b>{at}. {e(novice(n))}</b><small>{info}</small>{key}<small data-ok="{e(n["id"])}"></small></span></a></li>')
        mark = f' · {e(p["mark"])}' if p["mark"] else ""
        out.append(f'<section class="stratum t{k % 5}" data-part="{k}"><header class="unit"><div><span class="lab">Часть {k + 1}{mark}</span>'
                   f'<h3>{e(p["title"])}</h3></div><span class="cnt" data-cnt="{k}"></span><i class="ub"><i data-bar="{k}"></i></i></header>'
                   f'<ol class="trail">{"".join(items)}</ol></section>')
    return f"""
<section class="view" id="path">
  <div class="hero"><canvas id="iso" aria-hidden="true"></canvas><div class="in">
    <p class="lab">Путь по главе</p><h1>{e(title)}</h1>
    <div class="stat"><div><b id="st-steps">0/{len(nodes)}</b><span id="progtxt">шагов пройдено</span></div><div><b id="st-tasks">—</b><span>верно с первого раза</span></div><div><b id="st-cards">0/{len(nodes)}</b><span>карточек «знаю»</span></div></div>
    <progress id="prog" max="100" value="0" aria-label="Пройдено курса"></progress>
    <a class="cta" href="#/resume"><b><span id="ctatxt">Начать</span><small id="ctastep">{e(novice(nodes[0]))}</small></b><i>→</i></a>
    <p class="legend">Пластины шага снизу вверх: открыт, задания решены, пройден.</p></div></div>
  <div id="strata"><svg id="thread" aria-hidden="true"></svg>{"".join(out)}
    <div class="fin"><svg viewBox="0 0 96 88" aria-hidden="true">{plate(28, 1)}{plate(14, 2)}{plate(0, 3)}</svg><h3 id="finh">Забой</h3><p id="fintxt">Здесь закончится путь.</p></div></div>
</section>"""


def render_cards(nodes):
    cards = "".join(
        f'<div class="card" data-card="{e(n["id"])}"><span class="card-mark" aria-live="polite"></span><h3>{e(novice(n))}</h3>'
        f'<details><summary>Показать ответ</summary><p>{e(nodetext._f(n["layers"].get("main")))}</p></details>'
        f'<button type="button" data-know="{e(n["id"])}" aria-pressed="false">Знаю</button> '
        f'<button type="button" data-repeat="{e(n["id"])}" aria-pressed="false">Повторить</button></div>'
        for n in nodes)
    bar = ('<div class="cardbar"><span id="cardstat"></span> '
           '<button type="button" id="cardfilter" aria-pressed="false">Показать только «повторить»</button> '
           '<button type="button" id="cardreset">Сбросить отметки</button></div>')
    trainer = ('<div id="trainer" hidden><div class="deck"><button type="button" class="flip" id="flip" aria-live="polite">'
               '<span class="face f1"><span class="lab">Вопрос</span><b id="fq"></b><small>Нажмите, чтобы увидеть ответ</small></span>'
               '<span class="face f2"><span class="lab">Ответ</span><span id="fa"></span></span></button></div>'
               '<div class="tbtn"><button type="button" id="trep">Повторить</button><span id="tpos"></span><button type="button" id="tknow">Знаю</button></div></div>')
    return f'<section class="view" id="cards" hidden><p class="lab">Тренажёр</p><h2>Карточки</h2>{trainer}<h3 class="sub">Все карточки</h3>{bar}<div class="cgrid">{cards}</div></section>'


def render_notes(nodes, parts):
    out = []
    for k, p in enumerate(parts):
        rows = []
        for n in p["nodes"]:
            dm = (n.get("data_meaning") or {}).get("from_chapter")
            rows.append(f'<li><b>{e(novice(n))}.</b> {e(nodetext._f(n["layers"].get("main")))}'
                        f'{" <i>Для данных:</i> " + e(nodetext._f(dm)) if dm else ""}</li>')
        out.append(f'<h3 class="sub">Часть {k + 1}. {e(p["title"])}</h3><ul class="notes">{"".join(rows)}</ul>')
    return ('<section class="view" id="notes" hidden><p class="lab">Кратко</p><h2>Конспект</h2>'
            '<button onclick="window.print()">Печать / сохранить в PDF</button>' + "".join(out) + "</section>")


def render_map(nodes):
    titles = {n["id"]: novice(n) for n in nodes}
    rows = []
    for i, n in enumerate(nodes, 1):
        ids = [l["target"] for l in n.get("links", []) if l["type"] == "prerequisite" and l["target"] in titles]
        rows.append(f'<li data-map="{e(n["id"])}" data-pre="{e(" ".join(ids))}"><a href="#/step/{e(n["id"])}"><b>{i}. {e(novice(n))}</b></a>'
                    f'<span>опирается на: {e(", ".join(titles[t] for t in ids)) if ids else "—"}</span></li>')
    return ('<section class="view" id="map" hidden><p class="lab">Что на что опирается</p><h2>Карта связей</h2>'
            '<div class="mapbox"><svg id="arcs" aria-hidden="true"></svg><ul class="map">' + "".join(rows) + "</ul></div></section>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "data" / "current"))
    ap.add_argument("--out", default=str(ROOT / "out" / "course"))
    ap.add_argument("--title", default=None)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    layer, tasks, ill, errs = validate_layer.validate_dir(d)
    if layer is None or tasks is None or ill is None:
        print("Нет входных файлов или они не проходят схему:")
        for x in errs:
            print("  ! " + x)
        return 1
    routing = {}
    if (d / "routing.json").exists():
        routing = {r["node_id"]: r for r in validate_layer.load_json(d / "routing.json").get("routes", [])}
    nodes = sorted(layer["nodes"], key=lambda n: n["order"])
    glossary = {}
    gp = domain.path("glossary.json")
    if gp.exists():
        gl = validate_layer.load_json(gp)
        for t in gl if isinstance(gl, list) else gl.get("terms", []):
            if t.get("ru") and t.get("note"):
                glossary[t["ru"].lower()] = t["note"]
    by_step_t, by_step_i = {}, {}
    for t in tasks["tasks"]:
        by_step_t.setdefault(t["step_id"], []).append(t)
    lost = [i for i in ill["illustrations"] if not (d / i["file"]).exists()]
    for i in ill["illustrations"]:
        if i not in lost:
            by_step_i.setdefault(i["step_id"], []).append(i)
    if lost:
        warn(f"нет файлов на этом компьютере, в курс не вошли: {len(lost)} (например {lost[0]['file']}). "
             "Ролики собирает engine/video/make_video.py, анимации — engine/video/make_animations.py")
    rows = validate_layer.load_json(d / "coverage.json") if (d / "coverage.json").exists() else {}
    parts = chapter_parts(nodes, rows.get("rows", []) if isinstance(rows, dict) else rows)
    part_of = {n["id"]: k + 1 for k, p in enumerate(parts) for n in p["nodes"]}
    title = a.title or f"Демо-курс: {layer['chapter']}"
    steps = "".join(render_step(n, k + 1, len(nodes), by_step_t.get(n["id"], []), by_step_i.get(n["id"], []),
                               routing.get(n["id"]), glossary, part_of[n["id"]]) for k, n in enumerate(nodes))
    body = render_path(nodes, parts, by_step_t, routing, title) + steps + render_cards(nodes) + render_notes(nodes, parts) + render_map(nodes)
    misc = {m["id"]: m["text"] for m in domain.load("misconceptions.json")}
    tpl = (ROOT / "engine" / "template.html").read_text(encoding="utf-8")
    page = (tpl.replace("{{TITLE}}", e(title)).replace("{{BODY}}", body)
            .replace("{{ORDER}}", json.dumps([n["id"] for n in nodes]))
            .replace("{{MISC}}", json.dumps(misc, ensure_ascii=False).replace("</", "<\\/")))
    out = pathlib.Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    for i in ill["illustrations"]:
        src = d / i["file"]
        if src.exists():
            shutil.copyfile(src, out / "assets" / pathlib.Path(i["file"]).name)
            vtt = src.with_suffix(".vtt")  # субтитры ролика рядом с mp4
            if src.suffix.lower() == ".mp4" and vtt.exists():
                shutil.copyfile(vtt, out / "assets" / vtt.name)
    video_bytes = sum(f.stat().st_size for f in (out / "assets").glob("*.mp4"))
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) - video_bytes  # ТЗ: ≤30 МБ без видео
    if total > 30 * 1024 * 1024:
        warn(f"курс весит {total // 1048576} МБ > 30 МБ")
    print(f"Собрано: {out / 'index.html'} ({total // 1024} КБ), шагов {len(nodes)}, заданий {len(tasks['tasks'])}")
    problems = sorted(set(errs + WARN))
    for p in problems:
        print("  ! " + p)
    return 2 if (a.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
