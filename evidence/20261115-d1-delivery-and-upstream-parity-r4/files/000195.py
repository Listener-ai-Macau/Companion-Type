"""One exited native1.7B comparison. Full mixed text never earns identity credit."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import accepted
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'practical-qwen-native17-r5';F=C/'full'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=read(F/'run.json');assert run.get('finishedAt') and run['state'] in ['COMPLETE_TWO_BOUNDED_NATIVE_FULL_MEETINGS_REVIEW_REQUIRED','REJECTED_NATIVE17_NO_ORDINARY_ACCURACY_GAIN_COMPLEX_NOT_RUN','FAILED_BOUNDED_NATIVE_RETAINED_NO_AUTOMATIC_RETRY']
for process in psutil.process_iter(['cmdline']):
    try:assert not any(Path(arg).name in ['practical_qwen_checkpoint_worker_20261107.py','run_practical_qwen_checkpoint_20261107.py'] for arg in process.info['cmdline'] or []),'Wait for owned inference to exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
P=read(C/'protocol.json');N=read(C/'native-protocol.json');baseline=read(B/'practical-qwen-bounded-r4/review.json');rule=read(C/'comparison-rule.json')
assert sha(Path(__file__).with_name('practical_qwen_checkpoint_worker_20261107.py'))==P['workerSourceSha256']
assert sha(Path(__file__).with_name('practical_qwen_bounded_decode_20261107.py'))==P['recoverySourceSha256']
assert rule['baselineStrictCer']==0.06438438438438439
receipts=[read(p) for p in run['priorAttemptReceipts']]+[run];rows=[]
for case in read(C/'audio-only.json'):
    name=case['meeting'];out=F/'transcripts'/name;quality=out/'quality-review.json'
    old=next(r for r in baseline['results'] if r['meeting']==name)
    if not quality.exists():
        state=read(out/'state.json') if (out/'state.json').exists() else None
        rows.append({'meeting':name,'audioSeconds':case['audioSeconds'],'state':state['state'] if state else 'NOT_RUN_AFTER_PREDECLARED_ORDINARY_GATE',
          'rawChronologicalCerBaseline06':old['rawChronologicalCerNativeQwen'],'rawChronologicalCerNativeQwen':None,'qualityScoreAvailable':False,
          'completedWindows':state.get('completedWindows',0) if state else 0,'failure':state.get('error') if state else None,'qualityQualified':False});continue
    state=read(out/'completed-state.json');q=read(quality);old_q=read(B/'practical-qwen-bounded-r4/full/transcripts'/name/'quality-review.json')
    assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
    assert state['binding']['protocolSha256']==sha(C/'protocol.json') and state['binding']['baseProtocolSha256']==sha(C/'native-protocol.json')
    assert q['referenceSha256']==old_q['referenceSha256'] and q['referenceCharacters']==old_q['referenceCharacters'] and q['referenceParser']==old_q['referenceParser']
    assert sha(out/'model-output.json')==state['modelOutputSha256'] and sha(out/'attribution-review.json')==state['attributionReviewSha256']
    assert read(out/'product-contract.json')['exitCode']==0
    weights=read(out/'weight-roundtrip.json')
    assert weights['state']=='PINNED_TENSOR_BYTES_STREAMED_AND_ROUNDTRIP_VERIFIED' and weights['fileSha256']==weights['deviceRoundtripSha256']==next(f['sha256'] for f in N['files'] if Path(f['file']).name=='model.safetensors')
    assert weights['skippedTensorCount']==0 and weights['allExpectedParametersLoaded'] and not weights['wholeModelToEmptyUsed']
    packets={}
    for path in (out/'nodes').glob('*.json'):
        packet=read(path);raw=packet['raw'];assert packet['binding']==state['binding']
        assert hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==packet['rawSha256']
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
        current=leaves(index);all_leaves.extend(current)
        if len(current)>1:recovered.append(index)
        aggregate=read(out/'windows'/('%06d.raw.json'%index))['raw'];assert aggregate['text']=='\n'.join(r['text'] for r in current)
    assert all_leaves[0]['startSample']==0 and all_leaves[-1]['endSample']==state['completedSample'] and state['completedWindows']==state['totalWindows']
    assert all(a['endSample']==b['startSample'] for a,b in zip(all_leaves,all_leaves[1:]))
    assert read(out/'model-output.json')['text']=='\n'.join(r['text'] for r in all_leaves) and recovered==state['recoveredRootIndices']
    metric=q['chronologicalTextDiagnostic'];edits=sum(metric['edits'].values());assert edits/q['referenceCharacters']==metric['cer']
    owned=sum(row['wholeProcessFamilySeconds'] for receipt in receipts for row in receipt['results'] if row['meeting']==name)
    history=[read(p) for p in out.glob('prior-state-*.json')]+[state]
    rows.append({'meeting':name,'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
      'rawChronologicalCerBaseline06':old['rawChronologicalCerNativeQwen'],'rawChronologicalCerNativeQwen':metric['cer'],
      'editsBaseline06':old['editsNativeQwen'],'editsNative17':edits,'editsByType':metric['edits'],'referenceCharacters':q['referenceCharacters'],
      'referenceAndStrictScorerIdentical':True,'ordinaryOrComplexChronologicalMetricOnly':True,'nonOverlapOnlyOrPerSpeakerCerMeasured':False,
      'allAudioCoveredByAcceptedLeavesOnce':True,'allAcceptedLeafWordsPreserved':True,'recoveredRootIndices':recovered,
      'acceptedLeafCount':len(all_leaves),'failedRawNodesRetained':sum(not accepted(r) for r in packets.values()),
      'committedInferenceSecondsIncludingFailedNodes':sum(r['inferenceSeconds'] for r in packets.values() if r.get('neuralInferencePerformed') is True),
      'acceptedLeafInferenceSeconds':sum(r['inferenceSeconds'] for r in all_leaves),
      'knownOwnedAsrProcessFamilySecondsIncludingInterruptions':owned,'knownOwnedAsrRtf':owned/case['audioSeconds'],
      'workerJobPrivateCommitPeakBytes':max(s.get('limits',{}).get('jobPeakPrivateCommitBytes',0) for s in history),
      'fullWeightTensorCount':weights['tensorCount'],'allFullWeightBytesGpuRoundtripVerified':True,
      'otherCheckpointNeuralOutputsReused':False,'actualSharedProductDocumentContractPassed':True,
      'allTextSpeakersUnknown':True,'wordAlignmentMeasured':False,'bothOverlappingVoicesRecovered':False,
      'modelOutputSha256':state['modelOutputSha256'],'qualityQualified':False})
ordinary=next(r for r in rows if r['meeting']=='S_R004S03C01');cer=ordinary.get('rawChronologicalCerNativeQwen')
complete_count=sum(r['rawChronologicalCerNativeQwen'] is not None for r in rows)
if cer is None:
    decision='Native1.7B full execution failed; keep raw failure, no full ordinary quality score and no automatic model-error retry.'
    next_step='原QM04保留1.7B实际执行失败，不原样重跑。依据真实错误与0.6B完整研究基线排查具体源头或推进独立词级对齐/逐人内容的可执行缺口；不降低文字5%或其它质量门。'
elif cer>=rule['baselineStrictCer']:
    decision='Reject1.7B default adoption: complete ordinary strict CER does not beat the predeclared6.43844% baseline. Stop additional complex inference; do not hide failure or pick a different backend per exposed meeting.'
    next_step='原QM04/人物内容继续：更大原生权重没有改善完整普通会，停止继续堆同类模型/调惩罚/提示词。保留0.6B研究基线及这轮失败，先补可验证的词级时间对齐与逐人/非重叠/重叠内容测量，定位实际错误来源后才选择降噪、分离或领域适配。普通5%/纪要事实/独立集/手机实卡/售卖门继续OPEN。'
elif complete_count==2:
    decision='Retain native1.7B as an opt-in research candidate: ordinary strict full text beats the predeclared0.6B baseline. Report each complex diagnostic separately; no installed default, aligned-identity, overlap-content or sale promotion.'
    next_step='沿原QM04/QM05/RM-OVERLAP继续：保留1.7B真实整会结果，普通严格5%只按本场实际成绩记录。下一项用独立官方词级对齐模型处理已有识别原文，保留每个原字并核验真实时间，再接FP16分人，分别测全会逐人/非重叠/重叠错误，不能把30秒块贴成一个人或拿混音分数当重叠通过。普通不足5%继续原准确率项；复杂分离逐路/事实纪要/跨域独立集/双端实卡/售卖门全保留。'
else:
    decision='Ordinary improves but complex full execution failed or remains unmeasured; no two-meeting or product qualification.'
    next_step='保留普通整会改善及复杂实际失败，先处理这条具体失败源头，不原样重跑。独立对齐/分人/逐路重叠与严格5%、纪要事实、跨域独立集、手机实卡及售卖门继续OPEN。'
pilot_run=read(C/'pilot-run.json');pilot_receipts=[read(p) for p in pilot_run['priorAttemptReceipts']]+[pilot_run]
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'NATIVE17_FULL_COMPARISON_COMPLETE_QUALITY_AND_SALE_OPEN' if complete_count==2 else 'NATIVE17_COMPARISON_TERMINAL_NOT_QUALIFIED',
  'modelId':N['modelId'],'revision':N['revision'],'protocolSha256':sha(C/'protocol.json'),'nativeProtocolSha256':sha(C/'native-protocol.json'),
  'results':rows,'completeMeetingCount':complete_count,'ordinaryFullChronologicalCerBelow5Percent':cer<.05 if cer is not None else None,
  'decision':decision,'next':next_step,'predeclaredComparisonRule':rule,
  'sharedPilotOwnedProcessFamilySeconds':sum(r['wholeProcessFamilySeconds'] for receipt in pilot_receipts for r in receipt['results']),
  'timeScope':'Known owned full-ASR attempts include load/interrupted work. Shared short pilot separate. Resource waits/manual engineering/scoring/transfer/word-alignment/minutes are excluded; not stop-recording-to-final-summary latency.',
  'nativePilot':read(C/'pilot/state.json'),'independentCommandProof':read(C/'independent-command-proof.json') if (C/'independent-command-proof.json').exists() else None,
  'qualityQualified':False,'defaultProductChanged':False,'finalHoldoutOpened':False,'realCustomerTrialPerformed':False,
  'installedWindowsAndroidOrCardAcceptance':False,'factualMinutesMeasured':False,
  'qualification':'NOT_QUALIFIED: exposed development chronological text only. Non-overlap-only/time-constrained per-person, separated overlap, factual minutes, final cross-domain holdout and actual installed phone/card/sale gates remain open. Prior AMI speaker failure retained.',
  'noTrainingReferenceHotwordsOrFillerErDeletion':True}
assert not (C/'review.json').exists();atomic_json(C/'review.json',review)
print(json.dumps({'state':review['state'],'results':[{k:r.get(k) for k in ['meeting','rawChronologicalCerBaseline06','rawChronologicalCerNativeQwen','editsNative17','knownOwnedAsrProcessFamilySecondsIncludingInterruptions']} for r in rows],'ordinaryBelow5':review['ordinaryFullChronologicalCerBelow5Percent'],'qualified':False},ensure_ascii=False))
