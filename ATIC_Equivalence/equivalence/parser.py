"""
Dialect-tolerant STL parser (string -> typed AST).

Accepted notation (case-sensitive single letters, case-insensitive words):

  Boolean      &  &&  /\\  ∧  and  \\wedge      |  ||  \\/  ∨  or  \\vee
               !  ~  ¬  not  \\neg              ->  =>  →  implies      <->  <=>  ↔  iff
  Future       G  []  □  always  globally       F  <>  ◇  eventually  finally
               X  next                          U  until    R  release    W (weak until)
  Past         H  historically   O  once   Y  yesterday   S  since
  Events       rise(φ)  fall(φ)
  Intervals    G[a,b]  G[a:b]  G[a..b]  G_[a,b]  G_{[a,b]}  G[a,inf)  X[n]   (symbolic bounds allowed: G[0,T])
  Atoms        x  x = 1  x == 1  x >= 2.5  x1 + x2 <= 1.5  abs(x - y) < 0.2  |x - y| < 0.2
               f(a, b) < d   (uninterpreted function)   p(i)  (uninterpreted predicate)
  Constants    true  false
  Parametric   AND_{i<j}(φ)  OR_i(φ)                     (parsed, but no backend supports them)

Precedence (loosest -> tightest):  <->  ->  |  &  U/R/S/W  unary(! G F X H O Y)  comparisons  + -  * /
Unary temporal operators bind tighter than binary ones (SPOT convention): `G a -> b` == `(G a) -> b`.

To support a new notation, extend `_UNICODE`, `_LATEX` or `_WORDS` below.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import List, Tuple

from .ast import (Abs, And, Arith, Binary, BoolConst, Cmp, Edge, Formula, Func, Iff,
                  Implies, Indexed, Interval, Neg, Not, Num, Or, PredApp, Prop, Term,
                  Unary, Var)


class ParseError(ValueError):
    pass


# --------------------------------------------------------------------------
# Pre-processing: map exotic notations to the canonical ASCII token set
# --------------------------------------------------------------------------

_UNICODE = {
    "∧": " & ", "∨": " | ", "¬": " ! ", "→": " -> ", "⇒": " -> ", "⟶": " -> ", "⟹": " -> ",
    "↔": " <-> ", "⇔": " <-> ", "⟺": " <-> ", "≤": " <= ", "≥": " >= ", "≠": " != ",
    "□": " G ", "◻": " G ", "◇": " F ", "◊": " F ", "⋄": " F ", "○": " X ", "◯": " X ",
    "∞": "inf", "−": "-", "𝒰": " U ",
}

_LATEX = [
    (r"\\(?:wedge|land)(?![A-Za-z])", " & "), (r"\\(?:vee|lor)(?![A-Za-z])", " | "), (r"\\(?:neg|lnot)(?![A-Za-z])", " ! "),
    (r"\\(?:rightarrow|Rightarrow|implies|to)(?![A-Za-z])", " -> "),
    (r"\\(?:leftrightarrow|Leftrightarrow|iff)(?![A-Za-z])", " <-> "),
    (r"\\(?:Box|square)(?![A-Za-z])", " G "), (r"\\(?:Diamond|lozenge)(?![A-Za-z])", " F "), (r"\\bigcirc(?![A-Za-z])", " X "),
    (r"\\mathcal\{U\}", " U "), (r"\\mathbf\{U\}", " U "),
    (r"\\(?:leq|le)(?![A-Za-z])", " <= "), (r"\\(?:geq|ge)(?![A-Za-z])", " >= "), (r"\\(?:neq|ne)(?![A-Za-z])", " != "),
    (r"\\infty(?![A-Za-z])", "inf"), (r"\\(?:left|right)(?![A-Za-z])", ""),
]

# word-form operators (matched only when written in lower case, so a signal named `Until` survives)
_WORDS = {
    "and": ("op", "&"), "or": ("op", "|"), "not": ("op", "!"), "implies": ("op", "->"),
    "iff": ("op", "<->"), "true": ("const", True), "false": ("const", False),
    "always": ("tu", "G"), "globally": ("tu", "G"), "eventually": ("tu", "F"),
    "finally": ("tu", "F"), "next": ("tu", "X"), "historically": ("tu", "H"),
    "once": ("tu", "O"), "yesterday": ("tu", "Y"), "previously": ("tu", "Y"),
    "until": ("tb", "U"), "release": ("tb", "R"), "releases": ("tb", "R"), "since": ("tb", "S"),
}

_TEMPORAL_UNARY = {"G", "F", "X", "H", "O", "Y"}
_TEMPORAL_BINARY = {"U", "R", "S", "W"}


def preprocess(s: str) -> str:
    for k, v in _UNICODE.items():
        s = s.replace(k, v)
    for pat, rep in _LATEX:
        s = re.sub(pat, rep, s)
    # subscripted intervals: G_{[0,5]} -> G[0,5],  G_[0,5] -> G[0,5]
    s = re.sub(r"(?<![A-Za-z0-9_])([GFXUROHSWY])\s*_\s*\{\s*([\[(][^}]*?[\])])\s*\}", r"\1\2", s)
    s = re.sub(r"(?<![A-Za-z0-9_])([GFXUROHSWY])_(?=[\[(])", r"\1", s)
    return s


# --------------------------------------------------------------------------
# Tokeniser
# --------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"""
   (?P<ws>\s+)
 | (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+)
 | (?P<indexed>(?:AND|OR)_(?:\{[^}]*\}|[A-Za-z0-9]+))
 | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
 | (?P<op><->|<=>|->|=>|&&|\|\||/\\|\\/|<=|>=|==|!=|\[\]|<>|\.\.|[=<>!~&|+\-*/,:()\[\]$])
""", re.X)


@dataclass
class Tok:
    kind: str     # num id indexed op tu tb const eof
    val: object
    pos: int


def tokenize(s: str) -> List[Tok]:
    toks, i = [], 0
    while i < len(s):
        m = _TOKEN_RE.match(s, i)
        if not m:
            raise ParseError(f"unexpected character {s[i]!r} at position {i}")
        kind = m.lastgroup
        val = m.group()
        i = m.end()
        if kind == "ws":
            continue
        if kind == "num":
            toks.append(Tok("num", Fraction(val), m.start()))
        elif kind == "id" and val in _WORDS:
            k, v = _WORDS[val]
            toks.append(Tok(k, v, m.start()))
        else:
            toks.append(Tok(kind, val, m.start()))
    toks.append(Tok("eof", None, len(s)))
    return toks


# --------------------------------------------------------------------------
# Pratt parser
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Ident:          # identifier whose role (Prop vs Var) is decided by context
    name: str


@dataclass(frozen=True)
class _Call:           # f(args) whose role (PredApp vs Func) is decided by context
    name: str
    args: tuple


_BOOL_BINARY = {  # token -> (lbp, right_assoc, constructor key)
    "<->": (10, False, "iff"), "<=>": (10, False, "iff"),
    "->": (20, True, "imp"), "=>": (20, True, "imp"),
    "|": (30, False, "or"), "||": (30, False, "or"), "\\/": (30, False, "or"),
    "&": (40, False, "and"), "&&": (40, False, "and"), "/\\": (40, False, "and"),
}
_TEMPORAL_LBP = 50
_UNARY_RBP = 60
_CMP = {"<": "<", "<=": "<=", ">": ">", ">=": ">=", "==": "==", "=": "==", "!=": "!="}
_CMP_LBP = 70
_ARITH = {"+": 80, "-": 80, "*": 90, "/": 90}
_NEG_RBP = 95

_OPERAND_START_OPS = {"(", "[", "!", "~", "[]", "<>"}


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.toks = tokenize(preprocess(text))
        self.i = 0

    # -- token helpers --------------------------------------------------
    def peek(self, k=0) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def at_op(self, *vals, k=0) -> bool:
        t = self.peek(k)
        return t.kind == "op" and t.val in vals

    def expect_op(self, *vals) -> Tok:
        t = self.next()
        if t.kind != "op" or t.val not in vals:
            raise ParseError(f"expected {' or '.join(vals)} at position {t.pos}, got {t.val!r}")
        return t

    def _starts_operand(self, t: Tok) -> bool:
        if t.kind in ("id", "num", "indexed", "tu", "const"):
            return True
        return t.kind == "op" and t.val in _OPERAND_START_OPS

    # -- conversions ----------------------------------------------------
    def as_formula(self, x) -> Formula:
        if isinstance(x, Formula):
            return x
        if isinstance(x, _Ident):
            return Prop(x.name)
        if isinstance(x, _Call):
            return PredApp(x.name, tuple(self.as_term(a) for a in x.args))
        if isinstance(x, Num) and x.value in (0, 1):
            return BoolConst(bool(x.value))
        raise ParseError(f"arithmetic expression used where a formula is expected: {x}")

    def as_term(self, x) -> Term:
        if isinstance(x, Term):
            return x
        if isinstance(x, _Ident):
            return Var(x.name)
        if isinstance(x, _Call):
            args = tuple(self.as_term(a) for a in x.args)
            if x.name == "abs" and len(args) == 1:
                return Abs(args[0])
            return Func(x.name, args)
        raise ParseError(f"formula used where an arithmetic term is expected: {x}")

    # -- intervals ------------------------------------------------------
    def parse_bound(self):
        t = self.next()
        sign = 1
        if t.kind == "op" and t.val in ("+", "-"):
            sign = -1 if t.val == "-" else 1
            t = self.next()
        if t.kind == "num":
            return sign * t.val
        if t.kind == "op" and t.val == "$":
            return None
        if t.kind == "id":
            if t.val.lower() in ("inf", "infty", "infinity", "oo"):
                return None
            return t.val
        raise ParseError(f"bad interval bound {t.val!r} at position {t.pos}")

    def parse_interval(self, op: str):
        self.expect_op("[")
        lo = self.parse_bound()
        if self.at_op("]"):          # single value: X[3], F[5]
            self.next()
            return Interval(lo, lo)
        self.expect_op(",", ":", "..")
        hi = self.parse_bound()
        self.expect_op("]", ")")
        if lo is None:
            raise ParseError("interval lower bound cannot be infinite")
        if isinstance(lo, Fraction) and isinstance(hi, Fraction) and lo > hi:
            raise ParseError(f"empty interval [{lo},{hi}]")
        if isinstance(lo, Fraction) and lo < 0:
            raise ParseError("negative interval bound")
        return Interval(lo, hi)

    def maybe_interval(self, op: str) -> Interval:
        if self.at_op("["):
            return self.parse_interval(op)
        return Interval()

    # -- core -----------------------------------------------------------
    def parse(self, rbp: int = 0):
        left = self.nud(self.next())
        while True:
            t = self.peek()
            lbp = self.lbp(t)
            if lbp <= rbp:
                break
            self.next()
            left = self.led(t, left)
        return left

    def lbp(self, t: Tok) -> int:
        if t.kind == "op":
            if t.val in _BOOL_BINARY:
                return _BOOL_BINARY[t.val][0]
            if t.val in _CMP:
                return _CMP_LBP
            if t.val in _ARITH:
                return _ARITH[t.val]
            return 0
        if t.kind == "tb" or (t.kind == "id" and t.val in _TEMPORAL_BINARY):
            return _TEMPORAL_LBP
        return 0

    def unary_temporal(self, op: str):
        interval = Interval()
        if op in ("G", "F", "H", "O") or self.at_op("["):
            interval = self.maybe_interval(op)
        if op in ("X", "Y") and not interval.is_full:
            # X[n] φ  ==  X X ... X φ
            if interval.lo != interval.hi or not isinstance(interval.lo, Fraction):
                raise ParseError(f"{op} only accepts a single step count, e.g. X[3]")
            arg = self.as_formula(self.parse(_UNARY_RBP))
            for _ in range(int(interval.lo)):
                arg = Unary(op, Interval(), arg)
            return arg
        return Unary(op, interval, self.as_formula(self.parse(_UNARY_RBP)))

    def nud(self, t: Tok):
        if t.kind == "num":
            return Num(t.val)
        if t.kind == "const":
            return BoolConst(t.val)
        if t.kind == "tu":
            return self.unary_temporal(t.val)
        if t.kind == "indexed":
            kind, index = t.val.split("_", 1)
            index = re.sub(r"\s+", "", index.strip("{}"))
            self.expect_op("(")
            body = self.as_formula(self.parse(0))
            self.expect_op(")")
            return Indexed(kind, index, body)
        if t.kind == "id":
            name = t.val
            nxt = self.peek()
            if name in _TEMPORAL_UNARY and self._starts_operand(nxt):
                return self.unary_temporal(name)
            if re.fullmatch(r"[GFX]{2,3}", name) and self._starts_operand(nxt):
                # fused operators, e.g. GF p  ->  G(F(p))
                inner = self.as_formula(self.parse(_UNARY_RBP))
                for op in reversed(name):
                    inner = Unary(op, Interval(), inner)
                return inner
            if self.at_op("("):
                self.next()
                if name in ("rise", "fall"):
                    arg = self.as_formula(self.parse(0))
                    self.expect_op(")")
                    return Edge(name, arg)
                args = []
                if not self.at_op(")"):
                    args.append(self.parse(0))
                    while self.at_op(","):
                        self.next()
                        args.append(self.parse(0))
                self.expect_op(")")
                return _Call(name, tuple(args))
            return _Ident(name)
        if t.kind == "op":
            v = t.val
            if v == "(":
                inner = self.parse(0)
                self.expect_op(")")
                return inner
            if v in ("!", "~"):
                return Not(self.as_formula(self.parse(_UNARY_RBP)))
            if v == "[]":
                return self.unary_temporal("G")
            if v == "<>":
                return self.unary_temporal("F")
            if v == "-":
                arg = self.as_term(self.parse(_NEG_RBP))
                return Num(-arg.value) if isinstance(arg, Num) else Neg(arg)
            if v == "|":                     # |expr|  absolute value
                inner = self.as_term(self.parse(_CMP_LBP + 5))
                self.expect_op("|")
                return Abs(inner)
        raise ParseError(f"unexpected token {t.val!r} at position {t.pos}")

    def led(self, t: Tok, left):
        if t.kind == "tb" or (t.kind == "id" and t.val in _TEMPORAL_BINARY):
            op = t.val
            interval = self.maybe_interval(op)
            right = self.parse(_TEMPORAL_LBP - 1)          # right-associative
            return Binary(op, interval, self.as_formula(left), self.as_formula(right))
        v = t.val
        if v in _BOOL_BINARY:
            lbp, right_assoc, key = _BOOL_BINARY[v]
            right = self.as_formula(self.parse(lbp - 1 if right_assoc else lbp))
            left = self.as_formula(left)
            if key == "and":
                return And(_flat(And, left) + _flat(And, right))
            if key == "or":
                return Or(_flat(Or, left) + _flat(Or, right))
            if key == "imp":
                return Implies(left, right)
            return Iff(left, right)
        if v in _CMP:
            right = self.parse(_CMP_LBP)
            if self.at_op(*_CMP):
                raise ParseError("chained comparisons (a < x < b) are ambiguous; write (a < x) & (x < b)")
            return Cmp(_CMP[v], self.as_term(left), self.as_term(right))
        if v in _ARITH:
            right = self.parse(_ARITH[v])
            return Arith(v, self.as_term(left), self.as_term(right))
        raise ParseError(f"unexpected token {v!r} at position {t.pos}")


def _flat(cls, f) -> Tuple:
    return f.args if isinstance(f, cls) else (f,)


def parse(text: str) -> Formula:
    """Parse a formula string in any supported dialect into the typed AST."""
    if text is None or not str(text).strip():
        raise ParseError("empty formula")
    text = str(text)
    if "..." in text.replace("[", " ").replace("]", " ") and re.search(r"\.\.\.\s*$", text.strip()):
        raise ParseError("formula is truncated ('...') in the source data")
    p = _Parser(text)
    tree = p.parse(0)
    if p.peek().kind != "eof":
        t = p.peek()
        raise ParseError(f"unexpected trailing input {t.val!r} at position {t.pos}")
    return p.as_formula(tree)
