"""Audio-only fixed native-BF16 evaluation of the final acoustic pilot.

Reuses24 strict validation clips plus79 unchanged ordinary-Chinese source
leaves. It never selects checkpoints or changes segmentation after scores.
"""
from datetime import datetime
from pathlib import Path
import argparse
import json
import os
import sys
import time
import wave

os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from meeting_acoustic_contract_20261116 import (
    PREFIXES, TRAINABLE_PARAMETERS, accepted_output, committed_checkpoint, read, require,
    select_gpu, sha, tensor_header, verify_bindings,
)
from meeting_acoustic_worker_20261116 import available_ram, exclusive_run, own_limits, present_discrete_gpu
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure
from practical_io_20261107 import atomic_json

now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet',required=True,type=Path)
    parser.add_argument('--training-run',required=True,type=Path)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args(); packet = read(args.packet); verify_bindings(packet)
    limits = own_limits(25)
    training_binding = {'packetSha256':sha(args.packet),'workerSha256':sha(packet['trainingWorker'])}
    complete = read(args.training_run/'training-complete.json')
    require(complete['state'] == 'COMPLETE_FIXED_ACOUSTIC_DOMAIN_PILOT_PENDING_INDEPENDENT_EVALUATION'
            and complete['binding'] == training_binding and complete['completedExamples'] == 944
            and complete['optimizerUpdates'] == 472, 'Only the fixed final epoch may be evaluated')
    checkpoint,receipt = committed_checkpoint(args.training_run,training_binding)
    require(receipt['mode'] == 'train' and receipt['completedExamples'] == 944, 'Preflight/partial checkpoints cannot be evaluated')
    binding = {'packetSha256':sha(args.packet),'checkpointSha256':receipt['sha256'],'workerSha256':sha(__file__)}
    cases = read(packet['evaluationAudioOnly'])
    require(len(cases) == 103 and len({c['id'] for c in cases}) == 103, 'Fixed103 evaluation leaves required')
    require(not any('reference' in key.lower() or key in ['text','target'] for c in cases for key in c), 'Evaluation labels leaked into worker')
    require(not any('L_R003S03C02' in c['meeting'] for c in cases), 'Final blind holdout is protected')
    run = args.run.resolve(); run.mkdir(parents=True,exist_ok=args.resume)
    results = run/'results'; results.mkdir(exist_ok=args.resume)
    state = {'state':'PREPARING_FIXED_AUDIO_ONLY_CANDIDATE_EVALUATION','at':now(),
             'pid':os.getpid(),'binding':binding,'newNeuralCalls':0,'reusedResults':0,
             'completed':[],'modelLoaded':False,'qualityQualified':False,'saleQualified':False,
             'nativeInferencePrecision':'Original BF16 architecture, final FP32 acoustic weights cast to BF16; no quantization.',
             'referencePassedToInference':False,'originalSegmentationChanged':False}
    def save(**values):
        state.update(values,observedAt=now(),limits=limits.query())
        atomic_json(run/'state.json',state,progress=True)
    pressure = SystemRamPressure(); model = None
    def check_stop():
        if (run/'stop.request').exists() or pressure.low():
            raise InterruptedError('Owned stop/Windows low RAM; completed candidate results retained')
    with exclusive_run(run):
        if args.resume and (run/'state.json').exists():
            old = read(run/'state.json'); require(old['binding'] == binding,'Evaluation resume binding changed')
            archive = run/('previous-state-'+sha(run/'state.json')[:16]+'.json')
            if not archive.exists():
                archive.write_bytes((run/'state.json').read_bytes())
        try:
            save()
            for case in cases:
                check_stop(); target = results/(case['id']+'.json')
                require(sha(case['audio']) == case['audioSha256'],'Evaluation PCM changed')
                with wave.open(case['audio'],'rb') as stream:
                    require((stream.getnchannels(),stream.getframerate(),stream.getsampwidth(),stream.getnframes())
                            == (1,16000,2,case['frames']), 'Evaluation audio changed')
                    pcm = stream.readframes(stream.getnframes())
                require(len(pcm) == case['frames']*2,'Truncated evaluation PCM')
                exact_zero = not any(pcm)
                if target.exists():
                    output = read(target)
                    require(output['binding'] == binding and output['audioSha256'] == case['audioSha256']
                            and accepted_output(output) and bool(output.get('exactDigitalSilence')) == exact_zero,
                            'Failed/different cached prefix; refuse automatic retry')
                    state['reusedResults'] += 1
                elif exact_zero:
                    output = {'id':case['id'],'meeting':case['meeting'],'scope':case['scope'],
                              'binding':binding,'audioSha256':case['audioSha256'],'language':case['language'],
                              'text':'','generatedIds':[],'naturalEos':None,
                              'exactDigitalSilence':True,'neuralInferencePerformed':False,'seconds':0.,
                              'referencePassedToInference':False,'textPostEdited':False}
                    atomic_json(target,output)
                else:
                    if model is None:
                        state['presentDevices'] = present_discrete_gpu()
                        started = time.monotonic()
                        while time.monotonic()-started < packet['resources']['stableRamSeconds']:
                            check_stop()
                            require(available_ram() >= packet['resources']['minimumAvailableBytes'], 'RAM recovery floor not met')
                            time.sleep(1)
                        import torch
                        import transformers
                        require(torch.__version__ == packet['runtime']['torch'] and transformers.__version__ == packet['runtime']['transformers'] and torch.version.hip, 'Runtime changed')
                        torch.set_num_threads(4); torch.set_num_interop_threads(1)
                        devices = []
                        for i in range(torch.cuda.device_count()):
                            prop = torch.cuda.get_device_properties(i)
                            devices.append({'index':i,'name':prop.name,'architecture':getattr(prop,'gcnArchName','')})
                        chosen = select_gpu(devices); device = 'cuda:'+str(chosen['index'])
                        torch.cuda.set_device(chosen['index'])
                        from companion_community1_adapter_20261115 import pin_rocm_blas
                        pin_rocm_blas(packet['blas']['file'],packet['blas']['sha256'])
                        from transformers import AutoProcessor
                        from practical_qwen_streamed_loader_20261107 import load_model
                        from companion_local_pcm_session_20261114 import parse_generated_tokens
                        model,loading = load_model(packet['modelRoot'],torch=torch,device=device,expected_sha256=packet['modelSha256'])
                        model.requires_grad_(False).eval()
                        processor = AutoProcessor.from_pretrained(packet['modelRoot'],local_files_only=True)
                        header,offset = tensor_header(checkpoint)
                        trainable = [(n,p) for n,p in model.named_parameters() if n.startswith(PREFIXES)]
                        require(sum(p.numel() for _,p in trainable) == TRAINABLE_PARAMETERS, 'Inference acoustic coverage mismatch')
                        with torch.no_grad(),checkpoint.open('rb') as stream:
                            for name,p in trainable:
                                meta = header['weight/'+name]
                                require(meta['dtype'] == 'F32' and meta['shape'] == list(p.shape), 'Final checkpoint mismatch')
                                stream.seek(offset+meta['data_offsets'][0]); flat = p.reshape(-1)
                                for pos in range(0,flat.numel(),262144):
                                    check_stop(); count = min(262144,flat.numel()-pos)
                                    raw = bytearray(stream.read(count*4)); require(len(raw) == count*4,'Truncated acoustic checkpoint')
                                    flat[pos:pos+count].copy_(torch.frombuffer(raw,dtype=torch.float32).to(device,dtype=p.dtype))
                        atomic_json(run/'model-load.json',loading)
                        save(modelLoaded=True,device=chosen)
                    import numpy as np
                    samples = np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
                    padding = case.get('inputPaddingSamples',0)
                    require(isinstance(padding,int) and 0 <= padding < 8000,'Unexpected original input padding')
                    if padding:
                        samples = np.pad(samples,(0,padding))
                    values = processor.apply_transcription_request(audio=samples,language=case['language'],
                                processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':device}}).to(device,torch.bfloat16)
                    require(int(values['input_features_mask'].sum()) >= len(samples)//160,'Evaluation audio truncated')
                    prefix = values['input_ids'].shape[1]
                    torch.cuda.synchronize(); began = time.perf_counter()
                    with torch.inference_mode():
                        generated = model.generate(**values,do_sample=False,max_new_tokens=512)
                    torch.cuda.synchronize(); elapsed = time.perf_counter()-began
                    ids = generated[0,prefix:].cpu().tolist()
                    eos = model.generation_config.eos_token_id; eos = [eos] if isinstance(eos,int) else eos
                    parsed = parse_generated_tokens(ids,processor.tokenizer,language=case['language'])
                    output = {'id':case['id'],'meeting':case['meeting'],'scope':case['scope'],
                              'binding':binding,'audioSha256':case['audioSha256'],'language':case['language'],
                              'text':parsed['text'],'generatedIds':ids,
                              'naturalEos':bool(ids and ids[-1] in eos),'seconds':elapsed,
                              'exactDigitalSilence':False,'neuralInferencePerformed':True,
                              'sourceFrames':case['frames'],'modelInputSamples':len(samples),'inputPaddingSamples':padding,
                              'referencePassedToInference':False,'textPostEdited':False}
                    atomic_json(target,output); state['newNeuralCalls'] += 1
                    del generated,values,samples
                    require(accepted_output(output),'Candidate decode did not terminate; preserve failure without retrying/changing boundaries')
                state['completed'].append({'id':case['id'],'file':str(target),'sha256':sha(target)})
                save(state='RUNNING_FIXED_AUDIO_ONLY_CANDIDATE_EVALUATION')
            save(state='COMPLETE_FIXED_RAW_ASR_EVALUATION_PENDING_INDEPENDENT_SCORING',
                 completedCacheOnly=state['newNeuralCalls'] == 0)
            atomic_json(run/'evaluation-complete.json',state)
        except BaseException as error:
            import traceback
            save(state='FAILED_CANDIDATE_EVALUATION_NO_RETRY',error=repr(error),traceback=traceback.format_exc())
            raise
        finally:
            save(finishedAt=now()); pressure.close()


if __name__ == '__main__':
    main()
