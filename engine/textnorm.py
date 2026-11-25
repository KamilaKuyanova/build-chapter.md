"""Нормализация текста для сравнения цитат и чисел. Геологии здесь нет."""
import re

_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_SUP_RUN = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+")
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_HYPHEN_BREAK = re.compile(r"(?<=[^\W\d_])-\s*\n\s*(?=[a-zа-яё])")
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def join_hyphens(text):
    """«обрат-\\nных» -> «обратных»."""
    return _HYPHEN_BREAK.sub("", text)


def unify(text):
    text = _SUP_RUN.sub(lambda m: "^" + m.group(0).translate(_SUP), text)
    text = text.translate(_SUB).replace("\u00ad", "").replace("\u00a0", " ")
    text = re.sub(r"[‐‑‒–—−]", "-", text)
    return re.sub(r"[«»„“”]", '"', text)


def norm_quote(text):
    """Вид, в котором цитата ищется на странице: без разметки, регистра и различий в тире."""
    text = unify(join_hyphens(text))
    text = re.sub(r"\\[()\[\]]|\$+|\*+|`|</?(?:sub|sup|br|b|i|u|em|strong|span|div|p)\b[^<>]*>", "", text)
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+([.,;:!?)\]])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def numbers(text):
    """Множество чисел в тексте; запятая и точка в дроби равнозначны."""
    text = re.sub(r"(?<=[^\W\d_])[₀-₉]+", " ", text)  # индекс в «F₀» — не число
    text = re.sub(r"\\[,;:! ]", " ", unify(text)).replace("{,}", ",")
    found = set()
    for raw in _NUM.findall(text):
        whole, _, frac = raw.replace(",", ".").partition(".")
        whole = whole.lstrip("0") or "0"
        frac = frac.rstrip("0")
        found.add(f"{whole}.{frac}" if frac else whole)
    return found


def words(text):
    return re.findall(r"[^\W\d_]+", text.casefold().replace("ё", "е"))
