"""Frozen overnight stock-hedge accounting and guarded evaluation primitives.

This module contains no network access. The CLI never evaluates real inputs in
an uncommitted tree. Synthetic tests call the pure row accounting functions.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import math
import random
import statistics
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

PROTOCOL_PATH = Path("planning/overnight-hedge-20261030/candidate.md")
INPUT_MANIFEST_PATH = Path("planning/overnight-hedge-20261030/input-manifest.json")
PROTOCOL_SHA256 = "30eae811523310cb174fb0c8b244337031b00f0b16f479d954a495d531040731"
INPUT_MANIFEST_SHA256 = "576d58194e467bfb2b3ab7ae7ea49cede871a21f276330a6fd1ab447f82484e5"
SELECTION_SHA256 = "8156d9030ca082af279f2fd3c99cfb445fa21237a09b1782abb0911b7d4ac8f7"
SELECTION_PATH = Path("planning/overnight-hedge-20261030/prepared-v5/normalized-selection.json")
PERIOD_COUNTS = {"2019": 9, "2022": 63, "2024": 195, "2025": 127}
FILLS = ("midpoint", "halfway", "full_cross")
ARMS = ("unhedged_q0", "fixed500longshares", "fixed1000longshares", "open_itm_q1000", "assignment_oracle_q1000A")
TOL = 1e-10
MODULE_PATH_AT_LOAD = Path(__file__).resolve()
MODULE_SHA256_AT_LOAD = hashlib.sha256(MODULE_PATH_AT_LOAD.read_bytes()).hexdigest()


def q_for_arm(arm: str, assigned: bool, spy_open: float, spy_strike: float) -> int:
    if arm == "unhedged_q0":
        return 0
    if arm == "fixed500longshares":
        return 500
    if arm == "fixed1000longshares":
        return 1000
    if arm == "open_itm_q1000":
        return 1000 if spy_open >= spy_strike + 0.01 - TOL else 0
    if arm == "assignment_oracle_q1000A":
        return 1000 if assigned else 0
    raise ValueError(f"unknown hedge arm: {arm}")


def read_wrds_references(stock_csv: bytes, distribution_csv: bytes) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    """Parse accepted SPY raw OHLC and supported unconditional cash dividends."""
    stock_reader = csv.DictReader(io.StringIO(stock_csv.decode("utf-8-sig", errors="strict")))
    required_stock = {"secid", "date", "ticker", "index_flag", "open", "close", "cfadj"}
    if not stock_reader.fieldnames or not required_stock.issubset(stock_reader.fieldnames):
        raise ValueError("WRDS stock prices lack required source fields")
    prices: dict[str, dict[str, float]] = {}
    identities: dict[str, tuple[str, str]] = {}
    seen_price_keys: set[tuple[str, str]] = set()
    for record in stock_reader:
        sid = record["secid"].strip()
        ticker = {"109820": "SPY", "108105": "SPX"}.get(sid)
        expected_flag = {"SPY": "0", "SPX": "1"}.get(ticker)
        if ticker is None or record["ticker"].strip() != ticker or record["index_flag"].strip() != expected_flag:
            raise ValueError("WRDS stock identity/flags conflict with frozen IDs")
        identity = (ticker, record["index_flag"].strip())
        if sid in identities and identities[sid] != identity:
            raise ValueError("WRDS stock identity changed within security ID")
        identities[sid] = identity
        day = date.fromisoformat(record["date"].strip()).isoformat()
        values = {key: float(record[key]) for key in ("open", "close", "cfadj")}
        if not all(math.isfinite(value) for value in values.values()) or values["open"] <= 0 or values["close"] <= 0 or values["cfadj"] <= 0:
            raise ValueError("invalid WRDS raw OHLC/cfadj")
        key = (sid, day)
        if key in seen_price_keys:
            raise ValueError(f"duplicate WRDS stock price key {sid}:{day}")
        seen_price_keys.add(key)
        if sid == "109820":
            if values["cfadj"] != 1.0:
                raise ValueError(f"non-unit SPY cfadj on {day}")
            prices[day] = {"open": values["open"], "close": values["close"]}

    div_reader = csv.DictReader(io.StringIO(distribution_csv.decode("utf-8-sig", errors="strict")))
    required_div = {"secid", "record_date", "seq_num", "ex_date", "amount", "adj_factor", "distr_type", "frequency", "currency", "approx_flag", "cancel_flag", "liquid_flag", "ticker", "index_flag"}
    if not div_reader.fieldnames or not required_div.issubset(div_reader.fieldnames):
        raise ValueError("WRDS distributions lack required source fields")
    seen: set[tuple[str, str, str]] = set()
    dividends: list[dict[str, Any]] = []
    for record in div_reader:
        if (record["secid"].strip(), record["ticker"].strip(), record["index_flag"].strip()) != ("109820", "SPY", "0"):
            raise ValueError("distribution source has unexpected SPY identity or flags")
        record_date = date.fromisoformat(record["record_date"].strip()).isoformat()
        ex_date = date.fromisoformat(record["ex_date"].strip()).isoformat()
        key = (record["secid"].strip(), record_date, record["seq_num"].strip())
        if key in seen:
            raise ValueError("duplicate WRDS distribution identity key")
        seen.add(key)
        amount = float(record["amount"])
        adj_factor = float(record["adj_factor"])
        if not math.isfinite(amount) or not math.isfinite(adj_factor):
            raise ValueError("nonfinite WRDS distribution amount/factor")
        if (record["distr_type"].strip() == "1" and record["frequency"].strip() in {"1", "2", "3", "4", "5"}
                and amount > 0 and record["currency"].strip() == "USD"
                and record["approx_flag"].strip() == "0" and record["cancel_flag"].strip() == "0"
                and record["liquid_flag"].strip() == "0" and adj_factor == 1.0):
            dividends.append({"ex_date": ex_date, "amount": amount})
    dividends.sort(key=lambda event: event["ex_date"])
    return prices, dividends


def _dividends_for_interval(events: list[dict[str, Any]], expiry: str, cover: str) -> tuple[float, list[dict[str, Any]]]:
    included = [event for event in events if expiry < event["ex_date"] <= cover]
    return math.fsum(float(event["amount"]) for event in included), included


def _build_normalized_row(period: str, entry: str, expiry: str, cover: str,
                          fill: str, source: dict[str, Any], prices: dict[str, dict[str, float]],
                          events: list[dict[str, Any]], modern: bool) -> dict[str, Any]:
    for d in (entry, expiry, cover):
        date.fromisoformat(d)
    if not (entry < expiry < cover):
        raise ValueError(f"invalid date order {entry}/{expiry}/{cover}")
    if expiry not in prices or cover not in prices:
        raise ValueError(f"missing required stock date {expiry if expiry not in prices else cover}")
    if modern:
        assigned = bool(source["assigned"])
        credit = float(source["credit"])
        terminal_cash = float(source["spxw_leg_terminal_cash"])
        old_gross = float(source["dividend_carry_pnl"])
        old_dividend = float(source["dividend_carry_pnl"]) - float(source["next_open_pnl"])
        old_base = float(source["base_cost_pnl"])
        old_stress = float(source["stress_cost_pnl"])
    else:
        assigned = bool(source["assigned"])
        credit = float(source["credit"])
        terminal_cash = float(source["spxw_leg_terminal_cash"])
        old_gross = float(source["dividend_carry_pnl"])
        old_dividend = float(source["dividend_carry_pnl"]) - float(source["next_open_pnl"])
        old_base = float(source["base_cost_pnl"])
        old_stress = float(source["stress_cost_pnl"])
    spy_open = prices[expiry]["open"]
    spy_close = prices[expiry]["close"]
    cover_open = prices[cover]["open"]
    dividend_amount, dividend_events = _dividends_for_interval(events, expiry, cover)
    if modern:
        spy_strike = float(source["_spy_strike"])
        spy_contract = source["_spy_contract"]
        spxw_contract = source["_spxw_contract"]
        spxw_strike = float(source["_spxw_strike"])
        old_controls = {
            "conditional_close_mark_pnl": source["conditional_close_mark_pnl"],
            "direct_intrinsic_pnl": source["direct_intrinsic_pnl"],
            "threshold_residual_cash": source["threshold_residual_cash"],
            "pair_controls": source["_pair_controls"],
        }
    else:
        spy_strike = float(source["spy_strike"])
        spy_contract = source["spy_contract"]
        spxw_contract = source["spxw_contract"]
        spxw_strike = float(source["spxw_strike"])
        old_controls = {"conditional_close_mark_pnl": source["conditional_close_mark_pnl"],
                        "direct_intrinsic_pnl": source["direct_intrinsic_pnl"],
                        "threshold_residual_cash": source["threshold_residual_cash"],
                        "reverse_terminal_intrinsic_control_pnl": source["reverse_terminal_intrinsic_control_pnl"]}
    return {
        "period": period, "entry": entry, "expiry": expiry, "cover": cover, "fill": fill,
        "spy_contract": spy_contract, "spy_strike": spy_strike,
        "spxw_contract": spxw_contract, "spxw_strike": spxw_strike,
        "credit": credit, "spxw_terminal_cash": terminal_cash, "assigned": assigned,
        "spy_open": spy_open, "spy_close": spy_close, "cover_open": cover_open,
        "dividend_amount": dividend_amount, "dividend_events": dividend_events,
        "days_entry_expiry": (date.fromisoformat(expiry) - date.fromisoformat(entry)).days,
        "days_entry_cover": (date.fromisoformat(cover) - date.fromisoformat(entry)).days,
        "days_expiry_cover": (date.fromisoformat(cover) - date.fromisoformat(expiry)).days,
        "old_gross_pnl": old_gross, "old_dividend_pnl": old_dividend,
        "old_base_cost_pnl": old_base, "old_stress_cost_pnl": old_stress,
        "old_controls": old_controls,
    }


def normalize_stockrefs(rows: list[dict[str, Any]], prices: dict[str, dict[str, float]],
                        events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for source in rows:
        if source.get("arm") != "wrds_all":
            continue
        normalized.append(_build_normalized_row(str(source["period"]), source["entry"], source["expiry"],
                                                source["cover"], source["fill"], source, prices, events, False))
    return validate_normalized(normalized)


def normalize_optionmetrics(period: str, outcomes: list[dict[str, Any]],
                            prices: dict[str, dict[str, float]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for pair in outcomes:
        spy_contract = pair["spy_contract"]
        spxw_contract = pair["spxw_contract"]
        for fill_row in pair["fill_rows"]:
            source = {**fill_row, "_spy_strike": pair["spy_strike"],
                      "_spy_contract": spy_contract, "_spxw_contract": spxw_contract,
                      "_spxw_strike": pair["spxw_strike"], "_pair_controls": pair["controls"]}
            normalized.append(_build_normalized_row(period, pair["entry"], pair["expiry"], pair["cover"],
                                                    fill_row["fill"], source, prices, events, True))
    return validate_normalized(normalized)


def validate_normalized(rows: list[dict[str, Any]], *, require_all_periods: bool = False) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    by_period: dict[str, set[tuple[str, str, str]]] = {}
    for row in rows:
        key = (row["period"], row["entry"], row["expiry"], row["fill"])
        if key in seen:
            raise ValueError(f"duplicate normalized row identity {key}")
        seen.add(key)
        pair = (row["entry"], row["expiry"], row["cover"])
        by_period.setdefault(row["period"], set()).add(pair)
        if row["fill"] not in FILLS:
            raise ValueError(f"unexpected fill name {row['fill']}")
    periods = PERIOD_COUNTS if require_all_periods else {period: PERIOD_COUNTS[period] for period in by_period}
    for period, expected in periods.items():
        pairs = by_period.get(period, set())
        expected_rows = expected * len(FILLS)
        actual_rows = sum(1 for row in rows if row["period"] == period)
        if len(pairs) != expected or actual_rows != expected_rows:
            raise ValueError(f"fixed population mismatch for {period}: pairs={len(pairs)}, rows={actual_rows}")
        for identity in pairs:
            present = {row["fill"] for row in rows if (row["entry"], row["expiry"], row["cover"]) == identity and row["period"] == period}
            if present != set(FILLS):
                raise ValueError(f"incomplete fill set for {period}/{identity}")
    return sorted(rows, key=lambda row: (row["period"], row["entry"], row["fill"]))


def hedge_row(row: dict[str, Any], arm: str, *, funding: str = "gross_prefunding",
              slippage_bp: float = 0.0, stress: bool = False,
              include_dividends: bool = True) -> dict[str, Any]:
    """Rebuild one row's gross and net cash flow from frozen inputs."""
    required = ("credit", "spxw_terminal_cash", "assigned", "spy_strike", "spy_open",
                "spy_close", "cover_open", "dividend_amount", "days_entry_expiry",
                "days_entry_cover", "days_expiry_cover")
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"missing hedge fields: {missing}")
    numbers = ("credit", "spxw_terminal_cash", "spy_strike", "spy_open", "spy_close",
               "cover_open", "dividend_amount", "days_entry_expiry", "days_entry_cover",
               "days_expiry_cover")
    if any(not math.isfinite(float(row[k])) for k in numbers):
        raise ValueError("nonfinite hedge input")
    if any(float(row[k]) <= 0 for k in ("spy_open", "spy_close", "cover_open", "spy_strike")):
        raise ValueError("stock prices and strike must be positive")
    if row["days_expiry_cover"] < 0:
        raise ValueError("cover date precedes expiry")
    assigned = bool(row["assigned"])
    q = q_for_arm(arm, assigned, float(row["spy_open"]), float(row["spy_strike"]))
    residual = q - 1000 * int(assigned)
    dividend = float(row["dividend_amount"])
    gross_without_dividend = (float(row["credit"]) + float(row["spxw_terminal_cash"])
                              + 1000 * int(assigned) * float(row["spy_strike"])
                              - q * float(row["spy_close"])
                              + residual * float(row["cover_open"]))
    gross = gross_without_dividend + residual * dividend

    option_fee_rate = 1.50 if stress else 0.65
    stock_fee_rate = 0.01 if stress else 0.005
    borrow_rate = 0.10 if stress else 0.03
    funding_rate = 0.10 if stress else 0.05
    days_exit = row["days_entry_cover"] if assigned else row["days_entry_expiry"]
    premium_debit_funding = max(-float(row["credit"]), 0.0) * funding_rate * days_exit / 365
    option_fees = 11 * option_fee_rate
    traded_shares = q + abs(residual)
    stock_fees = traded_shares * stock_fee_rate
    hedgedays = row["days_expiry_cover"]
    residual_short_borrow = max(-residual, 0) * float(row["spy_close"]) * borrow_rate * hedgedays / 365
    if funding == "gross_prefunding":
        hedge_funding = q * float(row["spy_close"]) * funding_rate * hedgedays / 365
    elif funding == "assignment_cash_net":
        hedge_funding = max(q * float(row["spy_close"]) - 1000 * int(assigned) * float(row["spy_strike"]), 0.0) * funding_rate * hedgedays / 365
    else:
        raise ValueError(f"unknown funding assumption: {funding}")
    traded_notional = q * float(row["spy_close"]) + abs(residual) * float(row["cover_open"])
    slippage = traded_notional * float(slippage_bp) / 10000
    costs = option_fees + stock_fees + residual_short_borrow + premium_debit_funding + hedge_funding + slippage
    return {
        "arm": arm, "q": q, "assigned": assigned, "residual_shares": residual,
        "residual_bounds": [q - 1000, q],
        "possible_residual_shares": [q - 100 * k for k in range(11)],
        "gross_pnl": gross if include_dividends else gross_without_dividend,
        "gross_pnl_without_dividends": gross_without_dividend,
        "gross_pnl_with_dividends": gross,
        "overnight_price_contribution": residual * (float(row["cover_open"]) - float(row["spy_close"])),
        "dividend_cash": residual * (dividend if include_dividends else 0.0),
        "dividend_cash_with_dividends": residual * dividend,
        "stock_notional_close": q * float(row["spy_close"]),
        "stock_notional_cover": abs(residual) * float(row["cover_open"]),
        "costs": {"option_fees": option_fees, "stock_fees": stock_fees,
                  "residual_short_borrow": residual_short_borrow,
                  "premium_debit_funding": premium_debit_funding,
                  "hedge_funding": hedge_funding, "stock_slippage": slippage},
        "net_pnl": (gross if include_dividends else gross_without_dividend) - costs,
        "net_pnl_without_dividends": gross_without_dividend - costs,
        "net_pnl_with_dividends": gross - costs,
        "funding": funding, "slippage_bp": float(slippage_bp), "stress": stress,
        "dividends_included": include_dividends,
    }


def verify_q0_parity(row: dict[str, Any], result: dict[str, Any], *, tol: float = 1e-8) -> None:
    """Compare rebuilt q0 accounting to retained legacy row-level fields."""
    checks = {
        "gross_pnl": row["old_gross_pnl"],
        "dividend_cash": row["old_dividend_pnl"],
        "net_pnl": row["old_base_cost_pnl"],
    }
    for key, expected in checks.items():
        if abs(float(result[key]) - float(expected)) > tol:
            raise AssertionError(f"q0 parity failed for {key}: {result[key]} != {expected}")


def verify_row_identities(row: dict[str, Any], q0: dict[str, Any], q0_stress: dict[str, Any],
                          oracle: dict[str, Any], *, tol: float = 1e-8) -> None:
    verify_q0_parity(row, q0, tol=tol)
    if abs(q0_stress["gross_pnl"] - row["old_gross_pnl"]) > tol:
        raise AssertionError("q0 stress gross identity failed")
    if abs(q0_stress["net_pnl"] - row["old_stress_cost_pnl"]) > tol:
        raise AssertionError("q0 stress cost parity failed")
    conditional = float(row["old_controls"]["conditional_close_mark_pnl"])
    if abs(oracle["gross_pnl"] - conditional) > tol:
        raise AssertionError("assignment-oracle gross identity failed")
    if abs(q0["gross_pnl"] - row["old_gross_pnl"]) > tol:
        raise AssertionError("q0 gross identity failed")


def type7(values: list[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("type-7 quantile requires values and probability in [0,1]")
    ordered = sorted(float(v) for v in values)
    h = (len(ordered) - 1) * probability
    lo = math.floor(h)
    hi = math.ceil(h)
    return ordered[lo] + (h - lo) * (ordered[hi] - ordered[lo])


def bootstrap_indices(cluster_labels: list[str], *, draws: int = 10000,
                      seed: int = 20261030) -> tuple[list[list[int]], str]:
    """Return shared cluster-bootstrap row indices and a stable digest."""
    if not cluster_labels or draws < 1:
        raise ValueError("bootstrap requires rows and positive draw count")
    by_cluster: dict[str, list[int]] = {}
    for i, label in enumerate(cluster_labels):
        by_cluster.setdefault(str(label), []).append(i)
    names = sorted(by_cluster)
    rng = random.Random(seed)
    all_draws: list[list[int]] = []
    for _ in range(draws):
        sampled = [names[rng.randrange(len(names))] for _ in names]
        all_draws.append([i for name in sampled for i in by_cluster[name]])
    payload = json.dumps(all_draws, separators=(",", ":")).encode()
    return all_draws, hashlib.sha256(payload).hexdigest()


def paired_mean_interval(values: list[float], indices: list[list[int]]) -> dict[str, Any]:
    means = [statistics.fmean(values[i] for i in draw) for draw in indices if draw]
    return {"mean": statistics.fmean(values), "ci95_type7": [type7(means, .025), type7(means, .975)],
            "draw_denominators": sorted({len(draw) for draw in indices})}


def max_peak_to_trough_drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        cumulative += float(value)
        peak = max(peak, cumulative)
        maximum = max(maximum, peak - cumulative)
    return maximum


def bootstrap_cluster_intervals(labels: list[str], columns: dict[str, list[float]], *,
                                draws: int = 10000, seed: int = 20261030) -> tuple[dict[str, dict[str, Any]], str]:
    """Compute many shared cluster-bootstrap intervals with one vectorized draw set."""
    if not labels or not columns or any(len(values) != len(labels) for values in columns.values()):
        raise ValueError("bootstrap columns must match nonempty cluster labels")
    by_cluster: dict[str, list[int]] = {}
    for index, label in enumerate(labels):
        by_cluster.setdefault(str(label), []).append(index)
    names = sorted(by_cluster)
    weights = np.zeros((draws, len(names)), dtype=np.uint16)
    rng = random.Random(seed)
    sample_ids: list[list[int]] = []
    for draw_index in range(draws):
        sampled = [rng.randrange(len(names)) for _ in names]
        sample_ids.append(sampled)
        for index in sampled:
            weights[draw_index, index] += 1
    digest = hashlib.sha256(json.dumps(sample_ids, separators=(",", ":")).encode()).hexdigest()
    sizes = np.asarray([len(by_cluster[name]) for name in names], dtype=np.float64)
    denominators = weights @ sizes
    matrix = np.asarray([
        [math.fsum(float(values[i]) for i in by_cluster[name]) for name in names]
        for values in columns.values()
    ], dtype=np.float64).T
    draw_means = (weights @ matrix) / denominators[:, None]
    results = {}
    for column_index, (name, values) in enumerate(columns.items()):
        samples = draw_means[:, column_index]
        results[name] = {
            "mean": statistics.fmean(float(value) for value in values),
            "ci95_type7": [float(np.quantile(samples, .025, method="linear")),
                           float(np.quantile(samples, .975, method="linear"))],
            "draw_denominators": sorted({int(value) for value in denominators}),
        }
    return results, digest


def verify_frozen_sources(repo: Path) -> dict[str, dict[str, Any]]:
    protocol_bytes = (repo / PROTOCOL_PATH).read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != PROTOCOL_SHA256:
        raise RuntimeError("frozen protocol changed")
    manifest_path = repo / INPUT_MANIFEST_PATH
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != INPUT_MANIFEST_SHA256:
        raise RuntimeError("frozen input manifest changed")
    manifest = json.loads(manifest_bytes)
    verified = {}
    for item in manifest["source_files"]:
        path = Path(item["path"])
        data = path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        if len(data) != item["bytes"] or actual_hash != item["sha256"]:
            raise RuntimeError(f"frozen source changed: {item['name']}")
        verified[item["name"]] = {**item, "data": data}
    return verified


def _json_source(sources: dict[str, dict[str, Any]], name: str) -> Any:
    return json.loads(sources[name]["data"])


def prepare_normalized_selection(repo: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sources = verify_frozen_sources(repo)
    prices, events = read_wrds_references(sources["wrds_stock_prices"]["data"],
                                          sources["wrds_distributions"]["data"])
    stock_arm_rows = _json_source(sources, "stockrefs_arm_rows")["wrds_all"]
    stock_rows = normalize_stockrefs(stock_arm_rows, prices, events)
    modern_rows = []
    for period, name in (("2024", "2024_outcomes"), ("2025", "2025_outcomes")):
        modern_rows.extend(normalize_optionmetrics(period, _json_source(sources, name), prices, events))
    rows = validate_normalized(stock_rows + modern_rows, require_all_periods=True)
    for row in rows:
        if row["period"] in {"2019", "2022"}:
            manifest_name, output_name = "stockrefs_manifest", "stockrefs_arm_rows"
        else:
            prefix = row["period"]
            manifest_name, output_name = f"{prefix}_manifest", f"{prefix}_outcomes"
        row["source_binding"] = {
            "input_manifest_sha256": INPUT_MANIFEST_SHA256,
            "source_manifest_sha256": sources[manifest_name]["sha256"],
            "source_rows_sha256": sources[output_name]["sha256"],
        }
    summary_checks = verify_retained_summary_means(sources, rows)
    audit = {
        "status": "PREPARED_INPUTS_ONLY_NOT_RUN",
        "row_count": len(rows),
        "pair_counts": dict(PERIOD_COUNTS),
        "fill_counts": {period: {fill: PERIOD_COUNTS[period] for fill in FILLS} for period in PERIOD_COUNTS},
        "stock_reference_dates": {"spy_date_count": len(prices), "unconditional_supported_dividend_count": len(events)},
        "row_level_outcomes_calculated": False,
        "retained_summary_checks": summary_checks,
        "source_bindings": {name: {key: value for key, value in item.items() if key != "data"}
                            for name, item in sorted(sources.items())},
    }
    return rows, audit


def verify_retained_summary_means(sources: dict[str, dict[str, Any]],
                                  rows: list[dict[str, Any]], *, tol: float = 1e-7) -> list[dict[str, Any]]:
    """Check fixed row counts and existing q0 control means by period and fill."""
    stock_summaries = _json_source(sources, "stockrefs_summaries")["wrds_all"]
    outputs = []
    for period in PERIOD_COUNTS:
        if period in ("2019", "2022"):
            summary_root = stock_summaries[period]
        else:
            name = "2024_summary" if period == "2024" else "2025_summary"
            summary_root = _json_source(sources, name)["cohorts"]["all"]["fills"]
        for fill in FILLS:
            group_rows = [row for row in rows if row["period"] == period and row["fill"] == fill]
            expected_n = PERIOD_COUNTS[period]
            if len(group_rows) != expected_n:
                raise ValueError(f"retained summary group missing rows: {period}/{fill}")
            source_metrics = summary_root[fill]
            checks = (("old_gross_pnl", "dividend_carry_pnl"),
                      ("old_base_cost_pnl", "base_cost_pnl"),
                      ("old_stress_cost_pnl", "stress_cost_pnl"))
            for row_field, metric in checks:
                source_metric = source_metrics[metric]
                source_count = int(source_metric["count"])
                source_mean = float(source_metric["mean"])
                actual_mean = statistics.fmean(float(row[row_field]) for row in group_rows)
                if source_count != expected_n or abs(source_mean - actual_mean) > tol:
                    raise ValueError(f"retained q0 summary mismatch for {period}/{fill}/{metric}")
                outputs.append({"period": period, "fill": fill, "metric": metric,
                                "count": source_count, "retained_mean": source_mean,
                                "rebuilt_mean": actual_mean,
                                "absolute_difference": abs(source_mean - actual_mean),
                                "status": "MATCH"})
    return outputs


def _validate_fresh_output(repo: Path, output: Path, command: str) -> Path:
    output = (repo / output).resolve() if not output.is_absolute() else output.resolve()
    planning = (repo / "planning/overnight-hedge-20261030").resolve()
    if planning not in output.parents or output.exists():
        raise RuntimeError(f"{command} output must be a fresh path inside the ignored study planning directory")
    check = subprocess.run(["git", "check-ignore", "-q", str(output)], cwd=repo)
    if check.returncode != 0:
        raise RuntimeError(f"{command} output path is not ignored by Git")
    return output


def _write_preparation(repo: Path, output: Path) -> None:
    output = _validate_fresh_output(repo, output, "prepare")
    rows, audit = prepare_normalized_selection(repo)
    # Repeat the full frozen input check after normalization, before writing anything.
    verify_frozen_sources(repo)
    selection_bytes = (json.dumps(rows, separators=(",", ":"), sort_keys=True) + "\n").encode()
    selection_hash = hashlib.sha256(selection_bytes).hexdigest()
    output.mkdir(parents=True)
    (output / "normalized-selection.json").write_bytes(selection_bytes)
    (output / "source-audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    verify_frozen_sources(repo)
    receipt = {"status": "PREPARED_INPUTS_ONLY_NOT_RUN", "selection_sha256": selection_hash,
               "row_count": len(rows), "protocol_sha256": PROTOCOL_SHA256,
               "input_manifest_sha256": INPUT_MANIFEST_SHA256,
               "source_audit_sha256": hashlib.sha256((output / "source-audit.json").read_bytes()).hexdigest()}
    (output / "normalized-selection-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


def evaluate_normalized(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Run the frozen case grid on a prepared selection; not called by this worker."""
    rows = validate_normalized(rows, require_all_periods=True)
    ledger: list[dict[str, Any]] = []
    for row in rows:
        q0 = hedge_row(row, "unhedged_q0", funding="gross_prefunding", slippage_bp=0, stress=False)
        q0_stress = hedge_row(row, "unhedged_q0", funding="gross_prefunding", slippage_bp=0, stress=True)
        oracle = hedge_row(row, "assignment_oracle_q1000A", funding="gross_prefunding", slippage_bp=0, stress=False)
        verify_row_identities(row, q0, q0_stress, oracle)
        for arm in ARMS:
            case0 = hedge_row(row, arm, funding="gross_prefunding", slippage_bp=0, stress=False)
            expected_delta = case0["q"] * (row["cover_open"] - row["spy_close"] + row["dividend_amount"])
            q0case = hedge_row(row, "unhedged_q0", funding="gross_prefunding", slippage_bp=0, stress=False)
            if abs((case0["gross_pnl"] - q0case["gross_pnl"]) - expected_delta) > 1e-8:
                raise AssertionError("paired gross hedge-minus-q0 identity failed")
        for arm in ARMS:
            for funding in ("gross_prefunding", "assignment_cash_net"):
                for bp in (0, 1, 5):
                    for stress in (False, True):
                        case = hedge_row(row, arm, funding=funding, slippage_bp=bp,
                                         stress=stress, include_dividends=True)
                        ledger.append({"period": row["period"], "entry": row["entry"],
                                       "expiry": row["expiry"], "cover": row["cover"],
                                       "fill": row["fill"],
                                       "source_binding": row["source_binding"], **case})

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in ledger:
        key = (record["period"], record["fill"], record["arm"], record["funding"], record["slippage_bp"], record["stress"])
        grouped.setdefault(key, []).append(record)
    summaries = []
    expected_summary_groups = {
        (period, fill, arm, funding, bp, stress): PERIOD_COUNTS[period]
        for period in PERIOD_COUNTS for fill in FILLS for arm in ARMS
        for funding in ("gross_prefunding", "assignment_cash_net")
        for bp in (0, 1, 5) for stress in (False, True)
    }
    if len(ledger) != 70920:
        raise ValueError(f"expected 70920 ledger rows, got {len(ledger)}")
    if set(grouped) != set(expected_summary_groups) or len(expected_summary_groups) != 720:
        raise ValueError("expected summary group grid is incomplete")
    for key, records in sorted(grouped.items()):
        if not records or len(records) != expected_summary_groups[key]:
            raise ValueError(f"summary group count mismatch for {key}: {len(records)}")
        vals = [float(record["net_pnl"]) for record in sorted(records, key=lambda r: r["entry"])]
        max_drawdown = max_peak_to_trough_drawdown(vals)
        summaries.append({"period": key[0], "fill": key[1], "arm": key[2], "funding": key[3],
                          "slippage_bp": key[4], "stress": key[5], "count": len(vals),
                          "mean": statistics.fmean(vals), "median": statistics.median(vals),
                          "stddev_sample": statistics.stdev(vals) if len(vals) > 1 else None,
                          "min": min(vals), "max": max(vals),
                          "win_rate": sum(v > 0 for v in vals) / len(vals),
                          "max_peak_to_trough_cash_drawdown": max_drawdown,
                          "nonzero_residual_rows": sum(record["residual_shares"] != 0 for record in records),
                          "max_close_notional": max(record["stock_notional_close"] for record in records),
                          "max_cover_notional": max(record["stock_notional_cover"] for record in records),
                          "mean_overnight_price_contribution": statistics.fmean(record["overnight_price_contribution"] for record in records),
                          "mean_dividend_cash": statistics.fmean(record["dividend_cash"] for record in records),
                          "mean_cost_components": {
                              component: statistics.fmean(float(record["costs"][component]) for record in records)
                              for component in records[0]["costs"]}})

    uncertainty = []
    expected_uncertainty_groups = {
        (period, fill, arm, funding, bp, stress): PERIOD_COUNTS[period]
        for period in ("2022", "2024", "2025") for fill in FILLS for arm in ARMS[1:]
        for funding in ("gross_prefunding", "assignment_cash_net")
        for bp in (0, 1, 5) for stress in (False, True)
    }
    for period in ("2022", "2024", "2025"):
        for fill in FILLS:
            matching = sorted((row for row in rows if row["period"] == period and row["fill"] == fill), key=lambda r: r["entry"])
            labels = [f"{d.isocalendar().year}-W{d.isocalendar().week:02d}" for d in (date.fromisoformat(row["expiry"]) for row in matching)]
            columns: dict[str, list[float]] = {}
            for funding in ("gross_prefunding", "assignment_cash_net"):
                for bp in (0, 1, 5):
                    for stress in (False, True):
                        q0_vals = [hedge_row(row, "unhedged_q0", funding=funding, slippage_bp=bp, stress=stress)["net_pnl"] for row in matching]
                        case_name = f"{funding}|{bp}|{int(stress)}"
                        columns[f"{case_name}|q0"] = q0_vals
                        for arm in ARMS[1:]:
                            arm_vals = [hedge_row(row, arm, funding=funding, slippage_bp=bp, stress=stress)["net_pnl"] for row in matching]
                            delta = [a - b for a, b in zip(arm_vals, q0_vals)]
                            columns[f"{case_name}|{arm}"] = arm_vals
                            columns[f"{case_name}|{arm}-q0"] = delta
            intervals, digest = bootstrap_cluster_intervals(labels, columns)
            cluster_labels = sorted(set(labels))
            for funding in ("gross_prefunding", "assignment_cash_net"):
                for bp in (0, 1, 5):
                    for stress in (False, True):
                        case_name = f"{funding}|{bp}|{int(stress)}"
                        for arm in ARMS[1:]:
                            uncertainty.append({"period": period, "fill": fill, "arm": arm,
                                                "funding": funding, "slippage_bp": bp, "stress": stress,
                                                "q0_absolute_mean": intervals[f"{case_name}|q0"],
                                                "arm_absolute_mean": intervals[f"{case_name}|{arm}"],
                                                "arm_minus_q0_paired_mean": intervals[f"{case_name}|{arm}-q0"],
                                                "draws": 10000, "seed": 20261030,
                                                "cluster_count": len(set(labels)), "row_count": len(labels),
                                                "ordered_cluster_labels": cluster_labels,
                                                "draw_cluster_sample_ids_sha256": digest})
    actual_uncertainty_groups = {(item["period"], item["fill"], item["arm"], item["funding"],
                                  item["slippage_bp"], item["stress"]): item["row_count"]
                                 for item in uncertainty}
    if len(ledger) != 70920 or len(summaries) != 720 or len(uncertainty) != 432:
        raise ValueError("fixed evaluation grid count mismatch")
    if actual_uncertainty_groups != expected_uncertainty_groups:
        raise ValueError("uncertainty group counts do not match fixed populations")
    return {"status": "EVALUATED", "row_count": len(rows), "case_ledger": ledger,
            "summaries": summaries, "uncertainty": uncertainty}


def _verify_selection(repo: Path, selection_path: Path = SELECTION_PATH) -> str:
    path = (repo / selection_path).resolve()
    expected_path = (repo / SELECTION_PATH).resolve()
    if path != expected_path or not path.is_file():
        raise RuntimeError("normalized selection path does not match frozen prepared-v4 path")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if SELECTION_SHA256.startswith("PENDING_") or digest != SELECTION_SHA256:
        raise RuntimeError("normalized selection hash is not pinned")
    return digest


def guarded_evaluate_preflight(repo: Path, *, protocol_sha256: str = PROTOCOL_SHA256,
                               input_manifest_sha256: str = INPUT_MANIFEST_SHA256) -> str:
    """Reject dirty/wrong HEAD and changed frozen files before real evaluation."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, check=True,
                            capture_output=True, text=True).stdout
    if status:
        raise RuntimeError("real evaluation requires a clean Git worktree")
    code_rel = Path("src/spyspx/overnight_hedge.py")
    canonical_module_path = (repo / code_rel).resolve()
    if MODULE_PATH_AT_LOAD != canonical_module_path:
        raise RuntimeError("loaded evaluator module path does not match canonical repository path")
    loaded_bytes_hash = hashlib.sha256(MODULE_PATH_AT_LOAD.read_bytes()).hexdigest()
    if loaded_bytes_hash != MODULE_SHA256_AT_LOAD:
        raise RuntimeError("loaded evaluator source bytes changed after module load")
    committed_code = subprocess.run(["git", "show", f"HEAD:{code_rel.as_posix()}"], cwd=repo,
                                    check=True, capture_output=True).stdout
    if hashlib.sha256(committed_code).hexdigest() != MODULE_SHA256_AT_LOAD:
        raise RuntimeError("loaded evaluator bytes do not match Git HEAD")
    if canonical_module_path.read_bytes() != committed_code:
        raise RuntimeError("loaded evaluator bytes do not match Git HEAD")
    if protocol_sha256.startswith("PENDING_") or input_manifest_sha256.startswith("PENDING_"):
        raise RuntimeError("frozen protocol and input hashes are not pinned")
    for path, expected in ((repo / PROTOCOL_PATH, protocol_sha256),
                           (repo / INPUT_MANIFEST_PATH, input_manifest_sha256)):
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"frozen input hash mismatch: {path.name}")
    verify_frozen_sources(repo)
    return head


def verify_head_unchanged(repo: Path, expected_head: str) -> None:
    if guarded_evaluate_preflight(repo) != expected_head:
        raise RuntimeError("Git HEAD or frozen source state changed during evaluation")


def _integrity_evidence(repo: Path, expected_head: str, selection_path: Path) -> dict[str, Any]:
    actual_head = guarded_evaluate_preflight(repo)
    if actual_head != expected_head:
        raise RuntimeError("Git HEAD changed during evaluation")
    selection_hash = _verify_selection(repo, selection_path)
    sources = verify_frozen_sources(repo)
    return {"git_sha": actual_head, "code_sha256": MODULE_SHA256_AT_LOAD,
            "protocol_sha256": hashlib.sha256((repo / PROTOCOL_PATH).read_bytes()).hexdigest(),
            "input_manifest_sha256": hashlib.sha256((repo / INPUT_MANIFEST_PATH).read_bytes()).hexdigest(),
            "selection_sha256": selection_hash,
            "source_sha256": {name: item["sha256"] for name, item in sorted(sources.items())}}


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="prepare normalized frozen input receipt only")
    prep.add_argument("--output", type=Path, required=True)
    evaluate = sub.add_parser("evaluate", help="guarded real evaluation; lead commit required")
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = Path.cwd().resolve()
    if args.command == "prepare":
        _write_preparation(repo, args.output)
        return 0
    head_before = guarded_evaluate_preflight(repo)
    output = _validate_fresh_output(repo, args.output, "evaluation")
    stage = output.with_name(f".{output.name}.staging")
    if stage.exists():
        raise RuntimeError("evaluation staging path already exists")
    selection_path = repo / SELECTION_PATH
    selection_receipt_path = selection_path.with_name("normalized-selection-receipt.json")
    if not selection_path.is_file() or not selection_receipt_path.is_file():
        raise RuntimeError("prepare must create the frozen normalized selection first")
    receipt = json.loads(selection_receipt_path.read_text())
    selection_bytes = selection_path.read_bytes()
    selection_digest = _verify_selection(repo)
    if selection_digest != receipt["selection_sha256"]:
        raise RuntimeError("normalized selection changed after prepare")
    if (receipt["protocol_sha256"], receipt["input_manifest_sha256"]) != (PROTOCOL_SHA256, INPUT_MANIFEST_SHA256):
        raise RuntimeError("normalized selection uses a different frozen protocol or inputs")
    frozen_sources = verify_frozen_sources(repo)
    normalized_rows = json.loads(selection_bytes)
    verify_retained_summary_means(frozen_sources, normalized_rows)
    started = datetime.now(timezone.utc).isoformat()
    stdout_capture, stderr_capture = io.StringIO(), io.StringIO()
    command = [sys.executable, "-m", "spyspx.overnight_hedge", "evaluate", "--output", str(args.output)]
    with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
        result = evaluate_normalized(normalized_rows)
    evidence_before_write = _integrity_evidence(repo, head_before, selection_path)
    source_bindings = verify_frozen_sources(repo)
    parity = verify_retained_summary_means(source_bindings, normalized_rows)
    if len(parity) != 36:
        raise ValueError(f"expected 36 retained summary parity checks, got {len(parity)}")
    stage.mkdir(parents=True)
    payloads = {
        "case-ledgers.json": json.dumps(result["case_ledger"], separators=(",", ":")) + "\n",
        "summaries.json": json.dumps(result["summaries"], indent=2, sort_keys=True) + "\n",
        "uncertainty.json": json.dumps(result["uncertainty"], indent=2, sort_keys=True) + "\n",
        "parity.json": json.dumps({"status": "PASSED", "row_count": result["row_count"],
                                   "row_tolerance_usd": 1e-8, "summary_tolerance_usd": 1e-7,
                                   "retained_summary_comparisons": parity,
                                   "comparison_count": len(parity)}, indent=2, sort_keys=True) + "\n",
        "coverage.json": json.dumps({"status": "COMPLETE", "row_count": result["row_count"],
                                     "pair_counts": PERIOD_COUNTS}, indent=2) + "\n",
        "source-audit.json": json.dumps({name: {k: v for k, v in value.items() if k != "data"}
                                         for name, value in source_bindings.items()}, indent=2, sort_keys=True) + "\n",
        "draw-metadata.json": json.dumps({"draws": 10000, "seed": 20261030, "quantiles": "type7",
                                         "algorithm": "Python random.Random(seed); sorted ISO-week labels; each draw samples cluster_count integer cluster IDs with replacement using randrange(cluster_count); expand each selected cluster to original input row indices in input order, preserving sampled cluster order; hash compact JSON of per-draw sampled cluster ID lists",
                                         "hash_semantics": "draw_cluster_sample_ids_sha256 hashes sampled integer cluster ID arrays, not expanded row indices",
                                         "indices_sha256_by_uncertainty_group": [
                                             {k: item[k] for k in ("period", "fill", "ordered_cluster_labels", "draw_cluster_sample_ids_sha256", "cluster_count", "row_count")}
                                             for item in result["uncertainty"]]}, indent=2, sort_keys=True) + "\n",
        "summary.json": json.dumps({"status": result["status"], "row_count": result["row_count"],
                                    "population_counts": PERIOD_COUNTS,
                                    "summary_count": len(result["summaries"]),
                                    "uncertainty_count": len(result["uncertainty"])}, indent=2) + "\n",
        "normalized-selection-receipt.json": selection_receipt_path.read_text(),
        "stdout.log": stdout_capture.getvalue(),
        "stderr.log": stderr_capture.getvalue(),
    }
    for name, contents in payloads.items():
        (stage / name).write_text(contents)
    evidence_after_write = _integrity_evidence(repo, head_before, selection_path)
    if evidence_before_write != evidence_after_write:
        raise RuntimeError("frozen code, inputs, protocol, or selection changed before manifest publication")
    output_hashes = {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in payloads}
    stage.rename(output)
    evidence_before_manifest = _integrity_evidence(repo, head_before, selection_path)
    if evidence_before_write != evidence_before_manifest:
        raise RuntimeError("frozen code, inputs, protocol, or selection changed before manifest publication")
    metadata = {"status": "EVALUATED", "command": command, "started_utc": started,
                "ended_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                "numpy_version": np.__version__,
                "model_identity": "N/A", "model_endpoint": "N/A", "clean_git_sha": head_before,
                "protocol_sha256": PROTOCOL_SHA256, "input_manifest_sha256": INPUT_MANIFEST_SHA256,
                "normalized_selection_sha256": SELECTION_SHA256,
                "integrity_evidence_before_write": evidence_before_write,
                "integrity_evidence_after_write": evidence_before_manifest,
                "inputs": {name: {k: v for k, v in item.items() if k != "data"} for name, item in source_bindings.items()},
                "output_sha256": output_hashes}
    (output / "manifest.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
