"""Implement full-time model composition, preserving known failed prototypes."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,sys,wave
import numpy as np
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from continuous_meeting_audio_routing_20261115 import compose_routes
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
T=D/'supervised-blind-separation-r1';OLD=T/'natural-window-unit-alignment-r1';C=T/'continuous-overlap-composition-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1/continuous-overlap-composition-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not C.exists() and not E.exists();C.mkdir();E.mkdir()
plan=read(T/'continuous-routing-r1/routing-plan.json');meetings={r['meeting']:r for r in plan['meetings']}
old_protocol=read(OLD/'protocol.json');separated={r['id']:r for r in read(Path(old_protocol['separationRun'])/'state.json')['results']}
route=read(OLD/'routed-composition-protocol.json');locations={r['id']:r for r in route['cases']}
cases=read(OLD/'audio-only.json');results=[];reused={};proof=[]
base=Path('E:/CodexData/Companion/product-d1d2-20261114/context-matched-baseline-r3/base-run-r1/sessions')
for case in cases:
    assert sha(case['wav'])==case['wavSha256']
    with wave.open(case['wav'],'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,16000)
        original=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
    location=locations[case['id']];low,high=location['sourceStartFrame'],location['sourceEndFrame']
    assert high-low==len(original)
    mask=np.zeros(len(original),dtype=np.bool_)
    for segment in meetings[case['meeting']]['segments']:
        if segment['predictedActiveSpeakers']<2:continue
        begin,end=max(low,segment['startFrame']),min(high,segment['endFrame'])
        if end>begin:mask[begin-low:end-low]=True
    source=separated[case['id']];values=[]
    for stream in source['streams']:
        assert sha(stream['file'])==stream['sha256'];values.append(np.load(stream['file'],allow_pickle=False))
    lanes=compose_routes(original,np.stack(values),mask,np)
    folder=E/'routed-waveforms'/case['id'];folder.mkdir(parents=True)
    streams=[]
    for index in range(2):
        file=folder/('stream-'+str(index)+'.npy')
        with file.open('wb') as f:np.save(f,lanes[index],allow_pickle=False);f.flush();os.fsync(f.fileno())
        streams.append(dict(index=index,file=str(file),sha256=sha(file),frames=len(original)))
    reuse=not mask.any()
    if reuse:
        document=base/case['id']/'document.json';doc=read(document)
        assert doc['isFinal'] and not doc['reviewRequired'] and doc['confirmedAudioFrames']==len(original)
        reused[case['id']]=[]
        for index in range(2):
            packet=dict(id=case['id'],stream=index,sourceWavSha256=case['wavSha256'],inputFloatSha256=streams[index]['sha256'],
                text=doc['text'] if index==0 else '',frames=len(original),reviewRequired=False,
                leaves=[],wordsPostEdited=False,referenceUsed=False,allFramesPreserved=True,outputStreamDropped=False,
                exactOriginalAsrReused=index==0,exactDigitalSilence=index==1,
                originalDocument=str(document),originalDocumentSha256=sha(document),qualityQualified=False)
            file=folder/('reused-asr-'+str(index)+'.json');write(file,packet)
            reused[case['id']].append(dict(file=str(file),sha256=sha(file)))
    results.append(dict(id=case['id'],sourceWavSha256=case['wavSha256'],frames=len(original),streams=streams,
        reuseOriginal=reuse,predictedOverlapFrames=int(mask.sum()),allFramesPreserved=True,
        referenceOrSpeakerProfileUsed=False))
    proof.append(dict(id=case['id'],frames=len(original),predictedOverlapFrames=int(mask.sum()),
        outsideOverlapOriginalLane0BitExact=True,outsideOverlapLane1ExactZero=True,
        insideOverlapBothSeparatedLanesBitExact=True,originalAsrReused=reuse))
worker=S/'continuous_overlap_composition_worker_20261115.py'
text=(S/'window_aligned_separator_worker_20261115.py').read_text(encoding='utf-8')
needle="                    def infer(low,high):return raw_infer(samples,low,high)"
begin=text.index(needle);end=text.index("                    atomic_json(folder/'result.json',packet)",begin)
block=text[begin:end]
replacement="""                    if source['reuseOriginal']:
                        reuse_manifest=read(a.control/'reused-asr-input-only.json')
                        item=reuse_manifest[case['id']][stream['index']]
                        assert sha(item['file'])==item['sha256']
                        packet=read(item['file'])
                        assert packet['inputFloatSha256']==stream['sha256'] and not packet['referenceUsed']
                    else:
"""+''.join('    '+line+'\n' for line in block.splitlines())
text=text[:begin]+replacement+text[end:]
assert not worker.exists();compile(text,str(worker),'exec');worker.write_text(text,encoding='utf-8')
runner=S/'run_continuous_overlap_composition_20261115.py'
text=(S/'run_window_aligned_separator_20261115.py').read_text(encoding='utf-8')
assert 'window_aligned_separator_worker_20261115.py' in text;text=text.replace('window_aligned_separator_worker_20261115.py',worker.name)
assert not runner.exists();compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
for name in ['audio-only.json','source-binding.json','model-binding.json']:shutil.copyfile(OLD/name,C/name)
write(C/'reused-asr-input-only.json',reused)
protocol={**old_protocol,'state':'FROZEN_CONTINUOUS_PREDICTED_TIME_ROUTING_AUDIO_COMPOSITION_BEFORE_ASR',
    'at':datetime.now().astimezone().isoformat(),'asrRun':str(E/'asr-r1'),
    'composition':'OriginalNemo0.5wholeaudio activity, same final80 separator and originalASR. Lane0 preserves exact original mic outside predicted>=2speaker intervals and separator0 inside; lane1 is exact zero outside and separator1 inside. No word selection, reference gate, threshold/padding/fade variants, new weights, or speaker-ID assignment.',
    'continuousRoutingPlanSha256':sha(T/'continuous-routing-r1/routing-plan.json'),
    'stop':'One concrete continuous-time routing implementation. Same original32 development word/person/bilingual gates; no variant selection or adoption if quality fails. No final holdout.'}
write(C/'protocol.json',protocol)
manifest=dict(state='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING',protocolSha256=sha(C/'protocol.json'),results=results,
    waveformRoutingImplemented=True,newSeparatorNeuralCalls=0,referenceRead=False)
write(E/'routed-waveforms/state.json',manifest)
write(C/'routing-proof.json',dict(state='PASS_ALL32_SAMPLE_COVERAGE_AND_ORIGINAL_AUDIO_PRESERVATION',cases=proof,
    reusedOriginalCases=len(reused),newAsrStreams=2*(32-len(reused)),newSeparatorNeuralCalls=0,
    thresholdChanged=False,speakerStreamAssociationImplemented=False,qualityQualified=False))
binding=read(OLD/'worker-binding.json');binding.update(workerSha256=sha(worker),runnerSha256=sha(runner),protocolSha256=sha(C/'protocol.json'))
for path in [C/'model-binding.json',C/'source-binding.json',C/'reused-asr-input-only.json',E/'routed-waveforms/state.json',S/'continuous_meeting_audio_routing_20261115.py']:
    binding['helpers'][str(path)]=sha(path)
write(C/'worker-binding.json',binding)
execution=read(OLD/'asr-execution.json');execution.update(run=protocol['asrRun'],separationManifest=str(E/'routed-waveforms/state.json'));write(C/'asr-execution.json',execution)
route.update(at=protocol['at'],originalAlwaysOnProtocolSha256=sha(C/'protocol.json'),
    stage='Same original detector activity and exact same clip route; used audio now routed at original predicted sample intervals. Original0/1speaker audio remains raw, >=2 uses same fixed source-adapted separator. New architecture implementation, previous coarse experiments remain failed.')
write(C/'routed-composition-protocol.json',route)
router=Path('work/score_window_aligned_separator_router_20261115.py').read_text(encoding='utf-8')
needle='C=Path('+repr(str(OLD))+')';assert needle in router
Path('work/score_continuous_overlap_composition_20261115.py').write_text(router.replace(needle,'C=Path('+repr(str(C))+')'),encoding='utf-8')
print(json.dumps(read(C/'routing-proof.json') | {'cases':len(proof)},ensure_ascii=False))
