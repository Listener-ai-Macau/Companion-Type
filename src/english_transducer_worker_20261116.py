"""One native publishedF32 English transducer comparison, no model training."""
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
from companion_local_pcm_session_20261114 import exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from practical_io_20261107 import atomic_json

now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')


def make_empty(config,torch):
    from accelerate import init_empty_weights
    from transformers import ParakeetForTDT
    with init_empty_weights(include_buffers=False):model=ParakeetForTDT(config)
    require(all(p.is_meta for p in model.parameters()),'Expected empty native parameter allocation')
    require(all(not b.is_meta for b in model.buffers()),'Native deterministic buffers became meta')
    return model


def tiny_loader_control(torch,device):
    from transformers import ParakeetTDTConfig,ParakeetForTDT
    torch.manual_seed(20261116)
    config=ParakeetTDTConfig(vocab_size=16,blank_token_id=15,pad_token_id=0,
        decoder_hidden_size=16,num_decoder_layers=1,
        encoder_config={'hidden_size':16,'num_hidden_layers':2,'num_attention_heads':2,
            'intermediate_size':32,'num_mel_bins':8,'subsampling_conv_channels':4,
            'dropout':0.,'attention_dropout':0.,'activation_dropout':0.,'layerdrop':0.})
    config._attn_implementation='eager';config.encoder_config._attn_implementation='eager'
    standard=ParakeetForTDT(config).to(device).eval().requires_grad_(False)
    tensors={k:v.detach().clone() for k,v in standard.state_dict().items()}
    bounded=make_empty(config,torch);bounded.load_state_dict(tensors,strict=True,assign=True)
    bounded=bounded.to(device).eval().requires_grad_(False)
    request={'input_features':torch.randn((1,64,8),device=device,dtype=torch.float32),
        'attention_mask':torch.ones((1,64),device=device,dtype=torch.long),
        'decoder_input_ids':torch.tensor([[15]],device=device)}
    with torch.inference_mode():left=standard(**request).logits;right=bounded(**request).logits
    difference=float((left-right).abs().max())
    require(torch.allclose(left,right,atol=1e-6,rtol=1e-6),'Native streamed-loader tiny TDT logits differ')
    return {'state':'PASS_TINY_NATIVE_TDT_STANDARD_AND_EMPTY_ASSIGNED_LOGITS',
        'maxAbsDifference':difference,'tensorCount':len(tensors),'device':device,
        'pretrainedAudioCalls':0,'tinyGpuForwards':2,'trainingUpdates':0}


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect',action='store_true');mode.add_argument('--execute',action='store_true')
    p.add_argument('--run',type=Path);a=p.parse_args();P=read(a.protocol)
    limits=own_limits(5 if a.inspect else 25)
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen English component source changed: '+item['file'])
    cases=read(P['audioOnly']);require(len(cases)==12 and len({c['id'] for c in cases})==12,'Fixed12 English clips required')
    for case in cases:
        require(set(case)=={'id','audio','audioSha256','frames'},'Labels/speaker hints entered English inference')
        require(sha(case['audio'])==case['audioSha256'],'Original English PCM changed')
        with wave.open(case['audio'],'rb') as w:
            require((w.getnchannels(),w.getframerate(),w.getsampwidth(),w.getnframes())==(1,16000,2,case['frames']),
                    'Original English input format changed')
    require(Path(P['weights']['file']).stat().st_size==P['weights']['bytes'],'Official model size changed')
    if a.inspect:
        require('torch' not in sys.modules,'Offline inspection imported neural runtime')
        print(json.dumps({'state':'PASS_ONE_NATIVE_ENGLISH_TRANSDUCER_OFFLINE_INPUT_INSPECTION',
            'cases':12,'torchImported':False,'newNeuralCalls':0,'trainingUpdates':0,'limits':limits.query()}));return
    require(a.run is not None,'Explicit experimental run directory required')
    run=a.run.resolve();run.mkdir(parents=True,exist_ok=False);(run/'results').mkdir()
    binding={'protocolSha256':sha(a.protocol),'workerSha256':sha(__file__),'modelSha256':P['weights']['sha256']}
    state={'state':'PREPARING_ONE_NATIVE_ENGLISH_TRANSDUCER','at':now(),'pid':os.getpid(),
        'binding':binding,'completed':[],'newNeuralCalls':0,'tinyGpuForwards':0,'trainingUpdates':0,
        'referencesRead':False,'qualityQualified':False,'saleQualified':False}
    pressure=SystemRamPressure()
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query());atomic_json(run/'state.json',state,progress=True)
    def check_stop():
        require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Overnight experiment deadline reached')
        if pressure.low() or (run/'stop.request').exists():raise InterruptedError('Owned stop/Windows low RAM; preserve outputs')
    with exclusive_run(run),exclusive_file(Path(P['neuralLock'])),PowerLease():
        try:
            save();state['presentDevices']=present_discrete_gpu();began=time.monotonic()
            while time.monotonic()-began<60:
                check_stop();require(available_ram()>=P['minimumAvailableBytes'],'Original RAM admission floor not met')
                time.sleep(1)
            import torch
            import transformers
            require(torch.__version__==P['runtime']['torch'] and transformers.__version__==P['runtime']['transformers']
                    and torch.version.hip,'Frozen native AMD runtime changed')
            torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.set_float32_matmul_precision('highest')
            inventory=[]
            for i in range(torch.cuda.device_count()):
                prop=torch.cuda.get_device_properties(i)
                inventory.append({'index':i,'name':prop.name,'architecture':getattr(prop,'gcnArchName','')})
            chosen=select_gpu(inventory);device='cuda:'+str(chosen['index']);torch.cuda.set_device(chosen['index'])
            from companion_community1_adapter_20261115 import pin_rocm_blas
            pin_rocm_blas(P['blas']['file'],P['blas']['sha256']);save(device=chosen)
            proof=tiny_loader_control(torch,device);atomic_json(run/'loader-control.json',proof)
            state['tinyGpuForwards']=2;gc.collect();torch.cuda.empty_cache()
            from transformers import AutoConfig,AutoProcessor,GenerationConfig,StoppingCriteria,StoppingCriteriaList
            from moss_streamed_weights_20261104 import load_streamed_weights
            config=AutoConfig.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
            require(config.model_type=='parakeet_tdt' and list(config.durations)==[0,1,2,3,4],'Unexpected native transducer architecture')
            config._attn_implementation='eager';config.encoder_config._attn_implementation='eager'
            model=make_empty(config,torch)
            save(state='LOADING_EXACT_PUBLISHED_F32_ENGLISH_TENSORS')
            weights,receipt=load_streamed_weights(P['weights']['file'],torch=torch,device=device,
                expected_sha256=P['weights']['sha256'],chunk_bytes=8*1024**2)
            model.load_state_dict(weights,strict=True,assign=True)
            model=model.to(device).eval().requires_grad_(False)
            require(all(not p.is_meta and not p.requires_grad and p.device==torch.device(device)
                and p.dtype==torch.float32 for p in model.parameters()),'Native weights moved, cast, or became trainable')
            model.generation_config=GenerationConfig.from_pretrained(P['modelRoot'],local_files_only=True)
            require(set(model.generation_config.suppress_tokens)==set(range(config.vocab_size,config.vocab_size+5)),
                    'Published duration-logit suppression is missing')
            atomic_json(run/'weight-roundtrip.json',receipt);del weights;gc.collect()
            processor=AutoProcessor.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
            require(processor._decoder_type=='tdt' and processor.feature_extractor.sampling_rate==16000
                and processor.feature_extractor.hop_length==160,'Published TDT frontend/decoder differs')
            import numpy as np
            for case in cases:
                check_stop();save(state='RECOGNIZING_ONE_FIXED_ENGLISH_TRANSDUCER',currentId=case['id'])
                with wave.open(case['audio'],'rb') as w:pcm=w.readframes(w.getnframes())
                samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
                # Follow the official default CPU feature extraction, then run
                # the entire pretrained acoustic model/decoder on the6800XT.
                request=processor(audio=samples,sampling_rate=16000,return_tensors='pt',
                    audio_kwargs={'truncation':False,'device':'cpu'}).to(device)
                feature_frames=int(request['attention_mask'].sum())
                require(feature_frames==case['frames']//160,'Native features truncated original audio')
                encoder_frames=int(model._get_subsampling_output_length(request['attention_mask'].sum(-1))[0])
                tick=time.perf_counter()
                class OwnedStop(StoppingCriteria):
                    def __call__(self,input_ids,scores,**kwargs):
                        check_stop();require(time.perf_counter()-tick<=600,'Fixed transducer decode exceeded time budget');return False
                torch.cuda.synchronize()
                with torch.inference_mode():
                    result=model.generate(**request,do_sample=False,disable_compile=True,
                        stopping_criteria=StoppingCriteriaList([OwnedStop()]))
                torch.cuda.synchronize();seconds=time.perf_counter()-tick
                ids=result.sequences[0].cpu().tolist();durations=result.durations[0].cpu().tolist()
                require(len(ids)==len(durations),'Native token/duration result pairing differs')
                text=processor.batch_decode(result.sequences,skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,group_tokens=False)[0]
                eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos or []
                exhausted=sum(durations)>=encoder_frames;natural=exhausted or bool(ids and ids[-1] in eos)
                packet={'id':case['id'],'binding':binding,'audioSha256':case['audioSha256'],
                    'generatedIdsIncludingBlank':ids,'frameDurations':durations,'text':text,
                    'featureFrames':feature_frames,'encoderFrames':encoder_frames,
                    'encoderExhausted':exhausted,'naturalTermination':natural,'seconds':seconds,
                    'allInputFramesPreserved':True,'weightsDtype':'published float32 unchanged',
                    'wordsPostEdited':False,'repeatedLexicalTokensCollapsed':False,
                    'referenceUsed':False,'trainingUpdates':0}
                file=run/'results'/(case['id']+'.json');atomic_json(file,packet);state['newNeuralCalls']+=1
                require(natural,'Native generation hit a bound without terminal condition; preserve without changed retries')
                state['completed'].append({'id':case['id'],'file':str(file),'sha256':sha(file)})
                del request,result,samples,pcm;gc.collect();torch.cuda.empty_cache();save()
            save(state='COMPLETE_ONE_NATIVE_ENGLISH_TRANSDUCER_PENDING_INDEPENDENT_SCORING')
            atomic_json(run/'completed.json',state)
        except BaseException as error:
            import traceback
            save(state='FAILED_ONE_NATIVE_ENGLISH_TRANSDUCER_RETAINED_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
            raise
        finally:save(finishedAt=now());pressure.close()


if __name__=='__main__':main()
