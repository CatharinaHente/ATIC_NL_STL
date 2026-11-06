"""
STL_LTL_translation.py  —  Layer 2
-------------------------------------
Reads data/layer1.csv and translates ALL normalised STL formulas to LTL
for SPOT, writing data/layer2.csv.

Translation rules:
  G[a,b] phi     →  G phi          (bounds stripped)
  F[a,b] phi     →  F phi
  phi U[a,b] psi →  phi U psi
  phi R[a,b] psi →  phi R psi
  var = 1        →  var             (bool true assignment)
  var = 0        →  !var            (bool false assignment)
  x > 5          →  x_gt_5         (predicate abstraction)
  &&  → &    ||  → |

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
from rise_fall_rewriter import rewrite as rewrite_rise_fall


# ---------------------------------------------------------------------------
# Translation rules
# ---------------------------------------------------------------------------

# Strip bounded temporal operator intervals: G[0,10] → G, F[3,7] → F etc.
_STRIP_BOUNDS_RE = re.compile(r'\b([GFUR])\s*\[\s*\d+\s*,\s*\d+\s*\]')

# Past operators — H, O, S are NOT supported by this SPOT version
# Detect them so we can return empty LTL and flag as unsupported
_PAST_OP_RE = re.compile(r'\b([HO])\s*[\[(]|\bS\b(?!\s*[A-Za-z0-9_(])')

# abs(expr) op number  →  abs_expr_op_num  (predicate abstraction)
# Handles: abs(x) > 5, abs(x - y) <= 0.2
_ABS_PRED_RE = re.compile(
    r'abs\s*\(([^)]+)\)\s*(<=|>=|!=|==|<|>)\s*(-?\d+(?:\.\d+)?)'
)

# Boolean assignments
_BOOL_FALSE_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*0\b')
_BOOL_TRUE_RE  = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*1\b')

# Arithmetic predicates: x > 5, V_In >= 3.2
_PREDICATE_RE = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)\s*(<=|>=|!=|==|<|>)\s*(-?\d+(?:\.\d+)?)'
)

_OP_NAME = {
    '>': 'gt', '<': 'lt', '>=': 'ge',
    '<=': 'le', '==': 'eq', '!=': 'ne',
}
_CONNECTIVES = [
    (re.compile(r'&&'), '&'),
    (re.compile(r'\|\|'), '|'),
]


def _make_prop(var: str, op: str, val: str) -> str:
    op_str  = _OP_NAME.get(op, op)
    val_str = val.replace('.', 'p').replace('-', 'm')
    return re.sub(r'[^a-zA-Z0-9_]', '_', f"{var}_{op_str}_{val_str}")


def _abs_to_prop(inner: str, op: str, val: str) -> str:
    """abs(cmd - robot) <= 0.2  →  abs_cmd_m_robot_le_0p2"""
    inner_clean = re.sub(r'[^a-zA-Z0-9_]', '_', inner.strip())
    inner_clean = re.sub(r'_+', '_', inner_clean).strip('_')
    op_str  = _OP_NAME.get(op, op)
    val_str = val.replace('.', 'p').replace('-', 'm')
    return f"abs_{inner_clean}_{op_str}_{val_str}"


def stl_to_ltl(formula: str) -> tuple[str, str | None]:
    """
    Translate a normalised STL formula string to SPOT LTL syntax.

    Returns (ltl_string, error_reason) where error_reason is None on success
    or a string explaining why the formula cannot be translated.

    Steps applied in order:
      0. Rewrite rise()/fall() → Y operator
      1. Check for unsupported past operators (H, O, S) — flag and return empty
      2. Strip bounded temporal operator intervals
      3. Abstract abs(expr) op num → proposition
      4. Abstract arithmetic expressions: (x + y) op num → prop
      5. Boolean assignments: var=0→!var, var=1→var
      6. Abstract arithmetic predicates: x>5 → x_gt_5
      7. Normalise connectives: &&→&, ||→|
    """
    f = formula.strip()

    # 0. rewrite rise()/fall() → Y operator
    f = rewrite_rise_fall(f).ltl

    # 1. check for unsupported past operators
    if _PAST_OP_RE.search(f):
        return "", "Contains H/O/S past operator — not supported by this SPOT version."

    # 2. strip bounded temporal operator intervals
    f = _STRIP_BOUNDS_RE.sub(lambda m: m.group(1), f)

    # 3. abstract abs(expr) predicates
    f = _ABS_PRED_RE.sub(
        lambda m: _abs_to_prop(m.group(1), m.group(2), m.group(3)), f
    )

    # 4. abstract arithmetic expressions: (x1 + x2) <= 1.5 → x1_plus_x2_le_1p5
    #    matches: (expr with +/-) op number
    f = re.sub(
        r'\(([A-Za-z_][A-Za-z0-9_]*\s*[+\-]\s*[A-Za-z_][A-Za-z0-9_]*)\)\s*(<=|>=|!=|==|<|>)\s*(-?\d+(?:\.\d+)?)',
        lambda m: _make_prop(
            re.sub(r'[^a-zA-Z0-9]', '_', m.group(1).replace('+','_plus_').replace('-','_minus_').replace(' ','')),
            m.group(2), m.group(3)
        ),
        f
    )

    # 5. boolean assignments
    f = _BOOL_FALSE_RE.sub(lambda m: f'!{m.group(1)}', f)
    f = _BOOL_TRUE_RE.sub(lambda m: m.group(1), f)

    # 6. abstract arithmetic predicates
    f = _PREDICATE_RE.sub(
        lambda m: _make_prop(m.group(1), m.group(2), m.group(3)), f
    )

    # 7. normalise connectives
    for pat, rep in _CONNECTIVES:
        f = pat.sub(rep, f)

    return f.strip(), None


# ---------------------------------------------------------------------------
# Dataset runner — translates ALL rows
# ---------------------------------------------------------------------------

EXTRA_COLS = ["ltl_gold", "ltl_pred", "translation_error"]


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

    rows_out       = []
    missing        = 0
    unsupported    = 0

    print(f"Translating all {len(rows_in)} rows from {src.name} ...\n")

    for row in rows_in:
        gold_norm = row.get(gold_col, "").strip()
        pred_norm = row.get(pred_col, "").strip()

        if not gold_norm or not pred_norm:
            missing += 1
            rows_out.append({**row, "ltl_gold": "", "ltl_pred": "",
                             "translation_error": "Missing formula"})
            continue

        ltl_gold, err_gold = stl_to_ltl(gold_norm)
        ltl_pred, err_pred = stl_to_ltl(pred_norm)

        err = err_gold or err_pred
        if err:
            unsupported += 1

        rows_out.append({**row,
            "ltl_gold":          ltl_gold,
            "ltl_pred":          ltl_pred,
            "translation_error": err or "",
        })

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    print(f"Written: {out}  ({len(rows_out)} rows)")
    print(f"  Unsupported (past operators) : {unsupported}")
    if missing:
        print(f"  Missing formulas             : {missing}")


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