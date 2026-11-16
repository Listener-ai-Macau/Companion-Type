"""One fixed pretrained-model microphone diagnostic, inference only.

One unchanged distant-mic native-ID control, then12 official headset-mix clips.
No training, diarization labels, provided speaker counts or reference text.
"""
from pathlib import Path
from datetime import datetime
import argparse
import json
import os
import sys
import time
import wave

os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from meeting_acoustic_contract_20261116 import read,require,select_gpu,sha
from meeting_acoustic_worker_20261116 import available_ram,exclusive_run,own_limits,present_discrete_gpu
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json

now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')


def inspect(protocol):
    for item in protocol['files']:
        require(sha(item['file'])==item['sha256'],'Diagnostic binding changed: '+item['file'])
    timing=read(protocol['timebaseReview'])
    require(protocol['timebaseWithinOriginal100MsBound'] and timing['allPairsPass']
            and len(timing['rows'])==12
            and all(r['withinOriginal100MsTimingBound'] and not r['audioOrReferenceShiftApplied'] for r in timing['rows']),
            'Unresolved microphone-view timebase; do not infer')
    cases=read(protocol['audioOnly'])
    require(len(cases)==13 and len({c['id'] for c in cases})==13,'Fixed13-input diagnostic required')
    require(cases[0]['kind']=='native-distant-control','Exact native control must precede all new inputs')
    require(not any(k in c for c in cases for k in ['reference','referenceText','speaker','speakers','target']), 'Labels leaked into inference')
    for case in cases:
        require(sha(case['audio'])==case['audioSha256'],'Diagnostic PCM changed')
        with wave.open(case['audio'],'rb') as stream:
            require((stream.getnchannels(),stream.getframerate(),stream.getsampwidth(),stream.getnframes())
                    ==(1,16000,2,case['frames']),'Diagnostic audio format/frame mismatch')
    require(protocol['trainingUpdates']==0,'This worker cannot train')
    return cases


def main():
    p=argparse.ArgumentParser(); p.add_argument('--protocol',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect',action='store_true'); mode.add_argument('--execute',action='store_true')
    p.add_argument('--run',type=Path); p.add_argument('--resume',action='store_true'); a=p.parse_args()
    limits=own_limits(5 if a.inspect else 25)
    protocol=read(a.protocol); cases=inspect(protocol)
    if a.inspect:
        result={'state':'PASS_FIXED_MICROPHONE_DIAGNOSTIC_INPUT_INSPECTION_NO_NEURAL_RUNTIME',
                'protocolSha256':sha(a.protocol),'inputs':len(cases),'expectedNewGpuDecodes':13,
                'torchImported':'torch' in sys.modules,'newNeuralCalls':0,'trainingUpdates':0,'limits':limits.query()}
        require(not result['torchImported'],'Inspection imported torch')
        print(json.dumps(result,ensure_ascii=False)); return
    require(a.run is not None,'Explicit diagnostic output directory required')
    run=a.run.resolve(); run.mkdir(parents=True,exist_ok=a.resume)
    (run/'results').mkdir(exist_ok=a.resume)
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),'modelSha256':protocol['modelSha256']}
    state={'state':'PREPARING_INFERENCE_ONLY_MICROPHONE_DIAGNOSTIC','at':now(),'pid':os.getpid(),
           'binding':binding,'newNeuralCalls':0,'trainingUpdates':0,'completed':[],
           'nativeControlExact':False,'qualityQualified':False,'saleQualified':False,
           'scope':'Headset mix is a diagnostic condition, not product single-mic acceptance.'}
    pressure=SystemRamPressure(); model=None
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query())
        atomic_json(run/'state.json',state,progress=True)
    def stop():
        if (run/'stop.request').exists() or pressure.low():
            raise InterruptedError('Owned stop/Windows low RAM; no automatic retry')
    with exclusive_run(run):
        if a.resume and (run/'state.json').exists():
            old=read(run/'state.json'); require(old['binding']==binding,'Diagnostic resume identity changed')
            archive=run/('previous-state-'+sha(run/'state.json')[:16]+'.json')
            if not archive.exists(): archive.write_bytes((run/'state.json').read_bytes())
        try:
            save()
            for case in cases:
                stop(); target=run/'results'/(case['id']+'.json')
                if target.exists():
                    result=read(target)
                    require(result['binding']==binding and result['audioSha256']==case['audioSha256']
                            and result['naturalEos'],'Failed/different cached prefix; refuse retry')
                else:
                    if model is None:
                        state['presentDevices']=present_discrete_gpu()
                        began=time.monotonic()
                        while time.monotonic()-began<60:
                            stop(); require(available_ram()>=protocol['minimumAvailableBytes'],'RAM recovery floor not met')
                            time.sleep(1)
                        import torch
                        import transformers
                        require(torch.__version__==protocol['runtime']['torch'] and torch.version.hip
                                and transformers.__version__==protocol['runtime']['transformers'],'Runtime changed')
                        torch.set_num_threads(4); torch.set_num_interop_threads(1)
                        devices=[]
                        for i in range(torch.cuda.device_count()):
                            prop=torch.cuda.get_device_properties(i)
                            devices.append({'index':i,'name':prop.name,'architecture':getattr(prop,'gcnArchName','')})
                        chosen=select_gpu(devices); device='cuda:'+str(chosen['index']); torch.cuda.set_device(chosen['index'])
                        from companion_community1_adapter_20261115 import pin_rocm_blas
                        pin_rocm_blas(protocol['blas']['file'],protocol['blas']['sha256'])
                        from practical_qwen_streamed_loader_20261107 import load_model
                        from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
                        from companion_local_pcm_session_20261114 import parse_generated_tokens
                        model,loading=load_model(protocol['modelRoot'],torch=torch,device=device,expected_sha256=protocol['modelSha256'])
                        model.eval().requires_grad_(False)
                        require(all(not v.requires_grad for v in model.parameters()),'Inference model acquired trainable parameters')
                        processor=AutoProcessor.from_pretrained(protocol['modelRoot'],local_files_only=True)
                        atomic_json(run/'model-load.json',loading)
                        save(modelLoaded=True,device=chosen)
                    import numpy as np
                    with wave.open(case['audio'],'rb') as stream:
                        pcm=stream.readframes(stream.getnframes())
                    samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
                    inputs=processor.apply_transcription_request(audio=samples,language='English',
                        processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':device}}).to(device,torch.bfloat16)
                    require(int(inputs['input_features_mask'].sum())>=len(samples)//160,'Input features truncated')
                    prefix=inputs['input_ids'].shape[1]
                    class OwnedStop(StoppingCriteria):
                        def __call__(self,input_ids,scores,**kwargs):
                            stop(); return False
                    torch.cuda.synchronize(); began=time.perf_counter()
                    with torch.inference_mode():
                        ids=model.generate(**inputs,max_new_tokens=512,do_sample=False,
                                           stopping_criteria=StoppingCriteriaList([OwnedStop()]))
                    torch.cuda.synchronize(); elapsed=time.perf_counter()-began
                    generated=ids[0,prefix:].cpu().tolist(); eos=model.generation_config.eos_token_id
                    eos=[eos] if isinstance(eos,int) else eos
                    parsed=parse_generated_tokens(generated,processor.tokenizer,language='English')
                    result={'id':case['id'],'caseId':case['caseId'],'kind':case['kind'],
                            'audioSha256':case['audioSha256'],'binding':binding,
                            'generatedIds':generated,'text':parsed['text'],
                            'naturalEos':bool(generated and generated[-1] in eos),'seconds':elapsed,
                            'referenceUsed':False,'trainingUpdates':0,'wordsPostEdited':False}
                    atomic_json(target,result); state['newNeuralCalls']+=1
                    del ids,inputs,samples,pcm
                    require(result['naturalEos'],'Failed pretrained decode retained; do not alter parameters/windows and retry')
                if case['kind']=='native-distant-control':
                    require(result['generatedIds']==protocol['expectedControlIds'],'Unchanged native control differs; stop before interpreting microphone comparison')
                    state['nativeControlExact']=True
                else:
                    require(state['nativeControlExact'],'Missing exact native control')
                state['completed'].append({'id':case['id'],'file':str(target),'sha256':sha(target)})
                save(state='RUNNING_FIXED_PRETRAINED_MICROPHONE_DIAGNOSTIC')
            save(state='COMPLETE_PRETRAINED_MICROPHONE_DIAGNOSTIC_PENDING_INDEPENDENT_SCORING')
            atomic_json(run/'completed.json',state)
        except BaseException as error:
            import traceback
            save(state='FAILED_PRETRAINED_DIAGNOSTIC_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
            raise
        finally:
            save(finishedAt=now()); pressure.close()


if __name__=='__main__': main()
