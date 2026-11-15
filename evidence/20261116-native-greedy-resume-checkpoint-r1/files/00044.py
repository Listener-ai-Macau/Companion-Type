from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
C=BASE/'staged-r4';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/staged-r4')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not E.exists();C.mkdir()
prior=read(BASE/'overnight-r5/overnight-binding.json');B={k:prior[k] for k in ['modelControl','blas','blasSha256','gpuPython','neuralDeadline','reportDeadline']}
old=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/overnight-r5')
prefix=read(old/'ES2003b-partial-ids.json')['generatedIds']
control=read(old/'published-gpu-causal-control.json');assert control['logitMaxAbsDifference']==0 and max(control['cacheMaxAbsDifferences'])==0
cases=[{'meeting':'runtime-control61','audio':prior['controlAudio'],'audioSha256':prior['controlAudioSha256'],
 'frames':976048,'audioSeconds':61.003,'runtimeControl':True,'expectedPrefixIds':control['next16TokenIds'],'maxNewTokens':16}]+read(BASE/'full-audio-only.json')
cases[1]['expectedPrefixIds']=prefix
completed=E.parent/'staged-r1/runtime-control61-prefill-state.json'
cases[0]['reusedPrefill']={'state':str(completed),'stateSha256':sha(completed),
 'cache':str(E.parent/'staged-r1/cache/runtime-control61')}
cases[0]['resumeGeneratedIds']=cases[0]['expectedPrefixIds'][:8]
es=E.parent/'staged-r2/ES2003b-prefill-state.json'
cases[1]['reusedPrefill']={'state':str(es),'stateSha256':sha(es),'cache':str(E.parent/'staged-r2/cache/ES2003b')}
retained=E.parent/'staged-r2/ES2003b-partial-ids.json'
cases[1]['resumeGeneratedPrefix']={'file':str(retained),'sha256':sha(retained),'tokens':len(read(retained)['generatedIds'])}
helpers=dict(prior['helpers'])
for n in ['moss_native_cache_store_20261115.py','moss_causal_prefill_20261115.py','moss_native_full_execution_20261115.py','moss_native_greedy_20261115.py']:
 helpers[str(S/n)]=sha(S/n)
B.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(S/'moss_staged_meeting_worker_20261115.py'),
 runnerSha256=sha(S/'run_moss_staged_meetings_20261115.py'),helpers=helpers,cases=cases,
 scoringControl=str(BASE/'overnight-r5'),scoringPython='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',
 scorerSha256=sha(S/'score_joint_whole_meetings_20261115.py'),
 change='After one complete native acoustic+causal prefill, serialize all used BF16 KV cells and first logits bit-exact. Exit producer. Fresh decoder retires completed audio modules, restores all native KV, serves saved prefill logits once into original generate, then continues without audio/multimodal tensors or speaker reset.',
 oldResults='Fixed cache resolved full27924token prefill at1.45GB. Real generate21tokens in407s total is too slow. Same real model/synthetic longKV native forward0.54s, installed adapter0.56s, native generate8=5.06s excludes generic attention/adapter/generation bottleneck alone. Different live audio-stage lifetime/data condition remains unresolved; stage boundary plus exact original21token prefix distinguishes it.',
 controls={'serializeAllUsedCellsAsUint16NoQuantization':True,'restoreEveryKVPrefixTorchEqual':True,
  'runtime61Second16TokensMustMatchRetainedNative':True,'realWholeFirstRetainedTokensMustMatch':len(prefix)},
 privateBytes=2147483648,cpuPercent=5,actualWindowsLowMemoryStop=True,maxNewTokens=32768,
 checkpointDiskEstimateGiB=14.5,minimumDiskFreeGiB=50,qualityQualified=False,productDefaultChanged=False,
 newWeightTraining=False,automaticRetries=0,finalHoldoutOpened=False)
B.update(cpuEosGreedy=True,
 change='Native batch1 greedy argmax/EOS semantics with CPU-owned token list and EOS decision; no GPU unfinished-sequence Boolean reduction. Restore original full native KV and replay retained own-model generated IDs in128token causal blocks, preserving all original IDs. Mandatory original16token control now replays8 and continues8.',
 oldResults='Staged-r2 strict16token control passed; real ES decoded2294tokens atabout2token/s/private1.2GB before HIP C++ abort surfaced in GenerationMixin StopCheck GPU bool/scalar check. System Display4101/14/17/18 query found no matching prior-hour events; asynchronous origin remains unknown. Remove this specific GPU stop-check path, reuse complete prefill and saved original2294 IDs; no same-input replay from audio, no driver/guard/model changes.')
(C/'staged-binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');record=read(p)
record['state']='OVERNIGHT_NATIVE_FULL_CONTEXT_MEMORY_PASSED_STAGED_SPEED_CONTROL_PENDING'
record['ownerOvernightRun20261115']['currentStagedControl']=str(C)
record['ownerOvernightRun20261115']['currentStagedRun']=str(E)
record['ownerOvernightRun20261115']['runtimeFindings']={'fullPrefillTokens':27924,'privatePeakBytes':1451319296,
 'completeMeetingOutputs':0,'slowNativeGeneratedTokens':len(prefix),'attentionNative27924keysSeconds':.0082202,
 'warmNativeLongKvForwardSeconds':.5413478,'adaptedLongKvForwardSeconds':.5632175,'syntheticGenerate8Seconds':5.0605776,
 'checkpoint':str(C/'staged-binding.json'),'qualityQualified':False}
record['next']='继续同一整夜关口至11月16早07:30：全因果固定缓存已过27924token整会预填充且内存1.45GB；慢解码21token保留，核查排除单纯注意力/适配器/生成包装本身。现原生预填充完整BF16状态落盘并退出，冷解码进程移除已完成声学模块、逐值恢复KV和首logits，先61s原16token严格复现，再固定4整会，首场前21token对照旧输出；无新训练/默认更换。07:20停止推理留评分保护，资源/原字门不变，不拿准备或运行时间当质量改善。'
record['logResult']+='\n'+B['at']+' 整夜执行真实进展：r1 CPU控制派生配置误传只读adaptor_input_dim，0公开模型载入即停，已修且保留。r2/r3因果块控制逐值过，动态KV整会在12032/27924token私有2GiB停止；r4独立10GiB设备实写仅428MB私有，排除简单显存同比占RAM；全宽StaticCache原logit差0.25被原容差拒绝，未放宽。r5固定存储+已填前缀视图原61s logits/KV逐值相等、16token一致，整会27924token预填充真正完成，峰私有1.451GB；原始生成只21token/407s总墙钟，主动停止而非质量成绩。单query原attention8.22ms、原模型合成27kKV热forward0.54s/适配0.56s、native generate8=5.06s，不足解释真实慢速，未采用微基准小优化。现改变进程生命周期：完整原nativeKV/首logit逐值落盘、生产者退出、冷解码只保留语言主干，必须原61s16token及首会旧21token复现后继续。所有参考/分数/CPU5%/族2GiB/低RAM门保留，4完整原字基线已CPU复现，无新权重或新整会质量。'
p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
subprocess.run([sys.executable,'work/record_bilingual_progress.py',str(p)],check=True)
print(json.dumps({'control':str(C),'run':str(E),'retainedRealPrefixTokens':len(prefix)}))
