"""Refresh the existing workpoint from live run evidence, without launching any work."""
from pathlib import Path
from datetime import datetime
import json,psutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];E=Path(o['currentStagedRun']);run=read(E/'run.json')
prior=o.get('dayEvidenceMilestone');meeting=run.get('activeMeeting');pid=run.get('pid');live=False
if pid:
 try:live=abs(psutil.Process(pid).create_time()-run['pidCreatedAt'])<.05
 except psutil.NoSuchProcess:pass
control=E/'runtime-control61-decode-state.json'
control_pass=control.exists() and read(control)['state']=='PASS_BIT_EXACT_STAGED_NATIVE16_TOKEN_CONTROL'
finished=[x for x in run['completed'] if x!='runtime-control61']
milestone=(run['state'],meeting,tuple(finished),control_pass,bool(run.get('finishedAt')))
state='DAY_NATIVE_COMPLETE_MEETING_COMPARISON_RUNNING' if not run.get('finishedAt') else (
 'DAY_NATIVE_COMPLETE_MEETING_COMPARISON_FINISHED_REVIEW_PENDING' if run['state'].startswith('COMPLETE_FOUR_') else 'DAY_NATIVE_FAILURE_OR_DEADLINE_RETAINED')
d['state']=state;o.update(currentState=state,runState=str(E/'run.json'),activeMeeting=meeting if live else None,
 activePid=pid if live else None,activePidCreatedAt=run.get('pidCreatedAt') if live else None,noOwnNeuralProcessActive=not live,
 dayRunStartedAt=run['startedAt'],dayRuntimeControlPassed=control_pass,dayWholeMeetingsCompleted=finished,
 dayEvidenceMilestone=list(milestone),latestObservedAt=datetime.now().astimezone().isoformat(),privatePeakBytes=run['privatePeakBytes'])
if meeting:
 for phase in ['decode','prefill']:
  f=E/(meeting+'-'+phase+'-state.json')
  if f.exists():o['latestPhaseEvidence']=read(f);break
receipt=D/('protection-r31.json' if (D/'protection-r31.json').exists() else 'protection-r30.json')
source=read(receipt);assert source['remoteVerified']
d['sourceProtection'].update(dayResumeSourceCommit=source['modelCommit'],dayResumeSourceRemoteVerified=True,dayResumeSourceReceipt=str(receipt))
d['jointArchitecture20261115']['state']=state
if json.dumps(prior)!=json.dumps(list(milestone)):
 d['logResult']+='\n'+datetime.now().astimezone().isoformat()+' 下午16:00续作实际点：'+run['state']+' / '+str(meeting)+'，当前受核验自有PID='+str(pid if live else None)+'，原61s16token控制='+str(control_pass)+'，完整会已完成='+str(finished)+'，私有峰='+str(run['privatePeakBytes'])+'。源码'+source['modelCommit']+'已私有独立回读保护；未完成不记质量通过。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
subprocess.run([sys.executable,'work/record_bilingual_progress.py',str(p)],check=True)
print(json.dumps({'state':state,'meeting':meeting,'livePid':pid if live else None,'nativeControlPassed':control_pass,'completed':finished},ensure_ascii=False))
