from __future__ import annotations

from typing import Mapping

SYSTEM_PROMPT = """You are an NL-to-Signal-Temporal-Logic formalization system.

Inspect one natural-language requirement and choose exactly one action:

1. translate
Use this only when the requirement contains enough information to determine a
faithful formula in the supported STL grammar.

2. clarify
Use this when a threshold, interval, trigger, referent, scope, unit, signal,
event, or other required detail is missing or ambiguous. Ask one focused
clarification question. Do not guess the answer.

3. abstain
Use this when the requirement is inconsistent, depends on unavailable external
context, requires an unsupported logic extension, or otherwise cannot be
faithfully expressed in the supported grammar.

Rules:
- Never invent thresholds, intervals, units, signals, events, or domain facts.
- Preserve implication direction, Boolean grouping, and temporal scope.
- Distinguish persistent states from event transitions.
- Use only the supplied STL grammar.
- Put a formula in `stl` only when action is `translate`.
- Put a question in `clarification_question` only when action is `clarify`.
- Keep `assumptions` empty unless the input explicitly authorizes an assumption.
- Return only the required structured output.
"""

DEFAULT_GRAMMAR = """Supported canonical syntax:
- Boolean: !, &, |, ->
- Future temporal: G(phi), F(phi), G[a,b](phi), F[a,b](phi),
  (phi) U (psi), (phi) U[a,b] (psi)
- Optional extensions may be used only when explicitly listed in the row:
  H, O, S, rise(phi), fall(phi)
- Atomic predicates: signal < c, <=, =, >=, >; arithmetic/functions only when
  they are present in the requirement or signal context.
"""


def build_user_prompt(sample: Mapping[str, str]) -> str:
    signal_context = (sample.get("signal_context") or "").strip() or "Not provided."
    fragment = (sample.get("fragment") or "").strip() or "Not specified."
    operators = (sample.get("operators") or "").strip() or "Use the supported grammar only."

    return f"""Sample ID: {sample.get("id", "")}

{DEFAULT_GRAMMAR}

Dataset fragment label:
{fragment}

Operators relevant to this row:
{operators}

Signal/predicate context:
{signal_context}

Natural-language requirement:
{sample.get("requirement_nl", "")}
"""


def build_clarification_followup(
    sample: Mapping[str, str],
    first_question: str | None,
    oracle_answer: str,
) -> str:
    question = first_question or "(The system requested clarification.)"
    return f"""Original requirement:
{sample.get("requirement_nl", "")}

Your clarification question:
{question}

Authoritative user answer:
{oracle_answer}

Now reconsider the requirement using that answer. Return `translate` with the
final STL formula when the answer resolves the issue. If it remains impossible
or inconsistent, return `abstain`. Do not request information already supplied.
"""
