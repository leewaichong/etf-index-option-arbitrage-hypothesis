"""Offline normalization of a documented WRDS OptionMetrics web CSV export."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from spyspx.optionmetrics_admission import _validate_output, git_info

RAW_REQUIRED = ("secid", "date", "symbol", "symbol_flag", "exdate", "cp_flag", "strike_price", "best_bid", "best_offer", "optionid", "am_settlement", "contract_size", "ss_flag", "root", "suffix", "ticker", "index_flag", "exercise_style")
NORMALIZED = ("normalized_security_id", "normalized_option_id", "normalized_quote_date", "normalized_symbol", "normalized_symbol_flag", "normalized_expiry_date", "normalized_cp_flag", "normalized_strike_milli", "normalized_best_bid", "normalized_best_offer", "normalized_am_settlement", "normalized_contract_size", "normalized_special_settlement", "normalized_exercise_style", "normalized_underlying")
PLACEHOLDERS = {"", "?", "unknown", "tbd", "placeholder", "n/a", "na", "null", "none", "example", "changeme"}
MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_object(data: bytes, label: str) -> dict:
    try:
        obj = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be a JSON object")
    return obj


def _read_snapshot(paths: dict[str, Path]) -> dict[str, dict]:
    records = {}
    for role in ("raw_export", "source_metadata", "identity_metadata"):
        path = paths[role].resolve(strict=True)
        data = path.read_bytes()
        records[role] = {"path": str(path), "bytes": len(data), "sha256": sha256(data), "data": data}
    return records


def _records(snapshot: dict[str, dict]) -> dict[str, dict]:
    return {role: {key: record[key] for key in ("path", "bytes", "sha256")} for role, record in snapshot.items()}


def _unchanged(snapshot: dict[str, dict]) -> bool:
    for record in snapshot.values():
        try:
            data = Path(record["path"]).read_bytes()
        except OSError:
            return False
        if len(data) != record["bytes"] or sha256(data) != record["sha256"]:
            return False
    return True


def _decode_export(raw: bytes, compression: str) -> bytes:
    has_gzip_magic = raw.startswith(b"\x1f\x8b")
    if compression not in {"none", "gzip"}:
        raise ValueError("query compression must be none or gzip")
    if has_gzip_magic != (compression == "gzip"):
        raise ValueError("raw export gzip magic does not match authenticated compression metadata")
    if compression == "none":
        return raw
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as stream:
            decoded = stream.read(MAX_DECOMPRESSED_BYTES + 1)
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise ValueError(f"raw export is corrupt or truncated gzip: {exc}") from exc
    if len(decoded) > MAX_DECOMPRESSED_BYTES:
        raise ValueError(f"decoded gzip exceeds the {MAX_DECOMPRESSED_BYTES}-byte safety limit")
    return decoded


def _validate_metadata(source: dict, identity: dict, raw_hash: str, source_hash: str, raw_size: int) -> dict:
    if source.get("status") != "AUTHENTICATED_EXPORT_ACQUIRED_NOT_EVALUATED" or source.get("historical_evaluation") != "NOT_RUN":
        raise ValueError("source metadata is not the authenticated, not-evaluated pilot record")
    query = source.get("query")
    dictionary = source.get("dictionary")
    verified_ids = source.get("identities_verified_from_returned_export")
    if not isinstance(query, dict) or not isinstance(dictionary, dict) or not isinstance(verified_ids, dict):
        raise ValueError("source metadata has malformed query, dictionary, or verified identity records")
    if query.get("file_sha256") != raw_hash:
        raise ValueError("source metadata hash does not match raw export")
    if type(query.get("reported_rows")) is not int or query["reported_rows"] < 0:
        raise ValueError("source metadata must define an integer reported row count")
    if "reported_bytes" in query and query["reported_bytes"] != raw_size:
        raise ValueError("source metadata reported_bytes does not match raw export")
    start = _iso(query.get("quote_start"), "query.quote_start")
    end = _iso(query.get("quote_end"), "query.quote_end")
    if end < start:
        raise ValueError("source metadata quote_end precedes quote_start")
    if query.get("option_type") != "Call Only" or query.get("exercise_style") != "Both" or query.get("security_type") != "Both" or query.get("days_to_expiry_operator") != "eq" or query.get("days_to_expiry") != 1 or query.get("output") != "csv" or query.get("date_format") != "YYYY-MM-DD":
        raise ValueError("source metadata query filters do not match the documented pilot export")
    if query.get("compression") not in {"none", "gzip"}:
        raise ValueError("source metadata compression must explicitly be none or gzip")
    if dictionary.get("product") != "optionm_all" or dictionary.get("library") != "optionm" or dictionary.get("file") != "opprcd":
        raise ValueError("source metadata does not identify the authenticated opprcd export")
    if dictionary.get("settlement_encoding") != {"0": "Standard", "1": "Non-std", "E": "Non-std Exp. Date"}:
        raise ValueError("source metadata settlement encoding is missing or changed")
    if source.get("source_join_sql") != "NOT_EXPOSED_BY_WEB_QUERY" or source.get("independent_source_join_verification") != "NOT_RUN":
        raise ValueError("source metadata must keep unseen SQL and independent join verification explicit")
    if identity.get("source_metadata_sha256") != source_hash:
        raise ValueError("identity metadata is not bound to the supplied authenticated metadata file")
    if identity.get("status") != "NORMALIZER_IDENTITY_EXPECTATIONS_ONLY" or identity.get("historical_evaluation") != "NOT_RUN" or identity.get("join_verification") != "NOT_RUN":
        raise ValueError("identity metadata must not claim evaluation or source-join verification")
    if not isinstance(identity.get("provenance_reference"), str) or identity["provenance_reference"].strip().lower() in PLACEHOLDERS:
        raise ValueError("identity metadata requires a non-placeholder provenance_reference")
    if identity.get("query_id") != query.get("id"):
        raise ValueError("identity metadata query_id does not match authenticated source metadata")
    if identity.get("license_scope") != source.get("license_scope"):
        raise ValueError("identity metadata license_scope does not match authenticated source metadata")
    ids = identity.get("security_ids")
    if not isinstance(ids, dict) or set(ids) != {"SPY", "SPX"}:
        raise ValueError("identity metadata security_ids must contain exactly SPY and SPX")
    normalized_ids = {}
    for family, value in ids.items():
        if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
            raise ValueError(f"identity metadata security_ids.{family} must be a positive integer")
        normalized_ids[family] = str(int(value))
    if normalized_ids["SPY"] == normalized_ids["SPX"]:
        raise ValueError("SPY and SPX security IDs must differ")
    if {k: str(v) for k, v in verified_ids.items()} != normalized_ids:
        raise ValueError("identity metadata security IDs disagree with authenticated returned-export identities")
    selector = query.get("selector")
    codes = query.get("codes")
    if not isinstance(codes, list):
        raise ValueError("source metadata codes must be a list")
    if selector == "ticker":
        if set(codes) != {"SPY", "SPX"} or len(codes) != 2:
            raise ValueError("ticker-selected export codes must explicitly name SPY and SPX")
    elif selector == "secid":
        try:
            selected_ids = [str(int(str(code))) for code in codes]
        except (TypeError, ValueError) as exc:
            raise ValueError("SECID-selected export codes must be explicit positive IDs") from exc
        if any(int(code) <= 0 for code in selected_ids) or len(selected_ids) != len(set(selected_ids)) or set(selected_ids) != set(normalized_ids.values()):
            raise ValueError("SECID-selected export codes do not match the supplied verified security IDs")
    else:
        raise ValueError("source metadata selector must be ticker or secid")
    expected_maps = {
        "ticker_by_family": {"SPY": "SPY", "SPX": "SPX"},
        "index_flag_by_family": {"SPY": "0", "SPX": "1"},
        "exercise_style_by_family": {"SPY": "A", "SPX": "E"},
    }
    for key, expected in expected_maps.items():
        actual = identity.get(key)
        if not isinstance(actual, dict) or {str(k): str(v) for k, v in actual.items()} != expected:
            raise ValueError(f"identity metadata {key} must explicitly match the supplied pilot mapping")
    if identity.get("root_by_family") != {"SPY": ["SPY"], "SPX": ["SPX", "SPXW"]}:
        raise ValueError("identity metadata root_by_family must explicitly list the supported roots")
    if identity.get("settlement_by_root") != {"SPY": "0", "SPXW": "0", "SPX": "1"}:
        raise ValueError("identity metadata settlement_by_root must explicitly identify PM and AM encodings")
    return {"source": source, "identity": identity, "query": query, "dictionary": dictionary, "security_ids": normalized_ids, "date_range": (start, end)}


def _parse_symbol(text: str) -> tuple[str, date, str, int]:
    """Parse only the observed web-export grammar ROOT + space + YYMMDD + C/P + integer strike."""
    match = re.fullmatch(r"(SPY|SPXW|SPX) (\d{6})([CP])(\d+)", text)
    if not match:
        raise ValueError("raw symbol does not match the documented root-space-date-right-integer-strike grammar")
    root, date_text, right, strike_text = match.groups()
    try:
        expiry = datetime.strptime(date_text, "%y%m%d").date()
    except ValueError as exc:
        raise ValueError("raw symbol contains an invalid YYMMDD expiry") from exc
    strike = int(strike_text)
    if strike_text != str(strike):
        raise ValueError("raw symbol strike is padded, outside the observed unpadded encoding")
    if strike <= 0 or strike > 99_999_999:
        raise ValueError("raw symbol strike is outside the supported eight-digit OSI integer range")
    return root, expiry, right, strike


def _iso(value: str, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{field} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid date") from exc


def normalize(snapshot: dict[str, dict]) -> dict:
    raw_bytes = snapshot["raw_export"]["data"]
    source_meta = _json_object(snapshot["source_metadata"]["data"], "source metadata")
    identity_meta = _json_object(snapshot["identity_metadata"]["data"], "identity metadata")
    meta = _validate_metadata(source_meta, identity_meta, snapshot["raw_export"]["sha256"], snapshot["source_metadata"]["sha256"], snapshot["raw_export"]["bytes"])
    source = meta["source"]
    query = meta["query"]
    decoded_bytes = _decode_export(raw_bytes, query["compression"])

    reader = csv.reader(io.StringIO(decoded_bytes.decode("utf-8-sig"), newline=""), strict=True)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("raw CSV is empty") from exc
    if len(headers) != len(set(headers)):
        raise ValueError("raw CSV contains duplicate headers")
    missing = [field for field in RAW_REQUIRED if field not in headers]
    if missing:
        raise ValueError("raw CSV is missing required headers: " + ", ".join(missing))
    collision = sorted(set(headers).intersection(NORMALIZED))
    if collision:
        raise ValueError("raw headers collide with normalized output columns: " + ", ".join(collision))

    ids = meta["security_ids"]
    sid_to_family = {value: family for family, value in ids.items()}
    family_roots = identity_meta["root_by_family"]
    normalized_rows, excluded_rows, hard_rows = [], [], []
    reasons: Counter[str] = Counter()
    seen_option_date = set()
    seen_economic = set()
    observed_dates = set()
    total = 0

    for line, cells in enumerate(reader, 2):
        total += 1
        if len(cells) != len(headers):
            raise ValueError(f"raw CSV row {line} has {len(cells)} cells, expected {len(headers)}")
        raw = dict(zip(headers, cells))
        reasons_for_row = []
        try:
            sid = raw["secid"].strip()
            family = sid_to_family.get(sid)
            ticker = raw["ticker"].strip()
            index_flag = raw["index_flag"].strip()
            if family is None:
                raise ValueError("unknown security ID")
            if ticker != identity_meta["ticker_by_family"][family]:
                raise ValueError("ticker contradicts the supplied security ID family")
            if index_flag != identity_meta["index_flag_by_family"][family]:
                raise ValueError("index_flag contradicts the supplied security ID family")
            root, symbol_expiry, symbol_right, symbol_strike = _parse_symbol(raw["symbol"])
            if root not in family_roots[family]:
                raise ValueError("embedded root contradicts ticker/security ID family")
            if raw["root"].strip() or raw["suffix"].strip():
                raise ValueError("root/suffix columns are nonempty, outside the observed export encoding")
            if raw["symbol_flag"].strip() != "1":
                raise ValueError("unknown or unsupported symbol_flag")
            if raw["cp_flag"].strip() not in {"C", "P"} or raw["cp_flag"].strip() != symbol_right:
                raise ValueError("embedded right contradicts cp_flag or is unknown")
            if raw["cp_flag"].strip() != "C":
                raise ValueError("row contradicts the authenticated Call Only export filter")
            if not re.fullmatch(r"\d+", raw["strike_price"].strip()) or int(raw["strike_price"]) != symbol_strike:
                raise ValueError("embedded strike contradicts strike_price integer")
            quote_date = _iso(raw["date"].strip(), "date")
            observed_dates.add(quote_date)
            expiry = _iso(raw["exdate"].strip(), "exdate")
            if symbol_expiry != expiry:
                raise ValueError("embedded expiry contradicts exdate")
            style = raw["exercise_style"].strip()
            if style not in {"A", "E"} or style != identity_meta["exercise_style_by_family"][family]:
                raise ValueError("unknown or contradictory exercise_style")
            ss_flag = raw["ss_flag"].strip()
            if ss_flag not in {"0", "1", "E"}:
                raise ValueError("unknown or missing ss_flag")
            if not meta["date_range"][0] <= quote_date <= meta["date_range"][1]:
                raise ValueError("quote date falls outside authenticated inclusive export range")
            if expiry != quote_date + timedelta(days=1) and ss_flag == "0":
                raise ValueError("expiry contradicts authenticated one-day DTE filter")
            settlement = raw["am_settlement"].strip()
            expected_settlement = identity_meta["settlement_by_root"].get(root)
            if settlement not in {"0", "1"} or expected_settlement is None:
                raise ValueError("unknown or ambiguous settlement encoding/root")
            if settlement != expected_settlement:
                raise ValueError("AM settlement contradicts embedded root family")
            if any(raw[field].strip().lower() in PLACEHOLDERS for field in ("optionid", "secid", "ticker", "index_flag", "cp_flag", "symbol_flag", "exercise_style")):
                raise ValueError("unknown sentinel in identity field")

            key_id = (sid, raw["optionid"].strip(), quote_date)
            key_economic = (sid, quote_date, root, expiry, symbol_right, symbol_strike)
            if not raw["optionid"].strip():
                raise ValueError("missing optionid")
            if key_id in seen_option_date:
                raise ValueError("duplicate optionid/session identity")
            if key_economic in seen_economic:
                raise ValueError("duplicate economic option/session identity")
            seen_option_date.add(key_id)
            seen_economic.add(key_economic)

            canonical = {
                "normalized_security_id": sid,
                "normalized_option_id": raw["optionid"].strip(),
                "normalized_quote_date": quote_date.isoformat(),
                "normalized_symbol": f"{root}{expiry:%y%m%d}{symbol_right}{symbol_strike:08d}",
                "normalized_symbol_flag": "1",
                "normalized_expiry_date": expiry.isoformat(),
                "normalized_cp_flag": symbol_right,
                "normalized_strike_milli": str(symbol_strike),
                "normalized_best_bid": raw["best_bid"].strip(),
                "normalized_best_offer": raw["best_offer"].strip(),
                "normalized_am_settlement": settlement,
                "normalized_contract_size": raw["contract_size"].strip(),
                "normalized_special_settlement": "" if ss_flag == "0" else f"WRDS ss_flag={ss_flag}",
                "normalized_exercise_style": style,
                "normalized_underlying": ticker,
            }
            if ss_flag != "0":
                reasons_for_row.append(f"nonstandard special settlement excluded (ss_flag={ss_flag})")
            if root == "SPX":
                reasons_for_row.append("consistent AM SPX excluded; PM SPXW only")
            full = {**raw, **canonical}
            if reasons_for_row:
                excluded_rows.append({**full, "normalization_reasons": "; ".join(reasons_for_row)})
                reasons.update(reasons_for_row)
            else:
                normalized_rows.append(full)
        except (ValueError, TypeError, KeyError) as exc:
            reason = str(exc) or "invalid or ambiguous row metadata"
            hard_rows.append({**raw, "line": line, "normalization_reasons": reason})
            reasons[reason] += 1

    if total != query["reported_rows"]:
        reasons["raw row count contradicts authenticated query metadata"] += 1
        hard_rows.append({"line": 0, "normalization_reasons": "raw row count contradicts authenticated query metadata"})
    if not normalized_rows:
        reasons["no standard PM target rows available to normalize"] += 1
        hard_rows.append({"line": 0, "normalization_reasons": "no standard PM target rows available to normalize"})
    return {
        "status": "NORMALIZATION_ONLY" if not hard_rows else "BLOCKED",
        "normalized_rows": normalized_rows,
        "excluded_rows": excluded_rows,
        "hard_rows": hard_rows,
        "reason_counts": dict(sorted(reasons.items())),
        "row_count": total,
        "normalized_count": len(normalized_rows),
        "excluded_count": len(excluded_rows),
        "hard_failure_count": len(hard_rows),
        "observed_dates": sorted(d.isoformat() for d in observed_dates),
        "source_metadata": source,
        "identity_metadata": identity_meta,
        "raw_headers": headers,
        "decoded_bytes": len(decoded_bytes),
        "decoded_sha256": sha256(decoded_bytes),
        "input_records": _records(snapshot),
    }


def _write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def publish(out: Path, repo: Path, result: dict, snapshot: dict, argv: list[str], code_path: Path) -> None:
    target = _validate_output(out, repo)
    if target.exists():
        raise FileExistsError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not _unchanged(snapshot):
        raise ValueError("BLOCKED: an input changed after its parsed snapshot")
    stage = Path(tempfile.mkdtemp(prefix=".optionmetrics-normalizer-", dir=target.parent))
    try:
        raw_headers = result["raw_headers"]
        if result["status"] == "NORMALIZATION_ONLY":
            _write_csv(stage / "normalized.csv", raw_headers + list(NORMALIZED), result["normalized_rows"])
        _write_csv(stage / "excluded.csv", raw_headers + list(NORMALIZED) + ["normalization_reasons"], result["excluded_rows"])
        hard_headers = list(dict.fromkeys([*raw_headers, "line", "normalization_reasons"]))
        _write_csv(stage / "hard-failures.csv", hard_headers, result["hard_rows"])
        identity = result["identity_metadata"]
        source = result["source_metadata"]
        manifest = {
            "status": result["status"], "historical_evaluation": "NOT RUN", "utc": datetime.now(timezone.utc).isoformat(),
            "argv": argv, "git": git_info(repo), "code_sha256": sha256(code_path.read_bytes()),
            "inputs": result["input_records"], "rows_seen": result["row_count"],
            "quote_date_coverage": {
                "declared_start": source["query"]["quote_start"],
                "declared_end": source["query"]["quote_end"],
                "observed_min": result["observed_dates"][0] if result["observed_dates"] else None,
                "observed_max": result["observed_dates"][-1] if result["observed_dates"] else None,
                "observed_distinct_dates": len(result["observed_dates"]),
                "coverage_claimed": False,
            },
            "decoded_csv": {"bytes": result["decoded_bytes"], "sha256": result["decoded_sha256"]},
            "normalized_rows": result["normalized_count"], "excluded_rows": result["excluded_count"],
            "hard_failures": result["hard_failure_count"], "reason_counts": result["reason_counts"],
            "transformation": {"symbol_grammar": "ROOT + one space + YYMMDD + C/P + unpadded integer strike", "canonical_symbol": "compact OSI with strike zero-padded to eight digits after exact identity match", "compression": source["query"]["compression"], "ss_flag_0": "normalized_special_settlement blank", "ss_flag_1_or_E": "excluded with nonblank normalized_special_settlement"},
            "source_metadata_reference": {"query_id": source["query"]["id"], "selector": source["query"]["selector"], "codes": source["query"]["codes"], "quote_start": source["query"]["quote_start"], "quote_end": source["query"]["quote_end"], "dictionary": source["dictionary"], "source_join_sql": "NOT_EXPOSED_BY_WEB_QUERY", "independent_source_join_verification": "NOT_RUN"},
            "identity_expectations": {k: identity[k] for k in ("security_ids", "ticker_by_family", "index_flag_by_family", "exercise_style_by_family", "root_by_family", "settlement_by_root")},
            "limitations": ["Normalization only. This is not source-join verification, source admission, complete-universe confirmation, or historical evaluation.", "No receipt attestation was created for unseen SQL.", "Normalized OSI symbols are derived representations and do not replace preserved raw symbols.", "No P&L or strategy output was computed."],
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if not _unchanged(snapshot):
            raise ValueError("BLOCKED: an input changed immediately before publication")
        if target.exists():
            raise FileExistsError(f"output already exists: {target}")
        os.rename(stage, target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--source-metadata", required=True, type=Path, help="authenticated-schema-and-pilot.json")
    parser.add_argument("--identity-metadata", required=True, type=Path, help="explicit identity expectations bound to source metadata")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    paths = {"raw_export": args.csv, "source_metadata": args.source_metadata, "identity_metadata": args.identity_metadata}
    try:
        snapshot = _read_snapshot(paths)
        result = normalize(snapshot)
        publish(args.out, repo, result, snapshot, [sys.argv[0], *(argv if argv is not None else sys.argv[1:])], Path(__file__))
        print(f"{result['status']}: rows={result['row_count']} normalized={result['normalized_count']} excluded={result['excluded_count']} hard_failures={result['hard_failure_count']}")
        return 0 if result["status"] == "NORMALIZATION_ONLY" else 2
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr); return 4
    except (OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
