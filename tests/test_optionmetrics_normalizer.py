"""Synthetic fixtures for the WRDS export normalizer, not licensed market data."""
import csv
import gzip
import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import spyspx.optionmetrics_normalizer as normalizer
from spyspx.optionmetrics_normalizer import NORMALIZED, RAW_REQUIRED, _read_snapshot, normalize, publish

RAW_HEADERS = ["secid", "date", "symbol", "symbol_flag", "exdate", "last_date", "cp_flag", "strike_price", "best_bid", "best_offer", "volume", "open_interest", "impl_volatility", "delta", "gamma", "vega", "theta", "optionid", "cfadj", "am_settlement", "contract_size", "ss_flag", "forward_price", "expiry_indicator", "root", "suffix", "ticker", "index_flag", "issuer", "exercise_style"]


def row(family="SPY", *, root=None, symbol=None, optionid="synthetic-spy", strike=325000, ss="0", settlement=None, quote="2019-08-06", expiry="2019-08-07"):
    root = root or ("SPY" if family == "SPY" else "SPXW")
    settlement = settlement if settlement is not None else ("1" if root == "SPX" else "0")
    strike_text = str(strike)
    return {
        "secid": "70001" if family == "SPY" else "80002", "date": quote,
        "symbol": symbol or f"{root} {expiry[2:4]}{expiry[5:7]}{expiry[8:10]}C{strike_text}",
        "symbol_flag": "1", "exdate": expiry, "last_date": "2019-08-06", "cp_flag": "C",
        "strike_price": strike_text, "best_bid": "1.00", "best_offer": "1.10", "volume": "0",
        "open_interest": "0", "impl_volatility": "0.2", "delta": "0.5", "gamma": "0.1",
        "vega": "0.1", "theta": "-0.1", "optionid": optionid, "cfadj": "1",
        "am_settlement": settlement, "contract_size": "100", "ss_flag": ss,
        "forward_price": "325", "expiry_indicator": "", "root": "", "suffix": "",
        "ticker": family, "index_flag": "0" if family == "SPY" else "1",
        "issuer": "Synthetic fixture", "exercise_style": "A" if family == "SPY" else "E",
    }


def fixtures(tmp_path, rows=None, *, selector="ticker", compression="none", quote_start="2019-08-06", quote_end="2019-08-06"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    rows = rows or [row(), row("SPX", optionid="synthetic-spx", strike=325000)]
    raw = tmp_path / ("synthetic.csv.gz" if compression == "gzip" else "synthetic.csv")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=RAW_HEADERS); writer.writeheader(); writer.writerows(rows)
    decoded = stream.getvalue().encode()
    raw.write_bytes(gzip.compress(decoded, mtime=0) if compression == "gzip" else decoded)
    raw_hash = hashlib.sha256(raw.read_bytes()).hexdigest()
    codes = ["SPY", "SPX"] if selector == "ticker" else ["70001", "80002"]
    source = {
        "status": "AUTHENTICATED_EXPORT_ACQUIRED_NOT_EVALUATED", "historical_evaluation": "NOT_RUN",
        "source_join_sql": "NOT_EXPOSED_BY_WEB_QUERY", "independent_source_join_verification": "NOT_RUN",
        "dictionary": {"product": "optionm_all", "library": "optionm", "file": "opprcd", "settlement_encoding": {"0": "Standard", "1": "Non-std", "E": "Non-std Exp. Date"}},
        "query": {"id": 77, "file_sha256": raw_hash, "reported_rows": len(rows), "quote_start": quote_start, "quote_end": quote_end, "selector": selector, "codes": codes, "option_type": "Call Only", "exercise_style": "Both", "security_type": "Both", "days_to_expiry_operator": "eq", "days_to_expiry": 1, "output": "csv", "compression": compression, "date_format": "YYYY-MM-DD"},
        "identities_verified_from_returned_export": {"SPY": "70001", "SPX": "80002"},
        "license_scope": "Synthetic unit test only",
    }
    source_path = tmp_path / "source-metadata.json"; source_path.write_text(json.dumps(source))
    identity = {
        "status": "NORMALIZER_IDENTITY_EXPECTATIONS_ONLY", "historical_evaluation": "NOT_RUN", "join_verification": "NOT_RUN",
        "query_id": 77, "source_metadata_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "provenance_reference": "synthetic unit fixture provenance", "license_scope": "Synthetic unit test only",
        "security_ids": {"SPY": "70001", "SPX": "80002"}, "ticker_by_family": {"SPY": "SPY", "SPX": "SPX"},
        "index_flag_by_family": {"SPY": "0", "SPX": "1"}, "exercise_style_by_family": {"SPY": "A", "SPX": "E"},
        "root_by_family": {"SPY": ["SPY"], "SPX": ["SPX", "SPXW"]},
        "settlement_by_root": {"SPY": "0", "SPXW": "0", "SPX": "1"},
        "identity_notes": "Synthetic mapping only",
    }
    identity_path = tmp_path / "identity-metadata.json"; identity_path.write_text(json.dumps(identity))
    return {"raw_export": raw, "source_metadata": source_path, "identity_metadata": identity_path}


def test_normalizes_unpadded_strikes_and_preserves_source_fields(tmp_path):
    rows = [row(strike=325000), row("SPX", optionid="synthetic-spx", strike=1800000)]
    paths = fixtures(tmp_path, rows)
    result = normalize(_read_snapshot(paths))
    assert result["status"] == "NORMALIZATION_ONLY"
    assert result["normalized_rows"][0]["symbol"] == "SPY 190807C325000"
    assert result["normalized_rows"][0]["normalized_symbol"] == "SPY190807C00325000"
    assert result["normalized_rows"][1]["normalized_symbol"] == "SPXW190807C01800000"
    assert result["normalized_rows"][0]["normalized_special_settlement"] == ""
    assert result["normalized_rows"][0]["ss_flag"] == "0"
    assert len(result["normalized_rows"][0]) == len(RAW_HEADERS) + len(NORMALIZED)


@pytest.mark.parametrize(("ss", "reason", "normalized_value"), [
    ("1", "ss_flag=1", "WRDS ss_flag=1"), ("E", "ss_flag=E", "WRDS ss_flag=E"),
])
def test_nonstandard_ssflags_are_nonblank_exclusions(ss, reason, normalized_value, tmp_path):
    paths = fixtures(tmp_path, [row(ss=ss), row("SPX", optionid="synthetic-spx", strike=1800000)])
    result = normalize(_read_snapshot(paths))
    assert result["status"] == "NORMALIZATION_ONLY"
    assert result["normalized_count"] == 1
    assert any(reason in item["normalization_reasons"] and item["normalized_special_settlement"] == normalized_value for item in result["excluded_rows"])


@pytest.mark.parametrize(("mutate", "message"), [
    (lambda r: r.update(symbol="SPY190807C325000"), "grammar"),
    (lambda r: r.update(symbol="SPY 190808C325000"), "expiry contradicts"),
    (lambda r: r.update(symbol="SPY 190807P325000"), "right contradicts"),
    (lambda r: r.update(symbol="SPY 190807C325001"), "strike contradicts"),
    (lambda r: r.update(ticker="SPX"), "ticker contradicts"),
    (lambda r: r.update(index_flag="1"), "index_flag contradicts"),
    (lambda r: r.update(secid="99999"), "unknown security ID"),
    (lambda r: r.update(symbol_flag="?"), "symbol_flag"),
    (lambda r: r.update(ss_flag="?"), "ss_flag"),
    (lambda r: r.update(exercise_style="?"), "exercise_style"),
    (lambda r: r.update(am_settlement="1"), "settlement contradicts"),
    (lambda r: r.update(root="SPY"), "root/suffix columns"),
])
def test_identity_or_encoding_failure_blocks_whole_batch(mutate, message, tmp_path):
    first = row(); mutate(first)
    result = normalize(_read_snapshot(fixtures(tmp_path, [first, row("SPX", optionid="synthetic-spx", strike=1800000)])))
    assert result["status"] == "BLOCKED"
    assert result["hard_failure_count"]
    assert any(message in item["normalization_reasons"] for item in result["hard_rows"])
    assert result["normalized_rows"]  # Diagnostic candidates exist only in memory; publish() must suppress them.


def test_spx_am_excluded_and_spxw_am_contradiction_blocks(tmp_path):
    paths = fixtures(tmp_path, [row(), row("SPX", root="SPX", optionid="synthetic-am", strike=1800000, settlement="1")])
    result = normalize(_read_snapshot(paths))
    assert result["status"] == "NORMALIZATION_ONLY"
    assert any("consistent AM SPX excluded" in item["normalization_reasons"] for item in result["excluded_rows"])
    paths = fixtures(tmp_path, [row(), row("SPX", root="SPXW", optionid="synthetic-bad", strike=1800000, settlement="1")])
    result = normalize(_read_snapshot(paths))
    assert result["status"] == "BLOCKED"


def test_duplicate_option_and_economic_keys_block(tmp_path):
    original = row()
    duplicate = dict(original, optionid="different-option-id")
    result = normalize(_read_snapshot(fixtures(tmp_path, [original, duplicate, row("SPX", optionid="synthetic-spx", strike=1800000)])))
    assert result["status"] == "BLOCKED"
    assert any("duplicate economic" in item["normalization_reasons"] for item in result["hard_rows"])
    different_contract = dict(original, symbol="SPY 190807C325001", strike_price="325001")
    result = normalize(_read_snapshot(fixtures(tmp_path, [original, different_contract, row("SPX", optionid="synthetic-spx", strike=1800000)])))
    assert result["status"] == "BLOCKED"
    assert any("duplicate optionid/session" in item["normalization_reasons"] for item in result["hard_rows"])


def test_duplicate_headers_and_ragged_rows_fail_closed(tmp_path):
    paths = fixtures(tmp_path)
    paths["raw_export"].write_text(paths["raw_export"].read_text().replace("secid,date", "secid,secid,date", 1))
    source = json.loads(paths["source_metadata"].read_text()); source["query"]["file_sha256"] = hashlib.sha256(paths["raw_export"].read_bytes()).hexdigest(); paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text()); identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest(); paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="duplicate headers"):
        normalize(_read_snapshot(paths))
    paths = fixtures(tmp_path)
    with paths["raw_export"].open("a") as f: f.write("extra,cells\n")
    source = json.loads(paths["source_metadata"].read_text()); source["query"]["file_sha256"] = hashlib.sha256(paths["raw_export"].read_bytes()).hexdigest(); source["query"]["reported_rows"] += 1; paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text()); identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest(); paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="cells"):
        normalize(_read_snapshot(paths))
    paths = fixtures(tmp_path)
    lines = paths["raw_export"].read_text().splitlines()
    paths["raw_export"].write_text("\n".join([lines[0], ",".join(lines[1].split(",")[:-1]), *lines[2:]]) + "\n")
    source = json.loads(paths["source_metadata"].read_text()); source["query"]["file_sha256"] = hashlib.sha256(paths["raw_export"].read_bytes()).hexdigest(); paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text()); identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest(); paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="cells"):
        normalize(_read_snapshot(paths))


def test_alias_normalized_header_and_hash_mismatch_fail(tmp_path):
    paths = fixtures(tmp_path)
    raw = paths["raw_export"].read_text().replace("secid,date", "secid,normalized_symbol,date", 1)
    paths["raw_export"].write_text(raw)
    source = json.loads(paths["source_metadata"].read_text()); source["query"]["file_sha256"] = hashlib.sha256(paths["raw_export"].read_bytes()).hexdigest(); paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text()); identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest(); paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="collide"):
        normalize(_read_snapshot(paths))
    paths = fixtures(tmp_path)
    source = json.loads(paths["source_metadata"].read_text()); source["query"]["file_sha256"] = "0" * 64; paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text()); identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest(); paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="does not match raw export"):
        normalize(_read_snapshot(paths))


def test_raw_bytes_unchanged_and_publish_suppresses_normalized_on_block(tmp_path):
    paths = fixtures(tmp_path)
    original_bytes = paths["raw_export"].read_bytes()
    snapshot = _read_snapshot(paths)
    result = normalize(snapshot)
    assert paths["raw_export"].read_bytes() == original_bytes
    blocked_paths = fixtures(tmp_path / "blocked", [row(), dict(row("SPX", optionid="bad", strike=1800000), symbol_flag="?")])
    blocked_snapshot = _read_snapshot(blocked_paths); blocked = normalize(blocked_snapshot)
    repo = Path(__file__).resolve().parents[1]
    out = repo / "planning" / "optionmetrics-20261029" / ("normalizer-test-" + tmp_path.name)
    try:
        publish(out, repo, blocked, blocked_snapshot, ["synthetic"], Path(normalizer.__file__))
        assert not (out / "normalized.csv").exists()
        assert json.loads((out / "manifest.json").read_text())["status"] == "BLOCKED"
    finally:
        shutil.rmtree(out, ignore_errors=True)
    assert paths["raw_export"].read_bytes() == original_bytes


@pytest.mark.parametrize(("change_at", "message"), [(1, "changed after its parsed snapshot"), (2, "changed immediately before publication")])
def test_snapshot_mutation_blocks_publish(tmp_path, monkeypatch, change_at, message):
    paths = fixtures(tmp_path); snapshot = _read_snapshot(paths); result = normalize(snapshot)
    out = Path(__file__).resolve().parents[1] / "planning" / "optionmetrics-20261029" / ("normalizer-mutation-" + tmp_path.name)
    check = normalizer._unchanged; calls = 0
    def mutate_second(snap):
        nonlocal calls
        calls += 1
        if calls == change_at:
            Path(snap["raw_export"]["path"]).write_bytes(Path(snap["raw_export"]["path"]).read_bytes() + b"\n")
        return check(snap)
    monkeypatch.setattr(normalizer, "_unchanged", mutate_second)
    with pytest.raises(ValueError, match=message):
        publish(out, Path(__file__).resolve().parents[1], result, snapshot, ["synthetic"], Path(normalizer.__file__))
    assert not out.exists()


def test_cli_normalization_only_bundle_is_explicitly_not_admission(tmp_path):
    paths = fixtures(tmp_path)
    repo = Path(__file__).resolve().parents[1]
    out = repo / "planning" / "optionmetrics-20261029" / ("normalizer-cli-" + tmp_path.name)
    args = ["--csv", str(paths["raw_export"]), "--source-metadata", str(paths["source_metadata"]), "--identity-metadata", str(paths["identity_metadata"]), "--out", str(out)]
    try:
        assert normalizer.main(args) == 0
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest["status"] == "NORMALIZATION_ONLY"
        assert manifest["historical_evaluation"] == "NOT RUN"
        assert manifest["source_metadata_reference"]["independent_source_join_verification"] == "NOT_RUN"
        assert (out / "normalized.csv").exists()
    finally:
        shutil.rmtree(out, ignore_errors=True)


def test_output_location_ignore_override_symlink_and_overwrite(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("planning/\n"); (repo / "planning").mkdir()
    assert normalizer._validate_output(repo / "planning" / "artifact", repo) == repo / "planning" / "artifact"
    (repo / ".gitignore").write_text("planning/*\n!planning/artifact\n")
    with pytest.raises(ValueError, match="not ignored"):
        normalizer._validate_output(repo / "planning" / "artifact", repo)
    (repo / ".gitignore").write_text("planning/\n")
    paths = fixtures(tmp_path / "inputs"); snap = _read_snapshot(paths); result = normalize(snap)
    out = repo / "planning" / "artifact"
    publish(out, repo, result, snap, ["synthetic"], Path(normalizer.__file__))
    with pytest.raises(FileExistsError):
        publish(out, repo, result, snap, ["synthetic"], Path(normalizer.__file__))
    outside = tmp_path / "outside"; outside.mkdir(); (repo / "planning" / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="inside this repo"):
        normalizer._validate_output(repo / "planning" / "escape" / "artifact", repo)


def _rebind_metadata(paths):
    source = json.loads(paths["source_metadata"].read_text())
    source["query"]["file_sha256"] = hashlib.sha256(paths["raw_export"].read_bytes()).hexdigest()
    paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text())
    identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest()
    paths["identity_metadata"].write_text(json.dumps(identity))


def test_inclusive_multiday_range_and_sec_id_selector(tmp_path):
    rows = [row(quote="2019-08-06", expiry="2019-08-07"), row("SPX", optionid="synthetic-spx", strike=1800000, quote="2019-08-07", expiry="2019-08-08")]
    paths = fixtures(tmp_path, rows, selector="secid", quote_start="2019-08-06", quote_end="2019-08-07")
    result = normalize(_read_snapshot(paths))
    assert result["status"] == "NORMALIZATION_ONLY"
    assert [item["normalized_quote_date"] for item in result["normalized_rows"]] == ["2019-08-06", "2019-08-07"]
    source = json.loads(paths["source_metadata"].read_text())
    source["query"]["codes"] = ["70001", "99999"]
    paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text())
    identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest()
    paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="SECID-selected"):
        normalize(_read_snapshot(paths))


def test_quote_outside_inclusive_range_blocks(tmp_path):
    rows = [row(quote="2019-08-05", expiry="2019-08-06"), row("SPX", optionid="synthetic-spx", strike=1800000)]
    result = normalize(_read_snapshot(fixtures(tmp_path, rows, quote_start="2019-08-06", quote_end="2019-08-07")))
    assert result["status"] == "BLOCKED"
    assert any("outside authenticated inclusive" in item["normalization_reasons"] for item in result["hard_rows"])


def test_gzip_magic_decoding_and_original_hash_binding(tmp_path):
    paths = fixtures(tmp_path, compression="gzip")
    raw = paths["raw_export"].read_bytes()
    snapshot = _read_snapshot(paths)
    result = normalize(snapshot)
    assert result["status"] == "NORMALIZATION_ONLY"
    assert result["input_records"]["raw_export"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["decoded_sha256"] == hashlib.sha256(gzip.decompress(raw)).hexdigest()
    assert paths["raw_export"].read_bytes() == raw
    source = json.loads(paths["source_metadata"].read_text()); source["query"]["compression"] = "none"
    paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text()); identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest()
    paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="magic does not match"):
        normalize(_read_snapshot(paths))


def test_corrupt_gzip_and_tampered_raw_hash_fail_closed(tmp_path):
    paths = fixtures(tmp_path, compression="gzip")
    data = paths["raw_export"].read_bytes()
    paths["raw_export"].write_bytes(data[:-8])
    _rebind_metadata(paths)
    with pytest.raises(ValueError, match="corrupt or truncated gzip"):
        normalize(_read_snapshot(paths))
    paths = fixtures(tmp_path, compression="gzip")
    source = json.loads(paths["source_metadata"].read_text()); source["query"]["file_sha256"] = "0" * 64
    paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text()); identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest()
    paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="does not match raw export"):
        normalize(_read_snapshot(paths))


def test_reported_raw_byte_count_must_match(tmp_path):
    paths = fixtures(tmp_path, compression="gzip")
    source = json.loads(paths["source_metadata"].read_text())
    source["query"]["reported_bytes"] = paths["raw_export"].stat().st_size + 1
    paths["source_metadata"].write_text(json.dumps(source))
    identity = json.loads(paths["identity_metadata"].read_text())
    identity["source_metadata_sha256"] = hashlib.sha256(paths["source_metadata"].read_bytes()).hexdigest()
    paths["identity_metadata"].write_text(json.dumps(identity))
    with pytest.raises(ValueError, match="reported_bytes"):
        normalize(_read_snapshot(paths))


def test_sec_id_selector_requires_row_identity_to_match_selected_family(tmp_path):
    data = [row(), row("SPX", optionid="synthetic-spx", strike=1800000)]
    paths = fixtures(tmp_path, data, selector="secid")
    changed = data[0].copy(); changed["secid"] = "80002"
    with paths["raw_export"].open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_HEADERS); writer.writeheader(); writer.writerows([changed, data[1]])
    _rebind_metadata(paths)
    result = normalize(_read_snapshot(paths))
    assert result["status"] == "BLOCKED"
    assert any("ticker contradicts" in item["normalization_reasons"] for item in result["hard_rows"])
