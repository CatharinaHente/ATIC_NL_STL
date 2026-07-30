# NL–STL manual adjudication and paper-metrics workflow
(integration of manual review queue into results)

## Purpose 

The evaluator AI sends valid but non-identical formulas to manual review because
syntactic comparison cannot establish semantic equivalence. 

Review data content: 
- 600 condition/sample rows;
- 151 condition-level manual-review rows;
- 110 unique semantic judgments after identical formula/question cases are
  collapsed across conditions (actual review count)

## Files

- `manual_review_workbook.xlsx` — formatted review workbook
- `manual_review_decisions.csv` — editable review table consumed by the script
- `manual_review_mapping.csv` — mapping from 110 unique judgments to 151
  condition-level rows
- `combined_detailed_scores.csv` — original 600-row evaluator output
- `adjudicate_and_plot.py` — recalculates cleaned metrics, error profiles,
  paired tests, and publication figures
- `condition_metrics.csv`, `task_mode_metrics.csv`,
  `target_group_metrics.csv` — original pre-adjudication summaries

## Procedure

1. Review formulas without looking at model/condition identity 
   by 2 indep. reviewers (Polina, Catharina)
3. Each reviewer fills their own decision, error category, and notes
4. Resolve disagreements in `final_decision`, `final_error_category`, and
   `final_notes`
5. Every `final_decision` should be one of:
   - `pass_equivalent`
   - `fail_semantic`
   - `fail_clarification`
   - `uncertain`

### Decision rubric

`pass_equivalent`
: The predicted output is semantically acceptable under the supplied signal
  context, even though syntax differs

`fail_semantic`
: The formula changes temporal bounds, temporal operators, trigger/event
  semantics, scope, nesting, identifiers, thresholds, or another meaningful
  part of the requirement

`fail_clarification`
: The formula is exact/acceptable, but the generated question targets the
  wrong missing slot or does not obtain enough information

`uncertain`
: Available context is insufficient to adjudicate confidently

## Failure analysis

Automatic failures already have broad evaluator categories:

- wrong initial action;
- no final formula;
- parse failure;
- API/schema error.

For adjudicated manual failures, `final_error_category` supplies the semantic
category. This makes it possible to distinguish over-clarification,
post-clarification abstention, temporal errors, identifier errors, and valid
non-identical formulas that the automatic evaluator could not recognize.

### Important equivalence rules

Often acceptable when supported by the signal context:

- Boolean shorthand `x` versus `x = 1`;
- `!x` versus `x = 0`;
- `abs(a-b)` versus `abs(b-a)`;
- redundant parentheses;
- commutative ordering of conjunction/disjunction;
- reversed arguments of a distance function only when the context defines it
  as symmetric.

Usually not equivalent:

- `rise(x)` versus `x = 1`;
- `F(rise(x))` versus `F(x = 1)`;
- bounded versus unbounded temporal operators;
- different trigger/consequent scope;
- changed temporal nesting;
- altered thresholds or time bounds.

## Run cleaned analysis

Install dependencies in the benchmark virtual environment:

```bash
python -m pip install pandas matplotlib numpy
```

Run:

```bash
python adjudicate_and_plot.py \
  --scores combined_detailed_scores.csv \
  --reviews manual_review_decisions.csv \
  --mapping manual_review_mapping.csv \
  --out-dir paper_results
```

note: the script does **not** call any LLM API and does not rerun the benchmark

## Outputs

### Clean tables

- `adjudicated_detailed_scores.csv`
- `cleaned_condition_metrics.csv`
- `cleaned_task_mode_metrics.csv`
- `cleaned_target_metrics.csv`
- `pairwise_mcnemar_tests.csv`
- `failure_profile_counts.csv`
- `accepted_equivalence_profile.csv`
- `unresolved_reviews.csv`

### Figures (png and pdf)

- `01_accuracy_bounds` — conservative lower/upper bounds while reviews remain
- `02_accuracy_ci` — final adjudicated accuracy with 95% Wilson intervals;
  generated when all reviews are resolved
- `03_hexagon_profiles` — six-dimensional radar/hexagon overview
- `04_quality_latency_pareto` — accuracy, latency, and formula coverage
- `05_failure_profile` — broad failure-mode composition
- `06_target_heatmap` — accuracy by benchmark target
- `07_latency_ecdf_log` — tail-aware latency comparison on a log scale
- `08_coverage_and_exact_match` — separates formula coverage from conditional
  exact-match rate

