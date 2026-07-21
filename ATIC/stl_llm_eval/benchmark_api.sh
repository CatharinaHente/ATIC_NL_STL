#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS_DIR="${HARNESS_DIR:-$SCRIPT_DIR}"
DATASET="${DATASET:-nl_stl_benchmark_150_context_enriched.csv}"
OPENAI_MODEL="${OPENAI_MODEL:-gpt-5.6-terra}"
ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-sonnet-5}"
CONCURRENCY="${CONCURRENCY:-2}"

cd "$HARNESS_DIR"

prevent_sleep() {
  if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -i "$@"
  else
    "$@"
  fi
}

case "${1:-}" in
  setup)
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    [[ -f .env ]] || cp .env.example .env
    echo "Add OPENAI_API_KEY and ANTHROPIC_API_KEY to .env."
    ;;

  mock)
    mkdir -p runs evaluation/mock_context_v2
    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers mock \
      --limit 5 \
      --output runs/mock_context_v2.jsonl

    python evaluate_results.py \
      --dataset "$DATASET" \
      --results runs/mock_context_v2.jsonl \
      --out-dir evaluation/mock_context_v2

    command -v open >/dev/null 2>&1 && open evaluation/mock_context_v2/report.html || true
    ;;

  one-openai)
    mkdir -p runs evaluation/first_openai_context_v2

    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai \
      --ids NLSTL150-001 \
      --dry-run

    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai \
      --openai-model "$OPENAI_MODEL" \
      --ids NLSTL150-001 \
      --concurrency 1 \
      --output runs/first_openai_context_v2.jsonl

    python evaluate_results.py \
      --dataset "$DATASET" \
      --results runs/first_openai_context_v2.jsonl \
      --out-dir evaluation/first_openai_context_v2

    command -v open >/dev/null 2>&1 && open evaluation/first_openai_context_v2/report.html || true
    ;;

  one-both)
    mkdir -p runs evaluation/first_both_context_v2

    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai anthropic \
      --openai-model "$OPENAI_MODEL" \
      --anthropic-model "$ANTHROPIC_MODEL" \
      --ids NLSTL150-001 \
      --concurrency 1 \
      --output runs/first_both_context_v2.jsonl

    python evaluate_results.py \
      --dataset "$DATASET" \
      --results runs/first_both_context_v2.jsonl \
      --out-dir evaluation/first_both_context_v2

    command -v open >/dev/null 2>&1 && open evaluation/first_both_context_v2/report.html || true
    ;;

  pilot-openai)
    mkdir -p runs evaluation/openai_pilot_context_v2

    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai \
      --openai-model "$OPENAI_MODEL" \
      --case-type expected_strength \
      --limit 5 \
      --concurrency "$CONCURRENCY" \
      --output runs/openai_pilot_context_v2.jsonl

    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai \
      --openai-model "$OPENAI_MODEL" \
      --case-type limitation_probe \
      --limit 5 \
      --concurrency "$CONCURRENCY" \
      --output runs/openai_pilot_context_v2.jsonl

    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai \
      --openai-model "$OPENAI_MODEL" \
      --task-mode clarify_then_translate \
      --limit 5 \
      --concurrency "$CONCURRENCY" \
      --output runs/openai_pilot_context_v2.jsonl

    python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai \
      --openai-model "$OPENAI_MODEL" \
      --group robotics_real_world \
      --limit 5 \
      --concurrency "$CONCURRENCY" \
      --output runs/openai_pilot_context_v2.jsonl

    python evaluate_results.py \
      --dataset "$DATASET" \
      --results runs/openai_pilot_context_v2.jsonl \
      --out-dir evaluation/openai_pilot_context_v2

    command -v open >/dev/null 2>&1 && open evaluation/openai_pilot_context_v2/report.html || true
    ;;

  full-openai)
    mkdir -p runs evaluation/openai_full_context_v2

    prevent_sleep python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai \
      --openai-model "$OPENAI_MODEL" \
      --concurrency "$CONCURRENCY" \
      --output runs/openai_full_context_v2.jsonl

    python evaluate_results.py \
      --dataset "$DATASET" \
      --results runs/openai_full_context_v2.jsonl \
      --out-dir evaluation/openai_full_context_v2

    command -v open >/dev/null 2>&1 && open evaluation/openai_full_context_v2/report.html || true
    ;;

  full-both)
    mkdir -p runs evaluation/openai_anthropic_full_context_v2

    prevent_sleep python run_benchmark.py \
      --dataset "$DATASET" \
      --providers openai anthropic \
      --openai-model "$OPENAI_MODEL" \
      --anthropic-model "$ANTHROPIC_MODEL" \
      --concurrency "$CONCURRENCY" \
      --output runs/openai_anthropic_full_context_v2.jsonl

    python evaluate_results.py \
      --dataset "$DATASET" \
      --results runs/openai_anthropic_full_context_v2.jsonl \
      --out-dir evaluation/openai_anthropic_full_context_v2

    command -v open >/dev/null 2>&1 && open evaluation/openai_anthropic_full_context_v2/report.html || true
    ;;

  *)
    echo "Usage: $0 {setup|mock|one-openai|one-both|pilot-openai|full-openai|full-both}"
    exit 1
    ;;
esac
