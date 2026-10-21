"""Tests for the matched-moneyness measurement. Synthetic fixtures only, no data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import matched_moneyness as mm  # noqa: E402


def occ(root, expiry, side, strike):
    y, m, d = expiry[2:4], expiry[5:7], expiry[8:10]
    return f"{root}{y}{m}{d}{side}{int(round(strike * 1000)):08d}"


def rows(root, spot, expiries, strikes, ratio=1.0, two_sided=True):
    out = []
    for e in expiries:
        for k in strikes:
            for side in ("C", "P"):
                intrinsic = max(0.0, spot * ratio - k) if side == "C" else max(0.0, k - spot * ratio)
                mid = intrinsic + 1.0
                out.append({"symbol": occ(root, e, side, k),
                            "bid": round(mid - 0.05, 2) if two_sided else 0.0,
                            "ask": round(mid + 0.05, 2)})
    return out


EXP = "2022-08-19"
STRIKES = [380, 390, 395, 398, 400, 402, 405, 410, 420]


class ParsingTests(unittest.TestCase):
    def test_symbol_parses_to_root_expiry_side_strike(self):
        p = mm.parse_occ("SPY220819C00400000")
        self.assertEqual(p["root"], "SPY")
        self.assertEqual(p["expiry"], "2022-08-19")
        self.assertEqual(p["side"], "call")
        self.assertEqual(p["strike"], 400.0)

    def test_rows_are_keyed_by_expiry_not_just_strike(self):
        raw = rows("SPY", 400.0, ["2022-08-19", "2022-08-26"], STRIKES)
        chain = mm.build_chain(raw)
        self.assertEqual(len(mm.expiries(chain)), 2)
        self.assertIn(("2022-08-19", 400.0, "call"), chain)
        self.assertIn(("2022-08-26", 400.0, "call"), chain)

    def test_one_sided_quotes_are_dropped_not_midpointed(self):
        chain = mm.build_chain(rows("SPY", 400.0, [EXP], STRIKES, two_sided=False))
        self.assertEqual(len(chain), 0)


class ForwardTests(unittest.TestCase):
    def test_forward_is_recovered_from_near_money_parity(self):
        chain = mm.build_chain(rows("SPY", 400.0, [EXP], STRIKES))
        fwd, n = mm.forward(chain, EXP, 400.0)
        self.assertAlmostEqual(fwd, 400.0, delta=0.5)
        self.assertLessEqual(n, len(STRIKES))

    def test_forward_ignores_far_strikes(self):
        wide = STRIKES + [40.0, 40.5, 4000.0]
        chain = mm.build_chain(rows("SPY", 400.0, [EXP], wide))
        fwd, _ = mm.forward(chain, EXP, 400.0)
        self.assertAlmostEqual(fwd, 400.0, delta=0.5)


class MatchedMoneynessTests(unittest.TestCase):
    def test_same_strike_gap_is_an_artefact_when_the_ratio_is_not_one(self):
        """The core lesson: matching strikes is not matching moneyness."""
        etf = mm.build_chain(rows("SPY", 400.0, [EXP], STRIKES, ratio=1.0))
        idx = mm.build_chain(rows("IDX", 400.0, [EXP], STRIKES, ratio=1.0035))
        g = mm.matched_gap(etf, idx, EXP, etf_spot=400.0)
        self.assertIsNotNone(g)
        self.assertAlmostEqual(g["ratio"], 1.0035, delta=0.002)
        self.assertLess(abs(g["median_matched_gap"]), 0.75,
                        "matched gap should collapse once moneyness is aligned")
        self.assertGreater(abs(g["median_same_strike_gap"]),
                           abs(g["median_matched_gap"]),
                           "the same-strike gap must be visibly larger")

    def test_no_common_expiry_returns_none(self):
        etf = mm.build_chain(rows("SPY", 400.0, ["2022-08-19"], STRIKES))
        idx = mm.build_chain(rows("IDX", 400.0, ["2022-08-26"], STRIKES))
        self.assertIsNone(mm.matched_gap(etf, idx, "2022-08-19", etf_spot=400.0))

    def test_gap_bps_conversion(self):
        self.assertAlmostEqual(mm.gap_bps(0.4, 400.0), 10.0)


class VerdictTests(unittest.TestCase):
    def _table(self, medians):
        return [{"cohort_expiry": f"2022-{i:02d}-01", "n_pairs": 20,
                 "median_gap_bps": m} for i, m in enumerate(medians, start=1)]

    def test_too_few_cohorts_is_not_estimable(self):
        self.assertEqual(mm.verdict(self._table([1.0] * 3))["verdict"], "NOT_ESTIMABLE")

    def test_inside_the_null_band_is_not_supported(self):
        v = mm.verdict(self._table([0.3, -0.2, 0.1, -0.4, 0.2, -0.1, 0.0, 0.3]))
        self.assertEqual(v["verdict"], "NOT_SUPPORTED")

    def test_large_and_consistent_is_a_stable_effect(self):
        v = mm.verdict(self._table([3.0, 2.5, 4.0, 3.2, 2.8, 3.5, 2.2, 3.9]))
        self.assertEqual(v["verdict"], "STABLE_EFFECT")

    def test_between_null_band_and_effect_threshold_is_inconclusive(self):
        v = mm.verdict(self._table([1.5] * 8))
        self.assertEqual(v["verdict"], "INCONCLUSIVE")

    def test_large_but_inconsistent_is_not_a_stable_effect(self):
        v = mm.verdict(self._table([3.0, -3.0, 3.0, -3.0, 3.0, -3.0, 3.0, -3.0]))
        self.assertNotEqual(v["verdict"], "STABLE_EFFECT")

    def test_cohort_summary_drops_thin_cohorts(self):
        table = mm.cohort_summary({"2022-08-19": [1.0] * 3, "2022-08-26": [1.0] * 20})
        self.assertEqual([r["cohort_expiry"] for r in table], ["2022-08-26"])


if __name__ == "__main__":
    unittest.main()
