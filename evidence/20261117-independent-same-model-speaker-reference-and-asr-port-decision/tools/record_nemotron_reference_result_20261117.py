"""Record the closed independent implementation control, not quality progress."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
run=E/'native8-reference-fidelity-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result=read(run/'reference/completed.json');weights=read(run/'official-weight-value-comparison-r2.json')
assert result['state']=='COMPLETE_INDEPENDENT_DIARIZER_REFERENCE_FIDELITY_CONTROL'
assert len(result['cases'])==2 and result['newEncoderLayerCalls']==186
assert result['modelParameterDigestBefore']==result['modelParameterDigestAfter']
assert not result['gpuInitialized'] and result['parameterUpdates']==0
assert not result['diagnosisRequiredBeforeDiarizerTraining']
assert weights['allHfTensorValuesMatchNemo'] and weights['hfTensors']==417
assert result['limits']['jobPeakPrivateCommitBytes']<2147483648
pid=result['pid'];owned_live=psutil.pid_exists(pid) and abs(psutil.Process(pid).create_time()-1794901876.9495533)<.01
assert not owned_live,'Original reference worker must be terminal before recording completion'
P=read(run/'protocol.json');at=datetime.now().astimezone().isoformat(timespec='seconds')
prior_annotations=[]
for name in ['reference-annotation-audit-r1','reference-annotation-audit-en2002a-r1']:
    p=D/name/'comparison.json';a=read(p)
    prior_annotations.append({'receipt':str(p),'sha256':sha(p),'meeting':a['meeting'],
        'originalDer':a['originalReferenceDer'],'alternateReferenceDiagnosticDer':a['externalMfaDiagnosticDer'],
        'historicalConclusion':a['state'],'qualificationChanged':False})
report={'at':at,'state':'INDEPENDENT_SAME_MODEL_DIARIZER_REFERENCE_CONTROL_CLOSE_NO_NEW_QUALITY_GAIN',
 'reference':{'repo':P['repo'],'revision':P['revision'],'weightsSha256':P['files']['model.safetensors']['sha256'],
    'implementation':result['modelClass'],'dtype':'float32','device':'cpu','parameters':result['parameters'],
    'originalNemoTensorValueCheck':str(run/'official-weight-value-comparison-r2.json'),
    'activeHfTensors':417,'exactSourceValueMatchFraction':1.0,
    'tensorCheckScope':'Exact per-tensor shape/value multiset, each original tensor/split used once; official contiguousQKV row split. Renaming and dropped training-only heads follow the cited public conversion source. Not a byte-identical serialization claim.'},
 'native':{'implementation':'Pinned NeMo-Speech.cpp v0.3.0, existing780M Vulkan FP16 outputs',
    'protocol':str(J/'igpu-native8-r3/protocol.json'),'originalOutputUnchanged':True},
 'cases':result['cases'],'resources':{'encoderLayerCalls':186,'parameterUpdates':0,'gpuInitialized':False,
    'privatePeakBytes':result['limits']['jobPeakPrivateCommitBytes'],'cpuPercentMaximum':25,'torchThreads':4,'blasThreads':1,
    'wholeWorkerSeconds':result['wholeWorkerSeconds'],'cpuTemperatureMode':'owner-authorized-observe-only',
    'originalWorkerPid':pid,'originalWorkerCreatedAt':1794901876.9495533,'ownedWorkerTerminal':True},
 'decision':'No material activity/mean-posterior discrepancy by the fixed diagnostic rule on these two original61s controls. Retain the current780M speaker component; stop this implementation-diagnosis branch rather than rewrite the engine or train the diarizer to compensate for an unproved adapter fault.',
 'limitations':['Only54.4s of each61s input was compared, preserving two full27.2s chunks with identical available future context; tail frames excluded prospectively.',
    'ReferenceF32 and nativeFP16 are not bitwise equal. English maximum individual posterior difference0.06662646 is retained, despite the small mean and activity disagreement.',
    'The prior CPU/780M same-precision maximum-difference tolerance is not silently reused for this different-precision independent-implementation diagnostic.',
    'No new word-error, person-text, facts, full-meeting/final quality or independent-room acceptance was measured.',
    'This control does not establish long-duration numerical equivalence, nativeTorch/HIP external6800XT stability, or CPU/iGPU training permission.'],
 'existingReferenceProtocolAuditNotNewWork':prior_annotations,
 'referenceProtocolDecision':'Existing Nov15 audit already explains much of the raw English missed-activity difference. Do not call reference-only time proven acoustic silence, train to annotation disagreement, or reopen that audit as new progress. Original references and acceptance gates remain unchanged.',
 'next':'The decisive quality step remains the single frozen1828-example457-update English specialist adaptation and unchanged independent paired/whole-source validation, after actual dedicatedGPU execution admission. No CPU/iGPU training.780M inference is available for evidence-justified component use; no full-task dependency on discreteGPU and no further unchanged control rerun.',
 'rawWord95Floor98TargetChanged':False,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,
 'finalHoldoutOpened':False,'systemDriverTdrPowerOrThermalControlsChanged':False}
target=J/'language-specific-adaptation-r1/native8-independent-reference-control-20261117.json';assert not target.exists();write(target,report)
path=Path('work/bilingual_progress.json');x=read(path);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['nativeSpeakerIndependentReference20261117']={'state':report['state'],'receipt':str(target),
    'newEncoderLayerCalls':186,'parameterUpdates':0,'activeTensorValuesExactlyMatched':417,
    'materialActivityDiscrepancyObserved':False,'accuracyImproved':False,'qualityQualified':False}
o['currentOwnedNeuralWorker']=None;o['currentWorkerState']='NO_OWNED_NEURAL_DATA_TEMPERATURE_OR_BUILD_WORKER'
audit=o['goalContinuationAudit20261117']
audit['latestActualContinuation']={'at':at,'previousTurnClassification':'progress',
    'previousTurnEvidence':str(J/'language-specific-adaptation-r1/native-vulkan-source-audit-20261117.json'),
    'thisTurnClassification':'progress','thisTurnEvidence':str(target),
    'reason':'Actual independent same-checkpoint inference and exact source tensor check close a plausible runtime-fidelity branch; no accuracy gain claimed.'}
x['at']=at;x['state']=o['state']=report['state'];x['next']=report['next']
x['logResult']+='\n\n'+at+'｜本轮按Owner要求只做能改变下一动作的模型证据：发现既有Native8说话人组件尚缺独立原生实现对照，以同一已固定Nemotron修订的官方Transformers序列化做中文/英文各61秒CPU推理，非换模型/训练/阈值网格。原CPU25%/4torch线程/BLAS1、2GiB私有/真实低RAM/60秒RAM准入保持，CPU温度仍仅观察。真实186次encoder层调用、0更新、未初始化GPU，峰1161756672B。只比每源前5440帧两完整27.2秒块，前瞻/尾部处理范围预先冻结：中文43520后验均差0.0001006673/最大0.01700538，活动13值分歧0.029871%；英文均差0.0002772651/最大0.06662646，活动8值分歧0.018382%。不是逐位一致，也未偷用旧同精度max门；按本次预先诊断规则无实质偏差，因此结束这条引擎改写分支，保留核显组件，不据此声称词准或全会质量已提升。417个HF张量在官方31层QKV拆分后与原.nemo值全部精确一致；初次未拆分只匹配75.43%元素的原核对收据/源代码保留，经官方转换源码明确布局后仅补序列化核对，无重跑神经。复读已有Nov15双英文参考协议审计，确认原活动漏检不能全当真实丢语音；未新改参考/成绩/验收，也不重做旧审计凑进展。推理PID9008/创建1794901876.9495533已终态回收，全部自有模型作业结束。下一决定性准确率工作保持固定一次英语专用底座适配+独立整会逐人验证，CPU/核显不训练；不再反复跑相同控制或把底层兼容当准确率。收据'+str(target)+'。'
write(path,x)
files=[]
def take(p,name):
    p=Path(p);assert p.is_file() and p.stat().st_size<32*1024**2
    assert p.suffix.lower() not in ['.wav','.gguf','.safetensors','.nemo','.ckpt']
    files.append({'source':str(p),'name':name})
for name in ['record_native_vulkan_audit_20261117.py','native_vulkan_primary_refs_20261117.json',
    'inspect_pinned_native_asr_sources_20261117.py','prepare_nemotron_reference_control_20261117.py',
    'verify_nemotron_reference_weights_20261117.py','record_nemotron_reference_result_20261117.py']:
    take(Path('work')/name,'tools/'+name)
take(target,'independent-speaker-reference-result.json')
take(J/'language-specific-adaptation-r1/native-vulkan-source-audit-20261117.json','english-native-asr-source-audit.json')
for p in (E/'language-specific-adaptation-r1/native-vulkan-port-r1').glob('*.json'):take(p,'english-source-metadata/'+p.name)
for p in run.rglob('*'):
    if p.is_file() and p.name!='input-features.npy' and p.suffix.lower() in ['.json','.npy','.py']:take(p,'speaker-reference/'+p.relative_to(run).as_posix())
for name in ['config.json','processor_config.json']:take(Path(P['modelRoot'])/name,'published-model-metadata/'+name)
config={'revision':70,'evidenceDirectory':'evidence/20261117-independent-same-model-speaker-reference-and-asr-port-decision',
    'sources':['src/nemotron_reference_control_20261117.py'],'closedDirectories':[],'files':files,
    'commitMessage':'Verify same-model diarizer reference and close costly nativeASR port branch before quality admission',
    'claims':{'state':report['state'],'actualReferenceEncoderLayerCalls':186,'parameterUpdates':0,
        'samePublishedCheckpointSourceValueCheck':True,'qualityImproved':False,'qualityQualified':False,'saleQualified':False,
        'noCpuOrIntegratedGpuTraining':True,'rawAudioModelWeightsOrCredentialsIncluded':False}}
write(Path('work/checkpoint_reference_fidelity_r70.json'),config)
print(json.dumps({'receipt':str(target),'files':len(files),'nativeBranchClosed':True,'newWordAccuracyScore':False,'originalWorkerTerminal':True},ensure_ascii=False))
