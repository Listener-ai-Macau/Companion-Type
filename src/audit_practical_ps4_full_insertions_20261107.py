"""Trace full-reference insertion errors to every preserved source lane, no selection."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import defaultdict,Counter
import json,wave
import numpy as np
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize,group_transcripts,Levenshtein
from reference_textgrid_20261104 import read_reference_intervals
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-full-r1');B=C.parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert not (C/'insertion-cause-review.json').exists();review=read(C/'review.json');plan=read(C/'full-route-plan.json');name=plan['meeting'];duration=plan['audioSeconds']
lanes=read(C/'asr-manifest-r2.json');cases=read(C/'audio-only.json');replaced={r['rootIndex'] for r in lanes}
base=read(plan['originalAlignedDocument']);provenance=read(plan['originalAttributionReview']);display={int(k):v for k,v in provenance['nativeToConsecutiveDisplaySpeakerIds'].items()}
der=read(B/'native8-f16-full-r1/results'/name/'review.json')['perReferenceSpeakerForEvaluationOnly']
fixed={ref:str(display[int(v['matchedAnonymousGroup'].removeprefix('speaker_'))]) for ref,v in der.items()}
rows=[]
for row,token in zip(base['utterances'],provenance['tokenEstimates']):
    if int(token['sourceLeaf'].split('-')[0]) not in replaced:rows.append({**row,'sourceId':'original:'+token['sourceLeaf']})
for lane in lanes:
    case=next(c for c in cases if c['rootIndex']==lane['rootIndex'])
    for leaf in lane['acceptedLeaves']:
        if leaf['text'].strip():rows.append({'text':leaf['text'],'startMs':round((case['startSample']+leaf['startSample'])/16),'endMs':round((case['startSample']+leaf['endSample'])/16),'speaker':display[lane['predictedSpeaker']],'approximateTiming':True,'sourceId':lane['id']})
rows.sort(key=lambda r:(r['startMs'],r['endMs'],str(r['speaker'])))
candidate=read(C/'full-meeting-output/model-output.json')
assert [{k:r[k] for k in ['text','startMs','endMs','speaker','approximateTiming']} for r in rows]==candidate['utterances']
scoring=next(r for r in read(B/'practical-qwen-native17-r5/full/scoring-only.json') if r['meeting']==name)
reference=[r for r in read_reference_intervals(scoring['reference']) if normalize(r['text'])];truth=group_transcripts(reference,duration)
streams=defaultdict(str);origins=defaultdict(list)
for row in sorted(rows,key=lambda r:(r['startMs'],r['endMs'])):
    speaker=str(row['speaker']) if row['speaker'] is not None else '__unconfirmed__';text=normalize(row['text'])
    streams[speaker]+=text;origins[speaker].extend([row['sourceId']]*len(text))
stats=defaultdict(Counter);inserted_characters=Counter()
for person,text in truth.items():
    who=fixed[person];hyp=streams.get(who,'')
    for op in Levenshtein.editops(text,hyp):
        if op.tag in ['insert','replace']:
            identity=origins[who][op.dest_pos];stats[identity][op.tag]+=1
            if op.tag=='insert':inserted_characters[hyp[op.dest_pos]]+=1
assert sum(v['insert'] for v in stats.values())==sum(r['edits']['insert'] for r in review['fixedGlobalMappingAfter']['perReferenceSpeaker'])
items=[]
for lane in lanes:
    case=next(c for c in cases if c['rootIndex']==lane['rootIndex']);lo=case['startSample']/16000;hi=case['endSample']/16000
    person=next(ref for ref,slot in fixed.items() if slot==str(display[lane['predictedSpeaker']]))
    true_seconds=sum(max(0.,min(hi,r['end'])-max(lo,r['start'])) for r in reference if r['speaker']==person)
    with wave.open(lane['audio'],'rb') as stream:audio=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float64)/32768
    scores=lane['voiceIdentity']['sameMeetingCosines'];target_score=scores.get(str(lane['predictedSpeaker']),scores.get(lane['predictedSpeaker']))
    items.append({'id':lane['id'],'rootIndex':lane['rootIndex'],'predictedSpeaker':lane['predictedSpeaker'],
        'referencePersonForPosthocAuditOnly':person,'referenceTargetActivitySeconds':true_seconds,'referenceTargetAbsentInThisRoot':true_seconds==0,
        'recognizedCharacters':len(normalize(lane['text'])),'insertedCharacters':stats[lane['id']]['insert'],'replacedCharacters':stats[lane['id']]['replace'],
        'wholeLaneOwnAnchorCosine':target_score,'waveRms':float(np.sqrt(np.mean(np.square(audio)))),
        'rawAsrPreview':lane['text'][:240],'allOriginalWordsAndAudioRetained':True})
absent=[r for r in items if r['referenceTargetAbsentInThisRoot']]
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FULL_PS4_INSERTION_FAILURE_LOCALIZED_NO_NEW_MODELS',
    'allAdmittedLaneCount':len(items),'posthocTrueTargetAbsentLaneCount':len(absent),
    'insertionCharactersFromTrueTargetAbsentLanes':sum(r['insertedCharacters'] for r in absent),
    'recognizedCharactersFromTrueTargetAbsentLanes':sum(r['recognizedCharacters'] for r in absent),
    'insertionCharacterHistogramTop20':inserted_characters.most_common(20),'topInsertionLanes':sorted(items,key=lambda r:-r['insertedCharacters'])[:15],
    'allLaneDiagnostics':items,'wholeGlobalFixedMappingUsed':True,'referenceUsedOnlyForPosthocAudit':True,
    'noOracleFilteringOrTextCleanupApplied':True,'newNeuralCalls':0,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'insertion-cause-review.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ['allLaneDiagnostics','topInsertionLanes']},ensure_ascii=False))
print(json.dumps({'topInsertionLanes':result['topInsertionLanes'][:5]},ensure_ascii=False))
