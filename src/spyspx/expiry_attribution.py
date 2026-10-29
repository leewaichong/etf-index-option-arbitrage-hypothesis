"""Post hoc descriptive attribution for a completed expiry extension run."""
from __future__ import annotations
import hashlib, json, math, random, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

UPSTREAM_FILES = ('manifest.json', 'pair_rows.json', 'aggregates.json', 'source_audit.json')
LANE = 'lane4_official_reselection'
FILL = 'full_cross'
SHARES = 1000
TOLERANCE = 1e-7


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def load_upstream(directory):
    root = Path(directory)
    hashes = {name: sha256(root / name) for name in UPSTREAM_FILES}
    docs = {name: json.loads((root / name).read_text()) for name in UPSTREAM_FILES}
    m = docs['manifest.json']
    if m.get('status') != 'OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED': raise ValueError('upstream run is not evaluated')
    if m.get('git_baseline_state') != 'clean': raise ValueError('upstream baseline was not clean')
    if m.get('integrity_status') != 'UNCHANGED' or m.get('snapshot_before') != m.get('snapshot_after'): raise ValueError('upstream integrity check failed')
    if docs['aggregates.json'].get('status') != m['status']: raise ValueError('upstream aggregates do not match manifest')
    if docs['source_audit.json'].get('status') != 'source_audit_only': raise ValueError('upstream source audit missing')
    return docs, hashes


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def make_rows(pair_rows):
    rows = [r for r in pair_rows if r.get('lane') == LANE and r.get('fill') == FILL]
    if not rows: raise ValueError('required lane/fill rows missing')
    by_expiry = {}
    result = []
    for r in rows:
        expiry = r.get('expiry_date')
        if not expiry or expiry in by_expiry: raise ValueError('duplicate or missing primary expiry')
        if any(reason not in ('next_session_price_unavailable',) for reason in r.get('missing_inputs',[])): raise ValueError('primary row has missing references')
        required = ('direct_intrinsic_pnl','conditional_close_mark_pnl','next_open_pnl','spy_expiry_raw_close','assigned',
                    'base_dividend_cost_pnl','stress_dividend_cost_pnl')
        if any(k not in r for k in required): raise ValueError('primary row is missing required ledger fields')
        if not finite(r['spy_expiry_raw_close']): raise ValueError('primary expiry raw price reference missing')
        by_expiry[expiry] = True
        assigned = bool(r['assigned'])
        next_open = r.get('spy_next_session_raw_open')
        overnight = (SHARES * (r['spy_expiry_raw_close'] - next_open) if assigned else 0.0) if finite(next_open) else (None if assigned else 0.0)
        unconditional = SHARES * (r['spy_expiry_raw_close'] - next_open) if finite(next_open) else None
        net = r['next_open_pnl'] - overnight if finite(r.get('next_open_pnl')) and finite(overnight) else None
        if net is not None and abs(net-r['conditional_close_mark_pnl']) > TOLERANCE: raise ValueError('neutralized spread identity failed')
        vals = {'direct_intrinsic':r['direct_intrinsic_pnl'], 'conditional_close':r['conditional_close_mark_pnl'],
                'next_open_gross':r['next_open_pnl'], 'conditional_overnight_short':overnight,
                'unconditional_overnight_short':unconditional, 'neutralized_expiry_spread':net,
                'base_dividend_cost':r['base_dividend_cost_pnl'], 'stress_dividend_cost':r['stress_dividend_cost_pnl'],
                'neutralized_base_dividend_cost':r['base_dividend_cost_pnl']-overnight if finite(r.get('base_dividend_cost_pnl')) and finite(overnight) else None,
                'neutralized_stress_dividend_cost':r['stress_dividend_cost_pnl']-overnight if finite(r.get('stress_dividend_cost_pnl')) and finite(overnight) else None}
        result.append({'expiry_date':expiry,'entry_date':r.get('entry_date'),'assigned':assigned,
          'entry_to_expiry_dividend_exposure':bool(r.get('entry_to_expiry_dividend_exposure')),
          'spy_expiry_raw_close':r['spy_expiry_raw_close'],'spy_next_session_raw_open':r.get('spy_next_session_raw_open'),
          'spy_terminal_reference':r.get('spy_terminal_reference'),'spx_terminal_reference':r.get('spx_terminal_reference'),
          'reference_source':r.get('reference_source'),'credit':r.get('credit'),
          'threshold_residual_cash':r.get('threshold_residual_cash'),'dividend_carry_amount':r.get('dividend_carry_amount'),
          'dividend_carry_dates':r.get('dividend_carry_dates'),
          'spy_expiry_cash':r.get('spy_leg_expiry_cash'),'spy_next_open_cash':r.get('spy_leg_next_open_cash'),
          'spxw_terminal_cash':r.get('spxw_leg_terminal_cash'),'spy_expiry_shares':r.get('spy_leg_expiry_shares'),
          'spxw_terminal_shares':r.get('spxw_leg_terminal_shares'),'selection_rationale':r.get('selection_rationale'),
          'spy_contract':r.get('spy_contract'),'spxw_contract':r.get('spxw_contract'),
          'direct_intrinsic_pnl':r['direct_intrinsic_pnl'],'conditional_close_mark_pnl':r['conditional_close_mark_pnl'],
          'next_open_pnl':r['next_open_pnl'],'base_dividend_cost_pnl':r['base_dividend_cost_pnl'],'stress_dividend_cost_pnl':r['stress_dividend_cost_pnl'],
          'overnight_attribution':overnight,'unconditional_overnight_benchmark':unconditional,
          'neutralized_expiry_spread':net,'neutralized_base_dividend_cost':vals['neutralized_base_dividend_cost'],
          'neutralized_stress_dividend_cost':vals['neutralized_stress_dividend_cost'],
          'identity_residual_expiry_spread':net-r['conditional_close_mark_pnl'] if net is not None else None,
          'identity_residual_base_cost':vals['neutralized_base_dividend_cost']-r['direct_intrinsic_pnl'] if finite(vals['neutralized_base_dividend_cost']) else None,
          'identity_residual_stress_cost':vals['neutralized_stress_dividend_cost']-r['direct_intrinsic_pnl'] if finite(vals['neutralized_stress_dividend_cost']) else None})
    return sorted(result,key=lambda r:r['expiry_date'])


def quantile(sorted_values, p):
    if len(sorted_values)==1: return sorted_values[0]
    x=(len(sorted_values)-1)*p; lo=math.floor(x); hi=math.ceil(x)
    return sorted_values[lo]+(sorted_values[hi]-sorted_values[lo])*(x-lo)


def bootstrap(rows, metric, draws=10000, seed=20261028):
    clusters=defaultdict(list)
    for r in rows:
        d=date.fromisoformat(r['expiry_date']); clusters[(d.isocalendar().year,d.isocalendar().week)].append(r)
    keys=sorted(clusters); rng=random.Random(seed); means=[]
    if not keys: return {'n_weeks':0,'draws':0,'seed':seed,'missing_policy':'drop missing metric rows; fail if draw has no observations','low':None,'high':None}
    for _ in range(draws):
        sampled=[rng.choice(keys) for _ in keys]
        vals=[r[metric] for key in sampled for r in clusters[key] if finite(r.get(metric))]
        if not vals: raise ValueError('bootstrap draw has no observed values')
        means.append(sum(vals)/len(vals))
    means.sort()
    return {'n_weeks':len(keys),'draws':draws,'seed':seed,'missing_policy':'drop missing metric rows; denominator varies by draw',
            'low':quantile(means,.025),'high':quantile(means,.975)}


def summarize(rows, metric):
    vals=[r[metric] for r in rows if finite(r.get(metric))]
    chronological=sorted((r for r in rows if finite(r.get(metric))),key=lambda r:r['expiry_date'])
    cumulative=0.; peak=0.; max_dd=0.
    for r in chronological:
        cumulative+=r[metric]; peak=max(peak,cumulative); max_dd=max(max_dd,peak-cumulative)
    ordered=sorted(vals); n=len(vals)
    return {'n':n,'missing_n':len(rows)-n,'mean':statistics.mean(vals) if n else None,
      'median':statistics.median(vals) if n else None,'sample_std':statistics.stdev(vals) if n>1 else (0.0 if n else None),
      'min':min(vals) if n else None,'max':max(vals) if n else None,'positive_count':sum(v>0 for v in vals),
      'cumulative_cash_pnl':sum(vals) if vals else None,'max_cash_drawdown_from_zero':max_dd if vals else None,
      'best5':sorted(vals,reverse=True)[:5],'worst5':ordered[:5],
      'mean_ex_best1':statistics.mean(ordered[:-1]) if n>1 else None,'mean_ex_best5':statistics.mean(ordered[:-5]) if n>5 else None}


def analyze(rows, draws=10000, seed=20261028):
    metrics=('direct_intrinsic_pnl','conditional_close_mark_pnl','next_open_pnl','overnight_attribution','unconditional_overnight_benchmark',
      'neutralized_expiry_spread','base_dividend_cost_pnl','stress_dividend_cost_pnl','neutralized_base_dividend_cost','neutralized_stress_dividend_cost')
    output={}; periods={'all':rows,'Q3':[r for r in rows if date.fromisoformat(r['expiry_date']).month in (7,8,9)],
      'Q4':[r for r in rows if date.fromisoformat(r['expiry_date']).month in (10,11,12)]}
    periods.update({m:[r for r in rows if r['expiry_date'].startswith(m)] for m in sorted({r['expiry_date'][:7] for r in rows})})
    for period, subset in periods.items():
        output[period]={'assignment_count':sum(r['assigned'] for r in subset),'available_dates':len(subset),
          'entry_to_expiry_dividend_exposure_count':sum(r['entry_to_expiry_dividend_exposure'] for r in subset),'metrics':{}}
        for metric in metrics:
            stats=summarize(subset,metric); stats['bootstrap_95pct']=bootstrap(subset,metric,draws,seed)
            output[period]['metrics'][metric]=stats
        no_exdiv=[r for r in subset if not r['entry_to_expiry_dividend_exposure']]
        output[period]['fixed_row_no_entry_exdiv_sensitivity']={metric:summarize(no_exdiv,metric) for metric in metrics}
    return output
