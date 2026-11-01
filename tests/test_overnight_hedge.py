from __future__ import annotations

import pytest
import random
import hashlib
import json

import spyspx.overnight_hedge as hedge
from spyspx.overnight_hedge import (
    bootstrap_indices,
    bootstrap_cluster_intervals,
    hedge_row,
    max_peak_to_trough_drawdown,
    normalize_optionmetrics,
    paired_mean_interval,
    q_for_arm,
    verify_retained_summary_means,
    verify_q0_parity,
    verify_row_identities,
)


def sample(**changes):
    row = {
        "credit": 100.0,
        "spxw_terminal_cash": 25.0,
        "assigned": False,
        "spy_strike": 100.0,
        "spy_open": 100.5,
        "spy_close": 101.0,
        "cover_open": 102.0,
        "dividend_amount": 0.5,
        "days_entry_expiry": 1,
        "days_entry_cover": 4,
        "days_expiry_cover": 3,
    }
    row.update(changes)
    return row


def test_unassigned_long_hedge_receives_unconditional_dividend():
    result = hedge_row(sample(), "fixed500longshares")
    ex_dividend = hedge_row(sample(), "fixed500longshares", include_dividends=False)
    assert result["gross_pnl"] == pytest.approx(100 + 25 + 500 * (102 - 101 + .5))
    assert ex_dividend["gross_pnl"] == pytest.approx(result["gross_pnl"] - 250)
    assert ex_dividend["gross_pnl_with_dividends"] == pytest.approx(result["gross_pnl"])
    q0 = hedge_row(sample(), "unhedged_q0")
    assert result["gross_pnl"] - q0["gross_pnl"] == pytest.approx(500 * (102 - 101 + .5))
    assert result["dividend_cash"] == pytest.approx(250)
    assert result["residual_shares"] == 500
    assert hedge_row(sample(dividend_amount=.5), "unhedged_q0")["dividend_cash"] == 0


def test_modern_adapter_reads_fill_controls_and_keeps_pair_controls_nested(monkeypatch):
    monkeypatch.setattr(hedge, "PERIOD_COUNTS", {"2024": 1})
    pair_controls = {
        "primary_assignment_threshold_applied": True,
        "primary_threshold_residual_cash": 0.125,
        "reverse_intrinsic_control_pnl": -2.0,
    }
    fill_rows = []
    for fill, credit, conditional, intrinsic, threshold in (
        ("midpoint", 100.0, 102.0, 4.0, 0.1),
        ("halfway", 101.0, 103.0, 5.0, 0.2),
        ("full_cross", 102.0, 104.0, 6.0, 0.3),
    ):
        gross = credit + 2.0
        fill_rows.append({
            "fill": fill, "assigned": False, "credit": credit,
            "spxw_leg_terminal_cash": 2.0, "dividend_carry_pnl": gross,
            "next_open_pnl": gross, "base_cost_pnl": gross - 7.15,
            "stress_cost_pnl": gross - 16.5,
            "conditional_close_mark_pnl": conditional,
            "direct_intrinsic_pnl": intrinsic,
            "threshold_residual_cash": threshold,
        })
    pair = {
        "entry": "2024-01-02", "expiry": "2024-01-03", "cover": "2024-01-04",
        "spy_contract": "SPY240103C00100000", "spxw_contract": "SPXW240103C05000000",
        "spy_strike": 100.0, "spxw_strike": 5000.0,
        "controls": pair_controls, "fill_rows": fill_rows,
    }
    prices = {
        "2024-01-03": {"open": 100.0, "close": 101.0},
        "2024-01-04": {"open": 102.0, "close": 102.0},
    }
    normalized = normalize_optionmetrics("2024", [pair], prices, [])
    assert [row["fill"] for row in normalized] == ["full_cross", "halfway", "midpoint"]
    for row in normalized:
        controls = row["old_controls"]
        source_fill = next(item for item in fill_rows if item["fill"] == row["fill"])
        assert controls["conditional_close_mark_pnl"] == source_fill["conditional_close_mark_pnl"]
        assert controls["direct_intrinsic_pnl"] == source_fill["direct_intrinsic_pnl"]
        assert controls["threshold_residual_cash"] == source_fill["threshold_residual_cash"]
        assert controls["pair_controls"] == pair_controls
        q0 = hedge_row(row, "unhedged_q0", stress=False)
        q0_stress = hedge_row(row, "unhedged_q0", stress=True)
        oracle = hedge_row(row, "assignment_oracle_q1000A", stress=False)
        verify_row_identities(row, q0, q0_stress, oracle)
    summary = {"cohorts": {"all": {"fills": {}}}}
    for row in normalized:
        summary["cohorts"]["all"]["fills"][row["fill"]] = {
            "dividend_carry_pnl": {"count": 1, "mean": row["old_gross_pnl"]},
            "base_cost_pnl": {"count": 1, "mean": row["old_base_cost_pnl"]},
            "stress_cost_pnl": {"count": 1, "mean": row["old_stress_cost_pnl"]},
        }
    sources = {
        "stockrefs_summaries": {"data": b'{"wrds_all":{}}'},
        "2024_summary": {"data": json.dumps(summary).encode()},
    }
    summary_parity = verify_retained_summary_means(sources, normalized)
    assert len(summary_parity) == 9
    assert {(item["fill"], item["metric"]) for item in summary_parity} == {
        (fill, metric) for fill in ("midpoint", "halfway", "full_cross")
        for metric in ("dividend_carry_pnl", "base_cost_pnl", "stress_cost_pnl")
    }


def test_net_assignment_funding_uses_spy_strike_and_dividend_cases_are_separate():
    row = sample(assigned=True, spy_strike=100.0, spxw_strike=5000.0)
    net_funded = hedge_row(row, "fixed1000longshares", funding="assignment_cash_net")
    gross_funded = hedge_row(row, "fixed1000longshares", funding="gross_prefunding")
    assert net_funded["costs"]["hedge_funding"] == pytest.approx((1000 * 101 - 1000 * 100) * .05 * 3 / 365)
    assert gross_funded["costs"]["hedge_funding"] == pytest.approx(1000 * 101 * .05 * 3 / 365)
    no_dividend = hedge_row(row, "fixed1000longshares", include_dividends=False)
    with_dividend = hedge_row(row, "fixed1000longshares", include_dividends=True)
    assert no_dividend["gross_pnl"] == pytest.approx(with_dividend["gross_pnl"])


def test_assignment_hedge_residual_and_partial_assignment_bounds():
    result = hedge_row(sample(assigned=True, spy_open=101), "fixed500longshares")
    assert result["residual_shares"] == -500
    assert result["residual_bounds"] == [-500, 500]
    assert result["possible_residual_shares"] == [500 - 100 * k for k in range(11)]


def test_open_rule_uses_open_and_frozen_spy_strike_only():
    assert q_for_arm("open_itm_q1000", True, 100.009, 100.0) == 0
    assert q_for_arm("open_itm_q1000", False, 100.01, 100.0) == 1000
    assert q_for_arm("open_itm_q1000", False, 100.01 - 5e-11, 100.0) == 1000


def test_funding_uses_expiry_to_cover_calendar_days_even_when_unassigned():
    out = hedge_row(sample(), "fixed500longshares")
    expected = 500 * 101 * .05 * 3 / 365
    assert out["costs"]["hedge_funding"] == pytest.approx(expected)


def test_q0_reconstruction_and_zero_dividend_cash_when_unassigned():
    row = sample(dividend_amount=.75, old_gross_pnl=125.0, old_dividend_pnl=0.0,
                 old_base_cost_pnl=117.85)
    out = hedge_row(row, "unhedged_q0")
    assert out["dividend_cash"] == 0
    assert out["gross_pnl"] == 125
    verify_q0_parity(row, out)


def test_assignment_oracle_eliminates_gross_stock_price_and_dividend_exposure():
    out = hedge_row(sample(assigned=True), "assignment_oracle_q1000A")
    assert out["residual_shares"] == 0
    assert out["overnight_price_contribution"] == 0
    assert out["dividend_cash"] == 0
    assert out["costs"]["hedge_funding"] > 0


def test_assigned_q0_retains_original_cover_fee_borrow_and_funding_timing():
    row = sample(assigned=True, credit=-100.0, days_entry_cover=4,
                 old_gross_pnl=-2575.0, old_dividend_pnl=-500.0,
                 old_base_cost_pnl=-2612.108904109589,
                 old_stress_cost_pnl=-2684.623287671233)
    base = hedge_row(row, "unhedged_q0", stress=False)
    stress = hedge_row(row, "unhedged_q0", stress=True)
    assert base["costs"]["stock_fees"] == pytest.approx(5.0)
    assert base["costs"]["residual_short_borrow"] == pytest.approx(1000 * 101 * .03 * 3 / 365)
    assert base["costs"]["premium_debit_funding"] == pytest.approx(100 * .05 * 4 / 365)
    verify_q0_parity(row, base)
    assert stress["net_pnl"] == pytest.approx(row["old_stress_cost_pnl"])


def test_unassigned_q0_legacy_stress_funding_window_and_costs():
    row = sample(credit=-100.0, dividend_amount=.9, days_entry_expiry=1,
                 days_entry_cover=4, days_expiry_cover=3, old_gross_pnl=-75.0,
                 old_dividend_pnl=0.0, old_base_cost_pnl=-84.15)
    result = hedge_row(row, "unhedged_q0", stress=True)
    assert result["costs"]["premium_debit_funding"] == pytest.approx(100 * .10 * 1 / 365)
    assert result["costs"]["residual_short_borrow"] == 0
    assert result["net_pnl"] == pytest.approx(-75 - 16.5 - 100 * .10 / 365)


def test_bootstrap_draws_are_reproducible_and_shared_intervals_accept_paired_data():
    labels = ["2024-W01", "2024-W01", "2024-W02", "2024-W03"]
    draws_a, hash_a = bootstrap_indices(labels, draws=100, seed=20261030)
    draws_b, hash_b = bootstrap_indices(labels, draws=100, seed=20261030)
    assert draws_a == draws_b
    assert hash_a == hash_b
    interval = paired_mean_interval([1.0, 3.0, 5.0, 7.0], draws_a)
    assert interval["mean"] == 4
    assert interval["ci95_type7"][0] <= interval["ci95_type7"][1]
    assert len(interval["draw_denominators"]) >= 1


def test_vectorized_shared_bootstrap_reuses_draws_for_absolute_and_paired_metrics():
    labels = ["2024-W01", "2024-W01", "2024-W02", "2024-W03"]
    columns = {"control": [1.0, 3.0, 5.0, 7.0],
               "treatment": [2.0, 5.0, 8.0, 11.0],
               "paired": [1.0, 2.0, 3.0, 4.0]}
    first, digest_a = bootstrap_cluster_intervals(labels, columns, draws=100, seed=20261030)
    second, digest_b = bootstrap_cluster_intervals(labels, columns, draws=100, seed=20261030)
    assert digest_a == digest_b
    assert first == second
    assert first["control"]["mean"] == pytest.approx(4.0)
    assert first["paired"]["mean"] == pytest.approx(2.5)
    assert first["control"]["draw_denominators"] == first["paired"]["draw_denominators"]
    names = sorted(set(labels))
    rng = random.Random(20261030)
    sample_ids = [[rng.randrange(len(names)) for _ in names] for _ in range(100)]
    expected_digest = hashlib.sha256(json.dumps(sample_ids, separators=(",", ":")).encode()).hexdigest()
    _, actual_digest = bootstrap_cluster_intervals(labels, columns, draws=100, seed=20261030)
    assert actual_digest == expected_digest


def test_true_peak_to_trough_drawdown_starts_at_zero():
    assert max_peak_to_trough_drawdown([100, -50, 100, -70]) == 70
    assert max_peak_to_trough_drawdown([-20, 5]) == 20


def test_missing_nonfinite_and_bad_dates_fail_closed():
    with pytest.raises(ValueError, match="missing"):
        hedge_row({"credit": 1}, "unhedged_q0")
    with pytest.raises(ValueError, match="nonfinite"):
        hedge_row(sample(spy_open=float("nan")), "unhedged_q0")
    with pytest.raises(ValueError, match="cover date"):
        hedge_row(sample(days_expiry_cover=-1), "unhedged_q0")


def test_duplicate_and_conflicting_stock_dates_are_rejected():
    header = "secid,date,ticker,index_flag,open,close,cfadj\n"
    row = "109820,2024-01-02,SPY,0,100,101,1\n"
    div_header = "secid,record_date,seq_num,ex_date,amount,adj_factor,distr_type,frequency,currency,approx_flag,cancel_flag,liquid_flag,ticker,index_flag\n"
    with pytest.raises(ValueError, match="duplicate WRDS stock price key"):
        hedge.read_wrds_references((header + row + row).encode(), div_header.encode())


def test_missing_required_expiry_or_cover_stock_date_fails_without_fallback():
    source = {"assigned": False}
    with pytest.raises(ValueError, match="missing required stock date"):
        hedge._build_normalized_row("2024", "2024-01-02", "2024-01-03", "2024-01-04",
                                    "midpoint", source, {}, [], modern=True)


def test_distribution_parser_requires_spy_identity_and_uses_supported_cash_only():
    stock = ("secid,date,ticker,index_flag,open,close,cfadj\n"
             "109820,2024-01-02,SPY,0,100,101,1\n").encode()
    header = "secid,record_date,seq_num,ex_date,amount,adj_factor,distr_type,frequency,currency,approx_flag,cancel_flag,liquid_flag,ticker,index_flag\n"
    accepted = "109820,2024-01-01,1,2024-01-03,0.5,1,1,4,USD,0,0,0,SPY,0\n"
    unsupported = "109820,2024-01-01,2,2024-01-04,0.7,1,1,4,USD,1,0,0,SPY,0\n"
    prices, events = hedge.read_wrds_references(stock, (header + accepted + unsupported).encode())
    assert prices["2024-01-02"] == {"open": 100, "close": 101}
    assert events == [{"ex_date": "2024-01-03", "amount": 0.5}]
    with pytest.raises(ValueError, match="unexpected SPY identity"):
        hedge.read_wrds_references(stock, (header + accepted.replace(",SPY,0", ",SPX,1")).encode())
    with pytest.raises(ValueError, match="duplicate WRDS distribution identity key"):
        hedge.read_wrds_references(stock, (header + accepted + accepted).encode())


def test_frozen_source_hash_mutation_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "source.csv"
    source.write_bytes(b"frozen")
    source_hash = hedge.hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    payload = {"source_files": [{"name": "sample", "path": str(source),
                                 "bytes": source.stat().st_size, "sha256": source_hash}]}
    manifest.write_text(__import__("json").dumps(payload))
    protocol = tmp_path / "protocol.md"
    protocol.write_bytes(b"frozen protocol")
    monkeypatch.setattr(hedge, "PROTOCOL_PATH", __import__("pathlib").Path("protocol.md"))
    monkeypatch.setattr(hedge, "PROTOCOL_SHA256", hedge.hashlib.sha256(protocol.read_bytes()).hexdigest())
    monkeypatch.setattr(hedge, "INPUT_MANIFEST_PATH", manifest.relative_to(tmp_path))
    monkeypatch.setattr(hedge, "INPUT_MANIFEST_SHA256", hedge.hashlib.sha256(manifest.read_bytes()).hexdigest())
    assert hedge.verify_frozen_sources(tmp_path)["sample"]["sha256"] == source_hash
    source.write_bytes(b"mutated")
    with pytest.raises(RuntimeError, match="frozen source changed"):
        hedge.verify_frozen_sources(tmp_path)


def test_dirty_head_is_rejected_before_real_evaluation(tmp_path, monkeypatch):
    class Proc:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.returncode = 0

    calls = iter([Proc("abc123\n"), Proc(" M src/spyspx/overnight_hedge.py\n")])
    monkeypatch.setattr(hedge.subprocess, "run", lambda *a, **k: next(calls))
    with pytest.raises(RuntimeError, match="clean Git worktree"):
        hedge.guarded_evaluate_preflight(tmp_path)


def test_loaded_code_must_match_committed_head(tmp_path, monkeypatch):
    (tmp_path / "planning").mkdir()
    (tmp_path / "src/spyspx").mkdir(parents=True)
    code = tmp_path / "src/spyspx/overnight_hedge.py"
    code.write_bytes(b"working tree code")
    monkeypatch.setattr(hedge, "MODULE_PATH_AT_LOAD", code.resolve())
    monkeypatch.setattr(hedge, "MODULE_SHA256_AT_LOAD", hedge.hashlib.sha256(code.read_bytes()).hexdigest())
    (tmp_path / "planning/protocol.md").write_text("protocol")
    manifest = tmp_path / "planning/manifest.json"
    manifest.write_text("{}")
    monkeypatch.setattr(hedge, "PROTOCOL_PATH", __import__("pathlib").Path("planning/protocol.md"))
    monkeypatch.setattr(hedge, "INPUT_MANIFEST_PATH", __import__("pathlib").Path("planning/manifest.json"))
    monkeypatch.setattr(hedge, "verify_frozen_sources", lambda _repo: {})
    monkeypatch.setattr(hedge, "subprocess", type("Subprocess", (), {"run": staticmethod(
        lambda cmd, **kwargs: type("Proc", (), {"stdout": (b"HEAD code" if cmd[1] == "show" else "HEAD123\n" if cmd[1] == "rev-parse" else ""), "returncode": 0})()
    )}))
    with pytest.raises(RuntimeError, match="loaded evaluator bytes do not match Git HEAD"):
        hedge.guarded_evaluate_preflight(tmp_path)


def test_canonical_loaded_module_path_is_required(tmp_path, monkeypatch):
    class Proc:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.returncode = 0
    (tmp_path / "src/spyspx").mkdir(parents=True)
    canonical = tmp_path / "src/spyspx/overnight_hedge.py"
    canonical.write_bytes(b"canonical")
    impostor = tmp_path / "elsewhere.py"
    impostor.write_bytes(b"canonical")
    monkeypatch.setattr(hedge, "MODULE_PATH_AT_LOAD", impostor.resolve())
    monkeypatch.setattr(hedge.subprocess, "run", lambda cmd, **kw: Proc("abc\n" if cmd[1] == "rev-parse" else ""))
    with pytest.raises(RuntimeError, match="canonical repository path"):
        hedge.guarded_evaluate_preflight(tmp_path)


def test_loaded_module_bytes_mutation_is_rejected(tmp_path, monkeypatch):
    class Proc:
        def __init__(self, stdout=""):
            self.stdout = stdout
            self.returncode = 0
    code = tmp_path / "src/spyspx/overnight_hedge.py"
    code.parent.mkdir(parents=True)
    code.write_bytes(b"loaded bytes")
    monkeypatch.setattr(hedge, "MODULE_PATH_AT_LOAD", code.resolve())
    monkeypatch.setattr(hedge, "MODULE_SHA256_AT_LOAD", hedge.hashlib.sha256(code.read_bytes()).hexdigest())
    code.write_bytes(b"substituted bytes")
    monkeypatch.setattr(hedge.subprocess, "run", lambda cmd, **kw: Proc("abc\n" if cmd[1] == "rev-parse" else ""))
    with pytest.raises(RuntimeError, match="changed after module load"):
        hedge.guarded_evaluate_preflight(tmp_path)


def test_normalized_selection_hash_is_checked_again_after_mutation(tmp_path, monkeypatch):
    selection = tmp_path / "selection.json"
    selection.write_bytes(b"frozen selection")
    relative = selection.relative_to(tmp_path)
    digest = hedge.hashlib.sha256(selection.read_bytes()).hexdigest()
    monkeypatch.setattr(hedge, "SELECTION_PATH", relative)
    monkeypatch.setattr(hedge, "SELECTION_SHA256", digest)
    assert hedge._verify_selection(tmp_path, relative) == digest
    selection.write_bytes(b"mutated selection")
    with pytest.raises(RuntimeError, match="not pinned"):
        hedge._verify_selection(tmp_path, relative)


def test_output_escape_is_rejected_before_any_write(tmp_path):
    with pytest.raises(RuntimeError, match="fresh path"):
        hedge._validate_fresh_output(tmp_path, tmp_path / "outside", "evaluation")


def test_head_change_during_evaluation_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(hedge, "guarded_evaluate_preflight", lambda _repo: "new-head")
    with pytest.raises(RuntimeError, match="changed during evaluation"):
        hedge.verify_head_unchanged(tmp_path, "old-head")


def test_prepare_refuses_to_overwrite_existing_output(tmp_path):
    planning = tmp_path / "planning/overnight-hedge-20261030"
    output = planning / "prepared"
    output.mkdir(parents=True)
    marker = output / "keep.txt"
    marker.write_text("preserve")
    with pytest.raises(RuntimeError, match="fresh path"):
        hedge._write_preparation(tmp_path, output)
    assert marker.read_text() == "preserve"
