"""Use fixed read-only cache association support, never reference labels."""
from pathlib import Path
source=Path('work/prepare_activity_guard_composition_20261115.py').read_text(encoding='utf-8')
replacements=[
    ("G=T/'single-source-activity-guard-r1';C=G/'composition-r1';OLD=T/'continuous-overlap-composition-r1'",
     "G=T/'contextual-speaker-binding-r1';C=T/'context-supported-composition-r1';OLD=T/'continuous-overlap-composition-r1'"),
    ("P=read(G/'protocol.json');observation=read(Path(P['observationRun'])/'state.json')\nassert observation['state']=='COMPLETE_ORIGINAL_ACTIVITY_HEAD_OBSERVATION_SCORING_PENDING'\nassert observation['allOriginalSpeakerPredictionsBitExact']\nE=Path(P['observationRun']).parent/'composition-r1';assert not C.exists() and not E.exists();C.mkdir();E.mkdir()\nobserved={r['meeting']:r for r in observation['results']};activity={}\nfor meeting,row in observed.items():\n    item=row['outputs']['guarded-overlap'];assert sha(item['file'])==item['sha256'];activity[meeting]=np.load(item['file'],allow_pickle=False)",
     """P=read(G/'protocol.json');association_run=Path(read(G/'association-execution.json')['run'])
observation=read(association_run/'state.json')
assert observation['state']=='COMPLETE_CONTEXTUAL_AUDIO_SPEAKER_ASSOCIATION_UNQUALIFIED'
assert not observation['referenceRead']
assert read(G/'association-validation.json')['independentOriginalRttmMembershipConfirmed']
E=association_run.parent.parent/'context-supported-composition-r1';assert not C.exists() and not E.exists();C.mkdir();E.mkdir()
activity={}
for row in read(association_run/'associations.json')['cases']:
    mask=np.zeros(row['frames'],dtype=np.bool_)
    for segment in row['segments']:
        if segment['associationReason']=='contextual-distinct-single-source-agreement':
            assert segment['predictedModelSlots'][0]!=segment['predictedModelSlots'][1]
            mask[segment['startFrame']:segment['endFrame']]=True
    activity[row['id']]=mask
P['candidateRule']='Fixed original .5speaker activities and fixed read-only original-cache source queries: route separation only where the already frozen contextual association rule supports2distinct original speaker slots and both source queries predict single speech. Other intervals preserve original microphone; model-uncertain source/audio artifacts retained. No weights/threshold/duration/word selection.'
"""),
    ("indices=np.arange(low,high,dtype=np.int64)//160;mask=activity[case['meeting']][indices]",
     "mask=activity[case['id']];assert mask.shape==(len(original),)"),
    ("'FROZEN_ORIGINAL_AUXILIARY_ACTIVITY_AGREEMENT_COMPOSITION_BEFORE_ASR'",
     "'FROZEN_ORIGINAL_CONTEXT_SUPPORTED_AUDIO_COMPOSITION_BEFORE_ASR'"),
    ("'guardObservationSha256':sha(Path(P['observationRun'])/'state.json')",
     "'guardObservationSha256':sha(association_run/'state.json')"),
    ("'PASS_ALL32_AUXILIARY_ACTIVITY_AGREEMENT_SAMPLE_ROUTING'",
     "'PASS_ALL32_CONTEXT_SUPPORTED_SAMPLE_ROUTING'"),
    ("G/'protocol.json',Path(P['observationRun'])/'state.json'",
     "G/'protocol.json',association_run/'state.json',association_run/'associations.json'"),
    ("stage='Same .5speaker activity, require unchanged original auxiliary-head argmax2 too. Fixed before activity inference, no labels or duration tuning. Precise sample routing, allusedwords counted.'",
     "stage='Same .5speaker activity and fixed contextual separated-source association predictions. Only model-supported pairs use separation, other time retains original audio and unconfirmed status. No reference-gated intervals or word selection. Previous failed auxiliary guard retained.'"),
    ("Path('work/score_activity_guard_composition_20261115.py')",
     "Path('work/score_context_supported_composition_20261115.py')")]
for old,new in replacements:
    assert old in source,old;source=source.replace(old,new)
compile(source,str(Path(__file__)),'exec')
exec(compile(source,str(Path(__file__)),'exec'))
