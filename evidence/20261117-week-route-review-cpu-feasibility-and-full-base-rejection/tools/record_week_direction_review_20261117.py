"""One source-backed weekly route review in the original model work item."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,math,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
xfile=Path('work/bilingual_progress.json');x=read(xfile);j=x['jointArchitecture20261115'];o=j['overnightExecution20261116']
at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
scores={m:read(v['file']) for m,v in o['completedSourceScores'].items()}
tdt=read(J/'english-transducer-r1/score.json');speaker=read(D/'public-speaker-development-r1/final-decision.json')
separator_file=D/'supervised-blind-separation-r1/natural-window-unit-alignment-r1/routed-decision.json'
separator=read(separator_file)
old_index=x['d1d2Execution20261115']
old_index.setdefault('supervisedBlindSeparationNaturalBeforeUnitAlignment',{
 'decision':old_index['supervisedBlindSeparationNaturalDecision'],'metrics':old_index['supervisedBlindSeparationNaturalMetrics']})
old_index.update(supervisedBlindSeparationNaturalDecision=str(separator_file),
 supervisedBlindSeparationNaturalMetrics=separator['byCondition'],supervisedBlindSeparationNaturalStatus=separator['state'])
tiny=read(E/'language-specific-adaptation-r1/cpu-loss-reference-r1/result.json')
first=read(E/'language-specific-adaptation-r1/real-cpu-backward-r1/result.json')
second=read(E/'language-specific-adaptation-r1/real-cpu-backward-r2/state.json')
assert tiny['state']=='PASS_CPU_NATIVE_DENSE_SELECTED_ORACLE_AND_CHECKPOINTED_GRADIENTS'
assert second['state']=='BACKWARD_ONE_ORIGINAL_TRAINING_EXAMPLE_CPU' and second['parameterUpdates']==0
assert not psutil.pid_exists(second['pid']) or abs(psutil.Process(second['pid']).create_time()-1794904250.7542365)>.01
source_files=[D.parent.parent/'execution20261110.json',D.parent.parent/'paired-product-decision20261110.json',
 J/'native-context180-r1/score-S_R004S03C01.json',J/'native-context180-r1/score-ES2003b.json',
 J/'english-transducer-r1/score.json',J/'english-asr-specialist-r1/score.json',
 D/'public-speaker-development-r1/final-decision.json',separator_file,
 J/'frcrn-front-end-r1/paired-score-r3.json',J/'context-activity-r1/owner-780m-and-fixed-vad-results-20261117.json',
 D/'reference-annotation-audit-r1/comparison.json',D/'reference-annotation-audit-en2002a-r1/comparison.json',
 J/'language-specific-adaptation-r1/daylight-training-data-repair-20261117.json',
 J/'language-specific-adaptation-r1/native8-independent-reference-control-20261117.json']
# Nov10 receipts live one level above the bilingual work root.
source_files[:2]=[R/'docs/handoffs/20261109-paired-real-meeting'/n for n in ['execution20261110.json','paired-product-decision20261110.json']]
assert all(p.is_file() for p in source_files)
review={'at':at,'reviewWindow':'2026-11-10 through2026-11-17 Asia/Shanghai','state':'QUALITY_CONVERGENCE_UNSATISFACTORY_REORDER_EXECUTION_RETAIN_SPECIALIST_ARCHITECTURE',
 'sourceCoverage':'Nov10 source-pair receipts plus detailed Nov14-17 protected model records. No complete same-task hourly accounting; do not fabricate a week-long compute-time percentage.',
 'ownerQuote':'开始继续吧。然后的话，需要把这个东西继续推进一下，太久了，已经又跑了一个星期了。你看这个，过去一个星。期走的弯路，然后分析一下这个进展顺不顺利，然后看下我们要不要改变方向或者是怎么样。',
 'assessment':'Useful runtime/data/interface work and some real ASR gains exist; required multilingual/per-person/final quality has not converged. The execution route needs changing; the specialist-model decomposition need not be discarded.',
 'confirmedQualityChanges':[
  {'scope':'S_R004S03C01 same complete Chinese source','unit':'CER','referenceUnits':8325,'beforeErrors':461,'afterErrors':428,'beforeRate':461/8325,'afterRate':428/8325,'qualified':False},
  {'scope':'ES2003b same complete English source','unit':'WER','referenceUnits':5781,'beforeErrors':1384,'afterErrors':1051,'beforeRate':1384/5781,'afterRate':1051/5781,'qualified':False},
  {'scope':'Original12 English validation clips','unit':'WER','referenceUnits':709,'mossErrors':124,'parakeetErrors':123,'whisperTurboQ8Errors':195,'qualified':False}],
 'engineeringRetained':['Durable local incremental/offline PCM, stream-final cache reuse, text-preserving continuous speaker integration; internal backend-schema tests passed, not installed UI/card qualification.',
  'Explicit780M Vulkan speaker inference on a full35min source; independent same-model CPU reference closes a material implementation-drift hypothesis only on two fixed prefixes.',
  'Source/participant-audited1828 English clips4.18h and5027 Chinese clips6h; these are usable inputs, not trained quality.'],
 'stopOrDefer':[
  {'route':'Blind separation before ordinary turn-taking ASR is strong','evidence':'319examples/80updates improved source metrics; after the preserved train/inference unit correction, natural multi-turn errors161/1476became319/1476 and short-response errors13/87became20/87. Earlier134/1476and19/87results were before that correction.','decision':'Defer to overlap stage; no separator retuning now.'},
  {'route':'Small speaker adapter as the main quality solution','evidence':f"Original difficult-source DER{speaker['baselineDer']:.6f} became{speaker['candidateDer']:.6f}.",'decision':'Retain/reject this fixed adapter; no incremental LoRA/grid replay.'},
  {'route':'Generic VAD/presence unions to fix diarization','evidence':'WebRTC/Silero gains insufficient; earlier forced-alignment audit already shows reference-protocol disagreement explains much rawEnglish missed-activity time.','decision':'Stop VAD replacement/threshold grids; do not train toward unproved silence labels or change acceptance references.'},
  {'route':'Denoise presumed to improve recognition','evidence':'Same-runtime English139to154 errors andChinese72to106 under fixedFRCRN pairing.','decision':'Reject this enhancer, no strength/gain variants.'},
  {'route':'Quantized/universal CPU model promoted before quality','evidence':'CPU30s model improved someEnglish output but ordinaryChinese5.54to9.07percentCER and otherChinese regressions.','decision':'Do not ship this universal profile. Preserve originalChinese base.'},
  {'route':'Use a TurboQ8 failure to stand in for fullWhisper capability','evidence':'OnlyTurboQ8 was tested:195/709; no complete large-v3 reference exists.','decision':'One fixed full large-v3F16 reference is justified; no fullmodel roster or precision grid.'},
  {'route':'Dependency/temperature/platform work becomes the entire model plan','evidence':'85/95CPU software cuts and whole-task discreteGPU dependency delayed work; owner has now clarified observation-only temperature andCPU/iGPUtraining permitted.','decision':'Training and discreteGPU presence are not universal prerequisites. Keep remaining actualRAM/CPU/time guards and concrete device limitations separate from permission.'},
  {'route':'Training executor built before checking available training coverage','evidence':'OldEnglish selection used26.6percent of available nonoverlap words; repaired to92.3percent/1828clips.','decision':'Keep repaired dataset; no more corpus expansion without a measured new coverage failure.'},
  {'route':'Implement a full nativeFP32 engine port before accuracy admission','evidence':'Parakeet converter/runtime/convolution graph need multiple precision changes while baseline itself is123/709.','decision':'Defer that port; do not confuse compatible execution with improved recognition.'}],
 'staleCurrentIndexCorrected':{'field':'d1d2Execution20261115.supervisedBlindSeparationNaturalMetrics',
  'issue':'The current index still pointed at the pre-unit-correction metrics, while the later aligned failure receipt already existed.',
  'originalIndexAndReceiptsRetained':True,'newCurrentDecision':str(separator_file),'newInferenceOrScoring':False},
 'actualTrainingHistory':'Speaker adaptation and blind-separator training actually ran and failed product gates. English119M ASR fixed-epoch adaptation still has0optimizerupdates; do not call it a trained failure or claim no training occurred anywhere in the week.',
 'newCpuEvidence':{'tinyLossAndGradientProof':tiny,'firstActualAttempt':{'receipt':str(E/'language-specific-adaptation-r1/real-cpu-backward-r1/result.json'),'state':first['state'],'copyOnWriteCommitPeakBytes':first['limits']['jobPeakPrivateCommitBytes'],'declaredPrivateLimitBytes':2147483648,'declaredLimitWasNotMetByThatMapping':True},
  'secondAttempt':{'receipt':str(E/'language-specific-adaptation-r1/real-cpu-backward-r2/state.json'),'lastPersistedState':second['state'],'processTerminal':True,'unifiedExecExitCode':1,
   'exampleSeconds':second['exampleFrames']/16000,'forwardSeconds':second['forwardSeconds'],'finiteForwardLoss':second['loss'],
   'lastRecordedCommitPeakBytes':second['limits']['jobPeakPrivateCommitBytes'],'completedBackwardProven':False,'optimizerUpdates':0,
   'interpretation':'Readonly mapping fixes initial load commit inflation; actual forward runs. Process exits during backward near2GiB without final result; memory pressure is plausible, not conclusively isolated. Do not silently retry or call a fullCPUepoch feasible.'}},
 'newPriority':'Retain the strongest existing base; one fixed meeting-domain English adaptation remains a candidate after a workable resource plan. Stop full-generic-model escalation, overlap/separator/VAD/quantization grids. KeepChinese baseline, preserve independent same-source no-regression gates, and do not treat the optional adaptation as a prerequisite for all product work.',
 'qualityGates':{'wordFloorErrorRateStrictlyBelow':.05,'targetErrorRateAtMost':.02,'englishFixed709WordsFloorMaxErrors':35,'englishFixed709WordsTargetMaxErrors':14,
  'componentAdvanceMaxErrorsOnlyNotAcceptance':99,'perPersonFactsWholeMeetingAndFinalGatesRetained':True,'reservedFinalOpened':False},
 'newQualityResultThisReview':False,'qualityQualified':False,'saleQualified':False,
 'sources':[{'file':str(p),'sha256':sha(p)} for p in source_files]}
base=E/'english-full-base-r1';control=base/'cpu-execution-r3';current=read(control/'run/state.json')
score=read(control/'score.json') if (control/'score.json').exists() else None
review['newQualityResultThisReview']=score is not None
review['qualityImprovedThisReview']=False
if score:
 review['newFullBaseDecision']='Reject full-large-v3F16 at227/709; retain original best123/709. Larger generic capacity did not fix this cohort. No decoding/precision variants.'
review['fullBaseReference']={'model':'FullWhisperlarge-v3F16','publisherRepo':'handy-computer/whisper-large-v3-gguf',
 'modelSha256':'e633ab1d74b0e98f4f57daedaee34291297dbbf01389bda3d890766600c1c584',
 'control':str(control),'latestState':current['state'],'pid':current['pid'],'createdAt':current['createdAt'],'completedClips':len(current['completed']),
 'cpuOnlyExecution':True,'sameOriginalInputs':True,'existingVulkanAttemptFailedBeforeDecode':True,
 'comparisonScope':'A different fixed complete model profile, not a causal separation of Turbo architecture versusQ8 quantization effects.',
 'score':score}
target=J/'week-direction-review-20261117.json';write(target,review)
report=Path('outputs/Companion-一周模型复盘与路线收敛-20261117.txt');report.parent.mkdir(exist_ok=True)
text=f'''Companion 一周模型复盘与路线收敛
更新时间：{at}
范围：11月10日至17日可核验模型专项记录；不把其它聊天的UI/IMU成果算入ASR成绩。

判断：模型质量收敛不顺利，需要改变执行顺序，保留专用模型组合架构。
现在不是接近整体交付：95%底线、98%目标、逐人文字、事实和最终未见会议均未通过。

一、真实效果进展
同一普通中文整会：461/8325=5.54%字错率→428/8325=5.14%；减少33错，仍没过5%。这只是该场，困难中文和个别人还差得多。
同一英文整会ES2003b：1384/5781=23.94%词错率→1051/5781=18.18%，相对减错24.1%，有实际收益但远未达标。
固定12英文短片：MOSS124/709，Parakeet123/709，只差1错；此前Whisper是TurboQ8，195/709，不等于完整large-v3的能力结论。
不同语言、不同会议、整会和短片不能混成一个进度百分比。以上均不是最终盲测。

二、应保留的工程成果
本地增量/离线、原音耐久、完成缓存复用、人物连续时间轴和不改字拼接已做过实际后端接口验证；未冒充正常安装UI/实卡通过。
780M已完成完整35分钟说话人活动推理；同模型独立实现固定片段对照接近。它解决可运行性，不是字准提升。
英语1828条/4.18h、中文5027条/6h来源数据已准备；数据小时数不是训练成果。

三、过去一周的弯路与停止决定
1. 过早做重叠分离：319条/80更新改善分离指标，但修正训练/运行单位后，多轮文字161/1476错→319/1476，短回答13/87错→20/87。普通轮流场景未强之前暂停分离。旧134/1476和19/87是修正前结果，原件保留；当前索引已改指最新失败。
2. 小说话人适配：原困难整会DER15.84%→15.92%，失败；不继续小头/LoRA变体。
3. VAD/活动补洞：两种通用检测器改善不足；11月15日已知英文参考时段口径存在差异，不能把全部漏检秒数当真实丢语音，更不能不断训练填静音。
4. 默认认为降噪有益：固定FRCRN使英文139→154错，中文72→106错。停止该前端的强度/增益变体。
5. 质量未定就先压缩/通用移植：CPU30秒统一模型普通中文5.54%→9.07%。不能拿可运行替代原效果。
6. 把TurboQ8失败泛化成完整Whisper失败：缺少高容量完整基座参照。本轮只补完整large-v3F16，不开模型清单/量化网格。
7. 平台/资源排查占据主线：独显、温度、KV和移植不能变成全部任务的前置。CPU/核显训练按最新指示允许；温度只记录。剩余真实内存/框架支持条件分别说明。
8. 先准备训练器，后发现英语只覆盖26.6%可用非重叠词；已修复至92.3%/1828条。停止无新证据扩语料。
9. 在英文模型还没有质量优势前尝试改底层FP32引擎，多层改造成本不值当前优先级。延期。
说话人与分离有实际训练并失败；英语ASR专项仍0更新。不能说一周全没训练，也不能说英语微调已经试过无效。

四、本轮已经做的实质执行
CPU损失/梯度正确性检查6.4秒通过，原生稠密、独立标量和有界分块梯度一致；约564MiB峰值，没有权重更新。
真实4.15秒英语训练原样本：修正Windows写时复制映射预留过大后，CPU完成前向39.66秒、得到有限损失；反向阶段进程退出，未写终态，最后峰值接近2GiB。不能称完成训练，暂不扩大这条CPU训练系统。
完整large-v3F16参考：核显分配1067217920字节设备缓冲失败，0识别输出；改为同权重CPU只读映射避免这项Vulkan分配，已在同原12条输入完成固定对照。核显失败是执行资源问题，不是识别率。
当前完整模型执行状态：{current['state']}，已完成{len(current['completed'])}/12。

五、明确改变什么
完整大模型参照已完成；没有超过原最佳底座就结束该方案，不继续以更大通用模型或更多参数变体碰运气。下一项只保留一次固定会议域英语适配候选；先有实际可执行资源方案，不因有显卡就开训。
保留当前较好的中文基线和说话人组件；英文先按固定709词对照检验，满足原改善/每会不退步门才扩到原完整会议。
99/709仅是值得继续整会检验的门，绝不等于95%合格；95%在本短片集需≤35错，98%需≤14错。
一次固定适配仍是候选手段；未通过独立改善门就结束该候选，不连续加epoch、调阈值、改标签或换容易样本。
普通轮流说话过线后再做重叠/噪声。实时稿与封口后的最终稿分别验收，产品还要整会逐人/事实/实卡。
这不是把目标降低为能运行；95/98目标和原最终留出集保持。

本报告只引用原待办/唯一时间线和原始结果，不建立第二套任务。没有完整同任务工时账，不能精确声称多少比例时间浪费；版本/测试/文档数量不算准确率成果。
机器可核证据：{target}
'''
if score:
 text+='\n完整基座最终对照：227/709=32.02%词错率，劣于原MOSS124/709与Parakeet123/709，按原门拒绝，不扩整会、不调参数。\n'
 text+=f"CPU实际推理{score['aggregate']['inferenceSeconds']:.2f}秒处理265.56秒音频，整worker{current['wholeWorkerSeconds']:.2f}秒包含60秒RAM稳定与加载校验；私有峰{current['limits']['jobPeakPrivateCommitBytes']/2**20:.2f}MiB。这是本批观测，不是公平跨后端速度基准或产品延迟承诺。\n"
 text+=json.dumps({k:score[k] for k in ['state','aggregate','meetings','advanceToWholeEnglish']},ensure_ascii=False,indent=2)+'\n'
report.write_text(text,encoding='utf-8')
review['ownerReadableReport']=str(report.resolve());review['ownerReadableReportSha256']=sha(report);write(target,review)
j['weekDirectionReview20261117']={'state':review['state'],'receipt':str(target),'ownerReadableReport':str(report.resolve()),
 'qualityConvergenceSatisfactory':False,'specialistArchitectureRetained':True,'trainingMandatory':False,'fullBaseReference':review['fullBaseReference']}
o['cpuNativeLossProof20261117']={'receipt':str(E/'language-specific-adaptation-r1/cpu-loss-reference-r1/result.json'),'state':tiny['state'],'gpuBackendProven':False}
o['cpuRealTrainingFeasibility20261117']=review['newCpuEvidence']['secondAttempt']
live=psutil.pid_exists(current['pid']) and abs(psutil.Process(current['pid']).create_time()-current['createdAt'])<.01
o['currentOwnedNeuralWorker']={'pid':current['pid'],'createdAt':current['createdAt'],'session':79443,'control':str(control),'stateFile':str(control/'run/state.json')} if live else None
o['currentWorkerState']=current['state'] if live else 'NO_OWNED_MODEL_WORKER_FULL_BASE_REFERENCE_TERMINAL'
x['at']=at;x['state']='WEEK_DIRECTION_REVIEW_COMPLETE_FULL_BASE_REFERENCE_'+('RUNNING' if live else 'TERMINAL')
x['next']='The fixed full-large-v3F16 reference is complete and rejected227/709; retain the existing strongest ASR bases. Next quality candidate is one predeclared English meeting-domain adaptation after a workable resource plan, preserving original independent improvement/no-regression gates. Training is optional for overall product work; do not restart the failedCPU119M backprop recipe or separator/VAD/quantization/engine-port/model-size grids.'
# Keep one cumulative timeline entry for this review, replacing its interim
# running snapshot after the exact same inference job becomes terminal.
marker='WEEK_REVIEW_BATCH_20261117'
entry=at+'｜'+marker+'｜Owner要求复盘过去一周并继续推进。复核Nov10原配对及Nov14-17模型结果：质量收敛不顺利，保留专用组合而改变顺序。普通中文5.54→5.14%、英文同整会23.94→18.18%有真实收益，但全部95/98/逐人/事实最终门未过；重叠分离/小头人物适配/FRCRN/VAD补洞/先压缩均有失败依据，停止相同变体。CPU独立TDT损失与梯度6.4秒通过；真实4.15秒样本前向39.66秒，反向开始后退出1，最后提交峰接近2GiB，无完成梯度或更新资格；首轮COW提交2.99GB超声明门失败保留，已只修只读映射/可写参数复制，不继续CPU119M系统。另纠正此前Whisper实际仅TurboQ8，不据此泛化完整large-v3：本轮固定完整F16/同709词/原门；780M缓冲分配失败未识别，CPU映射独立执行，当前'+current['state']+'、完成'+str(len(current['completed']))+'/12。完整模型结果不冒充既有准确率已提升；最新CPU/核显训练允许、温度仅观察，Goal不新建恢复，原资料与最终L未动。复盘收据'+str(target)+'。'
if score:
 entry+=' 完整基座CPU最终227/709=32.0169%WER，比原最佳123/709差，原门拒绝且无参数变体；推理264.88秒/原音265.56秒，全worker328.70秒含60秒准入，私有峰824827904B，全部作业终态回收。还发现原当前索引仍留分离单位修正前指标，已保留旧项并改指18:56最新r19失败：多轮161→319/1476、短回答13→20/87，未重跑模型或改历史评分。'
parts=x['logResult'].split('\n\n');parts=[p for p in parts if marker not in p];parts.append(entry);x['logResult']='\n\n'.join(parts)
write(xfile,x)
print(json.dumps({'review':str(target),'report':str(report.resolve()),'fullBaseState':current['state'],'completed':len(current['completed']),'ownedWorkerLive':live},ensure_ascii=False))
