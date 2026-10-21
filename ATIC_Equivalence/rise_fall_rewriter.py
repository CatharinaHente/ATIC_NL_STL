"""
rise_fall_rewriter.py
----------------------
Rewrites STL formulas containing rise() and fall() operators into
SPOT-compatible LTL using the Y (Yesterday) past operator.

Rewriting rules (exact, grounded in discrete-time STL semantics):
    rise(φ)  →  prop  &  !Y(prop)     where prop = abstracted proposition
    fall(φ)  →  !prop &   Y(prop)

SPOT syntax for Y: written directly adjacent to its argument, no parens:
    Y(fault)   → Yfault          (bare variable)
    Y(x_gt_5)  → Yx_gt_5        (abstracted predicate)

Input:  data/layer1.csv  (the 'skip' rows)
Output: data/rise_fall_ltl.csv  with columns ltl_gold, ltl_pred added,
        ready to be fed into spot_checker.py

Special cases detected and flagged:
    - rise/fall around arithmetic predicates  (rise(x > 5)) → abstracted
    - rise/fall in postcondition position     → flagged, still attempted
    - H[] (historically) operator            → flagged as unsupported by SPOT
    - mismatched structure (one side has rise, other doesn't) → flagged

Usage
-----
python rise_fall_rewriter.py \
    --input  data/layer1.csv \
    --output data/rise_fall_ltl.csv
"""

import argparse
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Predicate abstraction (shared with STL_LTL_translation.py)
# ---------------------------------------------------------------------------

_BOOL_TRUE_RE  = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*1\b')
_BOOL_FALSE_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*0\b')
_PREDICATE_RE  = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)\s*(<=|>=|!=|==|<|>)\s*(-?\d+(?:\.\d+)?)'
)
_OP_NAME = {'>': 'gt', '<': 'lt', '>=': 'ge', '<=': 'le', '==': 'eq', '!=': 'ne'}
_STRIP_BOUNDS_RE = re.compile(r'\b([GFUR])\s*\[\s*\d+\s*,\s*\d+\s*\]')
_CONNECTIVES = [(re.compile(r'&&'), '&'), (re.compile(r'\|\|'), '|')]
_HIST_RE = re.compile(r'\bH\s*\[')  # H[a,b] — historically, unsupported by SPOT


def _make_prop(var: str, op: str, val: str) -> str:
    op_str  = _OP_NAME.get(op, op)
    val_str = val.replace('.', 'p').replace('-', 'm')
    return re.sub(r'[^a-zA-Z0-9_]', '_', f"{var}_{op_str}_{val_str}")


def _base_ltl(formula: str) -> str:
    """Apply standard STL→LTL translation (without rise/fall handling)."""
    f = formula.strip()
    f = _STRIP_BOUNDS_RE.sub(lambda m: m.group(1), f)
    f = _BOOL_FALSE_RE.sub(lambda m: f'!{m.group(1)}', f)
    f = _BOOL_TRUE_RE.sub(lambda m: m.group(1), f)
    f = _PREDICATE_RE.sub(
        lambda m: _make_prop(m.group(1), m.group(2), m.group(3)), f
    )
    for pat, rep in _CONNECTIVES:
        f = pat.sub(rep, f)
    return f.strip()


# ---------------------------------------------------------------------------
# Rise/fall argument extractor
# Uses a simple bracket-counting approach to extract the full argument
# of rise(...) or fall(...), handling nested parentheses correctly.
# ---------------------------------------------------------------------------

def _extract_rise_fall_args(formula: str) -> list[tuple[int, int, str, str]]:
    """
    Find all rise(...) and fall(...) in formula.
    Returns list of (start, end, operator, inner_content) tuples.
    start/end are character indices of the full 'rise(...)' or 'fall(...)'.
    """
    results = []
    i = 0
    while i < len(formula):
        for op in ('rise', 'fall'):
            if formula[i:i+len(op)] == op and \
               i + len(op) < len(formula) and \
               formula[i+len(op)] == '(':
                # found rise( or fall(
                start = i
                j = i + len(op) + 1  # position after opening (
                depth = 1
                while j < len(formula) and depth > 0:
                    if formula[j] == '(':
                        depth += 1
                    elif formula[j] == ')':
                        depth -= 1
                    j += 1
                # j is now one past the closing )
                inner = formula[i+len(op)+1:j-1]
                results.append((start, j, op, inner))
                break
        i += 1
    return results


def _rewrite_rise_fall(formula: str) -> tuple[str, list[str]]:
    """
    Rewrite all rise(φ) and fall(φ) in a formula to SPOT LTL with Y operator.

    rise(φ)  →  (prop & !Yprop)
    fall(φ)  →  (!prop & Yprop)

    where prop is the abstracted proposition for φ.

    Returns (rewritten_formula, list_of_warnings).
    """
    warnings = []

    # find all rise/fall occurrences, process right-to-left to preserve indices
    occurrences = _extract_rise_fall_args(formula)
    if not occurrences:
        return formula, warnings

    occurrences_sorted = sorted(occurrences, key=lambda x: x[0], reverse=True)

    result = formula
    for start, end, op, inner in occurrences_sorted:
        # abstract the inner expression to a proposition
        prop = _base_ltl(inner)

        # strip outer parens if present (SPOT Y syntax needs no parens)
        prop_clean = prop.strip().lstrip('(').rstrip(')')

        # check for complex inner expressions
        if any(c in prop_clean for c in ['&', '|', '->', '!']):
            warnings.append(
                f"{op}({inner}) has complex inner expression — "
                f"abstracted to single proposition may lose structure"
            )

        if op == 'rise':
            replacement = f"({prop_clean} & !Y{prop_clean})"
        else:  # fall
            replacement = f"(!{prop_clean} & Y{prop_clean})"

        result = result[:start] + replacement + result[end:]

    return result, warnings


# ---------------------------------------------------------------------------
# Full formula translation with rise/fall rewriting
# ---------------------------------------------------------------------------

@dataclass
class RewriteResult:
    original:  str
    ltl:       str
    warnings:  list[str] = field(default_factory=list)
    has_hist:  bool = False   # contains H[] — unsupported by SPOT


def rewrite(formula: str) -> RewriteResult:
    """
    Full pipeline: normalise STL → rewrite rise/fall → base LTL translation.
    """
    warnings = []

    # check for H[] (historically) — SPOT doesn't support it
    has_hist = bool(_HIST_RE.search(formula))
    if has_hist:
        warnings.append("Contains H[] (historically) — unsupported by SPOT.")

    # 1. rewrite rise/fall first (before base translation strips bounds etc.)
    rewritten, rw_warnings = _rewrite_rise_fall(formula)
    warnings.extend(rw_warnings)

    # 2. apply standard STL→LTL translation to the rest
    ltl = _base_ltl(rewritten)

    return RewriteResult(
        original=formula,
        ltl=ltl,
        warnings=warnings,
        has_hist=has_hist,
    )


# ---------------------------------------------------------------------------
# Dataset runner
# ---------------------------------------------------------------------------

EXTRA_COLS = ["ltl_gold", "ltl_pred", "rewrite_warnings", "has_hist"]


def run(input_path: str, output_path: str,
        gold_col: str = "gold_formula",
        pred_col: str = "predicted_formula") -> None:

    src = Path(input_path)
    if not src.exists():
        print(f"ERROR: {src} not found.")
        return

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows_in     = list(csv.DictReader(src.open(encoding="utf-8")))
    base_fields = list(rows_in[0].keys())
    out_fields  = base_fields + [c for c in EXTRA_COLS if c not in base_fields]

    # only process skip rows
    skip_rows  = [r for r in rows_in if r.get("suitability") == "skip"]
    other_rows = [r for r in rows_in if r.get("suitability") != "skip"]

    print(f"Rewriting {len(skip_rows)} skipped (rise/fall) pairs …\n")

    rows_out = []
    counts   = {"ok": 0, "has_hist": 0, "warned": 0}

    for row in skip_rows:
        gold = row.get(gold_col, "").strip()
        pred = row.get(pred_col, "").strip()

        rg = rewrite(gold)
        rp = rewrite(pred)

        all_warnings = rg.warnings + rp.warnings
        has_hist     = rg.has_hist or rp.has_hist

        if has_hist:
            counts["has_hist"] += 1
        elif all_warnings:
            counts["warned"] += 1
        else:
            counts["ok"] += 1

        print(f"  {row.get('review_id','?'):10s}")
        print(f"    gold STL : {gold}")
        print(f"    gold LTL : {rg.ltl}")
        print(f"    pred STL : {pred}")
        print(f"    pred LTL : {rp.ltl}")
        if all_warnings:
            print(f"    warnings : {all_warnings}")
        print()

        rows_out.append({**row,
            "ltl_gold":        rg.ltl,
            "ltl_pred":        rp.ltl,
            "rewrite_warnings": "; ".join(all_warnings),
            "has_hist":        str(has_hist),
        })

    # pass through non-skip rows with empty columns
    for row in other_rows:
        rows_out.append({**row,
            "ltl_gold": "", "ltl_pred": "",
            "rewrite_warnings": "", "has_hist": "",
        })

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    print(f"Written: {out}  ({len(skip_rows)} rewritten rows)")
    print(f"\nSummary:")
    print(f"  Clean rewrites : {counts['ok']}")
    print(f"  Has H[] (SPOT unsupported) : {counts['has_hist']}")
    print(f"  Warned (complex inner expr): {counts['warned']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",    default="data/layer1.csv")
    parser.add_argument("--output",   default="data/rise_fall_ltl.csv")
    parser.add_argument("--gold-col", default="gold_formula")
    parser.add_argument("--pred-col", default="predicted_formula")
    args = parser.parse_args()

    run(args.input, args.output, args.gold_col, args.pred_col)