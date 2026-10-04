#!/usr/bin/env python3
"""ClarifySTL-inspired NL→STL orchestrator.

This is a clean-room reconstruction based on the public usage guide, prompt sheet,
Ambiguity_A/B examples, and the benchmark's sample metadata. It is not the
original ClarifySTL implementation.

Modes
-----
1. Benchmark wrapper mode (default): read one JSON request from stdin and write
   one benchmark decision JSON object to stdout.
2. Native file mode: --input requirement.txt --output result.json [--human].

Only JSON is written to stdout in benchmark mode. Diagnostics go to stderr.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Structured schemas
# ---------------------------------------------------------------------------

class DetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    needs_clarification: bool
    defect_types: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class TranslationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["translate", "abstain"]
    stl: str | None
    reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class RefineResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refined_requirement: str
    resolved_items: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Example retrieval
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[-+]?\d+(?:\.\d+)?")
STOP = {
    "the", "a", "an", "and", "or", "if", "then", "is", "are", "be", "to",
    "of", "for", "in", "on", "at", "it", "this", "that", "with", "within",
    "must", "should", "will", "from", "by", "after", "before", "during",
    "time", "units", "unit", "signal", "requirement", "please", "specify",
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOP]


@dataclass(frozen=True)
class Example:
    source: str
    kind: str
    input_text: str
    counterpart: str
    clarification: str


class ExampleStore:
    """Small TF-IDF retriever over Ambiguity_A and Ambiguity_B."""

    def __init__(self, paths: Iterable[Path]):
        self.examples: list[Example] = []
        for path in paths:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive
                log(f"Could not load examples from {path}: {exc}")
                continue
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict):
                    continue
                if "incompleteness" in row:
                    self.examples.append(Example(
                        source=path.name,
                        kind=str(row.get("type") or "incompleteness"),
                        input_text=str(row.get("incompleteness") or ""),
                        counterpart=str(row.get("completeness") or ""),
                        clarification=str(row.get("clarification") or ""),
                    ))
                elif "ambiguous_description" in row:
                    self.examples.append(Example(
                        source=path.name,
                        kind="ambiguity",
                        input_text=str(row.get("unambiguous_description") or ""),
                        counterpart=str(row.get("ambiguous_description") or ""),
                        clarification=str(row.get("clarification") or ""),
                    ))

        self._doc_tokens = [Counter(tokenize(e.input_text)) for e in self.examples]
        df: Counter[str] = Counter()
        for counts in self._doc_tokens:
            df.update(counts.keys())
        n = max(1, len(self.examples))
        self._idf = {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}

    def retrieve(self, query: str, *, k: int = 4, source_hint: str | None = None) -> list[Example]:
        if not self.examples:
            return []
        q = Counter(tokenize(query))
        qnorm = math.sqrt(sum((count * self._idf.get(term, 1.0)) ** 2 for term, count in q.items())) or 1.0
        ranked: list[tuple[float, int]] = []
        for idx, counts in enumerate(self._doc_tokens):
            if source_hint and source_hint not in self.examples[idx].source:
                continue
            dot = sum(qc * counts.get(term, 0) * (self._idf.get(term, 1.0) ** 2) for term, qc in q.items())
            dnorm = math.sqrt(sum((count * self._idf.get(term, 1.0)) ** 2 for term, count in counts.items())) or 1.0
            ranked.append((dot / (qnorm * dnorm), idx))
        ranked.sort(reverse=True)
        return [self.examples[idx] for score, idx in ranked[:k] if score > 0]


# ---------------------------------------------------------------------------
# LLM backend
# ---------------------------------------------------------------------------

class Backend:
    def __init__(self) -> None:
        self.name = os.getenv("CLARIFY_BACKEND", "openai").strip().lower()
        if self.name not in {"openai", "anthropic"}:
            raise ValueError("CLARIFY_BACKEND must be 'openai' or 'anthropic'.")
        if self.name == "openai":
            self.model = os.getenv("CLARIFY_OPENAI_MODEL") or os.getenv("OPENAI_MODEL")
        else:
            self.model = os.getenv("CLARIFY_ANTHROPIC_MODEL") or os.getenv("ANTHROPIC_MODEL")
        if not self.model:
            raise RuntimeError(
                "No model configured. Set CLARIFY_OPENAI_MODEL/OPENAI_MODEL or "
                "CLARIFY_ANTHROPIC_MODEL/ANTHROPIC_MODEL."
            )

    def parse(self, *, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        if self.name == "openai":
            from openai import OpenAI

            client = OpenAI(max_retries=2, timeout=180.0)
            response = client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                text_format=schema,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise RuntimeError("OpenAI returned no parsed structured output.")
            return parsed

        from anthropic import Anthropic

        client = Anthropic(max_retries=2, timeout=180.0)
        response = client.messages.parse(
            model=self.model,
            max_tokens=1600,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("Anthropic returned no parsed structured output.")
        return parsed


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SUPPORTED_GRAMMAR = """Supported canonical STL syntax:
- Boolean: !, &, |, ->
- Future temporal: G(phi), F(phi), G[a,b](phi), F[a,b](phi),
  (phi) U (psi), (phi) U[a,b] (psi)
- Optional row-listed extensions only: H, O, S, rise(phi), fall(phi)
- Atomic predicates: signal < c, <=, =, !=, >=, >
- Arithmetic/functions only when explicitly supplied by the requirement/context.
- Use exact identifiers defined by the signal context.
"""

DETECTOR_SYSTEM = """You are the detection and inquiry component of a ClarifySTL-inspired system.
Determine whether an NL requirement lacks information or contains ambiguity that prevents a faithful STL translation.

Detect, at minimum:
- incomplete temporal information
- incomplete numerical information
- incomplete conditional logic
- incomplete atomic proposition/signal grounding
- referential ambiguity
- temporal scope or attachment ambiguity
- Boolean grouping ambiguity
- event-versus-state ambiguity
- unsupported or externally dependent semantics

Do not ask for information that is already explicitly supplied in the requirement or signal context.
Do not use benchmark labels or expected formulas. Ask one focused question targeting the most consequential unresolved item.
If the requirement can be translated faithfully, mark needs_clarification false.
"""

TRANSLATOR_SYSTEM = f"""You are the final STL transformation component of a ClarifySTL-inspired system.
Translate only when the requirement is sufficiently specified and expressible in the supplied grammar.
Never invent thresholds, time bounds, units, identifiers, events, or domain facts.
Preserve implication direction, temporal nesting, Boolean grouping, and state-versus-transition semantics.
Return abstain when the requirement requires unavailable context or unsupported logic.

{SUPPORTED_GRAMMAR}
"""

REFINER_SYSTEM = """You refine an incomplete or ambiguous NL requirement using an authoritative clarification answer.
Seamlessly integrate only information justified by the answer and supplied signal context.
Do not add unrelated facts. List any important item that remains unresolved.
"""


def format_examples(examples: Iterable[Example]) -> str:
    blocks = []
    for idx, ex in enumerate(examples, 1):
        blocks.append(
            f"Example {idx} ({ex.kind}):\n"
            f"Problematic description: {ex.input_text}\n"
            f"More specified counterpart: {ex.counterpart}\n"
            f"Clarification query: {ex.clarification}"
        )
    return "\n\n".join(blocks) or "No retrieved examples."


def safe_sample_view(sample: dict[str, Any], *, stage: str) -> dict[str, str]:
    """Expose only non-gold, execution-appropriate sample information."""
    context = str(sample.get("signal_context") or "").strip()
    if stage == "refine":
        context = str(sample.get("signal_context_after_clarification") or context).strip()
    return {
        "id": str(sample.get("id") or ""),
        "requirement": str(sample.get("requirement_nl") or ""),
        "signal_context": context or "Not provided.",
        "fragment": str(sample.get("fragment") or "Not specified."),
        "operators": str(sample.get("operators") or "Not specified."),
        "domain": str(sample.get("domain") or "Not specified."),
        "limitation_description": str(sample.get("limitation_target") or ""),
    }


def build_detection_prompt(sample: dict[str, Any], store: ExampleStore) -> str:
    view = safe_sample_view(sample, stage="initial")
    examples_a = store.retrieve(view["requirement"], k=4, source_hint="Ambiguity_A")
    examples_b = store.retrieve(view["requirement"], k=3, source_hint="Ambiguity_B")
    return f"""Inspect this requirement before translation.

Requirement:
{view['requirement']}

Signal/predicate context:
{view['signal_context']}

Dataset fragment:
{view['fragment']}

Row-listed operators:
{view['operators']}

Domain:
{view['domain']}

Relevant incompleteness examples:
{format_examples(examples_a)}

Relevant ambiguity examples:
{format_examples(examples_b)}

Return a structured detection result. If clarification is needed, ask exactly one concise question.
"""


def build_refine_prompt(
    sample: dict[str, Any], first_decision: dict[str, Any], oracle_answer: str, store: ExampleStore
) -> str:
    view = safe_sample_view(sample, stage="refine")
    question = str(first_decision.get("clarification_question") or "")
    examples = store.retrieve(view["requirement"] + " " + question, k=4)
    return f"""Original requirement:
{view['requirement']}

Clarification question:
{question or '(unspecified question)'}

Authoritative answer:
{oracle_answer}

Signal/predicate context after clarification:
{view['signal_context']}

Related examples:
{format_examples(examples)}

Produce one refined requirement that incorporates the authoritative answer. Do not translate to STL yet.
"""


def build_translation_prompt(sample: dict[str, Any], requirement: str, *, stage: str) -> str:
    view = safe_sample_view(sample, stage=stage)
    return f"""Translate the following requirement, or abstain if faithful translation is impossible.

Requirement:
{requirement}

Signal/predicate context:
{view['signal_context']}

Dataset fragment:
{view['fragment']}

Row-listed operators:
{view['operators']}

Domain:
{view['domain']}

{SUPPORTED_GRAMMAR}

Use exact context identifiers. Put a formula in stl only when action is translate.
"""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

class ClarifyOrchestrator:
    def __init__(self, backend: Backend, store: ExampleStore):
        self.backend = backend
        self.store = store

    def initial(self, sample: dict[str, Any]) -> dict[str, Any]:
        detection = self.backend.parse(
            system=DETECTOR_SYSTEM,
            user=build_detection_prompt(sample, self.store),
            schema=DetectionResult,
        )
        assert isinstance(detection, DetectionResult)

        if detection.needs_clarification:
            question = (detection.clarification_question or "").strip()
            if not question:
                question = "What missing information is required to formalize this requirement precisely?"
            return {
                "action": "clarify",
                "stl": None,
                "defect_types": detection.defect_types,
                "clarification_question": question,
                "assumptions": [],
                "confidence": detection.confidence,
            }

        translation = self.backend.parse(
            system=TRANSLATOR_SYSTEM,
            user=build_translation_prompt(
                sample, str(sample.get("requirement_nl") or ""), stage="initial"
            ),
            schema=TranslationResult,
        )
        assert isinstance(translation, TranslationResult)
        return {
            "action": translation.action,
            "stl": translation.stl if translation.action == "translate" else None,
            "defect_types": [],
            "clarification_question": None,
            "assumptions": translation.assumptions,
            "confidence": translation.confidence,
        }

    def refine(
        self,
        sample: dict[str, Any],
        first_decision: dict[str, Any],
        oracle_answer: str,
    ) -> dict[str, Any]:
        refined = self.backend.parse(
            system=REFINER_SYSTEM,
            user=build_refine_prompt(sample, first_decision, oracle_answer, self.store),
            schema=RefineResult,
        )
        assert isinstance(refined, RefineResult)

        # One conservative re-check after refinement, mirroring ClarifySTL's
        # detect–query–refine–recheck architecture. The benchmark supports one
        # external clarification turn, so unresolved issues lead to abstention.
        recheck_sample = dict(sample)
        recheck_sample["requirement_nl"] = refined.refined_requirement
        detection = self.backend.parse(
            system=DETECTOR_SYSTEM,
            user=build_detection_prompt(recheck_sample, self.store),
            schema=DetectionResult,
        )
        assert isinstance(detection, DetectionResult)

        if detection.needs_clarification and detection.confidence >= 0.75:
            return {
                "action": "abstain",
                "stl": None,
                "defect_types": detection.defect_types,
                "clarification_question": None,
                "assumptions": [],
                "confidence": detection.confidence,
            }

        translation = self.backend.parse(
            system=TRANSLATOR_SYSTEM,
            user=build_translation_prompt(
                sample, refined.refined_requirement, stage="refine"
            ),
            schema=TranslationResult,
        )
        assert isinstance(translation, TranslationResult)
        return {
            "action": translation.action,
            "stl": translation.stl if translation.action == "translate" else None,
            "defect_types": [],
            "clarification_question": None,
            "assumptions": translation.assumptions,
            "confidence": min(refined.confidence, translation.confidence),
        }


# ---------------------------------------------------------------------------
# Entrypoints
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    print(f"[clarifystl-inspired] {message}", file=sys.stderr)


def resolve_example_paths() -> list[Path]:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        os.getenv("CLARIFY_AMBIGUITY_A"),
        os.getenv("CLARIFY_AMBIGUITY_B"),
        str(script_dir / "Ambiguity_A.json"),
        str(script_dir / "Ambiguity_B.json"),
    ]
    seen: set[Path] = set()
    paths: list[Path] = []
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if path not in seen and path.exists():
            seen.add(path)
            paths.append(path)
    return paths


def build_orchestrator() -> ClarifyOrchestrator:
    load_dotenv(dotenv_path=Path.cwd() / ".env")
    paths = resolve_example_paths()
    store = ExampleStore(paths)
    log(f"loaded {len(store.examples)} examples from {len(paths)} file(s)")
    return ClarifyOrchestrator(Backend(), store)


def benchmark_main() -> None:
    request = json.load(sys.stdin)
    if not isinstance(request, dict):
        raise ValueError("Benchmark request must be a JSON object.")
    sample = request.get("sample")
    if not isinstance(sample, dict):
        raise ValueError("Benchmark request is missing sample object.")
    stage = str(request.get("stage") or "initial")
    orchestrator = build_orchestrator()
    if stage == "initial":
        result = orchestrator.initial(sample)
    elif stage == "refine":
        first = request.get("first_decision") or {}
        answer = str(request.get("oracle_answer") or "")
        result = orchestrator.refine(sample, first, answer)
    else:
        raise ValueError(f"Unsupported stage: {stage}")
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def native_main(args: argparse.Namespace) -> None:
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    requirement = input_path.read_text(encoding="utf-8").strip()
    sample = {
        "id": input_path.stem,
        "requirement_nl": requirement,
        "signal_context": args.signal_context or "Not provided.",
        "signal_context_after_clarification": args.signal_context or "Not provided.",
        "fragment": args.fragment or "future_stl",
        "operators": args.operators or "G,F,U,&,|,!,->",
        "domain": args.domain or "Not specified.",
    }
    orchestrator = build_orchestrator()
    first = orchestrator.initial(sample)
    history: list[dict[str, Any]] = []
    refined_requirement = requirement
    final = first

    if first["action"] == "clarify":
        question = first.get("clarification_question") or "Please clarify."
        if args.human:
            print(question)
            answer = input("Answer: ").strip()
        else:
            answer = args.answer or os.getenv("CLARIFY_AUTO_ANSWER", "").strip()
            if not answer:
                raise RuntimeError(
                    "Native automated mode needs --answer or CLARIFY_AUTO_ANSWER. "
                    "The clean-room implementation does not invent user feedback."
                )
        history.append({"question": question, "answer": answer})
        final = orchestrator.refine(sample, first, answer)
        # The refined requirement is intentionally not exposed by benchmark mode;
        # native output keeps a concise audit trail.
        refined_requirement = f"{requirement} [Clarification: {answer}]"

    payload = {
        "original": requirement,
        "after_incompleteness": refined_requirement,
        "incompleteness_history": history,
        "after_ambiguity": refined_requirement,
        "ambiguity_history": [],
        "final_stl": final.get("stl"),
        "final_action": final.get("action"),
        "implementation": "ClarifySTL-inspired clean-room reconstruction",
        "backend": orchestrator.backend.name,
        "model": orchestrator.backend.model,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Native-mode requirement text file")
    parser.add_argument("--output", help="Native-mode JSON output file")
    parser.add_argument("--human", action="store_true", help="Ask clarification interactively")
    parser.add_argument("--answer", help="Automated native-mode clarification answer")
    parser.add_argument("--signal-context", default="")
    parser.add_argument("--fragment", default="future_stl")
    parser.add_argument("--operators", default="G,F,U,&,|,!,->")
    parser.add_argument("--domain", default="")
    return parser.parse_args()


def main() -> None:
    # No CLI arguments means benchmark stdin/stdout mode.
    if len(sys.argv) == 1:
        benchmark_main()
        return
    args = parse_args()
    if not args.input or not args.output:
        raise SystemExit("Native mode requires both --input and --output.")
    native_main(args)


if __name__ == "__main__":
    main()
