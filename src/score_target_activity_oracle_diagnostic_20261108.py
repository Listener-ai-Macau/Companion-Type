"""Score every oracle waveform condition; no model, word deletion or promotion."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,psutil
from practical_io_20261107 import atomic_json
from full_meeting_transcript_metrics_20261103 import normalize,Levenshtein
from moss_windows_resource_limits_20261104 import WorkerLimits

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
C=R/'docs/handoffs/20261108-target-activity-adaptation/oracle-activity-diagnostic'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert not (C/'review.json').exists()
for p in psutil.process_iter(['cmdline']):
    for arg in p.info['cmdline'] or []:
        assert not (str(arg).replace('\\','/').lower().startswith(str(M/'src').replace('\\','/').lower()+'/') and Path(str(arg)).name in ['target_activity_oracle_asr_worker_20261108.py','run_target_activity_oracle_diagnostic_20261108.py'])
run=read(C/'run-r2.json');assert run['state']=='COMPLETE_ORACLE_ACTIVITY_DIAGNOSTIC_REVIEW_REQUIRED'
protocol=read(C/'protocol-r2.json');outputs=read(C/'asr-manifest-r2.json');assert len(outputs)==12
assert read(C/'asr-state-r2.json')['state']=='COMPLETE_ORACLE_ACTIVITY_ASR_DIAGNOSTIC_NOT_PRODUCT'
assert sha(M/'src/target_activity_oracle_asr_worker_20261108.py')==protocol['workerSourceSha256']
prepared={r['id']:r for r in read(C/'separation-manifest-r2.json')}
byid={r['id']:r for r in outputs};assert len(byid)==len(prepared)==12
def edits(ref,hyp):
    truth=normalize(ref);text=normalize(hyp);ops=Counter(op.tag for op in Levenshtein.editops(truth,text))
    return {'referenceCharacters':len(truth),'hypothesisCharacters':len(text),'substitute':ops['replace'],'delete':ops['delete'],'insert':ops['insert'],'total':sum(ops.values()),'midpointClipEditRateDiagnostic':sum(ops.values())/len(truth) if truth else None}
rows=[]
for item in read(C/'scoring-only.json'):
    assert sha(item['cachedUngatedFile'])==item['cachedUngatedFileSha256']
    cached=read(item['cachedUngatedFile']);assert cached['text']==item['cachedUngatedText']
    row={'sourceLane':item['laneId'],'rootIndex':item['rootIndex'],'referencePerson':item['referencePerson'],
        'referenceRowsCrossingClipBoundary':item['referenceRowsCrossingClipBoundary'],
        'ungatedSeparated':{'text':cached['text'],'edits':edits(item['referenceText'],cached['text'])}}
    for mode in ['mixture','separated']:
        identity=item['laneId']+'-oracle-'+mode;output=byid[identity];audio=prepared[identity]
        assert output['binding']['protocolSha256']==sha(C/'protocol-r2.json')
        assert output['audioSha256']==audio['audioSha256']==sha(audio['audio'])
        assert output['referenceActivityUsedOnWaveform'] and output['allTargetActivePcmSamplesUnchanged']
        assert output['originalSampleCountAndTimelineUnchanged']
        row['oracleGated'+mode.title()]={'text':output['text'],'edits':edits(item['referenceText'],output['text']),
            'inputSamples':round(output['audioSeconds']*16000),'targetActiveSamples':audio['maskActiveSamples'],
            'acceptedLeaves':len(output['acceptedLeaves'])}
    rows.append(row)
keys=['ungatedSeparated','oracleGatedMixture','oracleGatedSeparated']
def total(selected,key):
    stats={k:sum(r[key]['edits'][k] for r in selected) for k in ['referenceCharacters','hypothesisCharacters','substitute','delete','insert','total']}
    stats['midpointClipEditRateDiagnostic']=stats['total']/stats['referenceCharacters'] if stats['referenceCharacters'] else None
    return stats
totals={key:total(rows,key) for key in keys}
before=totals['ungatedSeparated']['total'];mixed=totals['oracleGatedMixture']['total'];after=totals['oracleGatedSeparated']['total']
state='REFERENCE_GATE_HELPS_BUT_SEPARATION_STILL_UNQUALIFIED' if after<before and after<mixed else 'REFERENCE_ACTIVITY_GATE_ALONE_NOT_A_SOLUTION'
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':state,
    'purpose':'Causal diagnostic after two failed target-activity adaptations; not a third learned candidate.',
    'protocolSha256':sha(C/'protocol-r2.json'),'originalNativeAsrProtocolSha256':protocol['nativeAsrProtocolSha256'],
    'originalInferFunctionAstMatches':protocol['asrGenerationFunctionAstUnchanged'],
    'rootSelection':[12,27],'uniqueOriginalAudioSeconds':60,'existingTargetLanes':6,'newAudioConditions':12,
    'actualRootCoverage':read(C/'audio-gate-preparation.json')['roots'],
    'allConditionsScored':True,'sameFixedWholeMeetingPersonMapping':True,
    'totals':totals,'perRoot':[{'rootIndex':root,**{key:total([r for r in rows if r['rootIndex']==root],key) for key in keys}} for root in [12,27]],
    'allLaneDetails':rows,
    'observations':{'oracleGatedSeparationFewerEditsThanUngated':after<before,
        'oracleGatedSeparationFewerEditsThanEquallyGatedMixture':after<mixed,
        'differenceFromUngated':after-before,'differenceFromEquallyGatedMixture':after-mixed},
    'limitations':[
        'Oracle uses true reference activity to alter waveforms before ASR. It is unavailable in production; no oracle number qualifies the product.',
        'Six existing extracted lanes in two exposed Mandarin roots are not a whole meeting, independent corpus or final holdout. Reference-assisted root27 has1.900779s actual triple overlap.',
        'Midpoint-selected full utterance texts can straddle30s clip edges. Report these rows; paired edit differences are diagnostic, not strict full-recordingCER or pure-overlapCER.',
        'Utterance-based hard zeroing may clip phonetic context. Target-active samples are preserved but this is not an internally activity-conditioned separator or a mathematical upper bound on all separation methods.',
        'Without clean per-person waveform truth this does not uniquely attribute residual errors to ASR versus separation distortion or prove all larger adaptation impossible.'
    ],
    'actualOwnedSecondsIncludingKnownInterruptions':{stage:sum(r['wholeProcessFamilySeconds'] for receipt in [run]+[read(p) for p in run['priorAttemptReceipts']] for r in receipt['results'] if r['stage']==stage) for stage in ['inventory','asr']},
    'maximumRecordedNeuralJobPrivateBytes':read(C/'asr-state-r2.json')['limits']['jobPeakPrivateCommitBytes'],
    'newAsrCalls':read(C/'asr-state-r2.json')['newNeuralCalls'],'newSeparationCalls':0,'newTrainingRuns':0,
    'noReferenceWordsInAsrPrompt':True,'generatedTextFiltered':False,'originalTextAudioAndDefaultChanged':False,
    'phoneOrBoardAccessed':False,'finalHoldoutOpened':False,'qualityQualified':False,
    'next':('继续原RM-OVERLAP：已知正确活动时间的局部对照仍不能作为产品交付。先逐人复核本次残余替换/漏字/插入及片段边界影响，分开检查分离波形与ASR；只有取得独立真实验证和可用干净源监督后才投入针对性分离适配。保留NativeFP16与普通ASR，不重跑两个失败小头，不调阈值凑通过；全部<5%/纪要事实/双端实卡/售卖门继续开放。')}
atomic_json(C/'review.json',result)
readme=M/'README.md';text=readme.read_text(encoding='utf8');marker='Observed reference-activity waveform diagnostic,2026-11-08:';assert marker not in text
text+=f'\n\n{marker} this continues the same RM-OVERLAP after rejecting the two small-head adaptations. Fixed exposed Lroots12/27 contain real two-person overlap and1.900779s triple overlap respectively. Six already extracted lanes receive a perfect-reference utterance activity mask, preserving every active PCM value and the original30s timeline. The same mask is also applied to the original mixture. All12waveforms run the unchanged native1.7B ASR inference function; the original six ungated separated transcripts are reused, never regenerated or word-filtered. Midpoint-utterance clip edit totals are ungated separated{before},oracle-gated mixture{mixed},oracle-gated separated{after} over{totals["ungatedSeparated"]["referenceCharacters"]}reference characters. These are annotation-assisted local diagnostics with boundary-straddling utterances, not strict whole-recordingCER, pure-overlapCER, a new model pass or an absolute upper bound. Read evidence/20261108-target-activity-adaptation/oracle-activity-diagnostic/review.json for every person/root and limitations. No further separation/training, installed app/card change or final holdout opening occurred. Product qualification remains open.\n'
readme.write_text(text,encoding='utf8')
print(json.dumps({k:result[k] for k in ['state','totals','observations','actualOwnedSecondsIncludingKnownInterruptions','newAsrCalls','newSeparationCalls','qualityQualified']},ensure_ascii=False),flush=True)
