#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DECISION_PASS = {"pass_equivalent"}
DECISION_FAIL = {"fail_semantic", "fail_clarification"}
DECISION_UNRESOLVED = {"", "uncertain"}


def as_numeric(series: pd.Series) -> pd.Series:
    values = (
        series.astype("string")
        .str.strip()
        .str.lower()
        .replace(
            {
                "true": "1",
                "false": "0",
                "yes": "1",
                "no": "0",
                "": pd.NA,
                "nan": pd.NA,
                "none": pd.NA,
                "null": pd.NA,
            }
        )
    )
    return pd.to_numeric(values, errors="coerce")


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = (
        z
        * math.sqrt(
            p * (1 - p) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)


def exact_mcnemar_p(b: int, c: int) -> float:
    """Two-sided exact McNemar/binomial p-value."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def load_inputs(
    scores_path: Path,
    reviews_path: Path,
    mapping_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scores = pd.read_csv(scores_path, keep_default_na=False)
    reviews = pd.read_csv(reviews_path, keep_default_na=False)
    mapping = pd.read_csv(mapping_path, keep_default_na=False)

    numeric_columns = [
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
        "first_latency_seconds",
        "refinement_latency_seconds",
        "input_tokens",
        "output_tokens",
    ]
    for column in numeric_columns:
        if column in scores.columns:
            scores[column] = as_numeric(scores[column])

    return scores, reviews, mapping


def apply_adjudication(
    scores: pd.DataFrame,
    reviews: pd.DataFrame,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    allowed = DECISION_PASS | DECISION_FAIL | {"uncertain", ""}
    invalid = sorted(
        {
            value
            for value in reviews["final_decision"].astype(str).str.strip()
            if value not in allowed
        }
    )
    if invalid:
        raise SystemExit(
            "Unknown final_decision value(s): " + ", ".join(invalid)
        )

    review_fields = reviews[
        [
            "review_id",
            "final_decision",
            "final_error_category",
            "final_notes",
            "equivalence_hint",
        ]
    ].copy()

    map_fields = mapping[
        [
            "review_id",
            "condition",
            "sample_id",
            "run_index",
            "predicted_formula",
            "gold_formula",
            "predicted_question",
            "review_reason",
        ]
    ].copy()

    map_fields["run_index"] = as_numeric(map_fields["run_index"]).fillna(0)
    review_map = map_fields.merge(review_fields, on="review_id", how="left")

    join_columns = [
        "condition",
        "sample_id",
        "run_index",
        "predicted_formula",
        "gold_formula",
        "predicted_question",
        "review_reason",
    ]

    merged = scores.merge(
        review_map,
        on=join_columns,
        how="left",
        validate="many_to_one",
    )

    merged["adjudicated_outcome"] = ""
    merged.loc[
        merged["review_bucket"] == "automatic_pass",
        "adjudicated_outcome",
    ] = "pass"
    merged.loc[
        merged["review_bucket"] == "automatic_fail",
        "adjudicated_outcome",
    ] = "fail"

    manual_mask = merged["review_bucket"] == "manual_review"
    merged.loc[
        manual_mask
        & merged["final_decision"].isin(DECISION_PASS),
        "adjudicated_outcome",
    ] = "pass"
    merged.loc[
        manual_mask
        & merged["final_decision"].isin(DECISION_FAIL),
        "adjudicated_outcome",
    ] = "fail"
    merged.loc[
        manual_mask
        & merged["final_decision"].isin(DECISION_UNRESOLVED),
        "adjudicated_outcome",
    ] = "unresolved"

    merged["adjudicated_correct"] = merged["adjudicated_outcome"].map(
        {"pass": 1.0, "fail": 0.0}
    )

    # Broad failure profile. Human final_error_category is retained for
    # semantic failures and can be more specific than these broad classes.
    merged["failure_class"] = ""
    auto_fail_map = {
        "Wrong initial action": "wrong_initial_action",
        "No final formula": "no_final_formula",
        "Predicted formula did not parse": "parse_failure",
        "API/provider error": "api_or_schema_error",
    }
    auto_fail_mask = merged["review_bucket"] == "automatic_fail"
    merged.loc[auto_fail_mask, "failure_class"] = (
        merged.loc[auto_fail_mask, "review_reason"]
        .map(auto_fail_map)
        .fillna("other_automatic_failure")
    )

    manual_fail_mask = (
        (merged["review_bucket"] == "manual_review")
        & (merged["adjudicated_outcome"] == "fail")
    )
    merged.loc[manual_fail_mask, "failure_class"] = (
        merged.loc[manual_fail_mask, "final_error_category"]
        .replace("", pd.NA)
        .fillna("manual_semantic_or_question_failure")
    )

    return merged


def condition_metrics(details: pd.DataFrame) -> pd.DataFrame:
    rows = []
    fastest_latency = details.groupby("condition")["latency_seconds"].median().min()

    for condition, group in details.groupby("condition", sort=False):
        n = len(group)
        passed = int((group["adjudicated_outcome"] == "pass").sum())
        failed = int((group["adjudicated_outcome"] == "fail").sum())
        unresolved = int((group["adjudicated_outcome"] == "unresolved").sum())
        resolved = passed + failed

        ci_low, ci_high = wilson_interval(passed, resolved)
        lower_bound = passed / n if n else math.nan
        upper_bound = (passed + unresolved) / n if n else math.nan
        final_accuracy = passed / n if n and unresolved == 0 else math.nan

        formula_rows = group[group["final_formula_present"] == 1]
        clarify_rows = group[group["task_mode"] == "clarify_then_translate"]
        expected_rows = group[group["case_type"] == "expected_strength"]
        limitation_rows = group[group["case_type"] == "limitation_probe"]
        robotics_rows = group[group["group"] == "robotics_real_world"]
        median_latency = group["latency_seconds"].median()

        row = {
            "condition": condition,
            "n": n,
            "pass_count": passed,
            "fail_count": failed,
            "unresolved_count": unresolved,
            "resolved_count": resolved,
            "adjudicated_accuracy": final_accuracy,
            "resolved_accuracy": passed / resolved if resolved else math.nan,
            "accuracy_ci95_low_resolved": ci_low,
            "accuracy_ci95_high_resolved": ci_high,
            "accuracy_lower_bound_all_rows": lower_bound,
            "accuracy_upper_bound_all_rows": upper_bound,
            "api_success_rate": (group["api_status"] == "ok").mean(),
            "strict_action_accuracy": group["strict_action_correct"].mean(),
            "acceptable_action_accuracy": group["acceptable_action_correct"].mean(),
            "formula_present_rate": group["final_formula_present"].mean(),
            "overall_exact_match_rate": group["canonical_exact_match"].fillna(0).sum() / n,
            "conditional_exact_match_rate": formula_rows["canonical_exact_match"].mean(),
            "formula_parse_rate": formula_rows["pred_parse_ok"].mean(),
            "mean_ast_f1": formula_rows["ast_f1"].mean(),
            "mean_operator_f1": formula_rows["operator_f1"].mean(),
            "mean_identifier_f1": formula_rows["identifier_f1"].mean(),
            "mean_constant_f1": formula_rows["constant_f1"].mean(),
            "clarification_success_rate": (
                (clarify_rows["adjudicated_outcome"] == "pass").mean()
                if len(clarify_rows)
                else math.nan
            ),
            "expected_strength_success_rate": (
                (expected_rows["adjudicated_outcome"] == "pass").mean()
                if len(expected_rows)
                else math.nan
            ),
            "limitation_probe_success_rate": (
                (limitation_rows["adjudicated_outcome"] == "pass").mean()
                if len(limitation_rows)
                else math.nan
            ),
            "robotics_success_rate": (
                (robotics_rows["adjudicated_outcome"] == "pass").mean()
                if len(robotics_rows)
                else math.nan
            ),
            "median_latency_seconds": median_latency,
            "p90_latency_seconds": group["latency_seconds"].quantile(0.90),
            "p95_latency_seconds": group["latency_seconds"].quantile(0.95),
            "within_5s_rate": (group["latency_seconds"] <= 5).mean(),
            "within_10s_rate": (group["latency_seconds"] <= 10).mean(),
            "within_30s_rate": (group["latency_seconds"] <= 30).mean(),
            "relative_speed_score": (
                min(1.0, fastest_latency / median_latency)
                if median_latency and not math.isnan(median_latency)
                else math.nan
            ),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def grouped_metrics(details: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rows = []
    for group_key, group in details.groupby(["condition"] + keys, dropna=False, sort=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        condition = group_key[0]
        key_values = group_key[1:]
        passed = int((group["adjudicated_outcome"] == "pass").sum())
        unresolved = int((group["adjudicated_outcome"] == "unresolved").sum())
        row = {
            "condition": condition,
            **{key: value for key, value in zip(keys, key_values)},
            "n": len(group),
            "pass_count": passed,
            "unresolved_count": unresolved,
            "accuracy_lower_bound": passed / len(group),
            "accuracy_upper_bound": (passed + unresolved) / len(group),
            "acceptable_action_accuracy": group["acceptable_action_correct"].mean(),
            "formula_present_rate": group["final_formula_present"].mean(),
            "mean_ast_f1": group["ast_f1"].mean(),
            "median_latency_seconds": group["latency_seconds"].median(),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def pairwise_tests(details: pd.DataFrame) -> pd.DataFrame:
    conditions = list(dict.fromkeys(details["condition"].tolist()))
    rows = []
    usable = details[details["adjudicated_outcome"].isin(["pass", "fail"])].copy()
    usable["pass_bool"] = usable["adjudicated_outcome"] == "pass"

    for i, left in enumerate(conditions):
        for right in conditions[i + 1 :]:
            a = usable[usable["condition"] == left][
                ["sample_id", "pass_bool"]
            ].rename(columns={"pass_bool": "left_pass"})
            b = usable[usable["condition"] == right][
                ["sample_id", "pass_bool"]
            ].rename(columns={"pass_bool": "right_pass"})
            paired = a.merge(b, on="sample_id", how="inner")
            left_only = int((paired["left_pass"] & ~paired["right_pass"]).sum())
            right_only = int((~paired["left_pass"] & paired["right_pass"]).sum())
            rows.append(
                {
                    "condition_a": left,
                    "condition_b": right,
                    "paired_n": len(paired),
                    "a_only_pass": left_only,
                    "b_only_pass": right_only,
                    "accuracy_a": paired["left_pass"].mean(),
                    "accuracy_b": paired["right_pass"].mean(),
                    "paired_accuracy_difference_a_minus_b": (
                        paired["left_pass"].mean()
                        - paired["right_pass"].mean()
                    ),
                    "mcnemar_exact_p": exact_mcnemar_p(
                        left_only, right_only
                    ),
                }
            )
    return pd.DataFrame(rows)


def save_plot(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_accuracy_bounds(metrics: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(metrics))
    lower = metrics["accuracy_lower_bound_all_rows"].to_numpy()
    upper = metrics["accuracy_upper_bound_all_rows"].to_numpy()
    resolved = metrics["resolved_accuracy"].to_numpy()

    ax.hlines(y, lower, upper, linewidth=6, alpha=0.35)
    ax.scatter(resolved, y, s=70, label="Resolved-row estimate")
    ax.scatter(lower, y, marker="|", s=180, label="Lower bound")
    ax.scatter(upper, y, marker="|", s=180, label="Upper bound")
    ax.set_yticks(y, metrics["condition"])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Accuracy")
    ax.set_title("Adjudicated accuracy and unresolved-review bounds")
    ax.legend(loc="lower right")
    save_plot(fig, out / "01_accuracy_bounds")


def plot_accuracy_ci(metrics: pd.DataFrame, out: Path) -> None:
    complete = metrics[metrics["unresolved_count"] == 0].copy()
    if complete.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(complete))
    point = complete["adjudicated_accuracy"].to_numpy()
    low = complete["accuracy_ci95_low_resolved"].to_numpy()
    high = complete["accuracy_ci95_high_resolved"].to_numpy()
    errors = np.vstack([point - low, high - point])
    ax.errorbar(point, y, xerr=errors, fmt="o", capsize=5)
    ax.set_yticks(y, complete["condition"])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Adjudicated end-to-end accuracy")
    ax.set_title("Final accuracy with 95% Wilson intervals")
    save_plot(fig, out / "02_accuracy_ci")


def plot_hexagon_profiles(metrics: pd.DataFrame, out: Path) -> None:
    axes = [
        ("adjudicated_accuracy", "Accuracy"),
        ("acceptable_action_accuracy", "Action"),
        ("formula_present_rate", "Coverage"),
        ("mean_ast_f1", "AST F1"),
        ("clarification_success_rate", "Clarification"),
        ("relative_speed_score", "Relative speed"),
    ]
    # When reviews remain unresolved, use the lower bound rather than inventing
    # a final accuracy.
    plot_metrics = metrics.copy()
    plot_metrics["adjudicated_accuracy"] = plot_metrics[
        "adjudicated_accuracy"
    ].fillna(plot_metrics["accuracy_lower_bound_all_rows"])

    angles = np.linspace(0, 2 * np.pi, len(axes), endpoint=False)
    angles = np.concatenate([angles, angles[:1]])

    fig, subplot_axes = plt.subplots(
        2,
        2,
        figsize=(11, 9),
        subplot_kw={"polar": True},
    )
    for axis, (_, row) in zip(subplot_axes.flat, plot_metrics.iterrows()):
        values = [
            float(row[column]) if not pd.isna(row[column]) else 0.0
            for column, _ in axes
        ]
        values = values + values[:1]
        axis.plot(angles, values, marker="o")
        axis.fill(angles, values, alpha=0.18)
        axis.set_xticks(
            angles[:-1],
            [label for _, label in axes],
        )
        axis.set_ylim(0, 1)
        axis.set_yticks([0.25, 0.5, 0.75, 1.0])
        axis.set_title(row["condition"], pad=18)
    fig.suptitle(
        "Six-dimensional performance profiles",
        y=1.01,
        fontsize=15,
    )
    save_plot(fig, out / "03_hexagon_profiles")


def plot_quality_latency(metrics: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    y = metrics["adjudicated_accuracy"].fillna(
        metrics["accuracy_lower_bound_all_rows"]
    )
    sizes = 100 + 700 * metrics["formula_present_rate"]
    ax.scatter(
        metrics["median_latency_seconds"],
        y,
        s=sizes,
        alpha=0.75,
    )
    for _, row in metrics.iterrows():
        value = (
            row["adjudicated_accuracy"]
            if not pd.isna(row["adjudicated_accuracy"])
            else row["accuracy_lower_bound_all_rows"]
        )
        ax.annotate(
            row["condition"],
            (row["median_latency_seconds"], value),
            xytext=(6, 5),
            textcoords="offset points",
        )
    ax.set_xscale("log")
    ax.set_xlim(left=max(0.5, metrics["median_latency_seconds"].min() * 0.75))
    ax.set_ylim(0, 1)
    ax.set_xlabel("Median end-to-end latency in seconds (log scale)")
    ax.set_ylabel("Adjudicated accuracy")
    ax.set_title("Quality–latency–coverage trade-off")
    save_plot(fig, out / "04_quality_latency_pareto")


def plot_failure_profile(details: pd.DataFrame, out: Path) -> pd.DataFrame:
    failures = details[details["adjudicated_outcome"] == "fail"].copy()
    table = pd.crosstab(failures["condition"], failures["failure_class"])
    proportions = table.div(table.sum(axis=1), axis=0)

    fig, ax = plt.subplots(figsize=(11, 5.8))
    proportions.plot(kind="barh", stacked=True, ax=ax)
    ax.set_xlabel("Share of adjudicated failures")
    ax.set_ylabel("")
    ax.set_title("Failure-mode profile")
    ax.legend(
        title="Failure class",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
    )
    save_plot(fig, out / "05_failure_profile")
    return table.reset_index()


def plot_target_heatmap(target: pd.DataFrame, out: Path) -> None:
    pivot = target.pivot_table(
        index="condition",
        columns="target_paper",
        values="accuracy_lower_bound",
        aggfunc="mean",
    )
    fig, ax = plt.subplots(figsize=(11.5, 5.5))
    image = ax.imshow(
        pivot.to_numpy(),
        aspect="auto",
        vmin=0,
        vmax=1,
    )
    ax.set_xticks(
        np.arange(len(pivot.columns)),
        pivot.columns,
        rotation=25,
        ha="right",
    )
    ax.set_yticks(
        np.arange(len(pivot.index)),
        pivot.index,
    )
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            value = pivot.iloc[i, j]
            ax.text(
                j,
                i,
                "" if pd.isna(value) else f"{value:.2f}",
                ha="center",
                va="center",
            )
    fig.colorbar(image, ax=ax, label="Adjudicated pass rate")
    ax.set_title("Performance by benchmark target")
    save_plot(fig, out / "06_target_heatmap")


def plot_latency_ecdf(details: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for condition, group in details.groupby("condition", sort=False):
        values = np.sort(group["latency_seconds"].dropna().to_numpy())
        if not len(values):
            continue
        fraction = np.arange(1, len(values) + 1) / len(values)
        ax.plot(values, fraction, label=condition)
    ax.set_xscale("log")
    ax.set_xlabel("End-to-end latency in seconds (log scale)")
    ax.set_ylabel("Fraction completed")
    ax.set_title("Latency cumulative distribution")
    ax.legend()
    save_plot(fig, out / "07_latency_ecdf_log")


def plot_exact_and_coverage(metrics: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    x = np.arange(len(metrics))
    width = 0.25
    ax.bar(
        x - width,
        metrics["formula_present_rate"],
        width,
        label="Formula coverage",
    )
    ax.bar(
        x,
        metrics["overall_exact_match_rate"],
        width,
        label="Overall exact match",
    )
    ax.bar(
        x + width,
        metrics["conditional_exact_match_rate"],
        width,
        label="Exact match | formula produced",
    )
    ax.set_xticks(
        x,
        metrics["condition"],
        rotation=20,
        ha="right",
    )
    ax.set_ylim(0, 1)
    ax.set_ylabel("Rate")
    ax.set_title("Coverage and exact-match metrics")
    ax.legend()
    save_plot(fig, out / "08_coverage_and_exact_match")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scores",
        type=Path,
        default=Path("combined_detailed_scores.csv"),
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=Path("manual_review_decisions.csv"),
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("manual_review_mapping.csv"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("paper_results"),
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    scores, reviews, mapping = load_inputs(
        args.scores,
        args.reviews,
        args.mapping,
    )
    details = apply_adjudication(scores, reviews, mapping)

    unresolved = reviews[
        reviews["final_decision"].isin(["", "uncertain"])
    ].copy()
    unresolved.to_csv(
        args.out_dir / "unresolved_reviews.csv",
        index=False,
    )

    metrics = condition_metrics(details)
    task = grouped_metrics(details, ["task_mode"])
    target = grouped_metrics(
        details,
        ["target_paper", "case_type"],
    )
    pairwise = pairwise_tests(details)

    failure_counts = plot_failure_profile(details, args.out_dir)

    equivalences = (
        details[
            (details["review_bucket"] == "manual_review")
            & (details["adjudicated_outcome"] == "pass")
        ]
        .groupby(["condition", "final_error_category"], dropna=False)
        .size()
        .reset_index(name="count")
    )

    details.to_csv(
        args.out_dir / "adjudicated_detailed_scores.csv",
        index=False,
    )
    metrics.to_csv(
        args.out_dir / "cleaned_condition_metrics.csv",
        index=False,
    )
    task.to_csv(
        args.out_dir / "cleaned_task_mode_metrics.csv",
        index=False,
    )
    target.to_csv(
        args.out_dir / "cleaned_target_metrics.csv",
        index=False,
    )
    pairwise.to_csv(
        args.out_dir / "pairwise_mcnemar_tests.csv",
        index=False,
    )
    failure_counts.to_csv(
        args.out_dir / "failure_profile_counts.csv",
        index=False,
    )
    equivalences.to_csv(
        args.out_dir / "accepted_equivalence_profile.csv",
        index=False,
    )

    plot_accuracy_bounds(metrics, args.out_dir)
    plot_accuracy_ci(metrics, args.out_dir)
    plot_hexagon_profiles(metrics, args.out_dir)
    plot_quality_latency(metrics, args.out_dir)
    plot_target_heatmap(target, args.out_dir)
    plot_latency_ecdf(details, args.out_dir)
    plot_exact_and_coverage(metrics, args.out_dir)

    print(metrics.to_string(index=False))
    print()
    print(f"Unresolved unique review rows: {len(unresolved)}")
    print(f"Outputs written to: {args.out_dir}")
    if len(unresolved):
        print(
            "Final accuracy remains a bound until every final_decision "
            "is pass_equivalent, fail_semantic, or fail_clarification."
        )


if __name__ == "__main__":
    main()
