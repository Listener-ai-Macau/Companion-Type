"""Freeze one night-only pilot from existing sources; never launch a model."""
from datetime import datetime
from pathlib import Path
import ast
import hashlib
import json
import math
import shutil

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
S = ROOT/'model-research/src'
D = ROOT/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D/'joint-architecture-r1'
DATA = J/'meeting-domain-data-r1'
C = J/'night-acoustic-pilot-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/night-acoustic-pilot-r1')
RUNTIME = Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime')
MODEL = Path('E:/CodexData/Companion/.model-cache/qwen-native17-asr-20261107/model')
read = lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def item(path):
    return {'file':str(path),'sha256':sha(path)}

export = read(DATA/'acoustic-export-r2.json')
provenance = Path(export['trainJsonl']).with_name('example-provenance.json')
training = read(provenance)
assert len(training) == 944 and len({r['meeting'] for r in training}) == 22
assert sha(export['trainJsonl']) == export['trainJsonlSha256']
strict_source = D/'sequential-meeting-stageA-r2'
roles = {r['id']:r['role'] for r in read(strict_source/'scoring-only.json')}
validation = [r for r in read(strict_source/'audio-only.json') if roles[r['id']] == 'validation']
assert len(validation) == 24
evaluation = []
for row in validation:
    evaluation.append({'id':row['id'],'meeting':row['meeting'],'scope':'strict-validation',
                       'audio':row.get('wav',row.get('audio')),
                       'audioSha256':row.get('wavSha256',row.get('audioSha256')),
                       'frames':row['frames'],'language':row['language']})
ordinary_control = J/'cpu-retained-baseline-join-r4'
original_leaves = read(ordinary_control/'binding.json')['cases']
assert len(original_leaves) == 79
for row in original_leaves:
    assert sha(row['rawAsrFile']) == row['rawAsrSha256']
    raw = read(row['rawAsrFile'])['raw']
    padding = raw.get('inputPaddingSamples',0)
    assert raw.get('modelInputSamples',row['frames']+padding) == row['frames']+padding
    evaluation.append({'id':'S_R004S03C01-'+row['id'],'meeting':'S_R004S03C01',
                       'scope':'ordinary-whole-leaf','audio':row['wav'],
                       'audioSha256':row['wavSha256'],'frames':row['frames'],'language':'Chinese',
                       'sourceStartFrame':row['sourceStartFrame'],'sourceEndFrame':row['sourceEndFrame'],
                       'inputPaddingSamples':padding})
assert not ({r['meeting'] for r in training} & {r['meeting'] for r in evaluation})
assert not any('L_R003S03C02' in r['meeting'] for r in training+evaluation)
assert not any('reference' in key.lower() or key in ['text','target'] for r in evaluation for key in r)
leaves = [r for r in evaluation if r['scope'] == 'ordinary-whole-leaf']
assert leaves[0]['sourceStartFrame'] == 0 and leaves[-1]['sourceEndFrame'] == 37233904
assert all(a['sourceEndFrame'] == b['sourceStartFrame'] for a,b in zip(leaves,leaves[1:]))
source_names = [
    'meeting_acoustic_contract_20261116.py','meeting_acoustic_worker_20261116.py',
    'meeting_acoustic_night_20261116.py',
    'meeting_acoustic_evaluate_20261116.py','score_meeting_acoustic_candidate_20261116.py',
    'practical_qwen_streamed_loader_20261107.py','moss_streamed_weights_20261104.py',
    'moss_windows_resource_limits_20261104.py','practical_io_20261107.py',
    'companion_community1_adapter_20261115.py','companion_local_pcm_session_20261114.py',
]
for name in source_names:
    ast.parse((S/name).read_text(encoding='utf-8'))
base_protocol = Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json')
native = read(base_protocol)
assert read(native['supportedGpuFeatureNumericProof'])['state'] == 'PASS_SUPPORTED_GPU_FEATURES_INDEPENDENT_NUMPY_REFERENCE'
assert read(native['streamedLoaderControl'])['state'] == 'PASS_STANDARD_AND_STREAMED_TINY_QWEN_EXACT_LOGITS_AND_GENERATION'
training_bytes = 317477504*16+1720574976*2
checkpoint_bytes = 317477504*4*3
training_checkpoints = len(set([1,472]+list(range(64,473,64))))
needed_disk = checkpoint_bytes*(training_checkpoints+2)+5*1024**3
assert shutil.disk_usage('E:/').free > needed_disk
C.mkdir(exist_ok=True); E.mkdir(exist_ok=True)
audio_file = C/'evaluation-audio-only.json'
if (C/'packet.json').exists():
    assert not (E/'gpu-preflight/preflight.json').exists() and not (E/'training').exists(), 'Cannot refreeze after any neural batch begins'
    old = C/'packet.json'
    backup = C/('packet-before-offline-repair-'+sha(old)[:16]+'.json')
    assert not backup.exists(), 'Do not overwrite frozen history'
    backup.write_bytes(old.read_bytes())
    old_score = C/'scoring-control.json'
    if old_score.exists():
        (C/('scoring-before-offline-repair-'+sha(old_score)[:16]+'.json')).write_bytes(old_score.read_bytes())
audio_file.write_text(json.dumps(evaluation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
bindings = [S/n for n in source_names]+[audio_file,strict_source/'audio-only.json',base_protocol,
            Path(native['supportedGpuFeatureNumericProof']),Path(native['streamedLoaderControl'])]
bindings += [MODEL/n for n in ['config.json','generation_config.json','processor_config.json','tokenizer.json','tokenizer_config.json','chat_template.jinja']]
installed = RUNTIME/'Lib/site-packages/transformers/models/qwen3_asr'
bindings += [installed/n for n in ['modeling_qwen3_asr.py','processing_qwen3_asr.py','feature_extraction_qwen3_asr.py']]
packet = {
    'state':'FROZEN_SINGLE_NIGHT_ACOUSTIC_PILOT_OFFLINE_READY_GPU_EXECUTION_UNVERIFIED',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'ownerWorkMode':'Daytime existing-output analysis, data/code checks; night actual discrete GPU preflight then one fixed batch. No CPU/integrated-GPU training, scheduled job or implicit fallback.',
    'target':{'accuracy':.98,'floorAccuracy':.95,'originalTextErrorGateExclusive':.05},
    'modelRoot':str(MODEL),'modelSha256':'2db53c7d81bd9b8cbc6a074e89be2c968a0d373fb4ee68bb1b1e14f7042dfee1',
    'modelWeightBytes':4076193080,'modelWeightPayloadReadByPreparation':False,
    'runtime':{'python':str(RUNTIME/'Scripts/python.exe'),'torch':'2.11.0+rocm10.0.0','transformers':'5.22.1'},
    'blas':{'file':str(RUNTIME/'Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'),
            'sha256':'88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0'},
    'trainingWorker':str(S/'meeting_acoustic_worker_20261116.py'),
    'evaluationWorker':str(S/'meeting_acoustic_evaluate_20261116.py'),
    'nightEntry':str(S/'meeting_acoustic_night_20261116.py'),
    'runRoot':str(E),
    'scoringPython':'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',
    'independentScorer':str(S/'score_meeting_acoustic_candidate_20261116.py'),
    'scoringControl':str(C/'scoring-control.json'),
    'trainJsonl':item(Path(export['trainJsonl'])),'provenance':item(provenance),
    'training':{'trainablePrefixes':['model.audio_tower.','model.multi_modal_projector.'],
                'trainableParameters':317477504,'languageModelFrozen':True,
                'epochs':1,'batchSize':1,'gradientAccumulation':2,
                'lossNormalization':'Token-weighted mean across each accumulated group, explicit target-only mask including EOS.',
                'seed':20261116,'learningRate':2e-5,'gradientClip':1.,
                'optimizer':'AdamW,FP32 trainable parameters/gradients/moments on GPU,betas(.9,.999),eps1e-8,weight_decay0,capturableTrue,foreachFalse,fusedFalse',
                'autocast':'BF16; final independent inference returns acoustic weights to native BF16',
                'checkpointEveryUpdates':64,'checkpointAfterFirstUpdate':True,'checkpointPublication':'Stream bounded1MiB host blocks; immutable tensors/receipt then atomic latest pointer with receipt SHA256. Incomplete writes never replace a committed checkpoint.',
                'preflightWeightsReusedByActualTraining':False},
    'resources':{'cpuPercent':25,'computeThreads':4,'privateMemoryBytes':2*1024**3,
                 'minimumAvailableBytes':int(3.18*1024**3),'stableRamSeconds':60,
                 'actualWindowsLowMemoryStopsWorker':True,
                 'theoreticalModelGradientOptimizerLowerBoundBytes':training_bytes,
                 'theoreticalCheckpointPayloadBytes':checkpoint_bytes,
                 'plannedCheckpointDiskWithReserveBytes':needed_disk,
                 'actualGpuPeakOrTrainingDurationMeasured':False},
    'preflightReceipt':str(E/'gpu-preflight/preflight.json'),
    'evaluationAudioOnly':str(audio_file),
    'evaluation':{'strictValidationClips':24,'ordinaryChineseWholeLeaves':79,
                  'sourceFramesUnchanged':True,'knownOrdinaryBaselineErrors':461,
                  'speakerAttributedScoringIncluded':False,'factsScoringIncluded':False,
                  'originalFinalBlindHoldoutOpened':False},
    'participantSplit':'Source recordings are disjoint. AMI known participant split previously checked; Chinese true global participant disjointness is still unverified, so no unseen-person/final-sale claim.',
    'files':[item(p) for p in bindings],
    'newNeuralCalls':0,'weightUpdates':0,'trainingStarted':False,
    'actualGpuPreflightPassed':False,'qualityQualified':False,'saleQualified':False,
    'preparationRepair':'First builder attempt stopped before writing a packet because the inference-only source omits role. Freeze-time role selection now uses the already frozen scoring metadata; only explicitly named audio fields enter evaluation-audio-only.json. No validation words enter model workers.',
}
packet_file = C/'packet.json'
packet_file.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
score_files = [S/'score_meeting_acoustic_candidate_20261116.py',
               S/'score_sequential_meetings_20261115.py',S/'score_joint_whole_meetings_20261115.py',
               S/'reference_textgrid_20261104.py',S/'score_ami_bilingual_20261115.py',
               S/'ami_reference_coverage_20261115.py',strict_source/'raw-text-baseline.json',
               strict_source/'scoring-only.json',ordinary_control/'whole-scoring-only.json',ordinary_control/'binding.json']
scoring = {'packet':str(packet_file),'packetSha256':sha(packet_file),
           'strictBaseline':str(strict_source/'raw-text-baseline.json'),
           'strictReferences':str(strict_source/'scoring-only.json'),
           'ordinaryReferences':str(ordinary_control/'whole-scoring-only.json'),
           'ordinaryOriginalLeaves':str(ordinary_control/'binding.json'),
           'trainingRun':str(E/'training'),
           'files':[item(p) for p in score_files],
           'onlyIndependentScorerMayReadReferences':True,'qualityQualified':False}
(C/'scoring-control.json').write_text(json.dumps(scoring,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'packet':str(packet_file),'packetSha256':sha(packet_file),'examples':944,
                  'evaluationLeaves':len(evaluation),'theoreticalTrainingLowerBoundBytes':training_bytes,
                  'diskWithReserveBytes':needed_disk,'actualGpuPreflightPassed':False,'newNeuralCalls':0},ensure_ascii=False))
