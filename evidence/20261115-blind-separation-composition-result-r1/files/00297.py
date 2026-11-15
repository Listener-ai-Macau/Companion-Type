"""Freeze an existing detector's gate before inspecting composition scores."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import json,sys,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'blind-separation-composition-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
target=C/'routed-composition-protocol.json';assert not target.exists() and not (C/'decision.json').exists() and not (C/'routed-decision.json').exists()
locations=read(D/'context-matched-baseline-r3/scoring-only.json')
sources=read(D/'public-speaker-adaptation-r1/audio-only.json')
baseline=Path('E:/CodexData/Companion/product-d1d2-20261114/public-speaker-adaptation-r1/baseline-r1/results')
cases=read(C/'audio-only.json');detectors={};rows=[]
for source in [r for r in sources if r['role']=='validation']:
    meeting=source['meeting'];folder=baseline/meeting;meta=read(folder/'result.json');predicted=folder/'predicted.rttm'
    assert source['audioSha256']==meta['audioSha256']==sha(source['audio'])
    assert sha(predicted)==meta['rttmSha256'] and meta['originalThreshold']==.5 and meta['noSpeakerCountHint']
    events={}
    for line in predicted.read_text().splitlines():
        fields=line.split();start=float(fields[3]);end=start+float(fields[4]);speaker=fields[7]
        events.setdefault(start,[]).append((speaker,1));events.setdefault(end,[]).append((speaker,-1))
    active=Counter();points=sorted(events);overlaps=[]
    for i,start in enumerate(points[:-1]):
        for speaker,change in events[start]:
            active[speaker]+=change
            if active[speaker]==0:del active[speaker]
        if len(active)>=2:overlaps.append((start,points[i+1]))
    detectors[meeting]=dict(predictionRttm=str(predicted),predictionRttmSha256=sha(predicted),
                           originalAudioSha256=source['audioSha256'],trueSpeakerCountSupplied=False,
                           originalThreshold=.5)
    with wave.open(source['audio'],'rb') as original:
        for case in [r for r in cases if r['meeting']==meeting]:
            location=next(r for r in locations if r['id']==case['id'])
            low,high=location['sourceStartFrame'],location['sourceEndFrame']
            with wave.open(case['wav'],'rb') as clip:pcm=clip.readframes(clip.getnframes())
            original.setpos(low);assert original.readframes(high-low)==pcm
            lo,hi=low/16000,high/16000
            seconds=sum(max(0,min(hi,b)-max(lo,a)) for a,b in overlaps)
            rows.append(dict(id=case['id'],meeting=meeting,condition=case['condition'],
                             sourceStartFrame=low,sourceEndFrame=high,sourceClipPcmExact=True,
                             detectorPredictedOverlapSeconds=seconds,useBothSeparatedStreams=seconds>0))
assert len(rows)==32
result=dict(state='FROZEN_DETECTOR_ROUTED_COMPOSITION_BEFORE_ANY_TEXT_SCORE_INSPECTION',
    at=datetime.now().astimezone().isoformat(),cases=rows,detectors=detectors,
    rule='Existing original unadapted Nemotron output, unchanged0.5activity threshold. If any interval in the same PCM clip has>=2predicted active anonymous speakers, use both separated ASR streams. Otherwise retain original raw-input ASR exactly. No gate from reference speaker count/activity, reference words, ASR text/confidence/error or source loudness.',
    stage='Architecture composition added after64ASR streams generated but before any composition score or output-word inspection. The earlier always-on component remains separately evaluated under its own frozen protocol; no failed result is rewritten.',
    annotationAssistedDiagnosticCuts=True,sourceLocationsFromOriginalFrozenCohortOnly=True,
    anySourceClipsSelectedOrRemoved=False,all32InputsScored=True,thresholdVariants=0,
    keepRule='Same fixed diagnostic criteria: natural-context total improve, neither context source regress, solo total and either solo source not regress, all used intervals confirmed. Passing only permits original complete meeting/identity/bilingual gates, no default adoption.',
    originalAlwaysOnProtocolSha256=sha(C/'protocol.json'),ownerParticipationRequired=False,
    newDetectorNeuralCalls=0,newTrainingUpdates=0,qualityQualified=False,d2Complete=False,
    fullMeetingOrIdentityAcceptanceClaim=False,finalHoldoutOpened=False,limits=limits.query())
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cases':32,'routed':sum(r['useBothSeparatedStreams'] for r in rows),
                  'byCondition':{c:dict(total=sum(r['condition']==c for r in rows),routed=sum(r['condition']==c and r['useBothSeparatedStreams'] for r in rows)) for c in sorted({r['condition'] for r in rows})},'newNeuralCalls':0}))
