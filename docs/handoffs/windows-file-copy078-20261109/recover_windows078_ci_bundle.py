"""Repackage the verified CI native pair in a private byte-matched source copy."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,shutil,subprocess,tomllib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-windows-file-copy078';A=C/'ci-artifact'
D=Path('E:/CodexData/Companion/.build-cache/windows-file-copy078')
P=D/'bundle-source-ci';T=D/'bundle-target-ci'
receipt=json.loads((A/'result.json').read_text(encoding='utf8'))
assert receipt['sourceCommit']=='bb1550c42b674d7ec3e526db9f7fdefb84cff7ae'
assert receipt['state']=='CI_BUILD_FAILED_RETAINED' and receipt['error']=='AssertionError()'
assert 'Finished `release` profile [optimized]' in (A/'cargo-release.log').read_text(encoding='utf8')
assert 'Finished 1 bundle' in (A/'msi-bundle.log').read_text(encoding='utf8')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P.mkdir(exist_ok=False)
for row in receipt['sourceFiles']:
 raw=(S/row['path']).read_bytes()
 variants=[raw,raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
 raw=next(v for v in variants if hashlib.sha256(v).hexdigest()==row['sha256'])
 dest=P/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
for row in receipt['webAssets']:
 p=S/'apps/windows/dist'/row['path'];assert sha(p)==row['sha256']
 dest=P/'apps/windows/dist'/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for row in receipt['nativeFiles']:
 p=A/'windows-bin'/row['path'];assert sha(p)==row['sha256']
 dest=T/'release'/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
args=[os.sys.executable,str(R/'tools/check_type_build_target.py'),'--target-dir',str(T),'--project',str(P/'apps/windows/src-tauri'),'--source-dir',str(P),'--artifact-dir',str(A/'windows-bin')]
pre=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace')
(C/'private-ci-bundle-preflight.json').write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
before={row['path']:(P/row['path']).read_bytes() for row in receipt['sourceFiles']}
env={**os.environ,'CARGO_TARGET_DIR':str(T),'CARGO_BUILD_JOBS':'1','RAYON_NUM_THREADS':'1','TEMP':str(D),'TMP':str(D)}
with (C/'recovered-msi-bundle.log').open('wb') as log:
 run=subprocess.run(['C:/Program Files/nodejs/node.exe',str(S/'node_modules/@tauri-apps/cli/tauri.js'),'bundle','--bundles','msi','--ci','--no-sign'],cwd=P/'apps/windows',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
assert run.returncode==0,(C/'recovered-msi-bundle.log').read_text(encoding='utf8',errors='replace')[-3000:]
changes=[]
for name,raw in before.items():
 after=(P/name).read_bytes()
 if after!=raw:
  changes.append({'path':name,'beforeSha256':hashlib.sha256(raw).hexdigest(),'afterSha256':hashlib.sha256(after).hexdigest(),'onlyLineEndings':after.replace(b'\r\n',b'\n')==raw.replace(b'\r\n',b'\n'),'tomlSemanticallyIdentical':tomllib.loads(after.decode('utf8'))==tomllib.loads(raw.decode('utf8')) if name.endswith('.toml') else None})
  (C/('bundle-before-'+Path(name).name)).write_bytes(raw);(C/('bundle-after-'+Path(name).name)).write_bytes(after)
for row in receipt['nativeFiles']:assert sha(T/'release'/row['path'])==row['sha256']
for row in receipt['webAssets']:assert sha(P/'apps/windows/dist'/row['path'])==row['sha256']
generated=list((T/'release/bundle/msi').glob('*0.1.78*x64*.msi'));assert len(generated)==1
msi=C/'Companion-Windows-0.1.78-文件复制候选.msi';shutil.copy2(generated[0],msi)
result={'state':'PRIVATE_BUNDLE_COMPLETED_SOURCE_CHANGES_FOR_REVIEW','at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'ciSourceCommit':receipt['sourceCommit'],'sourceFiles':len(before),'ciExactWebAssetsMatched':True,'ciExactNativePairUnchanged':True,'privateSource':str(P),'target':str(T),'sourceChanges':changes,'msi':str(msi),'msiSha256':sha(msi),'nativeRecompiled':False,'installed':False}
(C/'bundle-recovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
