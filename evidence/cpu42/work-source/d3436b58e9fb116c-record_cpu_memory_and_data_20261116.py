from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=Path('work/bilingual_progress.json');d=read(p);j=d['jointArchitecture20261115'];o=d['ownerOvernightRun20261115'];now=datetime.now().astimezone().isoformat()
live=read(E/'qwen-cpu-chinese-whole-run-r2/run.json');inference=read(E/'qwen-cpu-chinese-whole-run-r2/inference-state.json')
data=read(E/'meeting-domain-data-r1/run.json');audit=read(B/'meeting-domain-data-r1/export-integrity.json');qwen=read(B/'qwen-cpu-port-r1/score.json');wss=read(B/'qwen-cpu-working-set-r1/neural-control/result.json')
assert len(data['completed'])==22 and len(data['failures'])==2 and audit['strictStageAEventsMissingInBroadAcoustic']==0
d['state']='CPU_CHINESE_FULL_COMPONENT_RUNNING_OWN_MEMORY_CAP_PUBLIC_TRAINING_DATA_VERIFIED_QUALITY_OPEN'
o.update(currentState=d['state'],activePid=live.get('pid'),activePidCreatedAt=live.get('pidCreatedAt'),noOwnNeuralProcessActive=False,currentExecutionDevice='cpu',latestObservedAt=now)
j['qwenCpuPort20261116']={'state':qwen['state'],'score':str(B/'qwen-cpu-port-r1/score.json'),'scoreSha256':sha(B/'qwen-cpu-port-r1/score.json'),
 'universalPortRejected':True,'englishNoRegressionGateFailed':True,'quantizationGridForbidden':True,'chineseOnlyCharacterizationScope':str(B/'qwen-cpu-chinese-characterization-r2/scope-decision.json'),
 'chineseWholeRun':str(E/'qwen-cpu-chinese-whole-run-r2'),'completedAtObservation':len(inference['completed']),'totalChunks':147,'qualityQualified':False}
j['ownedModelWorkingSetControl20261116']={'state':wss['state'],'proof':str(B/'qwen-cpu-working-set-r1/neural-control/result.json'),
 'scope':'Only this task model worker; no VSCode/Defender/other app or global memory changes.','workingSetMaximumBytes':1879048192,'privateFamilyMaximumBytes':2*1024**3,
 'actualWindowsLowMemoryStopRetained':True,'originalStartRecoveryGiB':3.18,'cpuPercent':25,'computeThreads':4,'proofSingleControlOnly':True}
j['meetingDomainTrainingPreparation20261116']={'state':'PUBLIC_TRAINING_DATA_22_WHOLE_SOURCES_190_STRICT_944_BROAD_EXAMPLES_PCM_LABEL_AUDIT_PASSED_NO_WEIGHT_TRAINING',
 'control':str(B/'meeting-domain-data-r1'),'run':str(E/'meeting-domain-data-r1/run.json'),'plan':str(B/'meeting-domain-data-r1/plan.json'),
 'sourceMeetings':22,'retainedSourceFailures':data['failures'],'fullOriginalHours':13.09690564236111,'strictSequentialExamples':190,'broadAcousticExamples':944,
 'broadAcousticHours':10126.0795/3600,'integrityProof':str(B/'meeting-domain-data-r1/export-integrity.json'),'trainingStarted':False,'parameterUpdates':0,
 'chineseGlobalPersonDisjointnessVerified':False,'modelTrainingReady':False,'reservedFinalHoldoutOpened':False,'qualityQualified':False}
j['cpuNativeForcedAlignerPort20261116']={'state':'OFFICIAL_CPU_TORCH_ISOLATED_OVERLAY_INSTALLED_NATIVE_CLASSIFIER_CONTROL_PREPARED_NOT_YET_RUN',
 'installation':str(B/'cpu-forced-alignment-r2/runtime-installation.json'),'control':str(B/'cpu-forced-alignment-control-r1/binding.json'),
 'existingClassifierWeightsUnchanged':True,'neuralCalls':0,'qualityQualified':False}
d['next']='按Owner25% CPU/4计算线程、原2GiB私有/真实低RAM保护续完147固定窗中文整会，仅刻画中文组件，不撤销Qwen CPU通用口因英文回退的拒用结论。先冻结原始评分依赖再算两场整会原始字错，之后在同一个神经计算队列验证既有Qwen时间戳分类器的CPU精确加载与中英控制，再依时间与资源完成中文时间轴/既有CPU连续人物日志组合。22完整公开源/190严格轮流多人/944较广声学训练输入已逐PCM与标签核验；没有新权重训练，中文跨会议真实人员隔离仍未证明。15:40停止模型计算，16:00交付真实质量、资源、原始结果和失败；默认日用包不切换。'
j['nextExecutableGate']=d['next']
d['logResult']+='\n'+now+' Qwen原中文家族CPU固定Q8对照24片完成：中文72/1258对原73，英文146/709对原141，其中EN2001a93对81违反原逐会议不回退门，保留通用口拒用，不扫量化/提示网格。另事前记录独立中文组件刻画范围，不能冒充撤销通用拒用。两整会原147固定30s窗首轮13:33真实Windows低RAM终止，留1窗；发现原2GiB私有门不能限制映射权重的常驻页，新增仅本任务模型worker的Windows硬工作集1.75GiB，不碰他人程序/注册表/全局策略。整模型只读映射零NN探针及同一30s真实原音对照通过：rawDecoded和hypothesis逐字相同，常驻家族约1.761GiB，计算11.924s对原15.677s只作单例控制，不宣称普遍提速；CPU25/4、2GiB私有、3.18GiB恢复及真实Windows低RAM仍保留。13:58重启中文全量复用已通过控制1窗，观察已完成'+str(len(inference['completed']))+'/147。公开训练源24计划实际22成功/2英文服务器403及404原失败保留，约13.0969h完整单麦原音和原标注；190严格多人轮流无重叠57.928min、944声学非重叠2.8128h导出完成，逐WAV/PCM/原音帧/完整标签/窗口无重复/验证排除审计通过，严格3978标注事件全部含于广集13081事件。初版3源的padding中点floor/ceil共享1采样已只修上下文，复用19已过源不重新导出。中文001-M为局部ID，真实跨会议人员隔离未证实，不宣称训练已准备完全；新权重参数更新0。官方Torch CPU首次误选cp312在pip安装前拒绝，按实际3.11 ABI修正为cp311原2.11.0+cpu隔离overlay已安装，不动旧ROCm环境；既有0.6B时间戳分类器CPU mmap标准tiny对照+真实中英识别原文控制待当前ASR结束后串行执行，未运行不计成果。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':d['state'],'completed':len(inference['completed']),'dataMeetings':len(data['completed']),'newWeightTraining':False},ensure_ascii=False))
