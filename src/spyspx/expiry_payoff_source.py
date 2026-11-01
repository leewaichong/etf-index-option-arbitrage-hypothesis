"""Streaming adapter for the public HistoricalData.net 34-column ZIP sample."""
from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import PurePosixPath
import re
import zipfile
from collections import Counter

from .expiry_payoff import Quote

SCHEMA = ("contract", "underlying", "expiration", "type", "strike", "style", "quote_date", "bid", "bid_size", "ask", "ask_size", "quote_time", "volume", "open_interest", "open", "high", "low", "close", "trade_vwap", "transactions", "multileg_volume", "active_minutes", "last_trade_date", "underlying_close", "settlement_time", "iv_bid", "iv_ask", "iv", "iv_flag", "delta", "gamma", "theta", "vega", "rho")
DAY_FILE = re.compile(r"(\d{4}-\d{2}-\d{2})_options\.csv$")


def read_zip(path):
    """Stream raw rows; retain only one-day call candidates and daily closes."""
    exclusions = Counter()
    terminal_values: dict[tuple[date, str], set[float]] = {}
    invalid_closes = set()
    quotes = []
    with zipfile.ZipFile(path) as archive:
        members = sorted((m for m in archive.infolist() if DAY_FILE.search(PurePosixPath(m.filename).name)), key=lambda m: m.filename)
        exclusions["daily_files"] = len(members)
        for info in members:
            # Only accept ordinary CSV files, never extract untrusted archive paths.
            if info.is_dir() or info.file_size > 100_000_000:
                exclusions["unsafe_or_oversize_member"] += 1
                continue
            filename_date = date.fromisoformat(DAY_FILE.search(PurePosixPath(info.filename).name).group(1))
            with archive.open(info) as raw:
                import io
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                header = tuple((reader.fieldnames or ()))
                if header != SCHEMA:
                    exclusions["schema_mismatch_file"] += 1
                    continue
                exclusions["schema_valid_files"] += 1
                day_quotes = []
                for row in reader:
                    exclusions["rows_scanned"] += 1
                    try:
                        u = (row["underlying"] or "").upper()
                        qd = date.fromisoformat(row["quote_date"])
                        exp = date.fromisoformat(row["expiration"])
                    except (KeyError, TypeError, ValueError):
                        exclusions["malformed_row"] += 1
                        continue
                    if u in {"SPY", "SPXW", "SPX"}:
                        exclusions[f"rows_{u}"] += 1
                    if qd != filename_date:
                        exclusions["filename_quote_date_mismatch"] += 1
                        continue
                    if u not in {"SPY", "SPXW"}:
                        continue
                    try:
                        uc = float(row["underlying_close"])
                    except (KeyError, TypeError, ValueError):
                        uc = float("nan")
                    if math.isfinite(uc) and uc > 0:
                        terminal_values.setdefault((qd, u), set()).add(uc)
                    else:
                        invalid_closes.add((qd, u))
                        exclusions["invalid_underlying_close_rows"] += 1
                    # Entry quotes only ever come from the calendar day before expiry.
                    if (row["type"] or "").lower() != "call" or (exp - qd).days != 1:
                        continue
                    try:
                        day_quotes.append(Quote(row["contract"].upper(), u, exp, row["type"], float(row["strike"]), row["style"], qd, float(row["bid"]), float(row["ask"]), uc, row["settlement_time"]))
                    except (KeyError, TypeError, ValueError):
                        exclusions["malformed_entry_quote"] += 1
                quotes.extend(day_quotes)
    terminal = {}
    conflicting_days = set()
    for key, values in terminal_values.items():
        if len(values) == 1 and key not in invalid_closes:
            terminal[key] = next(iter(values))
        else:
            exclusions["terminal_underlying_conflict"] += 1
            conflicting_days.add(key)
    for key in invalid_closes - terminal_values.keys():
        exclusions["terminal_underlying_conflict"] += 1
        conflicting_days.add(key)
    exclusions["entry_underlying_conflict"] += sum(1 for q in quotes if (q.quote_date, q.underlying) in conflicting_days)
    quotes = [q for q in quotes if (q.quote_date, q.underlying) not in conflicting_days]
    return quotes, terminal, exclusions
