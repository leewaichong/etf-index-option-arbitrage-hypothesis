from datetime import date

import pytest
import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

import spyspx.optionmetrics_timing as timing
from spyspx import optionmetrics_replication as base
from spyspx.optionmetrics_replication import SECURITY_IDS


def prices_for(day, prior, *, spy_open=101.0, spx_open=5010.0, cfadj=1.0):
    return {
        (SECURITY_IDS["SPY"], day): {"open": spy_open, "close": 102.0, "cfadj": cfadj},
        (SECURITY_IDS["SPY"], prior): {"open": 99.0, "close": 100.0, "cfadj": 1.0},
        (SECURITY_IDS["SPX"], day): {"open": spx_open, "close": 5020.0, "cfadj": 1.0},
    }


def test_prior_session_uses_adjacent_calendar_sessions_and_open_is_separate():
    day, prior = date(2024, 1, 2), date(2023, 12, 29)
    sessions = {prior, day}
    prices = prices_for(day, prior)
    refs = timing._reference_sets(prices, {prior: 4900.0, day: 5020.0}, sessions,
                                  [{"entry": day}])
    assert refs["prior_session_close"][0][(SECURITY_IDS["SPY"], day)]["close"] == 100.0
    assert refs["prior_session_close"][1][day] == 4900.0
    assert refs["current_session_open"][0][(SECURITY_IDS["SPY"], day)]["close"] == 101.0
    assert prices[(SECURITY_IDS["SPY"], day)]["close"] == 102.0


@pytest.mark.parametrize("mutation", ["missing_prior", "zero_open", "nonfinite_open", "nonunit_factor"])
def test_invalid_reference_fails_without_fallback(mutation):
    day, prior = date(2025, 1, 2), date(2024, 12, 31)
    sessions = {day} if mutation == "missing_prior" else {prior, day}
    prices = prices_for(day, prior)
    spx = {prior: 4900.0, day: 5020.0}
    if mutation == "zero_open":
        prices[(SECURITY_IDS["SPY"], day)]["open"] = 0
    elif mutation == "nonfinite_open":
        prices[(SECURITY_IDS["SPX"], day)]["open"] = float("nan")
    elif mutation == "nonunit_factor":
        prices[(SECURITY_IDS["SPY"], prior)]["cfadj"] = 1.1
    with pytest.raises(ValueError):
        timing._reference_sets(prices, spx, sessions, [{"entry": day}])


def test_all_three_modes_are_required_as_one_freeze():
    with pytest.raises(ValueError, match="all frozen modes"):
        timing.prepare(__import__("pathlib").Path("."), "primary_2024", {}, ("close_reference",))


def test_amended_protocol_and_preserved_prior_version_are_pinned():
    required = (timing.PROTOCOL,
                timing.PROTOCOL.with_name("candidate-protocol-v1-backup.md"),
                timing.MANIFEST)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        pytest.skip("private frozen control files unavailable: " + ", ".join(missing))
    protocol=timing.PROTOCOL.read_bytes()
    backup=timing.PROTOCOL.with_name("candidate-protocol-v1-backup.md").read_bytes()
    manifest=timing.MANIFEST.read_bytes()
    assert timing.sha(protocol)==timing.PROTOCOL_SHA256
    assert timing.sha(manifest)==timing.MANIFEST_SHA256
    assert timing.sha(backup)=="52ae35bb33af5b101b734aa6b22da20e03920399301e0fa290ad63303e561213"
    assert json.loads(manifest)["candidate_protocol_sha256"]==timing.PROTOCOL_SHA256


def test_distinct_references_change_strike_and_preserve_actual_close_fields():
    day, prior, expiry, cover = date(2024, 1, 3), date(2024, 1, 2), date(2024, 1, 4), date(2024, 1, 5)
    sessions = {prior, day, expiry, cover}
    prices = {
        (SECURITY_IDS["SPY"], day): {"open": 102.0, "close": 100.0, "cfadj": 1.0},
        (SECURITY_IDS["SPY"], prior): {"open": 99.0, "close": 98.0, "cfadj": 1.0},
        (SECURITY_IDS["SPX"], day): {"open": 5100.0, "close": 5000.0, "cfadj": 1.0},
    }
    rows = []
    for underlying, root, style, secid, strikes in (
        ("SPY", "SPY", "A", SECURITY_IDS["SPY"], (98_000, 100_000, 102_000)),
        ("SPX", "SPXW", "E", SECURITY_IDS["SPX"], (4900_000, 5000_000, 5100_000)),
    ):
        for i, strike in enumerate(strikes):
            rows.append({"normalized_cp_flag":"C", "normalized_contract_size":"100", "normalized_special_settlement":"",
                "symbol":f"{root} {strike}", "normalized_quote_date":day.isoformat(), "normalized_expiry_date":expiry.isoformat(),
                "normalized_underlying":underlying, "normalized_exercise_style":style, "normalized_am_settlement":"0",
                "normalized_best_bid":"1", "normalized_best_offer":"2", "normalized_strike_milli":str(strike),
                "normalized_symbol":f"{root}{i}", "normalized_option_id":str(i), "normalized_security_id":secid})
    selected = timing.select_modes(rows, [{"entry":day,"expiry":expiry,"cover":cover}], prices,
                                   {prior:4900.0, day:5000.0}, sessions,
                                   {"security-prices-20190801-20250829.csv":"price-hash","official_spx_calendar":"calendar-hash"})
    control = selected["close_reference"]["pairs"][0]
    earlier = selected["prior_session_close"]["pairs"][0]
    opened = selected["current_session_open"]["pairs"][0]
    assert control["spy"]["normalized_strike_milli"] == "100000"
    assert earlier["spy"]["normalized_strike_milli"] == "98000"
    assert opened["spy"]["normalized_strike_milli"] == "102000"
    assert control["selection_reference"]["date"] == day.isoformat()
    assert earlier["selection_reference"]["prior_date"] == prior.isoformat()
    assert prices[(SECURITY_IDS["SPY"], day)]["close"] == 100.0
    assert earlier["actual_entry_closes"] == {"spy_close":100.0,"official_spx_close":5000.0}
    assert earlier["selection_reference"]["spy_price"] == 98.0
    assert opened["selection_reference"]["source_sha256"]["spx"] == "price-hash"
    candidates=selected["prior_session_close"]["selection"]["candidate_audit"][0]
    assert candidates["bbo_eligible_candidate_count"]=={"SPY":3,"SPXW":3}
    assert candidates["returned_universe_only"] is True
    changed_close = {key: dict(value) for key, value in prices.items()}
    changed_close[(SECURITY_IDS["SPY"], day)]["close"] = 111.0
    changed_close[(SECURITY_IDS["SPX"], day)]["close"] = 5400.0
    changed_close[(SECURITY_IDS["SPY"], expiry)] = {"open": 999.0, "close": 999.0, "cfadj": 1.0}
    after = timing.select_modes(rows, [{"entry":day,"expiry":expiry,"cover":cover}], changed_close,
                                {prior:4900.0, day:5000.0}, sessions)
    assert after["prior_session_close"]["pairs"][0]["spy"]["normalized_strike_milli"] == "98000"
    assert after["current_session_open"]["pairs"][0]["spy"]["normalized_strike_milli"] == "102000"
    assert after["prior_session_close"]["pairs"][0]["actual_entry_closes"]["spy_close"] == 111.0


def test_ties_use_lower_strike_then_canonical_option_id():
    day, expiry, cover = date(2024,1,3), date(2024,1,4), date(2024,1,5)
    prices = {(SECURITY_IDS["SPY"],day):{"open":100,"close":100,"cfadj":1},
              (SECURITY_IDS["SPY"],date(2024,1,2)):{"open":100,"close":100,"cfadj":1},
              (SECURITY_IDS["SPX"],day):{"open":5000,"close":5000,"cfadj":1}}
    rows=[]
    for family, underlying, root, style, strikes in (
        ("SPY","SPY","SPY","A",((99000,("8","3")),(101000,("7",)))),
        ("SPX","SPX","SPXW","E",((4950000,("9","2")),)),
    ):
        for strike, ids in strikes:
            for oid in ids:
                rows.append({"normalized_cp_flag":"C","normalized_contract_size":"100","normalized_special_settlement":"",
                    "symbol":f"{root} x","normalized_quote_date":day.isoformat(),"normalized_expiry_date":expiry.isoformat(),
                    "normalized_underlying":underlying,"normalized_exercise_style":style,"normalized_am_settlement":"0",
                    "normalized_best_bid":"1","normalized_best_offer":"2","normalized_strike_milli":str(strike),
                    "normalized_symbol":f"{root}{oid}","normalized_option_id":oid})
    modes=timing.select_modes(rows,[{"entry":day,"expiry":expiry,"cover":cover}],prices,
                              {date(2024,1,2):4900,day:5000},{date(2024,1,2),day,expiry,cover})
    assert modes["close_reference"]["pairs"][0]["spy"]["normalized_strike_milli"] == "99000"
    assert modes["close_reference"]["pairs"][0]["spy"]["normalized_option_id"] == "3"
    assert modes["close_reference"]["pairs"][0]["spxw"]["normalized_option_id"] == "2"


def _coverage_fixture():
    prior, entry, expiry, cover = date(2024,1,2), date(2024,1,3), date(2024,1,4), date(2024,1,5)
    expected=[{"entry":entry,"expiry":expiry,"cover":cover}]
    sessions={prior,entry,expiry,cover}
    prices={(SECURITY_IDS["SPY"],d):{"close":100.0,"open":100.0,"cfadj":1.0} for d in sessions}
    prices[(SECURITY_IDS["SPX"],entry)]={"close":5000.0,"open":5000.0,"cfadj":1.0}
    official={prior:4900.0,entry:5000.0,expiry:5010.0}
    selected={mode:{"pairs":[{"entry":entry.isoformat(),"selection_reference":{"date":(prior if mode=="prior_session_close" else entry).isoformat()}}]} for mode in timing.MODES}
    dividends=[{"ex_date":entry,"distr_type":"1","frequency":"1","amount":0.5,"currency":"USD","approx_flag":"0","cancel_flag":"0","liquid_flag":"0","adj_factor":1.0}]
    settlements={expiry:{"value":5010.0}}
    return prior,entry,expiry,cover,expected,sessions,prices,official,selected,dividends,settlements


def test_reference_to_cover_factor_gate_and_preentry_dividend_is_staleness_only():
    prior,entry,expiry,cover,expected,sessions,prices,official,selected,dividends,settlements=_coverage_fixture()
    assert timing.terminal_coverage_blockers(selected,expected,prices,official,settlements,dividends,sessions)==[]
    audit=timing.reference_staleness_audit(selected,dividends)
    prior_note=audit["prior_session_close"][0]
    assert prior_note["confirmed_pre_entry_cash_dividend_dates"] == [entry.isoformat()]
    assert prior_note["position_dividend_charge_for_pre_entry_events"] == 0.0
    prices[(SECURITY_IDS["SPY"],prior)]["cfadj"] = 1.2
    blockers=timing.terminal_coverage_blockers(selected,expected,prices,official,settlements,dividends,sessions)
    assert any(x["mode"]=="prior_session_close" and "nonunit_spy_cfadj" in x["missing"] for x in blockers)


def test_confirmed_preentry_dividend_is_not_in_position_ledger():
    entry=date(2024,1,3);expiry=date(2024,1,4);cover=date(2024,1,5)
    spy={"normalized_symbol":"SPY-X","normalized_expiry_date":expiry.isoformat(),"normalized_quote_date":entry.isoformat(),
         "normalized_strike_milli":"100000","normalized_best_bid":"2","normalized_best_offer":"2.1"}
    spxw={"normalized_symbol":"SPXW-X","normalized_expiry_date":expiry.isoformat(),"normalized_quote_date":entry.isoformat(),
          "normalized_strike_milli":"5000000","normalized_best_bid":"19","normalized_best_offer":"19.1"}
    pair={"entry":entry.isoformat(),"expiry":expiry.isoformat(),"cover":cover.isoformat(),"spy":spy,"spxw":spxw,
          "spy_entry_close":100.0,"official_spx_entry_close":5000.0}
    event_list=_coverage_fixture()[9]
    fills,_=base.build_fill_rows(pair,{"spy_expiry_close":100.0,"spy_cover_open":100.0,"spxw_pm_settlement":5000.0},event_list)
    assert all(row["dividend_carry_dates"]==[] and row["dividend_carry_amount"]==0.0 for row in fills)


def test_unsupported_reference_to_cover_distribution_blocks():
    prior,entry,expiry,cover,expected,sessions,prices,official,selected,dividends,settlements=_coverage_fixture()
    dividends[0]["approx_flag"]="1"
    blockers=timing.terminal_coverage_blockers(selected,expected,prices,official,settlements,dividends,sessions)
    assert any(x["mode"]=="prior_session_close" and "unsupported_distribution_event_from_reference" in x["missing"] for x in blockers)


def test_source_reference_audit_covers_each_mode_and_flags_prior_carry():
    prior,entry,expiry,cover,expected,sessions,prices,official,selected,dividends,settlements=_coverage_fixture()
    audit=timing.source_reference_coverage_audit(prices,official,sessions,expected,dividends)
    assert audit["status"]=="SOURCE_REFERENCE_COVERAGE_PRESENT"
    primary=next(row for row in audit["mode_date_rows"] if row["mode"]=="prior_session_close")
    assert primary["reference_date"]==prior.isoformat()
    assert primary["confirmed_pre_entry_dividend_staleness_dates"]==[entry.isoformat()]
    dividends[0]["approx_flag"]="1"
    blocked=timing.source_reference_coverage_audit(prices,official,sessions,expected,dividends)
    assert blocked["status"]=="SOURCE_REFERENCE_COVERAGE_BLOCKED"


def test_reused_ledger_receives_actual_closes_not_selection_references(monkeypatch):
    entry=date(2024,1,3);expiry=date(2024,1,4);cover=date(2024,1,5);calls=[]
    pair={"entry":entry.isoformat(),"expiry":expiry.isoformat(),"cover":cover.isoformat(),
          "spy_entry_close":100.0,"official_spx_entry_close":5000.0,
          "selection_reference":{"date":"2024-01-02","spy_price":98.0,"spx_price":4900.0},
          "actual_entry_closes":{"spy_close":100.0,"official_spx_close":5000.0},
          "spy":{"normalized_symbol":"SPY-X"},"spxw":{"normalized_symbol":"SPXW-X"}}
    modes={mode:{"pairs":[dict(pair)]} for mode in timing.MODES}
    def fake_evaluate(selected,expected,*args):
        calls.append((selected[0]["spy_entry_close"],selected[0]["official_spx_entry_close"]))
        row={"entry":entry.isoformat(),"timing_status":"DAILY_CLOSE_TIMING_MISMATCH_THEORETICAL","fill_rows":[{"timing_status":"DAILY_CLOSE_TIMING_MISMATCH_THEORETICAL"}]}
        return [],[row]
    monkeypatch.setattr(base,"_evaluation_rows",fake_evaluate)
    result=timing.evaluate_modes(modes,[{"entry":entry,"expiry":expiry,"cover":cover}],{}, {}, {}, [], set())
    assert calls==[(100.0,5000.0)]*3
    for mode in timing.MODES[1:]:
        row=result[mode]["outcomes"][0]
        assert row["timing_status"]=="EARLIER_REFERENCE_DAILY_QUOTES_THEORETICAL"
        assert row["actual_entry_closes"]==pair["actual_entry_closes"]
        assert row["selection_reference"]["spy_price"]==98.0


def test_missing_terminal_coverage_stops_before_calculation(monkeypatch):
    _,_,expiry,_,expected,sessions,prices,official,selected,dividends,settlements=_coverage_fixture()
    del settlements[expiry]
    def forbidden(*args,**kwargs):
        raise AssertionError("payoff calculation ran despite missing terminal coverage")
    monkeypatch.setattr(timing,"evaluate_modes",forbidden)
    blockers,evaluated=timing.evaluate_after_coverage(selected,expected,prices,official,settlements,dividends,sessions)
    assert blockers and evaluated is None and len(expected)==1


def test_missing_selection_keeps_expected_denominator():
    _,_,expiry,_,expected,sessions,prices,official,selected,dividends,settlements=_coverage_fixture()
    selected["prior_session_close"]["pairs"]=[]
    blockers=timing.terminal_coverage_blockers(selected,expected,prices,official,settlements,dividends,sessions)
    assert len(blockers) >= len(expected)
    assert any("selected_pair" in row["missing"] for row in blockers)


def test_all_lanes_are_durably_frozen_before_terminal_loader():
    modes={mode:{"pairs":[{"entry":"2024-01-03"}]} for mode in timing.MODES}
    order=[]
    selection,terminal=timing.freeze_before_terminal_joins(
        modes,1,lambda:(order.append("freeze") or "selection-hash"),
        lambda:(order.append("terminal") or "terminal-source"))
    assert order==["freeze","terminal"] and selection=="selection-hash" and terminal=="terminal-source"
    order.clear();modes["prior_session_close"]["pairs"]=[]
    with pytest.raises(ValueError,match="fixed-denominator"):
        timing.freeze_before_terminal_joins(modes,1,lambda:order.append("freeze"),lambda:order.append("terminal"))
    assert order==[]


def _parity_fixture():
    entry="2024-01-03"; expiry="2024-01-04"
    fill_rows=[]
    for fill in ("midpoint","halfway","full_cross"):
        fill_rows.append({"fill":fill,"direct_intrinsic_pnl":1.0,"threshold_residual_cash":0.0,
            "dividend_carry_amount":0.0,"dividend_carry_pnl":1.0,"base_cost_pnl":0.5,"stress_cost_pnl":0.25,
            "stock_neutralized_pnl":1.0,"stock_overnight_attribution":0.0,"decomposition_residual":0.0,
            "next_open_pnl":1.0,"conditional_close_mark_pnl":1.0,"spy_entry_cash":20.0,"spy_entry_shares":-1000,
            "spxw_entry_cash":-19.0,"spxw_entry_shares":100,"assigned":False,"complete_cover":True,
            "timing_status":"DAILY_CLOSE_TIMING_MISMATCH_THEORETICAL"})
    controls={"reverse_full_cross_credit":-1.0,"reverse_intrinsic_control_pnl":-1.0,"reverse_closemark_control_pnl":-1.0,
        "reverse_spy_closemark_cash":0.0,"reverse_spxw_closemark_cash":0.0,"primary_assignment_threshold_applied":False,
        "primary_threshold_residual_cash":0.0,"no_trade_zero_control_pnl":0.0,"reverse_physical_next_open_ledger":"NOT_DEFINED_BY_PROTOCOL"}
    row={"entry":entry,"expiry":expiry,"status":"COMPLETE_THEORETICAL_ROW","spy_contract":"SPY-X","spxw_contract":"SPXW-X",
         "spy_strike":100.0,"spxw_strike":5000.0,"fill_rows":fill_rows,"controls":controls,
         "timing_status":"DAILY_CLOSE_TIMING_MISMATCH_THEORETICAL"}
    selected={"entry":entry,"expiry":expiry,"cover":"2024-01-05","spy_entry_close":100.0,"official_spx_entry_close":5000.0,
        "moneyness_mismatch":0.0,"spy":{"normalized_symbol":"SPY-X","normalized_security_id":"109820","normalized_option_id":"1",
            "normalized_strike_milli":"100000","normalized_best_bid":"2","normalized_best_offer":"2.1"},
        "spxw":{"normalized_symbol":"SPXW-X","normalized_security_id":"108105","normalized_option_id":"2",
            "normalized_strike_milli":"5000000","normalized_best_bid":"19","normalized_best_offer":"19.1"}}
    selected_current={**selected,"actual_entry_closes":{"spy_close":100.0,"official_spx_close":5000.0},
        "selection_reference":{"mode":"close_reference","date":entry,"spy_price":100.0,"spx_price":5000.0}}
    outcome={**row,"actual_entry_closes":{"spy_close":100.0,"official_spx_close":5000.0},
        "selection_reference":{"mode":"close_reference","date":entry}}
    summary=base.aggregate([row],"primary_2024")
    evaluated={"close_reference":{"outcomes":[outcome]}}
    inputs={"baseline_primary_2024/outcomes.json":{"data":json.dumps([row]).encode()},
        "baseline_primary_2024/summary.json":{"data":json.dumps(summary).encode()},
        "selection_primary_2024":{"data":json.dumps({"selected_pairs":[selected]}).encode(),"sha256":"selection-hash"},
        "baseline_primary_2024/outcomes.json":{"data":json.dumps([row]).encode(),"sha256":"outcome-hash"}}
    modes={"close_reference":{"pairs":[selected_current]}}
    return evaluated,modes,inputs


def test_recursive_baseline_parity_passes_all_fields_and_summaries():
    evaluated,modes,inputs=_parity_fixture()
    result=timing.verify_control_parity(evaluated,modes,inputs,"primary_2024")
    assert result["status"]=="PASS"
    assert result["aggregate_numeric_fields_compared"] > 0


@pytest.mark.parametrize("mutation",["reverse_control","missing_cash_field","aggregate","selected_quote","actual_close","outcome_actual_close","nonfinite","duplicate_fill","duplicate_entry"])
def test_baseline_parity_rejects_reverse_cash_and_summary_changes(mutation):
    evaluated,modes,inputs=_parity_fixture()
    if mutation=="reverse_control":
        evaluated["close_reference"]["outcomes"][0]["controls"]["reverse_intrinsic_control_pnl"] += 1
    elif mutation=="missing_cash_field":
        del evaluated["close_reference"]["outcomes"][0]["fill_rows"][0]["spy_entry_cash"]
    elif mutation=="aggregate":
        summary=json.loads(inputs["baseline_primary_2024/summary.json"]["data"])
        summary["cohorts"]["all"]["fills"]["full_cross"]["dividend_carry_pnl"]["mean"] += 1
        inputs["baseline_primary_2024/summary.json"]["data"]=json.dumps(summary).encode()
    elif mutation=="selected_quote":
        modes["close_reference"]["pairs"][0]["spy"]["normalized_best_offer"]="2.2"
    elif mutation=="actual_close":
        modes["close_reference"]["pairs"][0]["actual_entry_closes"]["spy_close"]+=1
    elif mutation=="outcome_actual_close":
        evaluated["close_reference"]["outcomes"][0]["actual_entry_closes"]["spy_close"]+=1
    elif mutation=="nonfinite":
        evaluated["close_reference"]["outcomes"][0]["fill_rows"][0]["spy_entry_cash"]=float("nan")
    elif mutation=="duplicate_fill":
        row=evaluated["close_reference"]["outcomes"][0]
        row["fill_rows"].append(dict(row["fill_rows"][0]))
    else:
        evaluated["close_reference"]["outcomes"].append(dict(evaluated["close_reference"]["outcomes"][0]))
    with pytest.raises(ValueError):
        timing.verify_control_parity(evaluated,modes,inputs,"primary_2024")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")], ids=["nan", "positive-infinity", "negative-infinity"])
@pytest.mark.parametrize("tree_kind", ["ledger", "summary"])
def test_parity_rejects_matching_nonfinite_values_on_both_sides(value, tree_kind):
    if tree_kind == "ledger":
        reference = {"fill_rows": [{"spy_entry_cash": value}]}
        actual = {"fill_rows": [{"spy_entry_cash": value}]}
        path = "ledger"
    else:
        reference = {"cohorts": {"all": {"fills": {"full_cross": {"mean": value}}}}}
        actual = {"cohorts": {"all": {"fills": {"full_cross": {"mean": value}}}}}
        path = "summary"
    with pytest.raises(ValueError, match="nonfinite"):
        timing._compare_exact_tree(reference, actual, 1e-8, path)


def _fake_clean_repo(tmp_path, monkeypatch):
    repo=tmp_path/"repo";repo.mkdir()
    subprocess.run(["git","init","-q"],cwd=repo,check=True)
    subprocess.run(["git","config","user.email","test@example.invalid"],cwd=repo,check=True)
    subprocess.run(["git","config","user.name","Test"],cwd=repo,check=True)
    mapping={}
    for relative in timing.CODE_PATHS:
        path=repo/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(relative)
        mapping[relative]=SimpleNamespace(__file__=str(path))
    subprocess.run(["git","add","."],cwd=repo,check=True)
    subprocess.run(["git","commit","-qm","fixture"],cwd=repo,check=True)
    monkeypatch.setattr(timing,"IMPORTED_MODULES",{relative:(lambda module=module:module) for relative,module in mapping.items()})
    return repo


def test_imported_module_path_substitution_is_rejected(tmp_path,monkeypatch):
    repo=_fake_clean_repo(tmp_path,monkeypatch)
    wrong=tmp_path/"elsewhere.py";wrong.write_text("x")
    monkeypatch.setitem(timing.IMPORTED_MODULES,timing.CODE_PATHS[0],lambda:SimpleNamespace(__file__=str(wrong)))
    with pytest.raises(ValueError,match="loaded module path"):
        timing.capture_identity(repo)


@pytest.mark.parametrize("mutation",["dirty_head","code","protocol","source","control","selection"])
def test_integrity_mutations_block(tmp_path,monkeypatch,mutation):
    repo=_fake_clean_repo(tmp_path,monkeypatch);identity=timing.capture_identity(repo)
    source=tmp_path/"source";source.write_text("source")
    control=tmp_path/"control";control.write_text("control")
    protocol=tmp_path/"protocol";protocol.write_text("protocol")
    inputs={}
    for role,path in (("protocol",protocol),("source",source),("control",control)):
        data=path.read_bytes();inputs[role]={"path":str(path),"bytes":len(data),"sha256":timing.sha(data),"data":data}
    selection=tmp_path/"selection";selection.write_text("selection");selection_ref=(selection,timing.sha(selection.read_bytes()))
    if mutation=="dirty_head":
        (repo/"dirty").write_text("x")
    elif mutation=="code":
        (repo/timing.CODE_PATHS[0]).write_text("changed")
    elif mutation in inputs:
        p=Path(inputs[mutation]["path"]);p.write_text("changed")
    elif mutation=="selection":
        selection.write_text("changed")
    with pytest.raises(ValueError,match="BLOCKED"):
        timing.check_identity(repo,identity,inputs,selection_ref)


def test_atomic_audit_is_safe_no_overwrite_and_cleans_failed_stage(tmp_path,monkeypatch):
    repo=_fake_clean_repo(tmp_path,monkeypatch);identity=timing.capture_identity(repo)
    source=tmp_path/"source";source.write_text("x");data=source.read_bytes()
    inputs={"source":{"path":str(source),"bytes":len(data),"sha256":timing.sha(data),"data":data}}
    target=repo/"planning/audit.json"
    monkeypatch.setattr(timing,"check_identity",lambda *a,**k:(_ for _ in ()).throw(ValueError("BLOCKED injected")))
    with pytest.raises(ValueError):timing.atomic_run_audit(target,{"status":"BLOCKED_SOURCE"},repo,identity,inputs)
    assert not target.exists() and not list(target.parent.glob(".*.tmp"))
    monkeypatch.setattr(timing,"check_identity",lambda *a,**k:{"status":"PASS"})
    timing.atomic_run_audit(target,{"status":"BLOCKED_SOURCE"},repo,identity,inputs)
    saved=json.loads(target.read_text())
    assert saved["integrity_check_before_audit_publish"]=={"status":"PASS"}
    with pytest.raises(FileExistsError):timing.atomic_run_audit(target,{},repo,identity,inputs)


def test_run_bundle_publication_is_atomic_and_refuses_overwrite(tmp_path,monkeypatch):
    repo=_fake_clean_repo(tmp_path,monkeypatch);identity=timing.capture_identity(repo)
    source=tmp_path/"source";source.write_text("source");data=source.read_bytes()
    inputs={"source":{"path":str(source),"bytes":len(data),"sha256":timing.sha(data),"data":data}}
    selection=tmp_path/"selection";selection.write_text("frozen");selection_ref=(selection,timing.sha(selection.read_bytes()))
    output=repo/"runs/optionmetrics_replication/synthetic"
    documents={"outcomes.json":{"status":"NOT RUN"},"comparison.json":{"status":"NOT RUN"}}
    manifest={"status":"SYNTHETIC_TEST_ONLY","integrity_checkpoints":{}}
    monkeypatch.setattr(timing,"check_identity",lambda *a,**k:(_ for _ in ()).throw(ValueError("BLOCKED injected")))
    with pytest.raises(ValueError):timing.atomic_publish_run_bundle(output,documents,manifest,repo,identity,inputs,selection_ref)
    assert not output.exists() and not list(output.parent.glob(".synthetic.*"))
    monkeypatch.setattr(timing,"check_identity",lambda *a,**k:{"status":"PASS"})
    receipt=timing.atomic_publish_run_bundle(output,documents,manifest,repo,identity,inputs,selection_ref)
    assert (output/"manifest.json").exists() and (output/"outcomes.json").exists()
    assert len(receipt["manifest_sha256"])==64 and set(receipt["output_sha256"])==set(documents)
    with pytest.raises(FileExistsError):timing.atomic_publish_run_bundle(output,documents,manifest,repo,identity,inputs,selection_ref)
