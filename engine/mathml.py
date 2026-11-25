"""LaTeX -> MathML без сторонних библиотек: формулы видны в курсе офлайн.

Поддержано то, что встречается в распознанных книгах. Если формула не разобралась,
показываем исходный код, а не искажённую формулу.
"""
import html
import re

SYM = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ", "epsilon": "ε", "varepsilon": "ε",
       "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "kappa": "κ", "varkappa": "ϰ", "lambda": "λ",
       "Lambda": "Λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "Pi": "Π", "rho": "ρ", "sigma": "σ", "Sigma": "Σ",
       "tau": "τ", "phi": "φ", "varphi": "φ", "Phi": "Φ", "chi": "χ", "psi": "ψ", "Psi": "Ψ", "omega": "ω",
       "Omega": "Ω", "Gamma": "Γ", "Theta": "Θ", "partial": "∂", "nabla": "∇", "infty": "∞", "ell": "ℓ"}
OPS = {"cdot": "·", "times": "×", "div": "÷", "pm": "±", "mp": "∓", "leq": "≤", "le": "≤", "leqslant": "≤",
       "geq": "≥", "ge": "≥", "geqslant": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "equiv": "≡", "sim": "∼",
       "to": "→", "rightarrow": "→", "Rightarrow": "⇒", "int": "∫", "sum": "∑", "prod": "∏", "ll": "≪", "gg": "≫",
       "propto": "∝", "ldots": "…", "dots": "…", "cdots": "⋯", "in": "∈", "quad": "\u2003", "qquad": "\u2003\u2003",
       "%": "%", ",": "\u2009", ";": "\u2005", ":": "\u2005", "!": "", " ": "\u2009", "&": "&", "{": "{", "}": "}",
       "_": "_", "#": "#", "|": "‖", "prime": "′", "circ": "∘", "degree": "°", "mid": "|", "doteq": "≐"}
FUNCS = {"ln", "log", "lg", "exp", "sin", "cos", "tan", "min", "max", "lim", "erf", "grad", "div", "sup", "inf", "arctan"}
ACCENT = {"bar": "¯", "overline": "¯", "hat": "^", "tilde": "~", "dot": "˙", "ddot": "¨", "vec": "→"}
TOKEN = re.compile(r"\\[A-Za-z]+\*?|\\.|[{}^_&]|\d+(?:[.,]\d+)*|\s+|.", re.S)


class Bad(ValueError):
    pass


def mo(s):
    return f"<mo>{html.escape(s)}</mo>"


def mtext(s):
    return f"<mtext>{html.escape(s)}</mtext>"


class Parser:
    def __init__(self, src):
        self.t = [x for x in TOKEN.findall(src) if not x.isspace()]
        self.raw = src
        self.i = 0
        self.tag = ""

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        if self.i >= len(self.t):
            raise Bad("формула оборвалась")
        self.i += 1
        return self.t[self.i - 1]

    def group_text(self):
        """Текст внутри {...} как есть (для \\text и \\mathrm)."""
        if self.peek() != "{":
            return self.next()
        self.next()
        depth, out = 1, []
        while depth:
            x = self.next()
            depth += (x == "{") - (x == "}")
            if depth:
                out.append(x)
        return " ".join(out) if any(len(x) > 1 for x in out) and len(out) < 3 else "".join(out)

    def row(self, stop=()):
        out = []
        while self.peek() is not None and self.peek() not in stop:
            out.append(self.scripts())
        return f"<mrow>{''.join(out)}</mrow>"

    def scripts(self):
        # «Па$^{-1}$»: основание степени осталось в тексте
        base, sub, sup = ("<mrow></mrow>" if self.peek() in ("^", "_") else self.atom()), None, None
        while self.peek() in ("^", "_"):
            if self.next() == "^":
                sup = self.arg() if sup is None else f"<mrow>{sup}{self.arg()}</mrow>"
            else:
                sub = self.arg() if sub is None else f"<mrow>{sub}{self.arg()}</mrow>"
        while self.peek() == "'":
            self.next()
            sup = (sup or "") + mo("′")
            sup = f"<mrow>{sup}</mrow>"
        if sub and sup:
            return f"<msubsup>{base}{sub}{sup}</msubsup>"
        if sub:
            return f"<msub>{base}{sub}</msub>"
        return f"<msup>{base}{sup}</msup>" if sup else base

    def arg(self):
        if self.peek() == "{":
            self.next()
            r = self.row(("}",))
            self.close()
            return r
        return self.atom()

    def close(self):
        if self.next() != "}":
            raise Bad("нет закрывающей скобки")

    def delim(self):
        x = self.next()
        if x == ".":
            return ""
        return mo({"\\{": "{", "\\}": "}", "\\|": "‖", "\\langle": "⟨", "\\rangle": "⟩"}.get(x, x))

    def env(self, name):
        rows, cell, cells = [], [], []
        end = False
        if name in ("array", "tabular") and self.peek() == "{":
            self.group_text()
        while not end:
            x = self.peek()
            if x is None:
                raise Bad("нет конца окружения")
            if x == "&":
                self.next()
                cells.append("".join(cell))
                cell = []
            elif x == "\\\\":
                self.next()
                cells.append("".join(cell))
                rows.append(cells)
                cell, cells = [], []
            elif x == "\\end":
                self.next()
                self.group_text()
                cells.append("".join(cell))
                rows.append(cells)
                end = True
            else:
                cell.append(self.scripts())
        body = "".join("<mtr>" + "".join(f"<mtd><mrow>{c}</mrow></mtd>" for c in r) + "</mtr>"
                       for r in rows if any(r))
        table = f'<mtable columnalign="left">{body}</mtable>'
        return f"<mrow>{mo('{')}{table}</mrow>" if name == "cases" else table

    def atom(self):
        x = self.next()
        if x == "{":
            r = self.row(("}",))
            self.close()
            return r
        if x in ("}", "^", "_"):
            raise Bad(f"лишний знак {x}")
        if x == "&":
            return ""
        if re.fullmatch(r"\d+(?:[.,]\d+)*", x):
            return f"<mn>{x}</mn>"
        if not x.startswith("\\"):
            if x.isalpha():
                return f"<mi>{html.escape(x)}</mi>"
            return f'<mo stretchy="false">{x}</mo>' if x in "()[]|" else mo({"-": "−"}.get(x, x))
        name = x[1:].rstrip("*")
        if name in ("frac", "dfrac", "tfrac"):
            a, b = self.arg(), self.arg()
            return f"<mfrac>{a}{b}</mfrac>"
        if name == "sqrt":
            if self.peek() == "[":
                self.next()
                idx = self.row(("]",))
                self.next()
                return f"<mroot>{self.arg()}{idx}</mroot>"
            return f"<msqrt>{self.arg()}</msqrt>"
        if name in ("text", "textrm", "mbox", "mathrm", "operatorname", "mathbf", "mathit", "rm", "textbf"):
            if name == "rm" and self.peek() != "{":
                return ""
            inner = self.group_text()
            if "\\" in inner:
                return Parser(inner).row()
            return mtext(inner)
        if name in ("mathcal", "boldsymbol", "mathbb", "displaystyle", "limits", "nolimits"):
            return self.arg() if self.peek() == "{" else ""
        if name == "left":
            a = self.delim()
            r = self.row(("\\right",))
            self.next()
            return f"<mrow>{a}{r}{self.delim()}</mrow>"
        if name.lower().startswith("big"):
            return self.delim()
        if name in ACCENT:
            return f"<mover>{self.arg()}{mo(ACCENT[name])}</mover>"
        if name == "underset" or name == "overset":
            a, b = self.arg(), self.arg()
            return f"<munder>{b}{a}</munder>" if name == "underset" else f"<mover>{b}{a}</mover>"
        if name == "tag":
            self.tag = self.group_text()
            return ""
        if name == "begin":
            return self.env(self.group_text().rstrip("*"))
        if name in FUNCS:
            return mtext(name) + mo("\u2061")
        if name in SYM:
            return f"<mi>{SYM[name]}</mi>"
        if name in OPS:
            return mo(OPS[name]) if OPS[name] else ""
        if name in ("\\", "newline"):
            return '<mspace linebreak="newline"/>'
        raise Bad(f"неизвестная команда \\{name}")


def convert(latex, block=False):
    src = latex.strip()
    src = re.sub(r"^(\$\$|\\\[|\\\(|\$)\s*|\s*(\$\$|\\\]|\\\)|\$)$", "", src).strip()
    try:
        p = Parser(src)
        body = p.row()
        if p.peek() is not None:
            raise Bad("лишнее в конце")
    except (Bad, IndexError, RecursionError):
        return f"<code>{html.escape(src)}</code>"
    tag = f'<mspace width="2em"/>{mtext("(" + p.tag.strip("() ") + ")")}' if p.tag else ""
    disp = ' display="block"' if block else ""
    return f'<math{disp} xmlns="http://www.w3.org/1998/Math/MathML"><mrow>{body}{tag}</mrow></math>'


INLINE = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]|\$\$(.+?)\$\$|\$([^$]+?)\$", re.S)


SUBSCRIPT = re.compile(r"(?<![\w/.])([A-Za-zА-Яа-яΑ-ω]{1,2})_([A-Za-zА-Яа-я0-9]{1,5})(?!\w)")


def plain(text):
    return SUBSCRIPT.sub(r"<i>\1</i><sub>\2</sub>", html.escape(text))


def rich(text):
    """Обычный текст экранируется, формулы внутри него становятся MathML."""
    out, last, text = [], 0, "" if text is None else str(text).replace("**", "")   # жирный шрифт md в цитате новичку не нужен
    for m in INLINE.finditer(text):
        out.append(plain(text[last:m.start()]))
        out.append(convert(next(g for g in m.groups() if g is not None)))
        last = m.end()
    out.append(plain(text[last:]))
    return "".join(out)
