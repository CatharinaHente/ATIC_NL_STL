#!/usr/bin/env bash
set -euo pipefail

# Four matched conditions:
#   1. Direct OpenAI
#   2. Direct Anthropic
#   3. Clarify-inspired workflow with OpenAI backend
#   4. Clarify-inspired workflow with Anthropic backend

DATASET="${DATASET:-nl_stl_benchmark_150_context_enriched.csv}"
RUN_TAG="${RUN_TAG:-full_v1}"
CONCURRENCY="${CONCURRENCY:-1}"
RUNS="${RUNS:-1}"

RUN_DIR="runs/full_suite/$RUN_TAG"
EVAL_DIR="evaluation/full_suite/$RUN_TAG"
ANALYSIS_DIR="analysis/full_suite/$RUN_TAG"
TIMING_FILE="$RUN_DIR/wall_clock_times.csv"

mkdir -p "$RUN_DIR" "$EVAL_DIR" "$ANALYSIS_DIR"

for required in \
    "$DATASET" \
    run_benchmark.py \
    evaluate_results.py \
    clarify_adapter.py \
    clarify_wrapper.py \
    analyze_full_suite.py \
    .env
do
    if [[ ! -f "$required" ]]; then
        echo "Missing required file: $required" >&2
        exit 1
    fi
done

# Read model IDs safely from .env without sourcing shell-sensitive lines such as
# CLARIFY_COMMAND=python clarify_wrapper.py.
read_env() {
    python -c '
from dotenv import dotenv_values
import sys

value = dotenv_values(".env").get(sys.argv[1], "")
print("" if value is None else value)
' "$1"
}

OPENAI_MODEL="$(read_env OPENAI_MODEL)"
ANTHROPIC_MODEL="$(read_env ANTHROPIC_MODEL)"

if [[ -z "$OPENAI_MODEL" ]]; then
    echo "OPENAI_MODEL is missing from .env" >&2
    exit 1
fi

if [[ -z "$ANTHROPIC_MODEL" ]]; then
    echo "ANTHROPIC_MODEL is missing from .env" >&2
    exit 1
fi

echo "OpenAI model:    $OPENAI_MODEL"
echo "Anthropic model: $ANTHROPIC_MODEL"
echo "Dataset:         $DATASET"
echo "Concurrency:     $CONCURRENCY"

if [[ ! -f "$TIMING_FILE" ]]; then
    echo \
"condition,started_utc,finished_utc,wall_seconds,concurrency,results_file" \
        > "$TIMING_FILE"
fi

prevent_sleep() {
    if command -v caffeinate >/dev/null 2>&1; then
        caffeinate -i "$@"
    else
        "$@"
    fi
}

timed_run() {
    local condition="$1"
    local results_file="$2"
    shift 2

    local started_utc
    local finished_utc
    local start_epoch
    local finish_epoch
    local wall_seconds

    echo
    echo "============================================================"
    echo "Running: $condition"
    echo "Output:  $results_file"
    echo "============================================================"

    started_utc="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    start_epoch="$(date +%s)"

    prevent_sleep "$@"

    finish_epoch="$(date +%s)"
    finished_utc="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    wall_seconds=$((finish_epoch - start_epoch))

    echo \
"$condition,$started_utc,$finished_utc,$wall_seconds,$CONCURRENCY,$results_file" \
        >> "$TIMING_FILE"

    echo "$condition completed in $wall_seconds seconds."
}

# ---------------------------------------------------------------------------
# 1. Direct OpenAI
# ---------------------------------------------------------------------------

timed_run \
    "OpenAI direct" \
    "$RUN_DIR/openai_direct.jsonl" \
    env OPENAI_MODEL="$OPENAI_MODEL" \
    python run_benchmark.py \
        --dataset "$DATASET" \
        --providers openai \
        --openai-model "$OPENAI_MODEL" \
        --runs "$RUNS" \
        --concurrency "$CONCURRENCY" \
        --output "$RUN_DIR/openai_direct.jsonl"

python evaluate_results.py \
    --dataset "$DATASET" \
    --results "$RUN_DIR/openai_direct.jsonl" \
    --out-dir "$EVAL_DIR/openai_direct"

# ---------------------------------------------------------------------------
# 2. Direct Anthropic
# ---------------------------------------------------------------------------

timed_run \
    "Anthropic direct" \
    "$RUN_DIR/anthropic_direct.jsonl" \
    env ANTHROPIC_MODEL="$ANTHROPIC_MODEL" \
    python run_benchmark.py \
        --dataset "$DATASET" \
        --providers anthropic \
        --anthropic-model "$ANTHROPIC_MODEL" \
        --runs "$RUNS" \
        --concurrency "$CONCURRENCY" \
        --output "$RUN_DIR/anthropic_direct.jsonl"

python evaluate_results.py \
    --dataset "$DATASET" \
    --results "$RUN_DIR/anthropic_direct.jsonl" \
    --out-dir "$EVAL_DIR/anthropic_direct"

# ---------------------------------------------------------------------------
# 3. Clarify-inspired workflow with the same OpenAI backend
# ---------------------------------------------------------------------------

timed_run \
    "Clarify-inspired OpenAI" \
    "$RUN_DIR/clarify_openai.jsonl" \
    env \
        CLARIFY_BACKEND=openai \
        CLARIFY_MODEL=clarifystl-inspired-openai-v1 \
        CLARIFY_OPENAI_MODEL="$OPENAI_MODEL" \
    python run_benchmark.py \
        --dataset "$DATASET" \
        --providers clarify \
        --clarify-model clarifystl-inspired-openai-v1 \
        --runs "$RUNS" \
        --concurrency "$CONCURRENCY" \
        --output "$RUN_DIR/clarify_openai.jsonl"

python evaluate_results.py \
    --dataset "$DATASET" \
    --results "$RUN_DIR/clarify_openai.jsonl" \
    --out-dir "$EVAL_DIR/clarify_openai"

# ---------------------------------------------------------------------------
# 4. Clarify-inspired workflow with the same Anthropic backend
# ---------------------------------------------------------------------------

timed_run \
    "Clarify-inspired Anthropic" \
    "$RUN_DIR/clarify_anthropic.jsonl" \
    env \
        CLARIFY_BACKEND=anthropic \
        CLARIFY_MODEL=clarifystl-inspired-anthropic-v1 \
        CLARIFY_ANTHROPIC_MODEL="$ANTHROPIC_MODEL" \
    python run_benchmark.py \
        --dataset "$DATASET" \
        --providers clarify \
        --clarify-model clarifystl-inspired-anthropic-v1 \
        --runs "$RUNS" \
        --concurrency "$CONCURRENCY" \
        --output "$RUN_DIR/clarify_anthropic.jsonl"

python evaluate_results.py \
    --dataset "$DATASET" \
    --results "$RUN_DIR/clarify_anthropic.jsonl" \
    --out-dir "$EVAL_DIR/clarify_anthropic"

# ---------------------------------------------------------------------------
# Combined metrics and plots
# ---------------------------------------------------------------------------

python analyze_full_suite.py \
    --run-tag "$RUN_TAG"

echo
echo "Full suite complete."
echo "Raw results:       $RUN_DIR"
echo "Evaluation reports: $EVAL_DIR"
echo "Combined analysis:  $ANALYSIS_DIR"
echo
echo "Open the combined plots and metrics with:"
echo "open \"$ANALYSIS_DIR\""