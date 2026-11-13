from pathlib import Path
from datetime import datetime
import hashlib,json,re,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,text=True,encoding='utf8').strip()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
checks=json.loads((O/'note-readability-followup-r4/result.json').read_bytes());assert all(x['exitCode']==0 for x in checks['steps'])
preview=json.loads((O/'note-readability-component-preview-r4/result.json').read_bytes());assert preview['state']=='SOURCE_COMPONENT_NOTE_AND_TRANSCRIPT_REVIEW_PASSED'
ui=['packages/ui/src/CompanionDashboard.tsx','packages/ui/src/transcriptReading.ts','packages/ui/src/TranscriptFind.tsx','packages/ui/src/MeetingTopic.tsx','packages/ui/src/meetingReading.ts','packages/ui/src/overviewTopics.css','packages/ui/src/meetingNoteDocument.css']
tests=['tools/test_note_readability.tsx','tools/test_transcript_reading_20261103.tsx','tools/test_long_minutes_reading.tsx']
git(S,'add','--',*(ui+tests));git(S,'diff','--cached','--check','--',*(ui+tests));git(S,'commit','--only','-m','Use mature meeting-note hierarchy and reversible Chinese transcript reading','--',*(ui+tests));author=git(S,'rev-parse','HEAD')
assert not git(E,'status','--porcelain')
base='2289585f163405c9b1451912ee74e3a403e0f4cf';old='af02c09d6b7b5773ed9d7ef76ffc0be98937bb81'
candidate=Path('E:/CodexData/Companion/deliveries/20261113-companion-tilt130-fw66832/delivery.json');assert json.loads(candidate.read_bytes())['windowsSource']==base
changed=git(S,'diff','--name-only',old,base,'--','apps/windows','packages','third_party').splitlines()
allowed={'apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json','apps/windows/src-tauri/src/backend/ble_bridge/desktop_input_stream.rs','apps/windows/src-tauri/tauri.conf.json','apps/windows/src/DesktopPointer.tsx','packages/desktop-input/src/pointer.rs','packages/desktop-input/src/pointer/remote_tests.rs','third_party/imu-pointer/gamepad/README.md'}
assert set(changed)<=allowed,changed
git(E,'fetch',str(S),author);git(E,'switch','-c','work/note132-reader-20261113',base);git(E,'restore','--source='+author,'--',*(ui+tests))
for rel,count in [('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
 p=E/rel;raw=p.read_bytes();assert raw.count(b'"version": "0.1.130"')==count;p.write_bytes(raw.replace(b'"version": "0.1.130"',b'"version": "0.1.132"'))
p=E/'apps/windows/src-tauri/Cargo.toml';raw=p.read_bytes();assert raw.count(b'version = "0.1.130"')==1;p.write_bytes(raw.replace(b'version = "0.1.130"',b'version = "0.1.132"'))
p=E/'apps/windows/src-tauri/Cargo.lock';raw,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.130(")',rb'\g<1>0.1.132\2',p.read_bytes());assert n==1;p.write_bytes(raw)
p=E/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=p.read_bytes();meta=json.loads(raw)
for rel,digest in meta['lockedInputs'].items():
 new=sha(E/rel)
 if new!=digest:assert raw.count(digest.encode())==1;raw=raw.replace(digest.encode(),new.encode())
p.write_bytes(raw)
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
git(E,'add','--',*(ui+tests+versions));git(E,'diff','--cached','--check');assert set(git(E,'diff','--cached','--name-only').splitlines())<=set(ui+tests+versions);git(E,'commit','-m','Freeze132 note reading over saved130 complete input candidate');assert not git(E,'status','--porcelain')
stable=['apps/windows/src-tauri/src/backend/transcription.rs','apps/windows/src-tauri/src/backend/transcription','apps/windows/src-tauri/src/backend/minutes.rs','apps/windows/src-tauri/src/backend/minutes','apps/windows/src-tauri/src/backend/import_audio.rs','third_party/denzic-platform'];assert not git(E,'diff',old,'HEAD','--',*stable)
H=R/'docs/handoffs/20261112-product-closure/windows132';H.mkdir(exist_ok=False)
proof=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),version='0.1.132',sourceCommit=git(E,'rev-parse','HEAD'),authoringSourceCommit=author,frozenSourceRoot=str(E),sourceRoot=str(E),branch=git(E,'branch','--show-current'),relatedAuthoringFiles=ui+tests,saved130SourcePreserved=base,saved130Receipt=str(candidate),verified130DifferencesFrom129=changed,uncommittedOtherPointerChangesIncluded=False,unchangedSinceActual129PublicAsrAndMinutes=stable,normalWindowsBuildPending=True,installed=False,ownerAccepted=False)
save(H/'frozen-source.json',proof);save(O/'windows132-frozen-source.json',proof)
apaths=[p for p in ui if 'CompanionDashboard'not in p]+['apps/mobile/src/App.tsx','apps/mobile/src/MinutesDocument.tsx','apps/mobile/src/MinutesText.tsx','apps/mobile/src/TranscriptReader.tsx','tools/test_mobile_minutes_reading.tsx','apps/android/app/build.gradle']
p=A/'apps/android/app/build.gradle';raw=p.read_bytes();assert raw.count(b'versionCode 154')==1 and raw.count(b"versionName '0.1.154'")==1;p.write_bytes(raw.replace(b'versionCode 154',b'versionCode 155').replace(b"versionName '0.1.154'",b"versionName '0.1.155'"))
git(A,'add','--',*apaths);git(A,'diff','--cached','--check','--',*apaths);git(A,'commit','--only','-m','Present clear meeting notes and reversible transcript reading on Android155','--',*apaths)
assert sha(A/'apps/android/app/libs/companion-android-backend.aar')=='39acfbedb8cb4294be0455b3faa40d0033c25cc544aa6a2ae8c964f91a999a96'
H=R/'docs/handoffs/20261110-android-media-import/android155';H.mkdir(exist_ok=False)
phone=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),versionCode=155,versionName='0.1.155',frontendSourceCommit=git(A,'rev-parse','HEAD'),frontendBranch=git(A,'branch','--show-current'),backendSourceCommit='92f53ef78a8cfd78caa60b98767dddbdf4c37583',aarSha256=sha(A/'apps/android/app/libs/companion-android-backend.aar'),nativeLibrariesRebuilt=False,nativeAarByteIdenticalToActual154=True,modelsRun=False,installed=False)
save(H/'source.json',phone);print(json.dumps(dict(windows=proof,android=phone),ensure_ascii=False))
