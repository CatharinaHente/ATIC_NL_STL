"""
Predicate abstraction for SPOT (LTL is propositional, STL atoms are arithmetic).

The old translation turned every comparison into an independent proposition by string
mangling, so `x < 20` and `x >= 20` became unrelated atoms (and `x1 + x2 <= 1.5` was
mangled to `x1 + x2_le_1p5`).  Here each comparison is

  1. linearised:  Σ cᵢ·vᵢ + k  op  0   (non-linear pieces such as abs(e), f(a,b), x*y
     become opaque variables; abs(e) op c with a numeric c is first expanded exactly:
     abs(e) < c  ≡  e < c ∧ e > -c,  abs(e) > c ≡ e > c ∨ e < -c, ...)
  2. normalised so the first variable has coefficient +1      (b - a <= 1  ≡  a - b >= -1)
  3. reduced to the two "upward" atom kinds  T > r  and  T >= r  plus negation
     (T < r ≡ ¬(T >= r),  T <= r ≡ ¬(T > r),  T == r ≡ T >= r ∧ ¬(T > r))

and for every linear term T the ordering axioms  G(a → b)  are added for each pair of its
atoms with  sat(a) ⊆ sat(b)  (e.g. G(x > 5 → x >= 3)).

For atoms over a single linear term this is *exact* (any combination allowed by the
axioms is realisable by some real value).  When two different terms share a variable
(e.g. `x1 + x2 > 1` and `x1 > 0`) the abstraction is an over-approximation: an
EQUIVALENT / containment verdict is still sound, but NON_EQUIVALENT may be spurious.
`AbstractionResult.exact` reports which case applies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Set, Tuple

from .ast import (Abs, And, Arith, BoolConst, Cmp, Formula, Func, Implies, Interval, Neg, Not, Num,
                  Or, PredApp, Prop, Term, Unary, Var, fmt_num, mk_and, mk_or, rebuild,
                  term_str)
from .normalize import canon_term

Linear = Tuple[Dict[str, Fraction], Fraction]       # ({var: coef}, constant)


def _opaque_name(t: Term, symmetric: Set[str]) -> str:
    return term_str(canon_term(t, symmetric))


def _opaque_vars(t: Term) -> Set[str]:
    from .ast import walk_terms
    return {s.name for s in walk_terms(t) if isinstance(s, Var)}


class _Linearizer:
    def __init__(self, symmetric: Set[str]):
        self.symmetric = symmetric
        self.opaque_vars: Dict[str, Set[str]] = {}   # opaque term name -> underlying vars

    def lin(self, t: Term) -> Linear:
        if isinstance(t, Num):
            return {}, t.value
        if isinstance(t, Var):
            return {t.name: Fraction(1)}, Fraction(0)
        if isinstance(t, Neg):
            c, k = self.lin(t.arg)
            return {v: -a for v, a in c.items()}, -k
        if isinstance(t, Arith):
            lc, lk = self.lin(t.left)
            rc, rk = self.lin(t.right)
            if t.op in ("+", "-"):
                s = 1 if t.op == "+" else -1
                out = dict(lc)
                for v, a in rc.items():
                    out[v] = out.get(v, 0) + s * a
                return {v: a for v, a in out.items() if a != 0}, lk + s * rk
            if t.op == "*" and (not lc or not rc):
                (c, k), m = ((rc, rk), lk) if not lc else ((lc, lk), rk)
                return {v: a * m for v, a in c.items() if a * m != 0}, k * m
            if t.op == "/" and not rc and rk != 0:
                return {v: a / rk for v, a in lc.items()}, lk / rk
        if isinstance(t, Abs):
            inner_c, inner_k = self.lin(t.arg)
            if not inner_c:
                return {}, abs(inner_k)
            # canonical sign so that abs(a - b) and abs(b - a) map to the same opaque term
            name = "abs(" + _lin_str(*_normalise_sign(inner_c, inner_k)[:2]) + ")"
            self.opaque_vars[name] = set(inner_c)
            return {name: Fraction(1)}, Fraction(0)
        # Func, products of variables, ...
        name = _opaque_name(t, self.symmetric)
        self.opaque_vars[name] = _opaque_vars(t)
        return {name: Fraction(1)}, Fraction(0)


def _normalise_sign(c: Dict[str, Fraction], k: Fraction):
    """Return (coefs, const, flipped) scaled so the first variable has coefficient +1."""
    first = sorted(c)[0]
    a = c[first]
    flipped = a < 0
    s = abs(a)
    c2 = {v: x / s * (-1 if flipped else 1) for v, x in c.items()}
    k2 = k / s * (-1 if flipped else 1)
    return c2, k2, flipped


def _lin_str(c: Dict[str, Fraction], k: Fraction = Fraction(0)) -> str:
    parts = []
    for v in sorted(c):
        a = c[v]
        coef = "" if abs(a) == 1 else fmt_num(abs(a)) + "*"
        parts.append(("-" if a < 0 else "+") + coef + v)
    s = "".join(parts).lstrip("+")
    if k:
        s += ("+" if k > 0 else "-") + fmt_num(abs(k))
    return s


_FLIP = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}


def _abs_expand(cmp: Cmp, lz: _Linearizer) -> Optional[Formula]:
    """abs(e) op c (c numeric) -> exact Boolean combination of comparisons over e."""
    l, r, op = cmp.left, cmp.right, cmp.op
    if not isinstance(l, Abs) and isinstance(r, Abs):
        l, r, op = r, l, _FLIP[op]
    if not isinstance(l, Abs):
        return None
    rc, rk = lz.lin(r)
    if rc:
        return None
    e, c = l.arg, rk
    N = Num(-c)
    C = Num(c)
    if op == "<":
        return BoolConst(False) if c <= 0 else And((Cmp("<", e, C), Cmp(">", e, N)))
    if op == "<=":
        return BoolConst(False) if c < 0 else And((Cmp("<=", e, C), Cmp(">=", e, N)))
    if op == ">":
        return BoolConst(True) if c < 0 else Or((Cmp(">", e, C), Cmp("<", e, N)))
    if op == ">=":
        return BoolConst(True) if c <= 0 else Or((Cmp(">=", e, C), Cmp("<=", e, N)))
    if op == "==":
        return BoolConst(False) if c < 0 else (Cmp("==", e, C) if c == 0 else Or((Cmp("==", e, C), Cmp("==", e, N))))
    if op == "!=":
        return BoolConst(True) if c < 0 else (Cmp("!=", e, C) if c == 0 else And((Cmp("!=", e, C), Cmp("!=", e, N))))
    return None


@dataclass
class AbstractionResult:
    formulas: List[Formula]
    axioms: List[Formula]
    atom_table: Dict[str, str] = field(default_factory=dict)   # SPOT atom name -> meaning
    exact: bool = True
    inexact_reason: str = ""


class PredicateAbstraction:
    """Shared across gold and prediction so equal predicates map to the same atom."""

    def __init__(self, symmetric: Set[str] = frozenset()):
        self.lz = _Linearizer(set(symmetric))
        self.atoms: Dict[Tuple[str, str, Fraction], str] = {}   # (term, op, rhs) -> name
        self.term_vars: Dict[str, Set[str]] = {}

    def _atom(self, term: str, op: str, rhs: Fraction, vars_: Set[str]) -> Prop:
        key = (term, op, rhs)
        if key not in self.atoms:
            self.atoms[key] = f"{term}{op}{fmt_num(rhs)}"
        self.term_vars.setdefault(term, set()).update(vars_)
        return Prop(self.atoms[key])

    def _cmp(self, n: Cmp) -> Formula:
        expanded = _abs_expand(n, self.lz)
        if expanded is not None:
            return rebuild(expanded, lambda m: self._cmp(m) if isinstance(m, Cmp) else m)
        lc, lk = self.lz.lin(n.left)
        rc, rk = self.lz.lin(n.right)
        c = dict(lc)
        for v, a in rc.items():
            c[v] = c.get(v, 0) - a
        c = {v: a for v, a in c.items() if a != 0}
        k = lk - rk
        op = n.op
        if not c:                                         # constant comparison
            val = {"<": k < 0, "<=": k <= 0, ">": k > 0, ">=": k >= 0, "==": k == 0, "!=": k != 0}[op]
            return BoolConst(val)
        c, k, flipped = _normalise_sign(c, k)
        if flipped:
            op = _FLIP[op]
        term, rhs = _lin_str(c), -k                       # term op rhs
        vars_ = set()
        for v in c:
            vars_ |= self.lz.opaque_vars.get(v, {v})
        gt = lambda: self._atom(term, ">", rhs, vars_)
        ge = lambda: self._atom(term, ">=", rhs, vars_)
        if op == ">":
            return gt()
        if op == ">=":
            return ge()
        if op == "<":
            return Not(ge())
        if op == "<=":
            return Not(gt())
        if op == "==":
            return And((ge(), Not(gt())))
        return Or((Not(ge()), gt()))                      # !=

    def abstract(self, f: Formula) -> Formula:
        def fn(n):
            if isinstance(n, Cmp):
                return self._cmp(n)
            if isinstance(n, PredApp):
                args = tuple(canon_term(a, self.lz.symmetric) for a in n.args)
                if n.name in self.lz.symmetric and len(args) == 2:
                    args = tuple(sorted(args, key=term_str))
                return Prop(f"{n.name}({','.join(term_str(a) for a in args)})")
            return n
        return rebuild(f, fn)

    def axioms(self) -> List[Formula]:
        by_term: Dict[str, List[Tuple[str, Fraction, str]]] = {}
        for (term, op, rhs), name in self.atoms.items():
            by_term.setdefault(term, []).append((op, rhs, name))
        out = []
        for term, atoms in by_term.items():
            for op1, r1, n1 in atoms:
                for op2, r2, n2 in atoms:
                    if n1 == n2:
                        continue
                    # sat(op1, r1) ⊆ sat(op2, r2)   with sat(>, r) = (r, ∞), sat(>=, r) = [r, ∞)
                    if op1 == ">=" and op2 == ">":
                        sub = r1 > r2
                    else:
                        sub = r1 >= r2
                    if sub:
                        out.append(Unary("G", Interval(), Implies(Prop(n1), Prop(n2))))
        return out

    def exactness(self) -> Tuple[bool, str]:
        seen: Dict[str, str] = {}
        for term, vs in self.term_vars.items():
            for v in vs:
                if v in seen and seen[v] != term:
                    return False, f"variable '{v}' occurs in different arithmetic terms ('{seen[v]}', '{term}')"
                seen[v] = term
        return True, ""

    def run(self, formulas: List[Formula]) -> AbstractionResult:
        out = [self.abstract(f) for f in formulas]
        exact, why = self.exactness()
        table = {name: f"{t} {op} {fmt_num(r)}" for (t, op, r), name in self.atoms.items()}
        return AbstractionResult(out, self.axioms(), table, exact, why)
