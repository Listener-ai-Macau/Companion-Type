"""Clean Windows candidate build on CI; no publishing, user data or inference."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess,traceback,tomllib,time
from check_type_build_target import inspect

S=Path(__file__).resolve().parents[1]
C=S/'ci-output';C.mkdir(exist_ok=False)
N=S/'apps/windows/src-tauri';T=Path(os.environ['CARGO_TARGET_DIR'])
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def capture(args,cwd=S):return subprocess.check_output(args,cwd=cwd,text=True,encoding='utf8').strip()
def run(name,args,cwd=S):
 started=time.perf_counter();print('Starting '+name,flush=True)
 with (C/(name+'.log')).open('wb') as log:
  p=subprocess.run(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT)
 print(f'Finished {name}: exit={p.returncode}, seconds={time.perf_counter()-started:.3f}',flush=True)
 if p.returncode:raise RuntimeError(f'{name} failed: {p.returncode}; see retained log')
def source_change(name,expected,after,before_manifest):
 actual=hashlib.sha256(after).hexdigest()
 if actual==expected:return None
 # Reproduced Tauri bundle behavior: CRLF -> LF in the application's own
 # manifest, after compilation. Accept only this exact formatting change.
 # Other source changes, dependency changes and all lock/license checks fail.
 if name=='apps/windows/src-tauri/Cargo.toml' and hashlib.sha256(before_manifest).hexdigest()==expected and after.replace(b'\r\n',b'\n')==before_manifest.replace(b'\r\n',b'\n') and tomllib.loads(after.decode('utf8'))==tomllib.loads(before_manifest.decode('utf8')):
  return {'path':name,'beforeSha256':expected,'afterSha256':actual,'onlyLineEndings':True,'tomlSemanticallyIdentical':True}
 raise AssertionError('Build input changed: '+name)
def save():(C/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
record={'at':datetime.now(timezone.utc).isoformat(),'state':'PREPARING_CLEAN_WINDOWS_CANDIDATE','sourceCommit':capture(['git','rev-parse','HEAD']),'platformCommit':capture(['git','rev-parse','HEAD'],S/'third_party/denzic-platform'),'version':json.loads((N/'tauri.conf.json').read_text())['version'],'modelsRun':False,'installed':False,'ordinaryRecipientTested':False,'saleQualified':False}
save()
try:
 assert os.name=='nt' and os.environ.get('GITHUB_ACTIONS')=='true','Dedicated Windows CI only'
 expected_platform=capture(['git','ls-tree','HEAD','third_party/denzic-platform']).split()[2]
 assert record['platformCommit']==expected_platform
 manifest=json.loads((N/'resources/licenses/ThirdPartyComponents.json').read_text(encoding='utf8'))
 # Preserve the recorded byte-level lock identity. Checkouts may translate
 # line endings; only an exact blob or its LF/CRLF representation is allowed.
 for name,expected in manifest['lockedInputs'].items():
  path=S/name
  if sha(path)!=expected:
   raw=subprocess.check_output(['git','show','HEAD:'+name],cwd=S)
   variants=[raw,raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
   actual=next((v for v in variants if hashlib.sha256(v).hexdigest()==expected),None)
   assert actual is not None,'Lock inventory differs from committed dependency input: '+name
   path.write_bytes(actual)
 record['lockedInputs']={name:sha(S/name) for name in manifest['lockedInputs']}
 record['rustc']=capture(['rustc','+1.95.0','--version']);record['node']=capture(['node','--version'])
 run('npm-ci',['npm.cmd','ci','--no-audit','--no-fund'])
 run('windows-web',['npm.cmd','run','build:windows'])
 dist=S/'apps/windows/dist'
 record['webAssets']=[{'path':p.relative_to(dist).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(dist.rglob('*')) if p.is_file()]
 names=capture(['git','ls-files','--recurse-submodules','--','apps/windows','packages','third_party','package.json','package-lock.json','tsconfig.base.json']).splitlines()
 record['sourceFiles']=[{'path':name,'sha256':sha(S/name)} for name in names if (S/name).is_file()]
 before_manifest=(N/'Cargo.toml').read_bytes()
 preflight=inspect(T,S,source_dir=S)
 (C/'native-target-preflight.json').write_text(json.dumps(preflight,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 assert preflight['result']=='TARGET_IDLE_AT_OBSERVATION',preflight['result']
 record['state']='BUILDING_NORMAL_RELEASE';save()
 run('cargo-release',['cargo','+1.95.0','build','--release','--locked'],N)
 run('recording-context-tests',['cargo','+1.95.0','test','--release','--locked','--lib','meeting_note','--','--test-threads=1'],N)
 pair=C/'windows-bin';pair.mkdir()
 for name in ['companion-type.exe','companion_type_lib.dll']:shutil.copy2(T/'release'/name,pair/name)
 record['nativeFiles']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in pair.iterdir()]
 record['state']='BUNDLING_MATCHING_NATIVE_PAIR';save()
 run('msi-bundle',['node',str(S/'node_modules/@tauri-apps/cli/tauri.js'),'bundle','--bundles','msi','--ci','--no-sign'],S/'apps/windows')
 # Retain the actual MSI even if later verification fails; a failed guard
 # never becomes permission to install it without independent inspection.
 installers=list((T/'release/bundle/msi').glob('*'+record['version']+'*x64*.msi'));assert len(installers)==1,installers
 msi=C/f"Companion-Windows-{record['version']}-candidate.msi";shutil.copy2(installers[0],msi)
 record.update(msi=msi.name,msiSha256=sha(msi),state='VERIFYING_BUNDLE_INPUTS');save()
 for row in record['nativeFiles']:assert sha(T/'release'/row['path'])==row['sha256']
 for row in record['webAssets']:assert sha(dist/row['path'])==row['sha256']
 record['postBundleSourceFormatting']=[]
 for row in record['sourceFiles']:
  change=source_change(row['path'],row['sha256'],(S/row['path']).read_bytes(),before_manifest)
  if change:record['postBundleSourceFormatting'].append(change)
 raw=(pair/'companion-type.exe').read_bytes();assert raw.count(b'__TAURI_BUNDLE_TYPE_VAR_UNK')==1
 record['expectedEmbeddedExeSha256']=hashlib.sha256(raw.replace(b'__TAURI_BUNDLE_TYPE_VAR_UNK',b'__TAURI_BUNDLE_TYPE_VAR_MSI')).hexdigest()
 record['expectedDllSha256']=sha(pair/'companion_type_lib.dll')
 resources=N/'resources'
 record['licenseFiles']=[{'path':p.relative_to(resources).as_posix(),'sha256':sha(p)} for p in (resources/'licenses').rglob('*') if p.is_file()]
 record['licenseFiles'].append({'path':'opus-license.txt','sha256':sha(resources/'opus-license.txt')})
 record.update(state='CI_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING',finishedAt=datetime.now(timezone.utc).isoformat(),msi=msi.name,msiSha256=sha(msi),normalReleaseOptimization=True,nativeAndWebUnchangedAfterBundle=True,localMsiPayloadInspectionRequired=True)
 save();print(json.dumps({k:record[k] for k in ['state','sourceCommit','version','msi','msiSha256']},ensure_ascii=False))
except BaseException as error:
 record.update(state='CI_BUILD_FAILED_RETAINED',error=repr(error),finishedAt=datetime.now(timezone.utc).isoformat());save()
 (C/'failure.txt').write_text(traceback.format_exc(),encoding='utf8');raise
