from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Mapping

from schemas import ProviderResult, TranslationDecision


class ClarifyAdapterError(RuntimeError):
    pass


def _normalize(payload: dict) -> ProviderResult:
    """Accept either the shared schema or common Clarify-style field names."""
    if "decision" in payload:
        return ProviderResult.model_validate(payload)

    action = str(payload.get("action") or payload.get("status") or "").lower()
    action_aliases = {
        "translation": "translate",
        "translated": "translate",
        "question": "clarify",
        "clarification": "clarify",
        "reject": "abstain",
        "unsupported": "abstain",
    }
    action = action_aliases.get(action, action)
    if action not in {"translate", "clarify", "abstain"}:
        raise ClarifyAdapterError(
            "Clarify output needs action/status translate, clarify, or abstain."
        )

    decision = TranslationDecision(
        action=action,
        stl=payload.get("stl") or payload.get("formula"),
        defect_types=payload.get("defect_types") or payload.get("ambiguity_types") or [],
        clarification_question=payload.get("clarification_question") or payload.get("question"),
        assumptions=payload.get("assumptions") or [],
        confidence=float(payload.get("confidence", 0.5)),
    )
    return ProviderResult(
        decision=decision,
        raw_response=payload,
        input_tokens=payload.get("input_tokens"),
        output_tokens=payload.get("output_tokens"),
        total_tokens=payload.get("total_tokens"),
    )


def call_clarify(
    sample: Mapping[str, str],
    *,
    stage: str,
    first_decision: dict | None = None,
    oracle_answer: str | None = None,
    timeout_seconds: int = 300,
) -> ProviderResult:
    """Run a local ClarifySTL wrapper as a subprocess.

    Set CLARIFY_COMMAND to a command that:
      1. reads one JSON object from stdin;
      2. writes one JSON object to stdout;
      3. follows the shared action/stl/question schema.

    Example:
      CLARIFY_COMMAND="python path/to/clarify_wrapper.py"
    """
    command = os.environ.get("CLARIFY_COMMAND", "").strip()
    if not command:
        raise ClarifyAdapterError(
            "CLARIFY_COMMAND is not configured. See clarify_wrapper_template.py."
        )

    request = {
        "stage": stage,
        "sample": dict(sample),
        "first_decision": first_decision,
        "oracle_answer": oracle_answer,
    }
    proc = subprocess.run(
        shlex.split(command),
        input=json.dumps(request, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.returncode != 0:
        raise ClarifyAdapterError(
            f"Clarify command failed ({proc.returncode}): {proc.stderr[-2000:]}"
        )
    stdout = proc.stdout.strip()
    if not stdout:
        raise ClarifyAdapterError("Clarify command returned empty stdout.")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ClarifyAdapterError(
            f"Clarify stdout is not JSON: {stdout[:1000]}"
        ) from exc
    return _normalize(payload)
