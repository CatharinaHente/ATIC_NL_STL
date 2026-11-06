"""
stlsat_checker.py
-----------------
Python interface to the STLSat binary for STL formula equivalence checking.
Reads data/layer1.csv and attempts ALL pairs, erroring cleanly on unsupported fragments.

Usage (dataset):
    python stlsat_checker.py --input data/layer1.csv --output data/stlsat_results.csv

Equivalence encoding:
    phi1 == phi2  iff  (phi1 && !phi2) || (!phi1 && phi2)  is UNSAT
"""

import argparse
import csv
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class Verdict(str, Enum):
    EQUIVALENT     = "EQUIVALENT"
    NON_EQUIVALENT = "NON_EQUIVALENT"
    ERROR          = "ERROR"
    TIMEOUT        = "TIMEOUT"


@dataclass
class EquivalenceResult:
    verdict:      Verdict
    detail:       str
    raw_output:   str
    formula:      str  = ""
    duration_sec: float = 0.0


# ---------------------------------------------------------------------------
# Fragment pre-check — catch unsupported operators before calling stlsat
# ---------------------------------------------------------------------------

_UNBOUNDED_RE  = re.compile(r'\b[GF]\s*(?!\[)')
_SINCE_RE      = re.compile(r'(?<![A-Za-z0-9_])\bS\b(?!\s*[A-Za-z0-9_(])')  # S operator not part of a word
_PAST_OP_RE    = re.compile(r'\b[HO]\s*\[')           # H[a,b] or O[a,b]
_PARAMETRIC_RE = re.compile(r'\b(?:OR|AND)_[a-zA-Z{]|\b(?:distance|in_surveillance)\s*\(')
_RISE_RE       = re.compile(r'\brise\s*\(')
_FALL_RE       = re.compile(r'\bfall\s*\(')
_SYMBOLIC_RE   = re.compile(r'\b[GFUR]\s*\[\s*\d+\s*,\s*[A-Za-z_]')  # G[0,H]


def _check_fragment(formula: str) -> str | None:
    # Note: unbounded G/F are already bounded by scale_bound_norm.py
    # so we no longer reject them here — STLSat attempts all normalised formulas
    if _SINCE_RE.search(formula):
        return "Past operator S — not supported by STLSat."
    if _PAST_OP_RE.search(formula):
        return "Past operator H[]/O[] — not supported by STLSat."
    if _PARAMETRIC_RE.search(formula):
        return "Parametric/indexed operator (OR_i, distance()) — not supported by STLSat."
    if _RISE_RE.search(formula) or _FALL_RE.search(formula):
        return "rise()/fall() — not supported by STLSat."
    if _SYMBOLIC_RE.search(formula):
        return "Symbolic interval bound (e.g. G[0,H]) — STLSat requires integer bounds."
    return None


# ---------------------------------------------------------------------------
# Syntax normalisation to STLSat format
# ---------------------------------------------------------------------------

# abs(expr) op number → |expr| op number  (STLSat uses pipe syntax)
_ABS_RE = re.compile(r'abs\s*\(([^)]+)\)')


def _to_stlsat_syntax(formula: str) -> str:
    """
    Normalise formula to STLSat syntax:
      1. abs(expr)  →  |expr|       (STLSat uses pipe syntax for absolute value)
      2. var = 1    →  var          (bool true assignment)
      3. single =   →  ==           (numeric equality)
      4. &  →  &&,  |  →  ||       (connectives — after abs conversion)
    Note: var = 0 becomes var == 0 (numeric predicate, correct for STLSat).
    """
    # 1. connectives first — before abs conversion adds pipe characters
    formula = re.sub(r'(?<!&)&(?!&)', '&&', formula)
    # for |: only double pipes that are NOT already part of abs notation
    # since abs hasn't been converted yet, all | are connectives at this point
    formula = re.sub(r'(?<!\|)\|(?!\|)', '||', formula)

    # 2. abs(expr) → |expr|  — after connectives are already doubled
    formula = _ABS_RE.sub(lambda m: f'|{m.group(1)}|', formula)

    # 3. bool true: var = 1 → var
    formula = re.sub(
        r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*1\b',
        lambda m: m.group(1),
        formula
    )

    # 4. single = → ==
    formula = re.sub(r'(?<![<>!=])=(?!=)', '==', formula)

    return formula


# ---------------------------------------------------------------------------
# STLSat binary location
# ---------------------------------------------------------------------------

def _find_stlsat() -> str:
    path = shutil.which("stlsat")
    if path:
        return path
    fallback = Path.home() / ".cargo" / "bin" / "stlsat"
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError(
        "stlsat binary not found. Install with:\n"
        "  cargo install --path <path-to-stlsat-repo>\n"
        "and ensure ~/.cargo/bin is on your PATH."
    )


# ---------------------------------------------------------------------------
# Core equivalence check
# ---------------------------------------------------------------------------

def check_equivalence(phi1: str, phi2: str, timeout: int = 30) -> EquivalenceResult:
    phi1 = _to_stlsat_syntax(phi1.strip())
    phi2 = _to_stlsat_syntax(phi2.strip())

    for phi, label in [(phi1, "phi1"), (phi2, "phi2")]:
        err = _check_fragment(phi)
        if err:
            return EquivalenceResult(
                verdict=Verdict.ERROR,
                detail=f"{label}: {err}",
                raw_output="", formula="",
            )

    combined = f"({phi1} && !({phi2})) || (!({phi1}) && ({phi2}))"

    try:
        binary = _find_stlsat()
    except FileNotFoundError as e:
        return EquivalenceResult(
            verdict=Verdict.ERROR, detail=str(e),
            raw_output="", formula=combined,
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".stl", delete=False) as tmp:
        tmp.write(combined + "\n")
        tmp_path = tmp.name

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [binary, tmp_path],
            capture_output=True, text=True, timeout=timeout,
        )
        duration = time.perf_counter() - t0
        raw = proc.stdout + proc.stderr
        result = _parse_output(raw, combined)
        result.duration_sec = duration
        return result
    except subprocess.TimeoutExpired:
        return EquivalenceResult(
            verdict=Verdict.TIMEOUT,
            detail=f"Timed out after {timeout}s.",
            raw_output="TIMEOUT", formula=combined,
        )
    except Exception as e:
        return EquivalenceResult(
            verdict=Verdict.ERROR,
            detail=f"Unexpected error: {e}",
            raw_output="", formula=combined,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _parse_output(raw: str, combined: str) -> EquivalenceResult:
    if "Some(false)" in raw:
        return EquivalenceResult(
            verdict=Verdict.EQUIVALENT,
            detail="Equivalent (XOR is UNSAT).",
            raw_output=raw, formula=combined,
        )
    if "Some(true)" in raw:
        return EquivalenceResult(
            verdict=Verdict.NON_EQUIVALENT,
            detail="NOT equivalent (XOR is SAT).",
            raw_output=raw, formula=combined,
        )
    return EquivalenceResult(
        verdict=Verdict.ERROR,
        detail=f"Unexpected output: {raw[:150]}",
        raw_output=raw, formula=combined,
    )


# ---------------------------------------------------------------------------
# Dataset runner — attempts ALL rows
# ---------------------------------------------------------------------------

EXTRA_COLS = ["equiv_verdict", "equiv_detail", "duration_ms"]


def run_dataset(
    input_path: str,
    output_path: str,
    gold_col: str = "gold_normalised",
    pred_col: str = "pred_normalised",
    timeout:  int = 30,
) -> None:
    src = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"ERROR: {src} not found. Run scale_bound_norm.py first.")
        return

    rows_in     = list(csv.DictReader(src.open(encoding="utf-8")))
    base_fields = list(rows_in[0].keys())
    out_fields  = base_fields + [c for c in EXTRA_COLS if c not in base_fields]

    counts      = {"EQUIVALENT": 0, "NON_EQUIVALENT": 0, "ERROR": 0}
    rows_out    = []
    equiv_pairs = []
    total_ms    = 0.0

    print(f"Checking all {len(rows_in)} pairs from {src.name} ...\n")

    for row in rows_in:
        gold = row.get(gold_col, "").strip()
        pred = row.get(pred_col, "").strip()

        if not gold or not pred:
            result = EquivalenceResult(
                verdict=Verdict.ERROR, detail="Missing formula.",
                raw_output="", duration_sec=0.0,
            )
        else:
            result = check_equivalence(gold, pred, timeout=timeout)

        duration_ms = result.duration_sec * 1000
        total_ms   += duration_ms
        counts[result.verdict.value] = counts.get(result.verdict.value, 0) + 1

        symbol = {"EQUIVALENT": "v", "NON_EQUIVALENT": "x", "ERROR": "!", "TIMEOUT": "T"}.get(result.verdict.value, "?")
        print(f"  [{symbol}] {row.get('review_id','?'):10s}  "
              f"{result.verdict.value:15s}  {duration_ms:.1f}ms")

        if result.verdict == Verdict.EQUIVALENT:
            equiv_pairs.append(row)

        rows_out.append({**row,
            "equiv_verdict": result.verdict.value,
            "equiv_detail":  result.detail,
            "duration_ms":   f"{duration_ms:.3f}",
        })

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    total = len(rows_in)
    print(f"\n{'='*55}")
    print(f"Results written to: {out}")
    print(f"\nSummary ({total} pairs):")
    print(f"  EQUIVALENT     : {counts.get('EQUIVALENT',0):4d}  ({100*counts.get('EQUIVALENT',0)/total:.1f}%)")
    print(f"  NON_EQUIVALENT : {counts.get('NON_EQUIVALENT',0):4d}  ({100*counts.get('NON_EQUIVALENT',0)/total:.1f}%)")
    print(f"  TIMEOUT        : {counts.get('TIMEOUT',0):4d}  ({100*counts.get('TIMEOUT',0)/total:.1f}%)")
    print(f"  ERROR          : {counts.get('ERROR',0):4d}  ({100*counts.get('ERROR',0)/total:.1f}%)")
    print(f"  Total time     : {total_ms:.1f}ms  (avg {total_ms/total:.2f}ms/pair)")

    if equiv_pairs:
        print(f"\nEquivalent pairs ({len(equiv_pairs)}):")
        for r in equiv_pairs:
            print(f"  {r.get('review_id','?')}")
            print(f"    gold : {r.get('gold_formula','')}")
            print(f"    pred : {r.get('predicted_formula','')}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    default="data/layer1.csv")
    parser.add_argument("--output",   default="data/stlsat_results.csv")
    parser.add_argument("--gold-col", default="gold_normalised")
    parser.add_argument("--pred-col", default="pred_normalised")
    parser.add_argument("--timeout",  type=int, default=30)
    args = parser.parse_args()

    run_dataset(args.input, args.output, args.gold_col, args.pred_col, args.timeout)