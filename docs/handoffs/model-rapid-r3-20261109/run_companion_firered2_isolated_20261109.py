"""One allocator-isolation test; retain completed audio and stop at any new failure."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-firered2-cpu-r1';O=C/'isolated8s-r3';O.mkdir(exist_ok=False);read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
I=read(C/'small8s-r2/probe-audio-only.json');old=read(C/'small8s-r2/probe/state.json');assert old['newNeuralCalls']==1 and len(old['results'])==1;prior=Path(old['results'][0]['file']);assert sha(prior)==old['results'][0]['sha256'];raw=read(prior);assert raw['id']==I[0]['id'] and raw['sourceAudioSha256']==I[0]['audioSha256']
write(O/'protocol.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'whyDifferent':'First8sclip succeeded, secondfailed during nativeConcat allocation in same recognizer. Exactly one discriminating test: fresh process for failedsecondclip, sameweights/runtime/threads/input. If it succeeds continue otherfixed8s clips, each in separate process; no repeated firstclip or cut/threshold tuning. Stop batch on firstfailure.','previousSuccessfulRawFile':str(prior),'previousSuccessfulRawSha256':sha(prior),'allocatorResetNotModelChange':True,'privateBudgetBytes':2147483648,'inferenceParametersChanged':False,'saleQualified':False})
state={'state':'RUNNING_FRESH_PROCESS_PER_CLIP','startedAt':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'rows':[{'id':I[0]['id'],'state':'INHERITED_SUCCESS','file':str(prior),'sha256':sha(prior),'seconds':raw['seconds']}],'newNeuralCalls':0};start=time.perf_counter();write(O/'run.json',state)
for index,packet in enumerate(I[1:],1):
 folder=O/('%02d'%index);folder.mkdir()
 for name in ['model-ready.json','run-protocol.json','full-audio-only.json']:shutil.copyfile(C/name,folder/name)
 write(folder/'probe-audio-only.json',[packet]);tick=time.perf_counter();result=subprocess.run([sys.executable,str(Path(__file__).with_name('run_companion_firered2_cpu_20261109.py')),'probe','--control',str(folder)],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);(folder/'controller-output.txt').write_text(result.stdout+result.stderr,encoding='utf8');controller=read(folder/'probe-controller.json') if (folder/'probe-controller.json').exists() else {};worker=read(folder/'probe/state.json') if (folder/'probe/state.json').exists() else {};row={'id':packet['id'],'state':controller.get('state','FAILED'),'controller':controller,'wallSeconds':time.perf_counter()-tick}
 if controller.get('state')=='COMPLETE' and len(worker.get('results',[]))==1:row.update(file=worker['results'][0]['file'],sha256=worker['results'][0]['sha256']);state['newNeuralCalls']+=worker['newNeuralCalls']
 state['rows'].append(row);state['wallSeconds']=time.perf_counter()-start
 if row['state']!='COMPLETE':state['state']='STOPPED_NEW_FAILURE_NO_RETRY';write(O/'run.json',state);print(json.dumps(row,ensure_ascii=False),flush=True);break
 write(O/'run.json',state);print(json.dumps(row,ensure_ascii=False),flush=True)
else:state['state']='COMPLETE_SIX_FIXED_CLIPS_WITH_ONE_INHERITED';write(O/'run.json',state)
print(json.dumps({'state':state['state'],'completedRows':len(state['rows']),'newNeuralCalls':state['newNeuralCalls'],'wallSeconds':state.get('wallSeconds')},ensure_ascii=False),flush=True)
