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


def page_label(node, claim_ids, own_pages=None):
    """«стр. N» для абзаца: свои страницы абзаца или по ссылкам на утверждения. Нет страницы = нарушение ТЗ."""
    if own_pages:
        return f'<span class="src">стр. {e(", ".join(map(str, sorted(set(own_pages)))))}</span>'
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
    parts = f if isinstance(f, list) else [f]
    return "".join(f'<p>{e(p.get("text"))} {page_label(node, p.get("claims"), p.get("pages"))}</p>' for p in parts)


def render_how(node):
    heads = (("mechanism", "Механизм"), ("practice", "Как делает специалист"),
             ("nuances", "Нюансы"), ("deeper", "Глубже"))
    parts = [(title, para(node, field)) for field, title in heads]
    return "".join(f"<h4>{title}</h4>{body}" for title, body in parts if body)


def render_terms(node):
    items = "".join(f'<dt><b>{e(t.get("term"))}</b></dt><dd>{e(t.get("definition"))}</dd>' for t in node.get("terms", []))
    return f"<dl>{items}</dl>" if items else ""


def render_formulas(node):
    out = []
    for f in node.get("formulas", []):
        rows = "".join(f'<li><code>{e(v.get("symbol"))}</code> — {e(v.get("meaning"))}'
                       f'{", " + e(v["unit"]) if v.get("unit") else ""}</li>' for v in f.get("variables", []))
        out.append(f'<div class="formula"><code>{e(f.get("latex"))}</code>'
                   f'<p>{e(f.get("meaning"))} <span class="src">стр. {e(f.get("page"))}</span></p><ul>{rows}</ul></div>')
    return "".join(out)


def render_tables(node):
    out = []
    for t in node.get("tables", []):
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in t.get("markdown", "").splitlines()
                if r.strip().startswith("|")]
        rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
        body = "".join("<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{e(c)}</{'th' if i == 0 else 'td'}>"
                                         for c in r) + "</tr>" for i, r in enumerate(rows))
        fixes = "".join(f"<li>{e(x)}</li>" for x in t.get("ocr_fixes", []))
        out.append(f'<h4>{e(t.get("title"))} <span class="src">стр. {e(t.get("page"))}</span></h4>'
                   f'<div style="overflow-x:auto"><table>{body}</table></div>'
                   f'{"<p>Исправления распознавания:</p><ul>" + fixes + "</ul>" if fixes else ""}')
    return "".join(out)


def render_data_meaning(node):
    if not node.get("data_meaning"):
        return ""
    hyp = "".join(f"<p><b>Гипотеза, не из книги:</b> {e(h)}</p>" for h in node.get("hypotheses", []))
    return f'<p>{e(node["data_meaning"])}</p>{hyp}'


def words(node):
    txt = json.dumps(node.get("core", {}), ensure_ascii=False)
    return len(txt.split())


def step_minutes(node):
    return max(1, round(words(node) / 120))


ASSETS = {}  # имя файла в out/assets -> исходный путь
NODES_DIR = None


def render_illustrations(node):
    out = []
    for il in node.get("illustrations", []):
        nid = node.get("id")
        if not il.get("alt"):
            warn(f"[{nid}] иллюстрация без alt-текста")
        if il.get("class") not in ("A", "B", "C", "D"):
            warn(f"[{nid}] у иллюстрации не указан класс кадра A–D")
        label = il.get("label", "")
        if il.get("generated") and "иллюстрация ИИ" not in label:
            warn(f"[{nid}] сгенерированная иллюстрация без метки «иллюстрация ИИ»")
        if il.get("class") in ("A", "B") and il.get("generated"):
            warn(f"[{nid}] класс {il.get('class')}: генерация запрещена (только код из данных/модели)")
        if il.get("class") in ("A", "B") and not label:
            warn(f"[{nid}] у кадра класса {il.get('class')} нет метки происхождения (реальные данные / симуляция / схема)")
        if il.get("redrawn_from_book") and "перерисовано по рис." not in il.get("caption", ""):
            warn(f"[{nid}] перерисованный рисунок книги без подписи «перерисовано по рис. N, стр. M»")
        fname = pathlib.Path(il.get("file", "")).name
        ASSETS[fname] = pathlib.Path(NODES_DIR) / il.get("file", "")
        out.append(
            f'<figure><img src="assets/{e(fname)}" alt="{e(il.get("alt"))}" loading="lazy">'
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
            f'{"<span class=tag>(пересказ модели)</span> " if c.get("by_model") else ""}'
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


def render_data_solution(node):
    ds = node.get("data_solution")
    if not ds:
        return ""
    feats = "".join(f"<li>{e(f)}</li>" for f in ds.get("features", []))
    return (f'<p>{e(ds.get("task"))}</p><div class="kv"><b>Признаки</b><ul>{feats}</ul>'
            f'<b>Правило</b><span>{e(ds.get("rule"))}</span><b>Вывод</b><span>{e(ds.get("conclusion"))}</span>'
            f'<b>Где ломается</b><span>{e(ds.get("breaks"))}</span></div>')


EX_TYPES = {"single", "multi", "order", "fill", "calc"}


def check_exercise(node, ex):
    nid, xid, t = node.get("id"), ex.get("id"), ex.get("type")
    if t not in EX_TYPES:
        warn(f"[{nid}] задание {xid}: неизвестный тип {t}")
        return
    if not ex.get("explanation"):
        warn(f"[{nid}] задание {xid}: нет пояснения к верному ответу")
    opts = ex.get("options", [])
    if t == "single" and not (isinstance(ex.get("answer"), int) and 0 <= ex["answer"] < len(opts)):
        warn(f"[{nid}] задание {xid}: ключ single вне диапазона")
    if t == "multi" and not (isinstance(ex.get("answer"), list) and ex["answer"]
                             and all(isinstance(i, int) and 0 <= i < len(opts) for i in ex["answer"])):
        warn(f"[{nid}] задание {xid}: ключ multi неверен")
    if t == "order" and len(opts) < 2:
        warn(f"[{nid}] задание {xid}: для порядка нужно ≥2 элементов")
    if t == "fill" and not (isinstance(ex.get("answer"), list) and ex["answer"]):
        warn(f"[{nid}] задание {xid}: у fill answer — непустой список допустимых ответов")
    if t == "calc" and not isinstance(ex.get("answer"), (int, float)):
        warn(f"[{nid}] задание {xid}: у calc answer — число")


def render_exercises(node):
    out = []
    claims = claim_index(node)
    for ex in node.get("exercises", []):
        check_exercise(node, ex)
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
    how = render_how(node)
    stub = '<p class="bad">ЗАГЛУШКА: узел не собран из книги.</p>' if node.get("_stub") else ""
    es = core.get("essence")
    ess_html = ""
    if es:
        t = es if isinstance(es, str) else es.get("text")
        cl = [] if isinstance(es, str) else es.get("claims")
        pg = None if isinstance(es, str) else es.get("pages")
        ess_html = f'<p class="essence">{e(t)} {page_label(node, cl, pg)}</p>'
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
  {block('Новые понятия', render_terms(node))}
  {block('Цифры и условия', '<p>' + e(node.get('conditions')) + '</p>' if node.get('conditions') else '')}
  {block('Формулы', render_formulas(node))}
  {block('Таблицы книги', render_tables(node))}
  {block('Частая ошибка', '<p>' + e(node.get('misconception')) + '</p>' if node.get('misconception') else '')}
  {block('Что это значит для данных', render_data_meaning(node))}
  {block('Аналогия', ana)}
  {block('Как это делается сейчас', '<p>' + e(node.get('current_practice')) + '</p>' if node.get('current_practice') else '')}
  {block('Источник', render_claims(node))}
  {block('Задачи из книги', render_problems(node))}
  {block('Решение на данных', render_data_solution(node))}
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
    global NODES_DIR
    NODES_DIR = a.nodes
    nodes = load_nodes(a.nodes)
    if not nodes:
        print("Нет узлов в", a.nodes)
        return 1
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import validate_nodes  # схема узла: форма и ссылки
    for msg in validate_nodes.validate_dir(a.nodes)[1]:
        warn("схема: " + msg)
    validate(nodes)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(build(nodes, a.title), encoding="utf-8")
    if ASSETS:
        (out / "assets").mkdir(exist_ok=True)
        for name, src in ASSETS.items():
            if src.exists():
                (out / "assets" / name).write_bytes(src.read_bytes())
            else:
                warn(f"файл иллюстрации не найден: {src}")
    # курс без видео ≤ 30 МБ на главу
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    if total > 30 * 1024 * 1024:
        warn(f"курс весит {total // 1048576} МБ > 30 МБ")
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
