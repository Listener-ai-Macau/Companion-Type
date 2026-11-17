"""Monitor only an owned iGPU inference child; preserve terminal failure evidence."""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, os, subprocess, sys, time
import psutil
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--index',type=int,required=True);a=p.parse_args()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    P=read(a.control/'protocol.json');cases=read(a.control/'audio-only.json');case=cases[a.index]
    run=Path(P['probabilityCacheRoot']).parent;run.mkdir(parents=True,exist_ok=True)
    state_file=run/(case['meeting']+'-run.json');assert not state_file.exists()
    state={'state':'STARTING_OWNED_EXPLICIT_780M_INFERENCE','at':datetime.now().astimezone().isoformat(),
        'meeting':case['meeting'],'training':False,'parameterUpdates':0,'automaticRetries':0,
        'privateFamilyPeakBytes':0,'minimumAvailableBytes':psutil.virtual_memory().available}
    def save():atomic_json(state_file,state)
    child=owned=None;pressure=SystemRamPressure();save()
    try:
        worker=Path(__file__).with_name('native8_780m_inference_20261117.py')
        with (run/(case['meeting']+'-worker.log')).open('xb') as log:
            child=subprocess.Popen([sys.executable,str(worker),'--control',str(a.control),'--index',str(a.index)],
                stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);state.update(pid=owned.pid,createdAt=owned.create_time());save()
            while child.poll() is None:
                assert not pressure.low() and psutil.virtual_memory().available>=P['minimumAvailableBytes'],'Original system RAM guard'
                assert datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Bounded iGPU execution deadline'
                assert not(a.control/'stop.request').exists(),'Owned stop requested'
                try:
                    private=sum(x.memory_info().private for x in [owned]+owned.children(recursive=True))
                    state['privateFamilyPeakBytes']=max(private,state['privateFamilyPeakBytes'])
                    state['minimumAvailableBytes']=min(state['minimumAvailableBytes'],psutil.virtual_memory().available)
                    assert private<=P['privateCommitBytes'],'Original2GiB family private commit guard'
                except psutil.NoSuchProcess:pass
                save();time.sleep(.5)
        result=a.control/'results'/case['meeting']/'completed-state.json'
        receipt=read(result) if result.exists() else {}
        state.update(exitCode=child.returncode,workerReceipt=str(result),workerState=receipt.get('state'),
            newNeuralPushes=receipt.get('newNeuralPushes',0),completedNeuralFrames=receipt.get('completedNeuralFrames',0))
        assert child.returncode==0 and receipt.get('state')=='COMPLETE_780M_SPEAKER_JOURNAL_UNQUALIFIED','Owned iGPU worker did not complete'
        assert receipt['gpuUsed'] and '780M' in receipt['selectedNativeDevice']['description']
        state['state']='COMPLETE_EXPLICIT_780M_INFERENCE_PENDING_INDEPENDENT_COMPARISON'
    except BaseException as error:
        state.update(state='FAILED_EXPLICIT_780M_INFERENCE_RETAINED_NO_RETRY',error=repr(error));raise
    finally:
        if child is not None and child.poll() is None:stop_owned_family(child,owned)
        pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
        print(json.dumps(state,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
