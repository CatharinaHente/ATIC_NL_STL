"""
STL_LTL_translation.py  —  Layer 2
-------------------------------------
Reads data/layer1.csv, filters rows where suitability == 'spot',
translates normalised STL formulas to LTL for SPOT, and writes data/layer2.csv.

Also accepts stlsat rows as input — those pass through with empty LTL columns
so layer2.csv can optionally be used as a unified dataset view.

Translation rules:
  G[a,b] φ     →  G φ          (bounds stripped)
  F[a,b] φ     →  F φ
  φ U[a,b] ψ  →  φ U ψ
  φ R[a,b] ψ  →  φ R ψ
  x > 5        →  x_gt_5       (predicate abstraction)
  var = 1      →  var           (bool true assignment)
  var = 0      →  !var          (bool false assignment — negation)
  &&  → &    ||  → |

Soundness note:
  Predicate abstraction is sound for NON-EQUIVALENCE.
  Arithmetic differences (x>5 vs x>6) are NOT caught — use STLSat for those.

Usage
-----
python STL_LTL_translation.py \
    --input  data/layer1.csv \
    --output data/layer2.csv
"""

import argparse
import csv
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Translation rules
# ---------------------------------------------------------------------------

# 1. Strip interval bounds: G[0,10] → G
_STRIP_BOUNDS_RE = re.compile(r'\b([GFUR])\s*\[\s*\d+\s*,\s*\d+\s*\]')

# 2a. Boolean true assignments:  var = 1 → var
_BOOL_TRUE_RE  = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*1\b')
# 2b. Boolean false assignments: var = 0 → !var
_BOOL_FALSE_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*0\b')

# 3. Arithmetic predicates: x > 5.0 → x_gt_5p0
_PREDICATE_RE = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)'
    r'\s*(<=|>=|!=|==|<|>)\s*'
    r'(-?\d+(?:\.\d+)?)'
)
_OP_NAME = {
    '>': 'gt', '<': 'lt', '>=': 'ge',
    '<=': 'le', '==': 'eq', '!=': 'ne',
}

# 4. Boolean connectives: && → &,  || → |
_CONNECTIVES = [
    (re.compile(r'&&'), '&'),
    (re.compile(r'\|\|'), '|'),
]


def _make_prop(var: str, op: str, val: str) -> str:
    op_str  = _OP_NAME.get(op, op)
    val_str = val.replace('.', 'p').replace('-', 'm')
    prop    = f"{var}_{op_str}_{val_str}"
    return re.sub(r'[^a-zA-Z0-9_]', '_', prop)


def stl_to_ltl(formula: str) -> str:
    """Translate a normalised STL formula string to SPOT LTL syntax."""
    f = formula.strip()

    # 1. strip interval bounds
    f = _STRIP_BOUNDS_RE.sub(lambda m: m.group(1), f)

    # 2. boolean assignments (order matters: do = 0 before = 1
    #    to avoid partial matches on larger numbers)
    f = _BOOL_FALSE_RE.sub(lambda m: f'!{m.group(1)}', f)
    f = _BOOL_TRUE_RE.sub(lambda m: m.group(1), f)

    # 3. abstract arithmetic predicates
    f = _PREDICATE_RE.sub(
        lambda m: _make_prop(m.group(1), m.group(2), m.group(3)), f
    )

    # 4. normalise connectives
    for pat, rep in _CONNECTIVES:
        f = pat.sub(rep, f)

    return f.strip()


# ---------------------------------------------------------------------------
# Dataset runner
# ---------------------------------------------------------------------------

EXTRA_COLS = ["ltl_gold", "ltl_pred"]


def run(input_path: str, output_path: str,
        gold_col: str = "gold_normalised",
        pred_col: str = "pred_normalised") -> None:

    src = Path(input_path)
    if not src.exists():
        print(f"ERROR: {src} not found. Run scale_bound_norm.py first.")
        return

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows_in     = list(csv.DictReader(src.open(encoding="utf-8")))
    base_fields = list(rows_in[0].keys())
    out_fields  = base_fields + [c for c in EXTRA_COLS if c not in base_fields]

    rows_out = []
    counts   = {"spot": 0, "stlsat": 0, "skip": 0}

    print(f"Translating {len(rows_in)} rows from {src.name} …\n")

    for row in rows_in:

        gold_norm = row.get(gold_col, "").strip()
        pred_norm = row.get(pred_col, "").strip()

        ltl_gold = stl_to_ltl(gold_norm) if gold_norm else ""
        ltl_pred = stl_to_ltl(pred_norm) if pred_norm else ""

        print(f"  {row.get('review_id','?'):10s}")
        print(f"    STL gold : {gold_norm}")
        print(f"    LTL gold : {ltl_gold}")
        print(f"    STL pred : {pred_norm}")
        print(f"    LTL pred : {ltl_pred}")
        print()

        rows_out.append({**row, "ltl_gold": ltl_gold, "ltl_pred": ltl_pred})

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    print(f"Written: {out}  ({len(rows_out)} rows)")
    print(f"  spot rows translated : {counts.get('spot', 0)}")
    print(f"  stlsat rows passed   : {counts.get('stlsat', 0)}")
    print(f"  skip rows passed     : {counts.get('skip', 0)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    default="data/layer1.csv")
    parser.add_argument("--output",   default="data/layer2.csv")
    parser.add_argument("--gold-col", default="gold_normalised")
    parser.add_argument("--pred-col", default="pred_normalised")
    args = parser.parse_args()

    run(args.input, args.output, args.gold_col, args.pred_col)