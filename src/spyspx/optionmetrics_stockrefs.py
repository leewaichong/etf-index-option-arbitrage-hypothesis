"""Source checks and lead-gated evaluation for frozen SPY stock references."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import random
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath

from . import optionmetrics_replication as source
from . import expiry_replication as legacy2019
from .expiry_extension import cost_adjusted, expiry_ledger, fill_cash_terms
from .expiry_payoff import Quote
from .expiry_payoff_source import read_zip as read_2022_quotes

LANE_2022 = "lane4_official_reselection"
POPULATION_2022 = "primary_one_per_expiry"
FILLS = ("midpoint", "halfway", "full_cross")
ARMS = (
    "baseline_old_all",
    "wrds_expiry_close_only",
    "wrds_cover_open_only",
    "wrds_dividends_only",
    "wrds_all",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LOCAL_INPUT_ROOT = REPOSITORY_ROOT / "data/expiry-payoff/stockrefs"
WRDS_ROOT = Path(os.environ.get("SPYSPX_STOCKREFS_WRDS_ROOT", LOCAL_INPUT_ROOT / "wrds"))
LEGACY_ROOT = Path(os.environ.get("SPYSPX_STOCKREFS_LEGACY_RUNS", LOCAL_INPUT_ROOT / "legacy-runs"))
CALENDAR = Path(os.environ.get("SPYSPX_STOCKREFS_CALENDAR", LOCAL_INPUT_ROOT / "calendar/SPX_History.csv"))
LEGACY_2019_ROOT = Path(os.environ.get("SPYSPX_STOCKREFS_LEGACY_2019_ROOT", LOCAL_INPUT_ROOT / "legacy-2019"))
OFFICIAL_EXTENSION_ROOT = Path(os.environ.get("SPYSPX_STOCKREFS_OFFICIAL_ROOT", LOCAL_INPUT_ROOT / "official-extension"))
CODE_ROOT = Path(os.environ.get("SPYSPX_STOCKREFS_CODE_ROOT", REPOSITORY_ROOT))
PROTOCOL_PATH = Path("planning/optionmetrics-stockrefs-20261029/candidate-protocol.md")
INPUT_MANIFEST_PATH = Path("planning/optionmetrics-stockrefs-20261029/input-manifest.json")
LEDGER_TOLERANCE = 1e-8
SUMMARY_TOLERANCE = 1e-7
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = 20261029
METRICS = ("direct_intrinsic_pnl", "conditional_close_mark_pnl", "next_open_pnl",
           "dividend_carry_pnl", "base_nondividend_cost_pnl", "stress_nondividend_cost_pnl",
           "base_dividend_cost_pnl", "stress_dividend_cost_pnl", "base_cost_pnl", "stress_cost_pnl",
           "stock_neutralized_pnl", "stock_neutralized_base_cost_pnl","stock_neutralized_stress_cost_pnl",
           "stock_overnight_attribution","reverse_terminal_intrinsic_control_pnl","zero_control_pnl")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: Path, expected_hash: str | None = None) -> dict:
    path = path.resolve(strict=True)
    data = path.read_bytes()
    digest = sha256(data)
    if expected_hash is not None and digest != expected_hash:
        raise ValueError(f"frozen source hash mismatch: {path}")
    return {"path": str(path), "bytes": len(data), "sha256": digest}


def read_stock_references(data: bytes) -> tuple[dict[date, dict], dict]:
    """Return SPY raw open/close rows using the established strict parser."""
    parsed, diagnostics = source._read_prices(data)
    result = {}
    for (secid, day), row in parsed.items():
        if secid != source.SECURITY_IDS["SPY"]:
            continue
        if not all(math.isfinite(float(row[k])) and float(row[k]) > 0 for k in ("open", "close")):
            raise ValueError(f"invalid SPY raw reference on {day}")
        if row["cfadj"] != 1.0:
            raise ValueError(f"non-unit SPY cfadj on {day}")
        result[day] = {"open": float(row["open"]), "close": float(row["close"])}
    if not result:
        raise ValueError("WRDS source contains no SPY stock rows")
    return result, diagnostics


def read_cash_dividends(data: bytes) -> tuple[list[dict], dict]:
    """Return supported regular USD cash distributions without rounding."""
    rows, diagnostics = source._read_distributions(data)
    relevant = []
    for row in rows:
        if source._is_confirmed_cash_dividend(row):
            # Preserve the source's full numeric precision, including 1.5964.
            relevant.append({"ex_date": row["ex_date"], "amount": float(row["amount"])})
    relevant.sort(key=lambda item: (item["ex_date"], item["amount"]))
    return relevant, diagnostics


def _confirmed_events(data: bytes) -> tuple[list[dict], dict]:
    events, diagnostics = source._read_distributions(data)
    return [{**event, "supported": source._is_confirmed_cash_dividend(event)} for event in events], diagnostics


def load_fixed_legacy() -> tuple[dict, list[dict], dict, list[dict]]:
    """Load only original, fixed pairs and their three authentic entry fills."""
    run22 = LEGACY_ROOT / "expiry_extension/20261028T114142711970Z"
    run19 = LEGACY_ROOT / "expiry_replication/20261028T125023997117Z"
    manifest22_bytes = (run22 / "manifest.json").read_bytes()
    pairs22_bytes = (run22 / "pair_rows.json").read_bytes()
    manifest19_bytes = (run19 / "manifest.json").read_bytes()
    pairs19_bytes = (run19 / "pair_rows.json").read_bytes()
    if sha256(manifest22_bytes) != "fc60f968f262cd53ff32f2a6aedc1f959cbed40a0eb23a8b86acaaf01170d816":
        raise ValueError("2022 legacy manifest hash changed")
    if sha256(pairs22_bytes) != "5a6e4e3f75244ec4e6f2119f46725746630eb467959dd8d440ed946baf29a2df":
        raise ValueError("2022 legacy pair-row hash changed")
    if sha256(manifest19_bytes) != "b695ac5474e8f40c2d904604abd1358069e3036b70c7d566fde686e3d3d8ca4f":
        raise ValueError("2019 legacy manifest hash changed")
    if sha256(pairs19_bytes) != "64d7ca81b391e4bb8fb557a860abb8bddcd90633f188ee4c0b69004270c102a4":
        raise ValueError("2019 legacy pair-row hash changed")
    m22 = json.loads(manifest22_bytes)
    m19 = json.loads(manifest19_bytes)
    if m22.get("git_sha") != "b97816d637d524c58f1f8d9c87b6a9a41ca02bc1":
        raise ValueError("2022 legacy control SHA changed")
    if m19.get("snapshot_before", {}).get("git_sha") != "63b3b65d00b5b895e819c8ae3e50904deb8610f2":
        raise ValueError("2019 legacy control SHA changed")
    rows22 = json.loads(pairs22_bytes)
    rows22 = [r for r in rows22 if r.get("lane") == LANE_2022 and r.get("population") == POPULATION_2022]
    rows19_all = json.loads(pairs19_bytes)
    rows19 = [r for r in rows19_all if r.get("reference_lane") == "PRIMARY_YAHOO_RAW_SPY_CLOSE"]
    if len(rows22) != 189 or len(rows19) != 9:
        raise ValueError("fixed legacy pair/fill population does not match the frozen design")
    by_expiry = {}
    for row in rows22:
        expiry = row.get("expiry_date")
        if not expiry or row.get("fill") not in FILLS:
            raise ValueError("2022 legacy row lacks fixed expiry or fill identity")
        by_expiry.setdefault(expiry, set()).add(row["fill"])
    if len(by_expiry) != 63 or any(fills != set(FILLS) for fills in by_expiry.values()):
        raise ValueError("2022 legacy controls do not contain 63 fixed pairs and three fills")
    for row in rows19:
        expiry = row.get("expiry_date")
        fills = {fr.get("fill") for fr in row.get("fill_rows", [])}
        if not expiry or fills != set(FILLS):
            raise ValueError("2019 legacy control lacks its fixed pair or three fills")
    return m22, rows22, m19, rows19


def source_audit(root: Path = WRDS_ROOT, calendar: Path = CALENDAR) -> dict:
    """Audit the frozen WRDS files against fixed legacy stock dates only."""
    price_path = root / "security-prices-20190801-20250829.csv"
    dividend_path = root / "distributions-20190801-20250829.csv"
    prices, price_diag = read_stock_references(price_path.read_bytes())
    dividends, dividend_diag = _confirmed_events(dividend_path.read_bytes())
    m22, rows22, m19, rows19 = load_fixed_legacy()
    days22 = {date.fromisoformat(r["entry_date"]) for r in rows22}
    days22 |= {date.fromisoformat(r["expiry_date"]) for r in rows22}
    days22 |= {date.fromisoformat(r["next_session_date"]) for r in rows22}
    days19 = {date.fromisoformat(r["entry_date"]) for r in rows19}
    days19 |= {date.fromisoformat(r["expiry_date"]) for r in rows19}
    days19 |= {date.fromisoformat(r["next_session_date"]) for r in rows19}
    expected = days19 | days22
    missing = sorted(day.isoformat() for day in expected - prices.keys())
    if missing:
        raise ValueError(f"WRDS stock reference coverage missing fixed dates: {missing}")
    # Read and hash the independent calendar; never derive or alter pair dates.
    calendar_record = _record(calendar, "119e2d6a02b6472562353b4bf4e14ab0cf13d9a0a0b67abdf85b993364b23a74")
    return {
        "status": "SOURCE_AUDIT_ONLY_NOT_RUN",
        "wrds_files": {
            "security_prices": _record(price_path, "e6af1f0e5dd22683d7e71054c18b7c448474baf3b6644a2f414a0e1d3aa57de1"),
            "distributions": _record(dividend_path, "29f8201b5150a78d807f95c9cff691bcd4e586edb566a8c69e140d2b71f951d1"),
        },
        "calendar": calendar_record,
        "legacy_controls": {
            "2022_manifest_sha256": "fc60f968f262cd53ff32f2a6aedc1f959cbed40a0eb23a8b86acaaf01170d816",
            "2022_fixed_rows": len(rows22), "2022_stock_dates": len(days22),
            "2019_manifest_sha256": "b695ac5474e8f40c2d904604abd1358069e3036b70c7d566fde686e3d3d8ca4f",
            "2019_fixed_pairs": len(rows19), "2019_stock_dates": len(days19),
        },
        "stock_source": {"rows": len(prices), "covered_fixed_dates": len(expected), "missing_dates": missing,
                         "parser": price_diag, "cfadj": "1 on all retained SPY rows", "raw_open_close_only": True},
        "dividend_source": {"parser": dividend_diag,
                            "fixed_window_events": [{"ex_date": x["ex_date"].isoformat(), "amount": x["amount"],
                                                     "supported": x["supported"]} for x in dividends
                                                    if any(min(days) < x["ex_date"] <= max(days) for days in (days19, days22))]},
        "predeclared_arms": list(ARMS),
        "outcomes_calculated": False,
    }


def _float(value, field: str, *, positive: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} is not numeric") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"{field} is not finite or positive")
    return result


def _read_old_2022_stocks(path: Path, yahoo_path: Path) -> tuple[dict, dict]:
    """Read original SPY raw bars and dividends, then the Yahoo boundary bar."""
    result = {}
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name == "day_by_symbol/SPY_day.csv"]
        if len(members) != 1:
            raise ValueError("2022 stock archive must have one SPY_day.csv")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            if not {"date", "open", "close", "dividend"}.issubset(reader.fieldnames or []):
                raise ValueError("2022 SPY stock archive schema is incomplete")
            for row in reader:
                day = date.fromisoformat(row["date"])
                dividend = 0.0 if not (row.get("dividend") or "").strip() else _float(row["dividend"], "legacy dividend")
                item = {"open": _float(row["open"], "legacy SPY open", positive=True),
                        "close": _float(row["close"], "legacy SPY close", positive=True), "dividend": dividend}
                if day in result:
                    raise ValueError(f"duplicate legacy SPY stock date {day}")
                result[day] = item
    class YahooPayloadView:
        """Supply the legacy reader's empty split calendar when Yahoo omitted it."""
        def read_text(self, encoding="utf-8"):
            document = json.loads(Path(yahoo_path).read_text(encoding=encoding))
            try:
                result = document["chart"]["result"][0]
                events = result.get("events")
                if isinstance(events, dict) and "splits" not in events and isinstance(events.get("dividends"), dict):
                    events["splits"] = {}
            except (KeyError, IndexError, TypeError):
                pass
            return json.dumps(document)

    yahoo_rows, yahoo_dividends = legacy2019.read_yahoo(YahooPayloadView(), Counter())
    following = sorted(day for day in yahoo_rows if day > max(result))
    if not following:
        raise ValueError("2022 Yahoo boundary has no session after original stock bars")
    boundary = following[0]
    boundary_dividend = sum(amount for day, amount in yahoo_dividends if day == boundary)
    result[boundary] = {**yahoo_rows[boundary], "dividend": boundary_dividend}
    return result, {"boundary_date": boundary.isoformat(), "source": str(yahoo_path)}


def _read_2022_settlements(paths: tuple[Path, Path, Path]) -> dict[date, float]:
    """Apply the original CBOE W/M/S row identity, ordering and conflict checks."""
    if len(paths)!=3: raise ValueError("2022 SPXW settlement sources must be W, M and S files")
    expected_counts=(115,6,6)
    h2_start,h2_end=date(2022,7,1),date(2022,12,30)
    by_date={};conflicts=set()
    for label,path,expected_count in zip(("W","M","S"),paths,expected_counts):
        doc=json.loads(path.read_text())
        records=doc.get("data",doc.get("results",[])) if isinstance(doc,dict) else doc
        local={};local_conflicts=set()
        for row in records:
            if row.get("trading_symbol")!="SPXW" or row.get("settlement_symbol")!="SPX": continue
            try:
                day=date.fromisoformat(row["expiration_date"])
            except (KeyError,ValueError,TypeError) as exc:
                raise ValueError(f"invalid {label} SPXW settlement date") from exc
            if not h2_start<=day<=h2_end: continue
            description=row.get("description")
            try:
                value=_float(row["settlement_value"],"SPXW PM settlement",positive=True)
                order=int(row["display_order"])
            except (KeyError,ValueError,TypeError) as exc:
                local_conflicts.add(day)
                continue
            if not isinstance(description,str) or not description.strip():
                local_conflicts.add(day);continue
            identity=(description,row["trading_symbol"],day,row["settlement_symbol"],value,order)
            if day in local_conflicts: continue
            if day in local and local[day]!=identity: local_conflicts.add(day)
            else: local[day]=identity
        for day in local_conflicts:local.pop(day,None)
        if len(local)!=expected_count:
            raise ValueError(f"{label} 2022 settlement coverage is {len(local)}, expected {expected_count}")
        for day,identity in local.items():
            if day in conflicts:continue
            if day in by_date and by_date[day]!=identity:
                conflicts.add(day);by_date.pop(day,None)
            else:by_date[day]=identity
    if conflicts: raise ValueError(f"conflicting 2022 SPXW PM settlement dates: {sorted(conflicts)}")
    if len(by_date)!=127: raise ValueError(f"2022 SPXW PM settlement union is {len(by_date)}, expected 127")
    return {day:identity[4] for day,identity in by_date.items()}


def _source_inventory() -> tuple[dict, dict]:
    """Verify original receipt records, WRDS extracts, and the independent calendar."""
    run22 = LEGACY_ROOT / "expiry_extension/20261028T114142711970Z"
    run19 = LEGACY_ROOT / "expiry_replication/20261028T125023997117Z"
    m22 = json.loads((run22 / "manifest.json").read_text())
    m19 = json.loads((run19 / "manifest.json").read_text())
    inventory = {}
    for key, records, fallback_root in (
        ("2022", m22["snapshot_before"]["files"], None),
        ("2019", m19["snapshot_before"]["inputs"], LEGACY_2019_ROOT),
    ):
        for name, record in records.items():
            raw_path = record.get("path")
            manifest_key = Path(name)
            if raw_path:
                path = Path(raw_path)
                if manifest_key.is_absolute() and path.resolve() != manifest_key.resolve():
                    raise ValueError(f"ambiguous original source receipt path: {key}/{name}")
            elif manifest_key.is_absolute():
                path = manifest_key
            elif fallback_root is not None:
                path = fallback_root / manifest_key
            else:
                raise ValueError(f"original receipt has no unambiguous path: {key}/{name}")
            if not path.is_file():
                raise ValueError(f"required original source receipt is unavailable: {key}/{name}")
            actual = _record(path)
            if actual["bytes"] != record["bytes"] or actual["sha256"] != record["sha256"]:
                raise ValueError(f"original source receipt mismatch: {key}/{name}")
            inventory[f"original_receipt:{key}:{name}"] = actual
    if sum(name.startswith("original_receipt:") for name in inventory) != 19:
        raise ValueError("expected exactly 19 original source receipt records")
    code_root = CODE_ROOT
    for label, manifest, root, records_key in (
        ("2022", m22, code_root, "extension_sha256"),
        ("2019", m19, code_root, "code_sha256"),
    ):
        snap = manifest["snapshot_before"]
        records = snap.get(records_key, {})
        if not isinstance(records, dict): raise ValueError(f"invalid frozen legacy code inventory: {label}")
        for relative, record in records.items():
            path = (root / relative).resolve(strict=True)
            actual = _record(path)
            expected_hash = record.get("sha256") if isinstance(record, dict) else record
            expected_bytes = record.get("bytes") if isinstance(record, dict) else None
            if actual["sha256"] != expected_hash or (expected_bytes is not None and actual["bytes"] != expected_bytes):
                raise ValueError(f"legacy implementation source changed: {label}/{relative}")
            inventory[f"legacy_code:{label}:{relative}"] = actual
    if sum(name.startswith("legacy_code:") for name in inventory) != 8:
        raise ValueError("expected exactly eight frozen legacy code records")
    for relative, expected_hash in m22["snapshot_before"].get("dependency_sha256", {}).items():
        path = (code_root / relative).resolve(strict=True)
        actual = _record(path)
        if actual["sha256"] != expected_hash:
            raise ValueError(f"frozen 2022 dependency changed: {relative}")
        inventory[f"legacy_dependency:2022:{relative}"] = actual
    if len([key for key in inventory if key.startswith("legacy_dependency:")]) != 2:
        raise ValueError("expected two frozen 2022 dependency records")
    for label, run in (("2022", run22), ("2019", run19)):
        for name in ("manifest.json", "pair_rows.json", "aggregates.json"):
            inventory[f"control_artifact:{label}:{name}"] = _record(run / name)
    wrds = {
        "security_prices": _record(WRDS_ROOT / "security-prices-20190801-20250829.csv", "e6af1f0e5dd22683d7e71054c18b7c448474baf3b6644a2f414a0e1d3aa57de1"),
        "distributions": _record(WRDS_ROOT / "distributions-20190801-20250829.csv", "29f8201b5150a78d807f95c9cff691bcd4e586edb566a8c69e140d2b71f951d1"),
        "independent_calendar": _record(CALENDAR, "119e2d6a02b6472562353b4bf4e14ab0cf13d9a0a0b67abdf85b993364b23a74"),
    }
    return inventory, wrds


def _read_fixed_2019_quotes(path: Path, required: dict[date, dict[str, date]]) -> tuple[dict, dict]:
    """Read only frozen 2019 entry contracts from their original daily files."""
    wanted_names = {f"L2_options_{day:%Y%m%d}.csv": day for day in required}
    matches = defaultdict(list)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            basename = info.filename.rsplit("/", 1)[-1]
            if basename not in wanted_names:
                continue
            parts = PurePosixPath(info.filename).parts
            if (len(parts) != 1 or parts[0] != info.filename or "\\" in info.filename or
                    info.filename.startswith("/") or ".." in parts or info.is_dir()):
                raise ValueError(f"unsafe fixed 2019 option member: {info.filename}")
            matches[wanted_names[basename]].append(info)

        selected = {}
        rows_scanned = 0
        for day, contracts in required.items():
            members = matches.get(day, [])
            if len(members) != 1:
                raise ValueError(f"fixed 2019 option member count for {day} is {len(members)}, expected one")
            info = members[0]
            with archive.open(info) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                if tuple(reader.fieldnames or ()) != legacy2019.OPTION_FIELDS:
                    raise ValueError(f"fixed 2019 option schema mismatch for {day}")
                for row in reader:
                    rows_scanned += 1
                    symbol = (row.get("OptionSymbol") or "").strip().upper()
                    expiry = contracts.get(symbol)
                    if expiry is None:
                        continue

                    try:
                        filename_day = datetime.strptime(
                            info.filename.removeprefix("L2_options_").removesuffix(".csv"), "%Y%m%d").date()
                    except (ValueError, AttributeError) as exc:
                        raise ValueError(f"invalid fixed 2019 option filename date: {info.filename}") from exc
                    if filename_day != day:
                        raise ValueError(f"fixed 2019 option filename date mismatch for {day}")
                    try:
                        data_day = legacy2019._date(row["DataDate"])
                        row_expiry = legacy2019._date(row["Expiration"])
                        underlying = row["UnderlyingSymbol"].strip().upper()
                        aka = row["AKA"].strip().upper()
                        option_type = row["Type"].strip().lower()
                        osi = legacy2019.OSI.fullmatch(symbol)
                        if not osi:
                            raise ValueError("selected OptionSymbol is not valid OSI")
                        osi_root, ymd, right, strike_milli = osi.groups()
                        osi_expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:]))
                        strike = _float(row["Strike"], "2019 selected strike", positive=True)
                        bid = _float(row["Bid"], "2019 selected bid", positive=True)
                        ask = _float(row["Ask"], "2019 selected ask", positive=True)
                        underlying_price = _float(row["UnderlyingPrice"], "2019 selected underlying", positive=True)
                    except (KeyError, TypeError, ValueError, OverflowError) as exc:
                        raise ValueError(f"invalid selected 2019 option row {symbol} on {day}: {exc}") from exc

                    expected_root = "SPY" if symbol.startswith("SPY") else "SPXW"
                    if (data_day != day or row_expiry != expiry or underlying != expected_root or
                            osi_root != expected_root or aka != symbol or osi_expiry != expiry or right != "C" or
                            option_type != "call" or (expiry - data_day).days != 1 or ask < bid or
                            abs(int(strike_milli) / 1000 - strike) > 1e-8):
                        raise ValueError(f"selected 2019 option identity or values conflict: {symbol} on {day}")
                    quote = Quote(symbol, underlying, expiry, "call", strike,
                                  "A" if underlying == "SPY" else "E", day, bid, ask, underlying_price, "PM")
                    key = (symbol, day)
                    if key in selected:
                        raise ValueError(f"duplicate selected 2019 option identity: {key}")
                    selected[key] = quote

    expected_keys = {(symbol, day) for day, contracts in required.items() for symbol in contracts}
    missing = expected_keys - selected.keys()
    if missing:
        raise ValueError(f"fixed 2019 selected option quotes missing: {sorted(missing)}")
    return selected, {"selected_quote_count": len(selected), "selected_entry_dates": len(required),
                      "selected_rows_scanned": rows_scanned, "mode": "FIXED_CONTRACT_DATES_ONLY"}


def _quote_index(period: str, *, diagnostics: dict | None = None) -> dict[tuple[str, date], Quote]:
    if period == "2022":
        raw = OFFICIAL_EXTENSION_ROOT / "options_sample_2022H2.zip"
        quotes, _, _ = read_2022_quotes(raw)
    else:
        _, _, _, rows19 = load_fixed_legacy()
        required = {}
        for row in rows19:
            day = date.fromisoformat(row["entry_date"])
            contracts = {row["spy_contract"]: date.fromisoformat(row["expiry_date"]),
                         row["spxw_contract"]: date.fromisoformat(row["expiry_date"])}
            previous = required.setdefault(day, {})
            for symbol, expiry in contracts.items():
                if symbol in previous and previous[symbol] != expiry:
                    raise ValueError(f"fixed 2019 contract maps to conflicting expiries: {symbol}")
                previous[symbol] = expiry
        quotes_by_key, details = _read_fixed_2019_quotes(
            LEGACY_2019_ROOT / "Sample_L2_2019_August.zip", required)
        if diagnostics is not None:
            diagnostics.update(details)
        return quotes_by_key
    index = {}
    for quote in quotes:
        key = (quote.contract, quote.quote_date)
        if key in index and index[key] != quote:
            raise ValueError(f"conflicting raw option quote identity {key}")
        index[key] = quote
    return index


def _frozen_selection(rows22: list[dict], rows19: list[dict], quote22: dict, quote19: dict) -> list[dict]:
    selection = []
    for period, cohorts, index in (("2022", rows22, quote22), ("2019", rows19, quote19)):
        pairs_by_key, seen_fills = {}, set()
        for cohort in cohorts:
            entry = date.fromisoformat(cohort["entry_date"])
            expiry = date.fromisoformat(cohort["expiry_date"])
            cover = date.fromisoformat(cohort["next_session_date"])
            pair_key = (entry, expiry)
            contracts = (cohort["spy_contract"], cohort["spxw_contract"])
            if pair_key in pairs_by_key and pairs_by_key[pair_key] != contracts:
                raise ValueError(f"contracts vary between stored fills: {period} {pair_key}")
            pairs_by_key[pair_key] = contracts
            fillrows = [cohort] if period == "2022" else cohort["fill_rows"]
            for ledger in fillrows:
                fill = ledger["fill"]
                identity = (period, entry, expiry, fill)
                if identity in seen_fills:
                    raise ValueError(f"duplicate pair/fill identity: {identity}")
                seen_fills.add(identity)
                spy = index.get((cohort["spy_contract"], entry))
                idx = index.get((cohort["spxw_contract"], entry))
                if spy is None or idx is None:
                    raise ValueError(f"raw entry quote missing for fixed contracts: {identity}")
                if (spy.underlying!="SPY" or idx.underlying!="SPXW" or spy.expiration!=expiry or
                        idx.expiration!=expiry or spy.quote_date!=entry or idx.quote_date!=entry or
                        spy.right.lower()!="call" or idx.right.lower()!="call" or
                        not all(math.isfinite(float(q.strike)) and float(q.strike)>0 and
                                math.isfinite(float(q.bid)) and math.isfinite(float(q.ask)) and
                                0<float(q.bid)<=float(q.ask) for q in (spy,idx))):
                    raise ValueError(f"raw entry quote identity or values are invalid: {identity}")
                if cover<=expiry or entry>=expiry:
                    raise ValueError(f"fixed pair dates are invalid: {identity}")
                cash = fill_cash_terms(spy, idx, fill)
                credit = _float(ledger["credit"], "stored entry credit")
                spy_cash = ledger.get("spy_entry_cash", ledger.get("spy_leg_entry_cash"))
                idx_cash = ledger.get("spxw_entry_cash", ledger.get("spxw_leg_entry_cash"))
                if abs(cash["spy_entry_cash"] - _float(spy_cash, "stored SPY entry cash")) > LEDGER_TOLERANCE:
                    raise ValueError(f"raw SPY quote does not reproduce fixed entry cash: {identity}")
                if abs(cash["spxw_entry_cash"] - _float(idx_cash, "stored SPXW entry cash")) > LEDGER_TOLERANCE:
                    raise ValueError(f"raw SPXW quote does not reproduce fixed entry cash: {identity}")
                if abs(cash["spy_entry_cash"] + cash["spxw_entry_cash"] - credit) > LEDGER_TOLERANCE:
                    raise ValueError(f"raw entry quotes do not reproduce fixed credit: {identity}")
                selection.append({"period":period,"entry":entry.isoformat(),"expiry":expiry.isoformat(),"cover":cover.isoformat(),
                    "fill":fill,"spy_contract":cohort["spy_contract"],"spxw_contract":cohort["spxw_contract"],
                    "spy_strike":float(spy.strike),"spxw_strike":float(idx.strike),
                    "spy_entry_cash":cash["spy_entry_cash"],"spxw_entry_cash":cash["spxw_entry_cash"],"credit":credit,
                    "spy_bid":float(spy.bid),"spy_ask":float(spy.ask),"spxw_bid":float(idx.bid),"spxw_ask":float(idx.ask),
                    "size_eligible":cohort.get("size_eligible")})
        expected = 189 if period == "2022" else 27
        if len(seen_fills) != expected:
            raise ValueError(f"fixed selection fill population mismatch for {period}")
        by_expiry = defaultdict(set)
        for p, e, x, f in seen_fills:
            by_expiry[x].add(f)
        if (len(by_expiry) != (63 if period == "2022" else 9) or
                len(pairs_by_key) != (63 if period == "2022" else 9) or
                any(x != set(FILLS) for x in by_expiry.values())):
            raise ValueError(f"fixed pair/fill uniqueness failed for {period}")
    return sorted(selection, key=lambda x:(x["period"],x["entry"],FILLS.index(x["fill"])))


def _quote_from_selection(item: dict) -> tuple[Quote, Quote]:
    entry, expiry = date.fromisoformat(item["entry"]), date.fromisoformat(item["expiry"])
    spy = Quote(item["spy_contract"],"SPY",expiry,"call",item["spy_strike"],"A",entry,
                item["spy_bid"],item["spy_ask"],1.0,"PM")
    idx = Quote(item["spxw_contract"],"SPXW",expiry,"call",item["spxw_strike"],"E",entry,
                item["spxw_bid"],item["spxw_ask"],1.0,"PM")
    return spy, idx


def compute_fill(item: dict, *, spy_close: float, cover_open: float, settlement: float,
                 dividends: list[tuple[date,float]]) -> dict:
    """Apply the original 10:1 ledger to one immutable fill."""
    spy, idx = _quote_from_selection(item)
    entry, expiry, cover = (date.fromisoformat(item[k]) for k in ("entry","expiry","cover"))
    ledger = expiry_ledger(spy=spy,idx=idx,credit=item["credit"],expiry_close=spy_close,
        spxw_settlement=settlement,next_open=cover_open,expiry_date=expiry,entry_date=entry,
        cover_date=cover,dividends=dividends)
    if not ledger["complete_cover"]:
        raise ValueError("fixed next-session cover is incomplete")
    days_exit=(cover-entry).days if ledger["assigned"] else (expiry-entry).days
    days_cover=(cover-expiry).days if ledger["assigned"] else 0
    nextpnl=ledger["next_open_pnl"]
    divpnl=ledger["dividend_carry_pnl"]
    base_nondiv=cost_adjusted(nextpnl,item["credit"],ledger["assigned"],days_exit,days_cover,spy_close)
    stress_nondiv=cost_adjusted(nextpnl,item["credit"],ledger["assigned"],days_exit,days_cover,spy_close,stress=True)
    base_div=cost_adjusted(divpnl,item["credit"],ledger["assigned"],days_exit,days_cover,spy_close)
    stress_div=cost_adjusted(divpnl,item["credit"],ledger["assigned"],days_exit,days_cover,spy_close,stress=True)
    overnight=1000*(spy_close-cover_open) if ledger["assigned"] else 0.0
    neutral=nextpnl-overnight
    if abs(neutral-ledger["conditional_close_mark_pnl"])>LEDGER_TOLERANCE:
        raise AssertionError("stock attribution identity failed")
    from .expiry_extension import fill_credits
    reverse_credit=fill_credits(spy,idx)["reverse_full_cross_control"]
    reverse_intrinsic=reverse_credit-(ledger["direct_intrinsic_pnl"]-item["credit"])
    return {**ledger,"base_nondividend_cost_pnl":base_nondiv,"stress_nondividend_cost_pnl":stress_nondiv,
        "base_dividend_cost_pnl":base_div,"stress_dividend_cost_pnl":stress_div,
        "base_cost_pnl":base_div,"stress_cost_pnl":stress_div,"stock_overnight_attribution":overnight,
        "stock_neutralized_pnl":neutral,"calendar_days_entry_to_exit":days_exit,
        "reverse_full_cross_entry_credit_control":reverse_credit,
        "reverse_terminal_intrinsic_control_pnl":reverse_intrinsic,"reverse_cross_control_pnl":reverse_intrinsic,
        "stock_neutralized_base_cost_pnl":base_div-overnight,
        "stock_neutralized_stress_cost_pnl":stress_div-overnight,
        "calendar_days_expiry_to_cover":days_cover,"zero_control_pnl":0.0,
        "cost_components":{"option_base":11*.65,"option_stress":11*1.5,
            "stock_base":1000*.005 if ledger["assigned"] else 0,
            "stock_stress":1000*.01 if ledger["assigned"] else 0,
            "borrow_days":days_cover,"funding_days":days_exit,
            "borrow_base":1000*spy_close*.03*days_cover/365 if ledger["assigned"] else 0,
            "borrow_stress":1000*spy_close*.1*days_cover/365 if ledger["assigned"] else 0,
            "funding_base":max(-item["credit"],0)*.05*days_exit/365,
            "funding_stress":max(-item["credit"],0)*.1*days_exit/365}}


def summarize_values(values: list[float]) -> dict:
    if not values:
        raise ValueError("cannot summarize an empty fixed population")
    return {"count":len(values),"mean":statistics.mean(values),"median":statistics.median(values),
            "min":min(values),"max":max(values),"positive_count":sum(v>0 for v in values),"total":sum(values)}


def compare_value(actual, expected, *, path="value", tolerance=LEDGER_TOLERANCE) -> None:
    if isinstance(expected,bool) or expected is None or isinstance(expected,str):
        if actual!=expected: raise ValueError(f"parity mismatch at {path}")
    elif isinstance(expected,(int,float)):
        if not math.isfinite(float(expected)):
            raise ValueError(f"nonfinite frozen parity value at {path}")
        if isinstance(actual,bool) or not isinstance(actual,(int,float)) or not math.isfinite(float(actual)):
            raise ValueError(f"nonfinite or missing parity value at {path}")
        if abs(float(actual)-float(expected))>tolerance: raise ValueError(f"parity mismatch at {path}: {actual!r} != {expected!r}")
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected): raise ValueError(f"parity mismatch at {path}")
        for index,value in enumerate(expected): compare_value(actual[index],value,path=f"{path}[{index}]",tolerance=tolerance)
    elif isinstance(expected,dict):
        if not isinstance(actual,dict) or not set(actual).issuperset(expected): raise ValueError(f"missing parity fields at {path}")
        for key,value in expected.items(): compare_value(actual[key],value,path=f"{path}.{key}",tolerance=tolerance)


LEDGER_PARITY_FIELDS = ("assigned", "spy_intrinsic", "spy_leg_expiry_cash", "spy_leg_expiry_shares",
    "spy_leg_close_mark_cash", "spy_leg_next_open_cash", "spy_leg_next_open_shares",
    "spxw_leg_terminal_cash", "spxw_leg_terminal_shares", "direct_intrinsic_pnl",
    "conditional_close_mark_pnl", "threshold_residual_cash", "next_open_pnl",
    "dividend_carry_pnl", "dividend_carry_amount", "dividend_carry_dates",
    "entry_exposure_dividend_dates", "entry_to_expiry_dividend_exposure", "complete_cover",
    "calendar_days_entry_to_exit", "calendar_days_expiry_to_cover", "zero_control_pnl")


def _baseline_summary_check(rows: list[dict], period: str, aggregate: dict) -> dict:
    checks = 0
    matched_records = 0
    if period == "2022":
        metrics = {
            "direct_intrinsic_pnl": "direct_intrinsic_pnl",
            "conditional_close_mark_pnl": "conditional_close_mark_pnl",
            "next_open_pnl": "next_open_pnl",
            "dividend_carry_pnl": "dividend_carry_pnl",
            "base_nondividend_cost_pnl": "base_nondividend_cost_pnl",
            "stress_nondividend_cost_pnl": "stress_nondividend_cost_pnl",
            "base_dividend_cost_pnl": "base_dividend_cost_pnl",
            "stress_dividend_cost_pnl": "stress_dividend_cost_pnl",
        }
        cases = {
            "direct_intrinsic_pnl": "gross",
            "conditional_close_mark_pnl": "gross",
            "next_open_pnl": "gross",
            "dividend_carry_pnl": "dividend_adjusted",
            "base_nondividend_cost_pnl": "base_nondividend",
            "stress_nondividend_cost_pnl": "stress_nondividend",
            "base_dividend_cost_pnl": "base_dividend",
            "stress_dividend_cost_pnl": "stress_dividend",
        }
        periods = ("all", "Q3", "Q4", "2022-07", "2022-08", "2022-09",
                   "2022-10", "2022-11", "2022-12")
        depths = ("all_selected", "size_eligible")
        summaries = aggregate.get("equal_expiry_primary_summaries")
        if not isinstance(summaries, list) or len(summaries) != 432:
            raise ValueError("2022 expected summary coverage is missing or incomplete")
        expected_keys = {
            (summary_period, fill, metric, cases[metric], depth)
            for summary_period in periods for fill in FILLS
            for metric in metrics for depth in depths
        }
        keyed = {}
        for target in summaries:
            if (target.get("lane") != LANE_2022 or
                    target.get("population") != "equal_expiry_primary"):
                raise ValueError("2022 summary has the wrong lane or population")
            key = (target.get("period"), target.get("fill"), target.get("metric"),
                   target.get("cost_case"), target.get("depth"))
            if key in keyed:
                raise ValueError(f"duplicate 2022 summary record: {key}")
            keyed[key] = target
        if set(keyed) != expected_keys:
            raise ValueError("2022 expected summary coverage has missing or unexpected records")

        for key in sorted(expected_keys):
            month, fill, metric, cost_case, depth = key
            target = keyed[key]
            subset = [r for r in rows if r["period"] == period and r["fill"] == fill and
                (month == "all" or
                 (month == "Q3" and date.fromisoformat(r["expiry"]).month in (7, 8, 9)) or
                 (month == "Q4" and date.fromisoformat(r["expiry"]).month in (10, 11, 12)) or
                 r["expiry"].startswith(month))]
            if depth == "size_eligible":
                subset = [r for r in subset if r["size_eligible"]]
            values = [_float(r[metrics[metric]], metric) for r in subset]
            if not values or len(values) != target.get("valid_rows"):
                raise ValueError(f"2022 summary denominator mismatch: {fill}/{month}/{metric}/{depth}")
            if target.get("missing_outcome_count") != 0:
                raise ValueError(f"2022 summary contains missing outcomes: {fill}/{month}/{metric}/{depth}")
            expiry_count = len({r["expiry"] for r in subset})
            compare_value(expiry_count, target.get("expiry_count"),
                          path=f"2022 summary {fill}/{month}/{metric}/{depth}/expiry_count",
                          tolerance=SUMMARY_TOLERANCE)
            checks += 1
            summary = summarize_values(values)
            for key_name, source_key in (("mean", "mean"), ("median", "median"),
                    ("min", "worst_loss"), ("positive_count", "positive_count"),
                    ("count", "valid_rows")):
                compare_value(summary[key_name], target.get(source_key),
                    path=f"2022 summary {fill}/{month}/{metric}/{cost_case}/{depth}/{key_name}",
                    tolerance=SUMMARY_TOLERANCE)
                checks += 1
            matched_records += 1
        expected_records = 432
    elif period == "2019":
        expected_groups = {
            "2019-08": 9, "2019-W31": 1, "2019-W32": 2, "2019-W33": 2,
            "2019-W34": 2, "2019-W35": 2, "all": 9,
        }
        metric_fields = {
            "base_cost_pnl": "base_cost_pnl",
            "conditional_close_mark_pnl": "conditional_close_mark_pnl",
            "direct_intrinsic_pnl": "direct_intrinsic_pnl",
            "next_open_pnl": "next_open_pnl",
            "reverse_cross_control": "reverse_cross_control_pnl",
            "reverse_cross_control_pnl": "reverse_cross_control_pnl",
            "stock_neutralized_base_cost_pnl": "stock_neutralized_base_cost_pnl",
            "stock_neutralized_pnl": "stock_neutralized_pnl",
            "stock_neutralized_stress_cost_pnl": "stock_neutralized_stress_cost_pnl",
            "stress_cost_pnl": "stress_cost_pnl",
            "zero_control": "zero_control_pnl",
            "zero_control_pnl": "zero_control_pnl",
        }
        summary_fields = {"n", "missing_n", "mean", "median", "min", "max",
                          "positive_count", "values"}
        cohorts = aggregate.get("cohorts")
        if (aggregate.get("population") != "one fixed primary pair per declared expiry; not a portfolio" or
                not isinstance(cohorts, dict) or set(cohorts) != set(expected_groups)):
            raise ValueError("2019 expected summary coverage has a missing group or wrong population")
        for group, expected_expiries in expected_groups.items():
            target_group = cohorts[group]
            if (target_group.get("primary_expiry_count") != expected_expiries or
                    not isinstance(target_group.get("fills"), dict) or
                    set(target_group["fills"]) != set(FILLS)):
                raise ValueError(f"2019 summary group coverage is incomplete: {group}")
            for fill in FILLS:
                targets = target_group["fills"][fill]
                if not isinstance(targets, dict) or set(targets) != set(metric_fields):
                    raise ValueError(f"2019 summary metric coverage is incomplete: {group}/{fill}")
                subset = [r for r in rows if r["period"] == period and r["fill"] == fill and
                    (group == "all" or
                     (group == "2019-08" and r["expiry"].startswith(group)) or
                     ("-W" in group and
                      f"{date.fromisoformat(r['expiry']).isocalendar().year}-W"
                      f"{date.fromisoformat(r['expiry']).isocalendar().week:02d}" == group))]
                compare_value(len({r["expiry"] for r in subset}), expected_expiries,
                    path=f"2019 summary {group}/{fill}/expiry_count", tolerance=SUMMARY_TOLERANCE)
                checks += 1
                for metric, target in targets.items():
                    if not isinstance(target, dict) or set(target) != summary_fields:
                        raise ValueError(f"2019 summary fields are incomplete: {group}/{fill}/{metric}")
                    field = metric_fields[metric]
                    values = [_float(r[field], field) for r in subset]
                    if not values:
                        raise ValueError(f"2019 summary has no matched rows: {group}/{fill}/{metric}")
                    actual = summarize_values(values)
                    for target_key, actual_key in (("n", "count"), ("missing_n", None),
                            ("mean", "mean"), ("median", "median"), ("min", "min"),
                            ("max", "max"), ("positive_count", "positive_count"),
                            ("values", "values")):
                        actual_value = 0 if actual_key is None else (values if actual_key == "values"
                                                                    else actual[actual_key])
                        compare_value(actual_value, target[target_key],
                            path=f"2019 summary {group}/{fill}/{metric}/{target_key}",
                            tolerance=SUMMARY_TOLERANCE)
                        checks += 1
                    matched_records += 1
        expected_records = len(expected_groups) * len(FILLS) * len(metric_fields)
    else:
        raise ValueError(f"unsupported baseline summary period: {period}")

    if matched_records == 0 or matched_records != expected_records or checks == 0:
        raise ValueError(f"{period} baseline summary coverage is empty or incomplete")
    return {"summary_fields_checked": checks, "summary_records_matched": matched_records,
            "summary_records_expected": expected_records, "status": "PASS"}


def _legacy_documents() -> tuple[dict,list[dict],dict,dict,list[dict],dict]:
    run22=LEGACY_ROOT/"expiry_extension/20261028T114142711970Z"
    run19=LEGACY_ROOT/"expiry_replication/20261028T125023997117Z"
    m22,r22,m19,r19=load_fixed_legacy()
    return (m22,r22,json.loads((run22/"aggregates.json").read_text()),
            m19,r19,json.loads((run19/"aggregates.json").read_text()))


def _saved_lookup(rows22:list[dict],rows19:list[dict])->dict:
    saved={}
    for row in rows22:
        key=("2022",row["entry_date"],row["expiry_date"],row["fill"])
        if key in saved: raise ValueError(f"duplicate saved pair/fill control {key}")
        saved[key]=row
    for cohort in rows19:
        for row in cohort["fill_rows"]:
            key=("2019",cohort["entry_date"],cohort["expiry_date"],row["fill"])
            if key in saved: raise ValueError(f"duplicate saved pair/fill control {key}")
            saved[key]={**row,"_cohort":cohort}
    return saved


def _legacy_references() -> tuple[dict,dict]:
    root22=OFFICIAL_EXTENSION_ROOT
    stocks,boundary=_read_old_2022_stocks(root22/"stocks_sample_2022H2.zip",root22/"yahoo_SPY_20220701_20230103.json")
    settlements=_read_2022_settlements((root22/"cboe_W_2022.json",root22/"cboe_M_2022.json",root22/"cboe_S_2022.json"))
    counts=Counter()
    yahoo19,divs19=legacy2019.read_yahoo(LEGACY_2019_ROOT/"yahoo_SPY_20190801_20190904.json",counts)
    spx19=legacy2019.read_spx(LEGACY_2019_ROOT/"SPX_History.csv",counts)
    settlements19=legacy2019.parse_cboe_pm(LEGACY_2019_ROOT/"cboe_W_2019.json",counts)
    monthly=legacy2019.parse_cboe_pm(LEGACY_2019_ROOT/"cboe_M_2019.json",counts)
    # Match load_study_inputs cross-file W/M conflict handling exactly.
    for day,row in monthly.items():
        if day in settlements19 and settlements19[day]["value"]!=row["value"]:
            settlements19.pop(day,None)
        else:
            settlements19[day]=row
    old22={"stocks":stocks,"settlements":settlements,"boundary":boundary}
    old19={"yahoo":yahoo19,"spx":spx19,"settlements":settlements19,"dividends":list(divs19)}
    return old22,old19


def _compute_baseline(selection:list[dict],saved:dict,old22:dict,old19:dict,
                      aggregate22:dict,aggregate19:dict)->tuple[list[dict],dict]:
    rows=[]
    from .expiry_extension import fill_credits
    for item in selection:
        key=(item["period"],item["entry"],item["expiry"],item["fill"])
        expected=saved.get(key)
        if expected is None: raise ValueError(f"saved legacy row absent: {key}")
        if item["period"]=="2022":
            stock=old22["stocks"]
            close=stock[date.fromisoformat(item["expiry"])]["close"]
            op=stock[date.fromisoformat(item["cover"])]["open"]
            settle=old22["settlements"].get(date.fromisoformat(item["expiry"]))
            divs=[(d,x["dividend"]) for d,x in stock.items() if x["dividend"]>0]
        else:
            close=old19["yahoo"][date.fromisoformat(item["expiry"])]["close"]
            op=old19["yahoo"][date.fromisoformat(item["cover"])]["open"]
            sr=old19["settlements"].get(date.fromisoformat(item["expiry"]))
            settle=sr["value"] if sr else None
            divs=old19["dividends"]
        if settle is None: raise ValueError(f"fixed SPXW PM settlement missing: {key}")
        calc=compute_fill(item,spy_close=close,cover_open=op,settlement=settle,dividends=divs)
        for field in LEDGER_PARITY_FIELDS:
            expected_field="calendar_days_entry_to_option_exit" if item["period"]=="2022" and field=="calendar_days_entry_to_exit" else field
            compare_value(calc[field],expected[expected_field],path=f"{key}.{expected_field}")
        compare_value(calc["credit"],expected["credit"],path=f"{key}.credit")
        for leg, selected_field, aliases in (
            ("SPY", "spy_entry_cash", ("spy_leg_entry_cash", "spy_entry_cash")),
            ("SPXW", "spxw_entry_cash", ("spxw_leg_entry_cash", "spxw_entry_cash")),
        ):
            saved_field = next((name for name in aliases if name in expected), None)
            if saved_field is None: raise ValueError(f"saved legacy cash field is missing: {key}.{leg}")
            compare_value(item[selected_field], expected[saved_field], path=f"{key}.{saved_field}")
        if item["period"]=="2022":
            compare_value(calc["spxw_leg_terminal_shares"],expected["spxw_leg_expiry_shares"],path=f"{key}.spxw_leg_expiry_shares")
        compare_value(item["spy_entry_cash"],expected.get("spy_entry_cash",expected.get("spy_leg_entry_cash")),path=f"{key}.spy entry cash")
        compare_value(item["spxw_entry_cash"],expected.get("spxw_entry_cash",expected.get("spxw_leg_entry_cash")),path=f"{key}.SPXW entry cash")
        compare_value(0,expected.get("spy_entry_shares"),path=f"{key}.SPY entry shares")
        compare_value(0,expected.get("spxw_entry_shares"),path=f"{key}.SPXW entry shares")
        spy,idx=_quote_from_selection(item)
        reverse_credit=fill_credits(spy,idx)["reverse_full_cross_control"]
        reverse=reverse_credit-(calc["direct_intrinsic_pnl"]-item["credit"])
        reverse_field="reverse_full_cross_pnl_control" if item["period"]=="2022" else "reverse_cross_control_pnl"
        compare_value(reverse,expected[reverse_field],path=f"{key}.{reverse_field}")
        if item["period"]=="2022":
            compare_value(calc["reverse_full_cross_entry_credit_control"],expected["reverse_full_cross_entry_credit_control"],path=f"{key}.reverse credit")
            compare_value(close,expected["spy_expiry_raw_close"],path=f"{key}.spy_expiry_raw_close")
            compare_value(settle,expected["spx_terminal_reference"],path=f"{key}.spx_terminal_reference")
            compare_value(close,expected["spy_terminal_reference"],path=f"{key}.spy_terminal_reference")
            for field in ("base_nondividend_cost_pnl","stress_nondividend_cost_pnl","base_dividend_cost_pnl","stress_dividend_cost_pnl"):
                compare_value(calc[field],expected[field],path=f"{key}.{field}")
            compare_value(calc["cost_components"],expected["cost_components"],path=f"{key}.cost_components")
            compare_value({"eligible":calc["next_open_pnl"] is not None,
                "direct_intrinsic_pnl":calc["direct_intrinsic_pnl"] if calc["next_open_pnl"] is not None else None,
                "conditional_close_mark_pnl":calc["conditional_close_mark_pnl"] if calc["next_open_pnl"] is not None else None,
                "next_open_pnl":calc["next_open_pnl"]},expected["conditional_close_vs_next_open_common"],
                path=f"{key}.conditional_close_vs_next_open_common")
            compare_value({"option_contracts":11,"base_option_per_contract":.65,"base_stock_per_share":.005,
                "base_borrow_apr":.03,"base_funding_apr":.05,"stress_option_per_contract":1.5,
                "stress_stock_per_share":.01,"stress_borrow_apr":.1,"stress_funding_apr":.1,
                "funding_exit":"expiry if unassigned, next-session cover if assigned","day_count":"simple ACT/365"},
                expected["cost_assumptions"],path=f"{key}.cost_assumptions")
        else:
            cohort=expected["_cohort"]
            compare_value(calc["reverse_full_cross_entry_credit_control"],cohort["reverse_cross_control_credit"],path=f"{key}.reverse credit")
            compare_value(close,cohort["spy_expiry_yahoo_raw_close"],path=f"{key}.spy_expiry_yahoo_raw_close")
            compare_value(op,cohort["spy_next_session_yahoo_raw_open"],path=f"{key}.spy_next_session_yahoo_raw_open")
            compare_value(settle,cohort["spxw_pm_settlement"],path=f"{key}.spxw_pm_settlement")
            compare_value(calc["base_cost_pnl"],expected["base_cost_pnl"],path=f"{key}.base_cost_pnl")
            compare_value(calc["stress_cost_pnl"],expected["stress_cost_pnl"],path=f"{key}.stress_cost_pnl")
            compare_value(calc["stock_neutralized_pnl"],expected["stock_neutralized_pnl"],path=f"{key}.stock_neutralized_pnl")
            compare_value(calc["base_cost_pnl"]-calc["stock_overnight_attribution"],expected["stock_neutralized_base_cost_pnl"],path=f"{key}.stock_neutralized_base_cost_pnl")
            compare_value(calc["stress_cost_pnl"]-calc["stock_overnight_attribution"],expected["stock_neutralized_stress_cost_pnl"],path=f"{key}.stock_neutralized_stress_cost_pnl")
        rows.append({**item,"arm":"baseline_old_all","spy_close":close,"cover_open":op,
                     "spxw_pm_settlement":settle,**calc})
    checks22=_baseline_summary_check(rows,"2022",aggregate22)
    checks19=_baseline_summary_check(rows,"2019",aggregate19)
    return rows,{"status":"PASS","row_count":len(rows),"row_fields_checked":len(rows)*len(LEDGER_PARITY_FIELDS),
        "tolerance_usd":LEDGER_TOLERANCE,"summary_tolerance_usd":SUMMARY_TOLERANCE,
        "period_summaries":{"2022":checks22,"2019":checks19}}


def _identity(repo:Path)->dict:
    head=subprocess.run(["git","rev-parse","HEAD"],cwd=repo,text=True,capture_output=True,check=True).stdout.strip()
    status=subprocess.run(["git","status","--porcelain"],cwd=repo,text=True,capture_output=True,check=True).stdout
    if status.strip(): raise ValueError("lead calculation commands require a clean Git worktree")
    roles=("src/spyspx/optionmetrics_stockrefs.py","src/spyspx/expiry_extension.py",
           "src/spyspx/expiry_payoff.py","src/spyspx/expiry_payoff_source.py",
           "src/spyspx/optionmetrics_replication.py","src/spyspx/optionmetrics_normalizer.py",
           "src/spyspx/optionmetrics_admission.py","src/spyspx/expiry_replication.py")
    modules={
        "src/spyspx/optionmetrics_stockrefs.py":sys.modules[__name__],
        "src/spyspx/expiry_extension.py":sys.modules["spyspx.expiry_extension"],
        "src/spyspx/expiry_payoff.py":sys.modules["spyspx.expiry_payoff"],
        "src/spyspx/expiry_payoff_source.py":sys.modules["spyspx.expiry_payoff_source"],
        "src/spyspx/optionmetrics_replication.py":source,
        "src/spyspx/optionmetrics_normalizer.py":sys.modules["spyspx.optionmetrics_normalizer"],
        "src/spyspx/optionmetrics_admission.py":sys.modules["spyspx.optionmetrics_admission"],
        "src/spyspx/expiry_replication.py":sys.modules["spyspx.expiry_replication"],
    }
    code={}
    for relative in roles:
        path=(repo/relative).resolve(strict=True)
        if Path(modules[relative].__file__).resolve(strict=True)!=path:
            raise ValueError(f"unexpected imported module path: {relative}")
        data=path.read_bytes()
        blob=subprocess.run(["git","show",f"{head}:{relative}"],cwd=repo,capture_output=True,check=False)
        if blob.returncode or blob.stdout!=data:
            raise ValueError(f"loaded code does not match clean committed Git blob: {relative}")
        code[relative]={"path":str(path),"bytes":len(data),"sha256":sha256(data)}
    return {"head":head,"clean":True,"code":code}


def _validate_frozen_metadata(repo:Path,identity:dict)->tuple[Path,Path,bytes,dict]:
    protocol=(repo/PROTOCOL_PATH).resolve(strict=True)
    manifest=(repo/INPUT_MANIFEST_PATH).resolve(strict=True)
    pdoc=protocol.read_bytes();mdoc=json.loads(manifest.read_text())
    if mdoc.get("arms")!=list(ARMS) or mdoc.get("status")!="FROZEN_INPUT_MANIFEST_NOT_RUN":
        raise ValueError("frozen input manifest status or arm set changed")
    if mdoc.get("base_sha")!="d6eff1d112d83d9debaa8469d3812b478af70fd3":
        raise ValueError("frozen input manifest base SHA changed")
    if "NOT RUN" not in pdoc.decode():raise ValueError("frozen protocol must retain NOT RUN status")
    p_receipt=mdoc.get("planning_documents",{}).get("candidate-protocol.md",{})
    if p_receipt.get("bytes")!=len(pdoc) or p_receipt.get("sha256")!=sha256(pdoc):
        raise ValueError("protocol bytes/hash do not match frozen input manifest")
    code_record=mdoc.get("implementation_code",{})
    module_code=identity.get("code",{}).get("src/spyspx/optionmetrics_stockrefs.py",{})
    if (not module_code or code_record.get("bytes")!=module_code.get("bytes") or
            code_record.get("sha256")!=module_code.get("sha256")):
        raise ValueError("implementation code does not match frozen input manifest")
    test_data=(repo/"tests/test_optionmetrics_stockrefs.py").read_bytes()
    test_record=mdoc.get("synthetic_tests",{})
    if not test_record or test_record.get("bytes")!=len(test_data) or test_record.get("sha256")!=sha256(test_data):
        raise ValueError("synthetic test code does not match frozen input manifest")
    return protocol,manifest,pdoc,mdoc


def _snapshot_bindings(repo:Path,identity:dict,inventory:dict,wrds:dict)->dict:
    protocol,manifest,pdoc,mdoc=_validate_frozen_metadata(repo,identity)
    fixed={"2022_manifest_sha256":"fc60f968f262cd53ff32f2a6aedc1f959cbed40a0eb23a8b86acaaf01170d816",
        "2022_pair_rows_sha256":"5a6e4e3f75244ec4e6f2119f46725746630eb467959dd8d440ed946baf29a2df",
        "2019_manifest_sha256":"b695ac5474e8f40c2d904604abd1358069e3036b70c7d566fde686e3d3d8ca4f",
        "2019_pair_rows_sha256":"64d7ca81b391e4bb8fb557a860abb8bddcd90633f188ee4c0b69004270c102a4"}

    for key,value in fixed.items():
        if mdoc.get("legacy_controls",{}).get(key)!=value: raise ValueError(f"frozen input control changed: {key}")
    for key,record in wrds.items():
        match=next((v for k,v in mdoc.get("sources",{}).items() if k.endswith(Path(record["path"]).name)),None)
        if match is None or match.get("sha256")!=record["sha256"] or match.get("bytes")!=record["bytes"]:
            raise ValueError(f"new source does not match frozen input manifest: {key}")
    groups={
        "original_receipt":("legacy_source_receipts",19),
        "legacy_code":("legacy_code_files",8),
        "legacy_dependency":("legacy_dependencies",2),
        "control_artifact":("control_artifacts",6),
    }
    for prefix,(field,count) in groups.items():
        actual={key.removeprefix(prefix+":"):value for key,value in inventory.items() if key.startswith(prefix+":")}
        frozen=mdoc.get(field,{})
        if len(actual)!=count or set(actual)!=set(frozen):
            raise ValueError(f"frozen manifest {field} keys/count do not match audited sources")
        for key,record in actual.items():
            expected=frozen[key]
            if any(expected.get(k)!=record.get(k) for k in ("path","bytes","sha256")):
                raise ValueError(f"frozen manifest source receipt mismatch: {field}/{key}")
    return {"head":identity["head"],"code":identity["code"],
        "protocol":{"path":str(protocol),"bytes":len(pdoc),"sha256":sha256(pdoc)},
        "input_manifest":{"path":str(manifest),"bytes":manifest.stat().st_size,"sha256":sha256(manifest.read_bytes())},
        "original_sources":inventory,"wrds_sources":wrds,
        "old_controls":fixed}


def _integrity_check(repo:Path,identity:dict,bindings:dict,selection_bytes:bytes|None=None,
                     arm_bytes:bytes|None=None)->None:
    current=_identity(repo)
    if current!=identity: raise ValueError("code, imported module, Git SHA, or clean state changed")
    for group in ("protocol","input_manifest"):
        item=bindings[group]; data=Path(item["path"]).read_bytes()
        if len(data)!=item["bytes"] or sha256(data)!=item["sha256"]: raise ValueError(f"{group} changed during calculation")
    for group in ("original_sources","wrds_sources"):
        for role,item in bindings[group].items():
            path=Path(item["path"]); data=path.read_bytes()
            if len(data)!=item["bytes"] or sha256(data)!=item["sha256"]: raise ValueError(f"frozen source changed: {role}")
    if selection_bytes is not None and sha256(selection_bytes)!=bindings["selection_sha256"]:
        raise ValueError("fixed selection snapshot changed during calculation")
    if arm_bytes is not None and sha256(arm_bytes)!=bindings["arm_freeze_sha256"]:
        raise ValueError("five-arm freeze changed during calculation")


def _write_json(path:Path,document:dict)->bytes:
    data=(json.dumps(document,indent=2,sort_keys=True,default=str)+"\n").encode()
    with path.open("xb") as handle:
        handle.write(data);handle.flush();os.fsync(handle.fileno())
    return data


def _period_coverage(selection:list[dict],prices:dict,events:list[dict])->list[dict]:
    pairs={}
    for row in selection:
        pairs[(row["period"],row["entry"],row["expiry"],row["cover"])]=row
    output=[]
    for period,entry_s,expiry_s,cover_s in sorted(pairs):
        entry,expiry,cover=map(date.fromisoformat,(entry_s,expiry_s,cover_s))
        missing=[d.isoformat() for d in (entry,expiry,cover) if d not in prices]
        relevant=[e for e in events if entry<e["ex_date"]<=cover]
        unsupported=[e["ex_date"].isoformat() for e in relevant if not e["supported"]]
        output.append({"period":period,"entry":entry_s,"expiry":expiry_s,"cover":cover_s,
            "complete":not missing and not unsupported,"missing_stock_dates":missing,
            "relevant_distribution_count":len(relevant),"unsupported_distribution_dates":unsupported})
    if len(output)!=(63+9): raise ValueError("coverage denominator changed from frozen 63/9 pairs")
    if any(not row["complete"] for row in output): raise ValueError("fixed source coverage is incomplete or contains unsupported actions")
    return output


def _quantile7(values:list[float],p:float)->float:
    if len(values)==1:return values[0]
    position=(len(values)-1)*p;lo,hi=math.floor(position),math.ceil(position)
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def _bootstrap_indices(rows:list[dict])->list[list[str]]:
    """Draw shared ISO-week cluster samples from the fixed 2022 expiry pairs."""
    weeks=sorted({f"{date.fromisoformat(row['expiry']).isocalendar().year}-W"
                  f"{date.fromisoformat(row['expiry']).isocalendar().week:02d}" for row in rows})
    if not weeks: raise ValueError("cannot bootstrap an empty frozen 2022 population")
    rng=random.Random(BOOTSTRAP_SEED)
    return [rng.choices(weeks,k=len(weeks)) for _ in range(BOOTSTRAP_DRAWS)]


def evaluate_rows(selection:list[dict],old22:dict,old19:dict,wrds_prices:dict,wrds_events:list[dict])->dict:
    rows_by_arm={}
    for arm in ARMS:
        rows=[]
        for item in selection:
            period=item["period"]
            if period=="2022":
                stock=old22["stocks"];expiry=date.fromisoformat(item["expiry"]);cover=date.fromisoformat(item["cover"])
                close0=stock[expiry]["close"];open0=stock[cover]["open"]
                old_div=[(d,r["dividend"]) for d,r in stock.items() if r["dividend"]>0]
                settlement=old22["settlements"].get(expiry)
            else:
                expiry=date.fromisoformat(item["expiry"]);cover=date.fromisoformat(item["cover"])
                close0=old19["yahoo"][expiry]["close"];open0=old19["yahoo"][cover]["open"]
                old_div=old19["dividends"];settlement_row=old19["settlements"].get(expiry)
                settlement=settlement_row["value"] if settlement_row else None
            if settlement is None:raise ValueError(f"missing fixed settlement for {item['expiry']}")
            wrds_close=wrds_prices[expiry]["close"];wrds_open=wrds_prices[cover]["open"]
            entry=date.fromisoformat(item["entry"]);new_div=[]
            for event in wrds_events:
                if entry<event["ex_date"]<=cover:
                    if not event["supported"]:raise ValueError(f"unsupported corporate action in fixed interval: {event['ex_date']}")
                    new_div.append((event["ex_date"],event["amount"]))
            close=wrds_close if arm in {"wrds_expiry_close_only","wrds_all"} else close0
            op=wrds_open if arm in {"wrds_cover_open_only","wrds_all"} else open0
            divs=new_div if arm in {"wrds_dividends_only","wrds_all"} else old_div
            calculated=compute_fill(item,spy_close=close,cover_open=op,settlement=settlement,dividends=divs)
            rows.append({**item,"arm":arm,"spy_close":close,"cover_open":op,"spxw_pm_settlement":settlement,
                "source_reference_values":{"old_expiry_close":close0,"wrds_expiry_close":wrds_close,
                    "old_cover_open":open0,"wrds_cover_open":wrds_open},
                "dividend_dates_used":[d.isoformat() for d,_ in divs if entry<d<=cover],**calculated})
        rows_by_arm[arm]=rows
    fixed=[(r["period"],r["entry"],r["expiry"],r["fill"]) for r in rows_by_arm[ARMS[0]]]
    if any([(r["period"],r["entry"],r["expiry"],r["fill"]) for r in rows_by_arm[arm]]!=fixed for arm in ARMS[1:]):
        raise AssertionError("pair/fill denominator changed across frozen arms")
    return rows_by_arm


def _assignment_flips(rows_by_arm:dict)->dict:
    baseline={(r["period"],r["entry"],r["expiry"],r["fill"]):r["assigned"] for r in rows_by_arm[ARMS[0]]}
    output={}
    for arm in ARMS[1:]:
        flips=[]
        for row in rows_by_arm[arm]:
            key=(row["period"],row["entry"],row["expiry"],row["fill"])
            old=baseline[key]
            if row["assigned"]!=old:
                flips.append({"period":row["period"],"entry":row["entry"],"expiry":row["expiry"],
                              "fill":row["fill"],"baseline_assigned":old,"arm_assigned":row["assigned"]})
        output[arm]={"flip_count":len(flips),"fixed_row_count":len(baseline),
            "by_period":{period:sum(row["period"]==period for row in flips) for period in ("2019","2022")},
            "by_fill":{fill:sum(row["fill"]==fill for row in flips) for fill in FILLS},"flips":flips}
    return output


def _arm_summaries(rows_by_arm:dict)->dict:
    output={}
    for arm,rows in rows_by_arm.items():
        output[arm]={}
        for period in ("2019","2022"):
            output[arm][period]={}
            for fill in FILLS:
                subset=[r for r in rows if r["period"]==period and r["fill"]==fill]
                output[arm][period][fill]={metric:summarize_values([_float(r[metric],metric) for r in subset]) for metric in METRICS}
    return output


def _uncertainty(rows_by_arm:dict)->dict:
    period="2022"
    base=[r for r in rows_by_arm[ARMS[0]] if r["period"]==period]
    draws=_bootstrap_indices(base)
    draw_weights=[dict((week,draw.count(week)) for week in set(draw)) for draw in draws]
    weeks=sorted({f"{date.fromisoformat(row['expiry']).isocalendar().year}-W"
                  f"{date.fromisoformat(row['expiry']).isocalendar().week:02d}" for row in base})
    base_lookup={(r["expiry"],r["fill"]):r for r in base}
    arm_rows={arm:[r for r in rows_by_arm[arm] if r["period"]==period] for arm in ARMS}
    absolute={};paired={};nonadditivity={}

    def cluster_stats(rows,fill,metric):
        by_week=defaultdict(list)
        for row in rows:
            if row["fill"]==fill:
                expiry=date.fromisoformat(row["expiry"])
                key=f"{expiry.isocalendar().year}-W{expiry.isocalendar().week:02d}"
                by_week[key].append(_float(row[metric],metric))
        return {week:(sum(values),len(values)) for week,values in by_week.items()}

    for arm in ARMS:
        absolute[arm]={}
        for fill in FILLS:
            absolute[arm][fill]={}
            for metric in METRICS:
                rows=[r for r in arm_rows[arm] if r["fill"]==fill]
                if len(rows)!=63: raise ValueError(f"2022 fixed denominator mismatch for {arm}/{fill}: {len(rows)}")
                stats=cluster_stats(rows,fill,metric)
                samples=[];resampled_counts=[]
                for weights in draw_weights:
                    numerator=sum(weight*stats.get(week,(0.0,0))[0] for week,weight in weights.items())
                    denominator=sum(weight*stats.get(week,(0.0,0))[1] for week,weight in weights.items())
                    if denominator<=0: raise ValueError("bootstrap draw has no observations for a fixed fill")
                    resampled_counts.append(denominator);samples.append(numerator/denominator)
                samples.sort()
                absolute[arm][fill][metric]={"point_mean":statistics.mean(_float(r[metric],metric) for r in rows),
                    "low_95":_quantile7(samples,.025),"high_95":_quantile7(samples,.975),
                    "fixed_n":63,"resampled_rows_min":min(resampled_counts),
                    "resampled_rows_max":max(resampled_counts),"descriptive_only":True}
    for arm in ARMS[1:]:
        paired[arm]={}
        arm_lookup={(r["expiry"],r["fill"]):r for r in arm_rows[arm]}
        for fill in FILLS:
            paired[arm][fill]={}
            for metric in METRICS:
                deltas=[]
                for key,base_row in base_lookup.items():
                    if key[1]!=fill: continue
                    row=arm_lookup[key]
                    deltas.append({"period":period,"expiry":key[0],"fill":fill,
                                   metric:_float(row[metric],metric)-_float(base_row[metric],metric)})
                if len(deltas)!=63: raise ValueError(f"paired 2022 denominator mismatch for {arm}/{fill}/{metric}")
                stats=cluster_stats(deltas,fill,metric);samples=[];resampled_counts=[]
                for weights in draw_weights:
                    numerator=sum(weight*stats.get(week,(0.0,0))[0] for week,weight in weights.items())
                    denominator=sum(weight*stats.get(week,(0.0,0))[1] for week,weight in weights.items())
                    if denominator<=0: raise ValueError("paired bootstrap draw has no observations for a fixed fill")
                    resampled_counts.append(denominator);samples.append(numerator/denominator)
                samples.sort();point=statistics.mean(row[metric] for row in deltas)
                paired[arm][fill][metric]={"mean_difference":point,"low_95":_quantile7(samples,.025),
                    "high_95":_quantile7(samples,.975),"fixed_n":63,
                    "resampled_rows_min":min(resampled_counts),"resampled_rows_max":max(resampled_counts),
                    "descriptive_only":True}
    for fill in FILLS:
        nonadditivity[fill]={}
        for metric in METRICS:
            means={arm:absolute[arm][fill][metric]["point_mean"] for arm in ARMS}
            singles=sum(means[a]-means[ARMS[0]] for a in ARMS[1:4])
            nonadditivity[fill][metric]={"total_nonadditivity_residual":
                (means[ARMS[4]]-means[ARMS[0]])-singles,
                "meaning":"combined-minus-baseline minus the sum of three single-source effects; not a pairwise interaction"}
    return {"status":"DESCRIPTIVE_ONLY","period":"2022","draws":BOOTSTRAP_DRAWS,"seed":BOOTSTRAP_SEED,
        "cluster":"ISO year/week","quantile":"linear type 7","shared_week_draws_across_all_arms_and_fills":True,
        "bootstrap_week_count":len(weeks),"primary_fill":"full_cross","absolute":absolute,"paired":paired,
        "nonadditivity":nonadditivity,"2019":{"status":"DESCRIPTIVE_ROWS_AND_MEANS_ONLY","intervals":"NOT COMPUTED"}}


def source_preflight()->dict:
    """Check retained sources, frozen controls, selections and coverage without ledger calculations."""
    started_utc=datetime.now(timezone.utc)
    started_clock=time.perf_counter()
    repo=Path(__file__).resolve().parents[2]
    code_path=Path(__file__).resolve();code_data=code_path.read_bytes()
    identity={"head":"SOURCE_PREFLIGHT_NO_GIT_IDENTITY","clean":False,
        "code":{"src/spyspx/optionmetrics_stockrefs.py":{"path":str(code_path),
            "bytes":len(code_data),"sha256":sha256(code_data)}}}
    _validate_frozen_metadata(repo,identity)  # Fail on stale metadata before hashing/scanning archives.
    inventory,wrds_records=_source_inventory()
    bindings=_snapshot_bindings(repo,identity,inventory,wrds_records)
    expected_selection="335a0266a9c556d97bf7ecb26c7e7f9691273aa253d133e973032a11513300ac"
    previous_path=repo/"planning/optionmetrics-stockrefs-20261029/source-preflight-v2-final.stdout"
    previous_bytes=previous_path.read_bytes()
    previous_sha=sha256(previous_bytes)
    if previous_sha!="a42fe4847f267410848b7502350c3ef3bdb0c241fadf17c3f0dc4f28531eda34":
        raise ValueError("retained broad source-preflight control receipt changed")
    previous=json.loads(previous_bytes)
    if (previous.get("status")!="SOURCE_PREFLIGHT_NOT_RUN" or
            previous.get("selection_sha256")!=expected_selection or
            previous.get("fixed_pair_fill_row_count")!=216 or previous.get("outcomes_calculated") is not False):
        raise ValueError("retained broad source-preflight control does not match the frozen population")
    m22,r22,a22,m19,r19,a19=_legacy_documents()
    saved=_saved_lookup(r22,r19)
    old22,old19=_legacy_references()
    q22=_quote_index("2022")
    q19_details={}
    q19=_quote_index("2019",diagnostics=q19_details)
    selection=_frozen_selection(r22,r19,q22,q19)
    if len(selection)!=216 or len(saved)!=216:
        raise ValueError("source preflight fixed 216 pair/fill rows are incomplete")
    pair_keys={(row["period"],row["entry"],row["expiry"]) for row in selection}
    if len(pair_keys)!=72: raise ValueError("source preflight fixed 72-pair denominator changed")
    arms={"status":"FROZEN_BEFORE_TERMINAL_JOIN_NOT_RUN","arms":list(ARMS),
        "primary":"wrds_all versus baseline_old_all","single_source_arms":list(ARMS[1:4]),
        "interaction_claim":"none; combined residual is total nonadditivity only"}
    selection_bytes=(json.dumps(selection,indent=2,sort_keys=True)+"\n").encode()
    arm_bytes=(json.dumps(arms,indent=2,sort_keys=True)+"\n").encode()
    bindings["selection_sha256"]=sha256(selection_bytes)
    bindings["arm_freeze_sha256"]=sha256(arm_bytes)
    if bindings["selection_sha256"]!=expected_selection:
        raise ValueError("optimized source preflight changed the retained fixed selection")
    audit=source_audit()
    price_path=WRDS_ROOT/"security-prices-20190801-20250829.csv"
    div_path=WRDS_ROOT/"distributions-20190801-20250829.csv"
    prices,_=read_stock_references(price_path.read_bytes())
    events,_=_confirmed_events(div_path.read_bytes())
    coverage=_period_coverage(selection,prices,events)
    for row in selection:
        expiry=date.fromisoformat(row["expiry"]);cover=date.fromisoformat(row["cover"])
        if row["period"]=="2022":
            if expiry not in old22["stocks"] or cover not in old22["stocks"] or expiry not in old22["settlements"]:
                raise ValueError(f"2022 old terminal source missing fixed date {expiry}")
        elif expiry not in old19["yahoo"] or cover not in old19["yahoo"] or expiry not in old19["settlements"] or expiry not in old19["spx"]:
            raise ValueError(f"2019 old terminal source missing fixed date {expiry}")
    ended_utc=datetime.now(timezone.utc)
    exact_argv=[sys.executable,"-m","spyspx.optionmetrics_stockrefs",*sys.argv[1:]]
    return {"status":"SOURCE_PREFLIGHT_NOT_RUN","outcomes_calculated":False,
        "ledger_or_pnl_calculated":False,"git_clean_sha":"NOT_REQUIRED_FOR_SOURCE_PREFLIGHT",
        "bindings_validated":True,"original_receipt_count":19,"legacy_code_file_count":8,
        "legacy_dependency_count":2,"control_artifact_count":6,
        "fixed_pair_count":72,"fixed_pair_fill_row_count":216,"entry_quote_identity_and_cash":"PASS",
        "five_arm_freeze_sha256":bindings["arm_freeze_sha256"],
        "selection_sha256":bindings["selection_sha256"],"source_coverage_rows":len(coverage),
        "quote_index":{"2019":q19_details,"2022":"UNCHANGED_READ_ZIP_PATH"},
        "broad_preflight_differential":{"status":"PASS",
            "prior_stdout_path":str(previous_path),"prior_stdout_bytes":len(previous_bytes),
            "prior_stdout_sha256":previous_sha,"prior_selection_sha256":previous["selection_sha256"],
            "prior_code_sha256":"59834b8cd2fbeb5268f55b79d329091103d28e8ff99d98de0f7912c27d844657",
            "optimized_selection_sha256":bindings["selection_sha256"],
            "optimized_code_sha256":sha256(code_data),"fixed_entry_quote_and_cash_rows":216},
        "runtime":{"argv":exact_argv,"cwd":os.getcwd(),"started_utc":started_utc.isoformat(),
            "ended_utc":ended_utc.isoformat(),"duration_seconds":time.perf_counter()-started_clock},
        "missing_dates":[],"source_audit":audit}


def _run_metadata(command:str,argv:list[str],started:datetime)->dict:
    return {"command":command,"argv":argv,"cwd":os.getcwd(),"started_utc":started.isoformat(),
        "model_endpoint":"N/A_DETERMINISTIC_HISTORICAL_CALCULATION","endpoint":"N/A_DETERMINISTIC_HISTORICAL_CALCULATION",
        "interpreter":sys.executable,"python":sys.version,"platform":platform.platform(),"host":socket.gethostname(),
        "runtime":"local deterministic historical calculation; evaluation status is carried by the run receipt"}


def _validate_output(repo:Path,path:Path)->Path:
    absolute=path if path.is_absolute() else repo/path
    absolute=absolute.resolve()
    root=(repo/"runs/optionmetrics_stockrefs").resolve()
    try:
        absolute.relative_to(root)
        if absolute==root: raise ValueError("output must be a tagged child of runs/optionmetrics_stockrefs")
    except ValueError as exc: raise ValueError("output must be a fresh child of runs/optionmetrics_stockrefs") from exc
    if absolute.exists(): raise FileExistsError(f"output already exists: {absolute}")
    absolute.parent.mkdir(parents=True,exist_ok=True)
    result=subprocess.run(["git","check-ignore","-q",str(absolute)],cwd=repo,check=False)
    if result.returncode: raise ValueError("output path is not ignored by Git")
    return absolute


def _validate_baseline_receipt(receipt_path:Path,bindings:dict)->dict:
    if not receipt_path.is_file(): raise ValueError("evaluate requires a retained successful baseline-parity receipt")
    receipt=json.loads(receipt_path.read_text())
    if receipt.get("status")!="PASS" or receipt.get("receipt_type")!="SPYSPX235_BASELINE_PARITY":
        raise ValueError("baseline parity receipt is not successful or has wrong type")
    if receipt.get("bindings")!=bindings:
        raise ValueError("baseline parity receipt does not bind the identical code, protocol, inputs and selection")
    baseline_file=receipt_path.with_name("baseline_rows.json")
    if not baseline_file.is_file() or sha256(baseline_file.read_bytes())!=receipt.get("baseline_rows_sha256"):
        raise ValueError("baseline parity rows do not match the retained receipt")
    manifest_path=receipt_path.with_name("manifest.json")
    if not manifest_path.is_file(): raise ValueError("baseline parity receipt has no retained bundle manifest")
    manifest=json.loads(manifest_path.read_text())
    if (manifest.get("status")!="BASELINE_PARITY_PASS_VARIANTS_NOT_RUN" or
            manifest.get("bindings")!=bindings or
            manifest.get("output_sha256",{}).get("baseline-parity.json")!=sha256(receipt_path.read_bytes()) or
            manifest.get("output_sha256",{}).get("baseline_rows.json")!=sha256(baseline_file.read_bytes())):
        raise ValueError("baseline parity bundle manifest does not validate the retained receipt")
    return receipt


def _lead_command(command:str,output:Path,*,baseline_receipt:Path|None=None,argv:list[str]|None=None)->dict:
    repo=Path(__file__).resolve().parents[2]
    started=datetime.now(timezone.utc)
    identity=_identity(repo)  # clean committed HEAD and imported source blobs before input reads
    inventory,wrds_records=_source_inventory()
    m22,r22,a22,m19,r19,a19=_legacy_documents()
    saved=_saved_lookup(r22,r19)
    q22=_quote_index("2022");q19=_quote_index("2019")
    selection=_frozen_selection(r22,r19,q22,q19)
    selection_bytes=(json.dumps(selection,indent=2,sort_keys=True)+"\n").encode()
    arms_doc={"status":"FROZEN_BEFORE_TERMINAL_JOIN_NOT_RUN","arms":list(ARMS),
        "primary":"wrds_all versus baseline_old_all","single_source_arms":list(ARMS[1:4]),
        "interaction_claim":"none; combined residual is total nonadditivity only"}
    arm_bytes=(json.dumps(arms_doc,indent=2,sort_keys=True)+"\n").encode()
    bindings=_snapshot_bindings(repo,identity,inventory,wrds_records)
    bindings["selection_sha256"]=sha256(selection_bytes)
    bindings["arm_freeze_sha256"]=sha256(arm_bytes)
    output=_validate_output(repo,output)
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=f".{output.name}.",dir=output.parent))
    try:
        # Persist the exact pairs, fills, cash and five arms before terminal-reference joins.
        _write_json(stage/"selection.json",json.loads(selection_bytes))
        _write_json(stage/"frozen-arms.json",arms_doc)
        if sha256((stage/"selection.json").read_bytes())!=bindings["selection_sha256"]:
            raise ValueError("durable fixed selection hash mismatch")
        audit=source_audit()
        prices_raw=(WRDS_ROOT/"security-prices-20190801-20250829.csv").read_bytes()
        div_raw=(WRDS_ROOT/"distributions-20190801-20250829.csv").read_bytes()
        wrds_prices,_=read_stock_references(prices_raw)
        wrds_events,_=_confirmed_events(div_raw)
        _integrity_check(repo,identity,bindings,selection_bytes,arm_bytes)
        coverage=_period_coverage(selection,wrds_prices,wrds_events)
        old22,old19=_legacy_references()
        _integrity_check(repo,identity,bindings,selection_bytes,arm_bytes)
        if command=="baseline-parity":
            baseline,parity=_compute_baseline(selection,saved,old22,old19,a22,a19)
            base_bytes=(json.dumps(baseline,indent=2,sort_keys=True,default=str)+"\n").encode()
            receipt={"status":"PASS","receipt_type":"SPYSPX235_BASELINE_PARITY",
                "bindings":bindings,"baseline_rows_sha256":sha256(base_bytes),"parity":parity,
                "NOT_RUN":"All five source-reference variants remain NOT RUN."}
            baseline_attribution=[{k:r[k] for k in ("period","entry","expiry","cover","fill","assigned",
                "spy_close","cover_open","stock_overnight_attribution","stock_neutralized_pnl","dividend_carry_amount",
                "dividend_carry_dates","base_cost_pnl","stress_cost_pnl")} for r in baseline]
            docs={"selection.json":selection,"frozen-arms.json":arms_doc,"baseline_rows.json":baseline,
                "baseline-attribution-rows.json":baseline_attribution,"baseline-summaries.json":_arm_summaries({ARMS[0]:baseline}),
                "source-audit.json":audit,"coverage.json":{"status":"SOURCE_COVERAGE_PASS_NOT_EVALUATED","rows":coverage},
                "baseline-parity.json":receipt,"run_metadata.json":_run_metadata(command,argv or sys.argv,started)}
        elif command=="evaluate":
            if baseline_receipt is None: raise ValueError("evaluate requires a retained successful baseline-parity receipt")
            receipt=_validate_baseline_receipt(baseline_receipt,bindings)
            baseline_file=baseline_receipt.with_name("baseline_rows.json")
            _integrity_check(repo,identity,bindings,selection_bytes,arm_bytes)
            baseline,parity=_compute_baseline(selection,saved,old22,old19,a22,a19)
            rows_by_arm=evaluate_rows(selection,old22,old19,wrds_prices,wrds_events)
            for arm in ARMS:
                if arm==ARMS[0]:
                    # The baseline arm is the independently replayed ledger, not copied saved outcomes.
                    rows_by_arm[arm]=baseline
            coverage_doc={"status":"COMPLETE_SOURCE_COVERAGE","rows":coverage}
            docs={"selection.json":selection,"frozen-arms.json":arms_doc,"arm-rows.json":rows_by_arm,
                "attribution-rows.json":{arm:[{k:r[k] for k in ("period","entry","expiry","cover","fill","assigned",
                    "spy_close","cover_open","stock_overnight_attribution","stock_neutralized_pnl","dividend_carry_amount",
                    "dividend_carry_dates","base_cost_pnl","stress_cost_pnl")} for r in rows] for arm,rows in rows_by_arm.items()},
                "summaries.json":_arm_summaries(rows_by_arm),"assignment-flips.json":_assignment_flips(rows_by_arm),
                "uncertainty.json":_uncertainty(rows_by_arm),
                "source-audit.json":audit,"coverage.json":coverage_doc,
                "baseline-parity-receipt.json":receipt,"baseline-replay-check.json":parity,
                "run_metadata.json":_run_metadata(command,argv or sys.argv,started)}
        else:
            raise ValueError(f"unsupported lead command {command}")
        _integrity_check(repo,identity,bindings,selection_bytes,arm_bytes)
        file_hashes={}
        for name,document in docs.items():
            if name in {"selection.json","frozen-arms.json"}:
                data=(stage/name).read_bytes()
            else:
                data=_write_json(stage/name,document)
            file_hashes[name]=sha256(data)
        run_status="BASELINE_PARITY_PASS_VARIANTS_NOT_RUN" if command=="baseline-parity" else "FIVE_ARM_HISTORICAL_SENSITIVITY_EVALUATED"
        manifest={"status":run_status,"historical_evaluation":"BASELINE PARITY ONLY" if command=="baseline-parity" else "KNOWN_DATA_SOURCE_SENSITIVITY",
            "model_endpoint":"N/A_DETERMINISTIC_HISTORICAL_CALCULATION","git_sha":identity["head"],"git_clean":True,
            "host":socket.gethostname(),"python":sys.version,"interpreter":sys.executable,
            "started_utc":started.isoformat(),"ended_utc":datetime.now(timezone.utc).isoformat(),
            "command":_run_metadata(command,argv or sys.argv,started),"bindings":bindings,
            "output_sha256":file_hashes,"selection_sha256":bindings["selection_sha256"],
            "checkpoints":{"clean_initial_head_and_imported_blob":"PASS","fixed_selection_and_five_arms_frozen":"PASS",
                "pre_terminal_source_code_control_protocol_integrity":"PASS","baseline_parity":"PASS" if command=="evaluate" else "PASS",
                "prepublication_integrity":"PASS","publication":"ATOMIC_NO_OVERWRITE"},
            "experiment_claim":"known-data sensitivity; not a holdout, execution test, or account return"}
        _write_json(stage/"manifest.json",manifest)
        _integrity_check(repo,identity,bindings,selection_bytes,arm_bytes)
        if output.exists(): raise FileExistsError(f"output already exists: {output}")
        os.rename(stage,output)
        return {"status":run_status,"output":str(output),"selection_sha256":bindings["selection_sha256"]}
    except Exception:
        shutil.rmtree(stage,ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    audit=sub.add_parser("source-audit",help="source checks only; calculates no P&L")
    audit.add_argument("--wrds-root",type=Path,default=WRDS_ROOT)
    audit.add_argument("--calendar",type=Path,default=CALENDAR)
    preflight=sub.add_parser("source-preflight",help="verify frozen source bindings and fixed selection; calculates no P&L")
    parity=sub.add_parser("baseline-parity",help="lead command: independently replay and compare both legacy baselines")
    parity.add_argument("--output",type=Path,required=True)
    evaluate=sub.add_parser("evaluate",help="lead command: five arms require a matching baseline-parity receipt")
    evaluate.add_argument("--baseline-receipt",type=Path,required=True)
    evaluate.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.command=="source-audit":
        json.dump(source_audit(args.wrds_root,args.calendar),sys.stdout,indent=2,sort_keys=True,default=str)
        sys.stdout.write("\n");return 0
    if args.command=="source-preflight":
        json.dump(source_preflight(),sys.stdout,indent=2,sort_keys=True,default=str)
        sys.stdout.write("\n");return 0
    if argv is None:
        if Path(sys.argv[0]).resolve()==Path(__file__).resolve():
            exact_argv=[sys.executable,"-m","spyspx.optionmetrics_stockrefs",*sys.argv[1:]]
        else:
            exact_argv=[sys.executable,*sys.argv]
    else:
        exact_argv=[sys.executable,"-m","spyspx.optionmetrics_stockrefs",*argv]
    result=_lead_command(args.command,args.output,
        baseline_receipt=args.baseline_receipt if args.command=="evaluate" else None,
        argv=exact_argv)
    json.dump(result,sys.stdout,indent=2,sort_keys=True);sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
