# Signal-context update for the NL–STL benchmark

This package replaces the sparse `signal_context` values with canonical context
for all 150 samples.

## Files

- `nl_stl_benchmark_150_context_enriched.csv`: execution dataset.
- `nl_stl_benchmark_150_context_enriched.xlsx`: readable dataset and audit workbook.
- `nl_stl_signal_context_audit.csv`: old context versus new contexts.
- `prompts.py`: replacement prompt module.
- `benchmark_api.sh`: replacement Bash wrapper using the enriched dataset.
- `preview_context_flow.py`: prints both prompt stages without API calls.

## What changed

Every row has `signal_context`, used on the initial model turn.

Interactive rows also have `signal_context_after_clarification`. This context is
included only after the model chooses `clarify` and receives `oracle_answer`.
This avoids leaking missing units, thresholds, referents, or counter availability
on the initial turn.

The original context is preserved in `signal_context_original`.

## Install into the existing `stl_llm_eval` folder

Back up the current files first:

```bash
cp prompts.py prompts_before_context_update.py
cp benchmark_api.sh benchmark_api_before_context_update.sh
```

Copy the new files into the folder:

```bash
cp /path/to/nl_stl_context_update/prompts.py ./prompts.py
cp /path/to/nl_stl_context_update/benchmark_api.sh ./benchmark_api.sh
cp /path/to/nl_stl_context_update/nl_stl_benchmark_150_context_enriched.csv ./
chmod +x benchmark_api.sh
```

## Verify without spending tokens

```bash
python preview_context_flow.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --id NLSTL150-021
```

Or inspect only the initial prompt through the benchmark runner:

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --providers openai \
  --ids NLSTL150-021 \
  --dry-run
```

## Run a new one-sample test

```bash
./benchmark_api.sh one-openai
```

The replacement Bash script writes to new `*_context_v2` result files. This is
important because the benchmark runner resumes existing files and would
otherwise skip samples that were already completed using the old context.

## Run the context-sensitive clarification example directly

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --providers openai \
  --ids NLSTL150-021 \
  --concurrency 1 \
  --output runs/context_v2_021.jsonl

python evaluate_results.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --results runs/context_v2_021.jsonl \
  --out-dir evaluation/context_v2_021

open evaluation/context_v2_021/report.html
```

## Run the pilot

```bash
./benchmark_api.sh pilot-openai
```

## Run all 150 OpenAI samples

```bash
./benchmark_api.sh full-openai
```
