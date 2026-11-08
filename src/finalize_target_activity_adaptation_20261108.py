"""Close the two finite activity-adaptation controls without promoting a model."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=R/'docs/handoffs/20261108-target-activity-adaptation'
OLD=R/'docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=datetime.now().astimezone().isoformat(timespec='seconds')
trials=[]
for name,folder in [('initial',C),('paired-control',C/'paired-control')]:
    protocol=read(folder/'protocol.json')
    for item in protocol['sourceFiles']:
        assert sha(item['file'])==item['sha256'],item['file']
    best=read(folder/'best-checkpoint.json')
    assert sha(best['checkpoint'])==best['checkpointSha256']
    assert best['binding']['protocolSha256']==sha(folder/'protocol.json')
    review=read(folder/'evaluation/review.json')
    assert review['state']=='ADAPTED_ACTIVITY_HEAD_REJECTED_BEFORE_FULL_EXPANSION'
    assert not review['allPredeclaredShortCriteriaPassed'] and not review['qualityQualified']
    assert review['actualRawMixtureClips']==13 and review['targetQueries']==67
    assert review['sameFixedAuthorThreshold']==.7 and review['noThresholdOrWindowSweep']
    assert review['newAsrOrSeparationCalls']==0 and review['noTranscriptFiltering']
    assert not review['productDefaultChanged'] and not review['finalHoldoutOpened']
    assert read(folder/'run.json')['state']=='COMPLETE_ADAPTATION_EVALUATION_REVIEW_REQUIRED'
    gradient=read(folder/'gradient-proof.json')
    assert gradient['nativeDecoratedUnwrappedAndCachedEvalLogitsExactlyEqual']
    assert gradient['backboneValuesAndBuffersUnchanged'] and gradient['speakerEncoderUnchanged']
    trials.append({'trial':name,'state':review['state'],
        'protocolSha256':sha(folder/'protocol.json'),
        'trainingHistorySha256':sha(folder/'training-history.json'),
        'evaluationReviewSha256':sha(folder/'evaluation/review.json'),
        'bestHeadSha256':best['checkpointSha256'],
        'baselineSeparateRoomValidationLoss':best['baselineValidationLoss'],
        'selectedSeparateRoomValidationLoss':best['validationLoss'],
        'relativeValidationLossReduction':1-best['validationLoss']/best['baselineValidationLoss'],
        'aggregateWrongActivitySeconds':review['aggregateWrongActivitySeconds'],
        'meetings':[{'meeting':m['meeting'],'positiveWindowRecall':m['candidate']['positiveWindowRecall'],
            'absentWindowFalseAcceptance':m['candidate']['absentWindowFalseAcceptance'],
            'missedTargetSeconds':m['candidate']['missedTargetSeconds'],
            'falseTargetSeconds':m['candidate']['falseTargetSeconds'],
            'shortEventRecall':m['candidate']['shortEventRecall'],
            'overlapTargetActivityRecall':m['candidate']['overlapTargetActivityRecall'],
            'gates':m['predeclaredGates']} for m in review['meetings']],
        'ownedStageSecondsIncludingKnownInterruptions':review['actualOwnedStageSecondsIncludingKnownInterruptions'],
        'sampledPrivatePeakBytes':review['sampledPrivatePeakBytes']})

# The paired-control target which was already present in the first trial must
# retain the independently prepared original labels, not a changed definition.
paired={r['id']:r for r in read(C/'paired-control/paired-training-labels.json')}
original={r['id']:r for r in read(C/'training-labels.json')}
inputs=read(C/'training-inputs-only.json')
for item in [r for r in inputs if r['role']=='train']:
    row=paired[item['id']]
    assert len(row['people'])==7 and len(set(row['people']))==7
    assert all(len(labels)==25 for labels in row['labels'])
    assert row['labels'][row['people'].index(item['person'])]==original[item['id']]['activityLabels']
assert len(paired)==64
parity=read(C/'cached-base-parity.json')
assert parity['queries']==67 and parity['maxAbsoluteProbabilityError']==0

# The original ordinary transcription is a protected bypass, not newly inferred.
B7=C.parent/'20261107-model-generation-recovery'
ordinary_before=B7/'practical-alignment-r1/derived-onset/transcripts/S_R004S03C01/model-output.json'
ordinary_after=B7/'practical-conditioned-ps4-r1/verified-patched-full-meetings/S_R004S03C01/model-output.json'
assert sha(ordinary_before)==sha(ordinary_after)
baseline=read(OLD/'review.json')
unadapted=sum(m['candidate']['wrongActivitySeconds'] for m in baseline['meetings'])
native=sum(m['baseline']['wrongActivitySeconds'] for m in baseline['meetings'])
paired_error=trials[1]['aggregateWrongActivitySeconds']['candidate']

decision={'at':now,'state':'BOUNDED_REAL_MEETING_HEAD_ADAPTATION_REJECTED_BASELINE_RETAINED',
    'ownerQuote':'需要你向着正确方向推进',
    'actualChange':'Implemented a trainable, byte-verified frozen-backbone adaptation path on the existing released target-activity model; actually trained two finite3epoch controls on additional real meetings. No new ASR/separation/backend default.',
    'decision':'Neither adaptation meets the unchanged cross-meeting activity criteria. Retain the existing NativeFP16 research baseline; do not install either head, expand it to full ASR/separation, add epochs, sweep cutoffs or call loss reduction a product gain.',
    'comparison':{'unit':'Sum of target-wise missed plus false activity seconds over the same13original30s clips/67queries. Simultaneous targets are counted separately. Not wordCER, standardDER, final<5% or minutes accuracy.',
        'nativeBaseline':native,'unadaptedTargetActivity':unadapted,
        'initialAdaptation':trials[0]['aggregateWrongActivitySeconds']['candidate'],
        'sameMixtureAllTargetsAdaptation':paired_error,
        'pairedReductionVersusUnadapted':1-paired_error/unadapted,
        'pairedReductionVersusFirstAdaptation':1-paired_error/trials[0]['aggregateWrongActivitySeconds']['candidate'],
        'pairedStillWorseThanNativeBaseline':paired_error>native},
    'trials':trials,
    'data':{'trainMeetings':['20200707_L_R001S08C01','20200708_L_R002S01C01'],
        'validationMeeting':'20200623_S_R001S01C01','originalMicrophoneChannel':0,
        'trainUniqueSeconds':64*4,'validationUniqueSeconds':32*4,
        'targetConditionsPerEpochInitial':64,'targetConditionsPerEpochPaired':448,
        'clipGroupsPerEpochBoth':64,'optimizerUpdatesBoth':48,'epochsBoth':3,
        'trainingAndValidationProfilesAreSupervised':True,
        'deploymentProfilesRemainAutomaticAndDisjoint':True,
        'roomSeparatedButPhysicalSpeakerDisjointnessNotEstablished':True,
        'tinyPilotNotEvidenceThatAllLargerOrDifferentAdaptationMustFail':True,
        'noSyntheticMixturesOrCleanPerPersonWaveformTargets':True},
    'interpretation':[
        'First adaptation increased recall but also false acceptance; lower separate-room cross_entropy did not predict successful attribution on the existing real deployment controls.',
        'All-profile supervision on identical mixtures reduced erroneous activity versus both target-activity predecessors, but missed short and overlapped target speech and remained worse than the existing native baseline.',
        'This is evidence against promoting this finite small-head recipe; it does not isolate data scale, acoustic representation, profile quality and architecture as a single proven root cause.'
    ],
    'resourceAndCost':{'hardCpuPercent':5,'neuralPrivateCommitLimitBytes':2*1024**3,
        'maximumActualRecordedNeuralJobPeakBytes':max(read(p)['limits']['jobPeakPrivateCommitBytes'] for folder in [C,C/'paired-control'] for p in [folder/'probe-state.json',folder/'train-state.json',folder/'evaluate-state.json']),
        'gpuUtilizationHardCapped':False,'otherApplicationsClosed':False,
        'stageTimesAreNotTranscriptionOrMeetingMinutesLatency':True,
        'separateAudioPreparationSeconds':read(C/'audio-preparation-state.json')['wholePreparationSeconds'],
        'technicalFailureBeforeAnyPairedTrainingUpdate':read(C/'paired-control/explicit-directory-recovery.json'),
        'originalTechnicalFailureAndLogsRetained':True},
    'protection':{'ordinaryAsrFile':str(ordinary_before),'ordinaryAsrSha256':sha(ordinary_before),
        'ordinaryBypassByteIdentical':True,'newOrdinaryAsrCalls':0,'newSeparationOrAsrCalls':0,
        'cachedNative67ProbabilityMaxError':0,'pairedOriginalTargetLabelsIdentical':True,
        'productDefaultChanged':False,'referenceUsedToFilterProductTextOrAudio':False,
        'finalHoldoutOpened':False,'phoneOrBoardAccessedThisBatch':False,
        'realCustomerTrialPerformed':False},
    'remaining':['ordinary strictCER<5%','complex per-person words and overlap separation',
        'cross-room/corpus and final held-out meeting qualification','factual minutes',
        'installed Windows/Android/card end-to-end verification','sale qualification'],
    'next':'继续原RM-OVERLAP，先做分离主干的标注辅助上限诊断，保持同一真实会议原音/目标声纹/固定文字评分：仅用参考时间标注提供正确说话人活动，单独报告为oracle研究对照，比较逐人漏字、串话与插入，绝不冒充产品准确率或直接过滤产品文字。只有活动已知正确时仍分不开，才进入有干净源监督的分离主干适配；若正确活动能解决，再针对活动模块准备更广的真实训练与独立验证。当前小头支路停止，不继续同权重/阈值/轮数试跑。普通原字/原音/模型默认及全部<5%/事实/双端实卡/售卖门保留。',
    'qualityQualified':False}
atomic_json(C/'decision.json',decision)

readme=R/'model-research/README.md'
marker='Observed finite real-meeting activity adaptation,2026-11-08:'
text=readme.read_text(encoding='utf8')
assert marker not in text
paragraph=f'''

{marker} the existing nomo-pvad/native ERes2NetV2 pair now has an actual trainable adaptation path, rather than a proposed training plan. Exact native decorated/unwrapped/cached logits, all67original probabilities (max error0), finite gradients and unchanged frozen backbone/BN/speaker weights were checked before real training. Only4,236,674existing conditioning/activity-head parameters are trainable. Additional original AISHELL-4 microphone0 speech supplies64four-second train clips from two new train_L sessions and32validation clips from a different train_S room. This is only256s/128s of unique audio, not generalization proof; physical-speaker independence is not established. Official CC BY-SA4.0 versus mirror-card Apache2 metadata discrepancy remains recorded. Partial range reads verify extracted payloads/official annotation text, not whole remote FLAC hashes. No private audio is uploaded.

Two bounded3epoch controls keep the base weights, seed, optimizer,48updates,0.7cutoff, automatic deployment profiles and old13real clips/67queries fixed. The initial single-target recipe lowers separate-room CE0.759331→0.603265 but raises target-wise wrong activity to{decision['comparison']['initialAdaptation']:.6f}s. The one causal data control queries every identical training mixture with all7same-meeting profiles (448conditions/epoch), starts again from upstream weights, and lowers CE to0.628825. It reduces wrong activity to{paired_error:.6f}s versus{unadapted:.6f}s unadapted, but the existing NativeFP16 baseline is{native:.6f}s. Both adaptations fail all-meeting acceptance and are rejected. Paired positive-window recall/absent-window false acceptance is L75.20%/6.07%,S94.74%/13.16%,AMI65.83%/39.81%. These correlated3s-window and target-wise activity diagnostics are not wordCER or standardDER. More recall alone and lower loss are not product progress. The small data budget does not prove every larger/different adaptation impossible.

Neural workers remain CPU5%/private2GiB/low-priority, with actual Windows low-memory cancellation; maximum recorded neural Job private peak is{decision['resourceAndCost']['maximumActualRecordedNeuralJobPeakBytes']}B. The paired first training attempt failed before any forward/update because its cache parent was omitted; the failure is retained, that directory preparation was corrected, and one explicit technical recovery leaves the frozen worker/protocol/model settings unchanged. Stage timing includes this failed attempt; training/activity time is not end-to-end transcription or minutes latency. The two validation-selected head artifacts are retained as unqualified research versions. No extra full separation/ASR, installed app/card changes, final-holdout opening or real-customer trial occurred. Ordinary transcription bypass remains byte-identical. Read evidence/20261108-target-activity-adaptation/decision.json and both evaluation/review.json files. Stop this tiny-head recipe, retain the native baseline and use a clearly labeled annotation-assisted upper-bound diagnostic to decide whether speaker activity or separation itself warrants the next adaptation. Raw strict<5%, complex per-person content, cross-domain, factual minutes, installed Windows/Android/card and sale gates remain open.
'''
readme.write_text(text+paragraph,encoding='utf8')
print(json.dumps({'state':decision['state'],'comparison':decision['comparison'],
    'maxNeuralJobPrivateBytes':decision['resourceAndCost']['maximumActualRecordedNeuralJobPeakBytes'],
    'ordinaryAsrProtected':True,'noProductAccuracyGainClaimed':True},ensure_ascii=False),flush=True)
