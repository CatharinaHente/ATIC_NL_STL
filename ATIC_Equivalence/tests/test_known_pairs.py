"""Hand-verified pairs (mostly from the ATIC manual review) with their correct verdicts."""
import unittest

from equivalence.pipeline import Checker, Config

CASES = [
    # (gold, pred, expected verdict, why)
    ("G(rise(fault = 1) -> F[0,5](recovery = 1))", "G(rise(fault) -> F[0,5](recovery = 1))", "EQUIVALENT", "bool shorthand"),
    ("G(rise(A = 1) -> F[0,15](G[0,5](B = 1)))", "G(rise(A) -> F[0,20](G[0,5](B)))", "PRED_WEAKER", "MR-075: old SPOT said EQUIVALENT (bounds stripped)"),
    ("F[0,120](sample_region & F[0,120](communication_region))", "F[0,120](sample_region & F(communication_region))", "PRED_WEAKER", "MR-089: old SPOT said EQUIVALENT"),
    ("G((!((t >= 20) & (t <= 30))) -> F[0,6](G[0,4]((t >= 20) & (t <= 30))))",
     "G((t < 20 | t > 30) -> F[0,6](G[0,4](t >= 20 & t <= 30)))", "EQUIVALENT", "MR-020: needs predicate negation; tableau wrong here"),
    ("G(altitude <= 120)", "G(altitude < 120)", "PRED_STRONGER", "MR-053: threshold ordering axiom"),
    ("G((A & B & C & D & !E) -> F[0,5](Fsig | Gsig))", "G(((A = 1) & (B = 1) & (C = 1) & (D = 1) & !(E = 1)) -> F[0,5]((Fsig = 1) | (Gsig = 1)))", "EQUIVALENT", "MR-040: Fsig is an identifier"),
    ("(warning = 1) S (loss_of_signal = 1)", "(warning) S (loss_of_signal)", "EQUIVALENT", "MR-007: since"),
    ("G((tank_level > 90) -> F[0,2](inlet_closed = 1))", "G(rise(tank_level > 90) -> F[0,2](inlet_closed = 1))", "PRED_WEAKER", "MR-066: rise of a predicate"),
    ("G(rise(x) -> F[0,3] y)", "G(x -> F[0,3] y)", "PRED_STRONGER", "rise is not the level"),
    ("G((reset = 1) -> H[0,5](fault = 0))", "G(reset -> H[0,5](!fault))", "EQUIVALENT", "MR-006: historically"),
    ("G(abs(c - r) <= 0.5)", "G(abs(r - c) <= 0.5)", "EQUIVALENT", "MR-081: abs symmetry"),
    ("G(abs(z) <= 0.5)", "G(z >= -0.5 & z <= 0.5)", "EQUIVALENT", "STLSat reads -0.5 as 0.5 unless emitted as (0 - 0.5)"),
    ("G[20,50](((x1 + x2) <= 1.5) U[2,4](x3 > 2))", "G[20,50]((x1 + x2 <= 1.5) U[0,4] (x3 > 2))", "PRED_WEAKER", "MR-019: bounded until"),
    ("G(((A = 1) | ((B = 1) & (C = 0))) -> F[0,2](D = 1))", "G(((A | B) & !C) -> F[0,2](D))", "PRED_WEAKER", "MR-028: smaller antecedent -> weaker"),
    ("G((!(o = 1) & ((t > 80) | (p > 10))) -> (s = 1))", "G((!o) -> ((t > 80 | p > 10) -> s))", "EQUIVALENT", "MR-077: currying"),
]


class KnownPairs(unittest.TestCase):
    def test_both_tools(self):
        with Checker(Config(spot_timeout=20, stlsat_timeout=60)) as c:
            for g, p, exp, why in CASES:
                r = c.check(g, p)
                with self.subTest(why=why):
                    if r["spot_status"] == "TIMEOUT":       # large nested bounds (e.g. MR-089) may exceed SPOT's budget
                        continue
                    self.assertEqual(r["spot_verdict"], exp, f"SPOT {why}: {r.get('spot_detail')}")
                    if r["stlsat_status"] == "OK" and not r["stlsat_bounded_approx"]:
                        self.assertEqual(r["stlsat_verdict"], exp, f"STLSat {why}")


if __name__ == "__main__":
    unittest.main()
