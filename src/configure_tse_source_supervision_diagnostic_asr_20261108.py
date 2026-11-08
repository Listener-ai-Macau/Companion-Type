"""Freeze a post-rejection word diagnostic; never turn failed waveform gates green."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,py_compile
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-tse-source-supervision';read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=read(C/'training-review.json');assert not review['advanceToNaturalFreeAsr'];alignment=read(C/'alignment-diagnostic.json');assert alignment['summary']['baseline']['known_additive_mixture']['negativeZeroLagCorrelations']==32
plan={'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_POST_REJECTION_NATURAL_WORDS_AND_RAW_SOLO_CONTROL','originalWaveformRejectionUnchanged':True,'originalTrainingProtocolSha256':sha(C/'training-protocol-r1.json'),'trainingReviewSha256':sha(C/'training-review.json'),'alignmentDiagnosticSha256':sha(C/'alignment-diagnostic.json'),'newEvidence':'All32 original mixed outputs have negative target correlation, so direct waveform error is partly polarity dependent, while trained outputs show more other-source preference. Word accuracy and raw-solo controls distinguish waveform representation error, extraction damage and recognition limitations. No gain/polarity/delay correction or new weights will be used.','scope':'All66 already-frozen new natural queries before/after plus all8 already-frozen real solo preservation excerpts in raw/baseline/adapted forms. No cherry-picked subset, prompts, ground-truth input, model change or candidate promotion.','newOutputRows':156,'noFurtherTrainingThisCandidate':True,'promotionAllowed':False,'qualityQualified':False};atomic_json(C/'post-rejection-asr-plan.json',plan)
# Reuse the preserved generator body; emitted decoder is self-contained and its
# inference AST must still equal the unchanged original native inference.
template=(S/'configure_tse_source_supervision_asr_20261108.py').read_text(encoding='utf8');body=template[template.index("source=(S/'joint_neural_spatial_asr_worker_20261108.py')"):]
body=body.replace("assert P['trainingProxyPassed'] and P['referencePassedToWorker'] is False","assert (P['trainingProxyPassed'] or P.get('diagnosticAfterRejection',False)) and P['referencePassedToWorker'] is False")
body=body.replace("'trainingProxyPassed':True","'trainingProxyPassed':False,'diagnosticAfterRejection':True,'diagnosticPlanSha256':sha(C/'post-rejection-asr-plan.json')").replace("'expectedOutputRows':132","'expectedOutputRows':156").replace('FROZEN_132_AUDIO_ONLY_FREE_GENERATIONS','FROZEN_POST_REJECTION_156_AUDIO_ONLY_DIAGNOSTIC')
P=read(C/'training-protocol-r1.json');audio=[];controls={x['id']:x for x in read(C/'synthetic-validation-units.json') if x['kind']=='single_target_preservation'};assert len(controls)==8;references=[]
for condition in ['baseline','adapted']:
    value=read(C/(condition+'-validation.json'));assert value['protocolSha256']==review['protocolSha256']
    for row in value['naturalAudioOnly']:audio.append({k:row[k] for k in ['id','sourceExampleId','condition','audio','audioSha256','audioSeconds']})
    for row in value['synthetic']:
        if row['unitId'] not in controls:continue
        unit=controls[row['unitId']];identity='solo-control--'+unit['id'];audio.append({'id':condition+'--'+identity,'sourceExampleId':identity,'condition':condition,'audio':row['audio'],'audioSha256':row['audioSha256'],'audioSeconds':row['audioSeconds']})
for unit in controls.values():
    identity='solo-control--'+unit['id'];raw=unit['mixture'];audio.append({'id':'raw--'+identity,'sourceExampleId':identity,'condition':'raw','audio':raw['audio'],'audioSha256':raw['audioSha256'],'audioSeconds':raw['audioSeconds']});references.append({'id':identity,'meeting':unit['meeting'],'referenceForScoringOnly':unit['targets'][0]['referenceForScoringOnly']})
assert len(audio)==156 and len({r['id'] for r in audio})==156
# Raw controls are physical mic0 only, matching the mono recognizer contract.
from companion_tse_source_data_20261108 import pcm_read,pcm_write
for row in audio:
    if row['condition']=='raw':
        mono=pcm_write(Path(P['audioRoot'])/'raw-solo-control'/(row['sourceExampleId']+'.wav'),pcm_read(row['audio'],2)[:,:1]);row.update({k:mono[k] for k in ['audio','audioSha256','audioSeconds']})
for row in audio:assert sha(row['audio'])==row['audioSha256']
manifest=C/'free-asr-audio-only-r1.json';assert not manifest.exists();atomic_json(manifest,audio);atomic_json(C/'solo-control-scoring-only.json',references);exec(compile(body,str(__file__)+':native-generator','exec'),globals())
