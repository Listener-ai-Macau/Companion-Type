"""Review exited, complete native ASR outputs without inference or text changes.

The chronological overlap diagnostic is never relabelled per-speaker CER.
Only known owned-process durations are summed; an externally interrupted
execution with censored duration remains explicitly unknown.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil
from practical_io_20261107 import atomic_json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
B=R/'docs/handoffs/20261107-model-generation-recovery'
C=B/'practical-qwen-signal-r3';F=C/'full'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=read(F/'run.json')
assert run['state']=='COMPLETE_TWO_OFFICIAL_NATIVE_FULL_MEETINGS_REVIEW_REQUIRED' and run.get('finishedAt')
for process in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(arg).name in ['run_practical_qwen_full_20261107.py','practical_qwen_full_worker_20261107.py'] for arg in process.info['cmdline'] or []),'Review only after the model family exits'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass

protocol=read(C/'protocol.json');baseline=read(B/'practical-verbatim-r1/review.json')
receipts=[read(p) for p in run['priorAttemptReceipts']]+[run]
worker=Path(__file__).with_name('practical_qwen_full_worker_20261107.py')
short_worker=Path(__file__).with_name('practical_qwen_native_worker_20261107.py')
rows=[]
for case in read(F/'audio-only.json'):
    name=case['meeting'];out=F/'transcripts'/name
    state=read(out/'completed-state.json');quality=read(out/'quality-review.json')
    contract=read(out/'product-contract.json');binding=state['binding']
    weights=read(out/'weight-roundtrip.json')
    assert weights['state']=='PINNED_TENSOR_BYTES_STREAMED_AND_ROUNDTRIP_VERIFIED'
    assert weights['tensorCount']==611 and weights['skippedTensorCount']==0
    assert weights['fileSha256']==weights['deviceRoundtripSha256']==next(f['sha256'] for f in protocol['files'] if Path(f['file']).name=='model.safetensors')
    assert weights['allExpectedParametersLoaded'] and weights['tiedOutputEmbeddingPreserved'] and not weights['wholeModelToEmptyUsed']
    assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
    assert binding['protocolSha256']==sha(C/'protocol.json') and binding['audioSha256']==case['audioSha256']
    assert binding['workerSourceSha256']==sha(worker) and binding['officialShortWorkerSourceSha256']==sha(short_worker)
    assert sha(out/'model-output.json')==state['modelOutputSha256'] and sha(out/'attribution-review.json')==state['attributionReviewSha256']
    assert contract['exitCode']==0 and quality['allRawAsrTextPreserved'] and quality['allAudioSamplesCoveredOnce']
    cursor=0;inference=0.;zero=0;raw_hashes={}
    for index in range(state['totalWindows']):
        path=out/'windows'/('%06d.raw.json'%index);packet=read(path);raw=packet['raw']
        canonical=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        assert packet['binding']==binding and hashlib.sha256(canonical).hexdigest()==packet['rawSha256']
        assert raw['index']==index and raw['startSample']==cursor and raw['endSample']>cursor
        cursor=raw['endSample'];inference+=raw['inferenceSeconds'];raw_hashes[path.name]=sha(path)
        if raw.get('exactDigitalSilence'):
            assert raw['naturalEos'] is None and not raw['generatedIds'] and raw['text']=='' and not raw['neuralInferencePerformed'];zero+=1
        else:assert raw['naturalEos']
    assert state['completedWindows']==state['totalWindows'] and cursor==state['completedSample']
    old=next(r for r in baseline['results'] if r['meeting']==name)
    metric=quality['chronologicalTextDiagnostic'];edits=sum(metric['edits'].values())
    assert edits/quality['referenceCharacters']==metric['cer']
    owned=sum(row['wholeProcessFamilySeconds'] for receipt in receipts for row in receipt['results'] if row['meeting']==name)
    history=[read(p) for p in out.glob('prior-state-*.json')]+[state]
    peaks=[s.get('limits',{}).get('jobPeakPrivateCommitBytes',0) for s in history]
    rows.append({'meeting':name,'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
      'rawChronologicalCerBeforeNativeVerbatim':old['rawCerBefore'],'rawChronologicalCerVerbatim':old['rawCerAfter'],
      'rawChronologicalCerNativeQwen':metric['cer'],'referenceCharacters':quality['referenceCharacters'],
      'editsBeforeNativeVerbatim':old['strictEditsBefore'],'editsVerbatim':old['strictEditsAfter'],'editsNativeQwen':edits,
      'editsByType':metric['edits'],'metricScope':'Full chronological text CER; overlapping reference order is not unique, complex meeting result is only a mixed-text diagnostic. Not the non-overlap-only gate or per-speaker/time-constrained CER.',
      'strictScorerAndAllFillersUnchanged':True,'rawTextPreserved':True,'allAudioSamplesCoveredOnce':True,
      'totalWindows':state['totalWindows'],'nonzeroNeuralWindows':state['totalWindows']-zero,'exactDigitalZeroWindows':zero,
      'successfulCommittedInferenceSeconds':inference,'knownOwnedAsrProcessFamilySecondsIncludingInterruptions':owned,
      'committedInferenceRtf':inference/case['audioSeconds'],'knownOwnedAsrRtf':owned/case['audioSeconds'],
      'ownedAsrTimeIncludesLoadsAndLostPartialAttempts':True,'externalMemoryWaitEngineeringScoringTransferMinutesExcluded':True,
      'sampledWorkerJobPrivateCommitPeakBytes':max(peaks),'privateCommitLimitBytes':protocol['privateCommitLimitBytes'],
      'cpuPercentMaximum':protocol['cpuPercent'],'gpuUtilizationHardCapped':False,
      'actualProductDocumentContractPassed':True,'modelOutputSha256':state['modelOutputSha256'],
      'rawFileManifestSha256':hashlib.sha256(json.dumps(raw_hashes,sort_keys=True).encode()).hexdigest(),
      'wordAlignmentMeasured':False,'speakerIdentityMeasured':False,'allTextSpeakersUnconfirmed':True,
      'overlapBothVoicesRecovered':False,'factualMinutesMeasured':False,'qualityQualified':False})

cache=read(C/'cache-recovery-proof.json')
assert cache['state']=='PASS_FULL_CACHE_IDENTICAL_ZERO_MODEL_AND_STICKY_MISSING_RAW_REFUSAL'
assert cache['originalExperimentRawAndOutputUnchanged'] and cache['neuralInferenceAdded']==0
concurrency=read(C/'concurrency-proof.json')
assert concurrency['state']=='PASS_REAL_COMMAND_REFUSES_CONCURRENT_NATIVE_ASR_BEFORE_NEURAL_LAUNCH' and concurrency['newNeuralStages']==0
ordinary=next(r for r in rows if r['meeting']=='S_R004S03C01')
complex_case=next(r for r in rows if r['meeting']=='L_R003S01C02')
futility=read(C/'execution-stop-rule.json')
assert ordinary['rawChronologicalCerNativeQwen']<futility['baselineStrictCer']
both_improved=all(r['rawChronologicalCerNativeQwen']<r['rawChronologicalCerVerbatim'] for r in rows)
if both_improved:
    decision='Retain the frozen native Qwen0.6B pipeline as a research candidate only. Both complete exposed chronological text comparisons improve. No per-meeting backend choosing or installed default promotion; text5%, verified word alignment, person attribution, overlap recovery and factual minutes remain open.'
    next_step='原QM04/RM-OVERLAP继续：保留这轮固定原生Qwen候选及FP16分人基线，先用不改原字的真实词级时间对齐接回“谁说了什么”，零ASR重跑核对全会逐人/时间约束指标；重叠区必须逐路恢复内容，不能给整个30秒块强贴人物。对齐/分离候选先按既有失败证据核验原生和部署一致性，冻结开发区间及资源预算，必须同时检查非重叠/短句回退；不扫阈值、热词或清理语气词凑5%。普通全会文字仍需<5%，复杂逐人和最终未见集/跨域/纪要事实/手机实卡/售卖门全保留。'
else:
    decision='Reject automatic default adoption. At least one frozen full meeting regresses against native-verbatim baseline; keep every failed result and do not select different backends per exposed meeting.'
    next_step='原QM04继续：按已保存整会错误清单区分原生文字错误、跨界和重叠丢字，不按已见会议挑后端。优先修可验证的源头，保留当前候选回退和同一两整会对照；原人物/逐路重叠/纪要事实/跨域/最终未见集/手机实卡/售卖门继续OPEN，禁止原样重跑失败模型。'
interruptions=[str(p) for p in F.glob('external-session-interruption-*.json')]
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
  'state':'NATIVE_QWEN_TWO_FULL_DEVELOPMENT_MEETINGS_COMPLETE_QUALITY_AND_SALE_OPEN',
  'modelId':protocol['modelId'],'revision':protocol['revision'],'dtype':protocol['dtype'],
  'protocolSha256':sha(C/'protocol.json'),'workerSourceSha256':sha(worker),'results':rows,
  'decision':decision,'next':next_step,'bothChronologicalTextComparisonsImproved':both_improved,
  'ordinaryFullChronologicalTextBelow5Percent':ordinary['rawChronologicalCerNativeQwen']<.05,
  'complexMixedTextDiagnosticBelow5Percent':complex_case['rawChronologicalCerNativeQwen']<.05,
  'timeAccounting':{'initialFullControllerStartedAt':receipts[0]['startedAt'],'finalFullControllerFinishedAt':run['finishedAt'],
    'elapsedFullExperimentSeconds':(datetime.fromisoformat(run['finishedAt'])-datetime.fromisoformat(receipts[0]['startedAt'])).total_seconds(),
    'elapsedIsProductLatency':False,'elapsedIncludesManualEngineeringAndRamRecoveryGaps':True,
    'externalExecutionSessionInterruptions':interruptions,'exactOwnedTimeForInterruptedExternalSessionKnown':not bool(interruptions),
    'knownOwnedDurationsExcludeThatCensoredAttempt':bool(interruptions),'meetingToFinalSummaryLatencyMeasured':False},
  'executionControls':{'gpuFeatureNumericProof':str(B/'practical-qwen-native-r1/processor-numeric-proof.json'),
    'streamedLoaderTinyExactProof':str(B/'practical-qwen-native-r1/streamed-loader-proof-r2.json'),
    'all611FullWeightTensorBytesRoundtripVerified':True,'wholeModelCpuAllocationAvoided':True,
    'exactDigitalZeroOnlyNoThreshold':True,'onePcm16LsbPreserved':True,
    'bareNativeModelSilenceHallucinationRetained':str(B/'practical-qwen-streamed-r2/short-native-state.json'),
    'completedCacheRecoveryProof':cache,'realCommandConcurrencyProof':concurrency},
  'qualityQualified':False,'defaultProductChanged':False,'installedWindowsOrAndroidBackendChanged':False,
  'cardAcousticOrPhoneAcceptance':False,'realCustomerTrialPerformed':False,'finalHoldoutOpened':False,
  'qualification':'NOT_QUALIFIED: two exposed Chinese full text comparisons only. No strict non-overlap-only/time-constrained per-person, overlap-separated words, factual minutes, multilingual/cross-room holdout or actual phone/card acceptance. Existing thresholds unchanged.',
  'referenceNeverPassedToInference':True,'noTrainingOrReferenceTextPostprocessing':True,
  'priorFailuresRetained':'CPU feature allocation failure; supported GPU feature numeric control; whole-file native loading1455; first tiny-loader config control; bare-model exact-zero hallucination; actual Windows low-RAM attempts; external-session interruption. None is relabelled a full quality pass.'}
assert not (C/'review.json').exists(),'Do not overwrite an assessed version'
atomic_json(C/'review.json',review)
print(json.dumps({'state':review['state'],'results':[{k:r[k] for k in ['meeting','rawChronologicalCerVerbatim','rawChronologicalCerNativeQwen','editsNativeQwen','knownOwnedAsrProcessFamilySecondsIncludingInterruptions']} for r in rows],'qualified':False},ensure_ascii=False))
