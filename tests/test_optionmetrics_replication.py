"""Synthetic fixtures for the bounded OptionMetrics replication adapter."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

import spyspx.optionmetrics_replication as replication


def csv_bytes(headers, rows):
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode()


def pair(entry="2024-12-30", expiry="2024-12-31", cover="2025-01-02"):
    return {"entry": date.fromisoformat(entry), "expiry": date.fromisoformat(expiry), "cover": date.fromisoformat(cover)}


def normalized_row(family="SPY", strike=100000, bid="2", ask="3", expiry="2019-08-07", quote="2019-08-06", optionid="synthetic-spy"):
    root = "SPY" if family == "SPY" else "SPXW"
    return {"normalized_security_id": "70001" if family == "SPY" else "80002", "normalized_option_id": optionid,
            "normalized_quote_date": quote, "normalized_symbol": f"{root}{expiry[2:4]}{expiry[5:7]}{expiry[8:10]}C{strike:08d}",
            "normalized_expiry_date": expiry, "normalized_cp_flag": "C", "normalized_strike_milli": str(strike),
            "normalized_best_bid": bid, "normalized_best_offer": ask, "normalized_am_settlement": "0",
            "normalized_contract_size": "100", "normalized_special_settlement": "", "normalized_exercise_style": "A" if family == "SPY" else "E",
            "normalized_underlying": family, "symbol": f"{root} {expiry[2:4]}{expiry[5:7]}{expiry[8:10]}C{strike}", "ss_flag": "0"}


def price_csv(rows):
    headers = ["secid", "date", "ticker", "index_flag", "open", "close", "cfadj"]
    return csv_bytes(headers, rows)


def dividend_csv(rows):
    headers = ["secid", "record_date", "ticker", "index_flag", "seq_num", "ex_date", "amount", "adj_factor", "distr_type", "frequency", "currency", "approx_flag", "cancel_flag", "liquid_flag"]
    return csv_bytes(headers, rows)


def action(ex_date="2019-08-08", **overrides):
    return {"secid": "109820", "record_date": "2019-08-01", "ticker": "SPY", "index_flag": "0", "seq_num": "1", "ex_date": ex_date,
            "amount": "0.25", "adj_factor": "1", "distr_type": "1", "frequency": "3", "currency": "USD",
            "approx_flag": "0", "cancel_flag": "0", "liquid_flag": "0", **overrides}


def test_frozen_manifest_hash_and_file_size_are_bound(tmp_path):
    p = tmp_path / "input.bin"; p.write_bytes(b"synthetic")
    manifest = {"files": {"fixture": {"path": str(p), "bytes": 9, "sha256": hashlib.sha256(b"synthetic").hexdigest()}}}
    assert replication._frozen_files(tmp_path, manifest)["fixture"]["sha256"] == manifest["files"]["fixture"]["sha256"]
    manifest["files"]["fixture"]["bytes"] = 10
    with pytest.raises(ValueError, match="integrity mismatch"):
        replication._frozen_files(tmp_path, manifest)


def test_projection_control_requires_unique_keys_and_exact_common_values():
    headers = list(replication.OPTION_COMMON) + ["ticker"]
    row = {field: f"v-{i}" for i, field in enumerate(headers)}
    control = {key: value for key, value in row.items() if key != "ticker"}
    left = csv_bytes(headers, [row])
    right = csv_bytes(list(control), [control])
    result = replication._projection_check(left, right, False)
    assert result["projection_consistent"] and result["common_fields"] == 29
    control["best_bid"] = "changed"
    result = replication._projection_check(left, csv_bytes(list(control), [control]), False)
    assert not result["projection_consistent"] and result["field_mismatch_counts"] == {"best_bid": 1}
    with pytest.raises(ValueError, match="duplicate projection key"):
        replication._projection_check(left, csv_bytes(list(control), [control, control]), False)


def test_projection_control_checks_gzip_representation():
    headers = list(replication.OPTION_COMMON) + ["ticker"]
    row = {field: f"v-{i}" for i, field in enumerate(headers)}
    plain = csv_bytes(headers, [row])
    control = csv_bytes(headers[:-1], [{k: v for k, v in row.items() if k != "ticker"}])
    result = replication._projection_check(gzip.compress(plain, mtime=0), gzip.compress(control, mtime=0), True)
    assert result["projection_consistent"]


def test_expected_calendar_keeps_year_boundary_and_rejects_off_calendar_expiry():
    sessions = {date.fromisoformat(x) for x in ("2024-12-30", "2024-12-31", "2025-01-02")}
    period = {"expected_count": 1, "expected_pairs": [{"entry": "2024-12-30", "expiry": "2024-12-31", "cover": "2025-01-02"}]}
    assert replication._validate_expected_pairs(period, sessions) == [pair()]
    bad = {"expected_count": 1, "expected_pairs": [{"entry": "2024-12-30", "expiry": "2025-01-01", "cover": "2025-01-02"}]}
    with pytest.raises(ValueError, match="invalid against"):
        replication._validate_expected_pairs(bad, sessions)


@pytest.mark.parametrize("badrow", [
    {"secid": "108105", "date": "2024-12-30", "ticker": "SPY", "index_flag": "0", "open": "10", "close": "10", "cfadj": "1"},
    {"secid": "109820", "date": "2024-12-30", "ticker": "SPY", "index_flag": "0", "open": "0", "close": "10", "cfadj": "1"},
    {"secid": "109820", "date": "2024-12-30", "ticker": "SPY", "index_flag": "0", "open": "10", "close": "-10", "cfadj": "1"},
    {"secid": "109820", "date": "2024-12-30", "ticker": "SPY", "index_flag": "0", "open": "10", "close": "10", "cfadj": "nan"},
])
def test_price_source_rejects_identity_and_price_sentinels(badrow):
    with pytest.raises(ValueError):
        replication._read_prices(price_csv([badrow]))


def test_price_source_rejects_duplicate_security_date():
    row = {"secid": "109820", "date": "2024-12-30", "ticker": "SPY", "index_flag": "0", "open": "10", "close": "10", "cfadj": "1"}
    with pytest.raises(ValueError, match="duplicate"):
        replication._read_prices(price_csv([row, row]))


def _cboe_record(value, expiry="2024-12-31", trading="SPXW", settlement="SPX"):
    return {"trading_symbol": trading, "settlement_symbol": settlement, "expiration_date": expiry, "settlement_value": value}


def test_cboe_pm_requires_exact_spxw_spx_and_allows_identical_duplicates(tmp_path):
    a = {"path": str(tmp_path / "cboe_W_2024.json"), "data": json.dumps({"data": [_cboe_record(4000)]}).encode()}
    b = {"path": str(tmp_path / "cboe_M_2024.json"), "data": json.dumps({"data": [_cboe_record(4000), _cboe_record(1, trading="SPX", settlement="SPX")]}).encode()}
    c = {"path": str(tmp_path / "cboe_S_2024.json"), "data": json.dumps({"data": []}).encode()}
    result, diag = replication._read_pm_sources({"cboe_W_2024.json": a, "cboe_M_2024.json": b, "cboe_S_2024.json": c}, "primary_2024")
    assert result[date(2024, 12, 31)]["value"] == 4000
    assert result[date(2024, 12, 31)]["sources"] == ["cboe_W_2024.json", "cboe_M_2024.json"]
    assert diag["conflicting_expiries"] == 0


def test_cboe_pm_conflicting_values_block_that_expiry(tmp_path):
    records = {}
    for suffix, value in (("W", 4000), ("M", 4001), ("S", 4000)):
        records[f"cboe_{suffix}_2024.json"] = {"data": json.dumps({"data": [_cboe_record(value)]}).encode()}
    result, diag = replication._read_pm_sources(records, "primary_2024")
    assert date(2024, 12, 31) not in result
    assert diag["conflicting_expiries"] == 1


def test_distribution_classification_and_duplicate_keys():
    parsed, summary = replication._read_distributions(dividend_csv([action()]))
    assert parsed[0]["distr_type"] == "1" and summary["coverage"] == ["2019-08-01", "2025-08-29"]
    bad = action(distr_type="%")
    parsed, _ = replication._read_distributions(dividend_csv([bad]))
    assert parsed[0]["distr_type"] == "%"  # caller must reject projected distribution type
    with pytest.raises(ValueError, match="duplicate"):
        replication._read_distributions(dividend_csv([action(), action()]))


def test_entry_selection_ties_and_bbo_exclusions_are_deterministic():
    spy_a = normalized_row(strike=101000, bid="1", ask="2", optionid="a")
    spy_b = normalized_row(strike=99000, bid="1", ask="2", optionid="b")
    idx = normalized_row("SPX", strike=3960000, bid="20", ask="21")
    invalid = normalized_row(strike=100000, bid="0", ask="1", optionid="bad")
    selected, diag = replication.select_pairs([spy_b, spy_a, idx, invalid], [pair("2019-08-06", "2019-08-07", "2019-08-08")],
        {("109820", date(2019, 8, 6)): {"close": 100.0}}, {date(2019, 8, 6): 4000.0})
    assert selected[0]["spy"]["normalized_option_id"] == "b"
    assert selected[0]["spxw"]["normalized_underlying"] == "SPX"
    assert diag["eligibility_exclusion_counts"]["unusable_bbo"] == 1


def _selected_pair():
    spy = normalized_row(strike=100000, bid="2", ask="3")
    idx = normalized_row("SPX", strike=4000000, bid="20", ask="21", optionid="synthetic-spx")
    return {"entry": "2019-08-06", "expiry": "2019-08-07", "cover": "2019-08-08", "spy": spy, "spxw": idx,
            "spy_entry_close": 100.0, "official_spx_entry_close": 4000.0, "moneyness_mismatch": 0.0}


def test_cash_signs_threshold_decomposition_carry_and_cost_durations():
    selected = _selected_pair()
    events = [{"ex_date": date(2019, 8, 7), "amount": .25}, {"ex_date": date(2019, 8, 8), "amount": .5}]
    fills, controls = replication.build_fill_rows(selected, {"spy_expiry_close": 100.01, "spy_cover_open": 100.20, "spxw_pm_settlement": 4000.0}, events)
    full = fills[-1]
    assert full["spy_entry_cash"] > 0 and full["spxw_entry_cash"] < 0
    assert full["assigned"] is True and full["spy_leg_expiry_shares"] == -1000
    assert full["calendar_days_entry_to_exit"] == 2 and full["calendar_days_expiry_to_cover"] == 1
    assert full["entry_exposure_dividend_dates"] == ["2019-08-07"]
    assert full["dividend_carry_dates"] == ["2019-08-08"]
    assert full["decomposition_residual"] == pytest.approx(0, abs=5e-12)
    assert full["stock_neutralized_pnl"] + full["stock_overnight_attribution"] == pytest.approx(full["next_open_pnl"])
    assert controls["reverse_full_cross_credit"] == pytest.approx(100 * 20 - 1000 * 3)
    assert controls["no_trade_zero_control_pnl"] == 0 and controls["reverse_physical_next_open_ledger"] == "NOT_DEFINED_BY_PROTOCOL"
    fills, _ = replication.build_fill_rows(selected, {"spy_expiry_close": 100.009, "spy_cover_open": 100.20, "spxw_pm_settlement": 4000.0}, events)
    assert fills[-1]["assigned"] is False
    assert fills[-1]["calendar_days_entry_to_exit"] == 1 and fills[-1]["calendar_days_expiry_to_cover"] == 0


def test_reverse_closemark_uses_both_terminal_legs_and_primary_subcent_threshold():
    _, controls = replication.build_fill_rows(_selected_pair(),
        {"spy_expiry_close": 100.005, "spy_cover_open": 100.20, "spxw_pm_settlement": 4001.0}, [])
    assert controls["primary_assignment_threshold_applied"] is False
    assert controls["reverse_spy_closemark_cash"] == 0
    assert controls["reverse_spxw_closemark_cash"] == -100
    assert controls["primary_threshold_residual_cash"] == pytest.approx(5.0)
    assert controls["reverse_closemark_control_pnl"] == pytest.approx(
        controls["reverse_intrinsic_control_pnl"] - 5.0)


def test_missing_terminal_references_keeps_denominator_and_no_outcome():
    expected = [pair("2024-12-30", "2024-12-31", "2025-01-02")]
    coverage, outcomes = replication._evaluation_rows([], expected, {}, {}, {}, [])
    assert len(coverage) == 1 and not coverage[0]["complete"]
    assert outcomes == [] and "selected_pair" in coverage[0]["missing_inputs"]
    with pytest.raises(ValueError, match="only a complete successful run"):
        replication.publish_run(Path("."), Path("."), "PREPARED_COVERAGE_BLOCKED", {}, {}, [], Path(__file__))


def test_relevant_unknown_distribution_blocks_coverage_without_fallback():
    expected = [pair("2019-08-06", "2019-08-07", "2019-08-08")]
    prices = {
        ("109820", date(2019, 8, 6)): {"close": 100.0, "open": 99.0, "cfadj": 1.0},
        ("109820", date(2019, 8, 7)): {"close": 100.0, "open": 100.0, "cfadj": 1.0},
        # The frozen cover day is absent. A later source date must not replace it.
        ("109820", date(2019, 8, 9)): {"close": 101.0, "open": 100.5, "cfadj": 1.0},
    }
    invalid_action = {"ex_date": date(2019, 8, 8), "amount": None, "adj_factor": 1.0, "distr_type": "%", "frequency": "3", "currency": "USD", "approx_flag": "0", "cancel_flag": "0", "liquid_flag": "0"}
    coverage, outcomes = replication._evaluation_rows([_selected_pair()], expected, prices, {date(2019, 8, 6): 4000, date(2019, 8, 7): 4000},
        {date(2019, 8, 7): {"value": 4000}}, [invalid_action], {date(2019, 8, 6), date(2019, 8, 7), date(2019, 8, 8), date(2019, 8, 9)})
    assert not coverage[0]["complete"]
    assert "spy_cover_price" in coverage[0]["missing_inputs"]
    assert "unsupported_distribution_event" in coverage[0]["missing_inputs"]
    assert outcomes == []


def test_run_persists_selected_snapshot_before_terminal_reference_join(tmp_path, monkeypatch):
    events = []
    expected = [pair("2019-08-06", "2019-08-07", "2019-08-08")]
    normalized = [normalized_row(), normalized_row("SPX", strike=4000000, bid="20", ask="21", optionid="idx")]
    prices = {("109820", date(2019, 8, 6)): {"close": 100.0, "open": 100.0, "cfadj": 1.0}}
    monkeypatch.setattr(replication, "_source_audit", lambda *a, **k: {"status": "SOURCE_AUDIT_ONLY"})
    monkeypatch.setattr(replication.normalizer, "normalize", lambda *_: {"normalized_rows": normalized, "status": "NORMALIZATION_ONLY"})
    monkeypatch.setattr(replication, "_read_prices", lambda *_: (prices, {}))
    monkeypatch.setattr(replication, "_read_calendar", lambda *_: ({d for d in (date(2019, 8, 6), date(2019, 8, 7), date(2019, 8, 8))}, {date(2019, 8, 6): 4000.0}))
    monkeypatch.setattr(replication, "_validate_expected_pairs", lambda *_: expected)
    monkeypatch.setattr(replication, "_read_pm_sources", lambda *_: (events.append("terminal") or ({}, {})))
    monkeypatch.setattr(replication, "_read_distributions", lambda *_: (events.append("actions") or [], {}))
    monkeypatch.setattr(replication, "_evaluation_rows", lambda *_: (events.append("join") or ([{"complete": False}], [])))
    inputs = {}
    for role, content in (("protocol", b"p"), ("input_manifest", b"m"), ("source_metadata", b"s"), ("identity_metadata", b"i")):
        path = tmp_path / role; path.write_bytes(content)
        inputs[role] = {"path": str(path), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "data": content}
    records = {role: {"path": str(tmp_path / role), "bytes": 0, "sha256": "0", "data": b""}
               for role in ("pilot_quotes", "security-prices-20190801-20250829.csv", "official_spx_calendar",
                            "distributions-20190801-20250829.csv")}
    status, result = replication.run_period(Path(__file__).resolve().parents[1], "pilot", {"periods": {"pilot": {}}}, records, inputs,
        ["synthetic"], Path(replication.__file__), tmp_path / "selected.json", tmp_path / "unused-run")
    assert status == "PREPARED_COVERAGE_BLOCKED"
    assert (tmp_path / "selected.json").is_file()
    assert events == ["terminal", "actions", "join"]
    assert result["historical_evaluation"] == "NOT RUN"


def test_atomic_selection_snapshot_refuses_changed_inputs(tmp_path):
    raw = tmp_path / "snapshot.json"; raw.write_text("before")
    inputs = {"x": {"path": str(raw), "bytes": 6, "sha256": hashlib.sha256(b"before").hexdigest()}}
    raw.write_text("after!")
    out = tmp_path / "out.json"
    with pytest.raises(ValueError, match="changed"):
        replication._atomic_json(out, {"historical_evaluation": "NOT RUN"}, inputs)
    assert not out.exists()


def test_run_identity_rejects_clean_head_change(tmp_path, monkeypatch):
    monkeypatch.setattr(replication, "_git_clean", lambda _repo: ("new-clean-head", True))
    with pytest.raises(ValueError, match="HEAD or clean state changed"):
        replication._check_run_identity(tmp_path, {"initial_head": "initial-head", "code": {}})


def test_run_identity_rejects_code_mutation_against_initial_blob(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    relative = "src/spyspx/expiry_payoff.py"
    source = (repo / relative).read_bytes()
    mutated = tmp_path / "expiry_payoff.py"
    mutated.write_bytes(source + b"# changed after initial load\n")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.setattr(replication, "_git_clean", lambda _repo: (head, True))
    identity = {"initial_head": head, "code": {"code_expiry_payoff": {
        "path": str(mutated), "relative_path": relative, "bytes": len(source),
        "sha256": hashlib.sha256(source).hexdigest(), "data": source}}}
    with pytest.raises(ValueError, match="code changed during run"):
        replication._check_run_identity(repo, identity)


def test_run_identity_rejects_selection_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(replication, "_git_clean", lambda _repo: ("same-head", True))
    selected = tmp_path / "selected.json"
    selected.write_text("original")
    expected_hash = hashlib.sha256(b"original").hexdigest()
    selected.write_text("mutated!")
    with pytest.raises(ValueError, match="selected snapshot changed"):
        replication._check_run_identity(tmp_path, {"initial_head": "same-head", "code": {}},
                                        selection_path=selected, selection_hash=expected_hash)


def test_success_manifest_binds_source_audit_selection_outputs_and_integrity(tmp_path, monkeypatch):
    target = tmp_path / "run-output"
    selected = tmp_path / "selected.json"
    selected.write_text("selection")
    selection_hash = hashlib.sha256(b"selection").hexdigest()
    monkeypatch.setattr(replication, "_output_path", lambda _repo, _out, _base: target)
    monkeypatch.setattr(replication, "_check_run_identity", lambda _repo, identity, _inputs, selection_path=None, selection_hash=None: {
        "verified": True, "head": identity["initial_head"], "clean": True, "code_sha256": {}, "inputs_verified": True,
        "selection_sha256": selection_hash})
    payload = {"status": "SOURCE_METHOD_PILOT_THEORETICAL_EVALUATED", "historical_evaluation": "RAN", "period": "pilot",
        "run_started_utc": "start", "coverage": [], "outcomes": [], "summary": {}, "source_audit": {"status": "SOURCE_AUDIT_ONLY"},
        "selection_snapshot": {"path": str(selected), "bytes": selected.stat().st_size, "sha256": selection_hash},
        "period_classification": "Previously studied source-method pilot.", "integrity_checks": {"before_calculation": {"verified": True}},
        "integrity_before": {}, "historical_evaluation_limitations": []}
    identity = {"initial_head": "initial-head", "code": {}}
    inputs = {role: {"path": str(tmp_path / role), "bytes": 1, "sha256": role, "data": b"x"}
              for role in ("protocol", "input_manifest")}
    result = replication.publish_run(tmp_path, target, "EVALUATED", payload, inputs, ["synthetic"], Path(__file__), identity)
    manifest = json.loads((target / "manifest.json").read_text())
    assert (target / "source_audit.json").is_file()
    assert manifest["selection_snapshot"]["sha256"] == selection_hash
    assert set(manifest["output_sha256"]) == {"source_audit.json", "coverage.csv", "outcomes.json", "summary.json"}
    assert all(check["verified"] for check in manifest["integrity_checks"].values())
    assert result["output_sha256"]["manifest.json"] == hashlib.sha256((target / "manifest.json").read_bytes()).hexdigest()


def test_run_cli_refuses_dirty_repo_before_frozen_input_read(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(replication, "_git_clean", lambda repo: ("synthetic-sha", False))
    monkeypatch.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(AssertionError("read before clean gate")))
    code = replication.main(["run", "--period", "primary_2024", "--out", "runs/optionmetrics_replication/synthetic"])
    assert code == 3
    assert "clean Git worktree" in capsys.readouterr().err


def test_runs_output_path_must_be_ignored_and_inside_repo(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("runs/\n")
    (repo / "runs").mkdir()
    (repo / "runs/optionmetrics_replication").mkdir()
    assert replication._output_path(repo, repo / "runs/optionmetrics_replication/a", "runs") == repo / "runs/optionmetrics_replication/a"
    (repo / ".gitignore").write_text("runs/optionmetrics_replication/*\n!runs/optionmetrics_replication/a\n")
    with pytest.raises(ValueError, match="not ignored"):
        replication._output_path(repo, repo / "runs/optionmetrics_replication/a", "runs")
    outside = tmp_path / "outside"; outside.mkdir()
    (repo / "runs/optionmetrics_replication/escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="inside ignored"):
        replication._output_path(repo, repo / "runs/optionmetrics_replication/escape/out", "runs")


def test_aggregation_reports_cohorts_and_shared_week_bootstrap():
    fills = []
    for fill, value in (("midpoint", 1.0), ("halfway", 2.0), ("full_cross", 3.0)):
        fills.append({"fill": fill, **{k: value for k in ("direct_intrinsic_pnl", "threshold_residual_cash", "dividend_carry_amount", "dividend_carry_pnl", "base_cost_pnl", "stress_cost_pnl", "stock_neutralized_pnl", "stock_overnight_attribution", "decomposition_residual", "conditional_close_mark_pnl")}})
    row = {"status": "COMPLETE_THEORETICAL_ROW", "entry": "2024-01-02", "expiry": "2024-01-03", "fill_rows": fills,
           "controls": {"reverse_intrinsic_control_pnl": -1.0, "reverse_closemark_control_pnl": -1.0, "no_trade_zero_control_pnl": 0}}
    result = replication.aggregate([row], "primary_2024", draws=25)
    assert result["cohorts"]["all"]["fills"]["full_cross"]["direct_intrinsic_pnl"]["total"] == 3.0
    assert "2024-01" in result["cohorts"]
    assert result["full_cross_iso_week_cluster_bootstrap"]["direct_intrinsic_pnl"]["draws"] == 25


def test_evaluation_status_distinguishes_pilot_from_new_option_price_periods():
    pilot_status, pilot = replication._period_classification("pilot")
    new_status, new = replication._period_classification("primary_2024")
    assert pilot_status == "SOURCE_METHOD_PILOT_THEORETICAL_EVALUATED"
    assert pilot["previously_studied"] and not pilot["independent_period"]
    assert new_status == "NEW_OPTION_PRICE_PERIOD_THEORETICAL_EVALUATED"
    assert new["prior_stock_data_and_other_strategy_outcomes_inspected"]
    assert not new["predictive_holdout"] and not new["globally_untouched"]
