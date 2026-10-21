"""
spot_checker.py
---------------
Reads data/layer2.csv, filters rows where suitability == 'spot',
checks LTL equivalence using SPOT, and writes data/spot_results.csv.

Usage
-----
python spot_checker.py \
    --input  data/layer2.csv \
    --output data/spot_results.csv
"""

import argparse
import csv
from pathlib import Path

try:
    import spot
    SPOT_AVAILABLE = True
except ImportError:
    SPOT_AVAILABLE = False
    print("WARNING: SPOT not installed. Run: conda install -c conda-forge spot")


# ---------------------------------------------------------------------------
# Single pair check
# ---------------------------------------------------------------------------

def check_pair(ltl1: str, ltl2: str) -> tuple[str, str]:
    """Returns (verdict, detail). verdict: EQUIVALENT | NON_EQUIVALENT | ERROR"""
    if not SPOT_AVAILABLE:
        return "ERROR", "SPOT not installed."
    if not ltl1 or not ltl2:
        return "ERROR", "Empty LTL formula."
    try:
        eq = spot.are_equivalent(ltl1, ltl2)
        if eq:
            return "EQUIVALENT", "Equivalent under LTL abstraction."
        else:
            return "NON_EQUIVALENT", "NOT equivalent — distinguishing trace exists."
    except Exception as e:
        return "ERROR", f"SPOT parse error: {e}"


# ---------------------------------------------------------------------------
# Dataset runner
# ---------------------------------------------------------------------------

EXTRA_COLS = ["equiv_verdict", "equiv_detail"]


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

    counts      = {"EQUIVALENT": 0, "NON_EQUIVALENT": 0, "ERROR": 0, "SKIPPED": 0}
    rows_out    = []
    equiv_pairs = []

    # only process spot rows
    spot_rows  = rows_in
    other_rows = []

    print(f"Checking {len(spot_rows)} SPOT pairs from {src.name} …")
    print(f"(Passing through {len(other_rows)} non-spot rows unchanged)\n")

    for row in spot_rows:
        ltl_gold = row.get(ltl_gold_col, "").strip()
        ltl_pred = row.get(ltl_pred_col, "").strip()

        verdict, detail = check_pair(ltl_gold, ltl_pred)
        counts[verdict] += 1

        symbol = {"EQUIVALENT": "✓", "NON_EQUIVALENT": "✗", "ERROR": "!"}[verdict]
        print(f"  [{symbol}] {row.get('review_id','?'):10s}  {verdict}")

        if verdict == "EQUIVALENT":
            equiv_pairs.append(row)

        rows_out.append({**row, "equiv_verdict": verdict, "equiv_detail": detail})

    # pass through non-spot rows with empty verdict columns
    for row in other_rows:
        counts["SKIPPED"] += 1
        rows_out.append({**row, "equiv_verdict": "", "equiv_detail": ""})

    # write results
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    # summary
    total = len(spot_rows)
    print(f"\n{'='*50}")
    print(f"Results written to: {out}")
    print(f"\nSummary ({total} SPOT pairs checked):")
    print(f"  EQUIVALENT     : {counts['EQUIVALENT']:4d}  ({100*counts['EQUIVALENT']/max(total,1):.1f}%)")
    print(f"  NON_EQUIVALENT : {counts['NON_EQUIVALENT']:4d}  ({100*counts['NON_EQUIVALENT']/max(total,1):.1f}%)")
    print(f"  ERROR          : {counts['ERROR']:4d}  ({100*counts['ERROR']/max(total,1):.1f}%)")
    print(f"  (non-spot rows passed through: {counts['SKIPPED']})")

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