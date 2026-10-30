import hashlib
import csv
import json
import subprocess
import pytest
from pathlib import Path

from spyspx.morning_hedge_attribution import (
    COSTS, EXPECTED_MANIFEST_SHA256, _load_frozen_rows, _validate_protocol,
    SCENARIO_MAIN, SCENARIO_Q0,
    aggregate, atomic_publish, bootstrap, primitive, reconstruct_assignment,
    reconstruct_costs, reconstruct_q, residual_diagnostics, symmetric_frequency_payoff,
    tail_diagnostics, validate_distribution_rows, validate_stock_rows, verify_code_binding,
    verify_input_bindings, validate_output_path,
)


def _adapter_fixture(tmp_path, *, duplicate=None, mutate_cost=None, mutate_cash=None):
    records = [
        ("2023", "2023-01-02", "2023-01-03", "2023-01-04", 99.90, 100.02, 100.02, 100.01),
        ("2023", "2023-01-05", "2023-01-20", "2023-01-23", 100.02, 100.00, 100.00, 99.95),
        ("2025", "2025-01-02", "2025-01-03", "2025-01-06", 100.02, 99.90, 100.02, 100.03),
        ("2025", "2025-01-07", "2025-01-08", "2025-01-09", 99.90, 100.02, 100.00, 99.99),
    ]
    srcdir = tmp_path / "sources"
    srcdir.mkdir()
    stock_values = {}
    for _, entry, expiry, cover, entry_open, expiry_open, expiry_close, cover_open in records:
        stock_values[("109820", entry)] = (entry_open, 100.2, 99.8, 100.0)
        stock_values[("109820", expiry)] = (expiry_open, max(expiry_open, expiry_close) + .1,
                                               min(expiry_open, expiry_close) - .1, expiry_close)
        stock_values[("109820", cover)] = (cover_open, cover_open + .1, cover_open - .1, 100.0)
        for date in (entry, expiry, cover):
            stock_values[("108105", date)] = (1000., 1001., 999., 1000.)
    stock_path = srcdir / "stock.csv"
    with stock_path.open("w", newline="") as f:
        fields = ["secid", "date", "ticker", "index_flag", "cfadj", "open", "high", "low", "close"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for (secid, date), (o, h, l, c) in stock_values.items():
            spy = secid == "109820"
            w.writerow({"secid": secid, "date": date, "ticker": "SPY" if spy else "SPX",
                        "index_flag": "0" if spy else "1", "cfadj": "1", "open": o, "high": h,
                        "low": l, "close": c})
    distribution_path = srcdir / "distributions.csv"
    distribution_path.write_text("secid,record_date,ex_date,seq_num,ticker,index_flag,amount,adj_factor,frequency,approx_flag,cancel_flag,currency,distr_type,liquid_flag\n"
                                "109820,2023-01-01,2023-01-04,1,SPY,0,0.25,1,4,0,0,USD,1,0\n")

    repl_rows, legacy_rows, outcomes, selected23, selected25 = [], [], [], [], []
    ledgers23 = {SCENARIO_MAIN: [], SCENARIO_Q0: []}
    ledgers25 = {"open_itm_q1000": [], "unhedged_q0": []}
    for idx, (year, entry, expiry, cover, entry_open, expiry_open, expiry_close, cover_open) in enumerate(records):
        q = reconstruct_q(expiry_open, 100.)
        assigned = reconstruct_assignment(expiry_close, 100.)
        spy_bid, spxw_ask = ((.1, 2.) if idx % 2 else (.3, 1.))
        credit = 1000 * spy_bid - 100 * spxw_ask
        dividend = .25 if expiry < "2023-01-04" <= cover else 0.
        spxw_strike_milli = "100000"
        settlement = 101. if idx % 2 == 0 else 100.
        terminal = 100 * max(settlement - 100., 0.)
        fill = {"fill": "full_cross", "credit": credit, "spxw_leg_terminal_cash": terminal,
                "assigned": assigned, "dividend_carry_amount": 1000 * int(assigned) * dividend}
        wrappers = []
        for arm, quantity, scenario in (("open_itm_q1000", q, SCENARIO_MAIN), ("unhedged_q0", 0, SCENARIO_Q0)):
            # Independent fixture oracle: keep expected values separate from production helpers.
            residual = quantity - 1000 * int(assigned)
            hedge_days = ( __import__("datetime").date.fromisoformat(cover) - __import__("datetime").date.fromisoformat(expiry)).days
            exit_days = (__import__("datetime").date.fromisoformat(cover if assigned else expiry) - __import__("datetime").date.fromisoformat(entry)).days
            costs = {"option_fees": 7.15, "stock_fees": .005 * (quantity + abs(residual)),
                     "residual_short_borrow": max(-residual, 0) * expiry_close * .03 * hedge_days / 365,
                     "premium_debit_funding": max(-credit, 0) * .05 * exit_days / 365,
                     "hedge_funding": quantity * expiry_close * .05 * hedge_days / 365,
                     "stock_slippage": (quantity * expiry_close + abs(residual) * cover_open) / 10000}
            cash = {"credit": credit, "spxw_leg_terminal_cash": terminal, "spy_strike": 100.,
                    "assigned": assigned, "q": quantity, "costs": costs}
            terms = primitive(cash, expiry_close=expiry_close, next_open=cover_open, dividend=dividend)
            ledger = {"arm": arm, "q": quantity, "assigned": int(assigned), "residual_shares": residual,
                      "costs": costs, "gross_pnl": terms["option_baseline"] + terms["overnight"] + terms["dividend"],
                      "net_pnl": terms["net"], "overnight_price_contribution": terms["overnight"],
                      "dividend_cash": terms["dividend"], "stock_notional_close": quantity * expiry_close,
                      "stock_notional_cover": abs(residual * cover_open)}
            if mutate_cost == (year, arm):
                ledger["costs"]["stock_fees"] += .25
                ledger["net_pnl"] -= .25
            if year == "2023":
                repl_rows.append({"entry": entry, "expiry": expiry, "cover": cover,
                                  "scenario": scenario, "ledger": ledger, "fill_row": fill})
                ledgers23[scenario].append(ledger)
            else:
                legacy_rows.append({"period": "2025", "entry": entry, "expiry": expiry, "cover": cover,
                    "fill": "full_cross", "arm": arm, "funding": "gross_prefunding", "slippage_bp": 1,
                    "stress": False, **ledger})
                ledgers25[arm].append(ledger)
        pair = {"entry": entry, "expiry": expiry, "cover": cover,
                "spy": {"normalized_strike_milli": "100000", "normalized_best_bid": str(spy_bid)},
                "spxw": {"normalized_strike_milli": spxw_strike_milli, "normalized_best_offer": str(spxw_ask)}}
        if year == "2023":
            selected23.append({**pair, "selected": pair})
        else:
            selected25.append(pair)
            outcomes.append({"entry": entry, "expiry": expiry, "cover": cover, "spy_strike": 100., "spxw_pm_settlement": settlement,
                "fill_rows": [fill, {**fill, "fill": "midpoint"}, {**fill, "fill": "halfway"}]})

    def stats(ledgers):
        values = [float(r["net_pnl"]) for r in ledgers]
        return {"count": len(values), "mean": float(sum(values) / len(values)),
                "median": float(sorted(values)[len(values)//2] if len(values) % 2 else (sorted(values)[len(values)//2-1] + sorted(values)[len(values)//2]) / 2),
                "total": float(sum(values)), "win_fraction": sum(x > 0 for x in values) / len(values)}
    summaries23 = {scenario: {"net_pnl": stats(rows)} for scenario, rows in ledgers23.items()}
    summaries25 = []
    for year, groups in (("2025", ledgers25),):
        for arm, rows in groups.items():
            summaries25.append({"period": year, "arm": arm, "fill": "full_cross", "funding": "gross_prefunding",
                "slippage_bp": 1, "stress": False, "count": len(rows), "mean": stats(rows)["mean"],
                "median": stats(rows)["median"], "win_rate": stats(rows)["win_fraction"],
                "mean_dividend_cash": 0., "mean_overnight_price_contribution": sum(r["overnight_price_contribution"] for r in rows)/len(rows),
                "mean_cost_components": {c: sum(r["costs"][c] for r in rows)/len(rows) for c in COSTS}})
    docs = {
        "legacy_ledgers": legacy_rows,
        "legacy_summaries": summaries25,
        "legacy_outcomes": outcomes,
        "legacy_selection": {"selected_pairs": selected25},
        "replication_selection": {"selected_pairs": selected23},
        "replication_ledgers": repl_rows,
        "replication_summary": {"scenario_summaries": summaries23},
    }
    if duplicate in ("legacy", "legacy_main", "legacy_q0"):
        target_arm = "unhedged_q0" if duplicate == "legacy_q0" else "open_itm_q1000"
        row = next(r for r in legacy_rows if r["arm"] == target_arm)
        docs["legacy_ledgers"].append(dict(row))
    if duplicate == "selection23":
        docs["replication_selection"]["selected_pairs"].append(dict(selected23[0]))
    if duplicate == "outcome":
        docs["legacy_outcomes"].append(dict(outcomes[0]))
    if duplicate in ("scenario23", "scenario23_q0"):
        target_scenario = SCENARIO_Q0 if duplicate == "scenario23_q0" else SCENARIO_MAIN
        row = next(r for r in repl_rows if r["scenario"] == target_scenario)
        docs["replication_ledgers"].append(dict(row))
    if mutate_cash:
        year, primitive_name = mutate_cash
        if year == "2023":
            target = next(r for r in repl_rows if r["scenario"] == SCENARIO_MAIN)
            target["fill_row"][primitive_name] += 1.
            for row in repl_rows:
                if row["entry"] == target["entry"]:
                    row["ledger"]["net_pnl"] += 1.
        else:
            target = next(o for o in outcomes if o["entry"] == "2025-01-02")
            full = next(f for f in target["fill_rows"] if f["fill"] == "full_cross")
            full[primitive_name] += 1.
            for row in legacy_rows:
                if row["entry"] == target["entry"]:
                    row["net_pnl"] += 1.
    roles = {}
    for role, doc in docs.items():
        path = srcdir / f"{role}.json"
        path.write_text(json.dumps(doc))
        roles[role] = {"path": str(path)}
    roles["stock_prices"] = {"path": str(stock_path)}
    settle_paths = {}
    for suffix in ("W", "M", "S"):
        path = srcdir / f"cboe_{suffix}.json"
        if suffix == "W":
            rows = [{"trading_symbol": "SPXW", "settlement_symbol": "SPX", "expiration_date": "2023-01-03", "settlement_value": 101.}]
        elif suffix == "M":
            rows = [{"trading_symbol": "SPXW", "settlement_symbol": "SPX", "expiration_date": "2023-01-13", "settlement_value": 102.}]
        else:
            rows = [{"trading_symbol": "SPXW", "settlement_symbol": "SPX", "expiration_date": "2023-01-20", "settlement_value": 100.},
                    {"trading_symbol": "SPX", "settlement_symbol": "SET", "expiration_date": "2023-01-20", "settlement_value": 999.}]
        path.write_text(json.dumps({"data": rows}))
        settle_paths[f"cboe_{suffix}_2023"] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    replication_manifest_path = srcdir / "replication-run-manifest.json"
    replication_manifest_path.write_text(json.dumps({"inputs": settle_paths}))
    roles["replication_manifest"] = {"path": str(replication_manifest_path)}
    manifest = {"sources": roles, "transitive_inputs": {"wrds_distributions": {
        "path": str(distribution_path), "sha256": hashlib.sha256(distribution_path.read_bytes()).hexdigest()}, **settle_paths}}
    return manifest


def test_primitive_closes_and_keeps_assignment_residual():
    row = {"credit": 120.0, "spxw_leg_terminal_cash": -20.0, "spy_strike": 100.0,
           "q": 700, "assigned": True, "costs": {k: 0.0 for k in COSTS}}
    row["costs"]["option_fees"] = 2
    row["costs"]["hedge_funding"] = 3
    p = primitive(row, expiry_close=101, next_open=102, dividend=.5)
    assert p["option_baseline"] == -900
    assert p["overnight"] == -300
    assert p["dividend"] == -150
    assert p["net"] == sum(p[k] for k in ("option_baseline", "overnight", "dividend", *[f"negative_{c}" for c in COSTS]))
    missing = dict(row, costs={k: v for k, v in row["costs"].items() if k != "option_fees"})
    with pytest.raises(KeyError):
        primitive(missing, expiry_close=101, next_open=102, dividend=.5)
    bad = dict(row, costs={**row["costs"], "stock_fees": float("nan")})
    with pytest.raises(ValueError, match="non-finite"):
        primitive(bad, expiry_close=101, next_open=102, dividend=.5)


def test_assignment_boundary_and_ohlc_duplicate_checks():
    assert reconstruct_q(100.01 - 5e-11, 100) == 1000
    assert reconstruct_q(100.009, 100) == 0
    assert reconstruct_assignment(100.01 - 5e-11, 100) is True
    assert reconstruct_assignment(100.01 - 5e-10, 100) is False
    rows = [{"secid": "109820", "ticker": "SPY", "index_flag": "0", "cfadj": "1", "date": "2025-01-02", "open": 10, "high": 12, "low": 9, "close": 11}]
    assert validate_stock_rows(rows)[("109820", "2025-01-02")]["close"] == 11
    with pytest.raises(ValueError, match="duplicate"):
        validate_stock_rows(rows * 2)
    with pytest.raises(ValueError, match="OHLC"):
        validate_stock_rows([{**rows[0], "high": 10.5}])
    with pytest.raises(ValueError, match="identity"):
        validate_stock_rows([{**rows[0], "cfadj": "2"}])


def test_distribution_identity_duplicate_and_cash_admission():
    event = {"secid": "109820", "record_date": "2025-01-01", "ticker": "SPY", "index_flag": "0", "ex_date": "2025-01-03",
             "seq_num": "1", "amount": "0.25", "adj_factor": "1", "frequency": "4", "approx_flag": "0",
             "cancel_flag": "0", "currency": "USD", "distr_type": "1", "liquid_flag": "0"}
    accepted = validate_distribution_rows([event])
    assert accepted[0]["amount"] == .25
    assert validate_distribution_rows([{**event, "cancel_flag": "1"}]) == []
    with pytest.raises(ValueError, match="duplicate"):
        validate_distribution_rows([event, event])
    with pytest.raises(ValueError, match="identity"):
        validate_distribution_rows([{**event, "ticker": "OTHER"}])
    with pytest.raises(ValueError, match="identity"):
        validate_distribution_rows([{**event, "secid": "999999"}])
    with pytest.raises(ValueError, match="non-finite"):
        validate_distribution_rows([{**event, "amount": "nan"}])
    assert validate_distribution_rows([{**event, "frequency": "6"}]) == []
    assert validate_distribution_rows([{**event, "adj_factor": "1.1"}]) == []
    assert validate_distribution_rows([{**event, "amount": "0"}]) == []


def test_quote_and_terminal_cash_reconstruction_uses_normalized_units():
    from spyspx.morning_hedge_attribution import rebuild_full_cross_credit, rebuild_spxw_terminal
    selected = {"spy": {"normalized_best_bid": "0.3"}, "spxw": {"normalized_best_offer": "1.0"}}
    assert rebuild_full_cross_credit(selected) == pytest.approx(200.)
    assert rebuild_spxw_terminal(101., "100000") == pytest.approx(100.)
    assert rebuild_spxw_terminal(99., "100000") == 0.


def test_premium_funding_uses_assignment_exit_date():
    assigned = reconstruct_costs(q=1000, assigned=True, credit=-100., expiry_close=100., cover_open=101.,
                                entry="2025-01-01", expiry="2025-01-03", cover="2025-01-06")
    unassigned = reconstruct_costs(q=1000, assigned=False, credit=-100., expiry_close=100., cover_open=101.,
                                  entry="2025-01-01", expiry="2025-01-03", cover="2025-01-06")
    assert assigned["premium_debit_funding"] == pytest.approx(100 * .05 * 5 / 365)
    assert unassigned["premium_debit_funding"] == pytest.approx(100 * .05 * 2 / 365)


def test_missing_residual_group_is_explicit_and_decomposition_closes():
    rows = [{"residual_q": 1, "overnight": 3, "net": 4, "overnight_price_change": .1, "overnight_return": .001}]
    result = residual_diagnostics(rows)
    assert result["overnight"]["short"]["conditional_mean"] is None
    d = symmetric_frequency_payoff(.2, 4, .4, 8)
    assert d["status"] == "defined" and d["sum"] == pytest.approx(2.4)
    assert symmetric_frequency_payoff(0, None, .4, 8)["status"] == "undefined_zero_group_support"


def test_tail_tie_order_and_winsorization():
    rows = [{"net": 1, "expiry": "2025-01-02", "entry": "b", "cover": "x"},
            {"net": 1, "expiry": "2025-01-01", "entry": "a", "cover": "x"}]
    out = tail_diagnostics(rows)
    assert out["symmetric_removals"]["1"]["status"] == "undefined_insufficient_rows"
    assert out["top_removals"]["1"]["retained_count"] == 1
    assert out["bottom_removals"]["1"]["retained_count"] == 1
    assert out["winsorized_5_95_mean_nonadditive"] == 1


def test_bootstrap_cluster_draws_are_repeatable_and_close():
    def rows():
        return [{"expiry": "2023-01-02", "components": {"option_baseline": 1., "net": 3.}},
                {"expiry": "2023-01-03", "components": {"option_baseline": 2., "net": 4.}},
                {"expiry": "2023-01-10", "components": {"option_baseline": 5., "net": 7.}}]
    a = bootstrap(rows(), rows(), comparison_index=0, draws=8)
    b = bootstrap(rows(), rows(), comparison_index=0, draws=8)
    assert a["indices_sha256"] == b["indices_sha256"]
    assert a["dimensions"]["2023"] == [8, 2]
    assert a["draws_by_component"]["net"] == pytest.approx(a["draws_by_component"]["option_baseline"])
    cluster_values = [[1., 2.], [5.]]
    for selected, observed in zip(a["sampled_cluster_indices"]["2023"], a["means_by_period"]["2023"]["option_baseline"]):
        sampled = [v for cluster_id in selected for v in cluster_values[cluster_id]]
        assert observed == pytest.approx(sum(sampled) / len(sampled))


def test_frozen_protocol_fails_closed_on_each_method_change():
    p = {"input_manifest_sha256": EXPECTED_MANIFEST_SHA256, "scenario": "open_itm_q1000|full_cross|base|1bp|gross_prefunding",
         "draws": 10000, "seed_base": 20261030, "quantile_method": "type7_linear", "cluster_unit": "ISO year-week",
         "sampling": "independent years; ratio of sampled row sums to sampled row counts", "dividends": "included",
         "periods": {"2023": "2023-01-01/2023-12-31", "2023_common": "2023-01-01/2023-08-31", "2025": "2025-01-01/2025-08-31"},
         "rng": "numpy.default_rng; draw 2023 integer matrix first, then 2025 matrix from the same generator",
         "status": "FROZEN", "actual_run_authorized": True}
    _validate_protocol(p, EXPECTED_MANIFEST_SHA256)
    for change in ({"draws": 9999}, {"scenario": "other"}, {"actual_run_authorized": False}):
        with pytest.raises(ValueError):
            _validate_protocol({**p, **change}, EXPECTED_MANIFEST_SHA256)


def test_input_binding_and_loaded_code_git_guards(tmp_path):
    data = tmp_path / "input.json"
    data.write_text("frozen")
    binding = {"cboe_W_2023": {"path": str(data), "sha256": hashlib.sha256(b"frozen").hexdigest()}}
    assert verify_input_bindings(binding)["cboe_W_2023"] == binding["cboe_W_2023"]["sha256"]
    data.write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_input_bindings(binding)
    source = tmp_path / "source.py"
    source.write_text("code")
    assert verify_code_binding(source, b"code", "abc", "abc", "", loaded_path=source,
                                loaded_sha256=hashlib.sha256(b"code").hexdigest()) == hashlib.sha256(b"code").hexdigest()
    with pytest.raises(ValueError, match="committed blob"):
        verify_code_binding(source, b"different", "abc", "abc", "", loaded_path=source,
                            loaded_sha256=hashlib.sha256(b"code").hexdigest())
    with pytest.raises(ValueError, match="Git identity"):
        verify_code_binding(source, b"code", "abc", "abc", "M file", loaded_path=source,
                            loaded_sha256=hashlib.sha256(b"code").hexdigest())
    with pytest.raises(ValueError, match="Git identity"):
        verify_code_binding(source, b"code", "abc", "def", "", loaded_path=source,
                            loaded_sha256=hashlib.sha256(b"code").hexdigest())
    with pytest.raises(ValueError, match="committed blob"):
        verify_code_binding(source, b"code", "abc", "abc", "", loaded_path=source,
                            loaded_sha256="0" * 64)


def test_output_path_rejects_existing_and_outside_directories(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("planning/\n")
    allowed = root / "planning/morning-hedge-attribution-20261030"
    allowed.mkdir(parents=True)
    validate_output_path(allowed / "fresh", root=root)
    (allowed / "exists").mkdir()
    with pytest.raises(ValueError, match="fresh child"):
        validate_output_path(allowed / "exists", root=root)
    with pytest.raises(ValueError, match="fresh child"):
        validate_output_path(root / "other" / "out", root=root)
    (root / ".gitignore").write_text("")
    unignored = allowed / "visible"
    with pytest.raises(ValueError, match="Git-ignored"):
        validate_output_path(unignored, root=root)


@pytest.mark.parametrize("source_name", ["cboe_W_2023", "cboe_M_2023", "cboe_S_2023"])
def test_atomic_output_rechecks_inputs_after_manifest_write(tmp_path, source_name):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("planning/\n")
    parent = root / "planning/morning-hedge-attribution-20261030"
    parent.mkdir(parents=True)
    output = parent / "run-001"
    bound = tmp_path / f"{source_name}.json"
    bound.write_text("original")
    digest = hashlib.sha256(b"original").hexdigest()

    def manifest_builder(hashes):
        return json.dumps({"output_sha256": hashes})

    def mutate_after_write(stage):
        assert (stage / "run-manifest.json").is_file()
        bound.write_text("mutated")

    def final_check(stage, hashes):
        assert verify_input_bindings({source_name: {"path": str(bound), "sha256": digest}})[source_name] == digest

    with pytest.raises(ValueError, match="hash mismatch"):
        atomic_publish(output, {"aggregate.json": "{}"}, "run-manifest.json", manifest_builder,
                       final_check, root=root, after_manifest_write=mutate_after_write)
    assert not output.exists()
    assert list(parent.iterdir()) == []


def test_atomic_output_renames_complete_ignored_bundle(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("planning/\n")
    parent = root / "planning/morning-hedge-attribution-20261030"
    parent.mkdir(parents=True)
    output = parent / "run-002"
    core = {"aggregate.json": "{}", "private-primitive-rows.json": "[]"}

    def build(hashes):
        return json.dumps({"output_sha256": hashes})

    def verify(stage, hashes):
        assert json.loads((stage / "run-manifest.json").read_text())["output_sha256"] == hashes
        assert {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in core} == hashes

    atomic_publish(output, core, "run-manifest.json", build, verify, root=root)
    assert sorted(p.name for p in output.iterdir()) == ["aggregate.json", "private-primitive-rows.json", "run-manifest.json"]


@pytest.mark.parametrize(
    ("status", "authorized", "valid"),
    [("PREPARED", False, False), ("FROZEN", False, False), ("FROZEN", True, True)],
)
def test_prepared_protocol_stays_unauthorized(status, authorized, valid):
    manifest_hash = "a" * 64
    protocol = {
        "input_manifest_sha256": manifest_hash,
        "scenario": "open_itm_q1000|full_cross|base|1bp|gross_prefunding",
        "draws": 10000,
        "seed_base": 20261030,
        "quantile_method": "type7_linear",
        "cluster_unit": "ISO year-week",
        "sampling": "independent years; ratio of sampled row sums to sampled row counts",
        "dividends": "included",
        "periods": {
            "2023": "2023-01-01/2023-12-31",
            "2023_common": "2023-01-01/2023-08-31",
            "2025": "2025-01-01/2025-08-31",
        },
        "rng": "numpy.default_rng; draw 2023 integer matrix first, then 2025 matrix from the same generator",
        "status": status,
        "actual_run_authorized": authorized,
    }
    if valid:
        _validate_protocol(protocol, manifest_hash)
    else:
        with pytest.raises(ValueError, match="protocol is not frozen and explicitly authorized"):
            _validate_protocol(protocol, manifest_hash)


def test_synthetic_source_adapters_cover_q_a_states_and_rebuild_both_cost_ledgers(tmp_path):
    source_manifest = _adapter_fixture(tmp_path)
    rows23, rows25, private = _load_frozen_rows(source_manifest, expected_counts={"2023": 2, "2025": 2})
    assert len(rows23) == len(rows25) == 2
    assert private["q_a_state_counts"] == {"q0_A0": 1, "q0_A1": 1, "q1000_A0": 1, "q1000_A1": 1}
    assert {r["state"] for r in private["private_rows"]} == set(private["q_a_state_counts"])
    assert all(all(r["row_checks"].values()) for r in private["private_rows"])
    first = next(r for r in private["private_rows"] if r["state"] == "q1000_A1")
    assert first["entry"] != first["expiry"]
    assert first["q"] == 1000
    assert first["expiry_spy_open"] >= first["spy_strike"] + .01 - 1e-10


@pytest.mark.parametrize("duplicate", ["legacy_main", "legacy_q0", "selection23", "outcome", "scenario23", "scenario23_q0"])
def test_adapter_rejects_duplicate_rows_before_index_overwrite(tmp_path, duplicate):
    with pytest.raises(ValueError, match="duplicate"):
        _load_frozen_rows(_adapter_fixture(tmp_path, duplicate=duplicate), expected_counts={"2023": 2, "2025": 2})


@pytest.mark.parametrize("mutation", [("2023", "open_itm_q1000"), ("2025", "unhedged_q0")])
def test_adapter_rejects_mutated_cost_even_when_ledger_net_is_rebalanced(tmp_path, mutation):
    with pytest.raises(ValueError, match="reconstructed .* cost mismatch"):
        _load_frozen_rows(_adapter_fixture(tmp_path, mutate_cost=mutation), expected_counts={"2023": 2, "2025": 2})


@pytest.mark.parametrize("mutation", [("2023", "credit"), ("2023", "spxw_leg_terminal_cash"),
                                       ("2025", "credit"), ("2025", "spxw_leg_terminal_cash")])
def test_adapter_rejects_tampered_source_cash_even_when_ledger_net_is_rebalanced(tmp_path, mutation):
    with pytest.raises(ValueError, match="rebuilt full-cross credit mismatch|rebuilt SPXW terminal cash mismatch"):
        _load_frozen_rows(_adapter_fixture(tmp_path, mutate_cash=mutation), expected_counts={"2023": 2, "2025": 2})


def test_synthetic_aggregate_closes_without_private_cohort_counts():
    def row(year, month, residual, overnight, baseline):
        components = {"option_baseline": baseline, "overnight": overnight, "dividend": 0.0,
                      **{f"negative_{c}": 0.0 for c in COSTS}}
        net = sum(components.values())
        components["net"] = net
        return {"expiry": f"{year}-{month:02d}-05", "entry": f"{year}-{month:02d}-04", "cover": f"{year}-{month:02d}-08",
                "residual_q": residual, "overnight": overnight, "overnight_price_change": .1,
                "overnight_return": .001, "net": net, "components": components}
    a = [row(2023, 1, -1000, 2., 3.), row(2023, 2, 0, 0., 4.)]
    b = [row(2025, 1, 1000, 5., 6.), row(2025, 2, 0, 0., 7.)]
    report, draws = aggregate(a, b, draws=16)
    bridge = report["mean_bridge_2025_minus_2023"]["full"]
    assert bridge["net"] == pytest.approx(sum(bridge[k] for k in bridge if k != "net"))
    assert report["residual_frequency_payoff_2025_minus_2023"]["full"]["short"]["status"] == "undefined_zero_group_support"
    assert draws["full"]["draws"] == 16
