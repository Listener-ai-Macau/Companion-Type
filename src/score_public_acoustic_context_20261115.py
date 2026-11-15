"""Score the one frozen acoustic-only trial, never train or alter raw words."""
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
import argparse,hashlib,json,os,re,unicodedata
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from rapidfuzz.distance import Levenshtein
from diagnose_overlap_serialization_20261115 import allowed_serializations

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True);a=parser.parse_args()
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    target=a.control/'decision.json';assert not target.exists()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
    protocol=read(a.control/'protocol.json');state=read(a.run/'trial-state.json')
    assert state['state']=='COMPLETE_ONE_ADAPTER_TRIAL_INDEPENDENT_SCORING_PENDING'
    assert state['trainingSteps']==50 and state['optimizerUpdates']==25
    assert state['allFrozenParameterBytesUnchanged'] and state['exactDisabledAdapterEnglishBaselinePreserved']
    assert state['adapterSavedReloadedExactTensors']==32
    assert sha(a.run/'final-adapter/adapter_model.safetensors')==state['adapterSha256']
    assert sha(Path(protocol['baselineOriginalScore']))==protocol['baselineOriginalScoreSha256']
    baseline=read(Path(protocol['baselineOriginalScore']));context=Path(protocol['baselineOriginalScore']).parent
    truth=read(context/'scoring-only.json')
    source=Path(__file__).with_name('full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
    start=source.index('def normalize(');end=source.index('\ndef ',start+1)
    scope={'re':re,'unicodedata':unicodedata};exec(source[start:end],scope);normalize=scope['normalize']
    rows=[]
    for case in truth:
        old=next(r for r in baseline['cases'] if r['id']==case['id'])
        packet=read(a.run/'candidate-validation'/(case['id']+'.json'))
        assert packet['naturalEos'] and packet['repeatBlock'] is None
        assert packet['audioSha256']==case['wavSha256'] and not packet['referenceUsed'] and not packet['wordsPostEdited']
        ref=normalize(case['rawReferenceText']);hyp=normalize(packet['text'])
        assert ref==old['normalizedReference'] and len(ref)==old['referenceCharacters']
        ops=Levenshtein.editops(ref,hyp)
        row=dict(id=case['id'],meeting=case['meeting'],condition=case['condition'],
                 referenceCharacters=len(ref),baselineEdits=old['totalEdits'],candidateEdits=len(ops),
                 candidateEditTypes=dict(Counter(o.tag for o in ops)),rawReferenceText=case['rawReferenceText'],
                 rawBaselineText=old['rawAsrText'],rawCandidateText=packet['text'],
                 candidateSha256=sha(a.run/'candidate-validation'/(case['id']+'.json')))
        if case['condition']=='multi-turn-context':
            variants,_=allowed_serializations(case['utterances'],normalize)
            row['baselineOracleOrderEdits']=min(Levenshtein.distance(v,old['normalizedHypothesis']) for v in variants)
            row['candidateOracleOrderEdits']=min(Levenshtein.distance(v,hyp) for v in variants)
        rows.append(row)
    def aggregate(items):
        chars=sum(r['referenceCharacters'] for r in items)
        old=sum(r['baselineEdits'] for r in items);new=sum(r['candidateEdits'] for r in items)
        result=dict(cases=len(items),referenceCharacters=chars,baselineEdits=old,candidateEdits=new,
                    baselineCer=old/chars,candidateCer=new/chars)
        if all('baselineOracleOrderEdits' in r for r in items):
            result.update(baselineOracleOrderEdits=sum(r['baselineOracleOrderEdits'] for r in items),
                          candidateOracleOrderEdits=sum(r['candidateOracleOrderEdits'] for r in items))
        return result
    conditions={c:aggregate([r for r in rows if r['condition']==c]) for c in ['multi-turn-context','clean-short-response']}
    meetings={m:{c:aggregate([r for r in rows if r['meeting']==m and r['condition']==c]) for c in conditions} for m in sorted({r['meeting'] for r in rows})}
    english_id='existing-English-first30';mixed_id='existing-natural-mixed-00009'
    english=[read(a.run/(phase+'-controls')/(english_id+'.json')) for phase in ['baseline','candidate']]
    english_same=normalize(english[0]['text'])==normalize(english[1]['text'])
    mixed=[read(a.run/(phase+'-controls')/(mixed_id+'.json')) for phase in ['baseline','candidate']]
    ref=normalize(read(a.control/'mixed-control-scoring-only.json')['reference'])
    mixed_edits=[Levenshtein.distance(ref,normalize(p['text'])) for p in mixed]
    original=Path('E:/CodexData/Companion/.model-cache/ordinary-asr-adaptation-20261114/d1d2-fixed-trial-r1/baseline-controls')
    controls_original_exact=all(read(original/(name+'.json'))['generatedIds']==read(a.run/'baseline-controls'/(name+'.json'))['generatedIds'] for name in [english_id,mixed_id])
    main=conditions['multi-turn-context'];short=conditions['clean-short-response']
    checks=dict(contextTotalImproved=main['candidateEdits']<main['baselineEdits'],
                neitherContextSourceRegressed=all(v['multi-turn-context']['candidateEdits']<=v['multi-turn-context']['baselineEdits'] for v in meetings.values()),
                cleanShortTotalNotRegressed=short['candidateEdits']<=short['baselineEdits'],
                oracleOrderDiagnosticNotRegressed=main['candidateOracleOrderEdits']<=main['baselineOracleOrderEdits'],
                englishNormalizedPreserved=english_same,naturalMixedNotRegressed=mixed_edits[1]<=mixed_edits[0],
                originalCapabilityBaselinesExact=controls_original_exact)
    keep=all(checks.values())
    report=dict(state='KEEP_FIXED_ACOUSTIC_ADAPTER_FOR_ORIGINAL_FULL_MEETING_GATES_ONLY' if keep else 'REJECT_FIXED_ACOUSTIC_CONTEXT_ADAPTER',
        at=datetime.now().astimezone().isoformat(),run=str(a.run),protocolSha256=sha(a.control/'protocol.json'),
        adapterSha256=state['adapterSha256'],checks=checks,keepForFullMeetingEvaluation=keep,
        byCondition=conditions,byMeetingAndCondition=meetings,cases=rows,
        englishRawOutputs=[p['text'] for p in english],mixedReferenceCharacters=len(ref),mixedEdits=mixed_edits,
        frozenOriginalWeightsByteExact=True,adapterSavedReloadedTensors=32,newTrainingUpdates=0,newNeuralCalls=0,
        ownerParticipationRequired=False,d1Complete=True,d2Complete=False,qualityQualified=False,saleQualified=False,
        adoptedInProduct=False,parameterVariantsPlanned=False,originalAcceptanceScoresUnchanged=True,
        limitations='50natural multi-turn nonoverlap training examples,32frozen condition diagnostics and two short capability controls. No claim of independent rooms/speakers, large training, whole meetings, certified overlap handling, device or sale qualification. Oracle reference order only diagnoses a confound and never replaces original acceptance.',limits=limits.query())
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['cases','limits']},ensure_ascii=False))

if __name__=='__main__':main()
