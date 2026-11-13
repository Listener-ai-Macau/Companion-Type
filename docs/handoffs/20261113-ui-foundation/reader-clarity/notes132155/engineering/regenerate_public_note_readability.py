from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');P=O/'public-source-full30-127';Q=O/'note-readability-public-native129';Q.mkdir(exist_ok=False)
gate=json.loads((P/'text-reviewed-before-cloud.json').read_bytes());assert gate['allTextRead'] and gate['publicOnly']
row=json.loads((P/'minutes.json').read_bytes());assert hashlib.sha256(row['transcriptText'].encode()).hexdigest()==gate['transcriptSha256']
active=json.loads((P/'active-public-library.json').read_bytes());state=Q/'sessions.json';state.write_text(json.dumps([row],ensure_ascii=False),encoding='utf8')
proof=json.loads((R/'docs/handoffs/20261112-product-closure/windows129/windows-verification.json').read_bytes());exe=Path(proof['nativeRoot'])/'companion-type.exe';assert hashlib.sha256(exe.read_bytes()).hexdigest()==proof['embeddedExeSha256']
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2)
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(state),'COMPANION_TYPE_RECORDING_DIR':str(Q/'recordings'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1'}
for key in ['COMPANION_TYPE_PRODUCT_SETTINGS_PATH','COMPANION_TYPE_MINUTES_COMMAND']:env.pop(key,None)
request=Q/'request.json';request.write_text(json.dumps(dict(action='meetingGenerateMinutes',sessionId=row['id'],meetingMode='offlineStore',minutesTemplate=dict(id='meeting'))),encoding='utf8')
before=Path(active['statePath']).read_bytes();start=time.monotonic()
with(Q/'native.log').open('xb')as log:run=subprocess.run([str(exe),'--meeting-minutes-request',str(request),str(Q/'minutes.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
assert run.returncode==0,'Native regeneration failed; retained log'
new=json.loads((Q/'minutes.json').read_bytes());minutes=new['minutesByMode']['offlineStore'];assert new['transcriptText']==row['transcriptText'] and minutes['quality']=='final' and minutes['processing']['complete']
assert Path(active['statePath']).read_bytes()==before
(Q/'actual-minutes.md').write_text(minutes['markdown'],encoding='utf8')
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='PUBLIC_NATIVE129_NOTES_REGENERATED_CONTENT_REVIEW_PENDING',engineVersion='0.1.129',seconds=round(time.monotonic()-start,3),sourceTextSha256=gate['transcriptSha256'],publicOnly=True,cloudTextOnly=True,cloudAudio=False,previousStateUntouched=True,originalTranscriptUnchanged=True,conciseOverviewGenerated=minutes['markdown'].startswith('## 会议概览\n'),newNativeBuild=False,ownerAccepted=False)
(Q/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(record,ensure_ascii=False))
