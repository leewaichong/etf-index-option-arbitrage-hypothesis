from collections import Counter
from datetime import date, timedelta
import importlib.util
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import expiry_extension as cli_module

import pytest

from spyspx.expiry_payoff import Quote
from spyspx.expiry_extension import cost_adjusted, expiry_ledger, fill_credits, select_official, size_eligible, source_value_reconciliation

CLI=ROOT/'scripts/expiry_extension.py'

def q(root,k,bid=2,ask=3,day=date(2022,9,15),exp=date(2022,9,16),close=None):
    close=close or (400 if root=='SPY' else 4000)
    return Quote(f'{root}{exp:%y%m%d}C{int(k*1000):08d}',root,exp,'call',float(k),
      'A' if root=='SPY' else 'E',day,bid,ask,close,'PM')

def test_official_selection_uses_official_entry_references_and_stable_ties():
    quotes=[q('SPY',399),q('SPY',401),q('SPXW',3990),q('SPXW',4010)]
    out=select_official(quotes,{date(2022,9,15):400},{date(2022,9,15):4000})
    assert len(out)==1 and out[0][0].strike==399  # equal ATM distance, lower strike wins
    # Vendor refs make 401 the closest contract, while the official refs choose 399.
    vendor=[q('SPY',399,close=401),q('SPY',401,close=401),q('SPXW',3990,close=4010),q('SPXW',4010,close=4010)]
    corrected=select_official(vendor,{date(2022,9,15):399},{date(2022,9,15):3990})
    assert corrected[0][0].strike==399
    vendor_selected=select_official(vendor,{date(2022,9,15):401},{date(2022,9,15):4010})
    assert vendor_selected[0][0].strike==401 and corrected[0][0].strike!=vendor_selected[0][0].strike

def test_future_observations_do_not_enter_entry_selection():
    base=[q('SPY',400),q('SPXW',4000)]
    ref={date(2022,9,15):400}
    chosen=select_official(base,ref,{date(2022,9,15):4000})
    later=[q('SPY',410,day=date(2022,9,16),exp=date(2022,9,17)),q('SPXW',4100,day=date(2022,9,16),exp=date(2022,9,17))]
    assert select_official(base+later,ref,{date(2022,9,15):4000})==chosen

def test_duplicate_quotes_count_consistent_and_exclude_conflicts():
    counts={}; a=q('SPY',400); i=q('SPXW',4000)
    assert len(select_official([a,a,i],{a.quote_date:400},{a.quote_date:4000},counts))==1
    assert counts['duplicate']==1
    counts={}; bad=Quote(a.contract,a.underlying,a.expiration,a.right,a.strike,a.style,a.quote_date,1,2,a.underlying_close,a.settlement_time)
    assert select_official([a,bad,i],{a.quote_date:400},{a.quote_date:4000},counts)==[]
    assert counts['duplicate_conflict']==1

def test_fill_signs_reverse_control_and_monotonicity():
    f=fill_credits(q('SPY',400,4,6),q('SPXW',4000,39,41))
    assert f['midpoint']==1000 and f['full_cross']==-100 and f['halfway']==450
    assert f['reverse_full_cross_control']==-2100
    assert f['full_cross']<=f['halfway']<=f['midpoint']
    assert f['zero_control']==0

def test_size_filter_does_not_choose_a_replacement():
    selected=(q('SPY',400),q('SPXW',4000))
    alternative=(q('SPY',399),q('SPXW',3990))
    assert not size_eligible(9,1) and size_eligible(10,1)
    assert not size_eligible(math.nan,1) and not size_eligible(-1,1)
    assert selected[0].strike==400 and alternative[0].strike==399

def test_assignment_threshold_cash_shares_close_identity_and_missing_cover():
    s,i=q('SPY',400),q('SPXW',4000)
    below=expiry_ledger(spy=s,idx=i,credit=0,expiry_close=400.009,spxw_settlement=4000,next_open=None,
      expiry_date=s.expiration,entry_date=s.quote_date)
    assert not below['assigned'] and below['complete_cover'] and below['next_open_pnl']==0
    assert abs(below['threshold_residual_cash'])<10
    at=expiry_ledger(spy=s,idx=i,credit=0,expiry_close=400.01,spxw_settlement=4000,next_open=None,
      expiry_date=s.expiration,entry_date=s.quote_date)
    assert at['assigned'] and at['next_open_pnl'] is None and not at['complete_cover']
    assert abs(at['threshold_residual_cash'])<10
    row=expiry_ledger(spy=s,idx=i,credit=100,expiry_close=401,spxw_settlement=4001,next_open=402,
      expiry_date=s.expiration,entry_date=s.quote_date,cover_date=date(2022,9,19))
    assert row['spy_leg_expiry_cash']==400000 and row['spy_leg_expiry_shares']==-1000
    assert row['spy_leg_next_open_cash']==-402000 and row['spxw_leg_terminal_cash']==100
    assert row['direct_intrinsic_pnl']==row['conditional_close_mark_pnl']

def test_dividend_window_and_act365_costs():
    s,i=q('SPY',400),q('SPXW',4000); cover=date(2022,9,19)
    row=expiry_ledger(spy=s,idx=i,credit=-20,expiry_close=401,spxw_settlement=4000,next_open=402,
      expiry_date=s.expiration,entry_date=s.quote_date,cover_date=cover,
      dividends=[(date(2022,9,16),.1),(date(2022,9,19),.2),(date(2022,9,20),.3)])
    assert row['dividend_carry_amount']==200 and row['dividend_carry_dates']==['2022-09-19']
    assert row['entry_to_expiry_dividend_exposure']
    base=cost_adjusted(100,-20,True,4,3,401); stress=cost_adjusted(100,-20,True,4,3,401,stress=True)
    assert stress<base<100
    assert cost_adjusted(100,-20,False,1,0,401)<100
    with pytest.raises(ValueError): cost_adjusted(1,1,True,-1,2,400)

@pytest.mark.parametrize('bad',[math.nan,math.inf,-math.inf])
def test_nonfinite_ledger_inputs_fail(bad):
    with pytest.raises(ValueError): expiry_ledger(spy=q('SPY',400),idx=q('SPXW',4000),credit=0,
      expiry_close=bad,spxw_settlement=4000,next_open=401,expiry_date=date(2022,9,16),entry_date=date(2022,9,15))

def synthetic_files(tmp):
    from spyspx.expiry_payoff_source import SCHEMA
    (tmp/'.gitignore').write_text('runs/\n')
    options=tmp/'options.zip'; stocks=tmp/'stocks.zip'; spx=tmp/'spx.csv'
    def row(root,day,expiry,k,close,bid,ask,bs='10',asz='1'):
        x={c:'' for c in SCHEMA}; x.update(contract=f'{root}{expiry[2:4]}{expiry[5:7]}{expiry[8:10]}C{int(k*1000):08d}',underlying=root,
          expiration=expiry,type='call',strike=str(k),style='A' if root=='SPY' else 'E',quote_date=day,bid=str(bid),ask=str(ask),
          bid_size=bs,ask_size=asz,underlying_close=str(close),settlement_time='PM'); return x
    import csv,io
    with zipfile.ZipFile(options,'w') as z:
      for day,rows in [('2022-09-15',[row('SPY','2022-09-15','2022-09-16',400,400,2,3,'0','1'),row('SPXW','2022-09-15','2022-09-16',4000,4000,20,21,'10','0'),
                                            row('SPY','2022-09-15','2022-09-16',399,400,2,3,'10','1'),row('SPXW','2022-09-15','2022-09-16',3990,4000,20,21,'10','1')]),
                       ('2022-09-16',[row('SPY','2022-09-16','2022-09-16',400,401,2,3),row('SPXW','2022-09-16','2022-09-16',4000,4000,20,21)])]:
        buf=io.StringIO(); w=csv.DictWriter(buf,fieldnames=SCHEMA); w.writeheader(); w.writerows(rows); z.writestr(f'day_by_date/{day}_options.csv',buf.getvalue())
    with zipfile.ZipFile(stocks,'w') as z:z.writestr('day_by_symbol/SPY_day.csv','date,open,close,dividend,adj_open,adj_close,split\n2022-09-15,399,400,0,1,1,0\n2022-09-16,400,401,0,1,1,0\n2022-09-19,402,403,0,1,1,0\n')
    spx.write_text('Date,Close\n2022-09-15,4000\n2022-09-16,4000\n2022-09-19,4000\n')
    sessions=[]; day=date(2022,7,1)
    while day<=date(2022,12,30):
      if day.weekday()<5:sessions.append(day)
      day+=timedelta(days=1)
    sessions=sessions[3:]
    settlement_dates=sessions[:115]
    kinds=[]
    for name,ds in [('w',settlement_dates),('m',sessions[115:121]),('q',sessions[121:127])]:
      path=tmp/f'{name}.json'; records=[]
      for d in ds: records.append({'description':'PM settlement','trading_symbol':'SPXW','expiration_date':d.isoformat(),'settlement_symbol':'SPX','settlement_value':4000,'display_order':1})
      path.write_text(json.dumps(records)); kinds.append(path)
    receipt=tmp/'receipt.json'
    official=[stocks,spx,*kinds]
    receipt.write_text(json.dumps({'files':[{'path':str(x),'bytes':x.stat().st_size,'sha256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in official]}))
    protocol=tmp/'synthetic-protocol.md'; protocol.write_text('fixture only\n')
    return options,stocks,spx,kinds,receipt,protocol

def invoke(tmp,mode,files):
    options,stocks,spx,settles,receipt,protocol=files; output=tmp/'runs'
    cmd=[sys.executable,str(CLI),mode,'--options-zip',str(options),'--stocks-zip',str(stocks),'--spx-csv',str(spx),
      '--weekly-json',str(settles[0]),'--monthly-json',str(settles[1]),'--quarterly-json',str(settles[2]),
      '--receipt',str(receipt),'--protocol',str(protocol),'--output-root',str(output)]
    env=os.environ.copy(); env['PYTHONPATH']=str(ROOT/'src')
    return subprocess.run(cmd,cwd=tmp,env=env,text=True,capture_output=True)

def test_cli_fixture_audit_and_run_artifacts_no_raw_quotes(tmp_path):
    files=synthetic_files(tmp_path)
    audit=invoke(tmp_path,'audit',files); assert audit.returncode==0,audit.stderr
    auditdir=Path(json.loads(audit.stdout)['output']); assert not (auditdir/'aggregates.json').exists()
    audit_json=json.loads((auditdir/'source_audit.json').read_text())
    assert audit_json['receipt_reconciliation']['status']=='PASS'
    assert audit_json['source_value_reconciliation']['vendor_spy_close_vs_raw_spy_close']['comparable_date_count']==2
    assert 'quote_rows' not in audit_json and 'payoff_rows' not in audit_json
    run=invoke(tmp_path,'run',files); assert run.returncode==0,run.stderr
    dest=Path(json.loads(run.stdout)['output']); ag=json.loads((dest/'aggregates.json').read_text()); pairs=json.loads((dest/'pair_rows.json').read_text())
    assert ag['realized_broker_execution_assignment_account_returns']=='NOT RUN' and ag['status']=='OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED'
    assert len(pairs)>=12 and all('bid' not in r and 'ask' not in r for r in pairs)
    assert ag['original_pair_count']==2 and ag['official_primary_count']==1
    assert {r['lane'] for r in pairs}=={'lane1_original_vendor','lane2_original_official','lane3_original_spx_control','lane4_official_reselection'}
    assert {r['fill'] for r in pairs}=={'midpoint','halfway','full_cross'}
    assert pairs[0]['spy_terminal_reference']==401  # raw close, not adjusted close 1
    assert pairs[0]['next_session_date']=='2022-09-19' and pairs[0]['calendar_days_expiry_to_next_session']==3
    assert ag['equal_expiry_primary_summaries'] and ag['original_equal_cohort_summaries']
    eq=ag['original_equal_cohort_summaries'][0]
    assert eq['expiry_dates']==['2022-09-16'] and eq['expiry_count']==1 and 'exclusions' in eq
    assert eq['metric']=='direct_intrinsic_pnl' and eq['population']=='original_equal_cohort'
    assert ag['common_complete_cover_comparisons'] and all('metric' in x and 'pre_depth_count' in x for x in ag['summaries'])
    primary_rows=[r for r in pairs if r['lane']=='lane4_official_reselection']
    assert {r['spy_contract'] for r in primary_rows}=={q('SPY',400).contract}
    assert all(not r['size_eligible'] for r in primary_rows)
    assert ag['exclusions']['primary_depth_loss']==1
    assert json.loads((dest/'source_audit.json').read_text())['receipt_reconciliation']['status']=='PASS'

def test_cli_missing_source_fails_before_output_directory(tmp_path):
    files=synthetic_files(tmp_path); files[0].unlink()
    result=invoke(tmp_path,'audit',files)
    assert result.returncode!=0 and not (tmp_path/'runs').exists()

def test_stock_parser_uses_raw_fields_and_excludes_conflicting_dates(tmp_path):
    path=tmp_path/'stocks.zip'
    with zipfile.ZipFile(path,'w') as z:
      z.writestr('day_by_symbol/SPY_day.csv','date,open,close,dividend,adj_open,adj_close,split\n'
        '2022-09-15,400,401,0.2,4,5,0\n2022-09-16,1,2,0,100,200,0\n'
        '2022-09-16,3,4,0,300,400,0\n2022-09-19,5,6,0,7,8,0\n2022-09-20,5,6,0,7,8,2\n')
    data,counts,_=cli_module.read_stocks(path)
    assert data[date(2022,9,15)]=={'open':400,'close':401,'dividend':.2}
    assert date(2022,9,16) not in data and date(2022,9,19) in data and date(2022,9,20) not in data
    assert counts['split_events']==1
    assert counts['conflicting_duplicate_date']==1

def test_spx_duplicate_policy_removes_conflict_and_counts_identical(tmp_path):
    path=tmp_path/'spx.csv'; path.write_text('Date,Close\n2022-09-15,4000\n2022-09-15,4000\n2022-09-16,4010\n2022-09-16,4020\n')
    values,counts=cli_module.read_spx(path)
    assert values=={date(2022,9,15):4000}
    assert counts['consistent_duplicate_date']==1 and counts['conflicting_duplicate_date']==1

def test_spx_accepts_exact_official_header_DATE_SPX(tmp_path):
    path=tmp_path/'official.csv'; path.write_text('DATE,SPX\n07/01/2022,3873.33\n')
    values,counts=cli_module.read_spx(path)
    assert values=={date(2022,7,1):3873.33} and counts['usable_dates']==1

def test_blank_stock_dividend_is_zero_and_invalid_session_remains_on_calendar(tmp_path):
    path=tmp_path/'stocks.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('day_by_symbol/SPY_day.csv',
      'date,open,close,dividend,split\n2022-09-16,400,401,,0\n2022-09-19,nan,402,0,0\n2022-09-20,405,406,garbage,0\n')
    prices,counts,sessions=cli_module.read_stocks(path)
    assert prices[date(2022,9,16)]['dividend']==0
    assert date(2022,9,19) in sessions and date(2022,9,19) not in prices
    assert date(2022,9,20) in sessions and date(2022,9,20) not in prices

def test_yahoo_raw_fields_append_only_outside_boundary(tmp_path):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    path=tmp_path/'yahoo.json'; stamps=[int(datetime(2022,12,30,15,tzinfo=timezone.utc).timestamp()),int(datetime(2023,1,3,15,tzinfo=timezone.utc).timestamp())]
    doc={'chart':{'result':[{'meta':{'symbol':'SPY'},'timestamp':stamps,'indicators':{'quote':[{'open':[400,410],'close':[401,411]}],
      'adjclose':[{'adjclose':[1,1]}]},'events':{'dividends':{}}}]}}
    path.write_text(json.dumps(doc)); yahoo,calendar=cli_module.read_yahoo(path)
    old=date(2022,12,30); stocks={old:{'open':400,'close':401,'dividend':1.2345}}; sessions={old}
    report=cli_module.add_yahoo_boundary(stocks,sessions,yahoo,calendar)
    assert stocks[old]['close']==401 and stocks[old]['dividend']==1.2345
    assert date(2023,1,3) in sessions and stocks[date(2023,1,3)]['open']==410
    assert report['append_dates']==['2023-01-03'] and report['max_abs_difference']['close']==0

def test_source_value_reconciliation_reports_comparable_differences():
    d1=date(2022,9,16); d2=date(2022,9,19)
    summary=source_value_reconciliation({(d1,'SPY'):100,(d2,'SPY'):101,(d1,'SPXW'):4000,(d2,'SPXW'):4002},
      {d1:{'close':100},d2:{'close':102}}, {d1:3999,d2:4002},
      {d1:{'value':4000},d2:{'value':4001}})
    spy=summary['vendor_spy_close_vs_raw_spy_close']
    assert spy=={'comparable_date_count':2,'exact_match_count':1,'different_value_count':1,
      'max_absolute_difference':1.0,'mean_absolute_difference':.5}
    vendor_idx=summary['vendor_spxw_close_vs_official_spxw_pm_settlement']
    assert vendor_idx['comparable_date_count']==2 and vendor_idx['exact_match_count']==1 and vendor_idx['mean_absolute_difference']==.5
    official=summary['official_spx_close_vs_official_spxw_pm_settlement']
    assert official['comparable_date_count']==2 and official['exact_match_count']==0
    assert official['different_value_count']==2 and official['max_absolute_difference']==1.0

def test_receipt_passes_and_counts_missing_duplicate_and_mismatch(tmp_path):
    files=synthetic_files(tmp_path)
    paths=[files[1],files[2],*files[3]]
    valid=json.loads(files[4].read_text())
    report=cli_module.validate_receipt(valid,paths)
    assert report['status']=='PASS' and report['passed_entries']==5
    valid['files'][0]['bytes']+=1
    valid['files'].append(dict(valid['files'][1]))
    valid['files']=[x for x in valid['files'] if Path(x['path']).name!=paths[2].name]
    report=cli_module.validate_receipt(valid,paths)
    assert report['status']=='FAIL' and report['mismatched_entries']==1
    assert report['duplicate_entries']==1 and report['missing_entries']==1

def test_receipt_mismatch_fails_run_before_outcome_artifacts(tmp_path):
    files=synthetic_files(tmp_path)
    receipt=json.loads(files[4].read_text()); receipt['files'][0]['sha256']='0'*64
    files[4].write_text(json.dumps(receipt))
    result=invoke(tmp_path,'run',files)
    assert result.returncode==2
    dest=Path(json.loads(result.stdout)['output'])
    audit=json.loads((dest/'source_audit.json').read_text())
    assert audit['status']=='RECEIPT_VALIDATION_FAILED'
    assert audit['receipt_reconciliation']['mismatched_entries']==1
    assert not (dest/'pair_rows.json').exists() and not (dest/'aggregates.json').exists()

def test_quote_size_parser_counts_invalid_sizes_separately(tmp_path):
    from spyspx.expiry_payoff_source import SCHEMA
    path=tmp_path/'sizes.zip'; row={c:'' for c in SCHEMA}
    row.update(contract='SPY220916C00400000',underlying='SPY',expiration='2022-09-16',type='call',strike='400',style='A',
      quote_date='2022-09-15',bid='2',ask='3',bid_size='nan',ask_size='-1',underlying_close='400',settlement_time='PM')
    import csv,io
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=SCHEMA); w.writeheader(); w.writerow(row)
    with zipfile.ZipFile(path,'w') as z:z.writestr('day_by_date/2022-09-15_options.csv',b.getvalue())
    sizes,counts=cli_module.read_size_map(path)
    assert not sizes and counts['invalid_size']==1

def test_settlement_exact_identity_spx_am_filter_and_expected_coverage(tmp_path):
    sessions=[]; d=date(2022,7,1)
    while d<=date(2022,12,30):
      if d.weekday()<5:sessions.append(d)
      d+=timedelta(days=1)
    sessions=sessions[3:]
    files=[]
    for name,dates in [('w',sessions[:115]),('m',sessions[115:121]),('q',sessions[121:127])]:
      p=tmp_path/f'{name}.json'; records=[{'description':'PM','trading_symbol':'SPXW','expiration_date':x.isoformat(),'settlement_symbol':'SPX','settlement_value':4000,'display_order':1} for x in dates]
      records.append({'description':'AM settlement','trading_symbol':'SPX','expiration_date':dates[0].isoformat(),'settlement_symbol':'SPX','settlement_value':4000,'display_order':0})
      p.write_text(json.dumps(records)); files.append(p)
    got,counts,coverage=cli_module.read_settlements(files)
    assert len(got)==127 and counts['expected_coverage_ok']
    assert counts['excluded_spx_am']==3 and all(x['coverage_ok'] for x in coverage)
    weekly=json.loads(files[0].read_text()); weekly.append(dict(weekly[0]))
    conflict=dict(weekly[1]); conflict['settlement_value']=4001; weekly.append(conflict)
    files[0].write_text(json.dumps(weekly))
    got,counts,_=cli_module.read_settlements(files)
    assert counts['consistent_settlement_duplicate']==1 and counts['conflicting_settlement']==1
    assert sessions[1] not in got
    # A missing exact record is a coverage failure, never an arbitrary survivor.
    files[0].write_text('[]')
    _,counts,_=cli_module.read_settlements(files)
    assert not counts['expected_coverage_ok']

def test_settlements_filter_full_year_and_keep_conflicts_excluded_across_files(tmp_path):
    files=[]
    for name,day in [('w','2022-07-01'),('m','2022-07-01'),('s','2022-09-01')]:
      p=tmp_path/f'{name}.json'; p.write_text(json.dumps([
        {'description':'PM','trading_symbol':'SPXW','expiration_date':'2022-01-21','settlement_symbol':'SPX','settlement_value':4000,'display_order':1},
        {'description':'PM','trading_symbol':'SPXW','expiration_date':day,'settlement_symbol':'SPX','settlement_value':4000,'display_order':1},
        {'description':'AM','trading_symbol':'SPX','expiration_date':day,'settlement_symbol':'SPX','settlement_value':4000,'display_order':1}]))
      files.append(p)
    _,counts,_=cli_module.read_settlements(files)
    assert counts['filtered_outside_h2']==3 and counts['excluded_spx_am']==3
    # An invalid value in one file invalidates a valid copy from another file.
    first=json.loads(files[0].read_text()); first[1]['settlement_value']='NaN'; files[0].write_text(json.dumps(first))
    values,counts,_=cli_module.read_settlements(files)
    assert date(2022,7,1) not in values and counts['conflicting_crossfile_settlement']==0

@pytest.mark.parametrize('target',['protocol','source','code','dependency'])
def test_cli_input_mutation_fails_closed_without_outcome_artifacts(tmp_path,monkeypatch,target):
    files=synthetic_files(tmp_path); protocol=files[-1]
    original=cli_module.read_zip
    def mutate(path):
      result=original(path)
      if target=='protocol':protocol.write_text('changed after snapshot')
      elif target=='source':files[0].write_bytes(files[0].read_bytes()+b'changed')
      return result
    monkeypatch.setattr(cli_module,'read_zip',mutate)
    if target in ('code','dependency'):
      real_snap=cli_module.snap; calls={'n':0}
      def mutate_code_snapshot(paths,protocol_path):
        value=real_snap(paths,protocol_path); calls['n']+=1
        if calls['n']==2:
          key='extension_sha256' if target=='code' else 'dependency_sha256'
          fname='src/spyspx/expiry_extension.py' if target=='code' else 'src/spyspx/expiry_payoff.py'
          value[key][fname]='changed'
        return value
      monkeypatch.setattr(cli_module,'snap',mutate_code_snapshot)
    monkeypatch.setattr(sys,'argv',[str(CLI),'run','--options-zip',str(files[0]),'--stocks-zip',str(files[1]),
      '--spx-csv',str(files[2]),'--weekly-json',str(files[3][0]),'--monthly-json',str(files[3][1]),
      '--quarterly-json',str(files[3][2]),'--receipt',str(files[4]),'--protocol',str(protocol),'--output-root',str(tmp_path/'runs')])
    monkeypatch.chdir(tmp_path)
    assert cli_module.main()==2
    dests=list((tmp_path/'runs').iterdir()); assert len(dests)==1
    dest=dests[0]
    assert json.loads((dest/'manifest.json').read_text())['integrity_status']=='CHANGED_DURING_PROCESSING'
    assert not (dest/'pair_rows.json').exists() and not (dest/'aggregates.json').exists()

def test_cli_no_usable_pairs_fails_without_outcome_artifacts(tmp_path):
    files=synthetic_files(tmp_path)
    with zipfile.ZipFile(files[0],'w'):pass
    result=invoke(tmp_path,'run',files); assert result.returncode==2
    dest=Path(json.loads(result.stdout)['output'])
    assert not (dest/'pair_rows.json').exists() and not (dest/'aggregates.json').exists()

def test_invalid_raw_duplicate_invalidates_whole_stock_date(tmp_path):
    path=tmp_path/'stocks.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr('day_by_symbol/SPY_day.csv',
      'date,open,close,dividend,adj_close\n2022-09-16,400,401,0,1\n2022-09-16,nan,402,0,1\n')
    values,counts,_=cli_module.read_stocks(path)
    assert date(2022,9,16) not in values and counts['invalid_raw_date_exclusion']==1

def test_malformed_source_fails_with_audit_and_manifest_only(tmp_path):
    files=synthetic_files(tmp_path)
    with zipfile.ZipFile(files[1],'w') as z:z.writestr('day_by_symbol/SPY_day.csv','wrong,header\nx,y\n')
    result=invoke(tmp_path,'run',files)
    assert result.returncode==2
    dest=Path(json.loads(result.stdout)['output'])
    assert (dest/'manifest.json').is_file() and (dest/'source_audit.json').is_file()
    assert not (dest/'pair_rows.json').exists() and not (dest/'aggregates.json').exists()
