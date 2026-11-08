"""Predeclare one real-data adaptation pilot and unchanged deployment controls."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-target-activity-adaptation';OLD=R/'docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1';S=R/'model-research/src';read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'protocol.json').exists() and read(C/'audio-preparation-state.json')['state']=='COMPLETE_INDEPENDENT_REAL_TRAINING_AUDIO_PREPARATION'
files=[S/name for name in ['target_activity_adaptation_worker_20261108.py','target_activity_native_20261108.py','target_activity_adapter_20261108.py']]+[C/name for name in ['prepared-audio.json','training-inputs-only.json','supervised-enrollment-plan.json','training-labels.json','data-selection.json']]
P={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ONE_SMALL_REAL_MEETING_ACTIVITY_HEAD_ADAPTATION_FROZEN','workerSourceSha256':sha(files[0]),'sourceFiles':[{'file':str(p),'sha256':sha(p)} for p in files],
    'base':'Same pinned nomo-pvad release-1.1/native ERes2NetV2 and verified GPU author features as20261107. No new model family, ASR or separation changes.',
    'trainable':'Bypass only native forward no_grad decorator; freeze exact acoustic backbone (including BN statistics) and independent speaker encoder. Train only existing conditioning/projection/temporal/activity head.',
    'data':'64supervised examples from2new official train_L sessions/room tags;32examples from a separate train_S room for adaptation validation. Original microphone0,4s real excerpts and disjoint supervised enrollment. None of prior L/S/AMI or final holdout is training data. Physical-speaker independence is not established.',
    'seed':20261108,'epochs':3,'batchSize':1,'gradientAccumulation':4,'learningRate':.0001,'weightDecay':.01,'gradientClipNorm':1.,'optimizer':'AdamW','loss':'2-class cross_entropy on valid native160ms cells; target1 iff any lexical target speech in the cell. No class/cutoff/window search.',
    'cachedBaseProbabilityTolerance':.00001,'featureStage':'Cache109unique backbone feature sets and18new matched profile vectors; reuse old15automatic evaluation vectors only after encoder/feature/audio hash checks. Require parity with all67frozen base probabilities before training.',
    'probe':'On first new training example, native decorated/unwrapped/cached logits+mask must be exactly equal, head gradients finite/nonzero, a probe optimizer step changes only head, frozen backbone/BN/speaker weights unchanged. Probe step never initializes the real run.',
    'checkpointSelection':'Lowest cross_entropy on separate train_S validation room among unadapted baseline and3epochs. Never use prior13deployment controls for checkpoint selection, hyperparameters or cutoff tuning. No separate-room loss gain means retain base and stop before deployment evaluation.',
    'evaluation':'One-shot unchanged13real development clips/67anonymous target queries, original automatic profiles,0.7 threshold and160ms grid. Same whole-meeting fixed reference mapping and original rejection criteria. Compare adapted vs unadapted candidate and existing NativeFP16 activity baseline separately.',
    'scope':'Small adaptation/resource/validation feasibility, not generalization proof. No original text/audio/default changes. Activity metrics are not wordCER; strict<5%, complex content/ordinary nonregression/full cross-domain/final holdout/minutes/Windows-Android/card/sale gates stay open.',
    'qualityQualified':False,'finalHoldoutOpened':False}
atomic_json(C/'protocol.json',P)
evaluation=C/'evaluation';evaluation.mkdir(exist_ok=True)
for name in ['audio-only.json','scoring-only.json']:(evaluation/name).write_bytes((OLD/name).read_bytes())
evaluation_protocol={'decisionThreshold':.7,'shortRejectionCriteria':read(OLD/'protocol.json')['shortRejectionCriteria'],'originalControlProtocolSha256':sha(OLD/'protocol.json'),'adaptationProtocolSha256':sha(C/'protocol.json'),'source':'Identical controls/rejection criteria, head changes only; no training/checkpoint choice from these labels.'}
atomic_json(evaluation/'protocol.json',evaluation_protocol)
# Reuse the exact existing metric implementation with explicitly scoped receipt/text changes.
original=(S/'finish_practical_target_activity_20261107.py').read_text(encoding='utf8');text=original.replace("C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1')","C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-target-activity-adaptation/evaluation')")
text=text.replace("['practical_target_activity_worker_20261107.py','run_practical_target_activity_20261107.py']","['target_activity_adaptation_worker_20261108.py','run_target_activity_adaptation_20261108.py']")
text=text.replace("['inventory','pilot','short']","['inventory','features','probe','train','evaluate']")
text=text.replace("'SHORT_ACTIVITY_HYPOTHESIS_PASSES_FULL_VALIDATION_STILL_REQUIRED'","'ADAPTED_ACTIVITY_HEAD_SHORT_PASSES_FULL_VALIDATION_STILL_REQUIRED'").replace("'SHORT_ACTIVITY_CANDIDATE_REJECTED_NO_FULL_EXPANSION'","'ADAPTED_ACTIVITY_HEAD_REJECTED_BEFORE_FULL_EXPANSION'")
text=text.replace("'pilotIncludesAll15ProfileEncodingsAnd6ActivityQueries':True,'shortStageReuses15VectorsAnd6SameAudioPilotQueries':True,","'original15AutomaticProfilesReusedUnchanged':True,'cached67BaseProbabilitiesMatchedBeforeTraining':True,'noAcousticBackboneRetraining':True,")
text=text.replace("'actualOwnedStageSecondsIncludingFailedPreparation':times","'actualOwnedStageSecondsIncludingKnownInterruptions':times")
insertion="old_review=read(C.parent.parent/'20261107-model-generation-recovery/practical-target-activity-r1/review.json')\nfor row in review['meetings']:\n    row['unadaptedCandidate']=next(r['candidate'] for r in old_review['meetings'] if r['meeting']==row['meeting'])\nreview['trainingHistory']=read(C.parent/'training-history.json')\nreview['selectedBySeparateRoomValidationOnly']=read(C.parent/'best-checkpoint.json')\n"
text=text.replace("atomic_json(C/'posthoc-activity-details.json'",insertion+"atomic_json(C/'posthoc-activity-details.json'")
scorer=S/'score_target_activity_adapter_20261108.py';assert not scorer.exists();scorer.write_text(text,encoding='utf8')
atomic_json(C/'metric-reuse-proof.json',{'source':str(S/'finish_practical_target_activity_20261107.py'),'sourceSha256':sha(S/'finish_practical_target_activity_20261107.py'),'generated':str(scorer),'generatedSha256':sha(scorer),'changes':'Control root, owned process names, actual adaptation-stage receipt labels, adapted state labels, and added original unadapted/training comparison. The interval/window scoring and rejection predicates are reused unchanged.'})
print(json.dumps({'state':P['state'],'epochs':3,'trainExamples':64,'validationExamples':32,'fixedDeploymentQueries':67,'workerSourceSha256':P['workerSourceSha256']},ensure_ascii=False),flush=True)
