"""Differential test: on random *bounded* formulas (incl. past operators, rise/fall and
numeric predicates) SPOT and STLSat-smt must return identical containment results.
Both encodings are exact on this fragment, so any disagreement is a bug.

    python -m unittest tests.test_differential        (≈1–2 min)
"""
import random
import unittest

from equivalence.pipeline import Checker, Config

ATOMS = ["a", "b", "(x > 1)", "(x <= 3)", "(x >= 1)", "(y < 0)", "(y > -0.5)", "(abs(y) <= 0.5)"]


def rand_formula(rng, depth):
    if depth == 0 or rng.random() < 0.25:
        return rng.choice(ATOMS)
    k = rng.random()
    lo = rng.randint(0, 2)
    hi = lo + rng.randint(0, 2)
    sub = lambda: rand_formula(rng, depth - 1)
    if k < 0.15:
        return f"!({sub()})"
    if k < 0.30:
        return f"({sub()} & {sub()})"
    if k < 0.42:
        return f"({sub()} | {sub()})"
    if k < 0.50:
        return f"({sub()} -> {sub()})"
    if k < 0.62:
        return f"G[{lo},{hi}]({sub()})"
    if k < 0.74:
        return f"F[{lo},{hi}]({sub()})"
    if k < 0.82:
        return f"({sub()} U[{lo},{hi}] {sub()})"
    if k < 0.86:
        return f"rise({sub()})"
    if k < 0.89:
        return f"fall({sub()})"
    if k < 0.93:
        return f"O[{lo},{hi}]({sub()})"
    if k < 0.96:
        return f"H[{lo},{hi}]({sub()})"
    return f"({sub()} S {sub()})"


def mutate(rng, f):
    """A nearby formula, so that a good share of pairs are (non-)trivially related."""
    swaps = [("G[", "F["), ("&", "|"), ("x > 1", "x >= 1"), ("rise(", "fall("), ("U[0,", "U[1,"), ("a", "b")]
    old, new = rng.choice(swaps)
    return f.replace(old, new, 1) if old in f else f"({f} & a)"


class Differential(unittest.TestCase):
    def test_spot_vs_stlsat(self, n=60, seed=7):
        rng = random.Random(seed)
        cfg = Config(stlsat_engine="smt", spot_timeout=20, stlsat_timeout=20)
        disagreements, compared = [], 0
        with Checker(cfg) as c:
            for _ in range(n):
                g = rand_formula(rng, 3)
                p = mutate(rng, g) if rng.random() < 0.7 else rand_formula(rng, 3)
                r = c.check(g, p)
                if r["spot_status"] == "OK" and r["stlsat_status"] == "OK":
                    compared += 1
                    if r["spot_verdict"] != r["stlsat_verdict"]:
                        disagreements.append((g, p, r["spot_verdict"], r["stlsat_verdict"]))
        self.assertGreater(compared, n * 0.8)
        self.assertEqual(disagreements, [], "\n".join(map(str, disagreements)))


if __name__ == "__main__":
    unittest.main()
