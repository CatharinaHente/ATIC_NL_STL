"""
Per-pair equivalence checking: parse -> normalise -> {syntactic, SPOT, STLSat}.

Verdicts (prediction relative to gold):
    EQUIVALENT      gold ⊆ pred and pred ⊆ gold
    PRED_STRONGER   pred ⊆ gold only      (prediction is stricter / admits fewer traces)
    PRED_WEAKER     gold ⊆ pred only      (prediction is looser / admits more traces)
    INCOMPARABLE    neither

Status per tool:  OK | UNSUPPORTED | PARSE_ERROR | TIMEOUT | TOOL_ERROR
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set

from .ast import Indexed, intervals, to_str, walk
from .atoms import PredicateAbstraction
from .normalize import canonical, normalise_pair
from .parser import ParseError, parse
from .past import Definition, PastEliminator, Unsupported, has_past
from . import semantics, spot_backend, stlsat_backend


@dataclass
class Config:
    run_spot: bool = True
    run_stlsat: bool = True
    spot_timeout: float = 30.0
    stlsat_timeout: float = 30.0
    stlsat_engine: str = "smt"               # smt | fol | tableau  (tableau is unsound on some inputs, see README)
    horizon_factor: float = 2.0              # STLSat cap for unbounded ops: factor * B + minimum
    horizon_minimum: int = 10
    until_semantics: str = "standard"        # standard (φ on [0,t')) | inclusive (φ on [0,t'], STLSat-native)
    symmetric_functions: Set[str] = field(default_factory=lambda: {"distance"})


def verdict(gold_in_pred: Optional[bool], pred_in_gold: Optional[bool]) -> Optional[str]:
    if gold_in_pred is None or pred_in_gold is None:
        return None
    return {(True, True): "EQUIVALENT", (False, True): "PRED_STRONGER",
            (True, False): "PRED_WEAKER", (False, False): "INCOMPARABLE"}[(gold_in_pred, pred_in_gold)]


def _features(g, p) -> Dict:
    nodes = list(walk(g)) + list(walk(p))
    ivs = list(intervals(g)) + list(intervals(p))
    return {
        "has_past_or_edge": has_past(g) or has_past(p),
        "has_unbounded": any(iv.hi is None for iv in ivs),
        "has_symbolic_bound": any(not iv.is_numeric for iv in ivs),
        "has_parametric": any(isinstance(n, Indexed) for n in nodes),
        "max_bound": max([int(b) for iv in ivs for b in (iv.lo, iv.hi)
                          if b is not None and not isinstance(b, str)] or [0]),
    }


def _unsupported_common(g, p) -> Optional[str]:
    for f in (g, p):
        for n in walk(f):
            if isinstance(n, Indexed):
                return f"parametric operator {n.kind}_{n.index}(...)"
    return None


class Checker:
    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or Config()
        self._spot = spot_backend.SpotWorker() if self.cfg.run_spot else None

    def close(self):
        if self._spot:
            self._spot.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # ------------------------------------------------------------------
    def check(self, gold: str, pred: str, context: Optional[str] = None) -> Dict:
        cfg = self.cfg
        row: Dict = {}
        # ---- parse ----
        try:
            g0, p0 = parse(gold), parse(pred)
        except ParseError as e:
            row.update(parse_ok=False, parse_error=str(e))
            for tool in ("spot", "stlsat"):
                row[f"{tool}_status"] = "PARSE_ERROR"
            return row
        row["parse_ok"] = True

        # ---- normalise ----
        t0 = time.perf_counter()
        norm = normalise_pair(g0, p0, context)
        g, p = norm.gold, norm.pred
        cg, cp = canonical(g, cfg.symmetric_functions), canonical(p, cfg.symmetric_functions)
        row.update(
            gold_norm=to_str(g), pred_norm=to_str(p),
            types_source=norm.env.source, time_scale=norm.time_scale,
            norm_notes="; ".join(norm.notes),
            syntactic_equal=to_str(cg) == to_str(cp),
            syntactic_ms=(time.perf_counter() - t0) * 1000,
        )
        row.update(_features(g, p))
        common = _unsupported_common(g, p)

        if cfg.run_spot:
            row.update(self._run_spot(g, p, common))
        if cfg.run_stlsat:
            row.update(self._run_stlsat(g, p, common))
        return row

    # ------------------------------------------------------------------
    def _run_spot(self, g, p, common) -> Dict:
        out = {"spot_status": None, "spot_verdict": None, "spot_gold_in_pred": None,
               "spot_pred_in_gold": None, "spot_exact": None, "spot_ms": None,
               "spot_wall_ms": None, "spot_prep_ms": None, "spot_detail": ""}
        if common:
            out.update(spot_status="UNSUPPORTED", spot_detail=common)
            return out
        try:
            t0 = time.perf_counter()
            pe = PastEliminator()
            ge, pe_ = pe.eliminate(g), pe.eliminate(p)
            if self.cfg.until_semantics == "inclusive":
                ge, pe_ = semantics.inclusive_to_standard(ge), semantics.inclusive_to_standard(pe_)
            pa = PredicateAbstraction(self.cfg.symmetric_functions)
            ga, pa_ = pa.abstract(ge), pa.abstract(pe_)
            # constraint definitions may contain comparisons too (e.g. rise(x > 5))
            defs = [Definition(d.aux, d.kind, pa.abstract(d.expr)) for d in pe.defs]
            exact, why = pa.exactness()
            q = spot_backend.build_query(ga, pa_, defs, pa.axioms())
            out["spot_prep_ms"] = (time.perf_counter() - t0) * 1000
        except Unsupported as e:
            out.update(spot_status="UNSUPPORTED", spot_detail=str(e))
            return out
        out["spot_exact"] = exact
        if not exact:
            out["spot_detail"] = "predicate abstraction is an over-approximation: " + why
        res = self._spot.check(q.gold, q.pred, self.cfg.spot_timeout)
        if res[0] == "timeout":
            out.update(spot_status="TIMEOUT", spot_wall_ms=res[1],
                       spot_detail=f"timed out after {self.cfg.spot_timeout}s")
        elif res[0] == "error":
            out.update(spot_status="TOOL_ERROR", spot_detail=res[1], spot_wall_ms=res[2])
        else:
            _, gp, pg, ms, wall = res
            v = verdict(gp, pg)
            if not exact and v != "EQUIVALENT":
                out["spot_detail"] += " (negative containment results may be spurious)"
            out.update(spot_status="OK", spot_gold_in_pred=gp, spot_pred_in_gold=pg,
                       spot_verdict=v, spot_ms=ms, spot_wall_ms=wall)
        return out

    # ------------------------------------------------------------------
    def _run_stlsat(self, g, p, common) -> Dict:
        out = {"stlsat_status": None, "stlsat_verdict": None, "stlsat_gold_in_pred": None,
               "stlsat_pred_in_gold": None, "stlsat_bounded_approx": None, "stlsat_horizon": None,
               "stlsat_ms": None, "stlsat_wall_ms": None, "stlsat_detail": ""}
        if common:
            out.update(stlsat_status="UNSUPPORTED", stlsat_detail=common)
            return out
        try:
            approx = stlsat_backend.has_unbounded(g) or stlsat_backend.has_unbounded(p)
            if approx:
                H = stlsat_backend.pair_horizon([g, p], self.cfg.horizon_factor, self.cfg.horizon_minimum)
                g, p = stlsat_backend.cap_unbounded(g, H), stlsat_backend.cap_unbounded(p, H)
                out["stlsat_horizon"] = H
            out["stlsat_bounded_approx"] = approx
            pe = PastEliminator()
            ge, pe_ = pe.eliminate(g), pe.eliminate(p)
            if self.cfg.until_semantics == "standard":
                ge, pe_ = semantics.standard_to_inclusive(ge), semantics.standard_to_inclusive(pe_)
                pe.defs[:] = [Definition(d.aux, d.kind, semantics.standard_to_inclusive(d.expr)) for d in pe.defs]
            q1, q2, _T = stlsat_backend.build_queries(ge, pe_, pe.defs)
        except Unsupported as e:
            out.update(stlsat_status="UNSUPPORTED", stlsat_detail=str(e))
            return out
        except ValueError as e:                        # symbolic bound in horizon computation
            out.update(stlsat_status="UNSUPPORTED", stlsat_detail=f"symbolic time bound ({e})")
            return out

        r1 = stlsat_backend.run_sat(q1, self.cfg.stlsat_engine, self.cfg.stlsat_timeout)   # gold ∧ ¬pred
        r2 = stlsat_backend.run_sat(q2, self.cfg.stlsat_engine, self.cfg.stlsat_timeout)   # pred ∧ ¬gold
        out["stlsat_wall_ms"] = r1.wall_ms + r2.wall_ms
        if r1.solver_ms is not None and r2.solver_ms is not None:
            out["stlsat_ms"] = r1.solver_ms + r2.solver_ms
        bad = [r for r in (r1, r2) if r.status not in ("SAT", "UNSAT")]
        if bad:
            st = "TIMEOUT" if any(r.status == "TIMEOUT" for r in bad) else "TOOL_ERROR"
            out.update(stlsat_status=st, stlsat_detail="; ".join(f"{r.status}: {r.detail}" for r in bad))
            # partial information is still useful: a SAT answer refutes one containment
            out["stlsat_gold_in_pred"] = None if r1.status not in ("SAT", "UNSAT") else r1.status == "UNSAT"
            out["stlsat_pred_in_gold"] = None if r2.status not in ("SAT", "UNSAT") else r2.status == "UNSAT"
            return out
        gp, pg = r1.status == "UNSAT", r2.status == "UNSAT"
        out.update(stlsat_status="OK", stlsat_gold_in_pred=gp, stlsat_pred_in_gold=pg,
                   stlsat_verdict=verdict(gp, pg))
        if approx:
            out["stlsat_detail"] = f"unbounded operators capped at horizon {out['stlsat_horizon']}"
        return out


# --------------------------------------------------------------------------
# Dataset runner
# --------------------------------------------------------------------------

def run_dataset(df, cfg: Optional[Config] = None, progress: bool = True):
    """df needs columns pair_id, gold, pred (context optional).  Returns df + result columns."""
    import pandas as pd
    rows = []
    with Checker(cfg) as c:
        for i, r in enumerate(df.itertuples(index=False), 1):
            ctx = getattr(r, "context", None)
            ctx = ctx if isinstance(ctx, str) else None
            t0 = time.perf_counter()
            res = c.check(str(r.gold), str(r.pred), ctx)
            res["total_wall_ms"] = (time.perf_counter() - t0) * 1000
            rows.append(res)
            if progress:
                print(f"[{i:4d}/{len(df)}] {r.pair_id:12s} syn={str(res.get('syntactic_equal', '-')):5s} "
                      f"spot={res.get('spot_status')}/{res.get('spot_verdict')}  "
                      f"stlsat={res.get('stlsat_status')}/{res.get('stlsat_verdict')}", flush=True)
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
