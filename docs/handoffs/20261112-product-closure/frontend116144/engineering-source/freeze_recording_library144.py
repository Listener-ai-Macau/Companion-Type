from pathlib import Path
from datetime import datetime
import json,os,shutil,subprocess

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';B=R/'docs/handoffs/20261112-product-closure/android144';B.mkdir(exist_ok=False)
paths=['apps/mobile/src/AudioImport.tsx','apps/mobile/src/recordingLibrary.css','apps/android/app/build.gradle','tools/test_mobile_audio_import.tsx','tools/check_android_delivery_source.cjs']
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='MOBILE144_SAME_COHERENT_BATCH_ACTUAL143_REVIEW_FOUND_HISTORICAL_CANCEL_NOISE_FIXED',version='0.1.144',priorInstalled='0.1.143',sameBatch='recording-library116144',prior143Source='7bad2b57fdbb6e0728af626e3ea0ae89fedb1e6f',reason='Actual143 phone screenshot still showed an old cancelled import as a persistent red failure in the compact library. Suppress historical completed/cancelled messages; keep current cancellation neutral and actual failures actionable. No Owner technical round or separate143 final kit was delivered.',productAndCheckFiles=paths,nativeBackendChanged=False,sourceAffectedImportContractsPassed=True,priorSourceWholeLibraryReview='mobile143-source-r5',priorActual143Review=str(B.parent/'android143'),actual144PhoneReviewPending=True)
(B/'source-review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
target=S/'docs/handoffs/20261112-product-closure/android144/source-review.json';target.parent.mkdir(parents=True);shutil.copyfile(B/'source-review.json',target)
paths.append(str(target.relative_to(S)))
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
for args in [['add','--',*paths],['diff','--cached','--check','--',*paths],['commit','--only','-m','Keep historical import cancellation out of ordinary mobile recording library','--',*paths]]:subprocess.run(git+args,cwd=S,check=True)
assert not subprocess.check_output(git+['status','--porcelain'],cwd=S,text=True).strip()
record['sourceCommit']=subprocess.check_output(git+['rev-parse','HEAD'],cwd=S,text=True).strip();(B/'frozen-source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
subprocess.run(git+['push','origin','HEAD'],cwd=S,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
print(json.dumps(record,ensure_ascii=False))
