"""Sequential target extraction / unchanged native ASR. No references enter here."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,importlib.util,json,os,sys,time,traceback,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['separation','asr'],required=True);parser.add_argument('--resume',action='store_true');args=parser.parse_args()
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
P=read(C/'protocol-r2.json');ready=read(C/'model-ready.json');assert sha(__file__)==P['workerSourceSha256']
assert sha(C/'audio-only.json')==P['audioOnlySha256'] and sha(C/'model-ready.json')==P['modelReadySha256']
for file,digest in P['helperSources'].items():assert sha(Path(__file__).with_name(file))==digest
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);tick=time.perf_counter();target=C/(args.stage+'-state-r2.json')
binding={'protocolSha256':sha(C/'protocol-r2.json'),'audioOnlySha256':P['audioOnlySha256'],'workerSourceSha256':P['workerSourceSha256']}
if target.exists():
    assert args.resume and read(target)['binding']==binding
    prior=C/('prior-'+args.stage+'-'+sha(target)[:12]+'.json')
    if not prior.exists():prior.write_bytes(target.read_bytes())
state={'state':'IMPORTING_NATIVE_TORCH','pid':os.getpid(),'startedAt':now(),'stage':args.stage,'binding':binding,'newNeuralCalls':0,'reusedOutputs':0,'completedInputs':0,'referencePassedToWorker':False,'qualityQualified':False}
def save():state['limits']=limits.query();atomic_json(target,state,progress=True)
save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip and torch.cuda.device_count()==1
    gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
    torch.cuda.set_device(0);state.update(gpu=gpu.name);save()
    def samples(file):
        with wave.open(str(file),'rb') as stream:
            assert stream.getframerate()==16000 and stream.getsampwidth()==2 and stream.getnchannels()==1
            return np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768
    def wave_out(dest,value):
        peak=float(np.max(np.abs(value)));scale=max(1.,peak)
        pcm=np.rint(value/scale*32767).clip(-32768,32767).astype('<i2')
        part=dest.with_suffix('.part');assert not dest.exists() and not part.exists()
        with wave.open(str(part),'wb') as stream:stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(pcm.tobytes())
        os.replace(part,dest);return peak,scale
    if args.stage=='separation':
        for file in ready['files']:assert sha(file['file'])==file['sha256']
        frontend=read(C/'audio-frontend-source.json');assert sha(C/'audio-frontend-source.json')==P['audioFrontendManifestSha256']
        for row in frontend['files']:assert sha(row['file'])==row['sha256']
        sys.path.insert(0,frontend['pythonPath'])
        module_file=Path(ready['sourceRoot'])/'inference.py';spec=importlib.util.spec_from_file_location('pinned_ps4_author',module_file);author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
        assert Path(author.torchaudio.__file__).resolve().is_relative_to(Path(frontend['pythonPath']).resolve())
        state.update(state='LOADING_MATCHED_PS4_NATIVE_MODEL');save();load_started=time.perf_counter()
        checkpoint=torch.load(ready['weight'],map_location='cpu',weights_only=True,mmap=True)
        weights=checkpoint.get('model',checkpoint.get('state_dict',checkpoint))
        assert isinstance(weights,dict) and all(isinstance(v,torch.Tensor) for v in weights.values())
        model=author.build_model(torch.device('cuda:0'))
        prefixed=all(k.startswith('module.') for k in weights)
        if prefixed:weights={k.removeprefix('module.'):v for k,v in weights.items()}
        loaded=model.load_state_dict(weights,strict=True)
        assert not loaded.missing_keys and not loaded.unexpected_keys
        actual=model.state_dict();assert set(actual)==set(weights)
        source_hash=hashlib.sha256();device_hash=hashlib.sha256()
        for key in sorted(weights):
            left=weights[key].detach().contiguous().cpu().numpy().tobytes();right=actual[key].detach().contiguous().cpu().numpy().tobytes()
            assert left==right;source_hash.update(key.encode()+left);device_hash.update(key.encode()+right)
        atomic_json(C/'weight-roundtrip-separation-r2.json',{'state':'ALL_EXACT_AUTHOR_STATE_TENSORS_LOADED_AND_GPU_BYTES_VERIFIED','tensors':len(weights),'sourceTensorHash':source_hash.hexdigest(),'deviceTensorHash':device_hash.hexdigest(),'uniformDdpPrefixRemoved':prefixed,'strictMissingKeys':[],'strictUnexpectedKeys':[],'authorInferenceSourceUnmodified':True,'safeWeightsOnlyLoad':True,'mmapCheckpoint':True})
        del checkpoint,weights,actual,left,right
        state.update(modelLoaded=True,modelLoadSeconds=time.perf_counter()-load_started,state='EXTRACTING_TARGET_VOICES');save()
        folder=Path(P['derivedAudioRoot']);folder.mkdir(exist_ok=True);outputs=[]
        for case in read(C/'audio-only.json'):
            assert sha(case['audio'])==case['audioSha256'];mix=samples(case['audio']);mix_peak=float(np.max(np.abs(mix)));assert mix_peak>0
            mixture=torch.from_numpy(mix/mix_peak).unsqueeze(0).to('cuda:0')
            for anchor in case['anchors']:
                identity=case['id']+'-speaker-'+str(anchor['speaker']);receipt=C/'separation-outputs-r2'/(identity+'.json');receipt.parent.mkdir(exist_ok=True)
                if receipt.exists():
                    result=read(receipt);assert result['binding']==binding and sha(result['audio'])==result['audioSha256'];state['reusedOutputs']+=1
                else:
                    assert not (C/'stop.request').exists();assert sha(anchor['audio'])==anchor['audioSha256']
                    enroll=samples(anchor['audio']);enroll_peak=float(np.max(np.abs(enroll)));assert enroll_peak>0
                    enrollment=torch.from_numpy(enroll/enroll_peak).unsqueeze(0).to('cuda:0')
                    torch.cuda.synchronize();started=time.perf_counter()
                    with torch.inference_mode():voice=author.extract_speaker(model,mixture,enrollment,torch.device('cuda:0'))
                    torch.cuda.synchronize();elapsed=time.perf_counter()-started
                    value=voice.numpy().reshape(-1);assert len(value)==len(mix) and np.isfinite(value).all()
                    dest=folder/(identity+'.wav');peak,scale=wave_out(dest,value)
                    result={'id':identity,'binding':binding,'meeting':case['meeting'],'rootIndex':case['rootIndex'],'kind':case['kind'],
                        'predictedSpeaker':anchor['speaker'],'audio':str(dest),'audioSha256':sha(dest),'audioSeconds':len(value)/16000,
                        'inputMixtureSha256':case['audioSha256'],'enrollmentSha256':anchor['audioSha256'],
                        'mixtureAuthorPeakNormalization':mix_peak,'enrollmentAuthorPeakNormalization':enroll_peak,
                        'floatOutputSha256':hashlib.sha256(value.tobytes()).hexdigest(),'floatOutputPeak':peak,'pcmExportDivisor':scale,
                        'inferenceSeconds':elapsed,'noReferenceInputOrOutputFiltering':True,'sampleCountUnchanged':True}
                    atomic_json(receipt,result);state['newNeuralCalls']+=1;del voice,value,enrollment;time.sleep(1)
                outputs.append(result);state['completedInputs']+=1;save()
            del mixture
        atomic_json(C/'separation-manifest-r2.json',outputs)
    else:
        assert read(C/'separation-state-r2.json')['state']=='COMPLETE_PS4_SEPARATION_UNQUALIFIED'
        N=read(P['nativeAsrProtocol']);assert sha(P['nativeAsrProtocol'])==P['nativeAsrProtocolSha256']
        assert N['maxNewTokens']==512 and not N['doSample'] and N['dtype']=='bfloat16' and N['prompt'] is None
        assert read(N['streamedLoaderControl'])['state']=='PASS_STANDARD_AND_STREAMED_TINY_QWEN_EXACT_LOGITS_AND_GENERATION'
        assert read(N['supportedGpuFeatureNumericProof'])['state']=='PASS_SUPPORTED_GPU_FEATURES_INDEPENDENT_NUMPY_REFERENCE'
        for file in N['files']:assert sha(file['file'])==file['sha256']
        from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
        from practical_qwen_streamed_loader_20261107 import load_model
        from practical_qwen_bounded_decode_20261107 import accepted,recover,repeated_block
        from practical_qwen_input_20261107 import is_exact_digital_silence
        processor=AutoProcessor.from_pretrained(N['modelRoot'],local_files_only=True)
        weight=next(f for f in N['files'] if Path(f['file']).name=='model.safetensors')
        model,receipt=load_model(N['modelRoot'],torch=torch,device='cuda:0',expected_sha256=weight['sha256'])
        atomic_json(C/'weight-roundtrip-asr-r2.json',receipt);state.update(modelLoaded=True,state='TRANSCRIBING_EVERY_EXTRACTED_VOICE');save()
        outputs=[]
        for case in read(C/'separation-manifest-r2.json'):
            assert sha(case['audio'])==case['audioSha256'];audio=samples(case['audio']);folder=C/'asr-outputs-r2'/case['id'];folder.mkdir(parents=True,exist_ok=True)
            def infer(lo,hi):
                part=audio[lo:hi]
                if is_exact_digital_silence(part):return {'startSample':lo,'endSample':hi,'text':'','generatedIds':[],'naturalEos':None,'repeatBlock':None,'exactDigitalSilence':True,'neuralInferencePerformed':False,'inferenceSeconds':0.}
                inputs=processor.apply_transcription_request(audio=part,language=N['language'],processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':'cuda:0'}}).to('cuda:0',model.dtype)
                assert int(inputs['input_features_mask'].sum().item())>=len(part)//160
                prefix=inputs['input_ids'].shape[1]
                class StopLoop(StoppingCriteria):
                    def __call__(self,input_ids,scores,**kwargs):
                        assert not (C/'stop.request').exists(),'Explicit owned stop'
                        return repeated_block(input_ids[0,prefix:].tolist(),suffix_only=True) is not None
                torch.cuda.synchronize();started=time.perf_counter()
                with torch.inference_mode():ids=model.generate(**inputs,max_new_tokens=N['maxNewTokens'],do_sample=N['doSample'],stopping_criteria=StoppingCriteriaList([StopLoop()]))
                torch.cuda.synchronize();elapsed=time.perf_counter()-started;generated=ids[0,prefix:].cpu().tolist()
                eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
                raw={'startSample':lo,'endSample':hi,'text':processor.tokenizer.decode(generated,skip_special_tokens=True,clean_up_tokenization_spaces=False),
                    'generatedIds':generated,'rawDecoded':processor.decode(generated,skip_special_tokens=False),'naturalEos':bool(generated and generated[-1] in eos),
                    'repeatBlock':repeated_block(generated),'neuralInferencePerformed':True,'inferenceSeconds':elapsed}
                state['newNeuralCalls']+=1;save();time.sleep(1);return raw
            def load(key):
                file=folder/(key+'.json')
                if not file.exists():return None
                packet=read(file);assert packet['binding']==binding and packet['audioSha256']==case['audioSha256']
                assert packet['rawSha256']==hashlib.sha256(json.dumps(packet['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                state['reusedOutputs']+=1;return packet['raw']
            def put(key,raw):atomic_json(folder/(key+'.json'),{'binding':binding,'audioSha256':case['audioSha256'],'raw':raw,'rawSha256':hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()})
            leaves=recover(0,len(audio),infer=infer,load=load,save=put)
            assert all(accepted(leaf['raw']) for leaf in leaves)
            result={**case,'text':'\n'.join(leaf['raw']['text'] for leaf in leaves),'acceptedLeaves':[leaf['raw'] for leaf in leaves]}
            atomic_json(folder/'completed.json',result);outputs.append(result);state['completedInputs']+=1;save()
        atomic_json(C/'asr-manifest-r2.json',outputs)
    state.update(state='COMPLETE_PS4_'+args.stage.upper()+'_UNQUALIFIED')
except BaseException as error:
    state.update(state='FAILED_PS4_'+args.stage.upper()+'_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);print(json.dumps(state),flush=True)
