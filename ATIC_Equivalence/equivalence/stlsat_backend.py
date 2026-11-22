"""
STLSat backend (bounded, discrete-time STL satisfiability via tableau / SMT).

Containment is decided with two satisfiability queries instead of one XOR query:

    gold ⊆ pred   iff   A ∧ gold ∧ ¬pred   is UNSAT
    pred ⊆ gold   iff   A ∧ pred ∧ ¬gold   is UNSAT

which yields EQUIVALENT / PRED_STRONGER / PRED_WEAKER / INCOMPARABLE for the same price
as an equivalence check (the XOR query is just the disjunction of the two).

Unbounded operators are not supported by STLSat.  They are capped with a per-pair horizon
H = factor · B + minimum, where B is the largest finite future horizon occurring in the pair.
Because H > B, a bounded operator in one formula can never coincide with a capped one
in the other.  Results obtained this way are flagged `bounded_approx` — they decide
equivalence on the horizon-capped formulas, not on the originals.

Facts checked against the installed binary (see README):
  * discrete time; `a U[a,b] b` requires `a` from time 0 (standard non-strict until)
  * `a` (Boolean) and `a == 1` (real) are *different* variables
  * output line "… result: Some(true|false)" plus "DURATION_SEC: <solver seconds>"
  * identifiers may not start with '_'; terms may not start with unary '-'
  * BUG: literals in (-1, 0) lose their sign (`z == -0.5 && z == 0.5` is SAT) -> emitted as (0 - c)
  * BUG: the tableau engine answers SAT on some UNSAT inputs (see README); smt/fol do not
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import List, Optional

from .ast import (Abs, And, Arith, Binary, BoolConst, Cmp, Formula, Func, Iff, Implies,
                  Interval, Neg, Not, Num, Or, PredApp, Prop, Term, Unary, Var,
                  future_horizon, rebuild, term_str)
from .past import Definition, Unsupported


# --------------------------------------------------------------------------
# Unbounded -> horizon
# --------------------------------------------------------------------------

def has_unbounded(f: Formula) -> bool:
    from .ast import walk
    return any(isinstance(n, (Unary, Binary)) and n.op in ("G", "F", "U", "R", "W")
               and n.interval.hi is None for n in walk(f))


def pair_horizon(formulas, factor: float, minimum: int) -> int:
    B = max(int(future_horizon(f, unbounded_as=0)) for f in formulas)
    return int(factor * B) + minimum


def cap_unbounded(f: Formula, H: int) -> Formula:
    def cap(iv: Interval) -> Interval:
        if iv.hi is not None:
            return iv
        lo = iv.lo if isinstance(iv.lo, Fraction) else Fraction(0)
        return Interval(iv.lo, lo + H)

    def fn(n):
        if isinstance(n, Unary) and n.op in ("G", "F") and n.interval.hi is None:
            return Unary(n.op, cap(n.interval), n.arg)
        if isinstance(n, Binary) and n.op in ("U", "R") and n.interval.hi is None:
            return Binary(n.op, cap(n.interval), n.left, n.right)
        if isinstance(n, Binary) and n.op == "W":
            if not n.interval.is_full:
                raise Unsupported("bounded weak-until W[a,b]")
            iv = Interval(Fraction(0), Fraction(H))
            return Or((Binary("U", iv, n.left, n.right), Unary("G", iv, n.left)))
        return n
    return rebuild(f, fn)


# --------------------------------------------------------------------------
# Emission
# --------------------------------------------------------------------------

def _ident(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    if not s or not (s[0].isalpha()):
        s = "v_" + s
    return s


def _num(v: Fraction) -> str:
    # STLSat bug (verified): a literal in (-1, 0) loses its sign, `-0.5` is read as `0.5`.
    # Negative constants are therefore always emitted as `(0 - c)`.
    if v < 0:
        return f"(0 - {_num(-v)})"
    if v.denominator == 1:
        return str(v.numerator)
    d = float(v)
    if Fraction(repr(d)) != v:
        raise Unsupported(f"constant {v} has no exact decimal representation")
    return repr(d)


def emit_term(t: Term) -> str:
    if isinstance(t, Num):
        return _num(t.value)
    if isinstance(t, Var):
        return _ident(t.name)
    if isinstance(t, Func):
        return _ident(term_str(t))           # uninterpreted -> opaque real variable
    if isinstance(t, Abs):
        return f"|{emit_term(t.arg)}|"
    if isinstance(t, Neg):
        return f"(0 - {emit_term(t.arg)})"
    if isinstance(t, Arith):
        if t.op in ("+", "-"):
            return f"({emit_term(t.left)} {t.op} {emit_term(t.right)})"
        raise Unsupported(f"STLSat does not support '{t.op}' in arithmetic terms")
    raise Unsupported(f"cannot emit term {t}")


def _iv(iv: Interval, op: str) -> str:
    for b in (iv.lo, iv.hi):
        if b is None:
            raise Unsupported(f"unbounded {op} reached STLSat emission")
        if not isinstance(b, Fraction):
            raise Unsupported(f"symbolic time bound '{b}' (STLSat needs integer bounds)")
        if b.denominator != 1:
            raise Unsupported(f"non-integer time bound {b}")
    return f"[{int(iv.lo)},{int(iv.hi)}]"


def emit(f: Formula) -> str:
    if isinstance(f, BoolConst):
        return "true" if f.value else "false"
    if isinstance(f, Prop):
        return _ident(f.name)
    if isinstance(f, PredApp):
        return _ident(f"{f.name}_{'_'.join(term_str(a) for a in f.args)}")
    if isinstance(f, Cmp):
        return f"({emit_term(f.left)} {f.op} {emit_term(f.right)})"
    if isinstance(f, Not):
        return f"!({emit(f.arg)})"
    if isinstance(f, And):
        return "(" + " && ".join(f"({emit(a)})" for a in f.args) + ")"
    if isinstance(f, Or):
        return "(" + " || ".join(f"({emit(a)})" for a in f.args) + ")"
    if isinstance(f, Implies):
        return f"(({emit(f.left)}) -> ({emit(f.right)}))"
    if isinstance(f, Iff):
        return f"(({emit(f.left)}) <-> ({emit(f.right)}))"
    if isinstance(f, Unary):
        if f.op == "X":
            return f"(F[1,1] ({emit(f.arg)}))"
        if f.op in ("G", "F"):
            return f"({f.op}{_iv(f.interval, f.op)} ({emit(f.arg)}))"
    if isinstance(f, Binary) and f.op in ("U", "R"):
        return f"(({emit(f.left)}) {f.op}{_iv(f.interval, f.op)} ({emit(f.right)}))"
    raise Unsupported(f"cannot emit {type(f).__name__} {getattr(f, 'op', '')} to STLSat")


def emit_definitions(defs: List[Definition], T: int) -> List[str]:
    out = []
    for d in defs:
        y, e = _ident(d.aux), emit(d.expr)
        if d.kind == "Y":
            step = f" && (G[0,{T - 1}] ((F[1,1] ({y})) <-> ({e})))" if T >= 1 else ""
            out.append(f"(!({y}){step})")
        else:
            out.append(f"(G[0,{T}] (({y}) <-> ({e})))")
    return out


def definitions_horizon(cores: List[Formula], defs: List[Definition]) -> int:
    R = max(int(future_horizon(c)) for c in cores)
    return R + sum(int(future_horizon(d.expr)) for d in defs) + (1 if defs else 0)


# --------------------------------------------------------------------------
# Running the binary
# --------------------------------------------------------------------------

def find_stlsat() -> str:
    path = shutil.which("stlsat")
    if path:
        return path
    fallback = Path.home() / ".cargo" / "bin" / "stlsat"
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError("stlsat binary not found (cargo install --path <stlsat repo>; add ~/.cargo/bin to PATH)")


_RESULT_RE = re.compile(r"result:\s*(Some\((true|false)\)|None)")
_DUR_RE = re.compile(r"DURATION_SEC:\s*([0-9.eE+-]+)")


@dataclass
class SatResult:
    status: str            # "SAT" | "UNSAT" | "UNKNOWN" | "TIMEOUT" | "ERROR"
    solver_ms: Optional[float]
    wall_ms: float
    detail: str = ""


def run_sat(formula: str, engine: str = "tableau", timeout: float = 30.0, binary: Optional[str] = None) -> SatResult:
    binary = binary or find_stlsat()
    with tempfile.NamedTemporaryFile("w", suffix=".stl", delete=False) as tmp:
        tmp.write(formula + "\n")
        path = tmp.name
    t0 = time.perf_counter()
    try:
        proc = subprocess.run([binary, "--engine", engine, path], capture_output=True, text=True, timeout=timeout)
        wall = (time.perf_counter() - t0) * 1000
        out = proc.stdout + proc.stderr
        m, d = _RESULT_RE.search(out), _DUR_RE.search(out)
        solver_ms = float(d.group(1)) * 1000 if d else None
        if not m:
            msg = next((ln for ln in out.splitlines() if "error" in ln.lower() or "panicked" in ln.lower()), out.strip()[:200])
            return SatResult("ERROR", solver_ms, wall, msg.strip()[:300])
        if m.group(1) == "None":
            return SatResult("UNKNOWN", solver_ms, wall, "solver returned None")
        return SatResult("SAT" if m.group(2) == "true" else "UNSAT", solver_ms, wall)
    except subprocess.TimeoutExpired:
        return SatResult("TIMEOUT", None, (time.perf_counter() - t0) * 1000, f"timed out after {timeout}s")
    finally:
        Path(path).unlink(missing_ok=True)


def build_queries(gold: Formula, pred: Formula, defs: List[Definition]):
    """Return (query gold∧¬pred, query pred∧¬gold, horizon used for definitions)."""
    T = definitions_horizon([gold, pred], defs) if defs else 0
    side = emit_definitions(defs, T)
    g, p = emit(gold), emit(pred)
    prefix = (" && ".join(side) + " && ") if side else ""
    return f"{prefix}({g}) && !({p})", f"{prefix}({p}) && !({g})", T
