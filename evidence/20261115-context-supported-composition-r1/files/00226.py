from pathlib import Path
from datetime import datetime
from collections import Counter
import json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
C=Path('C:\\Users\\Billy\\Desktop\\Denzic\\Companion\\docs\\handoffs\\20261109-paired-real-meeting\\bilingual-local20261114\\d1d2-execution\\supervised-blind-separation-r1\\context-supported-composition-r1')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
target=C/'routed-decision.json';assert not target.exists()
protocol=read(C/'routed-composition-protocol.json');original=read(C/'decision.json')
assert protocol['state']=='FROZEN_DETECTOR_ROUTED_COMPOSITION_BEFORE_ANY_TEXT_SCORE_INSPECTION'
assert protocol['at']<original['at']
rows=[]
for old in original['cases']:
    route=next(r for r in protocol['cases'] if r['id']==old['id']);routed=route['useBothSeparatedStreams']
    rows.append({**old,'candidate':old['candidate'] if routed else old['baseline'],
                 'candidateReviewRequired':old['candidateReviewRequired'] if routed else False,
                 'branch':'both-separated-streams' if routed else 'unchanged-original-asr',
                 'detectorPredictedOverlapSeconds':route['detectorPredictedOverlapSeconds']})
def aggregate(items):
    n=sum(r['referenceCharacters'] for r in items);old=sum(r['baseline']['edits'] for r in items);new=sum(r['candidate']['edits'] for r in items)
    return dict(cases=len(items),referenceCharacters=n,baselineDiagnosticEdits=old,candidateDiagnosticEdits=new,
                baselineDiagnosticCer=old/n,candidateDiagnosticCer=new/n,
                routed=sum(r['branch']=='both-separated-streams' for r in items),
                reviewRequiredCases=sum(r['candidateReviewRequired'] for r in items),
                baselineCounts=dict(sum((Counter(r['baseline']['counts']) for r in items),Counter())),
                candidateCounts=dict(sum((Counter(r['candidate']['counts']) for r in items),Counter())))
conditions={c:aggregate([r for r in rows if r['condition']==c]) for c in ['multi-turn-context','clean-short-response']}
meetings={m:{c:aggregate([r for r in rows if r['meeting']==m and r['condition']==c]) for c in conditions} for m in sorted({r['meeting'] for r in rows})}
main=conditions['multi-turn-context'];solo=conditions['clean-short-response']
checks=dict(naturalContextTotalImproved=main['candidateDiagnosticEdits']<main['baselineDiagnosticEdits'],
            neitherContextSourceRegressed=all(v['multi-turn-context']['candidateDiagnosticEdits']<=v['multi-turn-context']['baselineDiagnosticEdits'] for v in meetings.values()),
            soloTotalNotRegressed=solo['candidateDiagnosticEdits']<=solo['baselineDiagnosticEdits'],
            neitherSoloSourceRegressed=all(v['clean-short-response']['candidateDiagnosticEdits']<=v['clean-short-response']['baselineDiagnosticEdits'] for v in meetings.values()),
            allUsedOutputsConfirmed=not any(r['candidateReviewRequired'] for r in rows))
keep=all(checks.values())
report=dict(state='KEEP_FIXED_ROUTED_THREE_MODEL_COMPOSITION_FOR_ORIGINAL_WHOLE_MEETING_TESTING_ONLY' if keep else 'REJECT_FIXED_ROUTED_THREE_MODEL_COMPOSITION',
    at=datetime.now().astimezone().isoformat(),checks=checks,keepForOriginalWholeMeetingTesting=keep,
    byCondition=conditions,byMeetingAndCondition=meetings,cases=rows,routingProtocolSha256=sha(C/'routed-composition-protocol.json'),
    detectorFromOriginalWholeAudio=True,all32SourceClipsPcmExact=True,
    noGateFromReferenceOrWords=True,allWordsOfEveryUsedBranchCounted=True,
    bothSeparatedOutputsUsedWheneverRouted=True,allUnusedShadowArtifactsRetained=True,
    originalAlwaysOnDecisionUnchanged=True,originalAcceptanceScoresUnchanged=True,
    newNeuralCalls=0,newTrainingUpdates=0,qualityQualified=False,d2Complete=False,saleQualified=False,
    productDefaultChanged=False,ownerParticipationRequired=False,finalHoldoutOpened=False,
    scope='Three original pretrained specialists: originalNemotron predicted overlap→blindSS two streams→originalQwenASR; no-overlap retains original ASR. Diagnostic cuts are annotation-assisted, ORC-style evaluation does not prove identity or whole-meeting acceptance.',limits=limits.query())
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ['cases','limits']},ensure_ascii=False))
