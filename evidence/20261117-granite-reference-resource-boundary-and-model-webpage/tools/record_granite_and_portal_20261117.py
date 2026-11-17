"""Reconcile this one model/reference and webpage batch, preserving prior evidence."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, json, psutil

C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
ap=argparse.ArgumentParser();ap.add_argument('--protocol',type=Path,required=True);args=ap.parse_args()
protocol=read(args.protocol);run=Path(protocol['run'])
state=read(run/'state.json')
pid=state['pid'];created=state['createdAt']
alive=psutil.pid_exists(pid) and abs(psutil.Process(pid).create_time()-created)<.01
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
 start=x['logResult'].rfind('\n\n',0,x['logResult'].index(marker))
 x['logResult']=x['logResult'][:start]+text
else:x['logResult']+=text
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':x['state'],'workerState':state['state'],'completed':len(state['completed']),
                  'aliveWhenObserved':alive,'ownerStatus':ref['ownerStatus']},ensure_ascii=False))
