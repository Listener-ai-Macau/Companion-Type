"""Independent, bounded CPU reference for the already selected diarizer.

Two fixed original61s prefixes, same published checkpoint and author offline
geometry. Compare only complete chunks against retained780M outputs. No labels,
training, speaker permutation fitting, threshold adjustment or default change.
"""
from pathlib import Path
from datetime import datetime
import argparse,ctypes,hashlib,json,os,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate,SystemRamPressure
from companion_local_pcm_session_20261114 import exclusive_file
from durable_model_state_20261117 import atomic_json
import psutil

read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    run=a.run.resolve();P=read(run/'protocol.json');out=run/'reference';out.mkdir(exist_ok=False)
    assert P['cpuBudgetOwnerQuote']=='允许约 25% CPU，继续后台实测' and not P['training']
    limits=WorkerLimits(cpu_percent=5,memory_bytes=P['privateCommitBytes']);rate=CpuRate(5,2500)
    limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
    assert limits.query()['cpuRate']==2500 and P['torchThreads']==4
    pressure=SystemRamPressure();tick=time.perf_counter();last_save=0
    state={'state':'PREPARING_CPU_REFERENCE_FIDELITY_CONTROL','startedAt':datetime.now().astimezone().isoformat(),
        'pid':os.getpid(),'protocolSha256':sha(run/'protocol.json'),'workerSha256':sha(__file__),
        'newEncoderLayerCalls':0,'parameterUpdates':0,'referenceLabelsRead':False,'cases':[],
        'gpuInitialized':False,'cpuTemperatureMode':P['cpuTemperatureMode'],'qualityQualified':False}
    def save(**values):
        state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
        atomic_json(out/'state.json',state,progress=True)
    def stop():
        assert not pressure.low() and psutil.virtual_memory().available>=P['minimumAvailableBytes'],'Original realRAM guard'
        assert datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Bounded reference deadline'
        assert not (run/'stop.request').exists(),'Owned reference stop requested'
    try:
        with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
            for p,digest in P['dependencies'].items():assert sha(p)==digest,'Frozen implementation changed'
            root=Path(P['modelRoot'])
            for name,info in P['files'].items():assert sha(root/name)==info['sha256']
            save();began=time.monotonic()
            while time.monotonic()-began<P['ramStableSeconds']:stop();time.sleep(1)
            save(state='IMPORTING_EXISTING_CPU_REFERENCE_RUNTIME')
            import torch
            from companion_community1_adapter_20261115 import pin_rocm_blas
            state['cpuBlasThreadPin']=pin_rocm_blas(P['cpuBlas']['file'],P['cpuBlas']['sha256'])
            torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
            import numpy as np
            from transformers import AutoModelForAudioFrameClassification,AutoProcessor
            assert not torch.cuda.is_initialized()
            stop();save(state='LOADING_INDEPENDENT_PUBLISHED_MODEL_CPU_ONLY')
            processor=AutoProcessor.from_pretrained(root,local_files_only=True)
            model=AutoModelForAudioFrameClassification.from_pretrained(root,local_files_only=True,
                dtype=torch.float32,attn_implementation=P['attentionImplementation']).eval().requires_grad_(False)
            assert all(v.device.type=='cpu' for v in list(model.parameters())+list(model.buffers()))
            assert not torch.cuda.is_initialized() and not model.training
            cfg=model.config
            applied={k:getattr(cfg,k) for k in P['geometry'] if k!='speaker_cache_length'}
            applied['speaker_cache_length']=cfg.streaming_config.speaker_cache_length
            assert applied==P['geometry'],'Original author offline configuration changed'
            state.update(appliedGeometry=applied,modelClass=type(model).__name__,
                processorClass=type(processor).__name__,parameters=sum(v.numel() for v in model.parameters()),
                modelDtypes=sorted({str(v.dtype) for v in model.parameters()}),torchVersion=torch.__version__)
            def parameter_digest():
                h=hashlib.sha256()
                for name,value in model.named_parameters():
                    h.update(name.encode()+b'\0');h.update(memoryview(value.detach().contiguous().numpy()).cast('B'))
                return h.hexdigest()
            before=parameter_digest()
            def layer_finished(module,args,output):
                nonlocal last_save
                state['newEncoderLayerCalls']+=1;stop()
                if time.monotonic()-last_save>=5:
                    save(state='RUNNING_FIXED_CPU_REFERENCE');last_save=time.monotonic()
            handles=[layer.register_forward_hook(layer_finished) for layer in model.model.audio_tower.layers]
            for case in P['cases']:
                stop();assert sha(case['audio'])==case['audioSha256']
                with wave.open(case['audio'],'rb') as f:
                    assert (f.getframerate(),f.getnchannels(),f.getsampwidth(),f.getnframes())==(16000,1,2,case['frames'])
                    pcm=f.readframes(f.getnframes())
                assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
                samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
                folder=out/case['id'];folder.mkdir();state['currentCase']=case['id'];save()
                inputs=processor(samples,sampling_rate=16000,return_tensors='pt')
                assert inputs['input_features'].dtype==torch.float32
                np.save(folder/'input-features.npy',inputs['input_features'].numpy(),allow_pickle=False)
                case_tick=time.perf_counter();calls_before=state['newEncoderLayerCalls']
                with torch.inference_mode():output=model(**inputs)
                probabilities=output.logits.sigmoid().cpu().numpy()[0]
                assert probabilities.ndim==2 and probabilities.shape[1]==8 and np.isfinite(probabilities).all()
                np.save(folder/'probabilities.npy',probabilities,allow_pickle=False)
                assert sha(case['nativeManifest'])==case['nativeManifestSha256']
                manifest=read(case['nativeManifest']);assert manifest['committedFrames']>=case['comparePrefixFrames']
                native=np.load(case['nativeProbabilities'],mmap_mode='r',allow_pickle=False)
                n=case['comparePrefixFrames'];reference=probabilities[:n];baseline=native[:n]
                assert reference.shape==baseline.shape==(5440,8)
                def compare(left,right):
                    delta=np.abs(left-right);disagreement=np.not_equal(left>.5,right>.5)
                    return {'values':int(delta.size),'maxAbsolutePosteriorDifference':float(delta.max()),
                        'meanAbsolutePosteriorDifference':float(delta.mean()),
                        'activityDisagreements':int(disagreement.sum()),'activityDisagreementFraction':float(disagreement.mean())}
                stats=compare(reference,baseline);rule=P['diagnosticBranchRule']
                material=(stats['activityDisagreementFraction']>rule['materialActivityDisagreementFraction']
                    or stats['meanAbsolutePosteriorDifference']>rule['materialMeanAbsolutePosteriorDifference'])
                row={'id':case['id'],'sourceFrames':case['frames'],'outputFrames':len(probabilities),'comparedFrames':n,
                    'inferenceSeconds':time.perf_counter()-case_tick,'encoderLayerCalls':state['newEncoderLayerCalls']-calls_before,
                    'comparison':stats,'completeChunkComparisons':[compare(reference[:2720],baseline[:2720]),compare(reference[2720:],baseline[2720:])],
                    'materialImplementationDiscrepancy':material,'comparisonPerformedWithoutSpeakerPermutation':True,
                    'frontendWeightPrecisionImplementationNotYetIsolated':material,
                    'referenceFeaturesSha256':sha(folder/'input-features.npy'),'referenceProbabilitiesSha256':sha(folder/'probabilities.npy'),
                    'qualityScoreMeasured':False,'parameterUpdates':0}
                atomic_json(folder/'result.json',row);state['cases'].append(row);save()
                print(json.dumps({'id':case['id'],'comparison':stats,'materialDiscrepancy':material}),flush=True)
                del output,inputs,probabilities,reference,baseline,native
            for handle in handles:handle.remove()
            assert parameter_digest()==before and not torch.cuda.is_initialized()
            state.update(state='COMPLETE_INDEPENDENT_DIARIZER_REFERENCE_FIDELITY_CONTROL',
                modelParameterDigestBefore=before,modelParameterDigestAfter=before,gpuInitialized=False,
                diagnosisRequiredBeforeDiarizerTraining=any(r['materialImplementationDiscrepancy'] for r in state['cases']),
                qualityQualified=False,originalNativeBaselineChanged=False)
    except BaseException as error:
        state.update(state='FAILED_CPU_REFERENCE_PARTIAL_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        pressure.close();save(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick)
        atomic_json(out/'completed.json',state)
        print(json.dumps({'state':state['state'],'newEncoderLayerCalls':state['newEncoderLayerCalls'],'privatePeakBytes':state['limits']['jobPeakPrivateCommitBytes']}),flush=True)

if __name__=='__main__':main()
