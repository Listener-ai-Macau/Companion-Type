from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=Path('work/bilingual_progress.json');d=read(p);j=d['jointArchitecture20261115'];o=d['ownerOvernightRun20261115'];now=datetime.now().astimezone().isoformat()
whole=read(B/'qwen-cpu-chinese-characterization-r2/whole-score.json');alignment=read(B/'cpu-retained-baseline-join-r4/full-score.json');idle=read(E/'cpu-idle-app-r3/resume-r1/result.json')
assert len(whole['meetings'])==2 and all(not r['noMoreRawErrorsThanOriginalNativeBaseline'] for r in whole['meetings']);assert idle['priorAcceptedFirst30sNotRedecoded'] and read(B/'cpu-retained-baseline-join-r4/product-contract.json')['exitCode']==0
d['state']='CPU_COMPONENTS_AND_IDLE_MEMORY_VERIFIED_BILINGUAL_MODEL_QUALITY_REJECTED_NO_DEFAULT_PROMOTION'
o.update(currentState=d['state'],activePid=None,activePidCreatedAt=None,noOwnNeuralProcessActive=True,currentExecutionDevice='cpu',latestObservedAt=now,
 cpuBudgetPermission={'quote':'允许约 25% CPU，继续后台实测','maximumCpuPercent':25,'maximumComputeThreads':4,'privateFamilyGuardBytes':2*1024**3,'actualWindowsLowRamStopRetained':True})
j['qwenCpuPort20261116'].update(state='COMPLETE_CHINESE_WHOLE_SCOPE_WITH_BOTH_REGRESSIONS_UNIVERSAL_REJECTION_RETAINED',
 wholeChineseScore=str(B/'qwen-cpu-chinese-characterization-r2/whole-score.json'),wholeChineseScoreSha256=sha(B/'qwen-cpu-chinese-characterization-r2/whole-score.json'),
 wholeChineseMeetings=whole['meetings'],completedAtObservation=147,fullChineseAdvanceRejected=True,qualityQualified=False,productDefaultChanged=False)
j['cpuNativeForcedAlignerPort20261116']={'state':'NATIVE_CPU_CLASSIFIER_FULL_NORMAL_MEETING_COMPLETE_WITH_BOUNDED_PROCESS_LIFETIME_EXISTING_PRODUCT_JOIN_REUSED',
 'cpuControl':str(E/'cpu-forced-alignment-control-r2/worker-state.json'),'tinyStandardAndMmapExactLogits':True,'fullPlanLeaves':79,'fullActualNonemptyAlignmentCalls':76,
 'recoveryPolicy':str(B/'cpu-retained-baseline-alignment-r2/process-lifetime-policy.json'),'acceptedLeavesReusedAfterMemoryStop':61,'remainingLeavesComputed':18,'recoveryBatchLeaves':[16,2],
 'priorLongLivedProcessPrivateGuardFailure':str(E/'cpu-retained-baseline-alignment-full-r1/run.json'),'privateGuardWasNotRaised':True,'speakerContinuousStateWasNotRestarted':True,
 'score':str(B/'cpu-retained-baseline-join-r4/full-score.json'),'scoreSha256':sha(B/'cpu-retained-baseline-join-r4/full-score.json'),'metrics':alignment['meetings'][0],
 'allModelResultsReusedForFinalJoinFix':True,'establishedProductJoinSourceSha256':sha(R/'model-research/src/companion_local_speaker_document_20261114.py'),
 'sharedRustDocumentContractPassed':True,'allOriginalCharactersAndNewlinesPreserved':True,'sourceAsrWasRetainedPriorGpuNativeResult':True,'notANewAllCpuAsrScore':True,
 'cpuGpuTimestampOutputDiagnostic':str(B/'cpu-retained-baseline-join-r4/cpu-gpu-output-diagnostic.json'),'wordTimeTruthAccuracyMeasured':False,'qualityQualified':False}
j['cpuIdleModelLifetime20261116']={'state':idle['state'],'proof':str(E/'cpu-idle-app-r3/resume-r1/result.json'),'proofSha256':sha(E/'cpu-idle-app-r3/resume-r1/result.json'),
 'idleReleaseSeconds':15,'beforeWorkerRssBytes':idle['idleRelease']['beforeWorkingSetBytes'],'afterWorkerRssBytes':idle['idleWorkerRssBytes'],'afterWorkerPrivateBytes':idle['idleWorkerPrivateBytes'],
 'modelWeightMappingAbsentDuringPause':True,'resumeModelLoads':2,'previousAcceptedFirst30sNotRedecoded':True,'finalAsrTextEqualsProtectedPreviousCpuAppRun':True,
 'allOriginalPcmAndAcceptedResultBytesPreserved':True,'finalizationReusedAllAsrResults':True,'modelWasMossRejectedForRecognitionQuality':True,
 'internalFixture':str(E/'cpu-internal-app-fixture-r5/package.json'),'internalFixtureExpiresAt':'2026-11-16T15:40:00+08:00','usableCustomerReleasePackage':False,
 'installedNativeUiTested':False,'productDefaultChanged':False,'qualityQualified':False}
j['cpuWindowsIntakeFix20261116'].update(state='WINDOWS_ATOMIC_WRITER_READER_AND_LONG_PATH_RELIABILITY_VERIFIED_WITH_ACTUAL_CPU_BACKEND',
 sourceSha256=sha(R/'model-research/src/companion_local_pcm_session_20261114.py'),boundedReadRetryProof=str(E/'windows-reader-retry-r2/result.json'),
 currentIdleResumeProof=str(E/'cpu-idle-app-r3/resume-r1/result.json'),readPolicy='Only Windows sharing/access-denied reads retry up to3s; permanent denial and corrupt JSON still fail. No PCM replay or silent rewriting.')
j['meetingDomainTrainingPreparation20261116'].update(trainingSourceAudit=str(B/'meeting-domain-data-r1/training-source-audit.json'),
 acousticParameterCoverage=str(B/'meeting-domain-data-r1/acoustic-parameter-coverage.json'),previousRejectedLast8QvLoraParameters=262144,
 broaderAcousticAndBridgeParameterCount=317477504,ordinaryCpuAdamLowerBoundBytesExcludingActivations=7250880000,
 noTrainingInCurrentCpu2GiBBudget=True,noNewWeightTrainingThisBatch=True,strictAndBroadExamplesAreNotAdditiveDisjointAudio=True)
receipt=read(D/'protection-r42.json');assert receipt['remoteVerified'];d['sourceProtection'].update(dayResumeSourceCommit=receipt['modelCommit'],dayResumeSourceRemoteVerified=True,dayResumeSourceReceipt=str(D/'protection-r42.json'))
d['next']='本轮模型计算已结束，不扩已失败的MOSS固定30s通用替换、Whisper英语对照、Qwen CPU通用/中文长录音候选，也不提升内存或关闭用户软件。保护下午CPU分批生命周期/暂停释放/Windows读写与原文不回退证据，整理16:00交付。售卖质量门仍OPEN：普通中文原文5.54%、逐人5.80%且个别人9.98%/7.21%，英文及复杂多人/重叠仍大幅未达标，未知与原错误完整计分。下一次模型质量推进应固定原中文Qwen+连续Nemotron基线，使用22公开训练源的944声学样本/190多人轮流索引设计一次更宽声学编码器+桥接适配；不重复已失败的少量LM/末8层Q/V LoRA，不盲跑官方训练入口，先解决实际可用训练算力、中文真实跨会议人员隔离、标签mask/梯度/保存重载和CPU转换核验。当前25%/4线程/2GiB只完成推理验证，不承载约317M参数完整声学训练，且尚未训练新权重；最终L_R003S03C02未打开，默认R8不切换。'
j['nextExecutableGate']=d['next']
d['logResult']+='\n'+now+' 14:29两中文整会147窗/4376.4805s原音全部自然EOS完成，Qwen固定Q8 CPU原字错488/8325=5.8619%、1104/7153=15.4341%，原HF native461=5.5375%、1037=14.4974%，两场回退保留通用拒用，不升级中文默认、不扫量化/上下文网格。CPU计算1812.1854s含复用1窗，私有峰1008672768B、家族常驻1891098624B，系统可用最小2891034624B，真实低RAM门未再触发。CPU分类器首次继承CPP的CLEAN Python无Transformers，零模型调用前失败；改用既定依赖环境+隔离CPU Torch2.11 cp311后，标准/只读mmap随机tiny logits精确相同，真实中英识别原文2控制全部字符保留，原权重1835545960B SHA005682...不变，无HIP/CUDA编译。普通会现有原生GPU Qwen较好原文79叶复用，第一叶32.26825s控制通过；全量长期CPU进程于61叶后内存累积触发原2GiB家族保护，私有家族观测峰2899738624B，未伪称全程在限额内。原失败保留；不改窗口/权重/模型，改无状态对齐器最多16叶一进程，仅补未提交18叶，两批16/2私有峰1316294656/682360832B，原61叶按SHA复用，连续人物状态不重置。初步新拼接误沿旧整词区间规则且未把源换行拼进utterances，逐人1130错/未知369及Rust契约失败保留；定位组合层后，零新增NN，精确复用当前默认R8同SHA77fe80...的onset±60ms+原预测exclusive视图函数，8201单位/96段保全全部文字与换行，原始字错461不变、逐人483/8325=5.8018%与原基线相同、未知8，原多声CPU journal DER3.78248%，共享Rust文档契约通过。该原文来自旧GPU ASR，不能冒充新全CPU ASR成绩；302词区间零长/无效仍留存，onset-only不宣称真词长。CPU/GPU旧同文输出16402时间类中16319相同，解码时间P95差0/最大0.32s，不宣称位级或真时刻准确。另修本任务MOSS CPU后台follow最长3h即使无工作仍常驻模型的问题：15s无可执行识别请求就关闭native模型，保留轻量worker/原PCM/不可变结果，有新工作且原3.18GiB门允许才重载。实际75.25s应用命令schema暂停/恢复证明从1921904640B降到43425792B常驻、私有32264192B、权重映射消失，恢复新worker内加载2次，原已过30s不重算，全部原音/新旧结果SHA保留，最终原文与前次CPU应用测试逐字相同，结束后人物补全复用全部ASR，完成缓存重开0.25s无新增NN。早先5s暂停证明降到41MB后测试器读preview遇Windows瞬时权限冲突；新reader仅重试Windows5/32/33或CRT13最长3s，临时0.266s恢复、永久3s仍失败、坏JSON即时失败且源字节不变。30s暂停测试器原假定恰1结果，实际有1已过draft+1final而断言失败，修测试读取条件后在原session续算后45.25s，不再重跑已过前30s。原失败不删除。内部fixture r5保留旧r3、默认R8不安装/不改，15:40绝对有效窗只是本任务限制，不作为永久可用客户安装包。训练源审计表明旧末8层Q/V r8仅262144参数，已失败不能重名再试；较宽声学+桥接317477504参数普通CPU Adam不含激活下限7250880000B，当前2GiB不支持。官方入口问题只静态核对、旧自定义单样本mask/手动梯度已另有检查，不把旧失败归咎社区报告；新权重训练0，严格190事件已全含广944，不把两套样本小时相加。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':d['state'],'cpuIdleWorkerMiB':idle['idleWorkerRssBytes']/1024**2,'retainedBaselinePersonErrorRate':alignment['meetings'][0]['personTextFixedOriginalActivityIdentity']['errorRate'],'qualityQualified':False},ensure_ascii=False))
