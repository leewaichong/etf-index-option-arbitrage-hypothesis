#!/usr/bin/env python3
"""Audit retained August 2019 sources or run the frozen theoretical study."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys

from spyspx.expiry_replication import (RECEIPT_NAMES, aggregate_rows, audit_sources,
    build_pair_rows, load_study_inputs, primary_attribution, primary_coverage_failures, sha256)

ROOT = Path(__file__).resolve().parents[1]
CODE_FILES = ("scripts/expiry_replication.py", "src/spyspx/expiry_replication.py", "tests/test_expiry_replication.py")
DEPENDENCIES = ("src/spyspx/expiry_payoff.py", "src/spyspx/expiry_extension.py")


def git(root, *args):
    p = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    return p.stdout.strip() if p.returncode == 0 else "unavailable"


def output_root_is_ignored(root: Path, output: Path) -> bool:
    try:
        rel = output.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    if rel in ("", "."):
        return False
    p = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", "--", rel], cwd=root, capture_output=True)
    return p.returncode == 0


def snapshot(root: Path, protocol: Path, input_root: Path):
    tracked = [root / x for x in (*CODE_FILES, *DEPENDENCIES)]
    files = {str(p.relative_to(root)): {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in tracked}
    input_files = {}
    for name in (*RECEIPT_NAMES, "replication-acquisition-receipt.json"):
        p = input_root / name
        input_files[name] = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    status = git(root, "status", "--porcelain=v1")
    return {"git_sha": git(root, "rev-parse", "HEAD"), "git_status_porcelain": status,
            "git_state": "clean" if not status else "dirty", "code_sha256": files,
            "protocol": {"path": str(protocol.resolve()), "sha256": sha256(protocol)}, "inputs": input_files}


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source-audit", "run"))
    parser.add_argument("--input-root", type=Path, default=Path(os.environ.get(
        "SPYSPX_2019_INPUT_ROOT", ROOT / "data/expiry-payoff/legacy-2019")))
    parser.add_argument("--protocol", type=Path, default=ROOT / "planning/expiry-replication-protocol-201908-20261028.md")
    parser.add_argument("--output-root", type=Path, default=ROOT / "runs/expiry_replication")
    args = parser.parse_args(argv)
    root, input_root, protocol, out_root = ROOT, args.input_root.resolve(), args.protocol.resolve(), args.output_root.resolve()
    if not output_root_is_ignored(root, out_root):
        print(json.dumps({"status": "BLOCKED_OUTPUT_ROOT_NOT_IGNORED_OR_OUTSIDE_REPOSITORY", "output_root": str(out_root)}, indent=2), file=sys.stderr)
        return 2
    if not protocol.is_file():
        parser.error("frozen protocol file is missing")
    receipt = input_root / "replication-acquisition-receipt.json"
    if not receipt.is_file():
        parser.error("acquisition receipt is missing")
    if args.mode == "run" and git(root, "status", "--porcelain=v1"):
        print(json.dumps({"status": "BLOCKED_DIRTY_GIT", "git_sha": git(root, "rev-parse", "HEAD")}, indent=2), file=sys.stderr)
        return 2
    if args.mode == "run" and "**Status: NOT RUN.**" not in protocol.read_text(encoding="utf-8"):
        print(json.dumps({"status": "BLOCKED_PROTOCOL_NOT_FROZEN"}, indent=2), file=sys.stderr)
        return 2
    started = datetime.now(timezone.utc)
    before = snapshot(root, protocol, input_root)
    if args.mode == "source-audit":
        audit = audit_sources(input_root, receipt)
        after = snapshot(root, protocol, input_root)
        payload = {"status": "SOURCE_AUDIT_ONLY", "started_utc": started.isoformat(), "finished_utc": datetime.now(timezone.utc).isoformat(),
                   "argv": sys.argv if argv is None else [sys.argv[0], *argv], "cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH"),
                   "interpreter": sys.executable, "python_runtime": sys.version, "host": socket.gethostname(), "platform": platform.platform(),
                   "model_endpoint": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION", "model_identity": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION",
                   "broker_experiment_status": "NOT RUN", "snapshot_before": before,
                   "snapshot_after": after, "integrity_status": "UNCHANGED" if before == after else "CHANGED", "source_audit": audit}
        if payload["integrity_status"] != "UNCHANGED":
            print(json.dumps({"status": "SOURCE_AUDIT_INTEGRITY_CHANGED", "payload": payload}, indent=2))
            return 2
        dest = out_root / started.strftime("%Y%m%dT%H%M%S%fZ")
        dest.mkdir(parents=True, exist_ok=False)
        write_json(dest / "source_audit.json", audit)
        write_json(dest / "manifest.json", payload)
        print(dest)
        return 0 if audit["integrity_status"] == "PASS" and audit["coverage_status"] == "PASS" else 2

    if before["git_state"] != "clean":
        return 2
    audit = audit_sources(input_root, receipt)
    if audit["integrity_status"] != "PASS" or audit["coverage_status"] != "PASS":
        print(json.dumps({"status": "BLOCKED_SOURCE_OR_COVERAGE", "source_audit": audit}, indent=2))
        return 2
    _, quotes, stocks, sessions, spx, settlements, yahoo, dividends, following = load_study_inputs(input_root, audit)
    selected, preflight_failures = primary_coverage_failures(quotes, stocks, spx, settlements, yahoo, following)
    if preflight_failures:
        print(json.dumps({"status": "BLOCKED_PRIMARY_PAIR_OR_REFERENCE_COVERAGE", "failures": preflight_failures, "source_audit_status": "SOURCE_AUDIT_ONLY"}, indent=2))
        return 2
    rows, provider_controls = build_pair_rows(quotes, stocks, spx, settlements, yahoo, dividends, following, selected)
    if len(rows) != 9 or any(r.get("status") != "COMPLETE_THEORETICAL_ROW" or len(r.get("fill_rows", [])) != 3 for r in rows) or len(provider_controls) != 27:
        print(json.dumps({"status": "BLOCKED_INCOMPLETE_PRIMARY_OUTPUT", "source_audit_status": "SOURCE_AUDIT_ONLY"}, indent=2))
        return 2
    aggregates = aggregate_rows(rows)
    attribution, attribution_rows = primary_attribution(rows)
    after = snapshot(root, protocol, input_root)
    if before != after or after["git_state"] != "clean":
        print(json.dumps({"status": "BLOCKED_INTEGRITY_CHANGED", "snapshot_before": before, "snapshot_after": after}, indent=2))
        return 2
    payload = {"status": "INDEPENDENT_PERIOD_THEORETICAL_EVALUATED", "integrity_status": "UNCHANGED", "started_utc": started.isoformat(),
               "finished_utc": datetime.now(timezone.utc).isoformat(), "argv": sys.argv if argv is None else [sys.argv[0], *argv],
               "cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH"), "interpreter": sys.executable, "python_runtime": sys.version,
               "host": socket.gethostname(), "platform": platform.platform(), "model_endpoint": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION",
               "model_identity": "N/A_DETERMINISTIC_HISTORICAL_CALCULATION", "broker_experiment_status": "NOT RUN",
               "snapshot_before": before, "snapshot_after": after, "source_audit_status": "SOURCE_AUDIT_ONLY",
               "quote_timing": "SOURCE_DATE_ONLY_NO_QUOTE_TIMESTAMP", "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES",
               "limitations": audit["limitations"] + ["not a certified exercise-auction price study", "not a synchronized executable-edge test", "provider snapshot-close timing unresolved"]}
    dest = out_root / started.strftime("%Y%m%dT%H%M%S%fZ")
    dest.mkdir(parents=True, exist_ok=False)
    write_json(dest / "source_audit.json", audit)
    write_json(dest / "pair_rows.json", rows)
    write_json(dest / "provider_terminal_control_rows.json", provider_controls)
    write_json(dest / "aggregates.json", aggregates)
    write_json(dest / "primary_attribution_rows.json", attribution_rows)
    write_json(dest / "primary_attribution_summary.json", attribution)
    write_json(dest / "manifest.json", payload)
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
