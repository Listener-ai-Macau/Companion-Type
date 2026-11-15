from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,subprocess,sys

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
p=argparse.ArgumentParser();p.add_argument('--attempt',required=True,choices=['overnight-r5']);a=p.parse_args()
BASE=D/'joint-architecture-r1';C=BASE/a.attempt
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')/a.attempt
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not E.exists();C.mkdir()
B=read(BASE/'full-binding.json');helpers=dict(B['helpers'])
for n in ['moss_causal_prefill_20261115.py','moss_native_full_execution_20261115.py']:
 helpers[str(S/n)]=sha(S/n)
runtime=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/transformers')
for n in ['models/qwen3/modeling_qwen3.py','generation/utils.py','cache_utils.py','masking_utils.py']:
 helpers[str(runtime/n)]=sha(runtime/n)
binding={'at':datetime.now().astimezone().isoformat(),'modelControl':str(BASE),'workerSha256':sha(S/'moss_overnight_worker_20261115.py'),
 'runnerSha256':sha(S/'run_moss_overnight_20261115.py'),'helpers':helpers,'wholeManifestSha256':sha(BASE/'full-audio-only.json'),
 'controlAudio':'E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/whole-run-r1/frontend-control.wav',
 'controlAudioSha256':'5fb4dbdbb6991475d382e7729dd72c954fa2fa6ac3ddb80d3dc287495c119817',
 'blas':B['blas'],'blasSha256':B['blasSha256'],
 'gpuPython':'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',
 'neuralDeadline':'2026-11-16T07:20:00+08:00','reportDeadline':'2026-11-16T07:30:00+08:00',
 'controlsFrozenBeforeRun':{'cpuFP32Tolerance':{'atol':2e-5,'rtol':2e-5},
  'publishedGpuLogitTolerance':{'atol':.125,'rtol':.01},'publishedGpuCacheTolerance':{'atol':.0625,'rtol':.01},
  'publishedGpu16GreedyTokensMustMatch':True},
 'algorithmChange':'Native fixed BF16 StaticLayer storage/index_copy updates, returning only a view of filled prefix and DynamicCache-equivalent mask lengths. Native unfilled future columns stay excluded before attention, rather than changing reduction width. Full-context128token prefill remains, no KV resets or quantization.',
 'whyPriorFailureNotRepeated':'r4 allocation control verified10GiB live/touched device buffers at428MB private, excluding simple proportional VRAM-to-RAM charging. Native full-width StaticCache failed frozen published logit control maxdiff0.25 before any whole meeting; tolerance unchanged. Prefix views/mask sizes now match DynamicCache geometry while retaining fixed storage. This isolates in-place cache storage from padded-attention numerical differences; no relaxation or quality tuning.',
 'allocationProbeBytes':10*1024**3,
 'allocationControlReuse':{'file':str(E.parent/'overnight-r4/allocation-control-state.json'),
  'sha256':sha(E.parent/'overnight-r4/allocation-control-state.json')},
 'oneCandidateOnly':True,'qualityQualified':False,'newWeightTraining':False,'automaticRetries':0,'productDefaultChanged':False,
 'baselineResultsReused':True,'finalHoldoutOpened':False,'resourceLimits':{'cpuPercent':5,'familyPrivateBytes':2147483648,'actualWindowsLowMemoryStop':True},
 'stopCriteria':'Control failure: no whole run. Resource or runtime failure: retain, inspect root before changed continuation. No same-path retry, parameter sweep or guard increase. Stop NN07:20 to reserve final scoring/protection until07:30.'}
(C/'overnight-binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');record=read(p)
previous=record.get('ownerOvernightRun20261115')
record['ownerOvernightRun20261115']={'at':binding['at'],'quote':'好啊，那就按照这个顺序继续进行推进呗，然后你大概推进一个一个晚上，跑到明天。早上7:30吧，看一下就跑完它，看一下这整一晚能跑出一个怎么样的一个效果。搞个合适的东西去把它跑。',
 'timezone':'Asia/Shanghai','reportDeadline':binding['reportDeadline'],'neuralDeadline':binding['neuralDeadline'],
 'control':str(C),'run':str(E),'bindingSha256':sha(C/'overnight-binding.json'),'newThreadsOrAutomationsCreated':False,
 'previousAttempt':previous,'changedCondition':binding['whyPriorFailureNotRepeated']}
record['state']='OVERNIGHT_ARCHITECTURE_GATE_PREPARED_CAUSAL_PREFILL_CONTROL_PENDING'
record['next']='按Owner授权推进至北京时间2026-11-16早07:30：同一MOSS联合主干改为全decoder128token缓存预填充，先CPU/KV/真实61秒GPU16token数值控制；过后固定两中两英143.82min完整原会，不换权重/阈值/参考/门，复用原组合结果。自有模型族2GiB/CPU5%及真实低RAM保护不变，07:20结束新推理留评分/保护，失败不原样自动重试。完整多会质量有实质收益且可部署后才进入公开会议域适配，阶段A轮流无重叠优先，B/C和售卖保持未过。'
record['logResult']+='\n'+binding['at']+' Owner授权按架构关口连续推进一晚至2026-11-16早07:30。本批唯一实际变化为全decoder因果缓存预填充128token/块，替代旧仅注意力分块但QKV/FFN/掩码仍整长处理；旧精确LLVM失败算子未知，故先数值控制再整会，不把推测当根因已证实。冻结CPU/KV及真实61s16步GPU对照容差、同4完整开发会/资源/原字门，07:20停止推理留10分钟评分保护。不新增Goal/聊天/定时任务，不占桌面/实卡/外放/私人资料，不改原产品默认。'
p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
subprocess.run([sys.executable,'work/record_bilingual_progress.py',str(p)],check=True)
print(json.dumps({'control':str(C),'run':str(E),'deadline':binding['reportDeadline']}))
