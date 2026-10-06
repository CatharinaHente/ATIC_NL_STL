"""
stlsat_checker.py
-----------------
Python interface to the STLSat binary for STL formula equivalence checking.
 
Usage (from your pipeline):
    from stlsat_checker import check_equivalence, EquivalenceResult
 
    result = check_equivalence("G[0,10] (x > 5)", "G[0,10] (x > 5)")
    print(result.verdict)       # EQUIVALENT, NON_EQUIVALENT, or ERROR
    print(result.detail)        # human-readable explanation
    print(result.raw_output)    # raw stlsat stdout, useful for debugging
 
Formula string format expected (same as STLSat's own syntax):
    - Temporal : G[a,b] phi  |  F[a,b] phi  |  phi U[a,b] psi  |  phi R[a,b] psi
    - Boolean  : &&  ||  !  ->  <->
    - Atoms    : x > 5  |  x <= 3.0  |  on1  |  true  |  false
    - Grouping : (phi)
    - NO unbounded operators (G phi without [a,b] is rejected before calling stlsat)
 
Equivalence encoding:
    phi1 == phi2  iff  (phi1 && !phi2) || (!phi1 && phi2)  is UNSAT
"""
 
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
 
 
# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
 
class Verdict(str, Enum):
    EQUIVALENT     = "EQUIVALENT"
    NON_EQUIVALENT = "NON_EQUIVALENT"
    ERROR          = "ERROR"          # parse error, unsupported fragment, timeout, …
 
 
@dataclass
class EquivalenceResult:
    verdict:    Verdict
    detail:     str           # human-readable summary
    raw_output: str           # raw stlsat stdout + stderr, for debugging
    formula:    str = ""      # the combined formula that was checked
 
 
# ---------------------------------------------------------------------------
# Fragment pre-check
# ---------------------------------------------------------------------------
 
# Unbounded G/F look like  G <space> (  or  F <space> (  — no [a,b] following
_UNBOUNDED_RE = re.compile(r'\b[GF]\s*(?!\[)')
 
def _check_fragment(formula_str: str) -> str | None:
    """
    Return an error message if the formula uses operators outside STLSat's
    supported fragment, otherwise return None.
 
    STLSat requires ALL temporal operators to be bounded: G[a,b], F[a,b],
    U[a,b], R[a,b].  A bare G or F (without [a,b]) is not parseable by
    STLSat and would produce a confusing error — we catch it here first.
    """
    if _UNBOUNDED_RE.search(formula_str):
        return (
            "Formula contains an unbounded temporal operator (G or F without [a,b]). "
            "STLSat only supports bounded discrete-time STL. "
            "Consider bounding the operator or routing to the SPOT/LTLf fallback."
        )
    return None
 
 
# ---------------------------------------------------------------------------
# STLSat binary location
# ---------------------------------------------------------------------------
 
def _find_stlsat() -> str:
    """
    Locate the stlsat binary.  Looks in PATH first, then the default Cargo
    install location (~/.cargo/bin/stlsat).
    """
    path = shutil.which("stlsat")
    if path:
        return path
    fallback = Path.home() / ".cargo" / "bin" / "stlsat"
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError(
        "stlsat binary not found.  Make sure it is installed:\n"
        "  cargo install --path <path-to-stlsat-repo>\n"
        "and that ~/.cargo/bin is on your PATH."
    )
 
 
# ---------------------------------------------------------------------------
# Core equivalence check
# ---------------------------------------------------------------------------
 
def check_equivalence(
    phi1: str,
    phi2: str,
    timeout: int = 30,
) -> EquivalenceResult:
    """
    Check whether two STL formula strings are semantically equivalent.
 
    Parameters
    ----------
    phi1, phi2 : str
        STL formulas in STLSat syntax (see module docstring).
    timeout : int
        Seconds before the stlsat call is killed and ERROR is returned.
 
    Returns
    -------
    EquivalenceResult with verdict EQUIVALENT, NON_EQUIVALENT, or ERROR.
    """
    phi1 = phi1.strip()
    phi2 = phi2.strip()
 
    # --- fragment check ---
    for phi, label in [(phi1, "phi1"), (phi2, "phi2")]:
        err = _check_fragment(phi)
        if err:
            return EquivalenceResult(
                verdict=Verdict.ERROR,
                detail=f"Fragment check failed for {label}: {err}",
                raw_output="",
                formula="",
            )
 
    # --- build equivalence formula: (phi1 && !phi2) || (!phi1 && phi2) ---
    combined = f"({phi1} && !({phi2})) || (!({phi1}) && ({phi2}))"
 
    # --- write to temp file and call stlsat ---
    try:
        binary = _find_stlsat()
    except FileNotFoundError as e:
        return EquivalenceResult(
            verdict=Verdict.ERROR,
            detail=str(e),
            raw_output="",
            formula=combined,
        )
 
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".stl", delete=False
    ) as tmp:
        tmp.write(combined + "\n")
        tmp_path = tmp.name
 
    try:
        proc = subprocess.run(
            [binary, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw = proc.stdout + proc.stderr
        return _parse_stlsat_output(raw, combined)
 
    except subprocess.TimeoutExpired:
        return EquivalenceResult(
            verdict=Verdict.ERROR,
            detail=f"stlsat timed out after {timeout}s.",
            raw_output="TIMEOUT",
            formula=combined,
        )
    except Exception as e:
        return EquivalenceResult(
            verdict=Verdict.ERROR,
            detail=f"Unexpected error calling stlsat: {e}",
            raw_output="",
            formula=combined,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
 
 
# ---------------------------------------------------------------------------
# Output parser
# ---------------------------------------------------------------------------
 
def _parse_stlsat_output(raw: str, combined: str) -> EquivalenceResult:
    """
    STLSat prints:
        Tableau result: Some(true)   → SAT → formulas differ
        Tableau result: Some(false)  → UNSAT → formulas equivalent
    """
    if "Some(false)" in raw:
        return EquivalenceResult(
            verdict=Verdict.EQUIVALENT,
            detail="Formulas are semantically equivalent (XOR formula is UNSAT).",
            raw_output=raw,
            formula=combined,
        )

    if "Some(true)" in raw:
        return EquivalenceResult(
            verdict=Verdict.NON_EQUIVALENT,
            detail=(
                "Formulas are NOT equivalent (XOR formula is SAT — "
                "a distinguishing signal trace exists)."
            ),
            raw_output=raw,
            formula=combined,
        )

    return EquivalenceResult(
        verdict=Verdict.ERROR,
        detail=f"stlsat returned an unexpected result. Raw output: {raw[:300]}",
        raw_output=raw,
        formula=combined,
    )
 
 
# ---------------------------------------------------------------------------
# Batch helper — useful for the benchmark loop
# ---------------------------------------------------------------------------
 
def check_equivalence_batch(
    pairs: list[tuple[str, str]],
    timeout: int = 30,
) -> list[EquivalenceResult]:
    """
    Run equivalence checks for a list of (phi_reference, phi_generated) pairs.
    Returns one EquivalenceResult per pair, in the same order.
    """
    return [check_equivalence(p1, p2, timeout=timeout) for p1, p2 in pairs]
 
 
# ---------------------------------------------------------------------------
# Quick smoke test — run with:  python stlsat_checker.py
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":
    tests = [
        # (description, phi1, phi2, expected_verdict)
        (
            "identical formulas",
            "G[0,10] (x > 5)",
            "G[0,10] (x > 5)",
            Verdict.EQUIVALENT,
        ),
        (
            "logically equivalent rewrite",
            "G[0,10] (x > 5)",
            "!F[0,10] (x <= 5)",
            Verdict.EQUIVALENT,
        ),
        (
            "clearly different",
            "G[0,10] (x > 5)",
            "F[0,10] (x > 5)",
            Verdict.NON_EQUIVALENT,
        ),
        (
            "unbounded G — should give ERROR",
            "G (x > 5)",
            "G[0,10] (x > 5)",
            Verdict.ERROR,
        ),
    ]
 
    print("STLSat equivalence checker — smoke tests\n" + "=" * 45)
    all_passed = True
    for desc, phi1, phi2, expected in tests:
        result = check_equivalence(phi1, phi2)
        status = "PASS" if result.verdict == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"[{status}] {desc}")
        print(f"       verdict : {result.verdict.value}")
        print(f"       detail  : {result.detail}")
        print()
 
    print("All tests passed." if all_passed else "Some tests FAILED — check output above.")