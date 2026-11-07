"""Pinned native ASR with bounded, raw-preserving failed-decode recovery.

References never enter this worker. The original fixed30s trial is immutable;
normal raw nodes are inherited exactly, while failed nodes retain their IDs
and are covered by shorter disjoint children. This is not voice separation.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import accepted,recover,repeated_block
from moss_windows_resource_limits_20261104 import WorkerLimits
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--phase',choices=['pilot','full'],required=True);p.add_argument('--index',type=int,default=0);p.add_argument('--resume',action='store_true');a=p.parse_args()
C=Path(a.control);read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(C/'protocol.json');base=Path(P['baseControl']);base_protocol=base/'protocol.json'
assert sha(base_protocol)==P['baseProtocolSha256']
N=read(base_protocol);seeds=read(C/'seed-manifest.json');cases=read(C/'audio-only.json');verified_audio={}
assert sha(Path(__file__).with_name('practical_qwen_bounded_decode_20261107.py'))==P['recoverySourceSha256']
assert sha(__file__)==P['workerSourceSha256']
assert P['maximumSplitDepth']==2 and P['minimumLeafSamples']==120000 and P['repeatCopies']==20 and P['maximumRepeatBlockTokens']==8
case=read(C/'audio-only.json')[a.index] if a.phase=='full' else None
out=C/'full/transcripts'/case['meeting'] if case else C/'pilot'
out.mkdir(parents=True,exist_ok=True);(out/'nodes').mkdir(exist_ok=True)
target=out/'state.json';complete=out/'completed-state.json'
binding={'protocolSha256':sha(C/'protocol.json'),'seedManifestSha256':sha(C/'seed-manifest.json'),'workerSourceSha256':sha(__file__),'baseProtocolSha256':P['baseProtocolSha256']}
if case:binding['audioSha256']=case['audioSha256']
cache_only=False
if target.exists():
    assert a.resume;old=read(complete) if complete.exists() and read(complete).get('state')=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' else read(target)
    assert old['binding']==binding
    cache_only=old.get('completedCacheOnly',False) or old['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
    archive=out/('prior-state-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
else:assert not a.resume
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);tick=time.perf_counter()
state={'state':'PREPARING_BOUNDED_NATIVE_ASR','pid':os.getpid(),'startedAt':now(),'binding':binding,'phase':a.phase,'modelLoaded':False,'newNeuralCalls':0,'inheritedRootNodes':0,'reusedNodeFiles':0,'completedCacheOnly':cache_only,'referencePassedToWorker':False,'speakerJournalPending':True}
if case:state.update(meeting=case['meeting'],audioSha256=case['audioSha256'],audioSeconds=case['audioSeconds'])
def save():state['limits']=limits.query();atomic_json(target,state,progress=True)
save();torch=None;model=None;processor=None

def ensure_model():
    global torch,model,processor
    if model is not None:return
    assert not cache_only,'Completed cache is missing; refuse any new model'
    import torch as torch_module
    torch=torch_module;torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip and torch.cuda.device_count()==1
    gpu=torch.cuda.get_device_properties(0)
    assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030'),'Unique dedicated GPU required'
    torch.cuda.set_device(0)
    import transformers
    from transformers import AutoProcessor
    assert transformers.__version__=='5.22.1'
    assert read(N['supportedGpuFeatureNumericProof'])['state']=='PASS_SUPPORTED_GPU_FEATURES_INDEPENDENT_NUMPY_REFERENCE'
    loader=read(N['streamedLoaderControl']);assert loader['state']=='PASS_STANDARD_AND_STREAMED_TINY_QWEN_EXACT_LOGITS_AND_GENERATION'
    assert loader['weightRoundtrip']['loaderSourceSha256']==sha(Path(__file__).with_name('practical_qwen_streamed_loader_20261107.py'))
    for file in N['files']:assert sha(file['file'])==file['sha256']
    state.update(state='LOADING_BOUNDED_NATIVE_ASR',gpu=gpu.name);save();started=time.perf_counter()
    processor=AutoProcessor.from_pretrained(N['modelRoot'],local_files_only=True)
    from practical_qwen_streamed_loader_20261107 import load_model
    weight=next(f for f in N['files'] if Path(f['file']).name=='model.safetensors')
    model,receipt=load_model(N['modelRoot'],torch=torch,device='cuda:0',expected_sha256=weight['sha256'])
    atomic_json(out/'weight-roundtrip.json',receipt)
    state.update(modelLoaded=True,modelLoadSeconds=time.perf_counter()-started);save()

def original_seed(meeting,index):
    key=meeting+'/'+('%06d.raw.json'%index)
    if key not in seeds['files']:return None
    file=base/'full/transcripts'/meeting/'windows'/('%06d.raw.json'%index)
    assert sha(file)==seeds['files'][key]
    packet=read(file)
    assert packet['binding']['audioSha256']==next(c['audioSha256'] for c in cases if c['meeting']==meeting)
    assert packet['binding']['protocolSha256']==P['baseProtocolSha256'] and packet['binding']['workerSourceSha256']==P['baseWorkerSourceSha256']
    assert hashlib.sha256(json.dumps(packet['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==packet['rawSha256']
    state['inheritedRootNodes']+=1
    return packet['raw']

def resolve_span(audio,start,end,*,meeting,index,tag,seed=None):
    audio=Path(audio);fingerprint=(audio.stat().st_size,audio.stat().st_mtime_ns)
    if str(audio) not in verified_audio:
        assert sha(audio)==next(c['audioSha256'] for c in cases if c['meeting']==meeting)
        verified_audio[str(audio)]=fingerprint
    assert verified_audio[str(audio)]==fingerprint,'Original audio changed during this worker'
    with wave.open(str(audio),'rb') as f:
        assert f.getframerate()==16000 and f.getnchannels()==1 and f.getsampwidth()==2
        f.setpos(start);pcm=f.readframes(end-start)
    import numpy as np
    samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
    assert len(samples)==end-start
    from practical_qwen_input_20261107 import is_exact_digital_silence
    def infer(lo,hi):
        part=samples[lo-start:hi-start]
        if is_exact_digital_silence(part):
            return {'index':index,'startSample':lo,'endSample':hi,'text':'','tokens':[],'timestamps':[],'generatedIds':[],'rawDecoded':'','naturalEos':None,'inferenceSeconds':0.,'exactDigitalSilence':True,'neuralInferencePerformed':False}
        ensure_model()
        from transformers import StoppingCriteria,StoppingCriteriaList
        inputs=processor.apply_transcription_request(audio=part,language=N['language'],processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':'cuda:0'}}).to('cuda:0',model.dtype)
        length=inputs['input_ids'].shape[1]
        class StopOnFailedLoop(StoppingCriteria):
            def __call__(self,input_ids,scores,**kwargs):
                if (C/'stop.request').exists():raise InterruptedError('Explicit stop; raw output preserved')
                return repeated_block(input_ids[0,length:].tolist(),suffix_only=True) is not None
        torch.cuda.synchronize();started=time.perf_counter()
        with torch.inference_mode():ids=model.generate(**inputs,max_new_tokens=N['maxNewTokens'],do_sample=N['doSample'],stopping_criteria=StoppingCriteriaList([StopOnFailedLoop()]))
        torch.cuda.synchronize();elapsed=time.perf_counter()-started
        generated=ids[0,length:].cpu().tolist();eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
        raw={'index':index,'startSample':lo,'endSample':hi,'text':processor.tokenizer.decode(generated,skip_special_tokens=True,clean_up_tokenization_spaces=False),'tokens':[],'timestamps':[],'generatedIds':generated,'rawDecoded':processor.decode(generated,skip_special_tokens=False),'naturalEos':bool(generated and generated[-1] in eos),'inferenceSeconds':elapsed,'repeatBlock':repeated_block(generated),'neuralInferencePerformed':True}
        state['newNeuralCalls']+=1;save();time.sleep(N['cooperativePauseSeconds'])
        return raw
    def load(key):
        file=out/'nodes'/(tag+'-'+key+'.json')
        if not file.exists():
            assert not cache_only,'Completed decode node missing; refuse implicit model loading'
            return None
        packet=read(file);assert packet['binding']==binding
        assert hashlib.sha256(json.dumps(packet['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==packet['rawSha256']
        state['reusedNodeFiles']+=1
        return packet['raw']
    def put(key,raw):
        canonical=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        atomic_json(out/'nodes'/(tag+'-'+key+'.json'),{'binding':binding,'raw':raw,'rawSha256':hashlib.sha256(canonical).hexdigest()})
    return recover(start,end,infer=infer,load=load,save=put,seed=seed)

try:
    if a.phase=='pilot':
        ordinary=read(C/'audio-only.json')[0];complex_case=read(C/'audio-only.json')[1]
        old=original_seed(ordinary['meeting'],0)
        normal=resolve_span(ordinary['audio'],0,480000,meeting=ordinary['meeting'],index=0,tag='ordinary-fresh')
        assert len(normal)==1 and normal[0]['raw']['generatedIds']==old['generatedIds'] and normal[0]['raw']['text']==old['text'],'Normal original speech must retain exact generated IDs/text'
        failed=original_seed(complex_case['meeting'],34);assert not accepted(failed)
        recovered=resolve_span(complex_case['audio'],failed['startSample'],failed['endSample'],meeting=complex_case['meeting'],index=34,tag='failed-real30',seed=failed)
        assert len(recovered)>1 and all(accepted(r['raw']) for r in recovered)
        state.update(state='PASS_BOUNDED_NATIVE_PILOT_FULL_QUALITY_UNMEASURED',ordinaryExactGeneratedIdsAndText=True,
          failedParentRawRetained=True,recoveredLeafCount=len(recovered),recoveredText='\n'.join(r['raw']['text'] for r in recovered),
          allOriginalSamplesCoveredByAcceptedLeavesOnce=True,repeatedWordsDeleted=False,qualityQualified=False)
    else:
        pilot=read(C/'pilot/state.json');assert pilot['state']=='PASS_BOUNDED_NATIVE_PILOT_FULL_QUALITY_UNMEASURED' and pilot['binding']['protocolSha256']==binding['protocolSha256']
        audio=Path(case['audio']);assert sha(audio)==case['audioSha256']
        with wave.open(str(audio),'rb') as f:count=f.getnframes()
        size=N['windowSamples'];total=(count+size-1)//size;state.update(totalWindows=total,completedWindows=0);save()
        (out/'windows').mkdir(exist_ok=True);all_leaves=[];split_roots=[]
        for index,start in enumerate(range(0,count,size)):
            end=min(count,start+size);seed=None if (out/'nodes'/('%06d-root.json'%index)).exists() else original_seed(case['meeting'],index)
            leaves=resolve_span(audio,start,end,meeting=case['meeting'],index=index,tag='%06d'%index,seed=seed)
            if len(leaves)>1:split_roots.append(index)
            all_leaves.extend(leaves)
            aggregate={'index':index,'startSample':start,'endSample':end,'text':'\n'.join(r['raw']['text'] for r in leaves),'tokens':[],'timestamps':[],
              'naturalEos':leaves[0]['raw']['naturalEos'] if len(leaves)==1 else None,'isAggregatedRecovery':len(leaves)>1,
              'acceptedLeaves':[{k:r['raw'][k] for k in ['startSample','endSample','naturalEos']}|{'nodeKey':r['key']} for r in leaves]}
            canonical=json.dumps(aggregate,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            atomic_json(out/'windows'/('%06d.raw.json'%index),{'binding':binding,'raw':aggregate,'rawSha256':hashlib.sha256(canonical).hexdigest()})
            draft={'isFinal':False,'text':'\n'.join(r['raw']['text'] for r in all_leaves),'utterances':[{'text':r['raw']['text'],'startMs':round(r['raw']['startSample']/16),'endMs':round(r['raw']['endSample']/16),'speaker':None,'approximateTiming':True} for r in all_leaves if r['raw']['text'].strip()]}
            atomic_json(out/'text-draft.json',draft)
            state.update(state='RUNNING_BOUNDED_NATIVE_FULL_ASR',completedWindows=index+1,completedSample=end,recoveredRootIndices=split_roots);save()
        assert all_leaves[0]['raw']['startSample']==0 and all_leaves[-1]['raw']['endSample']==count
        assert all(x['raw']['endSample']==y['raw']['startSample'] for x,y in zip(all_leaves,all_leaves[1:]))
        doc={**draft,'isFinal':True};atomic_json(out/'model-output.json',doc)
        attribution={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'binding':binding,'rawWindowText':doc['text'],'allOriginalAudioSamplesCoveredOnce':True,'allTextPreservedThroughAttribution':True,'tokenEstimates':[],'utterancesWithAttribution':doc['utterances'],'scope':'Bounded failed-decode recovery, not overlap voice separation or verified word timestamps/identity. Every accepted leaf raw word retained; failed parent raw nodes remain separate.'}
        atomic_json(out/'attribution-review.json',attribution)
        state.update(state='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED',allAudioSamplesCoveredOnce=True,allAsrTextPreserved=True,qualityQualified=False,modelOutputSha256=sha(out/'model-output.json'),attributionReviewSha256=sha(out/'attribution-review.json'),acceptedLeafCount=len(all_leaves))
        if case['meeting']=='S_R004S03C01' and not split_roots:
            state['originalOrdinaryWholeDocumentIdentical']=sha(out/'model-output.json')==sha(base/'full/transcripts'/case['meeting']/'model-output.json')
            assert state['originalOrdinaryWholeDocumentIdentical']
except BaseException as error:
    state.update(state='FAILED_BOUNDED_NATIVE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query())
    atomic_json(target,state);atomic_json(complete,state);print(json.dumps(state,ensure_ascii=False),flush=True)
