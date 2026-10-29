"""Frozen SPY/SPXW one-calendar-day expiry payoff diagnostic."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
import math
import re
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Quote:
    contract: str
    underlying: str
    expiration: date
    right: str
    strike: float
    style: str
    quote_date: date
    bid: float
    ask: float
    underlying_close: float
    settlement_time: str


@dataclass(frozen=True)
class Payoff:
    spy_contract: str
    spxw_contract: str
    entry_date: date
    expiry: date
    spy_strike: float
    spxw_strike: float
    ratio: float
    crossing_credit: float
    midpoint_credit: float
    terminal_value: float
    gross_crossing_pnl: float
    gross_midpoint_pnl: float
    reverse_crossing_pnl: float
    strike_cash_mismatch: float
    entry_underlying_exposure_mismatch: float
    terminal_stress_low: float
    terminal_stress_high: float
    crossing_cost: float
    normalized_moneyness_mismatch: float


OSI = re.compile(r"^([A-Z0-9.]{1,6})(\d{6})([CP])(\d{8})$")


def _finite_positive(value: object) -> bool:
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (OverflowError, TypeError, ValueError):
        return False


def validate_quote(q: Quote) -> str | None:
    """Return a counted rejection reason, or None for a protocol-valid quote."""
    if q.underlying not in {"SPY", "SPXW"}:
        return "underlying"
    if not isinstance(q.right, str) or q.right.lower() != "call":
        return "right"
    if not _finite_positive(q.strike):
        return "strike"
    if not (_finite_positive(q.bid) and _finite_positive(q.ask) and q.ask >= q.bid):
        return "quote"
    if not _finite_positive(q.underlying_close):
        return "underlying_close"
    if q.quote_date > q.expiration:
        return "date"
    if not isinstance(q.contract, str):
        return "contract_identity"
    osi = OSI.fullmatch(q.contract)
    if not osi:
        return "contract_identity"
    root, ymd, cp, strike_milli = osi.groups()
    try:
        osi_expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:]))
    except ValueError:
        return "contract_identity"
    if osi_expiry != q.expiration or cp != "C" or abs(int(strike_milli) / 1000 - q.strike) > 1e-8:
        return "contract_identity"
    if root != q.underlying:
        return "contract_root"
    if q.underlying == "SPY" and ((q.style or "").upper() != "A" or (q.settlement_time or "").upper() != "PM"):
        return "spy_style_settlement"
    if q.underlying == "SPXW" and ((q.style or "").upper() != "E" or (q.settlement_time or "").upper() != "PM"):
        return "spxw_style_settlement"
    return None


def _unique_quotes(quotes: Iterable[Quote], exclusions: Counter) -> list[Quote]:
    seen: dict[tuple, Quote] = {}
    conflicted: set[tuple] = set()
    for q in quotes:
        reason = validate_quote(q)
        if reason:
            exclusions[reason] += 1
            continue
        key = (q.quote_date, q.contract)
        previous = seen.get(key)
        if previous is not None:
            if previous != q:
                conflicted.add(key)
            else:
                exclusions["duplicate"] += 1
        else:
            seen[key] = q
    for key in conflicted:
        seen.pop(key, None)
        exclusions["duplicate_conflict"] += 1
    return list(seen.values())


def select_pairs(quotes: Iterable[Quote], exclusions: Counter | None = None) -> list[tuple[Quote, Quote, float]]:
    """Select entry pairs without consulting terminal prices or future observations."""
    counts = exclusions if exclusions is not None else Counter()
    valid = _unique_quotes(quotes, counts)
    by_day: dict[date, list[Quote]] = defaultdict(list)
    for q in valid:
        by_day[q.quote_date].append(q)
    pairs = []
    for day, rows in by_day.items():
        spy = [q for q in rows if q.underlying == "SPY" and (q.expiration - day).days == 1]
        idx = [q for q in rows if q.underlying == "SPXW" and (q.expiration - day).days == 1]
        spy_closes = {q.underlying_close for q in spy}
        idx_closes = {q.underlying_close for q in idx}
        if len(spy_closes) != 1 or len(idx_closes) != 1:
            if spy or idx:
                counts["entry_underlying_conflict_or_missing"] += 1
            continue
        ratio = next(iter(idx_closes)) / next(iter(spy_closes))
        for s in spy:
            if abs(s.strike / s.underlying_close - 1) > 0.02 + 1e-12:
                counts["spy_outside_2pct"] += 1
                continue
            candidates = [i for i in idx if i.expiration == s.expiration]
            if not candidates:
                counts["no_same_expiry_spxw"] += 1
                continue
            # Explicit lower strike tie break.
            target = s.strike * ratio
            i = min(candidates, key=lambda x: (abs(x.strike - target), x.strike))
            if abs((i.strike / ratio) / s.strike - 1) > 0.001 + 1e-12:
                counts["moneyness_mismatch"] += 1
                continue
            pairs.append((s, i, ratio))
    return pairs


def _intrinsic(underlying: float, strike: float) -> float:
    return max(underlying - strike, 0.0)


def payoff(spy: Quote, spxw: Quote, ratio: float, spy_terminal: float,
           spx_terminal: float, stress_points: float = 3.05) -> Payoff:
    if not (_finite_positive(spy_terminal) and _finite_positive(spx_terminal) and _finite_positive(ratio)):
        raise ValueError("terminal references and ratio must be finite and positive")
    try:
        stress_valid = math.isfinite(float(stress_points)) and float(stress_points) >= 0
    except (OverflowError, TypeError, ValueError):
        stress_valid = False
    if not stress_valid:
        raise ValueError("stress_points must be finite and nonnegative")
    crossing = 1000 * spy.bid - 100 * spxw.ask
    midpoint = 1000 * (spy.bid + spy.ask) / 2 - 100 * (spxw.bid + spxw.ask) / 2
    terminal = 100 * _intrinsic(spx_terminal, spxw.strike) - 1000 * _intrinsic(spy_terminal, spy.strike)
    reverse_cross = 100 * spxw.bid - 1000 * spy.ask
    strike_cash_mismatch = 1000 * spy.strike - 100 * spxw.strike
    exposure_mismatch = 100 * spxw.underlying_close - 1000 * spy.underlying_close
    base_idx = 100 * _intrinsic(spx_terminal, spxw.strike)
    low_idx = 100 * _intrinsic(max(0, spx_terminal - stress_points), spxw.strike)
    high_idx = 100 * _intrinsic(spx_terminal + stress_points, spxw.strike)
    # Stress only the index reference; SPY intrinsic remains at the observed close.
    return Payoff(spy.contract, spxw.contract, spy.quote_date, spy.expiration,
                  spy.strike, spxw.strike, ratio, crossing, midpoint, terminal,
                  crossing + terminal, midpoint + terminal, reverse_cross - terminal,
                  strike_cash_mismatch, exposure_mismatch,
                  terminal + low_idx - base_idx, terminal + high_idx - base_idx,
                  midpoint - crossing, abs((spxw.strike / ratio) / spy.strike - 1))


def evaluate(pairs: Iterable[tuple[Quote, Quote, float]], terminal: Mapping[tuple[date, str], float],
             exclusions: Counter | None = None) -> list[Payoff]:
    counts = exclusions if exclusions is not None else Counter()
    out = []
    for spy, idx, ratio in pairs:
        skey, ikey = (spy.expiration, "SPY"), (idx.expiration, "SPXW")
        if skey not in terminal or ikey not in terminal:
            counts["missing_terminal_reference"] += 1
            continue
        if not (_finite_positive(terminal[skey]) and _finite_positive(terminal[ikey])):
            counts["invalid_terminal_reference"] += 1
            continue
        out.append(payoff(spy, idx, ratio, terminal[skey], terminal[ikey]))
    return out
