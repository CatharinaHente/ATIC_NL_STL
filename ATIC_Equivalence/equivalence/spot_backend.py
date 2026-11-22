"""
SPOT backend: exact discrete-time encoding of (bounded and unbounded) STL into LTL.

LTL's G, F, U *are* the unbounded operators (over infinite traces).  What LTL lacks are
time bounds; in discrete time those are expressible with X ("next"):

    F[a,b] φ   =  X^a (φ ∨ Xφ ∨ … ∨ X^(b-a) φ)      (SPOT sugar: F[a:b])
    G[a,b] φ   =  X^a (φ ∧ Xφ ∧ … ∧ X^(b-a) φ)      (SPOT sugar: G[a:b])
    φ U[0,b] ψ =  (φ U ψ) ∧ F[0,b] ψ
    φ U[a,b] ψ =  G[0,a-1] φ ∧ X^a((φ U ψ) ∧ F[0,b-a] ψ)          (a > 0)
    φ R[a,b] ψ =  ¬(¬φ U[a,b] ¬ψ)

so nothing is stripped (the old pipeline deleted all bounds, making F[0,15] ≡ F[0,20]).
Large bounds give large automata — that is the price of exactness and shows up as runtime.

Atoms are always double-quoted: unquoted, SPOT parses `Fsig` as F(sig) and `Xa` as X(a).

Each check runs in a separate worker process so a hard time-out can actually interrupt
SPOT's C++ code (a SIGALRM in the same process cannot).
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from fractions import Fraction
from typing import List, Optional

from .ast import (And, Binary, BoolConst, Formula, Iff, Implies, Interval, Not, Or, Prop,
                  Unary)
from .past import Definition, Unsupported


# --------------------------------------------------------------------------
# Emission
# --------------------------------------------------------------------------

def _int(b, what) -> int:
    if not isinstance(b, Fraction):
        raise Unsupported(f"symbolic time bound '{b}' in {what}")
    if b.denominator != 1:
        raise Unsupported(f"non-integer time bound {b} in {what}")
    return int(b)


def _x(n: int, s: str) -> str:
    return s if n == 0 else f"X[{n}]({s})"


def emit(f: Formula) -> str:
    if isinstance(f, BoolConst):
        return "1" if f.value else "0"
    if isinstance(f, Prop):
        if '"' in f.name:
            raise Unsupported("atom name contains a double quote")
        return f'"{f.name}"'
    if isinstance(f, Not):
        return f"!({emit(f.arg)})"
    if isinstance(f, And):
        return "(" + " & ".join(f"({emit(a)})" for a in f.args) + ")"
    if isinstance(f, Or):
        return "(" + " | ".join(f"({emit(a)})" for a in f.args) + ")"
    if isinstance(f, Implies):
        return f"(({emit(f.left)}) -> ({emit(f.right)}))"
    if isinstance(f, Iff):
        return f"(({emit(f.left)}) <-> ({emit(f.right)}))"
    if isinstance(f, Unary):
        a = emit(f.arg)
        if f.op == "X":
            return f"X({a})"
        if f.op not in ("G", "F"):
            raise Unsupported(f"operator {f.op} must be eliminated before SPOT emission")
        lo = _int(f.interval.lo, f.op)
        if f.interval.hi is None:
            return _x(lo, f"{f.op}({a})")
        hi = _int(f.interval.hi, f.op)
        if lo == hi:
            return _x(lo, a)
        return f"{f.op}[{lo}:{hi}]({a})"
    if isinstance(f, Binary):
        l, r = emit(f.left), emit(f.right)
        if f.op == "R":
            return emit(Not(Binary("U", f.interval, Not(f.left), Not(f.right))))
        if f.op == "W":
            if not f.interval.is_full:
                raise Unsupported("bounded weak-until W[a,b]")
            return f"(({l}) W ({r}))"
        if f.op != "U":
            raise Unsupported(f"operator {f.op} must be eliminated before SPOT emission")
        lo = _int(f.interval.lo, "U")
        hi = None if f.interval.hi is None else _int(f.interval.hi, "U")
        until = f"(({l}) U ({r}))"
        if hi is None:
            if lo == 0:
                return until
            return f"(G[0:{lo - 1}]({l}) & {_x(lo, until)})"
        core = f"({until} & {'F[0:%d](%s)' % (hi - lo, r) if hi > lo else '(' + r + ')'})"
        if lo == 0:
            return core
        return f"(G[0:{lo - 1}]({l}) & {_x(lo, core)})"
    raise Unsupported(f"cannot emit {type(f).__name__} to SPOT")


def emit_definitions(defs: List[Definition]) -> List[str]:
    out = []
    for d in defs:
        y, e = emit(Prop(d.aux)), emit(d.expr)
        if d.kind == "Y":
            out.append(f"(!{y} & G(X({y}) <-> ({e})))")
        else:
            out.append(f"G(({y}) <-> ({e}))")
    return out


# --------------------------------------------------------------------------
# Worker process (hard timeouts)
# --------------------------------------------------------------------------
# A plain subprocess speaking JSON lines (see _spot_worker.py).  Unlike multiprocessing
# 'spawn' this does not re-import the caller's __main__, so it works from scripts without
# a main guard and from notebooks.

class SpotWorker:
    STARTUP_TIMEOUT = 60.0

    def __init__(self):
        self._proc = None

    def _start(self):
        env = dict(os.environ)
        pkg_parent = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = pkg_parent + os.pathsep + env.get("PYTHONPATH", "")
        self._proc = subprocess.Popen([sys.executable, "-u", "-m", "equivalence._spot_worker"],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, env=env)
        # warm-up so that 'import spot' is not charged to the first check
        if self._request(["1", "1"], self.STARTUP_TIMEOUT) is None:
            err = self._proc.stderr.read() if self._proc.poll() is not None else "no answer"
            self.close(kill=True)
            raise RuntimeError(f"SPOT worker failed to start: {err[-500:]}")

    def _request(self, payload, timeout: float):
        try:
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return None
        ready, _, _ = select.select([self._proc.stdout], [], [], timeout)
        if not ready:
            return None
        line = self._proc.stdout.readline()
        return json.loads(line) if line else None

    def check(self, gold: str, pred: str, timeout: float):
        if self._proc is None or self._proc.poll() is not None:
            self._start()
        t0 = time.perf_counter()
        res = self._request([gold, pred], timeout)
        wall = (time.perf_counter() - t0) * 1000
        if res is None:
            self.close(kill=True)
            return ("timeout", wall)
        return tuple(res) + (wall,)

    def close(self, kill: bool = False):
        if self._proc is None:
            return
        try:
            if kill or self._proc.poll() is not None:
                self._proc.kill()
            else:
                self._proc.stdin.close()
                self._proc.wait(2)
        except Exception:
            self._proc.kill()
        finally:
            self._proc = None


@dataclass
class SpotQuery:
    gold: str           # full SPOT formula (with constraints/axioms conjoined)
    pred: str


def build_query(gold: Formula, pred: Formula, defs: List[Definition], axioms: List[Formula]) -> SpotQuery:
    side = emit_definitions(defs) + [emit(a) for a in axioms]
    g, p = emit(gold), emit(pred)
    if side:
        A = " & ".join(side)
        g, p = f"({A}) & ({g})", f"({A}) & ({p})"
    return SpotQuery(g, p)
