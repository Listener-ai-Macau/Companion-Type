"""Paired all-example scoring; absent targets remain in the insertion count."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,os,re
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize,Levenshtein
from companion_tse_training_20261108 import target_text
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-tse-source-supervision'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
P=read(C/'free-asr-protocol-r1.json');T=read(C/'training-protocol-r1.json');outputs=read(C/'free-asr-manifest-r1.json');assert len(outputs)==P['expectedOutputRows']==132
assert not (C/'free-asr-review.json').exists()
binding={'protocolSha256':sha(C/'free-asr-protocol-r1.json'),'audioOnlySha256':P['audioOnlySha256'],'workerSourceSha256':P['asrWorkerSourceSha256']}
byid={r['id']:r for r in outputs};assert len(byid)==132
for output in outputs:
    assert output['binding']==binding and sha(output['audio'])==output['audioSha256']
    assert output['text']=='\n'.join(r['text'] for r in output['acceptedLeaves'])
    source=byid[output['sameAudioReuseSource']] if output.get('sameAudioReuseSource') else output
    assert source['audioSha256']==output['audioSha256'] and source['acceptedLeaves']==output['acceptedLeaves']
    packets=[]
    for file in (C/'free-asr-outputs-r1'/source['id']).glob('*.json'):
        if file.name=='completed.json':continue
        packet=read(file);assert packet['binding']==binding and packet['audioSha256']==source['audioSha256'];assert packet['rawSha256']==hashlib.sha256(json.dumps(packet['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();packets.append(packet['raw'])
    assert packets and all(any(leaf==packet for packet in packets) for leaf in output['acceptedLeaves'])
def edits(ref,hyp):
    a,b=normalize(ref),normalize(hyp);v=Counter(x.tag for x in Levenshtein.editops(a,b));return {'referenceCharacters':len(a),'substitute':v['replace'],'delete':v['delete'],'insert':v['insert'],'total':sum(v.values())}
def total(values):
    d={key:sum(v[key] for v in values) for key in ['referenceCharacters','substitute','delete','insert','total']};d['cer']=d['total']/d['referenceCharacters'] if d['referenceCharacters'] else None;return d
examples={r['id']:r for r in read(C/'natural-validation-queries.json')};rows=[]
for identity in examples:
    example=examples[identity];assert example['role']=='natural_validation';reference=re.sub(r'<[^>]*>','',example['referenceForScoringOnly']).replace('&','').strip()
    if example['category']=='absent_other_speech':assert not normalize(reference)
    conditions={}
    for arm in ['baseline','adapted']:
        output=byid[arm+'--'+identity];assert output['sourceExampleId']==identity and output['condition']==arm;conditions[arm]={'text':output['text'],'edits':edits(reference,output['text'])}
    rows.append({'id':identity,'meeting':example['meeting'],'category':example['category'],'referenceForScoringOnly':reference,'conditions':conditions})
categories={category:{arm:total([r['conditions'][arm]['edits'] for r in rows if r['category']==category]) for arm in ['baseline','adapted']} for category in ['present_solo','present_overlap','absent_other_speech']}
totals={arm:total([r['conditions'][arm]['edits'] for r in rows]) for arm in ['baseline','adapted']}
overlap_improves=categories['present_overlap']['adapted']['total']<categories['present_overlap']['baseline']['total']
solo_ok=categories['present_solo']['adapted']['total']<=categories['present_solo']['baseline']['total']
absent_ok=categories['absent_other_speech']['adapted']['insert']<=categories['absent_other_speech']['baseline']['insert']
retain=overlap_improves and solo_ok and absent_ok and totals['adapted']['total']<totals['baseline']['total']
per_meeting={m:{category:{arm:total([r['conditions'][arm]['edits'] for r in rows if r['meeting']==m and r['category']==category]) for arm in ['baseline','adapted']} for category in ['present_solo','present_overlap','absent_other_speech']} for m in sorted({r['meeting'] for r in rows})}
both_meetings=all(v['present_overlap']['adapted']['total']<v['present_overlap']['baseline']['total'] and v['present_solo']['adapted']['total']<=v['present_solo']['baseline']['total'] and v['absent_other_speech']['adapted']['insert']<=v['absent_other_speech']['baseline']['insert'] for v in per_meeting.values())
retain=retain and both_meetings
result={'at':datetime.now().astimezone().isoformat(),'state':'FIXED_TSE_PILOT_FREE_ASR_GAIN_REQUIRES_UNSEEN_AUTOMATIC_MEETINGS' if retain else 'FIXED_TSE_PILOT_REJECTED_FREE_ASR_REGRESSION','metric':'Strict normalized character edits on all 66 new natural real-meeting supervised-profile queries from two source meetings, before/after exact same recognizer. Repeated source windows across target persons are target-extraction queries, not a whole-meeting CER. Empty targets count all hallucinated characters as insertions.','allExpectedOutputsScored':132,'totals':totals,'categories':categories,'perMeetingCategories':per_meeting,'bothNewMeetingsPassed':both_meetings,'perExample':rows,'overlapImproved':overlap_improves,'soloNonregression':solo_ok,'absentInsertionNonregression':absent_ok,'retainedForUnseenAutomaticMeetingValidationOnly':retain,'referencePassedToProcessingWorker':False,'inferenceAstMatchesOriginal':P['inferenceAstMatchesOriginal'],'finalHoldoutOpened':False,'physicalSpeakerSplitKnownIndependent':False,'qualityQualified':False,'strictFullMeetingCerBelow5Qualified':False,'saleQualified':False}
atomic_json(C/'free-asr-review.json',result);print(json.dumps({k:result[k] for k in ['state','totals','categories','retainedForUnseenAutomaticMeetingValidationOnly']},ensure_ascii=False),flush=True)
