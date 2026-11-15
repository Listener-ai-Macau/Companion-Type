"""Freeze one local window audit; no window/cosine sweep or product score claim."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
B=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery');parent=B/'practical-conditioned-ps4-full-r1';C=B/'practical-ps4-local-presence-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert read(parent/'review.json')['state']=='FULL_COMPLEX_ROUTED_CANDIDATE_NOT_ADOPTED_TOTAL_REGRESSION'
assert not C.exists();C.mkdir();plan=[]
cases=read(parent/'audio-only.json')
for lane in read(parent/'asr-manifest-r2.json'):
    count=round(lane['audioSeconds']*16000);assert count==480000
    windows=[{'startSample':lo,'endSample':lo+48000} for lo in range(0,count-48000+1,24000)]
    case=next(r for r in cases if r['rootIndex']==lane['rootIndex'])
    plan.append({'id':lane['id'],'audio':lane['audio'],'audioSha256':lane['audioSha256'],'requestedSpeaker':lane['predictedSpeaker'],
        'sourceRootStartSample':case['startSample'],'windows':windows})
atomic_json(C/'audio-only.json',plan)
P={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FROZEN_BEFORE_TIME_LOCAL_NATIVE_IDENTITY_AUDIT',
    'workerSourceSha256':sha(Path(__file__).with_name('practical_ps4_local_presence_worker_20261107.py')),'inputPlanSha256':sha(C/'audio-only.json'),
    'parentFullFailureSha256':sha(parent/'review.json'),'windowSamples':48000,'hopSamples':24000,'batchSize':16,
    'rule':'One fixed3s/1.5s-hop native192d ECAPA crop audit on every admitted separated track, all6 unchanged automatic same-meeting anchors, FP32/eval, top1 only. No absolute cutoff and no tuning alternate windows. No ASR text/reference in inference; all raw outputs retained.',
    'researchSuitabilityCriterion':'Posthoc lexical target activity intersecting the3s window is positive, no activity is negative. Require >=95% positive-window recall and <=5% absent-window false acceptance before considering an identity gate; otherwise reject this simple crop hypothesis. These are only engineering falsification criteria, not CER/product gates.',
    'scope':'Target identity in a crop is not a trained target-activity detector. Test whether it is sufficient before building a transcript filter. No ASR/separation rerun, no words removed, no product default or formal quality promotion.',
    'qualityQualified':False}
atomic_json(C/'protocol.json',P);print(json.dumps({'state':P['state'],'lanes':len(plan),'windows':sum(len(r['windows']) for r in plan)}))
