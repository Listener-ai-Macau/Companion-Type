from pathlib import Path
from datetime import datetime
import json,subprocess,sys
p=Path('work/bilingual_progress.json');a=json.loads(p.read_text(encoding='utf-8'))
d=a['d1d2Execution20261115'];e='E:/CodexData/Companion/product-d1d2-20261114/'
d.update(candidateSourceReceipt=e+'app-candidate-r5/source-binding.json',
 actualHiddenNativeUi=e+'app-candidate-r5/qa/hidden-delivery-r1/native-ui-result.json',
 newLocalCachePrivacyFix='PASS actual native90s paced LiveAsrHub, stop/seal/resume original immutable stream, busy-cache refusal, transcript157files/3jobs erase, trash/purge original-source delete, other-session preservation.',
 actualNativeLivePrivacy=e+'app-candidate-r5/qa/live-resume-privacy-final.json',
 actualSpeakerReviewPortability=e+'app-candidate-r5/qa/speaker-review-portability-r1/result.json',
 officialSameCheckpointReference=e+'official-native-parity-r1/full-comparison.json',
 referenceResult='Complete34min same weights: upstream DER15.8414424%, native15.84147%; channel2 disappears1040.94s/1040.99s in both. No quality benefit; preserve backend, no geometry/threshold sweep.',
 officialReferenceResourceResult='ROCm BLAS process16→1; full frontend allocation bounded with exact same per-frame upstream formula,61s+3edge/tail cases bit-exact. Fullworker peak1797033984B,2GiB/5% unchanged.',
 futurePackageCacheIdentityTodo='When integrating next coherent model package, include full config/bundle identity in native cache key. Current behavior fails closed on changed bundle; no wrong result reused; R8 entry changed and actual delivery verified.')
a['next']='先保护D1实际交付、r8源和本轮官方同权重完整参考证据；随后仅对已冻结最终小适配做旧/新普通完整会议原分段对照，禁止改训练参数、替换评分或最终holdout回灌。D2原文字/人物门仍失败，D3—D5、实卡安卓和实时延迟仍未合格。'
marker='2026-11-15官方同权重完整对照收敛结果'
if marker not in a['logResult']:
 a['logResult']+=' '+marker+'（'+datetime.now().astimezone().isoformat(timespec='seconds')+'）：61秒上游FP32与原生FP16原通道概率活动差0.1121%，不足解释长会。原34分钟前端全量FFT在0NN时分配异常，原run-r1和源码保留；仅将全局预加重后STFT按3000帧、全局补零与精确hop分块，调用原upstream公式，CPU公开61秒及3个非对齐尾/边界脉冲条件特征和mask逐值全等/maxdiff0。run-r2于11:49:39—11:50:10完整76次chunk，模型峰1797033984B，原2GiB/5%未放宽；完整204937帧、4匿名人物，严格零collar含重叠DER15.8414424%，原生15.84147%，均失败，原通道概率活动差0.6528%，group2最后1040.94/1040.99秒，返回发言消失同现。保留原默认，不再为无收益参考重跑旧38分钟或扫参数；区别实现移植与预训练模型在本场的局限已有证据。纯数值比较器512MiB不足额外6.25MiB数组失败，保留原因后只将该非神经比较器设1GiB，实际峰543977472B，模型上限未变。D1完成口径仍只是原内测可执行候选，D2质量仍失败。'
p.write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
subprocess.run([sys.executable,'work/record_bilingual_progress.py',str(p)],check=True)
# Read back the canonical point after recording this completed subitem.
b=json.loads(Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/product_backlog.json').read_text(encoding='utf-8'))
n=b['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']['ownerPairedRealMeetingSource20261109']['execution20261114']['localBilingualContinuation']
assert n['d1d2Execution20261115']['d1Complete'] and not n['d1d2Execution20261115']['d2Complete']
print(n['next'])
