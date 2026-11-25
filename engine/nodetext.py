"""Единый «текст шага» узла (официальная схема слоя). Нужен, чтобы одним и тем же кодом проверять правило ТЗ
«ответ на каждое задание есть в тексте шага» и в генераторе заданий, и в сборщике/валидаторе."""
import re


def _f(x):
    """Текст поля {text, by_model, ...} или строки/None."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return x.get("text", "") or ""
    return ""


def node_text(node):
    p = [node.get("title", ""), _f(node.get("why_here"))]
    ly = node.get("layers") or {}
    for k in ("topic", "main", "mechanism", "practice", "nuances"):
        p.append(_f(ly.get(k)))
    p += [_f(x) for x in ly.get("deeper", [])]
    for c in node.get("claims", []):
        p += [c.get("text", ""), c.get("quote", "")]
    dm = node.get("data_meaning") or {}
    p += [_f(dm.get("from_chapter")), _f(dm.get("breaks"))] + [_f(x) for x in dm.get("hypotheses", [])]
    ana = node.get("it_analogy") or {}
    p += [ana.get("text", ""), ana.get("breaks_where", "")]
    mc = node.get("misconception") or {}
    p.append(mc.get("text", "") if isinstance(mc, dict) else "")
    p.append(_f(node.get("now_practice")))
    dd = node.get("decision_on_data") or {}
    p += [" ".join(dd.get("features", [])), dd.get("rule", ""), dd.get("conclusion", ""), dd.get("counterexample", "")]
    for ex in node.get("worked_examples", []):
        p += [ex.get("condition", ""), " ".join(ex.get("steps", [])), ex.get("result", "")]
    for bt in node.get("book_tasks", []):
        p.append(bt.get("text", ""))
    p += node.get("terms_introduced", [])
    return "\n".join(x for x in p if x)


def norm(s):
    """Нормализация для поиска подстроки: регистр, пробелы, неразрывные пробелы, минус."""
    s = (s or "").replace(" ", " ").replace("−", "-").lower()
    return re.sub(r"\s+", " ", s).strip()


def in_text(fragment, text):
    return bool(fragment) and norm(fragment) in norm(text)
