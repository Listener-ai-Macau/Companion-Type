"""Build one normal local MSI in the existing shared target, with source receipts.

Used when the hosted build cannot start. This is a local build, never a CI pass.
No installer, app, microphone, model or recorder is started by this entry.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,re,shutil,subprocess,sys,time,traceback
from check_type_build_target import inspect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/scripts')
from development_storage import exclusive_build,preflight
from windows_build_limits import NativeBuildLimits

def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def capture(args,cwd=ROOT):return subprocess.check_output(list(map(str,args)),cwd=cwd,text=True,encoding='utf-8').strip()

def verified_reuse(receipt,target,version,local_crates=False,input_adapter=False):
 """Estimate an app-only rebuild after verifying a completed matching native build.

 The cold-build estimate remains8GiB. A matching warm build reserves2GiB;
 the common80GiB cache and30GiB free-space limits still apply without deletion.
 """
 previous=json.loads(receipt.read_bytes())
 assert previous['state']=='LOCAL_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING'
 assert Path(previous['sharedTarget']).resolve()==target.resolve()
 assert previous['normalReleaseOptimization'] and previous['nativeAndWebUnchangedAfterBundle']
 assert sha(Path(previous['msi']))==previous['msiSha256']
 for item in previous['nativeFiles']:assert sha(receipt.parent/'windows-bin'/item['path'])==item['sha256']
 assert capture(['rustc','+1.95.0','--version'])==previous['rustc']
 assert capture(['git','rev-parse','HEAD'],ROOT/'third_party/denzic-platform')==previous['platformCommit']
 suffixes={'.rs','.c','.h','.cpp','.hpp','.a','.lib','.s'}
 native=lambda name:Path(name).suffix.lower() in suffixes
 inputs={row['path']:row['sha256']for row in previous['sourceFiles']if native(row['path'])}
 current=capture(['git','ls-files','--recurse-submodules','--','apps/windows','packages','third_party']).splitlines()
 current_native={name for name in current if native(name)}
 added=current_native-set(inputs);removed=set(inputs)-current_native
 # Local app/core Rust edits reuse the already-built external dependency graph.
 # This is an estimate for two warm crates, not an override of the80GiB budget.
 # No changed build scripts, manifests, features, toolchain or external C/FFI.
 # The explicit input-adapter scope may additionally rebuild this one local
 # C shim inside desktop-input; all upstream headers/sources remain hashed.
 local_shim='packages/desktop-input/src/pointer/fusion_adapter.c'
 allowed=lambda name:(name.endswith('.rs') and (name.startswith('apps/windows/src-tauri/src/') or name.startswith('packages/desktop-input/src/')))or(input_adapter and name==local_shim)
 reference={'third_party/imu-pointer/grt/DTW.cpp'} if local_crates else set()
 assert not removed and all(name in reference or(local_crates and allowed(name))for name in added),'Native source inventory changed; use cold-build reserve'
 changed=[name for name,digest in inputs.items()if sha(ROOT/name)!=digest]
 assert all(local_crates and allowed(name)for name in changed),'External/native build inputs changed; use cold-build reserve'
 for row in previous['sourceFiles']:
  name=row['path']
  if name.endswith(('Cargo.toml','Cargo.lock')) and name not in ['apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock']:
   assert sha(ROOT/name)==row['sha256'],'Dependency configuration changed: '+name
 for name in added&reference:
  # The pinned C++ reference is shipped as source/provenance; neither build
  # script compiles it. The actual linked implementation is the local Rust port.
  assert 'DTW.cpp' not in (ROOT/'packages/desktop-input/build.rs').read_text()
  assert 'DTW.cpp' not in (ROOT/'apps/windows/src-tauri/build.rs').read_text()
 for name in ['apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock']:
  before=subprocess.check_output(['git','show',previous['sourceCommit']+':'+name],cwd=ROOT).replace(b'\r\n',b'\n')
  after=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
  if name.endswith('Cargo.lock'):
   before,n=re.subn(rb'(name = "companion-type"\nversion = ")[^"]+("\n)',lambda m:m[1]+version.encode()+m[2],before)
   assert n==1
  else:
   old=('version = "'+previous['version']+'"').encode();assert before.count(old)==1
   before=before.replace(old,('version = "'+version+'"').encode())
  assert before==after,'Cargo dependencies changed; use cold-build reserve'
 assert (target/'release/deps').is_dir() and (target/'release/companion-type.exe').is_file()
 return dict(receipt=str(receipt),receiptSha256=sha(receipt),sourceCommit=previous['sourceCommit'],unchangedNativeInputs=len(inputs)-len(changed),changedLocalRustInputs=[name for name in changed if name.endswith('.rs')],changedLocalCAdapters=[name for name in changed if name==local_shim],newLocalRustInputs=sorted(added-reference),newUncompiledReferenceInputs=sorted(added&reference),cargoDependenciesUnchanged=True,reuseScope='two-local-crates-and-input-shim'if input_adapter else'two-local-crates'if local_crates else'unchanged-native',reservedGiB=2)
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--reuse-build-receipt',type=Path,help='Completed same-target build with exact native inputs; reserve2GiB for an app-only rebuild')
 parser.add_argument('--reuse-dependency-build-receipt',type=Path,help='Verified same-toolchain/dependencies; only app/input Rust sources may differ; reserve2GiB for those warm crates')
 parser.add_argument('--reuse-input-adapter-build-receipt',type=Path,help='Verified same dependencies, app/input Rust and the single local Fusion C shim; reserve2GiB without allowing upstream C/header changes')
 parser.add_argument('--native-only',action='store_true',help='Verified warm native/web stage,1.5GiB reserve; no MSI yet')
 parser.add_argument('--bundle-native-receipt',type=Path,help='Exact completed native/web stage; hash-check and bundle only,256MiB reserve')
 args=parser.parse_args()
 assert not(args.native_only and args.bundle_native_receipt),'Choose one delivery stage'

 assert os.name=='nt' and os.environ.get('GITHUB_ACTIONS')!='true'
 cache=Path('E:/CodexData/Companion/.build-cache');target=cache/'shared-windows-target';out=args.output.resolve()
 # Completed releases belong outside the reusable compiler cache.
 delivery_root=(cache.parent/'deliveries').resolve()
 assert out.is_relative_to(cache.resolve()) or out.is_relative_to(delivery_root),'Output must stay within Companion cache or deliveries'
 assert not out.exists(),'Preserve earlier build attempts'
 out.mkdir(parents=True)
 record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'LOCAL_WINDOWS_DELIVERY_BUILD_PREPARING','sourceCommit':capture(['git','rev-parse','HEAD']),'platformCommit':capture(['git','rev-parse','HEAD'],ROOT/'third_party/denzic-platform'),'version':json.loads((ROOT/'apps/windows/src-tauri/tauri.conf.json').read_bytes())['version'],'modelsRun':False,'boardAccessed':False,'installed':False,'hostedCiRun':None,'saleQualified':False,'steps':[]}
 def save():(out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 save()
 env={**os.environ,'CARGO_TARGET_DIR':str(target),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_BUILD_JOBS':'1','RUSTUP_TOOLCHAIN':'1.95.0','PYTHONUTF8':'1'}
 def run(name,command,cwd=ROOT):
  started=time.monotonic();print('Starting '+name,flush=True)
  with (out/(name+'.log')).open('wb') as log:result=subprocess.run(list(map(str,command)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  record['steps'].append({'name':name,'exitCode':result.returncode,'seconds':round(time.monotonic()-started,3)});save()
  assert result.returncode==0,name+' failed; preserved '+str(out/(name+'.log'))
  print('Finished '+name,flush=True)
 try:
  limits=NativeBuildLimits();record.update(cpuHardCapPercent=10,jobPrivateCommitLimitBytes=6*1024**3,resourceLimits=limits.query())
  with exclusive_build(cache/'.shared-windows-build.lock'):
   # First normal release in this fixed target may need up to8GiB for crates;
   # this estimate does not increase the common80GiB budget or delete anything.
   reserve=8
   staged=None
   if args.bundle_native_receipt:
    staged=json.loads(args.bundle_native_receipt.read_bytes())
    assert staged['state']=='LOCAL_WINDOWS_NATIVE_STAGE_COMPLETE_BUNDLE_PENDING'
    assert staged['sourceCommit']==record['sourceCommit'] and staged['platformCommit']==record['platformCommit'] and staged['version']==record['version']
    assert Path(staged['sharedTarget']).resolve()==target.resolve() and staged['normalReleaseOptimization']
    assert capture(['rustc','+1.95.0','--version'])==staged['rustc']
    for row in staged['sourceFiles']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
    for row in staged['webAssets']:assert sha(ROOT/'apps/windows/dist'/row['path'])==row['sha256'],row['path']
    for row in staged['nativeFiles']:
     assert sha(target/'release'/row['path'])==row['sha256'] and sha(args.bundle_native_receipt.parent/'windows-bin'/row['path'])==row['sha256']
    reserve=0.25
    record['verifiedNativeStageReuse']={'receipt':str(args.bundle_native_receipt),'sha256':sha(args.bundle_native_receipt),'nativeAndWebExact':True,'reservedGiB':reserve}
   assert sum(bool(value)for value in [args.reuse_build_receipt,args.reuse_dependency_build_receipt,args.reuse_input_adapter_build_receipt])<=1,'Choose one reuse scope'
   reuse=args.reuse_build_receipt or args.reuse_dependency_build_receipt or args.reuse_input_adapter_build_receipt
   assert not(staged and reuse),'Native-stage reuse already verifies exact inputs'
   if args.native_only:assert reuse,'Warm native-stage estimate requires a verified existing dependency graph'
   if reuse:
    record['verifiedWarmBuildReuse']=verified_reuse(reuse,target,record['version'],bool(args.reuse_dependency_build_receipt or args.reuse_input_adapter_build_receipt),bool(args.reuse_input_adapter_build_receipt));reserve=1.5 if args.native_only else 2
   record['storageBefore']=preflight(cache,reserve_gib=reserve)
   observed=inspect(target,ROOT);assert observed['result']=='TARGET_IDLE_AT_OBSERVATION',observed['result']
   assert not capture(['git','status','--porcelain','--untracked-files=no']),'Commit the exact source before a normal delivery build'
   assert capture(['git','ls-tree','HEAD','third_party/denzic-platform']).split()[2]==record['platformCommit']
   record['rustc']=capture(['rustc','+1.95.0','--version']);record['node']=capture(['node','--version'])
   inventory=json.loads((ROOT/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json').read_bytes())
   for name,digest in inventory['lockedInputs'].items():assert sha(ROOT/name)==digest,name
   names=capture(['git','ls-files','--recurse-submodules','--','apps/windows','packages','third_party','package.json','package-lock.json','tsconfig.base.json']).splitlines()
   record['sourceFiles']=[{'path':name,'sha256':sha(ROOT/name)} for name in names if (ROOT/name).is_file()]
   before_manifest=(ROOT/'apps/windows/src-tauri/Cargo.toml').read_bytes()
   if not staged:run('windows-web',['cmd','/d','/c','npm.cmd','run','build:windows'])
   observed=inspect(target,ROOT,source_dir=ROOT);assert observed['result']=='TARGET_IDLE_AT_OBSERVATION',observed['result']
   dist=ROOT/'apps/windows/dist';record['webAssets']=[{'path':p.relative_to(dist).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(dist.rglob('*')) if p.is_file()]
   record['state']='LOCAL_NORMAL_RELEASE_BUILDING';save()
   if not staged:run('cargo-release',['cargo','build','--release','--locked','--offline','--manifest-path',ROOT/'apps/windows/src-tauri/Cargo.toml'])
   pair=out/'windows-bin';pair.mkdir()
   for name in ['companion-type.exe','companion_type_lib.dll']:shutil.copyfile(target/'release'/name,pair/name)
   record['nativeFiles']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in pair.iterdir()]
   if args.native_only:
    for row in record['sourceFiles']:assert sha(ROOT/row['path'])==row['sha256'],row['path']
    record.update(state='LOCAL_WINDOWS_NATIVE_STAGE_COMPLETE_BUNDLE_PENDING',normalReleaseOptimization=True,sharedTarget=str(target),intermediateTargetCopies=0,automaticDeletion=False,finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'))
    record['storageAfter']=preflight(cache,reserve_gib=0);record['resourceLimits']=limits.query();save()
    print(json.dumps({k:record[k]for k in ['state','sourceCommit','version','nativeFiles']},ensure_ascii=False));return
   run('msi-bundle',['node',ROOT/'node_modules/@tauri-apps/cli/tauri.js','bundle','--bundles','msi','--ci','--no-sign'],ROOT/'apps/windows')
   installers=list((target/'release/bundle/msi').glob('*'+record['version']+'*x64*.msi'));assert len(installers)==1
   installer=out/('Companion-Windows-'+record['version']+'.msi');shutil.copyfile(installers[0],installer)
   for row in record['nativeFiles']:assert sha(target/'release'/row['path'])==row['sha256']
   for row in record['webAssets']:assert sha(dist/row['path'])==row['sha256']
   record['postBundleSourceFormatting']=[]
   for row in record['sourceFiles']:
    actual=(ROOT/row['path']).read_bytes()
    if hashlib.sha256(actual).hexdigest()!=row['sha256']:
     assert row['path']=='apps/windows/src-tauri/Cargo.toml' and actual.replace(b'\r\n',b'\n')==before_manifest.replace(b'\r\n',b'\n'),row['path']
     record['postBundleSourceFormatting'].append({'path':row['path'],'onlyLineEndings':True})
   binary=(pair/'companion-type.exe').read_bytes();assert binary.count(b'__TAURI_BUNDLE_TYPE_VAR_UNK')==1
   resources=ROOT/'apps/windows/src-tauri/resources'
   record.update(state='LOCAL_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING',msi=str(installer),msiSha256=sha(installer),expectedEmbeddedExeSha256=hashlib.sha256(binary.replace(b'__TAURI_BUNDLE_TYPE_VAR_UNK',b'__TAURI_BUNDLE_TYPE_VAR_MSI')).hexdigest(),expectedDllSha256=sha(pair/'companion_type_lib.dll'),licenseFiles=[{'path':p.relative_to(resources).as_posix(),'sha256':sha(p)} for p in (resources/'licenses').rglob('*') if p.is_file()]+[{'path':'opus-license.txt','sha256':sha(resources/'opus-license.txt')}],normalReleaseOptimization=True,nativeAndWebUnchangedAfterBundle=True,sharedTarget=str(target),intermediateTargetCopies=0,automaticDeletion=False,finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'));save()
   record['resourceLimits']=limits.query();save()
   print(json.dumps({k:record[k] for k in ['state','sourceCommit','version','msi','msiSha256']},ensure_ascii=False))
 except BaseException as error:
  record.update(state='LOCAL_WINDOWS_DELIVERY_BUILD_FAILED_RETAINED',error=repr(error));save();(out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
if __name__=='__main__':main()
