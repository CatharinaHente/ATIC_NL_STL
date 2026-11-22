"""
Dataset loaders.  Every loader returns a DataFrame with the standard columns

    pair_id   gold   pred   context   (+ any metadata columns)

so the checker never needs to know where the data came from.  To add a dataset either
call `load_table(path, gold_col=..., pred_col=...)` or write a small loader below that
maps its columns onto these names.  Notation differences are handled by the parser.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]          # ATIC_NL_STL/
MANUAL_REVIEW = ROOT / "ATIC_ManualReview"


def load_table(path, gold_col: str, pred_col: str, id_col: Optional[str] = None,
               context_col: Optional[str] = None, **read_kw) -> pd.DataFrame:
    """Generic loader for .csv / .jsonl / .json / .xlsx files."""
    path = Path(path)
    if path.suffix == ".csv":
        df = pd.read_csv(path, **read_kw)
    elif path.suffix == ".jsonl":
        df = pd.read_json(path, lines=True, **read_kw)
    elif path.suffix == ".json":
        df = pd.read_json(path, **read_kw)
    elif path.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, **read_kw)
    else:
        raise ValueError(f"unsupported file type {path.suffix}")
    out = df.copy()
    out["pair_id"] = df[id_col].astype(str) if id_col else [f"row-{i}" for i in range(len(df))]
    out["gold"] = df[gold_col]
    out["pred"] = df[pred_col]
    out["context"] = df[context_col] if context_col else None
    return out


def load_manual_review(root: Path = MANUAL_REVIEW, unique: bool = True) -> pd.DataFrame:
    """ATIC manual-review sample.

    Formulas come from manual_review_mapping.csv (151 condition-level rows); the human
    adjudication and the signal context (which declares Boolean vs numeric signals) come
    from manual_review_decisions.csv (110 unique judgements).  Note: the decisions file
    truncates two predicted formulas with '...' (MR-067, MR-068), so it must not be used as
    the formula source.

    unique=True collapses the 151 rows to the 110 unique (gold, pred) pairs — every
    review_id has exactly one formula pair — and keeps the list of conditions.
    """
    mapping = pd.read_csv(root / "manual_review_mapping.csv")
    decisions = pd.read_csv(root / "manual_review_decisions.csv")
    meta_cols = ["review_id", "target_paper", "case_type", "task_mode", "difficulty",
                 "signal_context", "final_decision", "final_error_category", "final_notes",
                 "equivalence_hint"]
    df = mapping.merge(decisions[meta_cols], on="review_id", how="left", validate="many_to_one")
    df = df.rename(columns={"gold_formula": "gold", "predicted_formula": "pred",
                            "signal_context": "context"})
    # fail_clarification = formula acceptable, clarification question wrong (see ATIC_ManualReview/README.md)
    df["human_accepts_formula"] = df["final_decision"].isin(["pass_equivalent", "fail_clarification"])
    if unique:
        agg = {c: "first" for c in df.columns if c not in ("review_id", "condition", "provider", "model", "run_index", "sample_id")}
        conds = df.groupby("review_id")["condition"].apply(lambda s: "; ".join(sorted(set(s))))
        n = df.groupby("review_id").size().rename("n_condition_rows")
        df = (df.groupby("review_id").agg({**agg, "sample_id": "first"})
                .join(conds.rename("conditions")).join(n).reset_index())
    df["pair_id"] = df["review_id"]
    return df
