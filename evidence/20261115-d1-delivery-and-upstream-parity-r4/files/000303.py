"""Same frozen numerical trial; bounded checkpoint I/O and explicit zero-step replay."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-tse-supervised-adaptation';E=Path('E:/CodexData/Companion/.model-cache/tse-supervised-adaptation-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=C/'training-protocol-r2.json';P=read(old);assert all(sha(x['file'])==x['sha256'] for x in P['sourceFiles']);proof=C/'checkpoint-proof-r1/state.json';assert read(proof)['state']=='PASS_BOUNDED_CHECKPOINT_FULL_ADAMW_RNG_NEXT_UPDATE_EXACT'
checkpoint=read(C/'latest-training-checkpoint.json');assert checkpoint['completedSteps']==0 and checkpoint['protocolSha256']==sha(old);assert sha(checkpoint['trainableWeights'])==checkpoint['trainableWeightsSha256'] and sha(checkpoint['optimizerState'])==checkpoint['optimizerStateSha256']
baseline=C/'baseline-validation.json';assert read(baseline)['protocolSha256']==sha(old);archive=C/'baseline-validation-before-streamed-io.json';assert not archive.exists();archive.write_bytes(baseline.read_bytes());prior=C/'latest-training-checkpoint-before-streamed-io.json';assert not prior.exists();prior.write_bytes((C/'latest-training-checkpoint.json').read_bytes())
source=(S/'tse_supervised_memory_train_worker_20261108.py').read_text(encoding='utf8');source=source.replace('from companion_tse_checkpoint_20261108 import save_checkpoint,restore_checkpoint','from companion_tse_checkpoint_streamed_20261108 import save_checkpoint,restore_checkpoint,verify_archive')
needle="if step%P['checkpointInterval']==0 or step==len(train):"
replacement="""if step==P['replayInterruptedUpdateCount']:
            replay=verify_archive(P['partialInterruptedWeights'],{n:p for n,p in parameters},torch=torch);atomic_json(out/'interrupted-step-replay-proof.json',{**replay,'state':'PASS_INTERRUPTED_STEP16_WEIGHTS_REPLAYED_EXACTLY','step':step,'optimizerStateWasNotRecoveredFromPartialWeights':True});state['interruptedStep16WeightsReplayedBitExactly']=True;save()
        if step%P['checkpointInterval']==0 or step==len(train):"""
assert needle in source;source=source.replace(needle,replacement)
worker=S/'tse_supervised_streamed_train_worker_20261108.py';assert not worker.exists();worker.write_text(source,encoding='utf8',newline='\n')
failure=read(C/'checkpoint-native-failure-r1.json');extra=[worker,S/'companion_tse_checkpoint_streamed_20261108.py',proof,C/'checkpoint-proof-protocol-r1.json',archive,prior,C/'checkpoint-native-failure-r1.json']
updated={**P,'at':datetime.now().astimezone().isoformat(),'workerSha256':sha(worker),'sourceFiles':[*P['sourceFiles'],*[{'file':str(p),'sha256':sha(p)} for p in extra]],'checkpointIoProof':str(proof),'checkpointIoProofSha256':sha(proof),'supersedesZeroUpdateMemoryProtocol':{'file':str(old),'sha256':sha(old)},'checkpointRoot':str(E/'checkpoints-r3'),'audioRoot':str(E/'validation-audio-r3'),'baselineValidationProtocolSha256':sha(old),'baselineValidationSha256':sha(baseline),'replayInterruptedUpdateCount':16,'partialInterruptedWeights':failure['partialWeightFile'],'partialInterruptedWeightsSha256':failure['partialWeightFileSha256'],'checkpointIoCorrection':'Standard safetensors streamed in 1MiB chunks, no whole CPU state dictionaries. Verify all saved bytes against device, store complete AdamW and CPU/GPU RNG. Resume verified zero-step original checkpoint; replay the same interrupted first16 updates and require exact trained tensor equality before proceeding. Final model still receives one166-example pass; actual total executed updates include16 interrupted updates.'}
for key in ['seed','trainingOrder','validationOrder','learningRate','weightDecay','gradientClipNorm','epochs','loss','qualityDecision','lossComparisonTolerance']:assert updated[key]==P[key]
target=C/'training-protocol-r3.json';assert not target.exists();atomic_json(target,updated)
adopted={**checkpoint,'state':'ADOPTED_EXACT_ZERO_STEP_CHECKPOINT_SAME_NUMERICAL_TRIAL','adoptedFromZeroStepProtocolSha256':checkpoint['protocolSha256'],'adoptedFromCheckpointFile':str(prior),'adoptedFromCheckpointSha256':sha(prior),'protocolSha256':sha(target),'sameWeightsOrderLossOptimizerAndSeedVerified':True};atomic_json(C/'latest-training-checkpoint.json',adopted)
print(json.dumps({'state':'FROZEN_SAME_TRIAL_BOUNDED_CHECKPOINT_REPLAY','protocol':str(target),'replayedStepsBeforeContinuing':16}),flush=True)
