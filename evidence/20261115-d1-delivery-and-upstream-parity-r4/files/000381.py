"""Align unchanged recognized text; no references or speaker labels enter inference."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_alignment_text_20261107 import source_text_spans
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['pilot','full'],required=True);parser.add_argument('--resume',action='store_true');parser.add_argument('--control',type=Path,required=True);args=parser.parse_args()
C=args.control.resolve()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
P=read(C/'protocol.json');source=read(C/'model-source.json');plan=read(C/'audio-text-only.json')
assert sha(__file__)==P['workerSourceSha256']
assert sha(C/'model-source.json')==P['modelSourceSha256'] and sha(C/'audio-text-only.json')==P['inputPlanSha256']
for file,digest in P['helperSources'].items():assert sha(Path(__file__).with_name(file))==digest
for file,digest in P['runtimeSources'].items():assert sha(file)==digest
binding={'protocolSha256':sha(C/'protocol.json'),'planSha256':sha(C/'audio-text-only.json'),'modelSourceSha256':sha(C/'model-source.json')}
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);tick=time.perf_counter();target=C/('pilot-state.json' if args.phase=='pilot' else 'full-state.json')
if target.exists():
    assert args.resume;old=read(target);assert old['binding']==binding
    archive=C/('prior-'+target.stem+'-'+sha(target)[:12]+'.json')
    if not archive.exists():archive.write_bytes(target.read_bytes())
else:assert not args.resume
state={'state':'PREPARING_NATIVE_ALIGNER','pid':os.getpid(),'startedAt':now(),'phase':args.phase,'binding':binding,'modelLoaded':False,'newNeuralCalls':0,'reusedNodes':0,'completedLeaves':0,'referencePassedToWorker':False,'speakerLabelsPassedToWorker':False,'qualityQualified':False}
def save():state['limits']=limits.query();atomic_json(target,state,progress=True)
save();torch=None;model=None;processor=None
def ensure_model():
    global torch,model,processor
    if model is not None:return
    proof=read(C/'tiny-loader-proof.json')
    assert proof['state']=='PASS_STANDARD_AND_STREAMED_TINY_ALIGNER_EXACT_LOGITS'
    assert proof['weightRoundtrip']['loaderSourceSha256']==P['helperSources']['practical_alignment_loader_20261107.py']
    assert read(C/'preparation.json')['state']=='PINNED_NATIVE_ALIGNER_READY_NO_INFERENCE'
    import torch as module
    torch=module;torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip and torch.cuda.device_count()==1
    gpu=torch.cuda.get_device_properties(0)
    assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
    torch.cuda.set_device(0)
    import transformers
    assert transformers.__version__=='5.22.1'
    from transformers import AutoProcessor
    from practical_alignment_loader_20261107 import load_aligner
    for item in source['files']:assert sha(item['file'])==item['sha256']
    state.update(state='LOADING_NATIVE_ALIGNER',gpu=gpu.name);save()
    processor=AutoProcessor.from_pretrained(source['modelRoot'],local_files_only=True)
    model,receipt=load_aligner(source['modelRoot'],torch=torch,device='cuda:0',expected_sha256=next(f['sha256'] for f in source['files'] if Path(f['file']).name=='model.safetensors'))
    atomic_json(C/('weight-roundtrip-'+args.phase+'.json'),receipt)
    state.update(modelLoaded=True,modelLoadSeconds=receipt['loadSeconds']);save()
try:
    selected=[(case,leaf) for case in plan for leaf in case['leaves']]
    if args.phase=='pilot':selected=[next((c,l) for c,l in selected if l['text'].strip())]
    else:
        assert read(C/'pilot-state.json')['state']=='COMPLETE_NATIVE_ALIGNMENT_PILOT_NOT_TIME_QUALIFIED'
    state.update(totalLeaves=len(selected));save()
    for case,leaf in selected:
        if state.get('meeting')!=case['meeting']:
            assert sha(case['audio'])==case['audioSha256']
        name=case['meeting'];directory=C/'aligned'/name;directory.mkdir(parents=True,exist_ok=True)
        dest=directory/(leaf['id']+'.json');node_binding={**binding,'sourceNodeSha256':leaf['nodeSha256'],'meeting':name}
        state.update(meeting=name,leaf=leaf['id'])
        assert sha(leaf['nodeFile'])==leaf['nodeSha256']
        original=read(leaf['nodeFile'])['raw'];assert sha(case['sourceDocument'])==case['sourceDocumentSha256']
        assert original['text']==leaf['text'] and original['startSample']==leaf['startSample'] and original['endSample']==leaf['endSample']
        if dest.exists():
            packet=read(dest);assert packet['binding']==node_binding
            assert packet['payloadSha256']==hashlib.sha256(json.dumps(packet['payload'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            state['reusedNodes']+=1
        elif not leaf['text']:
            payload={'originalText':'','originalStartSample':leaf['startSample'],'originalEndSample':leaf['endSample'],
                'units':[],'allOriginalCharactersPreserved':True,'neuralInferencePerformed':False,
                'inferenceSeconds':0.,'unresolvedTimeUnits':0,'wordTimeAccuracyQualified':False,
                'reason':'No recognized text to align; no words invented from an empty source.'}
            canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            atomic_json(dest,{'binding':node_binding,'payload':payload,'payloadSha256':hashlib.sha256(canonical).hexdigest()})
        else:
            assert not (C/'stop.request').exists(),'Explicit stop, committed alignment nodes retained'
            ensure_model()
            with wave.open(case['audio'],'rb') as stream:stream.setpos(leaf['startSample']);pcm=stream.readframes(leaf['endSample']-leaf['startSample'])
            import numpy as np
            samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
            assert len(samples)==leaf['endSample']-leaf['startSample']
            inputs,word_lists=processor.prepare_forced_aligner_inputs(audio=samples,transcript=leaf['text'],language=leaf.get('alignmentLanguage','Chinese'),processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':'cuda:0'}})
            mapping=source_text_spans(leaf['text'],word_lists[0])
            assert mapping is not None,'Lexical mapping unavailable: preserve original text; never substitute tokenizer output'
            inputs=inputs.to('cuda:0',model.dtype)
            valid_frames=int(inputs['input_features_mask'].sum().item());assert valid_frames>=len(samples)//160
            torch.cuda.synchronize();started=time.perf_counter()
            with torch.inference_mode():logits=model(**inputs,use_cache=False).logits
            torch.cuda.synchronize();elapsed=time.perf_counter()-started
            classes=logits.argmax(-1)[0][inputs['input_ids'][0]==model.config.timestamp_token_id].cpu().tolist()
            assert len(classes)==2*len(mapping)
            decoded=processor.decode_forced_alignment(logits=logits,input_ids=inputs['input_ids'],word_lists=word_lists,timestamp_token_id=model.config.timestamp_token_id)[0]
            assert len(decoded)==len(mapping) and all(a['text']==b['alignmentUnit'] for a,b in zip(decoded,mapping))
            duration=len(samples)/16000;units=[];repairs=0
            for index,(row,span) in enumerate(zip(decoded,mapping)):
                start,end=row['start_time'],row['end_time']
                raw_start=classes[2*index]*processor.timestamp_segment_time/1000
                raw_end=classes[2*index+1]*processor.timestamp_segment_time/1000
                repairs+=int(abs(start-raw_start)>.0005)+int(abs(end-raw_end)>.0005)
                valid=0<=start<end<=duration
                units.append({**span,'predictedStartSeconds':start,'predictedEndSeconds':end,
                    'absoluteStartSeconds':leaf['startSample']/16000+start if valid else None,
                    'absoluteEndSeconds':leaf['startSample']/16000+end if valid else None,
                    'positiveAndInOriginalLeafBounds':valid,'timestampVerifiedAgainstTruth':False})
            assert ''.join(u['text'] for u in units)==leaf['text']
            payload={'originalText':leaf['text'],'originalStartSample':leaf['startSample'],'originalEndSample':leaf['endSample'],
                'rawTimestampClassIds':classes,'timestampClassMilliseconds':processor.timestamp_segment_time,
                'authorMonotonicRepairChangedTimestamps':repairs,'units':units,'allOriginalCharactersPreserved':True,
                'inferenceSeconds':elapsed,'inputNotTruncated':True,'validMelFrames':valid_frames,
                'neuralInferencePerformed':True,
                'unresolvedTimeUnits':sum(not u['positiveAndInOriginalLeafBounds'] for u in units),
                'noAsrOrReferenceWordsSubstituted':True,'wordTimeAccuracyQualified':False}
            canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            atomic_json(dest,{'binding':node_binding,'payload':payload,'payloadSha256':hashlib.sha256(canonical).hexdigest()})
            state['newNeuralCalls']+=1
            del logits,inputs
            time.sleep(1)
        state['completedLeaves']+=1;state.update(state='ALIGNING_EXISTING_RECOGNIZED_TEXT');save()
    if args.phase=='pilot':
        probe=read(C/'aligned'/selected[0][0]['meeting']/(selected[0][1]['id']+'.json'))['payload']
        assert len(probe['units'])>=1 and any(u['positiveAndInOriginalLeafBounds'] for u in probe['units'])
    state.update(state='COMPLETE_NATIVE_ALIGNMENT_PILOT_NOT_TIME_QUALIFIED' if args.phase=='pilot' else 'COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED',allOriginalCharactersPreserved=True,asrNeuralCalls=0)
except BaseException as error:
    state.update(state='FAILED_NATIVE_ALIGNMENT_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=now(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query())
    atomic_json(target,state);print(json.dumps(state,ensure_ascii=False),flush=True)
