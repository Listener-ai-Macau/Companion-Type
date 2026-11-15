"""Preserve completed official wheels and resume the interrupted SDK download."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import requests,psutil,hashlib,json,time,shutil,zipfile,subprocess,sys,os
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');proof=root/'docs/handoffs/20261105-model-resume'
cache=Path('E:/CodexData/Companion/.model-cache/amd-wheelhouse-20261105');cache.mkdir(parents=True,exist_ok=True)
night=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104');python=night/'amd-runtime/Scripts/python.exe'
receipt=proof/'runtime-restore-r2.json';assert not receipt.exists()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);allowed=psutil.Process().cpu_affinity();psutil.Process().cpu_affinity(allowed[-2:])
state={'at':now(),'state':'RECOVERING_OFFICIAL_PINNED_AMD_WHEELHOUSE','pid':os.getpid(),'modelLoaded':False,'retainedFirstInstallerExit':'Original installer and parent disappeared without a final receipt; cause unknown, preserve logs/partials. Not a model failure.','wheels':[]}
def save():
    t=receipt.with_suffix('.tmp');t.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');t.replace(receipt)
def sha(p):
    with p.open('rb') as inp:return hashlib.file_digest(inp,'sha256').hexdigest()
save();begin=time.perf_counter()
try:
    # Only paths/file identities observed in our interrupted pip run.
    temp=Path('C:/Users/Billy/AppData/Local/Temp')
    for folder,name in [('pip-unpack-9dzb06z7','torch-2.11.0+rocm10.0.0-cp311-cp311-win_amd64.whl'),
        ('pip-unpack-4p3i6wem','amd_torch_device_gfx1030-2.11.0+rocm10.0.0-cp311-cp311-win_amd64.whl'),
        ('pip-unpack-7h2stqh1','rocm_sdk_device_gfx1030-10.0.0-py3-none-win_amd64.whl'),('pip-unpack-nrfvkc8q','networkx-3.7-py3-none-any.whl')]:
        source=temp/folder/name;dest=cache/name
        with zipfile.ZipFile(source) as archive:assert archive.testzip() is None
        if not dest.exists():shutil.copyfile(source,dest)
        assert sha(source)==sha(dest);state['wheels'].append({'file':name,'sha256':sha(dest),'bytes':dest.stat().st_size,'origin':'Completed official AMD-index wheel retained from first pip attempt'});save()
    name='rocm_sdk_core-10.0.0-py3-none-win_amd64.whl';dest=cache/name;prefix=cache/(name+'.prefix')
    old=temp/'pip-unpack-g_3jufh_'/name
    if not prefix.exists():shutil.copyfile(old,prefix)
    start=prefix.stat().st_size;total=758050981;assert 0<start<total
    parts=cache/'core-ranges';parts.mkdir(exist_ok=True)
    url='https://stable.repo.amd.com/rocm/core/whl-next/rocm-sdk-core/'+name
    state.update(state='RESUMING_SDK_CORE_RANGES',reusedPrefixBytes=start,downloadedCoreBytes=start,expectedCoreBytes=total,workers=4);save()
    def one(span):
        a,b=span;p=parts/f'{a}-{b}.part';length=b-a+1;s=requests.Session();s.trust_env=False
        for attempt in range(3):
            offset=p.stat().st_size if p.exists() else 0
            if offset==length:return p
            assert offset<length
            try:
                with s.get(url,headers={'Range':f'bytes={a+offset}-{b}'},stream=True,timeout=(20,60)) as response:
                    response.raise_for_status();assert response.status_code==206 and response.headers.get('Content-Range')==f'bytes {a+offset}-{b}/{total}'
                    with p.open('ab' if offset else 'wb') as out:
                        for block in response.iter_content(1024**2):
                            if block:out.write(block)
                assert p.stat().st_size==length;return p
            except Exception:
                if attempt==2:raise
    spans=[(a,min(total-1,a+8*1024**2-1)) for a in range(start,total,8*1024**2)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(one,x):x for x in spans}
        for future in as_completed(futures):
            future.result();a,b=futures[future];state['downloadedCoreBytes']+=b-a+1;save()
    with dest.open('xb') as output:
        for source in [prefix]+[parts/f'{a}-{b}.part' for a,b in spans]:
            with source.open('rb') as inp:shutil.copyfileobj(inp,output,1024**2)
    assert dest.stat().st_size==total
    with zipfile.ZipFile(dest) as archive:assert archive.testzip() is None
    state['wheels'].append({'file':name,'bytes':total,'sha256':sha(dest),'origin':'Official pinned AMD HTTPS object, exact ranges plus complete ZIP CRC checked; SHA locally observed, no published SHA claimed.'});save()
    env={k:v for k,v in os.environ.items() if not k.startswith(('COMPANION_','LISTENER_','OPENAI_','HF_TOKEN','HUGGING_FACE_HUB_TOKEN','PYTHONPATH'))}
    env.update(PIP_CACHE_DIR=str(night/'pip-cache'),PIP_DISABLE_PIP_VERSION_CHECK='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    commands=[('install-amd-torch-r2',[str(python),'-m','pip','install','--progress-bar','off','--find-links',str(cache),
        '--index-url','https://stable.repo.amd.com/rocm/whl-next/','--extra-index-url','https://pypi.org/simple',
        '--report',str(proof/'amd-install-report-r2.json'),'torch[device-gfx1030]==2.11.0+rocm10.0.0']),
        ('install-model-frontend-r2',[str(python),'-m','pip','install','--progress-bar','off','--index-url','https://pypi.org/simple',
        '--report',str(proof/'frontend-install-report-r2.json'),'transformers==5.22.1','librosa==0.11.0','safetensors==0.7.0','soundfile==0.13.1','soxr','scipy','numba','psutil==7.1.3'])]
    for label,cmd in commands:
        state.update(state='INSTALLING_PINNED_ISOLATED_RUNTIME',activeStep=label);save();tick=time.perf_counter()
        with (proof/(label+'.log')).open('xb') as log:
            process=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            state['ownedInstallerPid']=process.pid;save();code=process.wait()
        state.setdefault('steps',[]).append({'step':label,'exitCode':code,'seconds':round(time.perf_counter()-tick,3)});save();assert code==0,(label,code)
    state.pop('ownedInstallerPid',None);state.pop('activeStep',None);state.update(state='ISOLATED_NATIVE_AMD_AND_MOSS_FRONTEND_READY_NOT_IMPORTED',runtime=str(python))
except BaseException as error:
    state.update(state='AMD_RUNTIME_RESTORE_FAILURE_RETAINED',error=repr(error));raise
finally:
    state.update(finishedAt=now(),wallSeconds=round(time.perf_counter()-begin,3));save();print(json.dumps(state,ensure_ascii=False),flush=True)
