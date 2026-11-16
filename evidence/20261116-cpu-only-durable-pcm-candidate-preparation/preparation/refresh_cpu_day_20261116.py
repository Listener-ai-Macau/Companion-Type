from pathlib import Path
from datetime import datetime
import json,psutil
p=Path('work/bilingual_progress.json');d=json.loads(p.read_text(encoding='utf-8'));o=d['ownerOvernightRun20261115'];E=Path(o['currentCpuWholeRun']);C=Path(o['currentCpuWholeControl'])
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
run=read(E/'run.json');state=read(E/'inference-state.json');B=read(C/'binding.json');completed={r['id']:r for r in state['completed']}
live=False
try:proc=psutil.Process(run['pid']);live=abs(proc.create_time()-run['pidCreatedAt'])<.1
except (psutil.Error,KeyError):pass
counts=[{'meeting':r['meeting'],'completedInputs':sum(c['id'] in completed for c in B['cases'] if c['meeting']==r['meeting']),
 'totalInputs':sum(c['meeting']==r['meeting'] for c in B['cases'])} for r in B['meetings']]
phase='DAY_CPU_FIXED_FULL4_RUNNING' if live else ('DAY_CPU_FIXED_FULL4_ASR_COMPLETE_SCORING_PENDING' if len(completed)==len(B['cases']) else 'DAY_CPU_FIXED_FULL4_RESOURCE_STOP_RETAINED')
o.update(currentState=phase,activePid=run.get('pid') if live else None,activePidCreatedAt=run.get('pidCreatedAt') if live else None,
 noOwnNeuralProcessActive=not live,latestObservedAt=datetime.now().astimezone().isoformat(),currentExecutionDevice='cpu',
 cpuWholeProgress={'run':str(E),'state':state['state'],'completedInputs':len(completed),'totalInputs':len(B['cases']),
 'completedSourceSeconds':sum(r['audioSeconds'] for r in completed.values()),'meetings':counts,'incompleteOutputCases':state['incompleteOutputCases'],
 'currentPrivatePeakBytes':run['privatePeakBytes'],'currentFamilyWorkingSetPeakBytes':run['familyWorkingSetPeakBytes'],
 'currentSystemAvailableMinBytes':run['systemAvailableMinBytes'],'systemAvailableBytesAtObservation':psutil.virtual_memory().available})
d['state']=phase
D=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution')
receipts=sorted(D.glob('protection-r*.json'),key=lambda x:int(x.stem.removeprefix('protection-r')))
verified=[(file,read(file)) for file in receipts if read(file).get('remoteVerified')]
receipt,proof=verified[-1];d['sourceProtection'].update(dayResumeSourceCommit=proof['modelCommit'],dayResumeSourceRemoteVerified=True,dayResumeSourceReceipt=str(receipt))
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':phase,'active':live,'completed':len(completed),'total':len(B['cases']),'meetings':counts,'protected':proof['modelCommit']},ensure_ascii=False))
