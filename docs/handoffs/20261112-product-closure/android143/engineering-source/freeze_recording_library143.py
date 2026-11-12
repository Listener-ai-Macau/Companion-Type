from pathlib import Path
from datetime import datetime
import json,os,shutil,subprocess

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';B=R/'docs/handoffs/20261112-product-closure/android143';B.mkdir(exist_ok=False);W=Path(__file__).parent
review=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/mobile143-source-r5/result.json');assert json.loads(review.read_bytes())['state']=='MOBILE_SOURCE_LIBRARY_NAMES_DATES_THEME_WIDTH_AND_OPEN_PASSED'
paths=['apps/mobile/src/App.tsx','apps/mobile/src/recordingLibrary.css','apps/mobile/src/RecordingLibraryManager.tsx','apps/android/app/build.gradle']
configuration=S/paths[-1];raw=configuration.read_bytes();assert raw.count(b'versionCode 142')==1 and raw.count(b"versionName '0.1.142'")==1;configuration.write_bytes(raw.replace(b'versionCode 142',b'versionCode 143').replace(b"versionName '0.1.142'",b"versionName '0.1.143'"))
proof=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='MOBILE_RECORDING_LIBRARY143_SOURCE_REVIEWED_NORMAL_BUILD_PENDING',version='0.1.143',priorInstalled='0.1.142',productFilesChanged=paths,sourceBrowserEvidence=str(review),nativeBackendChanged=False,savedOwnerDataChanged=False,actualPhoneReviewed=False,ownerExperienceAccepted=False,retainedPreparationFailures='Old synthetic bridge lacked current incomingFiles/audioImportStatus/libraryStatus/appPreferences/aiServiceStatus contracts; r1-r3 correctly failed, then current contract fixture was completed. r4 passed; final filter/player refinements passed r5. One web wrapper used cmd incorrectly and failed before compile; direct node tsc/vite completed. No failed package installed.')
(B/'source-review.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for name in ['refine_mobile_recording_library143.py','check_mobile_recording143.cjs','freeze_recording_library143.py']:
    target=B/'engineering-source'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(W/name,target)
for file in B.rglob('*'):
    if file.is_file():
        target=S/'docs/handoffs/20261112-product-closure/android143'/file.relative_to(B);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
paths+=['docs/handoffs/20261112-product-closure/android143']
for args in [['add','--',*paths],['diff','--cached','--check','--',*paths],['commit','--only','-m','Clarify mobile recording library and open unprocessed audio in transcript view','--',*paths]]:subprocess.run(git+args,cwd=S,check=True)
assert not subprocess.check_output(git+['status','--porcelain'],cwd=S,text=True).strip()
proof['sourceCommit']=subprocess.check_output(git+['rev-parse','HEAD'],cwd=S,text=True).strip();(B/'frozen-source.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
subprocess.run(git+['push','origin','HEAD'],cwd=S,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
print(json.dumps(proof,ensure_ascii=False))
