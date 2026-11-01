#!/usr/bin/env python3
"""Audit explicit expiry inputs or run the synthetic-tested extension pipeline."""
from __future__ import annotations

import argparse, csv, hashlib, io, json, math, os, platform, socket, subprocess, sys, zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from spyspx.expiry_extension import cost_adjusted, expiry_ledger, fill_credits, fill_cash_terms, select_official, size_eligible, source_value_reconciliation
from spyspx.expiry_payoff import select_pairs
from spyspx.expiry_payoff_source import SCHEMA, read_zip

ROOT=Path(__file__).resolve().parents[1]
EXT_FILES=[ROOT/'scripts/expiry_extension.py',ROOT/'src/spyspx/expiry_extension.py',ROOT/'tests/test_expiry_extension.py']
DEPENDENCIES=[ROOT/'src/spyspx/expiry_payoff.py',ROOT/'src/spyspx/expiry_payoff_source.py']

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def receipt_records(document):
    """Find receipt entries without treating unrelated metadata as an input record."""
    found=[]
    def visit(node,key_hint=None):
      if isinstance(node,list):
        for item in node:visit(item)
      elif isinstance(node,dict):
        path=next((node[k] for k in ('path','file','filename','name','basename','input_path','source_path','local_path') if isinstance(node.get(k),str)),None)
        if path is None and isinstance(key_hint,str) and Path(key_hint).name==key_hint and '.' in key_hint:path=key_hint
        if path is not None:
          found.append({'path':path,
            'bytes':next((node[k] for k in ('bytes','byte_count','size_bytes','file_size_bytes','size') if k in node),None),
            'sha256':next((node[k] for k in ('sha256','sha_256','checksum_sha256','file_sha256','hash_sha256') if k in node),None)})
        else:
          for key,value in node.items():visit(value,key)
    visit(document)
    return found

def validate_receipt(document, official_paths):
    entries=receipt_records(document); byname=defaultdict(list)
    for entry in entries:byname[Path(entry['path']).name].append(entry)
    required=[]; passed=0; missing=duplicates=mismatches=0
    for path in official_paths:
      matches=byname.get(path.name,[]); problems=[]
      if not matches:missing+=1; problems.append('missing_entry')
      elif len(matches)>1:duplicates+=1; problems.append('duplicate_entries')
      if len(matches)==1:
        record=matches[0]
        try: byte_match=int(record['bytes'])==path.stat().st_size
        except (TypeError,ValueError,OverflowError):byte_match=False
        hash_match=isinstance(record['sha256'],str) and record['sha256'].lower()==sha(path).lower()
        if not byte_match:problems.append('byte_count_mismatch')
        if not hash_match:problems.append('sha256_mismatch')
        if not byte_match or not hash_match:mismatches+=1
      else:byte_match=hash_match=False
      if not problems:passed+=1
      required.append({'basename':path.name,'status':'PASS' if not problems else 'FAIL','problems':problems})
    return {'status':'PASS' if passed==len(official_paths) else 'FAIL','required_entries':len(official_paths),
      'passed_entries':passed,'missing_entries':missing,'duplicate_entries':duplicates,'mismatched_entries':mismatches,
      'entries':required}

def ignored_output(path):
    path=path.resolve()
    for parent in (path,*path.parents):
      rulefile=parent/'.gitignore'
      if not rulefile.is_file():continue
      try: rules=[x.strip().rstrip('/') for x in rulefile.read_text().splitlines() if x.strip() and not x.lstrip().startswith('#') and not x.startswith('!')]
      except OSError:continue
      try: rel=path.relative_to(parent)
      except ValueError:continue
      parts=rel.parts
      if any(rule==str(parts[0]) or rule==str(rel) for rule in rules):return True
    return False

def snap(paths,protocol):
    git=lambda *a: subprocess.run(['git',*a],cwd=ROOT,text=True,capture_output=True).stdout.strip()
    return {'git_sha':git('rev-parse','HEAD'),'git_status':git('status','--porcelain'),
            'files':{str(p):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths},
            'protocol':{'path':str(protocol),'sha256':sha(protocol)},
            'extension_sha256':{str(p.relative_to(ROOT)):sha(p) for p in EXT_FILES},
            'dependency_sha256':{str(p.relative_to(ROOT)):sha(p) for p in DEPENDENCIES}}

def read_stocks(path):
    counts=Counter(); valid={}; rejected=set(); sessions=set()
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n=='day_by_symbol/SPY_day.csv']
        if len(names)!=1: raise ValueError('expected exactly one day_by_symbol/SPY_day.csv member')
        rows=csv.DictReader(io.TextIOWrapper(z.open(names[0]),encoding='utf-8-sig'))
        fields=set(rows.fieldnames or [])
        if not {'date','open','close','dividend'} <= fields: raise ValueError('stock raw schema missing date/open/close/dividend')
        for r in rows:
            counts['rows']+=1
            try:
                d=date.fromisoformat(r['date'])
            except (TypeError,ValueError):
                counts['invalid_date']+=1; continue
            sessions.add(d)
            try:
                op,cl=float(r['open']),float(r['close'])
                dividend_text=(r.get('dividend') or '').strip()
                dv=0.0 if not dividend_text else float(dividend_text)
                split=float(r.get('split') or r.get('splits') or 0)
                if not all(math.isfinite(x) for x in (op,cl,dv,split)) or op<=0 or cl<=0 or dv<0 or split<0: raise ValueError
            except (TypeError,ValueError,OverflowError):
                counts['invalid_raw_row']+=1; counts['invalid_raw_date_exclusion']+=1; rejected.add(d); continue
            if split not in (0,1):
                counts['split_events']+=1; rejected.add(d); continue
            if d in valid:
                counts['duplicate_date']+=1
                if valid[d] != (op,cl,dv): counts['conflicting_duplicate_date']+=1; rejected.add(d)
                else: counts['consistent_duplicate_date']+=1
            else: valid[d]=(op,cl,dv)
    for d in rejected: valid.pop(d,None)
    counts['usable_sessions']=len(valid)
    counts['calendar_sessions']=len(sessions)
    return {d:{'open':v[0],'close':v[1],'dividend':v[2]} for d,v in valid.items()},counts,sessions

def read_spx(path):
    counts=Counter(); seen={}; conflicts=set()
    with path.open(newline='',encoding='utf-8-sig') as f:
        rdr=csv.DictReader(f)
        fields=set(rdr.fieldnames or [])
        if {'DATE','SPX'}<=fields: date_col,value_col='DATE','SPX'
        elif {'Date','Close'}<=fields: date_col,value_col='Date','Close'
        elif {'date','close'}<=fields: date_col,value_col='date','close'
        else: raise ValueError('SPX schema requires DATE,SPX or a supported date/close pair')
        for r in rdr:
            try:
                raw_date=r[date_col].strip()
                d=(datetime.strptime(raw_date,'%m/%d/%Y').date() if date_col=='DATE' else date.fromisoformat(raw_date))
                v=float(r[value_col])
            except (ValueError,TypeError): counts['invalid_rows']+=1; continue
            if not math.isfinite(v) or v<=0: counts['invalid_rows']+=1; conflicts.add(d); continue
            if d in seen:
                counts['duplicate_date']+=1
                if seen[d]!=v: conflicts.add(d); counts['conflicting_duplicate_date']+=1
                else: counts['consistent_duplicate_date']+=1
            else: seen[d]=v
    for d in conflicts: seen.pop(d,None)
    counts['usable_dates']=len(seen)
    return seen,counts

def read_settlements(paths):
    bydate={}; counts=Counter(); conflicts=set(); perfile=[]
    for label,path,expected in zip(('W','M','S'),paths,(115,6,6)):
        records=json.loads(path.read_text()); records=records.get('data',records.get('results',[])) if isinstance(records,dict) else records
        local={}; local_conflicts=set(); h2_start=date(2022,7,1); h2_end=date(2022,12,30)
        for r in records:
            if r.get('trading_symbol')!='SPXW' or r.get('settlement_symbol')!='SPX':
                counts['filtered_wrong_identity']+=1
                if r.get('trading_symbol')=='SPX' or 'AM' in str(r.get('description','')).upper(): counts['excluded_spx_am']+=1
                continue
            try: d=date.fromisoformat(r['expiration_date'])
            except (KeyError,ValueError,TypeError): counts['invalid_settlement']+=1; continue
            if not h2_start<=d<=h2_end:
                counts['filtered_outside_h2']+=1; continue
            try:
                v=float(r['settlement_value']); order=int(r['display_order'])
                if not math.isfinite(v) or v<=0: raise ValueError
                key=(r['description'],r['trading_symbol'],d,r['settlement_symbol'],v,order)
            except (KeyError,ValueError,TypeError): counts['invalid_settlement']+=1; local_conflicts.add(d); continue
            if d in local_conflicts:
                counts['settlement_conflict_persisted']+=1; continue
            if d in local:
                counts['duplicate_settlement']+=1
                if local[d]!=key: local_conflicts.add(d); counts['conflicting_settlement']+=1
                else: counts['consistent_settlement_duplicate']+=1
            else: local[d]=key
        for d in local_conflicts: local.pop(d,None)
        conflicts.update(local_conflicts)
        for d in local_conflicts: bydate.pop(d,None)
        for d,key in local.items():
            if d in conflicts: continue
            if d in bydate and bydate[d]!=key: conflicts.add(d); bydate.pop(d,None); counts['conflicting_crossfile_settlement']+=1
            else: bydate[d]=key
        perfile.append({'kind':label,'expected_h2_unique_dates':expected,'usable_h2_unique_dates':sum(h2_start<=d<=h2_end for d in local),
                        'coverage_ok':sum(h2_start<=d<=h2_end for d in local)==expected})
    for d in conflicts: bydate.pop(d,None)
    counts['unique_dates']=len(bydate)
    counts['expected_coverage_ok']=(len(bydate)==127 and all(x['coverage_ok'] for x in perfile)
       and all(date(2022,7,1)<=d<=date(2022,12,30) for d in bydate))
    return {d:{'value':v[4],'description':v[0]} for d,v in bydate.items()},counts,perfile

def read_yahoo(path):
    doc=json.loads(path.read_text()); result=doc['chart']['result'][0]
    if result.get('meta',{}).get('symbol')!='SPY': raise ValueError('Yahoo chart symbol must be SPY')
    quote=result['indicators']['quote'][0]; rows={}; sessions=set()
    for i,stamp in enumerate(result.get('timestamp',[])):
        d=datetime.fromtimestamp(stamp,ZoneInfo('America/New_York')).date(); sessions.add(d)
        op=quote.get('open',[None]*len(result['timestamp']))[i]; cl=quote.get('close',[None]*len(result['timestamp']))[i]
        dividend=0.0
        for _,event in result.get('events',{}).get('dividends',{}).items():
            if datetime.fromtimestamp(int(event['date']),ZoneInfo('America/New_York')).date()==d: dividend=float(event['amount'])
        if op is not None and cl is not None and math.isfinite(float(op)) and math.isfinite(float(cl)) and op>0 and cl>0:
            rows[d]={'open':float(op),'close':float(cl),'dividend':dividend}
    return rows,sessions

def add_yahoo_boundary(stocks,sessions,yahoo,yahoo_sessions):
    overlap=sorted(set(stocks)&set(yahoo)); diffs={k:[abs(stocks[d][k]-yahoo[d][k]) for d in overlap] for k in ('open','close','dividend')}
    if any(abs(stocks[d]['close']-yahoo[d]['close'])>0.01 for d in overlap): raise ValueError('Yahoo SPY raw close reconciliation exceeds $0.01')
    appended=[]
    if stocks:
        last=max(stocks); next_candidates=sorted(d for d in yahoo_sessions if d>last)
        if next_candidates:
            d=next_candidates[0]; sessions.add(d); appended.append(d.isoformat())
            if d in yahoo: stocks[d]=yahoo[d]
    return {'source':'Yahoo chart raw open/close/dividends','symbol':'SPY','overlap_dates':len(overlap),
      'max_abs_difference':{k:max(v) if v else None for k,v in diffs.items()},'append_dates':appended,
      'appended_price_available':bool(appended and date.fromisoformat(appended[0]) in stocks)}

def read_size_map(path):
    result={}; counts=Counter(); conflicts=set()
    with zipfile.ZipFile(path) as z:
        members=sorted(n for n in z.namelist() if n.endswith('_options.csv'))
        for member in members:
            with z.open(member) as raw:
                reader=csv.DictReader(io.TextIOWrapper(raw,encoding='utf-8-sig'))
                if tuple(reader.fieldnames or ())!=SCHEMA: counts['schema_mismatch_file']+=1; continue
                for r in reader:
                    if r.get('underlying') not in ('SPY','SPXW') or (r.get('type') or '').lower()!='call': continue
                    try: key=(date.fromisoformat(r['quote_date']),r['contract'].upper()); bs=float(r['bid_size']); ask=float(r['ask_size'])
                    except (ValueError,TypeError): counts['missing_or_malformed_size']+=1; continue
                    if not math.isfinite(bs) or not math.isfinite(ask) or bs<0 or ask<0:
                        counts['invalid_size']+=1; continue
                    if key in result and result[key]!=(bs,ask): counts['conflicting_size_metadata']+=1; conflicts.add(key)
                    elif key in result: counts['duplicate_size_metadata']+=1
                    elif key not in conflicts: result[key]=(bs,ask)
    for key in conflicts: result.pop(key,None)
    return result,counts

def percentile_summary(rows,metric,labels):
    vals=[r[metric] for r in rows if isinstance(r.get(metric),(int,float)) and math.isfinite(r[metric])]
    dates=sorted({r['expiry_date'] for r in rows if r.get('expiry_date')})
    exclusions=Counter(reason for r in rows for reason in r.get('missing_inputs',[]))
    if labels.get('depth')=='size_eligible':exclusions['depth_filter_loss']=labels.get('depth_filter_loss',sum(not r.get('size_eligible',False) for r in rows))
    reasons=Counter(reason for r in rows for reason in r.get('missing_inputs',[]))
    meta={**labels,'metric':metric,'valid_rows':len(vals),'pre_depth_count':labels.get('pre_depth_count',len(rows)),
      'after_depth_count':labels.get('after_depth_count',len(rows)),
      'missing_outcomes':len(rows)-len(vals),'expiry_count':len(dates),'expiry_dates':dates,'missing_outcome_reasons':dict(reasons)}
    if not vals:return {**meta,'denominator':0,'rows_considered':len(rows),'missing_outcome_count':len(rows),'exclusions':dict(exclusions),'mean':None,'median':None,'worst_loss':None,'positive_count':0}
    s=sorted(vals); return {**meta,'denominator':len(vals),'mean':sum(vals)/len(vals),
      'rows_considered':len(rows),'missing_outcome_count':len(rows)-len(vals),
      'expiry_count':len(dates),'expiry_dates':dates,'exclusions':dict(exclusions),
      'median':(s[(len(s)-1)//2]+s[len(s)//2])/2,'worst_loss':min(vals),'positive_count':sum(v>0 for v in vals)}

def depth_period_counts(selected, subset, period):
    def matches(row):
      d=date.fromisoformat(row['expiry_date'])
      return period=='all' or period=='Q3' and d.month in (7,8,9) or period=='Q4' and d.month in (10,11,12) or period not in ('all','Q3','Q4') and row['expiry_date'].startswith(period)
    pre=sum(matches(r) for r in selected); after=sum(matches(r) for r in subset)
    return {'pre_depth_count':pre,'after_depth_count':after,'depth_filter_loss':pre-after}

def build_rows(quotes,vendor,stocks,spx,settle,sizes,sizecounts,sessions=None):
    original=select_pairs(quotes); official=select_official(quotes,{d:x['close'] for d,x in stocks.items()},spx)
    sessions=sorted(sessions if sessions is not None else stocks); following={d:sessions[i+1] for i,d in enumerate(sessions[:-1])}
    out=[]; exclusions=Counter(); pairsets={'lane1_original_vendor':original,'lane2_original_official':original,
      'lane3_original_spx_control':original,'lane4_official_reselection':official}
    for lane,pairs in pairsets.items():
      for spy,idx,ratio in pairs:
        exp=spy.expiration; entry=spy.quote_date; nextday=following.get(exp)
        dayrow=stocks.get(exp); nextrow=stocks.get(nextday) if nextday else None
        identity=(entry,spy.contract),(entry,idx.contract)
        refs={}
        if lane=='lane1_original_vendor':
            refs={'spx':vendor.get((exp,'SPXW')),'spy':vendor.get((exp,'SPY')),'source':'vendor_underlying_close'}
        elif lane=='lane3_original_spx_control': refs={'spx':spx.get(exp),'spy':dayrow['close'] if dayrow else None,'source':'official_spx_close_and_raw_spy_close'}
        else: refs={'spx':settle.get(exp,{}).get('value'),'spy':dayrow['close'] if dayrow else None,'source':'official_spxw_pm_and_raw_spy_close'}
        credits=fill_credits(spy,idx)
        meta_spy=sizes.get(identity[0]); meta_idx=sizes.get(identity[1])
        has_size=meta_spy is not None and meta_idx is not None
        size_ok=has_size and size_eligible(meta_spy[0],meta_idx[1])
        if lane=='lane4_official_reselection':
          if not has_size: exclusions['primary_missing_size']+=1
          elif not size_ok: exclusions['primary_depth_loss']+=1
        for fill in ('midpoint','halfway','full_cross'):
          credit=credits[fill]
          missing=[]
          if dayrow is None: missing.append('spy_expiry_close')
          if refs['spx'] is None: missing.append('spx_terminal')
          if refs['spy'] is None: missing.append('spy_terminal')
          for reason in missing: exclusions['missing_'+reason]=exclusions.get('missing_'+reason,0)+1
          ledger=None
          if not missing:
            try:
              ledger=expiry_ledger(spy=spy,idx=idx,credit=credit,expiry_close=refs['spy'],
                 spxw_settlement=refs['spx'],next_open=nextrow['open'] if nextrow else None,
                 expiry_date=exp,entry_date=entry,cover_date=nextday,
                 dividends=[(d,r['dividend']) for d,r in stocks.items() if r['dividend']>0])
            except (ValueError,AssertionError) as exc: missing.append('ledger:'+str(exc))
          row={'lane':lane,'population':'primary_one_per_expiry' if lane=='lane4_official_reselection' else 'original_all_alternatives',
            'entry_date':entry.isoformat(),'expiry_date':exp.isoformat(),'next_session_date':nextday.isoformat() if nextday else None,
            'calendar_days_entry_to_expiry':(exp-entry).days,'calendar_days_expiry_to_next_session':(nextday-exp).days if nextday else None,
            'spy_contract':spy.contract,'spxw_contract':idx.contract,'spy_strike':spy.strike,'spxw_strike':idx.strike,
            'selection_rationale':({'spy':'nearest ATM by abs(K/raw SPY close - 1), then lower strike and contract',
             'spxw':'smallest normalized moneyness mismatch by official SPX close, then lower strike and contract',
             'entry_spy_close':stocks.get(entry,{}).get('close'),'entry_spx_close':spx.get(entry)} if lane=='lane4_official_reselection' else
             {'spy':'original vendor-close eligible alternatives','spxw':'original nearest-index-strike matched pair'}),
            'fill':fill,'credit':credit,'reference_source':refs['source'],'spx_terminal_reference':refs['spx'],'spy_terminal_reference':refs['spy'],
            'reverse_full_cross_entry_credit_control':credits['reverse_full_cross_control'],'zero_control_pnl':0.0,
            'spy_expiry_raw_close':dayrow['close'] if dayrow else None,'spy_next_session_raw_open':nextrow['open'] if nextrow else None,
            'missing_inputs':missing,'size_metadata_available':has_size,'size_eligible':size_ok,
            'spy_bid_size':meta_spy[0] if meta_spy else None,'spxw_ask_size':meta_idx[1] if meta_idx else None}
          row.update(fill_cash_terms(spy,idx,fill))
          if nextday and nextrow is None and 'next_session_price_unavailable' not in missing: missing.append('next_session_price_unavailable')
          if ledger:
            row.update(ledger)
            terminal_cash=row['direct_intrinsic_pnl']-credit
            row['reverse_full_cross_pnl_control']=credits['reverse_full_cross_control']-terminal_cash
            row['calendar_days_entry_to_option_exit']=((nextday-entry).days if nextday else None) if ledger['assigned'] else (exp-entry).days
            row['calendar_days_expiry_to_cover']=(nextday-exp).days if ledger['assigned'] and nextday else 0
            row['spy_leg_entry_cash']=row['spy_entry_cash']; row['spxw_leg_entry_cash']=row['spxw_entry_cash']
            row['spy_leg_expiry_shares']=ledger['spy_leg_expiry_shares']; row['spxw_leg_expiry_shares']=ledger['spxw_leg_terminal_shares']
            row['cost_assumptions']={'option_contracts':11,'base_option_per_contract':.65,'base_stock_per_share':.005,
              'base_borrow_apr':.03,'base_funding_apr':.05,'stress_option_per_contract':1.50,
              'stress_stock_per_share':.01,'stress_borrow_apr':.10,'stress_funding_apr':.10,
              'funding_exit':'expiry if unassigned, next-session cover if assigned','day_count':'simple ACT/365'}
            row['base_nondividend_cost_pnl']=row['stress_nondividend_cost_pnl']=None
            row['base_dividend_cost_pnl']=row['stress_dividend_cost_pnl']=None
            row['cost_components']={'option_base':11*.65,'option_stress':11*1.5,
              'stock_base':1000*.005 if ledger['assigned'] else 0,'stock_stress':1000*.01 if ledger['assigned'] else 0,
              'borrow_days':row['calendar_days_expiry_to_cover'],'funding_days':row['calendar_days_entry_to_option_exit']}
            if ledger['next_open_pnl'] is not None and (not ledger['assigned'] or nextday is not None):
              de=(exp-entry).days if not ledger['assigned'] else (nextday-entry).days
              dx=(nextday-exp).days if ledger['assigned'] else 0
              row['base_nondividend_cost_pnl']=cost_adjusted(ledger['next_open_pnl'],credit,ledger['assigned'],de,dx,dayrow['close'])
              row['stress_nondividend_cost_pnl']=cost_adjusted(ledger['next_open_pnl'],credit,ledger['assigned'],de,dx,dayrow['close'],stress=True)
              if ledger['dividend_carry_pnl'] is not None:
                row['base_dividend_cost_pnl']=cost_adjusted(ledger['dividend_carry_pnl'],credit,ledger['assigned'],de,dx,dayrow['close'])
                row['stress_dividend_cost_pnl']=cost_adjusted(ledger['dividend_carry_pnl'],credit,ledger['assigned'],de,dx,dayrow['close'],stress=True)
              row['cost_components'].update({'borrow_base':1000*dayrow['close']*.03*dx/365 if ledger['assigned'] else 0,
                'borrow_stress':1000*dayrow['close']*.1*dx/365 if ledger['assigned'] else 0,
                'funding_base':max(-credit,0)*.05*de/365,'funding_stress':max(-credit,0)*.1*de/365})
            row['conditional_close_vs_next_open_common']={'eligible':ledger['next_open_pnl'] is not None,
              'direct_intrinsic_pnl':ledger['direct_intrinsic_pnl'] if ledger['next_open_pnl'] is not None else None,
              'conditional_close_mark_pnl':ledger['conditional_close_mark_pnl'] if ledger['next_open_pnl'] is not None else None,
              'next_open_pnl':ledger['next_open_pnl']}
          out.append(row)
    return out,exclusions,len(original),len(official)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('mode',choices=('audit','run'))
    for n in ('options-zip','stocks-zip','spx-csv','weekly-json','monthly-json','receipt','protocol','output-root'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--standard-json','--quarterly-json',dest='standard_json',type=Path,required=True)
    p.add_argument('--yahoo-json',type=Path); p.add_argument('--yahoo-receipt',type=Path)
    a=p.parse_args(); paths=[getattr(a,n.replace('-','_')).resolve() for n in ('options-zip','stocks-zip','spx-csv','weekly-json','monthly-json','standard-json','receipt')]; protocol=a.protocol.resolve()
    if bool(a.yahoo_json)!=bool(a.yahoo_receipt): p.error('--yahoo-json and --yahoo-receipt must be supplied together')
    yahoo_paths=[x.resolve() for x in (a.yahoo_json,a.yahoo_receipt) if x]
    settle_counts=Counter({'expected_coverage_ok':False})
    receipt_ok=False; receipt_report={'status':'NOT_CHECKED','required_entries':5}
    try:
      for f in [*paths,protocol,*yahoo_paths]:
        with f.open('rb'): pass
      if not zipfile.is_zipfile(paths[0]) or not zipfile.is_zipfile(paths[1]): raise ValueError('ZIP inputs are unreadable')
      protocol_bytes=protocol.read_bytes()
      if not protocol_bytes.strip(): raise ValueError('protocol is empty')
      if not ignored_output(a.output_root):raise ValueError('--output-root must be covered by an applicable .gitignore rule')
    except (OSError,ValueError) as e:p.error(f'input validation failed: {e}')
    paths=[*paths,*yahoo_paths,protocol]; started=datetime.now(timezone.utc); before=snap(paths,protocol)
    # Read and validate source schemas before creating a destination.
    try:
      receipt=json.loads(paths[6].read_text())
      receipt_report=validate_receipt(receipt,paths[1:6]); receipt_ok=receipt_report['status']=='PASS'
      if not receipt_ok:raise ValueError('official source receipt validation failed')
      quotes,vendor,quote_exclusions=read_zip(paths[0]); stocks,stock_counts,sessions=read_stocks(paths[1]); spx,spx_counts=read_spx(paths[2]); settle,settle_counts,coverage=read_settlements(paths[3:6]); sizes,size_counts=read_size_map(paths[0])
      yahoo_report={'status':'NOT_PROVIDED'}
      if yahoo_paths:
        yahoo_receipt=json.loads(yahoo_paths[1].read_text()); yahoo_report=validate_receipt({'files':[yahoo_receipt]},[yahoo_paths[0]])
        if yahoo_report['status']!='PASS': raise ValueError('Yahoo source receipt validation failed')
        yahoo,yahoo_sessions=read_yahoo(yahoo_paths[0]); yahoo_report.update(add_yahoo_boundary(stocks,sessions,yahoo,yahoo_sessions))
      audit={'status':'source_audit_only','quote_candidates':len(quotes),'quote_exclusions':dict(quote_exclusions),
       'stock_counts':dict(stock_counts),'spx_counts':dict(spx_counts),'settlement_counts':dict(settle_counts),
       'settlement_coverage_by_file':coverage,'settlement_coverage_status':'PASS' if settle_counts['expected_coverage_ok'] else 'FAIL','yahoo_boundary_reconciliation':yahoo_report,
       'size_metadata_counts':dict(size_counts),'receipt_present':bool(receipt),'receipt_reconciliation':receipt_report,
       'source_value_reconciliation':source_value_reconciliation(vendor,stocks,spx,settle),
       'stock_spx_join_dates':len(set(stocks)&set(spx)),'settlement_stock_join_dates':len(set(settle)&set(stocks))}
      entry_days={q.quote_date for q in quotes}; expiries={q.expiration for q in quotes}
      audit['source_reconciliation']={'entry_dates':len(entry_days),'entry_stock_close_dates':len(entry_days&set(stocks)),
        'entry_dates_missing_stock_close':len(entry_days-set(stocks)),'entry_dates_missing_spx_close':len(entry_days-set(spx)),
        'entry_spx_close_dates':len(entry_days&set(spx)),'expiry_stock_close_dates':len(expiries&set(stocks)),
        'expiry_dates_missing_stock_close':len(expiries-set(stocks)),'expiry_dates_missing_spx_close':len(expiries-set(spx)),
        'expiry_dates_missing_official_settlement':len(expiries-set(settle)),
        'expiry_official_spx_close_dates':len(expiries&set(spx)),'expiry_official_settlement_dates':len(expiries&set(settle)),
        'expiry_vendor_spy_reference_dates':len(expiries&{d for d,u in vendor if u=='SPY'}),
        'expiry_vendor_spxw_reference_dates':len(expiries&{d for d,u in vendor if u=='SPXW'})}
      status='source_audit_only'; rows=[]; aggregates=None; run_exclusions={}
      if a.mode=='run':
        rows,run_exclusions,n_original,n_primary=build_rows(quotes,vendor,stocks,spx,settle,sizes,size_counts,sessions)
        required_lanes={r['lane'] for r in rows}; missing_lanes={'lane1_original_vendor','lane2_original_official','lane3_original_spx_control','lane4_official_reselection'}-required_lanes
        coverage_failed=not settle_counts['expected_coverage_ok']
        status='NO_USABLE_DATA' if not rows else ('REQUIRED_LANES_FAILED' if missing_lanes or coverage_failed else 'OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED')
        summaries=[]
        equal_expiry=[]; equal_cohort=[]; control_summaries=[]
        for lane in sorted(required_lanes):
          lane_rows=[r for r in rows if r['lane']==lane]
          for fill in ('midpoint','halfway','full_cross'):
            selected=[r for r in lane_rows if r['fill']==fill]
            for metric,cost,depth in [('direct_intrinsic_pnl','gross','all'),('conditional_close_mark_pnl','gross','all'),('next_open_pnl','gross','all'),('dividend_carry_pnl','dividend_adjusted','all'),('base_nondividend_cost_pnl','base_nondividend','all'),('stress_nondividend_cost_pnl','stress_nondividend','all'),('base_dividend_cost_pnl','base_dividend','all'),('stress_dividend_cost_pnl','stress_dividend','all')]:
              depth_cases=[(selected,'all_selected')]
              if lane=='lane4_official_reselection':depth_cases.append(([r for r in selected if r['size_eligible']],'size_eligible'))
              for subset,label in depth_cases:
                base_labels={'lane':lane,'fill':fill,'cost_case':cost,'depth':label,'population':selected[0]['population'] if selected else 'none'}
                base_labels.update(depth_period_counts(selected,subset,'all'))
                summaries.append(percentile_summary(subset,metric,{**base_labels,'period':'all'}))
                for period,fn in [('Q3',lambda d:d.month in (7,8,9)),('Q4',lambda d:d.month in (10,11,12))]:
                  part=[r for r in subset if fn(date.fromisoformat(r['expiry_date']))]
                  summaries.append(percentile_summary(part,metric,{**base_labels,**depth_period_counts(selected,subset,period),'period':period}))
                months=sorted({r['expiry_date'][:7] for r in subset})
                for month in sorted({r['expiry_date'][:7] for r in selected}):
                  part=[r for r in subset if r['expiry_date'].startswith(month)]
                  summaries.append(percentile_summary(part,metric,{**base_labels,**depth_period_counts(selected,subset,month),'period':month}))
                periods={'all':lambda d:True,'Q3':lambda d:d.month in (7,8,9),'Q4':lambda d:d.month in (10,11,12)}
                periods.update({m:lambda d,m=m:d.strftime('%Y-%m')==m for m in sorted({r['expiry_date'][:7] for r in subset})})
                for period,fn in periods.items():
                  part=[r for r in subset if fn(date.fromisoformat(r['expiry_date']))]
                  cohorts=defaultdict(list)
                  for r in part:
                    if isinstance(r.get(metric),(int,float)) and math.isfinite(r[metric]):cohorts[r['expiry_date']].append(r[metric])
                  cohort_rows=[{metric:sum(v)/len(v),'expiry_date':expiry} for expiry,v in cohorts.items()]
                  stat=percentile_summary(cohort_rows,metric,{**base_labels,**depth_period_counts(selected,subset,period),'lane':lane,'fill':fill,'cost_case':cost,'depth':label,'period':period,
                    'population':'equal_expiry_primary' if lane=='lane4_official_reselection' else 'original_equal_cohort'})
                  (equal_expiry if lane=='lane4_official_reselection' else equal_cohort).append(stat)
        for lane in sorted(required_lanes):
          controls=[r for r in rows if r['lane']==lane and r['fill']=='full_cross']
          population=controls[0]['population'] if controls else 'none'
          for metric in ('reverse_full_cross_pnl_control','zero_control_pnl'):
            cohort_controls=[]
            by_expiry=defaultdict(list)
            for r in controls:
              if isinstance(r.get(metric),(int,float)):by_expiry[r['expiry_date']].append(r[metric])
            cohort_controls.extend([{metric:sum(vals)/len(vals),'expiry_date':exp,'size_eligible':all(x['size_eligible'] for x in controls if x['expiry_date']==exp)} for exp,vals in by_expiry.items()])
            control_summaries.append(percentile_summary(cohort_controls,metric,{'lane':lane,'fill':'reverse_full_cross_control' if metric.startswith('reverse') else 'zero_control','cost_case':'gross' if metric.startswith('reverse') else 'zero','depth':'all','period':'all','population':'equal_expiry_primary' if lane=='lane4_official_reselection' else 'original_equal_cohort'}))
        common_cover=[]
        for lane in sorted(required_lanes):
          for fill in ('midpoint','halfway','full_cross'):
            common=[r for r in rows if r['lane']==lane and r['fill']==fill and r.get('conditional_close_vs_next_open_common',{}).get('eligible')]
            for metric in ('direct_intrinsic_pnl','conditional_close_mark_pnl','next_open_pnl'):
              cohorts=defaultdict(list)
              for r in common: cohorts[r['expiry_date']].append(r['conditional_close_vs_next_open_common'][metric])
              cohort_rows=[{metric:sum(v)/len(v),'expiry_date':d} for d,v in cohorts.items()]
              common_cover.append(percentile_summary(cohort_rows,metric,{'lane':lane,'fill':fill,'cost_case':'gross','depth':'common_complete_cover','period':'all',
                'population':'primary_equal_expiry' if lane=='lane4_official_reselection' else 'alternatives_equal_expiry_cohort','selected_pair_dates':sorted(cohorts)}))
        aggregates={'status':status,'realized_broker_execution_assignment_account_returns':'NOT RUN','rows':len(rows),'original_pair_count':n_original,'official_primary_count':n_primary,
          'missing_required_lanes':sorted(missing_lanes),'source_coverage_failed':coverage_failed,'exclusions':{**run_exclusions,**dict(size_counts)},'summaries':summaries,
          'equal_expiry_primary_summaries':equal_expiry,'original_equal_cohort_summaries':equal_cohort,
          'control_summaries':control_summaries,'common_complete_cover_comparisons':common_cover,
          'reverse_full_cross_and_zero_are_controls_not_fills':True,'unassigned_funding_exit':'expiry date; funding ACT/365 entry-to-expiry',
          'assigned_borrow':'raw expiry close exposure ACT/365 expiry-to-next-session open','no_reselection_after_missing_outcome':True}
    except Exception as e:
      status='RECEIPT_VALIDATION_FAILED' if not receipt_ok else 'SOURCE_VALIDATION_FAILED'
      audit={'status':status,'receipt_reconciliation':receipt_report,'error':f'{type(e).__name__}: {e}'}
      rows=[]; aggregates=None; run_exclusions={}; error=str(e)
    else:error=None
    after=snap(paths,protocol); unchanged=before==after
    outroot=a.output_root.resolve(); outroot.mkdir(parents=True,exist_ok=True); dest=outroot/started.strftime('%Y%m%dT%H%M%S%fZ'); dest.mkdir()
    # Integrity gate occurs before any outcome artifacts are persisted.
    if not unchanged: status='INTEGRITY_FAILURE'; aggregates=None; rows=[]
    (dest/'source_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    manifest={'mode':a.mode,'status':status,'realized_broker_execution_assignment_account_returns':'NOT RUN','command':{'argv':sys.argv,'cwd':os.getcwd(),'pythonpath':os.environ.get('PYTHONPATH',''),'interpreter':sys.executable},
      'started_utc':started.isoformat(),'ended_utc':datetime.now(timezone.utc).isoformat(),'host':socket.gethostname(),'python':sys.version,
      'runtime':'local deterministic computation','model_endpoint':'N/A','git_sha':before['git_sha'],'git_baseline_state':'dirty' if before['git_status'] else 'clean',
      'snapshot_before':before,'snapshot_after':after,'integrity_status':'UNCHANGED' if unchanged else 'CHANGED_DURING_PROCESSING','error':error}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if unchanged and a.mode=='run' and aggregates is not None and status=='OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED':
      (dest/'pair_rows.json').write_text(json.dumps(rows,indent=2)+'\n'); (dest/'aggregates.json').write_text(json.dumps(aggregates,indent=2)+'\n')
    print(json.dumps({'output':str(dest),'status':status,'integrity_status':manifest['integrity_status']}))
    if not unchanged or error or not receipt_ok or not settle_counts['expected_coverage_ok'] or a.mode=='run' and (aggregates is None or status!='OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED'):return 2
    return 0

if __name__=='__main__': raise SystemExit(main())
