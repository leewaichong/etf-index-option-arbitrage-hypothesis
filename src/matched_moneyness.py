"""Matched-moneyness gap measurement for index vs ETF option pairs.

The question: if two instruments give the same economic exposure, options on them
with the same expiry should cost the same once their strikes are put at the same
moneyness. If they do not, and the difference persists, that is an arbitrage-style
edge rather than noise.

Two instruments on the same underlying do NOT necessarily trade at the same price:
a fund tracking one tenth of an index trades near one tenth of its level. Matching
"the same strike" therefore compares two different contracts. The only correct
comparison puts both legs at the same moneyness:

    matched index strike = round(etf_strike * ratio)
    ratio                = index_forward / etf_forward

with both forwards taken from put-call parity on the same snapshot.

No data ships with this module. Feed it rows from any source with a documented
schema (see README) or use the parser below.
"""
from __future__ import annotations

import re
import statistics as st
from dataclasses import dataclass
from typing import Iterable

OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")

# Thresholds used in the published test. They were fixed before the data was
# opened and are not tuned here.
MIN_EFFECT_BPS = 2.0
MIN_SAME_DIRECTION_SHARE = 0.60
NULL_BAND_BPS = 1.0
MIN_COHORTS = 8
MIN_COHORT_STRIKES = 8
NEAR_MONEY_BAND = 0.02


@dataclass(frozen=True)
class Quote:
    expiry: str      # YYYY-MM-DD
    strike: float
    side: str        # "call" | "put"
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


def parse_occ(symbol: str) -> dict | None:
    """Split an OSI/OCC symbol into root, expiry, side and strike."""
    m = OCC.match((symbol or "").strip())
    if not m:
        return None
    root, ymd, side, strike = m.groups()
    return {
        "root": root,
        "expiry": f"20{ymd[:2]}-{ymd[2:4]}-{ymd[4:6]}",
        "side": "call" if side == "C" else "put",
        "strike": int(strike) / 1000.0,
    }


def build_chain(rows: Iterable[dict]) -> dict:
    """Key quotes by (expiry, strike, side).

    Keying by strike alone silently mixes expiries, because a chain file carries
    every listed expiry at once. One-sided or crossed quotes are dropped rather
    than mid-pointed: a zero bid is not a price.
    """
    chain: dict[tuple[str, float, str], Quote] = {}
    for r in rows:
        parts = parse_occ(r.get("symbol") or r.get("option") or "")
        if not parts:
            continue
        try:
            bid, ask = float(r["bid"]), float(r["ask"])
        except (KeyError, TypeError, ValueError):
            continue
        if bid <= 0 or ask <= 0 or ask < bid:
            continue
        chain[(parts["expiry"], parts["strike"], parts["side"])] = Quote(
            expiry=parts["expiry"], strike=parts["strike"], side=parts["side"],
            bid=bid, ask=ask)
    return chain


def expiries(chain: dict) -> list[str]:
    return sorted({e for (e, _k, _s) in chain})


def forward(chain: dict, expiry: str, spot: float, band: float = NEAR_MONEY_BAND):
    """Zero-rate put-call parity forward from a tight near-the-money window.

    Using the whole chain pulls in far out-of-the-money strikes whose quotes are
    not real markets; that produced a forward several percent off and unusable
    gaps. Returns (forward, number_of_strikes_used).
    """
    lo, hi = spot * (1 - band), spot * (1 + band)
    strikes = sorted({k for (e, k, _s) in chain if e == expiry and lo <= k <= hi})
    values = []
    for k in strikes:
        c, p = chain.get((expiry, k, "call")), chain.get((expiry, k, "put"))
        if c and p:
            values.append(k + c.mid - p.mid)
    if not values:
        return None, 0
    return st.median(values), len(values)


def spot_proxy(chain: dict, expiry: str) -> float | None:
    """Rough spot when no underlying print is available, used only to pick the band."""
    strikes = sorted({k for (e, k, _s) in chain if e == expiry and _s == "call"})
    if not strikes:
        return None
    return strikes[len(strikes) // 2]


def matched_gap(etf_chain: dict, index_chain: dict, expiry: str,
                etf_spot: float | None = None, max_strike_distance: float = 8.0) -> dict | None:
    """Gap between the two legs at equal moneyness, in ETF points.

    `gap = index_mid / ratio - etf_mid`, so a positive number means the index leg
    is the more expensive one at the same moneyness.
    """
    etf_spot = etf_spot or spot_proxy(etf_chain, expiry)
    if not etf_spot:
        return None
    index_forward, n_parity = forward(index_chain, expiry, etf_spot)
    if not index_forward:
        return None
    etf_forward, _ = forward(etf_chain, expiry, etf_spot)
    if not etf_forward:
        return None
    ratio = index_forward / etf_forward

    etf_strikes = sorted({k for (e, k, s) in etf_chain if e == expiry and s == "call"})
    index_strikes = sorted({k for (e, k, s) in index_chain if e == expiry and s == "call"})
    if not etf_strikes or not index_strikes:
        return None
    anchor = min(etf_strikes, key=lambda k: abs(k - etf_spot))

    same, matched, pairs = [], [], []
    for k in [k for k in etf_strikes if abs(k - anchor) <= max_strike_distance]:
        e_row = etf_chain.get((expiry, k, "call"))
        if not e_row:
            continue
        i_same = index_chain.get((expiry, k, "call"))
        if i_same:
            same.append(i_same.mid / ratio - e_row.mid)
        target = k * ratio
        near = min(index_strikes, key=lambda x: abs(x - target))
        i_row = index_chain.get((expiry, near, "call"))
        if i_row:
            matched.append(i_row.mid / ratio - e_row.mid)
            pairs.append({"etf_strike": k, "index_strike": near})

    if not matched:
        return None
    return {
        "expiry": expiry,
        "ratio": round(ratio, 6),
        "parity_strikes": n_parity,
        "anchor_strike": anchor,
        "median_same_strike_gap": st.median(same) if same else None,
        "median_matched_gap": st.median(matched),
        "n_matched": len(matched),
        "pairs": pairs,
    }


def gap_bps(gap_points: float, etf_strike: float) -> float:
    """Express a gap in basis points of the ETF strike."""
    return 10000.0 * gap_points / etf_strike if etf_strike else float("nan")


def cohort_summary(per_cohort_bps: dict[str, list[float]], min_strikes: int = MIN_COHORT_STRIKES):
    """Median gap per cohort. A cohort is one expiry date."""
    table = []
    for expiry in sorted(per_cohort_bps):
        values = per_cohort_bps[expiry]
        if len(values) < min_strikes:
            continue
        table.append({"cohort_expiry": expiry, "n_pairs": len(values),
                      "median_gap_bps": round(st.median(values), 3)})
    return table


def verdict(table: list[dict]) -> dict:
    """Apply the rule fixed before the data was opened."""
    if len(table) < MIN_COHORTS:
        return {"verdict": "NOT_ESTIMABLE",
                "reason": f"fewer than {MIN_COHORTS} cohorts"}
    medians = [row["median_gap_bps"] for row in table]
    overall = st.median(medians)
    positives = sum(1 for m in medians if m > 0)
    share = max(positives, len(medians) - positives) / len(medians)
    out = {"median_of_cohort_medians_bps": round(overall, 3),
           "cohorts": len(medians),
           "cohorts_positive": positives,
           "same_direction_share": round(share, 3)}
    if abs(overall) < NULL_BAND_BPS:
        out["verdict"] = "NOT_SUPPORTED"
        out["reason"] = f"median inside the +-{NULL_BAND_BPS} bps null band"
    elif abs(overall) >= MIN_EFFECT_BPS and share >= MIN_SAME_DIRECTION_SHARE:
        out["verdict"] = "STABLE_EFFECT"
        out["reason"] = "median clears the effect threshold in a consistent direction"
    else:
        out["verdict"] = "INCONCLUSIVE"
        out["reason"] = "clears neither the null band nor the full effect rule"
    return out
