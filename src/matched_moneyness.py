"""Matched-moneyness gap between ETF options and index options.

This module implements the method that produced ``results/cohort_2022h2.csv``.

For one end-of-day snapshot (one quote date):

* ETF leg is root ``SPY``, index leg is root ``SPXW``. The root is the contract
  symbol with its trailing 15 characters removed, so ``SPX`` (AM-settled
  monthlies) is a different root and is never mixed in.
* ``ratio = underlying_close(SPXW) / underlying_close(SPY)`` on that date.
* Every quoted SPY call strike ``K`` on an expiry 1 to 7 calendar days out is
  paired with the quoted SPXW call whose strike is nearest to ``K * ratio``
  (ties go to the lower strike). No strike window around spot and, by default,
  no tolerance on how far the nearest strike may be.
* ``gap_bps = 1e4 * (index_mid / ratio - etf_mid) / K``. Positive means the
  index leg is the more expensive one at the same moneyness.
* A cohort is one expiry date. Pairs from every quote date that saw that expiry
  are pooled. The cohort is kept when it has at least 8 distinct ETF strikes.
  The published table counted pooled pairs instead; on the 2022 H2 sample the
  two rules (and a per-snapshot rule) keep the same 94 cohorts.

Input schema (one CSV row per contract, one quote date per snapshot). Extra
columns are ignored. Column names follow the HistoricalData.net option files.

==================  =========================================================
``contract``        OSI symbol, e.g. ``SPXW220819C03620000``; root is
                    ``contract[:-15]``
``quote_date``      YYYY-MM-DD, the session the row belongs to
``expiration``      YYYY-MM-DD
``type``            ``call`` or ``put``
``strike``          strike in the instrument's own units
``bid``, ``ask``    blank, zero, one-sided or crossed quotes are dropped
``underlying_close``  close of the underlying on ``quote_date``
==================  =========================================================

No data ships with this module.
"""
from __future__ import annotations

import bisect
import re
import statistics as st
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")

ETF_ROOT = "SPY"
INDEX_ROOT = "SPXW"
INPUT_COLUMNS = ("contract", "quote_date", "expiration", "type", "strike",
                 "bid", "ask", "underlying_close")

# Thresholds of the published test. Fixed before the data was opened.
MIN_EFFECT_BPS = 2.0
MIN_SAME_DIRECTION_SHARE = 0.60
NULL_BAND_BPS = 1.0
MIN_COHORTS = 8
MIN_COHORT_STRIKES = 8

# Defaults that reproduce results/cohort_2022h2.csv.
MIN_DTE = 1
MAX_DTE = 7
DEFAULT_RATIO_METHOD = "close"     # "close" or "parity"
DEFAULT_MAX_OFFSET = None          # no tolerance on the matched strike
NEAR_MONEY_BAND = 0.02             # parity variant only
OFFSET_REPORT_POINTS = 1.0         # pairs further off than this are counted


@dataclass(frozen=True)
class Quote:
    root: str
    expiry: str      # YYYY-MM-DD
    strike: float
    side: str        # "call" | "put"
    bid: float
    ask: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass(frozen=True)
class Pair:
    quote_date: str
    expiry: str
    etf_strike: float
    index_strike: float
    etf_mid: float
    index_mid: float
    ratio: float
    offset_etf_points: float   # index_strike / ratio - etf_strike
    gap_bps: float


@dataclass
class Snapshot:
    quote_date: str
    chain: dict                                   # (root, expiry, strike, side) -> Quote
    closes: dict                                  # root -> float
    close_values: dict = field(default_factory=dict)   # root -> set of closes seen

    def close_is_unique(self, root: str) -> bool:
        return len(self.close_values.get(root, ())) == 1


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


def contract_root(contract: str) -> str:
    """Product root of an OSI symbol: the symbol without its last 15 characters."""
    return (contract or "").strip()[:-15]


def _num(x) -> float | None:
    if x in ("", None):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def load_snapshot(rows: Iterable[dict], roots: tuple = (ETF_ROOT, INDEX_ROOT)) -> Snapshot:
    """Build one quote date's chain and underlying closes from schema rows.

    Quotes are keyed by (root, expiry, strike, side). All rows must share one
    ``quote_date``; mixing dates raises instead of letting one day overwrite
    another. Closes are read from every row of a root, including rows whose
    quote is later dropped. When a root carries more than one close the lowest
    is used and ``close_is_unique`` reports it.
    """
    chain: dict = {}
    close_values: dict = {r: set() for r in roots}
    quote_date = None
    for r in rows:
        root = contract_root(r.get("contract", ""))
        if root not in close_values:
            continue
        qd = r["quote_date"]
        if quote_date is None:
            quote_date = qd
        elif qd != quote_date:
            raise ValueError(f"rows from two quote dates in one snapshot: {quote_date}, {qd}")
        uc = _num(r.get("underlying_close"))
        if uc:
            close_values[root].add(uc)
        bid, ask = _num(r.get("bid")), _num(r.get("ask"))
        if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
            continue
        key = (root, r["expiration"], float(r["strike"]), r["type"])
        if key in chain:
            raise ValueError(f"duplicate quote for {key} on {quote_date}")
        chain[key] = Quote(root=root, expiry=key[1], strike=key[2], side=key[3], bid=bid, ask=ask)
    closes = {root: min(v) for root, v in close_values.items() if v}
    return Snapshot(quote_date=quote_date or "", chain=chain, closes=closes, close_values=close_values)


def build_chain(rows: Iterable[dict], roots: tuple = (ETF_ROOT, INDEX_ROOT)) -> dict:
    """Chain only, keyed by (root, expiry, strike, side). See ``load_snapshot``."""
    return load_snapshot(rows, roots).chain


def expiries(chain: dict, root: str) -> list:
    return sorted({e for (r, e, _k, _s) in chain if r == root})


def calls(chain: dict, root: str, expiry: str) -> dict:
    """Quoted calls of one root and expiry, strike -> Quote."""
    return {k: q for (r, e, k, s), q in chain.items() if r == root and e == expiry and s == "call"}


def forward(chain: dict, root: str, expiry: str, spot: float, band: float = NEAR_MONEY_BAND):
    """Zero-rate put-call parity forward from strikes within +-band of this root's own spot.

    Returns (forward, number_of_strikes_used) or (None, 0). Used only by the
    parity ratio variant.
    """
    lo, hi = spot * (1 - band), spot * (1 + band)
    values = []
    for (r, e, k, s), c in chain.items():
        if r == root and e == expiry and s == "call" and lo <= k <= hi:
            p = chain.get((root, expiry, k, "put"))
            if p is not None:
                values.append(k + c.mid - p.mid)
    if not values:
        return None, 0
    return st.median(values), len(values)


def ratio_for(snapshot: Snapshot, expiry: str, method: str = DEFAULT_RATIO_METHOD,
              etf_root: str = ETF_ROOT, index_root: str = INDEX_ROOT) -> float | None:
    """Index-to-ETF ratio. ``close``: ratio of underlying closes (the published method).

    ``parity``: ratio of parity forwards, each from a band around its own close.
    """
    e_close, i_close = snapshot.closes.get(etf_root), snapshot.closes.get(index_root)
    if not e_close or not i_close:
        return None
    if method == "close":
        return i_close / e_close
    if method == "parity":
        f_e, _ = forward(snapshot.chain, etf_root, expiry, e_close)
        f_i, _ = forward(snapshot.chain, index_root, expiry, i_close)
        return f_i / f_e if f_e and f_i else None
    raise ValueError(f"unknown ratio method {method!r}")


def nearest_strike(sorted_strikes: list, target: float) -> float:
    """Nearest strike to target; on an exact tie the lower strike wins."""
    i = bisect.bisect_left(sorted_strikes, target)
    candidates = sorted_strikes[max(i - 1, 0):i + 1]
    return min(candidates, key=lambda x: (abs(x - target), x))


def gap_bps(gap_points: float, etf_strike: float) -> float:
    """Express a gap in basis points of the ETF strike."""
    return 10000.0 * gap_points / etf_strike if etf_strike else float("nan")


def matched_gap(chain: dict, expiry: str, ratio: float, quote_date: str = "",
                etf_root: str = ETF_ROOT, index_root: str = INDEX_ROOT,
                max_offset: float | None = DEFAULT_MAX_OFFSET) -> dict | None:
    """Pair every quoted ETF call of ``expiry`` with the nearest quoted index call.

    ``max_offset`` (ETF points) drops pairs whose index strike, divided by the
    ratio, sits further than that from the ETF strike. ``None`` keeps every pair,
    which is how the published table was made.
    """
    e_calls = calls(chain, etf_root, expiry)
    i_calls = calls(chain, index_root, expiry)
    if not e_calls or not i_calls or not ratio:
        return None
    i_strikes = sorted(i_calls)
    pairs, n_far, n_dropped = [], 0, 0
    for k in sorted(e_calls):
        near = nearest_strike(i_strikes, k * ratio)
        offset = near / ratio - k
        if abs(offset) > OFFSET_REPORT_POINTS:
            n_far += 1
        if max_offset is not None and abs(offset) > max_offset:
            n_dropped += 1
            continue
        e_mid, i_mid = e_calls[k].mid, i_calls[near].mid
        pairs.append(Pair(quote_date=quote_date, expiry=expiry, etf_strike=k, index_strike=near,
                          etf_mid=e_mid, index_mid=i_mid, ratio=ratio, offset_etf_points=offset,
                          gap_bps=gap_bps(i_mid / ratio - e_mid, k)))
    if not pairs:
        return None
    return {
        "expiry": expiry,
        "ratio": ratio,
        "pairs": pairs,
        "n_matched": len(pairs),
        "median_matched_gap_bps": st.median(p.gap_bps for p in pairs),
        "n_offset_over_1pt": n_far,
        "n_dropped_by_tolerance": n_dropped,
    }


def same_strike_gap_bps(chain: dict, expiry: str, ratio: float,
                        etf_root: str = ETF_ROOT, index_root: str = INDEX_ROOT) -> float | None:
    """Median gap when both legs use the identical strike. The artefact the method avoids."""
    e_calls, i_calls = calls(chain, etf_root, expiry), calls(chain, index_root, expiry)
    gaps = [gap_bps(i_calls[k].mid / ratio - q.mid, k) for k, q in e_calls.items() if k in i_calls]
    return st.median(gaps) if gaps else None


def measure_snapshot(snapshot: Snapshot, min_dte: int = MIN_DTE, max_dte: int = MAX_DTE,
                     ratio_method: str = DEFAULT_RATIO_METHOD,
                     max_offset: float | None = DEFAULT_MAX_OFFSET,
                     etf_root: str = ETF_ROOT, index_root: str = INDEX_ROOT) -> dict:
    """All matched pairs of one snapshot.

    Returns {"pairs": [...], "n_offset_over_1pt": int, "n_dropped_by_tolerance": int}.
    """
    out = {"pairs": [], "n_offset_over_1pt": 0, "n_dropped_by_tolerance": 0}
    qd = date.fromisoformat(snapshot.quote_date)
    index_expiries = set(expiries(snapshot.chain, index_root))
    for exp in expiries(snapshot.chain, etf_root):
        dte = (date.fromisoformat(exp) - qd).days
        if not (min_dte <= dte <= max_dte) or exp not in index_expiries:
            continue
        ratio = ratio_for(snapshot, exp, ratio_method, etf_root, index_root)
        g = matched_gap(snapshot.chain, exp, ratio, snapshot.quote_date, etf_root, index_root, max_offset)
        if g:
            out["pairs"].extend(g["pairs"])
            out["n_offset_over_1pt"] += g["n_offset_over_1pt"]
            out["n_dropped_by_tolerance"] += g["n_dropped_by_tolerance"]
    return out


def cohort_summary(per_cohort_bps: dict, min_strikes: int = MIN_COHORT_STRIKES):
    """Median gap per cohort (one expiry). Counts pooled pairs, as the published table did."""
    table = []
    for expiry in sorted(per_cohort_bps):
        values = per_cohort_bps[expiry]
        if len(values) < min_strikes:
            continue
        table.append({"cohort_expiry": expiry, "n_pairs": len(values),
                      "median_gap_bps": round(st.median(values), 3)})
    return table


def cohort_table(pairs: Iterable[Pair], min_strikes: int = MIN_COHORT_STRIKES,
                 count: str = "distinct_strikes") -> list:
    """Cohort table from pairs.

    ``count`` sets what the minimum applies to:
    ``distinct_strikes``  distinct ETF strikes in the cohort (default, the
                          pre-registered "8 strikes per cohort")
    ``pairs``             pooled pairs across quote dates, which is how the
                          published table was filtered
    ``per_snapshot``      drop each (quote date, expiry) snapshot with fewer
                          than ``min_strikes`` pairs before pooling
    """
    by_snap: dict = {}
    for p in pairs:
        by_snap.setdefault((p.expiry, p.quote_date), []).append(p)
    pooled: dict = {}
    for (exp, _qd), ps in sorted(by_snap.items()):
        if count == "per_snapshot" and len(ps) < min_strikes:
            continue
        pooled.setdefault(exp, []).extend(ps)
    table = []
    for exp in sorted(pooled):
        ps = pooled[exp]
        if count == "distinct_strikes":
            enough = len({p.etf_strike for p in ps}) >= min_strikes
        elif count in ("pairs", "per_snapshot"):
            enough = len(ps) >= min_strikes
        else:
            raise ValueError(f"unknown count rule {count!r}")
        if enough:
            table.append({"cohort_expiry": exp, "n_pairs": len(ps),
                          "median_gap_bps": round(st.median(p.gap_bps for p in ps), 3)})
    return table


def verdict(table: list) -> dict:
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
