from pathlib import Path
from datetime import datetime
import ast,hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-speaker-adaptation-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert read(C/'preparation-state.json')['state']=='COMPLETE_OFFICIAL_PUBLIC_TRAIN_VALIDATION_DATA_NO_NEURAL_CALLS'
original=read(D/'official-native-parity-r1/protocol.json');plan=read(C/'planned-trial.json')
root=Path('E:/CodexData/Companion/product-d1d2-20261114/public-speaker-adaptation-r1')
P={**plan,'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_ONE_REAL_PUBLIC_MEETING_SPEAKER_ADAPTER_BEFORE_BASELINE_AND_UPDATES',
 'checkpoint':original['checkpoint'],'checkpointSha256':original['checkpointSha256'],
 'extractedCheckpoint':'E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1/new-ordinary-run-r2/model_weights.ckpt',
 'converter':original['converter'],'converterSha256':original['converterSha256'],
 'rocmBlasLibrary':original['rocmBlasLibrary'],'rocmBlasLibrarySha256':original['rocmBlasLibrarySha256'],
 'pythonExe':'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',
 'audioOnlySha256':sha(C/'audio-only.json'),'trainSupervisionSha256':sha(C/'train-supervision.json'),
 'validationScoringSha256':sha(C/'validation-scoring-only.json'),
 'controlRun':str(root/'control-r1'),'baselineRun':str(root/'baseline-r1'),
 'baselineDecision':str(C/'baseline-decision.json'),'adapterFile':str(root/'train-r1/adapter.safetensors'),
 'originalBenchmarkProtocolSha256':sha(R/'docs/handoffs/20261108-competitive-sale-standard/benchmark-protocol.json'),
 'calibrationReplayMaximumAbsoluteToleranceBeforeOutputs':2e-5,
 'trainingUpdates':8,'epochs':4,'learningRate':.0001,'seed':20261115}
P['extractedCheckpointSha256']=sha(P['extractedCheckpoint'])
assert P['originalBenchmarkProtocolSha256']=='2a82b5b36b231dd4ba77c670c347bb573aa7a13f225271eb9c5750e309e99623'
p=C/'protocol.json';assert not p.exists();p.write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sources=['public_nemotron_training_worker_20261115.py','run_public_nemotron_training_20261115.py',
 'public_nemotron_adaptation_20261115.py','public_nemotron_supervision_20261115.py',
 'companion_community1_adapter_20261115.py','moss_windows_resource_limits_20261104.py',
 'companion_local_pcm_session_20261114.py','companion_windows_power_request_20261115.py',
 'practical_io_20261107.py','practical_nemotron_worker_20261107.py']
for name in sources:ast.parse((S/name).read_text(encoding='utf-8'))
b={'workerSha256':sha(S/sources[0]),'runnerSha256':sha(S/sources[1]),'protocolSha256':sha(p),
 'helpers':{str(S/name):sha(S/name) for name in sources[2:]}}
(C/'worker-binding.json').write_text(json.dumps(b,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':P['state'],'trainSources':len(read(C/'train-supervision.json')),
 'heldValidationSources':len(read(C/'validation-scoring-only.json')),'plannedUpdates':8,'ownerInputRequired':False},ensure_ascii=False))
