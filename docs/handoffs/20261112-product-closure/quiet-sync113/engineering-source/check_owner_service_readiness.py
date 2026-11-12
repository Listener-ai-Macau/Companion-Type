"""Read only redacted native service readiness with an empty private library."""
from pathlib import Path
from datetime import datetime
import os,json,subprocess,hashlib,sys
number=int(sys.argv[1])if len(sys.argv)>1 else 112;assert 112<=number<200;version='0.1.'+str(number)
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261112-product-closure'/('windows'+str(number));O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112')/('windows'+str(number))/'self-acceptance-service-readiness';O.mkdir(exist_ok=False)
proof=json.loads((B/'windows-verification.json').read_bytes());exe=Path('C:/Program Files/Companion Type/companion-type.exe');assert hashlib.sha256(exe.read_bytes()).hexdigest()==proof['embeddedExeSha256']
(O/'sessions.json').write_text('[]',encoding='utf8');(O/'request.json').write_text('{}',encoding='utf8')
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(O/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(O/'recordings'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1'}
env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
run=subprocess.run([str(exe),'--local-recording-snapshot',str(O/'request.json'),str(O/'native-redacted-result.json')],env=env,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
(O/'stdout.log').write_bytes(run.stdout);(O/'stderr.log').write_bytes(run.stderr);assert run.returncode==0
data=json.loads((O/'native-redacted-result.json').read_bytes());assert data['deviceAccess'] is False and data['transcriptionRequested'] is False
settings=data['settings'];keep=['asrProvider','localAsrAvailable','deepseekApiKeySet','deepseekMinutesEnabled','openaiAsrApiKeySet','volcAppKeySet','volcAccessKeySet','storageSaveBlocked','storageWarning']
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='INSTALLED'+str(number)+'_REDACTED_NATIVE_SERVICE_READINESS_READ',version=version,settings={key:settings.get(key) for key in keep},originalOwnerLibraryRead=False,privateAudioRead=False,modelsStarted=False,boardAccessed=False,cloudCalled=False,serviceKeysPrinted=False,scope='Normal product settings read with an isolated empty session library. Presence flags are not successful live inference or service quality evidence.')
(O/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
