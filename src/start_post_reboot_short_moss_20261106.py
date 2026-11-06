from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,psutil,subprocess,sys
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=r/'docs/handoffs/20261105-model-resume';q=r/'model-research'
assert (m/'full-L-run/interruption-observed-20261106.json').exists()
for p in psutil.process_iter(['cmdline']):
    try:assert not any(Path(a).name=='moss_night_gpu_worker_20261104.py' for a in p.info['cmdline'] or []),'One model at a time'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
control=m/'post-reboot-short-20261106';control.mkdir(exist_ok=False)
prior=m/'compatibility-run'
protocol=json.loads((prior/'frozen-protocol.json').read_text(encoding='utf8'))
protocol['at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
protocol['runtime'].update(cooperativeGpuDuty=.1,durableProgressWrites=True)
protocol['scope']='Post-unexpected-system-restart exact same30s audio/model/decoding, lower cooperative active-time duty0.1 instead of0.25. Added durable progress and encoder-chunk observation only. No full-meeting inference, reference, training or automatic repeat. Compare every generated ID with the last completed pre-restart result.'
(control/'frozen-protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
(control/'audio-only.json').write_bytes((prior/'audio-only.json').read_bytes())
(control/'frozen-research-source-sha256.json').write_text(json.dumps({str(p.relative_to(q)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (q/'src').glob('*.py')},indent=2)+'\n',encoding='utf8')
argv=[sys.executable,str(q/'src/run_night_moss_gpu_20261104.py'),'--inputs',str(control/'audio-only.json'),'--run-name','post-reboot-short',
      '--protocol',str(control/'frozen-protocol.json'),'--control-root',str(control),'--output-suffix=-post-reboot-20261106']
with (control/'supervisor.log').open('xb') as stream:
    child=subprocess.Popen(argv,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'supervisorPid':child.pid,'command':argv,'hostAvailableBytes':psutil.virtual_memory().available,'automaticLongRunAfterwards':False}
(control/'launch.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))
