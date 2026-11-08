"""Report the one audio-gate ablation for every preserved target lane."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,psutil
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize,Levenshtein
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
B=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation';C=B/'no-hard-gate'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);assert not (C/'review.json').exists()
for p in psutil.process_iter(['cmdline']):
    for a in p.info['cmdline'] or []:
        assert not (str(a).replace('\\','/').lower().startswith(str(M/'src').replace('\\','/').lower()+'/') and Path(str(a)).name in ['dual_mic_gss_no_gate_asr_worker_20261108.py','run_dual_mic_gss_no_gate_20261108.py'])
run=read(C/'run-r2.json');assert run['state']=='COMPLETE_DUAL_MIC_SPATIAL_CODEC_SCREEN_REVIEW_REQUIRED'
P=read(C/'protocol-r2.json');outputs=read(C/'asr-manifest-r2.json');assert len(outputs)==6
base=read(B/'review.json');source_rows=read(B/'separation-manifest-r2.json');new_rows=read(C/'separation-manifest-r2.json');items=[]
binding={'protocolSha256':sha(C/'protocol-r2.json'),'audioOnlySha256':P['audioOnlySha256'],'workerSourceSha256':P['asrWorkerSourceSha256']}
def edits(a,b):
    a=normalize(a);b=normalize(b);ops=Counter(o.tag for o in Levenshtein.editops(a,b))
    return {'referenceCharacters':len(a),'hypothesisCharacters':len(b),'substitute':ops['replace'],'delete':ops['delete'],'insert':ops['insert'],'total':sum(ops.values())}
for output in outputs:
    assert output['binding']==binding and sha(output['audio'])==output['audioSha256']
    assert output['text']=='\n'.join(r['text'] for r in output['acceptedLeaves'])
    native=next(r for r in new_rows if r['id']==output['id']);assert sha(native['ungatedDerivedAudio'])==native['sourceUngatedFloatSha256']
    nodes=[]
    for f in (C/'asr-outputs-r2'/output['id']).glob('*.json'):
        if f.name=='completed.json':continue
        node=read(f);assert node['binding']==binding and node['audioSha256']==output['audioSha256']
        assert node['rawSha256']==hashlib.sha256(json.dumps(node['raw'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();nodes.append(node['raw'])
    assert all(any(leaf==node for node in nodes) for leaf in output['acceptedLeaves'])
    person=next(r for r in base['perPerson'] if r['meeting']==output['meeting'] and r['rootIndex']==output['rootIndex'] and r['predictedSlot']==output['predictedSpeaker'])
    current=edits(person['referenceText'],output['text']);previous=person['conditions']['dual_pcm']['edits']
    items.append({'case':person['case'],'rootIndex':person['rootIndex'],'referencePerson':person['referencePersonForScoringOnly'],
        'gated':previous,'ungated':current,'ungatedText':output['text'],'gatedText':person['conditions']['dual_pcm']['text'],
        'totalEditDelta':current['total']-previous['total'],'deletionDelta':current['delete']-previous['delete'],
        'insertionDelta':current['insert']-previous['insert']})
keys=['referenceCharacters','hypothesisCharacters','substitute','delete','insert','total']
totals={arm:{k:sum(r[arm][k] for r in items) for k in keys} for arm in ['gated','ungated']}
state='REMOVE_HARD_GATE_RETAINS_LOCAL_GAIN_NEEDS_INDEPENDENT_VALIDATION' if totals['ungated']['total']<totals['gated']['total'] else 'REMOVE_HARD_GATE_REJECTED_ADDITIONAL_SPEECH_ERRORS'
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':state,
    'sourceMainReviewSha256':sha(B/'review.json'),'scope':'One causal removal of post-GSS predicted waveform zeroing on all6rawdual lanes. No fresh separation, no reference-guided audio, no per-person winner selection.',
    'totals':totals,'perPerson':items,'allSixPeopleScored':True,
    'newGssCalls':0,'newAsrCalls':read(C/'asr-state-r2.json')['newNeuralCalls'],
    'asrOwnedSeconds':sum(r['wholeProcessFamilySeconds'] for r in run['results'] if r['stage']=='asr'),
    'newModelsOrTraining':0,'generatedTextFiltered':False,'originalMainComparisonChanged':False,
    'notProductGatePassed':True,'qualityQualified':False}
atomic_json(C/'review.json',result)
print(json.dumps({'state':state,'totals':totals,'newGssCalls':0,'newAsrCalls':result['newAsrCalls'],'perPersonDeltas':[{'root':r['rootIndex'],'person':r['referencePerson'],'edits':r['totalEditDelta'],'delete':r['deletionDelta'],'insert':r['insertionDelta']} for r in items]},ensure_ascii=False),flush=True)
