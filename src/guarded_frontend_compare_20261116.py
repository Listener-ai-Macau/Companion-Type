"""Fixed raw/FRCRN bilingual pairing on the retained native GPU profile.

Raw controls are measured under the same changed runtime as enhanced inputs;
old default-MIOpen outputs are not silently reused as the paired baseline.
"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import argparse
import gc
import hashlib
import json
import os
import sys
import time
import wave

os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from meeting_acoustic_contract_20261116 import read,require,sha,select_gpu
from meeting_acoustic_worker_20261116 import own_limits,present_discrete_gpu,available_ram,exclusive_run
from frontend_component_compare_20261116 import inspect
from companion_windows_power_request_20261115 import PowerLease
from companion_local_pcm_session_20261114 import exclusive_file
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json
from companion_gpu_execution_20261116 import GuardedGpu

now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--phase',choices=['inspect','raw','enhance','asr'],required=True)
    parser.add_argument('--run',type=Path);a=parser.parse_args()
    limits=own_limits(5 if a.phase=='inspect' else 25);P=read(a.protocol);cases=inspect(P)
    require(P['gpuProfile']['cudnnEnabled'] is False and P['trainingUpdates']==0,'Frozen GPU profile required')
    if a.phase=='inspect':
        require('torch' not in sys.modules,'Offline inspection imported torch')
        print(json.dumps({'state':'PASS_GUARDED_PAIRED_FRONTEND_OFFLINE_INPUTS','cases':24,'torchImported':False}));return
    require(a.run is not None,'Explicit output required');run=a.run.resolve();run.mkdir(parents=True,exist_ok=True)
    out=run/a.phase;out.mkdir(exist_ok=False);(out/'results').mkdir()
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),
        'enhancerSha256':P['enhancer']['sha256'],'asrSha256':P['asr']['modelSha256']}
    state={'state':'PREPARING_GUARDED_'+a.phase.upper(),'at':now(),'pid':os.getpid(),'binding':binding,
        'phase':a.phase,'completed':[],'newNeuralCalls':0,'trainingUpdates':0,'referencesRead':False,
        'qualityQualified':False,'saleQualified':False,'currentOperationBudgetSeconds':180}
    pressure=SystemRamPressure();guard=None
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
    def stop():
        require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Original overnight cutoff')
        require(not pressure.low() and available_ram()>=P['minimumAvailableBytes'],'Original RAM protection')
        require(not(run/'stop.request').exists(),'Owned stop requested')
    def pcm(case,dtype):
        with wave.open(case['audio'],'rb') as w:data=w.readframes(w.getnframes())
        return np.frombuffer(data,dtype='<i2').astype(dtype)/32768
    with exclusive_run(run),exclusive_file(Path(P['neuralLock'])),PowerLease():
        try:
            save();state['presentDevices']=present_discrete_gpu();began=time.monotonic()
            while time.monotonic()-began<60:stop();time.sleep(1)
            if a.phase=='enhance':
                gate=read(P['rawAdmissionScore'])
                require(gate['state']=='PASS_SAME_PROFILE_RAW_BILINGUAL_NONREGRESSION'
                    and gate['protocolSha256']==sha(a.protocol),'Raw bilingual same-profile admission not passed')
            import torch
            import numpy as np
            require(torch.__version__==P['runtime']['torch'] and torch.version.hip,'AMD runtime changed')
            torch.set_num_threads(4);torch.set_num_interop_threads(1)
            devices=[]
            for i in range(torch.cuda.device_count()):
                p=torch.cuda.get_device_properties(i);devices.append({'index':i,'name':p.name,'architecture':p.gcnArchName})
            chosen=select_gpu(devices);torch.cuda.set_device(chosen['index']);device='cuda:'+str(chosen['index'])
            from companion_community1_adapter_20261115 import pin_rocm_blas
            pin_rocm_blas(P['blas']['file'],P['blas']['sha256']);save(device=chosen)
            guard=GuardedGpu(torch,out,save,stop,fraction=.25 if a.phase=='enhance' else .5,minimum_ram=P['minimumAvailableBytes'])
            if a.phase=='enhance':
                sys.path.insert(0,P['upstreamRoot']);import official_functions as author
                author.torch=torch
                from frcrn_se.frcrn import FRCRN_SE_16K
                args=SimpleNamespace(win_len=640,win_inc=320,fft_len=640,win_type='hanning',sampling_rate=16000,
                    decode_window=1,one_time_decode_length=120)
                model=FRCRN_SE_16K(args).model
                saved=torch.load(P['enhancer']['file'],map_location='cpu',weights_only=True,mmap=True)
                weights=saved['model'] if 'model' in saved else saved
                if all(k.startswith('module.') for k in weights):weights={k.removeprefix('module.'):v for k,v in weights.items()}
                require(set(model.state_dict())==set(weights),'No partial/random enhancer loading')
                model.load_state_dict(weights,strict=True);model=model.to(device).eval().requires_grad_(False)
                for k,v in model.state_dict().items():require(torch.equal(v.cpu(),weights[k]),'Enhancer tensor differs '+k)
                del weights,saved;gc.collect();guard.attach(model)
                with torch.inference_mode():zero=model.inference(torch.zeros((1,32000),device=device))
                require(zero.shape==(32000,) and torch.count_nonzero(zero)==0,'Exact silence/control shape differs')
                state['newNeuralCalls']+=1;del zero
                inherited=read(P['compatibilityFullClipProof'])
                require(inherited['state']=='PASS_ORIGINAL27S_GPU_NATIVE_CONV_COMPATIBILITY_ONLY'
                    and sha(P['compatibilityWorker'])==inherited['workerSha256'],'Full-clip compatibility proof changed')
                require(inherited['originalProtocolSha256']==sha(P['compatibilityOriginalProtocol']),
                    'Compatibility original configuration changed')
                for case in cases:
                    stop();save(state='ENHANCING_GUARDED_ORIGINAL_PCM',currentId=case['id'])
                    prior=next((r for r in inherited['results'] if r['originalAudioSha256']==case['audioSha256']),None)
                    if prior:
                        source=Path(P['compatibilityFullClipProof']).parent/'results'/(case['id']+'.npy')
                        y=np.load(source,allow_pickle=False)
                        require(y.shape==(case['frames'],) and y.dtype==np.float32
                            and hashlib.sha256(y.tobytes()).hexdigest()==prior['outputSha256']
                            and prior['originalAllFramesAndGainRestored'],'Inherited exact full-clip waveform differs')
                        path=source;seconds=prior['inferenceSeconds'];origin='Inherited verified full-clip forward, not rerun'
                    else:
                        x=pcm(case,np.float64);norm,inverse=author.audio_norm(x);tick=time.perf_counter()
                        with torch.inference_mode():y=author.decode_one_audio_frcrn_se_16k(model,device,norm[None,:],args)
                        torch.cuda.synchronize();seconds=time.perf_counter()-tick
                        require(y.ndim==1 and len(y)>=case['frames'],'Original samples lost')
                        y=np.asarray(y[:case['frames']]*inverse,dtype=np.float32)
                        path=out/'results'/(case['id']+'.npy');np.save(path,y,allow_pickle=False)
                        state['newNeuralCalls']+=1;origin='New frozen-profile enhancement'
                        del x,norm
                    require(np.isfinite(y).all(),'Nonfinite enhanced waveform')
                    state['completed'].append({'id':case['id'],'language':case['language'],'file':str(path),
                        'sha256':sha(path),'frames':case['frames'],'originalAudioSha256':case['audioSha256'],
                        'seconds':seconds,'originalGainRestored':True,'origin':origin})
                    del y;gc.collect();torch.cuda.empty_cache();guard.heartbeat(force=True)
                save(state='COMPLETE_GUARDED_FRCRN24_ALL_FRAMES')
            else:
                import transformers
                require(transformers.__version__==P['runtime']['transformers'],'Transformers changed')
                from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
                from practical_qwen_streamed_loader_20261107 import load_model
                from companion_local_pcm_session_20261114 import parse_generated_tokens
                model,receipt=load_model(P['asr']['modelRoot'],torch=torch,device=device,expected_sha256=P['asr']['modelSha256'])
                model.eval().requires_grad_(False);atomic_json(out/'model-load.json',receipt);guard.attach(model)
                processor=AutoProcessor.from_pretrained(P['asr']['modelRoot'],local_files_only=True)
                inputs=[dict(P['asrControl'],id='native-original-control',kind='control')]
                if a.phase=='raw':inputs += [dict(c,kind='raw') for c in cases]
                else:
                    enhanced=read(run/'enhance/completed.json');raw=read(run/'raw/completed.json')
                    require(enhanced['binding']==binding and raw['binding']==binding
                        and len(enhanced['completed'])==24 and len(raw['completed'])==25,'Incomplete/different pairing')
                    state['enhancementCompletedSha256']=sha(run/'enhance/completed.json')
                    state['rawCompletedSha256']=sha(run/'raw/completed.json')
                    inputs += [dict(c,kind='enhanced') for c in enhanced['completed']]
                for case in inputs:
                    stop();guard.heartbeat(force=True,state='RECOGNIZING_GUARDED_'+a.phase.upper(),currentId=case['id'])
                    if case['kind'] in ('control','raw'):
                        require(sha(case['audio'])==case['audioSha256'],'Original PCM changed')
                        samples=pcm(case,np.float32);audio_sha=case['audioSha256']
                    else:
                        require(sha(case['file'])==case['sha256'],'Enhanced waveform changed')
                        samples=np.load(case['file'],allow_pickle=False);audio_sha=case['sha256']
                    require(samples.dtype==np.float32 and samples.shape==(case['frames'],),'Waveform shape/dtype changed')
                    request=processor.apply_transcription_request(audio=samples,language=case['language'],
                        processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':device}}).to(device,torch.bfloat16)
                    require(int(request['input_features_mask'].sum())>=len(samples)//160,'Waveform truncated')
                    prefix=request['input_ids'].shape[1]
                    class OwnedStop(StoppingCriteria):
                        def __call__(self,input_ids,scores,**kwargs):guard.heartbeat();return False
                    torch.cuda.synchronize();tick=time.perf_counter()
                    with torch.inference_mode():ids=model.generate(**request,max_new_tokens=512,do_sample=False,stopping_criteria=StoppingCriteriaList([OwnedStop()]))
                    torch.cuda.synchronize();seconds=time.perf_counter()-tick
                    generated=ids[0,prefix:].cpu().tolist();eos=model.generation_config.eos_token_id
                    eos=[eos] if isinstance(eos,int) else eos
                    result={'id':case['id'],'kind':case['kind'],'language':case['language'],'binding':binding,
                        'audioSha256':audio_sha,'generatedIds':generated,'naturalEos':bool(generated and generated[-1] in eos),
                        'text':parse_generated_tokens(generated,processor.tokenizer,language=case['language'])['text'],
                        'seconds':seconds,'referenceUsed':False,'wordsPostEdited':False,'trainingUpdates':0}
                    file=out/'results'/(case['id']+'.json');atomic_json(file,result);state['newNeuralCalls']+=1
                    require(result['naturalEos'],'Incomplete decode; no token/window retry')
                    if case['kind']=='control':
                        state['oldDefaultControlExact']=generated==P['asrControlIds']
                        if a.phase=='asr':
                            prior=read(run/'raw/results/native-original-control.json')
                            require(generated==prior['generatedIds'],'Paired same-runtime ASR control drift')
                            state['pairedControlExact']=True
                    state['completed'].append({'id':case['id'],'file':str(file),'sha256':sha(file)})
                    del ids,request,samples;gc.collect();torch.cuda.empty_cache();guard.heartbeat(force=True)
                save(state='COMPLETE_GUARDED_RAW25_PENDING_SCORE' if a.phase=='raw' else 'COMPLETE_GUARDED_ENHANCED25_PENDING_SCORE')
            state['gpuSummary']=guard.close();guard=None;save(currentOperation=None)
            atomic_json(out/'completed.json',state)
        except BaseException as error:
            import traceback
            save(state='FAILED_GUARDED_'+a.phase.upper()+'_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
        finally:
            if guard is not None:guard.close()
            pressure.close()

if __name__=='__main__':main()
