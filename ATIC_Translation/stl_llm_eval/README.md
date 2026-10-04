# NL–STL LLM evaluation harness

This folder can be copied into the repository that contains ClarifySTL.

It provides:

- `run_benchmark.py`: OpenAI, Claude, ClarifySTL, and mock runner
- `evaluate_results.py`: automatic first-pass scoring and review queue
- `stl_metrics.py`: lightweight parser, canonicalizer, and structural metrics
- `clarify_adapter.py`: subprocess adapter for a local ClarifySTL checkout
- `clarify_wrapper_template.py`: the only file that normally needs project-specific edits

## 1. Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Put the provider keys in `.env`. Never commit `.env`.

## 2. Verify the plumbing without spending API credit

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150.csv \
  --providers mock \
  --limit 5 \
  --output runs/mock.jsonl

python evaluate_results.py \
  --dataset nl_stl_benchmark_150.csv \
  --results runs/mock.jsonl \
  --out-dir evaluation/mock
```

The mock adapter intentionally uses the gold fields. It is only a pipeline test.

## 3. Run one real sample

Inspect the prompt:

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150.csv \
  --providers openai \
  --limit 1 \
  --dry-run
```

Run one sample against both providers:

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150.csv \
  --providers openai anthropic \
  --limit 1 \
  --concurrency 1 \
  --output runs/pilot.jsonl
```

Evaluate:

```bash
python evaluate_results.py \
  --dataset nl_stl_benchmark_150.csv \
  --results runs/pilot.jsonl \
  --out-dir evaluation/pilot
```

Open `evaluation/pilot/report.html`.

## 4. Add ClarifySTL

Copy `clarify_wrapper_template.py` to a convenient location in the ClarifySTL
repo, rename it `clarify_wrapper.py`, and replace `run_your_clarify_code`.

The wrapper receives:

```json
{
  "stage": "initial",
  "sample": {"id": "...", "requirement_nl": "..."},
  "first_decision": null,
  "oracle_answer": null
}
```

or, for the second turn:

```json
{
  "stage": "refine",
  "sample": {"id": "...", "requirement_nl": "..."},
  "first_decision": {"action": "clarify", "...": "..."},
  "oracle_answer": "the fixed answer stored in the benchmark"
}
```

It must print one JSON response following:

```json
{
  "action": "translate",
  "stl": "G(...)",
  "defect_types": [],
  "clarification_question": null,
  "assumptions": [],
  "confidence": 0.9
}
```

Then set in `.env`:

```bash
CLARIFY_COMMAND="python path/to/clarify_wrapper.py"
```

Test it:

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150.csv \
  --providers clarify \
  --limit 1 \
  --output runs/clarify-pilot.jsonl
```

## 5. Overnight run

First complete a 20-row pilot. Then:

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150.csv \
  --providers openai anthropic clarify \
  --runs 1 \
  --concurrency 3 \
  --output runs/full.jsonl
```

The file is appended after every completed item. Re-running the same command
resumes and skips successful `(provider, model, sample, run_index)` entries.

For repeated-run stability:

```bash
python run_benchmark.py \
  --dataset nl_stl_benchmark_150.csv \
  --providers openai anthropic \
  --runs 3 \
  --concurrency 3 \
  --output runs/repeated.jsonl
```

## 6. Useful filters

```bash
# One exact sample
--ids NLSTL150-001

# Only ClarifySTL-targeted challenge rows
--target ClarifySTL --case-type limitation_probe

# Only interactive rows
--task-mode clarify_then_translate

# Formula-first robotics rows
--group robotics_real_world
```

## 7. What is automatically evaluated?

- API/schema success
- initial action: translate, clarify, or abstain
- whether clarification was triggered when required
- STL parser success for the included core grammar
- canonical exact match
- token, AST, operator, identifier, and constant F1
- clarification-question slot coverage
- latency and token use
- automatic-pass, automatic-fail, and manual-review buckets

The evaluator is intentionally conservative. A valid formula that differs from
the gold formula goes to manual review unless an external semantic checker marks
it equivalent.

## 8. Optional semantic checker

Pass a local command to the evaluator:

```bash
python evaluate_results.py \
  --dataset nl_stl_benchmark_150.csv \
  --results runs/full.jsonl \
  --out-dir evaluation/full \
  --semantic-command "python my_trace_equivalence_checker.py"
```

The checker receives:

```json
{
  "gold_stl": "...",
  "predicted_stl": "...",
  "sample": {"id": "..."}
}
```

and can return:

```json
{
  "semantic_equivalent": true,
  "semantic_agreement": 1.0,
  "counterexample_found": false
}
```

This is the place to connect RTAMT, Breach, S-TaLiRo, or the monitor already
used by ClarifySTL. Trace agreement is not a formal proof, so preserve the
counterexample-search settings in the result.

## 9. Experimental hygiene

- Freeze the dataset before the final run.
- Pin exact provider model IDs and record the date.
- Use the same prompt and structured schema for providers.
- Do not expose gold formulas, oracle answers, or source labels in the initial prompt.
- Keep raw JSONL results under versioned experiment directories.
- Manually audit a random sample of automatic passes and failures.
