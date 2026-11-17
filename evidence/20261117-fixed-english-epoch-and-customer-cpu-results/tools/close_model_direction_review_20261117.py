"""Close the measured batch and revise the original workpoint after owner feedback.

No new inference/training, app installation, default-model change or data cleanup.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1')
C=E/'english-accuracy-reference-20261117';T=E/'gpu-owned-evening20261117-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
at=datetime.now().astimezone().isoformat(timespec='seconds')
s=read(T/'paired-score.json');cpu=read(C/'customer-cpu-probe-r1/score.json')
assert not s['advanceToCompleteSources'] and s['candidateErrors']==118
assert len(cpu['summaries'])==4
recovery=dict(at=at,state='COMPLETE_CPU_OUTPUTS_SCORED_IN_EXISTING_CLEAN_SCORING_RUNTIME',
 originalFailure=str(T/'finish-evaluation-shared-lease-r1/SCORING_EXISTING_CPU_BILINGUAL_PROBE.log'),
 cause='Orchestrator used systemPython for scoring; rapidfuzz is in the existing clean scorer runtime.',
 correctedRuntime='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',
 originalInferenceRuntime='sherpa-onnx1.13.4/systemPython',newInferenceCalls=0,newTrainingUpdates=0,
 cpuInferenceCasesComplete=48,score=str(C/'customer-cpu-probe-r1/score.json'))
target=C/'cpu-scoring-runtime-recovery.json';assert not target.exists();write(target,recovery)
review=dict(at=at,ownerQuotes=['为啥越来越差了','所以每次都训练这么长时间结果就是越来越差, 是不是在胡乱尝试呢, 是不是要换一个工作方式'],
 state='DIRECTION_REVIEW_COMPLETE_QUALITY_OPEN_NO_NEW_MODEL_TRIAL_STARTED',
 conclusion='Change the decision sequence. A valid isolated experiment and small improvement do not justify another long run when product-level convergence is missing.',
 confirmed=[
  'One fixed English epoch completed1828examples/457effectiveupdates;123to118errors/709words,4.065percentrelative reduction. EN2001a71to64;ES2003b52to54. Original paired admission failed; reject without whole-source expansion or hyperparameter/checkpoint grid.',
  'CPU old-client-asset profiles use different models/runtime/chunking from the researchParakeet path;32.86/43.44percentEnglish rates are not a time-series regression caused by the completed training.',
  'ExistingCPU assets ran2threads with471470080Bpeakprivatecommit andRTF0.0701to0.1128; this host demonstrated compute feasibility, not bilingual product qualification.',
  'Source audit found availability-prioritizedChinese model and fixedzh SenseVoice hint. This is a deployed-path gap; it has not been proved to cause the separate research-model errors.',
  'Selected multilingual ASR/speaker/separation roles remain useful architecture boundaries. Ordinary nonoverlap transcription should not be forced through failed blind separation or unconditional denoising.'],
 unresolved=[
  'No controlled same-model/same-waveform native-reference versus deployment-runtime and segmentation comparison yet identifies where additionalEnglish errors arise.',
  'No demonstrated English base meets the original5percent threshold on the target independent complete meetings.',
  'The reused709word exposed screen is not independent full-meeting/person/facts acceptance, despite participant-disjoint training data.',
  'MoreVRAM or another epoch has not been shown to close the83additional errors needed for5percent on this exposed screen.'],
 actualChange=[
  'No new training or new model trial after this review. Preserve rejected candidates, baseline and failures; current product defaults unchanged.',
  'Next one bounded diagnostic must compare identical original audio, same model family and fixed text policy across reference/runtime/segmentation; declare any unproved weight/precision equivalence as a confound. No training and no model grid.',
  'If reference is good but deployment regresses, repair/export/segmentation only. If reference itself fails target, qualify a suitable published base on independent full public meetings before domain adaptation.',
  'Long training resumes only with a named error class, matching lawfultraining data, a short feasibility/benefit decision and original per-meeting stop criteria. Runtime readiness alone is insufficient.',
  'Report comparable per-language raw error, complete-meeting scope and actual user-deployable path; retain original95floor/98target and separate speaker/facts qualification.'],
 priorCpuExportAcquisition=dict(receipt=str(C/'parakeet-cpu-export-acquisition-r1/completed.json'),
  revision=read(C/'parakeet-cpu-export-acquisition-r1/completed.json')['revision'],
  state='Already acquired and hashed only; noCPU export inference or product integration performed',newNeuralCalls=0),
 newInferenceDuringReview=0,newTrainingDuringReview=0,qualityQualified=False,saleQualified=False,
 sources=[str(T/'paired-score.json'),str(C/'fixed-epoch-error-budget.json'),str(C/'customer-cpu-probe-r1/score.json'),str(J/'customer-cpu-bilingual-deployment-20261117.json')])
week=J/'week-direction-review-20261117.json';v=read(week);v['latestOwnerWorkingModeReview']=review
v['assessment']='Quality has not converged. End the rejected one-epoch recipe; first isolate reference/runtime/segmentation on the actual customer path before another model or training run.'
v['newPriority']=review['actualChange'];write(week,v)
p=Path('work/bilingual_progress.json');x=read(p);batch=x['jointArchitecture20261115']['runtimeOptimization20261117']
batch['ownerWorkingModeReview']=dict(file=str(week),**review)
batch['customerCpuProbe'].update(state=cpu['state'],completedModelCasePairs=48,score=str(C/'customer-cpu-probe-r1/score.json'))
batch['evaluationReconciliation']=dict(englishFinalScore=str(T/'paired-score.json'),cpuScore=str(C/'customer-cpu-probe-r1/score.json'),scoringRuntimeRecovery=str(target),
 originalFailedFollowupRetained=True,allOwnedModelWorkersTerminal=True)
x['state']='MODEL_DIRECTION_REVIEW_COMPLETE_QUALITY_OPEN'
x['next']='No new long training/model trial. First isolate identical public audio through selected-model reference, CPU export and fixed segmentation, declaring weight/precision confounds. Use this to choose deployment repair versus published-base qualification; do not use runtime readiness or this rejected one-epoch result to justify another overnight run.'
x['jointArchitecture20261115']['overnightExecution20261116']['currentOwnedNeuralWorker']=None
marker='OWNER_MODEL_WORKING_MODE_REVIEW_20261117';assert marker not in x['logResult']
x['logResult']+='\n\n'+at+'｜'+marker+'｜完整承接Owner“为啥越来越差了”“所以每次都训练这么长时间结果就是越来越差, 是不是在胡乱尝试呢, 是不是要换一个工作方式”。本轮1828样本/457有效更新实际完整，123→118/709错，仅4.065%相对改善，EN2001a71→64而ES2003b52→54，未通过原门，拒绝；未扩整会/未挑中途/未再调参。2套现有CPU资产48组推理已全完，独立评分复用原干净环境完成；初次系统Python缺rapidfuzz仅评分失败，原日志保留、0额外神经调用/训练。CPU中文89/1258与94/1258，英文308/709与233/709；与研发不同模型/切段/运行时，不能串成训练越来越差，也未证明CPU本身致差。速度RTF0.07～0.113、私有峰471470080B仅证本机算力可行。当前主要工作方式问题是单项有停止门，但没有先把参考模型→研发→客户端的同源误差定位与产品基线打通，工程运行与微小降错不能作为下一长训依据。收住新训练/新模型试验，下一步限同原音/模型族/文本口径的参考-CPU部署-切段差异诊断；权重/精度未等价的保留混杂，不能直接归因量化。已有Parakeet官方CPU导出仅完成固定版本下载哈希，无新推理/产品接入。原95/98、逐人/事实/最终留出门保留，当前默认不换、无新构建安装，全部本会话模型作业已终态。'
write(p,x)
portal=Path('C:/Users/Billy/Documents/Codex/2026-11-14/ni/work/companion-project-portal/src/handbook.json');h=read(portal);g=h['modelGuide']
g['completedWork'][-1]=dict(work='核显、CPU与实际英文适配',result='英文1828段/4.18小时已完成457次有效更新；原12段123→118错但一场回退，未过原门。现有CPU双模型48组测试已完成。',decision='拒绝本轮训练配方；保留核显/CPU工程路径，先查参考到客户端的同源差异。')
g['methodIssues'][0].update(evidence='运行兼容与资源接入已推进；本轮完整训练仅少5错且一场回退，未把投入转成合格产品质量。',change='不再因跑通或微小改善就进入长训。先用同原音/模型族把参考、研发和客户部署差异查清，再选择修接入或换底座。')
g['methodIssues'][2].update(evidence='局部候选有停止门，但多条路线串行探索没有形成95%底线；本轮适配已按原门拒绝。',change='收住新模型和训练试验。每次诊断先写明要排除的原因、可改变的决定和停止条件；没有依据不跑整夜。')
g['route']=[dict(title='已拒绝本轮固定训练',text='Parakeet一轮457更新完成；英文17.35%→16.64% WER，一场52→54错，未过原门。保留失败，不追加学习率、轮数或检查点网格。'),
 dict(title='先定位参考到客户端的差异',text='同一原音、同一模型族和固定文本政策，对照参考实现、CPU部署和切段；权重或精度未证明一致时明确保留混杂。下一诊断不训练、不换一串模型。'),
 dict(title='依据原因决定是否训练',text='参考好而部署差就修导出/接入/切段；参考本身不达标，先用独立公开整会确认底座能力。只有明确错误类型和匹配数据后，才进入有边界的适配。'),
 dict(title='按真实用户路径验收',text='客户无独显本地中英文仍是交付目标。CPU速度已初测可行，质量未合格；先非重叠完整会议及逐人归属，再推进重叠和噪声，原95/98目标不变。')]
g['customerCpu']['note']='CPU实测已完成：速度与本机内存可行，中文和英文质量均未过原门；不同模型/切段的成绩不与研发训练成绩连成趋势。'
g['customerCpu']['items'][2]['text']='选中模型族的公开INT8 CPU导出已固定版本下载核验；尚无本次CPU导出推理、数值等价或产品接入结果。训练后候选已拒绝，不部署该检查点。'
write(portal,h)
print(json.dumps(dict(state=x['state'],review=str(week),newInference=0,newTraining=0,productDefaultChanged=False),ensure_ascii=False))
