"""An independent CPU scoring environment; never add references to inference."""
from pathlib import Path
import subprocess,sys,os,json,time,psutil
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=root/'docs/handoffs/20261105-model-resume';runtime=Path('E:/CodexData/Companion/.model-cache/scoring-runtime-20261105')
receipt=m/'scoring-setup.json';assert not receipt.exists() and not runtime.exists()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);psutil.Process().cpu_affinity(psutil.Process().cpu_affinity()[-1:])
state={'state':'INSTALLING_SEPARATE_CPU_SCORER','modelLoaded':False,'inferenceEnvironmentChanged':False,'steps':[]}
env=os.environ.copy();env.update(PIP_DISABLE_PIP_VERSION_CHECK='1',PIP_CACHE_DIR='E:/CodexData/Companion/.model-cache/scoring-pip-cache',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
for label,command in [('create-scoring',[sys.executable,'-m','venv','--system-site-packages',str(runtime)]),('install-scoring',[str(runtime/'Scripts/python.exe'),'-m','pip','install','--progress-bar','off','--index-url','https://pypi.org/simple','--report',str(m/'scoring-install-report.json'),'praatio==6.2.2','rapidfuzz==3.14.3','pyannote.metrics==4.0.0'])]:
    start=time.perf_counter()
    with (m/(label+'.log')).open('xb') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    state['steps'].append({'step':label,'exitCode':result.returncode,'seconds':round(time.perf_counter()-start,3)})
    state['state']='CPU_SCORING_SETUP_FAILURE_RETAINED' if result.returncode else 'CPU_SCORING_ENVIRONMENT_READY' if label=='install-scoring' else state['state']
    receipt.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');assert result.returncode==0,label
print(json.dumps(state),flush=True)
