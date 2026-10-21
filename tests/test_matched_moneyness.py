"""Tests for the matched-moneyness measurement. Synthetic fixtures only, no data.

The fixture is shaped like the HistoricalData.net daily files (``contract``,
``expiration``, ``type``, ``strike``, ``bid``, ``ask``, ``underlying_close``)
and uses a realistic SPXW/SPY ratio of 10.025, so the forward band, root
filtering and strike matching are exercised the way the real sample does.
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import matched_moneyness as mm  # noqa: E402

QD = "2022-08-15"           # a Monday
SPY_CLOSE = 400.0
SPXW_CLOSE = 4010.0         # ratio 10.025
RATIO = SPXW_CLOSE / SPY_CLOSE
PREMIUM = 0.04              # index leg rich by 0.04 ETF points at exact moneyness
IN_WINDOW = ["2022-08-17", "2022-08-19"]      # 2 and 4 days out
OUT_OF_WINDOW = ["2022-08-15", "2022-08-23"]  # 0 and 8 days out
SPY_STRIKES = [float(k) for k in range(380, 421)]                # 41 strikes
HOLE = {4105.0, 4110.0, 4115.0, 4120.0, 4125.0, 4130.0, 4135.0, 4140.0, 4145.0}
SPXW_STRIKES = [float(k) for k in range(3700, 4305, 5) if float(k) not in HOLE]


def fair(m):
    """Call value as a fraction of spot at moneyness m = K / S."""
    return max(0.0, 1.0 - m) + 0.01 + 0.02 * math.exp(-((m - 1.0) / 0.03) ** 2)


def occ(root, expiry, side, strike):
    return f"{root}{expiry[2:4]}{expiry[5:7]}{expiry[8:10]}{side}{int(round(strike * 1000)):08d}"


def chain_rows(root, spot, strikes, expiries, extra=0.0, half_spread=0.05, quote_date=QD):
    """Call and put rows priced off one moneyness curve; puts satisfy zero-rate parity."""
    out = []
    for e in expiries:
        for k in strikes:
            call = spot * fair(k / spot) + extra
            put = call - (spot - k)
            for side, mid in (("C", call), ("P", put)):
                out.append({"contract": occ(root, e, side, k), "underlying": root, "expiration": e,
                            "type": "call" if side == "C" else "put", "strike": f"{k:g}",
                            "style": "A" if root == "SPY" else "E", "quote_date": quote_date,
                            "bid": repr(mid - half_spread), "ask": repr(mid + half_spread),
                            "underlying_close": repr(spot)})
    return out


def day_rows(quote_date=QD, spy_close=SPY_CLOSE, spxw_close=SPXW_CLOSE):
    exps = IN_WINDOW + OUT_OF_WINDOW
    rows = chain_rows("SPY", spy_close, SPY_STRIKES, exps, quote_date=quote_date)
    rows += chain_rows("SPXW", spxw_close, SPXW_STRIKES, exps, extra=PREMIUM * spxw_close / spy_close,
                       half_spread=0.5, quote_date=quote_date)
    # AM-settled SPX monthly on the same expiry, priced far off. Must never be used.
    rows += chain_rows("SPX", spxw_close, SPXW_STRIKES, ["2022-08-19"], extra=500.0, quote_date=quote_date)
    # an unrelated root sharing the file
    rows += chain_rows("KO", 64.38, [60.0, 65.0], ["2022-08-19"], quote_date=quote_date)
    return rows


class LoadingTests(unittest.TestCase):
    def test_real_column_names_build_a_non_empty_chain(self):
        chain = mm.build_chain(day_rows())
        self.assertGreater(len(chain), 0)
        self.assertIn(("SPY", "2022-08-19", 400.0, "call"), chain)
        self.assertIn(("SPXW", "2022-08-19", 4010.0, "call"), chain)

    def test_root_is_contract_without_last_15_chars(self):
        self.assertEqual(mm.contract_root("SPXW220819C03620000"), "SPXW")
        self.assertEqual(mm.contract_root("SPX220819C03620000"), "SPX")
        self.assertEqual(mm.parse_occ("SPY220819C00400000")["strike"], 400.0)

    def test_spx_and_other_roots_are_not_loaded(self):
        chain = mm.build_chain(day_rows())
        self.assertEqual({k[0] for k in chain}, {"SPY", "SPXW"})

    def test_closes_come_from_underlying_close(self):
        snap = mm.load_snapshot(day_rows())
        self.assertEqual(snap.quote_date, QD)
        self.assertEqual(snap.closes, {"SPY": SPY_CLOSE, "SPXW": SPXW_CLOSE})
        self.assertTrue(snap.close_is_unique("SPY") and snap.close_is_unique("SPXW"))

    def test_bad_quotes_are_dropped_but_their_close_still_counts(self):
        rows = chain_rows("SPY", SPY_CLOSE, [400.0], ["2022-08-19"])
        rows[0]["bid"] = ""            # one-sided call
        rows[1]["bid"], rows[1]["ask"] = "2.0", "1.0"   # crossed put
        snap = mm.load_snapshot(rows)
        self.assertEqual(snap.chain, {})
        self.assertEqual(snap.closes["SPY"], SPY_CLOSE)

    def test_two_quote_dates_in_one_snapshot_raise(self):
        rows = day_rows() + day_rows(quote_date="2022-08-16")
        with self.assertRaises(ValueError):
            mm.load_snapshot(rows)


class RatioTests(unittest.TestCase):
    def test_close_ratio_is_spxw_close_over_spy_close(self):
        snap = mm.load_snapshot(day_rows())
        self.assertEqual(mm.ratio_for(snap, "2022-08-19"), RATIO)

    def test_parity_forward_uses_each_roots_own_spot(self):
        """A band centred on the ETF spot finds no index strikes at a ratio near 10."""
        snap = mm.load_snapshot(day_rows())
        f_spy, n_spy = mm.forward(snap.chain, "SPY", "2022-08-19", SPY_CLOSE)
        f_spx, n_spx = mm.forward(snap.chain, "SPXW", "2022-08-19", SPXW_CLOSE)
        self.assertAlmostEqual(f_spy, SPY_CLOSE, places=9)
        self.assertAlmostEqual(f_spx, SPXW_CLOSE, places=9)
        self.assertGreater(n_spx, 0)
        self.assertEqual(mm.forward(snap.chain, "SPXW", "2022-08-19", SPY_CLOSE), (None, 0))
        self.assertAlmostEqual(mm.ratio_for(snap, "2022-08-19", "parity"), RATIO, places=9)


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.snap = mm.load_snapshot(day_rows())
        self.res = mm.measure_snapshot(self.snap)
        self.pairs = self.res["pairs"]

    def test_every_spy_call_strike_is_used_on_1_to_7_day_expiries(self):
        self.assertEqual(len(self.pairs), len(SPY_STRIKES) * len(IN_WINDOW))
        self.assertEqual({p.expiry for p in self.pairs}, set(IN_WINDOW))
        self.assertEqual({p.etf_strike for p in self.pairs}, set(SPY_STRIKES))

    def test_index_leg_is_spxw_not_spx(self):
        spx_mid = SPXW_CLOSE * fair(4010.0 / SPXW_CLOSE) + 500.0
        for p in self.pairs:
            self.assertLess(p.index_mid, spx_mid - 100)

    def test_exact_moneyness_pair_recovers_the_planted_premium(self):
        p = next(p for p in self.pairs if p.expiry == "2022-08-19" and p.etf_strike == 400.0)
        self.assertEqual(p.index_strike, 4010.0)
        self.assertAlmostEqual(p.offset_etf_points, 0.0, places=9)
        self.assertAlmostEqual(p.gap_bps, 1e4 * PREMIUM / 400.0, places=6)

    def test_gap_bps_is_index_mid_over_ratio_minus_etf_mid_in_etf_strike_bps(self):
        p = next(p for p in self.pairs if p.expiry == "2022-08-17" and p.etf_strike == 385.0)
        q_e = self.snap.chain[("SPY", "2022-08-17", 385.0, "call")]
        q_i = self.snap.chain[("SPXW", "2022-08-17", p.index_strike, "call")]
        self.assertEqual(p.gap_bps, 1e4 * (q_i.mid / RATIO - q_e.mid) / 385.0)

    def test_near_exact_pairs_center_on_the_premium(self):
        tight = [p.gap_bps for p in self.pairs if abs(p.offset_etf_points) <= 0.01]
        self.assertGreater(len(tight), 4)
        for g in tight:
            self.assertAlmostEqual(g, 1e4 * PREMIUM / 400.0, delta=0.5)

    def test_strike_hole_is_reported_and_tolerance_drops_it(self):
        far = sorted({p.etf_strike for p in self.pairs if abs(p.offset_etf_points) > 1.0})
        self.assertEqual(far, [410.0, 411.0, 412.0])
        self.assertEqual(self.res["n_offset_over_1pt"], 3 * len(IN_WINDOW))
        tol = mm.measure_snapshot(self.snap, max_offset=1.0)
        self.assertEqual(len(tol["pairs"]), len(self.pairs) - 6)
        self.assertEqual(tol["n_dropped_by_tolerance"], 6)

    def test_nearest_strike_tie_goes_to_the_lower_strike(self):
        self.assertEqual(mm.nearest_strike([4000.0, 4010.0], 4005.0), 4000.0)
        self.assertEqual(mm.nearest_strike([4000.0, 4010.0], 4005.1), 4010.0)
        self.assertEqual(mm.nearest_strike([4000.0, 4010.0], 3000.0), 4000.0)
        self.assertEqual(mm.nearest_strike([4000.0, 4010.0], 9000.0), 4010.0)

    def test_no_index_expiry_means_no_pairs(self):
        rows = [r for r in day_rows() if not (r["contract"].startswith("SPXW") and r["expiration"] == "2022-08-17")]
        pairs = mm.measure_snapshot(mm.load_snapshot(rows))["pairs"]
        self.assertEqual({p.expiry for p in pairs}, {"2022-08-19"})

    def test_same_strike_gap_is_an_artefact_when_the_ratio_is_not_one(self):
        """Matching strikes is not matching moneyness."""
        r = 1.0035
        rows = chain_rows("SPY", 400.0, SPY_STRIKES, ["2022-08-19"])
        # the index proxy lists the ETF's strikes plus the exact-moneyness ones
        rows += chain_rows("XSP", 400.0 * r, sorted(set(SPY_STRIKES) | {k * r for k in SPY_STRIKES}),
                           ["2022-08-19"])
        snap = mm.load_snapshot(rows, roots=("SPY", "XSP"))
        same = mm.same_strike_gap_bps(snap.chain, "2022-08-19", r, "SPY", "XSP")
        g = mm.matched_gap(snap.chain, "2022-08-19", r, QD, "SPY", "XSP")
        self.assertGreater(abs(same), 10 * abs(g["median_matched_gap_bps"]))


class CohortTests(unittest.TestCase):
    def test_cohort_pools_quote_dates_of_one_expiry(self):
        pairs = []
        for qd, spy, spx in (("2022-08-15", 400.0, 4010.0), ("2022-08-16", 402.0, 4030.0)):
            pairs += mm.measure_snapshot(mm.load_snapshot(day_rows(qd, spy, spx)))["pairs"]
        table = {r["cohort_expiry"]: r for r in mm.cohort_table(pairs)}
        self.assertEqual(table["2022-08-19"]["n_pairs"], 2 * len(SPY_STRIKES))
        self.assertEqual({p.quote_date for p in pairs}, {"2022-08-15", "2022-08-16"})

    def _pairs(self, specs):
        return [mm.Pair(qd, "2022-08-19", k, k * 10, 1.0, 10.0, 10.0, 0.0, 0.1) for qd, k in specs]

    def test_min_rule_variants(self):
        # 8 pooled pairs but only 4 distinct strikes, spread over two quote dates
        pairs = self._pairs([(qd, k) for qd in ("2022-08-15", "2022-08-16") for k in (400, 401, 402, 403)])
        self.assertEqual(len(mm.cohort_table(pairs, count="pairs")), 1)
        self.assertEqual(len(mm.cohort_table(pairs, count="distinct_strikes")), 0)
        self.assertEqual(len(mm.cohort_table(pairs, count="per_snapshot")), 0)

    def test_cohort_summary_drops_thin_cohorts(self):
        table = mm.cohort_summary({"2022-08-19": [1.0] * 3, "2022-08-26": [1.0] * 20})
        self.assertEqual([r["cohort_expiry"] for r in table], ["2022-08-26"])

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


if __name__ == "__main__":
    unittest.main()
