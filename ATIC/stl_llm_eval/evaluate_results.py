from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import html
import json
import math
from pathlib import Path
import statistics
import subprocess
import shlex

from stl_metrics import compare_formulas, slot_scores


def load_dataset(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def load_results(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                rows.append({
                    "status": "error",
                    "provider": "unknown",
                    "model": "unknown",
                    "sample_id": "",
                    "run_index": -1,
                    "error": f"Malformed JSONL line {line_number}: {exc}",
                })
    return rows


def expected_action(task_mode: str) -> str:
    return {
        "translate": "translate",
        "clarify_then_translate": "clarify",
        "abstain_or_request_context": "abstain",
    }.get(task_mode, "")


def acceptable_initial_action(task_mode: str, action: str) -> bool:
    if task_mode == "abstain_or_request_context":
        return action in {"abstain", "clarify"}
    return action == expected_action(task_mode)


def semantic_hook(command: str, gold: str, predicted: str, sample: dict) -> dict:
    if not command:
        return {}
    request = {
        "gold_stl": gold,
        "predicted_stl": predicted,
        "sample": sample,
    }
    proc = subprocess.run(
        shlex.split(command),
        input=json.dumps(request, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        return {"semantic_hook_error": proc.stderr[-1000:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"semantic_hook_error": "Hook stdout was not valid JSON."}


def flatten_list(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(str(x) for x in value)
    return str(value)


def score_record(record: dict, sample: dict, semantic_command: str) -> dict:
    detail = {
        "provider": record.get("provider", ""),
        "model": record.get("model", ""),
        "sample_id": record.get("sample_id", ""),
        "run_index": record.get("run_index", 0),
        "api_status": record.get("status", ""),
        "group": sample.get("group", ""),
        "target_paper": sample.get("target_paper", ""),
        "case_type": sample.get("case_type", ""),
        "task_mode": sample.get("task_mode", ""),
        "difficulty": sample.get("difficulty", ""),
        "latency_seconds": record.get("latency_seconds"),
        "error": record.get("error", ""),
    }
    if record.get("status") != "ok":
        detail.update({
            "strict_action_correct": 0,
            "acceptable_action_correct": 0,
            "final_formula_present": 0,
            "review_bucket": "automatic_fail",
            "review_reason": "API/provider error",
        })
        return detail

    first = record.get("first_decision") or {}
    final = record.get("final_decision") or first
    first_action = first.get("action", "")
    final_action = final.get("action", "")
    task_mode = sample.get("task_mode", "")
    strict_action = first_action == expected_action(task_mode)
    acceptable_action = acceptable_initial_action(task_mode, first_action)

    detail.update({
        "first_action": first_action,
        "final_action": final_action,
        "strict_action_correct": int(strict_action),
        "acceptable_action_correct": int(acceptable_action),
        "oracle_used": int(bool(record.get("oracle_used"))),
        "predicted_defect_types": flatten_list(first.get("defect_types")),
        "predicted_question": first.get("clarification_question") or "",
        "predicted_formula": final.get("stl") or "",
        "confidence": final.get("confidence"),
        "assumptions": flatten_list(final.get("assumptions")),
        "input_tokens": (
            (record.get("first_usage") or {}).get("input_tokens") or 0
        ) + (
            (record.get("final_usage") or {}).get("input_tokens") or 0
            if record.get("oracle_used") else 0
        ),
        "output_tokens": (
            (record.get("first_usage") or {}).get("output_tokens") or 0
        ) + (
            (record.get("final_usage") or {}).get("output_tokens") or 0
            if record.get("oracle_used") else 0
        ),
    })

    if task_mode == "translate":
        gold = sample.get("gold_stl", "")
    elif task_mode == "clarify_then_translate":
        gold = sample.get("gold_after_clarification", "")
    else:
        gold = ""

    predicted = final.get("stl") or ""
    detail["gold_formula"] = gold
    detail["final_formula_present"] = int(bool(predicted))

    if task_mode == "clarify_then_translate":
        detail.update(slot_scores(
            first.get("clarification_question") or "",
            sample.get("clarification_question") or "",
            sample.get("defect_type") or "",
        ))
        detail["predicted_slots"] = flatten_list(detail["predicted_slots"])
        detail["gold_slots"] = flatten_list(detail["gold_slots"])

    if gold and predicted:
        metrics = compare_formulas(predicted, gold)
        detail.update(metrics)
        for key in ("extra_identifiers_vs_gold", "extra_constants_vs_gold"):
            detail[key] = flatten_list(detail[key])
        detail.update(semantic_hook(semantic_command, gold, predicted, sample))

    # Conservative triage: only exact structural agreement auto-passes.
    if not acceptable_action:
        bucket = "automatic_fail"
        reason = "Wrong initial action"
    elif task_mode == "abstain_or_request_context":
        if first_action in {"abstain", "clarify"} and not predicted:
            bucket = "automatic_pass"
            reason = "Appropriate abstention/context request"
        else:
            bucket = "manual_review"
            reason = "Out-of-scope row produced a formula"
    elif not predicted:
        bucket = "automatic_fail"
        reason = "No final formula"
    elif detail.get("pred_parse_ok") is False:
        bucket = "automatic_fail"
        reason = "Predicted formula did not parse"
    elif detail.get("canonical_exact_match"):
        if task_mode == "clarify_then_translate" and detail.get("clarification_slot_f1", 0) < 0.5:
            bucket = "manual_review"
            reason = "Formula exact, but clarification question may target the wrong slot"
        else:
            bucket = "automatic_pass"
            reason = "Canonical exact match"
    elif detail.get("semantic_equivalent") is True:
        bucket = "automatic_pass"
        reason = "External semantic checker marked equivalent"
    elif detail.get("semantic_equivalent") is False:
        bucket = "automatic_fail"
        reason = "External semantic checker found disagreement"
    else:
        bucket = "manual_review"
        reason = "Valid but non-identical formula; semantic equivalence not established"

    detail["review_bucket"] = bucket
    detail["review_reason"] = reason
    return detail


def mean(values):
    vals = [float(v) for v in values if v not in (None, "")]
    return statistics.fmean(vals) if vals else ""


def summarize(details: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    dimensions = [
        "provider", "model", "group", "target_paper", "case_type", "task_mode"
    ]
    for d in details:
        key = tuple(d.get(k, "") for k in dimensions)
        groups[key].append(d)

    summaries = []
    for key, items in sorted(groups.items()):
        n = len(items)
        ok = [x for x in items if x.get("api_status") == "ok"]
        parsed = [x for x in ok if x.get("pred_parse_ok") is not None]
        row = dict(zip(dimensions, key))
        row.update({
            "n": n,
            "api_success_rate": len(ok) / n if n else 0,
            "strict_action_accuracy": mean(x.get("strict_action_correct") for x in items),
            "acceptable_action_accuracy": mean(x.get("acceptable_action_correct") for x in items),
            "formula_parse_rate": mean(x.get("pred_parse_ok") for x in parsed),
            "canonical_exact_match_rate": mean(x.get("canonical_exact_match") for x in items),
            "mean_token_f1": mean(x.get("token_f1") for x in items),
            "mean_ast_f1": mean(x.get("ast_f1") for x in items),
            "mean_operator_f1": mean(x.get("operator_f1") for x in items),
            "mean_identifier_f1": mean(x.get("identifier_f1") for x in items),
            "mean_constant_f1": mean(x.get("constant_f1") for x in items),
            "mean_clarification_slot_f1": mean(x.get("clarification_slot_f1") for x in items),
            "mean_latency_seconds": mean(x.get("latency_seconds") for x in items),
            "mean_input_tokens": mean(x.get("input_tokens") for x in items),
            "mean_output_tokens": mean(x.get("output_tokens") for x in items),
            "automatic_pass": sum(x.get("review_bucket") == "automatic_pass" for x in items),
            "automatic_fail": sum(x.get("review_bucket") == "automatic_fail" for x in items),
            "manual_review": sum(x.get("review_bucket") == "manual_review" for x in items),
        })
        summaries.append(row)
    return summaries


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value):
    if isinstance(value, float):
        return f"{value:.3f}"
    return "" if value is None else str(value)


def write_html(path: Path, summaries: list[dict], details: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    overall = [
        s for s in summaries
        if s["group"] == "" and s["target_paper"] == ""
    ]
    review = [d for d in details if d.get("review_bucket") == "manual_review"]

    def table(rows, columns):
        head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
        body = []
        for row in rows:
            cells = "".join(
                f"<td>{html.escape(fmt(row.get(c, '')))}</td>" for c in columns
            )
            body.append(f"<tr>{cells}</tr>")
        return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    summary_cols = [
        "provider", "model", "group", "target_paper", "case_type", "task_mode",
        "n", "api_success_rate", "strict_action_accuracy",
        "canonical_exact_match_rate", "formula_parse_rate",
        "mean_ast_f1", "mean_clarification_slot_f1",
        "automatic_pass", "automatic_fail", "manual_review",
    ]
    review_cols = [
        "provider", "model", "sample_id", "target_paper", "task_mode",
        "first_action", "predicted_formula", "gold_formula",
        "review_reason",
    ]

    content = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>NL–STL Evaluation</title>
<style>
body{{font-family:Arial,sans-serif;margin:32px;color:#222}}
table{{border-collapse:collapse;width:100%;margin-bottom:28px;font-size:13px}}
th,td{{border:1px solid #ccc;padding:6px;vertical-align:top}}
th{{background:#1f4e78;color:white;position:sticky;top:0}}
tr:nth-child(even){{background:#f7f9fb}}
code{{white-space:pre-wrap}}
.badge{{display:inline-block;padding:4px 8px;background:#e8eef6;border-radius:6px}}
</style></head><body>
<h1>NL–STL Evaluation Report</h1>
<p class="badge">Detailed rows: {len(details)} · Manual review: {len(review)}</p>
<h2>Grouped results</h2>
{table(summaries, summary_cols)}
<h2>Manual-review queue</h2>
{table(review, review_cols)}
</body></html>"""
    path.write_text(content, encoding="utf-8")


def add_overall_summaries(details: list[dict], summaries: list[dict]) -> list[dict]:
    # Add provider/model totals with blank stratification dimensions.
    grouped = defaultdict(list)
    for d in details:
        grouped[(d.get("provider", ""), d.get("model", ""))].append(d)
    synthetic = []
    for (provider, model), items in grouped.items():
        temp = []
        for x in items:
            y = dict(x)
            y.update({"group": "", "target_paper": "", "case_type": "", "task_mode": ""})
            temp.append(y)
        synthetic.extend(summarize(temp))
    return synthetic + summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NL-to-STL benchmark JSONL.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("evaluation"))
    parser.add_argument(
        "--semantic-command",
        default="",
        help="Optional command reading {gold_stl,predicted_stl,sample} JSON on stdin.",
    )
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    raw_results = load_results(args.results)
    details = []
    for record in raw_results:
        sample = dataset.get(record.get("sample_id", ""))
        if not sample:
            details.append({
                "provider": record.get("provider", ""),
                "model": record.get("model", ""),
                "sample_id": record.get("sample_id", ""),
                "api_status": "error",
                "error": "Sample ID not found in dataset",
                "review_bucket": "automatic_fail",
                "review_reason": "Unknown sample ID",
            })
            continue
        details.append(score_record(record, sample, args.semantic_command))

    summaries = add_overall_summaries(details, summarize(details))
    write_csv(args.out_dir / "detailed_scores.csv", details)
    write_csv(args.out_dir / "summary_scores.csv", summaries)
    write_html(args.out_dir / "report.html", summaries, details)

    counts = defaultdict(int)
    for d in details:
        counts[d.get("review_bucket", "unknown")] += 1
    print(f"Scored {len(details)} results.")
    print(dict(counts))
    print(f"Detailed: {args.out_dir / 'detailed_scores.csv'}")
    print(f"Summary:  {args.out_dir / 'summary_scores.csv'}")
    print(f"Report:   {args.out_dir / 'report.html'}")


if __name__ == "__main__":
    main()
