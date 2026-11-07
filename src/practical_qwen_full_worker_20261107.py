"""Full original audio with official native ASR and durable per-window output.

Unknown speakers and coarse input-window times stay explicit. No reference,
VAD omission, cleanup rewrite, repetition filter or hotword prompt is used.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',HF_ENABLE_PARALLEL_LOADING='false')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--index',required=True,type=int);p.add_argument('--resume',action='store_true');a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
P=read(C.parent/'protocol.json');case=read(C/'audio-only.json')[a.index]
proof=read(C.parent/'short-native-state.json');assert proof['state']=='PASS_OFFICIAL_NATIVE_SHORT_EXECUTION_FULL_QUALITY_UNMEASURED'
assert proof['sourceSha256']==sha(Path(__file__).with_name('practical_qwen_native_worker_20261107.py'))
assert proof['modelRevision']==P['revision'] and proof['transformersVersion']=='5.22.1'
assert P['featureDevice']=='selected_gpu' and P['textPostprocessing']=='direct_tokenizer_skip_special_tokens_only_no_cleanup_no_repetition_fix'
loader_proof=read(P['streamedLoaderControl']);assert loader_proof['state']=='PASS_STANDARD_AND_STREAMED_TINY_QWEN_EXACT_LOGITS_AND_GENERATION'
assert loader_proof['weightRoundtrip']['loaderSourceSha256']==sha(Path(__file__).with_name('practical_qwen_streamed_loader_20261107.py'))
assert not any('reference' in k.lower() for k in case)
assert P['backend']=='official_native_transformers' and P['dtype']=='bfloat16' and P['attnImplementation']=='eager' and P['maxNewTokens']==512 and not P['doSample'] and P['prompt'] is None and P['windowSamples']==480000
out=C/'transcripts'/case['meeting'];out.mkdir(parents=True,exist_ok=a.resume);chunks=out/'windows';chunks.mkdir(exist_ok=a.resume)
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);tick=time.perf_counter();target=out/'state.json'
import numpy as np
from practical_qwen_input_20261107 import is_exact_digital_silence
assert P['digitalSilencePolicy']=='skip_only_exact_zero_no_threshold_no_nonzero_cut'
assert sha(Path(__file__).with_name('practical_qwen_input_20261107.py'))==P['digitalSilenceGuardSourceSha256']
binding={'audioSha256':case['audioSha256'],'protocolSha256':sha(C.parent/'protocol.json'),'workerSourceSha256':sha(__file__),'officialShortWorkerSourceSha256':proof['sourceSha256']}
state={'state':'PREPARING_OFFICIAL_NATIVE_FULL_ASR','pid':os.getpid(),'startedAt':now(),'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'modelLoaded':False,'newNeuralWindows':0,'reusedWindows':0,'referencePassedToWorker':False,'speakerJournalPending':True,'priorAttemptSeconds':0.}
if a.resume:
    complete_path=out/'completed-state.json'
    old=read(complete_path) if complete_path.exists() and read(complete_path).get('state')=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' else read(target)
    assert old['binding']==binding
    state['priorAttemptSeconds']=old.get('priorAttemptSeconds',0)+old.get('wholeWorkerSeconds',0)
    state['completedCacheOnly']=old['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' or old.get('completedCacheOnly',False)
    archive=out/('prior-state-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
state['binding']=binding
def save():
    state['limits']=limits.query();atomic_json(target,state,progress=True)
save();model=None;processor=None;torch=None
try:
    assert sha(case['audio'])==case['audioSha256']
    raws=[]
    with wave.open(case['audio'],'rb') as audio:
        assert audio.getframerate()==16000 and audio.getnchannels()==1 and audio.getsampwidth()==2
        count=audio.getnframes();assert count/16000==case['audioSeconds'];size=P['windowSamples']
        state.update(totalWindows=(count+size-1)//size,completedWindows=0);save()
        for index,start in enumerate(range(0,count,size)):
            if (C/'stop.request').exists() or (C.parent/'stop.request').exists():raise InterruptedError('Own full task explicitly stopped')
            end=min(count,start+size);file=chunks/('%06d.raw.json'%index)
            fresh_zero=False
            if not file.exists():
                assert not state.get('completedCacheOnly'),'Completed raw cache missing; no new model may be loaded'
                audio.setpos(start);pcm=np.frombuffer(audio.readframes(end-start),dtype='<i2');assert len(pcm)==end-start
                if is_exact_digital_silence(pcm):
                    raw={'index':index,'startSample':start,'endSample':end,'text':'','tokens':[],'timestamps':[],'generatedIds':[],'rawDecoded':'','naturalEos':None,'inferenceSeconds':0.,'exactDigitalSilence':True,'neuralInferencePerformed':False}
                    canonical=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
                    atomic_json(file,{'binding':binding,'raw':raw,'rawSha256':hashlib.sha256(canonical).hexdigest()});fresh_zero=True
            if file.exists():
                assert a.resume or fresh_zero;packet=read(file);assert packet['binding']==binding
                raw=packet['raw'];assert hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==packet['rawSha256']
                assert raw['index']==index and raw['startSample']==start and raw['endSample']==end
                if not fresh_zero:state['reusedWindows']+=1
            else:
                assert not state.get('completedCacheOnly'),'Completed raw ASR missing; refuse implicit neural rerun'
                if model is None:
                    for item in P['files']:assert sha(item['file'])==item['sha256']
                    import torch
                    torch.set_num_threads(1);torch.set_num_interop_threads(1)
                    assert torch.version.hip and torch.cuda.device_count()==1
                    info=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in info.name and info.gcnArchName.startswith('gfx1030')
                    torch.cuda.set_device(0)
                    import transformers
                    from transformers import AutoModelForMultimodalLM,AutoProcessor,StoppingCriteria,StoppingCriteriaList
                    assert transformers.__version__=='5.22.1'
                    state.update(state='LOADING_OFFICIAL_NATIVE_FULL_ASR',gpu=info.name,transformersVersion=transformers.__version__);save();t=time.perf_counter()
                    processor=AutoProcessor.from_pretrained(P['modelRoot'],local_files_only=True)
                    from practical_qwen_streamed_loader_20261107 import load_model
                    weight=next(item for item in P['files'] if Path(item['file']).name=='model.safetensors')
                    model,weight_receipt=load_model(P['modelRoot'],torch=torch,device='cuda:0',expected_sha256=weight['sha256'])
                    atomic_json(out/'weight-roundtrip.json',weight_receipt)
                    state.update(modelLoaded=True,modelLoadSeconds=time.perf_counter()-t);save()
                    class StopOnlyThisTask(StoppingCriteria):
                        def __call__(self,input_ids,scores,**kwargs):
                            if (C/'stop.request').exists() or (C.parent/'stop.request').exists():raise InterruptedError('Owned task stopped')
                            return False
                    import numpy as np
                audio.setpos(start);samples=np.frombuffer(audio.readframes(end-start),dtype='<i2').astype(np.float32)/32768;assert len(samples)==end-start
                inputs=processor.apply_transcription_request(audio=samples,language='Chinese',processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':'cuda:0'}}).to('cuda:0',model.dtype)
                length=inputs['input_ids'].shape[1];torch.cuda.synchronize();t=time.perf_counter()
                with torch.inference_mode():ids=model.generate(**inputs,max_new_tokens=512,do_sample=False,stopping_criteria=StoppingCriteriaList([StopOnlyThisTask()]))
                torch.cuda.synchronize();seconds=time.perf_counter()-t;generated=ids[0,length:].cpu().tolist();eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
                raw={'index':index,'startSample':start,'endSample':end,'text':processor.tokenizer.decode(generated,skip_special_tokens=True,clean_up_tokenization_spaces=False),'tokens':[],'timestamps':[],'generatedIds':generated,'rawDecoded':processor.decode(generated,skip_special_tokens=False),'naturalEos':bool(generated and generated[-1] in eos),'inferenceSeconds':seconds}
                canonical=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
                atomic_json(file,{'binding':binding,'raw':raw,'rawSha256':hashlib.sha256(canonical).hexdigest()});state['newNeuralWindows']+=1
                assert raw['naturalEos'],'Generation hit the limit; retain raw partial output, do not silently label final'
                if case['meeting']=='S_R004S03C01' and index==0:
                    short=read(C.parent/'S-original-first30s-output.json')
                    assert generated==short['generatedIds'] and raw['text']==short['text'],'Identical original first30s must match passed short native control exactly'
                    state['first30sNativeShortExactIdsAndText']=True
                time.sleep(P['cooperativePauseSeconds'])
            if raw.get('exactDigitalSilence'):
                audio.setpos(start);assert is_exact_digital_silence(np.frombuffer(audio.readframes(end-start),dtype='<i2'))
                assert raw['text']=='' and raw['generatedIds']==[] and raw['naturalEos'] is None
                state['exactDigitalZeroWindows']=state.get('exactDigitalZeroWindows',0)+1
            else:assert raw['naturalEos'],'An incomplete cached native decode cannot silently become a final window'
            if case['meeting']=='S_R004S03C01' and index==0:
                short=read(C.parent/'S-original-first30s-output.json')
                assert raw['generatedIds']==short['generatedIds'] and raw['text']==short['text']
                state['first30sNativeShortExactIdsAndText']=True
            raws.append(raw);state.update(state='RUNNING_FULL_OFFICIAL_NATIVE_ASR',completedWindows=index+1,completedSample=end);save()
            draft={'isFinal':False,'text':'\n'.join(r['text'] for r in raws),'utterances':[{'text':r['text'],'startMs':round(r['startSample']/16),'endMs':round(r['endSample']/16),'speaker':None,'approximateTiming':True} for r in raws if r['text'].strip()]}
            atomic_json(out/'text-draft.json',draft)
    assert raws[0]['startSample']==0 and raws[-1]['endSample']==count and all(x['endSample']==y['startSample'] for x,y in zip(raws,raws[1:]))
    doc={**draft,'isFinal':True};atomic_json(out/'model-output.json',doc)
    review={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'binding':binding,'rawWindowText':doc['text'],'allOriginalAudioSamplesCoveredOnce':True,'allTextPreservedThroughAttribution':True,'tokenEstimates':[],'utterancesWithAttribution':doc['utterances'],'scope':'Full official native ASR. No word timestamps or speaker identity established. Original input window times approximate; all participants remain unknown until separately validated alignment/diarization. No both-voices or minutes acceptance.'}
    atomic_json(out/'attribution-review.json',review)
    state.update(state='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED',allAudioSamplesCoveredOnce=True,allAsrTextPreserved=True,modelOutputSha256=sha(out/'model-output.json'),attributionReviewSha256=sha(out/'attribution-review.json'),qualityQualified=False)
except BaseException as error:
    state.update(state='FAILED_OFFICIAL_NATIVE_FULL_ASR_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(target,state);atomic_json(out/'completed-state.json',state);print(json.dumps(state),flush=True)
