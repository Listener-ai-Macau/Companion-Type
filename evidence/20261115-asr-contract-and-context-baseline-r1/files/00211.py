from pathlib import Path
from datetime import datetime
import hashlib,json,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'context-matched-baseline-r3';RUN=Path('E:/CodexData/Companion/product-d1d2-20261114/context-matched-baseline-r3/base-run-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
score=read(C/'baseline-score.json');run=read(RUN/'run.json');state=read(RUN/'baseline-state.json')
assert run['exitCode']==0 and state['neuralCalls']==32 and state['parameterUpdates']==0
if psutil.pid_exists(run['pid']):assert abs(psutil.Process(run['pid']).create_time()-run['pidCreatedAt'])>=.01
short=[r for r in score['cases'] if r['condition']=='clean-short-response']
assert len(short)==20 and sum(r['totalEdits']==0 for r in short)==16
very_short=[r for r in short if r['referenceCharacters']<=2]
assert len(very_short)==8 and all(r['totalEdits']==0 for r in very_short)
decision={'state':'BASE_DIAGNOSTIC_COMPLETE_NO_AUTOMATIC_ADDITIONAL_TRAINING',
 'at':datetime.now().astimezone().isoformat(),'run':str(RUN),'runSeconds':run['seconds'],
 'familyPrivatePeakBytes':run['privatePeakBytes'],'neuralCalls':32,'newParameterUpdates':0,
 'byCondition':score['byCondition'],'byMeetingAndCondition':score['byMeetingAndCondition'],
 'cleanShortExactCases':16,'cleanShortCases':20,'atMost2CharacterCases':8,'atMost2CharacterExactCases':8,
 'findings':[
  'The previous training selection excludes<2s and multi-turn contexts, but this baseline does not show a universal inability to recognize short speech. All8at-most2-character controls are exact.',
  'All13clean-short character errors occur in4cases from one validation meeting; the other source is0/37. This87-character cohort is too small for a general quality or statistical claim.',
  'Every selected natural multi-turn window contains overlapping reference speech. Its chronological merged CER is diagnostic and confounded by ordering; do not train the base blindly against an arbitrary mixed-speaker order.',
  'In context20200805_S_R001S01C01-06, the first two substantially overlapping reference utterances appear in the reverse order in raw ASR. The original55edits remain unchanged. Some content from both voices is present; this is not evidence of55missed or misheard independent characters.',
  'The same example has a potentially ambiguous transcription (reference秋天, hypothesis秋千) in a sentence about a swing. No reference is silently corrected without audio adjudication, and original gates/scores remain unchanged.'
 ],'decision':'No automatic repetition of the rejected clean-utterance LoRA, no new short-response oversampling or mixed-overlap teacher targets on this evidence. First separate actual acoustic losses, reference ambiguity, overlap ordering and speaker attribution. Preserve original whole meetings and never claim these clips satisfy D2.',
 'next':'Keep one optional official Community1 speaker-only comparison behind its account-access gate; prepare fixed local adapter and exact original scoring before any run. Independent ASR work should use audio-grounded error adjudication from existing sources, not further blind hyperparameter/model variants.',
 'originalGatesChanged':False,'finalHoldoutOpened':False,'d1Complete':True,'d2Complete':False,'qualityQualified':False,'saleQualified':False}
target=C/'decision.json';assert not target.exists();target.write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(asrInputContractConclusion=str(D/'asr-input-contract-audit-r1/conclusion.json'),
 contextMatchedBaselineStatus=decision['state'],contextMatchedBaselineScore=str(C/'baseline-score.json'),
 contextMatchedBaselineDecision=str(target),contextMatchedBaselineNewTraining=0)
v['next']='新32条基座诊断已完整结案、禁止自动追加训练。先完成本批源码和原字/条件证据保护；下一可执行项准备官方Community1单说话人组件对照的固定本地接口和原门评分，授权仅该可选支线等待。ASR继续按已有音频证据区分实际漏听/标签歧义/重叠排序与归属，不盲目换模型、扩参或回灌最终holdout；D2仍未完成。'
v['logResult']+=' '+decision['at']+' 条件匹配基座实际诊断结案：13:45:48—13:50:54共305.218秒，32调用、0新训练，RX6800XT实核ordinal1，族私有峰1253470208B、原5%/2GiB和低RAM保护保持，owned启动器创建时戳核实已退出。20条干净<2秒共26.82725秒/87字13错（8替5漏）CER14.9425%，16/20条全对；两个来源分别0/37与13/50，8条<=2字全部全对，不能概括成普遍不会短应答或据87字决定新训练。12条完整自然多人窗322.6832秒/1476字161错（33替86漏42插）10.9079%，均有参考重叠；其中一条首两段重叠内容在ASR倒序，55原错保留，不把这些全称声学漏字，参考秋天/输出秋千存在待听音审定歧义亦未改原标签。两个条件可能包含同音片段，分报不合为独立会议/不称D2通过。原128训练覆盖缺口仍成立但不等于补训会有效，本轮明确不自动再做短应答扩采/任意重叠序列训练、旧适配保持拒绝，当前原模型和默认权重保持。原71+72块官方解析完全相等与产品26784字符/70换行保留、5份上游源码Gitblob核验已成独立conclusion，当前英文归一会删部分语气词和统一数字/缩写，不复制替代原门。'
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

note=Path('outputs/Companion-社区可行性与实际进度-20261115.txt')
old=D/'asr-input-contract-audit-r1/owner-report-before-update.txt'
if not old.exists():old.write_bytes(note.read_bytes())
note.write_text('''Companion 社区可行性与实际进度｜2026-11-15 13:51 更新

有机会做成有明确使用条件的本地会议产品，现有开源组件已能搭建完整链路。我们已交付可执行内测候选；跨会议文字和人物质量仍没有达到原D2门槛，目前不能称可售完成。此前从一份较好会议推断很快收敛过于乐观，现已用多份完整会议验证并保留失败。

大家怎么做
常见路线是组合预训练组件：ASR负责内容，声纹/说话人日志负责谁何时说话，对齐器负责词和时间，会议应用负责原音、人物复核、纪要、保存与导出。FunASR和WhisperX均公开这种组合。分出两个人同时说话的时间，不等于已恢复两人的全部内容。WhisperX官方仍列出重叠识别和人物日志的限制。MOSS、VibeVoice等联合模型也是另一条路线，但我们的MOSS本机长会失败记录必须保留，不能把开源演示当作已经解决AMD长会质量。

B站查到了FunASR+3d-speaker会议接口、单声道人物接口和Qwen多人整合包。视频详情页返回412，核实范围仅搜索标题和简介，没有看完视频或验证其准确率。不能据演示标题推断完整会议、重叠和长时间身份稳定性合格。

是否需要从零训练
当前没有必要从零训练语音基座。6800XT已实际完成本地推理和一轮小LoRA训练，证明运行和小规模适配可行；这与证明能达到商业会议精度是两回事。当前最难的是跨录音条件的内容完整、人物长时一致、弱音短回应和重叠文字归属。只有证实哪类错误、标签可靠、训练与验证隔离后，才值得做有针对性的适配。

当前已完成什么
D1按原定义已完成可执行内测候选：完整35分9.813秒英文会实际通过原生导入、本地转写、两种配置中的真实纪要调用、保存、新进程重开、Markdown/JSON/原音导出；人物名复核、备份恢复、缓存隐私删除、停止后续转和后台原生界面均实际核验。语音推理全本地，纪要使用既有配置的云服务。90秒公开中英文录中送音/停止续转已实际核验；冷启动首个预览约81.236秒，流畅实时延迟仍未达标。实卡Windows/Android全链路和正式纪要事实准确率未完成。

D2仍未完成。保留基础模型的原始完整开发会议成绩：
旧中文38分47秒：原字CER5.5375%，人物DER3.8556%，逐人cpCER5.8018%。
新增中文34分9秒：原字CER14.4974%，人物DER15.8415%，逐人cpCER27.0656%。
普通英文35分9秒：原字WER23.9405%，原参考人物DER26.0181%，逐人cpWER38.7130%。
复杂英文35分42秒：WER34.3685%，原参考人物DER31.0766%。
中文按字、英文按词，不能互比；原中文CER<5%/人物DER<=10%不变。英文<5%是更保守的开发扩展条件，不冒充原中文指标。最终留出会未打开。外部强制对齐参考会显著改变英文DER，已另做诊断并保留原分，不用新标注宣布通过。

已经排除的弯路
固定换人切段、全局声纹重分组未改善，拒绝采用。原Nemotron权重的官方实现与本地实现在完整34分钟同输入上DER均约15.8414%，返回人物丢失两者同现，不能再把主要问题归咎本地移植。只读缓存跟踪与完整原概率逐字节相同，缺席期间48个历史人物嵌入仍在，因此完全挤掉缓存的假设不成立，不继续盲改槽位或扫门限。
固定128训练句/32验证句LoRA在短句上少3字错，但两份完整中文会仅461→456和1037→1040错，均未达门槛且没有一致收益，已拒绝进入产品默认，不继续扩epoch/lr/rank。

本轮新核实的事实
两场英文共143最终块保存token与官方转写解析逐段完全相同；产品原始到最终26784字符、70换行完全相同，未发现程序解析吞字。官方榜单的头戴麦分段、当前ami_cleaned和会删除语气词/统一数字等的归一方式与本机整场远场原字验收不同，模型卡历史AMI9.26%不能直接当作本机目标预期，也不证明差距全部来自评测条件。
原128条训练最短2.20256秒、最少7字，不含<2秒或自然多人上下文。本轮在原训练与验证来源隔离的两份录音上，预先固定12个完整多人窗和全部20个干净短应答，基座实际32调用、0新训练。
20短应答16条全对，8条<=2字全对；87字13错集中4条、同一录音，另一个来源37字全对。12多人窗1476字161错，但均有重叠，某些错误来自两人内容排序不同，不能把10.9079%全部解释为声学漏听。这些诊断既不构成D2通过，也不足以支持马上再训一轮。

接下来怎么收敛
保留已能使用的D1候选和原D2门槛。停止没有一致完整会议收益的小训练和参数尝试，先按原音区分真正漏听、参考歧义、重叠排序与人物归属。人物组件只保留一项官方Community1固定本地对照准备，不扩模型清单；其官方页要求账号同意共享资料及访问条件，本机无已授权凭据，已询问Owner稍后自行在本机授权，不要把token发聊天。该对照能否改善、能否满足2GiB和AMD环境都尚未证明，不把它当成必胜替换。主任务没有标成完成或整体阻塞。

本机候选入口
outputs/Companion-打开本地会议候选-20261115.cmd
outputs/Companion-查看完整会议结果-20261115.cmd

主要来源
https://github.com/modelscope/FunASR
https://github.com/m-bain/whisperX#limitations-
https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf
https://github.com/huggingface/open_asr_leaderboard/blob/main/transformers/submit_jobs_qwen3asr.sh
https://github.com/huggingface/open_asr_leaderboard/blob/main/normalizer/normalizer.py
https://huggingface.co/datasets/hf-audio/esb-datasets-test-only/blob/main/datasets-test-only.py
https://huggingface.co/pyannote/speaker-diarization-community-1
https://huggingface.co/nvidia/Nemotron-3-Diarization
https://arxiv.org/html/2611.12246v1
https://github.com/OpenMOSS/MOSS-Transcribe-Diarize
https://github.com/microsoft/VibeVoice/blob/main/docs/vibevoice-asr.md
B站索引，详情412：https://www.bilibili.com/video/BV1bT5gzbE7S/
B站索引，详情412：https://www.bilibili.com/video/BV1xxw6zyE4C/
B站索引，详情412：https://www.bilibili.com/video/BV17DMi6WESP/
''',encoding='utf-8')
readme=R/'model-research/README.md';body=readme.read_text(encoding='utf-8')
body+='\n\n2026-11-15 13:51 ASR输出/评测口径与条件匹配基座诊断结案：两场英文143最终块与官方processor转写逐段完全相同，ES产品26784字符/70换行原始到最终全等，0新NN；当前榜单ami_cleaned/IHM分段/英文normalizer与本机整场单远场原字门不同，不追认历史榜单复现或放宽评分。原128适配训练最短2.20256秒且无自然多人窗，覆盖缺口已证实，但新32条基座诊断（32调用、0训练、305.218秒、族峰1253470208B）不支持简单归因为不会短应答：20干净<2秒共87字13错，16条全对、8条<=2字全对，错误集中一个来源4条；12多人完整窗1476字161错全部有重叠，至少一例首两段话倒序，原55错保持且不全称漏听，标签潜在秋天/秋千歧义未擅自更正。只分条件报、无完整D2资格；不自动扩训/重叠任意序列teacher forcing，原固定LoRA拒绝与原门/最终holdout保持。数据准备两次边界断言失败与修复均留证，未增加NN重试。证据由evidence/20261115-asr-contract-and-context-baseline-r1逐文件绑定；D1候选仍d574b5e4/R8，D2未过。可选Community1访问需Owner账号条件同意，暂无授权，不影响独立源头审计。\n'
readme.write_text(body,encoding='utf-8')
print(json.dumps({'state':decision['state'],'newTrainingUpdates':0,'shortExact':16,'veryShortExact':8,'ownedLauncherExited':True},ensure_ascii=False))
