"""Keep scoring independent of the global packages and of the GPU runtime."""
from pathlib import Path
import subprocess,sys,os,json,time,psutil
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=root/'docs/handoffs/20261105-model-resume'
runtime=Path('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106')
receipt=m/'scoring-setup-clean-20261106.json';assert not receipt.exists() and not runtime.exists()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);psutil.Process().cpu_affinity(psutil.Process().cpu_affinity()[-1:])
state={'state':'INSTALLING_CLEAN_CPU_SCORER','modelLoaded':False,'inferenceEnvironmentChanged':False,
       'systemSitePackages':False,'previousFailure':'Previous CPU-only venv inherited unrelated global Gradio/Transformers constraints; retain failed pip check and create clean venv, no global edits.','steps':[]}
env={k:v for k,v in os.environ.items() if k.upper() not in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','PYTHONPATH']}
env.update(PIP_DISABLE_PIP_VERSION_CHECK='1',PIP_CACHE_DIR='E:/CodexData/Companion/.model-cache/scoring-pip-cache',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
steps=[('create-scoring-clean',[sys.executable,'-m','venv',str(runtime)]),
       ('install-scoring-clean',[str(runtime/'Scripts/python.exe'),'-m','pip','install','--progress-bar','off','--index-url','https://pypi.org/simple','--report',str(m/'scoring-install-clean-report-20261106.json'),
         'praatio==6.2.2','rapidfuzz==3.14.3','pyannote.metrics==4.0.0','psutil==7.1.3','scipy==1.17.1','numpy==2.4.6','pandas==2.3.3','tzdata==2026.2']),
       ('check-scoring-clean',[str(runtime/'Scripts/python.exe'),'-m','pip','check'])]
for label,command in steps:
    start=time.perf_counter()
    with (m/(label+'.log')).open('xb') as log:
        result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    state['steps'].append({'step':label,'exitCode':result.returncode,'seconds':round(time.perf_counter()-start,3)})
    state['state']='CPU_SCORING_SETUP_FAILURE_RETAINED' if result.returncode else 'CLEAN_CPU_SCORER_DEPENDENCIES_VERIFIED' if label=='check-scoring-clean' else state['state']
    receipt.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');assert result.returncode==0,label
print(json.dumps(state),flush=True)
