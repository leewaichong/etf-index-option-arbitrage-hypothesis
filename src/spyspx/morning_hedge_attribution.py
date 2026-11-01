"""Guarded, post-hoc attribution of the frozen morning hedge ledgers.

The command is intentionally gated by a separately frozen protocol. Pure helpers
are usable with synthetic rows; evaluating private ledgers is a distinct action.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import contextlib
import io
import hashlib
import json
import math
import platform
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_MANIFEST_SHA256 = "1c6cc79b3746f00fa2c39c7f6d73f6798a6ee40bac404f1d9466c6b3d5aa2c3f"
COSTS = ("option_fees", "stock_fees", "residual_short_borrow", "premium_debit_funding", "hedge_funding", "stock_slippage")
PERIOD_COUNTS = {"2023": 196, "2025": 127}
COST_TOL = 1e-7
ASSIGNMENT_TOL = 1e-10
SCENARIO_MAIN = "open_itm_q1000|full_cross|base|1bp|gross_prefunding"
SCENARIO_Q0 = "unhedged_q0|full_cross|base|1bp|gross_prefunding"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


MODULE_PATH_AT_LOAD = Path(__file__).resolve()
MODULE_SHA256_AT_LOAD = sha256(MODULE_PATH_AT_LOAD)


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_input_bindings(bindings: dict[str, dict[str, Any]]) -> dict[str, str]:
    hashes = {name: sha256(Path(item["path"])) for name, item in bindings.items()}
    for name, item in bindings.items():
        if hashes[name] != item["sha256"]:
            raise ValueError(f"frozen input hash mismatch: {name}")
    return hashes


def verify_code_binding(source: Path, committed_bytes: bytes,
                        expected_head: str, actual_head: str, dirty: str, *,
                        loaded_path: Path | None = None, loaded_sha256: str | None = None) -> str:
    loaded_path = MODULE_PATH_AT_LOAD if loaded_path is None else loaded_path
    loaded_sha256 = MODULE_SHA256_AT_LOAD if loaded_sha256 is None else loaded_sha256
    source_hash = sha256(source)
    blob_hash = hashlib.sha256(committed_bytes).hexdigest()
    if source.resolve() != loaded_path.resolve() or source_hash != blob_hash or source_hash != loaded_sha256:
        raise ValueError("loaded attribution code differs from committed blob")
    if expected_head != actual_head or dirty:
        raise ValueError("Git identity changed or worktree is dirty")
    return source_hash


def _git_ignored(path: Path, root: Path) -> bool:
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", str(path)], cwd=root)
    if result.returncode not in (0, 1):
        raise RuntimeError("git check-ignore failed")
    return result.returncode == 0


def validate_output_path(out: Path, *, root: Path = ROOT, check_ignored: Any = None) -> None:
    out = out.absolute()
    allowed = (root / "planning/morning-hedge-attribution-20261030").resolve()
    if out.exists() or out.is_symlink() or not out.parent.is_dir() or out.parent.resolve() != allowed:
        raise ValueError("output must be a fresh child of the ignored planning directory")
    if not (check_ignored(out) if check_ignored else _git_ignored(out, root)):
        raise ValueError("output path is not Git-ignored")


def index_unique(rows: Iterable[Any], key: Any, label: str) -> dict[Any, Any]:
    indexed: dict[Any, Any] = {}
    for row in rows:
        row_key = key(row)
        if row_key in indexed:
            raise ValueError(f"duplicate {label} key: {row_key}")
        indexed[row_key] = row
    return indexed


def primitive(row: dict[str, Any], *, expiry_close: float, next_open: float,
              dividend: float, q: int | None = None, assigned: bool | None = None) -> dict[str, float]:
    """Reconstruct additive row cash terms from source primitives."""
    a = int(bool(row["assigned"])) if assigned is None else int(assigned)
    quantity = int(row["q"] if q is None else q)
    credit = _finite(row["credit"], "credit")
    settle = _finite(row["spxw_leg_terminal_cash"], "spxw_leg_terminal_cash")
    strike = _finite(row["spy_strike"], "spy_strike")
    base = credit + settle + 1000 * a * (strike - expiry_close)
    overnight = (quantity - 1000 * a) * (next_open - expiry_close)
    div_cash = (quantity - 1000 * a) * _finite(dividend, "dividend")
    raw_costs = row["costs"]
    costs = {name: _finite(raw_costs[name], f"costs.{name}") for name in COSTS}
    total_cost = sum(costs.values())
    net = base + overnight + div_cash - total_cost
    return {"option_baseline": base, "overnight": overnight, "dividend": div_cash,
            **{f"negative_{k}": -v for k, v in costs.items()}, "cost_total": total_cost, "net": net}


def reconstruct_q(open_price: float, strike: float, *, tolerance: float = 1e-10) -> int:
    return 1000 if open_price >= strike + 0.01 - tolerance else 0


def reconstruct_assignment(expiry_close: float, strike: float, *, tolerance: float = ASSIGNMENT_TOL) -> bool:
    return expiry_close >= strike + 0.01 - tolerance


def reconstruct_costs(*, q: int, assigned: bool, credit: float, expiry_close: float,
                      cover_open: float, entry: str, expiry: str, cover: str,
                      slippage_bp: float = 1.0) -> dict[str, float]:
    residual = q - 1000 * int(assigned)
    hedge_days = (datetime.fromisoformat(cover) - datetime.fromisoformat(expiry)).days
    exit_days = (datetime.fromisoformat(cover if assigned else expiry) - datetime.fromisoformat(entry)).days
    if hedge_days < 0 or exit_days < 0:
        raise ValueError("negative funding or hedge duration")
    return {"option_fees": 11 * .65,
            "stock_fees": .005 * (q + abs(residual)),
            "residual_short_borrow": max(-residual, 0) * expiry_close * .03 * hedge_days / 365,
            "premium_debit_funding": max(-credit, 0) * .05 * exit_days / 365,
            "hedge_funding": q * expiry_close * .05 * hedge_days / 365,
            "stock_slippage": (q * expiry_close + abs(residual) * cover_open) * slippage_bp / 10000}


def _finite(value: Any, label: str) -> float:
    x = float(value)
    if not math.isfinite(x):
        raise ValueError(f"non-finite {label}")
    return x


def validate_stock_rows(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, float]]:
    prices: dict[tuple[str, str], dict[str, float]] = {}
    for r in rows:
        key = (str(r["secid"]), str(r["date"]))
        if key in prices:
            raise ValueError(f"duplicate stock key: {key}")
        if r["secid"] == "109820" and (r["ticker"] != "SPY" or r["index_flag"] != "0" or r["cfadj"] != "1"):
            raise ValueError("SPY stock identity/cfadj mismatch")
        if r["secid"] == "108105" and (r["ticker"] != "SPX" or r["index_flag"] != "1" or r["cfadj"] != "1"):
            raise ValueError("SPX stock identity/cfadj mismatch")
        o, h, l, c = (_finite(r[k], f"OHLC {k}") for k in ("open", "high", "low", "close"))
        if min(o, h, l, c) <= 0 or l > min(o, c) or h < max(o, c) or l > h:
            raise ValueError(f"invalid OHLC identity for {key}")
        prices[key] = {"open": o, "high": h, "low": l, "close": c, "cfadj": float(r["cfadj"])}
    return prices


def validate_distribution_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    events: set[tuple[str, str, str]] = set()
    accepted = []
    for row in rows:
        if (str(row["secid"]).strip(), str(row["ticker"]).strip(), str(row["index_flag"]).strip()) != ("109820", "SPY", "0"):
            raise ValueError("distribution SPY identity mismatch")
        record_date = datetime.fromisoformat(str(row["record_date"])).date().isoformat()
        event_key = (row["secid"], record_date, row["seq_num"])
        if event_key in events:
            raise ValueError(f"duplicate distribution event: {event_key}")
        events.add(event_key)
        amount = _finite(row["amount"], "distribution amount")
        adj = _finite(row["adj_factor"], "distribution adjustment factor")
        frequency = str(row["frequency"])
        if (frequency in {"1", "2", "3", "4", "5"} and amount > 0 and adj == 1.0
                and row["currency"] == "USD" and row["distr_type"] == "1"
                and row["approx_flag"] == "0" and row["cancel_flag"] == "0" and row["liquid_flag"] == "0"):
            accepted.append({**row, "record_date": record_date, "amount": amount, "adj_factor": adj})
    return accepted


def rebuild_full_cross_credit(selected: dict[str, Any]) -> float:
    spy_bid = _finite(selected["spy"]["normalized_best_bid"], "normalized SPY bid")
    spxw_ask = _finite(selected["spxw"]["normalized_best_offer"], "normalized SPXW ask")
    if spy_bid < 0 or spxw_ask < 0:
        raise ValueError("negative normalized option quote")
    return 1000 * spy_bid - 100 * spxw_ask


def rebuild_spxw_terminal(settlement: float, strike_milli: Any) -> float:
    pm = _finite(settlement, "SPXW PM settlement")
    strike = _finite(strike_milli, "normalized SPXW strike") / 1000
    return 100 * max(pm - strike, 0.0)


def _quantile(values: Iterable[float], q: float) -> float:
    return float(np.quantile(np.asarray(list(values), dtype=float), q, method="linear"))


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    x = np.asarray([float(r["net"]) for r in rows])
    moves = np.asarray([float(r.get("overnight_price_change", 0.0)) for r in rows])
    returns = np.asarray([float(r.get("overnight_return", 0.0)) for r in rows])
    return {"count": len(x), "mean": float(x.mean()) if len(x) else None,
            "median": float(np.median(x)) if len(x) else None,
            "total": float(x.sum()) if len(x) else 0.0,
            "win_probability": float(np.mean(x > 0)) if len(x) else None,
            "overnight_price_change_mean": float(moves.mean()) if len(moves) else None,
            "overnight_price_change_median": float(np.median(moves)) if len(moves) else None,
            "overnight_price_change_mean_abs": float(np.abs(moves).mean()) if len(moves) else None,
            "overnight_return_mean": float(returns.mean()) if len(returns) else None,
            "overnight_return_mean_abs": float(np.abs(returns).mean()) if len(returns) else None}


def concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = np.asarray([float(r["net"]) for r in rows], dtype=float)
    positive_sum = float(values[values > 0].sum())
    ordered = np.sort(values)[::-1]
    absolute_ordered = np.sort(np.abs(values))[::-1]
    return {"positive_net_pnl_sum": positive_sum,
            "top_winner_sum": {str(k): float(ordered[:k][ordered[:k] > 0].sum()) for k in (1, 5, 10)},
            "top_winner_share_of_positive_net_pnl": {str(k): float(ordered[:k][ordered[:k] > 0].sum() / positive_sum) if positive_sum > 0 else None for k in (1, 5, 10)},
            "top_absolute_net_contribution_share": {str(k): float(absolute_ordered[:k].sum() / np.abs(values).sum()) if np.abs(values).sum() > 0 else None for k in (1, 5, 10)}}


def tail_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda r: (float(r["net"]), str(r.get("expiry", "")),
                                          str(r.get("entry", "")), str(r.get("cover", ""))))
    out: dict[str, Any] = {"original_count": len(rows), "symmetric_removals": {}, "top_removals": {}, "bottom_removals": {}}
    for k in (1, 5, 10):
        for label, removed in (("top", ordered[-k:]), ("bottom", ordered[:k])):
            kept = ordered[:-k] if label == "top" else ordered[k:]
            record = {"status": "defined" if kept else "undefined_no_rows", "original_count": len(rows),
                      "removed_count": min(k, len(rows)), "retained_count": len(kept),
                      "removed_sum": float(sum(float(r["net"]) for r in removed)), **_metrics(kept)}
            out[f"{label}_removals"][str(k)] = record
        if len(ordered) > 2 * k:
            kept = ordered[k:-k]
            out["symmetric_removals"][str(k)] = {"status": "defined", "retained_count": len(kept),
                "removed_sum": float(sum(float(r["net"]) for r in ordered[:k] + ordered[-k:])), **_metrics(kept)}
        else:
            out["symmetric_removals"][str(k)] = {"status": "undefined_insufficient_rows", "retained_count": 0}
    x = np.asarray([float(r["net"]) for r in rows])
    out["winsorized_5_95_mean_nonadditive"] = float(np.clip(x, _quantile(x, .05), _quantile(x, .95)).mean()) if len(x) else None
    return out


def residual_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    counts = {s: sum(int(r["residual_q"]) > 0 if s == "long" else int(r["residual_q"]) < 0 if s == "short" else int(r["residual_q"]) == 0 for r in rows)
              for s in ("short", "flat", "long")}
    result: dict[str, Any] = {"count": n, "states": {k: {"count": v, "probability": v / n if n else None} for k, v in counts.items()}}
    for component in ("overnight", "net", "overnight_price_change", "overnight_return"):
        result[component] = {s: {"conditional_mean": float(np.mean([r[component] for r in rows if (int(r["residual_q"]) > 0 if s == "long" else int(r["residual_q"]) < 0 if s == "short" else int(r["residual_q"]) == 0)])) if counts[s] else None,
                             "all_rows_contribution_per_row": float(sum(float(r[component]) for r in rows if (int(r["residual_q"]) > 0 if s == "long" else int(r["residual_q"]) < 0 if s == "short" else int(r["residual_q"]) == 0)) / n) if n else None}
                         for s in counts}
    return result


def symmetric_frequency_payoff(p23: float, mu23: float | None, p25: float, mu25: float | None) -> dict[str, Any]:
    if mu23 is None or mu25 is None:
        return {"status": "undefined_zero_group_support", "frequency": None, "conditional_payoff": None, "sum": None}
    frequency = (p25 - p23) * (mu25 + mu23) / 2
    payoff = (mu25 - mu23) * (p25 + p23) / 2
    return {"status": "defined", "frequency": frequency, "conditional_payoff": payoff, "sum": frequency + payoff}


def bootstrap(rows23: list[dict[str, Any]], rows25: list[dict[str, Any]], *, comparison_index: int,
              draws: int = 10000) -> dict[str, Any]:
    rng = np.random.default_rng(20261030 + comparison_index)
    sampled_indices: dict[str, list[list[int]]] = {}
    means: dict[str, dict[str, list[float]]] = {}
    for year, rows in (("2023", rows23), ("2025", rows25)):
        if not rows:
            raise ValueError(f"bootstrap period has no rows: {year}")
        clusters: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            d = datetime.fromisoformat(str(r["expiry"])).date().isocalendar()
            clusters[f"{d.year:04d}-W{d.week:02d}"].append(i)
        labels = sorted(clusters)
        matrix = rng.integers(0, len(labels), size=(draws, len(labels)))
        sampled_indices[year] = matrix.tolist()
        components = sorted(set.intersection(*(set(r["components"]) for r in rows))) if rows else []
        cluster_counts = np.asarray([len(clusters[label]) for label in labels], dtype=np.int64)
        row_sums = np.asarray([[sum(float(rows[i]["components"][c]) for i in clusters[label])
                                for c in components] for label in labels], dtype=float)
        denominators = (cluster_counts[matrix]).sum(axis=1)
        numerators = row_sums[matrix].sum(axis=1)
        means[year] = {c: numerators[:, j] / denominators for j, c in enumerate(components)}
    if set(means["2023"]) != set(means["2025"]):
        raise ValueError("bootstrap component schemas differ")
    diffs = {c: np.asarray(means["2025"][c]) - np.asarray(means["2023"][c]) for c in means["2023"]}
    if "net" in diffs:
        additive = [c for c in diffs if c != "net"]
        if additive and not np.allclose(diffs["net"], sum((diffs[c] for c in additive), np.zeros(draws)), atol=1e-8, rtol=0):
            raise ValueError("bootstrap draw accounting closure failed")
    return {"draws": draws, "seed": 20261030 + comparison_index, "comparison_index": comparison_index,
            "rng": "numpy.default_rng; 2023 matrix then independent 2025 matrix", "quantile_method": "type7_linear",
            "indices_sha256": {y: canonical_sha(v) for y, v in sampled_indices.items()},
            "dimensions": {y: [draws, len(v[0]) if v else 0] for y, v in sampled_indices.items()},
            "sampled_cluster_indices": sampled_indices,
            "means_by_period": {y: {c: v.tolist() for c, v in values.items()} for y, values in means.items()},
            "draws_by_component": {c: d.tolist() for c, d in diffs.items()},
            "intervals_95": {c: [_quantile(d, .025), _quantile(d, .975)] for c, d in diffs.items()}}


def aggregate(rows23: list[dict[str, Any]], rows25: list[dict[str, Any]], *, draws: int = 10000) -> tuple[dict[str, Any], dict[str, Any]]:
    cohorts = {"2023_full": rows23, "2023_jan_aug": [r for r in rows23 if int(str(r["expiry"])[5:7]) <= 8],
               "2025_jan_aug": [r for r in rows25 if int(str(r["expiry"])[5:7]) <= 8]}
    summaries = {name: {**_metrics(group), "residual": residual_diagnostics(group), "tails": tail_diagnostics(group),
                        "concentration": concentration(group)} for name, group in cohorts.items()}
    for y in ("2023", "2025"):
        rows = rows23 if y == "2023" else rows25
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            grouped[str(r["expiry"])[:7]].append(r)
        summaries[f"{y}_months"] = {m: {**_metrics(g), "residual": residual_diagnostics(g), "tails": tail_diagnostics(g),
                                      "concentration": concentration(g)} for m, g in sorted(grouped.items())}
    bm = {}
    for i, (name, a, b) in enumerate((("full", rows23, rows25), ("jan_aug", cohorts["2023_jan_aug"], cohorts["2025_jan_aug"]))):
        bm[name] = bootstrap(a, b, comparison_index=i, draws=draws)
        for component in ("option_baseline", "overnight", "dividend", *[f"negative_{c}" for c in COSTS], "net"):
            if any(component not in r.get("components", {}) for r in a + b):
                raise ValueError(f"missing bridge component: {component}")
        delta = {c: float(np.mean([r["components"][c] for r in b]) - np.mean([r["components"][c] for r in a])) for c in ("option_baseline", "overnight", "dividend", *[f"negative_{c}" for c in COSTS])}
        delta["net"] = float(np.mean([r["net"] for r in b]) - np.mean([r["net"] for r in a]))
        if not math.isclose(sum(delta[c] for c in delta if c != "net"), delta["net"], rel_tol=0, abs_tol=1e-7):
            raise ValueError(f"mean bridge does not close: {name}")
        summaries.setdefault("mean_bridge_2025_minus_2023", {})[name] = delta
        group_deltas = {}
        for state in ("short", "flat", "long"):
            def state_rows(group: list[dict[str, Any]]) -> list[dict[str, Any]]:
                return [r for r in group if (int(r["residual_q"]) < 0 if state == "short" else int(r["residual_q"]) == 0 if state == "flat" else int(r["residual_q"]) > 0)]
            x, y = state_rows(a), state_rows(b)
            dec = symmetric_frequency_payoff(len(x)/len(a) if a else 0, float(np.mean([r["overnight"] for r in x])) if x else None,
                                             len(y)/len(b) if b else 0, float(np.mean([r["overnight"] for r in y])) if y else None)
            actual_gap = (sum(r["overnight"] for r in y)/len(b) if b else 0) - (sum(r["overnight"] for r in x)/len(a) if a else 0)
            if dec["status"] == "defined" and not math.isclose(dec["sum"], actual_gap, rel_tol=0, abs_tol=1e-7):
                raise ValueError(f"residual state decomposition does not close: {name}/{state}")
            group_deltas[state] = {**dec, "overnight_gap": actual_gap}
        summaries.setdefault("residual_frequency_payoff_2025_minus_2023", {})[name] = group_deltas
        for cohort_name, cohort in (("2023", a), ("2025", b)):
            no_overnight = [float(r["net"]) - float(r["overnight"]) for r in cohort]
            summaries.setdefault("net_minus_overnight_price_diagnostic", {}).setdefault(name, {})[cohort_name] = {
                "count": len(no_overnight), "mean": float(np.mean(no_overnight)) if no_overnight else None,
                "total": float(sum(no_overnight)), "interpretation": "option baseline plus dividends less costs; removing only the overnight price term is an accounting diagnostic, not a risk-free hedge strategy"}
    return summaries, bm


def _json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def _read_rows(path: Path) -> list[dict[str, str]]:
    op = gzip.open if path.suffix == ".gz" else open
    with op(path, "rt", newline="") as f:
        return list(csv.DictReader(f))


def _pair_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row["entry"]), str(row["expiry"]), str(row["cover"]))


def _load_frozen_rows(source_manifest: dict[str, Any], *,
                      expected_counts: dict[str, int] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    expected_counts = PERIOD_COUNTS if expected_counts is None else expected_counts
    src = source_manifest["sources"]
    def doc(role: str) -> Any:
        return _json(Path(src[role]["path"]))

    legacy = doc("legacy_ledgers")
    summaries25 = doc("legacy_summaries")
    summaries23 = doc("replication_summary")["scenario_summaries"]
    outcomes_list = doc("legacy_outcomes")
    selection23_list = doc("replication_selection")["selected_pairs"]
    selection25_list = doc("legacy_selection")["selected_pairs"]
    settlements23: dict[str, float] = {}
    settlement_candidates: dict[str, list[float]] = defaultdict(list)
    for source_name in ("cboe_W_2023", "cboe_M_2023", "cboe_S_2023"):
        source = source_manifest.get("transitive_inputs", {}).get(source_name)
        if not source or not source.get("sha256"):
            raise ValueError(f"missing bound frozen settlement source: {source_name}")
        source_doc = _json(Path(source["path"]))
        rows = source_doc.get("data", []) if isinstance(source_doc, dict) else []
        for settlement_row in rows:
            if settlement_row.get("trading_symbol") == "SPXW" and settlement_row.get("settlement_symbol") == "SPX":
                day = str(settlement_row["expiration_date"])
                settlement_candidates[day].append(_finite(settlement_row["settlement_value"], "SPXW PM settlement"))
    for day, values in settlement_candidates.items():
        if len(set(values)) != 1:
            raise ValueError(f"conflicting frozen SPXW settlements for {day}")
        settlements23[day] = values[0]
    outcomes = index_unique(outcomes_list, _pair_key, "2025 outcome")
    selection23 = index_unique(selection23_list, lambda r: _pair_key(r), "2023 selection")
    selection25 = index_unique(selection25_list, _pair_key, "2025 selection")
    prices = validate_stock_rows(_read_rows(Path(src["stock_prices"]["path"])))
    repl = doc("replication_ledgers")
    repl_main = index_unique((r for r in repl if r["scenario"] == SCENARIO_MAIN), _pair_key, "2023 main scenario")
    repl_q0 = index_unique((r for r in repl if r["scenario"] == SCENARIO_Q0), _pair_key, "2023 q0 scenario")
    main25_rows = [r for r in legacy if r["period"] == "2025" and r["arm"] == "open_itm_q1000" and r["fill"] == "full_cross"
                   and r["funding"] == "gross_prefunding" and r["slippage_bp"] == 1 and not r["stress"]]
    q025_rows = [r for r in legacy if r["period"] == "2025" and r["arm"] == "unhedged_q0" and r["fill"] == "full_cross"
                 and r["funding"] == "gross_prefunding" and r["slippage_bp"] == 1 and not r["stress"]]
    main25 = index_unique(main25_rows, _pair_key, "2025 main ledger")
    q025 = index_unique(q025_rows, _pair_key, "2025 q0 ledger")
    if set(repl_main) != set(repl_q0) or set(repl_main) != set(selection23):
        raise ValueError("2023 main, q0, and selected-pair key sets differ")
    if set(main25) != set(q025) or set(main25) != set(outcomes) or set(outcomes) != set(selection25):
        raise ValueError("2025 main, q0, outcome, and selected-pair key sets differ")

    distributions = validate_distribution_rows(_read_rows(Path(source_manifest["transitive_inputs"]["wrds_distributions"]["path"])))
    years: dict[str, list[dict[str, Any]]] = {"2023": [], "2025": []}
    private_rows: list[dict[str, Any]] = []
    state_counts: dict[str, int] = defaultdict(int)
    indexed: dict[str, tuple[dict, dict, dict]] = {}
    for key, wrap in repl_main.items():
        indexed["2023"] = indexed.get("2023", ({}, {}, {}))
        indexed["2023"][0][key] = {"period": "2023", **wrap["ledger"]}
        indexed["2023"][1][key] = {"period": "2023", **repl_q0[key]["ledger"]}
        indexed["2023"][2][key] = wrap["fill_row"]
    for key, ledger in main25.items():
        indexed["2025"] = indexed.get("2025", ({}, {}, {}))
        indexed["2025"][0][key] = ledger
        indexed["2025"][1][key] = q025[key]
        full = [r for r in outcomes[key]["fill_rows"] if r["fill"] == "full_cross"]
        if len(outcomes[key]["fill_rows"]) != 3 or len(full) != 1:
            raise ValueError(f"unexpected 2025 fill rows for {key}")
        indexed["2025"][2][key] = full[0]

    if len(outcomes) != expected_counts["2025"] or len(repl_main) != expected_counts["2023"]:
        raise ValueError("unexpected retained pair counts")
    if len(summaries25) == 0:
        raise ValueError("missing accepted 2025 summaries")

    def event_dividend(key: tuple[str, str, str]) -> float:
        return sum(float(d["amount"]) for d in distributions if key[1] < d["ex_date"] <= key[2])

    for year in ("2023", "2025"):
        main_map, q0_map, fill_map = indexed[year]
        for key in sorted(main_map):
            entry, expiry, cover = key
            if (year == "2023" and not "2023-01-01" <= key[1] <= "2023-12-31") or (year == "2025" and not "2025-01-01" <= key[1] <= "2025-08-31"):
                raise ValueError(f"expiry outside declared period: {key}")
            if year == "2023":
                selected = selection23[key]["selected"]
                spy_strike = _finite(selected["spy"]["normalized_strike_milli"], "2023 normalized SPY strike") / 1000
                q0_fill = repl_q0[key]["fill_row"]
                fill = fill_map[key]
                spxw_settlement = settlements23.get(expiry)
                if spxw_settlement is None:
                    raise ValueError(f"missing frozen 2023 SPXW PM settlement for {expiry}")
            else:
                selected = selection25[key]
                outcome = outcomes[key]
                full = [r for r in outcome["fill_rows"] if r["fill"] == "full_cross"]
                if len(outcome["fill_rows"]) != 3 or len(full) != 1:
                    raise ValueError(f"unexpected 2025 fill rows for {key}")
                spy_strike = _finite(outcome["spy_strike"], "2025 SPY strike")
                selected_strike = _finite(selected["spy"]["normalized_strike_milli"], "2025 selected SPY strike") / 1000
                if not math.isclose(spy_strike, selected_strike, rel_tol=0, abs_tol=1e-9):
                    raise ValueError(f"2025 selected strike/outcome mismatch for {key}")
                q0_fill = full[0]
                fill = full[0]
                spxw_settlement = _finite(outcome["spxw_pm_settlement"], "2025 SPXW PM settlement")
            for date in (entry, expiry, cover):
                if ("109820", date) not in prices or ("108105", date) not in prices:
                    raise ValueError(f"missing stock OHLC identity for selected date {date}")
            expiry_open = prices[("109820", expiry)]["open"]
            expiry_close = prices[("109820", expiry)]["close"]
            cover_open = prices[("109820", cover)]["open"]
            q = reconstruct_q(expiry_open, spy_strike)
            assigned = reconstruct_assignment(expiry_close, spy_strike)
            ledger, q0 = main_map[key], q0_map[key]
            if (int(ledger["q"]) != q or int(ledger["assigned"]) != int(assigned)
                    or bool(fill["assigned"]) != assigned or int(q0["assigned"]) != int(assigned)):
                raise ValueError(f"frozen hedge or assignment state mismatch for {key}")
            residual = q - 1000 * int(assigned)
            q0_residual = -1000 * int(assigned)
            if int(ledger["residual_shares"]) != residual or int(q0["q"]) != 0 or int(q0["residual_shares"]) != q0_residual:
                raise ValueError(f"retained residual share mismatch for {key}")
            state_counts[f"q{q}_A{int(assigned)}"] += 1
            dividend = event_dividend(key)
            if any(not math.isclose(1000 * int(assigned) * dividend,
                                    _finite(source_fill["dividend_carry_amount"], "dividend_carry_amount"),
                                    rel_tol=0, abs_tol=COST_TOL)
                   for source_fill in (fill, q0_fill)):
                raise ValueError(f"raw distribution cash mismatch for {key}")
            selected_credit = rebuild_full_cross_credit(selected)
            spxw_strike_milli = selected["spxw"]["normalized_strike_milli"]
            terminal_cash = rebuild_spxw_terminal(spxw_settlement, spxw_strike_milli)
            if not math.isclose(selected_credit, _finite(fill["credit"], "retained credit"), rel_tol=0, abs_tol=COST_TOL):
                raise ValueError(f"rebuilt full-cross credit mismatch for {key}")
            if not math.isclose(terminal_cash, _finite(fill["spxw_leg_terminal_cash"], "retained SPXW terminal cash"), rel_tol=0, abs_tol=COST_TOL):
                raise ValueError(f"rebuilt SPXW terminal cash mismatch for {key}")
            if year == "2023":
                q0_primitive = q0_fill
                if any(not math.isclose(float(fill[k]), float(q0_primitive[k]), rel_tol=0, abs_tol=COST_TOL)
                       for k in ("credit", "spxw_leg_terminal_cash", "assigned")):
                    raise ValueError(f"2023 main/q0 source primitive mismatch for {key}")
            else:
                q0_primitive = fill
            close_notional = q * expiry_close
            cover_notional = abs(residual * cover_open)
            for name, quantity, a, source_fill, actual_ledger in (
                ("main", q, assigned, fill, ledger), ("q0", 0, assigned, q0_primitive, q0)):
                expected_costs = reconstruct_costs(q=quantity, assigned=a, credit=selected_credit,
                    expiry_close=expiry_close, cover_open=cover_open, entry=entry, expiry=expiry, cover=cover)
                for cost_name in COSTS:
                    if not math.isclose(_finite(actual_ledger["costs"][cost_name], cost_name), expected_costs[cost_name], rel_tol=0, abs_tol=COST_TOL):
                        raise ValueError(f"reconstructed {name} cost mismatch for {key}/{cost_name}")
                raw = {"credit": selected_credit, "spxw_leg_terminal_cash": terminal_cash,
                       "spy_strike": spy_strike, "assigned": a, "q": quantity, "costs": expected_costs}
                terms = primitive(raw, expiry_close=expiry_close, next_open=cover_open, dividend=dividend)
                for field, actual in (("net_pnl", terms["net"]),
                    ("gross_pnl", terms["option_baseline"] + terms["overnight"] + terms["dividend"]),
                    ("overnight_price_contribution", terms["overnight"]), ("dividend_cash", terms["dividend"])):
                    if not math.isclose(_finite(actual_ledger[field], field), actual, rel_tol=0, abs_tol=COST_TOL):
                        raise ValueError(f"reconstructed {name} accounting mismatch for {key}/{field}")
                if name == "main":
                    main_terms = terms
                else:
                    q0_terms = terms
            if not math.isclose(close_notional, _finite(ledger["stock_notional_close"], "stock_notional_close"), rel_tol=0, abs_tol=1e-6):
                raise ValueError(f"stock close notional mismatch for {key}")
            if not math.isclose(cover_notional, _finite(ledger["stock_notional_cover"], "stock_notional_cover"), rel_tol=0, abs_tol=1e-6):
                raise ValueError(f"stock cover notional mismatch for {key}")
            if not math.isclose(0.0, _finite(q0["stock_notional_close"], "q0 stock_notional_close"), rel_tol=0, abs_tol=1e-6):
                raise ValueError(f"q0 stock close notional mismatch for {key}")
            if not math.isclose(abs(q0_residual * cover_open), _finite(q0["stock_notional_cover"], "q0 stock_notional_cover"), rel_tol=0, abs_tol=1e-6):
                raise ValueError(f"q0 stock cover notional mismatch for {key}")
            row = {"entry": entry, "expiry": expiry, "cover": cover, "net": main_terms["net"], "residual_q": residual,
                   "overnight": main_terms["overnight"], "overnight_price_change": cover_open - expiry_close,
                   "overnight_return": (cover_open - expiry_close) / expiry_close,
                   "components": {k: v for k, v in main_terms.items() if k in ("option_baseline", "overnight", "dividend", *[f"negative_{c}" for c in COSTS], "net")}}
            years[year].append(row)
            private_rows.append({**row, "q": q, "assigned": assigned, "spy_strike": spy_strike,
                "expiry_spy_open": expiry_open, "expiry_spy_close": expiry_close, "cover_spy_open": cover_open,
                "dividend_per_share": dividend, "costs_reconstructed": reconstruct_costs(q=q, assigned=assigned,
                    credit=float(fill["credit"]), expiry_close=expiry_close, cover_open=cover_open, entry=entry, expiry=expiry, cover=cover),
                "main_ledger_net": ledger["net_pnl"], "q0_reconstructed": q0_terms, "q0_ledger_net": q0["net_pnl"],
                "state": f"q{q}_A{int(assigned)}", "row_checks": {"main": True, "q0": True, "q": True, "A": True,
                    "residual": True, "all_six_costs_rebuilt": True, "gross_net_dividend_overnight": True,
                    "stock_notionals": True}})
    for year in ("2023", "2025"):
        if len(years[year]) != expected_counts[year]:
            raise ValueError(f"unexpected {year} retained pair count: {len(years[year])}")
    _reconcile_2023_summary(summaries23, indexed["2023"][0], indexed["2023"][1])
    _reconcile_summary(summaries25, indexed["2025"][0], indexed["2025"][1], "2025")
    return years["2023"], years["2025"], {"private_rows": private_rows, "q_a_state_counts": dict(sorted(state_counts.items()))}


def _reconcile_summary(summaries: list[dict[str, Any]], main: dict, q0: dict, year: str) -> None:
    for arm, ledger_map in (("open_itm_q1000", main), ("unhedged_q0", q0)):
        selected = [v for k, v in ledger_map.items() if v["period"] == year]
        prior = [r for r in summaries if str(r["period"]) == year and r["arm"] == arm and r["fill"] == "full_cross" and r["funding"] == "gross_prefunding" and float(r["slippage_bp"]) == 1 and not r["stress"]]
        if len(prior) != 1 or len(selected) != int(prior[0]["count"]):
            raise ValueError(f"prior summary count mismatch: {year}/{arm}")
        p = prior[0]
        if not math.isclose(float(np.mean([r["net_pnl"] for r in selected])), float(p["mean"]), rel_tol=0, abs_tol=1e-7):
            raise ValueError(f"prior summary mean mismatch: {year}/{arm}")
        if not math.isclose(float(np.median([r["net_pnl"] for r in selected])), float(p["median"]), rel_tol=0, abs_tol=1e-7):
            raise ValueError(f"prior summary median mismatch: {year}/{arm}")
        if not math.isclose(float(np.mean([r["net_pnl"] > 0 for r in selected])), float(p["win_rate"]), rel_tol=0, abs_tol=1e-9):
            raise ValueError(f"prior summary win rate mismatch: {year}/{arm}")
        if not math.isclose(float(sum(r["net_pnl"] for r in selected)), float(p["mean"]) * int(p["count"]), rel_tol=0, abs_tol=1e-6):
            raise ValueError(f"prior summary total mismatch: {year}/{arm}")
        for field, ledger_field in (("mean_dividend_cash", "dividend_cash"),
                                    ("mean_overnight_price_contribution", "overnight_price_contribution")):
            if field in p and not math.isclose(float(np.mean([r[ledger_field] for r in selected])), float(p[field]), rel_tol=0, abs_tol=1e-7):
                raise ValueError(f"prior summary {field} mismatch: {year}/{arm}")
        if "mean_cost_components" in p:
            for cost in COSTS:
                if not math.isclose(float(np.mean([r["costs"][cost] for r in selected])), float(p["mean_cost_components"][cost]), rel_tol=0, abs_tol=1e-7):
                    raise ValueError(f"prior summary cost mismatch: {year}/{arm}/{cost}")


def _reconcile_2023_summary(summaries: dict[str, Any], main: dict, q0: dict) -> None:
    for arm, ledger_map in (("open_itm_q1000", main), ("unhedged_q0", q0)):
        scenario_key = f"{arm}|full_cross|base|1bp|gross_prefunding"
        if scenario_key not in summaries:
            raise ValueError(f"missing accepted 2023 scenario summary: {scenario_key}")
        prior = summaries[scenario_key]["net_pnl"]
        values = [float(row["net_pnl"]) for row in ledger_map.values()]
        checks = (("count", len(values), int(prior["count"])),
                  ("mean", float(np.mean(values)), float(prior["mean"])),
                  ("median", float(np.median(values)), float(prior["median"])),
                  ("total", float(sum(values)), float(prior["total"])),
                  ("win_fraction", float(np.mean(np.asarray(values) > 0)), float(prior["win_fraction"])))
        for field, actual, expected in checks:
            if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-7):
                raise ValueError(f"accepted 2023 summary mismatch: {arm}/{field}")


def _git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def atomic_publish(out: Path, payloads: dict[str, str], manifest_name: str,
                   manifest_builder: Any, final_check: Any, *, root: Path = ROOT,
                   after_manifest_write: Any = None) -> None:
    validate_output_path(out, root=root)
    stage = Path(tempfile.mkdtemp(prefix=f".{out.name}.", dir=out.parent))
    try:
        for name, text in payloads.items():
            (stage / name).write_text(text)
        hashes = {name: sha256(stage / name) for name in payloads}
        (stage / manifest_name).write_text(manifest_builder(hashes))
        if after_manifest_write is not None:
            after_manifest_write(stage)
        final_check(stage, hashes)
        validate_output_path(out, root=root)
        if not _git_ignored(stage, root):
            raise ValueError("staging directory is not Git-ignored")
        stage.rename(out)
    except BaseException:
        import shutil
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _guard(manifest_path: Path, manifest_digest: str, protocol_path: Path, protocol_digest: str) -> tuple[str, dict[str, Any]]:
    if manifest_digest != EXPECTED_MANIFEST_SHA256 or sha256(manifest_path) != manifest_digest:
        raise ValueError("input manifest hash mismatch")
    if sha256(protocol_path) != protocol_digest:
        raise ValueError("protocol hash mismatch")
    if _git(["status", "--porcelain", "--untracked-files=all"]):
        raise ValueError("Git worktree must be clean; ignored planning output is permitted")
    head = _git(["rev-parse", "HEAD"])
    source = ROOT / "src/spyspx/morning_hedge_attribution.py"
    verify_code_binding(source, subprocess.check_output(["git", "show", f"{head}:src/spyspx/morning_hedge_attribution.py"], cwd=ROOT),
                        head, head, "")
    module_spec = __import__("importlib.util", fromlist=["find_spec"]).find_spec(__name__)
    if module_spec is None or Path(module_spec.origin).resolve() != MODULE_PATH_AT_LOAD or Path(__file__).resolve() != MODULE_PATH_AT_LOAD:
        raise ValueError("loaded module path mismatch")
    return head, json.loads(protocol_path.read_text())


def _validate_protocol(p: dict[str, Any], manifest_hash: str) -> None:
    expected = {"input_manifest_sha256": manifest_hash, "scenario": "open_itm_q1000|full_cross|base|1bp|gross_prefunding",
                "draws": 10000, "seed_base": 20261030, "quantile_method": "type7_linear",
                "cluster_unit": "ISO year-week", "sampling": "independent years; ratio of sampled row sums to sampled row counts",
                "dividends": "included", "periods": {"2023": "2023-01-01/2023-12-31", "2023_common": "2023-01-01/2023-08-31", "2025": "2025-01-01/2025-08-31"}}
    for key, value in expected.items():
        if p.get(key) != value:
            raise ValueError(f"protocol field mismatch: {key}")
    if p.get("rng") != "numpy.default_rng; draw 2023 integer matrix first, then 2025 matrix from the same generator":
        raise ValueError("protocol RNG specification mismatch")
    if p.get("status") != "FROZEN" or p.get("actual_run_authorized") is not True:
        raise ValueError("protocol is not frozen and explicitly authorized")


def run(manifest: Path, manifest_hash: str, protocol: Path, protocol_hash: str, out: Path) -> None:
    head, protocol_data = _guard(manifest, manifest_hash, protocol, protocol_hash)
    _validate_protocol(protocol_data, manifest_hash)
    validate_output_path(out)
    source_manifest = json.loads(manifest.read_text())
    if len(source_manifest.get("sources", {})) != 12:
        raise ValueError("frozen input manifest must retain its 12 declared sources")
    replica_manifest = _json(Path(source_manifest["sources"]["replication_manifest"]["path"]))
    replica_inputs = replica_manifest.get("inputs", {})
    transitive_names = ("wrds_distributions", "cboe_W_2023", "cboe_M_2023", "cboe_S_2023")
    transitive = {name: replica_inputs[name] for name in transitive_names if name in replica_inputs}
    if set(transitive) != set(transitive_names):
        raise ValueError("replication manifest is missing a required transitive input")
    source_manifest["transitive_inputs"] = transitive
    bindings = {**source_manifest["sources"], **transitive,
                "input_manifest": {"path": str(manifest), "sha256": manifest_hash},
                "protocol": {"path": str(protocol), "sha256": protocol_hash}}
    before = verify_input_bindings(bindings)
    stdout_capture, stderr_capture = io.StringIO(), io.StringIO()
    started = datetime.now(timezone.utc).isoformat()
    with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
        rows23, rows25, private = _load_frozen_rows(source_manifest)
        summaries, boot = aggregate(rows23, rows25)
        payloads = {"aggregate.json": json.dumps({"status": "ATTRIBUTION_RUN", "cohorts": summaries,
                    "q_a_state_counts": private["q_a_state_counts"],
                    "comparison_windows": {"2023_full": [min(r["expiry"] for r in rows23), max(r["expiry"] for r in rows23)],
                                           "2023_jan_aug": [min(r["expiry"] for r in rows23 if r["expiry"][5:7] <= "08"), max(r["expiry"] for r in rows23 if r["expiry"][5:7] <= "08")],
                                           "2025_jan_aug": [min(r["expiry"] for r in rows25), max(r["expiry"] for r in rows25)]}}, indent=2, sort_keys=True) + "\n",
                    "bootstrap-draws.json": json.dumps(boot, separators=(",", ":"), sort_keys=True) + "\n",
                    "private-primitive-rows.json": json.dumps(private["private_rows"], separators=(",", ":"), sort_keys=True) + "\n"}
        source = ROOT / "src/spyspx/morning_hedge_attribution.py"
        def build_manifest(output_hashes: dict[str, str]) -> str:
            after = verify_input_bindings(bindings)
            return json.dumps({"status": "ATTRIBUTION_RUN", "command": [sys.executable, *sys.argv],
                "started_utc": started, "ended_utc": datetime.now(timezone.utc).isoformat(),
                "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
                "model_identity": "N/A_DETERMINISTIC", "model_endpoint": "N/A_DETERMINISTIC",
                "clean_git_sha": head, "protocol_sha256": protocol_hash, "input_manifest_sha256": manifest_hash,
                "loaded_code_path": str(MODULE_PATH_AT_LOAD), "loaded_code_sha256": MODULE_SHA256_AT_LOAD,
                "input_sha256_before": before, "input_sha256_after": after,
                "output_sha256": output_hashes, "output_hash_scope": "all output files except this manifest",
                "stdout": stdout_capture.getvalue(), "stderr": stderr_capture.getvalue()}, indent=2, sort_keys=True) + "\n"

        def final_check(stage: Path, output_hashes: dict[str, str]) -> None:
            if {name: sha256(stage / name) for name in payloads} != output_hashes:
                raise ValueError("staged output changed after hashing")
            staged_manifest = _json(stage / "run-manifest.json")
            if staged_manifest.get("output_sha256") != output_hashes:
                raise ValueError("staged run manifest does not bind output hashes")
            if verify_input_bindings(bindings) != before:
                raise ValueError("frozen input changed during staging")
            if sha256(manifest) != manifest_hash or sha256(protocol) != protocol_hash:
                raise ValueError("manifest or protocol changed during staging")
            blob = subprocess.check_output(["git", "show", f"{head}:src/spyspx/morning_hedge_attribution.py"], cwd=ROOT)
            verify_code_binding(source, blob, head, _git(["rev-parse", "HEAD"]),
                                _git(["status", "--porcelain", "--untracked-files=all"]))
            spec = __import__("importlib.util", fromlist=["find_spec"]).find_spec(__name__)
            if spec is None or Path(spec.origin).resolve() != MODULE_PATH_AT_LOAD or Path(__file__).resolve() != MODULE_PATH_AT_LOAD:
                raise ValueError("loaded module path changed during staging")
            validate_output_path(out)
            if not _git_ignored(stage, ROOT):
                raise ValueError("staging directory is not Git-ignored")

        atomic_publish(out, payloads, "run-manifest.json", build_manifest, final_check)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--input-manifest", type=Path, required=True)
    ev.add_argument("--input-manifest-sha256", required=True)
    ev.add_argument("--protocol", type=Path, required=True)
    ev.add_argument("--protocol-sha256", required=True)
    ev.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    run(args.input_manifest, args.input_manifest_sha256, args.protocol, args.protocol_sha256, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
