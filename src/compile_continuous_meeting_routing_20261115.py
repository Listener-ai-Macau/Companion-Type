"""Compile input-only full-meeting routing from existing predicted RTTM.

This produces a backend plan, not audio, words, a new model, or qualified
speaker associations. Zero/one predicted speaker preserves the original mic;
two or more requires separation followed by unresolved speaker association.
"""
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
import argparse,hashlib,json,wave
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def compile_intervals(path,frames,rate):
    events=defaultdict(Counter);events[0];events[frames]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        fields=line.split();assert fields[0]=='SPEAKER'
        start=max(0,min(frames,round(float(fields[3])*rate)))
        end=max(0,min(frames,round((float(fields[3])+float(fields[4]))*rate)))
        assert end>=start
        if end==start:continue
        events[start][fields[7]]+=1;events[end][fields[7]]-=1
    active=Counter();points=sorted(events);segments=[]
    for start,end in zip(points,points[1:]):
        active.update(events[start]);assert all(n>=0 for n in active.values())
        active=Counter({s:n for s,n in active.items() if n})
        speakers=sorted(active);branch='separate-then-associate-speakers' if len(speakers)>=2 else 'original-microphone'
        if segments and segments[-1]['predictedSpeakers']==speakers:
            segments[-1]['endFrame']=end
        else:segments.append(dict(startFrame=start,endFrame=end,predictedSpeakers=speakers,
            predictedActiveSpeakers=len(speakers),branch=branch,
            separatedStreamToSpeakerAssociationRequired=len(speakers)>=2,
            originalAudioMustRemainAvailable=True))
    active.update(events[frames]);assert all(n==0 for n in active.values())
    assert segments[0]['startFrame']==0 and segments[-1]['endFrame']==frames
    assert all(a['endFrame']==b['startFrame'] for a,b in zip(segments,segments[1:]))
    assert sum(r['endFrame']-r['startFrame'] for r in segments)==frames
    return segments

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
    assert not a.output.exists();a.output.mkdir()
    route=read(a.control/'routed-composition-protocol.json')
    sources=read(a.control.parent.parent/'public-speaker-adaptation-r1/audio-only.json')
    meetings=[];audits=[]
    for meeting,detector in sorted(route['detectors'].items()):
        source=next(r for r in sources if r['meeting']==meeting and r['role']=='validation')
        assert sha(source['audio'])==source['audioSha256']==detector['originalAudioSha256']
        assert sha(detector['predictionRttm'])==detector['predictionRttmSha256']
        assert detector['originalThreshold']==.5 and not detector['trueSpeakerCountSupplied']
        with wave.open(source['audio'],'rb') as f:
            rate=f.getframerate();frames=f.getnframes()
            assert (rate,f.getnchannels(),f.getsampwidth())==(16000,1,2)
        segments=compile_intervals(detector['predictionRttm'],frames,rate)
        overlap=sum(r['endFrame']-r['startFrame'] for r in segments if r['predictedActiveSpeakers']>=2)
        meetings.append(dict(meeting=meeting,audio=source['audio'],audioSha256=source['audioSha256'],
            originalRttmSha256=detector['predictionRttmSha256'],sampleRate=rate,frames=frames,
            seconds=frames/rate,predictedOverlapSeconds=overlap/rate,
            originalMicrophoneSeconds=(frames-overlap)/rate,segments=segments))
        for case in [r for r in route['cases'] if r['meeting']==meeting and r['useBothSeparatedStreams']]:
            low,high=case['sourceStartFrame'],case['sourceEndFrame']
            predicted=sum(max(0,min(high,r['endFrame'])-max(low,r['startFrame'])) for r in segments if r['predictedActiveSpeakers']>=2)
            audits.append(dict(id=case['id'],meeting=meeting,wholeClipRoutedSeconds=(high-low)/rate,
                actualPredictedOverlapSeconds=predicted/rate,
                originalNonoverlapSecondsAlsoSentThroughSeparation=(high-low-predicted)/rate))
    coarse=sum(r['wholeClipRoutedSeconds'] for r in audits);needed=sum(r['actualPredictedOverlapSeconds'] for r in audits)
    result=dict(state='COMPLETE_FULL_MEETING_INPUT_ONLY_CONTINUOUS_ROUTING_PLAN_ASSOCIATION_PENDING',
        at=datetime.now().astimezone().isoformat(),meetings=meetings,coarseDiagnosticAudit=audits,
        auditSummary=dict(routedClips=len(audits),wholeClipRoutedSeconds=coarse,predictedOverlapSeconds=needed,
            nonoverlapAlsoRoutedSeconds=coarse-needed,nonoverlapFractionOfRoutedAudio=(coarse-needed)/coarse),
        sourcePlan='Whole original audio, original unadapted0.5Nemo predictions only; no reference text/activity or speaker-count hint. Predicted0/1 keeps original PCM, >=2 requests separation and explicit unresolved association. No audio, tokens, or speakers silently discarded.',
        sampleCoverageVerified=True,wordsGenerated=0,newNeuralCalls=0,newWeights=0,
        finalHoldoutOpened=False,actualAudioRoutingOrAssociationImplemented=False,qualityQualified=False,
        limitations=['Predicted overlap and speaker IDs can be wrong; no new DER claim.',
            'Clip audit uses previously frozen annotation-assisted source locations; whole-meeting plan does not use them.',
            'Two anonymous separator channels cannot be assigned to predicted speaker IDs by sorting; association remains required.',
            'Subword boundary handling, original-audio preservation and real complete-meeting quality need end-to-end validation.'])
    (a.output/'routing-plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(state=result['state'],meetings=len(meetings),summary=result['auditSummary'])))

if __name__=='__main__':main()
