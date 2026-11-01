"""Bounded 2023 morning-price hedge admission, selection, and evaluation CLI.

Source admission and selection never calculate hedge P&L. Evaluation requires a
durable selection receipt and a clean committed source tree.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from . import optionmetrics_normalizer as normalizer
from . import optionmetrics_replication as replication
from . import overnight_hedge as hedge

PERIOD = "2023"
PROTOCOL_PATH = Path("planning/morning-hedge-replication-20261030/frozen-protocol.md")
PROTOCOL_SHA256 = "8f66787ce63d47771c1bbb5edd516c02d46ebc37b2538f3581ae3e073cbfa403"
CALENDAR_PATH = Path("planning/morning-hedge-replication-20261030/frozen-calendar-2023.json")
CALENDAR_SHA256 = "122296e11825bbdec9af5bbed5cca5f3fc6c8ea0dc99548351dc05d44beee809"
CALENDAR_SOURCE_SHA256 = "119e2d6a02b6472562353b4bf4e14ab0cf13d9a0a0b67abdf85b993364b23a74"
EXPECTED_PAIRS = 196
FILLS = ("midpoint", "halfway", "full_cross")
ARMS = hedge.ARMS
FUNDING = ("gross_prefunding", "assignment_cash_net")
SLIPPAGE = (0.0, 1.0, 5.0)
REQUIRED_ROLES = (
    "quotes_2023", "projection_2023", "quote_source_metadata", "quote_identity_metadata",
    "official_spx_calendar", "wrds_stock_prices", "wrds_distributions",
    "cboe_W_2023", "cboe_M_2023", "cboe_S_2023",
)
OPTIONAL_ROLES = ("capture_receipts",)
CODE_PATHS = {
    "code_adapter": "src/spyspx/morning_hedge_2023.py",
    "code_normalizer": "src/spyspx/optionmetrics_normalizer.py",
    "code_replication": "src/spyspx/optionmetrics_replication.py",
    "code_overnight_hedge": "src/spyspx/overnight_hedge.py",
    "code_expiry_extension": "src/spyspx/expiry_extension.py",
    "code_expiry_payoff": "src/spyspx/expiry_payoff.py",
    "code_admission": "src/spyspx/optionmetrics_admission.py",
}
SOURCE_LIMITS = [
    "WRDS web export does not expose extraction SQL; projection comparison checks returned exports only.",
    "This deterministic daily-price calculation does not establish synchronized fills or execution.",
    "2023 vendor quote-clock semantics are unverified unless separately supported by retained vendor proof.",
    "Option quote sizes are unavailable; no capacity, margin, or account-return claim is made.",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True,
                          capture_output=True).stdout.strip()


def _verify_frozen_files(repo: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for key, relative, expected in (("protocol", PROTOCOL_PATH, PROTOCOL_SHA256),
                                    ("calendar", CALENDAR_PATH, CALENDAR_SHA256)):
        path = repo / relative
        data = path.read_bytes()
        if sha256(data) != expected:
            raise ValueError(f"frozen {key} hash mismatch")
        result[key] = {"path": str(path.resolve()), "bytes": len(data), "sha256": expected, "data": data}
    return result


def _capture_code_identity(repo: Path) -> dict[str, Any]:
    head = _git(repo, "rev-parse", "HEAD")
    if _git(repo, "status", "--porcelain"):
        raise ValueError("evaluation requires a clean Git worktree")
    loaded_paths = {
        "code_adapter": Path(__file__),
        "code_normalizer": Path(normalizer.__file__),
        "code_replication": Path(replication.__file__),
        "code_overnight_hedge": Path(hedge.__file__),
        "code_expiry_extension": Path(sys.modules["spyspx.expiry_extension"].__file__),
        "code_expiry_payoff": Path(sys.modules["spyspx.expiry_payoff"].__file__),
        "code_admission": Path(sys.modules["spyspx.optionmetrics_admission"].__file__),
    }
    records = {}
    for role, relative in CODE_PATHS.items():
        path = repo / relative
        if loaded_paths[role].resolve(strict=True) != path.resolve(strict=True):
            raise ValueError(f"loaded module path does not match frozen project path: {role}")
        data = path.read_bytes()
        committed = subprocess.run(["git", "show", f"{head}:{relative}"], cwd=repo,
                                   capture_output=True, check=False)
        if committed.returncode or committed.stdout != data:
            raise ValueError(f"loaded {role} bytes do not match clean HEAD")
        records[role] = {"path": str(path.resolve()), "relative_path": relative,
                         "bytes": len(data), "sha256": sha256(data), "data": data}
    return {"head": head, "code": records}


def _check_identity(repo: Path, identity: dict[str, Any], inputs: dict[str, dict[str, Any]],
                    selection_path: Path | None = None, selection_sha: str | None = None) -> dict:
    if _git(repo, "rev-parse", "HEAD") != identity["head"] or _git(repo, "status", "--porcelain"):
        raise ValueError("BLOCKED: Git HEAD or clean state changed")
    hashes = {}
    for role, item in identity["code"].items():
        data = Path(item["path"]).read_bytes()
        committed = subprocess.run(["git", "show", f"{identity['head']}:{item['relative_path']}"],
                                   cwd=repo, capture_output=True, check=False)
        if data != item["data"] or committed.returncode or committed.stdout != data:
            raise ValueError(f"BLOCKED: loaded code changed: {role}")
        hashes[role] = item["sha256"]
    _check_inputs(inputs)
    if selection_path is not None:
        data = selection_path.read_bytes()
        if sha256(data) != selection_sha:
            raise ValueError("BLOCKED: durable selection changed")
    return {"verified": True, "head": identity["head"], "clean": True,
            "code_sha256": hashes, "inputs_verified": True, "selection_sha256": selection_sha}


def _check_inputs(inputs: dict[str, dict[str, Any]]) -> None:
    for role, item in inputs.items():
        if item.get("missing"):
            if Path(item["path"]).exists():
                raise ValueError(f"BLOCKED: previously missing input appeared during run: {role}")
            continue
        data = Path(item["path"]).read_bytes()
        if len(data) != item["bytes"] or sha256(data) != item["sha256"]:
            raise ValueError(f"BLOCKED: input changed: {role}")


def _load_manifest(repo: Path, manifest_path: Path, expected_sha: str, *, allow_missing: bool = False) -> tuple[dict, dict[str, dict[str, Any]]]:
    path = manifest_path if manifest_path.is_absolute() else repo / manifest_path
    data = path.read_bytes()
    if sha256(data) != expected_sha:
        raise ValueError("input manifest SHA-256 does not match --input-manifest-sha256")
    manifest = json.loads(data)
    if manifest.get("status") not in {"FROZEN_NOT_RUN", "FROZEN_INPUTS_NOT_RUN"}:
        raise ValueError("input manifest status must explicitly be frozen and not run")
    files = manifest.get("files")
    if not isinstance(files, dict) or not set(REQUIRED_ROLES).issubset(files):
        raise ValueError("input manifest is missing required 2023 source roles")
    unknown = set(files) - set(REQUIRED_ROLES) - set(OPTIONAL_ROLES)
    if unknown:
        raise ValueError(f"input manifest contains unsupported roles: {sorted(unknown)}")
    snapshot = {"input_manifest": {"path": str(path.resolve()), "bytes": len(data),
                                    "sha256": expected_sha, "data": data}}
    for role, record in files.items():
        if set(("path", "bytes", "sha256", "acquisition")) - set(record):
            raise ValueError(f"manifest role {role} lacks path, bytes, SHA-256, or acquisition metadata")
        acquisition = record["acquisition"]
        if not isinstance(acquisition, dict) or not acquisition:
            raise ValueError(f"manifest role {role} lacks documented acquisition metadata")
        for key in ("source_url", "acquired_utc", "coverage", "fields"):
            if key not in acquisition:
                raise ValueError(f"manifest role {role} acquisition metadata lacks {key}")
        source = Path(record["path"])
        if not source.is_absolute():
            source = repo / source
        try:
            source = source.resolve(strict=True)
        except FileNotFoundError:
            if not allow_missing:
                raise
            snapshot[role] = {"path": str(source.resolve()), "bytes": record["bytes"],
                              "sha256": record["sha256"], "data": b"", "acquisition": acquisition,
                              "missing": True}
            continue
        blob = source.read_bytes()
        if len(blob) != record["bytes"] or sha256(blob) != record["sha256"]:
            raise ValueError(f"frozen input integrity mismatch: {role}")
        snapshot[role] = {"path": str(source), "bytes": len(blob), "sha256": record["sha256"], "data": blob,
                          "acquisition": acquisition}
    snapshot.update(_verify_frozen_files(repo))
    return manifest, snapshot


def _json(data: bytes, label: str) -> dict:
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _read_calendar(data: bytes) -> tuple[set[date], dict[date, float]]:
    sessions, closes = replication._read_calendar(data)
    return sessions, closes


def _expected_pairs(calendar_bytes: bytes, frozen_calendar_bytes: bytes) -> tuple[list[dict], set[date], dict[date, float]]:
    sessions, spx_closes = _read_calendar(calendar_bytes)
    if sha256(calendar_bytes) != CALENDAR_SOURCE_SHA256:
        raise ValueError("official SPX calendar source hash does not match the frozen calendar receipt")
    frozen = _json(frozen_calendar_bytes, "frozen 2023 calendar")
    if frozen.get("status") != "FROZEN_NOT_RUN" or frozen.get("calendar_sha256") != CALENDAR_SOURCE_SHA256:
        raise ValueError("frozen calendar metadata is inconsistent")
    pairs = frozen.get("expected_pairs")
    if frozen.get("expected_count") != EXPECTED_PAIRS or not isinstance(pairs, list) or len(pairs) != EXPECTED_PAIRS:
        raise ValueError("frozen calendar must contain exactly 196 expected pairs")
    checked = replication._validate_expected_pairs({"expected_count": EXPECTED_PAIRS, "expected_pairs": pairs}, sessions)
    if len(checked) != EXPECTED_PAIRS:
        raise ValueError("independent calendar denominator mismatch")
    return checked, sessions, spx_closes


def _frozen_pairs_only(frozen_calendar_bytes: bytes) -> list[dict]:
    frozen = _json(frozen_calendar_bytes, "frozen 2023 calendar")
    if frozen.get("expected_count") != EXPECTED_PAIRS or len(frozen.get("expected_pairs", [])) != EXPECTED_PAIRS:
        raise ValueError("frozen calendar must contain exactly 196 expected pairs")
    return [{key: date.fromisoformat(row[key]) for key in ("entry", "expiry", "cover")}
            for row in frozen["expected_pairs"]]


def _blocked_coverage(expected: list[dict], missing_roles: list[str]) -> list[dict]:
    reasons = [f"source_input_missing:{role}" for role in missing_roles]
    return [{"entry": item["entry"].isoformat(), "expiry": item["expiry"].isoformat(),
             "cover": item["cover"].isoformat(), "selected": False, "complete": False,
             "missing_inputs": reasons, "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES"}
            for item in expected]


def _parse_cboe_pm(records: dict[str, dict[str, Any]]) -> tuple[dict[date, dict], dict]:
    result: dict[date, dict] = {}
    conflicts = Counter()
    source_names = ("cboe_W_2023", "cboe_M_2023", "cboe_S_2023")
    for role in source_names:
        try:
            obj = _json(records[role]["data"], role)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"{role} must be a Cboe JSON object") from exc
        rows = obj.get("data")
        if not isinstance(rows, list):
            raise ValueError(f"{role} must contain a data list")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{role} contains a non-object settlement row")
            if (row.get("trading_symbol"), row.get("settlement_symbol")) != ("SPXW", "SPX"):
                continue
            day = date.fromisoformat(str(row.get("expiration_date", "")))
            value = float(row.get("settlement_value"))
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Cboe SPXW settlement must be finite and positive")
            existing = result.get(day)
            if existing and existing["value"] != value:
                conflicts[day.isoformat()] += 1
                result.pop(day, None)
                continue
            if day.isoformat() not in conflicts:
                if existing:
                    existing["sources"].append(role)
                else:
                    result[day] = {"value": value, "sources": [role]}
    return result, {"conflicting_expiries": dict(conflicts), "accepted_expiries": len(result),
                    "rule": "exact SPXW trading_symbol and SPX settlement_symbol; identical duplicates only"}


def _all_interval_actions(events: list[dict], entry: date, cover: date) -> list[dict]:
    return [event for event in events if entry < event["ex_date"] <= cover]


def _selection_payload(manifest_sha: str, protocol_sha: str, calendar_sha: str,
                       selected: list[dict], expected: list[dict], diagnostics: dict,
                       input_records: dict, identity: dict | None) -> dict:
    by_entry = {row["entry"]: row for row in selected}
    rows = []
    for pair in expected:
        item = by_entry.get(pair["entry"].isoformat())
        rows.append({"entry": pair["entry"].isoformat(), "expiry": pair["expiry"].isoformat(),
                     "cover": pair["cover"].isoformat(), "selected": item})
    return {"status": "SELECTION_FROZEN_NOT_RUN", "historical_evaluation": "NOT RUN",
            "period": PERIOD, "expected_pair_count": EXPECTED_PAIRS,
            "protocol_sha256": protocol_sha, "calendar_sha256": calendar_sha,
            "input_manifest_sha256": manifest_sha, "input_hashes": input_records,
            "selected_pairs": rows, "selection_diagnostics": diagnostics,
            "quote_clock_semantics": "UNVERIFIED_FOR_2023_UNLESS_VENDOR_PROOF_IS_PRESENT",
            "initial_git": identity["head"] if identity else None,
            "selection_utc": utc_now()}


def _atomic_bundle(out: Path, repo: Path, files: dict[str, bytes], inputs: dict,
                   final_guard=None) -> dict:
    target = _safe_output(repo, out)
    if target.exists():
        raise FileExistsError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".morning-hedge-2023-", dir=target.parent))
    try:
        hashes = {}
        for name, data in files.items():
            if Path(name).name != name:
                raise ValueError("output file names must be simple names")
            (stage / name).write_bytes(data)
            hashes[name] = sha256(data)
        _check_inputs(inputs)
        receipt = {"outputs": hashes, "written_utc": utc_now()}
        (stage / "bundle.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        _check_inputs(inputs)
        if target.exists():
            raise FileExistsError(f"output already exists: {target}")
        if final_guard is not None:
            final_guard()
        os.rename(stage, target)
        return {**hashes, "bundle.json": sha256((target / "bundle.json").read_bytes()), "path": str(target)}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _admit_raw_sources(records: dict[str, dict[str, Any]]) -> tuple[dict, dict]:
    """Apply the same strict quote identity and projection checks in both modes."""
    raw = records["quotes_2023"]
    normalized = normalizer.normalize({"raw_export": raw,
                                       "source_metadata": records["quote_source_metadata"],
                                       "identity_metadata": records["quote_identity_metadata"]})
    if normalized["hard_failure_count"]:
        raise ValueError("OptionMetrics normalizer reported hard source/identity failures")
    source_meta = _json(records["quote_source_metadata"]["data"], "quote source metadata")
    query = source_meta.get("query", {})
    if query.get("quote_start") != "2023-01-01" or query.get("quote_end") != "2023-12-31":
        raise ValueError("quote source metadata must declare the 2023 calendar entry window")
    projection = replication._projection_check(raw["data"], records["projection_2023"]["data"],
                                               query.get("compression") == "gzip")
    if not projection["projection_consistent"]:
        raise ValueError("returned projection control does not match enriched export")
    return normalized, projection


def _admission_blockers(selection_diag: dict, action_failures: list[dict],
                        settlement_diag: dict, expected: list[dict], settlements: dict) -> tuple[list[str], list[str]]:
    blockers = []
    if selection_diag.get("missing_selection_count", len(expected) - selection_diag.get("selected_count", 0)):
        blockers.append("missing_entry_selections")
    if action_failures:
        blockers.append("unsupported_distribution_events")
    if settlement_diag.get("conflicting_expiries"):
        blockers.append("conflicting_settlements")
    expected_expiries = {item["expiry"].isoformat() for item in expected}
    accepted_expiries = {day.isoformat() for day in settlements}
    missing_settlements = sorted(expected_expiries - accepted_expiries)
    if missing_settlements:
        blockers.append("missing_settlements")
    return blockers, missing_settlements


def _safe_output(repo: Path, out: Path) -> Path:
    root = repo.resolve(strict=True)
    target = (out if out.is_absolute() else repo / out).absolute().resolve()
    planning = root / "planning/morning-hedge-replication-20261030"
    if not target.is_relative_to(planning) or target == planning:
        raise ValueError("--out must be a unique child of ignored morning-hedge planning")
    relative = target.relative_to(root).as_posix()
    if subprocess.run(["git", "check-ignore", "--quiet", "--no-index", "--", relative], cwd=root,
                      check=False).returncode != 0:
        raise ValueError("--out is not ignored by Git")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", relative], cwd=root,
                            capture_output=True, check=False)
    if tracked.returncode == 0:
        raise ValueError("--out is tracked")
    return target


def _safe_selection_path(repo: Path, path: Path) -> Path:
    target = path.resolve(strict=True)
    root = repo.resolve(strict=True)
    planning = (root / "planning/morning-hedge-replication-20261030").resolve()
    if not target.is_relative_to(planning):
        raise ValueError("--selection must be inside ignored morning-hedge planning")
    relative = target.relative_to(root).as_posix()
    if subprocess.run(["git", "check-ignore", "--quiet", "--no-index", "--", relative], cwd=root,
                      check=False).returncode != 0:
        raise ValueError("--selection is not under an ignored path")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", relative], cwd=root,
                            capture_output=True, check=False)
    if tracked.returncode == 0:
        raise ValueError("--selection is tracked")
    return target


def source_admission(repo: Path, manifest_path: Path, manifest_sha: str, out: Path,
                     argv: list[str]) -> dict:
    manifest, inputs = _load_manifest(repo, manifest_path, manifest_sha, allow_missing=True)
    start = utc_now()
    records = {key: value for key, value in inputs.items() if key not in {"input_manifest", "protocol", "calendar"}}
    missing_roles = [role for role in REQUIRED_ROLES if inputs[role].get("missing")]
    if missing_roles:
        expected = _frozen_pairs_only(inputs["calendar"]["data"])
        coverage = _blocked_coverage(expected, missing_roles)
        input_records = {key: {k: value[k] for k in ("path", "bytes", "sha256")} for key, value in inputs.items()}
        audit = {"status": "NOT_RUN_SOURCE_INPUTS_MISSING", "historical_evaluation": "NOT RUN",
                 "period": PERIOD, "started_utc": start, "ended_utc": utc_now(), "argv": argv,
                 "cwd": str(Path.cwd()), "git": {"head": _git(repo, "rev-parse", "HEAD"),
                 "clean": not bool(_git(repo, "status", "--porcelain"))},
                 "manifest_sha256": manifest_sha, "protocol_sha256": inputs["protocol"]["sha256"],
                 "calendar_sha256": inputs["calendar"]["sha256"], "source_files": input_records,
                 "missing_roles": missing_roles, "expected_pair_count": EXPECTED_PAIRS,
                 "limitations": SOURCE_LIMITS}
        target = _safe_output(repo, out)
        return _atomic_bundle(target, repo, {"source-audit.json": (json.dumps(audit, indent=2, sort_keys=True) + "\n").encode(),
                                             "coverage.json": (json.dumps(coverage, indent=2, sort_keys=True) + "\n").encode()}, inputs)
    normalized, projection = _admit_raw_sources(records)
    expected, sessions, official_spx = _expected_pairs(records["official_spx_calendar"]["data"], inputs["calendar"]["data"])
    prices, price_diag = replication._read_prices(records["wrds_stock_prices"]["data"])
    events, action_diag = replication._read_distributions(records["wrds_distributions"]["data"])
    source_coverage = records["wrds_distributions"].get("acquisition", {}).get("coverage")
    if source_coverage != ["2019-08-01", "2025-08-29"]:
        raise ValueError("distribution source metadata must document full retained interval 2019-08-01 through 2025-08-29")
    # Parse every supported/unsupported event across every expected full interval before filtering to hedge dividends.
    action_failures = []
    for pair in expected:
        for event in _all_interval_actions(events, pair["entry"], pair["cover"]):
            if not replication._is_confirmed_cash_dividend(event):
                action_failures.append({"entry": pair["entry"].isoformat(), "ex_date": event["ex_date"].isoformat(),
                                        "reason": "unsupported_distribution_event"})
    settlement, settlement_diag = _parse_cboe_pm(records)
    spy_prices = {key: value for key, value in prices.items() if key[0] == replication.SECURITY_IDS["SPY"]}
    selected, selection_diag = replication.select_pairs(normalized["normalized_rows"], expected, spy_prices, official_spx)
    input_records = {key: {k: value[k] for k in ("path", "bytes", "sha256")} for key, value in inputs.items()}
    selection = _selection_payload(manifest_sha, inputs["protocol"]["sha256"], inputs["calendar"]["sha256"],
                                   selected, expected, selection_diag, input_records, None)
    selection_bytes = (json.dumps(selection, indent=2, sort_keys=True) + "\n").encode()
    selected_path = _safe_output(repo, out)
    selection_sha = sha256(selection_bytes)
    blockers, missing_settlements = _admission_blockers(selection_diag, action_failures,
                                                        settlement_diag, expected, settlement)
    audit = {
        "status": "NOT_RUN_SOURCE_ADMISSION_BLOCKED" if blockers else "SOURCE_ADMISSION_COMPLETE_SELECTION_FROZEN_NOT_RUN",
        "blockers": blockers, "missing_settlement_expiries": missing_settlements,
        "historical_evaluation": "NOT RUN", "period": PERIOD, "started_utc": start,
        "ended_utc": utc_now(), "argv": argv, "cwd": str(Path.cwd()),
        "git": {"head": _git(repo, "rev-parse", "HEAD"), "clean": not bool(_git(repo, "status", "--porcelain"))},
        "manifest_sha256": manifest_sha, "protocol_sha256": inputs["protocol"]["sha256"],
        "calendar_sha256": inputs["calendar"]["sha256"], "source_files": input_records,
        "normalizer": {k: normalized[k] for k in ("status", "row_count", "normalized_count", "excluded_count", "hard_failure_count", "reason_counts", "observed_dates")},
        "projection_control": projection, "independent_calendar": {"expected_pairs": len(expected), "sessions": len(sessions),
            "first_pair": {k: v.isoformat() for k, v in expected[0].items()},
            "last_pair": {k: v.isoformat() for k, v in expected[-1].items()}},
        "stock_price_source": price_diag, "distribution_source": action_diag,
        "unsupported_events_in_expected_intervals": action_failures,
        "settlement_source": settlement_diag, "selection": selection_diag,
        "selection_sha256": selection_sha, "selection_path_in_bundle": "selection.json",
        "selection_semantics": "entry quotes and entry references only; no terminal values used",
        "quote_clock_semantics": "UNVERIFIED_FOR_2023_UNLESS_VENDOR_PROOF_IS_PRESENT",
        "limitations": SOURCE_LIMITS,
    }
    audit_bytes = (json.dumps(audit, indent=2, sort_keys=True) + "\n").encode()
    result = _atomic_bundle(selected_path, repo, {"source-audit.json": audit_bytes,
                               "selection.json": selection_bytes}, inputs)
    result["selection_sha256"] = selection_sha
    return result


def _read_selection(path: Path, expected_sha: str, manifest_sha: str,
                    inputs: dict[str, dict[str, Any]] | None = None) -> tuple[dict, bytes]:
    data = path.read_bytes()
    if sha256(data) != expected_sha:
        raise ValueError("selection SHA-256 mismatch")
    selection = _json(data, "selection")
    if selection.get("status") != "SELECTION_FROZEN_NOT_RUN" or selection.get("historical_evaluation") != "NOT RUN":
        raise ValueError("selection is not a frozen, not-run selection receipt")
    if selection.get("period") != PERIOD or selection.get("input_manifest_sha256") != manifest_sha:
        raise ValueError("selection is bound to another period or input manifest")
    if selection.get("protocol_sha256") != PROTOCOL_SHA256 or selection.get("calendar_sha256") != CALENDAR_SHA256:
        raise ValueError("selection is bound to another frozen protocol or calendar")
    if inputs is not None:
        current = {key: {k: value[k] for k in ("path", "bytes", "sha256")} for key, value in inputs.items()}
        if selection.get("input_hashes") != current:
            raise ValueError("selection source hashes do not match the supplied frozen inputs")
    rows = selection.get("selected_pairs")
    if not isinstance(rows, list) or len(rows) != EXPECTED_PAIRS:
        raise ValueError("selection must retain all 196 expected calendar rows")
    frozen_calendar = json.loads((repo_root() / CALENDAR_PATH).read_bytes())
    expected_pairs = frozen_calendar["expected_pairs"]
    seen = set()
    for row, expected in zip(rows, expected_pairs):
        key = (row.get("entry"), row.get("expiry"), row.get("cover"))
        expected_key = (expected["entry"], expected["expiry"], expected["cover"])
        if key != expected_key or key[0] in seen:
            raise ValueError("selection rows do not match the frozen independent calendar")
        seen.add(key[0])
        chosen = row.get("selected")
        if chosen is not None:
            if (chosen.get("entry"), chosen.get("expiry"), chosen.get("cover")) != expected_key:
                raise ValueError("selected contract pair dates differ from frozen calendar")
            for family in ("spy", "spxw"):
                quote = chosen.get(family)
                if not isinstance(quote, dict) or quote.get("normalized_quote_date") != expected["entry"] or quote.get("normalized_expiry_date") != expected["expiry"]:
                    raise ValueError("selected entry quote dates do not match the frozen calendar")
    return selection, data


def _verify_entry_selection(selection: dict, normalized_quotes: list[dict], expected: list[dict],
                            prices: dict, spx: dict) -> None:
    spy_prices = {key: value for key, value in prices.items() if key[0] == replication.SECURITY_IDS["SPY"]}
    recomputed, _ = replication.select_pairs(normalized_quotes, expected, spy_prices, spx)
    recomputed_by_entry = {row["entry"]: row for row in recomputed}
    for frozen in selection["selected_pairs"]:
        current = recomputed_by_entry.get(frozen["entry"])
        if current != frozen.get("selected"):
            raise ValueError(f"BLOCKED: durable entry selection does not reproduce for {frozen['entry']}")


def _coverage_rows(selection: dict, expected: list[dict], prices: dict, spx: dict,
                   settlements: dict, events: list[dict], sessions: set[date]) -> tuple[list[dict], list[dict]]:
    selected_by_entry = {row["entry"]: row.get("selected") for row in selection["selected_pairs"]}
    coverage, computed = [], []
    for pair in expected:
        entry, expiry, cover = pair["entry"], pair["expiry"], pair["cover"]
        selected = selected_by_entry.get(entry.isoformat())
        missing = []
        if selected is None:
            missing.append("selected_pair")
        entry_spy = prices.get((replication.SECURITY_IDS["SPY"], entry))
        expiry_spy = prices.get((replication.SECURITY_IDS["SPY"], expiry))
        cover_spy = prices.get((replication.SECURITY_IDS["SPY"], cover))
        for label, ref in (("spy_entry_price", entry_spy), ("spy_expiry_price", expiry_spy), ("spy_cover_price", cover_spy)):
            if ref is None:
                missing.append(label)
        if entry not in spx:
            missing.append("official_spx_entry_close")
        if expiry not in spx:
            missing.append("official_spx_expiry_close")
        terminal = settlements.get(expiry)
        if terminal is None:
            missing.append("official_spxw_pm_settlement")
        interval = [e for e in events if entry < e["ex_date"] <= cover]
        unsupported = [e for e in interval if not replication._is_confirmed_cash_dividend(e)]
        if unsupported:
            missing.append("unsupported_distribution_event")
        for day in sorted(d for d in sessions if entry <= d <= cover):
            ref = prices.get((replication.SECURITY_IDS["SPY"], day))
            if ref is None:
                missing.append("spy_session_price_gap")
            elif ref["cfadj"] != 1.0:
                missing.append("nonunit_spy_cfadj")
        for label, day in (("entry", entry), ("expiry", expiry), ("cover", cover)):
            if day not in sessions:
                missing.append(f"{label}_not_in_session_calendar")
        coverage.append({"entry": entry.isoformat(), "expiry": expiry.isoformat(), "cover": cover.isoformat(),
                         "selected": selected is not None, "complete": not missing,
                         "missing_inputs": sorted(set(missing)), "relevant_action_count": len(interval),
                         "unsupported_action_count": len(unsupported),
                         "entry_to_expiry_dividend_exposure": any(entry < e["ex_date"] <= expiry for e in interval),
                         "distribution_coverage": ["2019-08-01", "2025-08-29"],
                         "depth_status": "UNAVAILABLE_SOURCE_NO_SIZES"})
        if missing or selected is None:
            continue
        spy_close = expiry_spy["close"]
        assigned = spy_close >= float(selected["spy"]["normalized_strike_milli"]) / 1000 + .01 - 1e-10
        refs = {"spy_expiry_close": spy_close, "spy_cover_open": cover_spy["open"],
                "spxw_pm_settlement": terminal["value"]}
        pair_selected = {"entry": selected["entry"], "expiry": selected["expiry"], "cover": selected["cover"],
                         **{k: selected[k] for k in ("spy", "spxw", "spy_entry_close", "official_spx_entry_close", "moneyness_mismatch")}}
        fills, controls = replication.build_fill_rows(pair_selected, refs, interval)
        carry_events = [e for e in interval if expiry < e["ex_date"] <= cover]
        row_base = {"period": PERIOD, "entry": pair_selected["entry"], "expiry": pair_selected["expiry"],
                    "cover": pair_selected["cover"], "spy_contract": pair_selected["spy"]["normalized_symbol"],
                    "spxw_contract": pair_selected["spxw"]["normalized_symbol"],
                    "spy_strike": int(pair_selected["spy"]["normalized_strike_milli"]) / 1000,
                    "spxw_strike": int(pair_selected["spxw"]["normalized_strike_milli"]) / 1000,
                    "official_spx_expiry_close": spx[expiry], "spxw_pm_settlement": terminal["value"],
                    "spy_open": expiry_spy["open"], "spy_close": spy_close, "cover_open": cover_spy["open"],
                    "assigned": assigned, "fill_rows": fills, "controls": controls,
                    "interval_events": interval, "carry_events": carry_events,
                    "hedge_dividend_amount": math.fsum(float(e["amount"]) for e in carry_events),
                    "status": "COMPLETE_THEORETICAL_ROW", "timing_status": "DAILY_PRICE_THEORETICAL",
                    "quote_clock_semantics": "UNVERIFIED_FOR_2023"}
        computed.append(row_base)
    return coverage, computed


def _summary(values: list[float]) -> dict:
    vals = [float(x) for x in values]
    mean = math.fsum(vals) / len(vals) if vals else None
    sample_std = (math.sqrt(math.fsum((x - mean) ** 2 for x in vals) / (len(vals) - 1))
                  if len(vals) > 1 else None)
    return {"count": len(vals), "mean": mean, "sample_standard_deviation": sample_std,
            "median": sorted(vals)[len(vals)//2] if len(vals) % 2 else (sum(sorted(vals)[len(vals)//2-1:len(vals)//2+1]) / 2 if vals else None),
            "total": math.fsum(vals) if vals else None,
            "win_fraction": sum(v > 0 for v in vals) / len(vals) if vals else None,
            "min": min(vals) if vals else None, "max": max(vals) if vals else None}


def _scenario_key(arm: str, fill: str, stress: bool, bp: float, funding: str) -> str:
    return f"{arm}|{fill}|{'stress' if stress else 'base'}|{bp:g}bp|{funding}"


def _build_ledgers(rows: list[dict]) -> tuple[list[dict], dict]:
    output = []
    by_pair: dict[str, dict[str, dict]] = defaultdict(dict)
    scenario_rows: dict[str, list[dict]] = defaultdict(list)
    for pair in rows:
        for fill_row in pair["fill_rows"]:
            interval_events = pair["interval_events"]
            dividend_amount = float(pair.get("hedge_dividend_amount", math.fsum(
                float(event["amount"]) for event in pair.get("carry_events", interval_events)
                if date.fromisoformat(pair["expiry"]) < event["ex_date"] <= date.fromisoformat(pair["cover"]))))
            common = {"entry": pair["entry"], "expiry": pair["expiry"], "cover": pair["cover"],
                      "fill": fill_row["fill"], "spy_contract": pair["spy_contract"],
                      "spxw_contract": pair["spxw_contract"], "spy_strike": pair["spy_strike"],
                      "spxw_strike": pair["spxw_strike"], "credit": fill_row["credit"],
                      "spxw_terminal_cash": fill_row["spxw_leg_terminal_cash"],
                      "assigned": pair["assigned"], "spy_open": pair["spy_open"],
                      "spy_close": pair["spy_close"], "cover_open": pair["cover_open"],
                      "dividend_amount": dividend_amount,
                      "days_entry_expiry": (date.fromisoformat(pair["expiry"]) - date.fromisoformat(pair["entry"])).days,
                      "days_entry_cover": (date.fromisoformat(pair["cover"]) - date.fromisoformat(pair["entry"])).days,
                      "days_expiry_cover": (date.fromisoformat(pair["cover"]) - date.fromisoformat(pair["expiry"])).days,
                      "old_gross_pnl": fill_row["dividend_carry_pnl"],
                      "old_dividend_pnl": fill_row["dividend_carry_pnl"] - fill_row["next_open_pnl"],
                      "old_base_cost_pnl": fill_row["base_cost_pnl"],
                      "old_stress_cost_pnl": fill_row["stress_cost_pnl"],
                      "old_controls": {"conditional_close_mark_pnl": fill_row["conditional_close_mark_pnl"],
                                       "direct_intrinsic_pnl": fill_row["direct_intrinsic_pnl"],
                                       "threshold_residual_cash": fill_row["threshold_residual_cash"],
                                       "pair_controls": pair["controls"]}}
            arm_outputs = {}
            all_ledgers = {}
            for arm in ARMS:
                for stress in (False, True):
                    for bp in SLIPPAGE:
                        for funding in FUNDING:
                            ledger = hedge.hedge_row(common, arm, funding=funding, slippage_bp=bp, stress=stress)
                            key = _scenario_key(arm, fill_row["fill"], stress, bp, funding)
                            all_ledgers[key] = ledger
                            if not stress and bp == 1 and funding == "gross_prefunding":
                                arm_outputs[arm] = ledger
                            if arm == "unhedged_q0" and bp == 0 and funding == "gross_prefunding":
                                if stress:
                                    if (abs(ledger["gross_pnl"] - fill_row["dividend_carry_pnl"]) > 1e-8 or
                                            abs(ledger["net_pnl"] - fill_row["stress_cost_pnl"]) > 1e-8):
                                        raise AssertionError("2023 q0 stress parity failed")
                                elif (abs(ledger["gross_pnl"] - fill_row["dividend_carry_pnl"]) > 1e-8 or
                                      abs(ledger["dividend_cash"] - (fill_row["dividend_carry_pnl"] - fill_row["next_open_pnl"])) > 1e-8 or
                                      abs(ledger["net_pnl"] - fill_row["base_cost_pnl"]) > 1e-8):
                                    raise AssertionError("2023 q0 base parity failed")
                            scenario_rows[key].append({"entry": pair["entry"], "expiry": pair["expiry"],
                                                       "ledger": ledger, "pair": pair, "fill_row": fill_row})
                if arm == "assignment_oracle_q1000A":
                    if abs(arm_outputs[arm]["gross_pnl"] - fill_row["conditional_close_mark_pnl"]) > 1e-8:
                        raise AssertionError("2023 oracle gross does not match conditional close mark")
                else:
                    qdelta = arm_outputs[arm]["gross_pnl"] - arm_outputs["unhedged_q0"]["gross_pnl"]
                    expected_delta = arm_outputs[arm]["q"] * (pair["cover_open"] - pair["spy_close"] + common["dividend_amount"])
                    if abs(qdelta - expected_delta) > 1e-8:
                        raise AssertionError(f"2023 hedge q-delta identity failed for {arm}")
            output.append({"entry": pair["entry"], "expiry": pair["expiry"], "cover": pair["cover"],
                           "fill": fill_row["fill"], "fill_row": fill_row, "arms": arm_outputs,
                           "scenario_ledgers": all_ledgers})
            by_pair[pair["entry"]][fill_row["fill"]] = arm_outputs
    return output, {"scenarios": scenario_rows}


def _case_rows(ledger_rows: list[dict]) -> list[dict]:
    cases = []
    for row in ledger_rows:
        for key, ledger in row["scenario_ledgers"].items():
            cases.append({"entry": row["entry"], "expiry": row["expiry"], "cover": row["cover"],
                          "fill": row["fill"], "fill_row": row["fill_row"],
                          "scenario": key, "ledger": ledger})
    return cases


def _summarize_ledgers(rows: list[dict], scenario_rows: dict[str, list[dict]], *, draws: int = 10_000) -> dict:
    metrics = ("gross_pnl", "net_pnl", "gross_pnl_without_dividends", "gross_pnl_with_dividends",
               "overnight_price_contribution", "dividend_cash", "stock_notional_close", "stock_notional_cover",
               "q", "residual_shares")
    cost_metrics = ("option_fees", "stock_fees", "residual_short_borrow", "premium_debit_funding",
                    "hedge_funding", "stock_slippage")
    output = {"period": PERIOD, "status": "DESCRIPTIVE_THEORETICAL_SUMMARIES", "pair_count": len({r["entry"] for r in rows}),
              "row_count": len(rows), "cohorts": {}, "scenario_summaries": {},
              "bootstrap": {"draws": draws, "seed": 20261030, "cluster": "expiry ISO year/week",
                            "quantile_method": "linear_type_7", "descriptive_only": True}}
    periods = {"all": rows}
    periods.update({month: [r for r in rows if r["expiry"][:7] == month]
                    for month in sorted({r["expiry"][:7] for r in rows})})
    for cohort, cohort_rows in periods.items():
        output["cohorts"][cohort] = {"pair_count": len({r["entry"] for r in cohort_rows}), "fills": {}}
        for fill in FILLS:
            fill_rows = [r for r in cohort_rows if r["fill"] == fill]
            arms = {}
            for arm in ARMS:
                ledgers = [r["arms"][arm] for r in fill_rows]
                arms[arm] = {metric: _summary([x[metric] for x in ledgers]) for metric in metrics}
                arms[arm]["cost_components"] = {name: _summary([x["costs"][name] for x in ledgers])
                                                 for name in (ledgers[0]["costs"] if ledgers else [])}
                arms[arm]["long_shares"] = sum(max(0, x["residual_shares"]) for x in ledgers)
                arms[arm]["short_shares"] = sum(max(0, -x["residual_shares"]) for x in ledgers)
                arms[arm]["maximum_close_notional"] = max((x["stock_notional_close"] for x in ledgers), default=0)
                arms[arm]["maximum_cover_notional"] = max((x["stock_notional_cover"] for x in ledgers), default=0)
                arms[arm]["max_peak_to_trough_drawdown"] = hedge.max_peak_to_trough_drawdown([x["net_pnl"] for x in ledgers])
            output["cohorts"][cohort]["fills"][fill] = arms
    scenario_results = {}
    for scenario, records in scenario_rows.items():
        records = sorted(records, key=lambda r: r["entry"])
        ledgers = [record["ledger"] for record in records]
        scenario_results[scenario] = {metric: _summary([ledger[metric] for ledger in ledgers]) for metric in metrics}
        scenario_results[scenario]["cost_components"] = {name: _summary([ledger["costs"][name] for ledger in ledgers])
                                                          for name in ledgers[0]["costs"]}
        def exposure_stats(items):
            values = [item["ledger"] for item in items]
            return {
                "signed_residual_exposure": {
                    "long_share_count": sum(max(0, x["residual_shares"]) for x in values),
                    "short_share_count": sum(max(0, -x["residual_shares"]) for x in values),
                    "mean_signed_shares": math.fsum(x["residual_shares"] for x in values) / len(values)},
                "residual_share_counts": dict(sorted(Counter(str(x["residual_shares"]) for x in values).items())),
                "residual_position_counts": {
                    "long": sum(x["residual_shares"] > 0 for x in values),
                    "short": sum(x["residual_shares"] < 0 for x in values),
                    "nonzero": sum(x["residual_shares"] != 0 for x in values),
                    "zero": sum(x["residual_shares"] == 0 for x in values)},
                "maximum_notional": max(max(x["stock_notional_close"], x["stock_notional_cover"]) for x in values),
                "max_peak_to_trough_drawdown": hedge.max_peak_to_trough_drawdown([x["net_pnl"] for x in values]),
            }
        scenario_results[scenario].update(exposure_stats(records))
        scenario_results[scenario]["month_cohorts"] = {}
        for month in sorted({record["expiry"][:7] for record in records}):
            month_records = [record for record in records if record["expiry"].startswith(month)]
            month_ledgers = [record["ledger"] for record in month_records]
            month_summary = {metric: _summary([item[metric] for item in month_ledgers]) for metric in metrics}
            month_summary["cost_components"] = {name: _summary([item["costs"][name] for item in month_ledgers])
                                                 for name in month_ledgers[0]["costs"]}
            month_summary.update(exposure_stats(month_records))
            scenario_results[scenario]["month_cohorts"][month] = month_summary
    # One shared bootstrap call per fill/cost configuration covers all arms,
    # absolute metrics, and paired q-minus-q0 metrics.
    for fill in FILLS:
        for stress in (False, True):
            for bp in SLIPPAGE:
                for funding in FUNDING:
                    keys = {arm: _scenario_key(arm, fill, stress, bp, funding) for arm in ARMS}
                    ordered = {arm: sorted(scenario_rows[key], key=lambda r: r["entry"]) for arm, key in keys.items()}
                    labels = [f"{date.fromisoformat(item['expiry']).isocalendar().year}-W{date.fromisoformat(item['expiry']).isocalendar().week:02d}"
                              for item in ordered["unhedged_q0"]]
                    columns = {}
                    for arm in ARMS:
                        own = [item["ledger"] for item in ordered[arm]]
                        zero = [item["ledger"] for item in ordered["unhedged_q0"]]
                        if [item["entry"] for item in ordered[arm]] != [item["entry"] for item in ordered["unhedged_q0"]]:
                            raise ValueError("paired bootstrap scenario rows are not aligned")
                        scenario = keys[arm]
                        for metric in (*metrics, *(f"cost:{name}" for name in cost_metrics)):
                            def metric_value(item, metric_name):
                                return float(item["costs"][metric_name[5:]]) if metric_name.startswith("cost:") else float(item[metric_name])
                            columns[f"{scenario}:{metric}:absolute"] = [metric_value(item, metric) for item in own]
                            columns[f"{scenario}:{metric}:paired_vs_q0"] = (
                                [0.0] * len(own) if arm == "unhedged_q0" else
                                [metric_value(item, metric) - metric_value(base, metric) for item, base in zip(own, zero)])
                    intervals, sample_hash = hedge.bootstrap_cluster_intervals(labels, columns, draws=draws, seed=20261030)
                    for arm in ARMS:
                        scenario = keys[arm]
                        scenario_results[scenario]["confidence_intervals"] = {
                            column: value for column, value in intervals.items() if column.startswith(scenario + ":")}
                        scenario_results[scenario]["draw_cluster_sample_ids_sha256"] = sample_hash
    output["scenario_summaries"] = scenario_results
    return output


def evaluate(repo: Path, manifest_path: Path, manifest_sha: str, selection_path: Path,
             selection_sha: str, out: Path, argv: list[str], draws: int = 10_000) -> dict:
    started = utc_now()
    identity = _capture_code_identity(repo)
    manifest, inputs = _load_manifest(repo, manifest_path, manifest_sha, allow_missing=True)
    selection_path = _safe_selection_path(repo, selection_path)
    selection, selection_bytes = _read_selection(selection_path, selection_sha, manifest_sha, inputs)
    run_identity_checks = {"before_terminal_joins": _check_identity(repo, identity, inputs, selection_path, selection_sha)}
    missing_roles = [role for role in REQUIRED_ROLES if inputs[role].get("missing")]
    expected = _frozen_pairs_only(inputs["calendar"]["data"])
    if not missing_roles:
        expected, sessions, spx = _expected_pairs(inputs["official_spx_calendar"]["data"], inputs["calendar"]["data"])
    else:
        sessions, spx = set(), {}
    if len(selection["selected_pairs"]) != len(expected):
        raise ValueError("durable selection denominator differs from independent frozen calendar")
    if missing_roles:
        coverage, pair_rows = _blocked_coverage(expected, missing_roles), []
        price_diag, action_diag, settlement_diag = {}, {}, {}
    else:
        prices, price_diag = replication._read_prices(inputs["wrds_stock_prices"]["data"])
        normalized, _projection = _admit_raw_sources(inputs)
        _verify_entry_selection(selection, normalized["normalized_rows"], expected, prices, spx)
        events, action_diag = replication._read_distributions(inputs["wrds_distributions"]["data"])
        settlement, settlement_diag = _parse_cboe_pm(inputs)
        coverage, pair_rows = _coverage_rows(selection, expected, prices, spx, settlement, events, sessions)
    complete = len(coverage) == EXPECTED_PAIRS and all(item["complete"] for item in coverage) and len(pair_rows) == EXPECTED_PAIRS
    audit = {"period": PERIOD, "historical_evaluation": "NOT RUN", "prices": price_diag,
             "distributions": action_diag, "settlements": settlement_diag,
             "coverage_complete_count": sum(item["complete"] for item in coverage),
             "coverage_expected_count": EXPECTED_PAIRS, "missing_input_roles": missing_roles}
    status = "NOT_RUN_COVERAGE_BLOCKED"
    files: dict[str, bytes] = {
        "coverage.json": (json.dumps(coverage, indent=2, sort_keys=True) + "\n").encode(),
        "source-audit.json": (json.dumps(audit, indent=2, sort_keys=True) + "\n").encode(),
    }
    if complete:
        # Contract selection is durable and revalidated before this first outcome construction.
        normalized_rows = []
        for row in pair_rows:
            normalized_rows.append(row)
        ledgers, by_scenario = _build_ledgers(normalized_rows)
        if len(ledgers) != EXPECTED_PAIRS * len(FILLS):
            raise ValueError("complete evaluation must retain exactly 588 pair/fill rows")
        summary = _summarize_ledgers(ledgers, by_scenario["scenarios"], draws=draws)
        status = "EVALUATED"
        case_rows = _case_rows(ledgers)
        if len(case_rows) != EXPECTED_PAIRS * len(FILLS) * len(ARMS) * 2 * len(SLIPPAGE) * len(FUNDING):
            raise ValueError("complete evaluation must retain exactly 35,280 scenario case rows")
        files.update({"row-ledgers.json": (json.dumps(case_rows, indent=2, sort_keys=True) + "\n").encode(),
                      "summary.json": (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode()})
    run_identity_checks["after_evaluation_before_publication"] = _check_identity(repo, identity, inputs, selection_path, selection_sha)
    metadata = {"status": status, "historical_evaluation": "RAN" if status == "EVALUATED" else "NOT RUN",
                "period": PERIOD, "run_started_utc": started, "run_ended_utc": utc_now(),
                "argv": argv, "cwd": str(Path.cwd()), "host": os.uname().nodename,
                "python": sys.version, "python_executable": sys.executable,
                "git": {"sha": identity["head"], "clean": True}, "model_endpoint": "N/A_DETERMINISTIC",
                "model_identity": "N/A_DETERMINISTIC", "protocol_sha256": inputs["protocol"]["sha256"],
                "calendar_sha256": inputs["calendar"]["sha256"], "input_manifest_sha256": manifest_sha,
                "inputs": {key: {k: value[k] for k in ("path", "bytes", "sha256")} for key, value in inputs.items()},
                "selection_path": str(selection_path), "selection_sha256": selection_sha,
                "code_sha256": {role: item["sha256"] for role, item in identity["code"].items()},
                "integrity_before": {key: {k: value[k] for k in ("path", "bytes", "sha256")} for key, value in inputs.items()},
                "integrity_after": {key: {k: value[k] for k in ("path", "bytes", "sha256")} for key, value in inputs.items()},
                "integrity_checks": run_identity_checks,
                "output_sha256": {name: sha256(data) for name, data in files.items()},
                "limitations": SOURCE_LIMITS}
    files["run-manifest.json"] = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()
    _check_identity(repo, identity, inputs, selection_path, selection_sha)
    result = _atomic_bundle(out, repo, files, inputs,
                            final_guard=lambda: _check_identity(repo, identity, inputs,
                                                                selection_path, selection_sha))
    result["status"] = status
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source-audit", "evaluate"))
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--input-manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--selection-sha256")
    parser.add_argument("--draws", type=int, default=10_000)
    args = parser.parse_args(argv)
    repo = repo_root()
    command = [sys.argv[0], *(argv if argv is not None else sys.argv[1:])]
    try:
        if args.mode == "source-audit":
            result = source_admission(repo, args.input_manifest, args.input_manifest_sha256, args.out, command)
        else:
            if not args.selection or not args.selection_sha256:
                raise ValueError("evaluate requires --selection and --selection-sha256 from a completed source-audit bundle")
            if args.draws != 10_000:
                raise ValueError("the frozen bootstrap draw count is 10000")
            result = evaluate(repo, args.input_manifest, args.input_manifest_sha256,
                              args.selection, args.selection_sha256, args.out, command, args.draws)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
