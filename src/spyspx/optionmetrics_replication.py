"""Bounded deterministic OptionMetrics source audit and frozen diagnostic runner."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .expiry_extension import cost_adjusted, expiry_ledger, fill_cash_terms
from .expiry_payoff import Quote
from .optionmetrics_admission import _validate_output, git_info
from . import optionmetrics_normalizer as normalizer

PROTOCOL = Path("planning/optionmetrics-20261029/optionmetrics-replication-protocol-20261029.md")
INPUT_MANIFEST = Path("planning/optionmetrics-20261029/optionmetrics-input-manifest-20261029.json")
PROTOCOL_SHA256 = "952969cade05ec3e8b0c5ce388e8fac12a5ec9b0e823fa3160eb25f50dd5c662"
INPUT_MANIFEST_SHA256 = "75515e7ab8b748d9f3e4502a4adaf6bf7786e88a00da46c27070080976925cf0"
PERIOD_EXPORT = {
    "pilot": ("pilot_quotes", "authenticated-schema-and-pilot.json", "pilot-normalizer-identity-metadata.json", "pilot20190806-projection-control.csv"),
    "primary_2024": ("quotes-2024.csv.gz", "normalizer-source-metadata-2024.json", "normalizer-identity-metadata-2024.json", "price-only-control-2024-20250828.csv.gz"),
    "confirmation_2025": ("quotes-2025-through-0828.csv.gz", "normalizer-source-metadata-2025-through-0828.json", "normalizer-identity-metadata-2025-through-0828.json", "price-only-control-2024-20250828.csv.gz"),
}
SECURITY_IDS = {"SPY": "109820", "SPX": "108105"}
TICKER_FLAGS = {"SPY": "0", "SPX": "1"}
OPTION_COMMON = ("secid", "date", "symbol", "symbol_flag", "exdate", "last_date", "cp_flag", "strike_price", "best_bid", "best_offer", "volume", "open_interest", "impl_volatility", "delta", "gamma", "vega", "theta", "optionid", "cfadj", "am_settlement", "contract_size", "ss_flag", "forward_price", "expiry_indicator", "root", "suffix", "index_flag", "issuer", "exercise_style")
SOURCE_LIMITS = [
    "WRDS extraction SQL was not exposed. Returned-export projection checks do not verify server-side join logic.",
    "Passing source checks validates these acquired rows only, not the vendor universe or completeness.",
    "Daily 15:59 ET quotes are paired with later closes. Every output is a timing-mismatched theoretical diagnostic.",
    "Bid/ask sizes are unavailable from these sources. No account, margin, capacity, fill, or return claims are made.",
]
RUN_CODE_PATHS = {
    "code_normalizer": "src/spyspx/optionmetrics_normalizer.py",
    "code_admission": "src/spyspx/optionmetrics_admission.py",
    "code_expiry_extension": "src/spyspx/expiry_extension.py",
    "code_expiry_payoff": "src/spyspx/expiry_payoff.py",
    "code_replication": "src/spyspx/optionmetrics_replication.py",
    "code_legacy_pilot_parser": "src/spyspx/expiry_replication.py",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iso_day(value: str, field: str) -> date:
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a valid ISO date") from exc
    return parsed


def _git_clean(repo: Path) -> tuple[str, bool]:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, text=True, capture_output=True, check=True).stdout
    return sha, not bool(status.strip())


def _capture_run_identity(repo: Path, period: str) -> dict:
    sha, clean = _git_clean(repo)
    if not clean:
        raise ValueError("run requires a clean Git worktree before any input read or selection")
    roles = ["code_normalizer", "code_admission", "code_expiry_extension", "code_expiry_payoff", "code_replication"]
    if period == "pilot":
        roles.append("code_legacy_pilot_parser")
    loaded_paths = {
        "code_normalizer": Path(normalizer.__file__),
        "code_admission": Path(sys.modules["spyspx.optionmetrics_admission"].__file__),
        "code_expiry_extension": Path(sys.modules["spyspx.expiry_extension"].__file__),
        "code_expiry_payoff": Path(sys.modules["spyspx.expiry_payoff"].__file__),
        "code_replication": Path(__file__),
    }
    if period == "pilot":
        pilot_spec = importlib.util.find_spec("spyspx.expiry_replication")
        if pilot_spec is None or pilot_spec.origin is None:
            raise ValueError("pilot parser module path could not be resolved")
        loaded_paths["code_legacy_pilot_parser"] = Path(pilot_spec.origin)
    captured = {}
    for role in roles:
        relative = RUN_CODE_PATHS[role]
        expected = (repo / relative).resolve(strict=True)
        actual = loaded_paths[role].resolve(strict=True)
        if actual != expected:
            raise ValueError(f"unexpected module path for {role}")
        data = actual.read_bytes()
        blob = subprocess.run(["git", "show", f"{sha}:{relative}"], cwd=repo, capture_output=True, check=False)
        if blob.returncode or blob.stdout != data:
            raise ValueError(f"loaded {role} bytes do not match initial HEAD {sha}")
        captured[role] = {"path": str(actual), "relative_path": relative, "bytes": len(data), "sha256": digest(data), "data": data}
    return {"initial_head": sha, "initial_clean": True, "code": captured}


def _check_run_identity(repo: Path, identity: dict, inputs: dict[str, dict] | None = None,
                        selection_path: Path | None = None, selection_hash: str | None = None) -> dict:
    sha, clean = _git_clean(repo)
    if sha != identity["initial_head"] or not clean:
        raise ValueError("BLOCKED: Git HEAD or clean state changed during run")
    code_hashes = {}
    for role, record in identity["code"].items():
        path = Path(record["path"])
        relative = record["relative_path"]
        current = path.read_bytes()
        blob = subprocess.run(["git", "show", f"{identity['initial_head']}:{relative}"], cwd=repo, capture_output=True, check=False)
        if (len(current) != record["bytes"] or digest(current) != record["sha256"] or
                blob.returncode or blob.stdout != record["data"] or current != record["data"]):
            raise ValueError(f"BLOCKED: code changed during run: {role}")
        code_hashes[role] = record["sha256"]
    if inputs is not None and not _snapshots_unchanged(inputs):
        raise ValueError("BLOCKED: an input changed during run")
    if selection_path is not None:
        try:
            selected = selection_path.read_bytes()
        except OSError as exc:
            raise ValueError("BLOCKED: selected snapshot disappeared") from exc
        if selection_hash is None or digest(selected) != selection_hash:
            raise ValueError("BLOCKED: selected snapshot changed during run")
    return {"verified": True, "head": sha, "clean": clean, "code_sha256": code_hashes,
            "inputs_verified": True,
            "selection_sha256": selection_hash if selection_path is not None else None}


def _frozen_files(repo: Path, manifest: dict) -> dict[str, dict]:
    result = {}
    for role, record in manifest["files"].items():
        path = Path(record["path"])
        if not path.is_absolute():
            path = repo / path
        resolved = path.resolve(strict=True)
        data = resolved.read_bytes()
        if len(data) != record["bytes"] or digest(data) != record["sha256"]:
            raise ValueError(f"frozen input integrity mismatch for {role}")
        result[role] = {"path": str(resolved), "bytes": len(data), "sha256": digest(data), "data": data}
    return result


def _sidecars(repo: Path, period: str, records: dict[str, dict]) -> dict[str, dict]:
    export_role, source_name, identity_name, _ = PERIOD_EXPORT[period]
    root = repo / "planning/optionmetrics-20261029"
    paths = {"source_metadata": root / source_name, "identity_metadata": root / identity_name}
    output = {}
    for role, path in paths.items():
        path = path.resolve(strict=True)
        data = path.read_bytes()
        output[role] = {"path": str(path), "bytes": len(data), "sha256": digest(data), "data": data}
    src = json.loads(output["source_metadata"]["data"])
    if src["query"]["file_sha256"] != records[export_role]["sha256"]:
        raise ValueError(f"{period} source metadata does not bind its frozen raw export")
    return output


def _parse_csv(data: bytes, label: str, *, compressed: bool = False) -> tuple[list[str], list[dict[str, str]]]:
    if compressed:
        data = normalizer._decode_export(data, "gzip")
    try:
        reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError(f"{label} is empty") from exc
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"{label} is not valid CSV text: {exc}") from exc
    if not headers or len(headers) != len(set(headers)):
        raise ValueError(f"{label} has empty or duplicate headers")
    rows = []
    try:
        for line, cells in enumerate(reader, 2):
            if len(cells) != len(headers):
                raise ValueError(f"{label} row {line} has {len(cells)} cells; expected {len(headers)}")
            rows.append(dict(zip(headers, cells)))
    except csv.Error as exc:
        raise ValueError(f"{label} has malformed CSV at row {reader.line_num}: {exc}") from exc
    return headers, rows


def _number(value: object, field: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} is not numeric") from exc
    if not math.isfinite(number) or (positive and number <= 0) or (nonnegative and number < 0):
        raise ValueError(f"{field} is not finite or outside its allowed range")
    return number


def _read_calendar(data: bytes) -> tuple[set[date], dict[date, float]]:
    headers, rows = _parse_csv(data, "official SPX calendar")
    if headers != ["DATE", "SPX"]:
        raise ValueError("official SPX calendar headers must be DATE,SPX")
    values: dict[date, float] = {}
    for row in rows:
        day = datetime.strptime(row["DATE"].strip(), "%m/%d/%Y").date()
        value = _number(row["SPX"], "official SPX close", positive=True)
        if day in values:
            raise ValueError(f"official SPX calendar has duplicate date {day}")
        values[day] = value
    return set(values), values


def _validate_expected_pairs(period_data: dict, sessions: set[date]) -> list[dict]:
    pairs = period_data.get("expected_pairs")
    if not isinstance(pairs, list) or len(pairs) != period_data.get("expected_count"):
        raise ValueError("frozen expected-pair list does not match expected_count")
    result, seen = [], set()
    ordered_sessions = sorted(sessions)
    next_session = {left: right for left, right in zip(ordered_sessions, ordered_sessions[1:])}
    for item in pairs:
        entry, expiry, cover = (iso_day(item[k], f"expected_pairs.{k}") for k in ("entry", "expiry", "cover"))
        if entry in seen or expiry != entry + timedelta(days=1) or entry not in sessions or expiry not in sessions or cover not in sessions or next_session.get(expiry) != cover:
            raise ValueError(f"frozen expected pair is invalid against the independent session calendar: {item}")
        seen.add(entry)
        result.append({"entry": entry, "expiry": expiry, "cover": cover})
    if result != sorted(result, key=lambda item: item["entry"]):
        raise ValueError("frozen expected pairs are not in date order")
    return result


def _projection_check(export: bytes, control: bytes, compressed: bool, companion: bytes | None = None) -> dict:
    export_headers, export_rows = _parse_csv(export, "enriched OptionMetrics export", compressed=compressed)
    companion_rows = []
    if companion is not None:
        companion_headers, companion_rows = _parse_csv(companion, "companion OptionMetrics export", compressed=True)
        if companion_headers != export_headers:
            raise ValueError("yearly OptionMetrics exports have different headers")
    control_headers, control_rows = _parse_csv(control, "projection control", compressed=control.startswith(b"\x1f\x8b"))
    common = [field for field in export_headers if field in set(control_headers)]
    if tuple(common) != OPTION_COMMON:
        raise ValueError("projection control does not expose the expected 29 common fields")
    key_fields = ("secid", "date", "optionid")
    def keyed(rows, label):
        result = {}
        for row in rows:
            key = tuple(row[field] for field in key_fields)
            if key in result:
                raise ValueError(f"{label} contains duplicate projection key")
            result[key] = row
        return result
    left, right = keyed(export_rows + companion_rows, "combined enriched exports"), keyed(control_rows, "projection control")
    missing = set(left) - set(right)
    extra = set(right) - set(left)
    mismatches = Counter()
    for key in left.keys() & right.keys():
        for field in common:
            if left[key][field] != right[key][field]:
                mismatches[field] += 1
    return {"common_fields": len(common), "export_rows": len(left), "control_rows": len(right), "matching_keys": len(left.keys() & right.keys()),
            "companion_rows": len(companion_rows),
            "missing_control_keys": len(missing), "extra_control_keys": len(extra), "field_mismatch_counts": dict(sorted(mismatches.items())),
            "projection_consistent": not missing and not extra and not mismatches,
            "interpretation": "returned-export projection consistency only; not source SQL or join verification"}


def _read_prices(data: bytes) -> tuple[dict[tuple[str, date], dict], dict]:
    headers, rows = _parse_csv(data, "WRDS security prices")
    required = {"secid", "date", "ticker", "index_flag", "open", "close", "cfadj"}
    if not required.issubset(headers):
        raise ValueError("WRDS security prices are missing required fields")
    result, identity, counters = {}, {}, Counter()
    for row in rows:
        sid = row["secid"].strip()
        family = {v: k for k, v in SECURITY_IDS.items()}.get(sid)
        if family is None or row["ticker"].strip() != family or row["index_flag"].strip() != TICKER_FLAGS[family]:
            raise ValueError("WRDS security-price identity conflicts with supplied verified IDs")
        triple = (row["ticker"].strip(), row["index_flag"].strip())
        if sid in identity and identity[sid] != triple:
            raise ValueError("WRDS security-price identity changes within a security ID")
        identity[sid] = triple
        day = iso_day(row["date"].strip(), "security price date")
        key = (sid, day)
        if key in result:
            raise ValueError(f"duplicate WRDS security-price key {sid}/{day}")
        close = _number(row["close"], "raw close", positive=True)
        open_value = _number(row["open"], "raw open", positive=True)
        cfadj = _number(row["cfadj"], "cfadj", positive=True)
        result[key] = {"open": open_value, "close": close, "cfadj": cfadj, "ticker": row["ticker"].strip(), "index_flag": row["index_flag"].strip()}
    return result, {"rows": len(rows), "security_rows": dict(Counter(row["ticker"] for row in rows)), "identities": identity, "return_fields_used": False}


def _read_distributions(data: bytes) -> tuple[list[dict], dict]:
    headers, rows = _parse_csv(data, "WRDS distributions")
    required = {"secid", "record_date", "seq_num", "ex_date", "amount", "adj_factor", "distr_type", "frequency", "currency", "approx_flag", "cancel_flag", "liquid_flag", "ticker", "index_flag"}
    if not required.issubset(headers):
        raise ValueError("WRDS distributions are missing required fields")
    seen, parsed, counters = set(), [], Counter()
    for row in rows:
        if row["secid"].strip() != SECURITY_IDS["SPY"] or row["ticker"].strip() != "SPY" or row["index_flag"].strip() != "0":
            raise ValueError("distribution source contains an unexpected security identity")
        record_date = iso_day(row["record_date"].strip(), "distribution record_date")
        ex_date = iso_day(row["ex_date"].strip(), "distribution ex_date")
        key = (row["secid"].strip(), record_date, row["seq_num"].strip())
        if key in seen:
            raise ValueError("duplicate WRDS distribution identity key")
        seen.add(key)
        try:
            amount = _number(row["amount"], "distribution amount", nonnegative=True)
        except ValueError:
            amount = None
        try:
            adj = _number(row["adj_factor"], "distribution adjustment factor", positive=True)
        except ValueError:
            adj = None
        parsed_row = {"record_date": record_date, "ex_date": ex_date, "seq_num": row["seq_num"].strip(), "amount": amount, "adj_factor": adj,
                      "distr_type": row["distr_type"].strip(), "frequency": row["frequency"].strip(), "currency": row["currency"].strip(),
                      "approx_flag": row["approx_flag"].strip(), "cancel_flag": row["cancel_flag"].strip(), "liquid_flag": row["liquid_flag"].strip()}
        parsed.append(parsed_row)
        counters[f"distr_type:{parsed_row['distr_type']}"] += 1
        counters[f"frequency:{parsed_row['frequency']}"] += 1
        counters[f"currency:{parsed_row['currency']}"] += 1
        counters[f"approx_flag:{parsed_row['approx_flag']}"] += 1
        counters[f"cancel_flag:{parsed_row['cancel_flag']}"] += 1
        counters[f"liquid_flag:{parsed_row['liquid_flag']}"] += 1
        counters["invalid_amount"] += int(amount is None)
        counters["invalid_adj_factor"] += int(adj is None)
    return parsed, {"rows": len(rows), "category_counts": dict(sorted(counters.items())), "coverage": ["2019-08-01", "2025-08-29"]}


def _is_confirmed_cash_dividend(event: dict) -> bool:
    return (event["distr_type"] == "1" and event["frequency"] in {"1", "2", "3", "4", "5"}
            and isinstance(event["amount"], (int, float)) and event["amount"] > 0
            and event["currency"] == "USD" and event["approx_flag"] == "0" and event["cancel_flag"] == "0"
            and event["liquid_flag"] == "0" and event["adj_factor"] == 1.0)


def _read_pm_sources(records: dict[str, dict], period: str) -> tuple[dict[date, dict], dict]:
    if period == "pilot":
        from .expiry_replication import parse_cboe_pm
        counts = Counter()
        w_path = Path(records["pilot_cboe_W"]["path"])
        m_path = Path(records["pilot_cboe_M"]["path"])
        w = parse_cboe_pm(w_path, counts)
        m = parse_cboe_pm(m_path, counts)
        combined = dict(w)
        conflicts = 0
        for day, record in m.items():
            if day in combined and combined[day]["value"] != record["value"]:
                combined.pop(day, None)
                conflicts += 1
            elif day in combined:
                combined[day] = {**combined[day], "sources": sorted(set(combined[day].get("sources", [combined[day]["source"]]) + [record["source"]]))}
            else:
                combined[day] = record
        return combined, {"records": len(combined), "conflicting_dates": conflicts, "source_types": ["legacy W/M HTML"]}
    year = "2024" if period == "primary_2024" else "2025"
    found: dict[date, dict] = {}
    conflicts = set()
    count = 0
    for suffix in ("W", "M", "S"):
        key = f"cboe_{suffix}_{year}.json"
        doc = json.loads(records[key]["data"])
        rows = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            raise ValueError(f"{key} must contain an object with a data list")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{key} contains a malformed row")
            if row.get("trading_symbol") != "SPXW" or row.get("settlement_symbol") != "SPX":
                continue
            day_text = row.get("expiration_date")
            day = iso_day(day_text, f"{key}.expiration_date")
            value = _number(row.get("settlement_value"), "SPXW PM settlement", positive=True)
            count += 1
            identity = {"value": value, "trading_symbol": "SPXW", "settlement_symbol": "SPX", "expiry": day.isoformat(), "source": key}
            if day in found:
                found[day]["sources"].append(key)
                if found[day]["value"] != value:
                    conflicts.add(day)
            else:
                found[day] = {**identity, "sources": [key]}
    for day in conflicts:
        found.pop(day, None)
    return found, {"matching_rows": count, "unique_expiries": len(found), "conflicting_expiries": len(conflicts), "source_types": ["W/M/S JSON data lists"]}


def _source_audit(period: str, frozen: dict, records: dict, sidecars: dict, *, defer_terminal_joins: bool = False) -> dict:
    manifest = frozen["_manifest"]
    raw_role, _, _, control_name = PERIOD_EXPORT[period]
    raw = records[raw_role]["data"]
    source_meta, identity_meta = sidecars["source_metadata"], sidecars["identity_metadata"]
    normalizer_snapshot = {
        "raw_export": records[raw_role],
        "source_metadata": source_meta,
        "identity_metadata": identity_meta,
    }
    normalized = normalizer.normalize(normalizer_snapshot)
    if normalized["status"] != "NORMALIZATION_ONLY":
        return {"status": "SOURCE_AUDIT_BLOCKED", "blockers": ["authenticated web export normalizer rejected this source"], "normalizer": _normalizer_summary(normalized),
                "pair_denominator": {"expected_count": manifest["periods"][period]["expected_count"], "coverage_rows": [], "missing_reference_counts": {}}}
    compressed = raw.startswith(b"\x1f\x8b")
    companion_role = "quotes-2025-through-0828.csv.gz" if period == "primary_2024" else "quotes-2024.csv.gz"
    companion = None if period == "pilot" else records[companion_role]["data"]
    projection = _projection_check(raw, records[control_name]["data"], compressed, companion)
    blockers = []
    if not projection["projection_consistent"]:
        blockers.append("returned-export projection control mismatch")
    quotes = normalized["normalized_rows"]
    price_rows, price_summary = _read_prices(records["security-prices-20190801-20250829.csv"]["data"])
    sessions, official_spx = _read_calendar(records["official_spx_calendar"]["data"])
    pairs = _validate_expected_pairs(manifest["periods"][period], sessions)
    dividends, dividend_summary = _read_distributions(records["distributions-20190801-20250829.csv"]["data"])
    settlements, settlement_summary = _read_pm_sources(records, period)

    quote_keys = Counter()
    identity_by_id = defaultdict(set)
    eligibility = Counter()
    by_entry = defaultdict(Counter)
    roots_present = set()
    for row in quotes:
        key = (row["normalized_security_id"], row["normalized_option_id"], row["normalized_quote_date"])
        quote_keys[key] += 1
        identity_by_id[row["normalized_security_id"]].add((row["normalized_underlying"], row["normalized_exercise_style"]))
        day = iso_day(row["normalized_quote_date"], "normalized quote date")
        root = row["symbol"].split(" ", 1)[0]
        roots_present.add(root)
        if row["normalized_cp_flag"] != "C":
            eligibility["non_call"] += 1
            continue
        if row["normalized_contract_size"] != "100":
            eligibility["contract_size_not_100"] += 1
            continue
        if row["normalized_special_settlement"]:
            eligibility["special_settlement"] += 1
            continue
        try:
            bid = _number(row["normalized_best_bid"], "option bid", positive=True)
            ask = _number(row["normalized_best_offer"], "option ask", positive=True)
            if ask < bid:
                raise ValueError("crossed")
        except ValueError:
            eligibility["unusable_bbo"] += 1
            continue
        if root == "SPX":
            eligibility["consistent_am_spx"] += 1
            continue
        if row["normalized_quote_date"] in {p["entry"].isoformat() for p in pairs}:
            by_entry[day][row["normalized_underlying"]] += 1
    duplicate_count = sum(n - 1 for n in quote_keys.values() if n > 1)
    if duplicate_count:
        blockers.append("duplicate normalized option/session key")
    if any(len(v) != 1 for v in identity_by_id.values()):
        blockers.append("security identity metadata varies within returned export")
    if set(identity_by_id) != set(SECURITY_IDS.values()):
        blockers.append("both verified securities are not represented in normalized rows")
    if not {"SPY", "SPXW"}.issubset(roots_present):
        blockers.append("both SPY and SPXW roots are not represented in standard normalized rows")

    expected_coverage, missing_reference_count = [], Counter()
    quote_dates = {iso_day(r["normalized_quote_date"], "quote date") for r in quotes}
    price_dates = {(sid, day) for sid, day in price_rows}
    for pair in ([] if defer_terminal_joins else pairs):
        entry, expiry, cover = pair["entry"], pair["expiry"], pair["cover"]
        missing = []
        for sid, day, label in ((SECURITY_IDS["SPY"], entry, "spy_entry"), (SECURITY_IDS["SPY"], expiry, "spy_expiry"), (SECURITY_IDS["SPY"], cover, "spy_cover")):
            if (sid, day) not in price_dates:
                missing.append(label)
        for day, label in ((entry, "spx_entry"), (expiry, "spx_expiry")):
            if day not in official_spx:
                missing.append(label)
        if expiry not in settlements:
            missing.append("spxw_pm_settlement")
        if entry not in quote_dates:
            missing.append("option_quote_date")
        for label in missing:
            missing_reference_count[label] += 1
        expected_coverage.append({"entry": entry.isoformat(), "expiry": expiry.isoformat(), "cover": cover.isoformat(), "missing_references": missing})
        for day in sessions:
            if entry <= day <= cover:
                price = price_rows.get((SECURITY_IDS["SPY"], day))
                if price is None or price["cfadj"] != 1.0:
                    if "spy_adjustment_factor_or_session_price" not in missing:
                        missing.append("spy_adjustment_factor_or_session_price")
                        missing_reference_count["spy_adjustment_factor_or_session_price"] += 1
        for event in dividends:
            if entry < event["ex_date"] <= cover:
                if not _is_confirmed_cash_dividend(event):
                    if "unsupported_distribution_event" not in missing:
                        missing.append("unsupported_distribution_event")
                        missing_reference_count["unsupported_distribution_event"] += 1
        expected_coverage[-1]["missing_references"] = missing

    source_integrity = not blockers
    if missing_reference_count:
        source_integrity = False
        blockers.append("expected-period source reference coverage is incomplete")
    if period == "confirmation_2025":
        scope_counts = Counter(row["date"] for row in _parse_csv(raw, "2025 raw export", compressed=True)[1])
        exclusions = {"out_of_period_2025-08-28_rows": int(scope_counts.get("2025-08-28", 0))}
        jan8 = sum(1 for row in _parse_csv(raw, "2025 raw export", compressed=True)[1] if row["date"] == "2025-01-08" and row["exdate"] == "2025-01-09")
        exclusions["off_calendar_2025-01-08_to_2025-01-09_rows"] = jan8
        if exclusions["out_of_period_2025-08-28_rows"] != 595 or exclusions["off_calendar_2025-01-08_to_2025-01-09_rows"] != 322:
            blockers.append("frozen 2025 superset scope exclusion count mismatch")
            source_integrity = False
    else:
        exclusions = {}
    spx_id = SECURITY_IDS["SPX"]
    wrds_spx_close = {day: row["close"] for (sid, day), row in price_rows.items() if sid == spx_id}
    common_spx_days = sorted(set(wrds_spx_close) & set(official_spx))
    spx_differences = [abs(wrds_spx_close[day] - official_spx[day]) for day in common_spx_days]
    settlement_comparisons = [] if defer_terminal_joins else [(official_spx[day], settlements[day]["value"]) for day in settlements if day in official_spx]
    settlement_differences = [abs(a - b) for a, b in settlement_comparisons]
    return {
        "status": "SOURCE_AUDIT_ONLY" if source_integrity else "SOURCE_AUDIT_BLOCKED",
        "historical_evaluation": "NOT RUN", "source_join_sql": "NOT_EXPOSED_BY_WEB_QUERY", "independent_sql_join_verification": "NOT RUN",
        "normalizer": _normalizer_summary(normalized), "projection_control": projection,
        "price_source": price_summary, "distribution_source": dividend_summary, "settlement_source": settlement_summary,
        "source_value_reconciliation": {
            "wrds_spx_close_vs_official_spx_close": {"comparable_dates": len(common_spx_days), "exact_matches": sum(x == 0 for x in spx_differences),
                "different_values": sum(x != 0 for x in spx_differences), "max_absolute_difference": max(spx_differences) if spx_differences else None},
            "official_spx_close_vs_spxw_pm_settlement": {"comparable_expiries": len(settlement_comparisons), "exact_matches": sum(x == 0 for x in settlement_differences),
                "different_values": sum(x != 0 for x in settlement_differences), "max_absolute_difference": max(settlement_differences) if settlement_differences else None,
                "interpretation": "comparison deferred until after selected snapshot" if defer_terminal_joins else "source comparison only; SPX close is not used as SPXW PM settlement"},
        },
        "pair_denominator": {"expected_count": len(pairs), "coverage_rows": expected_coverage, "missing_reference_counts": dict(missing_reference_count), "terminal_coverage_deferred": defer_terminal_joins},
        "raw_superset_exclusions": exclusions, "eligibility_exclusion_counts": dict(sorted(eligibility.items())),
        "entry_quote_date_count": len(quote_dates), "entry_quote_rows_by_expected_day": {d.isoformat(): dict(by_entry[d]) for d in sorted(by_entry)},
        "blockers": blockers, "limitations": SOURCE_LIMITS,
    }


def _normalizer_summary(result: dict) -> dict:
    return {k: result[k] for k in ("status", "row_count", "normalized_count", "excluded_count", "hard_failure_count", "reason_counts", "observed_dates")}


def _records(inputs: dict[str, dict]) -> dict:
    return {role: {k: value[k] for k in ("path", "bytes", "sha256")} for role, value in inputs.items()}


def _snapshots_unchanged(inputs: dict[str, dict]) -> bool:
    for record in inputs.values():
        try:
            data = Path(record["path"]).read_bytes()
        except OSError:
            return False
        if len(data) != record["bytes"] or digest(data) != record["sha256"]:
            return False
    return True


def _runtime_inputs(repo: Path, period: str) -> tuple[dict, dict, dict]:
    protocol_path, manifest_path = repo / PROTOCOL, repo / INPUT_MANIFEST
    protocol_bytes, manifest_bytes = protocol_path.read_bytes(), manifest_path.read_bytes()
    if digest(protocol_bytes) != PROTOCOL_SHA256 or digest(manifest_bytes) != INPUT_MANIFEST_SHA256:
        raise ValueError("frozen protocol or input manifest hash changed")
    manifest = json.loads(manifest_bytes)
    if manifest.get("status") != "FROZEN_INPUTS_AND_COVERAGE_NOT_RUN" or manifest.get("evaluation") != "NOT_RUN":
        raise ValueError("frozen input manifest status changed")
    records = _frozen_files(repo, manifest)
    sidecar = _sidecars(repo, period, records)
    inputs = {"protocol": {"path": str(protocol_path.resolve()), "bytes": len(protocol_bytes), "sha256": digest(protocol_bytes), "data": protocol_bytes},
              "input_manifest": {"path": str(manifest_path.resolve()), "bytes": len(manifest_bytes), "sha256": digest(manifest_bytes), "data": manifest_bytes},
              **records, **sidecar}
    return manifest, records, inputs


def _output_path(repo: Path, out: Path, base: str) -> Path:
    root = repo.resolve(strict=True)
    target = out if out.is_absolute() else repo / out
    resolved = target.absolute().resolve()
    if not resolved.is_relative_to(root) or not resolved.is_relative_to(root / base):
        raise ValueError(f"output must resolve inside ignored {base}/")
    if base == "runs" and not resolved.is_relative_to(root / "runs/optionmetrics_replication"):
        raise ValueError("run output must be under runs/optionmetrics_replication/")
    # Reuse the repository's exact ignore and tracked-path checks for planning/data.
    if base in {"planning", "data"}:
        return _validate_output(resolved, repo)
    rel = resolved.relative_to(root).as_posix()
    if subprocess.run(["git", "check-ignore", "--quiet", "--no-index", "--", rel], cwd=root, check=False).returncode != 0:
        raise ValueError("output path is not ignored by active Git rules")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=root, capture_output=True, check=False)
    if tracked.returncode == 0:
        raise ValueError("output path is tracked")
    return resolved


def _atomic_json(out: Path, payload: dict, inputs: dict[str, dict]) -> str:
    if out.exists():
        raise FileExistsError(f"output already exists: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".optionmetrics-replication-", dir=out.parent))
    try:
        data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
        (stage / out.name).write_bytes(data)
        if not _snapshots_unchanged(inputs):
            raise ValueError("BLOCKED: a source input changed before publication")
        os.rename(stage / out.name, out)
        return digest(data)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def audit_bundle(out: Path, repo: Path, audit: dict, period: str, inputs: dict[str, dict], argv: list[str], code_path: Path) -> None:
    target = _output_path(repo, out, "planning")
    if target.exists():
        raise FileExistsError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not _snapshots_unchanged(inputs):
        raise ValueError("BLOCKED: a source input changed after audit")
    stage = Path(tempfile.mkdtemp(prefix=".optionmetrics-source-audit-", dir=target.parent))
    try:
        finished_utc = datetime.now(timezone.utc).isoformat()
        manifest = {"status": audit["status"], "historical_evaluation": "NOT RUN", "mode": "source-audit", "period": period,
                    "run_started_utc": audit.get("run_started_utc"), "run_ended_utc": finished_utc, "argv": argv, "cwd": str(Path.cwd()), "git": git_info(repo),
                    "code_sha256": digest(code_path.read_bytes()), "protocol_sha256": inputs["protocol"]["sha256"],
                    "input_manifest_sha256": inputs["input_manifest"]["sha256"], "inputs": _records(inputs),
                    "integrity_before": _records(inputs), "integrity_after": _records(inputs),
                    "audit": audit, "outputs": {"audit.json": "written in this bundle"}}
        data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
        (stage / "audit.json").write_bytes(data)
        (stage / "manifest.json").write_text(json.dumps({"audit_sha256": digest(data), "status": audit["status"]}, indent=2) + "\n")
        if not _snapshots_unchanged(inputs):
            raise ValueError("BLOCKED: a source input changed immediately before publication")
        if target.exists():
            raise FileExistsError(f"output already exists: {target}")
        os.rename(stage, target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def select_pairs(quotes: list[dict], pairs: list[dict], spy_prices: dict, spx_prices: dict) -> tuple[list[dict], dict]:
    by_day = defaultdict(list)
    excluded = Counter()
    for row in quotes:
        if row["normalized_cp_flag"] != "C":
            excluded["not_call"] += 1
            continue
        if row["normalized_contract_size"].strip() != "100":
            excluded["contract_size_not_100"] += 1
            continue
        if row["normalized_special_settlement"]:
            excluded["special_settlement"] += 1
            continue
        root = row["symbol"].split(" ", 1)[0]
        if root == "SPX":
            excluded["consistent_am_spx"] += 1
            continue
        try:
            bid = _number(row["normalized_best_bid"], "option bid", positive=True)
            ask = _number(row["normalized_best_offer"], "option ask", positive=True)
        except ValueError:
            excluded["unusable_bbo"] += 1
            continue
        if ask < bid:
            excluded["crossed_bbo"] += 1
            continue
        day = iso_day(row["normalized_quote_date"], "quote date")
        expiry = iso_day(row["normalized_expiry_date"], "expiry date")
        if (expiry - day).days != 1:
            excluded["not_exact_calendar_dte_one"] += 1
            continue
        by_day[day].append(row)
    selected = []
    missing = []
    for pair in pairs:
        entry, expiry = pair["entry"], pair["expiry"]
        spy_ref = spy_prices.get((SECURITY_IDS["SPY"], entry))
        spx_ref = spx_prices.get(entry)
        if not spy_ref or not spx_ref:
            missing.append({**{k: v.isoformat() for k, v in pair.items()}, "reason": "missing official entry reference"})
            continue
        rows = by_day[entry]
        spy_rows = [r for r in rows if r["normalized_underlying"] == "SPY" and r["normalized_exercise_style"] == "A" and r["normalized_am_settlement"] == "0"]
        idx_rows = [r for r in rows if r["normalized_underlying"] == "SPX" and r["normalized_exercise_style"] == "E" and r["normalized_am_settlement"] == "0" and r["symbol"].startswith("SPXW ")]
        for family, candidates in (("SPY", spy_rows), ("SPXW", idx_rows)):
            filtered = [r for r in candidates if r["normalized_expiry_date"] == expiry.isoformat()]
            if family == "SPY":
                filtered = [r for r in filtered if abs(int(r["normalized_strike_milli"]) / 1000 / spy_ref["close"] - 1) <= .02 + 1e-12]
                filtered.sort(key=lambda r: (abs(int(r["normalized_strike_milli"]) / 1000 / spy_ref["close"] - 1), int(r["normalized_strike_milli"]), r["normalized_symbol"]))
                spy_rows = filtered
            else:
                idx_rows = filtered
        if not spy_rows or not idx_rows:
            missing.append({**{k: v.isoformat() for k, v in pair.items()}, "reason": "no eligible SPY or SPXW quote"})
            continue
        spy = spy_rows[0]
        spy_strike = int(spy["normalized_strike_milli"]) / 1000
        candidates = []
        for row in idx_rows:
            strike = int(row["normalized_strike_milli"]) / 1000
            mismatch = abs((strike / spx_ref) / (spy_strike / spy_ref["close"]) - 1)
            if mismatch <= .001 + 1e-12:
                candidates.append((mismatch, strike, row["normalized_symbol"], row))
        if not candidates:
            missing.append({**{k: v.isoformat() for k, v in pair.items()}, "reason": "no SPXW quote within frozen moneyness tolerance"})
            continue
        mismatch, _, _, idx = min(candidates, key=lambda x: x[:3])
        selected.append({"entry": entry.isoformat(), "expiry": expiry.isoformat(), "cover": pair["cover"].isoformat(),
                         "spy": dict(spy), "spxw": dict(idx), "spy_entry_close": spy_ref["close"], "official_spx_entry_close": spx_ref,
                         "moneyness_mismatch": mismatch})
    return selected, {"selected_count": len(selected), "missing_selection_count": len(missing), "missing_selections": missing,
                      "eligibility_exclusion_counts": dict(sorted(excluded.items()))}


def build_fill_rows(pair: dict, refs: dict, dividends: list[dict]) -> tuple[list[dict], dict]:
    spy_row, idx_row = pair["spy"], pair["spxw"]
    spy = Quote(spy_row["normalized_symbol"], "SPY", iso_day(spy_row["normalized_expiry_date"], "expiry"), "call", int(spy_row["normalized_strike_milli"]) / 1000, "A", iso_day(spy_row["normalized_quote_date"], "quote"), float(spy_row["normalized_best_bid"]), float(spy_row["normalized_best_offer"]), pair["spy_entry_close"], "PM")
    idx = Quote(idx_row["normalized_symbol"], "SPXW", iso_day(idx_row["normalized_expiry_date"], "expiry"), "call", int(idx_row["normalized_strike_milli"]) / 1000, "E", iso_day(idx_row["normalized_quote_date"], "quote"), float(idx_row["normalized_best_bid"]), float(idx_row["normalized_best_offer"]), pair["official_spx_entry_close"], "PM")
    entry, expiry, cover = (iso_day(pair[k], k) for k in ("entry", "expiry", "cover"))
    cash_divs = [(event["ex_date"], event["amount"]) for event in dividends if entry < event["ex_date"] <= cover]
    fill_rows = []
    for fill in ("midpoint", "halfway", "full_cross"):
        terms = fill_cash_terms(spy, idx, fill)
        credit = terms["spy_entry_cash"] + terms["spxw_entry_cash"]
        ledger = expiry_ledger(spy=spy, idx=idx, credit=credit, expiry_close=refs["spy_expiry_close"], spxw_settlement=refs["spxw_pm_settlement"], next_open=refs["spy_cover_open"], expiry_date=expiry, entry_date=entry, cover_date=cover, dividends=cash_divs)
        assigned = ledger["assigned"]
        days_exit = (cover - entry).days if assigned else (expiry - entry).days
        days_cover = (cover - expiry).days if assigned else 0
        base = cost_adjusted(ledger["dividend_carry_pnl"], credit, assigned, days_exit, days_cover, refs["spy_expiry_close"])
        stress = cost_adjusted(ledger["dividend_carry_pnl"], credit, assigned, days_exit, days_cover, refs["spy_expiry_close"], stress=True)
        stock_overnight = -1000 * (refs["spy_cover_open"] - refs["spy_expiry_close"]) if assigned else 0.0
        stock_neutralized = ledger["next_open_pnl"] - stock_overnight
        decomposition = ledger["direct_intrinsic_pnl"] + ledger["threshold_residual_cash"] + stock_overnight - ledger["dividend_carry_amount"]
        if abs(decomposition - ledger["dividend_carry_pnl"]) > 1e-8 or abs(stock_neutralized + stock_overnight - ledger["next_open_pnl"]) > 1e-8:
            raise AssertionError("cash decomposition identity failed")
        fill_rows.append({"fill": fill, **terms, "credit": credit, **ledger, "stock_overnight_attribution": stock_overnight,
                          "stock_neutralized_pnl": stock_neutralized, "base_cost_pnl": base, "stress_cost_pnl": stress,
                          "calendar_days_entry_to_exit": days_exit, "calendar_days_expiry_to_cover": days_cover,
                          "decomposition_residual": ledger["dividend_carry_pnl"] - decomposition,
                          "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES", "timing_status": "DAILY_CLOSE_TIMING_MISMATCH_THEORETICAL"})
    reverse_credit = 100 * idx.bid - 1000 * spy.ask
    spy_intrinsic = max(refs["spy_expiry_close"] - spy.strike, 0)
    idx_intrinsic = max(refs["spxw_pm_settlement"] - idx.strike, 0)
    reverse_intrinsic = reverse_credit + 1000 * spy_intrinsic - 100 * idx_intrinsic
    spy_assigned_at_threshold = spy_intrinsic + 1e-10 >= .01
    primary_spy_closemark_cash = (1000 * spy.strike - 1000 * refs["spy_expiry_close"]) if spy_assigned_at_threshold else 0.0
    primary_spxw_closemark_cash = 100 * idx_intrinsic
    reverse_closemark = reverse_credit - primary_spy_closemark_cash - primary_spxw_closemark_cash
    controls = {"reverse_full_cross_credit": reverse_credit, "reverse_intrinsic_control_pnl": reverse_intrinsic,
                "reverse_closemark_control_pnl": reverse_closemark,
                "reverse_spy_closemark_cash": -primary_spy_closemark_cash,
                "reverse_spxw_closemark_cash": -primary_spxw_closemark_cash,
                "primary_assignment_threshold_applied": spy_assigned_at_threshold,
                "primary_threshold_residual_cash": (reverse_intrinsic - reverse_closemark),
                "no_trade_zero_control_pnl": 0.0,
                "reverse_physical_next_open_ledger": "NOT_DEFINED_BY_PROTOCOL"}
    return fill_rows, controls


def _summary(values: list[float]) -> dict:
    vals = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return {"count": len(vals), "mean": statistics.mean(vals) if vals else None, "median": statistics.median(vals) if vals else None,
            "total": sum(vals) if vals else None, "win_fraction": sum(v > 0 for v in vals) / len(vals) if vals else None,
            "min": min(vals) if vals else None, "max": max(vals) if vals else None}


def _q7(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * p
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def aggregate(rows: list[dict], period: str, draws: int = 10_000, seed: int = 20261029) -> dict:
    complete = [row for row in rows if row.get("status") == "COMPLETE_THEORETICAL_ROW"]
    groups = {"all": complete}
    for month in sorted({row["expiry"][:7] for row in complete}):
        groups[month] = [row for row in complete if row["expiry"].startswith(month)]
    metrics = ("direct_intrinsic_pnl", "threshold_residual_cash", "dividend_carry_amount", "dividend_carry_pnl", "base_cost_pnl", "stress_cost_pnl", "stock_neutralized_pnl", "stock_overnight_attribution", "decomposition_residual")
    bootstrap_metrics = ("direct_intrinsic_pnl", "dividend_carry_pnl", "base_cost_pnl", "stress_cost_pnl", "stock_neutralized_pnl", "stock_overnight_attribution")
    output = {}
    for group, subset in groups.items():
        output[group] = {"pair_count": len(subset), "fills": {}}
        for fill in ("midpoint", "halfway", "full_cross"):
            fill_rows = [fr for row in subset for fr in row["fill_rows"] if fr["fill"] == fill]
            output[group]["fills"][fill] = {metric: _summary([fr[metric] for fr in fill_rows]) for metric in metrics}
            output[group]["fills"][fill]["conditional_close_mark_pnl"] = _summary([fr["conditional_close_mark_pnl"] for fr in fill_rows])
            output[group]["fills"][fill]["zero_control_pnl"] = _summary([0.0 for _ in fill_rows])
        output[group]["reverse_controls"] = {metric: _summary([row["controls"][metric] for row in subset]) for metric in ("reverse_intrinsic_control_pnl", "reverse_closemark_control_pnl", "no_trade_zero_control_pnl")}
    boot = {}
    if period != "pilot" and complete:
        clusters = defaultdict(list)
        for row in complete:
            d = iso_day(row["expiry"], "expiry")
            iso = d.isocalendar()
            clusters[f"{iso.year}-W{iso.week:02d}"].append(row)
        weeks = sorted(clusters)
        rng = random.Random(seed)
        draws_by_week = [[rng.choice(weeks) for _ in weeks] for _ in range(draws)]
        for metric in bootstrap_metrics:
            samples = []
            for sampled in draws_by_week:
                values = [fr[metric] for wk in sampled for r in clusters[wk] for fr in r["fill_rows"] if fr["fill"] == "full_cross"]
                samples.append(sum(values) / len(values))
            samples.sort()
            boot[metric] = {"draws": draws, "seed": seed, "iso_week_clusters": len(weeks), "low_95": _q7(samples, .025), "high_95": _q7(samples, .975),
                            "quantile_method": "linear_type_7", "descriptive_only": True}
    return {"status": "DESCRIPTIVE_THEORETICAL_SUMMARIES", "period": period, "cohorts": output,
            "full_cross_iso_week_cluster_bootstrap": boot, "bootstrap_shared_draws_across_metrics": True,
            "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES", "population": "fixed expected expiry pairs; not a portfolio"}


def _period_classification(period: str) -> tuple[str, dict]:
    if period == "pilot":
        return "SOURCE_METHOD_PILOT_THEORETICAL_EVALUATED", {
            "kind": "source_method_pilot", "previously_studied": True, "independent_period": False,
            "description": "Previously studied expiry used for source-method validation."}
    return "NEW_OPTION_PRICE_PERIOD_THEORETICAL_EVALUATED", {
        "kind": "new_option_price_period", "prior_stock_data_and_other_strategy_outcomes_inspected": True,
        "predictive_holdout": False, "globally_untouched": False,
        "description": "New option-price period with known previous stock and other-strategy exposure."}


def _evaluation_rows(selected: list[dict], expected: list[dict], prices: dict, spx: dict, settlements: dict, dividends: list[dict], sessions: set[date] | None = None) -> tuple[list[dict], list[dict]]:
    coverage_rows, outcome_rows = [], []
    for item in expected:
        entry, expiry, cover = (item[k] for k in ("entry", "expiry", "cover"))
        pair = next((x for x in selected if x["entry"] == entry.isoformat()), None)
        missing = []
        if pair is None:
            missing.append("selected_pair")
        spy_entry = prices.get((SECURITY_IDS["SPY"], entry))
        spy_expiry = prices.get((SECURITY_IDS["SPY"], expiry))
        spy_cover = prices.get((SECURITY_IDS["SPY"], cover))
        for record, label in ((spy_entry, "spy_entry_price"), (spy_expiry, "spy_expiry_price"), (spy_cover, "spy_cover_price")):
            if record is None:
                missing.append(label)
        if entry not in spx:
            missing.append("official_spx_entry_close")
        if expiry not in spx:
            missing.append("official_spx_expiry_close")
        settle = settlements.get(expiry)
        if settle is None:
            missing.append("official_spxw_pm_settlement")
        relevant_events = [e for e in dividends if entry < e["ex_date"] <= cover]
        for event in relevant_events:
            if not _is_confirmed_cash_dividend(event):
                missing.append("unsupported_distribution_event")
        action_coverage = iso_day("2019-08-01", "action coverage") <= entry and cover <= iso_day("2025-08-29", "action coverage")
        if not action_coverage:
            missing.append("distribution_coverage_gap")
        session_days = sorted(day for day in (sessions or {entry, expiry, cover}) if entry <= day <= cover)
        for day in session_days:
            stock = prices.get((SECURITY_IDS["SPY"], day))
            if stock is None:
                missing.append("spy_session_price_gap")
            elif stock["cfadj"] != 1.0:
                missing.append("nonunit_spy_cfadj")
        for label, day in (("entry", entry), ("expiry", expiry), ("cover", cover)):
            if day not in session_days:
                missing.append(f"{label}_not_in_session_calendar")
        coverage_rows.append({"entry": entry.isoformat(), "expiry": expiry.isoformat(), "cover": cover.isoformat(), "selected": pair is not None,
                              "complete": not missing, "missing_inputs": sorted(set(missing)), "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES",
                              "distribution_coverage": ["2019-08-01", "2025-08-29"], "relevant_distribution_count": len(relevant_events),
                              "entry_to_expiry_dividend_exposure": any(entry < e["ex_date"] <= expiry for e in relevant_events)})
        if missing or pair is None:
            continue
        refs = {"spy_expiry_close": spy_expiry["close"], "spy_cover_open": spy_cover["open"], "spxw_pm_settlement": settle["value"]}
        fills, controls = build_fill_rows(pair, refs, relevant_events)
        outcome_rows.append({"entry": entry.isoformat(), "expiry": expiry.isoformat(), "cover": cover.isoformat(), "status": "COMPLETE_THEORETICAL_ROW",
                             "spy_contract": pair["spy"]["normalized_symbol"], "spxw_contract": pair["spxw"]["normalized_symbol"],
                             "spy_strike": int(pair["spy"]["normalized_strike_milli"]) / 1000, "spxw_strike": int(pair["spxw"]["normalized_strike_milli"]) / 1000,
                             "official_spx_expiry_close": spx[expiry], "spxw_pm_settlement": settle["value"], "fill_rows": fills, "controls": controls,
                             "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES", "timing_status": "DAILY_CLOSE_TIMING_MISMATCH_THEORETICAL"})
    return coverage_rows, outcome_rows


def _csv_bytes(headers: list[str], rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode()


def run_period(repo: Path, period: str, manifest: dict, records: dict, inputs: dict, argv: list[str], code_path: Path, selection_out: Path, out: Path, run_identity: dict | None = None) -> tuple[str, dict]:
    audit = _source_audit(period, {"_manifest": manifest}, records, {"source_metadata": inputs["source_metadata"], "identity_metadata": inputs["identity_metadata"]}, defer_terminal_joins=True)
    if audit["status"] != "SOURCE_AUDIT_ONLY":
        coverage = [{"entry": row["entry"], "expiry": row["expiry"], "cover": row["cover"], "selected": False, "complete": False,
                     "missing_inputs": ["source_gate_blocked", *audit.get("blockers", [])], "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES"}
                    for row in manifest["periods"][period]["expected_pairs"]]
        return "BLOCKED_SOURCE_AUDIT", {"audit": audit, "historical_evaluation": "NOT RUN", "period": period,
                                        "expected_pairs": len(coverage), "completed_pairs": 0, "coverage": coverage}
    raw_role = PERIOD_EXPORT[period][0]
    norm = normalizer.normalize({"raw_export": records[raw_role], "source_metadata": inputs["source_metadata"], "identity_metadata": inputs["identity_metadata"]})
    prices, _ = _read_prices(records["security-prices-20190801-20250829.csv"]["data"])
    sessions, spx = _read_calendar(records["official_spx_calendar"]["data"])
    expected = _validate_expected_pairs(manifest["periods"][period], sessions)
    identity_checks = {}
    if run_identity is not None:
        identity_checks["before_selection_calculation"] = _check_run_identity(repo, run_identity, inputs)
    selected, selection_info = select_pairs(norm["normalized_rows"], expected, prices, spx)
    if run_identity is not None:
        identity_checks["before_durable_selection"] = _check_run_identity(repo, run_identity, inputs)
    selection = {"status": "SELECTED_NOT_EVALUATED", "historical_evaluation": "NOT RUN", "period": period,
                 "protocol_sha256": inputs["protocol"]["sha256"], "input_manifest_sha256": inputs["input_manifest"]["sha256"],
                 "selected_pairs": selected, "selection": selection_info, "inputs": _records(inputs), "git": git_info(repo),
                 "selected_utc": datetime.now(timezone.utc).isoformat(), "argv": argv, "code_sha256": digest(code_path.read_bytes()),
                 "limitations": SOURCE_LIMITS + ["Selections were made from entry observations only. Terminal values were not used."]}
    if run_identity is not None:
        selection["initial_run_identity"] = {"head": run_identity["initial_head"], "code_sha256": {k: v["sha256"] for k, v in run_identity["code"].items()}}
    selection_hash = _atomic_json(selection_out, selection, inputs)
    selection_record = {"path": str(selection_out.resolve()), "bytes": selection_out.stat().st_size, "sha256": selection_hash}
    if run_identity is not None:
        identity_checks["after_selection_before_terminal_use"] = _check_run_identity(repo, run_identity, inputs, selection_out, selection_hash)
    # The source audit parses terminal files for source checks. Contract joins and payoff calculations happen only after selection is durable.
    settlements, _ = _read_pm_sources(records, period)
    dividends, _ = _read_distributions(records["distributions-20190801-20250829.csv"]["data"])
    if run_identity is not None:
        identity_checks["before_calculation"] = _check_run_identity(repo, run_identity, inputs, selection_out, selection_hash)
    coverage, outcomes = _evaluation_rows(selected, expected, prices, spx, settlements, dividends, sessions)
    complete = len(outcomes) == len(expected) and all(row["complete"] for row in coverage)
    if not complete:
        return "PREPARED_COVERAGE_BLOCKED", {"historical_evaluation": "NOT RUN", "period": period, "coverage": coverage,
                                             "expected_pairs": len(expected), "completed_pairs": len(outcomes), "selection": selection_info,
                                             "source_audit": audit, "selection_snapshot": selection_record,
                                             "blockers": ["required selections or terminal coverage are missing"], "inputs": _records(inputs)}
    for row in outcomes:
        if len(row["fill_rows"]) != 3:
            raise AssertionError("a complete pair must contain exactly three primary fill rows")
    evaluated_status, period_classification = _period_classification(period)
    result = {"status": evaluated_status, "historical_evaluation": "RAN", "period": period,
              "coverage": coverage, "outcomes": outcomes, "summary": aggregate(outcomes, period), "source_audit": audit,
              "selection_snapshot": selection_record,
              "period_classification": period_classification,
              "integrity_checks": identity_checks,
              "integrity_before": _records(inputs),
              "historical_evaluation_limitations": SOURCE_LIMITS + ["This is a daily-close theoretical diagnostic, not an ex-ante or executable result."]}
    return "EVALUATED", result


def publish_run(repo: Path, out: Path, status: str, payload: dict, inputs: dict[str, dict], argv: list[str], code_path: Path, run_identity: dict | None = None) -> dict:
    if status != "EVALUATED":
        raise ValueError("only a complete successful run can publish under runs/")
    target = _output_path(repo, out, "runs")
    if target.exists():
        raise FileExistsError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".optionmetrics-run-", dir=target.parent))
    try:
        outputs = {
            "source_audit.json": (json.dumps(payload["source_audit"], indent=2, sort_keys=True) + "\n").encode(),
            "coverage.csv": _csv_bytes(["entry", "expiry", "cover", "selected", "complete", "missing_inputs", "depth_status"], [{**row, "missing_inputs": ";".join(row["missing_inputs"])} for row in payload["coverage"]]),
            "outcomes.json": (json.dumps(payload["outcomes"], indent=2, sort_keys=True) + "\n").encode(),
            "summary.json": (json.dumps(payload["summary"], indent=2, sort_keys=True) + "\n").encode(),
        }
        (stage / "source_audit.json").write_bytes(outputs["source_audit.json"])
        (stage / "coverage.csv").write_bytes(outputs["coverage.csv"])
        (stage / "outcomes.json").write_bytes(outputs["outcomes.json"])
        (stage / "summary.json").write_bytes(outputs["summary.json"])
        code_hash = digest(code_path.read_bytes())
        if run_identity is not None:
            publication_check = _check_run_identity(repo, run_identity, inputs)
        else:
            publication_check = {"verified": False, "reason": "no initial run identity supplied"}
        selection_path = Path(payload["selection_snapshot"]["path"])
        selection_bytes = selection_path.read_bytes()
        if len(selection_bytes) != payload["selection_snapshot"]["bytes"] or digest(selection_bytes) != payload["selection_snapshot"]["sha256"]:
            raise ValueError("BLOCKED: durable selected snapshot changed before run publication")
        start_utc = payload["run_started_utc"]
        end_utc = datetime.now(timezone.utc).isoformat()
        metadata = {"status": payload["status"], "historical_evaluation": payload["historical_evaluation"], "period": payload["period"],
                    "run_started_utc": start_utc, "run_ended_utc": end_utc, "argv": argv, "cwd": str(Path.cwd()),
                    "host": os.uname().nodename, "python": sys.version, "python_executable": sys.executable, "PYTHONPATH": os.environ.get("PYTHONPATH"),
                    "git": {"sha": run_identity["initial_head"], "clean": True}, "initial_run_identity": {"head": run_identity["initial_head"], "clean": True},
                    "code_sha256": code_hash, "protocol_sha256": inputs["protocol"]["sha256"],
                    "input_manifest_sha256": inputs["input_manifest"]["sha256"], "inputs": _records(inputs),
                    "integrity_before": payload.get("integrity_before", _records(inputs)), "integrity_after": _records(inputs),
                    "integrity_checks": {**payload.get("integrity_checks", {}), "before_publication": publication_check},
                    "code_integrity_before": {role: record["sha256"] for role, record in run_identity["code"].items()} if run_identity else {},
                    "code_integrity_after": publication_check.get("code_sha256", {}),
                    "head_integrity": {"initial": run_identity["initial_head"], "before_publication": publication_check.get("head"), "verified": publication_check.get("verified", False)},
                    "selection_snapshot": payload["selection_snapshot"],
                    "period_classification": payload["period_classification"],
                    "model_endpoint": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION", "model_identity": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION",
                    "code_hashes": {role: record["sha256"] for role, record in inputs.items() if role.startswith("code_")},
                    "source_join_sql": "NOT_EXPOSED_BY_WEB_QUERY", "independent_sql_join_verification": "NOT RUN",
                    "output_sha256": {name: digest(data) for name, data in outputs.items()}, "limitations": payload["historical_evaluation_limitations"]}
        manifest_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()
        (stage / "manifest.json").write_bytes(manifest_bytes)
        if run_identity is None:
            raise ValueError("BLOCKED: run publication requires initial HEAD and code identity")
        selection_check = selection_path.read_bytes()
        if len(selection_check) != payload["selection_snapshot"]["bytes"] or digest(selection_check) != payload["selection_snapshot"]["sha256"]:
            raise ValueError("BLOCKED: durable selected snapshot changed immediately before run publication")
        selection_check = _check_run_identity(repo, run_identity, inputs, selection_path, payload["selection_snapshot"]["sha256"])
        metadata["integrity_checks"]["immediately_before_publication"] = selection_check
        metadata["integrity_checks"]["before_publication"] = selection_check
        metadata["head_integrity"]["before_publication"] = selection_check["head"]
        metadata["head_integrity"]["verified"] = selection_check["verified"]
        metadata["code_integrity_after"] = selection_check["code_sha256"]
        metadata["integrity_after"] = _records(inputs)
        manifest_bytes = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()
        (stage / "manifest.json").write_bytes(manifest_bytes)
        _check_run_identity(repo, run_identity, inputs, selection_path, payload["selection_snapshot"]["sha256"])
        if target.exists():
            raise FileExistsError(f"output already exists: {target}")
        os.rename(stage, target)
        return {"output_sha256": {**metadata["output_sha256"], "manifest.json": digest(manifest_bytes)}}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source-audit", "run"))
    parser.add_argument("--period", choices=tuple(PERIOD_EXPORT), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--selection-out", type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    command = [sys.argv[0], *(argv if argv is not None else sys.argv[1:])]
    try:
        started = datetime.now(timezone.utc).isoformat()
        run_identity = None
        if args.mode == "run":
            run_identity = _capture_run_identity(repo, args.period)
            selection_out = args.selection_out or repo / "planning/optionmetrics-20261029/selected-snapshots" / f"{args.period}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            selection_out = _output_path(repo, selection_out, "planning")
            _output_path(repo, args.out, "runs")
        manifest_path = repo / INPUT_MANIFEST
        manifest_raw = manifest_path.read_bytes()
        if digest(manifest_raw) != INPUT_MANIFEST_SHA256:
            raise ValueError("frozen input manifest hash changed")
        manifest = json.loads(manifest_raw)
        if digest((repo / PROTOCOL).read_bytes()) != PROTOCOL_SHA256:
            raise ValueError("frozen protocol hash changed")
        frozen = _frozen_files(repo, manifest)
        sidecars = _sidecars(repo, args.period, frozen)
        inputs = {"protocol": {"path": str((repo / PROTOCOL).resolve()), "bytes": (repo / PROTOCOL).stat().st_size, "sha256": PROTOCOL_SHA256, "data": (repo / PROTOCOL).read_bytes()},
                  "input_manifest": {"path": str(manifest_path.resolve()), "bytes": len(manifest_raw), "sha256": digest(manifest_raw), "data": manifest_raw}, **frozen, **sidecars}
        if run_identity is not None:
            for role, record in run_identity["code"].items():
                inputs[role] = {k: record[k] for k in ("path", "bytes", "sha256", "data")}
        else:
            for role, relative in RUN_CODE_PATHS.items():
                if role == "code_legacy_pilot_parser" and args.period != "pilot":
                    continue
                path = (repo / relative).resolve(strict=True)
                data = path.read_bytes()
                inputs[role] = {"path": str(path), "bytes": len(data), "sha256": digest(data), "data": data}
        code_path = (repo / RUN_CODE_PATHS["code_replication"]).resolve(strict=True)
        if args.mode == "source-audit":
            result = _source_audit(args.period, {"_manifest": manifest}, frozen, sidecars)
            result["run_started_utc"] = started
            result["git"] = {**git_info(repo), "classification": "SOURCE_AUDIT_ONLY", "dirty_tree_allowed": True}
            audit_bundle(args.out, repo, result, args.period, inputs, command, Path(__file__))
            print(f"{result['status']}: period={args.period} expected={result['pair_denominator']['expected_count']} blockers={len(result['blockers'])}")
            return 0 if result["status"] == "SOURCE_AUDIT_ONLY" else 2
        status, result = run_period(repo, args.period, manifest, frozen, inputs, command, code_path, selection_out, args.out, run_identity)
        result["run_started_utc"] = started
        if status == "EVALUATED":
            publication = publish_run(repo, args.out, status, result, inputs, command, code_path, run_identity)
            print(f"{status}: period={args.period} complete={len(result['outcomes'])} outputs={len(publication['output_sha256'])}")
            return 0
        out_plan = repo / "planning/optionmetrics-20261029/prepared-coverage" / f"{args.period}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        _atomic_json(_output_path(repo, out_plan, "planning"), result, inputs)
        print(f"{status}: period={args.period} coverage_rows={len(result.get('coverage', []))} historical_evaluation=NOT RUN")
        return 2
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr); return 4
    except (OSError, ValueError, TypeError, KeyError, csv.Error, gzip.BadGzipFile) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
