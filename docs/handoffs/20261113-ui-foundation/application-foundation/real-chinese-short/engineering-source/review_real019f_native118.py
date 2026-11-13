from pathlib import Path
from datetime import datetime
import json,os,hashlib,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r3')
L=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/concentrated20261113/chinese-real-short/capture/short/library')
def sha(p):
 with Path(p).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
label=sys.argv[1]if len(sys.argv)>1 else 'native-ui-r1';assert label.startswith('native-ui-r')and label[11:].isdigit()
out=O/label;out.mkdir(exist_ok=False)
proof_path=R/'docs/handoffs/20261112-product-closure/windows118/windows-verification.json';proof=json.loads(proof_path.read_bytes());asr=json.loads((O/'result.json').read_bytes())
spec=dict(statePath=str(L/'sessions.json'),stateSha256=sha(L/'sessions.json'),recordingDir=str(L/'recordings'),captureReceipt=str(L.parent.parent/'result.json'),originalAudioFiles=asr['sourceFilesBefore'])
specpath=out/'public019f-spec.json';specpath.write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf8')
env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(out/'product'),'COMPANION_ACCEPTANCE_CACHE':str(out/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(proof_path),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],'COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1','COMPANION_ACCEPTANCE_REAL_PUBLIC_SPEC':str(specpath),'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
with(out/'runner.log').open('wb')as log:run=subprocess.run(['python',str(S/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background'],cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT)
evidence=out/'product/docs/handoffs/20261109-core-acceptance'
assert evidence.exists(),(out/'runner.log').read_text(encoding='utf8',errors='replace')[-2500:]
cases=list(evidence.iterdir());assert len(cases)==1
detail=json.loads((cases[0]/'result.json').read_bytes())
for name,digest in spec['originalAudioFiles'].items():assert sha(L/'recordings'/name)==digest
assert sha(L/'sessions.json')==spec['stateSha256']
result=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),exitCode=run.returncode,nativeEvidence=str(cases[0]/'result.json'),nativeState=detail['state'],sourceLibraryAndAllFourOriginalAudioFilesUnchanged=True,actualGuiResults=detail.get('ui'),actualProcessRestart=detail.get('processRestart'),audibilityIssueClosed=False,ownerExperienceAccepted=False)
(out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
assert run.returncode==0,(out/'runner.log').read_text(encoding='utf8',errors='replace')[-2500:]
assert detail['ui']['actualPhysicalAudioResultsRead'] and detail['processRestart']['previousAppExited']
