"""Close actual iGPU admission/DSP results in the original model workpoint."""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';J=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
at=datetime.now().astimezone().isoformat(timespec='seconds')
C=J/'context-activity-r1/webrtc-presence-r1';run=E/'context-activity-r1/webrtc-presence-r1/run-mode0'
done=read(run/'completed.json');assert len(done['completed'])==2 and done['newNeuralCalls']==0 and done['parameterUpdates']==0
scores={}
for meeting in ['ES2003b','EN2002a']:
    value=read(run/(meeting+'-score.json'));pred=read(run/(meeting+'-composition/prediction.json'))
    packet=read(run/(meeting+'-presence.json'))
    assert packet['allOriginalFramesCovered'] and pred['originalActiveIdentitiesPreserved'] and pred['unknownIdentitySeconds']==0
    assert value['collarSeconds']==0 and value['overlapIncluded'] and value['oneOriginalWholeSourceIdentityMappingForAllConditions']
    assert not value['advanceToSecondEnglishSource'] and not value['originalDerTenPercentGate']
    scores[meeting]={'baseline':value['originalRawMultiVoice'],'combined':value['combinedWithOriginalFixedIdentity'],
        'relativeDerReduction':value['relativeDerReduction'],'passesFixed20PercentReduction':False,'originalDerTenPercentGate':False,
        'audioSeconds':packet['audioSeconds'],'dspSeconds':packet['seconds'],'dspWindows':packet['dspWindows'],
        'fullOriginalFrames':packet['frames'],'tailZeroPaddingSamples':packet['tailZeroPaddingSamples'],
        'score':str(run/(meeting+'-score.json')),'scoreSha256':sha(run/(meeting+'-score.json'))}
iC=J/'igpu-native8-r1';istate=read(iC/'results/cpu-native8-control61/completed-state.json')
assert istate['newNeuralPushes']==0 and not istate['gpuUsed'] and 'CpuThermalLimit' in istate['error']
ilog=E/'system-restart-20261116-2315/igpu-native8-thermal-r1';iterm=read(ilog/'completed.json');assert iterm['ownedStopRequested']
cpu=E/'context-activity-r1/silero-presence-day-r2/run-default/state.json';cs=read(cpu);assert cs['newNeuralCalls']==0
report={'at':at,'state':'WEBRTC_FIXED_DSP_REJECTED_780M_ADMISSION_STOPPED_BEFORE_COMPUTE',
    'ownerSteering':'核显; use780M for daytime compatible inference rather than treating absent6800XT as noGPU.',
    'igpu':{'control':str(iC),'workerState':istate['state'],'error':istate['error'],
        'neuralPushes':0,'gpuInitialized':False,'trainingUpdates':0,
        'actualInferenceCompatibilityOrPerformanceProven':False,'originalStrict6800SelectorUnchanged':True,
        'loggerTerminal':str(ilog/'completed.json'),'ownedLoggerClosed':True,
        'reason':'Original95C task guard interrupted60s admission before native DLL/model loading. Not evidence780M cannot compute, and not reboot-cause proof.',
        'observationRecordingLimitation':'Worker retains the last successful temperature observation, rather than the exception trigger observation. Original sensor timeline and error are retained; no fabricated trigger value.',
        'next':'No unchanged automatic retry; explicit780M path is frozen for a later admissible inference window.'},
    'cpuSilero':{'state':cs['state'],'newNeuralCalls':0,'parameterUpdates':0,'receipt':str(cpu),
        'decision':'Admission stopped; no new quality result, no unchanged retry.'},
    'webrtc':{'mode':0,'frameMilliseconds':10,'extraPaddingSmoothingOrThresholdSweep':False,
        'sourceCount':2,'wholeSourceSeconds':sum(x['audioSeconds'] for x in scores.values()),
        'dspWindows':done['processedDspFrames'],'workerPeakPrivateCommitBytes':done['limits']['jobPeakPrivateCommitBytes'],
        'cpuCapPercent':5,'newNeuralCalls':0,'parameterUpdates':0,'scores':scores,
        'decision':'Reject this fixed VAD plus unchanged Native8 gap-only identity composition: both fail the predeclared20percent relative DER reduction and original10percent full DER gate. No mode/frame/pad grid.',
        'interpretation':'A presence-only supplement cannot be assumed to solve missed/overlapping speakers or English word recognition. These scores do not establish a universal failure of all speech detectors.'},
    'quality':{'newAsrWerCerMeasured':False,'existingWholeEnglishWer':1051/5781,'existingOneWholeChineseCer':428/8325,
        'theseAreIndividualWholeMeetingScoresNotUniversalLanguageAccuracy':True,
        'minimumErrorRateBelow':0.05,'targetErrorRateAtMost':0.02,'qualityQualified':False,'saleQualified':False},
    'next':'Keep repaired English1828-clip/4.1814h fixed adaptation input and original held-out admission. Daytime explicit780M inference when guards admit; no CPU/iGPU training. NightGPU actual gradient/largestshape/recovery proof before one fixed epoch. Speaker failures remain separate from raw-language ASR and overlap gates.',
    'finalHoldoutOpened':False,'productDefaultChanged':False,'weightsChanged':False}
target=J/'context-activity-r1/daylight-igpu-dsp-20261117.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['currentOwnedNeuralWorker']=None
o['integratedGpuAuthorization20261117'].update(state=report['igpu']['workerState'],ownedThermalLoggerClosed=True,receipt=str(target))
o['daytimeDspPresence20261117']={'state':'REJECTED_FIXED_WEBRTC_MODE0_NO_THRESHOLD_GRID','receipt':str(target),
    'scoreFiles':[v['score'] for v in scores.values()],'qualityQualified':False}
x['at']=at;x['state']=o['state']=report['state']
x['next']='白天有780M，可做兼容的本地推理/小规模正确性和资源实测；已冻结独立Vulkan入口，旧6800路径不改。本轮原95°C门在加载前中止，0模型调用，不能称核显不支持/已跑通；自有温度logger已关，不同条件不重试。CPU5%/峰17.2MiB的WebRTC固定mode0/10ms已覆盖两完整英文会议4252.523s/425253窗，沿原Native8人物填空融合后ES26.018→24.470%、EN31.077→28.206%DER，仅相对5.95%/9.24%，均未过20%保留门且10%整会门失败，淘汰不网格。英文转写仍18.18%WER/中文一整会5.14%CER；原1828片4.1814h/457更新训练输入与95/98、人物/事实/盲测门保持，0CPU或核显训练，下一步原GPU实际梯度/最大形状/恢复证明后固定一轮。'
x['logResult']+='\n\n'+at+'｜Owner核显纠正已承接。实作独立780M Vulkan FP16推理入口和原CPU61后验对照器，不改旧6800专用selector/系统驱动；原95°C任务准入在DLL/模型加载前触发，0GPU初始化/0神经push/0训练，未产生速度或兼容结论，不以该任务门诊断重启。自有logger已于11:43:22闭合；当前无自有模型在跑。另完成一项可执行且不同原理的传统WebRTC VAD：固定官方wheel2.0.14.post1/mode0/16k16bit/10ms，2秒数字静音0误报、两整场4252.52275秒原PCM425253窗全部覆盖，单进程CPU5%峰17993728B，约6秒内完成且无Torch/GPU/训练。保持原Native8已活人物和连续后验，仅填原空白，零未知身份；原0collar/含重叠/同一全场身份映射评分：ES2003b DER26.0181→24.4702%(相对5.9493%)，EN2002a31.0766→28.2058%(9.2380%)，两者均不达预先20%保留门/原10%全场门，淘汰固定方案，不调mode/pad/帧长碰结果。该失败不扩大成所有VAD无效，也不将说话人分数当中英文转写成绩；原中文/英文WER/CER未变、产品默认未变、最终保留音频/标注未读。继续原英文1828片4.1814h数据/457步适配及人物核心缺口，原资源和质量门不放宽。收据'+str(target)+'。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'receipt':str(target),'scores':{k:{'DER':v['combined']['DER'],'relativeReduction':v['relativeDerReduction']} for k,v in scores.items()},'newNeuralCalls':0,'trainingUpdates':0},ensure_ascii=False))
