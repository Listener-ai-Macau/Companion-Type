from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'independent-voice-return-probe-r1';read=lambda p:json.loads(p.read_text(encoding='utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not (C/'protocol.json').exists()
runner=S/'run_independent_voice_return_probe_20261115.py';text=runner.read_text(encoding='utf-8')
text=text.replace('FIXED_SMALL_ASR_ADAPTER','INDEPENDENT_VOICE_PROBE').replace('FIXED_ADAPTER_TRIAL_SCORING_PENDING','INDEPENDENT_VOICE_PROBE_SCORING_PENDING').replace('FIXED_ASR_PHASE_RETAINED','VOICE_PROBE_RETAINED').replace('>3600','>300')
runner.write_text(text,encoding='utf-8')
base=read(D/'community1-comparison-r1/protocol.json')
protocol={k:base[k] for k in ['additionalSites','runtimeManifest','runtimeManifestSha256','rocmBlasLibrary','rocmBlasLibrarySha256']}
protocol.update(state='FROZEN_SINGLE_UNGATED_INDEPENDENT_VOICE_RETURN_DIAGNOSIS',
    at=datetime.now().astimezone().isoformat(),plannedProbeSha256=sha(C/'planned-probe.json'),
    audioOnlySha256=sha(C/'audio-only.json'),scoringOnlySha256=sha(C/'scoring-only.json'),
    modelBindingSha256=sha(C/'model-binding.json'),
    repository='pyannote/wespeaker-voxceleb-resnet34-LM',revision='837717ddb9ff5507820346191109dc79c958d614',
    gated=False,accountOrTokenUsed=False,ownerParticipationRequired=False,
    probeOnly=True,referenceAssistedCuts=True,fullSpeakerDiarizationProduced=False,
    newTraining=False,originalReferencesOrScoringChanged=False,
    priorOriginalSpeakerFailure=str(D/'public-speaker-development-r1/final-decision.json'),
    priorAcousticFailure=str(D/'public-acoustic-context-r1/decision.json'),
    run='E:/CodexData/Companion/product-d1d2-20261114/independent-voice-return-probe-r1/probe-r1',
    cpuPercentMaximum=5,privateCommitLimitBytes=2*1024**3,actualWindowsLowRamStop=True,
    qualityQualified=False,saleQualified=False,automaticRetries=0)
write(C/'protocol.json',protocol)
helpers=['companion_community1_adapter_20261115.py','companion_local_pcm_session_20261114.py','moss_windows_resource_limits_20261104.py']
write(C/'worker-binding.json',dict(workerSha256=sha(S/'independent_voice_return_probe_worker_20261115.py'),
     runnerSha256=sha(runner),protocolSha256=sha(C/'protocol.json'),helpers={str(S/n):sha(S/n) for n in helpers}))
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    sourceCommit=read(D/'protection-r12.json')['modelCommit'],sourceRemoteVerified=True,
    publicAcousticContextProtection=str(D/'protection-r12.json'),
    independentVoiceReturnProbe=str(C),independentVoiceReturnProbeProtocol=str(C/'protocol.json'),
    independentVoiceReturnProbeRun=protocol['run'],independentVoiceReturnProbeStatus='FROZEN_READY_NOT_EXECUTED')
v['next']='小样本人物与声学适配已保护并拒绝默认，不追加变体。按固定7段公开原音，验证无门禁独立WeSpeaker声纹是否能区分原34分钟难会的长时间返场声音：4个早期参考/3个返场查询只进独立评分，神经模型只收匿名PCM；CPU/GPU真实权重数值控制先过，三次均匹配原人后才有理由设计一份原整会组合验证。此为有原标注切段的诊断，不作无监督人数/分离/整会DER或D2证明，原默认/原门不改，Owner无需参与。'
v['logResult']+=' '+protocol['at']+' 两固定公开微调已结束，声学230文件/81.459MB逐字节保护并独立私有远端回读'+e['sourceCommit']+'；新262144参数为声学实测，先前准备日志131k量级为估算，实际以该结果为准。三训练TextGrid与既有官方下载2MiB原压缩包成员逐字节一致，确认来源不等于每字音义绝对正确。接续原组合架构唯一剩余可辨解释：独立声纹表征是否仍区分不开长离场回归声音。公开WeSpeakerResNet34-LM HF版本837717d、26.645MB权重SHA366edf44f4c80889a3eb7a9d7bdf02c4aede3127f7dd15e274dcdb826b143c56，无门禁/无token/无需账户信息；仅参考辅助7段34.9745s固定3–8s完整无重叠原mic0，先前缓存平均方案用的是Nemotron内部表征，和此独立验证模型不同。早期4人物首个合格片段、返场003-M首3合格片段由原标注固定、标签不进NN，原D2分与最终留出不变。若3查询任一未正确最高匹配则停此固定诊断，不换参考/窗口/阈值。成功也只允许设计完整无提示组合，不能说已过人物质量。'
write(p,v)
print(json.dumps({'control':str(C),'run':protocol['run'],'newTraining':False},ensure_ascii=False))
