"""
spot_checker.py
---------------
Reads data/layer2.csv and checks equivalence of ALL LTL formula pairs
using SPOT's are_equivalent(). Writes data/spot_results.csv.

Usage
-----
python spot_checker.py \
    --input  data/layer2.csv \
    --output data/spot_results.csv
"""

import argparse
import csv
import signal
import time
from pathlib import Path

try:
    import spot
    SPOT_AVAILABLE = True
    # shared language containment checker — caches automata across calls
    _lcc = spot.language_containment_checker()
except ImportError:
    SPOT_AVAILABLE = False
    _lcc = None
    print("WARNING: SPOT not installed. Run: conda install -c conda-forge spot")


# ---------------------------------------------------------------------------
# Timeout helper (Unix only)
# ---------------------------------------------------------------------------

class _Timeout:
    def __init__(self, seconds):
        self.seconds = seconds

    def _handler(self, signum, frame):
        raise TimeoutError(f"SPOT timed out after {self.seconds}s")

    def __enter__(self):
        try:
            signal.signal(signal.SIGALRM, self._handler)
            signal.alarm(self.seconds)
        except (AttributeError, OSError):
            pass  # Windows — no SIGALRM, skip timeout
        return self

    def __exit__(self, *args):
        try:
            signal.alarm(0)
        except (AttributeError, OSError):
            pass


# ---------------------------------------------------------------------------
# Single pair check
# ---------------------------------------------------------------------------

def check_pair(ltl1: str, ltl2: str, timeout: int = 10) -> tuple[str, str, float]:
    """Returns (verdict, detail, duration_ms)."""
    if not SPOT_AVAILABLE:
        return "ERROR", "SPOT not installed.", 0.0
    if not ltl1 or not ltl2:
        return "ERROR", "Empty LTL formula.", 0.0
    try:
        t0 = time.perf_counter()
        with _Timeout(timeout):
            eq = _lcc.are_equivalent(ltl1, ltl2)
        duration_ms = (time.perf_counter() - t0) * 1000
        if eq:
            return "EQUIVALENT", "Equivalent under LTL abstraction.", duration_ms
        else:
            return "NON_EQUIVALENT", "NOT equivalent — distinguishing trace exists.", duration_ms
    except TimeoutError as e:
        return "TIMEOUT", str(e), (time.perf_counter() - t0) * 1000
    except Exception as e:
        return "ERROR", f"SPOT parse error: {e}", 0.0


# ---------------------------------------------------------------------------
# Dataset runner — checks ALL rows
# ---------------------------------------------------------------------------

EXTRA_COLS = ["equiv_verdict", "equiv_detail", "duration_ms"]


def run(input_path: str, output_path: str,
        ltl_gold_col: str = "ltl_gold",
        ltl_pred_col: str = "ltl_pred") -> None:

    src = Path(input_path)
    if not src.exists():
        print(f"ERROR: {src} not found. Run STL_LTL_translation.py first.")
        return

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows_in     = list(csv.DictReader(src.open(encoding="utf-8")))
    base_fields = list(rows_in[0].keys())
    out_fields  = base_fields + [c for c in EXTRA_COLS if c not in base_fields]

    counts      = {"EQUIVALENT": 0, "NON_EQUIVALENT": 0, "ERROR": 0}
    rows_out    = []
    equiv_pairs = []
    total_ms    = 0.0

    print(f"Checking all {len(rows_in)} pairs from {src.name} ...\n")

    for row in rows_in:
        ltl_gold = row.get(ltl_gold_col, "").strip()
        ltl_pred = row.get(ltl_pred_col, "").strip()

        verdict, detail, duration_ms = check_pair(ltl_gold, ltl_pred)
        counts[verdict] = counts.get(verdict, 0) + 1
        total_ms += duration_ms

        symbol = {"EQUIVALENT": "v", "NON_EQUIVALENT": "x", "ERROR": "!"}[verdict]
        print(f"  [{symbol}] {row.get('review_id','?'):10s}  "
              f"{verdict:15s}  {duration_ms:.2f}ms")

        if verdict == "EQUIVALENT":
            equiv_pairs.append(row)

        rows_out.append({**row,
            "equiv_verdict": verdict,
            "equiv_detail":  detail,
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
    print(f"  EQUIVALENT     : {counts['EQUIVALENT']:4d}  ({100*counts['EQUIVALENT']/total:.1f}%)")
    print(f"  NON_EQUIVALENT : {counts['NON_EQUIVALENT']:4d}  ({100*counts['NON_EQUIVALENT']/total:.1f}%)")
    print(f"  ERROR          : {counts['ERROR']:4d}  ({100*counts['ERROR']/total:.1f}%)")
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
    parser.add_argument("--input",        default="data/layer2.csv")
    parser.add_argument("--output",       default="data/spot_results.csv")
    parser.add_argument("--ltl-gold-col", default="ltl_gold")
    parser.add_argument("--ltl-pred-col", default="ltl_pred")
    args = parser.parse_args()

    run(args.input, args.output, args.ltl_gold_col, args.ltl_pred_col)