# ClarifySTL-inspired reconstruction

This folder contains a **clean-room reconstruction**, not the missing original
ClarifySTL implementation. It follows the public guide/prompt architecture:

1. retrieve related Ambiguity_A/B examples;
2. detect incompleteness/ambiguity;
3. generate one focused clarification question;
4. refine the requirement with the benchmark oracle answer;
5. re-check the refined requirement;
6. translate to STL or abstain.

## Install into `stl_llm_eval`

Copy these three files into the benchmark folder:

```bash
cp clarify_wrapper.py /path/to/stl_llm_eval/clarify_wrapper.py
cp Ambiguity_A.json /path/to/stl_llm_eval/Ambiguity_A.json
cp Ambiguity_B.json /path/to/stl_llm_eval/Ambiguity_B.json
```

The existing benchmark requirements already provide `openai`, `anthropic`,
`pydantic`, and `python-dotenv`.

## Configure `.env`

OpenAI-backed reconstruction:

```dotenv
CLARIFY_COMMAND=python clarify_wrapper.py
CLARIFY_MODEL=clarifystl-inspired-openai
CLARIFY_BACKEND=openai
CLARIFY_OPENAI_MODEL=${OPENAI_MODEL}
```

Anthropic-backed reconstruction:

```dotenv
CLARIFY_COMMAND=python clarify_wrapper.py
CLARIFY_MODEL=clarifystl-inspired-anthropic
CLARIFY_BACKEND=anthropic
CLARIFY_ANTHROPIC_MODEL=${ANTHROPIC_MODEL}
```

Environment-variable interpolation in `.env` depends on `python-dotenv` and the
shell. The safest option is to write the exact model ID instead of `${...}`.

Optional explicit data paths:

```dotenv
CLARIFY_AMBIGUITY_A=/absolute/path/to/Ambiguity_A.json
CLARIFY_AMBIGUITY_B=/absolute/path/to/Ambiguity_B.json
```

When the JSON files sit beside `clarify_wrapper.py`, explicit paths are not
required.

## Smoke test without the benchmark

The program requires a configured API backend. Test the native CLI:

```bash
cat > requirement.txt <<'EOF'
The vehicle must keep a safe distance from the obstacle.
EOF

python clarify_wrapper.py \
  --input requirement.txt \
  --output result.json \
  --human \
  --signal-context 'Numeric signal: obstacle_distance [m].'
```

## Benchmark test

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --providers clarify \
  --ids NLSTL150-001 \
  --concurrency 1 \
  --output runs/clarify_inspired_one.jsonl
```

Then test one clarification row:

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --providers clarify \
  --ids NLSTL150-021 \
  --concurrency 1 \
  --output runs/clarify_inspired_interactive.jsonl
```

## Matched 20-row pilot

Extract the IDs from the OpenAI pilot and run exactly those samples:

```bash
PILOT_IDS=$(python - <<'PY'
import json
ids = []
with open('runs/openai_pilot_context_v2.jsonl', encoding='utf-8') as f:
    for line in f:
        sample_id = json.loads(line).get('sample_id')
        if sample_id and sample_id not in ids:
            ids.append(sample_id)
print(' '.join(ids))
PY
)

caffeinate -i python run_benchmark.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --providers clarify \
  --ids $PILOT_IDS \
  --concurrency 1 \
  --output runs/clarify_inspired_pilot.jsonl

python evaluate_results.py \
  --dataset nl_stl_benchmark_150_context_enriched.csv \
  --results runs/clarify_inspired_pilot.jsonl \
  --out-dir evaluation/clarify_inspired_pilot
```

## Fair reporting

Report this provider as `ClarifySTL-inspired`, with the backend named explicitly.
It uses the benchmark oracle answer after a clarification request, just like the
OpenAI and Anthropic benchmark conditions. It must not be described as the
original ClarifySTL artifact.
