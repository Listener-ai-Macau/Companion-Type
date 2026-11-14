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

def verified_reuse(receipt,target,version):
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
 assert set(inputs)=={name for name in current if native(name)},'Native source inventory changed; use cold-build reserve'
 for name,digest in inputs.items():assert sha(ROOT/name)==digest,'Native source changed: '+name
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
 return dict(receipt=str(receipt),receiptSha256=sha(receipt),sourceCommit=previous['sourceCommit'],unchangedNativeInputs=len(inputs),cargoDependenciesUnchanged=True,reservedGiB=2)
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--reuse-build-receipt',type=Path,help='Completed same-target build with exact native inputs; reserve2GiB for an app-only rebuild')
 args=parser.parse_args()
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
   if args.reuse_build_receipt:
    record['verifiedWarmBuildReuse']=verified_reuse(args.reuse_build_receipt,target,record['version']);reserve=2
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
   run('windows-web',['cmd','/d','/c','npm.cmd','run','build:windows'])
   observed=inspect(target,ROOT,source_dir=ROOT);assert observed['result']=='TARGET_IDLE_AT_OBSERVATION',observed['result']
   dist=ROOT/'apps/windows/dist';record['webAssets']=[{'path':p.relative_to(dist).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(dist.rglob('*')) if p.is_file()]
   record['state']='LOCAL_NORMAL_RELEASE_BUILDING';save()
   run('cargo-release',['cargo','build','--release','--locked','--offline','--manifest-path',ROOT/'apps/windows/src-tauri/Cargo.toml'])
   pair=out/'windows-bin';pair.mkdir()
   for name in ['companion-type.exe','companion_type_lib.dll']:shutil.copyfile(target/'release'/name,pair/name)
   record['nativeFiles']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in pair.iterdir()]
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
