from __future__ import annotations

import csv
import json
import shutil
import subprocess
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
import zipfile

import pytest

from spyspx.expiry_payoff import Quote
from spyspx.expiry_replication import (OPTION_FIELDS, STOCK_FIELDS, _parse_option_file, _parse_stock_file,
    EXPECTED_EXPIRIES, RECEIPT_NAMES, aggregate_rows, audit_sources, parse_cboe_pm, read_spx, read_yahoo, validate_receipt)
from spyspx.expiry_extension import select_official


def _csv_bytes(fields, rows):
    import io
    f = io.StringIO(newline="")
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    return f.getvalue().encode()


def _option(**changes):
    row = {"UnderlyingSymbol": "SPXW", "UnderlyingPrice": "3000", "Exchange": "W", "OptionSymbol": "SPXW190802C03000000", "OptionExt": "", "Type": "call", "Expiration": "08/02/2019", "DataDate": "08/01/2019", "Strike": "3000", "Last": "1", "Bid": "1", "Ask": "1.2", "Volume": "1", "OpenInterest": "1", "IV": ".2", "Delta": ".5", "Gamma": ".1", "Theta": "-.1", "Vega": ".1", "AKA": "SPXW190802C03000000"}
    row.update(changes); return row


def test_explicit_osi_root_and_am_spx_exclusion():
    buf = _csv_bytes(OPTION_FIELDS, [_option(), _option(UnderlyingSymbol="SPX", OptionSymbol="SPX190802C03000000", AKA="SPX190802C03000000")])
    import io
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z: z.writestr("L2_options_20190801.csv", buf)
    archive.seek(0)
    with zipfile.ZipFile(archive) as z:
        quotes=[]; counts=Counter()
        _parse_option_file(z, "L2_options_20190801.csv", date(2019,8,1), counts, quotes, set())
    assert [q.contract for q in quotes] == ["SPXW190802C03000000"]
    assert counts["excluded_spx_am_contract_rows"] == 1


def test_option_filename_date_and_identity_conflicts_rejected():
    import io
    row = _option(DataDate="08/02/2019")
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,"w") as z: z.writestr("L2_options_20190801.csv",_csv_bytes(OPTION_FIELDS,[row,_option(UnderlyingSymbol="SPY")]))
    archive.seek(0)
    with zipfile.ZipFile(archive) as z:
        q=[]; c=Counter(); _parse_option_file(z,"L2_options_20190801.csv",date(2019,8,1),c,q,set())
    assert not q
    assert c["options_filename_date_conflicts"] == 1
    assert c["option_identity_conflict"] == 1


def test_strict_option_schema_rejects_missing_column():
    import io
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,"w") as z: z.writestr("x",_csv_bytes(OPTION_FIELDS[:-1],[]))
    archive.seek(0)
    with zipfile.ZipFile(archive) as z:
        counts=Counter(); _parse_option_file(z,"x",date(2019,8,1),counts,[],set())
    assert counts["options_schema_invalid_files"] == 1


def test_invalid_bid_ask_is_rejected():
    import io
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,"w") as z: z.writestr("x",_csv_bytes(OPTION_FIELDS,[_option(Bid="0",Ask="1"),_option(Bid="2",Ask="1")]))
    archive.seek(0)
    with zipfile.ZipFile(archive) as z:
        c=Counter(); q=[]; _parse_option_file(z,"x",date(2019,8,1),c,q,set())
    assert not q and c["invalid_bid_ask"] == 2


def test_stock_schema_and_filename_date_conflict():
    import io
    fields=STOCK_FIELDS
    row={"symbol":"SPY","quotedate":"8/2/2019","open":"294","high":"295","low":"293","close":"294.5","volume":"10","adjustedclose":"294.5"}
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,"w") as z: z.writestr("stock",_csv_bytes(fields,[row]))
    archive.seek(0)
    with zipfile.ZipFile(archive) as z:
        c=Counter(); stocks={}; sessions=set(); _parse_stock_file(z,"stock",date(2019,8,1),c,stocks,sessions)
    assert date(2019,8,2) in sessions and c["stock_filename_date_conflicts"] == 1


def test_duplicate_settlement_identical_and_conflict(tmp_path):
    from html import escape
    p=tmp_path/"w.json"
    row='<tr><td>SPXW Weekly</td><td>SPXW</td><td>08/02/2019</td><td>SPX</td><td>2953.56</td></tr>'
    p.write_text(json.dumps({"data":row+row}))
    c=Counter(); result=parse_cboe_pm(p,c)
    assert result[date(2019,8,2)]["value"] == pytest.approx(2953.56)
    assert c["cboe_consistent_duplicates"] == 1
    p.write_text(json.dumps({"data":row+row.replace("2953.56","2954.56")}))
    c=Counter(); assert date(2019,8,2) not in parse_cboe_pm(p,c)
    assert c["cboe_conflicting_duplicates"] == 1


def test_pm_filter_and_annotated_settlement(tmp_path):
    p=tmp_path/"w.json"
    p.write_text(json.dumps({"data": "<tr><td>x</td><td>SPX</td><td>08/02/2019</td><td>SET</td><td>2953</td></tr>"
                                      "<tr><td>x</td><td>SPXW</td><td>08/12/2019</td><td>SPX</td><td>2882.2*</td></tr>"}))
    rows=parse_cboe_pm(p,Counter())
    assert date(2019,8,2) not in rows
    assert rows[date(2019,8,12)]["footnote_marker"] is True


def test_spx_schema_strict(tmp_path):
    p=tmp_path/"spx.csv"; p.write_text("Date,Close\n2019-08-02,2953\n")
    with pytest.raises(ValueError,match="DATE,SPX"):
        read_spx(p,Counter())


def test_receipt_hash_corruption_fails(tmp_path):
    from spyspx.expiry_replication import RECEIPT_NAMES
    records=[]
    for name in RECEIPT_NAMES:
        data=tmp_path/name; data.write_bytes(name.encode())
        records.append({"path":str(data),"bytes":data.stat().st_size,"sha256":__import__("hashlib").sha256(data.read_bytes()).hexdigest()})
    records[0]["sha256"]="0"*64
    receipt=tmp_path/"receipt.json"
    receipt.write_text(json.dumps({"files":records}))
    result=validate_receipt(tmp_path,receipt)
    assert result["status"] == "FAIL"
    assert "sha256_mismatch" in result["entries"][0]["problems"]


def test_selection_thresholds_tie_breaks_and_future_independence():
    d, e = date(2019,8,1), date(2019,8,2)
    quotes=[
        Quote("SPY190802C00294000","SPY",e,"call",294,"A",d,1,1.2,294,"PM"),
        Quote("SPY190802C00296000","SPY",e,"call",296,"A",d,1,1.2,294,"PM"),
        Quote("SPXW190802C02940000","SPXW",e,"call",2940,"E",d,1,1.2,2940,"PM"),
        Quote("SPXW190802C02960000","SPXW",e,"call",2960,"E",d,1,1.2,2940,"PM"),
    ]
    pairs=select_official(quotes,{d:295},{d:2950},{})
    assert len(pairs)==1
    chosen=pairs[0]
    future_day, future_expiry = date(2019,8,2), date(2019,8,7)
    quotes.extend([Quote("SPY190807C00295000","SPY",future_expiry,"call",295,"A",future_day,100,101,999,"PM"),
                   Quote("SPXW190807C02950000","SPXW",future_expiry,"call",2950,"E",future_day,100,101,9999,"PM")])
    result=select_official(quotes,{d:295,future_day:999},{d:2950,future_day:9999},{})
    assert result[0][:2] == chosen[:2]


def test_selection_accepts_threshold_edges_and_uses_lower_strike_ties():
    d,e=date(2019,8,1),date(2019,8,2)
    quotes=[Quote("SPY190802C00098000","SPY",e,"call",98,"A",d,1,1.2,100,"PM"),
            Quote("SPY190802C00102000","SPY",e,"call",102,"A",d,1,1.2,100,"PM"),
            Quote("SPXW190802C00979040","SPXW",e,"call",979.04,"E",d,1,1.2,1000,"PM"),
            Quote("SPXW190802C00980960","SPXW",e,"call",980.96,"E",d,1,1.2,1000,"PM"),
            Quote("SPXW190802C00982000","SPXW",e,"call",982,"E",d,1,1.2,1000,"PM")]
    selected=select_official(quotes,{d:100},{d:1000},{})
    assert len(selected)==1
    # Both legs sit exactly on the allowed thresholds; equal-distance ties use the lower strike.
    assert selected[0][0].strike==98
    assert selected[0][1].strike==pytest.approx(979.04)


def test_missing_first_next_session_does_not_skip_to_later_yahoo_row():
    from spyspx.expiry_replication import build_pair_rows
    entry, expiry, next_day = date(2019,8,1), date(2019,8,2), date(2019,8,5)
    quotes=[Quote("SPY190802C00294000","SPY",expiry,"call",294,"A",entry,1,1.2,294,"PM"),
            Quote("SPXW190802C02940000","SPXW",expiry,"call",2940,"E",entry,1,1.2,2940,"PM")]
    stocks={entry:{"open":294,"close":294,"adjustedclose":294},expiry:{"open":294,"close":295,"adjustedclose":295}}
    settlements={expiry:{"value":2950,"footnote_marker":False}}
    later=date(2019,8,6)
    rows,_=build_pair_rows(quotes,stocks,{entry:2940,expiry:2950},settlements,{entry:{"open":294,"close":294},later:{"open":296,"close":297}},[],{expiry:next_day})
    selected=next(r for r in rows if r["expiry_date"]==expiry.isoformat())
    assert selected["status"] == "MISSING_REFERENCE"
    assert "missing_first_next_session_raw_open" in selected["missing_inputs"]


def test_aggregate_keeps_missing_expiry_denominator():
    rows=[{"expiry_date":"2019-08-02","status":"MISSING_REFERENCE"},
          {"expiry_date":"2019-08-07","status":"COMPLETE_THEORETICAL_ROW","fill_rows":[{"fill":"full_cross","direct_intrinsic_pnl":2,"conditional_close_mark_pnl":2,"next_open_pnl":2,"base_cost_pnl":1,"stress_cost_pnl":0,"stock_neutralized_pnl":2,"stock_neutralized_base_cost_pnl":1,"stock_neutralized_stress_cost_pnl":0,"reverse_cross_control_pnl":-1,"zero_control_pnl":0},{"fill":"midpoint","direct_intrinsic_pnl":3,"conditional_close_mark_pnl":3,"next_open_pnl":3,"base_cost_pnl":2,"stress_cost_pnl":1,"stock_neutralized_pnl":3,"stock_neutralized_base_cost_pnl":2,"stock_neutralized_stress_cost_pnl":1,"reverse_cross_control_pnl":-1,"zero_control_pnl":0},{"fill":"halfway","direct_intrinsic_pnl":2.5,"conditional_close_mark_pnl":2.5,"next_open_pnl":2.5,"base_cost_pnl":1.5,"stress_cost_pnl":.5,"stock_neutralized_pnl":2.5,"stock_neutralized_base_cost_pnl":1.5,"stock_neutralized_stress_cost_pnl":.5,"reverse_cross_control_pnl":-1,"zero_control_pnl":0}]}]
    out=aggregate_rows(rows)
    assert out["cohorts"]["all"]["missing_primary_expiry_count"] == 8
    assert out["cohorts"]["all"]["fills"]["full_cross"]["direct_intrinsic_pnl"]["mean"] == 2


def _make_source_fixture(root, *, bad_yahoo_close=False, bad_provider_close=False, invalid_provider_close=False):
    import io
    from spyspx.expiry_replication import sha256
    root.mkdir(parents=True, exist_ok=True)
    sessions=[]
    day=date(2019,8,1)
    while day <= date(2019,8,30):
        if day.weekday()<5: sessions.append(day)
        day=date.fromordinal(day.toordinal()+1)
    assert len(sessions)==22
    entry_expiry={d-timedelta(days=1):d for d in EXPECTED_EXPIRIES}
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for d in sessions:
            opts=[]
            opts.append(_option(UnderlyingSymbol="SPY",UnderlyingPrice="100.1",Exchange="W",OptionSymbol="SPY190920C00100000",AKA="SPY190920C00100000",Expiration="09/20/2019",DataDate=d.strftime("%m/%d/%Y"),Strike="100",Bid="1",Ask="1.2"))
            if d in entry_expiry:
                e=entry_expiry[d]
                opts.extend([_option(UnderlyingSymbol="SPY",UnderlyingPrice="100.1",Exchange="W",OptionSymbol=f"SPY{e.strftime('%y%m%d')}C00100000",AKA=f"SPY{e.strftime('%y%m%d')}C00100000",Expiration=e.strftime("%m/%d/%Y"),DataDate=d.strftime("%m/%d/%Y"),Strike="100",Bid="1",Ask="1.2"),
                             _option(UnderlyingSymbol="SPXW",UnderlyingPrice="1000",Exchange="W",OptionSymbol=f"SPXW{e.strftime('%y%m%d')}C01000000",AKA=f"SPXW{e.strftime('%y%m%d')}C01000000",Expiration=e.strftime("%m/%d/%Y"),DataDate=d.strftime("%m/%d/%Y"),Strike="1000",Bid="10",Ask="11")])
            z.writestr(f"L2_options_{d:%Y%m%d}.csv",_csv_bytes(OPTION_FIELDS,opts))
            close="" if invalid_provider_close and d==sessions[0] else (100.2 if bad_provider_close and d==sessions[0] else 100.1)
            stock={"symbol":"SPY","quotedate":f"{d.month}/{d.day}/{d.year}","open":"99.99","high":"101","low":"99","close":str(close),"volume":"10","adjustedclose":str(close)}
            z.writestr(f"L2_stockquotes_{d:%Y%m%d}.csv",_csv_bytes(STOCK_FIELDS,[stock]))
    (root/"Sample_L2_2019_August.zip").write_bytes(archive.getvalue())
    w_dates=[date(2019,8,d) for d in (2,5,7,9,12,14,16,19,21,23,26,28,30)]
    w_rows=[]
    for d in w_dates:
        val="1000*" if d.day==12 else "1000"
        w_rows.append(f"<tr><td>S&amp;P 500 CLOSE</td><td>SPXW</td><td>{d:%m/%d/%Y}</td><td>SPX</td><td>{val}</td></tr>")
    (root/"cboe_W_2019.json").write_text(json.dumps({"data":"".join(w_rows)}))
    (root/"cboe_M_2019.json").write_text(json.dumps({"data":"<tr><td>S&amp;P 500 CLOSE</td><td>SPXW</td><td>08/30/2019</td><td>SPX</td><td>1000</td></tr>"}))
    (root/"cboe_S_2019.json").write_text(json.dumps({"data":"<tr><td>S&amp;P 500 (SET)</td><td>1000</td></tr>"}))
    with (root/"SPX_History.csv").open("w") as f:
        f.write("DATE,SPX\n")
        for d in sessions: f.write(f"{d:%m/%d/%Y},1000\n")
    yahoo_dates=sessions+[date(2019,9,3),date(2019,9,4)]
    timestamps=[int(datetime.combine(d,time(12),ZoneInfo("America/New_York")).timestamp()) for d in yahoo_dates]
    yahoo_close=[100.0]*len(yahoo_dates)
    if bad_yahoo_close: yahoo_close[sessions.index(date(2019,8,1))]=None
    chart={"chart":{"result":[{"meta":{"symbol":"SPY","exchangeTimezoneName":"America/New_York"},"timestamp":timestamps,
        "indicators":{"quote":[{"open":[99.99]*len(yahoo_dates),"close":yahoo_close}]},"events":{"dividends":{},"splits":{}}}],"error":None}}
    (root/"yahoo_SPY_20190801_20190904.json").write_text(json.dumps(chart))
    for n in ("provider_sample_files.html","provider_data_structure.html"):(root/n).write_text("fixture docs")
    records=[]
    for name in RECEIPT_NAMES:
        p=root/name
        records.append({"path":str(p),"bytes":p.stat().st_size,"sha256":sha256(p),"url":"fixture"})
    (root/"replication-acquisition-receipt.json").write_text(json.dumps({"status":"ACQUIRED_NOT_EVALUATED","use_scope":"synthetic fixture","files":records}))
    return root


def _cli_project_fixture(tmp_path):
    source=Path(__file__).resolve().parents[1]
    root=tmp_path/"repo"; root.mkdir()
    for rel in ("scripts/expiry_replication.py","src/spyspx/expiry_replication.py","src/spyspx/expiry_payoff.py","src/spyspx/expiry_extension.py","tests/test_expiry_replication.py"):
        target=root/rel; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source/rel,target)
    (root/".gitignore").write_text("runs/\n")
    subprocess.run(["git","init","-q"],cwd=root,check=True)
    return root


from datetime import timedelta


def test_source_audit_records_vendor_yahoo_close_disagreement_without_reconciliation(tmp_path):
    root=_make_source_fixture(tmp_path/"inputs")
    audit=audit_sources(root,root/"replication-acquisition-receipt.json")
    assert audit["coverage_status"] == "PASS"
    assert audit["provider_vs_yahoo_raw"]["overlap_count"] == 22
    assert audit["provider_vs_yahoo_raw"]["close_mismatches_over_0_01"] == 22
    assert audit["provider_vs_yahoo_raw"]["close_reconciled"] is False
    assert audit["provider_vs_yahoo_raw"]["open_max_abs_difference"] == pytest.approx(0)


@pytest.mark.parametrize("which",["yahoo","provider","provider_invalid"])
def test_invalid_primary_yahoo_or_provider_row_fails_coverage(tmp_path,which):
    root=_make_source_fixture(tmp_path/"inputs",bad_yahoo_close=which=="yahoo",bad_provider_close=which=="provider",invalid_provider_close=which=="provider_invalid")
    audit=audit_sources(root,root/"replication-acquisition-receipt.json")
    assert audit["coverage_status"] == "FAIL"
    if which=="yahoo": assert audit["coverage_checks"]["yahoo_raw_august_coverage_complete"] is False
    elif which=="provider": assert audit["coverage_checks"]["spy_option_underlying_matches_provider_close"] is False
    else: assert audit["coverage_checks"]["provider_stock_raw_rows_valid"] is False


def test_yahoo_omitted_events_key_is_recorded_as_empty_calendar(tmp_path):
    path=tmp_path/"yahoo.json"
    stamp=int(datetime.combine(date(2019,8,1),time(12),ZoneInfo("America/New_York")).timestamp())
    path.write_text(json.dumps({"chart":{"result":[{"meta":{"symbol":"SPY","exchangeTimezoneName":"America/New_York"},"timestamp":[stamp],"indicators":{"quote":[{"open":[100.0],"close":[101.0]}]}}]}}))
    counts=Counter()
    rows,dividends=read_yahoo(path,counts)
    assert rows[date(2019,8,1)]=={"open":100.0,"close":101.0}
    assert dividends==[]
    assert counts["yahoo_event_calendar_status"]=="NO_EVENTS_KEY_RETURNED"
    assert counts["yahoo_dividend_events"]==0
    assert counts["yahoo_splits"]==0


@pytest.mark.parametrize("events",[None, {"dividends":[],"splits":{}}, {"dividends":{},"splits":None}])
def test_yahoo_malformed_present_events_key_is_rejected(tmp_path,events):
    path=tmp_path/"yahoo.json"
    stamp=int(datetime.combine(date(2019,8,1),time(12),ZoneInfo("America/New_York")).timestamp())
    path.write_text(json.dumps({"chart":{"result":[{"meta":{"symbol":"SPY","exchangeTimezoneName":"America/New_York"},"timestamp":[stamp],"indicators":{"quote":[{"open":[100.0],"close":[101.0]}]},"events":events}]}}))
    with pytest.raises(ValueError,match="malformed present event"):
        read_yahoo(path,Counter())


def test_source_audit_cli_success_writes_no_outcome_artifacts(tmp_path,monkeypatch):
    import scripts.expiry_replication as cli
    root=_make_source_fixture(tmp_path/"inputs")
    project=_cli_project_fixture(tmp_path)
    monkeypatch.setattr(cli,"ROOT",project)
    protocol=tmp_path/"protocol.md"; protocol.write_text("**Status: NOT RUN.**")
    output=project/"runs"
    output.mkdir()
    code=cli.main(["source-audit","--input-root",str(root),"--protocol",str(protocol),"--output-root",str(output)])
    assert code==0
    run=next(output.iterdir())
    assert (run/"source_audit.json").is_file()
    assert not (run/"pair_rows.json").exists()


def test_run_cli_dirty_git_fails_before_output(tmp_path,monkeypatch):
    import scripts.expiry_replication as cli
    root=_make_source_fixture(tmp_path/"inputs")
    project=_cli_project_fixture(tmp_path)
    monkeypatch.setattr(cli,"ROOT",project)
    monkeypatch.setattr(cli,"git",lambda root,*args:"dirty" if args==("status","--porcelain=v1") else "sha")
    protocol=tmp_path/"protocol.md"; protocol.write_text("**Status: NOT RUN.**")
    output=project/"runs"
    output.mkdir()
    code=cli.main(["run","--input-root",str(root),"--protocol",str(protocol),"--output-root",str(output)])
    assert code==2 and not list(output.iterdir())


def test_run_cli_synthetic_success_separates_primary_and_provider_control(tmp_path,monkeypatch):
    import scripts.expiry_replication as cli
    root=_make_source_fixture(tmp_path/"inputs")
    project=_cli_project_fixture(tmp_path)
    monkeypatch.setattr(cli,"ROOT",project)
    monkeypatch.setattr(cli,"git",lambda root,*args:"" if args==("status","--porcelain=v1") else "synthetic-sha")
    protocol=tmp_path/"protocol.md"; protocol.write_text("**Status: NOT RUN.** Frozen synthetic test protocol.")
    output=project/"runs"
    output.mkdir()
    code=cli.main(["run","--input-root",str(root),"--protocol",str(protocol),"--output-root",str(output)])
    assert code==0
    run=next(output.iterdir())
    pairs=json.loads((run/"pair_rows.json").read_text())
    controls=json.loads((run/"provider_terminal_control_rows.json").read_text())
    manifest=json.loads((run/"manifest.json").read_text())
    assert len(pairs)==9 and all(r["reference_lane"]=="PRIMARY_YAHOO_RAW_SPY_CLOSE" for r in pairs)
    assert len(controls)==27 and all(r["timing_status"]=="UNRESOLVED_PROVIDER_SNAPSHOT_CLOSE" for r in controls)
    assert all(r["depth_status"]=="UNAVAILABLE_SOURCE_NO_SIZES" for r in pairs)
    assert manifest["integrity_status"]=="UNCHANGED"
    assert manifest["snapshot_before"]==manifest["snapshot_after"]


@pytest.mark.parametrize("mutated",["protocol","code","input","git"])
def test_run_cli_integrity_mutation_writes_no_payoff_outputs(tmp_path,monkeypatch,mutated):
    import scripts.expiry_replication as cli
    root=_make_source_fixture(tmp_path/"inputs")
    project=_cli_project_fixture(tmp_path)
    monkeypatch.setattr(cli,"ROOT",project)
    monkeypatch.setattr(cli,"git",lambda root,*args:"" if args==("status","--porcelain=v1") else "synthetic-sha")
    original=cli.snapshot; calls=0
    def changed(*args):
        nonlocal calls
        calls+=1; snap=original(*args)
        if calls==2:
            if mutated=="protocol": snap["protocol"]["sha256"]="mutated"
            elif mutated=="code": snap["code_sha256"]["scripts/expiry_replication.py"]["sha256"]="mutated"
            elif mutated=="input": snap["inputs"]["Sample_L2_2019_August.zip"]["sha256"]="mutated"
            else: snap["git_state"]="dirty"
        return snap
    monkeypatch.setattr(cli,"snapshot",changed)
    protocol=tmp_path/"protocol.md"; protocol.write_text("**Status: NOT RUN.** Frozen synthetic test protocol.")
    output=project/"runs"
    output.mkdir()
    code=cli.main(["run","--input-root",str(root),"--protocol",str(protocol),"--output-root",str(output)])
    assert code==2 and not list(output.iterdir())
