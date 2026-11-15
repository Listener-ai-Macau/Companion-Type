"""Reconcile owner architecture steering and measured failures into one workpoint."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=ROOT/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
now=datetime.now().astimezone().isoformat()
pilot=read(E/'native-runtime-r1/run.json')
native=read(E/'whole-run-r1/run.json')
cpp=read(E/'cpp-r1/whole-r1/run.json')
assert pilot.get('finishedAt') and native.get('finishedAt') and cpp.get('finishedAt')
assert not native['qualityQualified'] and not cpp['qualityQualified']
owner='我觉得你这些小条小配很难达成我们的目标吧？是不是要考虑更加大幅度或者大跨越的一个开发方式？不然一直在这里感觉尝试也没什么特别大的意义。'
decision={
 'at':now,'state':'ARCHITECTURE_GATE_OPEN_JOINT_CANDIDATE_NOT_DEPLOYABLE_UNDER_CURRENT_RUNS',
 'ownerQuote':owner,
 'decision':'Stop threshold/gap/auxiliary-head variants and tiny rejected adaptation loops. Compare complete meeting architectures before further meeting-domain training.',
 'baseline':'Retain validated local Qwen/Nemotron/aligner combination and raw original scores; do not adopt failed candidates.',
 'candidate':'MOSS-Transcribe-Diarize0.9B joint words/speaker/timestamps, reused pretrained weights, not training from scratch.',
 'candidateHistory':'Same family previously failed author custom long-context runtime. This batch changed to official native Transformers, then a pinned C++/Vulkan port; not a newly discovered larger model.',
 'nativeTensorIdentityProof':str(C/'tensor-reuse-proof.json'),
 'portPrecision':'Pinned upstream BF16 GGUF, not locally claimed tensor-identical to native HF payload.',
 'completedInference':'Native Transformer runtime emitted natural-EOS outputs for two180-second public training recordings. This is compatibility evidence, not complete-meeting quality.',
 'nativeWholeFailure':{'run':str(E/'whole-run-r1/run.json'),'state':native['state'],
  'observed':'First35-minute ES2003b input encoded; full context prefill hit LLVM out-of-memory/access violation and owned-family memory protection before any complete transcript.',
  'rootCauseLimit':'Compiler/runtime allocation failure. No evidence that this measures recognition ability; exact failing operator not established.'},
 'cppFailure':{'run':str(E/'cpp-r1/whole-r1/run.json'),'state':cpp['state'],
  'observed':'Actual6800XT Vulkan selected and BF16 model loaded; initial2048-token KV allocation234881024B failed while opening session, with job peak2172166144B under2GiB protection. No smoke or full transcript.',
  'sourceAudit':str(C/'cpp-r1/allocation-source-proof.json'),
  'rootCauseLimit':'Native allocation failed at the memory boundary; do not claim all16GiB VRAM was physically exhausted. Lowering65536 context cannot fix initial2048-token allocation. No same-run retry, quantization grid, or guard increase.'},
 'qualityConclusion':'No complete candidate transcript exists; no architecture superiority, new accuracy, sale readiness, or D2 completion claimed.',
 'retainedPriority':['A: original single-mic sequential speakers, no overlap first','B: overlapping speakers after A','C: noise/room robustness after B'],
 'nextExecutableGate':'Before any further full inference or adaptation, establish a source-level change that bounds full-context compute and compiler allocations under existing resource guards and passes native numerical controls. The failed unchanged paths remain stopped. Stop this candidate if deployment feasibility cannot be established; do not feed more training into it.',
 'qualityComparisonGate':{'developmentMeetings':['ES2003b','S_R004S03C01','EN2002a','20200623_S_R001S07C01'],
  'minutes':143.81672083333334,'allOriginalAudio':True,
  'splitDisclosure':'These four complete recordings are previously seen development/regression cases, not a blind final test. They cannot establish unseen-room generalization alone.',
  'preserve':'Original raw text/person error<5%, zero-collar DER<=10%, facts>=95% and critical errors0 unchanged. No reference prompts, true speaker counts, per-meeting rules, or filler/number cleanup.',
  'finalHoldoutOpened':False,'originalBaselineInferenceRerun':False},
 'trainingGate':'Only after deployment and cross-meeting quality gates pass: a coherent public-meeting domain adaptation of the selected pretrained task, with meeting/person/room-disjoint train/dev/test manifests and no reference-driven sampling. No new weights trained in this batch.',
 'productDirection':'Incremental local draft during upload, then whole-session final words and stable persons; offline file imports use the same final engine. This is the architecture direction, not an already shipped joint default.',
 'assessmentCorrection':{'englishOriginalTimingDerNotProofOfLostSpeech':True,
  'evidence':str(C/'activity-diagnosis-correction.json'),
  'originalEnglishWerStillFailing':True,'originalScoresUnchanged':True,
  'languageMetricCaution':'Chinese CER5.80% and English WER19.89% are different units. Same lexical-character diagnostic gives English328/2794=11.74%, Chinese73/1258=5.80%; recordings and linguistic structure still differ.'},
 'resourceContract':{'cpuPercent':5,'ownedFamilyPrivateBytes':2147483648,'actualWindowsLowMemoryStop':True,'oneNeuralFamily':True,'unchanged':True},
 'newWeightTraining':False,'shippedDefaultChanged':False,'qualityQualified':False,'saleQualified':False,'D2Complete':False}
(C/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');record=read(p)
record['ownerLatestArchitectureSteering20261115']={'at':now,'quote':owner,
 'precedingRequest':'为什么中文跟英文差这么远；分别修，解释自训还是调参，目标必须通用，不能一个会议解了就算。'}
record['jointArchitecture20261115']=decision
record['state']='ARCHITECTURE_ROUTE_REASSESSMENT_NATIVE_PILOT_PASSED_WHOLE_RUNTIME_FAILED_NOT_QUALIFIED'
record['qualityQualified']=False;record['saleQualified']=False
record['next']='按Owner架构收敛优先：停止阈值/补洞/辅助头及小样本无收益变体；先判断联合文字/人物/时间主干在原CPU5%/族私有2GiB/真实低RAM保护下的完整会议可部署性。原生TF短训练音频已过，整会LLVM/内存失败；固定C++ BF16端在初始2048token KV分配失败，两路径保留并停止，不降上下文/提限/量化扫参。只有明确源头级有界执行改变并过数值控制才再跑同4完整开发会，原组合基线复用；可部署和多会质量未过不训练或切默认。英文原时间标注DER不等价实际漏语音，先核历史参考审计，保留原门/原分。A轮流无重叠优先，B重叠/C噪声、自然混说、实卡双端/D1延迟及D2售卖均仍待完。'
entry=(f'\n{now} Owner明确质疑零散小调并要求更大跨越，转为架构级止损：冻结原组合为对照，只选同已有MOSS0.9B联合文字/人物/时间主干做完整会议架构验证，不把它说成新9B模型。复用旧权重逐张量重构官方native HF整文件SHA通过；新native实跑中英文两条180s训练音频自然EOS，峰约1.28GiB，非质量成绩。完整35分钟ES2003b71声学窗已编码，但27924token长上下文prefill触发LLVM out-of-memory/0xC0000005和2GiB族保护，0整会输出。随后固定v0.4.2原生C++/Vulkan实际核ABI/6800XT并载入BF16端，打开会话的初始2048token KV234881024B分配失败，Job峰2172166144B；未做完61s烟测或整会，停止未自动重试、未改资源门/默认。此为部署阻塞，不能称新架构质量收益，四个143.82min原会仍是已见开发防回退而非盲测。回溯原12:11/12:36参考审计发现相同英语输出换外部MFA诊断时间后ES2003b DER26.02→6.69、EN2002a31.08→15.97，外部也未经独立人工核验，原门和原分不换；撤回把时间漏检主因直接等同真实漏话的推断。统一字单位仅诊断EN11.74% vsZH5.80%，原英文WER19.89%与人物WER34.41%仍失败；不删填充/儿化/数字降分。下一步先部署可行性→完整多会选架构→公开会议/人物/房间隔离的成体系域适配→A后B/C→产品双通路，不继续无效微调。新权重训练0、默认未变、最终holdout未打开，原D1/D2/售卖门未关闭。')
assert entry not in record['logResult'];record['logResult']+=entry
p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
subprocess.run([sys.executable,'work/record_bilingual_progress.py',str(p)],check=True)
print(json.dumps({'decision':str(C/'decision.json'),'state':record['state']},ensure_ascii=False))
