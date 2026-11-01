from __future__ import annotations

import csv
import io
from datetime import date

import pytest

from spyspx import optionmetrics_stockrefs as stockrefs


def csv_bytes(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def price_row(day="2022-09-16", **overrides):
    return {"secid": "109820", "date": day, "ticker": "SPY", "index_flag": "0",
            "open": "390", "close": "389", "cfadj": "1", **overrides}


def dividend_row(amount="1.5964", day="2022-09-16", **overrides):
    return {"secid": "109820", "record_date": "2022-09-19", "ticker": "SPY", "index_flag": "0",
            "seq_num": "1", "ex_date": day, "amount": amount, "adj_factor": "1", "distr_type": "1",
            "frequency": "3", "currency": "USD", "approx_flag": "0", "cancel_flag": "0",
            "liquid_flag": "0", **overrides}


def test_price_references_use_raw_open_close_and_reject_duplicates():
    headers = ["secid", "date", "ticker", "index_flag", "open", "close", "cfadj"]
    rows, _ = stockrefs.read_stock_references(csv_bytes(headers, [price_row()]))
    assert rows[date(2022, 9, 16)] == {"open": 390.0, "close": 389.0}
    with pytest.raises(ValueError, match="duplicate"):
        stockrefs.read_stock_references(csv_bytes(headers, [price_row(), price_row()]))


@pytest.mark.parametrize("field,value", [("close", "nan"), ("open", "0"), ("cfadj", "1.01")])
def test_price_references_reject_nonfinite_nonpositive_or_adjusted_rows(field, value):
    headers = ["secid", "date", "ticker", "index_flag", "open", "close", "cfadj"]
    with pytest.raises(ValueError):
        stockrefs.read_stock_references(csv_bytes(headers, [price_row(**{field: value})]))


def test_cash_dividend_keeps_vendor_precision_and_excludes_unsupported_events():
    headers = list(dividend_row())
    rows, _ = stockrefs.read_cash_dividends(csv_bytes(headers, [
        dividend_row(), dividend_row(seq_num="2", amount="1.7814", day="2022-12-16"),
        dividend_row(seq_num="3", currency="EUR"),
    ]))
    assert rows == [
        {"ex_date": date(2022, 9, 16), "amount": 1.5964},
        {"ex_date": date(2022, 12, 16), "amount": 1.7814},
    ]


def test_arm_matrix_is_frozen_to_five_declared_cases():
    assert stockrefs.ARMS == (
        "baseline_old_all", "wrds_expiry_close_only", "wrds_cover_open_only",
        "wrds_dividends_only", "wrds_all",
    )


def synthetic_selection(*, close=100.02, cover_open=101.0):
    del close, cover_open  # Source prices live separately from the immutable selection.
    return [{
        "period": "2022", "entry": "2022-07-05", "expiry": "2022-07-06", "cover": "2022-07-07",
        "fill": fill, "spy_contract": "SPY220706C00100000", "spxw_contract": "SPXW220706C04000000",
        "spy_strike": 100.0, "spxw_strike": 4000.0, "spy_entry_cash": 1100.0,
        "spxw_entry_cash": -1100.0, "credit": 0.0, "spy_bid": 1.0, "spy_ask": 1.2,
        "spxw_bid": 10.0, "spxw_ask": 12.0, "size_eligible": True,
    } for fill in stockrefs.FILLS]


def refs(close, op, dividend=0.0):
    return {date(2022, 7, 6): {"close": close, "open": close, "dividend": 0.0},
            date(2022, 7, 7): {"close": op, "open": op, "dividend": dividend}}


def wrds(close, op):
    return {date(2022, 7, 6): {"close": close, "open": close},
            date(2022, 7, 7): {"close": op, "open": op}}


def test_synthetic_assignment_flip_and_costs_recompute_from_new_expiry_close():
    old = refs(99.99, 101.0)
    result = stockrefs.evaluate_rows(synthetic_selection(), {"stocks": old, "settlements": {date(2022, 7, 6): 3999.0}}, {},
                                     wrds(100.02, 101.0), [])
    baseline = result["baseline_old_all"][0]
    close_only = result["wrds_expiry_close_only"][0]
    assert baseline["assigned"] is False
    assert close_only["assigned"] is True
    assert close_only["calendar_days_expiry_to_cover"] == 1
    assert close_only["cost_components"]["borrow_days"] == 1
    assert close_only["cost_components"]["borrow_base"] > 0
    assert close_only["spy_entry_cash"] == baseline["spy_entry_cash"]
    assert close_only["credit"] == baseline["credit"]
    assert close_only["spxw_pm_settlement"] == baseline["spxw_pm_settlement"]


def test_synthetic_cover_open_only_changes_assigned_closeout_and_costs():
    old = refs(100.02, 100.0)
    result = stockrefs.evaluate_rows(synthetic_selection(), {"stocks": old, "settlements": {date(2022, 7, 6): 3999.0}}, {},
                                     wrds(100.02, 101.0), [])
    baseline = result["baseline_old_all"][0]
    cover_only = result["wrds_cover_open_only"][0]
    assert baseline["assigned"] is cover_only["assigned"] is True
    assert baseline["direct_intrinsic_pnl"] == cover_only["direct_intrinsic_pnl"]
    assert baseline["next_open_pnl"] - cover_only["next_open_pnl"] == 1000.0
    assert baseline["cost_components"]["borrow_base"] == cover_only["cost_components"]["borrow_base"]
    assert baseline["spy_entry_cash"] == cover_only["spy_entry_cash"]


def test_synthetic_dividend_only_applies_exdate_carry_and_keeps_nondividend_cost():
    old = refs(100.02, 101.0)
    result = stockrefs.evaluate_rows(synthetic_selection(), {"stocks": old, "settlements": {date(2022, 7, 6): 3999.0}}, {},
                                     wrds(100.02, 101.0), [{"ex_date": date(2022, 7, 7), "amount": 0.5001, "supported": True}])
    baseline = result["baseline_old_all"][0]
    dividend = result["wrds_dividends_only"][0]
    assert dividend["dividend_carry_dates"] == ["2022-07-07"]
    assert dividend["dividend_carry_amount"] == pytest.approx(500.1)
    assert dividend["dividend_carry_pnl"] == pytest.approx(baseline["dividend_carry_pnl"] - 500.1)
    assert dividend["base_nondividend_cost_pnl"] == baseline["base_nondividend_cost_pnl"]
    assert dividend["base_dividend_cost_pnl"] == pytest.approx(baseline["base_dividend_cost_pnl"] - 500.1)
    assert dividend["entry_exposure_dividend_dates"] == []


def test_synthetic_zero_assignment_reverse_scope_and_fixed_denominator():
    selection = synthetic_selection()
    old = refs(99.99, 101.0)
    result = stockrefs.evaluate_rows(selection, {"stocks": old, "settlements": {date(2022, 7, 6): 3999.0}}, {},
                                     wrds(99.99, 101.0), [])
    assert all(len(rows) == len(selection) for rows in result.values())
    for arm in stockrefs.ARMS:
        assert [(r["period"], r["entry"], r["expiry"], r["fill"], r["credit"], r["spy_entry_cash"])
                for r in result[arm]] == [(r["period"], r["entry"], r["expiry"], r["fill"], r["credit"], r["spy_entry_cash"])
                                          for r in result["baseline_old_all"]]
    row = result["baseline_old_all"][0]
    assert row["assigned"] is False
    assert row["spy_leg_expiry_shares"] == 0
    assert row["dividend_carry_amount"] == 0
    assert row["zero_control_pnl"] == 0
    assert row["reverse_terminal_intrinsic_control_pnl"] == row["reverse_cross_control_pnl"]
    assert "physical_cover" not in row


def test_parity_comparator_rejects_missing_and_nonfinite_required_values():
    with pytest.raises(ValueError, match="missing parity fields"):
        stockrefs.compare_value({}, {"cash": 1.0})
    with pytest.raises(ValueError, match="nonfinite"):
        stockrefs.compare_value(float("nan"), 1.0)


def test_bootstrap_uses_shared_seeded_iso_week_indices():
    rows = [{"expiry": f"2022-07-{day:02d}"} for day in (6, 8, 13, 15)]
    first = stockrefs._bootstrap_indices(rows)
    assert len(first) == 10_000
    assert len(first[0]) == 2
    assert first == stockrefs._bootstrap_indices(rows)


def test_baseline_receipt_gate_rejects_tampered_rows_and_unbound_controls(tmp_path):
    import json
    from pathlib import Path

    bindings = {"head": "synthetic", "selection_sha256": "frozen"}
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    rows = b"[]\n"
    (bundle / "baseline_rows.json").write_bytes(rows)
    receipt = {"status": "PASS", "receipt_type": "SPYSPX235_BASELINE_PARITY",
               "bindings": bindings, "baseline_rows_sha256": stockrefs.sha256(rows)}
    receipt_bytes = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    (bundle / "baseline-parity.json").write_bytes(receipt_bytes)
    manifest = {"status": "BASELINE_PARITY_PASS_VARIANTS_NOT_RUN", "bindings": bindings,
                "output_sha256": {"baseline-parity.json": stockrefs.sha256(receipt_bytes),
                                  "baseline_rows.json": stockrefs.sha256(rows)}}
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    assert stockrefs._validate_baseline_receipt(bundle / "baseline-parity.json", bindings) == receipt
    (bundle / "baseline_rows.json").write_bytes(b"tampered\n")
    with pytest.raises(ValueError, match="rows do not match"):
        stockrefs._validate_baseline_receipt(bundle / "baseline-parity.json", bindings)
    with pytest.raises(ValueError, match="identical code"):
        stockrefs._validate_baseline_receipt(bundle / "baseline-parity.json", {"head": "other"})


def test_dirty_worktree_cannot_enter_lead_calculation_gate(tmp_path):
    import subprocess

    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True)

    git("init", "-q")
    (tmp_path / "tracked.txt").write_text("clean\n")
    git("add", "tracked.txt")
    subprocess.run(["git", "-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid",
                    "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    (tmp_path / "untracked.txt").write_text("dirty\n")
    with pytest.raises(ValueError, match="clean Git worktree"):
        stockrefs._identity(tmp_path)
    (tmp_path / "untracked.txt").unlink()
    (tmp_path / "tracked.txt").write_text("modified\n")
    with pytest.raises(ValueError, match="clean Git worktree"):
        stockrefs._identity(tmp_path)


def test_integrity_gate_detects_protocol_source_control_selection_and_arm_mutation(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path

    files = {}
    for name in ("protocol", "manifest", "legacy", "wrds", "calendar"):
        path = tmp_path / name
        path.write_text(name)
        files[name] = path
    def binding(path):
        data = path.read_bytes()
        return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    identity = {"head": "synthetic", "clean": True, "code": {}}
    monkeypatch.setattr(stockrefs, "_identity", lambda repo: identity)
    bindings = {"protocol": binding(files["protocol"]), "input_manifest": binding(files["manifest"]),
                "original_sources": {"control": binding(files["legacy"])},
                "wrds_sources": {"prices": binding(files["wrds"]), "calendar": binding(files["calendar"])},
                "selection_sha256": hashlib.sha256(b"selection").hexdigest(),
                "arm_freeze_sha256": hashlib.sha256(b"arms").hexdigest()}
    stockrefs._integrity_check(tmp_path, identity, bindings, b"selection", b"arms")
    for name, group, key in (("protocol", "protocol", None), ("manifest", "input_manifest", None),
                             ("legacy", "original_sources", "control"), ("wrds", "wrds_sources", "prices"),
                             ("calendar", "wrds_sources", "calendar")):
        files[name].write_text("mutated")
        with pytest.raises(ValueError, match="changed|mismatch"):
            stockrefs._integrity_check(tmp_path, identity, bindings, b"selection", b"arms")
        files[name].write_text(name)
    with pytest.raises(ValueError, match="selection snapshot"):
        stockrefs._integrity_check(tmp_path, identity, bindings, b"changed", b"arms")
    with pytest.raises(ValueError, match="five-arm freeze"):
        stockrefs._integrity_check(tmp_path, identity, bindings, b"selection", b"changed")
    changed_identity = {"head": "other", "clean": True, "code": {}}
    monkeypatch.setattr(stockrefs, "_identity", lambda repo: changed_identity)
    with pytest.raises(ValueError, match="code, imported module, Git SHA"):
        stockrefs._integrity_check(tmp_path, identity, bindings, b"selection", b"arms")


def test_output_path_must_be_fresh_ignored_child(tmp_path):
    import subprocess
    from pathlib import Path

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("runs/\n")
    target = stockrefs._validate_output(tmp_path, Path("runs/optionmetrics_stockrefs/tag-a"))
    assert target == tmp_path / "runs/optionmetrics_stockrefs/tag-a"
    with pytest.raises(ValueError, match="fresh child"):
        stockrefs._validate_output(tmp_path, Path("outside/tag"))
    target.mkdir(parents=True)
    with pytest.raises(FileExistsError, match="already exists"):
        stockrefs._validate_output(tmp_path, target)
    with pytest.raises(ValueError, match="fresh child"):
        stockrefs._validate_output(tmp_path, Path("runs/optionmetrics_stockrefs"))


def test_unsupported_distribution_in_relevant_window_is_blocked():
    selection = synthetic_selection()
    old = refs(100.02, 101.0)
    event = {"ex_date": date(2022, 7, 7), "amount": 0.25, "supported": False}
    with pytest.raises(ValueError, match="unsupported corporate action"):
        stockrefs.evaluate_rows(selection, {"stocks": old, "settlements": {date(2022, 7, 6): 3999.0}}, {},
                                wrds(100.02, 101.0), [event])


def test_synthetic_2019_baseline_dispatch_uses_saved_row_cohort(monkeypatch):

    item = synthetic_selection()[2].copy()
    item.update(period="2019", fill="full_cross", entry="2019-08-01", expiry="2019-08-02", cover="2019-08-05")
    close, op, settlement = 100.02, 101.0, 3999.0
    calculated = stockrefs.compute_fill(item, spy_close=close, cover_open=op, settlement=settlement, dividends=[])
    cohort = {"reverse_cross_control_credit": calculated["reverse_full_cross_entry_credit_control"],
              "spy_expiry_yahoo_raw_close": close, "spy_next_session_yahoo_raw_open": op,
              "spxw_pm_settlement": settlement}
    saved_row = {**calculated, "spy_entry_cash": item["spy_entry_cash"],
                 "spxw_entry_cash": item["spxw_entry_cash"], "spy_entry_shares": 0,
                 "spxw_entry_shares": 0, "_cohort": cohort}
    saved = {("2019", item["entry"], item["expiry"], item["fill"]): saved_row}
    old19 = {"yahoo": {date(2019, 8, 2): {"close": close}, date(2019, 8, 5): {"open": op}},
             "settlements": {date(2019, 8, 2): {"value": settlement}}, "dividends": []}
    monkeypatch.setattr(stockrefs, "_baseline_summary_check",
                        lambda *args: {"summary_fields_checked": 0, "status": "PASS"})
    rows, receipt = stockrefs._compute_baseline([item], saved, {}, old19, {}, {})
    assert receipt["status"] == "PASS"
    assert rows[0]["period"] == "2019"
    assert rows[0]["stock_neutralized_pnl"] == calculated["stock_neutralized_pnl"]


def _synthetic_2022_summary_fixture():
    from datetime import timedelta

    metrics = {
        "direct_intrinsic_pnl": "gross",
        "conditional_close_mark_pnl": "gross",
        "next_open_pnl": "gross",
        "dividend_carry_pnl": "dividend_adjusted",
        "base_nondividend_cost_pnl": "base_nondividend",
        "stress_nondividend_cost_pnl": "stress_nondividend",
        "base_dividend_cost_pnl": "base_dividend",
        "stress_dividend_cost_pnl": "stress_dividend",
    }
    periods = ("all", "Q3", "Q4", "2022-07", "2022-08", "2022-09",
               "2022-10", "2022-11", "2022-12")
    rows = []
    index = 0
    for month, count in ((7, 10), (8, 11), (9, 10), (10, 11), (11, 10), (12, 11)):
        day = date(2022, month, 1)
        added = 0
        while added < count:
            if day.weekday() < 5:
                for fill_index, fill in enumerate(stockrefs.FILLS):
                    row = {"period": "2022", "expiry": day.isoformat(), "fill": fill,
                           "size_eligible": index % 3 != 0}
                    for metric_index, metric in enumerate(metrics):
                        row[metric] = float(index + fill_index * 2 + metric_index - 15)
                    rows.append(row)
                index += 1
                added += 1
            day += timedelta(days=1)

    summaries = []
    for period in periods:
        for fill in stockrefs.FILLS:
            subset = [r for r in rows if r["fill"] == fill and
                (period == "all" or
                 (period == "Q3" and date.fromisoformat(r["expiry"]).month in (7, 8, 9)) or
                 (period == "Q4" and date.fromisoformat(r["expiry"]).month in (10, 11, 12)) or
                 r["expiry"].startswith(period))]
            for metric, case in metrics.items():
                for depth in ("all_selected", "size_eligible"):
                    kept = subset if depth == "all_selected" else [r for r in subset if r["size_eligible"]]
                    values = [r[metric] for r in kept]
                    summary = stockrefs.summarize_values(values)
                    summaries.append({"lane": stockrefs.LANE_2022, "population": "equal_expiry_primary",
                        "period": period, "fill": fill, "metric": metric, "cost_case": case, "depth": depth,
                        "valid_rows": len(values), "missing_outcome_count": 0,
                        "expiry_count": len({r["expiry"] for r in kept}), "mean": summary["mean"],
                        "median": summary["median"], "worst_loss": summary["min"],
                        "positive_count": summary["positive_count"]})
    return rows, {"equal_expiry_primary_summaries": summaries}


def test_2022_baseline_summary_matches_declared_equal_expiry_population():
    rows, aggregate = _synthetic_2022_summary_fixture()
    result = stockrefs._baseline_summary_check(rows, "2022", aggregate)
    assert result == {"summary_fields_checked": 2592, "summary_records_matched": 432,
                      "summary_records_expected": 432, "status": "PASS"}


@pytest.mark.parametrize("mutation", ["wrong_population", "zero", "missing_record", "missing_field"])
def test_2022_baseline_summary_fails_closed_on_bad_coverage(mutation):
    rows, aggregate = _synthetic_2022_summary_fixture()
    summaries = aggregate["equal_expiry_primary_summaries"]
    if mutation == "wrong_population":
        for row in summaries:
            row["population"] = stockrefs.POPULATION_2022
    elif mutation == "zero":
        aggregate["equal_expiry_primary_summaries"] = []
    elif mutation == "missing_record":
        summaries.pop()
    else:
        summaries[0].pop("mean")
    with pytest.raises(ValueError):
        stockrefs._baseline_summary_check(rows, "2022", aggregate)


def _synthetic_2019_summary_fixture():
    metric_fields = {
        "base_cost_pnl": "base_cost_pnl", "conditional_close_mark_pnl": "conditional_close_mark_pnl",
        "direct_intrinsic_pnl": "direct_intrinsic_pnl", "next_open_pnl": "next_open_pnl",
        "reverse_cross_control": "reverse_cross_control_pnl",
        "reverse_cross_control_pnl": "reverse_cross_control_pnl",
        "stock_neutralized_base_cost_pnl": "stock_neutralized_base_cost_pnl",
        "stock_neutralized_pnl": "stock_neutralized_pnl",
        "stock_neutralized_stress_cost_pnl": "stock_neutralized_stress_cost_pnl",
        "stress_cost_pnl": "stress_cost_pnl", "zero_control": "zero_control_pnl",
        "zero_control_pnl": "zero_control_pnl",
    }
    expiry_dates = [date.fromisoformat(value) for value in (
        "2019-08-02", "2019-08-07", "2019-08-09", "2019-08-14", "2019-08-16",
        "2019-08-21", "2019-08-23", "2019-08-28", "2019-08-30")]
    rows = []
    for index, expiry in enumerate(expiry_dates):
        for fill_index, fill in enumerate(stockrefs.FILLS):
            row = {"period": "2019", "expiry": expiry.isoformat(), "fill": fill}
            for metric_index, field in enumerate(set(metric_fields.values())):
                row[field] = float(index + fill_index + metric_index - 4)
            row["zero_control_pnl"] = 0.0
            rows.append(row)

    groups = {"2019-08": lambda day: True,
              **{f"2019-W{week}": lambda day, week=week: day.isocalendar().week == week
                 for week in range(31, 36)},
              "all": lambda day: True}
    cohorts = {}
    for group, accepts in groups.items():
        days = [day for day in expiry_dates if accepts(day)]
        fills = {}
        for fill in stockrefs.FILLS:
            subset = [r for r in rows if r["fill"] == fill and date.fromisoformat(r["expiry"]) in days]
            metrics = {}
            for metric, field in metric_fields.items():
                values = [r[field] for r in subset]
                summary = stockrefs.summarize_values(values)
                metrics[metric] = {"n": len(values), "missing_n": 0, "mean": summary["mean"],
                    "median": summary["median"], "min": summary["min"], "max": summary["max"],
                    "positive_count": summary["positive_count"], "values": values}
            fills[fill] = metrics
        cohorts[group] = {"primary_expiry_count": len(days), "fills": fills}
    return rows, {"population": "one fixed primary pair per declared expiry; not a portfolio",
                  "cohorts": cohorts}


def test_2019_baseline_summary_matches_declared_population_and_aliases():
    rows, aggregate = _synthetic_2019_summary_fixture()
    result = stockrefs._baseline_summary_check(rows, "2019", aggregate)
    assert result == {"summary_fields_checked": 2037, "summary_records_matched": 252,
                      "summary_records_expected": 252, "status": "PASS"}


@pytest.mark.parametrize("mutation", ["wrong_population", "zero", "missing_group", "missing_fill",
                                        "missing_metric", "missing_field"])
def test_2019_baseline_summary_fails_closed_on_bad_coverage(mutation):
    rows, aggregate = _synthetic_2019_summary_fixture()
    cohorts = aggregate["cohorts"]
    if mutation == "wrong_population":
        aggregate["population"] = "wrong population"
    elif mutation == "zero":
        aggregate["cohorts"] = {}
    elif mutation == "missing_group":
        cohorts.pop("2019-W35")
    elif mutation == "missing_fill":
        cohorts["all"]["fills"].pop("midpoint")
    elif mutation == "missing_metric":
        cohorts["all"]["fills"]["midpoint"].pop("zero_control")
    else:
        cohorts["all"]["fills"]["midpoint"]["direct_intrinsic_pnl"].pop("mean")
    with pytest.raises(ValueError):
        stockrefs._baseline_summary_check(rows, "2019", aggregate)


def test_bootstrap_summaries_are_separate_per_fill_and_share_draws(monkeypatch):
    from datetime import timedelta

    rows_by_arm = {arm: [] for arm in stockrefs.ARMS}
    start = date(2022, 1, 3)
    levels = {"midpoint": 100.0, "halfway": 1000.0, "full_cross": 10000.0}
    for day_index in range(63):
        expiry = start + timedelta(days=day_index)
        for fill in stockrefs.FILLS:
            base = levels[fill]
            for arm_index, arm in enumerate(stockrefs.ARMS):
                row = {"period": "2022", "entry": (expiry-timedelta(days=1)).isoformat(),
                       "expiry": expiry.isoformat(), "cover": (expiry+timedelta(days=1)).isoformat(),
                       "fill": fill, "assigned": False}
                for metric_index, metric in enumerate(stockrefs.METRICS):
                    row[metric] = base + arm_index * (metric_index + 1) * (1 if fill == "midpoint" else 2 if fill == "halfway" else 3)
                rows_by_arm[arm].append(row)
    # The summary helper requires both fixed periods, but uncertainty uses only 2022.
    for arm in stockrefs.ARMS:
        for fill in stockrefs.FILLS:
            row = {"period": "2019", "entry": "2019-08-01", "expiry": "2019-08-02",
                   "cover": "2019-08-05", "fill": fill, "assigned": False}
            for metric_index, metric in enumerate(stockrefs.METRICS):
                row[metric] = levels[fill] + metric_index
            rows_by_arm[arm].append(row)
    calls = []
    original = stockrefs._bootstrap_indices
    def tracked(rows):
        calls.append(len(rows))
        return original(rows)
    monkeypatch.setattr(stockrefs, "_bootstrap_indices", tracked)
    uncertainty = stockrefs._uncertainty(rows_by_arm)
    summaries = stockrefs._arm_summaries(rows_by_arm)
    assert calls == [189]
    assert uncertainty["shared_week_draws_across_all_arms_and_fills"] is True
    for fill, point in levels.items():
        base_interval = uncertainty["absolute"][stockrefs.ARMS[0]][fill]["direct_intrinsic_pnl"]
        paired_interval = uncertainty["paired"]["wrds_all"][fill]["direct_intrinsic_pnl"]
        assert base_interval["fixed_n"] == paired_interval["fixed_n"] == 63
        assert base_interval["point_mean"] == summaries[stockrefs.ARMS[0]]["2022"][fill]["direct_intrinsic_pnl"]["mean"] == point
        expected_shift = 4 * (1 if fill == "midpoint" else 2 if fill == "halfway" else 3)
        assert paired_interval["mean_difference"] == expected_shift
    assert uncertainty["absolute"][stockrefs.ARMS[0]]["midpoint"]["direct_intrinsic_pnl"]["point_mean"] != \
           uncertainty["absolute"][stockrefs.ARMS[0]]["full_cross"]["direct_intrinsic_pnl"]["point_mean"]
    assert set(uncertainty["nonadditivity"]) == set(stockrefs.FILLS)
    assert len(original([{ "expiry": "2022-01-03" }])) == 10_000


def test_bootstrap_unequal_iso_week_sizes_use_resampled_row_count(monkeypatch):
    from datetime import timedelta

    rows_by_arm = {arm: [] for arm in stockrefs.ARMS}
    # Weekday expiries create partial edge weeks and unequal clusters.
    start = date(2022, 1, 3)
    expiry = start
    for index in range(63):
        while expiry.weekday() >= 5:
            expiry += timedelta(days=1)
        for arm_index, arm in enumerate(stockrefs.ARMS):
            for fill_index, fill in enumerate(stockrefs.FILLS):
                row = {"period": "2022", "expiry": expiry.isoformat(), "fill": fill}
                for metric_index, metric in enumerate(stockrefs.METRICS):
                    row[metric] = float((expiry.isocalendar().week * 10 + index + arm_index)
                                        * (fill_index + 1) * (metric_index + 1))
                rows_by_arm[arm].append(row)
        expiry += timedelta(days=1)
    original = stockrefs._bootstrap_indices
    draws = original(rows_by_arm[stockrefs.ARMS[0]])
    uncertainty = stockrefs._uncertainty(rows_by_arm)
    result = uncertainty["absolute"][stockrefs.ARMS[0]]["full_cross"]["direct_intrinsic_pnl"]

    week_rows = {}
    for row in rows_by_arm[stockrefs.ARMS[0]]:
        if row["fill"] != "full_cross":
            continue
        expiry = date.fromisoformat(row["expiry"])
        key = f"{expiry.isocalendar().year}-W{expiry.isocalendar().week:02d}"
        week_rows.setdefault(key, []).append(row["direct_intrinsic_pnl"])
    expected_samples = []
    denominators = []
    for draw in draws:
        values = [value for week in draw for value in week_rows[week]]
        denominators.append(len(values))
        expected_samples.append(sum(values) / len(values))
    expected_samples.sort()
    assert len({len(values) for values in week_rows.values()}) > 1
    assert min(denominators) < 63 < max(denominators)
    assert result["fixed_n"] == 63
    assert result["resampled_rows_min"] == min(denominators)
    assert result["resampled_rows_max"] == max(denominators)
    assert result["low_95"] == stockrefs._quantile7(expected_samples, .025)
    assert result["high_95"] == stockrefs._quantile7(expected_samples, .975)


def test_2022_stock_reader_preserves_yahoo_boundary_dividend(tmp_path):
    import json
    import zipfile
    from datetime import datetime
    from zoneinfo import ZoneInfo

    stock_zip = tmp_path / "stocks.zip"
    with zipfile.ZipFile(stock_zip, "w") as archive:
        archive.writestr("day_by_symbol/SPY_day.csv",
                         "date,open,close,dividend\n2022-12-30,100,101,0\n")
    zone = ZoneInfo("America/New_York")
    timestamps = [int(datetime(2023, 1, 3, 12, tzinfo=zone).timestamp())]
    boundary_ts = int(datetime(2023, 1, 3, 12, tzinfo=zone).timestamp())
    yahoo = {
        "chart": {"result": [{
            "meta": {"symbol": "SPY", "exchangeTimezoneName": "America/New_York"},
            "timestamp": timestamps,
            "indicators": {"quote": [{"open": [102], "close": [103]}]},
            "events": {"dividends": {"event": {"date": boundary_ts, "amount": 0.25}}},
        }]}
    }
    yahoo_path = tmp_path / "yahoo.json"
    yahoo_path.write_text(json.dumps(yahoo))

    stocks, boundary = stockrefs._read_old_2022_stocks(stock_zip, yahoo_path)

    assert boundary["boundary_date"] == "2023-01-03"
    assert stocks[date(2023, 1, 3)] == {"open": 102.0, "close": 103.0, "dividend": 0.25}


def _small_2019_option_row(symbol, root, strike, **overrides):
    return {
        "UnderlyingSymbol": root, "UnderlyingPrice": "280", "Exchange": "CBOE",
        "OptionSymbol": symbol, "OptionExt": "", "Type": "Call",
        "Expiration": "08/02/2019", "DataDate": "08/01/2019", "Strike": str(strike),
        "Last": "1", "Bid": "1", "Ask": "1.2", "Volume": "1", "OpenInterest": "1",
        "IV": "0.2", "Delta": "0.5", "Gamma": "0.01", "Theta": "-0.1", "Vega": "0.1",
        "AKA": symbol, **overrides,
    }


def _write_small_2019_archive(path, rows, member="L2_options_20190801.csv", fields=None):
    from zipfile import ZipFile

    headers = fields or list(stockrefs.legacy2019.OPTION_FIELDS)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    with ZipFile(path, "w") as archive:
        archive.writestr(member, stream.getvalue())


def test_fixed_2019_quote_index_matches_legacy_parser_on_small_archive(tmp_path):
    from collections import Counter
    from zipfile import ZipFile

    day, expiry = date(2019, 8, 1), date(2019, 8, 2)
    spy = "SPY190802C00200000"
    spxw = "SPXW190802C03000000"
    rows = [
        _small_2019_option_row(spy, "SPY", 200),
        _small_2019_option_row(spxw, "SPXW", 3000),
        _small_2019_option_row("IRRELEVANT", "OTHER", 1, DataDate="not-a-date", Expiration="bad"),
    ]
    path = tmp_path / "small.zip"
    _write_small_2019_archive(path, rows)

    actual, diagnostics = stockrefs._read_fixed_2019_quotes(path, {day: {spy: expiry, spxw: expiry}})
    expected = []
    with ZipFile(path) as archive:
        stockrefs.legacy2019._parse_option_file(
            archive, "L2_options_20190801.csv", day, Counter(), expected, set())

    assert actual == {(quote.contract, quote.quote_date): quote for quote in expected}
    assert diagnostics == {"selected_quote_count": 2, "selected_entry_dates": 1,
                          "selected_rows_scanned": 3, "mode": "FIXED_CONTRACT_DATES_ONLY"}


@pytest.mark.parametrize("change,match", [
    (lambda row: row.update(AKA="SPY190802C00200001"), "identity or values conflict"),
    (lambda row: row.update(DataDate="08/02/2019"), "identity or values conflict"),
    (lambda row: row.update(Strike="201"), "identity or values conflict"),
    (lambda row: row.update(Bid="2", Ask="1"), "identity or values conflict"),
])
def test_fixed_2019_quote_index_rejects_selected_identity_conflicts(tmp_path, change, match):
    day, expiry, symbol = date(2019, 8, 1), date(2019, 8, 2), "SPY190802C00200000"
    row = _small_2019_option_row(symbol, "SPY", 200)
    change(row)
    path = tmp_path / "bad.zip"
    _write_small_2019_archive(path, [row])
    with pytest.raises(ValueError, match=match):
        stockrefs._read_fixed_2019_quotes(path, {day: {symbol: expiry}})


def test_fixed_2019_quote_index_rejects_missing_and_duplicate_selected_rows(tmp_path):
    day, expiry = date(2019, 8, 1), date(2019, 8, 2)
    spy, spxw = "SPY190802C00200000", "SPXW190802C03000000"
    required = {day: {spy: expiry, spxw: expiry}}
    path = tmp_path / "missing.zip"
    _write_small_2019_archive(path, [_small_2019_option_row(spy, "SPY", 200)])
    with pytest.raises(ValueError, match="quotes missing"):
        stockrefs._read_fixed_2019_quotes(path, required)

    path = tmp_path / "duplicate.zip"
    selected = _small_2019_option_row(spy, "SPY", 200)
    _write_small_2019_archive(path, [selected, selected])
    with pytest.raises(ValueError, match="duplicate selected"):
        stockrefs._read_fixed_2019_quotes(path, {day: {spy: expiry}})


def test_fixed_2019_quote_index_rejects_unsafe_matching_member(tmp_path):
    day, expiry, symbol = date(2019, 8, 1), date(2019, 8, 2), "SPY190802C00200000"
    path = tmp_path / "unsafe.zip"
    _write_small_2019_archive(path, [_small_2019_option_row(symbol, "SPY", 200)],
                              member="nested/L2_options_20190801.csv")
    with pytest.raises(ValueError, match="unsafe fixed"):
        stockrefs._read_fixed_2019_quotes(path, {day: {symbol: expiry}})
