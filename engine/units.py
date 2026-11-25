"""Нарезка md-главы на единицы: абзац, формула, таблица, рисунок, пример, задача.

Единица — атом покрытия. Описания рисунков в md написаны нейросетью (origin=figure_ai),
поэтому цитировать их как автора нельзя: проверка цитат их не видит.
"""
import re

from .textnorm import words

PAGE = re.compile(r"^<!-- page (\d+) -->\s*$")
FENCE = re.compile(r"^-{3,}\s*$")
FIG_AI = re.compile(r"^━━━")
HEADING = re.compile(r"^#{1,6}\s+(.*)$")
CAPTION = re.compile(r"^(?:#+\s*)?[*_]*(?:Рис|РИС|Fig|FIG|Figure|FIGURE)[.\s]*(\d+(?:\.\d+)*)")
TAB_CAPTION = re.compile(r"^[*_]*(?:Таблица|ТАБЛИЦА|Table|TABLE)\s+(\d+(?:\.\d+)*)")
EXAMPLE = re.compile(r"^[*_]*(?:Пример|ПРИМЕР|Example|EXAMPLE)\s+(\d+(?:\.\d+)*)")
TASK_HEAD = re.compile(
    r"^(?:#+\s*)?[*_]*(?:Задач[аи]|ЗАДАЧ[АИ]|Упражнения|Problems?|Exercises?)[*_.:]*\s*$")
TASK = re.compile(r"^(\d{1,3})\.\s+\S")
LIST = re.compile(r"^\s*(?:[-•*]\s*|\d{1,2}[.)]\s+)\S")


def slice_book(text, spec):
    """Строки главы как [(страница, строка)] по частям из chapters.json (страницы PDF)."""
    pages, page = [], None
    for line in text.splitlines():
        m = PAGE.match(line)
        if m:
            page = int(m.group(1))
        elif page is not None and not line.startswith("<!--"):
            pages.append((page, line))
    if not spec.get("parts"):  # готовый фрагмент: берём весь файл
        return pages
    out = []
    for part in spec["parts"]:
        first, last = part["pages"]
        chunk = [x for x in pages if first <= x[0] <= last]
        if not chunk:
            raise ValueError(f"{spec['id']}: на страницах {first}-{last} нет текста")
        for name in ("start", "stop"):
            if not part.get(name):
                continue
            rx = re.compile(part[name])
            skip = 1 if name == "stop" else 0
            hits = [i for i, (_, l) in enumerate(chunk) if i >= skip and rx.search(l)]
            if not hits:
                raise ValueError(f"{spec['id']}: граница {name} не найдена: {part[name]}")
            chunk = chunk[hits[0]:] if name == "start" else chunk[:hits[0]]
        out += chunk
    return out

def _blocks(lines):
    """Блоки (страница, вид, текст). Граница страницы всегда рвёт блок."""
    blocks, buf, buf_page = [], [], None
    i, n = 0, len(lines)

    def flush():
        nonlocal buf
        if buf:
            blocks.append((buf_page, "text", "\n".join(buf)))
            buf = []

    while i < n:
        page, line = lines[i]
        if buf and page != buf_page:
            flush()
        if FENCE.match(line):
            flush()
            j = i + 1
            while j < n and not lines[j][1].strip():
                j += 1
            if j < n and FIG_AI.match(lines[j][1]):
                # описание кончается чертой, а если её нет — пустой строкой после KEYWORDS
                k, keywords = j, False
                while k < n and lines[k][0] == page and not FENCE.match(lines[k][1]):
                    keywords = keywords or lines[k][1].startswith("KEYWORDS")
                    if keywords and not lines[k][1].strip():
                        break
                    k += 1
                blocks.append((page, "figure_ai", "\n".join(l for _, l in lines[j:k]).strip()))
                while k < n and lines[k][0] == page and not lines[k][1].strip():
                    k += 1
                if k < n and lines[k][0] == page and FENCE.match(lines[k][1]):
                    # одна черта может и закрыть описание, и открыть следующее
                    m = k + 1
                    while m < n and not lines[m][1].strip():
                        m += 1
                    if not (m < n and lines[m][0] == page and FIG_AI.match(lines[m][1])):
                        k += 1
                i = k
            else:
                i += 1
            continue
        s = line.strip()
        if s.startswith("$$") or s.startswith("\\["):
            flush()
            close = "$$" if s.startswith("$$") else "\\]"
            k, rest = i, s[2:]
            while close not in rest and k + 1 < n and lines[k + 1][0] == page:
                k += 1
                rest = lines[k][1]
            blocks.append((page, "formula", "\n".join(l for _, l in lines[i:k + 1]).strip()))
            i = k + 1
            continue
        if not s:
            flush()
        else:
            starts_new = (HEADING.match(line) or TASK.match(s) or EXAMPLE.match(s)
                          or CAPTION.match(s) or TAB_CAPTION.match(s)
                          or bool(buf) and s.startswith("|") != buf[-1].strip().startswith("|"))
            if starts_new or (buf and HEADING.match(buf[-1])):
                flush()
            buf_page = page
            buf.append(line.rstrip())
        i += 1
    flush()
    return blocks


def _service(blocks):
    """Колонтитулы и номера страниц."""
    key = lambda t: re.sub(r"[\W\d_]+", " ", t).strip().casefold()
    counts = {}
    for _, kind, t in blocks:
        if kind == "text" and len(t) < 110:
            counts[key(t)] = counts.get(key(t), 0) + 1
    by_page = {}
    for idx, (p, _, _) in enumerate(blocks):
        by_page.setdefault(p, []).append(idx)
    service = set()
    for idxs in by_page.values():
        edge = set(idxs[:3] + idxs[-3:])
        for i in edge:
            kind, t = blocks[i][1], blocks[i][2]
            if kind != "text" or HEADING.match(t):
                continue
            bare = t.strip()
            repeated = counts.get(key(t), 0) >= 3 and (bare.isupper() or len(bare) >= 15)
            if (re.fullmatch(r"[-—–\s]*\d{1,4}[-—–\s]*", bare) or bare.startswith("©")
                    or (repeated and not TASK_HEAD.match(bare))):
                service.add(i)
    return service


def _garbled(text, lang):
    """Кириллица, распознанная латиницей: «OchoBbAcb Ha pe3yIbTaTax»."""
    if lang != "ru":
        return False
    plain = re.sub(r"\$[^$]*\$|\\\(.*?\\\)|\[[^\]]*\]|\([^)]*\)", " ", text, flags=re.S)
    ws = [w for w in words(plain) if len(w) > 2]
    if len(ws) < 6:
        return False
    latin = sum(1 for w in ws if re.search(r"[a-z]", w))
    return latin / len(ws) > 0.5


def build_units(text, spec):
    lang = spec.get("lang", "ru")
    blocks = _blocks(slice_book(text, spec))
    service = _service(blocks)
    units, seq, section, group, in_tasks, last_task = [], {}, "", None, False, 0
    for i, (page, kind, t) in enumerate(blocks):
        s = t.strip()
        origin, number = "author", None
        if i in service:
            typ, origin = "service", "service"
        elif kind == "figure_ai":
            typ, origin = "figure_desc", "figure_ai"
        elif kind == "formula":
            typ = "formula"
        elif TASK_HEAD.match(s):
            typ, in_tasks, group, last_task = "heading", True, None, 0
        elif CAPTION.match(s):
            typ, number = "figure", CAPTION.match(s).group(1)
        elif HEADING.match(s):
            typ, in_tasks, group = "heading", False, None
            section = HEADING.match(s).group(1).strip("* ")
        elif TAB_CAPTION.match(s):
            typ, number = "table_caption", TAB_CAPTION.match(s).group(1)
        elif s.startswith("|"):
            typ = "table"
        elif EXAMPLE.match(s):
            typ, number, in_tasks = "example", EXAMPLE.match(s).group(1), False
            group = f"example {number}"
        elif in_tasks and TASK.match(s) and int(TASK.match(s).group(1)) > last_task:
            typ, number = "task", TASK.match(s).group(1)
            last_task = int(number)
            group = f"task {number}"
        elif LIST.match(s):
            typ = "list"
            if in_tasks and TASK.match(s):  # нумерация пошла заново: задачи кончились
                in_tasks, group = False, None
        elif len(words(s)) < 2 and len(s) < 30 and not re.search(r"\w{4,}\.$", s):
            typ, origin = "service", "service"
        else:
            typ = "paragraph"
        seq[page] = seq.get(page, 0) + 1
        unit = {"id": f"p{page:03d}.{seq[page]:02d}", "page": page, "type": typ,
                "origin": origin, "section": section, "text": s}
        if number:
            unit["number"] = number
        if group and typ not in ("figure", "figure_desc", "service", "table_caption"):
            unit["group"] = group
        if origin == "author" and typ != "formula" and _garbled(s, lang):
            unit["ocr_suspect"] = True
        units.append(unit)
    return units


KINDS = {"example": "worked_example", "list": "paragraph", "table_caption": "table"}


def kind(unit):
    """Вид единицы по coverage.schema.json."""
    return KINDS.get(unit["type"], unit["type"])


def needs_cover(unit):
    """Единицы, которые обязаны попасть в узел или получить причину."""
    return unit["origin"] == "author" and unit["type"] != "heading"
