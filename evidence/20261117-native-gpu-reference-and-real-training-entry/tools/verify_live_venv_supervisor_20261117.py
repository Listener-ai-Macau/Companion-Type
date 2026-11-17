"""Real Windows venv launcher/child lifecycle; no torch, model or audio calls."""
from pathlib import Path
from datetime import datetime,timedelta
import hashlib,json,os,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from run_owned_tdt_adaptation_20261117 import bind_owned_worker
import psutil
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117/venv-supervisor-regression-r1');C.mkdir(exist_ok=True)
exe='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
stub=C/'owned_probe.py'
stub.write_text('''from pathlib import Path
from datetime import datetime
import argparse,json,os,time
p=argparse.ArgumentParser();p.add_argument('--protocol');p.add_argument('--phase');p.add_argument('--run');a=p.parse_args()
d=Path(a.run)/a.phase;d.mkdir(parents=True)
s=dict(pid=os.getpid(),phase=a.phase,state='LIVE_OWNED_VENV_PROBE',observedAt=datetime.now().astimezone().isoformat(),parameterUpdates=0,candidateOptimizerUpdates=0,completedTrainingExamples=0,currentOperationBudgetSeconds=10)
(d/'state.json').write_text(json.dumps(s));time.sleep(2)
(d/'completed.json').write_text(json.dumps(s))
''',encoding='utf-8')
old=json.loads((R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/language-specific-adaptation-r1/prepared-gpu-evening20261117-r1/protocol.json').read_text())
protocol=dict(runtime={'python':exe},stopAt=(datetime.now().astimezone()+timedelta(seconds=30)).isoformat(),
 gpuExecutionEnabled=True,thermal=old['thermal'],files=[{'file':str(stub),'sha256':hashlib.sha256(stub.read_bytes()).hexdigest()}])
file=C/'protocol.json';file.write_text(json.dumps(protocol),encoding='utf-8')
command=[exe,str(S/'run_owned_tdt_adaptation_20261117.py'),'--worker',str(stub),'--protocol',str(file),'--phase','baseline','--run',str(C/'run')]
if not (C/'run/supervisor-baseline/completed.json').exists():
 p=subprocess.run(command,capture_output=True,text=True,timeout=20)
 (C/'stdout.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
result=json.loads((C/'run/supervisor-baseline/completed.json').read_text())
assert result['state']=='OWNED_TDT_PHASE_COMPLETE' and result['workerIdentity']['pid']!=result['pid']
# A live process outside the owned launch tree must still be rejected.
probe=subprocess.Popen([exe,'-c','import time; time.sleep(3)'])
outside=subprocess.Popen([exe,'-c','import time; time.sleep(3)'])
try:
 time.sleep(.3)
 outside_children=psutil.Process(outside.pid).children()
 assert len(outside_children)==1
 try:bind_owned_worker(psutil.Process(probe.pid),[exe,'-c','import time; time.sleep(3)'],outside_children[0].pid)
 except RuntimeError:outside_rejected=True
 else:outside_rejected=False
 assert outside_rejected
finally:probe.wait(timeout=8);outside.wait(timeout=8)
receipt=dict(state='PASS_REAL_VENV_CHILD_COMPLETION_AND_OUTSIDE_PROCESS_REJECTION',launcherPid=result['pid'],workerIdentity=result['workerIdentity'],
 outsideProcessRejected=outside_rejected,newNeuralCalls=0,newTrainingUpdates=0,modelOrAudioLoaded=False)
(C/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
