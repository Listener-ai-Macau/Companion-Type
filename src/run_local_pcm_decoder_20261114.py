"""Launch one local native decoder after unchanged resource/device gates.
No cloud, automatic retry, default-app changes or foreground device access.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, os, subprocess, sys, time
import psutil
from companion_local_pcm_session_20261114 import PcmSession, atomic_json, read_json, exclusive_file
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
from run_paired_fixed_asr_20261109 import resume_resources
from companion_windows_power_request_20261115 import PowerLease

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
BASE=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json')
PRIOR=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-r2-runs/near-N_SPK8014/task.json')
GPU_PY=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe')
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()

def run_one_decoder():
    parser=argparse.ArgumentParser();parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--inventory',type=Path,required=True);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--follow-seconds',type=float,default=0);parser.add_argument('--wait-resource-seconds',type=float,default=0)
    parser.add_argument('--deadline-seconds',type=float,default=900);args=parser.parse_args()
    assert 0<=args.wait_resource_seconds<=1800 and 0<=args.follow_seconds<=10800 and 0<args.deadline_seconds<=14400
    assert args.run.is_absolute() and args.session.is_absolute() and args.inventory.is_absolute()
    assert not args.run.exists(),'Preserve prior attempt; any continuation uses a new attempt directory'
    session=PcmSession(args.session);session.reconcile();assert session.pending(),'No model is needed for an empty or already completed queue'
    args.run.mkdir(parents=True)
    record={'at':now(),'state':'WAITING_UNCHANGED_LOCAL_MODEL_RESOURCE_RECOVERY','session':str(session.root),
            'baseProtocolSha256':sha(BASE),'automaticRetries':0,'localOnly':True,'sourceAudioUploaded':False,
            'qualityQualified':False,'availableBytesAtStart':psutil.virtual_memory().available}
    target=args.run/'run.json';save=lambda:atomic_json(target,record)
    started=time.perf_counter();record['resources']=resume_resources(PRIOR);save()
    while not record['resources']['ready'] and time.perf_counter()-started<args.wait_resource_seconds:
        time.sleep(5);record['resources']=resume_resources(PRIOR);record['lastResourceObservationAt']=now();save()
    if not record['resources']['ready']:
        record.update(state='DEFERRED_LOCAL_MODEL_UNCHANGED_RAM_GATE',finishedAt=now(),modelWorkerStarted=False)
        save();print(json.dumps(record,ensure_ascii=False));return 2
    inventory=read_json(args.inventory)
    assert inventory['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
    selected=inventory['selected']
    assert selected['name']=='AMD Radeon RX 6800 XT' and selected['architecture']=='gfx1030'
    age=(datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()
    if not 0<=age<1800:
        record.update(state='DEFERRED_LOCAL_MODEL_REFRESH_DEVICE_IDENTITY',finishedAt=now(),modelWorkerStarted=False,inventoryAgeSeconds=age)
        save();print(json.dumps(record,ensure_ascii=False));return 2
    worker=Path(__file__).with_name('companion_local_qwen_worker_20261114.py')
    env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
    if os.environ.get('COMPANION_LOCAL_ARTIFACT_ROOT'):
        env['PYTHONPATH']=str(Path(__file__).resolve().parent/'cache-audit-hook')
    env.update(HIP_VISIBLE_DEVICES=str(selected['ordinal']),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    command=[str(GPU_PY),str(worker),'--session',str(session.root),'--protocol',str(BASE),
             '--inventory',str(args.inventory),'--run',str(args.run),'--follow-seconds',str(args.follow_seconds)]
    record.update(state='RUNNING_LOCAL_BILINGUAL_PCM_DECODER',workerSourceSha256=sha(worker),
                  currentGpu=selected,inventorySha256=sha(args.inventory),modelWorkerStarted=True)
    pressure=SystemRamPressure();child=None;peak=0;began=time.perf_counter()
    try:
        if pressure.low():raise RuntimeError('Actual Windows pressure changed before decoder spawn')
        with (args.run/'worker.log').open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            record['workerPid']=child.pid;save()
            while child.poll() is None:
                low=pressure.low()
                if low or time.perf_counter()-began>args.deadline_seconds:
                    record.update(actualWindowsLowRam=low,stopReason='actual_windows_low_ram' if low else 'bounded_deadline',
                                  systemAvailableBytesAtStop=psutil.virtual_memory().available)
                    (args.run/'stop.request').write_text(record['stopReason'],encoding='ascii')
                    stop_owned_family(child,psutil.Process(child.pid));break
                try:
                    family=[psutil.Process(child.pid)]+psutil.Process(child.pid).children(recursive=True)
                    peak=max(peak,sum(p.memory_info().private for p in family))
                except psutil.Error:pass
                time.sleep(.5)
        record.update(exitCode=child.returncode,privatePeakBytes=peak,
                      state='LOCAL_MODEL_ATTEMPT_COMPLETE_REVIEW_PENDING' if child.returncode==0 else 'LOCAL_MODEL_ATTEMPT_STOPPED_RETAINED')
    except BaseException as error:
        record.update(state='LOCAL_MODEL_LAUNCH_OR_RUN_FAILED_RETAINED',errorType=type(error).__name__,error=str(error));raise
    finally:
        if child is not None and child.poll() is None:stop_owned_family(child,psutil.Process(child.pid))
        pressure.close();record.pop('workerPid',None);record.update(finishedAt=now(),seconds=time.perf_counter()-began)
        save()
    print(json.dumps(record,ensure_ascii=False));return 0 if record.get('exitCode')==0 else 1

def main():
    # Serialize this adapter across recording sessions, not only within a
    # session. The OS releases ownership on crash; no stale PID can admit a
    # second model while the first adapter is alive. Legacy research runners
    # remain separately scheduled and are not claimed to share this lock.
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')), PowerLease():
        return run_one_decoder()

if __name__=='__main__':raise SystemExit(main())
