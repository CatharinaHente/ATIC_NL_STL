#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from prompts import build_clarification_followup, build_user_prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview initial and clarification prompts without API calls.")
    parser.add_argument("--dataset", type=Path, default=Path("nl_stl_benchmark_150_context_enriched.csv"))
    parser.add_argument("--id", default="NLSTL150-021")
    args = parser.parse_args()

    with args.dataset.open(newline="", encoding="utf-8-sig") as f:
        rows = {row["id"]: row for row in csv.DictReader(f)}
    sample = rows.get(args.id)
    if sample is None:
        raise SystemExit(f"Sample not found: {args.id}")

    print("=== INITIAL PROMPT ===")
    print(build_user_prompt(sample))

    if sample.get("oracle_answer"):
        print("\n=== SIMULATED FOLLOW-UP PROMPT ===")
        print(build_clarification_followup(
            sample,
            sample.get("clarification_question") or "Please clarify the missing information.",
            sample["oracle_answer"],
        ))
    else:
        print("\nThis row has no oracle-answer follow-up.")


if __name__ == "__main__":
    main()
