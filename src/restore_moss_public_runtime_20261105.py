"""Restore only pinned public research assets, separate from the product app.

No model import, inference, driver change, account token or reference access.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,shutil,subprocess,sys,time,requests,psutil

p=argparse.ArgumentParser();p.add_argument('step',choices=['source','runtime','weights']);args=p.parse_args()
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');proof=root/'docs/handoffs/20261105-model-resume';proof.mkdir(parents=True,exist_ok=True)
research=root/'model-research';research.mkdir(exist_ok=True)
assets=Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104');assets.mkdir(parents=True,exist_ok=True)
night=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104');night.mkdir(parents=True,exist_ok=True)
model_rev='10304d926740cf5a5cee05a268086e3265197910';source_rev='79c675f0670cc2f824bcbcdd98263704f40f1f7e'
expected_sha='9a0ceb4ab7330357db3ff583dba8d83625d5b733b00e1d55d6970e11b07026c4';expected_bytes=1817113576
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
allowed=psutil.Process().cpu_affinity();psutil.Process().cpu_affinity(allowed[-2:])
session=requests.Session();session.trust_env=False;session.headers['User-Agent']='Companion-public-research-recovery/1.0'
receipt=proof/(args.step+'-restore.json');assert not receipt.exists(),'Preserve previous outcome; inspect before retry'
state={'at':now(),'step':args.step,'state':'STARTED','speechModelLoaded':False,'modelRevision':model_rev,'officialSourceCommit':source_rev,'referenceOpened':False,'ownerAppsChanged':False}
def save():
    tmp=receipt.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');tmp.replace(receipt)
def get(url):
    resp=session.get(url,timeout=(15,60));resp.raise_for_status();return resp
def exact_file(target,data):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert target.read_bytes()==data,('Existing pinned file differs',str(target))
    else:target.write_bytes(data)
    return hashlib.sha256(data).hexdigest()
save();started=time.perf_counter()
try:
    if args.step=='source':
        metadata=get(f'https://huggingface.co/api/models/OpenMOSS-Team/MOSS-Transcribe-Diarize/revision/{model_rev}').json()
        assert metadata['sha']==model_rev and not metadata.get('gated') and not metadata.get('private')
        tree=get(f'https://huggingface.co/api/models/OpenMOSS-Team/MOSS-Transcribe-Diarize/tree/{model_rev}?recursive=true&expand=false').json()
        gtree=get(f'https://api.github.com/repos/OpenMOSS/MOSS-Transcribe-Diarize/git/trees/{source_rev}?recursive=1').json()
        assert gtree['sha']==source_rev and not gtree.get('truncated')
        files=[]
        for item in tree:
            name=item['path']
            if item['type']!='file' or name.endswith(('.safetensors','.png','.yaml')):continue
            data=get(f'https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize/resolve/{model_rev}/{name}').content
            sha=exact_file(assets/'model'/name,data);exact_file(research/'pinned-model-config'/name,data)
            files.append({'source':'hf','file':name,'sha256':sha,'bytes':len(data)})
        for item in gtree['tree']:
            name=item['path']
            if item['type']!='blob' or not (name.endswith('.py') or name in ['pyproject.toml','README.md','README_zh.md','LICENSE']):continue
            data=get(f'https://raw.githubusercontent.com/OpenMOSS/MOSS-Transcribe-Diarize/{source_rev}/{name}').content
            gitblob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert gitblob==item['sha']
            sha=exact_file(assets/'official-source'/name,data);exact_file(research/'upstream'/name,data)
            files.append({'source':'github','file':name,'sha256':sha,'gitBlob':gitblob,'bytes':len(data)})
        weight=next(x for x in tree if x['path']=='model-00000-of-00001.safetensors')
        assert weight['size']==expected_bytes and weight['lfs']['oid']==expected_sha
        prepared={'state':'SOURCE_READY_NOT_EXECUTED','startedAt':state['at'],'finishedAt':now(),'modelRevision':model_rev,'sourceCommit':source_rev,'weightFiles':[weight],'files':files}
        for base in [assets,research/'provenance']:
            base.mkdir(parents=True,exist_ok=True)
            for name,value in [('prepare-state.json',prepared),('hf-metadata.json',metadata),('hf-tree.json',tree),('github-tree.json',gtree)]:
                (base/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        (research/'src').mkdir(exist_ok=True)
        helpers=['moss_night_gpu_worker_20261104.py','run_night_moss_gpu_20261104.py','moss_windows_resource_limits_20261104.py',
            'moss_streamed_weights_20261104.py','moss_pcm16_ram_20261104.py','moss_amd_execution_20261104.py',
            'moss_key_streamed_attention_20261104.py','moss_gpu_cooperative_pacing_20261104.py','score_night_moss_gpu_20261104.py',
            'score_moss_prefix_screening_20261104.py','check_moss_key_streamed_attention_20261104.py','check_moss_key_streamed_gpu_20261104.py',
            'check_moss_resource_controls_20261104.py','check_moss_ram_pressure_guard_20261104.py','check_moss_streamed_weights_20261104.py',
            'check_moss_pcm16_ram_20261104.py','check_moss_system_ram_budget_20261104.py']
        for name in helpers:exact_file(research/'src'/name,(Path('work')/name).read_bytes())
        (research/'.gitignore').write_text('__pycache__/\n*.pyc\n*.safetensors\n*.wav\n*.whl\n.env\n',encoding='utf8')
        (research/'README.md').write_text('''# Companion isolated model research\n\nThis directory preserves research source independently of the installed app. It does not register an application backend, change a product default, or require the application to import PyTorch. Canonical tasks and the full development timeline remain in ../docs; no separate task tree is maintained here.\n\nPinned public model: OpenMOSS-Team/MOSS-Transcribe-Diarize @ 10304d926740cf5a5cee05a268086e3265197910. Author source: OpenMOSS/MOSS-Transcribe-Diarize @ 79c675f0670cc2f824bcbcdd98263704f40f1f7e. Upstream licensing is preserved with upstream source and model configuration. Large public weights/runtime/audio are reconstructible E-drive caches; this C-drive source/Git and safe provenance must be retained.\n\nPrevious R15 completed all 28 full-context prefill layers then stopped on Windows actual low-RAM notification after 224 generated tokens. No complete long-meeting quality result exists. Scripts are recovered from surviving work files, not claimed byte-identical to deleted original commit 8651630f. Restore the same weights/source before testing compatibility, retain the 2GiB model-family private-commit limit and low-memory signal, one model at a time. Do not raise memory budgets or blindly repeat the failed full input. Native Windows AMD runtime is isolated; exact Python/transitive dependencies may differ after cleanup and require a new compatibility receipt. No speaker-reference text/count/hotwords go into inference. The final holdout L_R003S03C02 stays unopened.\n''',encoding='utf8')
        state.update(state='PINNED_AUTHOR_SOURCE_CONFIG_AND_SURVIVING_RESEARCH_SCRIPTS_RESTORED',files=len(files),recoveredHelpers=len(helpers),protectedResearchSource=str(research),assets=str(assets))
    elif args.step=='runtime':
        runtime=night/'amd-runtime';assert not runtime.exists()
        env={k:v for k,v in os.environ.items() if not k.startswith(('COMPANION_','LISTENER_','OPENAI_','HF_TOKEN','HUGGING_FACE_HUB_TOKEN','PYTHONPATH'))}
        env.update(PIP_CACHE_DIR=str(night/'pip-cache'),PIP_DISABLE_PIP_VERSION_CHECK='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
        steps=[]
        commands=[('create-runtime',[sys.executable,'-m','venv',str(runtime)]),
            ('install-amd-torch',[str(runtime/'Scripts/python.exe'),'-m','pip','install','--progress-bar','off','--index-url','https://stable.repo.amd.com/rocm/whl-next/',
                '--extra-index-url','https://pypi.org/simple','--report',str(proof/'amd-install-report.json'),'torch[device-gfx1030]==2.11.0+rocm10.0.0']),
            ('install-model-frontend',[str(runtime/'Scripts/python.exe'),'-m','pip','install','--progress-bar','off','--index-url','https://pypi.org/simple',
                '--report',str(proof/'frontend-install-report.json'),'transformers==5.22.1','librosa==0.11.0','safetensors==0.7.0','soundfile','soxr','scipy','numba','psutil==7.1.3'])]
        for label,command in commands:
            state.update(state='INSTALLING_ISOLATED_RUNTIME',activeStep=label);save();tick=time.perf_counter()
            with (proof/(label+'.log')).open('xb') as out:
                process=subprocess.Popen(command,env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                state['ownedInstallerPid']=process.pid;save();code=process.wait()
            steps.append({'step':label,'exitCode':code,'seconds':round(time.perf_counter()-tick,3)});state['steps']=steps;save();assert code==0,(label,code)
        state.pop('ownedInstallerPid',None);state.pop('activeStep',None)
        state.update(state='ISOLATED_PINNED_TORCH_AND_TRANSFORMERS_INSTALLED_NOT_IMPORTED',runtime=str(runtime),pythonBasis=sys.version,transitiveDependenciesReconstructed=True)
    else:
        assert json.loads((assets/'prepare-state.json').read_text(encoding='utf8'))['modelRevision']==model_rev
        target=assets/'model/model-00000-of-00001.safetensors';assert not target.exists()
        partial=target.with_suffix('.part');start=partial.stat().st_size if partial.exists() else 0
        assert start<expected_bytes
        headers={'Range':f'bytes={start}-'} if start else {}
        with session.get(f'https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize/resolve/{model_rev}/{target.name}',headers=headers,stream=True,timeout=(20,90)) as response:
            response.raise_for_status();assert response.status_code==(206 if start else 200)
            if start:assert response.headers.get('Content-Range','').startswith(f'bytes {start}-')
            with partial.open('ab' if start else 'wb') as out:
                count=start;last=time.perf_counter()
                for chunk in response.iter_content(4*1024*1024):
                    if not chunk:continue
                    out.write(chunk);count+=len(chunk)
                    if time.perf_counter()-last>3:
                        state.update(state='STREAMING_PUBLIC_WEIGHTS',downloadedBytes=count,expectedBytes=expected_bytes);save();last=time.perf_counter()
        assert partial.stat().st_size==expected_bytes
        state.update(state='VERIFYING_PUBLISHED_WEIGHT_SHA256');save()
        with partial.open('rb') as inp:actual=hashlib.file_digest(inp,'sha256').hexdigest()
        assert actual==expected_sha;partial.replace(target)
        state.update(state='PINNED_WEIGHTS_RESTORED_HASH_VERIFIED_NOT_INFERRED',bytes=expected_bytes,sha256=actual,file=str(target))
except BaseException as error:
    state.update(state='RESTORATION_FAILURE_RETAINED',error=repr(error));raise
finally:
    state.update(finishedAt=now(),wallSeconds=round(time.perf_counter()-started,3));save();print(json.dumps(state,ensure_ascii=False),flush=True)
