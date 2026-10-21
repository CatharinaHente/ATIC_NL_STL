"""
stlsat_checker.py
-----------------
Python interface to the STLSat binary for STL formula equivalence checking.
Also includes a dataset runner that reads stlsat-routed rows from layer1.csv.
 
Usage (single pair):
    from stlsat_checker import check_equivalence, EquivalenceResult
    result = check_equivalence("G[0,10] (x > 5)", "G[0,10] (x > 5)")
 
Usage (dataset):
    python stlsat_checker.py --input data/layer1.csv --output data/stlsat_results.csv
 
Formula string format (STLSat syntax):
    G[a,b] phi  |  F[a,b] phi  |  phi U[a,b] psi  |  phi R[a,b] psi
    &&  ||  !  ->  <->   |   x > 5  |  on1  |  true  |  false
 
Equivalence encoding:
    phi1 == phi2  iff  (phi1 && !phi2) || (!phi1 && phi2)  is UNSAT
"""
 
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
 
 
@dataclass
class EquivalenceResult:
    verdict:      Verdict
    detail:       str
    raw_output:   str
    formula:      str = ""
    duration_sec: float = 0.0
 
 
# ---------------------------------------------------------------------------
# Fragment pre-check
# ---------------------------------------------------------------------------
 
_UNBOUNDED_RE = re.compile(r'\b[GF]\s*(?!\[)')
 
 
def _check_fragment(formula_str: str) -> str | None:
    if _UNBOUNDED_RE.search(formula_str):
        return (
            "Unbounded temporal operator (G or F without [a,b]). "
            "STLSat only supports bounded discrete-time STL."
        )
    return None
 
 
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
 
def _to_stlsat_syntax(formula: str) -> str:
    """
    Normalise formula to STLSat syntax:
      1. var = 0  →  !(var)        bool false assignment
      2. var = 1  →  var           bool true assignment
      3. single = →  ==            remaining equality (numeric predicates)
      4. &  →  &&,   |  →  ||     connectives
    Order matters: do bool assignments before the = → == substitution.
    """
    # 1. bool false:  var = 0  →  !(var)
    formula = re.sub(
        r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*0\b',
        lambda m: f'!({m.group(1)})',
        formula
    )
    # 2. bool true:  var = 1  →  var
    formula = re.sub(
        r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*1\b',
        lambda m: m.group(1),
        formula
    )
    # 3. single = → ==  (skip <=, >=, !=, already-doubled ==)
    formula = re.sub(r'(?<![<>!=])=(?!=)', '==', formula)
    # 4. connectives
    formula = re.sub(r'(?<!&)&(?!&)', '&&', formula)
    formula = re.sub(r'(?<!\|)\|(?!\|)', '||', formula)
    return formula
 
 
def check_equivalence(
    phi1: str,
    phi2: str,
    timeout: int = 30,
) -> EquivalenceResult:
    phi1 = _to_stlsat_syntax(phi1.strip())
    phi2 = _to_stlsat_syntax(phi2.strip())
 
    for phi, label in [(phi1, "phi1"), (phi2, "phi2")]:
        err = _check_fragment(phi)
        if err:
            return EquivalenceResult(
                verdict=Verdict.ERROR,
                detail=f"Fragment check failed for {label}: {err}",
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
        result = _parse_stlsat_output(raw, combined)
        result.duration_sec = duration
        return result
 
    except subprocess.TimeoutExpired:
        return EquivalenceResult(
            verdict=Verdict.ERROR,
            detail=f"stlsat timed out after {timeout}s.",
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
 
 
# ---------------------------------------------------------------------------
# Output parser
# ---------------------------------------------------------------------------
 
def _parse_stlsat_output(raw: str, combined: str) -> EquivalenceResult:
    if "Some(false)" in raw:
        return EquivalenceResult(
            verdict=Verdict.EQUIVALENT,
            detail="Equivalent (XOR formula is UNSAT).",
            raw_output=raw, formula=combined,
        )
    if "Some(true)" in raw:
        return EquivalenceResult(
            verdict=Verdict.NON_EQUIVALENT,
            detail="NOT equivalent (XOR formula is SAT).",
            raw_output=raw, formula=combined,
        )
    return EquivalenceResult(
        verdict=Verdict.ERROR,
        detail=f"Unexpected stlsat output: {raw[:200]}",
        raw_output=raw, formula=combined,
    )
 
 
# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------
 
def check_equivalence_batch(
    pairs: list[tuple[str, str]],
    timeout: int = 30,
) -> list[EquivalenceResult]:
    return [check_equivalence(p1, p2, timeout=timeout) for p1, p2 in pairs]
 
 
# ---------------------------------------------------------------------------
# Dataset runner
# ---------------------------------------------------------------------------
 
EXTRA_COLS = ["equiv_verdict", "equiv_detail", "duration_sec"]
 
 
def run_dataset(
    input_path: str,
    output_path: str,
    gold_col:  str = "gold_normalised",
    pred_col:  str = "pred_normalised",
    timeout:   int = 30,
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
 
    stlsat_rows = rows_in
    other_rows  = []
 
    counts      = {"EQUIVALENT": 0, "NON_EQUIVALENT": 0, "ERROR": 0, "SKIPPED": 0}
    rows_out    = []
    equiv_pairs = []
    total_time  = 0.0
 
    print(f"Checking {len(stlsat_rows)} STLSat pairs from {src.name} ...")
    print(f"(Passing {len(other_rows)} non-stlsat rows through unchanged)\n")
 
    for row in stlsat_rows:
        gold = row.get(gold_col, "").strip()
        pred = row.get(pred_col, "").strip()
 
        if not gold or not pred:
            result = EquivalenceResult(
                verdict=Verdict.ERROR,
                detail="Missing formula.",
                raw_output="", duration_sec=0.0,
            )
        else:
            result = check_equivalence(gold, pred, timeout=timeout)
 
        total_time += result.duration_sec
        counts[result.verdict.value] = counts.get(result.verdict.value, 0) + 1
 
        symbol = {"EQUIVALENT": "v", "NON_EQUIVALENT": "x", "ERROR": "!"}[result.verdict.value]
        print(f"  [{symbol}] {row.get('review_id','?'):10s}  "
              f"{result.verdict.value:15s}  {result.duration_sec*1000:.1f}ms")
 
        if result.verdict == Verdict.EQUIVALENT:
            equiv_pairs.append(row)
 
        rows_out.append({**row,
            "equiv_verdict": result.verdict.value,
            "equiv_detail":  result.detail,
            "duration_sec":  f"{result.duration_sec:.4f}",
        })
 
    for row in other_rows:
        counts["SKIPPED"] += 1
        rows_out.append({**row,
            "equiv_verdict": "",
            "equiv_detail":  "",
            "duration_sec":  "",
        })
 
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)
 
    total = len(stlsat_rows)
    print(f"\n{'='*55}")
    print(f"Results written to: {out}")
    print(f"\nSummary ({total} STLSat pairs):")
    print(f"  EQUIVALENT     : {counts['EQUIVALENT']:4d}  ({100*counts['EQUIVALENT']/max(total,1):.1f}%)")
    print(f"  NON_EQUIVALENT : {counts['NON_EQUIVALENT']:4d}  ({100*counts['NON_EQUIVALENT']/max(total,1):.1f}%)")
    print(f"  ERROR          : {counts['ERROR']:4d}  ({100*counts['ERROR']/max(total,1):.1f}%)")
    print(f"  Total time     : {total_time*1000:.1f}ms  (avg {total_time*1000/max(total,1):.1f}ms/pair)")
    print(f"  (non-stlsat rows passed through: {counts['SKIPPED']})")
 
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    default=None)
    parser.add_argument("--output",   default="data/stlsat_results.csv")
    parser.add_argument("--gold-col", default="gold_normalised")
    parser.add_argument("--pred-col", default="pred_normalised")
    parser.add_argument("--timeout",  type=int, default=30)
    args = parser.parse_args()
 
    if args.input:
        run_dataset(args.input, args.output, args.gold_col, args.pred_col, args.timeout)
    else:
        print('Error')