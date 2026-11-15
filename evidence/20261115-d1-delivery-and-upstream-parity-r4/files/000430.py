"""Freeze audio-only same-meeting target-presence check before new embedding calls."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'identity-policy.json').exists();assert read(C/'review.json')['state']=='PS4_REAL_COMPONENT_SCREEN_FAILED_NOT_ADOPTED'
E=Path('E:/CodexData/Companion/.model-cache/ps4-target-extraction-20261107/audio');plan=[]
for meeting in read(C/'input-selection.json')['meetings']:
    for anchor in meeting['availableAnchors']:
        person=anchor['speaker'];file=E/(meeting['meeting']+'-anchor-'+str(person)+'.wav')
        plan.append({'id':meeting['meeting']+'-anchor-'+str(person),'meeting':meeting['meeting'],'kind':'anchor','predictedSpeaker':person,'audio':str(file),'audioSha256':sha(file)})
for lane in read(C/'separation-manifest-r2.json'):
    plan.append({'id':lane['id'],'meeting':lane['meeting'],'kind':'extracted-lane','predictedSpeaker':lane['predictedSpeaker'],'audio':lane['audio'],'audioSha256':lane['audioSha256']})
atomic_json(C/'identity-audio-only.json',plan)
P={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FROZEN_BEFORE_MATCHING_ENCODER_IDENTITY_PROBE',
    'workerSourceSha256':sha(Path(__file__).with_name('practical_ps4_identity_worker_20261107.py')),
    'modelReadySha256':sha(C/'model-ready.json'),'audioPlanSha256':sha(C/'identity-audio-only.json'),
    'model':'The exact frozen PS4 embedded ECAPA encoder. Same author peak normalization/pre-emphasis/mel/log mean normalization,192d unit embeddings, whole saved lane against all frozen same-meeting anchors. No new anchor choice or incompatible external speaker model.',
    'rule':'Predeclared top1 cosine identity only, no absolute cutoff or threshold sweep. Record every lane, including contradictions; no reference/text/speaker names passed. A later opt-in cached candidate can admit only self-matching target lanes and bypass ordinary single-person extraction. Do not reinterpret the failed original forced-extraction gate as passed.',
    'limitations':'Whole-lane embedding cannot prove every word is the target or detect all unseen speakers. Development audio overlap with pretraining unknown; no new full qualification.',
    'newAsrOrSeparationCallsAllowed':0,'qualityQualified':False}
atomic_json(C/'identity-policy.json',P);print(json.dumps({'state':P['state'],'inputs':len(plan)}))
