#!/usr/bin/env python3
"""Audit source structure or run the frozen expiry-payoff diagnostic."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import zipfile

from spyspx.expiry_payoff import evaluate, select_pairs, validate_quote
from spyspx.expiry_payoff_source import SCHEMA, read_zip

CODE_ROOT = Path(__file__).resolve().parents[1]
CODE_FILES = (
    "scripts/expiry_payoff.py",
    "src/spyspx/expiry_payoff.py",
    "src/spyspx/expiry_payoff_source.py",
    "tests/test_expiry_payoff.py",
    "tests/test_expiry_payoff_cli.py",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=CODE_ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def snapshot(source: Path, protocol: Path) -> dict:
    status = git_value(["status", "--porcelain=v1"])
    stat = source.stat()
    return {
        "git_sha": git_value(["rev-parse", "HEAD"]),
        "git_status_porcelain": status,
        "workspace_state": "dirty" if status else "clean",
        "code_file_sha256": {name: sha256(CODE_ROOT / name) for name in CODE_FILES},
        "protocol": {"path": str(protocol.resolve()), "sha256": sha256(protocol)},
        "input": {"path": str(source), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": sha256(source)},
    }


def summarize(outcomes) -> dict:
    cohorts: dict[str, list] = defaultdict(list)
    for outcome in outcomes:
        cohorts[outcome.expiry.isoformat()].append(outcome)
    rows = []
    for expiry, group in sorted(cohorts.items()):
        vals = [p.gross_crossing_pnl for p in group]
        ordered = sorted(vals)
        rows.append({
            "expiry": expiry,
            "n_alternative_pairs": len(group),
            "mean_crossing_gross_pnl_usd": sum(vals) / len(vals),
            "median_crossing_gross_pnl_usd": (ordered[(len(ordered)-1)//2] + ordered[len(ordered)//2]) / 2,
            "min_crossing_gross_pnl_usd": min(vals),
            "max_crossing_gross_pnl_usd": max(vals),
            "positive_share": sum(v > 0 for v in vals) / len(vals),
            "mean_midpoint_gross_pnl_usd": sum(p.gross_midpoint_pnl for p in group) / len(group),
            "mean_reverse_crossing_gross_pnl_usd": sum(p.reverse_crossing_pnl for p in group) / len(group),
            "mean_crossing_credit_usd": sum(p.crossing_credit for p in group) / len(group),
            "mean_midpoint_credit_usd": sum(p.midpoint_credit for p in group) / len(group),
            "mean_terminal_value_usd": sum(p.terminal_value for p in group) / len(group),
            "mean_crossing_cost_vs_midpoint_usd": sum(p.crossing_cost for p in group) / len(group),
            "mean_normalized_moneyness_mismatch": sum(p.normalized_moneyness_mismatch for p in group) / len(group),
            "mean_strike_cash_mismatch_usd": sum(p.strike_cash_mismatch for p in group) / len(group),
            "mean_absolute_strike_cash_mismatch_usd": sum(abs(p.strike_cash_mismatch) for p in group) / len(group),
            "mean_entry_underlying_exposure_mismatch_usd": sum(p.entry_underlying_exposure_mismatch for p in group) / len(group),
            "mean_absolute_entry_underlying_exposure_mismatch_usd": sum(abs(p.entry_underlying_exposure_mismatch) for p in group) / len(group),
            "mean_terminal_stress_low_usd": sum(p.terminal_stress_low for p in group) / len(group),
            "mean_terminal_stress_high_usd": sum(p.terminal_stress_high for p in group) / len(group),
        })
    cohort_means = [r["mean_crossing_gross_pnl_usd"] for r in rows]
    sorted_cohorts = sorted(cohort_means)
    n = len(sorted_cohorts)
    return {
        "label": "CLOSE_PROXY_DIAGNOSTIC_NOT_EXACT_SETTLEMENT",
        "status": "CLOSE_PROXY_DIAGNOSTIC_READY" if outcomes else "NO_USABLE_DATA",
        "exact_settlement_status": "NOT RUN",
        "selection": "one calendar day before expiry; alternatives, not simultaneous positions",
        "position": {"short_spy_calls": 10, "long_spxw_calls": 1, "multiplier_each": 100},
        "terminal_reference": "vendor underlying_close proxy; +/-3.05 SPX points is an assumed stress, not an observed error bound",
        "net_pnl": "unavailable; fees, financing, borrow, capital and SPY assignment/liquidation are not modeled",
        "intrinsic_mark_limitation": "SPY intrinsic does not model assignment or liquidation of up to 1000 shares",
        "retained_pairs": sum(len(group) for group in cohorts.values()),
        "expiry_cohorts": len(rows),
        "cohort_table": rows,
        "equal_cohort_mean_crossing_gross_pnl_usd": sum(cohort_means) / n if n else None,
        "equal_cohort_median_crossing_gross_pnl_usd": (sorted_cohorts[(n-1)//2] + sorted_cohorts[n//2]) / 2 if n else None,
        "equal_cohort_range_crossing_gross_pnl_usd": [min(cohort_means), max(cohort_means)] if n else None,
        "positive_cohort_share": sum(x > 0 for x in cohort_means) / n if n else None,
        "assumed_additional_total_cost_sensitivity_usd_per_alternative_pair": [
            {"cost_usd": c, "equal_cohort_mean_after_assumed_cost_usd": sum(x-c for x in cohort_means)/n}
            for c in (0, 1, 5, 10, 25, 50)
        ] if n else [],
        "break_even_assumed_additional_total_cost_usd_per_alternative_pair": sum(cohort_means) / n if n else None,
        "no_trade_control_usd": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source-audit", "run"))
    parser.add_argument("zip", type=Path)
    parser.add_argument("--protocol", type=Path, required=True,
                        help="readable frozen protocol file whose checksum is recorded")
    parser.add_argument("--project-root", type=Path, default=CODE_ROOT,
                        help="root for a new ignored runs/expiry_payoff output directory")
    args = parser.parse_args()
    source = args.zip.resolve()
    if not source.is_file() or not zipfile.is_zipfile(source):
        parser.error("input must be a readable ZIP file")
    protocol = args.protocol.resolve()
    try:
        if not protocol.is_file():
            raise OSError("not a regular file")
        protocol_sha256 = sha256(protocol)
    except OSError as exc:
        parser.error(f"--protocol must be a readable file: {protocol} ({exc})")

    started = datetime.now(timezone.utc)
    project_root = args.project_root.resolve()
    baseline = snapshot(source, protocol)
    if baseline["protocol"]["sha256"] != protocol_sha256:
        parser.error("--protocol changed while validating")
    output_root = project_root / "runs" / "expiry_payoff"
    output_root.mkdir(parents=True, exist_ok=True)
    dest = output_root / started.strftime("%Y%m%dT%H%M%S%fZ")
    dest.mkdir()
    quotes, terminal, adapter_counts = [], {}, Counter()
    validation_counts = Counter()
    valid_quotes = 0
    exclusions = Counter()
    outcomes = []
    processing_error = None
    try:
        quotes, terminal, adapter_counts = read_zip(source)
        for quote in quotes:
            reason = validate_quote(quote)
            if reason:
                validation_counts[reason] += 1
            else:
                valid_quotes += 1
        exclusions = Counter(adapter_counts)
        if args.mode == "run":
            pairs = select_pairs(quotes, exclusions)
            outcomes = evaluate(pairs, terminal, exclusions)
    except Exception as exc:
        processing_error = f"{type(exc).__name__}: {exc}"
    after = snapshot(source, protocol)
    unchanged = baseline == after and processing_error is None

    audit = {
        "mode": args.mode,
        "status": "PROCESSING_ERROR" if processing_error else ("source_audit_only" if args.mode == "source-audit" else ("NO_USABLE_DATA" if not outcomes else "CLOSE_PROXY_DIAGNOSTIC_READY")),
        "schema_expected_columns": len(SCHEMA),
        "candidate_entry_quotes": len(quotes),
        "valid_entry_quotes": valid_quotes,
        "invalid_candidate_quotes": dict(sorted(validation_counts.items())),
        "usable_terminal_references": len(terminal),
        "terminal_reference_keys_conflicted": adapter_counts["terminal_underlying_conflict"],
        "adapter_exclusions": dict(sorted(adapter_counts.items())),
    }
    manifest = {
        "command": {"executable": sys.executable, "argv": sys.argv, "cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH", "")},
        "started_utc": started.isoformat(),
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version,
        "runtime": "local deterministic computation; model endpoint not applicable",
        "protocol": baseline["protocol"],
        "baseline_before_outcomes": baseline,
        "snapshot_after_processing": after,
        "integrity_status": "UNCHANGED" if unchanged else "CHANGED_DURING_PROCESSING",
        "processing_error": processing_error,
        "exact_settlement_status": "NOT RUN",
        "mode": args.mode,
    }
    (dest / "source_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    status = {**audit, "integrity_status": manifest["integrity_status"], "output": str(dest),
              "input_sha256": baseline["input"]["sha256"]}
    if unchanged and args.mode == "run":
        aggregates = summarize(outcomes)
        aggregates["exclusions"] = dict(sorted(exclusions.items()))
        (dest / "aggregates.json").write_text(json.dumps(aggregates, indent=2) + "\n")
    (dest / "command.log").write_text(json.dumps(status) + "\n")
    print(json.dumps(status, indent=2))
    if not unchanged:
        return 2
    if processing_error:
        return 2
    if args.mode == "source-audit":
        return 0 if valid_quotes else 2
    return 0 if outcomes else 2


if __name__ == "__main__":
    raise SystemExit(main())
