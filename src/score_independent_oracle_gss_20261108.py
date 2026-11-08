"""All people, all frozen windows, both arms; no favourable transcript selection."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize,Levenshtein
from reference_textgrid_20261104 import read_reference_intervals
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-dual-mic-independent-meetings/oracle-activity-control'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2);assert not (C/'review.json').exists()
run=read(C/'run-r2.json');assert run['state']=='COMPLETE_DUAL_MIC_SPATIAL_CODEC_SCREEN_REVIEW_REQUIRED'
P=read(C/'protocol-r2.json');outputs=read(C/'asr-manifest-r2.json');assert len(outputs)==P['expectedOutputRows']
assert read(C/'asr-state-r2.json')['state']=='COMPLETE_DUAL_MIC_FIXED_ASR_NOT_PRODUCT'
byid={r['id']:r for r in outputs};assert len(byid)==len(outputs)
binding={'protocolSha256':sha(C/'protocol-r2.json'),'audioOnlySha256':P['audioOnlySha256'],'workerSourceSha256':P['asrWorkerSourceSha256']}
for output in outputs:
    assert output['binding']==binding and sha(output['audio'])==output['audioSha256']
    assert output['text']=='\n'.join(r['text'] for r in output['acceptedLeaves'])
    source=byid[output['sameAudioReuseSource']] if output.get('sameAudioReuseSource') else output
    assert source['audioSha256']==output['audioSha256'] and source['acceptedLeaves']==output['acceptedLeaves']
    nodes=[]
    for file in (C/'asr-outputs-r2'/source['id']).glob('*.json'):
        if file.name=='completed.json':continue
        packet=read(file);assert packet['binding']==binding and packet['audioSha256']==source['audioSha256']
        assert packet['rawSha256']==hashlib.sha256(json.dumps(packet['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();nodes.append(packet['raw'])
    assert nodes and all(any(leaf==node for node in nodes) for leaf in output['acceptedLeaves'])
def edits(ref,hyp):
    ref,hyp=normalize(ref),normalize(hyp);v=Counter(x.tag for x in Levenshtein.editops(ref,hyp))
    return dict(referenceCharacters=len(ref),hypothesisCharacters=len(hyp),substitute=v['replace'],delete=v['delete'],insert=v['insert'],total=sum(v.values()))
def total(rows):return {k:sum(r[k] for r in rows) for k in ['referenceCharacters','hypothesisCharacters','substitute','delete','insert','total']}
rows=[];roots=[];arms=['mono_activity','dual_pcm'];scoring=read(C/'scoring-only.json')
for case in read(C/'spatial-audio-only.json'):
    refcase=next(r for r in scoring if r['originalMeeting']==case['meeting'] and r['sourceChannel']==0)
    assert sha(refcase['reference'])==refcase['referenceSha256'];review=read(refcase['fixedMappingReview'])
    mapping={int(v['matchedAnonymousGroup'].removeprefix('speaker_')):person for person,v in review['perReferenceSpeakerForEvaluationOnly'].items() if v['matchedAnonymousGroup'] is not None}
    # Surplus predicted IDs remain distinct and all their insertions count.
    for p in case['predictedRootPeople']:mapping.setdefault(p,'UNMATCHED_PREDICTED_SLOT_'+str(p))
    lo,hi=case['rootStartSample']/16000,case['rootEndSample']/16000
    truth=[r for r in read_reference_intervals(refcase['reference']) if normalize(r['text']) and lo<=(r['start']+r['end'])/2<hi]
    people=sorted({r['speaker'] for r in truth}|{mapping[p] for p in case['predictedRootPeople']});current=[]
    for person in people:
        true_rows=sorted([r for r in truth if r['speaker']==person],key=lambda r:(r['start'],r['end']));reference=''.join(r['text'] for r in true_rows)
        personrow={'case':case['id'],'meeting':case['meeting'],'rootIndex':case['rootIndex'],'kind':case['kind'],'referencePersonForScoringOnly':person,'referenceText':reference,'boundaryStraddlingReferenceRows':[{k:r[k] for k in ['start','end','text']} for r in true_rows if r['start']<lo or r['end']>hi],'predictedSlot':next((p for p in case['predictedRootPeople'] if mapping[p]==person),None),'conditions':{}}
        for arm in arms:
            lane=next((r for r in outputs if r['meeting']==case['meeting'] and r['rootIndex']==case['rootIndex'] and r['arm']==arm and mapping[r['predictedSpeaker']]==person),None)
            personrow['conditions'][arm]={'text':lane['text'] if lane else '', 'predictedPersonAvailable':lane is not None,'edits':edits(reference,lane['text'] if lane else '')}
        current.append(personrow);rows.append(personrow)
    roots.append({'case':case['id'],'kind':case['kind'],'meeting':case['meeting'],'totals':{arm:total([r['conditions'][arm]['edits'] for r in current]) for arm in arms},'missingPredictedReferencePeople':[r['referencePersonForScoringOnly'] for r in current if r['predictedSlot'] is None]})
overlap=[r for r in rows if r['kind']!='ordinary-regression'];ordinary=[r for r in rows if r['kind']=='ordinary-regression'];totals={arm:total([r['conditions'][arm]['edits'] for r in overlap]) for arm in arms}
root_regress=[r['case'] for r in roots if r['kind']!='ordinary-regression' and r['totals']['dual_pcm']['total']>r['totals']['mono_activity']['total']]
person_regress=[{'case':r['case'],'person':r['referencePersonForScoringOnly'],'monoDeletions':r['conditions']['mono_activity']['edits']['delete'],'dualDeletions':r['conditions']['dual_pcm']['edits']['delete']} for r in overlap if r['conditions']['dual_pcm']['edits']['delete']>r['conditions']['mono_activity']['edits']['delete']]
gain=totals['dual_pcm']['total']<totals['mono_activity']['total'];no_ordinary_regression=all(r['conditions']['dual_pcm']['text']==r['conditions']['mono_activity']['text'] for r in ordinary)
result={'at':datetime.now().astimezone().isoformat(),'state':'INDEPENDENT_RAW_DUAL_LOCAL_GAIN_WITH_PARTICIPANT_FAILURES' if gain and (root_regress or person_regress) else 'INDEPENDENT_RAW_DUAL_LOCAL_GAIN_NOT_PRODUCT_QUALIFIED' if gain else 'INDEPENDENT_RAW_DUAL_REJECTED_NO_AGGREGATE_GAIN','allOutputRowsVerified':len(outputs),'allRawGenerationHashesAndBindingsVerified':True,'allFrozenCasesAndPeopleScored':True,'oracleReferenceActivityUsed':True,'productScore':False,'metric':'Fixed full-meeting-identity-mapped character edit counts on prediction-selected30s windows; whole midpoint-selected reference utterances, straddling boundaries disclosed. Not strict full-meetingCER or pure-overlapCER.','overlapTotals':totals,'ordinaryTotals':{arm:total([r['conditions'][arm]['edits'] for r in ordinary]) for arm in arms},'perMeetingOverlapTotals':{m:{arm:total([r['conditions'][arm]['edits'] for r in overlap if r['meeting']==m]) for arm in arms} for m in sorted({r['meeting'] for r in overlap})},'perRoot':roots,'perPerson':rows,'overlapRootRegressions':root_regress,'participantDeletionRegressions':person_regress,'ordinaryRawTextSameAcrossArms':no_ordinary_regression,'standardFullJournalReview':str(C/'journal-review.json'),'actualReferenceClipCoverage':read(C/'journal-review.json')['selectedClipActualReferenceCoverage'],'sameRecognizerInferenceAst':P['asrInferenceAstMatchesOriginal'],'newSpatialAlgorithmCalls':read(C/'separation-state-r2.json')['newAlgorithmCalls'],'newAsrCalls':read(C/'asr-state-r2.json')['newNeuralCalls'],'sameAudioReuses':read(C/'asr-state-r2.json')['reusedOutputs'],'timings':{s:sum(r['wholeProcessFamilySeconds'] for receipt in [run]+[read(p) for p in run['priorAttemptReceipts']] for r in receipt['results'] if r['stage']==s) for s in ['separation','inventory','asr']},'maximumRecordedJobPrivateBytes':max(read(C/name)['limits']['jobPeakPrivateCommitBytes'] for name in ['separation-state-r2.json','asr-state-r2.json']),'cpuLimitPercent':10,'privateLimitBytes':2*1024**3,'twoWayLabelFusionPerformed':False,'finalHoldoutOpened':False,'productDefaultChanged':False,'newTrainingRuns':0,'newHardwareAccess':False,'qualityQualified':False,'broadPromotionAllowed':False}
attempt_states=[read(p) for p in C.glob('prior-asr-*.json')]+[read(C/'asr-state-r2.json')]
assert all(s['binding']==binding for s in attempt_states)
result['asrCallsByRetainedAttempt']=[{'startedAt':s['startedAt'],'newNeuralCalls':s['newNeuralCalls'],'cachedOutputOrRawNodeReuses':s['reusedOutputs']} for s in attempt_states]
result['newAsrCalls']=sum(s['newNeuralCalls'] for s in attempt_states)
result['sameAudioReuses']=sum(bool(r.get('sameAudioReuseSource')) for r in outputs)
result['cachedOutputOrRawNodeReusesAcrossAttempts']=sum(s['reusedOutputs'] for s in attempt_states)
atomic_json(C/'review.json',result)
print(json.dumps({k:result[k] for k in ['state','overlapTotals','ordinaryTotals','perMeetingOverlapTotals','overlapRootRegressions','participantDeletionRegressions','newAsrCalls','timings']},ensure_ascii=False),flush=True)
