"""Score every fixed condition after inference, preserving people and all words."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,psutil,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize,Levenshtein
from reference_textgrid_20261104 import read_reference_intervals
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
B=R/'docs/handoffs/20261107-model-generation-recovery';C=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);assert not (C/'review.json').exists()
for p in psutil.process_iter(['cmdline']):
    for a in p.info['cmdline'] or []:
        assert not (str(a).replace('\\','/').lower().startswith(str(M/'src').replace('\\','/').lower()+'/') and Path(str(a)).name in ['dual_mic_gss_worker_20261108.py','dual_mic_gss_asr_worker_20261108.py','run_dual_mic_gss_validation_20261108.py'])
run=read(C/'run-r2.json');assert run['state']=='COMPLETE_DUAL_MIC_SPATIAL_CODEC_SCREEN_REVIEW_REQUIRED'
P=read(C/'protocol-r2.json');outputs=read(C/'asr-manifest-r2.json');assert len(outputs)==21
assert read(C/'asr-state-r2.json')['state']=='COMPLETE_DUAL_MIC_FIXED_ASR_NOT_PRODUCT'
byid={r['id']:r for r in outputs};assert len(byid)==21
expected={'protocolSha256':sha(C/'protocol-r2.json'),'audioOnlySha256':P['audioOnlySha256'],'workerSourceSha256':P['asrWorkerSourceSha256']}
for output in outputs:
    assert output['binding']==expected and sha(output['audio'])==output['audioSha256']
    assert output['text']=='\n'.join(r['text'] for r in output['acceptedLeaves'])
    source=byid[output['sameAudioReuseSource']] if output.get('sameAudioReuseSource') else output
    assert source['audioSha256']==output['audioSha256'] and source['acceptedLeaves']==output['acceptedLeaves']
    nodes=[]
    for file in (C/'asr-outputs-r2'/source['id']).glob('*.json'):
        if file.name=='completed.json':continue
        node=read(file);assert node['binding']==expected and node['audioSha256']==source['audioSha256']
        assert node['rawSha256']==hashlib.sha256(json.dumps(node['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();nodes.append(node['raw'])
    assert nodes and all(any(leaf==node for node in nodes) for leaf in output['acceptedLeaves'])

def edits(truth,hyp):
    truth=normalize(truth);hyp=normalize(hyp);c=Counter(o.tag for o in Levenshtein.editops(truth,hyp))
    return {'referenceCharacters':len(truth),'hypothesisCharacters':len(hyp),'substitute':c['replace'],'delete':c['delete'],'insert':c['insert'],'total':sum(c.values())}
def total(items):return {k:sum(r[k] for r in items) for k in ['referenceCharacters','hypothesisCharacters','substitute','delete','insert','total']}

rows=[];roots=[];arms=['mono_activity','dual_pcm','dual_opus']
for case in read(C/'audio-only.json'):
    meeting=case['meeting'];lo=case['rootStartSample']/16000;hi=case['rootEndSample']/16000
    scoring=next(r for r in read(B/'practical-target-activity-r1/scoring-only.json') if r['meeting']==meeting)
    assert sha(scoring['reference'])==scoring['referenceSha256']
    truth=[r for r in read_reference_intervals(scoring['reference']) if normalize(r['text'])]
    mapping={int(v['matchedAnonymousGroup'].removeprefix('speaker_')):person for person,v in read(scoring['fixedMappingReview'])['perReferenceSpeakerForEvaluationOnly'].items()}
    selected=[r for r in truth if lo<=(r['start']+r['end'])/2<hi]
    people=sorted({r['speaker'] for r in selected}|{mapping[p] for p in case['predictedRootPeople']})
    current=[]
    for person in people:
        true_rows=sorted([r for r in selected if r['speaker']==person],key=lambda r:(r['start'],r['end']))
        ref=''.join(r['text'] for r in true_rows)
        row={'case':case['id'],'meeting':meeting,'rootIndex':case['rootIndex'],'referencePersonForScoringOnly':person,
            'referenceText':ref,'boundaryStraddlingReferenceRows':[{k:r[k] for k in ['start','end','text']} for r in true_rows if r['start']<lo or r['end']>hi],
            'predictedSlot':next((p for p in case['predictedRootPeople'] if mapping[p]==person),None),'conditions':{}}
        for arm in arms:
            out=next((r for r in outputs if r['meeting']==meeting and r['rootIndex']==case['rootIndex'] and r['arm']==arm and mapping[r['predictedSpeaker']]==person),None)
            row['conditions'][arm]={'text':out['text'] if out else '', 'predictedPersonAvailable':out is not None,
                'edits':edits(ref,out['text'] if out else '')}
        if meeting=='L_R003S01C02':
            old=[r for r in read(B/'practical-conditioned-ps4-full-r1/asr-manifest-r2.json') if r['rootIndex']==case['rootIndex'] and mapping[r['predictedSpeaker']]==person]
            cached='\n'.join(r['text'] for r in old);row['conditions']['previous_single_mic_ps4']={'text':cached,'edits':edits(ref,cached),'newAsrCalls':0,'notSameSegmentationAsNewArms':True}
        current.append(row);rows.append(row)
    root={'case':case['id'],'kind':case['kind'],'totals':{arm:total([r['conditions'][arm]['edits'] for r in current]) for arm in arms},
        'missingPredictedReferencePeople':[r['referencePersonForScoringOnly'] for r in current if r['predictedSlot'] is None]}
    if meeting=='L_R003S01C02':root['previous_single_mic_ps4']=total([r['conditions']['previous_single_mic_ps4']['edits'] for r in current])
    roots.append(root)
overlap=[r for r in rows if r['meeting']=='L_R003S01C02'];ordinary=[r for r in rows if r['meeting']=='S_R004S03C01']
aggregate={arm:total([r['conditions'][arm]['edits'] for r in overlap]) for arm in arms}
old=total([r['conditions']['previous_single_mic_ps4']['edits'] for r in overlap])
raw=aggregate['dual_pcm'];mono=aggregate['mono_activity'];coded=aggregate['dual_opus']
state='LOCAL_DUAL_GUIDED_PIPELINE_SHOWS_GAIN_REQUIRES_INDEPENDENT_MEETINGS' if raw['total']<mono['total'] and raw['total']<old['total'] else 'DUAL_GUIDED_SCREEN_REJECTED_NO_RAW_SPATIAL_GAIN'
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':state,
    'protocolSha256':sha(C/'protocol-r2.json'),'allOutputRowsVerified':21,'allRawGenerationHashesAndBindingsVerified':True,
    'allConditionsAndPeopleScored':True,'referenceUsedOnlyAfterProcessingForScoring':True,
    'rootCoverage':'Lroot12known two-speaker and disclosed Lroot27true-triple supplement;Sroot1ordinary.2 exposed Mandarin meetings, not independent generalization or final holdout.',
    'metric':'Sum of fixed whole-meeting-identity-mapped character edit counts against midpoint-selected whole utterances. Clip-edge-straddling references retained/reported. Not strict full-recordingCER, standardDER or pure-overlapCER.',
    'overlapTotals':aggregate,'cachedPreviousSingleMicPs4':old,
    'ordinaryTotals':{arm:total([r['conditions'][arm]['edits'] for r in ordinary]) for arm in arms},
    'perRoot':roots,'perPerson':rows,
    'comparisons':{'rawDualMinusMatchedMonoEdits':raw['total']-mono['total'],'rawDualMinusCachedPs4Edits':raw['total']-old['total'],
        'compressedDualMinusRawDualEdits':coded['total']-raw['total'],
        'rawDualMinusMatchedMonoDeletions':raw['delete']-mono['delete'],
        'compressedDualMinusRawDualDeletions':coded['delete']-raw['delete']},
    'ordinaryRawBypass':read(C/'ordinary-bypass.json'),
    'ordinaryRawTextSameAcrossArms':all(r['conditions']['mono_activity']['text']==r['conditions']['dual_pcm']['text'] for r in ordinary),
    'sameRecognizerInferenceAst':P['asrInferenceAstMatchesOriginal'],
    'newSpatialAlgorithmCalls':read(C/'separation-state-r2.json')['newAlgorithmCalls'],
    'newAsrCalls':read(C/'asr-state-r2.json')['newNeuralCalls'],'sameAudioReuses':read(C/'asr-state-r2.json')['reusedOutputs'],
    'timings':{stage:sum(r['wholeProcessFamilySeconds'] for receipt in [run]+[read(p) for p in run['priorAttemptReceipts']] for r in receipt['results'] if r['stage']==stage) for stage in ['separation','inventory','asr']},
    'neuralAndSpatialPrivateLimitBytes':2*1024**3,
    'maximumRecordedJobPrivateBytes':max(read(C/name)['limits']['jobPeakPrivateCommitBytes'] for name in ['separation-state-r2.json','asr-state-r2.json']),
    'cpuLimitPercent':5,'gpuUtilizationHardCapped':False,
    'compressionInterpretation':'FLAC/source PCM exactly preserved. Host stereo32kbpsOpus is lossy; this same-GSS comparison measures its effect in this screen. It is not the current firmware mono CELT bitstream or a codec-rate sweep.',
    'limitations':['NumPy CPU reference is not measured CuPy/AMD-GPU parity or author full WPE pipeline;WPE deliberately off.',
        'Exactly channels0/1 from an8mic public array; no verified acoustic-port geometry match to the close recorder pair.',
        'New overlap arms share the same predicted waveform activity gate;misses remain charged. This is not an adopted hard-gating product policy.',
        'Matched mono_activity is an activity-only baseline, not the best available single-mic separator. CachedPS4 uses a different pipeline/segmentation; both comparisons are reported.',
        'No ground-truth per-root backend selection, text/filler cleaning or hypothesis deletion.'],
    'finalHoldoutOpened':False,'productDefaultChanged':False,'newTrainingRuns':0,'newHardwareAccess':False,'qualityQualified':False}
atomic_json(C/'review.json',result)
print(json.dumps({k:result[k] for k in ['state','overlapTotals','cachedPreviousSingleMicPs4','ordinaryTotals','comparisons','newAsrCalls','timings','qualityQualified']},ensure_ascii=False),flush=True)
