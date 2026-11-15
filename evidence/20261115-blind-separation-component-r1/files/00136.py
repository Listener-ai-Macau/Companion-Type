from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'blind-separation-composition-r1';read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'protocol.json').exists()
runner=S/'run_blind_separation_composition_20261115.py';assert not runner.exists()
text=(S/'run_fixed_asr_adapter_20261115.py').read_text(encoding='utf-8')
for old,new in [('ordinary_asr_adapter_worker_20261114.py','blind_separation_worker_20261115.py'),
                ("choices=['trial'],default='trial'","choices=['control','separate','asr'],default='control'"),
                ("'--run',str(a.run)]","'--run',str(a.run),'--phase',a.phase]"),
                ("'newTraining':True","'newTraining':False"),
                ('FIXED_SMALL_ASR_ADAPTER','BLIND_SEPARATION_COMPOSITION'),
                ('FIXED_ADAPTER_TRIAL_SCORING_PENDING','BLIND_COMPOSITION_PHASE_COMPLETE'),
                ('FIXED_ASR_PHASE_RETAINED','BLIND_COMPOSITION_PHASE_RETAINED')]:
    assert old in text; text=text.replace(old,new)
compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
prep=read(C/'preparation.json');deps=read(C/'isolated-runtime.json')
model=read(C/'model-binding.json');assert model['gated'] is False
old=D/'context-matched-baseline-r3';native=read(D/'community1-comparison-r1/protocol.json')
root=Path('E:/CodexData/Companion/product-d1d2-20261114/blind-separation-composition-r1')
original=Path('E:/CodexData/Companion/product-d1d2-20261114/context-matched-baseline-r3/base-run-r1')
control=next((original/'sessions'/read(C/'audio-only.json')[0]['id']/'decode').rglob('root.json'))
runtime=[]
for p in sorted(Path(deps['target']).rglob('*')):
    if p.is_file() and '__pycache__' not in p.parts:runtime.append(dict(file=str(p),sha256=sha(p)))
protocol=dict(state='FROZEN_ONE_PUBLIC_BLIND_SEPARATOR_PLUS_UNCHANGED_ASR_BEFORE_FORWARD',
    at=datetime.now().astimezone().isoformat(),sourceRoot=prep['sourceRoot'],checkpoint=prep['checkpoint'],
    isolatedDependencies=deps['target'],runtimeFiles=runtime,audioOnlySha256=sha(C/'audio-only.json'),
    controlRun=str(root/'control-r1'),separationRun=str(root/'separate-r1'),asrRun=str(root/'asr-r1'),
    rocmBlasLibrary=native['rocmBlasLibrary'],rocmBlasLibrarySha256=native['rocmBlasLibrarySha256'],
    nativeProtocol='E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json',
    baselineNativeControl=str(control),baselineScore=str(old/'baseline-score.json'),scoringManifest=str(old/'scoring-only.json'),
    baselineScoreSha256=sha(old/'baseline-score.json'),scoringManifestSha256=sha(old/'scoring-only.json'),
    separation='Unmodified56M-ish official core FP32 checkpoint, no training or speaker profile/count hints. Fixed author2s windows1.5s stride; local overlap waveform MSE permutation then tapered weight-normalized OLA, all original frames/tail preserved. Raw float32 outputs no clipping, per-output RMS normalization, denoising or transcript selection.',
    control='Actual checkpoint CPU/GPU first4096samples maxabs<=.001/mean<=.0001; single2s core/CSS output bit-exact; alternating-channel toy all samples/tails recover<=1e-6, exact digital-zero bypass. No tolerance changes after results.',
    asr='Separate process after separator exits; unchanged nativeQwen1.7B BF16 eager greedy512 and existing bounded recovery. One original prefix exact control, reuse original32 baseline. Both64float streams decoded/retained, no low-energy/source/profile/transcript filtering.',
    score='Two-stream ORC-style CER: every complete reference utterance assigned exactly once to one of2anonymous streams, preserving within-stream reference time order. Min summed Levenshtein; every output word from both streams counted including duplicates/empty-target insertions. Diagnostic, not identity/cpCER/full meeting acceptance.',
    keepRule='Original12multi-turn total diagnostic edits must reduce; neither source may regress. Original20single-voice total diagnostic edits and each source must not regress. Any unconfirmed/invalid ASR interval rejects. Passing permits original whole-meeting/identity integration testing only; not product adoption.',
    stop='One fixed model and policy only; no model/window/threshold/gain sweep. Reject if prerequisites or fixed criteria fail; do not replace original references/gates or final holdout.',
    ownerOriginal='开始吧，那你继续吧继续吧，然后的话需要把，训练重点转移到分开这个东西，用这个模型组合来做这个会议复杂场景会议室里。',
    ownerParticipationRequired=False,newTraining=False,allInputPublic=True,finalHoldoutOpened=False,
    cpuPercentMaximum=5,privateCommitLimitBytes=2*1024**3,actualWindowsLowRamStop=True,
    qualityQualified=False,d2Complete=False,productDefaultChanged=False)
write(C/'protocol.json',protocol)
helpers=['blind_separation_composition_20261115.py','companion_community1_adapter_20261115.py',
         'companion_local_qwen_worker_20261114.py','companion_local_pcm_session_20261114.py',
         'companion_local_decode_recovery_20261114.py','practical_qwen_bounded_decode_20261107.py',
         'practical_qwen_streamed_loader_20261107.py','moss_windows_resource_limits_20261104.py']
binding={str(S/n):sha(S/n) for n in helpers}
for p in [Path(protocol['nativeProtocol']),control,C/'model-binding.json',C/'source-binding.json']:
    binding[str(p)]=sha(p)
write(C/'worker-binding.json',dict(workerSha256=sha(S/'blind_separation_worker_20261115.py'),
    runnerSha256=sha(runner),protocolSha256=sha(C/'protocol.json'),helpers=binding))
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    blindSeparationComposition=str(C),blindSeparationCompositionProtocol=str(C/'protocol.json'),
    blindSeparationCompositionRunRoot=str(root),blindSeparationCompositionStatus='FROZEN_READY_FOR_NUMERICAL_CONTROL',
    blindSeparationCompositionProductDefaultChanged=False)
v['next']='执行固定公开盲分离组件控制→原32段完整双路分离→既有Qwen分别转写64路→保留两路所有词的ORC式诊断；满足真实重叠改善和单人不退步才接原整会/人物组合，不追加参数/模型变体。原标注/5%和10%门不变，Owner无需听审或账号，最终留出不打开。'
v['logResult']+=' '+protocol['at']+' 分离组合准备完成：公开MossFormer2_SS_16K版本407cb03原checkpoint670353271B完整SHA00a3a48bda492db1e829b85dd443f8f43a43039a3e90f1a24962ea9caf14a11a通过，含model1099张量/optimizer，CPU只mmap模型不加载优化器训练。官方代码6b3774d与许可固定；3个purePython依赖仅隔离目录，不改原torch/transformers。官方外层按路RMS放大及拼接尾段/次序无法满足本链约束，采用原网络/权重+固定作者2s/1.5s本地CSS适配：重叠波形MSE次序匹配、权重归一拼接、保留片尾，输出float32不逐路放大、不截幅；明确不是官方wrapper逐字节重现。准备检查曾SystemRamPressure误作contextmanager在导入torch前停止，已按既有close接口修正，0神经/0更新。冻结原12多轮+20短响应、两路全部词计分、普通不退步才扩原整会；尚无组件前向或质量结论。'
write(p,v)
print(json.dumps({'control':str(C),'runs':str(root),'cases':32,'runtimeFiles':len(runtime)},ensure_ascii=False))
