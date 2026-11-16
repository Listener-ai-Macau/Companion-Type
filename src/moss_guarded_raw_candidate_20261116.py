"""One pretrained native MOSS recipe, fixed180s context, no learned changes.

Replays the retained native180s generated-ID control, then covers complete
original recordings exactly once. Per-block speaker IDs are local only.
"""
from pathlib import Path
from datetime import datetime
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
from moss_windows_resource_limits_20261104 import SystemRamPressure
from companion_windows_power_request_20261115 import PowerLease
from companion_local_pcm_session_20261114 import exclusive_file
from practical_io_20261107 import atomic_json
from companion_gpu_execution_20261116 import GuardedGpu

now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')


def inspect(protocol):
    for item in protocol['files']:
        require(sha(item['file'])==item['sha256'],'Frozen context180 binding changed: '+item['file'])
    sources=read(protocol['audioOnly'])
    require(len(sources)==4 and protocol['contextFrames']==2880000 and protocol['trainingUpdates']==0,
            'Fixed original four-source180s inference recipe required')
    for source in sources:
        require(set(source)=={'meeting','audio','audioSha256','audioSeconds','frames'},'Labels entered inference source')
        require(sha(source['audio'])==source['audioSha256'],'Original whole source changed')
        with wave.open(source['audio'],'rb') as w:
            require((w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,source['frames']),
                    'Original source format/frame count changed')
    return sources


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect',action='store_true');mode.add_argument('--phase',choices=['inference'])
    p.add_argument('--run',type=Path);p.add_argument('--meetings',nargs='+');p.add_argument('--resume',action='store_true')
    a=p.parse_args();limits=own_limits(5 if a.inspect else 25);P=read(a.protocol);sources=inspect(P)
    if a.inspect:
        require('torch' not in sys.modules,'Inspection imported neural runtime')
        print(json.dumps({'state':'PASS_NATIVE_CONTEXT180_OFFLINE_INPUT_INSPECTION','sources':4,
                          'torchImported':False,'trainingUpdates':0,'limits':limits.query()}));return
    a.meetings=a.meetings or P['admittedMeetings']
    require(a.run is not None and a.meetings,'Explicit run and source subset required')
    chosen=[next((s for s in sources if s['meeting']==name),None) for name in a.meetings]
    require(all(chosen) and len(set(a.meetings))==len(a.meetings),'Unknown/duplicate source')
    run=a.run.resolve();run.mkdir(parents=True,exist_ok=True);(run/'results').mkdir(exist_ok=a.resume)
    monitor=run/'inference';monitor.mkdir(exist_ok=a.resume)
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),
             'nativeCheckpointSha256':P['nativeCheckpointSha256'],'authorCheckpointSha256':P['authorCheckpointSha256']}
    state={'state':'PREPARING_PRETRAINED_NATIVE_CONTEXT180','at':now(),'pid':os.getpid(),
           'binding':binding,'meetings':a.meetings,'completedBlocks':[],'completedMeetings':[],
           'nativeControlExact':False,'newNeuralCalls':0,'trainingUpdates':0,
           'speakerIdentityScope':'Local to each180s block; not a continuous whole-meeting identity claim.',
           'qualityQualified':False,'saleQualified':False,'referencesRead':False,
           'currentOperationBudgetSeconds':180}
    pressure=SystemRamPressure();model=None;guard=None
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query());atomic_json(run/'state.json',state,progress=True)
        atomic_json(monitor/'state.json',state,progress=True)
    def check_stop():
        require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Overnight inference deadline reached')
        if pressure.low() or (run/'stop.request').exists():
            raise InterruptedError('Owned stop/Windows low memory; preserve every committed output')
    with exclusive_run(run),exclusive_file(Path(P['neuralLock'])),PowerLease():
        if a.resume and (run/'state.json').exists():
            old=read(run/'state.json');require(old['binding']==binding and old['meetings']==a.meetings,'Resume identity changed')
            archive=run/('previous-state-'+sha(run/'state.json')[:16]+'.json')
            if not archive.exists():archive.write_bytes((run/'state.json').read_bytes())
        try:
            save();state['presentDevices']=present_discrete_gpu()
            began=time.monotonic()
            while time.monotonic()-began<60:
                check_stop();require(available_ram()>=P['minimumAvailableBytes'],'Original3.18GiB RAM admission floor not met')
                time.sleep(1)
            import torch
            import transformers
            require(torch.__version__==P['runtime']['torch'] and transformers.__version__==P['runtime']['transformers']
                    and torch.version.hip,'Native runtime changed')
            torch.set_num_threads(4);torch.set_num_interop_threads(1)
            devices=[]
            for index in range(torch.cuda.device_count()):
                prop=torch.cuda.get_device_properties(index)
                devices.append({'index':index,'name':prop.name,'architecture':getattr(prop,'gcnArchName','')})
            selected=select_gpu(devices);device='cuda:'+str(selected['index']);torch.cuda.set_device(selected['index'])
            from companion_community1_adapter_20261115 import pin_rocm_blas
            pin_rocm_blas(P['blas']['file'],P['blas']['sha256'])
            guard=GuardedGpu(torch,run,save,check_stop,fraction=.5,minimum_ram=P['minimumAvailableBytes'])
            from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
            from moss_native_architecture_20261115 import load_public_native
            processor=AutoProcessor.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
            save(state='LOADING_NATIVE_PRETRAINED_CONTEXT180',device=selected,currentOperationBudgetSeconds=180)
            model,receipt=load_public_native(P['nativeControl'],P['modelRoot'],torch=torch,device=device)
            model.eval().requires_grad_(False);guard.attach(model)
            require(all(not p.requires_grad for p in model.parameters()),'Model unexpectedly trainable')
            atomic_json(run/'model-load.json',receipt)
            import numpy as np

            def decode(case,start,end,identifier,kind):
                check_stop();file=run/'results'/(identifier+'.json')
                if file.exists():
                    packet=read(file)
                    require(packet['binding']==binding and packet['audioSha256']==case['audioSha256']
                            and (packet['startFrame'],packet['endFrame'])==(start,end)
                            and packet['naturalEos'],'Failed/different cached decode; refuse automatic retry')
                    return packet,file
                require(datetime.now().astimezone()<datetime.fromisoformat(P['latestDecodeStart']),
                        'Too late to admit another overnight decode')
                with wave.open(case['audio'],'rb') as w:
                    w.setpos(start);pcm=w.readframes(end-start)
                require(len(pcm)==(end-start)*2,'Incomplete original PCM interval')
                samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
                inputs=processor.apply_transcription_request(audio=samples,
                    processor_kwargs={'audio_kwargs':{'sampling_rate':16000}}).to(device,torch.bfloat16)
                require(int(inputs['padding_mask'].sum())==end-start,'Native request truncated original audio')
                prefix=inputs['input_ids'].shape[1];tick=time.perf_counter();last=[0.]
                class OwnedStop(StoppingCriteria):
                    def __call__(self,input_ids,scores,**kwargs):
                        guard.heartbeat();require(time.perf_counter()-tick<=P['maximumDecodeSeconds'],'Fixed decode exceeded admission time budget')
                        count=input_ids.shape[1]-prefix
                        if time.monotonic()-last[0]>=15:
                            save(state='DECODING_NATIVE_CONTEXT180',currentId=identifier,currentGeneratedTokens=count)
                            atomic_json(run/'current-partial.json',{'id':identifier,'binding':binding,
                                'generatedIds':input_ids[0,prefix:].cpu().tolist(),'notFinal':True})
                            last[0]=time.monotonic()
                        return False
                torch.cuda.synchronize()
                with torch.inference_mode():
                    ids=model.generate(**inputs,max_new_tokens=4096,do_sample=False,logits_to_keep=1,
                                       stopping_criteria=StoppingCriteriaList([OwnedStop()]))
                torch.cuda.synchronize();seconds=time.perf_counter()-tick
                generated=ids[0,prefix:].cpu().tolist();eos=model.generation_config.eos_token_id
                eos=[eos] if isinstance(eos,int) else eos
                raw=processor.tokenizer.decode(generated,skip_special_tokens=False,clean_up_tokenization_spaces=False)
                packet={'id':identifier,'meeting':case['meeting'],'kind':kind,'binding':binding,
                    'audioSha256':case['audioSha256'],'startFrame':start,'endFrame':end,
                    'frames':end-start,'audioSeconds':(end-start)/16000,'generatedIds':generated,
                    'rawDecoded':raw,'naturalEos':bool(generated and generated[-1] in eos),
                    'seconds':seconds,'trainingUpdates':0,'referenceUsed':False,
                    'noGainDenoiseResamplingOrVad':True,'speakerIdsAreLocalToBlock':True}
                atomic_json(file,packet);state['newNeuralCalls']+=1
                del inputs,ids,samples,pcm,generated;gc.collect();torch.cuda.empty_cache()
                require(packet['naturalEos'],'Incomplete pretrained output retained; no changed-token/window retries')
                return packet,file

            proof=read(P['runtimeControlProof']);control=P['control']
            require(proof['lexicalUnitsExact'] and not proof['generatedIdsExact']
                and proof['oldLexicalUnitsSha256']==proof['newLexicalUnitsSha256'],
                'New-runtime raw lexical control is not stable')
            source=proof['newControl'];require(sha(source['file'])==source['sha256'],'Retained new-runtime control changed')
            packet=read(source['file'])
            require(packet['naturalEos'] and packet['audioSha256']==control['audioSha256']
                and packet['frames']==control['frames']
                and packet['binding']['nativeCheckpointSha256']==P['nativeCheckpointSha256'],
                'Retained runtime control audio/weights differ')
            state.update(nativeControlExact=False,nativeRawTextControlExact=True,
                runtimeControlProofSha256=sha(P['runtimeControlProof']),
                inheritedControlFile=source['file'],inheritedControlSha256=source['sha256'],
                originalStrictControlFailureRetained=True,
                controlScope='Only raw lexical output451units stable; generated timestamp tokens differ. No timestamp/identity equivalence or product accuracy claim.')
            save(state='RAW_TEXT_CONTROL_VALIDATED_NONIDENTICAL_RUNTIME_CANDIDATE')
            for case in chosen:
                meeting=case['meeting'];blocks=[]
                for index,start in enumerate(range(0,case['frames'],P['contextFrames'])):
                    end=min(case['frames'],start+P['contextFrames']);identifier=meeting+'-context180-'+format(index,'04d')
                    packet,file=decode(case,start,end,identifier,'complete-original-source-block')
                    item={'id':identifier,'meeting':meeting,'file':str(file),'sha256':sha(file),
                          'startFrame':start,'endFrame':end,'frames':end-start,'seconds':packet['seconds']}
                    blocks.append(item);state['completedBlocks'].append(item)
                    save(state='RUNNING_COMPLETE_SOURCE_CONTEXT180',meeting=meeting)
                require(sum(b['frames'] for b in blocks)==case['frames'],'Whole source frames not covered exactly once')
                completed={'state':'COMPLETE_ORIGINAL_SOURCE_FIXED180_RAW_ASR_PENDING_SCORING',
                    'binding':binding,'meeting':meeting,'audioSha256':case['audioSha256'],'frames':case['frames'],
                    'blocks':blocks,'naturalEos':True,'noFramesDroppedOrDuplicated':True,
                    'speakerIdsAreLocalToBlock':True,'qualityQualified':False,'trainingUpdates':0}
                atomic_json(run/(meeting+'-completed.json'),completed)
                state['completedMeetings'].append(meeting);save()
            state['gpuSummary']=guard.close();guard=None
            save(state='COMPLETE_PRETRAINED_CONTEXT180_SOURCE_SUBSET_PENDING_INDEPENDENT_SCORING')
            atomic_json(run/'completed.json',state)
        except BaseException as error:
            import traceback
            save(state='FAILED_NATIVE_CONTEXT180_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc())
            raise
        finally:
            save(finishedAt=now())
            if guard is not None:guard.close()
            pressure.close()


if __name__=='__main__':main()
