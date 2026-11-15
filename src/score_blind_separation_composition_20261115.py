"""Count all two-stream words using a bounded ORC-style diagnostic only."""
from pathlib import Path
from datetime import datetime
from itertools import product
from collections import Counter
import argparse,json,os,re,unicodedata
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_community1_adapter_20261115 import sha
from rapidfuzz.distance import Levenshtein

def optimal_combination(refs,hyps):
    assert len(hyps)==2 and len(refs)<=14
    best=None
    for assignment in product(range(2),repeat=len(refs)):
        joined=[''.join(r for r,s in zip(refs,assignment) if s==i) for i in range(2)]
        ops=[Levenshtein.editops(r,h) for r,h in zip(joined,hyps)]
        cost=sum(len(o) for o in ops)
        if best is None or cost<best['edits']:
            counts=Counter(o.tag for items in ops for o in items)
            best=dict(edits=cost,counts=dict(counts),referenceAssignmentForDiagnosticOnly=list(assignment))
    assert best['edits']>=abs(sum(map(len,refs))-sum(map(len,hyps)))
    return best

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    target=a.control/'decision.json';assert not target.exists()
    protocol=read(a.control/'protocol.json');run=Path(protocol['asrRun'])
    state=read(run/'state.json');assert state['state']=='COMPLETE_FIXED_SEPARATION_ASR_COMPOSITION_SCORING_PENDING'
    assert state['all64StreamsRetained'] and state['originalNativePrefixExact']
    assert sha(protocol['scoringManifest'])==protocol['scoringManifestSha256']
    assert sha(protocol['baselineScore'])==protocol['baselineScoreSha256']
    baseline=read(protocol['baselineScore']);cases=read(protocol['scoringManifest'])
    source=Path(__file__).with_name('full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
    start=source.index('def normalize(');end=source.index('\ndef ',start+1)
    scope={'re':re,'unicodedata':unicodedata};exec(source[start:end],scope);normalize=scope['normalize']
    assert optimal_combination(['甲','乙'],['甲','乙'])['edits']==0
    assert optimal_combination(['甲'],['甲','甲'])['edits']==1
    assert optimal_combination(['甲','乙'],['乙','甲'])['edits']==0
    assert optimal_combination([],['甲','乙'])['edits']==2
    rows=[]
    for case in cases:
        original=next(r for r in baseline['cases'] if r['id']==case['id'])
        truth=[normalize(r['text']) for r in case['utterances']]
        assert ''.join(truth)==original['normalizedReference']
        packets=[]
        for channel in range(2):
            item=next(r for r in state['results'] if r['id']==case['id'] and r['stream']==channel)
            assert sha(item['file'])==item['sha256']
            packet=read(item['file']);assert not packet['wordsPostEdited'] and not packet['referenceUsed'] and not packet['outputStreamDropped']
            packets.append(packet)
        old=optimal_combination(truth,[original['normalizedHypothesis'],''])
        new=optimal_combination(truth,[normalize(p['text']) for p in packets])
        rows.append(dict(id=case['id'],meeting=case['meeting'],condition=case['condition'],
                         referenceCharacters=sum(map(len,truth)),baseline=old,candidate=new,
                         originalChronologicalEdits=original['totalEdits'],rawReference=case['rawReferenceText'],
                         rawBaseline=original['rawAsrText'],rawCandidateStreams=[p['text'] for p in packets],
                         candidateReviewRequired=any(p['reviewRequired'] for p in packets)))
    assert len(rows)==32
    def aggregate(items):
        n=sum(r['referenceCharacters'] for r in items);old=sum(r['baseline']['edits'] for r in items);new=sum(r['candidate']['edits'] for r in items)
        return dict(cases=len(items),referenceCharacters=n,baselineDiagnosticEdits=old,candidateDiagnosticEdits=new,
                    baselineDiagnosticCer=old/n,candidateDiagnosticCer=new/n,
                    reviewRequiredCases=sum(r['candidateReviewRequired'] for r in items),
                    baselineCounts=dict(sum((Counter(r['baseline']['counts']) for r in items),Counter())),
                    candidateCounts=dict(sum((Counter(r['candidate']['counts']) for r in items),Counter())))
    conditions={c:aggregate([r for r in rows if r['condition']==c]) for c in ['multi-turn-context','clean-short-response']}
    meetings={m:{c:aggregate([r for r in rows if r['meeting']==m and r['condition']==c]) for c in conditions} for m in sorted({r['meeting'] for r in rows})}
    overlap=conditions['multi-turn-context'];solo=conditions['clean-short-response']
    checks=dict(naturalContextTotalImproved=overlap['candidateDiagnosticEdits']<overlap['baselineDiagnosticEdits'],
                neitherContextSourceRegressed=all(v['multi-turn-context']['candidateDiagnosticEdits']<=v['multi-turn-context']['baselineDiagnosticEdits'] for v in meetings.values()),
                soloTotalNotRegressed=solo['candidateDiagnosticEdits']<=solo['baselineDiagnosticEdits'],
                neitherSoloSourceRegressed=all(v['clean-short-response']['candidateDiagnosticEdits']<=v['clean-short-response']['baselineDiagnosticEdits'] for v in meetings.values()),
                allOutputsConfirmed=not any(r['candidateReviewRequired'] for r in rows))
    keep=all(checks.values())
    result=dict(state='KEEP_FIXED_BLIND_SEPARATION_COMPOSITION_FOR_ORIGINAL_WHOLE_MEETING_TESTING_ONLY' if keep else 'REJECT_FIXED_ALWAYS_ON_BLIND_SEPARATION_COMPOSITION',
                at=datetime.now().astimezone().isoformat(),checks=checks,keepForOriginalWholeMeetingTesting=keep,
                byCondition=conditions,byMeetingAndCondition=meetings,cases=rows,
                originalAcceptanceScoresUnchanged=True,allWordsFromBothOutputsCounted=True,
                noReferenceUsedDuringInference=True,newTrainingUpdates=0,newNeuralCalls=0,
                ownerParticipationRequired=False,qualityQualified=False,d2Complete=False,saleQualified=False,
                productDefaultChanged=False,finalHoldoutOpened=False,limits=limits.query(),
                scope='Reference-assisted32diagnostic cuts,2anonymous CSS streams and optimal utterance allocation for diagnostic evaluation only. No speaker identity qualification or full-meeting gate replacement. Single-speaker leakage/duplicate/empty-target words remain insertion penalties.')
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','limits']},ensure_ascii=False))

if __name__=='__main__':main()
