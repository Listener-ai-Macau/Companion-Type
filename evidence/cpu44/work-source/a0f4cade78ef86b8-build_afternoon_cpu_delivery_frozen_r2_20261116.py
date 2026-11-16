from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=1,memory_bytes=512*1024**2)
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
out=Path('outputs/Companion-CPU与复杂会议阶段交付-20261116-1600-r2').resolve();assert not out.exists();out.mkdir(parents=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def txt(name,text):
 p=out/name;p.parent.mkdir(exist_ok=True);p.write_bytes(text.encode('utf-8'));return p
receipt=read(D/'protection-r43.json');assert receipt['remoteVerified'];qwen=read(B/'qwen-cpu-chinese-characterization-r2/whole-score.json');moss=read(B/'all-cpu-full4-composition-r1/full-score.json');aligned=read(B/'cpu-retained-baseline-join-r4/full-score.json');idle=read(E/'cpu-idle-app-r3/resume-r1/result.json');training=read(B/'meeting-domain-data-r1/export-integrity.json')
assert idle['allOriginalPcmPreserved'] and read(B/'cpu-retained-baseline-join-r4/product-contract.json')['exitCode']==0
sources={
 '原始证据/MOSS-四场整会CPU评分.json':B/'all-cpu-full4-composition-r1/full-score.json',
 '原始证据/QwenCPU-两场中文整会评分.json':B/'qwen-cpu-chinese-characterization-r2/whole-score.json',
 '原始证据/保留原识别文字-CPU时间轴与说话人评分.json':B/'cpu-retained-baseline-join-r4/full-score.json',
 '原始证据/CPU时间轴-共享Rust文档契约.json':B/'cpu-retained-baseline-join-r4/product-contract.json',
 '原始证据/CPU模型-空闲释放与恢复.json':E/'cpu-idle-app-r3/resume-r1/result.json',
 '原始证据/训练数据-完整性与样本统计.json':B/'meeting-domain-data-r1/export-integrity.json',
 '原始证据/训练准备-原生声学参数覆盖.json':B/'meeting-domain-data-r1/acoustic-parameter-coverage.json',
 '原始证据/训练准备-官方入口静态核对.json':B/'meeting-domain-data-r1/training-source-audit.json',
 '原始证据/Windows-并发JSON读取保护.json':E/'windows-reader-retry-r2/result.json',
 '原始证据/CPU时间轴-与历史GPU输出比较.json':B/'cpu-retained-baseline-join-r4/cpu-gpu-output-diagnostic.json',
 '原始证据/源码保护-r43.json':D/'protection-r43.json'}
provenance=[]
for name,p in sources.items():
 target=out/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(p,target);assert sha(target)==sha(p);provenance.append({'file':name,'source':str(p),'sha256':sha(p)})
doc=read(E/'cpu-retained-baseline-join-r4/composed/S_R004S03C01-model-output.json');assert ''.join(x['text'] for x in doc['utterances'])==doc['text']
txt('普通中文会议-保留原识别全文.txt',doc['text'])
def stamp(ms):
 seconds,millis=divmod(ms,1000);minutes,seconds=divmod(seconds,60);return f'{minutes:02d}:{seconds:02d}.{millis:03d}'
lines=['公开单麦会议 S_R004S03C01：匿名发言日志（待复核）',
 '识别文字复用之前较好的原生GPU Qwen结果；本轮CPU执行时间对齐，使用已完整连续推理的CPU Nemotron人物日志。此文件不是重新用CPU ASR取得的5.54%成绩。',
 '匿名编号由模型预测，不是真实姓名。时间为估计发声起点；显示行末不是真实词长。逐人错误率5.80%，仍未达到原5%要求。原始文字、标点、重复和换行保留在同目录识别全文与原始评分中。','']
for row in doc['utterances']:
 label='未归属（需核对）' if row['speaker'] is None else '说话人 '+str(row['speaker']+1)+'（模型匿名分配）'
 lines.extend([f'[{stamp(row["startMs"])} → {stamp(row["endMs"])}] {label}',row['text'],''])
txt('普通中文会议-匿名发言日志.txt','\n'.join(lines)+'\n')
for row in qwen['meetings']:txt('模型原始输出/QwenCPU-'+row['meeting']+'-原始识别.txt',read(row['rawFile'])['text'])
for row in moss['meetings']:
 name=row['meeting'];file=E/'cpu-fixed-whole-r2/composed'/(name+'-raw.json');packet=read(file);txt('模型原始输出/MOSSCPU-'+name+'-含原协议标记.txt',packet['rawDecoded'])
now=datetime.now().astimezone().isoformat();summary={'state':'AFTERNOON_CPU_ENGINEERING_RESULTS_DELIVERABLE_MODEL_QUALITY_NOT_QUALIFIED','generatedAt':now,
 'requestedWorkUntil':'2026-11-16T16:00:00+08:00','neuralDeadline':'2026-11-16T15:40:00+08:00','latestOwnedNeuralProcessFinishedAt':'2026-11-16T15:09:38.475379+08:00',
 'sourceProtection':receipt,'cpuBudget':{'maximumPercent':25,'maximumComputeThreads':4,'privateFamilyGuardBytes':2*1024**3,'actualWindowsLowRamStopRetained':True,'startRecoveryAvailableGiB':3.18},
 'uniqueFullDevelopmentRecordings':4,'uniqueFullDevelopmentAudioSeconds':8629.00325,'blindFinalHoldoutOpened':False,
 'metricUnits':{'English':'word error rate; unchanged original scorer','Chinese':'character error rate; unchanged original scorer','DER':'full original continuous-time zero-collar, includes overlap, from raw multi-voice journal'},
 'mossCpuWholeResults':moss['meetings'],'qwenCpuChineseWholeResults':qwen['meetings'],'retainedNativeAsrCpuAlignmentAndVoices':aligned,
 'cpuIdleMemoryResult':idle,'publicTrainingData':training,'newWeightTrainingThisBatch':False,'priorOptionalSmallAdaptersWereTrainedAndRejected':True,
 'installedDefaultChangedByThisTask':False,'nativeUiAndActualCardOrPhoneTestedThisBatch':False,'customerReleasePackageIncluded':False,
 'internalFixtureExpiresAt':'2026-11-16T15:40:00+08:00','qualityQualified':False,'saleQualified':False,
 'remaining':['Both English full meetings and harder Chinese remain substantially above the original5% raw/per-person error requirement.','Ordinary Chinese retained native raw5.54%, fixed-person5.80%; some individual speakers exceed those averages.','No true word-time accuracy, both overlapping voices, factual minutes, blind final cohort or installed card/phone acceptance.','A new broader meeting-domain acoustic adaptation has not been trained; CPU2GiB cannot fit its ordinary full acoustic+bridge training memory lower bound.','Chinese true cross-meeting participant separation remains unverified.'],
 'provenance':provenance,'limits':limits.query()}
(out/'结果.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
english=[r for r in moss['meetings'] if r['language']=='English'];normal=aligned['meetings'][0];hours=13.09690564236111
report=f'''Companion：CPU与复杂会议阶段交付
生成时间：{now}
用户约定本轮推进至：2026-11-16 16:00（Asia/Shanghai）。本文件的生成时间和模型实际完成时间分别记录，不把等待时间当作训练或功能进展。

结论：纯CPU工程链路、内存回收和可恢复处理已获得实际运行证据；识别模型仍不合格，尚未达到售卖标准。
本轮没有训练新权重。此前11月15日确实训练过小型语言/声学适配器，因收益不足或回退而未采用，本报告保留这段历史。

1. 没有独显时能做什么
已实跑CPU ASR、原生时间戳分类器和连续说话人模型。显卡可以加速开发推理和训练，但不能作为用户安装后的必需前提。
在本机已授权的约25% CPU、最多4计算线程下，Qwen固定Q8组件完成两场中文完整原音：72.94分钟音频，纯ASR计算约30.20分钟，所有147窗均自然结束。这个速度证明此机器能用CPU处理长录音，并不等于质量达标或适用于所有电脑。
CPU Nemotron对四场完整原音（共143.82分钟）连续计算约6分21秒，保持每场从源起点的一份连续人物状态。没有把真实说话人数或参考文字输入模型。
原生CPU时间戳分类器对一场38.79分钟完整会议的79叶处理结束，非空76叶实际分类计算约322.68秒；复用了旧原生GPU ASR文字，不能把这项称为更好原文的全CPU重识别。

2. 内存与恢复的实际变化
本任务CPU ASR模型在15秒无可执行工作后主动关闭native模型，保留轻量worker、原音和已接受结果。有新音频并且原启动内存条件满足时再加载。
实际暂停测试：常驻 {idle['idleRelease']['beforeWorkingSetBytes']} B → {idle['idleWorkerRssBytes']} B（约41.41 MiB），私有约30.77 MiB，确认模型权重映射消失。恢复后同一worker加载2次；之前已接受的前30秒没有重算，原PCM和缓存文件SHA保持，最后文字与前次CPU应用测试逐字一致。
结束后只补CPU人物日志，复用了全部识别结果；已完成缓存重开约0.25秒，没有新神经计算。“结束后补人物日志约6.766秒”从ASR缓存已完成时起算，不代表录音停止到最终完成的总耗时。
Qwen长录音任务的常驻页上限约1.75 GiB，私有内存保护仍为原2 GiB，真实Windows低内存停止与3.18 GiB启动/恢复门保持。本任务没有关闭用户软件、防护或修改驱动/网络。
长时间CPU对齐进程曾累积内存并触发2 GiB家族保护，观测峰值超过门限，失败原样留存。修复采用无状态对齐器每进程最多16叶，不改音频切分或模型计算；保留已完成61叶，仅补18叶。两批私有峰值约1.23/0.64 GiB。连续人物模型没有按叶重置。
Windows并发JSON发布/读取和深缓存路径问题均有实际复现与修复。新读取保护只对Windows临时共享/权限冲突有界重试3秒，永久拒绝和坏JSON仍失败。

3. 质量：原门槛保持，失败候选不升级默认
原要求：原始字/词错率与逐人错误率<5%，人物日志DER≤10%，纪要事实≥95%且关键事实错误0。以下完整录音都是已经暴露的开发/回归会议，不是最终盲测。
英文按词错率WER，中文按字错率CER；这些百分数的计数单位不同，不能直接解释为中文比英文“准确几倍”。

MOSS固定30秒CPU完整会议结果：
'''
for row in moss['meetings']:
 report+=f"  {row['meeting']}：原始错误率 {row['rawText']['errorRate']*100:.4f}%（{row['rawText']['errors']}/{row['rawText']['referenceUnits']}）；原基线 {row['baselineRawText']['errorRate']*100:.4f}%；原始多声人物DER {row['primaryRawJournalDER']['DER']*100:.4f}%。\n"
report+='\nQwen固定Q8 CPU中文组件刻画：\n'
for row in qwen['meetings']:
 report+=f"  {row['meeting']}：{row['rawText']['errorRate']*100:.4f}%（{row['rawText']['errors']}/{row['rawText']['referenceUnits']}），原生基线 {row['nativeBaselineRawText']['errorRate']*100:.4f}%。两场均回退。\n"
report+=f'''
普通中文较好的原生ASR原文保留，CPU对齐+连续CPU人物日志组合：原字错率{normal['rawText']['errorRate']*100:.4f}%（461/8325），固定整会人物映射的逐人错误率{normal['personTextFixedOriginalActivityIdentity']['errorRate']*100:.4f}%（483/8325），原始多声DER{normal['originalReferenceRawContinuousSpeakerDER']['DER']*100:.4f}%。逐人总体错误率与原基线相同，但001-M约9.98%、005-F约7.21%，不能用总体均值遮住个别人失败。匿名人物编号不是实际身份。
此组合完整保留原识别文字、标点、重复和换行，输出通过共享Rust文档契约。时间轴为预测onset±60ms的既定产品策略，真实词长精度没有合格证明；302个零长/无效预测词区间仍保留原始证据。
此前新拼接器误用了较早整词区间规则并漏拼换行，导致13.57%逐人错误与格式失败；已保留失败，修复精确复用当前默认R8同SHA的既有拼接函数，所有79份模型结果复用，没有为此新增识别或对齐计算，也没有改参考标签或门槛。

固定英语专用Whisper Q8对照也未通过：195/709=27.50%，相同输入MOSS124/709=17.49%、原Qwen141/709=19.89%；按事前标准拒绝，不继续做量化/提示网格。195错中178为其他词汇错误、17为语气词，删掉语气词不能解决质量。
MOSS在英文部分场景改善，但完整中文回退；Qwen CPU通用移植在英文和完整中文均存在回退。默认较好版本保留，本轮内部fixture没有安装为日用默认。

4. 训练准备与下一条收敛路径
已整理22场完整公开会议，约{hours:.4f}小时原音（10英文、12中文）；原计划另外2场英文来源分别403/404，失败保留，没有绕过限制。
944条、约2.8128小时非重叠声学训练输入已逐WAV/PCM/原音帧核验；其中另有190条严格“多人轮流、不重叠”的训练索引（57.93分钟）。两套数据的事件有包含关系，不能把时长简单相加或宣称1134条互不重复样本。
音频未重采样、未加噪，所选原标签字符保留，验证会议排除；最终L_R003S03C02未打开。中文001-M等是会议内局部标签，真实跨会议人员隔离仍未证明，不能冒充已验证的新说话人泛化。
旧末8层Q/V声学LoRA只训练262144参数且已失败；下一次不把改rank/阈值当新方向。计划在成熟底座上做一次更宽的会议域声学编码器+桥接适配，先A轮流发言，再B重叠，再C噪声，并沿用跨会中英不回退与原质量门。
这仍是待训练设计。约317477504个声学+桥接参数的普通CPU Adam，仅BF16权重/梯度、FP32双动量与冻结语言模型就约7.25 GB，不含激活、运行时和检查点；当前2 GiB任务预算不能承载。用户无需独显运行产品与开发阶段需要合适训练资源是两件分别验证的事。
官方训练入口已固定到9567667698f195fa807b1581de5c03184e63d2b0做静态审计；社区报告了prefix mask/梯度缩放问题，但未在本任务当前运行时重现，旧自定义单样本mask/手动梯度另有检查，不能把旧适配器失败归因于该社区报告。
下一次权重训练前还要验证真实标签mask、累计梯度、实际可训练模块、保存重载、CPU转换不回退，并解决可用训练资源与真实人员隔离。数据整理和源码保护不等于模型准确率提升。

5. 交付边界与复核
本包是阶段结果、可读原始转写、代码版本和证据索引；不是客户可安装的正式模型发布包。
内部CPU fixture r5仅用于本任务验证，绝对模型运行截止为2026-11-16 15:40；不将这个会到期的验证fixture冒充永久可用的交付安装包。默认local-package-r8与用户系统设置未由本任务改装。
本轮直接执行版本化后台命令schema，验证了录中处理、暂停回收/恢复、离线补全与缓存复用；未声称实卡、手机或已安装原生UI通过。复杂重叠双路文字、跨域盲测、真实词级时间准确率及纪要事实尚未合格，售卖状态保持OPEN。
源代码已私有提交并独立远端回读：{receipt['modelCommit']}（分支research/moss-resume-20261105）。失败与回退证据同批保留。
本批最后神经任务已于15:09:38结束；后续为结果复核、源码保护和交付整理，不以重复模型计算填满约定时段。

公开来源与数据说明：
AMI官方训练数据与标注：https://groups.inf.ed.ac.uk/ami/corpus/datasets.shtml
AISHELL-4官方发布：https://www.openslr.org/111/ ，官方标注CC-BY-SA4.0；镜像Apache2标签有冲突，保留官方来源，未认定商用发布已完成条款核对。
Qwen官方微调说明：https://github.com/QwenLM/Qwen3-ASR/blob/main/finetuning/README.md
训练入口社区报告：https://github.com/QwenLM/Qwen3-ASR/issues/216
模块化分人与Qwen域适配研究：https://arxiv.org/abs/2607.08208v2 （两人对话研究，不能直接证明本产品多人会议已达标）。
本包不分发原始训练录音、原训练标签JSONL、模型权重或运行时二进制。模型生成转写与原始评分供复核，出处与绝对源路径/哈希见结果.json。
'''
txt('说明.txt',report)
manifest=[]
for p in sorted(out.rglob('*')):
 if p.is_file():manifest.append({'file':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
(out/'文件清单.json').write_text(json.dumps({'generatedAt':now,'files':manifest,'scope':'Only generated report/results and source-version receipts; no raw training data, model weights or runtime binaries.'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archive=out.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(out.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(out.parent).as_posix())
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
assert (out/'普通中文会议-保留原识别全文.txt').read_bytes()==doc['text'].encode('utf-8')
for item in manifest:assert sha(out/item['file'])==item['sha256']
delivery={'state':summary['state'],'directory':str(out),'archive':str(archive),'archiveSha256':sha(archive),'files':len(manifest)+1,'modelCommit':receipt['modelCommit'],'qualityQualified':False,'saleQualified':False,'customerReleasePackage':False}
(B/'afternoon-delivery-r2.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(delivery,ensure_ascii=False))
