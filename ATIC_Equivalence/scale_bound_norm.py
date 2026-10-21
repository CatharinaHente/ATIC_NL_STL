"""
scale_bound_norm.py  —  Layer 1
---------------------------------
Pre-processes raw STL formula strings from the manual review dataset.

Only modifies a formula when strictly necessary:
  1. Real-valued intervals   → scale by LCM of denominators (exact, STLSat-safe)
  2. Unbounded G/F           → add [0, HORIZON] bound (SPOT path, semantic change)
  3. rise() or unsupported   → mark as SKIP

Output
------
data/layer1.csv   All pairs with normalised formulas and suitability column:
                    stlsat  → bounded + integer, feed to stlsat_checker.py
                    spot    → was unbounded, feed to STL_LTL_translation.py
                    skip    → rise() or unsupported, excluded from both checkers

Usage
-----
python scale_bound_norm.py \
    --input  ../ATIC_ManualReview/manual_review_mapping.csv \
    --output data/layer1.csv \
    --horizon 100
"""

import argparse
import csv
import re
from dataclasses import dataclass, field
from fractions import Fraction
from functools import reduce
from math import lcm
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_HORIZON = 100

# ---------------------------------------------------------------------------
# Detection regexes
# ---------------------------------------------------------------------------

_INTERVAL_RE  = re.compile(r'\[(\s*\d+(?:\.\d+)?\s*),(\s*\d+(?:\.\d+)?\s*)\]')
_UNBOUNDED_RE = re.compile(r'\b([GF])\s*(?!\[)')
_RISE_RE      = re.compile(r'\brise\s*\(')

# ---------------------------------------------------------------------------
# Suitability labels
# ---------------------------------------------------------------------------

STLSAT = "stlsat"
SPOT   = "spot"
SKIP   = "skip"

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class NormResult:
    original:    str
    normalised:  str
    suitability: str
    changes:     list[str] = field(default_factory=list)
    warnings:    list[str] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fractions(formula: str) -> list[Fraction]:
    fracs = []
    for m in _INTERVAL_RE.finditer(formula):
        fracs.append(Fraction(m.group(1).strip()).limit_denominator(10000))
        fracs.append(Fraction(m.group(2).strip()).limit_denominator(10000))
    return fracs

def _scale_factor(fracs: list[Fraction]) -> int:
    denoms = [f.denominator for f in fracs]
    return reduce(lcm, denoms, 1)

def _scale_interval(m: re.Match, scale: int) -> str:
    lo = int(Fraction(m.group(1).strip()).limit_denominator(10000) * scale)
    hi = int(Fraction(m.group(2).strip()).limit_denominator(10000) * scale)
    return f'[{lo},{hi}]'

# ---------------------------------------------------------------------------
# Core normaliser (single formula)
# ---------------------------------------------------------------------------

def normalise(formula: str, horizon: int = DEFAULT_HORIZON) -> NormResult:
    """Normalise one STL formula string. Only modifies when necessary."""
    f        = formula.strip()
    changes  = []
    warnings = []

    # 1. Unsupported: rise()
    if _RISE_RE.search(f):
        return NormResult(
            original=formula, normalised=f, suitability=SKIP,
            warnings=["Contains rise() — unsupported by STLSat and SPOT."],
        )

    suitability = STLSAT  # optimistic

    # 2. Real-valued intervals → scale (exact, STLSat-safe)
    fracs    = _fractions(f)
    has_real = any(fr.denominator != 1 for fr in fracs)
    if has_real:
        scale = _scale_factor(fracs)
        f = _INTERVAL_RE.sub(lambda m: _scale_interval(m, scale), f)
        changes.append(f"Scaled real-valued intervals by ×{scale}")

    # 3. Unbounded G/F → add horizon bound (SPOT path only)
    if _UNBOUNDED_RE.search(f):
        f = _UNBOUNDED_RE.sub(lambda m: f'{m.group(1)}[0,{horizon}]', f)
        changes.append(f"Bounded unbounded operator(s) with [0,{horizon}]")
        warnings.append(
            f"Semantic change: G/F[0,{horizon}] ≠ G/F unbounded. "
            "Valid for SPOT path only."
        )
        suitability = SPOT

    return NormResult(
        original=formula, normalised=f,
        suitability=suitability,
        changes=changes, warnings=warnings,
    )

# ---------------------------------------------------------------------------
# Pair normaliser
# ---------------------------------------------------------------------------

def normalise_pair(
    gold: str, pred: str, horizon: int = DEFAULT_HORIZON
) -> tuple[NormResult, NormResult, str]:
    """Combined suitability is most restrictive: SKIP > SPOT > STLSAT"""
    ng  = normalise(gold, horizon)
    np_ = normalise(pred, horizon)
    priority = {SKIP: 0, SPOT: 1, STLSAT: 2}
    combined = ng.suitability if priority[ng.suitability] <= priority[np_.suitability] \
               else np_.suitability
    return ng, np_, combined

# ---------------------------------------------------------------------------
# Dataset runner
# ---------------------------------------------------------------------------

EXTRA_COLS = [
    "suitability",
    "gold_normalised", "pred_normalised",
    "gold_changes", "pred_changes", "warnings",
]


def run(
    input_path: str,
    output_path: str,
    gold_col: str = "gold_formula",
    pred_col: str = "predicted_formula",
    horizon: int  = DEFAULT_HORIZON,
) -> None:

    src  = Path(input_path)
    out  = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows_in     = list(csv.DictReader(src.open(encoding="utf-8")))
    base_fields = list(rows_in[0].keys())
    out_fields  = base_fields + [c for c in EXTRA_COLS if c not in base_fields]

    counts   = {STLSAT: 0, SPOT: 0, SKIP: 0, "error": 0}
    rows_out = []

    print(f"Processing {len(rows_in)} pairs …\n")

    for row in rows_in:
        gold = row.get(gold_col, "").strip()
        pred = row.get(pred_col, "").strip()

        if not gold or not pred:
            counts["error"] += 1
            rows_out.append({**row,
                "suitability": "error",
                "gold_normalised": gold, "pred_normalised": pred,
                "gold_changes": "", "pred_changes": "",
                "warnings": "Missing gold or predicted formula"})
            continue

        ng, np_, combined = normalise_pair(gold, pred, horizon)
        counts[combined] += 1

        symbol = {STLSAT: "S", SPOT: "P", SKIP: "-"}[combined]
        print(f"  [{symbol}] {row.get('review_id','?'):10s}  → {combined}")

        rows_out.append({**row,
            "suitability":     combined,
            "gold_normalised": ng.normalised,
            "pred_normalised": np_.normalised,
            "gold_changes":    "; ".join(ng.changes),
            "pred_changes":    "; ".join(np_.changes),
            "warnings":        "; ".join(ng.warnings + np_.warnings),
        })

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    total = len(rows_in)
    print(f"\nWritten: {out}  ({total} rows)")
    print(f"\nSummary ({total} pairs):")
    print(f"  STLSat-ready : {counts[STLSAT]:4d}  ({100*counts[STLSAT]/total:.1f}%)")
    print(f"  SPOT-input   : {counts[SPOT]:4d}  ({100*counts[SPOT]/total:.1f}%)")
    print(f"  Skipped      : {counts[SKIP]:4d}  ({100*counts[SKIP]/total:.1f}%)")
    if counts["error"]:
        print(f"  Errors       : {counts['error']:4d}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    default="../ATIC_ManualReview/manual_review_mapping.csv")
    parser.add_argument("--output",   default="data/layer1.csv")
    parser.add_argument("--gold-col", default="gold_formula")
    parser.add_argument("--pred-col", default="predicted_formula")
    parser.add_argument("--horizon",  type=int, default=DEFAULT_HORIZON)
    args = parser.parse_args()

    run(args.input, args.output, args.gold_col, args.pred_col, args.horizon)