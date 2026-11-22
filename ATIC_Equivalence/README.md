# ATIC Equivalence

Formal (LLM-free) comparison of a **gold** and a **predicted** STL formula, using
[SPOT](https://spot.lre.epita.fr/) (LTL automata) and [STLSat](https://github.com/ZamponiMarco/stlsat)
(bounded STL satisfiability). Beyond equivalent / not equivalent, every pair gets a **strictness verdict**:

| verdict | meaning |
|---|---|
| `EQUIVALENT` | gold ⊆ pred and pred ⊆ gold |
| `PRED_STRONGER` | pred ⊆ gold only: the prediction is stricter (admits fewer signals) |
| `PRED_WEAKER` | gold ⊆ pred only: the prediction is looser |
| `INCOMPARABLE` | neither implies the other |

Results and the SPOT vs STLSat comparison are in **`analysis.ipynb`**.

## Usage

```bash
conda activate ATIC                     # needs: spot (conda-forge), pandas, matplotlib; stlsat on PATH
python -m equivalence --dataset manual_review --out data/results/manual_review_smt.csv
python -m equivalence --input other.csv --gold-col gold --pred-col pred [--id-col id] [--context-col ctx] --out res.csv
python -m equivalence --help            # engine, timeouts, horizon, until semantics, --no-spot / --no-stlsat
python -m unittest discover tests       # ~1 min, incl. SPOT-vs-STLSat differential test
```

```python
from equivalence.pipeline import Checker
with Checker() as c:
    c.check("G(rise(a = 1) -> F[0,5] b)", "G(rise(a) -> F[0,5](b = 1))")   # -> dict with both tools' verdicts and timings
```

## Architecture

```
dataset (any table)           datasets.py      -> pair_id, gold, pred, context
      │
      ▼
parser.py        dialect-tolerant parser -> typed AST (ast.py)
      │
normalize.py     signal types (context or inference), b = 1 -> b, joint interval scaling, canonical form
      │
      ├── syntactic stage   canonical(gold) == canonical(pred)?   (µs; sound, incomplete)
      │
      ├── SPOT            past.py (exact past/rise/fall elimination)
      │                   atoms.py (predicate abstraction + ordering axioms)
      │                   spot_backend.py (bounded ops -> X-chains, two containment checks)
      │
      └── STLSat          cap unbounded ops at a per-pair horizon (flagged bounded_approx)
                          past.py, semantics.py (until reading), stlsat_backend.py (two SAT queries)
```

`pipeline.py` orchestrates and records status, verdict, solver time and wall time per tool.

## Semantics decisions (all configurable in `pipeline.Config`)

* **Discrete time**, one interval unit = one sample. This matches STLSat and SPOT's X operator.
  Real-valued bounds are scaled to integers with **one factor for both formulas**.
* **Boolean signals**: `x`, `x = 1`, `!x`, `x = 0` are only identified when `x` is Boolean. Types come
  from the dataset's `signal_context`, otherwise from inference over both formulas.
* **Until** (`until_semantics`): the default `standard` is φ U[a,b] ψ ⇔ ∃t'∈[a,b] ψ(t') ∧ φ on [0,t').
  STLSat natively uses the *inclusive* reading (φ also at t'), so U/R are rewritten exactly before they reach
  STLSat (`semantics.py`). `inclusive` makes SPOT follow STLSat instead.
* **Past operators / edges**: Y is false at t = 0, i.e. signals are taken to be false before the trace starts
  (`rise(φ)` holds at 0 iff φ(0)). The encoding is exact (see `past.py`).
* **Unbounded operators**: exact in SPOT (LTL's G/F/U *are* the unbounded operators). STLSat needs bounds,
  so they are capped at H = `horizon_factor` · B + `horizon_minimum`, where B is the largest finite horizon
  in the pair. Such verdicts are flagged `stlsat_bounded_approx = True`.
* **Symmetric functions**: `distance(a,b) = distance(b,a)` (`symmetric_functions`), because the ATIC signal
  contexts define distance as symmetric.
* **Not supported by either tool**: symbolic time bounds (`G[0,T]`) and parameterised operators
  (`AND_{i<j}`, `OR_i`). These get status `UNSUPPORTED`, but the syntactic stage still compares them.

## STLSat issues found (installed binary, Nov 2026)

1. **Negative constants in (−1, 0) lose their sign**: `z == -0.5 && z == 0.5` is SAT. Worked around by
   emitting `(0 - 0.5)`.
2. **The tableau engine (the default!) is unsound on some inputs.** This formula is UNSAT, and `smt`/`fol`
   say so, but `tableau` returns SAT:
   ```
   ((t < 20 || t > 30) -> G[0,1] (t >= 20 && t <= 30)) && !(!(t >= 20 && t <= 30) -> G[0,1] (t >= 20 && t <= 30))
   ```
   The pipeline therefore defaults to `--engine smt`. Both are worth reporting upstream.

## Adding a dataset

1. Formulas in a new notation: add aliases to `_UNICODE`, `_LATEX` or `_WORDS` in `parser.py`, and add a case
   to `tests/test_parser.py::Dialects`.
2. New table layout: `load_table(path, gold_col=..., pred_col=..., id_col=..., context_col=...)`, or a small
   loader in `datasets.py` (see `load_manual_review`).
3. If the dataset declares signal types differently, extend `normalize.parse_signal_context`.

## Setup

**STLSat**: install Rust (https://rustup.rs/), then `brew install z3`,
`export Z3_SYS_Z3_HEADER=$(brew --prefix z3)/include/z3.h`, `export LIBRARY_PATH=$(brew --prefix z3)/lib:$LIBRARY_PATH`,
`git clone https://github.com/ZamponiMarco/stlsat.git && cd stlsat && cargo install --path .`

**SPOT**: `conda install -c conda-forge spot` (tested with 2.16).

## Deferred: FRET

FRET (NASA) turns structured English (FRETish) into past/future-time MTL. It does not compare formulas,
so strictness is computed here by language containment instead. FRET is a candidate source of additional
NL↔formula pairs. Its formulas could be read with `load_table` once the past-time MTL notation is checked
against the parser.
