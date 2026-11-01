"""Source audit and frozen theoretical August 2019 expiry replication."""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import math
import random
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

from .expiry_extension import cost_adjusted, expiry_ledger, fill_cash_terms, fill_credits, select_official
from .expiry_payoff import Quote, OSI

OPTION_FIELDS = ("UnderlyingSymbol", "UnderlyingPrice", "Exchange", "OptionSymbol", "OptionExt", "Type", "Expiration", "DataDate", "Strike", "Last", "Bid", "Ask", "Volume", "OpenInterest", "IV", "Delta", "Gamma", "Theta", "Vega", "AKA")
STOCK_FIELDS = ("symbol", "quotedate", "open", "high", "low", "close", "volume", "adjustedclose")
EXPECTED_EXPIRIES = tuple(date.fromisoformat(x) for x in ("2019-08-02", "2019-08-07", "2019-08-09", "2019-08-14", "2019-08-16", "2019-08-21", "2019-08-23", "2019-08-28", "2019-08-30"))
PRIMARY_DRAWS, PRIMARY_SEED = 10_000, 20261028
RECEIPT_NAMES = ("Sample_L2_2019_August.zip", "cboe_W_2019.json", "cboe_M_2019.json", "cboe_S_2019.json", "SPX_History.csv", "yahoo_SPY_20190801_20190904.json", "provider_sample_files.html", "provider_data_structure.html")
DATE_FILE = re.compile(r"L2_(options|stockquotes)_(\d{8})\.csv$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _date(text: str) -> date:
    return datetime.strptime(text.strip(), "%m/%d/%Y").date()


def _number(value, *, positive=False):
    x = float(value)
    if not math.isfinite(x) or (positive and x <= 0):
        raise ValueError("invalid numeric value")
    return x


def validate_receipt(root: Path, receipt_path: Path) -> dict:
    doc = json.loads(receipt_path.read_text(encoding="utf-8"))
    records = doc.get("files", [])
    by_name: dict[str, list] = defaultdict(list)
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            by_name[Path(record["path"]).name].append(record)
    entries = []
    for name in (*RECEIPT_NAMES, receipt_path.name):
        p = root / name
        matches = by_name.get(name, [])
        if name == receipt_path.name:
            # The receipt contains source file hashes, not a self-hash.
            entries.append({"basename": name, "status": "PRESENT", "bytes": p.stat().st_size, "sha256": sha256(p)})
            continue
        problems = []
        if len(matches) != 1:
            problems.append("receipt_missing_or_duplicate")
        if not p.is_file():
            problems.append("file_missing")
        if len(matches) == 1 and p.is_file():
            rec = matches[0]
            if rec.get("bytes") != p.stat().st_size:
                problems.append("byte_count_mismatch")
            if str(rec.get("sha256", "")).lower() != sha256(p):
                problems.append("sha256_mismatch")
        entries.append({"basename": name, "status": "FAIL" if problems else "PASS", "problems": problems,
                        "bytes": p.stat().st_size if p.is_file() else None, "sha256": sha256(p) if p.is_file() else None})
    failed = any(x["status"] == "FAIL" for x in entries)
    return {"status": "FAIL" if failed else "PASS", "receipt_status": doc.get("status"), "use_scope": doc.get("use_scope"), "entries": entries}


def _parse_option_file(z: zipfile.ZipFile, member: str, filename_day: date, counts: Counter, target_quotes: list, target_days: set, spy_underlying: dict | None = None):
    with z.open(member) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
        if tuple(reader.fieldnames or ()) != OPTION_FIELDS:
            counts["options_schema_invalid_files"] += 1
            return
        counts["options_schema_valid_files"] += 1
        for row in reader:
            counts["option_rows_scanned"] += 1
            try:
                qday, expiry = _date(row["DataDate"]), _date(row["Expiration"])
                if qday != filename_day:
                    counts["options_filename_date_conflicts"] += 1
                    continue
                root = row["UnderlyingSymbol"].strip().upper()
                if root == "SPY" and spy_underlying is not None:
                    try:
                        spy_underlying.setdefault(qday, set()).add(_number(row["UnderlyingPrice"], positive=True))
                    except (KeyError, ValueError, TypeError):
                        counts["invalid_spy_option_underlying"] += 1
                if root not in ("SPY", "SPXW", "SPX"):
                    continue
                target_days.add(qday)
                if root == "SPX":
                    counts["excluded_spx_am_contract_rows"] += 1
                    continue
                symbol = row["OptionSymbol"].strip().upper()
                osi = OSI.fullmatch(symbol)
                aka = row["AKA"].strip().upper()
                if not osi or aka != symbol:
                    counts["option_identity_invalid"] += 1
                    continue
                osi_root, ymd, right, strike_milli = osi.groups()
                osi_expiry = date(2000 + int(ymd[:2]), int(ymd[2:4]), int(ymd[4:]))
                strike = _number(row["Strike"], positive=True)
                if (osi_root != root or osi_expiry != expiry or right != ("C" if row["Type"].strip().lower() == "call" else "P")
                        or abs(int(strike_milli) / 1000 - strike) > 1e-8):
                    counts["option_identity_conflict"] += 1
                    continue
                if row["Type"].strip().lower() != "call" or (expiry - qday).days != 1:
                    continue
                bid, ask = _number(row["Bid"]), _number(row["Ask"])
                if bid <= 0 or ask <= 0 or ask < bid:
                    counts["invalid_bid_ask"] += 1
                    continue
                under = _number(row["UnderlyingPrice"], positive=True)
                target_quotes.append(Quote(symbol, root, expiry, "call", strike, "A" if root == "SPY" else "E", qday, bid, ask, under, "PM"))
            except (KeyError, ValueError, TypeError, OverflowError):
                counts["malformed_option_rows"] += 1


def _parse_stock_file(z: zipfile.ZipFile, member: str, filename_day: date, counts: Counter, stocks: dict, sessions: set):
    with z.open(member) as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
        if tuple(reader.fieldnames or ()) != STOCK_FIELDS:
            counts["stock_schema_invalid_files"] += 1
            return
        counts["stock_schema_valid_files"] += 1
        for row in reader:
            if row.get("symbol", "").strip().upper() != "SPY":
                continue
            counts["stock_spy_rows_scanned"] += 1
            try:
                day = _date(row["quotedate"])
            except (KeyError, ValueError, TypeError):
                counts["stock_invalid_date"] += 1
                continue
            sessions.add(day)
            if day != filename_day:
                counts["stock_filename_date_conflicts"] += 1
                continue
            try:
                op, close = _number(row["open"], positive=True), _number(row["close"], positive=True)
                adjusted = _number(row["adjustedclose"], positive=True)
                if day in stocks:
                    counts["stock_duplicate_dates"] += 1
                    if stocks[day] != {"open": op, "close": close, "adjustedclose": adjusted}:
                        counts["stock_conflicting_duplicates"] += 1
                        stocks[day] = None
                else:
                    stocks[day] = {"open": op, "close": close, "adjustedclose": adjusted}
            except (KeyError, ValueError, TypeError, OverflowError):
                counts["stock_invalid_price_rows"] += 1
                stocks[day] = None


def parse_cboe_pm(path: Path, counts: Counter) -> dict[date, dict]:
    """Read W/M HTML table rows, accepting only exact SPXW/SPX identity."""
    text = json.loads(path.read_text(encoding="utf-8-sig"))["data"]
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.I | re.S)
    found: dict[date, dict] = {}
    conflicted: set[date] = set()
    for row in rows:
        cells = [html.unescape(re.sub(r"<[^>]+>", "", x)).replace("\ufeff", "").strip() for x in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, flags=re.I | re.S)]
        if len(cells) != 5:
            continue
        if cells[1].strip() != "SPXW" or cells[3].strip() != "SPX":
            continue
        try:
            day = _date(cells[2])
            value_text = cells[4].strip()
            annotated = value_text.endswith("*")
            if annotated:
                value_text = value_text[:-1].strip()
            value = _number(value_text, positive=True)
        except (ValueError, TypeError):
            counts["cboe_invalid_spxw_pm_rows"] += 1
            continue
        if day.year != 2019 or day.month != 8:
            continue
        record = {"value": value, "trading_symbol": cells[1], "settlement_symbol": cells[3], "source": path.name, "footnote_marker": annotated}
        if day in found and found[day] != record:
            conflicted.add(day)
            counts["cboe_conflicting_duplicates"] += 1
        else:
            if day in found:
                counts["cboe_consistent_duplicates"] += 1
            found[day] = record
    for day in conflicted:
        found.pop(day, None)
    return found


def read_spx(path: Path, counts: Counter) -> dict[date, float]:
    result, conflicts = {}, set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != ("DATE", "SPX"):
            raise ValueError("SPX_History.csv schema must be DATE,SPX")
        for row in reader:
            try:
                day = _date(row["DATE"])
                value = _number(row["SPX"], positive=True)
            except (ValueError, TypeError):
                counts["spx_invalid_rows"] += 1
                continue
            if day.year != 2019 or day.month != 8:
                continue
            if day in result and result[day] != value:
                conflicts.add(day)
                counts["spx_conflicting_duplicates"] += 1
            else:
                result[day] = value
    for day in conflicts:
        result.pop(day, None)
    return result


def read_yahoo(path: Path, counts: Counter):
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = doc["chart"]["result"][0]
    if result["meta"].get("symbol") != "SPY" or result["meta"].get("exchangeTimezoneName") != "America/New_York":
        raise ValueError("Yahoo payload symbol/timezone mismatch")
    zone = ZoneInfo("America/New_York")
    quote = result["indicators"]["quote"][0]
    rows = {}
    timestamps = result.get("timestamp", [])
    if len(quote.get("open", [])) != len(timestamps) or len(quote.get("close", [])) != len(timestamps):
        raise ValueError("Yahoo raw quote arrays do not match timestamp count")
    for i, timestamp in enumerate(timestamps):
        day = datetime.fromtimestamp(timestamp, zone).date()
        if day in rows:
            raise ValueError("Yahoo payload contains duplicate session dates")
        op = quote.get("open", [])[i]
        close = quote.get("close", [])[i]
        try:
            op, close = _number(op, positive=True), _number(close, positive=True)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Yahoo payload has invalid raw open/close for {day}") from exc
        rows[day] = {"open": op, "close": close}
    events = result.get("events")
    if "events" not in result:
        events = {"dividends": {}, "splits": {}}
        counts["yahoo_event_calendar_status"] = "NO_EVENTS_KEY_RETURNED"
    elif not isinstance(events, dict) or not isinstance(events.get("dividends"), dict) or not isinstance(events.get("splits"), dict):
        raise ValueError("Yahoo payload has malformed present event records")
    else:
        counts["yahoo_event_calendar_status"] = "EVENTS_KEY_RETURNED"
    event_doc = events
    events = event_doc["dividends"]
    dividends = []
    for event in events.values():
        day = datetime.fromtimestamp(event["date"], zone).date()
        dividends.append((day, _number(event["amount"])))
    counts["yahoo_sessions"] = len(rows)
    counts["yahoo_dividend_events"] = len(dividends)
    counts["yahoo_splits"] = len(event_doc["splits"])
    return rows, sorted(dividends)


def audit_sources(root: Path, receipt_path: Path) -> dict:
    counts = Counter()
    receipt = validate_receipt(root, receipt_path)
    required_members = set()
    quotes: list[Quote] = []
    spy_option_underlying: dict[date, set[float]] = {}
    stocks: dict[date, dict | None] = {}
    sessions: set[date] = set()
    zip_path = root / "Sample_L2_2019_August.zip"
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            base = PurePosixPath(name).name
            match = DATE_FILE.fullmatch(base)
            if not _daily_member(match, name):
                counts["ignored_zip_members"] += 1
                continue
            kind, ymd = match.groups()
            day = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
            required_members.add((kind, day))
            if kind == "options":
                _parse_option_file(z, name, day, counts, quotes, set(), spy_option_underlying)
            else:
                _parse_stock_file(z, name, day, counts, stocks, sessions)
    counts["archive_member_count"] = len(required_members)
    counts["options_daily_files"] = sum(kind == "options" for kind, _ in required_members)
    counts["stock_daily_files"] = sum(kind == "stockquotes" for kind, _ in required_members)
    counts["option_quote_candidates"] = len(quotes)
    counts["stock_provider_sessions"] = len(sessions)
    option_close_shared = sorted(set(spy_option_underlying) & set(stocks))
    option_close_diffs = [abs(next(iter(spy_option_underlying[d])) - stocks[d]["close"]) for d in option_close_shared
                          if len(spy_option_underlying[d]) == 1 and stocks[d] is not None]
    counts["spy_option_underlying_close_match_dates"] = sum(x <= 1e-8 for x in option_close_diffs)
    counts["spy_option_underlying_close_conflict_dates"] = sum(x > 1e-8 for x in option_close_diffs)
    w = parse_cboe_pm(root / "cboe_W_2019.json", counts)
    m = parse_cboe_pm(root / "cboe_M_2019.json", counts)
    settlements = dict(w)
    for day, record in m.items():
        if day in settlements and settlements[day]["value"] != record["value"]:
            counts["cboe_crossfile_conflicts"] += 1
            settlements.pop(day, None)
        else:
            if day in settlements:
                counts["cboe_crossfile_consistent_duplicates"] += 1
            settlements[day] = record
    counts["cboe_w_pm_dates"] = len(w)
    counts["cboe_m_pm_dates"] = len(m)
    counts["cboe_pm_dates_union"] = len(set(w) | set(m))
    counts["expected_primary_expiries_with_w_pm"] = sum(d in w and not w[d]["footnote_marker"] for d in EXPECTED_EXPIRIES)
    counts["cboe_legacy_s_excluded"] = 1
    spx = read_spx(root / "SPX_History.csv", counts)
    try:
        yahoo, dividends = read_yahoo(root / "yahoo_SPY_20190801_20190904.json", counts)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        yahoo, dividends = {}, []
        counts["yahoo_payload_error"] = str(exc)
    overlap = sorted(set(yahoo) & set(stocks))
    diffs = [abs(yahoo[d]["close"] - stocks[d]["close"]) for d in overlap if stocks[d] is not None and isinstance(yahoo[d].get("close"), (float, int))]
    open_diffs = [abs(yahoo[d]["open"] - stocks[d]["open"]) for d in overlap if stocks[d] is not None and isinstance(yahoo[d].get("open"), (float, int))]
    counts["yahoo_provider_close_overlap"] = len(diffs)
    counts["yahoo_close_mismatch_over_1c"] = sum(x > .01 for x in diffs)
    counts["yahoo_provider_open_overlap"] = len(open_diffs)
    counts["yahoo_open_mismatch_over_1c"] = sum(x > .01 for x in open_diffs)
    counts["yahoo_august_dates_with_valid_raw_open_close"] = sum(d in yahoo and all(isinstance(yahoo[d].get(k), (int, float)) and math.isfinite(yahoo[d][k]) and yahoo[d][k] > 0 for k in ("open", "close")) for d in sessions)
    counts["expected_primary_expiries"] = len(EXPECTED_EXPIRIES)
    counts["expected_primary_expiries_with_pm"] = sum(d in settlements and not settlements[d]["footnote_marker"] for d in EXPECTED_EXPIRIES)
    counts["expected_primary_expiries_with_spx"] = sum(d in spx for d in EXPECTED_EXPIRIES)
    counts["expected_primary_expiries_with_provider_stock"] = sum(d in stocks and stocks[d] is not None for d in EXPECTED_EXPIRIES)
    count_sessions = sorted(sessions | set(yahoo) | {date(2019, 9, 3)})
    next_by_expiry = {d: next((s for s in count_sessions if s > d), None) for d in EXPECTED_EXPIRIES}
    counts["expected_primary_expiries_with_first_next_session"] = sum(v is not None and v in yahoo and isinstance(yahoo[v].get("open"), (float, int)) and math.isfinite(yahoo[v]["open"]) and yahoo[v]["open"] > 0 for v in next_by_expiry.values())
    counts["yahoo_appended_dates"] = sum(d not in sessions for d in yahoo if d > max(sessions, default=date.min))
    counts["cboe_aug12_footnote_marker"] = int(date(2019, 8, 12) in settlements and settlements[date(2019, 8, 12)]["footnote_marker"])
    checks = {
        "receipt": receipt["status"] == "PASS",
        "archive_has_22_option_and_stock_days": counts["options_daily_files"] == 22 and counts["stock_daily_files"] == 22,
        "all_daily_schemas_valid": counts["options_schema_valid_files"] == 22 and counts["stock_schema_valid_files"] == 22,
        "all_primary_pm_settlements": counts["expected_primary_expiries_with_pm"] == len(EXPECTED_EXPIRIES),
        "all_primary_expiries_in_weekly_pm_source": counts["expected_primary_expiries_with_w_pm"] == len(EXPECTED_EXPIRIES),
        "weekly_august_calendar_and_aug12_annotation_present": counts["cboe_w_pm_dates"] == 13 and counts["cboe_aug12_footnote_marker"] == 1,
        "all_primary_official_spx_closes": counts["expected_primary_expiries_with_spx"] == len(EXPECTED_EXPIRIES),
        "all_primary_raw_spy_closes": counts["expected_primary_expiries_with_provider_stock"] == len(EXPECTED_EXPIRIES),
        "all_primary_first_next_session_quotes": counts["expected_primary_expiries_with_first_next_session"] == len(EXPECTED_EXPIRIES),
        "provider_stock_raw_rows_valid": counts["stock_invalid_price_rows"] == 0 and counts["stock_conflicting_duplicates"] == 0 and len(stocks) == 22,
        "spy_option_underlying_matches_provider_close": counts["spy_option_underlying_close_match_dates"] == 22 and counts["spy_option_underlying_close_conflict_dates"] == 0,
        "yahoo_raw_august_coverage_complete": counts["yahoo_august_dates_with_valid_raw_open_close"] == 22,
        "yahoo_provider_opens_within_cent": len(open_diffs) == 22 and counts["yahoo_open_mismatch_over_1c"] == 0,
        "yahoo_has_first_september_session": date(2019, 9, 3) in yahoo and isinstance(yahoo[date(2019, 9, 3)].get("open"), (int, float)) and yahoo[date(2019, 9, 3)]["open"] > 0,
        "yahoo_has_no_splits": counts["yahoo_splits"] == 0,
        "official_spx_covers_all_provider_sessions": all(d in spx for d in sessions),
        "option_identity_and_filename_dates_clean": counts["option_identity_conflict"] == 0 and counts["options_filename_date_conflicts"] == 0,
        "stock_filename_dates_clean": counts["stock_filename_date_conflicts"] == 0,
    }
    return {"status": "source_audit_only", "integrity_status": "PASS" if receipt["status"] == "PASS" else "FAIL",
            "coverage_status": "PASS" if all(checks.values()) else "FAIL", "coverage_checks": checks,
            "receipt": receipt, "inputs": {name: {"path": str(root / name), "bytes": (root / name).stat().st_size, "sha256": sha256(root / name)} for name in (*RECEIPT_NAMES, receipt_path.name)},
            "coverage": {"primary_expiries": [d.isoformat() for d in EXPECTED_EXPIRIES], "first_next_sessions": {d.isoformat(): x.isoformat() if x else None for d, x in next_by_expiry.items()}, "provider_sessions": [d.isoformat() for d in sorted(sessions)], "official_spxw_pm_dates": [d.isoformat() for d in sorted(settlements)], "raw_spx_dates": [d.isoformat() for d in sorted(spx)]},
            "counts": dict(sorted(counts.items())), "provider_vs_yahoo_raw": {"overlap_count": len(diffs), "close_mismatches_over_0_01": sum(x > .01 for x in diffs), "close_max_abs_difference": max(diffs) if diffs else None, "close_mean_abs_difference": sum(diffs)/len(diffs) if diffs else None, "open_max_abs_difference": max(open_diffs) if open_diffs else None, "open_mismatches_over_0_01": sum(x > .01 for x in open_diffs), "close_status": "SOURCE_DISTINCTION_UNRESOLVED_TIMING", "close_reconciled": False},
            "limitations": ["SOURCE_AUDIT_ONLY_NO_OUTCOMES", "quotes have no timestamp", "no bid/ask sizes: UNAVAILABLE_SOURCE_NO_SIZES", "stock source has no dividend column; Yahoo event records used", "source close quotes are not evidence of fills", "legacy S table is AM settlement and excluded"]}


def load_study_inputs(root: Path, audit: dict | None = None):
    """Load raw rows for an authorized run. Never called by source-audit mode."""
    audit = audit if audit is not None else audit_sources(root, root / "replication-acquisition-receipt.json")
    if audit["integrity_status"] != "PASS" or audit["coverage_status"] != "PASS":
        raise ValueError("receipt, source, or coverage gate failed")
    counts = Counter()
    quotes: list[Quote] = []
    stocks: dict[date, dict | None] = {}
    sessions: set[date] = set()
    with zipfile.ZipFile(root / "Sample_L2_2019_August.zip") as z:
        for name in z.namelist():
            match = DATE_FILE.fullmatch(PurePosixPath(name).name)
            if not _daily_member(match, name):
                continue
            kind, ymd = match.groups(); day = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:]))
            if kind == "options": _parse_option_file(z, name, day, counts, quotes, set())
            else: _parse_stock_file(z, name, day, counts, stocks, sessions)
    settles = parse_cboe_pm(root / "cboe_W_2019.json", counts)
    for day, row in parse_cboe_pm(root / "cboe_M_2019.json", counts).items():
        if day in settles and settles[day]["value"] != row["value"]: settles.pop(day, None)
        else: settles[day] = row
    spx = read_spx(root / "SPX_History.csv", counts)
    yahoo, dividends = read_yahoo(root / "yahoo_SPY_20190801_20190904.json", counts)
    market_sessions = sorted(sessions | set(yahoo) | {date(2019, 9, 3)})
    following = {d: market_sessions[i + 1] for i, d in enumerate(market_sessions[:-1])}
    return audit, quotes, stocks, sessions, spx, settles, yahoo, dividends, following


def _daily_member(match, name):
    return bool(match) and PurePosixPath(name).parent.parts == ()


def select_primary_pairs(quotes, yahoo, spx):
    spy_closes = {d: r["close"] for d, r in yahoo.items() if isinstance(r.get("close"), (int, float)) and math.isfinite(r["close"]) and r["close"] > 0}
    selected = select_official(quotes, spy_closes, spx, {})
    selected = [pair for pair in selected if pair[0].expiration in EXPECTED_EXPIRIES]
    selected_by_expiry = {pair[0].expiration: pair for pair in selected}
    return selected_by_expiry


def primary_coverage_failures(quotes, stocks, spx, settlements, yahoo, following):
    selected = select_primary_pairs(quotes, yahoo, spx)
    failures = {}
    for expiry in EXPECTED_EXPIRIES:
        reasons = []
        pair = selected.get(expiry)
        if pair is None:
            reasons.append("missing_valid_selected_pair")
        if expiry not in settlements or settlements[expiry].get("footnote_marker"):
            reasons.append("missing_valid_spxw_pm_settlement")
        if expiry not in spx:
            reasons.append("missing_official_spx_close")
        if pair is not None:
            entry = pair[0].quote_date
            if entry not in yahoo or not _valid_price(yahoo[entry].get("close")):
                reasons.append("missing_yahoo_entry_raw_close")
            if entry not in spx:
                reasons.append("missing_official_entry_spx_close")
        if expiry not in yahoo or not _valid_price(yahoo[expiry].get("close")):
            reasons.append("missing_yahoo_expiry_raw_close")
        if expiry not in stocks or stocks[expiry] is None or not _valid_price(stocks[expiry].get("close")):
            reasons.append("missing_provider_terminal_control_close")
        next_day = following.get(expiry)
        if next_day is None:
            reasons.append("missing_first_next_session_date")
        elif next_day not in yahoo or not _valid_price(yahoo[next_day].get("open")):
            reasons.append("missing_first_next_session_yahoo_raw_open")
        if reasons:
            failures[expiry.isoformat()] = reasons
    return selected, failures


def _valid_price(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def build_pair_rows(quotes, stocks, spx, settlements, yahoo, dividends, following, selected_by_expiry=None):
    selected_by_expiry = selected_by_expiry if selected_by_expiry is not None else select_primary_pairs(quotes, yahoo, spx)
    rows, provider_control_rows = [], []
    for expiry in EXPECTED_EXPIRIES:
        if expiry not in selected_by_expiry:
            rows.append({"expiry_date": expiry.isoformat(), "status": "MISSING_SELECTION", "fill_rows": []})
            continue
        spy, idx, ratio = selected_by_expiry[expiry]
        entry = spy.quote_date
        entry_spy = yahoo.get(entry, {}).get("close"); entry_spx = spx.get(entry)
        rationale = {"spy": "nearest ATM by absolute strike/raw entry close distance, within 2 percent; then lower strike and contract", "spxw": "minimum normalized moneyness mismatch using official entry SPX, at most 0.001; then lower strike and contract", "entry_spy_close": entry_spy, "entry_spx_close": entry_spx, "ratio_spx_to_spy": ratio}
        next_day = following.get(expiry)
        stock_expiry = stocks.get(expiry)
        next_open = yahoo[next_day]["open"] if next_day in yahoo and _valid_price(yahoo[next_day].get("open")) else None
        settle = settlements.get(expiry)
        missing = []
        yahoo_expiry = yahoo.get(expiry)
        if yahoo_expiry is None or not isinstance(yahoo_expiry.get("close"), (int, float)) or not math.isfinite(yahoo_expiry["close"]) or yahoo_expiry["close"] <= 0: missing.append("missing_yahoo_raw_spy_expiry_close")
        if settle is None or settle.get("footnote_marker"): missing.append("missing_or_annotated_pm_settlement")
        if expiry not in spx: missing.append("missing_official_spx_reference")
        if next_day is None: missing.append("missing_first_next_session_date")
        elif next_open is None: missing.append("missing_first_next_session_raw_open")
        if missing:
            rows.append({"expiry_date": expiry.isoformat(), "entry_date": entry.isoformat(), "status": "MISSING_REFERENCE", "missing_inputs": missing,
                         "spy_contract": spy.contract, "spxw_contract": idx.contract, "selection_rationale": rationale, "next_session_date": next_day.isoformat() if next_day else None, "fill_rows": []})
            continue
        credits = fill_credits(spy, idx)
        primary_expiry_close = yahoo_expiry["close"]
        fill_rows = []
        for fill in ("midpoint", "halfway", "full_cross"):
            credit = credits[fill]
            ledger = expiry_ledger(spy=spy, idx=idx, credit=credit, expiry_close=primary_expiry_close, spxw_settlement=settle["value"], next_open=next_open,
                                   expiry_date=expiry, entry_date=entry, cover_date=next_day, dividends=dividends)
            if not ledger["complete_cover"] or abs(ledger["threshold_residual_cash"]) >= 10.0 + 1e-9:
                raise AssertionError("expiry ledger cover or threshold identity failed")
            days_entry_exit = (next_day - entry).days if ledger["assigned"] else (expiry - entry).days
            days_cover = (next_day - expiry).days if ledger["assigned"] else 0
            base = cost_adjusted(ledger["dividend_carry_pnl"], credit, ledger["assigned"], days_entry_exit, days_cover, primary_expiry_close)
            stress = cost_adjusted(ledger["dividend_carry_pnl"], credit, ledger["assigned"], days_entry_exit, days_cover, primary_expiry_close, stress=True)
            neutral = ledger["next_open_pnl"] - (1000 * (primary_expiry_close - next_open) if ledger["assigned"] else 0)
            if abs(neutral - ledger["conditional_close_mark_pnl"]) > 1e-8:
                raise AssertionError("stock-neutralized next-open identity failed")
            cash = fill_cash_terms(spy, idx, fill)
            record = {"fill": fill, "credit": credit, "direct_intrinsic_pnl": ledger["direct_intrinsic_pnl"], "conditional_close_mark_pnl": ledger["conditional_close_mark_pnl"],
                      "next_open_pnl": ledger["next_open_pnl"], "base_cost_pnl": base, "stress_cost_pnl": stress, "stock_neutralized_pnl": neutral,
                      "stock_neutralized_base_cost_pnl": base - (1000 * (primary_expiry_close - next_open) if ledger["assigned"] else 0),
                      "stock_neutralized_stress_cost_pnl": stress - (1000 * (primary_expiry_close - next_open) if ledger["assigned"] else 0),
                      "reverse_cross_control_pnl": credits["reverse_full_cross_control"] - (ledger["direct_intrinsic_pnl"] - credit),
                      "zero_control_pnl": 0.0,
                      "calendar_days_entry_to_exit": days_entry_exit, "calendar_days_expiry_to_cover": days_cover,
                      "spy_entry_cash": cash["spy_entry_cash"], "spxw_entry_cash": cash["spxw_entry_cash"],
                      "spy_entry_shares": cash["spy_entry_shares"], "spxw_entry_shares": cash["spxw_entry_shares"], **ledger}
            record["depth_status"] = "UNAVAILABLE_SOURCE_NO_SIZES"
            provider_close = stock_expiry["close"]
            provider_ledger = expiry_ledger(spy=spy, idx=idx, credit=credit, expiry_close=provider_close, spxw_settlement=settle["value"], next_open=next_open,
                                            expiry_date=expiry, entry_date=entry, cover_date=next_day, dividends=dividends)
            provider_days_exit = (next_day-entry).days if provider_ledger["assigned"] else (expiry-entry).days
            provider_days_cover = (next_day-expiry).days if provider_ledger["assigned"] else 0
            provider_base = cost_adjusted(provider_ledger["dividend_carry_pnl"], credit, provider_ledger["assigned"], provider_days_exit,
                                          provider_days_cover, provider_close)
            provider_stress = cost_adjusted(provider_ledger["dividend_carry_pnl"], credit, provider_ledger["assigned"], provider_days_exit,
                                            provider_days_cover, provider_close, stress=True)
            provider_control_rows.append({"reference_lane": "PROVIDER_TERMINAL_SNAPSHOT_CONTROL", "primary_selection_lane": "YAHOO_RAW_SPY_CLOSE", "expiry_date": expiry.isoformat(), "entry_date": entry.isoformat(),
                "fill": fill, "spy_contract": spy.contract, "spxw_contract": idx.contract, "credit": credit, "provider_spy_expiry_snapshot_close": provider_close,
                "yahoo_spy_first_next_session_raw_open": next_open, "official_spxw_pm_settlement": settle["value"], "direct_intrinsic_pnl": provider_ledger["direct_intrinsic_pnl"],
                "conditional_close_mark_pnl": provider_ledger["conditional_close_mark_pnl"], "next_open_pnl": provider_ledger["next_open_pnl"],
                "base_cost_pnl": provider_base, "stress_cost_pnl": provider_stress, "assigned_under_threshold_rule": provider_ledger["assigned"],
                "calendar_days_entry_to_exit": provider_days_exit, "calendar_days_expiry_to_cover": provider_days_cover,
                "threshold_residual_cash": provider_ledger["threshold_residual_cash"], "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES",
                "timing_status": "UNRESOLVED_PROVIDER_SNAPSHOT_CLOSE"})
            fill_rows.append(record)
        rows.append({"expiry_date": expiry.isoformat(), "entry_date": entry.isoformat(), "status": "COMPLETE_THEORETICAL_ROW", "missing_inputs": [], "spy_contract": spy.contract, "spxw_contract": idx.contract,
                     "spy_strike": spy.strike, "spxw_strike": idx.strike, "selection_rationale": rationale, "next_session_date": next_day.isoformat(),
                     "reference_lane": "PRIMARY_YAHOO_RAW_SPY_CLOSE", "spy_expiry_yahoo_raw_close": primary_expiry_close, "spy_provider_expiry_snapshot_close": stock_expiry["close"],
                     "spy_next_session_yahoo_raw_open": next_open, "spxw_pm_settlement": settle["value"],
                     "official_spx_expiry_close": spx[expiry], "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES", "fill_rows": fill_rows,
                     "reverse_cross_control_credit": credits["reverse_full_cross_control"], "zero_control_credit": 0.0})
    return rows, provider_control_rows


def _summary(values):
    present = [x for x in values if isinstance(x, (int, float)) and math.isfinite(x)]
    return {"n": len(present), "missing_n": len(values) - len(present), "mean": statistics.mean(present) if present else None,
            "median": statistics.median(present) if present else None, "min": min(present) if present else None, "max": max(present) if present else None,
            "positive_count": sum(x > 0 for x in present), "values": present}


def _quantile(sorted_values, probability):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def aggregate_rows(rows):
    complete = [r for r in rows if r.get("status") == "COMPLETE_THEORETICAL_ROW"]
    periods = {"all": complete}
    months = sorted({r["expiry_date"][:7] for r in complete})
    weeks = sorted({f"{date.fromisoformat(r['expiry_date']).isocalendar().year}-W{date.fromisoformat(r['expiry_date']).isocalendar().week:02d}" for r in complete})
    for month in months:
        periods[month] = [r for r in complete if r["expiry_date"].startswith(month)]
    for week in weeks:
        periods[week] = [r for r in complete if f"{date.fromisoformat(r['expiry_date']).isocalendar().year}-W{date.fromisoformat(r['expiry_date']).isocalendar().week:02d}" == week]
    metrics = ("direct_intrinsic_pnl", "conditional_close_mark_pnl", "next_open_pnl", "base_cost_pnl", "stress_cost_pnl", "stock_neutralized_pnl", "stock_neutralized_base_cost_pnl", "stock_neutralized_stress_cost_pnl", "reverse_cross_control_pnl", "zero_control_pnl")
    output = {}
    for period, subset in periods.items():
        if period == "all":
            expected = list(EXPECTED_EXPIRIES)
        elif "-W" in period:
            year, week = period.split("-W")
            expected = [d for d in EXPECTED_EXPIRIES if d.isocalendar().year == int(year) and d.isocalendar().week == int(week)]
        else:
            expected = [d for d in EXPECTED_EXPIRIES if d.strftime("%Y-%m") == period]
        output[period] = {"primary_expiry_count": len(subset), "expected_primary_expiry_count": len(expected), "missing_primary_expiry_count": len(expected) - len(subset), "expiry_dates": [r["expiry_date"] for r in subset], "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES", "fills": {}}
        for fill in ("midpoint", "halfway", "full_cross"):
            lane = [fr for row in subset for fr in row["fill_rows"] if fr["fill"] == fill]
            output[period]["fills"][fill] = {metric: _summary([r.get(metric) for r in lane]) for metric in metrics}
            output[period]["fills"][fill]["reverse_cross_control"] = _summary([r["reverse_cross_control_pnl"] for r in lane])
            output[period]["fills"][fill]["zero_control"] = _summary([r["zero_control_pnl"] for r in lane])
    return {"status": "INDEPENDENT_PERIOD_THEORETICAL_EVALUATED", "population": "one fixed primary pair per declared expiry; not a portfolio", "cohort_unit": "expiry", "cohorts": output}


def primary_attribution(rows, draws=PRIMARY_DRAWS, seed=PRIMARY_SEED):
    full = [row for row in rows if row.get("status") == "COMPLETE_THEORETICAL_ROW"]
    rows_out = []
    for row in full:
        fills = {x["fill"]: x for x in row["fill_rows"]}
        fx = fills["full_cross"]
        rows_out.append({"expiry_date": row["expiry_date"], "entry_date": row["entry_date"], "spy_contract": row["spy_contract"], "spxw_contract": row["spxw_contract"],
                         "direct_intrinsic_pnl": fx["direct_intrinsic_pnl"], "conditional_close_mark_pnl": fx["conditional_close_mark_pnl"], "next_open_pnl": fx["next_open_pnl"],
                         "base_cost_pnl": fx["base_cost_pnl"], "stress_cost_pnl": fx["stress_cost_pnl"], "stock_neutralized_pnl": fx["stock_neutralized_pnl"],
                         "overnight_short_stock_attribution": fx["next_open_pnl"] - fx["stock_neutralized_pnl"], "threshold_residual_cash": fx["threshold_residual_cash"],
                         "spy_leg_expiry_shares": fx["spy_leg_expiry_shares"], "spy_leg_next_open_shares": fx["spy_leg_next_open_shares"],
                         "complete_cover": fx["complete_cover"], "depth_status": row["depth_status"]})
    metrics = ("direct_intrinsic_pnl", "conditional_close_mark_pnl", "next_open_pnl", "base_cost_pnl", "stress_cost_pnl", "stock_neutralized_pnl", "overnight_short_stock_attribution")
    clusters = defaultdict(list)
    for row in rows_out:
        d = date.fromisoformat(row["expiry_date"]); iso = d.isocalendar(); clusters[f"{iso.year}-W{iso.week:02d}"].append(row)
    rng = random.Random(seed)
    summary = {metric: _summary([r[metric] for r in rows_out]) for metric in metrics}
    boot = {}
    keys = sorted(clusters)
    shared_draws = [[rng.choice(keys) for _ in keys] for _ in range(draws)] if keys else []
    for metric in metrics:
        samples = [sum(r[metric] for k in picked for r in clusters[k]) / sum(len(clusters[k]) for k in picked)
                   for picked in shared_draws]
        samples.sort()
        boot[metric] = {"draws": draws if keys else 0, "seed": seed, "iso_week_clusters": len(keys),
                       "low_95": _quantile(samples, .025), "high_95": _quantile(samples, .975),
                       "quantile_method": "linear_type_7", "shared_cluster_draws_across_metrics": True,
                       "draw_pairing": "same sampled ISO-week sequence for each primary metric"}
    return {"status": "DESCRIPTIVE_PRIMARY_ATTRIBUTION", "summary": summary, "iso_week_cluster_bootstrap": boot,
            "warning": "Nine declared expiry dates support descriptive summaries only; intervals do not establish significance or out-of-sample effectiveness."}, rows_out
