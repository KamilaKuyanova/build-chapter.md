#!/usr/bin/env python3
"""Сборщик демо-курса: data/nodes/*.json -> out/course/index.html (один файл, офлайн, без сервера).

Курс собирается ТОЛЬКО из учебного слоя (узлы). Вёрстка вручную не допускается.
Запуск:  python engine/build_course.py [--strict] [--nodes data/nodes] [--out out/course]
--strict: сборка падает, если есть нарушения правил ТЗ (нет страницы, <15 заданий и т.п.).
"""
import argparse
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WARN = []


def warn(msg):
    WARN.append(msg)


def e(s):
    return html.escape("" if s is None else str(s), quote=True)


def load_nodes(nodes_dir):
    nodes = []
    for p in sorted(pathlib.Path(nodes_dir).glob("*.json")):
        n = json.loads(p.read_text(encoding="utf-8"))
        n["_file"] = p.name
        nodes.append(n)
    nodes.sort(key=lambda n: (n.get("order", 10**6), n.get("id", "")))
    return nodes


def claim_index(node):
    return {c["id"]: c for c in node.get("claims", []) if "id" in c}


def page_label(node, claim_ids):
    """«стр. N» для абзаца по ссылкам на утверждения. Нет страницы = нарушение ТЗ."""
    idx = claim_index(node)
    pages = []
    for cid in claim_ids or []:
        c = idx.get(cid)
        if c and c.get("page") is not None:
            pages.append(str(c["page"]))
    if not pages:
        warn(f"[{node.get('id')}] абзац без страницы источника (claims={claim_ids})")
        return '<span class="src bad">стр. ? (нет источника)</span>'
    return f'<span class="src">стр. {e(", ".join(sorted(set(pages), key=str)))}</span>'


def para(node, field):
    f = node.get("core", {}).get(field)
    if not f:
        return ""
    if isinstance(f, str):
        f = {"text": f, "claims": []}
    return f'<p>{e(f.get("text"))} {page_label(node, f.get("claims"))}</p>'


def words(node):
    txt = json.dumps(node.get("core", {}), ensure_ascii=False)
    return len(txt.split())


def step_minutes(node):
    return max(1, round(words(node) / 120))


def render_illustrations(node):
    out = []
    for il in node.get("illustrations", []):
        if not il.get("alt"):
            warn(f"[{node.get('id')}] иллюстрация без alt-текста")
        label = il.get("label", "")
        out.append(
            f'<figure><img src="{e(il.get("file"))}" alt="{e(il.get("alt"))}" loading="lazy">'
            f'<figcaption>{e(il.get("caption"))} <span class="tag">класс {e(il.get("class"))}'
            f'{" · " + e(label) if label else ""}</span></figcaption></figure>'
        )
    if not node.get("illustrations"):
        warn(f"[{node.get('id')}] нет иллюстраций (нужна минимум 1 на шаг)")
    return "".join(out)


def render_claims(node):
    items = []
    for c in node.get("claims", []):
        if not c.get("quote") or c.get("page") is None:
            warn(f"[{node.get('id')}] утверждение {c.get('id')} без цитаты или страницы")
        who = "автор" if c.get("origin") == "author" else "модель"
        kinds = {"observation": "наблюдение", "conclusion": "вывод", "assumption": "допущение"}
        items.append(
            f'<li><b>{e(kinds.get(c.get("kind"), c.get("kind")))}.</b> {e(c.get("text"))} '
            f'<blockquote>«{e(c.get("quote"))}» — {who}, '
            f'<span class="src">стр. {e(c.get("page") if c.get("page") is not None else "?")}</span></blockquote></li>'
        )
    return "<ul class='claims'>" + "".join(items) + "</ul>" if items else ""


def block(title, body):
    return f"<section class='blk'><h3>{e(title)}</h3>{body}</section>" if body else ""


def render_examples(node):
    out = []
    for ex in node.get("worked_examples", []):
        steps = "".join(f"<li>{e(s)}</li>" for s in ex.get("steps", []))
        out.append(
            f'<div class="ex"><p><b>Условие.</b> {e(ex.get("condition"))}</p><ol>{steps}</ol>'
            f'<p><b>Итог.</b> {e(ex.get("result"))} <span class="src">стр. {e(ex.get("page", "?"))}</span></p></div>'
        )
    return "".join(out)


def render_problems(node):
    return "".join(
        f'<p><b>Задача {e(p.get("number"))}.</b> {e(p.get("text"))}'
        f'{" Рисунок: " + e(p.get("figure")) if p.get("figure") else ""} '
        f'<span class="src">стр. {e(p.get("page", "?"))}</span></p>'
        for p in node.get("book_problems", [])
    )


def render_exercises(node):
    out = []
    claims = claim_index(node)
    for ex in node.get("exercises", []):
        if ex.get("claim_id") not in claims:
            warn(f"[{node.get('id')}] задание {ex.get('id')} без ссылки на утверждение узла")
        data = json.dumps(ex, ensure_ascii=False).replace("</", "<\\/")
        out.append(f'<div class="quiz" data-ex=\'{e(data)}\'></div>')
    return "".join(out)


def render_step(node, i, total):
    it = node.get("it_analogy") or {}
    ana = ""
    if it.get("analogy"):
        ana = (f'<p>{e(it["analogy"])}</p><p><b>Где аналогия не работает:</b> {e(it.get("breaks_where"))}</p>')
        if not it.get("breaks_where"):
            warn(f"[{node.get('id')}] у аналогии не названа граница")
    core = node.get("core", {})
    how = "".join(para(node, f) for f in ("mechanism", "practice", "nuances"))
    dm = node.get("data_meaning")
    stub = '<p class="bad">ЗАГЛУШКА: узел не собран из книги.</p>' if node.get("_stub") else ""
    es = core.get("essence")
    ess_html = ""
    if es:
        t = es if isinstance(es, str) else es.get("text")
        cl = [] if isinstance(es, str) else es.get("claims")
        ess_html = f'<p class="essence">{e(t)} {page_label(node, cl)}</p>'
    nav = (
        f'<nav class="stepnav"><a href="#/step/{e(node["id"])}-prev" data-nav="prev">← Назад</a> '
        f'<button class="done" data-done="{e(node["id"])}">Отметить пройденным</button> '
        f'<a href="#/step/{e(node["id"])}-next" data-nav="next">Дальше →</a></nav>'
    )
    return f"""
<article class="view step" id="step-{e(node['id'])}" data-id="{e(node['id'])}" hidden>
  <p class="meta">Шаг {i} из {total} · ≈{step_minutes(node)} мин · {e(node.get('book_title'))}</p>
  <h2>{e(node.get('title'))}</h2>
  {stub}
  {block('Суть', ess_html)}
  {block('Как это работает', how)}
  {block('Разбор примеров из главы', render_examples(node))}
  {block('Цифры и условия', '<p>' + e(node.get('conditions')) + '</p>' if node.get('conditions') else '')}
  {block('Частая ошибка', '<p>' + e(node.get('misconception')) + '</p>' if node.get('misconception') else '')}
  {block('Что это значит для данных', '<p>' + e(dm) + '</p>' if dm else '')}
  {block('Аналогия', ana)}
  {block('Как это делается сейчас', '<p>' + e(node.get('current_practice')) + '</p>' if node.get('current_practice') else '')}
  {block('Источник', render_claims(node))}
  {block('Задачи из книги', render_problems(node))}
  {block('Иллюстрации', render_illustrations(node))}
  {block('Проверь себя', render_exercises(node))}
  {nav}
</article>"""


def render_cards(nodes):
    cards = []
    for n in nodes:
        es = n.get("core", {}).get("essence")
        back = es if isinstance(es, str) else (es or {}).get("text", "")
        cards.append(
            f'<div class="card" data-id="{e(n["id"])}"><h3>{e(n.get("title"))}</h3>'
            f'<details><summary>Показать ответ</summary><p>{e(back)}</p></details>'
            f'<button data-know="{e(n["id"])}">Знаю</button> <button data-repeat="{e(n["id"])}">Повторить</button></div>'
        )
    return '<section class="view" id="cards" hidden><h2>Карточки</h2>' + "".join(cards) + "</section>"


def render_notes(nodes):
    rows = []
    for n in nodes:
        es = n.get("core", {}).get("essence")
        t = es if isinstance(es, str) else (es or {}).get("text", "")
        rows.append(f'<li><b>{e(n.get("title"))}.</b> {e(t)}'
                    f'{" <i>Для данных:</i> " + e(n.get("data_meaning")) if n.get("data_meaning") else ""}</li>')
    return ('<section class="view" id="notes" hidden><h2>Конспект</h2>'
            '<button onclick="window.print()">Печать / сохранить в PDF</button><ul>' + "".join(rows) + "</ul></section>")


def render_map(nodes):
    titles = {n["id"]: n.get("title") for n in nodes}
    rows = []
    for n in nodes:
        pre = [titles.get(l["to"], l["to"]) for l in n.get("links", []) if l.get("type") == "prerequisite"]
        rows.append(f'<li><b>{e(n.get("title"))}</b> ← опирается на: {e(", ".join(pre)) if pre else "—"}</li>')
    return '<section class="view" id="map" hidden><h2>Карта связей</h2><ul>' + "".join(rows) + "</ul></section>"


def render_path(nodes):
    items = "".join(
        f'<li><a href="#/step/{e(n["id"])}">{e(n.get("title"))}</a> <span class="meta">≈{step_minutes(n)} мин</span> '
        f'<span class="ok" data-ok="{e(n["id"])}"></span></li>' for n in nodes)
    return ('<section class="view" id="path"><h2>Путь по главе</h2><p><progress id="prog" max="100" value="0"></progress> '
            '<span id="progtxt"></span> <a href="#/resume" id="resume">Продолжить с места остановки</a></p>'
            f'<ol>{items}</ol></section>')


def validate(nodes):
    total_ex = sum(len(n.get("exercises", [])) for n in nodes)
    types = {x.get("type") for n in nodes for x in n.get("exercises", [])}
    if total_ex < 15:
        warn(f"заданий {total_ex} < 15 на главу")
    if len(types) < 4:
        warn(f"типов заданий {len(types)} < 4 (есть: {sorted(t for t in types if t)})")
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        warn("повторяющиеся id узлов")
    for n in nodes:
        for l in n.get("links", []):
            if l.get("to") not in ids:
                warn(f"[{n.get('id')}] связь на несуществующий узел {l.get('to')}")
    if not any(n.get("data_step") for n in nodes):
        warn("нет шага «решение на данных» (data_step: true)")


def build(nodes, chapter_title):
    tpl = (ROOT / "engine" / "template.html").read_text(encoding="utf-8")
    steps = "".join(render_step(n, i + 1, len(nodes)) for i, n in enumerate(nodes))
    body = render_path(nodes) + steps + render_cards(nodes) + render_notes(nodes) + render_map(nodes)
    order = json.dumps([n["id"] for n in nodes])
    return (tpl.replace("{{TITLE}}", e(chapter_title)).replace("{{BODY}}", body).replace("{{ORDER}}", order))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default=str(ROOT / "data" / "nodes"))
    ap.add_argument("--out", default=str(ROOT / "out" / "course"))
    ap.add_argument("--title", default="Демо-курс по главе")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    nodes = load_nodes(a.nodes)
    if not nodes:
        print("Нет узлов в", a.nodes)
        return 1
    validate(nodes)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(build(nodes, a.title), encoding="utf-8")
    size = (out / "index.html").stat().st_size
    print(f"Собрано: {out / 'index.html'} ({size // 1024} КБ), узлов: {len(nodes)}")
    for w in sorted(set(WARN)):
        print("  ! " + w)
    if a.strict and WARN:
        print(f"STRICT: {len(set(WARN))} нарушений")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
