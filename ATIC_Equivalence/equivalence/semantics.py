"""
Until/Release semantics in discrete time.

There are two discrete-time readings of φ U[a,b] ψ that coincide in dense time:

  standard   ∃t'∈[a,b]: ψ(t') ∧ ∀t''∈[0,t')  φ(t'')     (RTAMT, textbook discrete STL, SPOT's U)
  inclusive  ∃t'∈[a,b]: ψ(t') ∧ ∀t''∈[0,t']  φ(t'')     (STLSat's native U — verified empirically)

Both tools must decide the *same* semantics, so the pipeline fixes one (Config.until_semantics,
default "standard") and rewrites U/R exactly into the other tool's native operator:

  standard -> inclusive (for STLSat):
      φ U_s[0,b] ψ  ≡  (φ ∨ ψ) U_i[0,b] ψ
      φ U_s[a,b] ψ  ≡  G[0,a-1] φ  ∧  F[a,a]( (φ ∨ ψ) U_i[0,b-a] ψ )          (a > 0)
  inclusive -> standard (for SPOT):
      φ U_i[0,b] ψ  ≡  φ U_s[0,b] (φ ∧ ψ)
      φ U_i[a,b] ψ  ≡  G[0,a-1] φ  ∧  X^a( φ U_s[0,b-a] (φ ∧ ψ) )              (a > 0)
  and in both readings  φ R ψ ≡ ¬(¬φ U ¬ψ).

(Proof sketch of the first identity: given a standard witness, take the *first* ψ-time t0;
φ holds before it and ψ at it, so φ ∨ ψ holds on [0,t0].  Conversely, from an inclusive
witness t'', the first ψ-time t0 ≤ t'' has φ on [0,t0).  For a > 0 the prefix is split off
so the first-ψ argument is only applied inside [a,b].)
"""
from __future__ import annotations

from fractions import Fraction

from .ast import And, Binary, Formula, Interval, Not, Or, Unary, rebuild
from .past import Unsupported


def _split(iv: Interval):
    if not iv.is_numeric:
        raise Unsupported(f"symbolic time bound in until {iv}")
    lo = int(iv.lo)
    hi = None if iv.hi is None else int(iv.hi)
    return lo, hi


def _shift(lo: int, f: Formula) -> Formula:
    return f if lo == 0 else Unary("F", Interval(Fraction(lo), Fraction(lo)), f)


def _prefix(lo: int, phi: Formula):
    return [] if lo == 0 else [Unary("G", Interval(Fraction(0), Fraction(lo - 1)), phi)]


def _rest(hi, lo):
    return Interval(Fraction(0), None if hi is None else Fraction(hi - lo))


def release_to_until(f: Formula) -> Formula:
    def fn(n):
        if isinstance(n, Binary) and n.op == "R":
            return Not(Binary("U", n.interval, Not(n.left), Not(n.right)))
        return n
    return rebuild(f, fn)


def standard_to_inclusive(f: Formula) -> Formula:
    """Rewrite standard-semantics U/R into STLSat-native (inclusive) U."""
    f = release_to_until(f)

    def fn(n):
        if isinstance(n, Binary) and n.op == "U":
            lo, hi = _split(n.interval)
            core = Binary("U", _rest(hi, lo), Or((n.left, n.right)), n.right)
            parts = _prefix(lo, n.left) + [_shift(lo, core)]
            return parts[0] if len(parts) == 1 else And(tuple(parts))
        return n
    return rebuild(f, fn)


def inclusive_to_standard(f: Formula) -> Formula:
    """Rewrite inclusive-semantics U/R into standard U (for SPOT)."""
    f = release_to_until(f)

    def fn(n):
        if isinstance(n, Binary) and n.op == "U":
            lo, hi = _split(n.interval)
            core = Binary("U", _rest(hi, lo), n.left, And((n.left, n.right)))
            parts = _prefix(lo, n.left) + [_shift(lo, core)]
            return parts[0] if len(parts) == 1 else And(tuple(parts))
        return n
    return rebuild(f, fn)
