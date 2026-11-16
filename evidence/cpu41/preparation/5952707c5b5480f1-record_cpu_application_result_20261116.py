from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];j=d['jointArchitecture20261115'];now=datetime.now().astimezone().isoformat()
cpu=read(E/'cpu-native8-r2/run.json');score=read(B/'all-cpu-full4-composition-r1/full-score.json');english=read(B/'english-asr-specialist-r1/score.json');app=read(E/'cpu-app-schema-test-r3/result.json')
assert cpu['state']=='COMPLETE_CPU_ONLY_NATIVE8_FULL4_NOT_QUALIFIED' and not english['advanceToWholeEnglish'] and len(app['cases'])==2
d['state']='CPU_LOCAL_BACKEND_INTEGRATION_PASSED_BILINGUAL_MEETING_QUALITY_OPEN'
o.update(currentState=d['state'],activePid=None,activePidCreatedAt=None,noOwnNeuralProcessActive=True,currentExecutionDevice='cpu',latestObservedAt=now,
 cpuSpeakerRuntimeState=cpu['state'],cpuSpeakerFull4Result=cpu,allCpuFull4Score=str(B/'all-cpu-full4-composition-r1/full-score.json'),allCpuFull4ScoreSha256=sha(B/'all-cpu-full4-composition-r1/full-score.json'),
 cpuApplicationBackendResult={'file':str(E/'cpu-app-schema-test-r3/result.json'),'sha256':sha(E/'cpu-app-schema-test-r3/result.json'),**app})
j['cpuNoDiscreteProductCandidate20261116'].update(state='ACTUAL_CPU_COMMAND_BACKEND_SCHEMAS_PASSED_MODEL_QUALITY_REJECTED_NO_DEFAULT_PROMOTION',
 actualAppEntryExecuted=True,actualEntryScope='Versioned command backend schemas on paced public file input; installed native UI/card/phone not tested by this batch.',
 internalFixture=str(E/'cpu-internal-app-fixture-r3/package.json'),defaultPackageAssemblyDeferred=True,actualBackendResult=app)
j['englishSpecialistContrast20261116'].update(state=english['state'],neuralCalls=12,result=str(B/'english-asr-specialist-r1/score.json'),aggregate=english['aggregate'],advanceToWholeEnglish=False)
j['cpuWindowsIntakeFix20261116']={'state':'ACTUAL_WIN_READER_CONFLICT_AND_DEEP_CACHE_PATH_FIXED_BOTH_APP_BACKENDS_PASSED',
 'failureRoots':[str(E/'cpu-pcm-dualroute-r1'),str(E/'cpu-app-schema-test-r1'),str(E/'cpu-app-schema-test-r2')],
 'sourceSha256':sha(R/'model-research/src/companion_local_pcm_session_20261114.py'),
 'fixes':['Atomic JSON commits wait bounded3s for Windows delete-sharing conflicts; PCM remains durable.','Only intake lock acquisition waits bounded3s; gaps/changed replay/EOS conflicts still fail.','Short unique temporary filenames and canonical extended local paths support deep content-addressed app caches, without registry/system policy changes.'],
 'actualCpuTransportProof':str(E/'cpu-pcm-dualroute-r2/result.json'),'actualCpuApplicationProof':str(E/'cpu-app-schema-test-r3/result.json'),
 'installedDefaultChanged':False,'qualityQualified':False}
j['meetingDomainTrainingPreparation20261116']={'state':'COLLECTING_24_PUBLIC_TRAINING_ONLY_FARFIELD_MEETINGS_NO_TRAINING','control':str(B/'meeting-domain-data-r1'),
 'run':str(E/'meeting-domain-data-r1/run.json'),'trainingStarted':False,'parameterUpdates':0,'plan':str(B/'meeting-domain-data-r1/plan.json'),
 'chineseGlobalPersonDisjointnessVerified':False,'reservedFinalHoldoutOpened':False,'qualityQualified':False}
receipt=read(D/'protection-r40.json');assert receipt['remoteVerified'];d['sourceProtection'].update(dayResumeSourceCommit=receipt['modelCommit'],dayResumeSourceRemoteVerified=True,dayResumeSourceReceipt=str(D/'protection-r40.json'))
d['next']='CPU链路和4整会声纹已实跑通过，质量继续开放：原中文Qwen保持，MOSS30s通用替换及Whisper固定英语对照均拒用，不扩失败参数网格/不切日用默认。完成本批应用入口证据保护与训练数据准备：24个公开训练会议按地点/大小房间覆盖，原验证/四整会/最终L_R003排除；英文全局参与者与原验证不交叉，中文跨会议全局人名尚无证明，保留未知不冒充。GPU已由Owner拔下，本批CPU验证不等于已训练新权重；先完成数据/标签/官方训练格式与可恢复交付，15:40模型截止、16:00交付原始结果与真实剩余。'
j['nextExecutableGate']=d['next']
d['logResult']+='\n'+now+' CPU完整人物日志4场8629.00325s原音全部从源起点连续推理结束，复用既过61s控制；计算380.845s，峰私有1537232896B，原25%/4线程/2GiB与低RAM门保持。和原GPU日志的主raw多声DER分别26.0329/3.7825/31.1979/15.8896%，只小幅数值变化；同290份ASR原文保持，人物ER19.6333/13.2613/30.5031/25.3180%，未合格。Whisper Q8固定12英文709词195错(27.50%)，MOSS124(17.49%)、原Qwen141(19.89%)，按事先99错门拒绝，不扩整会/调参；195中178其他词汇、17语气词，不能靠删语气词满足指标。后台真CPU75.25s增量/离线联测发现Windows状态JSON被读时替换WinError5，已确定复现/3s有界提交与短锁等待修源头；长缓存临时262字符和后续声纹目录超260也已重现，短tmp+本地扩展路径修复，实际303字符路径读写/普通路径等价通过，无系统策略变更。原失败保留。应用命令schema实跑中英各75.25s、完整离线ASR+连续声纹、录中预览到人物日志、复用全部原草稿结果和再次打开均通过；首次录中文字16.25/15.922s，原音75.25s结束，已完成草稿后人物补全4.516s，再开缓存0.25s且不新增NN。逐字/空白完全一致、无重写原结果、无上传/独显计算/实卡/原生UI/默认切换，属于内部不合格模型的技术fixture。r40='+receipt['modelCommit']+'私有提交独立回读通过。接续24公开完整训练源准备，覆盖12英文官方training/全局参与者排除验证、12中文三种房间，仅采集/单麦原PCM/标签整理；不训练/不把中文局部speakerID当全球身份，最终holdout未开。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':d['state'],'cpuNativeFullMeetings':len(cpu['results']),'backendCases':len(app['cases']),'qualityQualified':False,'protectedCommit':receipt['modelCommit']},ensure_ascii=False))
