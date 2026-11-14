from pathlib import Path
from datetime import datetime
import hashlib,json,re,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/visual-meeting20261114')
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,text=True,encoding='utf8').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
assert json.loads((Q/'craft-r2/result.json').read_bytes())['state']=='PRODUCTION_MEETING_ENTRY_AND_EXPANDED_NOTES_BOTH_THEMES_PASSED'
assert json.loads((Q.parent/'software-value20261114/craft-r2/result.json').read_bytes())['errors']==[]
assert json.loads((Q.parent/'software-value20261114/craft-source-checks/result.json').read_bytes())['state']=='SOFTWARE_VALUE_BOTH_TYPES_PASSED'
shared=['packages/ui/src/'+n for n in['MeetingSectionHeading.tsx','MeetingAiWorkbench.tsx','meetingAiWorkbench.css','meetingNoteDocument.css','meetingVisual.css','notebookTheme.css']]
for rel in shared:assert(S/rel).read_bytes()==(A/rel).read_bytes()
# This shell stylesheet is desktop-only, and its scratch phone copy is unused.
p=A/'packages/ui/src/notebookFoundation.css';assert not git(A,'ls-files','--',str(p.relative_to(A)));assert p.read_bytes()==(S/'packages/ui/src/notebookFoundation.css').read_bytes();p.unlink()
own=shared+['packages/ui/src/notebookFoundation.css','packages/ui/src/CompanionDashboard.tsx']
git(S,'add','--',*own);git(S,'diff','--cached','--check','--',*own);git(S,'commit','--only','-m','Refine notebook reading hierarchy typography and assistant as one visual system','--',*own);author=git(S,'rev-parse','HEAD')
base='cbb59d13cd51cb70ff7b81da7644b3aded60ff3a';native_receipt=Path('E:/CodexData/Companion/deliveries/20261114-companion-stability143-fw66837/windows143-local/result.json');receipt=json.loads(native_receipt.read_bytes());assert receipt['sourceCommit']==base
assert not git(E,'status','--porcelain')
git(E,'fetch',str(S),author);git(E,'switch','-c','work/notebook-craft146-20261114',base)
# Include the complete144 material lifecycle before the current visual changes.
ui=own+['packages/ui/src/'+n for n in['MeetingWorkspaceNav.tsx','aiMaterialNote.ts','MinutesTemplatePreview.tsx','minutesTemplatePreview.css']]
tools=['tools/build_windows_delivery_local.py'];git(E,'restore','--source='+author,'--',*(ui+tools))
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
for name,count in[('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
 p=E/name;raw=p.read_bytes();assert raw.count(b'"version": "0.1.143"')==count;p.write_bytes(raw.replace(b'"version": "0.1.143"',b'"version": "0.1.146"'))
p=E/'apps/windows/src-tauri/Cargo.toml';raw=p.read_bytes();assert raw.count(b'version = "0.1.143"')==1;p.write_bytes(raw.replace(b'version = "0.1.143"',b'version = "0.1.146"'))
p=E/'apps/windows/src-tauri/Cargo.lock';raw,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.143(")',rb'\g<1>0.1.146\2',p.read_bytes());assert n==1;p.write_bytes(raw)
p=E/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=p.read_bytes()
for rel,old in json.loads(raw)['lockedInputs'].items():
 digest=sha(E/rel)
 if digest!=old:assert raw.count(old.encode())==1;raw=raw.replace(old.encode(),digest.encode())
p.write_bytes(raw);git(E,'add','--',*(ui+tools+versions));git(E,'diff','--cached','--check');git(E,'commit','-m','Freeze146 notebook visual craft with complete144 materials over normal143 input')
assert not git(E,'diff',base,'HEAD','--','packages/desktop-input','apps/windows/src/DesktopPointer.tsx','apps/windows/src-tauri/src','packages/core','third_party');assert not git(E,'status','--porcelain')
at=datetime.now().astimezone().isoformat(timespec='seconds');proof=dict(at=at,version='0.1.146',sourceCommit=git(E,'rev-parse','HEAD'),sourceRoot=str(E),frozenSourceRoot=str(E),branch=git(E,'branch','--show-current'),authoringSourceCommit=author,relatedAuthoringFiles=ui,saved143SourcePreserved=base,saved143Receipt=str(native_receipt),backendAndInputUnchangedSinceSaved143=True,uncommittedOtherChangesIncluded=False,normalWindowsBuildPending=True,installed=False,ownerAccepted=False,modelChangesIncluded=False);H=R/'docs/handoffs/20261112-product-closure/windows146';H.mkdir(exist_ok=False);save(H/'frozen-source.json',proof)
p=A/'apps/android/app/build.gradle';raw=p.read_bytes();assert raw.count(b'versionCode 163')==1;p.write_bytes(raw.replace(b'versionCode 163',b'versionCode 164').replace(b"versionName '0.1.163'",b"versionName '0.1.164'"))
phone=shared+['apps/mobile/src/MinutesDocument.tsx','apps/android/app/build.gradle'];git(A,'add','--',*phone);git(A,'diff','--cached','--check','--',*phone);git(A,'commit','--only','-m','Deliver shared notebook document hierarchy and restrained phone assistant styling','--',*phone)
assert sha(A/'apps/android/app/libs/companion-android-backend.aar')=='39acfbedb8cb4294be0455b3faa40d0033c25cc544aa6a2ae8c964f91a999a96'
old=json.loads((R/'docs/handoffs/20261110-android-media-import/android163/source.json').read_bytes());android={**old,'at':at,'versionCode':164,'versionName':'0.1.164','frontendSourceCommit':git(A,'rev-parse','HEAD'),'installed':False};H=R/'docs/handoffs/20261110-android-media-import/android164';H.mkdir(exist_ok=False);save(H/'source.json',android);save(Q/'source146164.json',dict(at=at,windows=proof,android=android,sourceReadingReview=str(Q/'craft-r2/result.json'),sourceMaterialReview=str(Q.parent/'software-value20261114/craft-r2/result.json'),scope='One coherent visual craft batch. Existing facts, model/input behavior and material export remain; no new cloud/speech or hardware use.'))
print(json.dumps(dict(state='NOTEBOOK146164_EXACT_SOURCE_FROZEN',windows=proof['sourceCommit'],android=android['frontendSourceCommit']),ensure_ascii=False))
