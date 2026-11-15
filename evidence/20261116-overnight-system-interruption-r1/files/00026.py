"""Reconcile a rebooted run without restarting inference or changing original evidence."""
from pathlib import Path
from datetime import datetime
import hashlib, json, sys, re, psutil

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
RUN=E/'staged-r4'
OUT=Path('C:/Users/Billy/Documents/Codex/2026-11-14/xu-y/outputs/Companion-整夜会议模型结果-20261116')
OUT.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

interruption=read(C/'overnight-system-interruption-r1/interruption.json')
assert not psutil.pid_exists(14144) and not psutil.pid_exists(11636)
partial=read(RUN/'ES2003b-partial-ids.json')
assert partial['notFinal'] and len(partial['generatedIds'])==4064
sys.path.insert(0,'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
from tokenizers import Tokenizer
tokenizer=E/'native-model/tokenizer.json'
raw=Tokenizer.from_file(str(tokenizer)).decode(partial['generatedIds'],skip_special_tokens=False)
assert 'torch' not in sys.modules
(OUT/'ES2003b-部分输出-原始文本.txt').write_text(raw,encoding='utf-8')
# Only add line breaks for readability, retaining every character of the model text.
readable=re.sub(r'(?=\[\d+(?:\.\d+)?\])','\n',raw).lstrip('\n')
header=('未完成转写，仅供查看已保存的模型输出，不构成整会结果或质量验收。\n'
        '公开会议：AMI ES2003b，原音35分09.813秒，单麦Array1-01。\n'
        '保存4064个原生成token；无自然结束标记；未读取参考文本纠正。\n'
        '说话人编号与时间是模型预测，未经核对；末尾可能中断在一句话或时间标签内。\n'
        '本文件只添加换行便于阅读；原始字符全文另存，禁止把这部分当完整会议评分。\n\n')
(OUT/'ES2003b-部分转写-可阅读.txt').write_text(header+readable,encoding='utf-8')
manifest=E/'staged-r2/cache/ES2003b/manifest.json'
recovery={'at':datetime.now().astimezone().isoformat(),'state':'RECOVERY_INPUTS_RETAINED_DO_NOT_AUTORUN_AFTER_BUGCHECK',
 'originalRunUnmodified':str(RUN/'run.json'),'originalRunSha256':sha(RUN/'run.json'),
 'interruption':interruption,'generatedIds':str(RUN/'ES2003b-partial-ids.json'),
 'generatedIdsSha256':sha(RUN/'ES2003b-partial-ids.json'),'generatedTokenCount':4064,
 'tokenizer':str(tokenizer),'tokenizerSha256':sha(tokenizer),
 'fullPromptCacheManifest':str(manifest),'fullPromptCacheManifestSha256':sha(manifest),
 'originalAudioSha256':partial['audioSha256'],'fullPromptTokens':27924,
 'rawText':str(OUT/'ES2003b-部分输出-原始文本.txt'),'rawTextSha256':sha(OUT/'ES2003b-部分输出-原始文本.txt'),
 'newGpuInferenceAfterReboot':False,'newWeightTraining':False,'wholeMeetingsCompleted':0,
 'wholeQualityScoresProduced':0,'qualityQualified':False,'productDefaultChanged':False,
 'resumePreconditions':['Establish a stable deployment environment after system bugcheck; do not blindly retry the same Windows HIP path.',
 'Verify retained cache files against manifest, original audio and exact generated prefix hashes.',
 'Fresh numerical/native-token control must pass before replaying the retained generated IDs with no reference-word corrections.',
 'Retain CPU5%, family-private2GiB and actual-low-RAM protections; preserve complete context and frozen scoring protocol.'],
 'notAnAutomaticResumeCommand':True,'privateMemoryDumpsCollectedOrPublished':False}
write(OUT/'恢复输入与中断核对.json',recovery)
write(C/'overnight-system-interruption-r1/reconciliation.json',recovery)

report='''Companion 整夜会议模型推进结果｜2026-11-16 早07:30交付批次

结果：未完成计划的四场完整会议对照，没有新的准确率验收结果，也未达到销售标准。
实际作业因整机异常重启中断；不能将00:16之后到早上的时间算成有效计算时间。

已做成的技术变化
1. 在保留完整单麦会议上下文的情况下，ES2003b的71个音频窗口、27924个输入token预填充完成。
   固定KV存储与已填前缀视图把该阶段进程族私有内存峰值控制在约1.35GiB；原2GiB保护未提高。
2. 完整原精度KV与首步logit落盘，恢复时做逐值核对；未拆成互不关联的说话人小片段。
   公开61秒控制音频，原生成前缀回放8步、续写8步，与原native实现的16个token严格一致。
   这是运行与续作控制，不是识别质量或整会通过证明。
3. 首场公开会议保留4064个原生成token，未自然结束。已导出原始字符与可阅读的部分文本。
   无人工补字、无按参考标签改词、无生成后删除错误内容，未将部分片段作为完整会议评分。

失败与中断
先前一次长解码在2294个生成token后发生HIP C++异常，栈在GPU停止检查同步处呈现；具体异步起因未证实。
改用CPU持有相同贪心token/EOS规则，通过短控制并保留原前缀续写；最新保存于00:14:43，为4064token。
Windows记录00:16:45启动、00:16:48 Kernel-Power 41，BugcheckCode257，即0x101 CLOCK_WATCHDOG_TIMEOUT。
Microsoft文档将其解释为次级处理器未及时收到预期时钟中断；仅凭错误码不能判定模型、显卡驱动或硬件哪项负责。
重启后原作业与监督进程均退出，没有自动续跑。早07:10恢复检查时发现中断，随后只做CPU导出、证据保护和状态核对。
原run.json因重启没有finally而残留RUNNING，已用独立reconciliation.json纠正当前状态，原文件原样保留。

当前仍未完成
完整四会转写0/4，新候选完整质量评分0/4；没有新训练权重，没有替换产品默认模型。
中英文跨会议、每人文字、完整说话人日志、事实与噪声/重叠鲁棒性仍需通过原有门槛。
既有基线未提高，也没有用这次部分输出宣布英文或中文准确率提升。最终留出会议未打开。

下一步收敛路径
第一关先解决完整会议长时运行的稳定性，保留已有缓存和原输出，不在同条件下盲目重复整夜HIP运行。
系统错误需保留并结合可用崩溃证据定位；选择能证明稳定的执行环境后，先严格数值/续写控制，再完成同四场原会议。
第二关按冻结的完整原字与说话人评分，比较联合模型和原组合基线。只有实际跨会改善，才进入公开会议领域适配。
多人不重叠先验收，再重叠、再噪声；产品保持增量草稿与离线完整终稿双阶段。
不会因为这次失败直接从零训练，也不会据错误码直接购卡、改驱动或开通付费云。

本批材料
ES2003b-部分转写-可阅读.txt：直接查看保留的模型部分输出。
ES2003b-部分输出-原始文本.txt：未加换行的原始解码字符。
恢复输入与中断核对.json：精确原输出、原音、tokenizer与完整缓存的哈希及恢复前置条件。
代码及小体积证据沿用同一私有研究分支保护；大体积原音、权重和KV仅保留本地与清单哈希。

官方解释：https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-0x101---clock-watchdog-timeout
模型来源：https://github.com/OpenMOSS/MOSS-Transcribe-Diarize
'''
(OUT/'07点30交付说明.txt').write_text(report,encoding='utf-8')

p=Path('work/bilingual_progress.json');d=read(p)
d['state']='OVERNIGHT_SYSTEM_REBOOT_INTERRUPTED_NO_COMPLETE_MEETING_RESULT'
d['qualityQualified']=False;d['saleQualified']=False
d['next']='先核对00:16整机0x101异常与可用崩溃证据，保留完整缓存和4064原token，不在同条件下盲目重跑长时Windows HIP。具备稳定执行环境后严格复现原数值/续写控制，再完成原4完整开发会冻结评分，对比联合模型与原组合；实际跨会提升才进入领域适配。A多人不重叠→B重叠→C噪声顺序、原字/逐人/DER/事实门与资源保护保持。'
o=d['ownerOvernightRun20261115'];o.update(currentState=d['state'],activePid=None,activePidCreatedAt=None,activeMeeting=None,
 noOwnNeuralProcessActive=True,lastMeeting='ES2003b',retainedRealGeneratedPrefixTokens=4064,
 interruption=interruption,reconciliation=str(C/'overnight-system-interruption-r1/reconciliation.json'),
 report=str(OUT/'07点30交付说明.txt'),partialTranscript=str(OUT/'ES2003b-部分转写-可阅读.txt'),
 wholeMeetingOutputs=0,newCandidateWholeQualityScores=0,noNewNeuralInferenceAfterReboot=True,
 failedToCompletePlannedWholeMeetingComparison=True)
j=d['jointArchitecture20261115'];j.update(state=d['state'],qualityConclusion='整会运行可行性仍未证明；完整预填充与续作控制通过，系统重启前只得部分输出，无新完整质量分数。',nextExecutableGate=d['next'])
d['logResult']+='\n'+datetime.now().astimezone().isoformat()+' 早间核对：最后原生成保存00:14:43/4064token，系统00:16:45异常重启，Event41 Bugcheck257=0x101，具体故障组件未证实；00:16后作业未自动恢复，不能称整夜有效运行。原PID14144/11636均不存在，原RUNNING文件保留另设reconciliation纠正。完整四会0/4，新候选完整评分0/4，无新训练/默认替换/售卖通过。完整27924token缓存/4064原ID保留，CPU仅导出原字符与带未完成标识阅读版；重启后不再启动GPU推理。下一关先稳定部署再原四会比较，不盲目同条件HIP重试，保留原全部字门与最终留出。'
write(p,d)
print(json.dumps({'output':str(OUT),'state':d['state'],'generatedTokens':4064,'rawChars':len(raw),'wholeMeetingResults':0,'torchImported':False},ensure_ascii=False))
