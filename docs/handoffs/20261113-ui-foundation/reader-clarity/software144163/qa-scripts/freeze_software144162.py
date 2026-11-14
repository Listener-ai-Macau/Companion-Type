from pathlib import Path
from datetime import datetime
import hashlib,json,re,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source')
Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/software-value20261114')
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,text=True,encoding='utf8').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
assert json.loads((Q/'r3/result.json').read_bytes())['errors']==[]
assert not (R/'docs/handoffs/20261112-product-closure/windows144').exists()
assert not (R/'docs/handoffs/20261110-android-media-import/android162').exists()
shared=['packages/ui/src/'+n for n in ['MeetingAiWorkbench.tsx','meetingAiWorkbench.css','aiMaterialNote.ts','MinutesTemplatePreview.tsx','minutesTemplatePreview.css']]
for name in shared:assert(S/name).read_bytes()==(A/name).read_bytes(),name
ui=shared+['packages/ui/src/MeetingWorkspaceNav.tsx','packages/ui/src/CompanionDashboard.tsx']
qa=['tools/test_document_context_panel.tsx']
git(S,'add','--',*(ui+qa));git(S,'diff','--cached','--check','--',*(ui+qa));git(S,'commit','--only','-m','Connect meeting questions to readable saved materials and exact export','--',*(ui+qa))
author=git(S,'rev-parse','HEAD');base='46e0a1180d7f6efc5d5e7ca9d1d9b7c7dac7ac5a'
assert not git(E,'status','--porcelain')
# Normal142 is the completed immutable native receipt. New unverified input
# edits and its independent Owner window remain owned by the embedded worker.
git(E,'fetch',str(S),author);git(E,'switch','-c','work/software-material144-20261114',base)
tools=['tools/build_windows_delivery_local.py']
git(E,'restore','--source='+author,'--',*(ui+tools))
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
for name,count in [('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
 p=E/name;raw=p.read_bytes();assert raw.count(b'"version": "0.1.142"')==count;p.write_bytes(raw.replace(b'"version": "0.1.142"',b'"version": "0.1.144"'))
p=E/'apps/windows/src-tauri/Cargo.toml';raw=p.read_bytes();assert raw.count(b'version = "0.1.142"')==1;p.write_bytes(raw.replace(b'version = "0.1.142"',b'version = "0.1.144"'))
p=E/'apps/windows/src-tauri/Cargo.lock';raw,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.142(")',rb'\g<1>0.1.144\2',p.read_bytes());assert n==1;p.write_bytes(raw)
p=E/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=p.read_bytes()
for rel,old in json.loads(raw)['lockedInputs'].items():
 digest=sha(E/rel)
 if digest!=old:assert raw.count(old.encode())==1;raw=raw.replace(old.encode(),digest.encode())
p.write_bytes(raw)
git(E,'add','--',*(ui+tools+versions));git(E,'diff','--cached','--check');assert set(git(E,'diff','--cached','--name-only').splitlines())<=set(ui+tools+versions)
git(E,'commit','-m','Freeze144 meeting assistant material lifecycle over normal142 native backend')
stable=['packages/desktop-input','packages/core','apps/windows/src/DesktopPointer.tsx','apps/windows/src-tauri/src','third_party']
assert not git(E,'diff',base,'HEAD','--',*stable);assert not git(E,'status','--porcelain')
at=datetime.now().astimezone().isoformat(timespec='seconds')
proof=dict(at=at,version='0.1.144',sourceCommit=git(E,'rev-parse','HEAD'),sourceRoot=str(E),frozenSourceRoot=str(E),branch=git(E,'branch','--show-current'),authoringSourceCommit=author,relatedAuthoringFiles=ui,saved142SourcePreserved=base,saved142Receipt='E:/CodexData/Companion/deliveries/20261114-companion-front142-fw66837/windows142-deps-local/result.json',backendAndInputUnchangedSinceSaved142=True,uncommittedOtherChangesIncluded=False,normalWindowsBuildPending=True,installed=False,ownerAccepted=False,modelChangesIncluded=False)
save(R/'docs/handoffs/20261112-product-closure/windows144/frozen-source.json',proof)
p=A/'apps/android/app/build.gradle';raw=p.read_bytes();assert raw.count(b'versionCode 161')==1;p.write_bytes(raw.replace(b'versionCode 161',b'versionCode 162').replace(b"versionName '0.1.161'",b"versionName '0.1.162'"))
phone=shared+['apps/mobile/src/App.tsx','apps/mobile/src/MinutesTemplates.tsx','apps/mobile/src/RecordingContentNavigation.tsx','apps/android/app/build.gradle']
git(A,'add','--',*phone);git(A,'diff','--cached','--check','--',*phone);git(A,'commit','--only','-m','Deliver visible meeting assistant with protected material save and export on phone','--',*phone)
assert sha(A/'apps/android/app/libs/companion-android-backend.aar')=='39acfbedb8cb4294be0455b3faa40d0033c25cc544aa6a2ae8c964f91a999a96'
old=json.loads((R/'docs/handoffs/20261110-android-media-import/android161/source.json').read_bytes())
android={**old,'at':at,'versionCode':162,'versionName':'0.1.162','frontendSourceCommit':git(A,'rev-parse','HEAD'),'installed':False}
save(R/'docs/handoffs/20261110-android-media-import/android162/source.json',android)
save(Q/'source144162.json',dict(at=at,windows=proof,android=android,sourceUiReview=str(Q/'r3/result.json'),scope='Source-bound meeting assistant to editable saved material and exact export; no new model, hardware, enterprise service or accuracy claim.'))
print(json.dumps(dict(state='SOFTWARE144162_EXACT_SOURCE_FROZEN',windows=proof['sourceCommit'],android=android['frontendSourceCommit']),ensure_ascii=False))
