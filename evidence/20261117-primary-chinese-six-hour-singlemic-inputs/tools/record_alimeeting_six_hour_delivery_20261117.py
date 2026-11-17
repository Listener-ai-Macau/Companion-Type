"""Close verified primary Chinese inputs; preserve model/quality work as unfinished."""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';J=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
O=E/'meeting-domain-data-r1/alimeeting-official-intake-r2';C=O/'range-training-cohort-r2'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(C/'protocol.json');run=read(C/'acquisition-r1/completed.json');proof=read(C/'integrity-r1/completed.json')
header=read(O/'primary-wave-headers-r1/completed.json');split=read(O/'primary-train-eval-person-split.json')
assert proof['state']=='PASS_5027_ORIGINAL_CHINESE_ASR_INPUTS_SOURCE_TEXT_PCM_TIMING_AND_PERSON_INTEGRITY'
assert run['completedExamples']==proof['verifiedExamples']==5027 and proof['verifiedFrames']==345643200
assert proof['all5027OriginalLabelsAndFrameIntervalsExact'] and not proof['participantIntersection']
assert not proof['modelTrainingAdmitted'] and proof['newNeuralCalls']==proof['parameterUpdates']==0
at=datetime.now().astimezone().isoformat(timespec='seconds')
report={'at':at,'state':'SIX_HOUR_PRIMARY_CHINESE_NONOVERLAP_ASR_INPUTS_DELIVERED_MODEL_TRAINING_NOT_STARTED',
    'taskScope':'Verified nonoverlap Chinese ASR acoustic-adaptation inputs. Not continuous diarization/overlap training or a new quality result.',
    'source':{'officialDataset':'modelscope/AliMeeting (also OpenSLR119)',
        'officialPublishedTrainMeetings':209,'officialPublishedTrainPeople':452,
        'all209OriginalTextgridsFetched':True,'all209OriginalWaveHeadersChecked':True,
        'allConvertedRecordingFrameCountsIndependentlyReproduced':True,
        'originalAnnotationsBeyondRealAudioEnd':246,'wholeSourcesExcluded':header['inadmissibleSourceMeetings'],
        'conversionIntervalsClippedWhileKeepingFullText':5,
        'originalSourcesOrLabelsRewritten':False,'cleanSourceMeetings':200,
        'paperCountCorrection':'Paper212/456 differs from the actual official released file index209/452. Conversion inventory matches the official index; earlier incomplete-mirror inference is corrected, not hidden.',
        'shortTierSchemaCorrection':'Some official tiers use gender_SPKID without meeting prefix. Both published forms were parsed with interval-count and near-file speaker verification; no label renamed in the originals.'},
    'inputs':{'examples':5027,'audioSeconds':21602.7,'audioHours':21602.7/3600,
        'meetings':194,'venues':12,'globalTrainingPeople':374,'rawTextCharacters':121579,
        'sampleRate':16000,'channels':1,'bits':16,'sourceChannelIndex':0,
        'manifest':run['manifest'],'manifestSha256':run['manifestSha256'],
        'paddingSeconds':0,'speedPerturbation':False,'gainResamplingDenoisingOrChannelAverage':False,
        'wholeOriginalUtteranceTextAndBoundariesPreserved':True,
        'trainingAudioActualBytes':run['writtenClipBytes']},
    'integrity':{'receipt':str(C/'integrity-r1/completed.json'),'sha256':sha(C/'integrity-r1/completed.json'),
        'all5027RawTextFrameIntervalsAndWaveHeadersChecked':True,'all5027PcmChecksumsChecked':True,
        'everyOutputByteCheckedAgainstSelectedSourceChannelAtCapture':True,
        'freshIndependentVenueSourceControls':12,'trueOtherSpeakerOverlaps':0,'duplicateSourceFrames':0,
        'training374VersusAliEvaluation25Intersection':[],
        'aliEvaluationSpeakerProof':str(O/'primary-train-eval-person-split.json'),
        'evaluationAudioOrTextgridRead':False,'testIndexOrPayloadRead':False,
        'originalAishellCrossCorpusPersonIsolationProven':False,'originalAishellFinalHoldoutOpened':False},
    'resources':{'workerCpuCapPercent':5,'ioThreads':4,'privateCommitCapBytes':256*1024**2,
        'acquisitionPeakPrivateBytes':run['limits']['jobPeakPrivateCommitBytes'],
        'independentIntegrityPeakPrivateBytes':proof['limits']['jobPeakPrivateCommitBytes'],
        'acquisitionSeconds':run['elapsedSeconds'],'integritySeconds':proof['elapsedSeconds'],
        'rawRangeBytesFetched':run['downloadedRawRangeBytes'],'reusedFirstMonoExamples':run['reusedVerifiedMonoExamples'],
        'actualOwnedDataBytes':run['actualOwnedDataBytes'],'maximumOwnedDataBytes':12*1024**3,
        'conservativeCombinedEnvelopeBytesIncludingPreviousFullSourceTransfers':P['budget']['conservativeCombinedEnvelopeBytes'],
        'minimumDiskReserveBytes':50*1024**3,'credentialValuesPrintedOrPersisted':False},
    'firstWaveRecovery':{'originalFailure':str(O/'first-mic-source-r1/terminal-fsync-failure.json'),
        'independentWholeSourceAndMonoProof':str(O/'first-mic-source-r1/post-source-check-r2/completed.json'),
        'rootFix':'Windows fsync requires a write-capable handle here; r+b plus precommit checksum snapshot. No conversion repeated; independent source read verified existing output before commit.'},
    'model':{'newNeuralCalls':0,'parameterUpdates':0,'cpuOrIntegratedGpuTraining':False,
        'newAsrWerCerMeasured':False,'newSpeakerDerMeasured':False,'modelTrainingAdmitted':False,
        'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,
        'original95Floor98TargetAndWholePersonFactFinalGatesChanged':False},
    'timeValueDecision':{'ownerQuote':'务必确认方向是正确的, 另外看看尽量每一笔时间之处都是值得的才行',
        'closeDataAcquisitionHere':True,'noMoreCorpusExpansionWithoutNewFailureEvidence':True,
        'priority':'Actual model evidence: fixed English adaptation preflight/one epoch/paired validation under the original resource constraints. Chinese dataset is now locally usable source input; no automatic second model/parameter grid.',
        'retentionGate':'Keep a component only for the predeclared independent improvement and no-regression evidence; do not count input hours or reports as model accuracy.',
        'remaining':['Actual nativeGPU loss/gradient/largestshape/checkpoint and fixed1828example457update English epoch.',
            'Chinese model-specific training contract and approved runtime; oldAISHELL cross-corpus person qualification remains unresolved.',
            'Speaker activity/person text/facts and original reserved final qualification remain open.']}}
target=J/'meeting-domain-data-r1/alimeeting-primary-six-hour-delivery-20261117.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['currentOwnedDataWorker']=None
o['chinesePrimarySourceAcquisition20261117'].update(state=report['state'],delivery=str(target),
    trainingManifest=run['manifest'],integrity=str(C/'integrity-r1/completed.json'),trainingAdmitted=False)
o['chineseAlternativeTrainIntake20261117'].update(state=report['state'],receipt=str(target),trainingReady=False)
o['ownerTimeValueReview20261117']=report['timeValueDecision']
x['at']=at;x['state']=o['state']=report['state']
x['next']='中文数据采集到此收口，不再扩库：官方209原标注/原WAV头已核，9场越音频末尾整场排除；5027片21602.7s/194场/12场地/374训练人已取得完整单麦PCM并独立验原字/原时间/帧/无重叠/无重复，另12场地重取官方字节复核全符，Ali训练对验证25人零交集。实际数据约6.195GB，原12GiB/50GiB预留/CPU5%/私有256MiB保留；0神经调用0训练0新准确率。原AISHELL跨库人员隔离/复杂说话人/事实/最终盲测仍开放。按Owner时间价值要求，优先能改变路线的模型证据：英文原1828片457更新的一次固定适配，实际GPU损失梯度/最大形状/恢复先过，随后同原样本/跨会议比较再决定保留；不网格、不把数据/报告当准确率。CPU VAD仅在原运行准入满足时跑已固定两整场比较，否则不反复重试。保护本批源与失败、更新原入口后继续最高可执行原项。'
x['logResult']+='\n\n'+at+'｜官方中文数据批次收口：5027片/345643200帧/21602.7s(6.00075h)已从官方原音精确取第一通道，原句和区间不改、0pad/0变速/0增益/0混通道，覆盖194场/12场地/374训练ID。固定采集423.219s，CPU5%峰89894912B/4IO；独立核验70.422s峰165060608B，全部5027原文/原帧区间/PCM/头/来源收据检查通过，直接对每条原区间逐一检查其他人重叠为0，排序检查重复源帧0，另按固定hash选12场地控制重取官方字节逐样本校验相符，Ali训练374对官方验证25全局ID零交集。全部原音/GT引用在本机，验证只读文件索引、无其音频/原标注，原AISHELL最终L未读且跨库人物资格未证。此为非重叠中文ASR适配输入，不是说话人连续流/重叠训练集，更不是新WER/CER/DER；本批0神经模型0优化器0更新。实际本任务数据6194986157B<原12GiB，保守计既有文件+两次整源核验+新范围流量+输出合计12737939567B仍<12GiB，50GiB磁盘预留不动，凭据仅内存不落盘/输出。Owner新强调每笔时间值得：该数据批次到此收口，后续不无故扩库，优先固定一次英文适配的实际GPU预检/前后独立比较；不达原门槛记录淘汰，不连续调参数碰结果，不把样本/文档数量计成准确率进步。收据'+str(target)+'。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'delivery':str(target),'examples':5027,'hours':21602.7/3600,'newNeuralCalls':0,'parameterUpdates':0,'dataAcquisitionClosed':True},ensure_ascii=False))
