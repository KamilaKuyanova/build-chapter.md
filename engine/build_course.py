#!/usr/bin/env python3
"""Сборщик демо-курса (часть Б). Входы в ОФИЦИАЛЬНЫХ форматах: layer.json, tasks.json, illustrations.json [, routing.json].
Выход: out/course/index.html (один файл, офлайн, без сервера) + assets/.
Запуск: python engine/build_course.py [--dir data/current] [--out out/course] [--strict]
--strict: ненулевой код выхода при любых нарушениях правил ТЗ (проверка engine/validate_layer.py)."""
import argparse
import html
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import nodetext  # noqa: E402
import validate_layer  # noqa: E402

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
    return f'<p class="{cls}">{e(f["text"])}{hyp} {who(f)} {page_tag(node, f)}</p>'


def fld_paras(node, f, title=""):
    """Слой поля по абзацам, у каждого своя страница; без разбивки — одним абзацем."""
    if not isinstance(f, dict):
        return ""
    body = "".join(fld(node, p) for p in f.get("paras") or [f])
    return f"<h4>{e(title)}</h4>{body}" if body else ""


def render_formulas(node):
    out = []
    for f in node.get("formulas", []):
        rows = "".join(f'<li><code>{e(v["symbol"])}</code> — {e(v["meaning"])}'
                       f'{", " + e(v["unit"]) if v.get("unit") else ""}</li>' for v in f["variables"])
        out.append(f'<div class="formula"><code>{e(f["latex"])}</code><p>{e(f["meaning"])} {who(f)} '
                   f'<span class="src">стр. {e(f["page_pdf"])}</span></p><ul>{rows}</ul></div>')
    return "".join(out)


def render_tables(node):
    out = []
    for t in node.get("tables", []):
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in t["markdown"].splitlines()
                if r.strip().startswith("|")]
        rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
        body = "".join("<tr>" + "".join(f"<{'td' if i else 'th'}>{e(c)}</{'td' if i else 'th'}>" for c in r) + "</tr>"
                       for i, r in enumerate(rows))
        fixes = "".join(f"<li>{e(x)}</li>" for x in t.get("ocr_fixes", []))
        out.append(f'<h4>{e(t["title"])} <span class="src">стр. {e(t["page_pdf"])}</span></h4>'
                   f'<div style="overflow-x:auto"><table>{body}</table></div>'
                   f'{"<p>Исправления распознавания:</p><ul>" + fixes + "</ul>" if fixes else ""}')
    return "".join(out)


def novice(node):
    return node.get("title_novice") or node["title"]


def block(title, body):
    return f"<section class='blk'><h3>{e(title)}</h3>{body}</section>" if body.strip() else ""


def minutes(node):
    return max(1, round(len(nodetext.node_text(node).split()) / 120))


def render_claims(node):
    items = []
    for c in node.get("claims", []):
        who_ = "модель" if c["source_kind"] == "figure_description_model" else "автор"
        mine = ' <span class="tag">пересказ модели</span>' if c.get("by_model") else ""
        pr = f" (печ. {c['page_print']})" if c.get("page_print") else ""
        items.append(f'<li><b>{e(KINDS.get(c["kind"], c["kind"]))}.</b> {e(c["text"])}{mine}'
                     f'<blockquote>«{e(c["quote"])}» — {who_}, <span class="src">стр. {c["page_pdf"]}{e(pr)}</span></blockquote></li>')
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
    return "".join(f'<p><b>Задача {e(t["number"])}.</b> {e(t["text"])}'
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
        if fname.lower().endswith(".mp4"):
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


def render_step(node, i, total, tasks, ills, route, glossary):
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
    meta = f"Шаг {i} из {total} · ≈{minutes(node)} мин"
    if route:
        meta += f" · формат: {e(FMT_LABEL.get(route['format'], route['format']))}"
    ess = ly.get("main")
    nav = (f'<nav class="stepnav"><a href="#/step/{e(node["id"])}-prev">← Назад</a> '
           f'<button class="done" data-done="{e(node["id"])}">Отметить пройденным</button> '
           f'<a href="#/step/{e(node["id"])}-next">Дальше →</a></nav>')
    return f"""
<article class="view step" id="step-{e(node['id'])}" data-id="{e(node['id'])}" hidden>
  <p class="meta">{meta}</p>
  <h2>{e(novice(node))}</h2>
  <p class="meta">{e(node['title'])}. {e(nodetext._f(ly.get('topic')))}</p>
  {block('Почему этот шаг здесь', fld(node, node.get('why_here')))}
  {block('Суть', fld(node, ess, 'essence'))}
  {block('Как это работает', how)}
  {block('Глубже', deeper)}
  {block('Разбор примеров из главы', render_examples(node))}
  {block('Формулы', render_formulas(node))}
  {block('Таблицы книги', render_tables(node))}
  {block('Частая ошибка', e(mc['text']) if mc else '')}
  {block('Что это значит для данных', render_data_meaning(node))}
  {block('Решение на данных', render_decision(node))}
  {block('Аналогия', ana_html)}
  {block('Как это делается сейчас', now)}
  {block('Линза неэффективности', lens_html)}
  {block('Новые понятия', render_terms(node, glossary))}
  {block('Источник', render_claims(node))}
  {block('Задачи из книги', render_book_tasks(node))}
  {block('Иллюстрации', render_illustrations(node, ills))}
  {block('Проверь себя', render_quizzes(tasks))}
  {nav}
</article>"""


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
    return f'<section class="view" id="cards" hidden><h2>Карточки</h2>{bar}{cards}</section>'


def render_notes(nodes):
    rows = []
    for n in nodes:
        dm = (n.get("data_meaning") or {}).get("from_chapter")
        rows.append(f'<li><b>{e(novice(n))}.</b> {e(nodetext._f(n["layers"].get("main")))}'
                    f'{" <i>Для данных:</i> " + e(nodetext._f(dm)) if dm else ""}</li>')
    return ('<section class="view" id="notes" hidden><h2>Конспект</h2>'
            '<button onclick="window.print()">Печать / сохранить в PDF</button><ul>' + "".join(rows) + "</ul></section>")


def render_map(nodes):
    titles = {n["id"]: novice(n) for n in nodes}
    rows = []
    for n in nodes:
        pre = [titles.get(l["target"], l["target"]) for l in n.get("links", []) if l["type"] == "prerequisite"]
        rows.append(f'<li><b>{e(novice(n))}</b> ← опирается на: {e(", ".join(pre)) if pre else "—"}</li>')
    return '<section class="view" id="map" hidden><h2>Карта связей</h2><ul>' + "".join(rows) + "</ul></section>"


def render_path(nodes):
    items = "".join(
        f'<li><a href="#/step/{e(n["id"])}">{e(novice(n))}</a> <span class="meta">≈{minutes(n)} мин</span> '
        f'<span data-ok="{e(n["id"])}"></span></li>' for n in nodes)
    return ('<section class="view" id="path"><h2>Путь по главе</h2><p><progress id="prog" max="100" value="0"></progress> '
            '<span id="progtxt"></span> <a href="#/resume">Продолжить с места остановки</a></p>'
            f'<ol>{items}</ol></section>')


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
    gp = ROOT / "domain_pack" / "glossary.json"
    if gp.exists():
        for t in validate_layer.load_json(gp).get("terms", []):
            if t.get("ru") and t.get("note"):
                glossary[t["ru"].lower()] = t["note"]
    by_step_t, by_step_i = {}, {}
    for t in tasks["tasks"]:
        by_step_t.setdefault(t["step_id"], []).append(t)
    for i in ill["illustrations"]:
        by_step_i.setdefault(i["step_id"], []).append(i)
    steps = "".join(render_step(n, k + 1, len(nodes), by_step_t.get(n["id"], []), by_step_i.get(n["id"], []),
                               routing.get(n["id"]), glossary) for k, n in enumerate(nodes))
    body = render_path(nodes) + steps + render_cards(nodes) + render_notes(nodes) + render_map(nodes)
    misc = {m["id"]: m["text"] for m in validate_layer.load_json(ROOT / "domain_pack" / "misconceptions.json")}
    tpl = (ROOT / "engine" / "template.html").read_text(encoding="utf-8")
    title = a.title or f"Демо-курс: {layer['chapter']}"
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
        else:
            warn(f"файл иллюстрации не найден: {src}")
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
