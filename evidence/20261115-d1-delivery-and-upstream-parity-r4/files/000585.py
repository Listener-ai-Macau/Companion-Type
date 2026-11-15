"""Current-task wait for connected external card, then exactly one full run."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,os,subprocess,sys,time

p=argparse.ArgumentParser();p.add_argument('--wait-seconds',type=int,default=600);args=p.parse_args()
assert 0<=args.wait_seconds<=3600
m=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261105-model-resume')
receipt=m/'external-gpu-connection-wait-20261106.json';assert not receipt.exists()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
state={'state':'WAITING_CONNECTED_EXTERNAL_RX6800XT','startedAt':now(),'pid':os.getpid(),'maximumWaitSeconds':args.wait_seconds,
       'scope':'This current authorized full-meeting task only. No scheduled task, no reboot or device/driver change, no repeated model launch.'}
def save():
    t=receipt.with_suffix('.tmp');t.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');t.replace(receipt)
start=time.perf_counter();save()
while True:
    if (m/'external-gpu-connection-wait-stop.request').exists():state['state']='STOPPED_BY_EXPLICIT_REQUEST';save();break
    result=subprocess.run(['C:/Windows/System32/pnputil.exe','/enum-devices','/class','Display','/connected','/deviceids'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    # PnP output encoding is locale-dependent; the PCI hardware ID is ASCII.
    detected=result.returncode==0 and b'DEV_73BF' in result.stdout
    state.update(lastCheckedAt=now(),pnpQueryExitCode=result.returncode,externalCardConnected=detected);save()
    if detected:
        state.update(state='EXTERNAL_CARD_CONNECTED_STARTING_ONE_FULL_RUN',connectedAt=now());save()
        command=[sys.executable,str(Path(__file__).with_name('resume_full_moss_and_score_20261106.py')),
                 '--control-name','full-L-connected-r18-20261106','--output-suffix=-20261106-r18']
        with (m/'full-L-connected-r18-wrapper.log').open('xb') as stream:
            child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            state.update(fullRunWrapperPid=child.pid);save();code=child.wait()
        state.update(state='ONE_FULL_RUN_EXITED_READ_BATCH_RESULT',fullRunWrapperExitCode=code,finishedAt=now());save();break
    if time.perf_counter()-start>=args.wait_seconds:
        state.update(state='EXTERNAL_GPU_STILL_DISCONNECTED_NO_MODEL_STARTED',finishedAt=now());save();break
    time.sleep(max(.001,min(20,args.wait_seconds-(time.perf_counter()-start))))
print(json.dumps(state,ensure_ascii=False),flush=True)
