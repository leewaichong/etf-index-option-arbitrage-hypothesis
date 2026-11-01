"""Offline admission audit for explicitly mapped, enriched OptionMetrics CSV exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

FIELDS = ("security_id", "option_id", "quote_date", "symbol", "symbol_flag", "strike_milli", "expiry_date", "cp_flag", "best_bid", "best_offer", "am_settlement", "contract_size", "special_settlement", "exercise_style")
ROLES = ("csv", "mapping", "receipt", "calendar")
PLACEHOLDERS = {"", "unknown", "tbd", "placeholder", "n/a", "na", "null", "none", "example", "changeme"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_text(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() not in PLACEHOLDERS


def parse_date(value: str) -> date:
    if not isinstance(value, str):
        raise ValueError("date must be an ISO string")
    return date.fromisoformat(value.strip())


def snapshot(paths: dict[str, Path]) -> dict[str, dict]:
    """Read every input once and retain the bytes used by the parser."""
    result = {}
    for role in ROLES:
        path = paths[role].resolve(strict=True)
        data = path.read_bytes()
        result[role] = {"path": str(path), "bytes": len(data), "sha256": sha256_bytes(data), "data": data}
    return result


def snapshot_records(snapshots: dict[str, dict]) -> dict[str, dict]:
    return {role: {k: v[k] for k in ("path", "bytes", "sha256")} for role, v in snapshots.items()}


def snapshots_unchanged(before: dict[str, dict]) -> bool:
    for role in ROLES:
        try:
            p = Path(before[role]["path"])
            data = p.read_bytes()
        except OSError:
            return False
        if len(data) != before[role]["bytes"] or sha256_bytes(data) != before[role]["sha256"]:
            return False
    return True


def parse_osi(text: str) -> tuple[str, date, str, int]:
    """Return normalized root, expiry, right, and OSI strike integer."""
    s = text.strip().upper()
    if len(s) == 21 and " " in s[:6] and s[6:12].isdigit():
        s = s[:6].rstrip() + s[6:]
    m = re.fullmatch(r"([A-Z0-9]{1,6})(\d{6})([CP])(\d{8})", s)
    if not m:
        raise ValueError("invalid or ambiguous OSI symbol")
    root, ymd, right, strike = m.groups()
    try:
        expiry = datetime.strptime(ymd, "%y%m%d").date()
    except ValueError as exc:
        raise ValueError("invalid OSI expiry") from exc
    return root, expiry, right, int(strike)


def _number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _receipt(data: bytes, raw_hash: str) -> dict:
    receipt = json.loads(data)
    if not isinstance(receipt, dict):
        raise ValueError("receipt must be a JSON object")
    required = ("source", "version", "provenance_reference", "license_scope", "file_sha256", "units_confirmed", "unit_reference", "multiplier_confirmed", "multiplier_reference", "underlyings", "requested_start_date", "requested_end_date", "export_filters", "export_universe", "exercise_join_reference", "exercise_join_cardinality", "underlying_join_reference", "underlying_join_cardinality", "extractor_attestation")
    missing = [k for k in required if k not in receipt or (isinstance(receipt[k], str) and not valid_text(receipt[k]))]
    if missing:
        raise ValueError("receipt missing or has placeholder metadata: " + ", ".join(missing))
    text_refs = ("source", "version", "provenance_reference", "license_scope", "unit_reference", "multiplier_reference", "exercise_join_reference", "underlying_join_reference", "extractor_attestation")
    if any(not valid_text(receipt.get(k)) for k in text_refs):
        raise ValueError("receipt provenance and join references must be non-placeholder text")
    if receipt["file_sha256"] != raw_hash:
        raise ValueError("receipt file_sha256 does not match input CSV")
    ids = receipt.get("security_ids")
    if not isinstance(ids, dict) or set(ids) != {"SPY", "SPX"}:
        raise ValueError("receipt security_ids must contain exactly SPY and SPX")
    normalized = {}
    for key, value in ids.items():
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValueError(f"security_ids.{key} must be a positive integer or digit string")
        text = str(value).strip()
        if not text.isdigit() or int(text) <= 0:
            raise ValueError(f"security_ids.{key} must be a positive integer or digit string")
        normalized[key] = str(int(text))
    if normalized["SPY"] == normalized["SPX"]:
        raise ValueError("SPY and SPX security IDs must be distinct")
    if receipt["underlyings"] != {"SPY": "SPY", "SPX": "SPX"}:
        raise ValueError("receipt underlyings must explicitly map SPY to SPY and SPX to SPX")
    multipliers = receipt["multiplier_confirmed"]
    if receipt["units_confirmed"] is not True or not isinstance(multipliers, dict) or set(multipliers) != {"SPY", "SPX"} or any(type(multipliers[k]) is not int or multipliers[k] != 100 for k in ("SPY", "SPX")):
        raise ValueError("receipt must separately confirm units and multiplier 100 for SPY and SPX")
    if receipt["exercise_join_cardinality"] != "many-to-one" or receipt["underlying_join_cardinality"] != "many-to-one":
        raise ValueError("receipt must attest many-to-one exercise and underlying joins")
    try:
        start, end = parse_date(receipt["requested_start_date"]), parse_date(receipt["requested_end_date"])
    except (TypeError, ValueError) as exc:
        raise ValueError("receipt requested date range must use ISO dates") from exc
    if end < start:
        raise ValueError("receipt requested_end_date precedes start date")
    for key in ("export_filters", "export_universe"):
        if not isinstance(receipt[key], (dict, list)) or not receipt[key]:
            raise ValueError(f"receipt {key} must be a nonempty documented object or list")
    return {**receipt, "_security_ids": normalized, "_date_range": (start, end)}


def _mapping(data: bytes) -> dict[str, str]:
    mapping = json.loads(data)
    if not isinstance(mapping, dict) or set(mapping) != set(FIELDS):
        raise ValueError("mapping must contain exactly the required canonical fields")
    if any(not valid_text(v) for v in mapping.values()):
        raise ValueError("mapping field headers must be non-placeholder strings")
    if len(set(mapping.values())) != len(FIELDS):
        raise ValueError("mapping must use distinct CSV headers for every canonical field")
    return mapping


def audit(paths: dict[str, Path], before: dict[str, dict] | None = None) -> dict:
    before = before or snapshot(paths)
    blobs = {role: before[role]["data"] for role in ROLES}
    mapping = _mapping(blobs["mapping"])
    receipt = _receipt(blobs["receipt"], before["csv"]["sha256"])
    sessions = set()
    for line in blobs["calendar"].decode("utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            sessions.add(parse_date(line))
    if not sessions:
        raise ValueError("calendar must contain explicit ISO session dates")

    reader = csv.reader(io.StringIO(blobs["csv"].decode("utf-8-sig"), newline=""))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("CSV is empty") from exc
    if len(headers) != len(set(headers)):
        raise ValueError("CSV contains duplicate header names")
    if any(mapping[k] not in headers for k in FIELDS):
        absent = [mapping[k] for k in FIELDS if mapping[k] not in headers]
        raise ValueError("mapped CSV headers missing: " + ", ".join(absent))
    indexes = {k: headers.index(mapping[k]) for k in FIELDS}
    sid_to_underlying = {v: k for k, v in receipt["_security_ids"].items()}
    start, end = receipt["_date_range"]
    accepted, rejected, hard = [], [], []
    reason_counts: Counter[str] = Counter()
    observed_dates: set[date] = set()
    seen_option_ids: set[tuple[str, str, date]] = set()
    seen_contracts: set[tuple[str, date, str, date, str, int]] = set()
    row_count = 0

    def reject(line: int, row: dict, reasons: list[str], is_hard: bool = False) -> None:
        rejected.append({"line": line, "reasons": "; ".join(dict.fromkeys(reasons)), **row})
        for reason in set(reasons):
            reason_counts[reason] += 1
        if is_hard:
            hard.extend(f"row {line}: {r}" for r in reasons)

    for line, cells in enumerate(reader, 2):
        row_count += 1
        if len(cells) != len(headers):
            raise ValueError(f"CSV row {line} has {len(cells)} cells; expected {len(headers)}")
        row = {k: cells[indexes[k]].strip() for k in FIELDS}
        reasons: list[str] = []
        sid = row["security_id"]
        underlying = sid_to_underlying.get(sid)
        try:
            root, osi_expiry, osi_right, osi_strike = parse_osi(row["symbol"])
        except ValueError as exc:
            reject(line, row, [str(exc)], True)
            continue
        allowed_roots = {"SPY"} if underlying == "SPY" else {"SPX", "SPXW"} if underlying == "SPX" else set()
        if root in {"SPY", "SPX", "SPXW"} and (underlying is None or root not in allowed_roots):
            reject(line, row, ["OSI root contradicts security_id/receipt underlying"], True)
            continue
        if underlying is None and root not in {"SPY", "SPX", "SPXW"}:
            reject(line, row, ["unsupported non-target root"])
            continue
        try:
            quote_date = parse_date(row["quote_date"])
            expiry = parse_date(row["expiry_date"])
            strike_milli = int(row["strike_milli"])
        except (TypeError, ValueError) as exc:
            reject(line, row, [f"invalid date or strike field: {exc}"], True)
            continue
        if underlying is not None:
            observed_dates.add(quote_date)
        if row["symbol_flag"] != "1":
            reject(line, row, ["unknown or unsupported symbol_flag"], True)
            continue
        if row["cp_flag"].upper() not in {"C", "P"} or row["cp_flag"].upper() != osi_right:
            reject(line, row, ["cp_flag conflicts with OSI right or is unknown"], True)
            continue
        if expiry != osi_expiry:
            reject(line, row, ["expiry_date conflicts with OSI expiry"], True)
            continue
        if strike_milli != osi_strike:
            reject(line, row, ["strike_milli conflicts with OSI strike integer"], True)
            continue
        if underlying is None:
            reject(line, row, ["unknown security_id for target OSI root"], True)
            continue
        if quote_date not in sessions:
            reject(line, row, ["quote_date is not an explicit calendar session"], True)
            continue
        if not start <= quote_date <= end:
            reject(line, row, ["target quote_date falls outside receipt requested date range"], True)
            continue
        contract_key = (sid, quote_date, root, osi_expiry, osi_right, osi_strike)
        option_key = (sid, row["option_id"], quote_date)
        if not row["option_id"]:
            reject(line, row, ["option_id missing"], True)
            continue
        if option_key in seen_option_ids or contract_key in seen_contracts:
            reject(line, row, ["duplicate option id/date or duplicate economic contract/session"], True)
            continue
        seen_option_ids.add(option_key)
        seen_contracts.add(contract_key)

        # Known but out-of-scope contracts are counted and retained as exclusions.
        if osi_right == "P": reasons.append("consistent put excluded; calls only")
        if expiry != quote_date + timedelta(days=1): reasons.append("other DTE excluded; expiry must be quote date plus one calendar day")
        if expiry not in sessions: reasons.append("expiry is not an explicit calendar session")
        settlement = row["am_settlement"]
        if settlement not in {"0", "1"}:
            reject(line, row, ["unknown or ambiguous AMSettlement"], True)
            continue
        style = row["exercise_style"].upper()
        if style not in {"A", "E"}:
            reject(line, row, ["unknown or ambiguous exercise_style"], True)
            continue
        expected_style = "A" if underlying == "SPY" else "E"
        if style != expected_style:
            reject(line, row, ["exercise_style contradicts underlying family"], True)
            continue
        if root == "SPXW" and settlement != "0":
            reject(line, row, ["SPXW contradicts AMSettlement; SPXW target requires PM value 0"], True)
            continue
        if root == "SPX" and settlement != "1":
            reject(line, row, ["SPX root contradicts settlement flag; AM SPX requires value 1"], True)
            continue
        if root == "SPY" and settlement != "0": reasons.append("SPY requires PM settlement value 0")
        if root == "SPX": reasons.append("consistent AM SPX excluded; PM SPXW only")
        if row["contract_size"] != "100": reasons.append("nonstandard contract_size excluded")
        if row["special_settlement"] != "": reasons.append("special settlement excluded")
        bid, ask = _number(row["best_bid"]), _number(row["best_offer"])
        if bid is None or ask is None or not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask <= 0 or bid > ask:
            reasons.append("unusable BBO excluded; bid and offer must be finite, positive, and uncrossed")
        if osi_right != "C":  # already recorded as a normal exclusion above
            pass
        eligible_root = root == "SPY" and underlying == "SPY" or root == "SPXW" and underlying == "SPX" and settlement == "0"
        if reasons:
            reject(line, row, reasons)
        elif eligible_root:
            accepted.append(row)
        else:
            reject(line, row, ["contract is outside admitted PM target roots"])

    accepted_roots = {parse_osi(row["symbol"])[0] for row in accepted}
    if not {"SPY", "SPXW"}.issubset(accepted_roots):
        hard.append("accepted rows must contain both SPY and SPXW roots")
    return {"accepted": accepted, "rejected": rejected, "hard_failures": list(dict.fromkeys(hard)),
            "reason_counts": dict(sorted(reason_counts.items())), "row_count": row_count,
            "observed_dates": sorted(d.isoformat() for d in observed_dates),
            "input_records": snapshot_records(before),
            "status": "ADMISSION_ONLY" if not hard else "BLOCKED"}


def git_info(repo: Path) -> dict:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False).stdout.strip()
    return {"sha": run("rev-parse", "HEAD") or "unavailable", "clean": not bool(run("status", "--porcelain"))}


def _validate_output(out: Path, repo: Path) -> Path:
    root = repo.resolve(strict=True)
    target = out.absolute()
    resolved = target.resolve()
    if not resolved.is_relative_to(root) or not any(resolved.is_relative_to(root / p) for p in ("planning", "data")):
        raise ValueError("output must resolve inside this repo under planning/ or data/")
    rel = resolved.relative_to(root).as_posix()
    check = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", "--", rel], cwd=root, check=False)
    if check.returncode != 0:
        raise ValueError("output path is not ignored by this repository's active Git ignore rules")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "--", rel], cwd=root, capture_output=True, text=True, check=False)
    if tracked.returncode == 0:
        raise ValueError("output path is tracked and cannot be used")
    return resolved


def write_bundle(out: Path, repo: Path, result: dict, argv: list[str], code_path: Path, before: dict[str, dict], receipt: dict) -> None:
    target = _validate_output(out, repo)
    if target.exists():
        raise FileExistsError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Recheck after audit and immediately before publication. Never replace the original snapshots.
    if not snapshots_unchanged(before):
        raise ValueError("BLOCKED: an input changed after its parsed snapshot")
    tmp = Path(tempfile.mkdtemp(prefix=".optionmetrics-admission-", dir=target.parent))
    try:
        if result["status"] == "ADMISSION_ONLY":
            with (tmp / "accepted.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(result["accepted"])
        with (tmp / "rejected.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["line", "reasons", *FIELDS]); w.writeheader(); w.writerows(result["rejected"])
        metadata = {"status": result["status"], "historical_evaluation": "NOT RUN", "utc": datetime.now(timezone.utc).isoformat(),
                    "argv": argv, "git": git_info(repo), "code_sha256": sha256_bytes(code_path.read_bytes()),
                    "inputs": result["input_records"], "accepted_rows": len(result["accepted"]), "rejected_rows": len(result["rejected"]),
                    "row_count": result["row_count"], "reason_counts": result["reason_counts"], "observed_dates": result["observed_dates"],
                    "total_observed_dates": len(result["observed_dates"]),
                    "observed_coverage": {"first_date": result["observed_dates"][0] if result["observed_dates"] else None, "last_date": result["observed_dates"][-1] if result["observed_dates"] else None, "unique_dates": len(result["observed_dates"])},
                    "declared_date_range": [receipt["requested_start_date"], receipt["requested_end_date"]],
                    "source_metadata": {k: receipt[k] for k in ("source", "version", "provenance_reference", "license_scope", "security_ids", "underlyings", "units_confirmed", "unit_reference", "multiplier_confirmed", "multiplier_reference", "export_filters", "export_universe")},
                    "exercise_join_reference": receipt["exercise_join_reference"], "exercise_join_cardinality": receipt["exercise_join_cardinality"],
                    "underlying_join_reference": receipt["underlying_join_reference"], "underlying_join_cardinality": receipt["underlying_join_cardinality"],
                    "extractor_attestation": receipt["extractor_attestation"], "hard_failures": result["hard_failures"],
                    "limitations": ["Admission only, not complete-study approval.", "Enriched CSV shape is not authenticated WRDS schema.", "No P&L, timing validation, terminal coverage, or pair selection is performed."]}
        (tmp / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        if not snapshots_unchanged(before):
            raise ValueError("BLOCKED: an input changed immediately before publication")
        if target.exists():
            raise FileExistsError(f"output already exists: {target}")
        os.rename(tmp, target)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path); parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path); parser.add_argument("--calendar", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    paths = dict(zip(ROLES, (args.csv, args.mapping, args.receipt, args.calendar)))
    try:
        before = snapshot(paths)
        result = audit(paths, before)
        receipt = _receipt(before["receipt"]["data"], before["csv"]["sha256"])
        write_bundle(args.out, repo, result, [sys.argv[0], *(argv if argv is not None else sys.argv[1:])], Path(__file__), before, receipt)
        print(f"{result['status']}: accepted={len(result['accepted'])} excluded={len(result['rejected'])} hard_failures={len(result['hard_failures'])}")
        return 0 if result["status"] == "ADMISSION_ONLY" else 2
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr); return 4
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, csv.Error) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
