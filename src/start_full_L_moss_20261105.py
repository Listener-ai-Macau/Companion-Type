"""Launch one frozen whole real development meeting after a completed smoke."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,psutil,subprocess,sys

r=Path('C:/Users/Billy/Desktop/Denzic/Companion')
m=r/'docs/handoffs/20261105-model-resume'
q=r/'model-research'
k=m/'compatibility-run'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
smoke=read(k/'native-speech-compatibility-r2.json')
assert smoke['state']=='COMPLETE_GPU_INFERENCE_SCORING_REQUIRED'
short=read(smoke['results'][0]['receipt'])
assert short['eosCompleted'] and short['allGeneratedTextParsed'] and not short['invalidNativeTimeRows']
assert short['firstProjectionTokenCount']==short['maximumProjectionTokenCount']==1
assert smoke['results'][0]['observedProcessFamilyPeakPrivateBytes']<2*1024**3
for process in psutil.process_iter(['pid','name','cmdline']):
    try:
        command=process.info['cmdline'] or []
        assert not any(Path(arg).name=='moss_night_gpu_worker_20261104.py' for arg in command), 'One speech model at a time'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
sys.path.insert(0,str(q/'src'))
from moss_windows_resource_limits_20261104 import SystemRamPressure
pressure=SystemRamPressure()
try:assert not pressure.low(),'Windows reports actual low system memory; do not launch'
finally:pressure.close()
control=m/'full-L-run';control.mkdir(exist_ok=False)
original=read(m/'public-audio-restore-r5.json')
case=next(c for c in original['cases'] if c['meeting']=='L_R003S01C02')
for path_key,sha_key in [('audio','audioSha256'),('reference','referenceSha256')]:
    with Path(case[path_key]).open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()==case[sha_key]
audio={key:case[key] for key in ['meeting','audio','audioSha256','audioSeconds']}
scoring={**case,'corpus':'AISHELL-4','referenceKind':'textgrid_lexical'}
protocol=read(k/'frozen-protocol.json')
protocol['at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
protocol['scope']='One complete real 2362.945-second development meeting. Exact original audio/reference hashes, published model/source pins, unchanged complete context/prompt. Reference retained in scoring-only manifest, not passed to inference. Reconstructed environment and explicit bounded temporary attention tiles query128/key256, CPU5%, private commit2GiB, GPU IDLE/cooperative duty0.25. No parameter tuning, no qualification or heldout claim.'
for filename,value in [('frozen-protocol.json',protocol),('audio-only.json',[audio]),('frozen-scoring-only.json',[scoring])]:
    (control/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
source_hashes={str(path.relative_to(q)):hashlib.sha256(path.read_bytes()).hexdigest() for path in (q/'src').glob('*.py')}
(control/'frozen-research-source-sha256.json').write_text(json.dumps(source_hashes,indent=2)+'\n',encoding='utf8')
argv=[sys.executable,str(q/'src/run_night_moss_gpu_20261104.py'),'--inputs',str(control/'audio-only.json'),
      '--run-name','full-L-native-20261105','--protocol',str(control/'frozen-protocol.json'),
      '--control-root',str(control),'--output-suffix=-20261105-r16']
with (control/'supervisor.log').open('xb') as log:
    child=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,cwd=str(q),
        creationflags=subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
receipt={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'ONE_FULL_MEETING_SUPERVISOR_LAUNCHED',
         'pid':child.pid,'command':argv,'hostAvailableMemoryBytes':psutil.virtual_memory().available,
         'smokeCompletedReceipt':str(k/'native-speech-compatibility-r2.json'),'conditionsChangedFromHistoricalR15':['Restored Python/transitive dependency environment explicitly frozen','Bounded attention key tile256 instead of historical1024; all keys retained'],
         'noAutomaticRetry':True,'referencePassedToWorker':False,'heldoutOpened':False}
(control/'launch.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(receipt,ensure_ascii=False))
