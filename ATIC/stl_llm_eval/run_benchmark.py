from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import threading
import time
from typing import Callable, Iterable

from dotenv import load_dotenv
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from clarify_adapter import call_clarify
from prompts import SYSTEM_PROMPT, build_clarification_followup, build_user_prompt
from schemas import ProviderResult, TranslationDecision


_WRITE_LOCK = threading.Lock()
_CLIENTS = threading.local()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dataset(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def select_samples(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    selected = rows

    if args.ids:
        wanted = set(args.ids)
        selected = [r for r in selected if r.get("id") in wanted]
    if args.target:
        selected = [r for r in selected if r.get("target_paper") in set(args.target)]
    if args.case_type:
        selected = [r for r in selected if r.get("case_type") in set(args.case_type)]
    if args.task_mode:
        selected = [r for r in selected if r.get("task_mode") in set(args.task_mode)]
    if args.group:
        selected = [r for r in selected if r.get("group") in set(args.group)]
    if args.shuffle:
        random.Random(args.seed).shuffle(selected)
    if args.limit is not None:
        selected = selected[: args.limit]
    return selected


def read_completed(path: Path) -> set[tuple[str, str, str, int]]:
    completed: set[tuple[str, str, str, int]] = set()
    if not path.exists():
        return completed
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                if row.get("status") == "ok":
                    completed.add((
                        row["provider"],
                        row["model"],
                        row["sample_id"],
                        int(row.get("run_index", 0)),
                    ))
            except Exception:
                continue
    return completed


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
            f.flush()


def decision_json(decision: TranslationDecision) -> str:
    return decision.model_dump_json()


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def call_openai(
    *,
    model: str,
    sample: dict[str, str],
    stage: str,
    first: ProviderResult | None = None,
    oracle_answer: str | None = None,
) -> ProviderResult:
    from openai import OpenAI

    client = getattr(_CLIENTS, "openai", None)
    if client is None:
        client = OpenAI(max_retries=2, timeout=180.0)
        _CLIENTS.openai = client
    if stage == "initial":
        input_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(sample)},
        ]
    else:
        input_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(sample)},
            {"role": "assistant", "content": decision_json(first.decision)},
            {
                "role": "user",
                "content": build_clarification_followup(
                    sample,
                    first.decision.clarification_question,
                    oracle_answer or "",
                ),
            },
        ]

    response = client.responses.parse(
        model=model,
        input=input_messages,
        text_format=TranslationDecision,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("OpenAI response had no parsed structured output.")

    usage = getattr(response, "usage", None)
    return ProviderResult(
        decision=parsed,
        raw_response={
            "id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "output_text": getattr(response, "output_text", None),
        },
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
        request_id=getattr(response, "id", None),
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def call_anthropic(
    *,
    model: str,
    sample: dict[str, str],
    stage: str,
    first: ProviderResult | None = None,
    oracle_answer: str | None = None,
) -> ProviderResult:
    from anthropic import Anthropic

    client = getattr(_CLIENTS, "anthropic", None)
    if client is None:
        client = Anthropic(max_retries=2, timeout=180.0)
        _CLIENTS.anthropic = client
    if stage == "initial":
        messages = [{"role": "user", "content": build_user_prompt(sample)}]
    else:
        messages = [
            {"role": "user", "content": build_user_prompt(sample)},
            {"role": "assistant", "content": decision_json(first.decision)},
            {
                "role": "user",
                "content": build_clarification_followup(
                    sample,
                    first.decision.clarification_question,
                    oracle_answer or "",
                ),
            },
        ]

    response = client.messages.parse(
        model=model,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=messages,
        output_format=TranslationDecision,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise RuntimeError(
            f"Claude response had no parsed output; stop_reason={response.stop_reason}"
        )
    usage = getattr(response, "usage", None)
    return ProviderResult(
        decision=parsed,
        raw_response={
            "id": getattr(response, "id", None),
            "stop_reason": getattr(response, "stop_reason", None),
            "text": getattr(response.content[0], "text", None) if response.content else None,
        },
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        total_tokens=(
            (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "output_tokens", 0) or 0)
        ),
        request_id=getattr(response, "id", None),
    )


def call_mock(
    *,
    model: str,
    sample: dict[str, str],
    stage: str,
    first: ProviderResult | None = None,
    oracle_answer: str | None = None,
) -> ProviderResult:
    """Plumbing smoke test only. It intentionally reads gold fields."""
    task = sample.get("task_mode")
    if stage == "initial":
        if task == "translate":
            decision = TranslationDecision(
                action="translate",
                stl=sample.get("gold_stl") or None,
                defect_types=[],
                clarification_question=None,
                assumptions=[],
                confidence=1.0,
            )
        elif task == "clarify_then_translate":
            decision = TranslationDecision(
                action="clarify",
                stl=None,
                defect_types=[sample.get("defect_type") or "unspecified"],
                clarification_question=sample.get("clarification_question") or "Please clarify.",
                assumptions=[],
                confidence=1.0,
            )
        else:
            decision = TranslationDecision(
                action="abstain",
                stl=None,
                defect_types=[sample.get("defect_type") or "unsupported"],
                clarification_question=None,
                assumptions=[],
                confidence=1.0,
            )
    else:
        decision = TranslationDecision(
            action="translate" if sample.get("gold_after_clarification") else "abstain",
            stl=sample.get("gold_after_clarification") or None,
            defect_types=[],
            clarification_question=None,
            assumptions=[],
            confidence=1.0,
        )
    return ProviderResult(decision=decision, raw_response={"mock": True})


def call_provider(
    provider: str,
    model: str,
    sample: dict[str, str],
    stage: str,
    first: ProviderResult | None = None,
    oracle_answer: str | None = None,
) -> ProviderResult:
    if provider == "openai":
        return call_openai(
            model=model, sample=sample, stage=stage,
            first=first, oracle_answer=oracle_answer,
        )
    if provider == "anthropic":
        return call_anthropic(
            model=model, sample=sample, stage=stage,
            first=first, oracle_answer=oracle_answer,
        )
    if provider == "clarify":
        return call_clarify(
            sample,
            stage=stage,
            first_decision=first.decision.model_dump() if first else None,
            oracle_answer=oracle_answer,
        )
    if provider == "mock":
        return call_mock(
            model=model, sample=sample, stage=stage,
            first=first, oracle_answer=oracle_answer,
        )
    raise ValueError(f"Unknown provider: {provider}")


def run_one(
    *,
    provider: str,
    model: str,
    sample: dict[str, str],
    run_index: int,
) -> dict:
    started = time.perf_counter()
    base = {
        "provider": provider,
        "model": model,
        "sample_id": sample["id"],
        "run_index": run_index,
        "started_at": utc_now(),
        "dataset_group": sample.get("group"),
        "target_paper": sample.get("target_paper"),
        "case_type": sample.get("case_type"),
        "task_mode": sample.get("task_mode"),
    }
    try:
        first_started = time.perf_counter()
        first = call_provider(provider, model, sample, "initial")
        first_latency = time.perf_counter() - first_started

        final = first
        refinement_latency = 0.0
        oracle_used = False
        if (
            first.decision.action == "clarify"
            and sample.get("oracle_answer")
            and sample.get("task_mode") == "clarify_then_translate"
        ):
            oracle_used = True
            refine_started = time.perf_counter()
            final = call_provider(
                provider,
                model,
                sample,
                "refine",
                first=first,
                oracle_answer=sample["oracle_answer"],
            )
            refinement_latency = time.perf_counter() - refine_started

        return {
            **base,
            "status": "ok",
            "finished_at": utc_now(),
            "latency_seconds": time.perf_counter() - started,
            "first_latency_seconds": first_latency,
            "refinement_latency_seconds": refinement_latency,
            "oracle_used": oracle_used,
            "first_decision": first.decision.model_dump(),
            "final_decision": final.decision.model_dump(),
            "first_usage": {
                "input_tokens": first.input_tokens,
                "output_tokens": first.output_tokens,
                "total_tokens": first.total_tokens,
            },
            "final_usage": {
                "input_tokens": final.input_tokens,
                "output_tokens": final.output_tokens,
                "total_tokens": final.total_tokens,
            },
            "first_request_id": first.request_id,
            "final_request_id": final.request_id,
            "first_raw_response": first.raw_response,
            "final_raw_response": final.raw_response,
        }
    except Exception as exc:
        return {
            **base,
            "status": "error",
            "finished_at": utc_now(),
            "latency_seconds": time.perf_counter() - started,
            "error_type": type(exc).__name__,
            "error": str(exc)[:4000],
        }


def model_for(provider: str, args: argparse.Namespace) -> str:
    if provider == "openai":
        return args.openai_model
    if provider == "anthropic":
        return args.anthropic_model
    if provider == "clarify":
        return args.clarify_model
    return "mock-gold-plumbing-test"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Run NL-to-STL benchmark against OpenAI, Claude, and ClarifySTL."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("runs/results.jsonl"))
    parser.add_argument(
        "--providers", nargs="+",
        choices=["openai", "anthropic", "clarify", "mock"],
        default=["openai", "anthropic"],
    )
    parser.add_argument(
        "--openai-model",
        default=os.getenv("OPENAI_MODEL", "gpt-5.6-terra"),
    )
    parser.add_argument(
        "--anthropic-model",
        default=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
    )
    parser.add_argument(
        "--clarify-model",
        default=os.getenv("CLARIFY_MODEL", "clarifystl-local"),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--target", nargs="*")
    parser.add_argument("--case-type", nargs="*")
    parser.add_argument("--task-mode", nargs="*")
    parser.add_argument("--group", nargs="*")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = select_samples(load_dataset(args.dataset), args)
    if not rows:
        raise SystemExit("No dataset rows matched the filters.")

    if args.dry_run:
        print(build_user_prompt(rows[0]))
        print(f"\nSelected {len(rows)} rows.")
        return

    completed = set() if args.no_resume else read_completed(args.output)
    jobs = []
    for provider in args.providers:
        model = model_for(provider, args)
        for sample in rows:
            for run_index in range(args.runs):
                key = (provider, model, sample["id"], run_index)
                if key not in completed:
                    jobs.append((provider, model, sample, run_index))

    print(
        f"Selected {len(rows)} dataset rows; scheduling {len(jobs)} requests "
        f"across {args.providers}. Output: {args.output}"
    )
    if not jobs:
        print("Everything is already complete. Use --no-resume to rerun.")
        return

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        future_map = {
            executor.submit(
                run_one,
                provider=provider,
                model=model,
                sample=sample,
                run_index=run_index,
            ): (provider, model, sample["id"], run_index)
            for provider, model, sample, run_index in jobs
        }
        done = 0
        for future in as_completed(future_map):
            payload = future.result()
            append_jsonl(args.output, payload)
            done += 1
            status = payload["status"]
            print(
                f"[{done}/{len(jobs)}] {payload['provider']} "
                f"{payload['sample_id']} run={payload['run_index']} {status}"
            )

    print("Run complete.")


if __name__ == "__main__":
    main()
