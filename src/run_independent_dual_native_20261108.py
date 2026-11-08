"""Four serial full-meeting native journals, actual Windows RAM-pressure protection."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,psutil,subprocess,sys,time,traceback
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-independent-meetings')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
parser=argparse.ArgumentParser();parser.add_argument('--resume-resource-stop',action='store_true');args=parser.parse_args()
target=C/'native-run.json';prior=read(target) if target.exists() else None
if prior:
    assert args.resume_resource_stop and prior['state']=='STOPPED_ACTUAL_LOW_RAM_PARTIAL_RETAINED'
    assert psutil.virtual_memory().available>prior['availableAtStopBytes']+prior['stoppedOwnPeakPrivateBytes'],'Wait for external RAM recovery, not a blind model retry'
    archive=C/('prior-native-run-'+hashlib.sha256(target.read_bytes()).hexdigest()[:12]+'.json');archive.write_bytes(target.read_bytes())
worker=Path(__file__).with_name('independent_dual_native_worker_20261108.py');P=read(C/'protocol.json');assert hashlib.sha256(worker.read_bytes()).hexdigest()==P['workerSourceSha256']
state={'state':'PREPARING_NATIVE_JOURNALS','pid':os.getpid(),'startedAt':now(),'results':[],'referencePayloadRead':False,'protocolSha256':hashlib.sha256((C/'protocol.json').read_bytes()).hexdigest(),'automaticModelRetries':0};pressure=SystemRamPressure();child=root=None
save=lambda:atomic_json(target,state)
try:
    cases=read(C/'audio-only.json');assert len(cases)==4
    for process in psutil.process_iter(['cmdline']):
        try:assert not any(str(x).replace('\\','/').lower().startswith(str(worker.parent).replace('\\','/').lower()+'/') and '_worker_' in Path(str(x)).name for x in process.info['cmdline'] or []),'One owned neural model at a time'
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    for index,case in enumerate(cases):
        out=C/'results'/case['meeting'];attempts=sorted(out.glob('attempt-*')) if out.exists() else []
        complete=[x for x in attempts if (x/'completed-state.json').exists() and read(x/'completed-state.json')['state']=='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED']
        if complete:
            assert len(complete)==1;state['results'].append({'meeting':case['meeting'],'out':str(complete[0]),'retainedCompletedAttempt':True});save();continue
        assert not attempts or args.resume_resource_stop
        if pressure.low():state.update(state='STOPPED_ACTUAL_LOW_RAM_PARTIAL_RETAINED',availableAtStopBytes=psutil.virtual_memory().available,stoppedOwnPeakPrivateBytes=0);break
        attempt=len(attempts)+1;dest=out/('attempt-'+str(attempt));tick=time.perf_counter();peak=0;lastchange=tick;lastsize=-1
        state.update(state='RUNNING_NATIVE_FULL_CHANNEL',activeMeeting=case['meeting'],attempt=attempt);save()
        with (C/(case['meeting']+f'-attempt-{attempt}.log')).open('xb') as log:
            child=subprocess.Popen([sys.executable,str(worker),'--control',str(C),'--index',str(index),'--attempt',str(attempt)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS)
            root=psutil.Process(child.pid);root.cpu_affinity([12,13,14,15]);state['activePid']=child.pid;save()
            while child.poll() is None:
                if pressure.low() or (C/'stop.request').exists():
                    low=pressure.low();available=psutil.virtual_memory().available;stop_owned_family(child,root);state.update(state='STOPPED_ACTUAL_LOW_RAM_PARTIAL_RETAINED' if low else 'STOPPED_OWNER_REQUEST_PARTIAL_RETAINED',availableAtStopBytes=available,stoppedOwnPeakPrivateBytes=peak);break
                f=dest/'state.json';size=f.stat().st_mtime_ns if f.exists() else 0
                if size!=lastsize:lastsize=size;lastchange=time.perf_counter()
                if time.perf_counter()-lastchange>600:stop_owned_family(child,root);state['state']='STOPPED_NO_PROGRESS_600S_RETAINED';break
                try:
                    members=[root]+root.children(recursive=True);private=sum(getattr(x.memory_info(),'private',0) for x in members);peak=max(peak,private)
                    with (C/'native-resources.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps({'at':now(),'meeting':case['meeting'],'attempt':attempt,'privateBytes':private,'availableBytes':psutil.virtual_memory().available})+'\n')
                except psutil.Error:pass
                time.sleep(1)
        receipt=read(dest/'completed-state.json') if (dest/'completed-state.json').exists() else {}
        state['results'].append({'meeting':case['meeting'],'out':str(dest),'exitCode':child.returncode,'workerState':receipt.get('state'),'wholeProcessFamilySeconds':time.perf_counter()-tick,'privatePeakBytes':peak});state.pop('activePid',None);save()
        if child.returncode or receipt.get('state')!='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED':
            if not state['state'].startswith('STOPPED_'):state['state']='FAILED_NATIVE_CHANNEL_RETAINED_NO_MODEL_RETRY'
            break
    else:state['state']='COMPLETE_FOUR_FULL_CHANNEL_JOURNALS_UNQUALIFIED'
except BaseException as error:state.update(state='CONTROLLER_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    if child is not None and child.poll() is None:stop_owned_family(child,root)
    pressure.close();state.pop('activePid',None);state['finishedAt']=now();save();print(json.dumps(state,ensure_ascii=False),flush=True)
