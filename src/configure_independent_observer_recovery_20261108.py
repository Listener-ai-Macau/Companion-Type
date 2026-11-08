"""Source-level observer repair; preserve failed controller and unchanged model outputs."""
from pathlib import Path
import ast,hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-dual-mic-independent-meetings/oracle-activity-control'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));old=S/'run_independent_oracle_gss_20261108.py';failure=read(C/'run-r2.json');assert failure['state']=='PS4_CONTROLLER_ERROR_RETAINED' and failure['error'].startswith('PermissionError') and "progress=read(receipt)" in failure['traceback']
text=old.read_text(encoding='utf8');text=text.replace('from practical_io_20261107 import atomic_json,stop_owned_family','from practical_io_20261107 import atomic_json,stop_owned_family\nfrom independent_progress_reader_20261108 import read_progress')
start=text.index("    old=read(target);assert args.resume_after_low_ram");end=text.index("    archive=C/",start)
text=text[:start]+'''    old=read(target)
    if old['state']=='STOPPED_ACTUAL_WINDOWS_LOW_RAM':
        assert args.resume_after_low_ram and old.get('finishedAt')
        last=json.loads((C/'resources-r2.json').read_text().splitlines()[-1]) if old['results'] else {'availableBytes':old['deferredAvailableBytes']}
        peak=old['results'][-1]['privatePeakBytes'] if old['results'] else 0
        assert not pressure.low() and psutil.virtual_memory().available>last['availableBytes']+peak,'Wait for actual external memory recovery'
    else:
        assert args.resume_after_observer_fix and old['state']=='PS4_CONTROLLER_ERROR_RETAINED' and old['error'].startswith('PermissionError')
        assert "progress=read(receipt)" in old['traceback'] and read(C.parent/'observer-lock-proof.json')['state']=='PASS_REAL_WINDOWS_EXCLUSIVE_LOCK_OBSERVER_CONTINUES_AND_RECOVERS'
        assert not pressure.low(),'Do not restart in actual low RAM'
''' +text[end:]
text=text.replace("parser.add_argument('--resume-after-low-ram',action='store_true');args=parser.parse_args()","parser.add_argument('--resume-after-low-ram',action='store_true');parser.add_argument('--resume-after-observer-fix',action='store_true');args=parser.parse_args()")
text=text.replace('else:assert not args.resume_after_low_ram','else:assert not args.resume_after_low_ram and not args.resume_after_observer_fix')
text=text.replace('lastpoint=None;progress_at=start','lastpoint=None;progress_at=start;last_observation={}')
needle="progress=read(receipt) if receipt.exists() else {};point=(progress.get('state'),progress.get('completedInputs'),progress.get('newNeuralCalls'))";assert text.count(needle)==1
text=text.replace(needle,"progress,observation_issue=read_progress(receipt,last_observation);last_observation=progress;point=(progress.get('state'),progress.get('completedInputs'),progress.get('newNeuralCalls'))\n                    if observation_issue:\n                        state['transientObserverSkips']=state.get('transientObserverSkips',0)+1")
new=S/'run_independent_oracle_gss_recovery_20261108.py';assert not new.exists();ast.parse(text);new.write_text(text,encoding='utf8')
atomic_json(C/'observer-recovery-source.json',{'state':'FIXED_TRANSIENT_OBSERVER_LOCK_SOURCE_UNCHANGED_ACOUSTIC_PROTOCOL','oldController':str(old),'oldControllerSha256':hashlib.sha256(old.read_bytes()).hexdigest(),'newController':str(new),'newControllerSha256':hashlib.sha256(new.read_bytes()).hexdigest(),'failedRunSha256':hashlib.sha256((C/'run-r2.json').read_bytes()).hexdigest(),'protocolAndWorkerHashesUnchanged':True,'sameBindingCompletedOutputsRetained':True,'modelErrorRetryAllowed':False})
print('CONFIGURED_SOURCE_FIXED_OBSERVER_RECOVERY',flush=True)
