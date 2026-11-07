"""Review one frozen audio-boundary comparison after its owned inference exits."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,wave
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import accepted

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
B=R/'docs/handoffs/20261107-model-generation-recovery'
C=B/'practical-qwen-author-boundaries-r6'; F=C/'full'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
run=read(F/'run.json')
assert run.get('finishedAt') and run['state'] in [
    'COMPLETE_TWO_BOUNDED_NATIVE_FULL_MEETINGS_REVIEW_REQUIRED',
    'AUTHOR_BOUNDARY_ORDINARY5_NOT_REACHED_COMPLEX_NOT_RUN',
    'FAILED_BOUNDED_NATIVE_RETAINED_NO_AUTOMATIC_RETRY',
    'BOUNDED_CONTROLLER_ERROR_RETAINED_NO_AUTOMATIC_RETRY']
for process in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(arg).name in ['practical_qwen_boundaries_worker_20261107.py',
            'run_practical_qwen_boundaries_20261107.py'] for arg in process.info['cmdline'] or []), 'Owned inference must exit first'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
P=read(C/'protocol.json'); N=read(C/'native-protocol.json')
parent=B/'practical-qwen-native17-r5'; baseline=read(parent/'review.json')
rule=read(C/'comparison-rule.json'); pilot=read(C/'pilot/state.json')
assert sha(C/'native-protocol.json')==sha(parent/'native-protocol.json')==P['baseProtocolSha256']
for name,key in [('practical_qwen_boundaries_worker_20261107.py','workerSourceSha256'),
                 ('practical_qwen_bounded_decode_20261107.py','recoverySourceSha256'),
                 ('practical_qwen_audio_boundaries_20261107.py','boundarySourceSha256')]:
    assert sha(Path(__file__).with_name(name))==P[key]
assert rule['baselineStrictCer']==0.05765765765765766 and rule['requiredCerExclusiveMax']==.05
assert not rule['referenceOrAsrTextUsedToSelectSpans']
assert pilot['ordinaryExactGeneratedIdsAndText'] and pilot['longestRealRootNoInputTruncation']
assert pilot['binding']['protocolSha256']==sha(C/'protocol.json')
assert read(C/'boundary-math-proof.json')['state'].startswith('PASS')
receipts=[read(p) for p in run['priorAttemptReceipts']]+[run]; rows=[]
for case in read(C/'audio-only.json'):
    name=case['meeting']; out=F/'transcripts'/name
    old=next(row for row in baseline['results'] if row['meeting']==name)
    assert case['audioSha256']==old['audioSha256'] and sha(case['audio'])==case['audioSha256']
    with wave.open(case['audio'],'rb') as source:
        total=source.getnframes()
        assert source.getframerate()==16000 and source.getnchannels()==1 and source.getsampwidth()==2
    spans=case['spans']
    assert spans[0]['startSample']==0 and spans[-1]['endSample']==total
    assert all(a['endSample']==b['startSample'] for a,b in zip(spans,spans[1:]))
    assert all(s['endSample']>s['startSample'] and s['index']==i for i,s in enumerate(spans))
    quality=out/'quality-review.json'
    if not quality.exists():
        state=read(out/'state.json') if (out/'state.json').exists() else None
        rows.append({'meeting':name,'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
            'state':state['state'] if state else 'NOT_RUN_AFTER_PREDECLARED_ORDINARY5_GATE',
            'rawChronologicalCerBaselineNative17':old['rawChronologicalCerNativeQwen'],
            'rawChronologicalCerNativeQwen':None,'qualityScoreAvailable':False,
            'completedWindows':state.get('completedWindows',0) if state else 0,
            'failure':state.get('error') if state else None,'qualityQualified':False})
        continue
    state=read(out/'completed-state.json'); q=read(quality)
    oldq=read(parent/'full/transcripts'/name/'quality-review.json')
    assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
    assert state['binding']['protocolSha256']==sha(C/'protocol.json')
    assert state['binding']['baseProtocolSha256']==sha(C/'native-protocol.json')
    for key in ['referenceSha256','referenceCharacters','referenceParser']:assert q[key]==oldq[key]
    assert sha(out/'model-output.json')==state['modelOutputSha256']
    assert sha(out/'attribution-review.json')==state['attributionReviewSha256']
    assert read(out/'product-contract.json')['exitCode']==0
    weights=read(out/'weight-roundtrip.json')
    expected=next(f['sha256'] for f in N['files'] if Path(f['file']).name=='model.safetensors')
    assert weights['state']=='PINNED_TENSOR_BYTES_STREAMED_AND_ROUNDTRIP_VERIFIED'
    assert weights['fileSha256']==weights['deviceRoundtripSha256']==expected
    assert weights['skippedTensorCount']==0 and weights['allExpectedParametersLoaded'] and not weights['wholeModelToEmptyUsed']
    packets={}
    for path in (out/'nodes').glob('*.json'):
        packet=read(path); raw=packet['raw']; assert packet['binding']==state['binding']
        assert hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==packet['rawSha256']
        if raw.get('neuralInferencePerformed'):
            assert raw['inputNotTruncated'] and raw['validMelFrames']>=raw['modelInputSamples']//160
            assert raw['modelInputSamples']==raw['endSample']-raw['startSample']+raw['inputPaddingSamples']
        packets[path.stem]=raw
    def leaves(index,key='root',depth=0):
        raw=packets['%06d-%s'%(index,key)]
        if accepted(raw):return [raw]
        assert depth<2
        left=leaves(index,key+'a',depth+1); right=leaves(index,key+'b',depth+1)
        assert left[0]['startSample']==raw['startSample'] and right[-1]['endSample']==raw['endSample']
        assert left[-1]['endSample']==right[0]['startSample']
        return left+right
    all_leaves=[]; recovered=[]
    assert state['totalWindows']==len(spans)==state['completedWindows']
    for index,span in enumerate(spans):
        root=packets['%06d-root'%index]
        assert root['startSample']==span['startSample'] and root['endSample']==span['endSample']
        if root.get('neuralInferencePerformed'):assert root['inputPaddingSamples']==span['paddingSamples']
        current=leaves(index); all_leaves.extend(current)
        if len(current)>1:recovered.append(index)
        assert read(out/'windows'/('%06d.raw.json'%index))['raw']['text']=='\n'.join(r['text'] for r in current)
    assert all_leaves[0]['startSample']==0 and all_leaves[-1]['endSample']==total==state['completedSample']
    assert all(a['endSample']==b['startSample'] for a,b in zip(all_leaves,all_leaves[1:]))
    doc=read(out/'model-output.json')
    assert doc['text']=='\n'.join(r['text'] for r in all_leaves) and recovered==state['recoveredRootIndices']
    metric=q['chronologicalTextDiagnostic']; edits=sum(metric['edits'].values())
    assert edits/q['referenceCharacters']==metric['cer']
    owned=sum(row['wholeProcessFamilySeconds'] for receipt in receipts for row in receipt['results'] if row['meeting']==name)
    history=[read(p) for p in out.glob('prior-state-*.json')]+[state]
    rows.append({'meeting':name,'state':state['state'],'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],
        'rawChronologicalCerBaselineNative17':old['rawChronologicalCerNativeQwen'],
        'rawChronologicalCerNativeQwen':metric['cer'],'editsBaselineNative17':old['editsNative17'],
        'editsAuthorBoundaries':edits,'editsByType':metric['edits'],'referenceCharacters':q['referenceCharacters'],
        'referenceAndStrictScorerIdentical':True,'ordinaryOrComplexChronologicalMetricOnly':True,
        'nonOverlapOnlyOrPerSpeakerCerMeasured':False,'allOriginalSamplesCoveredByAcceptedLeavesOnce':True,
        'sourcePaddingSamplesSeparatelyRecorded':sum(s['paddingSamples'] for s in spans),
        'allNeuralInputsNotTruncated':True,'allAcceptedLeafWordsPreserved':True,
        'rootCount':len(spans),'acceptedLeafCount':len(all_leaves),'recoveredRootIndices':recovered,
        'failedRawNodesRetained':sum(not accepted(r) for r in packets.values()),
        'committedInferenceSecondsIncludingFailedNodes':sum(r['inferenceSeconds'] for r in packets.values() if r.get('neuralInferencePerformed')),
        'acceptedLeafInferenceSeconds':sum(r['inferenceSeconds'] for r in all_leaves),
        'knownOwnedAsrProcessFamilySecondsIncludingInterruptions':owned,'knownOwnedAsrRtf':owned/case['audioSeconds'],
        'workerJobPrivateCommitPeakBytes':max(s.get('limits',{}).get('jobPeakPrivateCommitBytes',0) for s in history),
        'allFullWeightBytesGpuRoundtripVerified':True,'priorBoundaryNeuralOutputsReused':False,
        'actualSharedProductDocumentContractPassed':True,'allTextSpeakersUnknown':True,
        'wordAlignmentMeasured':False,'bothOverlappingVoicesRecovered':False,
        'modelOutputSha256':state['modelOutputSha256'],'qualityQualified':False})
ordinary=next(row for row in rows if row['meeting']=='S_R004S03C01')
cer=ordinary.get('rawChronologicalCerNativeQwen'); count=sum(row['rawChronologicalCerNativeQwen'] is not None for row in rows)
below=cer<.05 if cer is not None else None
if below is False:
    assert count==1 and run['state']=='AUTHOR_BOUNDARY_ORDINARY5_NOT_REACHED_COMPLEX_NOT_RUN'
    decision='Ordinary strict5% gate not reached. Stop complex inference as declared; retain any actual improvement or regression. No window/threshold sweep or per-meeting backend selection.'
    next_step='原QM04/QM05/RM-OVERLAP继续：低能量切分本轮未到严格5%，按预定规则停止额外复杂整会；保留同一1.7B固定30秒及作者边界实测，不扫窗口/阈值、不继续盲增模型。下一项对已有原字做独立词级时间对齐，再接已验证FP16分人，分别核验非重叠/短句/逐人/重叠内容，依据真实错误来源才选择降噪、目标人分离或领域适配。准确率5%/事实纪要/跨域独立集/双端实卡/售卖门继续OPEN。'
elif below and count==2:
    decision='Ordinary strict5% stage reached on one exposed full development meeting. Report complex diagnostic separately. No final qualification or installed/default promotion.'
    next_step='原QM04普通开发会本轮低于5%只记阶段结果，不代表产品合格；继续原QM05/RM-OVERLAP：已有原字的独立词级对齐、FP16说话人回填和非重叠/短句/重叠逐人错误测量，再验证真正目标人分离；纪要事实/跨域独立集/双端实卡/售卖门全保留，不按已见会议挑算法。'
else:
    decision='Execution incomplete or failed. Retain actual completed ordinary result and raw failure; unrun meetings have no quality score and no model-error retry.'
    next_step='保留本轮已完成整会分数与具体失败，未完成不评分；不原样重试神经错误，先查真实源头，同时推进已有识别原文的独立词级对齐与逐人/重叠测量。严格5%/事实纪要/跨域独立集/双端实卡/售卖门全保留。'
pilotrun=read(C/'pilot-run.json'); pilotreceipts=[read(p) for p in pilotrun['priorAttemptReceipts']]+[pilotrun]
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'AUTHOR_BOUNDARY_COMPARISON_TERMINAL_QUALITY_AND_SALE_OPEN',
    'executionState':run['state'],'modelId':N['modelId'],'revision':N['revision'],
    'protocolSha256':sha(C/'protocol.json'),'nativeProtocolSha256':sha(C/'native-protocol.json'),
    'priorNative17FullReview':str(parent/'review.json'),'priorNative17FullReviewSha256':sha(parent/'review.json'),
    'results':rows,'completeMeetingCount':count,'ordinaryFullChronologicalCerBelow5Percent':below,
    'decision':decision,'next':next_step,'predeclaredComparisonRule':rule,
    'authorRulePortNotAuthorDefaultChunkLength':True,'authorAsrDefaultTargetSeconds':1200,'localTargetSeconds':30,
    'sameWeightsAndGenerationSettings':True,'referenceUsedToSelectSpans':False,
    'sharedPilotOwnedProcessFamilySeconds':sum(r['wholeProcessFamilySeconds'] for receipt in pilotreceipts for r in receipt['results']),
    'timeScope':'This boundary candidate owned ASR attempts including load/interruption only. Prior native17 trials and shared pilot separate. Waits/manual work/scoring/transfer/alignment/minutes excluded; not final-summary latency.',
    'nativePilot':pilot,'independentCommandProofScope':'Prior fixed30s native17 independent command passed cancel/resume/cache/shared Document; current boundary profile not independently accepted in installed apps.',
    'priorIndependentCommandProof':str(parent/'independent-command-proof.json'),
    'qualityQualified':False,'defaultProductChanged':False,'finalHoldoutOpened':False,
    'realCustomerTrialPerformed':False,'installedWindowsAndroidOrCardAcceptance':False,'factualMinutesMeasured':False,
    'qualification':'NOT_QUALIFIED: exposed development chronological text only. Per-person aligned content, separated overlap, factual minutes, cross-domain final holdout and installed Windows/Android/card/sale gates open. Prior AMI diarization failure retained.',
    'noTrainingReferenceHotwordsOrFillerErDeletion':True}
assert not (C/'review.json').exists(); atomic_json(C/'review.json',review)
print(json.dumps({'state':review['state'],'results':[{k:r.get(k) for k in ['meeting','rawChronologicalCerBaselineNative17','rawChronologicalCerNativeQwen','editsAuthorBoundaries','knownOwnedAsrProcessFamilySecondsIncludingInterruptions']} for r in rows],'ordinaryBelow5':below,'qualified':False},ensure_ascii=False))
