import unittest

from equivalence.ast import to_str
from equivalence.datasets import load_manual_review
from equivalence.normalize import canonical, normalise_pair
from equivalence.parser import ParseError, parse


class Dialects(unittest.TestCase):
    SAME = [
        ["G[0,5](a -> F[0,2] b)", "G_[0,5] (a → F_{[0,2]} b)", "□[0,5](a ⇒ ◇[0:2] b)",
         "always[0,5] (a implies eventually[0..2] b)", r"\Box_{[0,5]} (a \rightarrow \Diamond_{[0,2]} b)",
         "[] [0,5] (a => <>[0,2] b)"],
        ["a && b || !c", "a & b | ~c", "(a and b) or not c", r"a /\ b \/ ¬c"],
        ["abs(x - y) <= 0.5", "|x - y| <= 0.5", "abs(x-y) ≤ 0.5"],
        ["x = 1", "x == 1"],
    ]

    def test_equivalent_notations(self):
        for group in self.SAME:
            forms = {to_str(parse(s)) for s in group}
            self.assertEqual(len(forms), 1, f"{group} -> {forms}")

    def test_precedence(self):
        self.assertEqual(to_str(parse("G a -> b")), "(G(a) -> b)")
        self.assertEqual(to_str(parse("!a U b")), "(!a U b)")
        self.assertEqual(to_str(parse("a & b U c")), "(a & (b U c))")
        self.assertEqual(to_str(parse("a -> b -> c")), "(a -> (b -> c))")
        self.assertEqual(to_str(parse("!x > 3")), "!(x > 3)")

    def test_identifiers_that_look_like_operators(self):
        # the old pipeline turned these into F[0,100000]sig / G[0,100000]sig
        self.assertEqual(to_str(parse("F[0,5](Fsig | Gsig)")), "F[0,5]((Fsig | Gsig))")
        self.assertEqual(to_str(parse("G[0,H](y > 0)")), "G[0,H]((y > 0))")      # symbolic bound
        self.assertEqual(to_str(parse("(warning) S (loss_of_signal)")), "(warning S loss_of_signal)")

    def test_errors(self):
        for bad in ["", "G[0,5]", "a &", "F[5,2] a", "G[0,30](x > 1) & F[0,60](station_a..."]:
            with self.assertRaises(ParseError):
                parse(bad)

    def test_whole_manual_review_parses(self):
        df = load_manual_review(unique=False)
        for s in set(df.gold) | set(df.pred):
            parse(s)


class Normalisation(unittest.TestCase):
    def test_boolean_shorthand(self):
        ctx = "Boolean (1=true, 0=false): `a`, `b`. Numeric: `x`."
        n = normalise_pair(parse("(a = 1) & (b = 0) & (x = 0)"), parse("a & !b & x == 0"), ctx)
        self.assertEqual(to_str(canonical(n.gold)), to_str(canonical(n.pred)))
        self.assertIn("(x == 0)", to_str(n.gold))          # numeric x stays a comparison

    def test_joint_interval_scaling(self):
        # each formula used to be scaled with its own factor: F[0,0.5] -> F[0,1] == F[0,1]
        n = normalise_pair(parse("F[0,0.5] a"), parse("F[0,1] a"))
        self.assertEqual(n.time_scale, 2)
        self.assertNotEqual(to_str(n.gold), to_str(n.pred))

    def test_canonical_symmetries(self):
        sym = {"distance"}
        a = canonical(parse("G(abs(a - b) < 1 & distance(p, q) < d)"), sym)
        b = canonical(parse("G(distance(q, p) < d & abs(b - a) < 1)"), sym)
        self.assertEqual(to_str(a), to_str(b))


if __name__ == "__main__":
    unittest.main()
