"""Frozen, audio-only paired-source diagnostic; no reference or model selection.

One native worker at a time. Existing bound tasks may resume only when explicitly
requested; any interrupted/failed task stops the batch, without automatic retry.
Original model pack is immutable; fresh HIP identity is bound in a private copy.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,shutil,subprocess,sys,time
import psutil
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=R/'docs/handoffs/20261109-paired-real-meeting'
P=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--resume',action='store_true');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    inventory=Path(a.inventory).resolve();fresh=read(inventory)
    assert fresh['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
    assert fresh['selected']['name']=='AMD Radeon RX 6800 XT' and fresh['selected']['architecture']=='gfx1030'
    assert abs((datetime.now().astimezone()-datetime.fromisoformat(fresh['finishedAt'])).total_seconds())<1800,'Refresh identity before loading a model'
    original=C.parent/'20261107-model-generation-recovery/practical-qwen-author-boundaries-r6/model-pack.json'
    pack=read(original);old=Path(pack['sourceControl']);runtime=P/'fixed-native-runtime-r2';capsule=runtime/'source';capsule.mkdir(parents=True,exist_ok=True)
    private_pack=runtime/'model-pack.json';existing_pack=read(private_pack) if private_pack.exists() else None
    for name,digest in pack['pinnedFiles'].items():
        assert sha(old/name)==digest
        dest=capsule/name;dest.parent.mkdir(parents=True,exist_ok=True)
        expected=(existing_pack['pinnedFiles'][name] if existing_pack else sha(inventory)) if name=='hip-inventory.json' else digest
        if dest.exists():assert sha(dest)==expected,'Runtime capsule changed; retain evidence'
        else:shutil.copyfile(inventory if name=='hip-inventory.json' else old/name,dest)
    # New inventory timestamps must not invalidate already bound saved ASR.
    # Fresh physical identity/ordinal is checked against the immutable capsule;
    # an actual ordinal change is a clear stop, never implicit iGPU fallback.
    frozen_device=read(capsule/'hip-inventory.json')['selected']
    assert all(fresh['selected'][k]==frozen_device[k] for k in ['ordinal','name','architecture']),'GPU identity/ordinal changed: retain old task and rebind explicitly before running'
    pack['sourceControl']=str(capsule);pack['pinnedFiles']['hip-inventory.json']=sha(capsule/'hip-inventory.json')
    if private_pack.exists():assert read(private_pack)==pack
    else:atomic_json(private_pack,pack)
    binding={'originalPackSha256':sha(original),'runtimePackSha256':sha(private_pack),'freshInventorySha256':sha(capsule/'hip-inventory.json'),'manifestSha256':sha(C/'fixed-asr-audio-only.json'),'sourceControlOnlyChangedToPrivateCapsule':True,'onlyPinnedFileChanged':'hip-inventory.json','referencePassedToInference':False,'newModelSelected':False}
    atomic_json(C/'fixed-native-runtime-r2-binding.json',binding)
    device_check={'at':now(),'currentInventorySha256':sha(inventory),'immutableBoundInventorySha256':sha(capsule/'hip-inventory.json'),'selected':fresh['selected'],'sameDeviceOrdinalVerified':True}
    if a.prepare_only:
        print(json.dumps({'state':'PASS_IMMUTABLE_RESUME_BINDING_NO_MODEL','binding':binding,'deviceCheck':device_check},ensure_ascii=False));return 0
    cases=read(C/'fixed-asr-audio-only.json');state_path=C/'fixed-native-r2-state.json'
    state={'state':'RUNNING_FROZEN_PAIRED_NATIVE_ASR','at':now(),'pid':os.getpid(),'binding':binding,'currentDeviceCheck':device_check,'completed':[],'qualityQualified':False,'automaticRetries':0}
    if state_path.exists():
        assert a.resume,'Existing batch must be explicitly resumed'
        previous=read(state_path);assert previous['binding']==binding
        atomic_json(C/('fixed-native-r2-state-before-'+str(time.time_ns())+'.json'),previous)
    else:assert not a.resume
    atomic_json(state_path,state)
    env={**os.environ,'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','TOKENIZERS_PARALLELISM':'false'}
    for case in cases:
        assert sha(case['audio'])==case['audioSha256']
        task_dir=P/'fixed-native-r2-runs'/case['id'];task=task_dir/'task.json'
        if task.exists() and read(task)['state']=='COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED':
            receipt=read(task);assert receipt['binding']=={'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'modelPackSha256':sha(private_pack)}
            assert sha(receipt['output'])==receipt['outputSha256'];state['completed'].append(case['id']);continue
        if task.exists():
            assert a.resume,'Interrupted task requires explicit continuation after resource recovery'
            prior=read(task);last=prior['attempts'][-1] if prior.get('attempts') else {}
            if last.get('actualWindowsLowRam'):
                pressure=SystemRamPressure()
                try:
                    available=psutil.virtual_memory().available
                    assert not pressure.low() and available>last['systemAvailableBytesAtStop']+2*last['privatePeakBytes'],'No measured RAM recovery since actual low-memory stop; no blind retry'
                finally:pressure.close()
        task_dir.mkdir(parents=True,exist_ok=True);state.update(activeCase=case['id'],caseStartedAt=now());atomic_json(state_path,state)
        command=[sys.executable,str(Path(__file__).with_name('companion_native_asr_20261107.py')),'--audio',case['audio'],'--model-pack',str(private_pack),'--work-dir',str(task_dir)]+(['--resume'] if task.exists() else [])
        # Adapter requires its output directory initially empty; write console logs outside it.
        console=P/'fixed-native-r2-console';console.mkdir(exist_ok=True);n=len(list(console.glob(case['id']+'-*.log')))+1
        with (console/(case['id']+'-'+str(n)+'.log')).open('xb') as log:
            start=time.perf_counter();child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            state['activeAdapterPid']=child.pid;atomic_json(state_path,state)
            try:code=child.wait()
            except BaseException:
                (task_dir/'stop.request').write_text('Owned batch interrupted; retain model outputs.\n',encoding='utf8')
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:stop_owned_family(child,psutil.Process(child.pid))
                state.pop('activeAdapterPid',None);state.update(state='INTERRUPTED_PAIRED_NATIVE_RETAINED',finishedAt=now());atomic_json(state_path,state);raise
        receipt=read(task) if task.exists() else {};state.pop('activeAdapterPid',None)
        state['lastAttempt']={'id':case['id'],'exitCode':code,'adapterSeconds':time.perf_counter()-start,'taskState':receipt.get('state'),'at':now()}
        if code or receipt.get('state')!='COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED':
            state.update(state='PAUSED_PAIRED_NATIVE_RETAINED_NO_AUTOMATIC_RETRY',taskError=receipt.get('error'));atomic_json(state_path,state);print(json.dumps(state,ensure_ascii=False));return 1
        state['completed'].append(case['id']);atomic_json(state_path,state)
    state.pop('activeCase',None);state.update(state='COMPLETE_FIVE_FROZEN_NATIVE_INPUTS_UNSCORED',finishedAt=now());atomic_json(state_path,state);print(json.dumps(state,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
