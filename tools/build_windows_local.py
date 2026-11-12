"""Local Windows native work with one reusable target, separate from receipts.

CI keeps its existing explicit CARGO_TARGET_DIR. Batch output directories store
small logs/receipts and final deliverables, never another complete Cargo tree.
"""
from pathlib import Path
import argparse,os,subprocess,sys
from check_type_build_target import inspect

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('task',choices=['check','test','build'])
    p.add_argument('--release',action='store_true')
    p.add_argument('--filter',help='Affected test filter, only with test')
    p.add_argument('--output',type=Path,help='Optional existing batch directory for one log')
    a=p.parse_args()
    if os.name!='nt':p.error('Windows native build entry')
    if a.filter and a.task!='test':p.error('--filter applies to test')
    cache=Path(os.environ.get('COMPANION_BUILD_CACHE','E:/CodexData/Companion/.build-cache'))
    target=cache/'shared-windows-target'
    state=inspect(target,ROOT,source_dir=ROOT)
    if state['result']!='TARGET_IDLE_AT_OBSERVATION':
        print(state['result']+': the existing target is in use; do not allocate a duplicate target')
        return 2
    env=os.environ.copy();env['CARGO_TARGET_DIR']=str(target)
    env['CARGO_INCREMENTAL']='0';env['CARGO_PROFILE_DEV_DEBUG']='0';env['CARGO_PROFILE_TEST_DEBUG']='0'
    env.setdefault('CARGO_BUILD_JOBS','2')
    cmd=['cargo',a.task,'--locked','--manifest-path',str(ROOT/'apps/windows/src-tauri/Cargo.toml')]
    if a.release:cmd.append('--release')
    if a.filter:cmd.extend(['--lib',a.filter])
    print('Using reusable native target: '+str(target),flush=True)
    if a.output:
        a.output.mkdir(parents=True,exist_ok=True)
        with (a.output/(a.task+('-release' if a.release else '')+'.log')).open('wb') as log:
            return subprocess.call(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    return subprocess.call(cmd,cwd=ROOT,env=env)
if __name__=='__main__':raise SystemExit(main())
