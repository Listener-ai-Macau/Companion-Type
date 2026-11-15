from pathlib import Path
from datetime import datetime
import hashlib,json,random,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'supervised-blind-separation-r1';OLD=D/'blind-separation-composition-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'protocol.json').exists()
data=read(C/'data-ready.json');assert data['summaries']['train']['examples']==319
assert data['summaries']['validation']['examples']==84
base=read(OLD/'protocol.json');order=list(range(319));random.Random(20261115).shuffle(order)
root=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1');root.mkdir(exist_ok=True)
assert shutil.disk_usage(root).free>36*1024**3
runner=S/'run_supervised_blind_separator_20261115.py';assert not runner.exists()
text=(S/'run_blind_separation_composition_20261115.py').read_text(encoding='utf-8')
assert 'blind_separation_worker_20261115.py' in text
text=text.replace('blind_separation_worker_20261115.py','blind_separator_training_worker_20261115.py')
text=text.replace("choices=['control','separate','asr']","choices=['control','baseline','train','candidate']")
text=text.replace("'newTraining':False","'newTraining':a.phase=='train'")
compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
sources=read(OLD/'source-binding.json')['files'];runtime=base['runtimeFiles']
protocol=dict(state='FROZEN_ONE_FULL_CORE_BLIND_SEPARATION_MEETING_STYLE_PASS_BEFORE_UPDATES',
    at=datetime.now().astimezone().isoformat(),sourceRoot=base['sourceRoot'],checkpoint=base['checkpoint'],
    checkpointSha256='00a3a48bda492db1e829b85dd443f8f43a43039a3e90f1a24962ea9caf14a11a',
    isolatedDependencies=base['isolatedDependencies'],sourceAndRuntimeFiles=sources+runtime,
    rocmBlasLibrary=base['rocmBlasLibrary'],rocmBlasLibrarySha256=base['rocmBlasLibrarySha256'],
    dataReadySha256=sha(C/'data-ready.json'),trainExamplesSha256=sha(C/'train-examples.json'),
    validationAudioOnlySha256=sha(C/'validation-audio-only.json'),validationTargetsSha256=sha(C/'validation-examples.json'),
    controlRun=str(root/'control-r1'),baselineRun=str(root/'baseline-r1'),trainRun=str(root/'train-r1'),candidateRun=str(root/'candidate-r1'),
    order=order,epochs=1,examples=319,optimizerUpdates=80,batchSize=1,gradientAccumulation=4,
    optimizer='AdamW lr1e-5 betas(.9,.999),weight_decay0,foreachFalse;gradientClip1,seed20261115',
    trainable='All original factory-learnable55.7M-core parameters; original nonlearned rotary frequencies remain nonlearned. Eval mode keeps original dropout and running buffers deterministic; full gradients enabled, not language-model tuning.',
    loss='Two-output PIT source-aggregated scale-dependent SDR, Eq9, with fixed30dB soft maximum of paper Eq2. One known inactive source zero is supported; at least one known source must be nonzero. Exact digital-zero input is an already verified no-NN zero bypass.',
    inferenceUnitRule='One common differentiable RMS(sum) restoration to mixture RMS, same two-stream relative level preservation as current actual pipeline. No independent per-output target-level normalization, word/reference/identity inputs or threshold/gain sweep.',
    sourceSupervision='89unique public source units:64exact additive two-source mixtures+25single raw inputs with truly absent second source.319fixed2s windows cover548.6614unique seconds,638sexposure including overlapping tails. Old32person-absent conditional labels and7duplicates excluded. Not real isolated natural-overlap waveforms; room background remains.',
    syntheticValidation='24different-source units/84windows, separate1Dinput-only files. Forward never reads target arrays; independent scorer applies identical PIT loss after prediction. Source-meeting split disjoint, physical speaker/room independence not proven; sources previously diagnostic.',
    syntheticKeepRule='Final-only candidate reduces mean error-energy ratio versus original unadapted core, both source meetings and actual1/2active-target classes do not regress, each cardinality beats the all-zero estimator (ratio1), and true inactive-output energy does not regress. Otherwise reject without lr/epoch/data/model variants. A pass only permits natural complete-word evaluation, never direct adoption.',
    naturalKeepRule='Original32natural context/short-response development cases with all used-stream words, then original complete Chinese/English/person gates unchanged. Both natural source meetings and solo control must not regress; no checkpoint chosen using these answers. Final holdout unopened.',
    checkpoints='Byte-verified full model in<=24MiBshards plus bounded optimizer/RNG every16optimizerupdates and final80;only final selected. Reserve6GiB,never automatically delete checkpoints. Original verified1MiB archive writer reused,<=3MiB concurrent archive scratch.',
    primaryPaper='https://arxiv.org/html/2110.15581v2',
    paperBoundary='Use published loss and30dBsoft maximum. Do not reuse paper WER selection of better output or ignoring silent-region words; product diagnostic retains all generated words.',
    ownerParticipationRequired=False,allAudioPublic=True,finalHoldoutOpened=False,
    cpuPercentMaximum=5,privateCommitLimitBytes=2*1024**3,actualWindowsLowRamStop=True,
    qualityQualified=False,d2Complete=False,productDefaultChanged=False,automaticRetries=0)
write(C/'protocol.json',protocol)
helpers=['blind_separator_supervision_20261115.py','companion_tse_checkpoint_streamed_20261108.py',
         'moss_streamed_weights_20261104.py','companion_community1_adapter_20261115.py',
         'companion_local_pcm_session_20261114.py','moss_windows_resource_limits_20261104.py']
write(C/'worker-binding.json',dict(workerSha256=sha(S/'blind_separator_training_worker_20261115.py'),
    runnerSha256=sha(runner),protocolSha256=sha(C/'protocol.json'),helpers={str(S/n):sha(S/n) for n in helpers}))
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    sourceCommit=read(D/'protection-r15.json')['modelCommit'],sourceRemoteVerified=True,
    blindSeparationCompositionProtection=str(D/'protection-r15.json'),
    supervisedBlindSeparation=str(C),supervisedBlindSeparationProtocol=str(C/'protocol.json'),
    supervisedBlindSeparationRunRoot=str(root),supervisedBlindSeparationStatus='FROZEN_SOURCE_AND_LOSS_CONTROL_BEFORE_UPDATES')
v['next']='沿同一盲分离器执行唯一冻结会议式训练：89已知分量一/双源、319个2s样本，原模型factory可学参数、PIT/SA-tSDR30dB、1epoch/80更新/原CPU5%私有2GiB；先真实梯度与不奖励全静音控制、原模型84个独立源预测，再训练、最终84源验证。源验证不同时改善两来源/声源数或空路退步则拒绝，不追加参数变体；过才原自然32词语和完整中英文/人物验收，Owner无需参与，最终留出不打开。'
v['logResult']+=' '+protocol['at']+' 预训练盲分离组合309文件/45.600MB含原64路、校准64路、全部有效64转写及22未评分输出/准备失败已逐字节保护，私有远端提交'+e['sourceCommit']+'匹配。继续Owner训练重点，闭合监督已验证273原文件hash，89独立train单位319窗（548.661秒唯一/638秒曝光）、24异会议val单位84窗，目标两路之和与输入逐样本全等、仅mic0、不用人物样音或身份。排除旧条件缺席32条（其输入实际双源）和重复7条，未把真实未知重叠当静音；单源的第二路确实不存在。验证输入已另存84个仅1D混音文件，目标波形由独立评分读取。冻结同一原55.7M盲分离核factory可学参数1pass/80更新、lr1e-5/acc4，SA-tSDR Eq9+论文30dB软上限，专门支持单/双源且防整体静音捷径；不采用论文挑最佳输出/忽略静音路文字的宽松词评。先控制/原源基线、后真训练/最终源验/自然词评，尚0新SS权重更新。'
write(p,v);print(json.dumps({'control':str(C),'trainExamples':319,'optimizerUpdates':80,'validationExamples':84,'runs':str(root)},ensure_ascii=False))
