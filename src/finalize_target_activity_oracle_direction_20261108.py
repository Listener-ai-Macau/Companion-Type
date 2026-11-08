"""Record the measured bottleneck and the paired-source prerequisite, no training."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-target-activity-adaptation/oracle-activity-diagnostic'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=read(C/'review.json');audit=read(C/'residual-boundary-audit.json')
assert audit['sourceReviewSha256']==sha(C/'review.json')
assert audit['totals']['oracleGatedSeparated']['interior_delete']>audit['totals']['oracleGatedMixture']['interior_delete']
assert not review['qualityQualified'] and review['allConditionsScored']
sources={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'PRIMARY_PAIRED_REAL_MEETING_SOURCE_AVAILABILITY_ONLY_NO_AUDIO_OR_TRAINING',
    'AliMeeting':{'primary':'https://www.openslr.org/119/','paper':'https://arxiv.org/abs/2110.07393',
        'observed':'Official release provides real Mandarin2–4person meetings with8channel far-field array and each participant headset recording; Train/Eval/Test are distinct released sets. CC BY-SA4.0. Train far73.24G and near22.85G are published archives.',
        'whyRelevant':'Paired real near/far recordings may expose which target words are lost through the separator and may provide supervised adaptation references after verification.',
        'notVerified':'Same-session pairing, sample/time alignment, person-channel mapping, physical-speaker/room split independence, cross-talk and reference quality have not been audited on downloaded payloads. Headset is not automatically a perfectly clean source.'},
    'AMI':{'primary':'https://groups.inf.ed.ac.uk/ami/corpus/',
        'signalMapping':'https://groups.inf.ed.ac.uk/ami/corpus/signals.shtml',
        'download':'https://groups.inf.ed.ac.uk/ami/download/',
        'observed':'Official corpus documents synchronized close/far recordings and individual headset channels; meetings.xml provides participant/channel information. Released signals and transcriptions CC BY4.0.',
        'whyRelevant':'Second-corpus paired-reference check; keep previously exposed EN2002a separate from any genuinely unused validation meeting.',
        'notVerified':'Recorded headsets contain room response/cross-talk; payload alignment and speaker reference purity need direct checks.'},
    'scope':'Source metadata was browsed; no paired audio payload was downloaded, no license override, no new model/checkpoint, no training or final-holdout opening. Do not call data preparation product accuracy progress.'}
atomic_json(C/'paired-real-source-availability.json',sources)
decision={'at':sources['at'],'state':'ACTIVITY_AND_TARGET_CONTENT_FAILURES_SEPARATED_NO_PRODUCT_PROMOTION',
    'measuredOn':'Two exposed Mandarin30s clips,6existing lanes, all12fixed waveform conditions, one unchanged nativeASR. This is a local causal diagnostic, not a general benchmark.',
    'reviewFile':str(C/'review.json'),'reviewSha256':sha(C/'review.json'),
    'residualAuditFile':str(C/'residual-boundary-audit.json'),'residualAuditSha256':sha(C/'residual-boundary-audit.json'),
    'actualResults':{'referenceCharacters':256,
        'ungatedSeparatedEdits':review['totals']['ungatedSeparated']['total'],
        'oracleGatedMixtureEdits':review['totals']['oracleGatedMixture']['total'],
        'oracleGatedSeparatedEdits':review['totals']['oracleGatedSeparated']['total'],
        'fullyContainedUtteranceDeletionsMixture':audit['totals']['oracleGatedMixture']['interior_delete'],
        'fullyContainedUtteranceDeletionsSeparated':audit['totals']['oracleGatedSeparated']['interior_delete'],
        'rootsDiffer':'root12 separated76vs mixture38edits; root27 separated37vs mixture50. Do not choose a backend per root using ground truth.'},
    'finding':'Correct target-active timing reduces false words but does not repair this extraction+ASR pipeline. Its excess omissions remain in fully contained utterances, so clip edges alone do not account for the failure. Stop treating activity-head improvement as a sufficient solution.',
    'causalLimit':'The controlled inputs support a relative failure of this separated-waveform+ASR combination. They do not uniquely identify waveform distortion versus recognizer sensitivity, prove all internally conditioned separators fail, or establish general meeting<5%.',
    'next':'继续原RM-OVERLAP，优先取得小批真实中文近场耳麦/远场混音配对，核对同一会议、说话人/声道、时间对齐和耳麦串音，再用每个人的参考音检查当前分离到底丢了什么。已核实AliMeeting官方提供近远场，AMI可作第二语料。完成配对参考验证前不扩大训练、不再重跑两个失败活动小头或换同类权重。数据可靠后只适配被实测定位的模块，并以未训练会议逐人漏字/串话/插入、普通语音不退步决定去留；最后再做完整会议、纪要事实和双端实卡。',
    'referenceDataPrerequisites':['Pinned source/audio hashes and matching session+person identities',
        'Sample alignment directly measured, no unverified resampling/latency assumptions',
        'Headset cross-talk/noise quantified before treating it as a source target',
        'Train/validation separated by actual available room/person metadata; exposed controls never treated as unseen',
        'Single far-field channel to reflect the one-microphone product; multichannel collection is not evidence of multichannel device capability'],
    'stopRules':['No additional cutoff/epoch/window sweeps on the failed small-head recipe',
        'No oracle transcript/audio gate installed or scored as a product result',
        'No per-root backend selection from known reference winners',
        'No broad separation training on transcript/activity labels presented as clean source supervision'],
    'cost':{'newAsrCalls':review['newAsrCalls'],'newSeparationCalls':0,'newTrainingRunsInOracleBatch':0,
        'ownedStageSeconds':review['actualOwnedSecondsIncludingKnownInterruptions'],
        'maximumNeuralJobPrivateBytes':review['maximumRecordedNeuralJobPrivateBytes'],
        'cpuPercentLimit':5,'neuralPrivateLimitBytes':2*1024**3,
        'noFurtherOwnedNeuralWorkerRequiredForThisDecision':True},
    'sourceAvailability':str(C/'paired-real-source-availability.json'),
    'originalOrdinaryAsrAndProductDefaultChanged':False,'phoneOrBoardAccessed':False,
    'finalHoldoutOpened':False,'wordCerGatePassed':False,'saleGatePassed':False,'qualityQualified':False}
atomic_json(C/'direction-decision.json',decision)
readme=R/'model-research/README.md';text=readme.read_text(encoding='utf8');marker='The reference-activity residual audit'
assert marker not in text
text+='\n\n'+marker+' attributes28oracle-separated versus9oracle-mixture deletions to fully contained utterances in one minimum edit alignment; residual loss is not confined to clip-edge-straddling reference sentences. Root12regresses while root27improves, so no ground-truth per-root winner is promoted. This supports inspecting target-content preservation in the current extraction+ASR combination, not further activity-only tuning, and does not uniquely identify distortion versus recognizer sensitivity. Official AliMeeting supplies real Mandarin near/far recordings; AMI supplies synchronized individual headset/far-field recordings. Their session/person pairing, alignment and headset cross-talk must be verified before any clean-source adaptation claim. Only source availability is recorded in paired-real-source-availability.json,0paired audio downloads/0additional training. Continue the original RM-OVERLAP with this prerequisite, preserving all old model failures and all product gates.\n'
readme.write_text(text,encoding='utf8')
print(json.dumps({'state':decision['state'],'actualResults':decision['actualResults'],'next':decision['next']},ensure_ascii=False),flush=True)
