"""Count protected checkpoint shapes only; no Torch import or model computation."""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,struct,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=1,memory_bytes=128*1024**2)
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/meeting-domain-data-r1'
p=Path('E:/CodexData/Companion/.model-cache/qwen-native17-asr-20261107/model/model.safetensors')
with p.open('rb') as f:
 length=struct.unpack('<Q',f.read(8))[0];assert length==88112;raw=f.read(length);header=json.loads(raw)
weights={k:v for k,v in header.items() if k!='__metadata__'};counts={prefix:sum(math.prod(v['shape']) for k,v in weights.items() if k.startswith(prefix)) for prefix in ['model.audio_tower.','model.multi_modal_projector.','model.language_model.']}
layers=sorted({int(k.split('.')[3]) for k in weights if k.startswith('model.audio_tower.layers.')});assert layers==list(range(24))
selected={k:v for k,v in weights.items() if k.startswith('model.audio_tower.layers.') and int(k.split('.')[3]) in range(16,24) and k.endswith(('.self_attn.q_proj.weight','.self_attn.v_proj.weight'))};assert len(selected)==16
old_lora=sum(8*sum(v['shape']) for v in selected.values());acoustic=sum(counts[k] for k in ['model.audio_tower.','model.multi_modal_projector.'])
total=sum(math.prod(v['shape']) for v in weights.values());assert sum(counts.values())==total
output={'state':'EXACT_PROTECTED_ASR_HEADER_PARAMETER_COVERAGE_AUDIT_NOT_A_TRAINED_MODEL','at':datetime.now().astimezone().isoformat(),'checkpoint':str(p),
 'originalCheckpointSha256':'2db53c7d81bd9b8cbc6a074e89be2c968a0d373fb4ee68bb1b1e14f7042dfee1','headerSha256':hashlib.sha256(raw).hexdigest(),'weightPayloadRead':False,
 'tensorCount':len(weights),'totalParameters':total,'componentParameters':counts,'audioEncoderLayers':24,'previousRejectedAudioLoraLayers':8,'previousRejectedAudioLoraTargetMatrices':16,
 'previousRejectedAudioLoraTrainableParameters':old_lora,'previousLoraParametersOverAcousticAndBridge':old_lora/acoustic,'previousBridgeTrained':False,
 'futureBroaderAcousticAndBridgeParameters':acoustic,'proposedBroaderTrainingEffectProven':False,
 'ordinaryCpuAdamBf16WeightGradFp32MomentsPlusFrozenLmLowerBoundBytes':acoustic*12+counts['model.language_model.']*2,
 'memoryEstimateScope':'Lower bound for ordinary full acoustic+bridge Adam on CPU: BF16 weights+grad and FP32 first/second moments, plus frozen BF16 language weights. Excludes activations, processor, allocator, optional FP32 master weights and checkpoints; it is not a GPU specification or measured peak.',
 'fitsCurrent2GiBPrivateCpuTrainingBudget':False,'inferenceCpuPortIndependentFromTrainingHardware':True,'doNotRepeatFailedLast8QvLoraWithOnlyRankOrPromptChanges':True,
 'nextTrainingDesign':'A single broader meeting-domain supervised adaptation candidate, with encoder/bridge coverage and bilingual no-regression gates frozen before training; training plan still requires proven participant split and usable training resources.',
 'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'acoustic-parameter-coverage.json',output);print(json.dumps(output,ensure_ascii=False))
