"""Public independent voice representation; no labels or model training."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,sys,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYANNOTE_METRICS_ENABLED='0')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha,pin_rocm_blas
from companion_local_pcm_session_20261114 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    p=argparse.ArgumentParser()
    for name in ['control','inventory','run']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    protocol=read(a.control/'protocol.json');binding=read(a.control/'worker-binding.json')
    assert sha(__file__)==binding['workerSha256'] and sha(a.control/'protocol.json')==binding['protocolSha256']
    for path,digest in binding['helpers'].items():assert sha(path)==digest
    runtime=read(protocol['runtimeManifest']);assert sha(protocol['runtimeManifest'])==protocol['runtimeManifestSha256']
    for item in runtime['files']:assert sha(item['file'])==item['sha256']
    sys.path[:0]=protocol['additionalSites']
    os.environ.update(HF_HOME=str(a.run/'offline-hf-cache'),MPLCONFIGDIR=str(a.run/'matplotlib-cache'))
    state=dict(state='STARTING_PUBLIC_INDEPENDENT_VOICE_DIAGNOSIS',startedAt=datetime.now().astimezone().isoformat(),
               explicitForwardCalls=0,parameterUpdates=0,referenceRead=False,qualityQualified=False)
    began=time.perf_counter()
    def save(**values):
        state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
        atomic_json(a.run/'state.json',state)
    save()
    try:
        inv=read(a.inventory);assert inv['selected']['name']=='AMD Radeon RX 6800 XT'
        assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inv['finishedAt'])).total_seconds()<1800
        import torch,numpy as np
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        assert torch.version.hip and torch.cuda.device_count()==1
        torch.cuda.set_device(0);gpu=torch.cuda.get_device_properties(0)
        assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
        blas=pin_rocm_blas(protocol['rocmBlasLibrary'],protocol['rocmBlasLibrarySha256'])
        model_binding=read(a.control/'model-binding.json');assert model_binding['gated'] is False
        for item in model_binding['files']:assert sha(item['file'])==item['sha256']
        assert sha(a.control/'audio-only.json')==protocol['audioOnlySha256']
        clips=read(a.control/'audio-only.json');assert len(clips)==7
        assert all(set(r)=={'id','audio','audioSha256','audioSeconds'} for r in clips)
        from pyannote.audio import Model
        from pyannote.audio.telemetry.metrics import is_metrics_enabled
        assert not is_metrics_enabled()
        weight=next(i['file'] for i in model_binding['files'] if Path(i['file']).name=='pytorch_model.bin')
        save(state='LOADING_PINNED_PUBLIC_WESPEAKER',gpu=gpu.name,blas=blas,
             modelBindingSha256=sha(a.control/'model-binding.json'),
             modelLoadMayExecuteInternalForwardsNotInstrumented=True)
        model=Model.from_pretrained(weight,map_location='cpu',strict=True,token=False)
        assert model is not None and type(model).__name__=='WeSpeakerResNet34'
        model.eval().requires_grad_(False);assert model.hparams.sample_rate==16000 and model.hparams.num_channels==1
        def audio(row):
            if (a.run/'stop.request').exists():raise InterruptedError('Owned probe stop')
            assert sha(row['audio'])==row['audioSha256']
            with wave.open(row['audio'],'rb') as f:
                assert (f.getframerate(),f.getnchannels(),f.getsampwidth())==(16000,1,2)
                n=f.getnframes();pcm=f.readframes(n)
            assert n/16000==row['audioSeconds']
            return torch.from_numpy(np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768).reshape(1,1,-1)
        captured={};capture_key=['cpu']
        def capture(module,args):captured[capture_key[0]]=args[0].detach().cpu()
        hook=model.resnet.register_forward_pre_hook(capture)
        first=audio(clips[0])
        with torch.inference_mode():cpu=model(first).cpu();state['explicitForwardCalls']+=1
        model.to('cuda:0');capture_key[0]='gpu'
        with torch.inference_mode():initial=model(first.to('cuda:0')).cpu();state['explicitForwardCalls']+=1
        torch.cuda.synchronize();hook.remove()
        assert cpu.shape==initial.shape==(1,256) and torch.isfinite(initial).all()
        diff=(captured['cpu']-captured['gpu']).abs()
        similarity=float(torch.nn.functional.cosine_similarity(cpu,initial).item())
        assert float(diff.max())<=.003 and float(diff.mean())<=.0001 and similarity>=.9999
        save(state='PASS_ACTUAL_CHECKPOINT_CPU_GPU_FEATURE_AND_EMBEDDING_CONTROL',
             maximumFeatureDifference=float(diff.max()),meanFeatureDifference=float(diff.mean()),
             embeddingCpuGpuCosine=similarity,checkpointHyperparameters=dict(model.hparams))
        embeddings=[initial.numpy()[0]]
        for index,row in enumerate(clips[1:],start=1):
            waveform=audio(row).to('cuda:0')
            with torch.inference_mode():value=model(waveform).cpu();state['explicitForwardCalls']+=1
            torch.cuda.synchronize();assert value.shape==(1,256) and torch.isfinite(value).all()
            embeddings.append(value.numpy()[0]);save(state='RUNNING_SEVEN_ANONYMOUS_VOICE_CLIPS',completed=index+1,total=7)
        result=np.stack(embeddings);assert np.isfinite(result).all() and (np.linalg.norm(result,axis=1)>0).all()
        np.save(a.run/'embeddings.npy',result,allow_pickle=False)
        save(state='COMPLETE_PUBLIC_INDEPENDENT_VOICE_EXTRACTOR_DIAGNOSIS_SCORE_PENDING',
             clipIds=[r['id'] for r in clips],embeddingsSha256=sha(a.run/'embeddings.npy'),
             pretrainedWeightsChanged=False,newSpeakerDiarizationProduced=False,referenceAssistedCutsAreDiagnosticOnly=True)
    except BaseException as error:
        save(state='FAILED_PUBLIC_INDEPENDENT_VOICE_PROBE_RETAINED',error=repr(error));raise
    finally:
        state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began)
        atomic_json(a.run/'state.json',state)
        print(json.dumps({k:state.get(k) for k in ['state','error','explicitForwardCalls','seconds']},ensure_ascii=False))

if __name__=='__main__':main()
