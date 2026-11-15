"""One fixed public separator + unchanged local ASR, sequential model phases."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,sys,time
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha,pin_rocm_blas
from companion_local_pcm_session_20261114 import atomic_json,parse_generated_tokens
from blind_separation_composition_20261115 import read_audio,separate_continuous,verify_stitching,load_separator
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    p=argparse.ArgumentParser()
    for name in ['control','inventory','run']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--phase',choices=['control','separate','asr'],required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    protocol=read(a.control/'protocol.json');binding=read(a.control/'worker-binding.json')
    assert sha(__file__)==binding['workerSha256'] and sha(a.control/'protocol.json')==binding['protocolSha256']
    for path,digest in binding['helpers'].items():assert sha(path)==digest
    for manifest in ['source-binding.json','model-binding.json']:
        for item in read(a.control/manifest)['files']:assert sha(item['file'])==item['sha256']
    for item in protocol['runtimeFiles']:assert sha(item['file'])==item['sha256']
    assert sha(a.control/'audio-only.json')==protocol['audioOnlySha256']
    sys.path[:0]=[protocol['isolatedDependencies'],protocol['sourceRoot']]
    state=dict(state='STARTING_BLIND_SEPARATION_COMPOSITION',phase=a.phase,
               startedAt=datetime.now().astimezone().isoformat(),explicitNeuralCalls=0,parameterUpdates=0,
               referencesRead=False,qualityQualified=False,protocolSha256=binding['protocolSha256'])
    began=time.perf_counter()
    def save(**values):
        state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
        atomic_json(a.run/'state.json',state)
    def check():
        if (a.run/'stop.request').exists():raise InterruptedError('Owned resource stop; original source and all outputs retained')
    save()
    try:
        inventory=read(a.inventory)
        assert inventory['selected']['name']=='AMD Radeon RX 6800 XT'
        assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()<1800
        import torch,numpy as np
        torch.set_num_threads(1)
        if a.phase!='asr':torch.set_num_interop_threads(1)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        assert torch.version.hip and torch.cuda.device_count()==1
        torch.cuda.set_device(0);gpu=torch.cuda.get_device_properties(0)
        assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
        blas=pin_rocm_blas(protocol['rocmBlasLibrary'],protocol['rocmBlasLibrarySha256'])
        save(state='LOADING_FIXED_MODEL_PHASE',gpu=gpu.name,blas=blas)
        cases=read(a.control/'audio-only.json');assert len(cases)==32
        if a.phase in ['control','separate']:
            model,weight_proof=load_separator(protocol,torch)
            from blind_separator_supervision_20261115 import apply_full_checkpoint
            model.to('cuda:0')
            trained_proof=apply_full_checkpoint(model,read(protocol['trainedCheckpoint']),torch)
            model.to('cpu')
            save(weightProof=weight_proof,trainedFullCheckpointReload=trained_proof,
                 trainingUpdatesBeforeValidation=80)

            def forward(part):
                check();x=torch.from_numpy(part).reshape(1,-1).to(next(model.parameters()).device)
                with torch.inference_mode():out=model(x)
                state['explicitNeuralCalls']+=1
                return np.stack([v.detach().cpu().numpy()[0] for v in out]).astype(np.float32,copy=False)
            if a.phase=='control':
                stitching=verify_stitching(np);original=read_audio(cases[0],np)
                cpu=forward(original[:4096]);model.to('cuda:0');gpu_result=forward(original[:4096])
                delta=np.abs(cpu-gpu_result)
                assert float(delta.max())<=.001 and float(delta.mean())<=.0001
                core=forward(original[:32000]);single,trace=separate_continuous(original[:32000],forward,np)
                assert np.array_equal(core,single) and len(trace)==1
                zero_core=forward(np.zeros(32000,dtype=np.float32))
                zero,zero_trace=separate_continuous(np.zeros(74001,dtype=np.float32),forward,np)
                assert np.count_nonzero(zero)==0 and not zero_trace
                np.save(a.run/'cpu-control.npy',cpu,allow_pickle=False)
                np.save(a.run/'gpu-control.npy',gpu_result,allow_pickle=False)
                save(state='PASS_BLIND_SEPARATOR_NUMERICAL_AND_LOSSLESS_STITCH_CONTROLS',
                     maximumCpuGpuWaveformDifference=float(delta.max()),meanCpuGpuWaveformDifference=float(delta.mean()),
                     singleWindowCoreExact=True,stitchingControls=stitching,
                     coreDigitalSilenceMaximum=float(np.abs(zero_core).max()),
                     exactDigitalSilenceBypass=True,noPerStreamGain=True)
            else:
                proof=read(Path(protocol['controlRun'])/'state.json')
                assert proof['state']=='PASS_BLIND_SEPARATOR_NUMERICAL_AND_LOSSLESS_STITCH_CONTROLS'
                assert proof['protocolSha256']==binding['protocolSha256']
                model.to('cuda:0');results=[]
                for index,case in enumerate(cases):
                    samples=read_audio(case,np);out,trace=separate_continuous(samples,forward,np)
                    raw_sum=out.sum(0).astype(np.float64)
                    e=float(np.mean(raw_sum**2))
                    gain=float(np.sqrt(np.mean(samples.astype(np.float64)**2)/e)) if e>0 else 1.
                    out=(out*gain).astype(np.float32)
                    folder=a.run/'streams'/case['id'];folder.mkdir(parents=True,exist_ok=False)

                    streams=[]
                    for channel in range(2):
                        target=folder/('stream-'+str(channel)+'.npy');np.save(target,out[channel],allow_pickle=False)
                        streams.append(dict(index=channel,file=str(target),sha256=sha(target),frames=len(samples),
                                            peak=float(np.abs(out[channel]).max()),rms=float(np.sqrt(np.mean(out[channel]**2))),
                                            samplesOutsideUnitRange=int((np.abs(out[channel])>1).sum())))
                    result=dict(id=case['id'],sourceWavSha256=case['wavSha256'],frames=len(samples),streams=streams,
                                stitching=trace,allFramesPreserved=True,perStreamGainApplied=False,sharedOutputUnitGain=gain,
                                referenceOrSpeakerProfileUsed=False,qualityQualified=False)
                    atomic_json(folder/'result.json',result);results.append(result)
                    save(state='SEPARATING_ORIGINAL_FROZEN_32_CASES',completed=index+1,total=32,results=results)
                save(state='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING',results=results)
        else:
            from companion_local_qwen_worker_20261114 import NativeDecoder
            from companion_local_decode_recovery_20261114 import recover_local_decode
            from practical_qwen_bounded_decode_20261107 import repeated_block
            from transformers import StoppingCriteria,StoppingCriteriaList
            execution_file=a.control/'asr-execution.json'
            execution=read(execution_file) if execution_file.exists() else {}
            separated=read(execution.get('separationManifest',str(Path(protocol['separationRun'])/'state.json')))
            assert separated['state']=='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING'
            assert separated['protocolSha256']==binding['protocolSha256']
            class Session:
                def state(self):return {'config':{'language':'Chinese'}}
            decoder=NativeDecoder(Path(protocol['nativeProtocol']),a.inventory,Session(),a.run);decoder.load()
            model,processor=decoder.model,decoder.processor
            def raw_infer(samples,low,high):
                check();part=samples[low:high]
                if not np.any(part):
                    return dict(startSample=low,endSample=high,text='',generatedIds=[],rawDecoded='',naturalEos=None,
                                language=None,exactDigitalSilence=True,neuralInferencePerformed=False,inferenceSeconds=0.)
                inputs=processor.apply_transcription_request(audio=part,language='Chinese',processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':'cuda:0'}}).to('cuda:0',model.dtype)
                size=inputs['input_ids'].shape[1]
                class Stop(StoppingCriteria):
                    def __call__(self,input_ids,scores,**kwargs):
                        check();return repeated_block(input_ids[0,size:].tolist(),suffix_only=True) is not None
                torch.cuda.synchronize();started=time.perf_counter()
                with torch.inference_mode():out=model.generate(**inputs,max_new_tokens=512,do_sample=False,stopping_criteria=StoppingCriteriaList([Stop()]))
                torch.cuda.synchronize();elapsed=time.perf_counter()-started;ids=out[0,size:].cpu().tolist()
                parsed=parse_generated_tokens(ids,processor.tokenizer,language='Chinese')
                eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
                state['explicitNeuralCalls']+=1
                return dict(startSample=low,endSample=high,text=parsed['text'],language=parsed['language'],
                            generatedIds=ids,rawDecoded=processor.tokenizer.decode(ids,skip_special_tokens=False,clean_up_tokenization_spaces=False),
                            naturalEos=bool(ids and ids[-1] in eos),repeatBlock=repeated_block(ids),
                            neuralInferencePerformed=True,inferenceSeconds=elapsed)
            # One unchanged original waveform/prefix control; all32 baseline
            # transcriptions are reused, never regenerated as a baseline sweep.
            if execution.get('nativePrefixControl'):
                assert sha(execution['nativePrefixControl'])==execution['nativePrefixControlSha256']
                control=read(execution['nativePrefixControl'])
            else:
                original=read_audio(cases[0],np);control=raw_infer(original,0,len(original))
            assert control['generatedIds']==read(protocol['baselineNativeControl'])['raw']['generatedIds']
            atomic_json(a.run/'original-native-control.json',control)
            results=[]
            for case in cases:
                source=next(r for r in separated['results'] if r['id']==case['id'])
                for stream in source['streams']:
                    assert sha(stream['file'])==stream['sha256']
                    samples=np.load(stream['file'],allow_pickle=False)
                    assert samples.dtype==np.float32 and samples.shape==(source['frames'],) and np.isfinite(samples).all()
                    folder=a.run/'transcripts'/case['id']/('stream-'+str(stream['index']));folder.mkdir(parents=True,exist_ok=False)
                    def infer(low,high):return raw_infer(samples,low,high)
                    def load(key):return read(folder/(key+'.json')) if (folder/(key+'.json')).exists() else None
                    def store(key,raw):atomic_json(folder/(key+'.json'),raw)
                    leaves=recover_local_decode(0,len(samples),infer=infer,load=load,save=store,language_mode='Chinese')
                    packet=dict(id=case['id'],stream=stream['index'],sourceWavSha256=case['wavSha256'],
                        inputFloatSha256=stream['sha256'],text='\n'.join(r['raw']['text'] for r in leaves),
                        frames=len(samples),reviewRequired=any(r['reviewRequired'] for r in leaves),
                        leaves=leaves,wordsPostEdited=False,referenceUsed=False,allFramesPreserved=True,
                        outputStreamDropped=False,qualityQualified=False)
                    atomic_json(folder/'result.json',packet);results.append(dict(id=case['id'],stream=stream['index'],
                        file=str(folder/'result.json'),sha256=sha(folder/'result.json'),reviewRequired=packet['reviewRequired']))
                    save(state='ASR_ON_BOTH_COMPLETE_SEPARATED_STREAMS',completed=len(results),total=64,results=results)
            save(state='COMPLETE_FIXED_SEPARATION_ASR_COMPOSITION_SCORING_PENDING',results=results,
                 originalNativePrefixExact=True,all64StreamsRetained=True)
    except BaseException as error:
        save(state='FAILED_BLIND_SEPARATION_PHASE_RETAINED',error=repr(error));raise
    finally:
        state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began)
        atomic_json(a.run/'state.json',state)
        print(json.dumps({k:state.get(k) for k in ['state','phase','error','explicitNeuralCalls','seconds']},ensure_ascii=False))

if __name__=='__main__':main()
