from pathlib import Path
import json,subprocess,sys
p=Path('work/bilingual_progress.json');a=json.loads(p.read_text(encoding='utf-8'))
D=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution')
E=Path('E:/CodexData/Companion/product-d1d2-20261114/nemotron-cache-trace-r1/whole-new-r1')
review=json.loads((E/'cache-review.json').read_text());assert review['exactFullProbabilityBytesUnchanged']
a['d1d2Execution20261115'].update(
 cacheTraceStatus='COMPLETE_EXACT_PROBABILITY_CONTROL:48same historical active embeddings persist across absence; total cache eviction not supported, no reserve-policy patch. Returned voice mostly channel1 with median other0.9846/target0.002 under original labels.',
 cacheTraceReview=str(E/'cache-review.json'),returningVoicePosteriorReview=str(E/'posterior-review.json'),
 englishComplexAnnotationDiagnostic=str(D/'reference-annotation-audit-en2002a-r1/comparison.json'))
a.update(modelWeightsChanged=True,baseModelWeightsChanged=False,shippedDefaultWeightsChanged=False,
 newOptionalAdapterWeightsCreated=True,optionalAdapterAdoptedInProduct=False,
 cloudInferenceUsed=True,cloudAsrInferenceUsed=False,cloudMinutesInferenceUsed=True,
 cloudInferenceScope='Existing configured minutes provider was actually used on public product QA earlier; every ASR/diarization operation remains local, no speech cloud fallback.',
 nativeInferencePerformedThisBatch=True)
a['next']='先保护完整小适配拒绝结论、两场英文参考口径诊断、缓存只读整场和后验证据；接着核对Qwen官方ASR评测的麦克风/分段/参考处理条件及本机同输入处理链，明确剩余文字差距的可复现原因，再选一个有证据的源头改动。人物不再猜缓存清空或扫门限，原D2门未过、最终holdout不动。'
marker='2026-11-15返回人物缓存假设结案'
if marker not in a['logResult']:
 a['logResult']+=' '+marker+'：同原.nemo/同340-40-264-40-300几何的上游FP32只读跟踪12:39:37—12:40:05完成28.609秒，76chunk新调用，完整204937x8概率NPY SHA e067ef343282e0af4253391d4657172d5ccc419ab34d8ac6a25571af1984a86c与未加跟踪结果逐字节完全相同，族峰1795411968B、0训练、2GiB/5%不变。缺席期间模型缓存最少仍有48个该通道活动帧，跨缺席前后48个原历史嵌入SHA保持，故简单完全驱逐不成立、不做reserve-slot补丁。退出后只读10ms后验按原参考诊断：003-M返回66.11秒中64.12秒有其它通道活动，最高通道1（对应004-M）占63.37秒，目标通道从缺席前中位0.961降到返回后0.00197，其他最高通道中位0.98455；不是在0.5附近迟疑的门限问题。10ms诊断不是新DER，目标独说段/含重叠全段都报、原全场分不改，模型分未校准/参考身份未独立听音重审边界保留。保留缓存存在仍高打分混淆的现象，不冒称已定声学根因或修好。下一步先核对现有ASR来源/评测处理差异，禁止在无新原因时重试同一失败训练或堆新模型。状态顶层已澄清新增LoRA权重存在但基座/默认未改，云调用只限此前公开QA的真实纪要服务，ASR始终本地。'
p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
subprocess.run([sys.executable,'work/record_bilingual_progress.py',str(p)],check=True)
b=json.loads(Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/product_backlog.json').read_text(encoding='utf-8'))
n=b['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']['ownerPairedRealMeetingSource20261109']['execution20261114']['localBilingualContinuation']
assert n['next']==a['next'] and n['d1d2Execution20261115']['d1Complete'] and not n['d1d2Execution20261115']['d2Complete']
print(n['next'])
