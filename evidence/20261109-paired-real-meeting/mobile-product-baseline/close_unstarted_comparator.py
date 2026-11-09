from pathlib import Path
from datetime import datetime
import copy,json,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
remote='/data/user/0/com.denzic.companion.app/cache/paired-asr-20261109-r1'
def adb(args):
    q=subprocess.run([str(A),'-s','d6bd213d',*args],capture_output=True)
    assert q.returncode==0,(q.stdout+q.stderr).decode(errors='replace')
    return q.stdout.decode(errors='replace')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PHONE_COMPARATOR_NOT_STARTED_INVENTORY_CLAIM_INVALIDATED','invalidates':'prepared.json','cause':'app_process returned zero with empty stdout and no state.json; not evidence of Java/API/model startup','instrumentationFallback':'INSTALL_FAILED_USER_RESTRICTED: Install canceled by user','instrumentationFallbackInstalled':False,'neuralCalls':0,'modelQualityMeasured':False,'productApkChanged':False,'mainDisplayUsed':False,'originalLibraryAccessed':False,'noFurtherInstallRetry':True}
adb(['shell','run-as','com.denzic.companion.app','rm','-f',remote+'/public-first30s.wav',remote+'/audio-only.json'])
adb(['shell','run-as','com.denzic.companion.app','rmdir',remote])
adb(['shell','rm','-f','/data/local/tmp/companion-paired-asr-20261109.jar'])
record['ownPublicStagingRemoved']=True
(C/'closed-unstarted.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
backlog=R/'docs/product_backlog.json';d=json.loads(backlog.read_text(encoding='utf8'));targets=copy.deepcopy(d['quality_targets'])
hold=d['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold']
assert hold['active'] and hold['reservedFor']=='Companion paired-source model baseline on installed phone JNI'
hold.update(active=False,releasedAt=record['at'],releaseReason='Paired phone JNI comparator did not start; isolated public staging removed. No foreground, BLE, original-library or product APK operation.')
assert d['quality_targets']==targets
backlog.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
