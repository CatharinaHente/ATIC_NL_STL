"""
Typed AST for (past + future) Signal Temporal Logic.

Every dataset is parsed into this one representation; every backend (SPOT,
STLSat, the syntactic canonicaliser) consumes it.  Nothing downstream ever
touches raw formula strings, which is what made the old regex pipeline fragile.

Time is *discrete*: one interval unit = one sample (this matches STLSat's
semantics and SPOT's X-based bounded operators).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Tuple, Union

# An interval bound is a number, a symbolic name (e.g. "T"), or None (= +inf, upper bound only)
Bound = Union[Fraction, str, None]


@dataclass(frozen=True)
class Interval:
    lo: Bound = Fraction(0)
    hi: Bound = None

    @property
    def is_full(self) -> bool:
        """[0, inf) — i.e. the classic unbounded LTL operator."""
        return self.lo == 0 and self.hi is None

    @property
    def is_numeric(self) -> bool:
        return all(b is None or isinstance(b, Fraction) for b in (self.lo, self.hi))

    def __str__(self) -> str:
        if self.is_full:
            return ""
        return f"[{_fmt_bound(self.lo)},{_fmt_bound(self.hi)}]"


def _fmt_bound(b: Bound) -> str:
    if b is None:
        return "inf"
    if isinstance(b, Fraction):
        return fmt_num(b)
    return str(b)


def fmt_num(v: Fraction) -> str:
    if v.denominator == 1:
        return str(v.numerator)
    return repr(float(v)) if float(v) == v else f"{v.numerator}/{v.denominator}"


FULL = Interval()


# --------------------------------------------------------------------------
# Arithmetic terms
# --------------------------------------------------------------------------

class Term:
    pass


@dataclass(frozen=True)
class Num(Term):
    value: Fraction


@dataclass(frozen=True)
class Var(Term):
    name: str


@dataclass(frozen=True)
class Arith(Term):
    op: str            # + - * /
    left: Term
    right: Term


@dataclass(frozen=True)
class Neg(Term):
    arg: Term


@dataclass(frozen=True)
class Abs(Term):
    arg: Term


@dataclass(frozen=True)
class Func(Term):
    """Uninterpreted function used as a numeric term, e.g. distance(a, b)."""
    name: str
    args: Tuple[Term, ...]


# --------------------------------------------------------------------------
# Formulas
# --------------------------------------------------------------------------

class Formula:
    pass


@dataclass(frozen=True)
class BoolConst(Formula):
    value: bool


@dataclass(frozen=True)
class Prop(Formula):
    """Boolean signal (or an already-abstracted atom)."""
    name: str


@dataclass(frozen=True)
class PredApp(Formula):
    """Uninterpreted predicate, e.g. in_surveillance(robot_i)."""
    name: str
    args: Tuple[Term, ...]


@dataclass(frozen=True)
class Cmp(Formula):
    op: str            # < <= > >= == !=
    left: Term
    right: Term


@dataclass(frozen=True)
class Not(Formula):
    arg: Formula


@dataclass(frozen=True)
class And(Formula):
    args: Tuple[Formula, ...]


@dataclass(frozen=True)
class Or(Formula):
    args: Tuple[Formula, ...]


@dataclass(frozen=True)
class Implies(Formula):
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Iff(Formula):
    left: Formula
    right: Formula


FUTURE_UNARY = ("G", "F", "X")
PAST_UNARY = ("H", "O", "Y")
FUTURE_BINARY = ("U", "R", "W")
PAST_BINARY = ("S",)


@dataclass(frozen=True)
class Unary(Formula):
    op: str            # G F X (future)  H O Y (past)
    interval: Interval
    arg: Formula


@dataclass(frozen=True)
class Binary(Formula):
    op: str            # U R W (future)  S (past)
    interval: Interval
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Edge(Formula):
    kind: str          # rise | fall
    arg: Formula


@dataclass(frozen=True)
class Indexed(Formula):
    """Parameterised conjunction/disjunction, e.g. AND_{i<j}(...), OR_i(...).
    Parsed so that the syntactic stage can still compare them; no backend supports them."""
    kind: str          # AND | OR
    index: str
    arg: Formula


# --------------------------------------------------------------------------
# Printing (readable, fully explicit, used for logs and the syntactic stage)
# --------------------------------------------------------------------------

def term_str(t: Term) -> str:
    if isinstance(t, Num):
        return fmt_num(t.value)
    if isinstance(t, Var):
        return t.name
    if isinstance(t, Arith):
        return f"({term_str(t.left)} {t.op} {term_str(t.right)})"
    if isinstance(t, Neg):
        return f"-({term_str(t.arg)})"
    if isinstance(t, Abs):
        return f"abs({term_str(t.arg)})"
    if isinstance(t, Func):
        return f"{t.name}({', '.join(term_str(a) for a in t.args)})"
    raise TypeError(t)


def to_str(f: Formula) -> str:
    if isinstance(f, BoolConst):
        return "true" if f.value else "false"
    if isinstance(f, Prop):
        return f.name
    if isinstance(f, PredApp):
        return f"{f.name}({', '.join(term_str(a) for a in f.args)})"
    if isinstance(f, Cmp):
        return f"({term_str(f.left)} {f.op} {term_str(f.right)})"
    if isinstance(f, Not):
        return f"!{to_str(f.arg)}"
    if isinstance(f, And):
        return "(" + " & ".join(to_str(a) for a in f.args) + ")"
    if isinstance(f, Or):
        return "(" + " | ".join(to_str(a) for a in f.args) + ")"
    if isinstance(f, Implies):
        return f"({to_str(f.left)} -> {to_str(f.right)})"
    if isinstance(f, Iff):
        return f"({to_str(f.left)} <-> {to_str(f.right)})"
    if isinstance(f, Unary):
        return f"{f.op}{f.interval}({to_str(f.arg)})"
    if isinstance(f, Binary):
        return f"({to_str(f.left)} {f.op}{f.interval} {to_str(f.right)})"
    if isinstance(f, Edge):
        return f"{f.kind}({to_str(f.arg)})"
    if isinstance(f, Indexed):
        return f"{f.kind}_{f.index}({to_str(f.arg)})"
    raise TypeError(f)


# --------------------------------------------------------------------------
# Generic traversal helpers
# --------------------------------------------------------------------------

def children(f: Formula):
    if isinstance(f, (Not, Unary, Edge, Indexed)):
        return (f.arg,)
    if isinstance(f, (And, Or)):
        return f.args
    if isinstance(f, (Implies, Iff, Binary)):
        return (f.left, f.right)
    return ()


def walk(f: Formula):
    yield f
    for c in children(f):
        yield from walk(c)


def walk_terms(t: Term):
    yield t
    if isinstance(t, Arith):
        yield from walk_terms(t.left)
        yield from walk_terms(t.right)
    elif isinstance(t, (Neg, Abs)):
        yield from walk_terms(t.arg)
    elif isinstance(t, Func):
        for a in t.args:
            yield from walk_terms(a)


def formula_terms(f: Formula):
    """All arithmetic terms (recursively) occurring in f."""
    for n in walk(f):
        if isinstance(n, Cmp):
            yield from walk_terms(n.left)
            yield from walk_terms(n.right)
        elif isinstance(n, PredApp):
            for a in n.args:
                yield from walk_terms(a)


def rebuild(f: Formula, fn) -> Formula:
    """Bottom-up map: rebuild f with fn applied to every (already rebuilt) node."""
    if isinstance(f, Not):
        f = Not(rebuild(f.arg, fn))
    elif isinstance(f, And):
        f = And(tuple(rebuild(a, fn) for a in f.args))
    elif isinstance(f, Or):
        f = Or(tuple(rebuild(a, fn) for a in f.args))
    elif isinstance(f, Implies):
        f = Implies(rebuild(f.left, fn), rebuild(f.right, fn))
    elif isinstance(f, Iff):
        f = Iff(rebuild(f.left, fn), rebuild(f.right, fn))
    elif isinstance(f, Unary):
        f = Unary(f.op, f.interval, rebuild(f.arg, fn))
    elif isinstance(f, Binary):
        f = Binary(f.op, f.interval, rebuild(f.left, fn), rebuild(f.right, fn))
    elif isinstance(f, Edge):
        f = Edge(f.kind, rebuild(f.arg, fn))
    elif isinstance(f, Indexed):
        f = Indexed(f.kind, f.index, rebuild(f.arg, fn))
    return fn(f)


def intervals(f: Formula):
    for n in walk(f):
        if isinstance(n, (Unary, Binary)):
            yield n.interval


def future_horizon(f: Formula, unbounded_as: Optional[int] = None) -> Optional[Fraction]:
    """Max time (relative to evaluation time) at which f reads a signal.
    Unbounded future operators count as `unbounded_as` (None -> return None).
    Past operators look backwards and add nothing."""
    if isinstance(f, (BoolConst, Prop, PredApp, Cmp)):
        return Fraction(0)
    if isinstance(f, Unary):
        h = future_horizon(f.arg, unbounded_as)
        if h is None:
            return None
        if f.op == "X":
            return h + 1
        if f.op in PAST_UNARY:
            return h
        hi = f.interval.hi
        if hi is None:
            if unbounded_as is None:
                return None
            hi = (f.interval.lo if isinstance(f.interval.lo, Fraction) else 0) + unbounded_as
        if not isinstance(hi, Fraction):
            raise ValueError("symbolic bound")
        return hi + h
    if isinstance(f, Binary):
        hs = [future_horizon(c, unbounded_as) for c in (f.left, f.right)]
        if any(h is None for h in hs):
            return None
        if f.op in PAST_BINARY:
            return max(hs)
        hi = f.interval.hi
        if hi is None:
            if unbounded_as is None:
                return None
            hi = (f.interval.lo if isinstance(f.interval.lo, Fraction) else 0) + unbounded_as
        if not isinstance(hi, Fraction):
            raise ValueError("symbolic bound")
        return hi + max(hs)
    hs = [future_horizon(c, unbounded_as) for c in children(f)]
    if any(h is None for h in hs):
        return None
    return max(hs) if hs else Fraction(0)


def mk_and(args) -> Formula:
    args = tuple(args)
    if not args:
        return BoolConst(True)
    return args[0] if len(args) == 1 else And(args)


def mk_or(args) -> Formula:
    args = tuple(args)
    if not args:
        return BoolConst(False)
    return args[0] if len(args) == 1 else Or(args)
