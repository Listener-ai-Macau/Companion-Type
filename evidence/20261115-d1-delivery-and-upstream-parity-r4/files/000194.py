"""Exited full-meeting decision for the frozen bounded recovery, no inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import accepted
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'practical-qwen-bounded-r4';F=C/'full';base=B/'practical-qwen-signal-r3'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=read(F/'run.json');assert run['state']=='COMPLETE_TWO_BOUNDED_NATIVE_FULL_MEETINGS_REVIEW_REQUIRED' and run.get('finishedAt')
for process in psutil.process_iter(['cmdline']):
    try:assert not any(Path(arg).name in ['practical_qwen_bounded_worker_20261107.py','run_practical_qwen_bounded_20261107.py'] for arg in process.info['cmdline'] or []),'Wait for the owned model family to exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
P=read(C/'protocol.json');assert sha(Path(__file__).with_name('practical_qwen_bounded_worker_20261107.py'))==P['workerSourceSha256']
assert sha(Path(__file__).with_name('practical_qwen_bounded_decode_20261107.py'))==P['recoverySourceSha256']
pilot=read(C/'pilot/state.json');assert pilot['state']=='PASS_BOUNDED_NATIVE_PILOT_FULL_QUALITY_UNMEASURED' and pilot['ordinaryExactGeneratedIdsAndText']
cache=read(C/'cache-recovery-proof.json');assert cache['state']=='PASS_BOUNDED_COMPLETE_CACHE_IDENTICAL_ZERO_MODEL_STICKY_NODE_REFUSAL'
concurrency=read(C/'concurrency-proof.json');assert concurrency['newNeuralStages']==0 and concurrency['originalFullRunNotStopped']
previous=read(base/'full/run.json');original_receipts=[read(p) for p in previous['priorAttemptReceipts']]+[previous]
receipts=[read(p) for p in run['priorAttemptReceipts']]+[run]
baseline=read(B/'practical-verbatim-r1/review.json');rows=[]
for case in read(C/'audio-only.json'):
    name=case['meeting'];out=F/'transcripts'/name;state=read(out/'completed-state.json');quality=read(out/'quality-review.json')
    assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' and state['binding']['protocolSha256']==sha(C/'protocol.json')
    assert sha(out/'model-output.json')==state['modelOutputSha256'] and sha(out/'attribution-review.json')==state['attributionReviewSha256']
    assert state['completedWindows']==state['totalWindows'] and read(out/'product-contract.json')['exitCode']==0
    packets={}
    for path in (out/'nodes').glob('*.json'):
        packet=read(path);assert packet['binding']==state['binding']
        raw=packet['raw'];assert hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==packet['rawSha256']
        packets[path.stem]=raw
    def leaves(index,key='root',depth=0):
        raw=packets['%06d-%s'%(index,key)]
        if accepted(raw):return [raw]
        assert depth<2
        left=leaves(index,key+'a',depth+1);right=leaves(index,key+'b',depth+1)
        assert left[0]['startSample']==raw['startSample'] and right[-1]['endSample']==raw['endSample'] and left[-1]['endSample']==right[0]['startSample']
        return left+right
    all_leaves=[];recovered=[]
    for index in range(state['totalWindows']):
        ls=leaves(index);all_leaves.extend(ls)
        if len(ls)>1:recovered.append(index)
        aggregate=read(out/'windows'/('%06d.raw.json'%index))['raw']
        assert aggregate['text']=='\n'.join(r['text'] for r in ls)
    assert all_leaves[0]['startSample']==0 and all_leaves[-1]['endSample']==state['completedSample']
    assert all(a['endSample']==b['startSample'] for a,b in zip(all_leaves,all_leaves[1:]))
    document=read(out/'model-output.json');assert document['text']=='\n'.join(r['text'] for r in all_leaves)
    assert recovered==state['recoveredRootIndices']
    if name=='S_R004S03C01':assert state['originalOrdinaryWholeDocumentIdentical'] and sha(out/'model-output.json')==sha(base/'full/transcripts'/name/'model-output.json') and not recovered
    old=next(r for r in baseline['results'] if r['meeting']==name);metric=quality['chronologicalTextDiagnostic'];edits=sum(metric['edits'].values());assert edits/quality['referenceCharacters']==metric['cer']
    prior_seconds=sum(row['wholeProcessFamilySeconds'] for receipt in original_receipts for row in receipt['results'] if row['meeting']==name)
    added_seconds=sum(row['wholeProcessFamilySeconds'] for receipt in receipts for row in receipt['results'] if row['meeting']==name)
    history=[read(p) for p in out.glob('prior-state-*.json')]+[state]
    rows.append({'meeting':name,'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
      'rawChronologicalCerBeforeNativeVerbatim':old['rawCerBefore'],'rawChronologicalCerVerbatim':old['rawCerAfter'],
      'rawChronologicalCerNativeQwen':metric['cer'],'strictEditsBefore':old['strictEditsBefore'],'strictEditsVerbatim':old['strictEditsAfter'],
      'editsNativeQwen':edits,'editsByType':metric['edits'],'referenceCharacters':quality['referenceCharacters'],
      'metricScope':'Full chronological strict text CER. Complex meeting value is only mixed-text diagnostic because overlapping reference order is not unique. No per-speaker/time-constrained or non-overlap-only qualification.',
      'rootWindows':state['totalWindows'],'acceptedLeafCount':len(all_leaves),'recoveredRootIndices':recovered,'failedRawNodeCount':sum(not accepted(raw) for raw in packets.values()),
      'allSamplesCoveredByAcceptedLeavesOnce':True,'everyAcceptedLeafRawWordPreserved':True,'failedParentRawRetainedSeparately':True,
      'originalOrdinaryWholeDocumentIdentical':state.get('originalOrdinaryWholeDocumentIdentical'),
      'acceptedLeafInferenceSecondsIncludingInheritedRoots':sum(r['inferenceSeconds'] for r in all_leaves),
      'newCommittedInferenceSecondsIncludingFailedNodes':sum(r['inferenceSeconds'] for r in packets.values() if r.get('neuralInferencePerformed') is True),
      'originalR3KnownOwnedAsrProcessFamilySeconds':prior_seconds,'boundedFullKnownOwnedProcessFamilySeconds':added_seconds,
      'knownCombinedAsrProcessFamilySecondsIncludingInterruptedAttempts':prior_seconds+added_seconds,
      'resourceWaitManualEngineeringScoringTransferMinutesExcluded':True,
      'workerJobPrivateCommitPeakBytes':max(s.get('limits',{}).get('jobPeakPrivateCommitBytes',0) for s in history),
      'actualProductDocumentContractPassed':True,'modelOutputSha256':state['modelOutputSha256'],
      'allSpeakersUnconfirmed':True,'wordAlignmentMeasured':False,'overlapBothVoicesRecovered':False,'qualityQualified':False})
ordinary=next(r for r in rows if r['meeting']=='S_R004S03C01')
both_improve=all(r['rawChronologicalCerNativeQwen']<r['rawChronologicalCerVerbatim'] for r in rows)
pilot_run=read(C/'pilot-run.json');pilot_receipts=[read(p) for p in pilot_run['priorAttemptReceipts']]+[pilot_run]
next_step='原QM04准确率优先继续：本轮解决固定30秒复读造成的未完成，普通完整S仍6.43844%>5%。保留独立原生候选及全部失败、固定两整会/严格评分和现有CPU5%/private2GiB预算；下一项验证有公开会议依据的更强原生ASR能力，不靠删语气词、数字改写、参考热词或按已见会议挑后端达标。实际词级对齐后才回填FP16分人，重叠必须分别恢复每人内容，不能给30秒块整段贴人物。复杂逐人/跨域/纪要事实/手机实卡/最终未见集/售卖门保持OPEN。'
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'BOUNDED_NATIVE_TWO_FULL_MEETINGS_COMPLETE_ACCURACY_AND_SALE_OPEN',
  'modelId':'Qwen/Qwen3-ASR-0.6B-hf','revision':read(base/'protocol.json')['revision'],'protocolSha256':sha(C/'protocol.json'),
  'results':rows,'bothChronologicalTextComparisonsImprovedVersusVerbatim':both_improve,'ordinaryFullChronologicalTextBelow5Percent':ordinary['rawChronologicalCerNativeQwen']<.05,
  'decision':'Bounded failure recovery completes the entire complex meeting, retaining original failed30s raw nodes and exact ordinary full Document. Keep as an opt-in research candidate only. Accuracy5%, aligned people/overlap words and sale acceptance remain open; no default promotion.',
  'next':next_step,'sourceOfPriorFailure':str(base/'review.json'),'pilot':pilot,'completedCacheProof':cache,'realConcurrencyProof':concurrency,
  'sharedPilotOwnedProcessFamilySeconds':sum(r['wholeProcessFamilySeconds'] for receipt in pilot_receipts for r in receipt['results']),
  'timeScope':'Per-meeting sums include known interrupted owned ASR attempts; shared pilot shown separately. The one externally aborted R3 controller has censored duration, excluded from known sums. Wall gaps include manual engineering and actual memory recovery; neither is product summary latency.',
  'qualityQualified':False,'defaultProductChanged':False,'installedWindowsOrAndroidBackendChanged':False,'cardAcousticOrPhoneAcceptance':False,'realCustomerTrialPerformed':False,'finalHoldoutOpened':False,
  'referenceNeverPassedToInference':True,'modelWeightsOrPromptsChanged':False,'decodeRecoveryAndConditionalInputCutsChanged':True,
  'posthocRepeatedWordRemoval':False,'fillerOrErRemovedToScore':False,
  'qualification':'NOT_QUALIFIED: exposed development full text only. Strict5%/person-aligned text/separated overlap/factual minutes/cross-corpus final holdout/installed phone-card and sale remain unqualified. Prior AMI31.0766% speaker failure is retained.'}
assert not (C/'review.json').exists();atomic_json(C/'review.json',review)
print(json.dumps({'state':review['state'],'results':[{k:r[k] for k in ['meeting','rawChronologicalCerVerbatim','rawChronologicalCerNativeQwen','editsNativeQwen','recoveredRootIndices','knownCombinedAsrProcessFamilySecondsIncludingInterruptedAttempts']} for r in rows],'qualified':False},ensure_ascii=False))
