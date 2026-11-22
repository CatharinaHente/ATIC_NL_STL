"""
Command line entry point.

    # ATIC manual review (110 unique pairs), default config
    python -m equivalence --dataset manual_review --out data/results/manual_review.csv

    # any other table
    python -m equivalence --input my.csv --gold-col gold_stl --pred-col pred_stl \\
                          [--id-col id] [--context-col signal_context] --out results.csv
"""
import argparse
from dataclasses import fields
from pathlib import Path

from .datasets import load_manual_review, load_table
from .pipeline import Config, run_dataset


def main():
    ap = argparse.ArgumentParser(prog="python -m equivalence")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dataset", choices=["manual_review"])
    src.add_argument("--input")
    ap.add_argument("--gold-col"), ap.add_argument("--pred-col")
    ap.add_argument("--id-col"), ap.add_argument("--context-col")
    ap.add_argument("--out", required=True)
    ap.add_argument("--all-rows", action="store_true", help="manual_review: check all 151 condition rows, not the 110 unique pairs")
    ap.add_argument("--no-spot", action="store_true")
    ap.add_argument("--no-stlsat", action="store_true")
    ap.add_argument("--engine", default=Config.stlsat_engine, choices=["smt", "fol", "tableau"])
    ap.add_argument("--until", default=Config.until_semantics, choices=["standard", "inclusive"])
    ap.add_argument("--spot-timeout", type=float, default=Config.spot_timeout)
    ap.add_argument("--stlsat-timeout", type=float, default=Config.stlsat_timeout)
    ap.add_argument("--horizon-factor", type=float, default=Config.horizon_factor)
    ap.add_argument("--horizon-minimum", type=int, default=Config.horizon_minimum)
    a = ap.parse_args()

    if a.dataset == "manual_review":
        df = load_manual_review(unique=not a.all_rows)
    else:
        if not (a.gold_col and a.pred_col):
            ap.error("--input requires --gold-col and --pred-col")
        df = load_table(a.input, a.gold_col, a.pred_col, a.id_col, a.context_col)

    cfg = Config(run_spot=not a.no_spot, run_stlsat=not a.no_stlsat, stlsat_engine=a.engine,
                 until_semantics=a.until, spot_timeout=a.spot_timeout, stlsat_timeout=a.stlsat_timeout,
                 horizon_factor=a.horizon_factor, horizon_minimum=a.horizon_minimum)
    out = run_dataset(df, cfg)
    for f in fields(cfg):
        if f.name != "symmetric_functions":
            out[f"cfg_{f.name}"] = getattr(cfg, f.name)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"\nwritten {a.out} ({len(out)} rows)")


if __name__ == "__main__":
    main()
