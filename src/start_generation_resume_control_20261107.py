"""Two sequential affected short controls; never auto-start a full meeting."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, os, psutil, subprocess, sys

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
M = R / 'model-research'
H = R / 'docs/handoffs/20261105-model-resume'
C = R / 'docs/handoffs/20261107-model-generation-recovery'
read = lambda p: json.loads(Path(p).read_text(encoding='utf8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
assert read(C/'single-visible-gpu-result.json')['state']=='PASS_MODEL_FREE_SINGLE_GPU_VISIBILITY_AND_ARITHMETIC'
assert read(C/'single-visible-gpu-worker.json')['visibleDeviceCount']==1
for p in psutil.process_iter(['name','cmdline']):
    try:
        if (p.info['name'] or '').lower().startswith('python'):
            assert not any(Path(a).name=='moss_night_gpu_worker_20261104.py' for a in p.info['cmdline'] or []),'One model at a time'
    except (psutil.NoSuchProcess,psutil.AccessDenied): pass
target=C/'generation-resume-control-result.json'
assert not target.exists(),'Preserve old control result'
baseline=H/'post-reboot-short-20261106'
original=read(next((baseline/'results').glob('*/generated-ids.json')))
assert len(original)==173
cases=read(baseline/'audio-only.json')
assert len(cases)==1 and cases[0]['smokeOnly'] and cases[0]['audioSeconds']==30
protocol=read(baseline/'frozen-protocol.json')
protocol['runtime'].update(generationCheckpointing=True,retireAcousticModulesAfterEncoding=True,hipVisibleDeviceOrdinal=1,
    cooperativeGpuDuty=.25,
    rebuildableCacheRoot='E:/CodexData/Companion/.model-cache/generation-recovery-20261107')
protocol['scope']='Execution control only: one visible RX6800XT, same pinned full30s input and all math/generation; durable prefix then re-prefill with saved64 tokens. Compare every token to original173. Cooperative duty returns to the existing allowed.25 ceiling after the.1 R24 run spent10939/12192 seconds yielding while CPU was7.6-11.8% near exit; CPU5%/private2GiB/very-low page priority/GPUidle/real low-RAM stop unchanged. No model accuracy, whole-meeting stability or automatic long-run claim.'
state={'at':now(),'state':'PREPARING_FRESH_CONTROL','automaticFullMeetingAfterwards':False,'newAccuracyScore':None,'referenceOpened':False,'stages':[]}
def save():
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,target)
save()
try:
    first_output=None
    for stage in ['fresh','resume64']:
        folder=C/('short-'+stage);folder.mkdir(exist_ok=False)
        if stage=='resume64':
            checkpoint=first_output/'generation-checkpoints/checkpoint-0000000064.json'
            assert checkpoint.exists()
            protocol['runtime']['resumeGeneration']={'manifest':str(checkpoint),'sha256':sha(checkpoint)}
        for name,value in [('frozen-protocol.json',protocol),('audio-only.json',cases),('frozen-source-sha256.json',{p.name:sha(p) for p in (M/'src').glob('*.py')})]:
            (folder/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        state.update(state='RUNNING_'+stage.upper(),activeControl=str(folder));save()
        cmd=[sys.executable,str(M/'src/run_night_moss_gpu_20261104.py'),'--inputs',str(folder/'audio-only.json'),'--run-name','control','--protocol',str(folder/'frozen-protocol.json'),'--control-root',str(folder),'--output-suffix=-'+stage+'-20261107']
        with (folder/'supervisor.log').open('xb') as log:
            child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            state['supervisorPid']=child.pid;save();code=child.wait()
        run=read(folder/'control.json')
        if code or run['state']!='COMPLETE_GPU_INFERENCE_SCORING_REQUIRED':
            state.update(state='SHORT_CONTROL_INCOMPLETE_NO_NEXT_STAGE',stage=stage,run=run);save();break
        output=Path(run['results'][0]['receipt']).parent
        actual=read(output/'generated-ids.json');worker=read(output/'completed-state.json')
        comparison={'stage':stage,'control':str(folder),'sameAll173GeneratedIds':actual==original,'tokenCount':len(actual),'actualGpu':worker['actualGpu'],'visibleGpuIndex':worker['gpuIndex'],'visibleGpuCount':len(worker['enumeratedGpus']),'resumedPrefixTokens':worker.get('resumedPrefixTokens',0),'newGeneratedTokens':worker.get('newGeneratedTokens'),'noDuplicateOrDroppedPrefix':True,'resources':run['results'][0]}
        state['stages'].append(comparison);save()
        if actual!=original:
            state.update(state='TOKEN_EQUIVALENCE_FAILED_NO_NEXT_STAGE');save();break
        assert len(worker['enumeratedGpus'])==1 and worker['gpuIndex']==0 and 'RX 6800 XT' in worker['actualGpu']
        if stage=='fresh': first_output=output
        else:
            assert worker['resumedPrefixTokens']==64 and worker['newGeneratedTokens']==109
            state.update(state='PASS_FRESH_AND_RESUMED_ALL173_IDS_IDENTICAL_EXECUTION_ONLY',verifiedSourceSha256={n:sha(M/'src'/n) for n in ['moss_night_gpu_worker_20261104.py','moss_generation_checkpoint_20261107.py','run_night_moss_gpu_20261104.py','moss_retire_acoustic_20261106.py']});save()
except BaseException as error:
    state.update(state='CONTROL_FAILURE_RETAINED',error=repr(error));save();raise
finally:
    state.update(finishedAt=now());state.pop('supervisorPid',None);save()
print(json.dumps(state,ensure_ascii=False),flush=True)
