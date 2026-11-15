from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-acoustic-context-r1';read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'protocol.json').exists()
prep=read(C/'preparation.json');assert prep['trainingCases']==50
baseline=Path('E:/CodexData/Companion/product-d1d2-20261114/context-matched-baseline-r3/base-run-r1')
audio=read(C/'validation-audio-only.json')
first=baseline/'sessions'/audio[0]['id']/'decode';controls=list(first.rglob('root.json'));assert len(controls)==1
native=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-runtime-r2/source/native-protocol.json')
now=datetime.now().astimezone().isoformat(timespec='seconds')
protocol=dict(state='FROZEN_SINGLE_ACOUSTIC_CONTEXT_ADAPTATION_BEFORE_NEURAL_UPDATES',at=now,
    trainManifestSha256=sha(C/'train.json'),validationAudioManifestSha256=sha(C/'validation-audio-only.json'),
    preparationSha256=sha(C/'preparation.json'),coverageAuditSha256=sha(C/'source-coverage-audit.json'),
    baselineNativeRun=str(baseline),baselineChineseControl=str(controls[0]),
    baselineNativeStateSha256=sha(baseline/'baseline-state.json'),
    nativeProtocol=str(native),nativeProtocolSha256=sha(native),
    baselineOriginalScore=str(D/'context-matched-baseline-r3/baseline-score.json'),
    baselineOriginalScoreSha256=sha(D/'context-matched-baseline-r3/baseline-score.json'),
    baselineOverlapOrderDiagnosis=str(D/'context-matched-baseline-r3/overlap-order-diagnosis.json'),
    training={'method':'PEFT LoRA, last8 audio encoder layers only; frozen language model and original weights',
        'rank':8,'alpha':16,'targetModules':'Only last8 audio-tower self-attention q_proj/v_proj','dropout':0.,
        'learningRate':2e-5,'epochs':1,'batchSize':1,'gradientAccumulation':2,
        'optimizer':'AdamW betas(0.9,0.999), weight_decay0','gradientClip':1.,'seed':20261114,
        'savedCheckpoints':'Every optimizer update recoverable; final adapter only for validation, no epoch/lr selection'},
    keepRule='Final candidate must strictly reduce original total CER of12frozen multi-turn contexts, not regress either validation meeting,20clean short-response total, or the constrained oracle-order diagnostic. Existing English normalized text must remain exact; natural mixed CER must not increase. Any failure rejects this fixed acoustic trial without lr/rank/epoch/data variants. Even passing only retains it for original whole-development gates; never automatic product adoption.',
    trialDifference='Rejected previous pilot updated only LM on128isolated2–12s utterances. This trial updates only acoustic last8 q/v on50natural complete multi-turn nonoverlap contexts including complete<2s responses,790.5571875s from3public training meetings. No overlap target order is invented.',
    rationale='Fixed diagnostic has161/1476raw chronological errors;40are removable by oracle reordering of overlapping utterances, leaving121mixed recognition/transcription errors. Separate acoustic adaptation from text-order learning; no claim that the residual is purely acoustic.',
    inference='Same original native1.7B BF16 eager greedy512 and parser; zero adapter/native prefix exact. Reuse all32already-produced original baseline outputs; generate candidate once. No validation label or speaker hint in neural worker.',
    doNotChange=['original complete meeting references and5%/10%gates','original final holdout L_R003S03C02 unopened','product default or daily application','original unmodified mic0 PCM and raw output words'],
    allAudioPublic=True,ownerParticipationRequired=False,automaticRetries=0,
    cpuPercentMaximum=5,privateCommitLimitBytes=2*1024**3,actualWindowsLowRamStop=True,
    qualityQualified=False,d2Complete=False,automaticProductAdoption=False,
    run='E:/CodexData/Companion/product-d1d2-20261114/public-acoustic-context-r1/trial-r1',
    originalSpeakerTrialProtection=str(D/'protection-r11.json'))
write(C/'protocol.json',protocol)
helpers=['companion_local_qwen_worker_20261114.py','companion_local_pcm_session_20261114.py',
         'practical_qwen_streamed_loader_20261107.py','companion_local_decode_recovery_20261114.py',
         'practical_qwen_bounded_decode_20261107.py','companion_community1_adapter_20261115.py',
         'moss_windows_resource_limits_20261104.py']
write(C/'worker-binding.json',dict(workerSha256=sha(S/'public_acoustic_context_worker_20261115.py'),
    runnerSha256=sha(S/'run_public_acoustic_context_20261115.py'),protocolSha256=sha(C/'protocol.json'),
    helpers={str(S/n):sha(S/n) for n in helpers},
    baselineControlSha256=sha(controls[0]),
    baselineDocumentBindings={str(baseline/'sessions'/r['id']/'document.json'):sha(baseline/'sessions'/r['id']/'document.json') for r in audio}))
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    sourceCommit=read(D/'protection-r11.json')['modelCommit'],sourceRemoteVerified=True,
    publicSpeakerTrainingProtection=str(D/'protection-r11.json'),
    overlapOrderDiagnosis=str(D/'context-matched-baseline-r3/overlap-order-diagnosis.json'),
    publicAcousticContext=str(C),publicAcousticContextProtocol=str(C/'protocol.json'),
    publicAcousticContextRun=protocol['run'],publicAcousticContextStatus='FROZEN_READY_NOT_TRAINED',
    publicAcousticAdapterAdoptedInProduct=False)
v['next']='执行唯一冻结声学侧适配：50段真实公开无重叠多轮对话13.18分钟、只训音频编码器后8层q/v，语言模型及原参数冻结，1epoch/25更新，验证沿原32段和中英文/自然混合控制；所有恢复点保留，未同时改善两来源且不退步其它控制就拒绝，不追加变体。候选若过仅接原整会，D2和默认不先变。'
v['logResult']+=' '+now+' 人物适配完整证据/528024B最终权重和8恢复点已逐字节保护198文件，私有远端独立回读提交'+e['sourceCommit']+'；805126656B中间路线数组仍在E盘不入Git，hash清单已保护。文字0新神经调用复查固定12段：161/1476原错误中40可由允许重叠整句重排序解释，余121/1476=8.1978%仍混合声学/拼写标注，不改原分。核对SOT原文为说话人整流FIFO及分隔符，不能把普通换行拼接冒充SOT。准备声学多轮数据首轮仅11段不足20已停止，无训练；初次系统Python无soundfile已改用现有AMD解释器，包不变。随后只查64份公开train标注有效覆盖、排除原开发整日及验证两整日，按有效片段数最多且日期词序决胜选择新增L20200707S01原FLAC，公开LFSSHA全文件通过，旧不足来源原件保留。冻结3train源50段790.557s、至少两人物且含完整短响应/无重叠/无标签标记，自然mic0无增益等；原32验证及英文/中英混合控制保持。下一次唯一试验只训声学编码后8层131k量级LoRA，区别旧128孤立短句LM，1epoch/25更新、每更可恢复，不调参/换片碰结果。尚未跑这份声学训练，D1可用/D2未过/默认未改。'
write(p,v)
print(json.dumps({'protocol':str(C/'protocol.json'),'trainingCases':50,'seconds':prep['totalSeconds'],'run':protocol['run']},ensure_ascii=False))
