"""Текст для уха и субтитры (часть Б). Читает словарь произношений и ударений из доменного пакета
(pronunciation.md и stress_dictionary.md пакета): движок не знает геологии, всё предметное в пакете.

prepare_for_speech(text) -> текст для синтеза: аббревиатуры по таблице чтения, числа словами, ударения знаком U+0301.
subtitles_srt(script)    -> SRT из сценария (оригинальный текст, без ударений).
Правила ТЗ: фраза ≤15–18 слов; числа и формулы словами; аббревиатура раскрыта при первом упоминании; 110–150 слов/мин."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
import sys as _sys_d  # noqa: E402
_sys_d.path.insert(0, str(ROOT / "engine"))
import domain  # noqa: E402
PRON, STRESS_MD = domain.path("pronunciation.md"), domain.path("stress_dictionary.md")
ACUTE = "́"


def _rows(section_header_start, src):
    lines = src.read_text(encoding="utf-8").splitlines()
    out, on = [], False
    for ln in lines:
        if ln.startswith("## "):
            on = ln.startswith("## " + section_header_start)
            continue
        if on and ln.startswith("|") and not set(ln.replace("|", "").strip()) <= set("- "):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if cells and cells[0] not in ("Пишется", "Слово"):
                out.append(cells)
    return out


def load_abbreviations():
    """{написание: (чтение, расшифровка)}"""
    d = {}
    for c in _rows("Обозначения", PRON):
        if len(c) >= 2 and c[0] and c[1]:
            # «Kп» в таблице латинская K; в текстах бывает кириллическая К
            for key in {x.strip() for x in c[0].split(",")}:
                d[key] = (c[1], c[2] if len(c) > 2 else "")
                if key.startswith("K"):
                    d["К" + key[1:]] = d[key]
    return d


def load_stress():
    """{слово_без_ударения: с_ударением}"""
    d = {}
    for c in _rows("Ударения", STRESS_MD):
        if len(c) >= 2 and ACUTE in c[1] or (len(c) >= 2 and c[1] and c[1] != c[0]):
            d[re.sub(r"\s*\(.*\)", "", c[0]).lower()] = c[1].replace("́", ACUTE)
    return d


ABBR, STRESS = load_abbreviations(), load_stress()


def _num_words(m):
    from num2words import num2words
    s = m.group(0).replace(",", ".")
    try:
        return num2words(float(s) if "." in s else int(s), lang="ru")
    except Exception:
        return m.group(0)


def prepare_for_speech(text):
    t = text
    # аббревиатуры: длинные ключи раньше коротких, только как отдельные слова
    for k in sorted(ABBR, key=len, reverse=True):
        if re.search(r"[А-Яа-яA-Za-zρκϰ]", k):
            t = re.sub(rf"(?<![А-Яа-яA-Za-z]){re.escape(k)}(?![А-Яа-яA-Za-z])", ABBR[k][0], t)
    t = re.sub(r"(?<![\w])\d+(?:[.,]\d+)?", _num_words, t)
    t = t.replace("%", " процентов").replace("−", " минус ")

    def acc(m):
        w = m.group(0)
        s = STRESS.get(w.lower())
        if not s:
            return w
        return s[0].upper() + s[1:] if w[0].isupper() else s
    return re.sub(r"[А-Яа-яЁё]+", acc, t)


def words(text):
    return len(re.findall(r"[А-Яа-яЁёA-Za-z0-9]+", text))


def wpm(script):
    """Слов в минуту по всему сценарию (по временным слотам фраз)."""
    total = sum(words(p["text"]) for p in script)
    secs = sum(max(0.001, p["t_end"] - p["t_start"]) for p in script)
    return 60 * total / secs if secs else 0


def first_mention_issues(script):
    """Аббревиатура должна быть раскрыта при первом упоминании: расшифровка в той же или более ранней фразе."""
    issues, seen_text = [], ""
    for p in script:
        seen_text += " " + p["text"].lower()
        for k, (_, expl) in ABBR.items():
            if expl and re.search(rf"(?<![А-Яа-яA-Za-z]){re.escape(k)}(?![А-Яа-яA-Za-z])", p["text"]) \
                    and k not in seen_text.replace(p["text"].lower(), "", 1) and expl.lower() not in seen_text:
                issues.append(f"«{k}» без расшифровки при первом упоминании (ожидается: {expl})")
    return sorted(set(issues))


def _ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def subtitles_srt(script):
    out = []
    for i, p in enumerate(script, 1):
        text = p.get("on_screen") or p["text"]
        out.append(f"{i}\n{_ts(p['t_start'])} --> {_ts(p['t_end'])}\n{text}\n")
    return "\n".join(out)
