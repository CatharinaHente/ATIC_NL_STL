#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CONDITIONS = [
    ("OpenAI direct", "openai_direct"),
    ("Anthropic direct", "anthropic_direct"),
    ("Clarify-inspired OpenAI", "clarify_openai"),
    ("Clarify-inspired Anthropic", "clarify_anthropic"),
]

DEADLINES_SECONDS = [2, 5, 10, 30]


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_mean(series: pd.Series) -> float:
    values = numeric(series).dropna()
    return float(values.mean()) if len(values) else math.nan


def percentile(series: pd.Series, value: float) -> float:
    values = numeric(series).dropna()
    return float(values.quantile(value)) if len(values) else math.nan


def read_jsonl(path: Path) -> pd.DataFrame:
    rows: list[dict] = []

    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, 1):
            if not line.strip():
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                rows.append(
                    {
                        "status": "error",
                        "sample_id": "",
                        "run_index": -1,
                        "error": (
                            f"Malformed JSONL line {line_number}: {exc}"
                        ),
                    }
                )

    return pd.DataFrame(rows)


def load_condition(
    condition: str,
    slug: str,
    run_root: Path,
    evaluation_root: Path,
) -> pd.DataFrame:
    detailed_path = evaluation_root / slug / "detailed_scores.csv"
    raw_path = run_root / f"{slug}.jsonl"

    if not detailed_path.exists():
        raise FileNotFoundError(f"Missing {detailed_path}")

    if not raw_path.exists():
        raise FileNotFoundError(f"Missing {raw_path}")

    details = pd.read_csv(detailed_path, keep_default_na=False)

    # Pandas may load evaluator CSV metric columns using StringDtype.
    # Convert Boolean words and numeric strings before groupby().mean().
    numeric_result_columns = [
        "run_index",
        "strict_action_correct",
        "acceptable_action_correct",
        "final_formula_present",
        "gold_parse_ok",
        "pred_parse_ok",
        "canonical_exact_match",
        "token_f1",
        "ast_f1",
        "operator_f1",
        "identifier_f1",
        "constant_f1",
        "clarification_slot_f1",
        "latency_seconds",
        "input_tokens",
        "output_tokens",
    ]

    replacements = {
        "true": "1",
        "false": "0",
        "yes": "1",
        "no": "0",
        "": pd.NA,
        "nan": pd.NA,
        "none": pd.NA,
        "null": pd.NA,
    }

    for column in numeric_result_columns:
        if column not in details.columns:
            continue

        values = (
            details[column]
            .astype("string")
            .str.strip()
            .str.lower()
            .replace(replacements)
        )

        details[column] = pd.to_numeric(
            values,
            errors="coerce",
        )
    raw = read_jsonl(raw_path)

    if "run_index" not in details.columns:
        details["run_index"] = 0

    # Keep the latest record for each logical sample/run.
    if len(raw):
        raw = raw.drop_duplicates(
            subset=["sample_id", "run_index"],
            keep="last",
        )

    latency_columns = [
        "sample_id",
        "run_index",
        "first_latency_seconds",
        "refinement_latency_seconds",
        "oracle_used",
    ]

    latency_columns = [
        column for column in latency_columns if column in raw.columns
    ]

    if latency_columns:
        details = details.merge(
            raw[latency_columns],
            on=["sample_id", "run_index"],
            how="left",
        )

    details["condition"] = condition
    return details


def summarize_condition(
    condition: str,
    details: pd.DataFrame,
    wall_times: pd.DataFrame,
) -> dict:
    n = len(details)

    formula_rows = details[
        details["predicted_formula"]
        .astype(str)
        .str.strip()
        .ne("")
    ]

    clarification_rows = details[
        details["task_mode"] == "clarify_then_translate"
    ]

    pass_mask = details["review_bucket"] == "automatic_pass"
    fail_mask = details["review_bucket"] == "automatic_fail"
    review_mask = details["review_bucket"] == "manual_review"

    wall_seconds = numeric(
        wall_times.loc[
            wall_times["condition"] == condition,
            "wall_seconds",
        ]
    ).sum()

    result = {
        "condition": condition,
        "n": n,
        "api_success_rate": (
            details["api_status"].eq("ok").mean()
        ),
        "strict_action_accuracy": safe_mean(
            details["strict_action_correct"]
        ),
        "acceptable_action_accuracy": safe_mean(
            details["acceptable_action_correct"]
        ),
        "formula_present_rate": safe_mean(
            details["final_formula_present"]
        ),
        "formula_parse_rate": safe_mean(
            formula_rows["pred_parse_ok"]
        ),
        "canonical_exact_match_rate": safe_mean(
            formula_rows["canonical_exact_match"]
        ),
        "mean_ast_f1": safe_mean(formula_rows["ast_f1"]),
        "mean_operator_f1": safe_mean(
            formula_rows["operator_f1"]
        ),
        "mean_identifier_f1": safe_mean(
            formula_rows["identifier_f1"]
        ),
        "mean_constant_f1": safe_mean(
            formula_rows["constant_f1"]
        ),
        "mean_clarification_slot_f1": safe_mean(
            clarification_rows["clarification_slot_f1"]
        ),
        "automatic_pass": int(pass_mask.sum()),
        "automatic_fail": int(fail_mask.sum()),
        "manual_review": int(review_mask.sum()),
        "automatic_pass_rate": float(pass_mask.mean()),
        "automatic_fail_rate": float(fail_mask.mean()),
        "manual_review_rate": float(review_mask.mean()),
        "confirmed_accuracy_lower_bound": float(
            pass_mask.mean()
        ),
        "accuracy_upper_bound_before_review": float(
            (pass_mask | review_mask).mean()
        ),
        "mean_latency_seconds": safe_mean(
            details["latency_seconds"]
        ),
        "median_latency_seconds": percentile(
            details["latency_seconds"], 0.50
        ),
        "p90_latency_seconds": percentile(
            details["latency_seconds"], 0.90
        ),
        "p95_latency_seconds": percentile(
            details["latency_seconds"], 0.95
        ),
        "median_first_stage_seconds": percentile(
            details.get(
                "first_latency_seconds",
                pd.Series(dtype=float),
            ),
            0.50,
        ),
        "median_refinement_seconds": percentile(
            details.loc[
                numeric(
                    details.get(
                        "refinement_latency_seconds",
                        pd.Series(index=details.index),
                    )
                ).fillna(0)
                > 0,
                "refinement_latency_seconds",
            ]
            if "refinement_latency_seconds" in details
            else pd.Series(dtype=float),
            0.50,
        ),
        "median_translate_latency_seconds": percentile(
            details.loc[
                details["task_mode"] == "translate",
                "latency_seconds",
            ],
            0.50,
        ),
        "median_clarification_latency_seconds": percentile(
            details.loc[
                details["task_mode"]
                == "clarify_then_translate",
                "latency_seconds",
            ],
            0.50,
        ),
        "mean_input_tokens": safe_mean(
            details["input_tokens"]
        ),
        "mean_output_tokens": safe_mean(
            details["output_tokens"]
        ),
        "wall_seconds": float(wall_seconds),
        "wall_minutes": float(wall_seconds / 60),
        "throughput_samples_per_minute": (
            float(n / (wall_seconds / 60))
            if wall_seconds > 0
            else math.nan
        ),
    }

    for deadline in DEADLINES_SECONDS:
        latency = numeric(details["latency_seconds"])
        result[f"completed_within_{deadline}s"] = float(
            (latency <= deadline).mean()
        )

    return result


def save_figure(
    figure: plt.Figure,
    path: Path,
) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def plot_outcomes(
    metrics: pd.DataFrame,
    output_dir: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(10, 5.5))

    x = np.arange(len(metrics))
    passes = metrics["automatic_pass"].to_numpy()
    reviews = metrics["manual_review"].to_numpy()
    failures = metrics["automatic_fail"].to_numpy()

    axis.bar(x, passes, label="Automatic pass")
    axis.bar(
        x,
        reviews,
        bottom=passes,
        label="Manual review",
    )
    axis.bar(
        x,
        failures,
        bottom=passes + reviews,
        label="Automatic fail",
    )

    axis.set_xticks(
        x,
        metrics["condition"],
        rotation=20,
        ha="right",
    )
    axis.set_ylabel("Samples")
    axis.set_title("Evaluation outcomes")
    axis.legend()

    save_figure(
        figure,
        output_dir / "01_outcomes.png",
    )


def plot_quality(
    metrics: pd.DataFrame,
    output_dir: Path,
) -> None:
    columns = [
        ("strict_action_accuracy", "Action accuracy"),
        ("canonical_exact_match_rate", "Canonical exact"),
        ("mean_ast_f1", "AST F1"),
        ("automatic_pass_rate", "Automatic pass"),
    ]

    figure, axis = plt.subplots(figsize=(11, 5.7))

    x = np.arange(len(metrics))
    width = 0.18

    for index, (column, label) in enumerate(columns):
        axis.bar(
            x + (index - 1.5) * width,
            metrics[column],
            width,
            label=label,
        )

    axis.set_xticks(
        x,
        metrics["condition"],
        rotation=20,
        ha="right",
    )
    axis.set_ylim(0, 1.05)
    axis.set_ylabel("Rate")
    axis.set_title("Core quality metrics")
    axis.legend()

    save_figure(
        figure,
        output_dir / "02_quality_metrics.png",
    )


def plot_latency_boxplot(
    details: pd.DataFrame,
    output_dir: Path,
) -> None:
    labels = []
    values = []

    for condition, group in details.groupby(
        "condition",
        sort=False,
    ):
        latency = numeric(
            group["latency_seconds"]
        ).dropna()

        if len(latency):
            labels.append(condition)
            values.append(latency.to_numpy())

    figure, axis = plt.subplots(figsize=(10, 5.7))

    axis.boxplot(
        values,
        tick_labels=labels,
        showfliers=True,
    )
    axis.tick_params(axis="x", rotation=20)
    axis.set_ylabel("Seconds per sample")
    axis.set_title("End-to-end latency distribution")

    save_figure(
        figure,
        output_dir / "03_latency_boxplot.png",
    )


def plot_latency_cdf(
    details: pd.DataFrame,
    output_dir: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(9, 5.5))

    for condition, group in details.groupby(
        "condition",
        sort=False,
    ):
        latency = np.sort(
            numeric(
                group["latency_seconds"]
            ).dropna().to_numpy()
        )

        if not len(latency):
            continue

        fraction = (
            np.arange(1, len(latency) + 1)
            / len(latency)
        )

        axis.plot(
            latency,
            fraction,
            label=condition,
        )

    axis.set_xlabel("End-to-end latency in seconds")
    axis.set_ylabel("Fraction of samples completed")
    axis.set_title("Latency cumulative distribution")
    axis.legend()

    save_figure(
        figure,
        output_dir / "04_latency_cdf.png",
    )


def plot_deadline_attainment(
    metrics: pd.DataFrame,
    output_dir: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(10.5, 5.7))

    x = np.arange(len(metrics))
    width = 0.18

    for index, deadline in enumerate(DEADLINES_SECONDS):
        axis.bar(
            x + (index - 1.5) * width,
            metrics[f"completed_within_{deadline}s"],
            width,
            label=f"Within {deadline}s",
        )

    axis.set_xticks(
        x,
        metrics["condition"],
        rotation=20,
        ha="right",
    )
    axis.set_ylim(0, 1.05)
    axis.set_ylabel("Fraction completed")
    axis.set_title("Response-deadline attainment")
    axis.legend()

    save_figure(
        figure,
        output_dir / "05_deadline_attainment.png",
    )


def plot_task_latency(
    details: pd.DataFrame,
    output_dir: Path,
) -> None:
    table = (
        details.assign(
            latency_seconds=numeric(
                details["latency_seconds"]
            )
        )
        .groupby(
            ["condition", "task_mode"]
        )["latency_seconds"]
        .median()
        .unstack()
    )

    figure, axis = plt.subplots(figsize=(10.5, 5.7))
    table.plot(kind="bar", ax=axis)

    axis.set_xlabel("")
    axis.set_ylabel("Median seconds per sample")
    axis.set_title("Median latency by task mode")
    axis.tick_params(axis="x", rotation=20)
    axis.legend(title="Task mode")

    save_figure(
        figure,
        output_dir / "06_latency_by_task_mode.png",
    )


def plot_quality_latency_tradeoff(
    metrics: pd.DataFrame,
    output_dir: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(8.5, 5.7))

    axis.scatter(
        metrics["median_latency_seconds"],
        metrics["automatic_pass_rate"],
        s=70,
    )

    for _, row in metrics.iterrows():
        axis.annotate(
            row["condition"],
            (
                row["median_latency_seconds"],
                row["automatic_pass_rate"],
            ),
            xytext=(5, 5),
            textcoords="offset points",
        )

    axis.set_xlabel("Median end-to-end latency in seconds")
    axis.set_ylabel("Automatic pass rate")
    axis.set_ylim(0, 1.05)
    axis.set_title("Quality–latency trade-off")

    save_figure(
        figure,
        output_dir / "07_quality_latency_tradeoff.png",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-tag",
        default="full_v1",
    )
    args = parser.parse_args()

    run_root = Path("runs/full_suite") / args.run_tag
    evaluation_root = (
        Path("evaluation/full_suite") / args.run_tag
    )
    output_dir = (
        Path("analysis/full_suite") / args.run_tag
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    timing_path = run_root / "wall_clock_times.csv"
    wall_times = pd.read_csv(timing_path)

    detail_frames = []
    summaries = []

    for condition, slug in CONDITIONS:
        details = load_condition(
            condition,
            slug,
            run_root,
            evaluation_root,
        )

        detail_frames.append(details)
        summaries.append(
            summarize_condition(
                condition,
                details,
                wall_times,
            )
        )

    combined = pd.concat(
        detail_frames,
        ignore_index=True,
    )
    metrics = pd.DataFrame(summaries)

    task_metrics = (
        combined.assign(
            automatic_pass=(
                combined["review_bucket"]
                == "automatic_pass"
            ).astype(float),
            latency_seconds=numeric(
                combined["latency_seconds"]
            ),
        )
        .groupby(
            ["condition", "task_mode"],
            dropna=False,
        )
        .agg(
            n=("sample_id", "count"),
            strict_action_accuracy=(
                "strict_action_correct",
                "mean",
            ),
            automatic_pass_rate=(
                "automatic_pass",
                "mean",
            ),
            median_latency_seconds=(
                "latency_seconds",
                "median",
            ),
            p95_latency_seconds=(
                "latency_seconds",
                lambda values: values.quantile(0.95),
            ),
            mean_ast_f1=("ast_f1", "mean"),
            mean_clarification_slot_f1=(
                "clarification_slot_f1",
                "mean",
            ),
        )
        .reset_index()
    )

    target_metrics = (
        combined.assign(
            automatic_pass=(
                combined["review_bucket"]
                == "automatic_pass"
            ).astype(float),
            latency_seconds=numeric(
                combined["latency_seconds"]
            ),
        )
        .groupby(
            [
                "condition",
                "target_paper",
                "case_type",
            ],
            dropna=False,
        )
        .agg(
            n=("sample_id", "count"),
            strict_action_accuracy=(
                "strict_action_correct",
                "mean",
            ),
            automatic_pass_rate=(
                "automatic_pass",
                "mean",
            ),
            median_latency_seconds=(
                "latency_seconds",
                "median",
            ),
            mean_ast_f1=("ast_f1", "mean"),
        )
        .reset_index()
    )

    metrics.to_csv(
        output_dir / "condition_metrics.csv",
        index=False,
    )
    task_metrics.to_csv(
        output_dir / "task_mode_metrics.csv",
        index=False,
    )
    target_metrics.to_csv(
        output_dir / "target_group_metrics.csv",
        index=False,
    )
    combined.to_csv(
        output_dir / "combined_detailed_scores.csv",
        index=False,
    )

    plot_outcomes(metrics, output_dir)
    plot_quality(metrics, output_dir)
    plot_latency_boxplot(combined, output_dir)
    plot_latency_cdf(combined, output_dir)
    plot_deadline_attainment(metrics, output_dir)
    plot_task_latency(combined, output_dir)
    plot_quality_latency_tradeoff(
        metrics,
        output_dir,
    )

    print()
    print("Condition metrics")
    print(metrics.to_string(index=False))
    print()
    print(f"Saved analysis to: {output_dir}")


if __name__ == "__main__":
    main()