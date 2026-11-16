"""One fixed official FRCRN frontend before unchanged native Qwen ASR.

Separate exclusive GPU phases; originals, all frames and all generated words
remain intact. No optimization, waveform search, or reference text input.
"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import argparse
import gc
import json
import os
import sys
import time
import wave

os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from meeting_acoustic_contract_20261116 import read,require,sha,select_gpu
from meeting_acoustic_worker_20261116 import own_limits,present_discrete_gpu,available_ram,exclusive_run
from companion_windows_power_request_20261115 import PowerLease
from companion_local_pcm_session_20261114 import exclusive_file
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json

now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')


def inspect(P):
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen frontend dependency changed: '+item['file'])
    cases=read(P['audioOnly'])
    require(len(cases)==24 and len({c['id'] for c in cases})==24,'Fixed24 validation inputs required')
    require(sum(c['language']=='English' for c in cases)==12 and sum(c['language']=='Chinese' for c in cases)==12,
            'Fixed bilingual cohort changed')
    for case in cases:
        require(set(case)=={'id','language','audio','audioSha256','frames'},'Reference/speaker hint entered inference')
        require(sha(case['audio'])==case['audioSha256'],'Original validation PCM changed')
        with wave.open(case['audio'],'rb') as w:
            require((w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getnframes())==(1,16000,2,case['frames']),
                    'Original mono PCM frame count/format changed')
    require(P['trainingUpdates']==0,'This comparison cannot train')
    return cases


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--phase',choices=['inspect','enhance','asr'],required=True);p.add_argument('--run',type=Path)
    a=p.parse_args();limits=own_limits(5 if a.phase=='inspect' else 25)
    P=read(a.protocol);cases=inspect(P)
    if a.phase=='inspect':
        require('torch' not in sys.modules,'Inspection imported torch')
        print(json.dumps({'state':'PASS_FIXED_FRCRN_FRONTEND_OFFLINE_INPUT_INSPECTION',
            'cases':24,'torchImported':False,'newNeuralCalls':0,'trainingUpdates':0,'limits':limits.query()}));return
    require(a.run is not None,'Explicit experiment output required')
    run=a.run.resolve();run.mkdir(parents=True,exist_ok=True)
    out=run/a.phase;out.mkdir(exist_ok=False);(out/'results').mkdir()
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),
             'enhancerSha256':P['enhancer']['sha256'],'asrSha256':P['asr']['modelSha256']}
    state={'state':'PREPARING_FIXED_FRONTEND_'+a.phase.upper(),'at':now(),'pid':os.getpid(),
        'binding':binding,'phase':a.phase,'completed':[],'newNeuralCalls':0,'trainingUpdates':0,
        'referencesRead':False,'qualityQualified':False,'saleQualified':False}
    pressure=SystemRamPressure()
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
    def check_stop():
        require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Overnight comparison deadline reached')
        if pressure.low() or (run/'stop.request').exists():raise InterruptedError('Owned stop/Windows low RAM; preserve completed outputs')
    def pcm(case,dtype):
        with wave.open(case['audio'],'rb') as w:data=w.readframes(w.getnframes())
        return np.frombuffer(data,dtype='<i2').astype(dtype)/32768
    with exclusive_run(run),exclusive_file(Path(P['neuralLock'])),PowerLease():
        try:
            save();state['presentDevices']=present_discrete_gpu();began=time.monotonic()
            while time.monotonic()-began<60:
                check_stop();require(available_ram()>=P['minimumAvailableBytes'],'Original3.18GiB RAM floor not met')
                time.sleep(1)
            import torch
            import numpy as np
            require(torch.__version__==P['runtime']['torch'] and torch.version.hip,'Frozen AMD runtime changed')
            torch.set_num_threads(4);torch.set_num_interop_threads(1)
            inventory=[]
            for i in range(torch.cuda.device_count()):
                prop=torch.cuda.get_device_properties(i)
                inventory.append({'index':i,'name':prop.name,'architecture':getattr(prop,'gcnArchName','')})
            chosen=select_gpu(inventory);device='cuda:'+str(chosen['index']);torch.cuda.set_device(chosen['index'])
            from companion_community1_adapter_20261115 import pin_rocm_blas
            pin_rocm_blas(P['blas']['file'],P['blas']['sha256']);save(device=chosen)
            if a.phase=='enhance':
                sys.path.insert(0,P['upstreamRoot'])
                import official_functions as author
                author.torch=torch
                from frcrn_se.frcrn import FRCRN_SE_16K
                args=SimpleNamespace(win_len=640,win_inc=320,fft_len=640,win_type='hanning',
                    sampling_rate=16000,decode_window=1,one_time_decode_length=120)
                model=FRCRN_SE_16K(args).model
                saved=torch.load(P['enhancer']['file'],map_location='cpu',weights_only=True,mmap=True)
                weights=saved['model'] if 'model' in saved else saved
                require(isinstance(weights,dict),'Unsupported official checkpoint structure')
                if weights and all(k.startswith('module.') for k in weights):
                    weights={k.removeprefix('module.'):v for k,v in weights.items()}
                require(set(model.state_dict())==set(weights),'Official enhancer checkpoint keys differ; no partial/random loading')
                model.load_state_dict(weights,strict=True);model=model.to(device).eval().requires_grad_(False)
                loaded=model.state_dict()
                for key,tensor in weights.items():
                    require(torch.equal(loaded[key].cpu(),tensor),'Official enhancer tensor reload differs: '+key)
                proof={'state':'PASS_ALL_OFFICIAL_FRCRN_TENSORS_RELOADED_EXACT',
                    'tensorCount':len(weights),'checkpointSha256':P['enhancer']['sha256'],
                    'partialMissingOrUnexpectedKeys':False,'parameters':sum(v.numel() for v in model.parameters()),
                    'trainingUpdates':0,'device':chosen}
                atomic_json(out/'weight-proof.json',proof)
                del loaded,weights,saved;gc.collect()
                require(all(not p.requires_grad for p in model.parameters()),'Enhancer acquired trainable weights')
                # Verify the published STFT/iSTFT preserves the sample timebase
                # on speech, and the loaded enhancer preserves exact silence.
                probe=pcm(cases[0],np.float64)[:32000];norm,_=author.audio_norm(probe)
                tensor=torch.from_numpy(norm.astype(np.float32)[None,:]).to(device)
                with torch.inference_mode():
                    restored=model.istft(model.stft(tensor)).squeeze(1)
                    # The published convolutions are non-centered and unpadded.
                    # Their Hann window has zero support at sample0; the inverse
                    # divides by overlap coefficients plus1e-8. An exact identity
                    # expectation at every endpoint is therefore incorrect.
                    # Independently compute that defined operator in NumPy,
                    # retaining the same tolerance and original sample indices.
                    window=model.istft.window.detach().cpu().numpy().reshape(-1)
                    coefficients=np.zeros(32000,dtype=np.float32)
                    for start in range(0,32000-640+1,320):coefficients[start:start+640]+=window**2
                    expected=norm.astype(np.float32)[None,:]*coefficients[None,:]/(coefficients[None,:]+1e-8)
                    actual=restored.detach().cpu().numpy()
                    same_shape=actual.shape==expected.shape
                    maximum=float(np.max(np.abs(actual-expected))) if same_shape else None
                    atomic_json(out/'dsp-roundtrip-inspection.json',{'state':'INSPECTED_PUBLISHED_NONCENTERED_STFT_OPERATOR',
                        'inputShape':list(tensor.shape),'outputShape':list(actual.shape),
                        'maximumAbsDifferenceFromIndependentDefinedOperator':maximum,
                        'zeroWindowSupportSamples':int(np.count_nonzero(coefficients==0)),
                        'maximumAbsDifferenceFromUnwindowedIdentity':float(np.max(np.abs(actual-norm[None,:]))) if same_shape else None,
                        'firstInputSample':float(norm[0]),'unchangedAbsoluteTolerance':1e-4,
                        'audioInputShiftPaddingOrGainChangeApplied':False})
                    require(same_shape and np.allclose(actual,expected,atol=1e-4,rtol=1e-4),
                            'Official STFT differs from independent non-centered window operator')
                    zero=model.inference(torch.zeros_like(tensor))
                    require(zero.shape==(32000,) and torch.count_nonzero(zero)==0,'Official enhancer silence/control length failed')
                state['newNeuralCalls']+=1
                atomic_json(out/'dsp-control.json',{'state':'PASS_OFFICIAL_STFT_SPEECH_ROUNDTRIP_AND_EXACT_ZERO_ENHANCER',
                    'speechMaximumAbsRoundtripError':maximum,
                    'referenceOperator':'Independent NumPy non-centered Hann overlap coefficients with published1e-8 inverse denominator; unsupported endpoints included as zero support.',
                    'frames':32000,'timeShiftApplied':False,'sampleRate':16000,'newEnhancerForwards':1})
                del tensor,restored,zero
                for case in cases:
                    check_stop();save(state='ENHANCING_FIXED_ORIGINAL_PCM',currentId=case['id'])
                    x=pcm(case,np.float64);norm,inverse=author.audio_norm(x)
                    require(np.isfinite(norm).all() and np.isfinite(inverse),'Official normalization produced invalid values')
                    torch.cuda.synchronize();tick=time.perf_counter()
                    with torch.inference_mode():
                        y=author.decode_one_audio_frcrn_se_16k(model,device,norm[None,:],args)
                    torch.cuda.synchronize();seconds=time.perf_counter()-tick
                    require(y.ndim==1 and len(y)>=case['frames'],'Official enhancement lost original samples')
                    y=np.asarray(y[:case['frames']]*inverse,dtype=np.float32)
                    require(np.isfinite(y).all(),'Nonfinite enhanced waveform')
                    path=out/'results'/(case['id']+'.npy');np.save(path,y,allow_pickle=False)
                    item={'id':case['id'],'language':case['language'],'file':str(path),'sha256':sha(path),
                        'frames':len(y),'originalAudioSha256':case['audioSha256'],
                        'seconds':seconds,'absolutePeak':float(np.max(np.abs(y))),
                        'inverseOfficialNormalizationScalar':float(inverse),
                        'originalGainRestored':True,'timeShiftResampleVadOrWordMask':False,
                        'format':'F32 NumPy waveform, no clipping or extra PCM16 quantization'}
                    state['completed'].append(item);state['newNeuralCalls']+=1
                    del x,norm,y;gc.collect();torch.cuda.empty_cache();save()
                save(state='COMPLETE_FIXED_OFFICIAL_FRCRN_INPUTS_NO_ASR_SCORE')
            else:
                enhanced=read(run/'enhance/completed.json')
                require(enhanced['binding']==binding and len(enhanced['completed'])==24
                    and enhanced['state']=='COMPLETE_FIXED_OFFICIAL_FRCRN_INPUTS_NO_ASR_SCORE',
                    'Incomplete/different official enhancement phase')
                state['enhancementCompletedSha256']=sha(run/'enhance/completed.json')
                import transformers
                require(transformers.__version__==P['runtime']['transformers'],'Frozen ASR runtime changed')
                from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
                from practical_qwen_streamed_loader_20261107 import load_model
                from companion_local_pcm_session_20261114 import parse_generated_tokens
                model,receipt=load_model(P['asr']['modelRoot'],torch=torch,device=device,expected_sha256=P['asr']['modelSha256'])
                model.eval().requires_grad_(False);atomic_json(out/'model-load.json',receipt)
                processor=AutoProcessor.from_pretrained(P['asr']['modelRoot'],local_files_only=True)
                inputs=[dict(P['asrControl'],kind='unchanged-native-control')]
                inputs += [dict(c,kind='official-enhanced-input') for c in enhanced['completed']]
                for case in inputs:
                    check_stop();save(state='RECOGNIZING_FIXED_ENHANCED_INPUTS',currentId=case['id'])
                    if case['kind']=='unchanged-native-control':
                        require(sha(case['audio'])==case['audioSha256'],'Original native ASR control changed')
                        samples=pcm(case,np.float32);audio_sha=case['audioSha256']
                    else:
                        require(sha(case['file'])==case['sha256'],'Enhanced waveform changed')
                        samples=np.load(case['file'],allow_pickle=False);audio_sha=case['sha256']
                    require(samples.shape==(case['frames'],) and samples.dtype==np.float32,'Waveform frames/dtype changed')
                    request=processor.apply_transcription_request(audio=samples,language=case['language'],
                        processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':device}}).to(device,torch.bfloat16)
                    require(int(request['input_features_mask'].sum())>=len(samples)//160,'Native ASR truncated waveform')
                    prefix=request['input_ids'].shape[1]
                    class OwnedStop(StoppingCriteria):
                        def __call__(self,input_ids,scores,**kwargs):check_stop();return False
                    torch.cuda.synchronize();tick=time.perf_counter()
                    with torch.inference_mode():
                        ids=model.generate(**request,max_new_tokens=512,do_sample=False,
                            stopping_criteria=StoppingCriteriaList([OwnedStop()]))
                    torch.cuda.synchronize();seconds=time.perf_counter()-tick
                    generated=ids[0,prefix:].cpu().tolist();eos=model.generation_config.eos_token_id
                    eos=[eos] if isinstance(eos,int) else eos
                    text=parse_generated_tokens(generated,processor.tokenizer,language=case['language'])['text']
                    result={'id':case['id'],'kind':case['kind'],'language':case['language'],'binding':binding,
                        'audioSha256':audio_sha,'generatedIds':generated,'text':text,
                        'naturalEos':bool(generated and generated[-1] in eos),'seconds':seconds,
                        'trainingUpdates':0,'wordsPostEdited':False,'referenceUsed':False}
                    file=out/'results'/(case['id']+'.json');atomic_json(file,result)
                    state['newNeuralCalls']+=1
                    require(result['naturalEos'],'ASR output incomplete; retain raw result without changed retries')
                    if case['kind']=='unchanged-native-control':
                        require(generated==P['asrControlIds'],'Unchanged ASR control differs; stop enhanced comparison')
                        state['nativeControlExact']=True
                    else:require(state.get('nativeControlExact'),'Missing native ASR control')
                    state['completed'].append({'id':case['id'],'file':str(file),'sha256':sha(file)})
                    del request,ids,samples;gc.collect();torch.cuda.empty_cache();save()
                save(state='COMPLETE_FIXED_OFFICIAL_FRCRN_ASR_PENDING_INDEPENDENT_SCORING')
            atomic_json(out/'completed.json',state)
        except BaseException as error:
            import traceback
            save(state='FAILED_FIXED_FRONTEND_'+a.phase.upper()+'_RETAINED_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
            raise
        finally:save(finishedAt=now());pressure.close()


if __name__=='__main__':main()
