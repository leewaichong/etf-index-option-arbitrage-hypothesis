import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import pytest

from spyspx.expiry_attribution import analyze, bootstrap, load_upstream, make_rows, summarize
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import expiry_attribution as cli

def row(day, assigned=False, close=100, op=99, nextpnl=30, closepnl=10, direct=11, base=25, stress=20, exdiv=False):
    return {'lane':'lane4_official_reselection','fill':'full_cross','expiry_date':day,'entry_date':'2022-07-01',
      'missing_inputs':[],'assigned':assigned,'spy_expiry_raw_close':close,'spy_next_session_raw_open':op,
      'direct_intrinsic_pnl':direct,'conditional_close_mark_pnl':closepnl,'next_open_pnl':nextpnl,
      'base_dividend_cost_pnl':base,'stress_dividend_cost_pnl':stress,
      'entry_to_expiry_dividend_exposure':exdiv,'spy_contract':'s','spxw_contract':'i'}

def test_controls_and_hand_computed_tails():
    rows=make_rows([row('2022-09-16',True,100,99,1010,10,11,1005,1000),row('2022-10-07',False,100,98,8,8,9,7,6)])
    assert rows[0]['overnight_attribution']==1000
    assert rows[0]['neutralized_expiry_spread']==10
    assert rows[0]['identity_residual_expiry_spread']==0
    stats=summarize([{'expiry_date':'2022-09-16','x':3},{'expiry_date':'2022-09-19','x':-1},{'expiry_date':'2022-09-20','x':2}],'x')
    assert stats['cumulative_cash_pnl']==4 and stats['max_cash_drawdown_from_zero']==1
    assert stats['best5']==[3,2,-1] and stats['worst5']==[-1,2,3]
    assert stats['mean_ex_best1']==.5

def test_bootstrap_deterministic_cluster_sampling_and_constant_interval():
    rows=[{'expiry_date':'2022-09-16','x':2},{'expiry_date':'2022-09-19','x':2},
          {'expiry_date':'2022-09-26','x':2},{'expiry_date':'2022-10-03','x':2}]
    a=bootstrap(rows,'x',100,7); b=bootstrap(rows,'x',100,7)
    assert a==b and a['n_weeks']==4 and a['low']==2 and a['high']==2

def test_missing_and_invalid_primary_references_fail_closed():
    with pytest.raises(ValueError): make_rows([row('2022-09-16'),row('2022-09-16')])
    bad=row('2022-09-16'); bad['missing_inputs']=['spy_terminal']
    with pytest.raises(ValueError): make_rows([bad])

def test_null_costs_stay_null_with_finite_overnight_exposure():
    source=row('2022-09-16',True,100,99,1010,10,11,None,None)
    result=make_rows([source])[0]
    assert result['overnight_attribution']==1000
    assert result['neutralized_base_dividend_cost'] is None
    assert result['neutralized_stress_dividend_cost'] is None
    assert result['identity_residual_base_cost'] is None
    assert result['identity_residual_stress_cost'] is None

def cli_fixture(tmp_path,request):
    upstream=tmp_path/'upstream'; upstream.mkdir()
    pair_rows=[row('2022-09-15',True,100,99,1010,10,11,None,None),
      row('2022-09-16',False,101,100,10,10,11,9,8,True),
      row('2022-10-07',True,102,100,2010,10,11,2005,2000)]
    docs={'manifest.json':{'status':'OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED','git_baseline_state':'clean',
       'integrity_status':'UNCHANGED','snapshot_before':{'files':1},'snapshot_after':{'files':1}},
      'pair_rows.json':pair_rows,'aggregates.json':{'status':'OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED'},
      'source_audit.json':{'status':'source_audit_only'}}
    for name,doc in docs.items(): (upstream/name).write_text(json.dumps(doc))
    protocol=tmp_path/'protocol.md'; protocol.write_text('# Synthetic protocol\n\nNOT RUN\n')
    run_root=cli.ROOT/'runs'
    run_root.mkdir(parents=True,exist_ok=True)
    run_sandbox=tempfile.TemporaryDirectory(dir=run_root,prefix='.attribution-synthetic-')
    request.addfinalizer(run_sandbox.cleanup)
    output=Path(run_sandbox.name)/'output'
    real_run=subprocess.run
    def run(args,*rest,**kwargs):
        if args[:2]==['git','check-ignore']:
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        return real_run(args,*rest,**kwargs)
    return upstream,protocol,output,run

def patch_cli_env(monkeypatch, fixture):
    upstream,protocol,output,run=fixture
    monkeypatch.setattr(cli,'git',lambda *args: 'fixture-sha' if args==('rev-parse','HEAD') else '')
    monkeypatch.setattr(cli.subprocess,'run',run)
    return ['--upstream-run',str(upstream),'--protocol',str(protocol),'--output-root',str(output),'--bootstrap-draws','8']

def test_cli_synthetic_end_to_end_writes_evaluated_outputs(tmp_path,request,monkeypatch,capsys):
    args=patch_cli_env(monkeypatch,cli_fixture(tmp_path,request))
    assert cli.main(args)==0
    output=Path(json.loads(capsys.readouterr().out)['output'])
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['status']=='ATTRIBUTION_EVALUATED'
    assert manifest['protocol_run_status']=='EVALUATED' and manifest['broker_account_claims']=='NOT RUN'
    assert manifest['git_status_before']==manifest['git_status_after']==''
    assert manifest['code_test_sha256_before']==manifest['code_test_sha256_after']
    assert manifest['protocol_sha256_before']==manifest['protocol_sha256_after']
    assert manifest['upstream_input_sha256_before']==manifest['upstream_input_sha256_after']
    computed=json.loads((output/'computed_rows.json').read_text())
    assert len(computed)==3 and computed[0]['neutralized_base_dividend_cost'] is None
    assert json.loads((output/'summaries.json').read_text())['all']['available_dates']==3

@pytest.mark.parametrize('mutation',['protocol','upstream','code_hash'])
def test_cli_integrity_mutations_fail_before_outcome_files(tmp_path,request,monkeypatch,mutation):
    fixture=cli_fixture(tmp_path,request); upstream,protocol,output,_=fixture
    args=patch_cli_env(monkeypatch,fixture)
    original_make=cli.make_rows; original_analyze=cli.analyze; original_sha=cli.sha256
    if mutation=='protocol':
        def change_protocol(rows,*a):
            protocol.write_text('changed after baseline\nNOT RUN\n')
            return original_analyze(rows,*a)
        monkeypatch.setattr(cli,'analyze',change_protocol)
    elif mutation=='upstream':
        def change_input(pair_rows):
            result=original_make(pair_rows)
            (upstream/'source_audit.json').write_text('{"status":"changed"}')
            return result
        monkeypatch.setattr(cli,'make_rows',change_input)
    else:
        code_path=cli.ROOT/'scripts/expiry_attribution.py'; count={'n':0}
        def changed_hash(path):
            value=original_sha(path)
            if Path(path)==code_path:
                count['n']+=1
                if count['n']>1: return 'changed-code-hash'
            return value
        monkeypatch.setattr(cli,'sha256',changed_hash)
    with pytest.raises(RuntimeError): cli.main(args)
    assert not output.exists() or not list(output.glob('*/manifest.json'))

def test_upstream_integrity_validation(tmp_path):
    values={'manifest.json':{'status':'OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED','git_baseline_state':'clean',
      'integrity_status':'UNCHANGED','snapshot_before':{'a':1},'snapshot_after':{'a':1}},
      'aggregates.json':{'status':'OFFICIAL_SETTLEMENT_CONDITIONAL_ASSIGNMENT_EVALUATED'},
      'source_audit.json':{'status':'source_audit_only'},'pair_rows.json':[row('2022-09-16',nextpnl=10,closepnl=10)]}
    for name,doc in values.items(): (tmp_path/name).write_text(json.dumps(doc))
    loaded,_=load_upstream(tmp_path); assert len(make_rows(loaded['pair_rows.json']))==1
    m=json.loads((tmp_path/'manifest.json').read_text()); m['integrity_status']='CHANGED_DURING_PROCESSING'; (tmp_path/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError): load_upstream(tmp_path)

def test_period_local_depth_counts_use_unequal_period_fixture():
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from expiry_extension import depth_period_counts
    selected=[{'expiry_date':'2022-07-15'},{'expiry_date':'2022-08-19'},
              {'expiry_date':'2022-10-21'},{'expiry_date':'2022-11-18'}]
    eligible=[selected[0],selected[2],selected[3]]
    assert depth_period_counts(selected,eligible,'Q3')=={'pre_depth_count':2,'after_depth_count':1,'depth_filter_loss':1}
    assert depth_period_counts(selected,eligible,'Q4')=={'pre_depth_count':2,'after_depth_count':2,'depth_filter_loss':0}
    assert depth_period_counts(selected,eligible,'all')=={'pre_depth_count':4,'after_depth_count':3,'depth_filter_loss':1}
