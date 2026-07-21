# NL–STL Benchmark 150

## Composition

This draft benchmark contains exactly 150 samples:

- 5 expected-strength samples for each of four reviewed approaches (20 total)
- 25 limitation-targeting samples for each approach (100 total)
- 30 formula-first robotics/control samples drawn from or aligned with published resources

Reviewed approaches:

1. DeepSTL
2. STL-DivEn / KGST
3. ChatSTL
4. ClarifySTL

## Provenance labels

- `paper_explicit`: formula and requirement are directly transcribed or lightly normalized.
- `paper_explicit_paraphrase`: based on a paper example but independently paraphrased.
- `paper_aligned`: constructed to match a demonstrated strength or data pattern.
- `limitation_constructed`: newly written to target a limitation reported or implied by the paper.
- `source_aligned`: a new NL rendering/formula aligned with a published robotics use case.

The benchmark is therefore not presented as 150 verbatim paper examples. The provenance fields are intended to prevent that interpretation.

## Three task modes

- `translate`: the input is intended to determine a gold STL formula.
- `clarify_then_translate`: the input is deliberately vague or ambiguous; use the stored oracle answer before scoring the final formula.
- `abstain_or_request_context`: a faithful standard-STL formula is not determined by the input, or an extension/context is required.

## Canonical syntax

The formulas use a readable canonical syntax:

- Boolean: `!`, `&`, `|`, `->`
- Future temporal: `G`, `F`, `U`
- Optional past/event constructs: `H`, `O`, `S`, `rise`, `fall`
- Parameterized team notation appears in a few robotics rows, e.g. `AND_j`, `OR_i`

Before model evaluation, normalize outputs to the exact grammar of the chosen parser/monitor.

## Recommended scoring

Use the accompanying evaluation protocol from the earlier benchmark work:

- syntactic validity
- canonical exact match
- AST-F1
- predicate and temporal grounding
- semantic trace agreement and counterexample search
- defect-classification macro-F1
- clarification-slot coverage
- answer incorporation
- abstention F1 and unsupported-assumption rate
- latency, token cost, and interaction turns

Report results separately for:

- expected-strength versus limitation probes
- each target paper
- formula-first robotics examples
- direct translation, clarification, and abstention
- difficulty and operator family

## Important review steps

This is a curated research draft, not a certified gold standard.

1. Parse all formulas using the exact evaluation grammar.
2. Have two STL-competent reviewers independently check each gold formula.
3. Generate satisfying and violating traces for all directly translatable formulas.
4. Check formulas containing event edges, past operators, parameterized team notation, and exact-time intervals against tool support.
5. Preserve the source/provenance columns when publishing results.

## ChatSTL source caveat

The ChatSTL expected-strength rows are based on the autonomous-driving scenario and generated-specification tables in the uploaded `NL-STL Examples.pdf`. The AP-level formulas have been canonicalized into a uniform STL-like syntax. The exact publication identity and parser dialect should be confirmed against the original paper before final publication.

## Primary source URLs

- DeepSTL: https://arxiv.org/abs/2109.10294
- STL-DivEn / KGST: https://arxiv.org/abs/2505.20658
- ClarifySTL: https://arxiv.org/abs/2605.01209
- RTAMT / RTAMT4ROS: https://arxiv.org/abs/2005.11827
- Multi-agent STL motion planning: https://arxiv.org/abs/2201.05247
- Event-based STL robot tasks: https://arxiv.org/abs/2011.00370
- Autonomous-vehicle STL constraints: https://arxiv.org/abs/2409.10689
- Manipulation skills with STL constraints: https://arxiv.org/abs/2209.03001
