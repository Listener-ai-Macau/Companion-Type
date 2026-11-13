from pathlib import Path
from datetime import datetime
import json,os,hashlib,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/reader-clarity20261113');L=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/concentrated20261113/chinese-real-short/capture/short/library');prior=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r3/result.json')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
out=O/'real-public019f-native';out.mkdir(exist_ok=False);proofpath=R/'docs/handoffs/20261112-product-closure/windows120/windows-verification.json';proof=json.loads(proofpath.read_bytes());asr=json.loads(prior.read_bytes())
spec=dict(statePath=str(L/'sessions.json'),stateSha256=sha(L/'sessions.json'),recordingDir=str(L/'recordings'),captureReceipt=str(L.parent.parent/'result.json'),originalAudioFiles=asr['sourceFilesBefore']);specpath=out/'public019f-spec.json';specpath.write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf8')
env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(out/'product'),'COMPANION_ACCEPTANCE_CACHE':str(out/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(proofpath),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],'COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1','COMPANION_ACCEPTANCE_REAL_PUBLIC_SPEC':str(specpath),'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
with(out/'runner.log').open('wb')as log:run=subprocess.run(['python',str(S/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background'],cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT)
for name,digest in spec['originalAudioFiles'].items():assert sha(L/'recordings'/name)==digest
assert sha(L/'sessions.json')==spec['stateSha256']
assert run.returncode==0,(out/'runner.log').read_text(encoding='utf8',errors='replace')[-2600:]
cases=list((out/'product/docs/handoffs/20261109-core-acceptance').iterdir());assert len(cases)==1;detail=json.loads((cases[0]/'result.json').read_bytes());assert detail['ui']['actualPhysicalAudioResultsRead']and detail['processRestart']['previousAppExited']
result=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='EXACT120_NATIVE_SAVED_REAL_PUBLIC019F_READING_REPLAY_SELECTED_EXPORT_AND_PROCESS_REOPEN_PASSED',version='0.1.120',sourceCommit=proof['sourceCommit'],nativeEvidence=str(cases[0]/'result.json'),sourceLibraryAndAllFourOriginalAudioFilesUnchanged=True,newAsrMinutesOrBoardRequested=False,ownerExperienceAccepted=False)
(out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
