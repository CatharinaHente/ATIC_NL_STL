"""
Pair-level normalisation (applied identically to gold and prediction).

1. Signal typing.  `x`, `x = 1`, `!x`, `x = 0` are only interchangeable if x is Boolean.
   Types come from the dataset's signal context when available (ATIC: "Boolean (1=true,
   0=false): `a`, `b`. Numeric: `x`."), otherwise they are inferred from *both* formulas
   jointly: a signal is Boolean if it is used bare as a proposition, or is only ever
   compared against the literals 0/1 with = / !=.
2. Boolean comparisons -> propositions:  b == 1 -> b,  b == 0 -> !b,  b != 1 -> !b, ...
3. Real-valued interval endpoints are scaled to integers with ONE factor for the whole
   pair (the old code scaled each formula with its own factor, which silently changed
   the relation between gold and prediction).
4. A semantics-preserving canonical form (flattening, sorting commutative operands,
   double negation, symmetric functions, abs(a-b) == abs(b-a), oriented comparisons)
   used by the cheap syntactic stage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from functools import reduce
from math import lcm
from typing import Dict, Iterable, Optional, Set, Tuple

from .ast import (Abs, And, Arith, Binary, BoolConst, Cmp, Edge, Formula, Func, Iff,
                  Implies, Indexed, Interval, Neg, Not, Num, Or, PredApp, Prop, Term, Unary,
                  Var, formula_terms, rebuild, term_str, to_str, walk)


# --------------------------------------------------------------------------
# 1. Signal typing
# --------------------------------------------------------------------------

@dataclass
class TypeEnv:
    boolean: Set[str] = field(default_factory=set)
    numeric: Set[str] = field(default_factory=set)
    source: str = "inferred"          # "context" | "inferred" | "context+inferred"


_CTX_SECTION = re.compile(r"(Boolean|Numeric)[^:]*:\s*(.*?)(?=(?:Boolean|Numeric|Semantics|Time|Objects|Parameters|Use these)\b|$)",
                          re.S)


def parse_signal_context(text: Optional[str]) -> Tuple[Set[str], Set[str]]:
    """Extract Boolean / Numeric identifiers from an ATIC-style signal_context string."""
    boolean, numeric = set(), set()
    if not text or not isinstance(text, str):
        return boolean, numeric
    for kind, body in _CTX_SECTION.findall(text):
        names = set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", body))
        (boolean if kind == "Boolean" else numeric).update(names)
    return boolean, numeric


def _is01(t: Term) -> bool:
    return isinstance(t, Num) and t.value in (0, 1)


def _key(t: Term) -> Optional[str]:
    """Identifier key for a Var or an uninterpreted Func application (e.g. in_zone(robot_i))."""
    if isinstance(t, Var):
        return t.name
    if isinstance(t, Func):
        return term_str(t)
    return None


def infer_types(formulas: Iterable[Formula], context: Optional[str] = None) -> TypeEnv:
    formulas = list(formulas)
    ctx_bool, ctx_num = parse_signal_context(context)
    bare, cmp01_only, cmp_other = set(), set(), set()
    for f in formulas:
        for n in walk(f):
            if isinstance(n, Prop):
                bare.add(n.name)
            elif isinstance(n, Cmp):
                for side, other in ((n.left, n.right), (n.right, n.left)):
                    k = _key(side)
                    if k is None:
                        continue
                    if n.op in ("==", "!=") and _is01(other):
                        cmp01_only.add(k)
                    else:
                        cmp_other.add(k)
        for t in formula_terms(f):
            if isinstance(t, (Arith, Neg, Abs)):
                for sub in (t.left, t.right) if isinstance(t, Arith) else (t.arg,):
                    k = _key(sub)
                    if k:
                        cmp_other.add(k)
    inferred_bool = (bare | cmp01_only) - cmp_other
    env = TypeEnv(boolean=set(ctx_bool), numeric=set(ctx_num), source="context" if (ctx_bool or ctx_num) else "inferred")
    extra = inferred_bool - env.boolean - env.numeric
    if extra:
        env.boolean |= extra
        if env.source == "context":
            env.source = "context+inferred"
    env.numeric |= (cmp_other - env.boolean)
    return env


# --------------------------------------------------------------------------
# 2. Boolean comparisons -> propositions
# --------------------------------------------------------------------------

def booleanize(f: Formula, env: TypeEnv) -> Formula:
    def fn(n: Formula) -> Formula:
        if isinstance(n, Cmp) and n.op in ("==", "!="):
            for side, other in ((n.left, n.right), (n.right, n.left)):
                k = _key(side)
                if k is not None and k in env.boolean and _is01(other):
                    atom = Prop(side.name) if isinstance(side, Var) else PredApp(side.name, side.args)
                    positive = (other.value == 1) == (n.op == "==")
                    return atom if positive else Not(atom)
        return n
    return rebuild(f, fn)


# --------------------------------------------------------------------------
# 3. Joint interval scaling
# --------------------------------------------------------------------------

def _bounds(f: Formula):
    for n in walk(f):
        if isinstance(n, (Unary, Binary)):
            for b in (n.interval.lo, n.interval.hi):
                if isinstance(b, Fraction):
                    yield b


def interval_scale(formulas: Iterable[Formula]) -> int:
    denoms = [b.denominator for f in formulas for b in _bounds(f)]
    return reduce(lcm, denoms, 1)


def scale_intervals(f: Formula, k: int) -> Formula:
    if k == 1:
        return f

    def sc(b):
        return b * k if isinstance(b, Fraction) else b

    def fn(n):
        if isinstance(n, Unary):
            return Unary(n.op, Interval(sc(n.interval.lo), sc(n.interval.hi)), n.arg)
        if isinstance(n, Binary):
            return Binary(n.op, Interval(sc(n.interval.lo), sc(n.interval.hi)), n.left, n.right)
        return n
    return rebuild(f, fn)


# --------------------------------------------------------------------------
# Pair normalisation entry point
# --------------------------------------------------------------------------

@dataclass
class NormalisedPair:
    gold: Formula
    pred: Formula
    env: TypeEnv
    time_scale: int
    notes: list


def normalise_pair(gold: Formula, pred: Formula, context: Optional[str] = None) -> NormalisedPair:
    env = infer_types([gold, pred], context)
    g, p = booleanize(gold, env), booleanize(pred, env)
    notes = []
    k = interval_scale([g, p])
    if k != 1:
        g, p = scale_intervals(g, k), scale_intervals(p, k)
        notes.append(f"real-valued interval bounds: time scaled by x{k} for both formulas "
                     f"(assumes sampling period 1/{k})")
    return NormalisedPair(g, p, env, k, notes)


# --------------------------------------------------------------------------
# 4. Canonical form (sound rewrites only)
# --------------------------------------------------------------------------

_FLIP = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}


def canon_term(t: Term, symmetric: Set[str]) -> Term:
    if isinstance(t, Arith):
        l, r = canon_term(t.left, symmetric), canon_term(t.right, symmetric)
        if t.op in ("+", "*") and term_str(l) > term_str(r):
            l, r = r, l
        return Arith(t.op, l, r)
    if isinstance(t, Neg):
        return Neg(canon_term(t.arg, symmetric))
    if isinstance(t, Abs):
        a = canon_term(t.arg, symmetric)
        # abs(a - b) == abs(b - a): pick the lexicographically smaller orientation
        if isinstance(a, Arith) and a.op == "-":
            swapped = Arith("-", a.right, a.left)
            if term_str(swapped) < term_str(a):
                a = swapped
        return Abs(a)
    if isinstance(t, Func):
        args = tuple(canon_term(a, symmetric) for a in t.args)
        if t.name in symmetric and len(args) == 2:
            args = tuple(sorted(args, key=term_str))
        return Func(t.name, args)
    return t


def canonical(f: Formula, symmetric: Set[str] = frozenset()) -> Formula:
    def fn(n: Formula) -> Formula:
        if isinstance(n, Cmp):
            l, r = canon_term(n.left, symmetric), canon_term(n.right, symmetric)
            op = n.op
            # constants on the right: 3 < x  ->  x > 3
            if isinstance(l, Num) and not isinstance(r, Num):
                l, r, op = r, l, _FLIP[op]
            elif op in ("==", "!=") and term_str(l) > term_str(r) and not isinstance(r, Num):
                l, r = r, l
            return Cmp(op, l, r)
        if isinstance(n, PredApp):
            args = tuple(canon_term(a, symmetric) for a in n.args)
            if n.name in symmetric and len(args) == 2:
                args = tuple(sorted(args, key=term_str))
            return PredApp(n.name, args)
        if isinstance(n, Not):
            if isinstance(n.arg, Not):
                return n.arg.arg
            if isinstance(n.arg, BoolConst):
                return BoolConst(not n.arg.value)
            return n
        if isinstance(n, (And, Or)):
            cls = type(n)
            flat = []
            for a in n.args:
                flat.extend(a.args if isinstance(a, cls) else (a,))
            uniq = {to_str(a): a for a in flat}
            args = tuple(uniq[k] for k in sorted(uniq))
            return args[0] if len(args) == 1 else cls(args)
        if isinstance(n, Iff):
            l, r = sorted((n.left, n.right), key=to_str)
            return Iff(l, r)
        return n
    return rebuild(f, fn)
