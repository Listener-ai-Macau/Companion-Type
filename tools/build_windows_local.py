"""Local Windows native work with one reusable target, separate from receipts.

CI keeps its existing explicit CARGO_TARGET_DIR. Batch output directories store
small logs/receipts and final deliverables, never another complete Cargo tree.
"""
from pathlib import Path
import argparse,os,subprocess,sys,hashlib,json,shutil
from check_type_build_target import inspect
sys.path.insert(0,str(Path(os.environ.get('DENZIC_WORKFLOW_ROOT',
    'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow'))/'scripts'))
from development_storage import exclusive_build,preflight,StorageLimit

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('task',choices=['check','test','build'])
    p.add_argument('--release',action='store_true')
    p.add_argument('--filter',help='Affected test filter, only with test')
    p.add_argument('--output',type=Path,help='Optional existing batch directory for one log')
    p.add_argument('--reserve-gib',type=float,default=3,help='Explicit incremental-job space estimate, 1 to 3GiB; use the shared configured cache budget')
    p.add_argument('--native-output',type=Path,help='Freeze the two CLI binaries under the shared build lock; new absolute output directory only')
    p.add_argument('--local-minutes-preview',action='store_true',help='Build the isolated desktop candidate without opening the public minutes feature')
    a=p.parse_args()
    if os.name!='nt':p.error('Windows native build entry')
    if a.filter and a.task!='test':p.error('--filter applies to test')
    if not 1<=a.reserve_gib<=3:p.error('--reserve-gib must be1 to3; do not enlarge the cache budget')
    if a.native_output and (a.task!='build' or not a.native_output.is_absolute() or a.native_output.exists()):p.error('--native-output requires build and a new absolute path')
    cache=Path(os.environ.get('COMPANION_BUILD_CACHE','E:/CodexData/Companion/.build-cache'))
    target=cache/'shared-windows-target'
    try:
        with exclusive_build(cache/'.shared-windows-build.lock'):
            preflight(cache,reserve_gib=a.reserve_gib)
            native_root=ROOT/'apps/windows/src-tauri'
            owned=[native_root/name for name in ['Cargo.toml','Cargo.lock','build.rs']]
            owned.extend(p for p in (native_root/'src').rglob('*') if p.is_file())
            input_root=ROOT/'packages/desktop-input'
            owned.extend(p for p in input_root.rglob('*') if p.is_file() and (p.suffix=='.rs' or p.name in ['Cargo.toml','build.rs']))
            hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in owned if p.exists()}
            result=build(a,target)
            preflight(cache,reserve_gib=0)
            if result==0 and a.native_output:
                if any(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=v for p,v in hashes.items()):raise RuntimeError('Native inputs changed while compiling; do not freeze an ambiguous candidate')
                a.native_output.mkdir(parents=True,exist_ok=False)
                profile='release' if a.release else 'debug'
                for name in ['companion-type.exe','companion_type_lib.dll']:shutil.copyfile(target/profile/name,a.native_output/name)
                receipt={'authoringHead':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'profile':profile,'nativeSourceHashes':hashes,'binaries':{n:hashlib.sha256((a.native_output/n).read_bytes()).hexdigest() for n in ['companion-type.exe','companion_type_lib.dll']},'deliveryPreview':a.local_minutes_preview,'scope':'Engineering native candidate copied under the shared target lock; acceptance recorded separately'}
                (a.native_output/'source.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
            return result
    except (StorageLimit,OSError) as error:
        print(str(error),file=sys.stderr)
        return 2

def build(a,target):
    state=inspect(target,ROOT,source_dir=ROOT)
    if state['result']!='TARGET_IDLE_AT_OBSERVATION':
        print(state['result']+': the existing target is in use; do not allocate a duplicate target')
        return 2
    env=os.environ.copy();env['CARGO_TARGET_DIR']=str(target)
    env['CARGO_INCREMENTAL']='0';env['CARGO_PROFILE_DEV_DEBUG']='0';env['CARGO_PROFILE_TEST_DEBUG']='0'
    env.setdefault('CARGO_BUILD_JOBS','2')
    cmd=['cargo',a.task,'--locked','--manifest-path',str(ROOT/'apps/windows/src-tauri/Cargo.toml')]
    if a.release:cmd.append('--release')
    if a.local_minutes_preview:cmd.extend(['--features','local-minutes-delivery-preview'])
    if a.filter:cmd.extend(['--lib',a.filter])
    print('Using reusable native target: '+str(target),flush=True)
    if a.output:
        a.output.mkdir(parents=True,exist_ok=True)
        with (a.output/(a.task+('-release' if a.release else '')+'.log')).open('wb') as log:
            return subprocess.call(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    return subprocess.call(cmd,cwd=ROOT,env=env)
if __name__=='__main__':raise SystemExit(main())
