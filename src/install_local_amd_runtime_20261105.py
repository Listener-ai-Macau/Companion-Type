"""Use verified complete local wheels explicitly; never reselect a truncated URL."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,subprocess,os,time,psutil
p=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261105-model-resume');n=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104');w=Path('E:/CodexData/Companion/.model-cache/amd-wheelhouse-20261105');python=n/'amd-runtime/Scripts/python.exe'
receipt=p/'runtime-restore-r3.json';assert not receipt.exists()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);psutil.Process().cpu_affinity(psutil.Process().cpu_affinity()[-2:])
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
state={'at':now(),'state':'INSTALLING_EXPLICIT_VERIFIED_LOCAL_AMD_WHEELS','modelLoaded':False,'steps':[],'pid':os.getpid()}
def save():
 t=receipt.with_suffix('.tmp');t.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');t.replace(receipt)
env={k:v for k,v in os.environ.items() if not k.startswith(('COMPANION_','LISTENER_','OPENAI_','HF_TOKEN','HUGGING_FACE_HUB_TOKEN','PYTHONPATH'))}
env.update(PIP_CACHE_DIR=str(n/'pip-cache'),PIP_DISABLE_PIP_VERSION_CHECK='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
local=[str(w/name) for name in ['rocm_sdk_core-10.0.0-py3-none-win_amd64.whl','torch-2.11.0+rocm10.0.0-cp311-cp311-win_amd64.whl','amd_torch_device_gfx1030-2.11.0+rocm10.0.0-cp311-cp311-win_amd64.whl','rocm_sdk_device_gfx1030-10.0.0-py3-none-win_amd64.whl']]
commands=[('install-amd-torch-r3',[str(python),'-m','pip','install','--progress-bar','off','--index-url','https://stable.repo.amd.com/rocm/whl-next/','--extra-index-url','https://pypi.org/simple','--report',str(p/'amd-install-report-r3.json'),*local,'torch[device-gfx1030]==2.11.0+rocm10.0.0']),
 ('install-model-frontend-r3',[str(python),'-m','pip','install','--progress-bar','off','--index-url','https://pypi.org/simple','--report',str(p/'frontend-install-report-r3.json'),'transformers==5.22.1','librosa==0.11.0','safetensors==0.7.0','soundfile==0.13.1','soxr','scipy','numba','psutil==7.1.3'])]
save();begin=time.perf_counter()
try:
 for label,cmd in commands:
  state['activeStep']=label;save();start=time.perf_counter()
  with (p/(label+'.log')).open('xb') as log:
   child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   state['ownedInstallerPid']=child.pid;save();code=child.wait()
  state['steps'].append({'step':label,'seconds':round(time.perf_counter()-start,3),'exitCode':code});save();assert code==0,(label,code)
 state.update(state='PINNED_NATIVE_AMD_AND_MOSS_DEPENDENCIES_READY_NOT_IMPORTED',python=str(python));state.pop('activeStep',None);state.pop('ownedInstallerPid',None)
except BaseException as error:state.update(state='LOCAL_WHEEL_RUNTIME_FAILURE_RETAINED',error=repr(error));raise
finally:state.update(finishedAt=now(),wallSeconds=round(time.perf_counter()-begin,3));save();print(json.dumps(state),flush=True)
