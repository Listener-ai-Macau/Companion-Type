from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');P=O/'public-source-full30-127';N=O/'note-readability-public-native129';Q=O/'visual-meeting-native148';Q.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
proof_path=R/'docs/handoffs/20261112-product-closure/windows148/windows-verification.json';proof=json.loads(proof_path.read_bytes());row=json.loads((N/'minutes.json').read_bytes());assert '\n## 会议概览\n'in row['minutesByMode']['offlineStore']['markdown']
active=json.loads((P/'active-public-library.json').read_bytes());manifest=json.loads(Path(active['nativeImportManifest']).read_bytes());focused=Q/'one-actual-public-session.json';save(focused,[row]);upstream=N/'sessions.json';before=sha(upstream)
originals={Path(name).name:sha(name)for name in [manifest['originalPath'],manifest['decodedPath']]}
spec=dict(statePath=str(focused),stateSha256=sha(focused),sourceKind='importedAudio',recordingKey=None,recordingDir=active['recordingDir'],originalAudioFiles=originals,sessionId=row['id'],audioDurationMs=manifest['durationMs'],nativeImportEvidence=active['nativeImportEvidence'],nativeImportManifest=active['nativeImportManifest'],upstreamStatePath=active['statePath'],nativeRegenerationReceipt=str(N/'result.json'),expectLibraryScopeAndSelection=False,expectNotebookPolish=False,expectVisualMeeting=True,expectClearReading=True,expectCompleteTitle=True,expectedVisualTopics=[line[2:]for line in row['minutesByMode']['offlineStore']['markdown'].split('## 会议概览\n',1)[1].split('# 公开中文会议',1)[0].splitlines()if line.startswith('- ')],expectFoldedOverview=True,overviewHeading='会议概览',expectReadableTranscript=True,expectedMinutesTerms=['会议概览','果蔬','蛋糕','奶制品'],expectedTranscriptTerms=['超市'],expectedExportTerms=['超市','三个月'])
save(Q/'spec.json',spec)
env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(Q/'product'),'COMPANION_ACCEPTANCE_CACHE':str(Q/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(proof_path),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],'COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1','COMPANION_ACCEPTANCE_REAL_PUBLIC_SPEC':str(Q/'spec.json'),'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
with(Q/'runner.log').open('xb')as log:run=subprocess.run([sys.executable,str(S/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background'],cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
assert run.returncode==0,(Q/'runner.log').read_text(errors='replace')[-2500:]
cases=list((Q/'product/docs/handoffs/20261109-core-acceptance').iterdir());assert len(cases)==1;evidence=cases[0]/'result.json';detail=json.loads(evidence.read_bytes());assert detail['ui']['actualReadableAndCompleteOriginalTranscriptSwitchChecked'] and detail['processRestart']['previousAppExited'] and detail['ui']['actualPublicImportedAudioResultsRead']
assert sha(upstream)==before
for name,digest in originals.items():assert sha(Path(active['recordingDir'])/name)==digest
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ACTUAL148_PUBLIC_NOTE_HIERARCHY_TRANSCRIPT_SWITCH_EXPORT_AND_PROCESS_REOPEN_PASSED',evidence=str(evidence),sourceStateAndAudioUnchanged=True,modelsOrCloudRerun=False,ownerAccepted=False,saleQualified=False)
save(Q/'result.json',record);print(json.dumps(record,ensure_ascii=False))
