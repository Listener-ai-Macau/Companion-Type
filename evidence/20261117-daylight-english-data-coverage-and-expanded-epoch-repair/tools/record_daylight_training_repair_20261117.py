"""Record actual no-GPU data/worker repair in the existing Companion task."""
from pathlib import Path
from datetime import datetime
import json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
data=J/'language-specific-adaptation-r1/expanded-data-r3'
prepared=J/'language-specific-adaptation-r1/prepared-r3'
plan=read(data/'english-data-plan.json');integrity=read(data/'integrity.json')
P=read(prepared/'protocol.json');intake=read(prepared/'intake.json')
new_score=read(prepared/'scoring-control.json')
old_score=read(J/'language-specific-adaptation-r1/prepared-r2/scoring-control.json')
assert new_score['admissionGate']==old_score['admissionGate']
assert new_score['references']==old_score['references']
assert (prepared/'validation-audio-only.json').read_bytes()==(J/'language-specific-adaptation-r1/prepared-r2/validation-audio-only.json').read_bytes()
assert plan['examples']==1828 and plan['independentIntegrityPassed'] and integrity['globalParticipantIntersection']==[]
assert intake['gpuExecutionEnabled'] is False and intake['trainingUpdates']==0
assert P['training']['optimizerUpdates']==457 and P['checkpointBudgetBytes']==32*1024**3
proof=read(E/'language-specific-adaptation-r1/expanded-epoch-contract-r3/result.json')
legacy=read(E/'language-specific-adaptation-r1/cpu-recovery-contract-expanded-legacy-r3/result.json')
coverage=read(J/'meeting-domain-data-r1/english-training-coverage-20261117.json')
at=datetime.now().astimezone().isoformat(timespec='seconds')
report={'at':at,'state':'DAYLIGHT_DATA_SELECTION_REPAIRED_EXPANDED1828_INPUT_AND457_UPDATE_RECIPE_FROZEN_NO_TRAINING',
    'ownerSteering':'GPU available at night; daytime data/error-analysis/code work withoutGPU. Do not repeatedly pollGPU availability or keep driver preparation as the daytime task.',
    'diagnosis':{'oldTrainingWords':12086,'availableAnnotatedNonoverlapWords':45465,
        'oldCoverage':12086/45465,'referenceSideTdtErrorsOnTrainingWordsSeenAtLeast5Times':74,
        'referenceSideTdtErrorsTotal':102,
        'conclusion':'Training data selection, rather than a missing-word glossary alone, deserves correction. No acoustic-causality or newWER claim from text-frequency association.'},
    'repair':{'implementation':'Original word overlap before turn grouping; preserve old475 clips as barriers and add only omitted natural nonoverlap windows. Existing2-30s/3s-gap/100ms-pad policy unchanged.',
        'old475RowsAndManifestBytePrefixPreserved':True,'supplementExamples':1353,'totalExamples':1828,
        'oldAudioSeconds':5093.779625,'newAudioSeconds':plan['audioSeconds'],
        'oldTrainingWords':12086,'newTrainingWords':41952,'newNonoverlapWordCoverage':41952/45465,
        'meetings':len(plan['meetings']),'globalTrainingParticipants':len(integrity['trainingGlobalParticipants']),
        'seenDevelopmentParticipants':len(integrity['seenDevelopmentGlobalParticipants']),
        'participantIntersection':[],'all1828PcmSlicesComparedByteForByte':True,
        'unlabelledWholeOrMultiSampleWordIntervals':0,'duplicateTrainingPcmFrames':0,
        'oneSampleOldAnnotationBoundaryContactsExplicitlyRetained':integrity['singleSourceSampleAnnotationBoundaryContacts']},
    'executor':{'trainableParameters':118886022,'fixedEpochs':1,'examples':1828,'optimizerUpdates':457,
        'learningRate':P['training']['learningRate'],'original32GiBCheckpointBudgetRetained':True,
        'checkpointStoragePlan':P['checkpointStoragePlan'],'old119AndNew457RecoveryContractsPassed':True,
        'original12Clip709WordAdmissionUnchanged':True,'originalValidationAudioBytesUnchanged':True,
        'gpuExecutionEnabled':False,'actualGpuLossGradientsLargestShapeCheckpointProof':False},
    'receipts':{'coverage':str(J/'meeting-domain-data-r1/english-training-coverage-20261117.json'),
        'dataPlan':str(data/'english-data-plan.json'),'integrity':str(data/'integrity.json'),
        'protocol':str(prepared/'protocol.json'),'scoringControl':str(prepared/'scoring-control.json'),
        'intake':str(prepared/'intake.json'),
        'expandedEpochProof':str(E/'language-specific-adaptation-r1/expanded-epoch-contract-r3/result.json'),
        'legacyRecoveryProof':str(E/'language-specific-adaptation-r1/cpu-recovery-contract-expanded-legacy-r3/result.json')},
    'retainedPreparationFailures':['DefaultPython lackedrapidfuzz; established scoring runtime reused without installing packages.',
        'The first independent completeness checker classified a one-source-sample oldclip boundary contact as an unlabelled whole word. Original failure/source retained; corrected diagnosis explicitly records that contact and still rejects any word with midpoint inside the clip or >1sample intersection. No audio/targets/reference/metric changed.'],
    'newNeuralCalls':0,'parameterUpdates':0,'cpuOrIntegratedGpuTraining':False,
    'originalAcceptanceMetricsChanged':False,'finalHoldoutOpened':False,
    'qualityQualified':False,'saleQualified':False}
target=J/'language-specific-adaptation-r1/daylight-training-data-repair-20261117.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
adapt=o['languageSpecificAdaptation20261116']
adapt['previous475ExamplePreparation']={k:adapt[k] for k in ['englishDataPlan','protocol','scoringControl','offlineIntake'] if k in adapt}
adapt.update(englishDataPlan=str(data/'english-data-plan.json'),protocol=str(prepared/'protocol.json'),
    scoringControl=str(prepared/'scoring-control.json'),offlineIntake=intake,
    state='EXPANDED1828_DATA_AND457_UPDATE_RECIPE_FROZEN_ACTUAL_GPU_EXECUTION_UNPROVEN',
    trainingStarted=False,trainingUpdates=0,gpuTrainingAdmissionReady=False,
    daylightTrainingDataRepair={'receipt':str(target),'state':report['state']},
    nextGpuConditions=['New actual GPU execution window and fresh original thermal/resource guards; no automatic driver action.',
        'Original same-profile12 English baseline, then actual selected/chunked/native GPU loss/gradient proof.',
        'New largest60588joint-cell and longest real training example with steadyAdam storage; exact tensor/integer/step/RNG checkpoint roundtrip.',
        'Fresh factory one fixed1828-example457-update epoch; checkpoint1/every32/final, original32GiB budget, no deletion/grid.',
        'Final457-update checkpoint paired independent original709-word admission, then original whole/person/facts/final gates.'])
o['daylightTrainingDataRepair20261117']={'receipt':str(target),'state':report['state']}
o['ownerDaylightPriority20261117']['currentAction']='Englishdata/worker repair completed and independently verified; continue no-GPU ASR/diarization work from this evidence. Driver comparison remains deferred.'
x['at']=at;x['state']=o['state']='DAYLIGHT_ENGLISH_DATA_AND_EXECUTOR_REPAIRED_NO_MODEL_TRAINING'
x['next']='白天继续无独显模型工作，勿反复查GPU/驱动。已修英文过早合并导致漏训练数据：保留旧475原件、补1353，共1828片/4.1814h/41952词，非重叠词覆盖26.6%→92.3%，逐字节PCM/完整词/目标token/无重复/40训练与13已见人员隔离均核；只单列旧片1采样点边界接触，原分数不改。执行器/独立评分/恢复已接1828/457固定一轮，原32GiB内检查点1/每32/末457，实际GPU梯度/最大形状/检查点仍未执行。接着推进无独显可做的说话人漏检验证/数据及本地推理代码；英文和中文95/98、逐人/事实/盲测保持开放，不CPU/核显训练。'
x['logResult']+='\n\n'+at+'｜Owner再次纠偏白天只做无显卡工作、不再围驱动等待。沿原训练数据/英文质量项实际修源头：旧export先合并整段同人发言后才判重叠/30s，已选10会议45465可标注非重叠词只收12086(26.6%)；新选择器先按原始词级判真重叠，旧475片及其manifest字节前缀原样保留，只在其余音频补出1353片，无新数据源/模型/参数网格。真实导出总1828片15053.027125s(4.1814h)、41952词(92.3%)、63453子词，目标最大161/最大joint60588cells；独立核全部PCM逐字节原件、原XML词序、token、无重复帧/无真重叠、40训练人对13已见人零交集。默认Python缺rapidfuzz换既有评分环境，完整性首断言把旧IS1000b片1采样点浮点边界接触误判整词漏标，原失败保留；按实际单采样分辨率显式单列该接触且不放过整词或>1采样交叠，原音/目标/验收均未改。适配执行器/评分/恢复从写死475/119改绑定冻结计划；新一轮1828/457、118886022参数/原lr1e-5不变，检查点1/每32/末457共16份满足原32GiB、不删不扩预算；旧119与新457元数据恢复/坏指针/末检查点身份约束通过。prepared-r3已冻结且GPU执行关、原时间窗未延长；本批0神经调用0权重更新/不CPU核显训练，没有新准确率成绩，不以数据量/测试量宣称95/98合格。结果'+str(target)+'。\n'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'receipt':str(target),'examples':1828,'words':41952,'hours':plan['audioSeconds']/3600,
    'checkpointBytesUpperBound':P['checkpointStoragePlan']['candidateCheckpointBytesUpperBound'],
    'newNeuralCalls':0,'trainingUpdates':0},ensure_ascii=False))
