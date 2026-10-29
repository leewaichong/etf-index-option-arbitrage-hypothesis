"""Helpers for official-reference expiry selection and physical-settlement ledgers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Iterable, Mapping

from .expiry_payoff import Quote, validate_quote


@dataclass(frozen=True)
class StockDay:
    day: date
    open: float
    close: float
    dividend: float


def compare_date_values(left: Mapping[date, float], right: Mapping[date, float]) -> dict:
    """Summarize value differences on dates present in both inputs."""
    shared=sorted(set(left)&set(right))
    differences=[abs(float(left[d])-float(right[d])) for d in shared]
    return {'comparable_date_count':len(shared),
        'exact_match_count':sum(float(left[d])==float(right[d]) for d in shared),
        'different_value_count':sum(float(left[d])!=float(right[d]) for d in shared),
        'max_absolute_difference':max(differences) if differences else None,
        'mean_absolute_difference':sum(differences)/len(differences) if differences else None}


def source_value_reconciliation(vendor: Mapping, raw_stocks: Mapping,
                                official_spx: Mapping[date, float],
                                spxw_settlements: Mapping) -> dict:
    """Compare the three requested source pairs without building payoff rows."""
    vendor_spy={d:v for (d,symbol),v in vendor.items() if symbol=='SPY'}
    vendor_spxw={d:v for (d,symbol),v in vendor.items() if symbol=='SPXW'}
    raw_close={d:row['close'] for d,row in raw_stocks.items()}
    settlement_values={d:row['value'] for d,row in spxw_settlements.items()}
    return {'vendor_spy_close_vs_raw_spy_close':compare_date_values(vendor_spy,raw_close),
        'vendor_spxw_close_vs_official_spxw_pm_settlement':compare_date_values(vendor_spxw,settlement_values),
        'official_spx_close_vs_official_spxw_pm_settlement':compare_date_values(official_spx,settlement_values)}


def _finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def select_official(quotes: Iterable[Quote], spy_closes: Mapping[date, float],
                    spx_closes: Mapping[date, float], exclusions: dict | None = None):
    """Choose the eligible nearest-ATM SPY and closest-moneyness SPXW pair."""
    counts = exclusions if exclusions is not None else {}
    valid = []
    seen, conflicts = {}, set()
    for q in quotes:
        reason = validate_quote(q)
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
            continue
        key = (q.quote_date, q.contract)
        if key in seen:
            if seen[key] != q:
                conflicts.add(key)
                counts["duplicate_conflict"] = counts.get("duplicate_conflict", 0) + 1
            else:
                counts["duplicate"] = counts.get("duplicate", 0) + 1
        else:
            seen[key] = q
    for k, q in seen.items():
        if k not in conflicts:
            valid.append(q)
    grouped = {}
    for q in valid:
        grouped.setdefault((q.quote_date, q.expiration), []).append(q)
    selected = []
    for (entry, expiry), group in sorted(grouped.items()):
        spy_ref, spx_ref = spy_closes.get(entry), spx_closes.get(entry)
        if not (_finite(spy_ref) and float(spy_ref) > 0 and _finite(spx_ref) and float(spx_ref) > 0):
            counts["missing_official_entry_reference"] = counts.get("missing_official_entry_reference", 0) + 1
            continue
        spy = [q for q in group if q.underlying == "SPY" and (expiry-entry).days == 1
               and abs(q.strike/float(spy_ref)-1) <= 0.02+1e-12]
        idx = [q for q in group if q.underlying == "SPXW" and (expiry-entry).days == 1]
        if spy and idx:
            s=min(spy,key=lambda q:(abs(q.strike/float(spy_ref)-1),q.strike,q.contract))
            candidates=[]
            for i in idx:
                mismatch=abs((i.strike/float(spx_ref))/(s.strike/float(spy_ref))-1)
                if mismatch<=0.001+1e-12:candidates.append((mismatch,i.strike,i.contract,i))
            if candidates:
                _,_,_,i=min(candidates,key=lambda x:x[:3])
                selected.append((s,i,float(spx_ref)/float(spy_ref)))
            else:counts['official_moneyness_mismatch']=counts.get('official_moneyness_mismatch',0)+1
        else:
            counts["no_official_eligible_pair"] = counts.get("no_official_eligible_pair", 0) + 1
    return selected


def fill_credits(spy: Quote, idx: Quote) -> dict[str, float]:
    mid = 1000*(spy.bid+spy.ask)/2-100*(idx.bid+idx.ask)/2
    cross = 1000*spy.bid-100*idx.ask
    return {"midpoint":mid,"halfway":(mid+cross)/2,"full_cross":cross,
            "reverse_full_cross_control":100*idx.bid-1000*spy.ask,"zero_control":0.0}

def fill_cash_terms(spy: Quote, idx: Quote, fill: str) -> dict[str, float]:
    """Entry leg cash receipts/payments for the three declared execution cases."""
    if fill not in {'midpoint','halfway','full_cross'}: raise ValueError('unknown execution fill')
    spy_mid=(spy.bid+spy.ask)/2; idx_mid=(idx.bid+idx.ask)/2
    spy_px={'midpoint':spy_mid,'halfway':(spy_mid+spy.bid)/2,'full_cross':spy.bid}[fill]
    idx_px={'midpoint':idx_mid,'halfway':(idx_mid+idx.ask)/2,'full_cross':idx.ask}[fill]
    return {'spy_entry_cash':1000*spy_px,'spxw_entry_cash':-100*idx_px,
            'spy_entry_shares':0,'spxw_entry_shares':0}


def size_eligible(spy_size, idx_size):
    return (_finite(spy_size) and _finite(idx_size) and float(spy_size) >= 10 and float(idx_size) >= 1)


def expiry_ledger(*, spy: Quote, idx: Quote, credit: float, expiry_close: float,
                  spxw_settlement: float, next_open: float | None,
                  expiry_date: date, entry_date: date, cover_date: date | None = None,
                  dividends: Iterable[tuple[date, float]] = (), tolerance: float = 1e-10) -> dict:
    """Return separate intrinsic, assignment-mark and next-open cash ledgers.

    The $0.01 assignment threshold can leave at most $10 cash versus direct
    intrinsic. ``tolerance`` only absorbs binary floating point at that boundary.
    """
    if not all(_finite(x) for x in (credit, expiry_close, spxw_settlement)) or expiry_close <= 0 or spxw_settlement <= 0:
        raise ValueError("credit and references must be finite; references must be positive")
    if not isinstance(expiry_date,date) or not isinstance(entry_date,date) or entry_date >= expiry_date:
        raise ValueError("entry and expiry dates are invalid")
    if next_open is not None and (not _finite(next_open) or next_open <= 0):
        raise ValueError("next_open must be finite and positive")
    if cover_date is not None and (not isinstance(cover_date,date) or cover_date <= expiry_date):
        raise ValueError("cover_date must follow expiry")
    if next_open is not None and cover_date is None:
        raise ValueError("a next_open price requires its cover date")
    dividend_rows = list(dividends)
    for d, amount in dividend_rows:
        if not isinstance(d,date) or not _finite(amount) or amount < 0:
            raise ValueError("dividend dates and amounts must be valid and nonnegative")
    spy_intrinsic = max(float(expiry_close)-spy.strike,0)
    assigned = spy_intrinsic+tolerance >= .01
    spx_intrinsic = max(float(spxw_settlement)-idx.strike,0)
    spy_direct_cash, idx_direct_cash = -1000*spy_intrinsic, 100*spx_intrinsic
    direct = float(credit)+spy_direct_cash+idx_direct_cash
    spy_expiry_cash = 1000*spy.strike if assigned else 0.0
    spy_shares = -1000 if assigned else 0
    close_cover_cash = -1000*float(expiry_close) if assigned else 0.0
    conditional = float(credit)+idx_direct_cash+spy_expiry_cash+close_cover_cash
    residual = conditional-direct
    if abs(residual) >= 10.0 + 1e-9:
        raise AssertionError("threshold assignment mark exceeds $10 cash equivalent")
    spy_open_cash = -1000*next_open if assigned and next_open is not None else 0.0
    next_pnl = None if assigned and next_open is None else float(credit)+idx_direct_cash+spy_expiry_cash+spy_open_cash
    carry_divs = [(d,float(x)) for d,x in dividend_rows if assigned and cover_date is not None and expiry_date < d <= cover_date]
    entry_divs = [(d,float(x)) for d,x in dividend_rows if entry_date < d <= expiry_date]
    carry_amount = 1000*sum(x for _,x in carry_divs)
    div_pnl = None if next_pnl is None else next_pnl-carry_amount
    return {"credit":float(credit),"assigned":assigned,"spy_intrinsic":spy_intrinsic,
        "spy_leg_expiry_cash":spy_expiry_cash,"spy_leg_expiry_shares":spy_shares,
        "spy_leg_close_mark_cash":close_cover_cash,"spy_leg_next_open_cash":None if assigned and next_open is None else spy_open_cash,
        "spy_leg_next_open_shares":1000 if assigned and next_open is not None else 0,
        "spxw_leg_terminal_cash":idx_direct_cash,"spxw_leg_terminal_shares":0,
        "direct_intrinsic_pnl":direct,"conditional_close_mark_pnl":conditional,
        "threshold_residual_cash":residual,"next_open_pnl":next_pnl,
        "dividend_carry_pnl":div_pnl,"dividend_carry_amount":carry_amount,
        "dividend_carry_dates":[d.isoformat() for d,_ in carry_divs],
        "entry_exposure_dividend_dates":[d.isoformat() for d,_ in entry_divs],
        "entry_to_expiry_dividend_exposure":bool(entry_divs),
        "complete_cover":(not assigned or next_open is not None)}


def cost_adjusted(pnl: float, credit: float, assigned: bool, days_entry_to_exit: int,
                  days_expiry_to_cover: int, expiry_spy_close: float, *, stress=False) -> float:
    if not all(_finite(x) for x in (pnl,credit,expiry_spy_close)) or expiry_spy_close <= 0:
        raise ValueError("cost inputs must be finite and expiry close positive")
    if any(not isinstance(d,int) or isinstance(d,bool) or d < 0 for d in (days_entry_to_exit,days_expiry_to_cover)):
        raise ValueError("ACT/365 day counts must be nonnegative integers")
    if not assigned and days_expiry_to_cover != 0:
        raise ValueError("unassigned positions have no share-cover duration")
    option, stock, borrow, funding = (1.50,.01,.10,.10) if stress else (.65,.005,.03,.05)
    return (pnl-11*option-(1000*stock if assigned else 0)
            -(1000*expiry_spy_close*borrow*days_expiry_to_cover/365 if assigned else 0)
            -max(-credit,0)*funding*days_entry_to_exit/365)
