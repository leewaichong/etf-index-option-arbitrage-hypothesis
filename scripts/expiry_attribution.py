#!/usr/bin/env python3
"""Run the frozen descriptive expiry carry attribution protocol."""
from __future__ import annotations
import argparse, hashlib, json, os, socket, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spyspx.expiry_attribution import UPSTREAM_FILES, analyze, load_upstream, make_rows, sha256

def git(*args):
    return subprocess.run(['git',*args],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--upstream-run',required=True,type=Path); p.add_argument('--protocol',required=True,type=Path)
    p.add_argument('--output-root',required=True,type=Path); p.add_argument('--bootstrap-draws',type=int,default=10000)
    p.add_argument('--bootstrap-seed',type=int,default=20261028)
    a=p.parse_args(argv); start=datetime.now(timezone.utc)
    if a.bootstrap_draws<1: p.error('--bootstrap-draws must be positive')
    if not a.upstream_run.is_dir(): p.error('upstream run directory does not exist')
    output_abs=a.output_root.resolve()
    ignored=subprocess.run(['git','check-ignore','-q',str(output_abs)],cwd=ROOT).returncode==0
    if not ignored: p.error('--output-root must be ignored by git')
    before_sha=git('rev-parse','HEAD'); before_status=git('status','--porcelain')
    code_files=[ROOT/'scripts/expiry_attribution.py',ROOT/'src/spyspx/expiry_attribution.py',ROOT/'tests/test_expiry_attribution.py']
    protocol_hash_before=sha256(a.protocol)
    code_hashes_before={str(x.relative_to(ROOT)):sha256(x) for x in code_files}
    input_paths={name:a.upstream_run/name for name in UPSTREAM_FILES}
    input_hashes_before={name:sha256(path) for name,path in input_paths.items()}
    if not a.protocol.is_file() or 'NOT RUN' not in a.protocol.read_text(): p.error('protocol must exist and state NOT RUN')
    docs,load_hashes=load_upstream(a.upstream_run)
    if load_hashes!=input_hashes_before: raise RuntimeError('upstream input changed while loading')
    rows=make_rows(docs['pair_rows.json'])
    computed=analyze(rows,a.bootstrap_draws,a.bootstrap_seed)
    after_status=git('status','--porcelain'); after_sha=git('rev-parse','HEAD'); end=datetime.now(timezone.utc)
    if (before_sha,before_status)!=(after_sha,after_status): raise RuntimeError('working tree changed during attribution; no output written')
    if before_status: raise RuntimeError('attribution requires a clean working tree')
    code_hashes_after={str(x.relative_to(ROOT)):sha256(x) for x in code_files}
    input_hashes_after={name:sha256(path) for name,path in input_paths.items()}
    protocol_hash_after=sha256(a.protocol)
    if code_hashes_before!=code_hashes_after: raise RuntimeError('code or test inputs changed during attribution; no output written')
    if input_hashes_before!=input_hashes_after: raise RuntimeError('upstream input changed during attribution; no output written')
    if protocol_hash_before!=protocol_hash_after: raise RuntimeError('protocol changed during attribution; no output written')
    manifest={'status':'ATTRIBUTION_EVALUATED','protocol_run_status':'EVALUATED','broker_account_claims':'NOT RUN',
      'command':{'argv':sys.argv,'cwd':os.getcwd(),'pythonpath':os.environ.get('PYTHONPATH',''),'interpreter':sys.executable},
      'started_utc':start.isoformat(),'ended_utc':end.isoformat(),'host':socket.gethostname(),'python':sys.version,
      'runtime':'local deterministic computation','model_endpoint':'N/A','git_sha':before_sha,'git_baseline_state':'clean',
      'git_status_before':before_status,
      'git_status_after':after_status,'code_test_sha256_before':code_hashes_before,'code_test_sha256_after':code_hashes_after,
      'protocol_sha256_before':protocol_hash_before,'protocol_sha256_after':protocol_hash_after,
      'upstream_run':str(a.upstream_run.resolve()),'upstream_input_sha256_before':input_hashes_before,'upstream_input_sha256_after':input_hashes_after,
      'bootstrap':{'draws':a.bootstrap_draws,'seed':a.bootstrap_seed,'cluster':'ISO year/week'}}
    outroot=a.output_root.resolve(); outroot.mkdir(parents=True,exist_ok=True)
    dest=outroot/end.strftime('%Y%m%dT%H%M%S%fZ'); dest.mkdir()
    (dest/'computed_rows.json').write_text(json.dumps(rows,indent=2)+'\n')
    (dest/'summaries.json').write_text(json.dumps(computed,indent=2)+'\n')
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'output':str(dest),'status':manifest['status']}))
    return 0

if __name__=='__main__': raise SystemExit(main())
