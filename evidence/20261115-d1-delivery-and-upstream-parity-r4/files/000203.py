"""Trace duplication before/after merge using immutable outputs; no text removal."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
from difflib import SequenceMatcher
import json,hashlib
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';P=B/'practical-conditioned-ps4-full-r1';C=B/'practical-target-activity-r1';C.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'merge-and-lane-cause-review.json').exists();limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
plan=read(P/'full-route-plan.json');lanes=read(P/'asr-manifest-r2.json');cases=read(P/'audio-only.json');base=read(plan['originalAlignedDocument']);provenance=read(plan['originalAttributionReview'])
assert len({r['id'] for r in lanes})==len(lanes)==159
display={int(k):v for k,v in provenance['nativeToConsecutiveDisplaySpeakerIds'].items()};replaced={r['rootIndex'] for r in lanes};rows=[];lineage=[]
for source_index,(row,token) in enumerate(zip(base['utterances'],provenance['tokenEstimates'])):
    assert row['text']==token['text']
    if int(token['sourceLeaf'].split('-')[0]) not in replaced:rows.append(row);lineage.append(('original',source_index,token['sourceLeaf'],row['startMs'],row['endMs'],token['text']))
leaf_checks=[]
for lane in lanes:
    case=next(c for c in cases if c['rootIndex']==lane['rootIndex']);leaves=lane['acceptedLeaves'];keys=[(a['startSample'],a['endSample']) for a in leaves]
    assert len(set(keys))==len(keys)
    spans=sorted(keys);assert spans[0][0]==0 and spans[-1][1]==case['endSample']-case['startSample']
    assert all(a[1]==b[0] for a,b in zip(spans,spans[1:])), 'Repeated or missing accepted audio span'
    for leaf in leaves:
        if not leaf['text'].strip():continue
        rows.append({'text':leaf['text'],'startMs':round((case['startSample']+leaf['startSample'])/16),'endMs':round((case['startSample']+leaf['endSample'])/16),'speaker':display[lane['predictedSpeaker']],'approximateTiming':True})
        lineage.append((lane['id'],leaf['startSample'],leaf['endSample'],leaf['text']))
    leaf_checks.append({'id':lane['id'],'acceptedLeaves':len(leaves),'continuousNonoverlappingAudioCoverage':True})
assert len(set(lineage))==len(lineage)
rows.sort(key=lambda r:(r['startMs'],r['endMs'],str(r['speaker'])))
assert rows==read(P/'full-meeting-output/model-output.json')['utterances']
pairs=[];byroot=defaultdict(list)
for lane in lanes:byroot[lane['rootIndex']].append(lane)
for root,items in byroot.items():
    for i,left in enumerate(items):
        for right in items[i+1:]:
            a,b=normalize(left['text']),normalize(right['text'])
            longest=SequenceMatcher(None,a,b,autojunk=False).find_longest_match()
            if longest.size>=8:
                pairs.append({'rootIndex':root,'left':left['id'],'right':right['id'],'longestSharedNormalizedCharacters':longest.size,'sharedRawAsrText':a[longest.a:longest.a+longest.size],
                    'emittedByDifferentAsrLanesBeforeMerge':True,'notProofOfAcousticLeakageOrLegitimateRepetitionByItself':True})
cause=read(P/'insertion-cause-review.json');absent=[r for r in cause['allLaneDiagnostics'] if r['referenceTargetAbsentInThisRoot']]
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'MERGE_LINEAGE_MATCHES_ONCE_PREMERGE_DUPLICATION_CANDIDATES_LOCALIZED',
    'fullCandidateReviewSha256':sha(P/'review.json'),'inputLaneCount':len(lanes),'reconstructedOutputRows':len(rows),'all159LanesHaveUniqueContiguousAcceptedSourceCoverage':True,'allRowsEqualPersistedFullCandidate':True,'noRepeatedInputIdentityInsertedByMerge':True,
    'differentAsrLanePairsSharingAtLeast8NormalizedCharacters':len(pairs),'rootsWithSuchPairs':len({p['rootIndex'] for p in pairs}),'sharedTextPairs':sorted(pairs,key=lambda p:-p['longestSharedNormalizedCharacters']),
    'wholeRootTargetAbsentExamples':absent,'allLaneSourceCoverage':leaf_checks,
    'conclusions':['The observed assembly reconstructs exactly from unique input leaves; it does not insert an accepted source leaf twice. This narrows the inspected merge-duplication hypothesis only.','Long shared sequences already exist in different raw per-person ASR outputs before final assembly. This supports investigating separation/target-presence/ASR residual behavior. It does not license transcript deduplication.','Nonzero separated audio and nonempty ASR when a mapped target is absent do not alone distinguish acoustic cross-talk from ASR hallucination. No listening/clean-source proof is claimed.','Independent target activity is the next separable hypothesis. Ordinary ASR and all prior failed outputs remain unchanged.'],
    'newNeuralCalls':0,'referenceUsedForPosthocDiagnosisOnly':True,'wordsRemovedOrOutputsChanged':False,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'merge-and-lane-cause-review.json',result)
print(json.dumps({k:result[k] for k in ['state','inputLaneCount','reconstructedOutputRows','differentAsrLanePairsSharingAtLeast8NormalizedCharacters','rootsWithSuchPairs','conclusions']},ensure_ascii=False))
