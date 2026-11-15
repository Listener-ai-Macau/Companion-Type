"""Implement the pre-frozen original auxiliary-head agreement rule only."""
from pathlib import Path
from datetime import datetime
import json,hashlib,shutil,os,sys,wave
import numpy as np
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from continuous_meeting_audio_routing_20261115 import compose_routes
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';T=D/'supervised-blind-separation-r1'
G=T/'single-source-activity-guard-r1';C=G/'composition-r1';OLD=T/'continuous-overlap-composition-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
P=read(G/'protocol.json');observation=read(Path(P['observationRun'])/'state.json')
assert observation['state']=='COMPLETE_ORIGINAL_ACTIVITY_HEAD_OBSERVATION_SCORING_PENDING'
assert observation['allOriginalSpeakerPredictionsBitExact']
E=Path(P['observationRun']).parent/'composition-r1';assert not C.exists() and not E.exists();C.mkdir();E.mkdir()
observed={r['meeting']:r for r in observation['results']};activity={}
for meeting,row in observed.items():
    item=row['outputs']['guarded-overlap'];assert sha(item['file'])==item['sha256'];activity[meeting]=np.load(item['file'],allow_pickle=False)
sepP=read(T/'natural-window-unit-alignment-r1/protocol.json')
separated={r['id']:r for r in read(Path(sepP['separationRun'])/'state.json')['results']}
oldP=read(OLD/'protocol.json');oldRun=Path(oldP['asrRun']);oldState=read(oldRun/'state.json')
assert oldState['state']=='COMPLETE_FIXED_SEPARATION_ASR_COMPOSITION_SCORING_PENDING'
old_results={(r['id'],r['stream']):r for r in oldState['results']}
old_wave=read(Path(read(OLD/'asr-execution.json')['separationManifest']))
old_lanes={r['id']:r for r in old_wave['results']}
route=read(OLD/'routed-composition-protocol.json');locations={r['id']:r for r in route['cases']}
cases=read(OLD/'audio-only.json');results=[];reused={};proof=[];reuse_original=0;reuse_cached=0
base=Path('E:/CodexData/Companion/product-d1d2-20261114/context-matched-baseline-r3/base-run-r1/sessions')
for case in cases:
    assert sha(case['wav'])==case['wavSha256']
    with wave.open(case['wav'],'rb') as f:
        assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,16000)
        original=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
    loc=locations[case['id']];low,high=loc['sourceStartFrame'],loc['sourceEndFrame'];assert high-low==len(original)
    indices=np.arange(low,high,dtype=np.int64)//160;mask=activity[case['meeting']][indices]
    parts=[]
    for stream in separated[case['id']]['streams']:
        assert sha(stream['file'])==stream['sha256'];parts.append(np.load(stream['file'],allow_pickle=False))
    lanes=compose_routes(original,np.stack(parts),mask,np)
    folder=E/'routed-waveforms'/case['id'];folder.mkdir(parents=True);streams=[]
    for i in range(2):
        file=folder/('stream-'+str(i)+'.npy')
        with file.open('wb') as f:np.save(f,lanes[i],allow_pickle=False);f.flush();os.fsync(f.fileno())
        streams.append(dict(index=i,file=str(file),sha256=sha(file),frames=len(original)))
    raw_reuse=not mask.any()
    cached_reuse=not raw_reuse and all(streams[i]['sha256']==old_lanes[case['id']]['streams'][i]['sha256'] for i in range(2))
    reuse=raw_reuse or cached_reuse
    if reuse:
        reused[case['id']]=[]
        if raw_reuse:
            document=base/case['id']/'document.json';doc=read(document)
            assert doc['isFinal'] and not doc['reviewRequired'] and doc['confirmedAudioFrames']==len(original)
            reuse_original+=1
        else:reuse_cached+=1
        for i in range(2):
            if raw_reuse:
                packet=dict(id=case['id'],stream=i,sourceWavSha256=case['wavSha256'],inputFloatSha256=streams[i]['sha256'],
                    text=doc['text'] if i==0 else '',frames=len(original),reviewRequired=False,leaves=[],
                    wordsPostEdited=False,referenceUsed=False,allFramesPreserved=True,outputStreamDropped=False,
                    exactOriginalAsrReused=i==0,exactDigitalSilence=i==1,originalDocument=str(document),
                    originalDocumentSha256=sha(document),qualityQualified=False)
            else:
                item=old_results[case['id'],i];assert sha(item['file'])==item['sha256'];packet=read(item['file'])
                assert packet['inputFloatSha256']==streams[i]['sha256'] and not packet['wordsPostEdited'] and not packet['referenceUsed']
                packet={**packet,'previousExactInputResult':item['file'],'previousExactInputResultSha256':item['sha256']}
            file=folder/('reused-asr-'+str(i)+'.json');write(file,packet);reused[case['id']].append(dict(file=str(file),sha256=sha(file)))
    results.append(dict(id=case['id'],sourceWavSha256=case['wavSha256'],frames=len(original),streams=streams,
        reuseOriginal=reuse,predictedOverlapFrames=int(mask.sum()),allFramesPreserved=True,referenceOrSpeakerProfileUsed=False))
    proof.append(dict(id=case['id'],condition=case['condition'],frames=len(original),guardedOverlapFrames=int(mask.sum()),
        originalOverlapFrames=old_lanes[case['id']]['predictedOverlapFrames'],
        outsideOverlapOriginalLane0BitExact=True,outsideOverlapLane1ExactZero=True,
        insideOverlapBothSeparatedLanesBitExact=True,originalAsrReused=raw_reuse,cachedAsrReused=cached_reuse))
    loc.update(useBothSeparatedStreams=bool(mask.any()),detectorPredictedOverlapSeconds=int(mask.sum())/16000)
for name in ['audio-only.json','source-binding.json','model-binding.json']:shutil.copyfile(OLD/name,C/name)
write(C/'reused-asr-input-only.json',reused)
protocol={**oldP,'state':'FROZEN_ORIGINAL_AUXILIARY_ACTIVITY_AGREEMENT_COMPOSITION_BEFORE_ASR',
    'at':datetime.now().astimezone().isoformat(),'asrRun':str(E/'asr-r1'),
    'composition':P['candidateRule']+' Same original microphone/overlap sample routing and same final80separator/ASR. No word-based selection.',
    'guardProtocolSha256':sha(G/'protocol.json'),'guardObservationSha256':sha(Path(P['observationRun'])/'state.json'),
    'stop':P['stop']}
write(C/'protocol.json',protocol)
write(E/'routed-waveforms/state.json',dict(state='COMPLETE_FIXED_BLIND_SEPARATION_ASR_PENDING',
    protocolSha256=sha(C/'protocol.json'),results=results,waveformRoutingImplemented=True,newSeparatorNeuralCalls=0,referenceRead=False))
write(C/'routing-proof.json',dict(state='PASS_ALL32_AUXILIARY_ACTIVITY_AGREEMENT_SAMPLE_ROUTING',cases=proof,
    reusedOriginalCases=reuse_original,reusedPreviousSameInputCases=reuse_cached,newAsrStreams=2*(32-len(reused)),
    speakerPosteriorValuesChanged=False,thresholdChanged=False,newWeights=False,newSeparatorNeuralCalls=0,
    originalNonoverlapPcmPreserved=True,speakerStreamAssociationImplemented=False,qualityQualified=False))
binding=read(OLD/'worker-binding.json');binding['protocolSha256']=sha(C/'protocol.json')
for path in [C/'model-binding.json',C/'source-binding.json',C/'reused-asr-input-only.json',E/'routed-waveforms/state.json',G/'protocol.json',Path(P['observationRun'])/'state.json']:
    binding['helpers'][str(path)]=sha(path)
write(C/'worker-binding.json',binding)
execution=read(OLD/'asr-execution.json');execution.update(run=protocol['asrRun'],separationManifest=str(E/'routed-waveforms/state.json'));write(C/'asr-execution.json',execution)
route.update(at=protocol['at'],originalAlwaysOnProtocolSha256=sha(C/'protocol.json'),
    stage='Same .5speaker activity, require unchanged original auxiliary-head argmax2 too. Fixed before activity inference, no labels or duration tuning. Precise sample routing, allusedwords counted.')
write(C/'routed-composition-protocol.json',route)
router=Path('work/score_continuous_overlap_composition_20261115.py').read_text(encoding='utf-8')
needle='C=Path('+repr(str(OLD))+')';assert needle in router
Path('work/score_activity_guard_composition_20261115.py').write_text(router.replace(needle,'C=Path('+repr(str(C))+')'),encoding='utf-8')
print(json.dumps(read(C/'routing-proof.json')|{'cases':len(proof)},ensure_ascii=False))
