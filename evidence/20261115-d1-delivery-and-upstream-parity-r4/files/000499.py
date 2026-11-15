"""Low-impact CPU-only conversion supervisor; no retry, training or inference."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,psutil,subprocess,sys,time,traceback
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json,stop_owned_family
p=argparse.ArgumentParser();p.add_argument('--attempt',type=int,default=1);a=p.parse_args();assert a.attempt>=1
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/native8-precision-preparation');target=C/('precision-run.json' if a.attempt==1 else 'precision-run-%04d.json'%a.attempt);assert not target.exists();assert (C/'prepared.json').exists();pressure=SystemRamPressure();state={'state':'PREPARING_CONVERSION_ONLY','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'automaticRetries':0,'trainingPerformed':False,'neuralInferencePerformed':False};save=lambda:atomic_json(target,state);save();child=None;root=None;tick=time.perf_counter();peak=0
try:
    assert not pressure.low(),'Actual Windows lowRAM; defer conversion'
    with (C/('conversion.log' if a.attempt==1 else 'conversion-%04d.log'%a.attempt)).open('xb') as log:
        child=subprocess.Popen(['E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',str(Path(__file__).with_name('practical_precision_conversion_20261107.py'))]+(['--reuse-verified-q8'] if a.attempt>1 else []),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS);root=psutil.Process(child.pid);root.cpu_affinity([12,13]);state.update(state='RUNNING_CONVERSION_ONLY',childPid=child.pid);save()
        while child.poll() is None:
            if pressure.low() or (C/'stop.request').exists():stop_owned_family(child,root);state['state']='STOPPED_CONVERSION_LOW_RAM_OR_EXPLICIT';break
            try:
                members=[root]+root.children(recursive=True);private=sum(getattr(p.memory_info(),'private',0) for p in members);peak=max(peak,private)
                with (C/'conversion-resources.jsonl').open('a',encoding='utf8') as file:file.write(json.dumps({'at':datetime.now().astimezone().isoformat(timespec='seconds'),'privateBytes':private,'rssBytes':sum(p.memory_info().rss for p in members),'availableBytes':psutil.virtual_memory().available})+'\n')
            except psutil.Error:pass
            time.sleep(1)
    state.update(exitCode=child.returncode,privatePeakBytes=peak)
    if not state['state'].startswith('STOPPED_'):state['state']='CONVERSION_EXITED_REVIEW_REQUIRED' if child.returncode==0 else 'CONVERSION_FAILED_RETAINED_NO_RETRY'
except BaseException as error:state.update(state='CONVERSION_SUPERVISOR_FAILED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,root)
    pressure.close();state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),wholeProcessFamilySeconds=time.perf_counter()-tick);save();print(json.dumps(state),flush=True)
