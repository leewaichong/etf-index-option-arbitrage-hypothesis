"""Synthetic boundary tests for the isolated 2023 hedge adapter."""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from datetime import date

import pytest

from spyspx import morning_hedge_2023 as morning
from spyspx import optionmetrics_replication as replication
from spyspx import overnight_hedge as hedge


def _normalized(root: str, strike: int, bid: float, ask: float, optionid: str, style: str):
    expiry = "2023-01-04"
    ymd = "230104"
    return {
        "normalized_quote_date": "2023-01-03", "normalized_expiry_date": expiry,
        "normalized_symbol": f"{root}{ymd}C{strike:08d}", "normalized_cp_flag": "C",
        "normalized_strike_milli": str(strike), "normalized_best_bid": str(bid),
        "normalized_best_offer": str(ask), "normalized_am_settlement": "0",
        "normalized_contract_size": "100", "normalized_special_settlement": "",
        "normalized_exercise_style": style, "normalized_underlying": "SPY" if root == "SPY" else "SPX",
        "normalized_option_id": optionid, "symbol": f"{root} 230104C{strike}",
    }


def _synthetic_pair(spy_close=100.05):
    selected = {
        "entry": "2023-01-03", "expiry": "2023-01-04", "cover": "2023-01-05",
        "spy": _normalized("SPY", 100000, 2.0, 2.2, "spy-id", "A"),
        "spxw": _normalized("SPXW", 4000000, 20.0, 20.2, "spxw-id", "E"),
        "spy_entry_close": 100.0, "official_spx_entry_close": 4000.0,
        "moneyness_mismatch": 0.0,
    }
    fills, controls = replication.build_fill_rows(
        selected, {"spy_expiry_close": spy_close, "spy_cover_open": 99.75,
                   "spxw_pm_settlement": 4000.0},
        [{"ex_date": date(2023, 1, 5), "amount": .25}],
    )
    return {
        "period": "2023", "entry": selected["entry"], "expiry": selected["expiry"],
        "cover": selected["cover"], "spy_contract": selected["spy"]["normalized_symbol"],
        "spxw_contract": selected["spxw"]["normalized_symbol"], "spy_strike": 100.0,
        "spxw_strike": 4000.0, "official_spx_expiry_close": 4000.0,
        "spxw_pm_settlement": 4000.0, "spy_open": 100.01, "spy_close": 100.05,
        "cover_open": 99.75, "assigned": spy_close >= 100.0 + .01 - 1e-10,
        "interval_events": [{"ex_date": date(2023, 1, 5), "amount": .25}],
        "fill_rows": fills, "controls": controls,
    }


@pytest.mark.skipif(not (morning.repo_root() / morning.CALENDAR_PATH).is_file(), reason="requires private frozen 2023 calendar fixture not distributed in the public checkout")
def test_frozen_calendar_contract_is_exactly_196_pairs_and_588_fills():
    calendar = json.loads((morning.repo_root() / morning.CALENDAR_PATH).read_text())
    assert calendar["expected_count"] == 196
    assert calendar["expected_fill_rows"] == 588
    assert len(calendar["expected_pairs"]) == 196
    assert calendar["expected_pairs"][0] == {"entry": "2023-01-03", "expiry": "2023-01-04", "cover": "2023-01-05"}
    assert calendar["expected_pairs"][-1]["cover"] == "2024-01-02"


@pytest.mark.skipif(not (morning.repo_root() / morning.CALENDAR_PATH).is_file(), reason="requires private frozen 2023 calendar fixture not distributed in the public checkout")
def test_frozen_expected_pairs_reject_missing_or_changed_calendar_membership(monkeypatch):
    calendar_path = morning.repo_root() / morning.CALENDAR_PATH
    calendar = calendar_path.read_bytes()
    obj = json.loads(calendar)
    sessions = {date.fromisoformat(x[k]) for x in obj["expected_pairs"] for k in ("entry", "expiry", "cover")}
    # The 2023 calendar validator calls the shared pure tuple validator, preserving all 196 dates.
    checked = replication._validate_expected_pairs(
        {"expected_count": 196, "expected_pairs": obj["expected_pairs"]}, sessions)
    assert len(checked) == 196
    with pytest.raises(ValueError, match="count"):
        replication._validate_expected_pairs({"expected_count": 195, "expected_pairs": obj["expected_pairs"]}, sessions)


@pytest.mark.skipif(not (morning.repo_root() / morning.CALENDAR_PATH).is_file(), reason="requires private frozen 2023 calendar fixture not distributed in the public checkout")
def test_missing_terminal_sources_retain_all_196_coverage_rows_and_no_payoffs():
    calendar = json.loads((morning.repo_root() / morning.CALENDAR_PATH).read_text())
    expected = [{key: date.fromisoformat(item[key]) for key in ("entry", "expiry", "cover")}
                for item in calendar["expected_pairs"]]
    selection = {"selected_pairs": [{"entry": item["entry"].isoformat(), "selected": None}
                                    for item in expected]}
    coverage, rows = morning._coverage_rows(selection, expected, {}, {}, {}, [], set())
    assert len(coverage) == 196
    assert not any(item["complete"] for item in coverage)
    assert rows == []
    assert all("selected_pair" in item["missing_inputs"] for item in coverage)


@pytest.mark.skipif(not (morning.repo_root() / morning.CALENDAR_PATH).is_file(), reason="requires private frozen 2023 calendar fixture not distributed in the public checkout")
def test_unsupported_action_is_retained_as_a_coverage_failure():
    calendar = json.loads((morning.repo_root() / morning.CALENDAR_PATH).read_text())
    expected = [{key: date.fromisoformat(item[key]) for key in ("entry", "expiry", "cover")}
                for item in calendar["expected_pairs"]]
    selection = {"selected_pairs": [{"entry": item["entry"].isoformat(), "selected": None}
                                    for item in expected]}
    unknown = {"ex_date": date(2023, 1, 4), "amount": .25, "adj_factor": 1.0,
               "distr_type": "?", "frequency": "3", "currency": "USD",
               "approx_flag": "0", "cancel_flag": "0", "liquid_flag": "0"}
    coverage, outcomes = morning._coverage_rows(selection, expected, {}, {}, {}, [unknown], set())
    assert "unsupported_distribution_event" in coverage[0]["missing_inputs"]
    assert outcomes == []


def test_action_validation_interval_and_hedge_dividend_interval_are_distinct():
    pair = _synthetic_pair()
    dates = [date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)]
    actions = [{"ex_date": day, "amount": amount, "adj_factor": 1.0, "distr_type": "1",
                "frequency": "4", "currency": "USD", "approx_flag": "0",
                "cancel_flag": "0", "liquid_flag": "0"}
               for day, amount in zip(dates, (.1, .2, .3))]
    expected = [{"entry": date(2023, 1, 3), "expiry": date(2023, 1, 4), "cover": date(2023, 1, 5)}]
    for assigned in (False, True):
        pair["assigned"] = assigned
        selected = {"entry": pair["entry"], "expiry": pair["expiry"], "cover": pair["cover"],
                    "spy": _normalized("SPY", 100000, 2, 2.2, "spy-id", "A"),
                    "spxw": _normalized("SPXW", 4000000, 20, 20.2, "spxw-id", "E"),
                    "spy_entry_close": 100.0, "official_spx_entry_close": 4000.0,
                    "moneyness_mismatch": 0.0}
        pair["assigned"] = assigned
        close = 100.02 if assigned else 100.0
        prices = {(replication.SECURITY_IDS["SPY"], day):
                  {"open": 100.0, "close": close if day == date(2023, 1, 4) else 100.0, "cfadj": 1.0}
                  for day in dates}
        selection = {"selected_pairs": [{"entry": "2023-01-03", "selected": selected}]}
        coverage, computed = morning._coverage_rows(selection, expected, prices,
            {dates[0]: 4000.0, dates[1]: 4000.0}, {dates[1]: {"value": 4000.0}}, actions, set(dates))
        assert coverage[0]["entry_to_expiry_dividend_exposure"]
        assert coverage[0]["relevant_action_count"] == 2
        assert computed[0]["interval_events"] == actions[1:]
        assert [event["ex_date"] for event in computed[0]["carry_events"]] == [dates[2]]
        assert computed[0]["hedge_dividend_amount"] == pytest.approx(.3)


def test_shared_raw_admission_rejects_normalizer_hard_failures_and_projection_mismatch(monkeypatch):
    records = {name: {"data": b"{}"} for name in
               ("quotes_2023", "quote_source_metadata", "quote_identity_metadata", "projection_2023")}
    records["quote_source_metadata"]["data"] = json.dumps({"query": {
        "quote_start": "2023-01-01", "quote_end": "2023-12-31", "compression": "gzip"}}).encode()
    selection = {"selected_pairs": [{"entry": "2023-01-03", "selected": {"symbol": "fixed"}}]}
    monkeypatch.setattr(morning.normalizer, "normalize", lambda *_: {"hard_failure_count": 1})
    with pytest.raises(ValueError, match="hard source/identity"):
        morning._admit_raw_sources(records)
    assert selection["selected_pairs"][0]["selected"] == {"symbol": "fixed"}
    clean = {"hard_failure_count": 0, "normalized_rows": []}
    monkeypatch.setattr(morning.normalizer, "normalize", lambda *_: clean)
    monkeypatch.setattr(replication, "_projection_check", lambda *_: {"projection_consistent": False})
    with pytest.raises(ValueError, match="projection control"):
        morning._admit_raw_sources(records)
    assert selection["selected_pairs"][0]["selected"] == {"symbol": "fixed"}


def test_source_admission_lists_each_incomplete_component():
    expected = [{"expiry": date(2023, 1, 4)}]
    blockers, missing = morning._admission_blockers(
        {"selected_count": 0, "missing_selection_count": 1}, [{"reason": "unsupported"}],
        {"conflicting_expiries": {"2023-01-04": 1}}, expected, {})
    assert blockers == ["missing_entry_selections", "unsupported_distribution_events",
                        "conflicting_settlements", "missing_settlements"]
    assert missing == ["2023-01-04"]


def test_entry_selector_has_no_terminal_or_future_assignment_inputs():
    parameters = set(inspect.signature(replication.select_pairs).parameters)
    assert parameters == {"quotes", "pairs", "spy_prices", "spx_prices"}


def test_open_arm_uses_only_frozen_strike_and_preserves_tolerance():
    assert hedge.q_for_arm("open_itm_q1000", False, 100.01 - 5e-11, 100.0) == 1000
    assert hedge.q_for_arm("open_itm_q1000", True, 100.009, 100.0) == 0
    assert hedge.q_for_arm("open_itm_q1000", False, 100.009, 100.0) == 0
    assert morning.ARMS == ("unhedged_q0", "fixed500longshares", "fixed1000longshares",
                            "open_itm_q1000", "assignment_oracle_q1000A")


def test_all_five_arms_reuse_ledger_parity_and_keep_three_fills():
    ledgers, grouped = morning._build_ledgers([_synthetic_pair()])
    assert len(ledgers) == 3
    assert {row["fill"] for row in ledgers} == set(morning.FILLS)
    for row in ledgers:
        assert set(row["arms"]) == set(morning.ARMS)
        assert row["arms"]["open_itm_q1000"]["q"] == 1000
        assert row["arms"]["assignment_oracle_q1000A"]["residual_shares"] == 0
    scenarios = grouped["scenarios"]
    assert len(scenarios) == 5 * 3 * 2 * 3 * 2
    zero = scenarios[morning._scenario_key("unhedged_q0", "full_cross", False, 0, "gross_prefunding")][0]["ledger"]
    q1000 = scenarios[morning._scenario_key("fixed1000longshares", "full_cross", False, 0, "gross_prefunding")][0]["ledger"]
    expected = 1000 * (99.75 - 100.05 + .25)
    assert q1000["gross_pnl"] - zero["gross_pnl"] == pytest.approx(expected)
    summary = morning._summarize_ledgers(ledgers, scenarios, draws=5)
    key = morning._scenario_key("unhedged_q0", "full_cross", False, 1, "gross_prefunding")
    intervals = summary["scenario_summaries"][key]["confidence_intervals"]
    assert intervals[f"{key}:net_pnl:absolute"]["mean"] is not None
    assert intervals[f"{key}:net_pnl:paired_vs_q0"]["ci95_type7"] == [0.0, 0.0]
    assert "2023-01" in summary["scenario_summaries"][key]["month_cohorts"]


@pytest.mark.skipif(not (morning.repo_root() / morning.CALENDAR_PATH).is_file(), reason="requires private frozen 2023 calendar fixture not distributed in the public checkout")
def test_complete_synthetic_196_pair_grid_produces_exactly_588_fill_rows():
    calendar = json.loads((morning.repo_root() / morning.CALENDAR_PATH).read_text())
    assert len(calendar["expected_pairs"]) == 196
    samples = [_synthetic_pair() for _ in calendar["expected_pairs"]]
    ledgers, _ = morning._build_ledgers(samples)
    assert len(ledgers) == 588
    assert all(len(row["scenario_ledgers"]) == 60 for row in ledgers)
    assert sum(len(row["scenario_ledgers"]) for row in ledgers) == 35_280
    cases = morning._case_rows(ledgers)
    assert len(cases) == 35_280
    assert all({"entry", "expiry", "cover", "fill", "scenario", "ledger"}.issubset(case) for case in cases)
    assert all("open_itm_q1000" in row["arms"] for row in ledgers)
    primary = ledgers[0]["arms"]["open_itm_q1000"]
    assert primary["costs"]["stock_slippage"] != 0
    assert morning._summary([1, 3])["sample_standard_deviation"] == pytest.approx(2 ** .5)


def test_q0_and_assignment_oracle_identities_hold_for_assigned_and_unassigned_rows():
    assigned = _synthetic_pair()
    rows, _ = morning._build_ledgers([assigned])
    for row in rows:
        primary = row["arms"]["assignment_oracle_q1000A"]
        fill = row["fill_row"]
        assert primary["gross_pnl"] == pytest.approx(fill["conditional_close_mark_pnl"])
        assert row["arms"]["unhedged_q0"]["residual_shares"] == -1000
    unassigned = _synthetic_pair(spy_close=100.005)
    unassigned["spy_open"] = 99.99
    rows, _ = morning._build_ledgers([unassigned])
    assert all(row["arms"]["open_itm_q1000"]["q"] == 0 for row in rows)


def test_pm_parser_accepts_identical_duplicates_and_drops_conflicts():
    row = {"trading_symbol": "SPXW", "settlement_symbol": "SPX",
           "expiration_date": "2023-01-04", "settlement_value": 4000.0}
    records = {name: {"data": json.dumps({"data": [row]}).encode()}
               for name in ("cboe_W_2023", "cboe_M_2023", "cboe_S_2023")}
    parsed, _ = morning._parse_cboe_pm(records)
    assert parsed[date(2023, 1, 4)]["value"] == 4000
    records["cboe_S_2023"] = {"data": json.dumps({"data": [{**row, "settlement_value": 4001}]}).encode()}
    parsed, diagnostic = morning._parse_cboe_pm(records)
    assert date(2023, 1, 4) not in parsed
    assert diagnostic["conflicting_expiries"] == {"2023-01-04": 1}


@pytest.mark.skipif(not ((morning.repo_root() / morning.CALENDAR_PATH).is_file() and (morning.repo_root() / morning.PROTOCOL_PATH).is_file()), reason="requires private frozen 2023 calendar and protocol fixtures not distributed in the public checkout")
def test_manifest_requires_all_fixed_roles_and_documented_acquisition(tmp_path):
    manifest = {"status": "FROZEN_NOT_RUN", "files": {}}
    for role in morning.REQUIRED_ROLES:
        path = tmp_path / f"{role}.csv"
        path.write_bytes(role.encode())
        manifest["files"][role] = {"path": str(path), "bytes": len(role), "sha256": hashlib.sha256(role.encode()).hexdigest(),
                                    "acquisition": {"source_url": "synthetic://fixture", "acquired_utc": "2026-10-30T00:00:00Z",
                                                    "coverage": ["2023-01-01", "2023-12-31"], "fields": ["fixture"]}}
    path = tmp_path / "manifest.json"
    data = json.dumps(manifest).encode()
    path.write_bytes(data)
    loaded, snapshot = morning._load_manifest(morning.repo_root(), path, hashlib.sha256(data).hexdigest())
    assert set(morning.REQUIRED_ROLES).issubset(snapshot)
    del manifest["files"]["cboe_S_2023"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="missing required"):
        morning._load_manifest(morning.repo_root(), path, hashlib.sha256(path.read_bytes()).hexdigest())
    missing_path = tmp_path / "not-acquired-cboe-S.json"
    missing_role = {"path": str(missing_path), "bytes": 0, "sha256": hashlib.sha256(b"").hexdigest(),
                    "acquisition": {"source_url": "synthetic://fixture", "acquired_utc": "2026-10-30T00:00:00Z",
                                    "coverage": ["2023-01-01", "2023-12-31"], "fields": ["fixture"]}}
    manifest["files"]["cboe_S_2023"] = missing_role
    data = json.dumps(manifest).encode()
    path.write_bytes(data)
    _, snapshot = morning._load_manifest(morning.repo_root(), path, hashlib.sha256(data).hexdigest(), allow_missing=True)
    assert snapshot["cboe_S_2023"]["missing"] is True
    coverage = morning._blocked_coverage(morning._frozen_pairs_only((morning.repo_root() / morning.CALENDAR_PATH).read_bytes()),
                                         ["cboe_S_2023"])
    assert len(coverage) == 196 and not any(row["complete"] for row in coverage)


def test_input_hash_mutation_blocks_snapshot(tmp_path):
    source = tmp_path / "input.csv"
    source.write_bytes(b"before")
    record = {"path": str(source), "bytes": 6, "sha256": hashlib.sha256(b"before").hexdigest()}
    source.write_bytes(b"after!")
    with pytest.raises(ValueError, match="input changed"):
        morning._check_inputs({"fixture": record})


def test_selection_mutation_and_dirty_head_are_rejected(tmp_path, monkeypatch):
    selection_path = tmp_path / "selection.json"
    selection_path.write_text("frozen")
    identity = {"head": "abc", "code": {}}
    monkeypatch.setattr(morning, "_git", lambda repo, *args: "abc" if args[0] == "rev-parse" else "")
    selection_path.write_text("changed")
    with pytest.raises(ValueError, match="selection changed"):
        morning._check_identity(morning.repo_root(), identity, {}, selection_path, hashlib.sha256(b"frozen").hexdigest())
    monkeypatch.setattr(morning, "_git", lambda repo, *args: "abc" if args[0] == "rev-parse" else " M file")
    with pytest.raises(ValueError, match="clean Git"):
        morning._capture_code_identity(morning.repo_root())


@pytest.mark.parametrize("mutation", ["strike", "bbo"])
@pytest.mark.skipif(not (morning.repo_root() / morning.CALENDAR_PATH).is_file(), reason="requires private frozen 2023 calendar fixture not distributed in the public checkout")
def test_validly_rehashed_selection_rejects_contract_mutations(tmp_path, mutation):
    calendar = json.loads((morning.repo_root() / morning.CALENDAR_PATH).read_text())
    expected = [{key: date.fromisoformat(row[key]) for key in ("entry", "expiry", "cover")}
                for row in calendar["expected_pairs"]]
    first = expected[0]
    quotes = [_normalized("SPY", 100000, 2.0, 2.2, "spy-id", "A"),
              _normalized("SPXW", 4000000, 20.0, 20.2, "spxw-id", "E")]
    prices = {(replication.SECURITY_IDS["SPY"], first["entry"]): {"close": 100.0}}
    spx = {first["entry"]: 4000.0}
    chosen, _ = replication.select_pairs(quotes, [first], prices, spx)
    selected_by_entry = {pair["entry"].isoformat(): None for pair in expected}
    selected_by_entry[first["entry"].isoformat()] = chosen[0]
    rows = [{"entry": pair["entry"].isoformat(), "expiry": pair["expiry"].isoformat(),
             "cover": pair["cover"].isoformat(), "selected": selected_by_entry[pair["entry"].isoformat()]}
            for pair in expected]
    if mutation == "strike":
        rows[0]["selected"]["spy"]["normalized_strike_milli"] = "101000"
    else:
        rows[0]["selected"]["spy"]["normalized_best_bid"] = "2.1"
    receipt = {"status": "SELECTION_FROZEN_NOT_RUN", "historical_evaluation": "NOT RUN",
               "period": "2023", "input_manifest_sha256": "fixture-manifest",
               "protocol_sha256": morning.PROTOCOL_SHA256, "calendar_sha256": morning.CALENDAR_SHA256,
               "selected_pairs": rows}
    receipt_path = tmp_path / f"selection-{mutation}.json"
    receipt_bytes = json.dumps(receipt, sort_keys=True).encode()
    receipt_path.write_bytes(receipt_bytes)
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    assert morning.sha256(receipt_path.read_bytes()) == receipt_sha
    loaded, _ = morning._read_selection(receipt_path, receipt_sha, "fixture-manifest")
    with pytest.raises(ValueError, match="durable entry selection does not reproduce"):
        morning._verify_entry_selection(loaded, quotes, expected, prices, spx)


@pytest.mark.parametrize("mutation", ["code", "selection"])
def test_atomic_staging_actual_identity_check_blocks_byte_mutation(tmp_path, monkeypatch, mutation):
    repo = tmp_path / "temporary-git-project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Synthetic Test"], check=True)
    (repo / ".gitignore").write_text("planning/morning-hedge-replication-20261030/\n")
    code_path = repo / "src" / "adapter.py"
    code_path.parent.mkdir()
    code_path.write_bytes(b"committed representative code")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore", "src/adapter.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    planning = repo / "planning" / "morning-hedge-replication-20261030"
    planning.mkdir(parents=True)
    selection_path = planning / "selection.json"
    selection_path.write_bytes(b"frozen selection")
    original_code = code_path.read_bytes()
    original_selection = selection_path.read_bytes()
    identity = {"head": head, "code": {"code_adapter": {
        "path": str(code_path), "relative_path": "src/adapter.py", "data": original_code,
        "sha256": hashlib.sha256(original_code).hexdigest()}}}
    selection_sha = hashlib.sha256(original_selection).hexdigest()
    monkeypatch.setattr(morning, "_git", lambda _repo, *args: head if args[0] == "rev-parse" else "")
    out = planning / f"blocked-{mutation}"

    def final_identity_check():
        (code_path if mutation == "code" else selection_path).write_bytes(b"mutated bytes")
        morning._check_identity(repo, identity, {}, selection_path, selection_sha)

    with pytest.raises(ValueError, match="loaded code changed|selection changed"):
        morning._atomic_bundle(out, repo, {"fixture.json": b"{}"}, {}, final_guard=final_identity_check)
    assert not out.exists()


def test_output_path_must_be_new_ignored_child_of_planning(tmp_path):
    with pytest.raises(ValueError, match="ignored morning-hedge planning"):
        morning._safe_output(morning.repo_root(), tmp_path / "outside")


@pytest.mark.skipif(not (morning.repo_root() / morning.CALENDAR_PATH).is_file(), reason="requires private frozen 2023 calendar fixture not distributed in the public checkout")
def test_selection_receipt_must_bind_period_manifest_and_exact_denominator(tmp_path):
    expected_pairs = json.loads((morning.repo_root() / morning.CALENDAR_PATH).read_text())["expected_pairs"]
    payload = {"status": "SELECTION_FROZEN_NOT_RUN", "historical_evaluation": "NOT RUN",
               "period": "2023", "input_manifest_sha256": "a" * 64,
               "protocol_sha256": morning.PROTOCOL_SHA256, "calendar_sha256": morning.CALENDAR_SHA256,
               "selected_pairs": [{**item, "selected": None} for item in expected_pairs]}
    path = tmp_path / "selection.json"
    data = json.dumps(payload).encode()
    path.write_bytes(data)
    parsed, _ = morning._read_selection(path, hashlib.sha256(data).hexdigest(), "a" * 64)
    assert len(parsed["selected_pairs"]) == 196
    payload["selected_pairs"].pop()
    data = json.dumps(payload).encode()
    path.write_bytes(data)
    with pytest.raises(ValueError, match="196"):
        morning._read_selection(path, hashlib.sha256(data).hexdigest(), "a" * 64)
