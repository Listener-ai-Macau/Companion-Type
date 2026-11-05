"""Post-inference prefix diagnostics; cannot qualify a full-meeting model."""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter,defaultdict
import argparse,hashlib,json,math,re,subprocess,sys
import psutil
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);psutil.Process().cpu_affinity([10])
from full_meeting_transcript_metrics_20261103 import speaker_cer,normalize,group_transcripts,Levenshtein
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID

p=argparse.ArgumentParser();p.add_argument('--meeting',required=True);p.add_argument('--run',default='screening-run-r4.json')
p.add_argument('--diagnose-complete-text-with-invalid-time',action='store_true')
p.add_argument('--score-label',default='');a=p.parse_args()
root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
run=read(root/a.run);assert run.get('activeMeeting')!=a.meeting
result=next(x for x in run['results'] if x['meeting']==a.meeting)
state=read(result['receipt']);raw_folder=Path(result['receipt']).parent;folder=raw_folder
if a.score_label:
    assert all(c.isalnum() or c in '._-' for c in a.score_label)
    folder=raw_folder/a.score_label;folder.mkdir(exist_ok=False)
assert result['exitCode']==0
timing_diagnostic=bool(a.diagnose_complete_text_with_invalid_time and state['state']=='OUTPUT_RETAINED_INCOMPLETE_OR_INVALID'
 and state.get('eosCompleted') and state.get('allGeneratedTextParsed') and state.get('invalidNativeTimeRows'))
assert state['state']=='COMPLETE_JOINT_CANDIDATE_UNQUALIFIED' or timing_diagnostic
case=next(x for x in read(root/'screening-scoring-only-r4.json') if x['meeting']==a.meeting)
path=Path(case['reference']);assert hashlib.sha256(path.read_bytes()).hexdigest()==case['referenceSha256']
assert hashlib.sha256((raw_folder/'model-output.json').read_bytes()).hexdigest()==state['modelOutputSha256']
refs=[];boundary=[]
for original in read_reference_intervals(path):
    start,end,text=original['start'],original['end'],original['text']
    if not normalize(text) or start>=120 or end<=0:continue
    row={'start':max(0.,start),'end':min(120.,end),'speaker':original['speaker'],'text':text}
    refs.append(row)
    if start<0 or end>120:boundary.append({**row,'originalStart':start,'originalEnd':end})
hyps=read(raw_folder/'raw-parsed-segments.json')
assert all(math.isfinite(r['start']) and math.isfinite(r['end']) and 0<=r['start']<r['end'] for r in hyps)
# cpCER uses times only for per-stream ordering. Extend its validation envelope
# to include the RAW estimates, never extend the actual audio or alter a stamp.
ordering_envelope=max([120.]+[r['end'] for r in hyps])
cp=speaker_cer(refs,hyps,ordering_envelope)
core=[r for r in refs if not any(r['speaker']==b['speaker'] and r['start']==b['start'] and r['end']==b['end'] for b in boundary)]
core_cp=speaker_cer(core,hyps,ordering_envelope) if core else None
(folder/'prefix-cpcer.json').write_text(json.dumps({'includingAllCrossingReferenceText':cp,'excludingCrossingReferenceSpansDiagnostic':core_cp,'boundaryCensoredSpans':boundary},ensure_ascii=False,indent=2),encoding='utf8')
case_file=folder/'prefix-scoring-case.json';case_file.write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf8')
der_file=folder/'prefix-native-sentence-der.json'
rttm=raw_folder/'predicted.rttm'
if timing_diagnostic:
    rttm=folder/'raw-native-time-diagnostic.rttm';assert not rttm.exists()
    rttm.write_text(''.join(f"SPEAKER meeting 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> {r['speaker']} <NA> <NA>\n" for r in hyps),encoding='utf8')
with (folder/'prefix-score-der.log').open('xb') as log:
    subprocess.run([sys.executable,str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),
      '--case',str(case_file),'--rttm',str(rttm),'--out',str(der_file)],check=True,
      stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
der=read(der_file)
events=defaultdict(list)
for side,rows in [('ref',refs),('hyp',hyps)]:
    for r in rows:
        # Evaluation UEM is the actual audio [0,120], as in standard DER.
        # Raw native outputs remain untouched and timing violations stay open.
        start,end=max(0.,r['start']),min(120.,r['end'])
        if end<=start:continue
        events[start].append((side,str(r['speaker']),1));events[end].append((side,str(r['speaker']),-1))
active={'ref':Counter(),'hyp':Counter()};counts=Counter();points=sorted(events)
for i,start in enumerate(points[:-1]):
    for side,speaker,delta in events[start]:
        active[side][speaker]+=delta
        if not active[side][speaker]:del active[side][speaker]
    duration=points[i+1]-start;truth=len(active['ref'])>=2;pred=len(active['hyp'])>=2
    if truth:counts['referenceSeconds']+=duration
    if pred:counts['predictedSeconds']+=duration
    if truth and pred:counts['truePositiveSeconds']+=duration
overlap={**counts,'recall':counts['truePositiveSeconds']/counts['referenceSeconds'] if counts['referenceSeconds'] else None,
 'precision':counts['truePositiveSeconds']/counts['predictedSeconds'] if counts['predictedSeconds'] else None}
ref_text=normalize(''.join(r['text'] for r in sorted(refs,key=lambda r:(r['start'],r['end']))))
hyp_text=normalize(''.join(r['text'] for r in sorted(hyps,key=lambda r:(r['start'],r['end']))))
byref=group_transcripts(refs,120.);byhyp=group_transcripts(hyps,ordering_envelope)
audit=[]
for pair in cp['anonymousAssignmentForEvaluationOnly']:
    left=byref.get(pair['referenceSpeaker'],'');right=byhyp.get(pair['hypothesisSpeaker'],'')
    audit.append({**pair,'referenceText':left,'hypothesisText':right,
      'referenceCharacterCount':len(left),'hypothesisCharacterCount':len(right)})
(folder/'prefix-speaker-error-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 'referenceParser':PARSER_ID,'rawModelOutputDirectory':str(raw_folder),'referenceSha256':case['referenceSha256'],
 'state':'REAL_PREFIX_SCREENING_SCORED_NOT_FULL_MEETING_QUALIFICATION','meeting':a.meeting,'parentMeeting':case['parentMeeting'],'audioSeconds':120.,
 'cpCerIncludingBoundaryCensoredReferenceText':cp['characterErrorRate'],'cpCerWithoutCensoredReferenceDiagnostic':core_cp['characterErrorRate'] if core_cp else None,
 'referenceCharacters':cp['referenceCharacters'],'textEdits':cp['edits'],'boundaryCensoredSpans':boundary,
 'nativeTimingValid':not bool(state.get('invalidNativeTimeRows')),'nativeTimingViolations':state.get('invalidNativeTimeRows',[]),
 'rawTimeOrderingEnvelopeSeconds':ordering_envelope,'sourceAudioSeconds':120.,'timingInvalidDiagnosticOnly':timing_diagnostic,
 'ordinaryChronologicalCerDiagnostic':Levenshtein.distance(ref_text,hyp_text)/len(ref_text),
 'nativeSentenceDer':der['components']['diarization error rate'],'referenceSpeakers':der['referenceSpeakers'],'predictedSpeakers':der['predictedSpeakers'],
 'uncoveredReferenceSpeakers':der['uncoveredReferenceSpeakers'],'macroAttributionRecall':der['macroReferenceAttributionRecall'],
 'shortReferenceSpans':der['shortReferenceSpans'],'overlapActivityDiagnostic':overlap,
 'resources':result,'runtime':{k:state.get(k) for k in ['actualGpu','actualDtype','resourceLimitsAfterGpuInit','cooperativeGpuPacing','modelLoadSeconds','audioEncodingSeconds','generationSeconds','wholeWorkerSeconds','gpuPeakAllocatedBytes','gpuPeakReservedBytes']},
 'fullMeetingQualified':False,'newWeightsTrained':False,
 'limits':'Fixed first120s screening of exposed real meetings, not whole meeting or blind holdout. Cross-edge lexical spans are censored: all text is retained in main cpCER, exclusion is a second diagnostic. Anonymous mapping is scoring only. Native sentence timestamps are not verified word alignment. Temporal overlap recall is not each-person word recovery.'}
target=folder/'prefix-review.json';assert not target.exists();target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:report[k] for k in ['state','parentMeeting','cpCerIncludingBoundaryCensoredReferenceText','cpCerWithoutCensoredReferenceDiagnostic','ordinaryChronologicalCerDiagnostic','nativeSentenceDer','referenceSpeakers','predictedSpeakers','overlapActivityDiagnostic']},ensure_ascii=False))
