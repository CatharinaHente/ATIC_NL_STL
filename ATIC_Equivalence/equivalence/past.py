"""
Exact elimination of past-time operators and rise/fall edges.

Neither SPOT (future LTL only — `Yfault` is parsed as an unrelated atom called "Yfault")
nor STLSat (bounded future STL) understands past operators.  We remove them exactly:

Every past construct is rewritten using only the strong "yesterday" Y, and every Y φ is
replaced by a fresh auxiliary atom y with a defining constraint:

    YDef  y ≡ Y φ        :   ¬y  ∧  G( X y ↔ φ )                    (Y is false at t = 0)
    EqDef s ≡ expr       :   G( s ↔ expr )                           (expr may mention Y-atoms)

Rewrite rules (discrete time, standard strict-past semantics):
    rise(φ)        = φ ∧ ¬Yφ                  fall(φ) = ¬φ ∧ Yφ
                     (Y is false at t = 0, i.e. signals are taken to be false before the trace starts:
                      rise(φ) holds at 0 iff φ(0); fall(φ) never holds at 0)
    O[a,b] φ       = ⋁_{k=a..b} Y^k φ
    O[a,∞) φ       = Y^a s,     s ≡ φ ∨ Y s
    H[a,b] φ       = ¬O[a,b]¬φ                (vacuously true before time a)
    φ S ψ          = s,         s ≡ ψ ∨ (φ ∧ Y s)
    φ S[a,b] ψ     = ⋁_{k=a..b} ( Y^k ψ ∧ ⋀_{j=0..k-1} Y^j φ )
    φ S[a,∞) ψ     = ⋀_{j=0..a-1} Y^j φ  ∧  Y^a(φ S ψ)

The constraints determine every auxiliary atom uniquely from the original signals, hence

    gold ≡ pred      iff      (A ∧ gold') ≡ (A ∧ pred')      where A = conjunction of definitions,

i.e. the encoding is exact, not an abstraction.  One eliminator is shared by gold and
prediction so identical sub-formulas get the same auxiliary atom.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List

from .ast import (And, Binary, BoolConst, Edge, Formula, Interval, Not, Or, Prop, Unary,
                  mk_and, mk_or, rebuild, to_str)


class Unsupported(Exception):
    pass


@dataclass(frozen=True)
class Definition:
    aux: str
    kind: str          # "Y" | "EQ"
    expr: Formula      # past-free


class PastEliminator:
    PREFIX = "aux__"

    def __init__(self, max_aux: int = 2000):
        self.defs: List[Definition] = []
        self._cache: Dict[tuple, Prop] = {}
        self.max_aux = max_aux

    # -- helpers ---------------------------------------------------------
    def _fresh(self, kind: str, expr: Formula, key=None) -> Prop:
        key = key or (kind, to_str(expr))
        if key in self._cache:
            return self._cache[key]
        if len(self.defs) >= self.max_aux:
            raise Unsupported(f"past-operator encoding needs more than {self.max_aux} auxiliary atoms")
        p = Prop(f"{self.PREFIX}{len(self.defs)}")
        self._cache[key] = p
        self.defs.append(Definition(p.name, kind, expr))
        return p

    def Y(self, phi: Formula, k: int = 1) -> Formula:
        for _ in range(k):
            if isinstance(phi, BoolConst) and not phi.value:
                continue                      # Y false == false
            phi = self._fresh("Y", phi)
        return phi

    def _recursive(self, tag: str, build) -> Prop:
        """s ≡ build(Y s): allocate s first, then its definition."""
        key = ("EQ", tag)
        if key in self._cache:
            return self._cache[key]
        s = Prop(f"{self.PREFIX}{len(self.defs)}")
        self._cache[key] = s
        self.defs.append(None)                # placeholder keeps numbering stable
        idx = len(self.defs) - 1
        self.defs[idx] = Definition(s.name, "EQ", build(self.Y(s)))
        return s

    @staticmethod
    def _numeric(iv: Interval, op: str):
        if not iv.is_numeric:
            raise Unsupported(f"symbolic bound in past operator {op}{iv}")
        lo = int(iv.lo)
        hi = None if iv.hi is None else int(iv.hi)
        if iv.lo != lo or (iv.hi is not None and iv.hi != hi):
            raise Unsupported("non-integer past bound")
        return lo, hi

    def once(self, phi: Formula, iv: Interval) -> Formula:
        lo, hi = self._numeric(iv, "O")
        if hi is None:
            s = self._recursive(("O", to_str(phi)), lambda ys: mk_or((phi, ys)))
            return self.Y(s, lo)
        return mk_or(self.Y(phi, k) for k in range(lo, hi + 1))

    def since(self, phi: Formula, psi: Formula, iv: Interval) -> Formula:
        lo, hi = self._numeric(iv, "S")
        if hi is None:
            s = self._recursive(("S", to_str(phi), to_str(psi)),
                                lambda ys: mk_or((psi, mk_and((phi, ys)))))
            if lo == 0:
                return s
            return mk_and([self.Y(phi, j) for j in range(lo)] + [self.Y(s, lo)])
        return mk_or(mk_and([self.Y(psi, k)] + [self.Y(phi, j) for j in range(k)])
                     for k in range(lo, hi + 1))

    # -- main entry --------------------------------------------------------
    def eliminate(self, f: Formula) -> Formula:
        def fn(n: Formula) -> Formula:
            if isinstance(n, Edge):
                yphi = self.Y(n.arg)
                return mk_and((n.arg, Not(yphi))) if n.kind == "rise" else mk_and((Not(n.arg), yphi))
            if isinstance(n, Unary) and n.op == "Y":
                return self.Y(n.arg)
            if isinstance(n, Unary) and n.op == "O":
                return self.once(n.arg, n.interval)
            if isinstance(n, Unary) and n.op == "H":
                return Not(self.once(Not(n.arg), n.interval))
            if isinstance(n, Binary) and n.op == "S":
                return self.since(n.left, n.right, n.interval)
            return n
        return rebuild(f, fn)

    @property
    def has_defs(self) -> bool:
        return bool(self.defs)


def has_past(f: Formula) -> bool:
    from .ast import walk
    return any(isinstance(n, Edge) or (isinstance(n, Unary) and n.op in ("H", "O", "Y"))
               or (isinstance(n, Binary) and n.op == "S") for n in walk(f))
