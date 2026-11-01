"""Synthetic unit fixtures only. These are not OptionMetrics study data."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import spyspx.optionmetrics_admission as admission
from spyspx.optionmetrics_admission import FIELDS, ROLES, audit, main


def fixture(tmp_path, mutate=None):
    (tmp_path / "mapping.json").write_text(json.dumps({f: f for f in FIELDS}))
    (tmp_path / "calendar.txt").write_text("2026-10-19\n2026-10-20\n")
    rows = [
        dict(security_id="11", option_id="a", quote_date="2026-10-19", symbol="SPY261020C00700000", symbol_flag="1", strike_milli="700000", expiry_date="2026-10-20", cp_flag="C", best_bid="1.00", best_offer="1.10", am_settlement="0", contract_size="100", special_settlement="", exercise_style="A"),
        dict(security_id="22", option_id="b", quote_date="2026-10-19", symbol="SPXW261020C07000000", symbol_flag="1", strike_milli="7000000", expiry_date="2026-10-20", cp_flag="C", best_bid="2.00", best_offer="2.10", am_settlement="0", contract_size="100", special_settlement="", exercise_style="E"),
    ]
    if mutate:
        mutate(rows)
    with (tmp_path / "source.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    digest = hashlib.sha256((tmp_path / "source.csv").read_bytes()).hexdigest()
    receipt = {
        "source": "OptionMetrics export", "version": "manual v5.0", "provenance_reference": "receipt ref",
        "license_scope": "internal research", "file_sha256": digest,
        "security_ids": {"SPY": "11", "SPX": "22"}, "underlyings": {"SPY": "SPY", "SPX": "SPX"},
        "units_confirmed": True, "unit_reference": "exchange spec reference",
        "multiplier_confirmed": {"SPY": 100, "SPX": 100}, "multiplier_reference": "exchange spec reference",
        "requested_start_date": "2026-10-19", "requested_end_date": "2026-10-20",
        "export_filters": {"dates": "requested range", "roots": ["SPY", "SPX", "SPXW"]},
        "export_universe": {"security_ids": ["11", "22"]},
        "exercise_join_reference": "extractor log ref", "exercise_join_cardinality": "many-to-one",
        "extractor_attestation": "extractor attests verified many-to-one join",
        "underlying_join_reference": "verified underlying join reference", "underlying_join_cardinality": "many-to-one",
    }
    (tmp_path / "receipt.json").write_text(json.dumps(receipt))
    return dict(zip(ROLES, [tmp_path / n for n in ("source.csv", "mapping.json", "receipt.json", "calendar.txt")]))


def test_mixed_broad_export_admits_targets_and_counts_expected_exclusions(tmp_path):
    def add_rows(rows):
        rows.extend([
            dict(rows[1], option_id="am", symbol="SPX261020C07000000", am_settlement="1"),
            dict(rows[0], option_id="put", symbol="SPY261020P00700000", cp_flag="P"),
            dict(rows[0], option_id="dte", expiry_date="2026-10-20", quote_date="2026-10-19", symbol="SPY261020C00700000"),
            dict(rows[1], option_id="illiquid", symbol="SPXW261020C07001000", strike_milli="7001000", best_bid="NaN"),
        ])
        rows[-2]["expiry_date"] = "2026-10-21"  # OSI agrees; quote date makes it a non-target DTE below
        rows[-2]["symbol"] = "SPY261021C00710000"
        rows[-2]["strike_milli"] = "710000"
    paths = fixture(tmp_path, add_rows)
    result = audit(paths)
    assert result["status"] == "ADMISSION_ONLY"
    assert len(result["accepted"]) == 2
    assert result["observed_dates"] == ["2026-10-19"]
    assert result["reason_counts"]["consistent AM SPX excluded; PM SPXW only"] == 1
    assert result["reason_counts"]["consistent put excluded; calls only"] == 1
    assert result["reason_counts"]["unusable BBO excluded; bid and offer must be finite, positive, and uncrossed"] == 1
    assert result["reason_counts"]["other DTE excluded; expiry must be quote date plus one calendar day"] == 1


@pytest.mark.parametrize(("mutate", "reason"), [
    (lambda r: r[0].update(symbol_flag=""), "symbol_flag"),
    (lambda r: r[0].update(symbol_flag="9"), "symbol_flag"),
    (lambda r: r[0].update(symbol="SPXW261020C00700000"), "root contradicts"),
    (lambda r: r[0].update(cp_flag="P"), "cp_flag conflicts"),
    (lambda r: r[0].update(symbol="SPY261021C00700000"), "expiry_date conflicts"),
    (lambda r: r[0].update(strike_milli="700001"), "strike_milli conflicts"),
    (lambda r: r[0].update(quote_date="2026-10-18"), "quote_date is not"),
])
def test_structural_conflicts_block(mutate, reason, tmp_path):
    result = audit(fixture(tmp_path, mutate))
    assert result["status"] == "BLOCKED"
    assert any(reason in failure for failure in result["hard_failures"])


@pytest.mark.parametrize(("field", "value"), [
    ("am_settlement", "?"), ("exercise_style", "?"),
])
def test_ambiguous_settlement_or_style_blocks(field, value, tmp_path):
    result = audit(fixture(tmp_path, lambda rows: rows[0].update({field: value})))
    assert result["status"] == "BLOCKED"


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("contract_size", "10", "nonstandard contract_size excluded"),
    ("special_settlement", "1", "special settlement excluded"),
    ("best_bid", "NaN", "unusable BBO excluded"), ("best_bid", "inf", "unusable BBO excluded"),
    ("best_bid", "0", "unusable BBO excluded"), ("best_offer", "0.9", "unusable BBO excluded"),
    ("best_bid", "-1", "unusable BBO excluded"), ("best_bid", "2.0", "unusable BBO excluded"),
])
def test_known_nonstandard_or_unusable_rows_are_excluded(field, value, reason, tmp_path):
    result = audit(fixture(tmp_path, lambda rows: rows[0].update({field: value})))
    assert result["status"] == "BLOCKED"  # second root alone cannot satisfy admitted-root requirement
    assert any(reason in item["reasons"] for item in result["rejected"])
    assert len(result["accepted"]) <= 1


def test_consistent_spx_am_is_excluded_but_spxw_am_is_conflict(tmp_path):
    def change(rows):
        rows[1].update(symbol="SPX261020C07000000", am_settlement="1")
    result = audit(fixture(tmp_path, change))
    assert any("consistent AM SPX excluded" in r["reasons"] for r in result["rejected"])
    assert any("accepted rows must contain both" in x for x in result["hard_failures"])
    (tmp_path / "sub").mkdir()
    paths = fixture(tmp_path / "sub", lambda rows: rows[1].update(am_settlement="1"))
    result = audit(paths)
    assert any("SPXW contradicts AMSettlement" in x for x in result["hard_failures"])


def test_receipt_ids_are_exact_distinct_positive_normalized_and_container_checked(tmp_path):
    for ids in ({"SPY": "11", "SPX": "11"}, {"SPY": "0", "SPX": "22"}, {"SPY": "11", "SPX": "22", "X": "33"}, {"SPY": "11"}, []):
        paths = fixture(tmp_path)
        receipt = json.loads(paths["receipt"].read_text()); receipt["security_ids"] = ids
        paths["receipt"].write_text(json.dumps(receipt))
        with pytest.raises(ValueError, match="security_ids|distinct"):
            audit(paths)


def test_mapping_alias_duplicate_header_and_wrong_cell_count_reject(tmp_path):
    paths = fixture(tmp_path)
    mapping = json.loads(paths["mapping"].read_text()); mapping["best_offer"] = mapping["best_bid"]
    paths["mapping"].write_text(json.dumps(mapping))
    with pytest.raises(ValueError, match="distinct"):
        audit(paths)
    paths = fixture(tmp_path)
    paths["csv"].write_text(paths["csv"].read_text().replace("option_id,quote_date", "option_id,option_id,quote_date", 1))
    receipt = json.loads(paths["receipt"].read_text()); receipt["file_sha256"] = hashlib.sha256(paths["csv"].read_bytes()).hexdigest(); paths["receipt"].write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="duplicate header"):
        audit(paths)
    paths = fixture(tmp_path)
    with paths["csv"].open("a") as f: f.write("too,many,cells\n")
    receipt = json.loads(paths["receipt"].read_text()); receipt["file_sha256"] = hashlib.sha256(paths["csv"].read_bytes()).hexdigest(); paths["receipt"].write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="cells"):
        audit(paths)


def test_mapping_missing_or_surplus_canonical_fields_reject(tmp_path):
    for change in (lambda m: m.pop("symbol"), lambda m: m.update(unrequested="extra")):
        paths = fixture(tmp_path)
        mapping = json.loads(paths["mapping"].read_text()); change(mapping); paths["mapping"].write_text(json.dumps(mapping))
        with pytest.raises(ValueError, match="exactly"):
            audit(paths)


def test_semantic_duplicate_blocks_even_with_different_option_ids_and_osi_padding(tmp_path):
    def duplicate(rows):
        row = dict(rows[0]); row["option_id"] = "different-id"; row["symbol"] = "SPY   261020C00700000"; rows.append(row)
    result = audit(fixture(tmp_path, duplicate))
    assert any("duplicate option id/date or duplicate economic" in x for x in result["hard_failures"])


def test_duplicate_option_id_with_normalized_date_blocks(tmp_path):
    def duplicate(rows):
        row = dict(rows[0]); row["quote_date"] = "2026-10-19"; rows.append(row)
    result = audit(fixture(tmp_path, duplicate))
    assert any("duplicate option id/date" in x for x in result["hard_failures"])


def test_receipt_metadata_range_and_join_are_required(tmp_path):
    paths = fixture(tmp_path)
    receipt = json.loads(paths["receipt"].read_text()); receipt["extractor_attestation"] = "TBD"; paths["receipt"].write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="placeholder metadata"):
        audit(paths)
    paths = fixture(tmp_path, lambda rows: rows[0].update(quote_date="2026-10-21"))
    paths["calendar"].write_text("2026-10-19\n2026-10-20\n2026-10-21\n")
    receipt = json.loads(paths["receipt"].read_text()); receipt["file_sha256"] = hashlib.sha256(paths["csv"].read_bytes()).hexdigest(); paths["receipt"].write_text(json.dumps(receipt))
    result = audit(paths)
    assert any("outside receipt requested date range" in x for x in result["hard_failures"])
    paths = fixture(tmp_path)
    receipt = json.loads(paths["receipt"].read_text()); receipt["underlying_join_cardinality"] = "many-to-many"; paths["receipt"].write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="many-to-one"):
        audit(paths)


def test_weekend_expiry_is_excluded_without_monday_roll(tmp_path):
    def set_weekend(rows):
        rows[0].update(quote_date="2026-10-23", expiry_date="2026-10-24", symbol="SPY261024C00700000")
        rows.append(dict(rows[0], quote_date="2026-10-19", expiry_date="2026-10-20", symbol="SPY261020C00710000", strike_milli="710000", option_id="valid-spy"))
    paths = fixture(tmp_path, set_weekend)
    paths["calendar"].write_text("2026-10-19\n2026-10-20\n2026-10-23\n2026-10-26\n")
    receipt = json.loads(paths["receipt"].read_text()); receipt["requested_end_date"] = "2026-10-26"; receipt["file_sha256"] = hashlib.sha256(paths["csv"].read_bytes()).hexdigest(); paths["receipt"].write_text(json.dumps(receipt))
    result = audit(paths)
    assert result["status"] == "ADMISSION_ONLY"
    assert any("expiry is not an explicit calendar session" in r["reasons"] for r in result["rejected"])


def test_cli_writes_role_keyed_records_and_never_overwrites(tmp_path):
    paths = fixture(tmp_path)
    repo = Path(__file__).resolve().parents[1]
    out = repo / "planning" / "optionmetrics-20261029" / ("review-unit-" + tmp_path.name)
    args = ["--csv", str(paths["csv"]), "--mapping", str(paths["mapping"]), "--receipt", str(paths["receipt"]), "--calendar", str(paths["calendar"]), "--out", str(out)]
    try:
        assert main(args) == 0
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest["historical_evaluation"] == "NOT RUN"
        assert set(manifest["inputs"]) == set(ROLES)
        assert all({"path", "bytes", "sha256"} <= set(v) for v in manifest["inputs"].values())
        assert manifest["total_observed_dates"] == 1
        assert manifest["source_metadata"]["provenance_reference"] == "receipt ref"
        assert (out / "accepted.csv").exists()
        assert main(args) == 4
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)


def test_role_keyed_manifest_preserves_colliding_input_basenames(tmp_path):
    paths = fixture(tmp_path)
    d1, d2 = tmp_path / "one", tmp_path / "two"; d1.mkdir(); d2.mkdir()
    (d1 / "shared.json").write_bytes(paths["mapping"].read_bytes())
    (d2 / "shared.json").write_bytes(paths["receipt"].read_bytes())
    paths["mapping"], paths["receipt"] = d1 / "shared.json", d2 / "shared.json"
    repo = Path(__file__).resolve().parents[1]
    out = repo / "planning" / "optionmetrics-20261029" / ("colliding-inputs-" + tmp_path.name)
    args = ["--csv", str(paths["csv"]), "--mapping", str(paths["mapping"]), "--receipt", str(paths["receipt"]), "--calendar", str(paths["calendar"]), "--out", str(out)]
    try:
        assert main(args) == 0
        records = json.loads((out / "manifest.json").read_text())["inputs"]
        assert records["mapping"]["path"] != records["receipt"]["path"]
        assert records["mapping"]["sha256"] != records["receipt"]["sha256"]
    finally:
        import shutil
        shutil.rmtree(out, ignore_errors=True)


def test_mutation_after_parse_prevents_publication_and_accepted_rows(tmp_path, monkeypatch):
    paths = fixture(tmp_path)
    out = Path(__file__).resolve().parents[1] / "planning" / "optionmetrics-20261029" / ("mutated-" + tmp_path.name)
    real_audit = admission.audit
    def changing_audit(p, before):
        result = real_audit(p, before)
        p["csv"].write_text(p["csv"].read_text() + "\n")
        return result
    monkeypatch.setattr(admission, "audit", changing_audit)
    args = ["--csv", str(paths["csv"]), "--mapping", str(paths["mapping"]), "--receipt", str(paths["receipt"]), "--calendar", str(paths["calendar"]), "--out", str(out)]
    assert main(args) == 3
    assert not out.exists()


def test_mutation_immediately_before_publish_prevents_bundle(tmp_path, monkeypatch):
    paths = fixture(tmp_path)
    out = Path(__file__).resolve().parents[1] / "planning" / "optionmetrics-20261029" / ("late-mutated-" + tmp_path.name)
    real_check = admission.snapshots_unchanged
    calls = 0
    def mutate_on_second_check(before):
        nonlocal calls
        calls += 1
        if calls == 2:
            Path(before["mapping"]["path"]).write_text(Path(before["mapping"]["path"]).read_text() + " ")
        return real_check(before)
    monkeypatch.setattr(admission, "snapshots_unchanged", mutate_on_second_check)
    args = ["--csv", str(paths["csv"]), "--mapping", str(paths["mapping"]), "--receipt", str(paths["receipt"]), "--calendar", str(paths["calendar"]), "--out", str(out)]
    assert main(args) == 3
    assert not out.exists()


def test_ignore_rules_and_symlink_escape_in_isolated_git_repo(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("planning/*\n")
    (repo / "planning").mkdir()
    assert admission._validate_output(repo / "planning" / "new", repo) == repo / "planning" / "new"
    (repo / ".gitignore").write_text("planning/*\n!planning/new\n")
    with pytest.raises(ValueError, match="not ignored"):
        admission._validate_output(repo / "planning" / "new", repo)
    outside = tmp_path / "outside"; outside.mkdir()
    (repo / "planning" / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="inside this repo"):
        admission._validate_output(repo / "planning" / "escape" / "new", repo)


def test_output_escape_rejected(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="inside this repo"):
        admission._validate_output(tmp_path / "escape", repo)
