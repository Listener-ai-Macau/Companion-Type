"""Zero-neural regression control: reuse the historical estimated-onset policy."""
from pathlib import Path
from datetime import datetime
import hashlib,json,math,psutil,shutil,subprocess
from practical_io_20261107 import atomic_json
from practical_transcript_20261107 import normalized_journal,onset_attribution
from moss_windows_resource_limits_20261104 import WorkerLimits
B=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery');C=B/'practical-alignment-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert read(C/'run.json')['state']=='COMPLETE_SEQUENTIAL_NATIVE_ALIGNMENT_REVIEW_REQUIRED'
for process in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(arg).name in ['practical_alignment_worker_20261107.py','run_practical_alignment_20261107.py'] for arg in process.info['cmdline'] or []),'Wait for the owned alignment family to exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
P=read(C/'protocol.json');policy=read(C/'onset-attribution-policy.json');state=read(C/'full-state.json')
assert policy['uncertaintyMarginSeconds']==.06 and state['state']=='COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED'
assert sha(Path(__file__).with_name('practical_transcript_20261107.py'))==policy['helperSourceSha256']
assert state['binding']['protocolSha256']==sha(C/'protocol.json') and state['binding']['planSha256']==sha(C/'audio-text-only.json')
assert sha(Path(__file__))==policy['postprocessorSourceSha256']
derived=C/'derived-onset';derived.mkdir(exist_ok=True)
shutil.copyfile(B/'practical-qwen-native17-r5/full/scoring-only.json',derived/'scoring-only.json')
SC='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
checker='E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe'
rows=[]
for case in read(C/'audio-text-only.json'):
    name=case['meeting'];original=read(case['sourceDocument']);assert sha(case['sourceDocument'])==case['sourceDocumentSha256']
    record=policy['speakerJournals'][name]
    assert sha(record['file'])==record['sha256'] and sha(record['producerFile'])==record['producerSha256']
    journal,mapping=normalized_journal(read(record['file']));utterances=[];tokens=[];payloads=[];offset=0
    for leaf in case['leaves']:
        packet=read(C/'aligned'/name/(leaf['id']+'.json'));payload=packet['payload']
        assert packet['binding']=={**state['binding'],'sourceNodeSha256':leaf['nodeSha256'],'meeting':name}
        assert sha(leaf['nodeFile'])==leaf['nodeSha256']
        assert packet['payloadSha256']==hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert payload['originalText']==leaf['text']==''.join(u['text'] for u in payload['units'])
        payloads.append(payload);duration=case['audioSeconds']
        low_ms=round(leaf['startSample']/16);high_ms=round(leaf['endSample']/16)
        assert low_ms<high_ms
        for unit in payload['units']:
            local_onset=unit['predictedStartSeconds']
            valid=math.isfinite(local_onset) and 0<=local_onset<(leaf['endSample']-leaf['startSample'])/16000
            start=leaf['startSample']/16000+local_onset if valid else None
            if valid:
                assert 0<=start<duration
                identity=onset_attribution(start,journal['segments'],duration=duration,margin=.06)
                onset=start;finish=None;reason=identity['attribution'];speaker=identity['speaker']
                start_ms=max(low_ms,min(high_ms-1,round(start*1000)))
                end_ms=max(start_ms+1,min(high_ms,round((start+.06)*1000)))
            else:
                assert start is None
                identity={'speaker':None,'candidateSpeakers':[],'overlapDetectedNearOnset':False}
                speaker=None;reason='invalid_predicted_onset_original_word_preserved_unknown';onset=None;finish=None
                local_start=unit['predictedStartSeconds'];local_end=unit['predictedEndSeconds']
                assert math.isfinite(local_start) and math.isfinite(local_end)
                start_ms=max(low_ms,min(high_ms-1,round(leaf['startSample']/16+local_start*1000)))
                end_ms=max(start_ms+1,min(high_ms,round(leaf['startSample']/16+local_end*1000)))
            utterances.append({'text':unit['text'],'startMs':start_ms,'endMs':end_ms,'speaker':speaker,'approximateTiming':True})
            tokens.append({**unit,**identity,'token':unit['alignmentUnit'],'estimatedOnsetSeconds':onset,
                'estimatedEndSeconds':finish,'attribution':reason,'sourceLeaf':leaf['id'],
                'textStart':offset+unit['textStartCodepoint'],'textEnd':offset+unit['textEndCodepoint'],
                'historicalOnsetPolicyUnchanged':True,'fixedUncertaintyMarginSeconds':.06,
                'onsetOnlyNotWordDuration':True,'estimatedDisplayEndIsOnsetPlus60msClipped':True})
        offset+=len(leaf['text'])+1
    assert original['text']=='\n'.join(leaf['text'] for leaf in case['leaves'])
    doc={'isFinal':True,'text':original['text'],'utterances':utterances}
    out=derived/'transcripts'/name;out.mkdir(parents=True,exist_ok=True)
    assert not (out/'model-output.json').exists(),'Preserve prior derived outputs; no silent overwrite'
    atomic_json(out/'model-output.json',doc)
    attribution={'meeting':name,'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
        'allOriginalAudioSamplesCoveredOnce':True,'allTextPreservedThroughAttribution':True,
        'rawWindowText':original['text'],'tokenEstimates':tokens,'utterancesWithAttribution':utterances,
        'nativeToConsecutiveDisplaySpeakerIds':mapping,'speakerJournalSha256':record['sha256'],
        'sourceDocumentSha256':case['sourceDocumentSha256'],'scope':'Independent predicted word onset only; zero-duration classes do not invalidate an in-bound onset. Historical onset±60ms identity policy unchanged. Display end is onset+60ms clipped, not real word duration. Overlap/gap/boundary remains unknown. Every original word retained, both voices not recovered.'}
    atomic_json(out/'attribution-review.json',attribution)
    atomic_json(out/'completed-state.json',{'state':'COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED',
        'finishedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'audioSha256':case['audioSha256'],
        'speakerJournalPending':False,'modelOutputSha256':sha(out/'model-output.json'),
        'attributionReviewSha256':sha(out/'attribution-review.json'),'qualityQualified':False})
    check=subprocess.run([checker,str(out/'model-output.json'),str(round(duration*1000))],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic_json(out/'product-contract.json',{'exitCode':check.returncode,'stdout':check.stdout,'stderr':check.stderr,'installedAppOrPhonePassed':False})
    assert check.returncode==0,check.stderr
    with (out/'scoring.log').open('xb') as log:
        scored=subprocess.run([SC,str(Path(__file__).with_name('score_practical_transcript_20261107.py')),'--control',str(derived),'--meeting',name],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    assert scored.returncode==0
    quality=read(out/'quality-review.json');prior=read(Path(case['sourceDocument']).parent/'quality-review.json')
    raw_score=out/'scorer-original-output.json';assert not raw_score.exists()
    raw_score.write_bytes((out/'quality-review.json').read_bytes())
    quality.update(nativeTokenOnsetsAreApproximate=None,
        timingKind='independent_predicted_word_onsets_not_true_word_duration',
        originalScorerOutputSha256=sha(raw_score),
        timingMetadataCorrectionOnlyNoMetricChanges=True)
    atomic_json(out/'quality-review.json',quality)
    assert quality['chronologicalTextDiagnostic']==prior['chronologicalTextDiagnostic']
    valid_count=sum(u['positiveAndInOriginalLeafBounds'] for payload in payloads for u in payload['units'])
    rows.append({'meeting':name,'audioSeconds':duration,'sourceTextByteContentUnchanged':True,
        'rawChronologicalCerUnchanged':quality['chronologicalTextDiagnostic']['cer'],
        'standardAnonymousCpCerDiagnostic':quality['anonymousStreamCpCerDiagnostic'],
        'unknownForcedUnmatchedDiagnostic':quality['confirmedAttributionCerDiagnostic'],
        'unconfirmedText':quality['unconfirmedSpeakerText'],'alignmentUnits':len(tokens),
        'positiveInBoundPredictedTimeUnits':valid_count,'invalidOrZeroDurationTimeUnits':len(tokens)-valid_count,
        'authorMonotonicRepairChangedTimestamps':sum(p.get('authorMonotonicRepairChangedTimestamps',0) for p in payloads),
        'allOriginalCharactersAndPunctuationPreserved':True,'knownAnonymousSpeakerIds':sorted(set(r['speaker'] for r in utterances if r['speaker'] is not None)),
        'overlapUnitsExplicitlyUnknown':sum(r['overlapDetectedNearOnset'] for r in tokens),
        'inBoundPredictedOnsetUnits':sum(r['estimatedOnsetSeconds'] is not None for r in tokens),
        'historicalOnsetPolicyWithoutThresholdChanges':True,
        'newAsrNeuralCalls':0,'newSpeakerNeuralCalls':0,
        'alignmentInferenceSeconds':sum(p['inferenceSeconds'] for p in payloads),
        'trueWordTimeAccuracyMeasured':False,'timeConstrainedPerSpeakerCerMeasured':False,
        'bothOverlappingVoicesRecovered':False,'actualSharedRustProductDocumentPassed':True,'qualityQualified':False})
run=read(C/'run.json');receipts=[read(p) for p in run['priorAttemptReceipts']]+[run]
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CACHED_NATIVE_ALIGNMENT_ONSET_REGRESSION_CONTROL_NOT_QUALIFIED',
    'results':rows,'modelId':read(C/'model-source.json')['modelId'],'revision':read(C/'model-source.json')['revision'],
    'ownedStageProcessFamilySecondsIncludingInterruptions':{stage:sum(r['wholeProcessFamilySeconds'] for receipt in receipts for r in receipt['results'] if r['stage']==stage) for stage in ['tiny-loader','pilot','full']},
    'timeScope':'Alignment only, existing ASR and speaker inference not rerun. Tiny random loader control separate. Pilot node reused by full stage, interrupted attempts included. Not recording-to-minutes latency.',
    'noWordTimeGroundTruthAndNoTcpCerClaim':True,'qualityQualified':False,'defaultProductChanged':False,
    'finalHoldoutOpened':False,'installedWindowsAndroidCardPassed':False,'customerTrialPerformed':False,
    'next':'沿原QM04/QM05/RM-OVERLAP：已获得独立时间对齐与逐人内容的真实完整开发会诊断，原字错率5%仍未过；下一项根据两场逐人/未知/重叠漏词，固定已验证分人基线，验证其驱动的目标人分离，再逐路转写，普通非重叠必须保原字不回退。词级真值/时间约束逐人评分、噪声场景/跨域独立集/纪要事实/双端实卡/售卖门继续OPEN，不扫阈值或按会议挑后端。',
    'newAsrAlignmentOrSpeakerNeuralCalls':0,
    'qualification':'NOT_QUALIFIED: historical estimated-onset identity policy on fixed cached words/timestamps/activity. Word durations are unresolved, zero intervals retained. No verified word-time accuracy, simultaneous voices recovered, final holdout, factual minutes or installed phone/card acceptance.'}
review['posthocResourceLimits']=limits.query()
first=read(C/'review.json')
review['priorFullIntervalPolicyReviewSha256']=sha(C/'review.json')
review['controlledComparison']=[{'meeting':row['meeting'],'fullIntervalCpCer':next(r for r in first['results'] if r['meeting']==row['meeting'])['standardAnonymousCpCerDiagnostic']['characterErrorRate'],'historicalOnsetCpCer':row['standardAnonymousCpCerDiagnostic']['characterErrorRate']} for row in rows]
review['postprocessorSourceSha256']=sha(Path(__file__))
assert not (C/'onset-review.json').exists();atomic_json(C/'onset-review.json',review)
print(json.dumps({'state':review['state'],'results':[{k:r[k] for k in ['meeting','rawChronologicalCerUnchanged','alignmentUnits','invalidOrZeroDurationTimeUnits','unconfirmedText']} for r in rows],'stageSeconds':review['ownedStageProcessFamilySecondsIncludingInterruptions']},ensure_ascii=False))
