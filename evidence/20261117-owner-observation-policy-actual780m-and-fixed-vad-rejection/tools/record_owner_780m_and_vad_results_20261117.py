"""Close actual 780M inference and reject the fixed VAD candidate at its old gates."""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';J=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
G=J/'igpu-native8-r3';V=J/'context-activity-r1/silero-owner-observe-r4'
GE=E/'igpu-native8-r3';VE=E/'context-activity-r1/silero-owner-observe-r4/run-default'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
control=read(GE/'cpu61-vs-780m.json');full=read(GE/'ES2003b-fixed-mapping-activity-score.json')
run=read(VE/'completed.json');scores=[read(VE/(m+'-score.json')) for m in ['ES2003b','EN2002a']]
assert control['state']=='PASS_780M_FP16_CONTROL_RUNTIME_ONLY'
assert full['sameFrozenWeights'] and full['originalWholeMappingForBothConditions']
assert run['newNeuralCalls']==132955 and run['parameterUpdates']==0
assert not any(s['advanceToSecondEnglishSource'] for s in scores)
assert all(not s['originalDerTenPercentGate'] for s in scores)
assert read(E/'system-restart-20261116-2315/igpu-native8-owner-observe-thermal-r3/completed.json')['ownedStopRequested']
at=datetime.now().astimezone().isoformat(timespec='seconds')
report={'at':at,'state':'ACTUAL_780M_CONTROL_AND_WHOLE_MEETING_PASS_RUNTIME_FIXED_SILERO_REJECTED_QUALITY',
    'ownerCpuTemperaturePolicy':{'quote':'这个为什么会有这个软件门栏呢？没有必要有这个东西啊。',
        'mode':'observe-only','maximumStartCelsius':None,'stopCelsius':None,
        'scope':'Current Companion model work. CPU temperature no longer starts/stops inference; telemetry failures are diagnostic only.',
        'hardwareOsThermalControlsChanged':False,'originalMemoryCpuLowRamAndTimeGuardsRetained':True},
    'rebootInvestigation':{'ownerReport':'Games/3DMark high load stable; repeated restarts associated with model work and USB4 externalGPU dock.',
        'priority':'Compute runtime/driver/USB4 eGPU path; preserve evidence and change one execution condition at a time.',
        'cpuThermalCauseProven':False,'gpuDriverOrVramCauseProven':False,
        'existingGpuRebootsWereInferenceNotWeightTraining':True,
        'driverOrTdrRegistrySettingsChanged':False,
        'primaryMechanismReference':'https://learn.microsoft.com/en-us/windows-hardware/drivers/display/timeout-detection-and-recovery',
        'successful780mVulkanTestDoesNotQualifyExternal6800xtHipOrUsb4Path':True},
    'integratedGpu':{'device':control['selectedNativeDevice'],'backend':'Vulkan','model':'PinnedNative8FP16 speaker activity',
        'weightsSha256':read(G/'protocol.json')['modelSha256'],
        'controlAudioSeconds':61,'controlPosteriorValues':control['comparedPosteriorValues'],
        'maximumPosteriorDifference':control['maximumAbsoluteError'],'meanPosteriorDifference':control['meanAbsoluteError'],
        'thresholdActivityDisagreements':control['thresholdActivityDisagreements'],
        'thresholdDisagreementFraction':control['thresholdActivityDisagreementFraction'],
        'sameFrozenRuntimeTolerancePassed':True,'bitwiseEquivalent':False,
        'controlModelCreateAndInferSeconds':control['nativeCreateAndFullInferenceSeconds'],
        'controlPeakPrivateBytes':control['jobPeakPrivateCommitBytes'],
        'fullMeeting':'ES2003b','fullAudioSeconds':full['audioSeconds'],'allOriginalSamples':full['allOriginalFrames'],
        'fullModelCreateAndInferSeconds':full['nativeCreateAndFullInferenceSeconds'],
        'fullPeakPrivateBytes':full['jobPeakPrivateCommitBytes'],
        'baselineDer':full['originalNative8Baseline']['DER'],'integratedGpuDerSameFixedMapping':full['native780mUsingSameWholeSourceIdentity']['DER'],
        'neuralPushesControl':read(G/'results/cpu-native8-control61/completed-state.json')['newNeuralPushes'],
        'neuralPushesWhole':read(G/'results/ES2003b/completed-state.json')['newNeuralPushes'],
        'wholeSourceTimingIsObservedNotCrossBackendSpeedClaim':True,
        'newTextAsrOrOverallProductAccuracyProven':False},
    'fixedVad':{'model':'Original officialSilero defaultweights;CPU inference1thread and explicitBLAS1thread',
        'protocol':str(V/'protocol.json'),'protocolSha256':sha(V/'protocol.json'),'run':str(VE),
        'sourceHours':(2109.813375+2142.709375)/3600,'newNeuralCalls':run['newNeuralCalls'],
        'privatePeakBytes':run['limits']['jobPeakPrivateCommitBytes'],'cpuPercentMaximum':5,
        'sources':[{'meeting':s['meeting'],'baselineDer':s['originalRawMultiVoice']['DER'],
            'combinedDer':s['combinedWithOriginalFixedIdentity']['DER'],'relativeDerReduction':s['relativeDerReduction'],
            'wholeSourceTwentyPercentAdmissionPassed':s['advanceToSecondEnglishSource'],
            'originalTenPercentDerPassed':s['originalDerTenPercentGate']} for s in scores],
        'decision':'REJECT_FIXED_SILERO_PRESENCE_UNION_NO_GRID',
        'directionDecision':'DefaultSilero and earlier fixedWebRTC both provide only small gains; stop replacing VAD or sweeping thresholds as the main diarization strategy. More reliable speaker activity/identity remains required.',
        'originalNative8ActiveIntervalsWordsTimesAndScoringMappingChanged':False},
    'resources':{'cpuPercentMaximum':5,'modelPrivateCommitMaximumBytes':2147483648,
        'minimumAvailableRamBytes':3414499000,'originalLowRamStopsRetained':True,
        'parameterUpdates':0,'cpuOrIntegratedGpuTraining':False,'ownedNeuralAndLoggerJobsTerminal':True},
    'qualityQualified':False,'saleQualified':False,'rawWord95Floor98TargetChanged':False,
    'productDefaultChanged':False,'finalHoldoutOpened':False,
    'next':'Use the demonstrated780M path for model inference/comparison. Inspect whether the already selected English adaptation base has an exact nativeVulkan ASR execution path before spending training time; explicit model only, no new default download, no rejectedQwen quantization rerun or model/threshold grid. DedicatedGPU training remains a separate evening activity.'}
target=J/'context-activity-r1/owner-780m-and-fixed-vad-results-20261117.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['owner780mAndFixedVadResults20261117']={'state':report['state'],'receipt':str(target),
    'actualIntegratedGpuInference':True,'wholeOriginalMeetingCompleted':True,
    'fixedSileroRejected':True,'newAsrWordAccuracyMeasured':False,'qualityQualified':False}
o['integratedGpuAuthorization20261117'].update(state='ACTUAL_780M_INFERENCE_AND_COMPLETE_MEETING_PROVEN',
    actualNativeInference=True,newNeuralPushes=73,parameterUpdates=0,receipt=str(target),ownedThermalLoggerClosed=True)
o['currentOwnedNeuralWorker']=None;o['currentWorkerState']='NO_OWNED_NEURAL_DATA_OR_TEMPERATURE_WORKER'
o['requiredModelExecutionDependency20261117']['state']='OWNER_RESUMED_780M_PATH_ACTUALLY_RUNNING_UNBLOCKED'
o['requiredModelExecutionDependency20261117']['wholeTaskRequiresDiscreteGpu']=False
o['ownerTimeValueReview20261117']['stopReplacingGenericVad']=True
x['at']=at;o['state']=x['state']=report['state'];x['next']=report['next']
x['logResult']+='\n\n'+at+'｜本批核显真实交付与固定VAD结论：CPU85/95临时软件中止门槛已依Owner改观测，原RAM/CPU/时限及不CPU核显训练保持。61秒固定控制在780M/Vulkan明确选中后完成3push/6101帧，48808后验最大差0.016933918/均差0.000102672、活动13处分歧，全过原容差，非逐位等价。完整ES2003b2109.813375s/33757014原样本也已完成70push/210982帧，创建+推理14.7195591s，全worker时间另含60秒RAM稳定/加载校验，不把它和旧CPU整worker混比提速；峰1891921920B<2GiB。沿同一原整会人物映射/零collar/含重叠，DER26.0181%→25.9558%，只是后端执行近似，不称质量改善合格或词识别已验。随后已选定的Silero原默认模型在CPU1线程/显式BLAS1线程完成两整源4252.52275s、132955窗口神经调用，峰853729280B，0更新。原固定融合/映射评分ES26.0181→24.4425%（相对6.0558%）、EN31.0766→28.0680%（相对9.6813%），均不过原每源20%改善门及10%DER门；明确淘汰，不再换VAD/调阈值。模型/音频原文/参考/语音时间未改，未打开最终L。核显完整推理及CPU小检测器均已结束；自有只读loggerPID25044/创建1794896961.4553976核身份后stop并终态回收，范围67.00001–96.375C不证明历史重启根因。Owner游戏/3DMark稳定而显卡坞模型重启的报告承接为优先查计算栈/驱动/USB4路径，未据其认定具体驱动或CPU绝不热重启，也不改驱动/TDR/系统温控。初次评分误用全局Python缺praatio，未写成绩/未重跑模型；改用既有clean scoring runtime后原门核验通过。保存本批，下一步只针对已选英语底座核实原生Vulkan ASR可执行性，避免再拿已拒Qwen量化或通用VAD凑进展。收据'+str(target)+'。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=[]
def take(p,name):
    p=Path(p);assert p.is_file() and p.stat().st_size<32*1024**2
    assert p.suffix.lower() not in ('.wav','.gguf','.jit','.safetensors')
    files.append({'source':str(p),'name':name})
for name in ['prepare_owner_resumed_780m_20261117.py','record_780m_owner_policy_and_run_20261117.py',
    'prepare_owner_observed_silero_20261117.py','score_780m_full_activity_20261117.py','record_owner_780m_and_vad_results_20261117.py']:
    take(Path('work')/name,'tools/'+name)
take(target,'result.json')
for name in ['igpu-native8-r2','igpu-native8-r3']:
    for p in (J/name).rglob('*'):
        if p.is_file():take(p,name+'/control/'+p.relative_to(J/name).as_posix())
    for p in (E/name).rglob('*'):
        if p.is_file():take(p,name+'/run/'+p.relative_to(E/name).as_posix())
for p in V.iterdir():
    if p.is_file():take(p,'silero/control/'+p.name)
for p in VE.rglob('*'):
    if p.is_file():take(p,'silero/run/'+p.relative_to(VE).as_posix())
for name in ['igpu-native8-owner-resume-thermal-r2','igpu-native8-owner-observe-thermal-r3']:
    b=E/'system-restart-20261116-2315'/name
    for p in b.iterdir():
        if p.is_file():take(p,'thermal/'+name+'/'+p.name)
config={'revision':69,'evidenceDirectory':'evidence/20261117-owner-observation-policy-actual780m-and-fixed-vad-rejection',
    'sources':['src/model_thermal_guard_20261117.py','src/native8_780m_inference_20261117.py'],
    'closedDirectories':[],'files':files,
    'commitMessage':'Apply owner CPU telemetry policy and prove780M whole inference; reject fixed defaultSilero union',
    'claims':{'state':report['state'],'actual780mControlAndWholeInference':True,'sileroCandidateRejected':True,
        'cpuTemperatureMode':'owner-authorized-observe-only','parameterUpdates':0,'cpuOrIntegratedGpuTraining':False,
        'originalMemoryCpuAndQualityGatesRetained':True,'rawAudioModelWeightsOrCredentialsIncluded':False,
        'qualityQualified':False,'saleQualified':False,'systemDriverTdrOrHardwareThermalSettingsChanged':False}}
Path('work/checkpoint_owner_780m_r69.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'receipt':str(target),'protectionFiles':len(files),'actual780m':True,
    'sileroGatePassed':False,'parameterUpdates':0,'allOwnedJobsTerminal':True},ensure_ascii=False))
