"""Template placed beside your ClarifySTL code.

Adapt `run_your_clarify_code` once, then set:
    CLARIFY_COMMAND="python clarify_wrapper.py"

The benchmark runner sends a JSON object on stdin and expects one JSON object on
stdout. Do not print logging to stdout; use stderr for logs.
"""
from __future__ import annotations

import json
import sys


def run_your_clarify_code(request: dict) -> dict:
    sample = request["sample"]
    stage = request["stage"]

    # ------------------------------------------------------------------
    # Replace this block with calls into your checked-out ClarifySTL repo.
    #
    # First stage should return one of:
    # {
    #   "action": "translate",
    #   "stl": "G(...)",
    #   "defect_types": [],
    #   "clarification_question": None,
    #   "assumptions": [],
    #   "confidence": 0.9
    # }
    #
    # or:
    # {
    #   "action": "clarify",
    #   "stl": None,
    #   "defect_types": ["numerical_vagueness"],
    #   "clarification_question": "What threshold defines low?",
    #   "assumptions": [],
    #   "confidence": 0.9
    # }
    #
    # Refine stage receives request["oracle_answer"] and
    # request["first_decision"] and should normally return translate/abstain.
    # ------------------------------------------------------------------
    raise NotImplementedError(
        f"Connect this template to ClarifySTL. Received {sample['id']} stage={stage}"
    )


def main() -> None:
    request = json.load(sys.stdin)
    result = run_your_clarify_code(request)
    json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
