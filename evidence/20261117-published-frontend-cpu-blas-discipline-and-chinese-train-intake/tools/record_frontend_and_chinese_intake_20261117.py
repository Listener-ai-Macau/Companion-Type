"""Record source changes and bounded primary-data intake in the existing model task."""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';J=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
at=datetime.now().astimezone().isoformat(timespec='seconds')
front=J/'language-specific-adaptation-r1/published-frontend-proof-20261117.json';F=read(front)
fix=J/'context-activity-r1/cpu-vad-explicit-blas-pin-20261117.json';B=read(fix)
A=E/'meeting-domain-data-r1/alimeeting-intake-audit-r1';profile=read(A/'nonoverlap-metadata-profile.json');head=read(A/'official-train-prefix-riff-r2.json')
assert F['realTrainingCases']==10 and F['allFeaturesFiniteAndMaskedPaddingZero']
assert not F['actualGpuBackwardMaximumShapeCheckpointProven'] and not B['actualCpuVADInferenceRevalidated']
assert profile['unaugmentedUtterances']==186364 and profile['speedTransformedCutsExcluded']==372728
assert profile['candidateWholeUtterances2To30SecondsWithoutAnyDifferentSpeakerOverlap']==19388
assert not profile['chineseTrainingAdmitted'] and head['conversionMetadataMatch'][0]['headerFramesMatchExactly']
corpus={'at':at,'state':'ALIMEETING_TRAIN_RAW_METADATA_PROFILED_OFFICIAL_FIRST_HEADER_MATCHED_NOT_TRAINING_READY',
    'metadataSource':read(A/'train-manifest-selection.json'),
    'manifestSha256':profile['manifestSha256'],'manifestBytes':39545263,
    'thirdPartyConvertedTrainSessions':209,'publisherReportsTrainSessions':212,
    'thirdPartyNormalizedSpeakerIds':452,'publisherReportsTrainPeople':456,
    'rawUnaugmentedUtterances':186364,'speedAugmentedCutsExcluded':372728,
    'candidateNonoverlapWholeUtterances2To30Seconds':19388,
    'candidateNonoverlapMetadataSeconds':profile['candidateSecondsWithoutSpeedPerturbation'],
    'candidateHoursAreNotAcquiredOrVerifiedAudioHours':True,'candidateSpeakerIds':393,
    'cachedFeaturesRejectedForThisTask':{'channels':8,'featureDimensions':80,
        'reason':'Companion is single-mic; these cached80mel/multichannel/speedperturbed features are not raw source PCM or the current model frontend.'},
    'officialPrefix':{'bytes':1048576,'url':read(A/'official-train-prefix-inspection.json')['url'],
        'sha256':head['prefixSha256'],'header':head['entries'][-1]['waveHeader'],
        'conversionMetadataMatch':head['conversionMetadataMatch'],
        'format':'WAVE_FORMAT_EXTENSIBLE PCM16,8channels,16k. Original Python3.11 wave failure preserved; RIFF/GUID inspection reused cached bytes, no retry/download enlargement.'},
    'newAudioExposure':'Only bounded original public Train prefix; containspartial PCM. No evaluation/test or reserved AISHELL payload read.',
    'primarySources':read(A/'primary-source-context.json')['sources'],
    'trainingReady':False,'remaining':['Independent original TextGrid/transcript checks; a matching WAV header is not a full source-content proof.',
        'Exact first-mic PCM extraction within original12GiB new-data and50GiB free-space limits; no full73.24GiB archive download.',
        'Participant isolation for the actual selected training/validation contract. AliMeeting authors assert their own Train/Eval separation; originalAISHELL cross-corpus identity remains unproven.'],
    'originalChineseTrainingGateChanged':False,'originalMetricsOrHoldoutChanged':False,
    'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False}
target=J/'meeting-domain-data-r1/alimeeting-train-intake-20261117.json'
target.write_text(json.dumps(corpus,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
correction={'at':at,'state':'EARLY_FRONTEND_FAILURE_LOCALIZATION_CORRECTION',
    'initialReceipt':str(E/'language-specific-adaptation-r1/published-frontend-r1/terminal-import-failure.json'),
    'correction':'Initial failure had only an initial-state snapshot and OpenBLAS stderr. Its import-failure label did not establish the exact failing stage. The separate operation trace later located CPUbmm on the same frontend profile; do not retroactively claim the initial run had a captured operator.',
    'confirmedCauseForTracedRun':'New audit omitted existing explicitROCmBLAS binding; environment/Torch thread limits left thatDLL at16. ExistingGPUtrainingworker already binds it. Reusing existing helper16→1 passed all10actual input checks under unchanged2GiB.'}
(E/'language-specific-adaptation-r1/frontend-failure-localization-correction.json').write_text(json.dumps(correction,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['currentOwnedNeuralWorker']=None
o['languageSpecificAdaptation20261116']['publishedSignalFrontendProof']={'receipt':str(front),'state':F['state'],
    'actualGpuBackwardMaximumShapeCheckpointProven':False}
o['cpuVadThreadDiscipline20261117']={'receipt':str(fix),'state':B['state'],'actualInferenceRevalidated':False}
o['chineseAlternativeTrainIntake20261117']={'receipt':str(target),'state':corpus['state'],'trainingReady':False}
o['goalContinuationAudit20261117']={'at':at,'previousTurnClassification':'progress',
    'basis':'Original twofullEnglish DSP results rejected fixedWebRTC; explicit780M path/failure closed and privately protectedr65. This turn realpublished frontend10cases completed, CPUVAD source thread binding fixed, distinct publicChinese training intake profiled. No accuracy gain claimed.'}
x['at']=at;x['state']=o['state']='PUBLISHED_FRONTEND_VERIFIED_CPU_VAD_BLAS_FIXED_ALIMEETING_INTAKE_NOT_ADMITTED'
x['next']='沿原英文1828片/457更新固定一轮继续：官方AutoProcessor已实际核最大joint/最长和8种长度边界共10个训练原片，数值有限/末padding0/形状吻合60588jointcells；峰679MiB、0模型0训练，GPU实际梯度/最大形状/检查点仍待合格独显窗口。新检查脚本漏用既有ROCmCPU_BLAS显式限线程导致bmm原生退出，现复用16→1通过；GPU训练入口本已有此调用。CPU Silero也补同一绑定和冻结依赖校验，旧源保留，新VAD未重跑/无新成绩。中文AliMeeting原始训练元数据已去掉372728变速副本，209场452ID里可列19388整段非重叠2–30s候选约20.3h；仅元数据，不能称已获可训练音频。官方Train首1MiB显示8ch/16k/PCM16扩展WAV，首文件帧数与转换清单精确匹配，原TextGrid和完整单麦PCM/原AISHELL人物隔离还未核，不开中文训练、不下载整73GiB档；下一优先获取可独立核的原训练标注和预算内单麦原音。780M路径仍待原资源温度准入合格，不CPU/核显训练。原95/98、逐人/事实/最终盲测门不改。'
x['logResult']+='\n\n'+at+'｜续作分类：上一轮WebRTC两整场实测淘汰与780M失败闭合/源码r65属于实质进展。白天本轮没有重复热停模型。英文训练链路检查：原目标token/blank/TDT均值归约与发布前端长度策略对照一致；只跑官方AutoProcessor信号处理，最大joint478640采样/161子词实际(1,2992,128)、2991有效帧→374编码帧/60588cells，最长479680采样→375帧，以及8种长度边界共10原片全部有限/末padding为0。新检查脚本最初两次OpenBLAS退出，另一次逐算子追踪确认CPU aten.bmm(128x257乘257x2992)，OMP/Torch1线程不约束ROCm独立CPU BLAS；这是探针遗漏已有pin_rocm_blas，不是新发现GPU训练入口缺失。复用原精确DLL接口16→1后官方原处理器实际通过，峰711929856B(<2GiB)、0神经模型/0GPU/0优化器/0权重更新；原初“导入失败”标签定位不足已另留纠正说明和原失败。发现CPU Silero同样漏显式BLAS绑定，已补精确DLL/helper冻结校验及模型加载前1线程，旧源1eb03b保留；该CPU VAD新源仅编译/控制顺序核查，温度/资源/权重默认不变，未重跑神经推理，不报质量或重启修复。另核中文新来源：AliMeeting作者明确自身Train/Eval不同人，官方212场456人；第三方原始train清单39.55MB经固定revision/LFS_SHA核验，实际209场452规范化ID/559092条，其中372728为0.9/1.1变速副本剔除，原186364条里整段2–30s且无任何其他人重叠19388条73062.23s(20.30h)/393ID，仅候选元数据不是已取得原音。8通道80mel缓存不用作单麦模型输入；固定上限仅从官方Train档取得首1MiB(HTTP206)，Python3.11wave不识65534的失败保留，本地RIFF/PCM_GUID解析确认8ch16k16bit，R0003_M0046_MS002原头32734096帧与清单精确一致，不等于完整音频或原TextGrid核验。未下载78.6GB全档、未读AliEval/Test或保留AISHELL最终资料；原中文跨库人物隔离仍未证，不开训。收据'+str(front)+'、'+str(fix)+'、'+str(target)+'。本轮无新ASR/DER质量成绩、默认产品/原验收门不变。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'frontendReceipt':str(front),'cpuVadFix':str(fix),'chineseIntake':str(target),
    'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False},ensure_ascii=False))
