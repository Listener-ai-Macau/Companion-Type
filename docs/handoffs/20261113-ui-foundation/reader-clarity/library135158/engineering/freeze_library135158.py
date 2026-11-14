from pathlib import Path
from datetime import datetime
import copy,hashlib,json,re,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/library-closure20261114')
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,text=True,encoding='utf8').strip()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
checks=json.loads((Q/'source-checks/result.json').read_bytes());assert all(x['exitCode']==0 for x in checks['steps']);assert json.loads((Q/'after-r1/result.json').read_bytes())['state']=='PRODUCTION_UI_SCOPE_SELECTION_AND_DRAFT_FLOW_PASSED'
ui=['packages/ui/src/CompanionDashboard.tsx','packages/ui/src/CompanionLibraryTools.tsx','packages/ui/src/LibraryScopeChips.tsx','packages/ui/src/libraryScopeChips.css','packages/ui/src/notebookFoundation.css']
git(S,'add','--',*ui);git(S,'diff','--cached','--check','--',*ui);git(S,'commit','--only','-m','Clarify recording scope and selected targets before organization','--',*ui);author=git(S,'rev-parse','HEAD')
assert not git(E,'status','--porcelain')
base='e8ab9a987d91aa0dc8171fbb251cfc04c6ca8ae7';receipt=Path('E:/CodexData/Companion/deliveries/20261114-companion-click134-fw66833/delivery.json');assert json.loads(receipt.read_bytes())['windowsSource']==base
assert not git(S,'diff','e7603bd5',base,'--','packages/ui')
git(E,'fetch',str(S),author);git(E,'switch','-c','work/library135-closure-20261114',base);git(E,'restore','--source='+author,'--',*ui)
for rel,count in [('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
 p=E/rel;t=p.read_bytes();assert t.count(b'"version": "0.1.134"')==count;p.write_bytes(t.replace(b'"version": "0.1.134"',b'"version": "0.1.135"'))
p=E/'apps/windows/src-tauri/Cargo.toml';t=p.read_bytes();assert t.count(b'version = "0.1.134"')==1;p.write_bytes(t.replace(b'version = "0.1.134"',b'version = "0.1.135"'))
p=E/'apps/windows/src-tauri/Cargo.lock';t,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.134(")',rb'\g<1>0.1.135\2',p.read_bytes());assert n==1;p.write_bytes(t)
p=E/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';t=p.read_bytes()
for rel,old in json.loads(t)['lockedInputs'].items():
 digest=sha(E/rel)
 if digest!=old:assert t.count(old.encode())==1;t=t.replace(old.encode(),digest.encode())
p.write_bytes(t)
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
git(E,'add','--',*(ui+versions));git(E,'diff','--cached','--check');assert set(git(E,'diff','--cached','--name-only').splitlines())<=set(ui+versions);git(E,'commit','-m','Freeze135 library flow closure over saved134 input repair')
stable=['packages/desktop-input','apps/windows/src/DesktopPointer.tsx','apps/windows/src-tauri/src/backend','third_party/denzic-platform','third_party/imu-pointer'];assert not git(E,'diff',base,'HEAD','--',*stable);assert not git(E,'status','--porcelain')
h=R/'docs/handoffs/20261112-product-closure/windows135';h.mkdir(exist_ok=False)
proof=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),version='0.1.135',sourceCommit=git(E,'rev-parse','HEAD'),sourceRoot=str(E),frozenSourceRoot=str(E),branch=git(E,'branch','--show-current'),authoringSourceCommit=author,relatedAuthoringFiles=ui,saved134SourcePreserved=base,saved134Receipt=str(receipt),backendAndInputUnchangedSinceSaved134=True,uncommittedOtherChangesIncluded=False,normalWindowsBuildPending=True,installed=False,ownerAccepted=False,modelChangesIncluded=False)
save(h/'frozen-source.json',proof);save(Q/'windows-source.json',proof)
apaths=['apps/mobile/src/RecordingLibraryManager.tsx','apps/mobile/src/notebookMobile.css','packages/ui/src/LibraryScopeChips.tsx','packages/ui/src/libraryScopeChips.css','apps/android/app/build.gradle']
p=A/'apps/android/app/build.gradle';t=p.read_bytes();assert t.count(b'versionCode 157')==1;p.write_bytes(t.replace(b'versionCode 157',b'versionCode 158').replace(b"versionName '0.1.157'",b"versionName '0.1.158'"))
git(A,'add','--',*apaths);git(A,'diff','--cached','--check','--',*apaths);git(A,'commit','--only','-m','Make phone recording selection compact and visible without hiding the list','--',*apaths)
aar=A/'apps/android/app/libs/companion-android-backend.aar';assert sha(aar)=='39acfbedb8cb4294be0455b3faa40d0033c25cc544aa6a2ae8c964f91a999a96'
h=R/'docs/handoffs/20261110-android-media-import/android158';h.mkdir(exist_ok=False);android=dict(at=proof['at'],versionCode=158,versionName='0.1.158',frontendSourceCommit=git(A,'rev-parse','HEAD'),frontendBranch=git(A,'branch','--show-current'),backendSourceCommit='92f53ef78a8cfd78caa60b98767dddbdf4c37583',aarSha256=sha(aar),nativeLibrariesRebuilt=False,nativeAarByteIdenticalToActual157=True,modelWorkAssignedOtherChat=True,modelsRun=False,installed=False);save(h/'source.json',android);save(Q/'android-source.json',android)
p=R/'docs/product_backlog.json';raw=p.read_bytes();text=raw.decode();d=json.loads(text);a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);f=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['completeProductRework20261113']['noteReadabilityFollowup'];f['backgroundContinuation20261114'].update(updatedAt=proof['at'],state='135158_LIBRARY_FRONTEND_SOURCE_VERIFIED_MATCHING_NATIVE_BUILDS_NEXT',windowsSource=proof['sourceCommit'],androidSource=android['frontendSourceCommit'],baseline=str(Q/'baseline/result.json'),sourceChecks=str(Q/'source-checks/result.json'),sourceUiReview=str(Q/'after-r1/result.json'),selectionPanelBeforePixels=445.1875,selectionPanelAfterPixels=46,modelsChanged=False)
a.update(updatedAt=proof['at'],state=f['backgroundContinuation20261114']['state'],next='Matching normal135/158, affected real native scope/selection/draft paths plus complete retained reading/export/reopen; one protected final delivery after background closure.')
hits=[]
for m in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
 v,n=json.JSONDecoder().raw_decode(text[m.end():])
 if v==old:hits.append((m,n))
assert len(hits)==1;m,n=hits[0];out=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:];assert p.read_bytes()==raw;p.write_bytes(out.encode())
print(json.dumps(dict(windows=proof['sourceCommit'],android=android['frontendSourceCommit'],modelsChanged=False),ensure_ascii=False))
