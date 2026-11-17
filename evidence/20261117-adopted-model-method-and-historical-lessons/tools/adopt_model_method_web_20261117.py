"""Adopt the owner's model-work change in the existing task and lesson source."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1')
C=E/'english-accuracy-reference-20261117';T=E/'gpu-owned-evening20261117-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
write=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
quote='那就换咯, 写道网页里面落实, 然后网页之前一些教训也要写好'
audit=read(C/'same-input-comparability-audit-r1.json');assert audit['englishCases']==12 and audit['newNeuralCalls']==0
week=J/'week-direction-review-20261117.json';w=read(week)
assert 'executionMethodAdopted20261117' not in w
lessons=[
 dict(id='long-training',title='小幅降错不足以支持下一次长训',
  evidence='英文4.18小时、1828段、457次有效更新：123→118错/709词；一场52→54错，原中间门未通过。',
  learned='训练确实发生了，但本配方没有给出足够、稳定的跨场改善。运行成功和训练损失不能替代识别质量。',
  action='拒绝并保留该配方，停止学习率、轮数和检查点网格。先定位错误来源。',
  reopen='明确主要错误类型及匹配的训练数据，并能说明新的变化为什么可能改变结论，才设计一次固定适配。',
  sources=[str(T/'paired-score.json'),str(C/'fixed-epoch-error-budget.json')]),
 dict(id='comparison',title='不同模型与处理方式的成绩不能连成趋势',
  evidence='已核对12段英文原音哈希和帧数一致；CPU路径同时换了模型、运行时，并将7段切成多段，共19段。',
  learned='17.35%研发基线与32.86%～43.44%现有CPU路径差距，不能直接证明CPU或量化导致识别变差。',
  action='每次标明模型、精度、切段、评分分母和场景；因果归因只用单变量对照，部署方案比较单独说明。',
  reopen='权重、运行方式、切段条件可以核对，或新对照明确只改变一个变量。',
  sources=[str(C/'same-input-comparability-audit-r1.json'),str(C/'customer-cpu-probe-r1/score.json')]),
 dict(id='separation',title='普通轮流说话不应强制前置分离',
  evidence='盲分离实际训练80步；训练/推理单位修正后，自然多轮161→319错/1476词，短回答13→20错/87词。',
  learned='分离指标改善不保证转写改善；普通非重叠输入可能被处理得更差。该结果也不代表所有分离模型都无效。',
  action='普通多人轮流说话保留原始音轨和独立说话人归属，分离留在确有重叠的分支。',
  reopen='先出现明确的重叠错误，并在同原音配对结果中证明分离给转写和归属带来净收益。',sources=[str(week)]),
 dict(id='speaker',title='人物归属和文字识别必须分别验收',
  evidence='人物小适配实际训练8步，困难来源DER约15.84%→15.92%，未改善。',
  learned='人物模型不能代替ASR降错；文字更准也不能自动证明说话人标记更准。',
  action='拒绝本固定人物适配，保留原组件；分别记录CER/WER、DER及逐人结果。',
  reopen='能定位人物混淆的具体原因，并有独立人物/来源和有效标签支撑新的验证。',sources=[str(week)]),
 dict(id='denoise',title='降噪和VAD不能默认代表质量提升',
  evidence='固定FRCRN同运行时配对，英文139→154错/709词、中文72→106错；VAD替换未达原门。',
  learned='声音听起来更干净或活动范围变大，不等于原始文字和人物归属更准确。',
  action='结束该降噪配方和阈值/强度网格，保留原音；先把非重叠基础识别做好。',
  reopen='噪声或活动检测被证实为主要原因，并且同源配对原评分改善。',sources=[str(week)]),
 dict(id='capacity',title='更大的通用模型不是自动的答案',
  evidence='完整Whisper large-v3 F16：227/709错；Granite 4.1 2B：113/709错，仍未过原门，推理总耗时约为原Parakeet的9.33倍。',
  learned='一次大模型对照可以排除一个固定方案，不能据此宣称所有架构都已试完，也不能只看少量降错而忽略成本。',
  action='保留并结束这两份固定参考配方，不增加提示词、精度或解码网格。',
  reopen='公开证据与目标会议场景更匹配，且能说明与已失败配方的实质差异，再决定是否做一个固定参考。',sources=[str(week),str(C/'score.json')]),
 dict(id='runtime',title='执行失败与模型质量失败要分清',
  evidence='Windows虚拟环境启动器与真实Python的PID不同曾在0神经调用时阻断训练；本轮RAM保护后从416步完整检查点恢复，最终候选完成457步。',
  learned='启动、资源、兼容性或锁失败不能当作模型质量结论；修好运行条件也不等于字错率提高。',
  action='先修真实执行原因，保留失败和已验证版本，只复验受影响范围；温度观察、CPU/核显能力与独显条件按当前Owner要求执行。',
  reopen='有新的实际环境/权限/代码变化才恢复对应作业；不反复重跑未变化的失败条件。',sources=[str(C/'venv-supervisor-regression-r1/result.json'),str(T/'supervisor-resume-1/completed.json')]),
 dict(id='acceptance',title='短片段、整会和客户可用是不同的证据',
  evidence='同源整会中文5.54%→5.14% CER、英文23.94%→18.18% WER有收益；709词筛选已暴露；CPU测试1.13.4与客户端DLL1.13.1不同。',
  learned='局部筛选、文件下载、研发推理或内部检查，均不能代替独立完整会议和已装客户路径验收。',
  action='保留真实收益与原音；按语言、场景、整会、逐人和客户CPU路径验收，最终留出集保持关闭。',
  reopen='候选先有可重复的实际改善，再进入对应整会/客户验收；参考文字与95/98目标保持。',sources=[str(week),str(J/'customer-cpu-bilingual-deployment-20261117.json')])]
method=dict(state='ACTIVE_REFERENCE_TO_CLIENT_DIAGNOSIS_FIRST',adoptedAt=at,ownerQuote=quote,
 title='已落实的新工作方式',summary='先固定基线与可比条件，再定位参考到客户端的差距；按原因修一处，有数据依据后才训练。',
 currentTask='同源输入与比较条件已核对；下一项是固定模型族、原音和文本政策的一次受控部署/切段对照。',
 audit=dict(file=str(C/'same-input-comparability-audit-r1.json'),cases=12,splitCases=7,cpuChunks=19,newNeuralCalls=0,
  result='12段原音一致；模型、运行时、切段同时不同，当前差距不能归因于CPU或量化。'),
 steps=[
  dict(title='固定基线与比较条件',status='本批已核对',action='核对原音、权重身份、精度、切段和原评分口径；研发训练与现有CPU配置分开列。',deliverable='可比较与不可比较的项目，以及仍未隔离的变量。'),
  dict(title='一次受控链路对照',status='下一执行项',action='复用固定公开原音；选中模型族的CPU部署方案与参考分开比较，同权重的切段对照只改切段。导出/精度未等价时保留差异。',deliverable='定位是否存在部署/切段损失；运行失败不改成质量失败。'),
  dict(title='按原因修一处',status='依据对照决定',action='参考好而部署差就修接入、导出或切段；参考本身差就先确认基础模型上限。明确错误类别和匹配数据后才设计适配。',deliverable='一个有证据支持的修改决定，及应保留、停止的路线。'),
  dict(title='按真实用户路径验收',status='改善成立后进入',action='先多人非重叠完整会议，分别核对中英文、逐人归属和关键事实；客户CPU可用后再推进重叠与噪声。',deliverable='原95%底线/98%目标的实际结果、资源表现及尚未通过的范围。')],
 executionConditions=[
  '每次计算先明确要区分的原因、结果会改变的决定和停止时限；失败先查原因，不自动延长成整夜训练。',
  '没有匹配错误与数据依据，不启动新长训；固定配方失败后不做学习率、轮数、检查点或模型网格。',
  '同样条件下的失败不重复；有可改变结论的新条件才恢复。中文按字、英文按词，整会与短片段分开。',
  '客户无独显本地中英文是交付基线；实际独显训练上限16GiB不扩大CPU或核显共享内存预算。'],
 retained=['已验证的本地增量/离线PCM、断点和完整性链路。','同源整会中英文的真实降错及原默认/回退版本。','可用公开训练数据、核显/CPU运行与独立实现对照证据。'],
 trainingScheduled=False,modelQualityQualified=False,saleQualified=False)
w['executionMethodAdopted20261117']=method;w['lessonsForNextExecution20261117']=lessons;w['currentUpdatedAt']=at
w['historicalTrainingStatementAtOriginalReview']=dict(at=w['at'],statement=w['actualTrainingHistory'])
w['actualTrainingHistory']='As of'+at+': English adaptation completed1828examples/457effectiveupdates and final validation123to118errors/709, failed original paired gate. Earlier speaker8 and separation80 updates also ran and failed their respective gates; none is promoted.'
for entry in w['stopOrDefer']:
 if entry['route']=='Use a TurboQ8 failure to stand in for fullWhisper capability':
  entry['earlierStageStatement']=dict(evidence=entry['evidence'],decision=entry['decision'])
  entry.update(evidence='Fulllarge-v3F16 subsequently completed original12/709 at227errors, distinct from priorTurboQ8 at195errors.',decision='Fixed full-model reference ended after failed gate; no decoding/precision roster. Earlier missing-reference statement is historical.')
w['newPriority']=[s['action'] for s in method['steps']];write(week,w)
p=Path('work/bilingual_progress.json');x=read(p);batch=x['jointArchitecture20261115']['runtimeOptimization20261117']
batch['executionMethod20261117']=dict(method,lessonSource=str(week),lessonCount=len(lessons))
x['state']='OWNER_ADOPTED_DIAGNOSE_FIRST_MODEL_WORK_METHOD'
x['next']='按已采纳的新工作方式续作：同源条件审计已完成（12段原音一致；CPU另有模型/运行时/切段差异）。下一项仅做一次固定CPU部署/切段对照，声明权重/精度差异，不归因于CPU；不启动新长训或模型网格。依据结果只修主要原因，再进入完整会议与客户路径验收。'
marker='OWNER_ADOPTED_MODEL_METHOD_WEB_20261117';assert marker not in x['logResult']
x['logResult']+='\n\n'+at+'｜'+marker+'｜Owner明确“'+quote+'”。新方法已从讨论转为原待办当前执行项：固定基线→受控链路对照→按原因修一处→真实用户路径验收，不新建任务树或另写共用规则。原12段原音哈希/帧数及48组CPU输出已只读核验，CPU英文7段被切分为19段，模型/运行时也不同；不能把17.35与32.86/43.44串成训练趋势或直接归因CPU/量化。此核对无新神经调用/评分/训练，不记准确率进展。原周复盘“英文尚无更新”及“完整Whisper未测”的早期语句保留为历史，当前点改为英文457更新失败、Whisper完整参考227/709失败。网页教训从同一复盘源读8项，每项写原结果、能说明什么、当前决定、何种新证据才重开及原证据入口；保留已验成果与所有失败，原95/98、最终留出、CPU/核显/独显边界不变。'
write(p,x)
print(json.dumps(dict(state=x['state'],lessonCount=len(lessons),method=method['state'],auditCompleted=True,newNeuralCalls=0),ensure_ascii=False))
