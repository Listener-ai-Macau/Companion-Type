"""Watch one explicitly created GPU worker; never retries or stops other apps."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import subprocess
import sys
import time
import psutil
from meeting_acoustic_contract_20261116 import read,require,sha
from meeting_acoustic_worker_20261116 import own_limits
from practical_io_20261107 import atomic_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--phase',required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    limits=own_limits(25);P=read(a.protocol);run=a.run.resolve();run.mkdir(parents=True,exist_ok=True)
    owner=run/('supervisor-'+a.phase);owner.mkdir(exist_ok=False)
    require(any(Path(x['file']).resolve()==a.worker.resolve() and x['sha256']==sha(a.worker) for x in P['files']),
        'Worker is not frozen in protocol')
    with (owner/'stdout.log').open('w',encoding='utf-8') as log:
        command=[P['runtime']['python'],str(a.worker.resolve()),'--protocol',str(a.protocol.resolve()),'--phase',a.phase,'--run',str(run)]
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        owned=psutil.Process(proc.pid);created=owned.create_time();began=time.monotonic();reason=None
        atomic_json(owner/'started.json',{'pid':proc.pid,'createdAt':created,'at':datetime.now().astimezone().isoformat(),
            'protocolSha256':sha(a.protocol),'workerSha256':sha(a.worker),'noAutomaticRetry':True})
        while proc.poll() is None:
            time.sleep(.5);state_file=run/a.phase/'state.json'
            if state_file.exists():
                try:s=read(state_file)
                except (OSError,json.JSONDecodeError):continue
                age=time.time()-datetime.fromisoformat(s['observedAt']).timestamp()
                if age>s.get('currentOperationBudgetSeconds',180)+3:reason='No owned worker progress within declared budget'
            elif time.monotonic()-began>180:reason='No startup progress within180s'
            if datetime.now().astimezone()>=datetime.fromisoformat(P['stopAt']):reason='Original overnight cutoff'
            if reason:
                require(abs(owned.create_time()-created)<.01,'PID identity changed; do not stop')
                for child in reversed(owned.children(recursive=True)):
                    try:child.kill()
                    except psutil.NoSuchProcess:pass
                try:owned.kill()
                except psutil.NoSuchProcess:pass
                break
        code=proc.wait(timeout=15)
    result={'state':'OWNED_GPU_WORKER_EXITED' if code==0 else 'OWNED_GPU_WORKER_FAILED_NO_RETRY',
        'at':datetime.now().astimezone().isoformat(),'exitCode':code,'watchdogReason':reason,'pid':proc.pid,
        'createdAt':created,'phase':a.phase,'trainingUpdates':0,'limits':limits.query(),
        'cannotGuaranteeGpuDriverRecovery':True}
    atomic_json(owner/'completed.json',result);print(json.dumps(result));sys.exit(0 if code==0 else 1)

if __name__=='__main__':main()
