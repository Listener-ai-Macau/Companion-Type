from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,psutil,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=argparse.ArgumentParser();p.add_argument('--previous',type=int,default=1);p.add_argument('--next',type=int,default=2);a=p.parse_args();assert a.next==a.previous+1
old=BASE/('cpu-fixed-whole-r'+str(a.previous));source=E/old.name;C=BASE/('cpu-fixed-whole-r'+str(a.next));run=E/C.name;assert not C.exists() and not run.exists()
closed=read(source/'run.json');state=read(source/'inference-state.json');assert closed['finishedAt'] and state['state']=='INCOMPLETE_CPU_FIXED_CHUNKS_RETAINED' and len(state['completed'])>0
pressure=SystemRamPressure();available=psutil.virtual_memory().available
try:assert not pressure.low() and available>=int(3.18*1024**3)
finally:pressure.close()
B=read(old/'binding.json');B.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(S/'cpu_fixed_chunks_worker_20261116.py'),runnerSha256=sha(S/'run_cpu_fixed_chunks_20261116.py'),
 resumeCompleted=state['completed'],resumeSource={'state':str(source/'inference-state.json'),'stateSha256':sha(source/'inference-state.json'),'priorRun':str(source/'run.json'),'priorRunSha256':sha(source/'run.json'),
 'reason':'Actual Windows low-memory signal; complete inputs retained without rerun, interrupted input resumes from its unchanged start. No model failure or memory-cap increase.',
 'observedPriorAvailableMinimumBytes':closed['systemAvailableMinBytes'],'availableAtPreparationBytes':available},minimumAvailableBeforeLoadBytes=int(3.18*1024**3))
for item in B['resumeCompleted']:assert sha(item['file'])==item['sha256']
C.mkdir()
for name in ['scoring-binding.json','predicted-speaker-bindings.json','whole-scoring-only.json','composition-source-binding.json']:(C/name).write_bytes((old/name).read_bytes())
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];d['state']='DAY_CPU_FIXED_FULL4_RESOURCE_RECOVERED_RESUME'+str(len(state['completed']))
o.update(currentState=d['state'],currentCpuWholeControl=str(C),currentCpuWholeRun=str(run),activePid=None,noOwnNeuralProcessActive=True,
 cpuWholeResourceStop={'closedRun':str(source/'run.json'),'completedInputs':len(state['completed']),'sourceSecondsCompleted':sum(r['audioSeconds'] for r in state['completed']),'actualLowRamStop':True,'privateLimitNotReached':True,'recoveryAvailableBytes':available})
d['logResult']+='\n'+B['at']+' 固定全会'+old.name+'实际Windows低RAM保护自停，保留'+str(len(state['completed']))+'个完整输入；闭合运行证据='+str(source/'run.json')+'，私有峰='+str(closed['privatePeakBytes'])+'。释放自有模型后可用回升至'+str(available)+'bytes且Windows通知正常，达到原约3.18GiB恢复条件；'+C.name+'仅续未完成输入，逐文件SHA核原完整结果不重算。中断partial证据落盘；25%/4线程、2GiB/真实低RAM保护与模型/所有原输入/评分不改。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'control':str(C),'run':str(run),'retainedCompleteInputs':len(state['completed']),'availableBytes':available}))
