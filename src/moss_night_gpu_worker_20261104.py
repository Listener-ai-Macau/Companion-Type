"""One fixed joint-model input. Reference files are never opened here."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter,defaultdict
import argparse,hashlib,json,math,os,re,sys,time,traceback

p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);p.add_argument('--protocol',required=True);p.add_argument('--inputs',required=True);p.add_argument('--output-name');args=p.parse_args()
assets=Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104')
root=Path(args.protocol).resolve().parent
if (root/'stop.request').exists():
    raise SystemExit('GPU experiment is paused: stop.request exists; no model imported or loaded')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
protocol_path=Path(args.protocol);protocol=read(protocol_path);case=read(args.inputs)[args.index]
from moss_windows_resource_limits_20261104 import WorkerLimits
worker_limits=WorkerLimits(cpu_percent=protocol['runtime'].get('workerCpuHardCapPercent',10),memory_bytes=protocol['runtime'].get('systemPrivateMemoryBudgetBytes',2*1024**3))
out=root/'results'/(args.output_name or case['meeting']);out.mkdir(parents=True,exist_ok=False)
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
state={'state':'IMPORTING','startedAt':now(),'pid':os.getpid(),'meeting':case['meeting'],
 'resourceLimits':worker_limits.receipt,
 'audioSha256':case['audioSha256'],'generatedTokens':0,'progressWriteDeferrals':0,'cacheWriteWarnings':0,
 'scope':'Official pinned joint architecture, local full input, no reference text/count/hotwords. Smoke is compatibility only.'}
def save():
    try:
        if 'gpu_stats' in globals():state.update(gpu_stats())
        target=out/'state.tmp';target.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');target.replace(out/'state.json')
    except OSError:state['progressWriteDeferrals']+=1
save();started=time.perf_counter()
try:
    with Path(case['audio']).open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==case['audioSha256']
    import importlib.metadata,random
    import numpy as np,torch,transformers
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    random.seed(0);np.random.seed(0);torch.manual_seed(0)
    assert torch.version.hip, 'Native AMD runtime required; no CPU execution fallback'
    gpu_index=protocol['runtime']['gpuIndex'];properties=torch.cuda.get_device_properties(gpu_index)
    assert 'RX 6800 XT' in properties.name and properties.gcnArchName.startswith('gfx1030')
    torch.cuda.set_device(gpu_index);device=torch.device('cuda',gpu_index)
    torch.cuda.reset_peak_memory_stats(device)
    active_limits=worker_limits.query()
    assert active_limits['gpuPriorityClass']==0 and active_limits['cpuControlFlags']==5
    state.update(actualGpu=properties.name,gpuIndex=gpu_index,hipVersion=torch.version.hip,torchVersion=torch.__version__,resourceLimitsAfterGpuInit=active_limits)
    def gpu_stats():
        try:return {'gpuAllocatedBytes':torch.cuda.memory_allocated(device),'gpuReservedBytes':torch.cuda.memory_reserved(device),'gpuPeakAllocatedBytes':torch.cuda.max_memory_allocated(device),'gpuPeakReservedBytes':torch.cuda.max_memory_reserved(device)}
        except Exception:return {}
    save()
    assert torch.__version__==protocol['runtime']['torch'] and transformers.__version__==protocol['runtime']['transformers']
    sys.path.insert(0,str(assets/'official-source'))
    from moss_transcribe_diarize import MossTranscribeDiarizeConfig,MossTranscribeDiarizeForConditionalGeneration,MossTranscribeDiarizeProcessor,parse_transcript
    from moss_transcribe_diarize.inference_utils import build_transcription_messages,prepare_inputs
    if protocol['runtime'].get('nativePcm16RamLoading'):
        from moss_transcribe_diarize import inference_utils
        from moss_pcm16_ram_20261104 import install_pcm16_loader
        state['pcm16RamLoader']=install_pcm16_loader(inference_utils)
    from transformers.generation.streamers import BaseStreamer
    from transformers import StoppingCriteria,StoppingCriteriaList
    (out/'runtime-freeze.json').write_text(json.dumps({d.metadata['Name']:d.version for d in importlib.metadata.distributions()},indent=2),encoding='utf8')
    for record in read(assets/'prepare-state.json')['files']:
        file=assets/('model' if record['source']=='hf' else 'official-source')/record['file']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==record['sha256']
    tick=time.perf_counter();state.update(state='LOADING_MODEL');save()
    config=MossTranscribeDiarizeConfig.from_pretrained(assets/'model',local_files_only=True)
    selected_dtype=getattr(torch,case.get('dtype',protocol['runtime']['dtype']))
    load_options={}
    if protocol['runtime'].get('directGpuWeightLoading'):
        # Fixed target: never use auto placement or CPU/disk offload. Loading
        # directly avoids holding a full CPU parameter copy before .to(cuda).
        load_options['device_map']={'':str(device)}
    pretrained_source=assets/'model'
    if protocol['runtime'].get('streamedWeightLoading'):
        from moss_streamed_weights_20261104 import load_streamed_weights
        tensors,transfer=load_streamed_weights(assets/'model/model-00000-of-00001.safetensors',torch=torch,
            device=device,expected_sha256=protocol['weightSha256'])
        state['streamedWeightLoading']=transfer;save()
        (out/'streamed-weight-transfer.json').write_text(json.dumps(transfer,indent=2),encoding='utf8')
        load_options['state_dict']=tensors;pretrained_source=None
    model,loading=MossTranscribeDiarizeForConditionalGeneration.from_pretrained(pretrained_source,config=config,
        dtype=selected_dtype,attn_implementation='sdpa',local_files_only=True,output_loading_info=True,**load_options)
    if 'state_dict' in load_options:
        del load_options['state_dict'],tensors
    model=model.eval() if load_options else model.to(device).eval()
    if protocol['runtime'].get('streamedWeightLoading'):
        # from_pretrained(None, state_dict=...) cannot discover this file itself.
        # Restore the author's actual EOS/pad/bos settings, not generic defaults.
        model.generation_config=transformers.GenerationConfig.from_pretrained(assets/'model',local_files_only=True)
        state['publishedGenerationConfigRestored']=True
    # Record the actual projection width; never assume a long prefix emits
    # only last-token logits when investigating WDDM/system-memory pressure.
    def observe_projection(module, values):
        width=int(values[0].shape[-2])
        if 'firstProjectionTokenCount' not in state:
            state['firstProjectionTokenCount']=width
        state['maximumProjectionTokenCount']=max(width,state.get('maximumProjectionTokenCount',0))
    model.lm_head.register_forward_pre_hook(observe_projection)
    state['directGpuWeightLoading']=bool(load_options)
    state['deviceMap']={str(k):str(v) for k,v in getattr(model,'hf_device_map',{}).items()}
    torch.cuda.synchronize(device)
    assert all(p.device==device for p in model.parameters())
    (out/'loading-info.json').write_text(json.dumps(loading,default=str,indent=2),encoding='utf8')
    assert not loading.get('unexpected_keys') and not loading.get('mismatched_keys')
    assert set(loading.get('missing_keys',[]))<= {'lm_head.weight'}
    assert model.lm_head.weight.data_ptr()==model.model.language_model.embed_tokens.weight.data_ptr(),'Output head must use published tied embedding weights'
    processor=MossTranscribeDiarizeProcessor.from_pretrained(assets/'model',config=config,local_files_only=True)
    state.update(modelLoadSeconds=time.perf_counter()-tick,modelParameterCount=sum(p.numel() for p in model.parameters()),
        actualDtype=str(next(model.parameters()).dtype),torchThreads=torch.get_num_threads(),outputEmbeddingTied=True,state='PREPARING_COMPLETE_AUDIO');save()
    pacer=None
    if protocol['runtime'].get('cooperativeGpuDuty'):
        from moss_gpu_cooperative_pacing_20261104 import GpuPacer
        pacer=GpuPacer(torch,device,duty=protocol['runtime']['cooperativeGpuDuty'],stop_file=root/'stop.request')
        pacer.install(model);state['cooperativeGpuPacing']=pacer.stats
    # During the first long-context prefill there is no generated token yet.
    # Persist each real completed decoder layer so a device/runtime failure
    # retains its actual progress and peak allocations, without changing math.
    prefill_handles=[]
    def prefill_layer_finished(module, values, result):
        if state['generatedTokens']==0:
            if protocol['runtime'].get('releaseUnusedModelAllocations'):
                torch.cuda.empty_cache()
                state['unusedAllocatorReleases']=state.get('unusedAllocatorReleases',0)+1
            state['decoderPrefillLayersCompleted']=state.get('decoderPrefillLayersCompleted',0)+1
            state['decoderPrefillLayerTotal']=len(model.model.language_model.layers)
            state['lastPrefillLayerAt']=now();save()
    for layer in model.model.language_model.layers:
        prefill_handles.append(layer.register_forward_hook(prefill_layer_finished))
    if protocol['runtime'].get('boundedMathAttention'):
        from moss_amd_execution_20261104 import install_execution_adapters
        if case.get('verifyExecution'):
            # Verify independent encoder-chunk batching on this exact pretrained
            # encoder, with synthetic features. This is not an accuracy sample.
            features=torch.randn(3,80,3000,device=device,dtype=selected_dtype)
            with torch.inference_mode():reference_encoder=model.model.whisper_encoder(features,return_dict=True).last_hidden_state
        execution_stats=install_execution_adapters(model,query_block=protocol['runtime']['queryBlock'],encoder_batch=protocol['runtime']['encoderBatch'],pacer=pacer,key_block=protocol['runtime'].get('keyBlock'))
        state['executionAdapters']=execution_stats
        if case.get('verifyExecution'):
            with torch.inference_mode():actual_encoder=model.model.whisper_encoder(features,return_dict=True).last_hidden_state
            torch.cuda.synchronize(device)
            difference=(reference_encoder.float()-actual_encoder.float()).abs()
            torch.testing.assert_close(actual_encoder,reference_encoder,rtol=.03125,atol=.0625)
            (out/'encoder-microbatch-equivalence.json').write_text(json.dumps({'maximumAbsoluteDifference':float(difference.max().item()),'meanAbsoluteDifference':float(difference.mean().item()),'syntheticIndependentChunks':3,'preservesChunkOrder':True,'scope':'Numerical execution comparison only, not speech quality.'},indent=2),encoding='utf8')
            del features,reference_encoder,actual_encoder,difference
            for key in ['sdpaCalls','blockedCalls','maxQueryTokens','maxKeyTokens','encoderCalls','encoderChunks','encoderMicrobatches','encoderNativeSdpaCalls']:execution_stats[key]=0

    original_features=model.model.get_audio_features
    def observed_features(*values,**kwargs):
        state.update(state='ENCODING_COMPLETE_AUDIO');save();begin=time.perf_counter()
        result=original_features(*values,**kwargs);torch.cuda.synchronize(device)
        if protocol['runtime'].get('releaseUnusedModelAllocations'):
            torch.cuda.empty_cache()
            state['unusedAllocatorReleases']=state.get('unusedAllocatorReleases',0)+1
        state.update(audioEncodingCacheReused=False,audioEncodingSeconds=time.perf_counter()-begin,
            encodedFeatureBytes=sum(x.numel()*x.element_size() for x in result),state='DECODER_PREFILL');save()
        return result
    model.model.get_audio_features=observed_features
    messages=build_transcription_messages(case['audio'])
    tick=time.perf_counter()
    inputs=prepare_inputs(processor,messages,max_length=protocol['runtime']['maxLength'],device=device).to(device)
    prompt_len=int(inputs['attention_mask'][0].sum().item())
    state.update(inputPreparationSeconds=time.perf_counter()-tick,inputTokens=prompt_len,
        acousticChunks=int(inputs['input_features'].shape[0]),audioFeatureTokenLengths=inputs['audio_feature_lengths'].tolist(),
        inputFeatureShape=list(inputs['input_features'].shape),state='STARTING_GENERATION');save()
    state['llvmJitImportedForPreprocessing']='llvmlite.binding' in sys.modules
    if pacer is not None:pacer.begin()
    generation_start=time.perf_counter()
    class RetainedStreamer(BaseStreamer):
        def __init__(self):self.seen_prompt=False;self.tokens=[];self.written=0
        def put(self,value):
            if not self.seen_prompt:self.seen_prompt=True;return
            self.tokens.extend(value.detach().cpu().reshape(-1).tolist())
            state['generatedTokens']=len(self.tokens)
            if 'firstGeneratedTokenSeconds' not in state:state['firstGeneratedTokenSeconds']=time.perf_counter()-generation_start
            if len(self.tokens)%32==0:self.checkpoint()
        def checkpoint(self):
            try:
                if protocol['runtime'].get('releaseUnusedModelAllocations'):
                    torch.cuda.empty_cache()
                    state['unusedAllocatorReleases']=state.get('unusedAllocatorReleases',0)+1
                with (out/'generated-token-ids.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(self.tokens[self.written:])+'\n')
                self.written=len(self.tokens)
                text=processor.tokenizer.decode(self.tokens,skip_special_tokens=True)
                (out/'partial-transcript.txt').write_text(text,encoding='utf8')
                parsed=parse_transcript(text)
                state.update(state='DECODING',lastCompletedSegmentEndSeconds=max((r.end for r in parsed),default=None),completedSegments=len(parsed),generationElapsedSeconds=time.perf_counter()-generation_start)
            except OSError:state['progressWriteDeferrals']+=1
            save()
        def end(self):self.checkpoint()
    class ExplicitStop(StoppingCriteria):
        def __call__(self,input_ids,scores,**kwargs):return (root/'stop.request').exists()
    streamer=RetainedStreamer();config=model.generation_config
    config.do_sample=False;config.max_new_tokens=protocol['runtime']['maxNewTokensSmoke' if case.get('smokeOnly') else 'maxNewTokensFull']
    with torch.inference_mode():
        output=model.generate(**inputs,generation_config=config,streamer=streamer,
            stopping_criteria=StoppingCriteriaList([ExplicitStop()]))
    torch.cuda.synchronize(device)
    state['generationSeconds']=time.perf_counter()-generation_start
    ids=output[0][prompt_len:].detach().cpu().tolist()
    text=processor.tokenizer.decode(ids,skip_special_tokens=True).strip()
    (out/'raw-transcript.txt').write_text(text,encoding='utf8');(out/'generated-ids.json').write_text(json.dumps(ids),encoding='utf8')
    parsed=parse_transcript(text)
    raw=[{'start':r.start,'end':r.end,'speaker':r.speaker,'text':r.text,'generationIndex':i} for i,r in enumerate(parsed)]
    (out/'raw-parsed-segments.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf8')
    stripped=re.sub(r'\[(?:S\d+|\d+(?:\.\d+)?)\]','',text)
    compact=lambda value:''.join(value.split())
    all_text_parsed=compact(stripped)==compact(''.join(r.text for r in parsed))
    violations=[i for i,r in enumerate(parsed) if not (math.isfinite(r.start) and math.isfinite(r.end) and 0<=r.start<r.end<=case['audioSeconds']+.000001)]
    speaker_map={label:i for i,label in enumerate(dict.fromkeys(r.speaker for r in parsed))}
    ordered=sorted(enumerate(parsed),key=lambda p:(p[1].start,p[1].end,p[0]))
    rows=[{'text':r.text,'startMs':round(r.start*1000),'endMs':round(r.end*1000),
        'speaker':speaker_map[r.speaker],'approximateTiming':False} for _,r in ordered]
    eos=config.eos_token_id;eos_ids={eos} if isinstance(eos,int) else set(eos or [])
    eos_completed=bool(ids and ids[-1] in eos_ids)
    complete=bool(parsed and all_text_parsed and eos_completed and not violations and not (root/'stop.request').exists())
    document={'isFinal':complete,'text':'\n'.join(r['text'] for r in rows),'utterances':rows}
    target=out/'model-output.json';target.write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding='utf8')
    if not violations:
        (out/'predicted.rttm').write_text(''.join(f'SPEAKER meeting 1 {r.start:.6f} {r.end-r.start:.6f} <NA> <NA> {r.speaker} <NA> <NA>\n' for r in parsed),encoding='utf8')
    events=defaultdict(list)
    for r in parsed:
        if 0<=r.start<r.end<=case['audioSeconds']:
            events[r.start].append((r.speaker,1));events[r.end].append((r.speaker,-1))
    active=Counter();maximum=0;overlap_seconds=0.;points=sorted(events)
    for i,point in enumerate(points[:-1]):
        for person,delta in events[point]:
            active[person]+=delta
            if active[person]==0:del active[person]
        maximum=max(maximum,len(active))
        if len(active)>1:overlap_seconds+=points[i+1]-point
    state.update(state='COMPLETE_JOINT_CANDIDATE_UNQUALIFIED' if complete else 'OUTPUT_RETAINED_INCOMPLETE_OR_INVALID',
        generatedTokens=len(ids),eosCompleted=eos_completed,allGeneratedTextParsed=all_text_parsed,
        invalidNativeTimeRows=violations,utterances=len(rows),predictedSpeakers=len(speaker_map),
        nativeSpeakerMap=speaker_map,maxSimultaneousPredictedSpeakers=maximum,predictedOverlapSeconds=overlap_seconds,
        audioSeconds=case['audioSeconds'],nativeTimingScope='Model-predicted sentence boundaries, not validated true word alignment.',
        sourceGenerationOrderRetainedSeparately=True,modelOutputSha256=hashlib.sha256(target.read_bytes()).hexdigest())
except BaseException as error:
    state.update(state='FAILED_RETAINED',errorType=type(error).__name__,error=str(error))
    (out/'failure.txt').write_text(traceback.format_exc(),encoding='utf8');raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-started);save()
    (out/'completed-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(state,ensure_ascii=False),flush=True)
