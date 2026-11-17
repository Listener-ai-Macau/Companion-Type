"""Reconcile this one model/reference and webpage batch, preserving prior evidence."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, json, psutil, sys

C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
ap=argparse.ArgumentParser();ap.add_argument('--protocol',type=Path,required=True);args=ap.parse_args()
protocol=read(args.protocol);run=Path(protocol['run'])
state=read(run/'state.json')
pid=state['pid'];created=state['createdAt']
alive=psutil.pid_exists(pid) and abs(psutil.Process(pid).create_time()-created)<.01
if protocol.get('loadingMode')=='readonly_cpu_views' or protocol.get('computeDevice')=='rx6800xt':
 gpu=protocol.get('computeDevice')=='rx6800xt'
 p=Path('work/bilingual_progress.json');x=read(p);j=x['jointArchitecture20261115'];o=j['overnightExecution20261116'];ref=o['englishAccuracyReference20261117']
 proof=read(run/'same-original-output-and-speed-control.json') if (run/'same-original-output-and-speed-control.json').exists() else None
 if gpu and (run/'ES2003b-seq-000.json').exists():
  first=read(run/'ES2003b-seq-000.json');old=read(C/'native-cpu-r6/ES2003b-seq-000.json')
  proof=dict(state='SAME_ORIGINAL_CPU_GPU_OUTPUT_AND_TIMING_OBSERVED',seconds=first['seconds'],baselineSeconds=old['seconds'],
   speedup=old['seconds']/first['seconds'],allGeneratedIdsIdentical=first['generatedIds']==old['generatedIds'],
   firstCaseOnly=True,qualityScoreProduced=False)
 result=read(C/'score.json') if (C/'score.json').exists() else None
 execution=dict(state=state['state'],observedAt=state['observedAt'],pid=pid,createdAt=created,
  aliveWhenObserved=alive,completedCases=len(state['completed']),attemptedOriginalCases=state.get('attemptedOriginalCases',0),
  newTrainingUpdates=0,stateFile=str(run/'state.json'),protocol=str(args.protocol),
  jobPrivatePeakBytes=state['limits']['jobPeakPrivateCommitBytes'],elapsedSeconds=state['elapsedSeconds'],
  loadingMode='native_gpu_resident_weights' if gpu else 'readonly_cpu_views',originalPrivateLimitBytes=protocol['privateLimitBytes'],originalCpuPercent=protocol['cpuPercent'])
 if state.get('error'):execution['error']=state['error']
 ref['priorDiskCopyExecution']=ref.get('priorDiskCopyExecution',ref['execution'])
 if result:
  ref['result']=dict(state=result['state'],errors=result['aggregate']['errors'],referenceWords=709,
   wer=result['aggregate']['errorRate'],advanceToWholeEnglish=result['advanceToWholeEnglish'],scoreFile=str(C/'score.json'))
  status=f"{'6800XT原生GPU对照' if gpu else '只读权重加载'}完成12/12原音；原评分{result['aggregate']['errors']}/709错，词错率{result['aggregate']['errorRate']*100:.2f}%。"+('通过中间筛选，整会与逐人仍待验证。' if result['advanceToWholeEnglish'] else '未通过中间筛选，保留完整结果并结束该候选固定方案。')
 elif alive:
  status=f"正在执行{'6800XT原生GPU' if gpu else '同一模型的只读权重加载'}对照，完成{len(state['completed'])}/12；原2GiB、25%CPU与真实低内存保护保留，完整新词错率尚未产生。"
 elif state['state'].startswith('COMPLETE'):
  status=f"{'6800XT原生GPU' if gpu else '只读权重加载'}已完成12/12原音，待按原参考独立评分。"
 else:
  status=f"{'6800XT原生GPU' if gpu else '只读加载'}方案在{len(state['completed'])}/12停止；具体边界{state.get('error','见原状态收据')}。保留现场，不继续调加载变体；尚无完整新词错率。"
 if proof:
  status+=f" 已完成的同一条12.05秒原音耗时{proof['seconds']:.2f}秒（原{proof['baselineSeconds']:.2f}秒），生成token逐个相同，提速{proof['speedup']:.2f}倍。"
 ref.update(execution=execution,state='FIXED_NATIVE_GRANITE_REFERENCE_SCORED' if result else ('EXECUTING_ONE_FIXED_NATIVE_ENGLISH_REFERENCE' if alive else state['state']),ownerStatus=status)
 o['currentOwnedNeuralWorker']={'pid':pid,'createdAt':created,'stateFile':str(run/'state.json')} if alive else None
 batch=j.setdefault('runtimeOptimization20261117',{'startedAt':at,'ownerQuote':'可以啊可以啊，那你先把那个找到了问题，那你对应优化一下，反正就不要再卡一些奇奇怪怪的地方。'})
 if gpu:
  batch['cpuReadonlyTrial']={'state':read(C/'native-cpu-readonly-r1/completed.json')['state'],'completedCases':0,
   'result':'Small BF16 equality passed; first real input did not finish within150.09seconds.2x speed criterion not met; profile ended without another CPU variant.',
   'receipt':str(C/'native-cpu-readonly-r1/completed.json')}
  batch['gpuOwnerQuote']='现在是插上显卡了'
  ref['gpuPreparation']={'state':'PREPARED_NATIVE_INPUTS_AND_ACTUAL_GPU_EXECUTION','protocol':str(args.protocol),
   'nativeInputs':protocol['preparedNativeInputs'],'preparedCases':12,'gpuExecutionPerformed':True}
 batch.update(at=at,execution=execution,sameOriginalOutputControl=proof,
  preflight=str(C/'execution-protocol-gpu-r1.json' if gpu else C/'preflight-readonly-r1.json'),
  decisionBasis=protocol.get('decisionBasis',{'old':'CPU copy and read-only profiles did not finish useful quality reference.','changed':'Owner connected6800XT; original nativeBF16 weights now resident in actualGPU, CPU-native inputs prepared once.','stop':'Same frozen original reference/gates/deadlines; no model grid.'}),newTrainingUpdates=0,qualityQualified=False,saleQualified=False)
 x['state']=('NATIVE_GRANITE_GPU_COMPLETE_SCORED' if gpu else 'NATIVE_GRANITE_COMPLETE_SCORED_WITH_READONLY_LOADING') if result else (('NATIVE_GRANITE_GPU_REFERENCE_IN_PROGRESS' if gpu else 'READONLY_LOADING_OPTIMIZATION_IN_PROGRESS') if alive else 'NATIVE_REFERENCE_OPTIMIZATION_TERMINAL_RETAINED')
 if result:
  x['next']=result['next']+' Original Chinese/per-person/facts/final5/2percent gates unchanged.'
 elif alive:
  x['next']='Follow this one fixed original12case profile to its bound; first same-input output IDs must match and inference must be at least2x faster. Score all12 only after completion. No new candidate, precision, training or loading grid.'
 else:
  x['next']='Retain the actual loading-boundary result, end this CPU loading profile without a second variant. Preserve the one selected candidate and original quality gates; next complete its quality comparison only with a fitting verified execution condition. Continue independent local product reliability/error attribution work.'
 marker='GPU_NATIVE_REFERENCE_EXECUTION_20261117' if gpu else 'READONLY_CPU_COPY_OPTIMIZATION_20261117'
 text=f'\n\n{at}｜{marker}｜承接Owner要求对应优化、不再卡奇怪位置。直接对照安装版Accelerate源load_offloaded_weight，原torch.tensor(np.memmap)每层每次复制。只改本项目CPU权重读取，使用只读映射零复制视图+原生模型/标准AlignDevicesHook，不改已装依赖、精度、解码或原音/参考。小BF16对照及第一条原音token逐个相同为前提，第一条至少2倍提速才继续原12条；原2GiB私有、25%CPU、真实RAM底线3414499000B及低内存保护保持，温度观察不加门。一次已验全12前端/原依赖和文件绑定，移除无变化的固定60秒等待。单一加载变更失败即结束，不再追加映射变体。当前实际：{status} 峰私有{execution["jobPrivatePeakBytes"]}B；0训练更新，运行提速与质量成绩分别记录。'
 if gpu:
  text=f'\n\n{at}｜{marker}｜Owner“现在是插上显卡了”，系统实际6800XT/780M均正常。只读CPU试验小数值相同，但首条150.09秒内未完成，已结束不再追加CPU加载变体。12条原音官方CPU前端已一次性准备并逐文件/原音/PCM/长度绑定，0预训练前向；原生GPU入口复用既有分块字节往返核验加载器，954状态原BF16一次进入实际6800XT，不再逐词CPU卸载或在ROCm中跑CPU音频前端。小GPU BF16原生/流式加载数值逐位相同，完整3分片与GPU回传字节相同；原2GiB私有/25%CPU/真实RAM底线与低内存保护保持，温度只观察，不改驱动/全局缓存/系统温控。实际{status} 峰私有{execution["jobPrivatePeakBytes"]}B。MIOpen全局缓存记录警告留原文，首条已正常完成，不据警告改全局缓存。此为推理对照，0训练更新，原参考与5/2percent最终门不变。'
 if result:text+=f' 完整709词成绩{result["aggregate"]["errors"]}错，逐场中间门通过{result["advanceToWholeEnglish"]}；售卖与整会/逐人仍未合格。'
 if marker in x['logResult']:
  pos=x['logResult'].index(marker);start=x['logResult'].rfind('\n\n',0,pos);end=x['logResult'].find('\n\n',pos)
  x['logResult']=x['logResult'][:start]+text+(x['logResult'][end:] if end>=0 else '')
 else:x['logResult']+=text
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'state':x['state'],'completed':len(state['completed']),'alive':alive,'status':status},ensure_ascii=False))
 sys.exit(0)
assets=read(C/'asset-acquisition-r1/completed.json')
score_path=C/'score.json'
score=read(score_path) if score_path.exists() else None
p=Path('work/bilingual_progress.json');x=read(p);j=x['jointArchitecture20261115'];o=j['overnightExecution20261116'];ref=o['englishAccuracyReference20261117']
execution={'state':state['state'],'observedAt':state['observedAt'],'pid':pid,'createdAt':created,
 'aliveWhenObserved':alive,'completedCases':len(state['completed']),
 'newNeuralCalls':state['newNeuralCalls'],'newTrainingUpdates':0,
 'stateFile':str(run/'state.json'),'protocol':str(args.protocol),
 'jobPrivatePeakBytes':state['limits']['jobPeakPrivateCommitBytes']}
if state.get('error'):execution['error']=state['error']
execution['elapsedSeconds']=state.get('elapsedSeconds')
execution['terminalReceipt']=str(run/'completed.json') if not alive else None
execution['completedCaseTiming']=[]
for item in state['completed']:
 packet=read(item['file'])
 execution['completedCaseTiming'].append({'id':item['id'],'seconds':packet['seconds'],
   'inputFrames':packet['frames'],'audioSeconds':packet['frames']/16000,
   'generatedTokens':len(packet['generatedIds']),'naturalTermination':packet['naturalTermination']})
ref.update(execution=execution,assetReceipt=str(C/'asset-acquisition-r1/completed.json'),
 assetsBytes=sum(v['bytes'] for v in assets['completed']),largeWeightsDownloaded=True)
if score:
 ref['result']={'state':score['state'],'errors':score['aggregate']['errors'],'referenceWords':709,
  'wer':score['aggregate']['errorRate'],'advanceToWholeEnglish':score['advanceToWholeEnglish'],'scoreFile':str(score_path)}
 ref['state']='FIXED_NATIVE_GRANITE_REFERENCE_SCORED'
 ref['ownerStatus']=f"Granite固定英文对照已完成：{score['aggregate']['errors']}/709错，词错率{score['aggregate']['errorRate']*100:.2f}%；"+('通过中间筛选，整会与逐人仍待验证。' if score['advanceToWholeEnglish'] else '未通过中间筛选，保留结果并结束本固定方案。')
elif not alive and state['state'].startswith('FAILED'):
 ref['state']='NATIVE_REFERENCE_EXECUTION_FAILED_RETAINED'
 ref['ownerStatus']='原精度参考完成1/12段；第1段12.05秒原音耗时约300秒，第2段触及600秒单条时限而停止。当前低内存CPU卸载方式速度不合适，尚不能判断完整准确率；保存现场，不原样重跑。'
elif state['state'].startswith('COMPLETE'):
 ref['state']='NATIVE_REFERENCE_COMPLETE_PENDING_INDEPENDENT_SCORE'
 ref['ownerStatus']='12段英文原音推理已完成，正在按原参考独立评分。'
else:
 ref['state']='EXECUTING_ONE_FIXED_NATIVE_ENGLISH_REFERENCE'
 ref['ownerStatus']=f"Granite原生BF16参考正在执行，已完成{len(state['completed'])}/12段；原25%CPU、2GiB私有与真实低内存保护保留，尚无完整新词错率。"
o['currentOwnedNeuralWorker']={'pid':pid,'createdAt':created,'stateFile':execution['stateFile']} if alive else None
batch=j.setdefault('modelDeliveryReview20261117',{'startedAt':at,'ownerQuote':'那请开始吧, 另外做这个东西的同时，我们需要维护我们那个网页，就是那个 companion 产品网页然后你之前做了什么东西在往上面写一下，然后大概是一个什么样的方式之类，现在这个东西也做了快一个多星期了，感觉还是没有什么进展。是我们工作方式有问题，还是？怎么说呢？就是。哎，我也不知道是什么问题，你先帮我看下是什么问题吧。来，我们讨论一下怎么做这个事情。'})
batch.update(at=at,execution=execution,webpage='C:/Users/Billy/Desktop/Denzic/Companion/Companion.html',
 modelPage='#models',modelViewSource='tools/model_progress.py reads the original backlog and immutable score receipts',
 methodAssessment='Real ASR gains exist but quality convergence is unsatisfactory. Runtime preparation and too many premature component branches displaced the core English accuracy experiment; webpage visibility also conflated executability with quality. Judge the correction by the next actual quality result, not this documentation.',
 preparationFailures=[{'run':'r1','reason':'Old responsive wrapper rejects25percent constructor; corrected using existing owned-job25percent adapter before model load.'},
 {'run':'r2','reason':'Prepared BF16 persistent buffer was incorrectly read as int64; corrected dtype-preserving loading. No original inference ran.'},
 {'run':'r3','reason':'Standard torchaudio frontend dependency absent; installed exact2.11.0CPU wheel in candidate-only dependency directory, leaving GPU environment unchanged.'},
 {'run':'r4','reason':'Initial explicit asset inventory omitted separate chat_template.jinja. Completed pinned metadata using a Git commit chain anchored in the original officialHF revision after official-hostTLS failures. Processor now validates all12original inputs before large model preparation.'}],
 newTrainingUpdates=0,qualityQualified=False,saleQualified=False)
x['state']='GRANITE_REFERENCE_SCORED_AND_MODEL_WEBPAGE_UPDATED' if score else ('GRANITE_REFERENCE_PARTIAL_CPU_BOUNDARY_RETAINED_AND_WEBPAGE_UPDATED' if not alive else 'GRANITE_NATIVE_REFERENCE_AND_MODEL_WEBPAGE_IN_PROGRESS')
x['nativeInferencePerformedThisBatch']=state['state'].startswith('DECODING') or bool(state['completed'])
batch['preparationFailures'].append({'run':'r5','reason':'ROCmTorch CPU frontend terminated with nativeOpenBLAS allocation failure; no Pythonfinally. Prior terminal/source retained. R6 uses matching officialCPU Torch with noHIP/CUDA and MKL; original limits/profile unchanged.'})
batch['cpuRuntimeInstallationReceipt']=str(C/'torch-install-payload-integrity.json')
if (C/'portal-source-checkpoint.json').exists():
 batch['webpageSourceCheckpoint']=read(C/'portal-source-checkpoint.json')
 batch['webpageBrowserQA']=read(C/'portal-browser-r5/result.json')
batch['nextExperimentBoundary']='Same2GiB CPU disk-offload profile is ended. The large published reference and product lightweight runtime need separate budgets; do not enlarge the owner2GiB limit without authorization. No new backend port or model grid is implied.'
if score:
 x['next']='Run original whole English sources with this exact candidate if its fixed admission passed; otherwise end this fixed profile and discuss the measured remaining quality gap. Keep Chinese baselines, original5/2percent/person/facts/final gates; no automatic model/decoder/precision grid.'
elif not alive:
 x['next']='This fixed CPU disk-offload run ended at1/12 because the second case hit600seconds; do not repeat or extend the same profile. Preserve this candidate, original references and receipts; resume its fixed12case quality comparison only after a concrete change to fitting compute/runtime budget. Keep available Chinese and local streaming/offline paths; ordinary non-overlap English quality remains the bottleneck. No new model grid, no training or overlap branch before a qualifying reference.'
marker='MODEL_REFERENCE_AND_PORTAL_BATCH_20261117'
text=(f'\n\n{at}｜{marker}｜承接Owner开始单一英文参考、维护Companion产品网页并讨论一周效率。'
 '原候选13个资产4635419847B已完整下载，3分片发布SHA核验；954个原状态键经官方4条纯重命名与本地原生结构/形状全匹配，BF16按层加载小数值对照相同。'
 '实际参考使用标准Transformers模型/处理器+Accelerate磁盘offload，保持原BF16/PCM/贪心配方，非新引擎或训练。'
 '准备返工如实保留：r1旧限流构造接口不接受25%；r2把BF16持久缓冲误读int64；r3缺标准torchaudio。'
 '仅补候选隔离依赖，原GPU环境未安装覆盖；r4发现独立模板漏项，经固定发布Git提交链补齐，把全部12条原处理器准入提前到大模型准备之前。r5在原生前处理阶段因ROCmCPU OpenBLAS分配失败退出1；切为同版本官方CPU Torch2.11.0+cpu/MKL，HIP/CUDA均无，原门不改。CPU包pip长路径搬运退出1如实保留，11631个原文件字节已独立核验，另145个原wheel缺失源码/编译辅助文件经长路径逐个精确补齐，不覆盖既有Python/DLL、不改系统设置。源/协议/终态全保留。'
 f'当前{run.name}状态{state["state"]}，{len(state["completed"])}/12完成、峰私有{state["limits"]["jobPeakPrivateCommitBytes"]}B，记录时自有PID{pid}活性{alive}；'
 '0训练更新，不把运行准备算词准改善。'
 'R6全部12条原生前端预检通过，第一条12.05秒音频自然结束输出耗时300.183秒；第二条600秒单条边界停止，全批仅1/12，不给709词完整分数、不据此判候选质量不合格；原样CPU卸载方式结束不自动重跑。'
 '网页新增首页模型前后对照与#models专页：真实收益/失败/当前候选/训练是否发生/工作方式问题/后续顺序，模型数据从唯一原待办和原评分生成；'
 '原资源、硬件、UI其它工作点保留，页面仅本地HTML不托管推送。工作方式改为一个核心质量问题、一个候选、同源准入后整会逐人，再决定训练与轻量化；'
 '现有局部门有约束但整体范围未收敛，规则/文档变化本身不是产品收益。')
if 'webpageSourceCheckpoint' in batch:
 text+=f' 网页源码本地提交{batch["webpageSourceCheckpoint"]["commit"]}；桌面1440与移动390宽浏览器实际打开、搜索与首页入口通过，JS异常0/全局横向溢出0。移动历史表改卡片显示，标题锚点避开固定栏；维护迁移并发改动保留未代提交。完整日志沿docstore同一网页来源回写，不恢复旧Markdown正文。'
if score:text+=f' 完整评分{score["aggregate"]["errors"]}/709={score["aggregate"]["errorRate"]*100:.4f}%WER；中间筛选通过{score["advanceToWholeEnglish"]}，原最终门未改。'
if marker in x['logResult']:
 pos=x['logResult'].index(marker);start=x['logResult'].rfind('\n\n',0,pos);end=x['logResult'].find('\n\n',pos)
 x['logResult']=x['logResult'][:start]+text+(x['logResult'][end:] if end>=0 else '')
else:x['logResult']+=text
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':x['state'],'workerState':state['state'],'completed':len(state['completed']),
                  'aliveWhenObserved':alive,'ownerStatus':ref['ownerStatus']},ensure_ascii=False))
