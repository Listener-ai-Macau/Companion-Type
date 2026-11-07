"""Score an exited complete public-meeting run; references never enter inference."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter,defaultdict
import argparse,hashlib,json,math,re,subprocess,sys
import psutil
psutil.Process().cpu_affinity([10]);psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
from full_meeting_transcript_metrics_20261103 import speaker_cer,normalize,group_transcripts,Levenshtein
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID

parser=argparse.ArgumentParser();parser.add_argument('--meeting',required=True);parser.add_argument('--run',default='whole-meetings-run.json')
parser.add_argument('--control-root',help='Isolated experiment control directory; defaults to the original night batch')
parser.add_argument('--diagnose-complete-text-with-invalid-time',action='store_true')
parser.add_argument('--score-label',default='')
args=parser.parse_args()
root=Path(args.control_root) if args.control_root else Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
run=read(root/args.run)
assert args.meeting!=run.get('activeMeeting'),'Do not score a meeting while its inference is active'
result=next(x for x in run['results'] if x['meeting']==args.meeting)
raw_folder=Path(result['receipt']).parent;folder=raw_folder;state=read(result['receipt'])
if args.score_label:
 assert all(c.isalnum() or c in '._-' for c in args.score_label)
 folder=raw_folder/args.score_label;folder.mkdir(exist_ok=False)
assert result['exitCode']==0
timing_diagnostic=bool(args.diagnose_complete_text_with_invalid_time and state['state']=='OUTPUT_RETAINED_INCOMPLETE_OR_INVALID'
 and state.get('eosCompleted') and state.get('allGeneratedTextParsed') and state.get('invalidNativeTimeRows'))
assert state['state']=='COMPLETE_JOINT_CANDIDATE_UNQUALIFIED' or timing_diagnostic
case=next(x for x in read(root/'frozen-scoring-only.json') if x['meeting']==args.meeting)
assert case['meeting']==state['meeting']==args.meeting,'Scoring case and completed worker meeting must match'
assert case['audioSha256']==state['audioSha256'],'Scoring reference belongs to a different source audio'
assert case['audioSeconds']==state['audioSeconds'],'Scoring and completed input durations must match'
reference=Path(case['reference']);assert hashlib.sha256(reference.read_bytes()).hexdigest()==case['referenceSha256']
assert hashlib.sha256((raw_folder/'model-output.json').read_bytes()).hexdigest()==state['modelOutputSha256']
references=[r for r in read_reference_intervals(reference) if normalize(r['text'])]
hypothesis=read(raw_folder/'raw-parsed-segments.json')
assert all(math.isfinite(r['start']) and math.isfinite(r['end']) and 0<=r['start']<r['end'] for r in hypothesis)
ordering_envelope=max([case['audioSeconds']]+[r['end'] for r in hypothesis])
score=speaker_cer(references,hypothesis,ordering_envelope)
target=folder/'full-speaker-cer.json';assert not target.exists();target.write_text(json.dumps(score,ensure_ascii=False,indent=2),encoding='utf8')
ref_groups=group_transcripts(references,ordering_envelope);hyp_groups=group_transcripts(hypothesis,ordering_envelope)
audit=[{**pair,'referenceText':ref_groups.get(pair['referenceSpeaker'],''),
        'hypothesisText':hyp_groups.get(pair['hypothesisSpeaker'],'')} for pair in score['anonymousAssignmentForEvaluationOnly']]
(folder/'full-speaker-error-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
case_file=folder/'scoring-case.json';case_file.write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf8')
der_file=folder/'standard-sentence-der.json'
rttm=raw_folder/'predicted.rttm'
if timing_diagnostic:
 rttm=folder/'raw-native-time-diagnostic.rttm';assert not rttm.exists()
 rttm.write_text(''.join(f"SPEAKER meeting 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> {r['speaker']} <NA> <NA>\n" for r in hypothesis),encoding='utf8')
with (folder/'score-der.log').open('xb') as log:
 subprocess.run([sys.executable,str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),
  '--case',str(case_file),'--rttm',str(rttm),'--out',str(der_file)],
  check=True,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
der=read(der_file)
events=defaultdict(list)
for side,rows in [('reference',references),('hypothesis',hypothesis)]:
 for row in rows:
  start,end=max(0.,row['start']),min(case['audioSeconds'],row['end'])
  if end<=start:continue
  events[start].append((side,row['speaker'],1));events[end].append((side,row['speaker'],-1))
active={'reference':Counter(),'hypothesis':Counter()};total=Counter();points=sorted(events)
for index,start in enumerate(points[:-1]):
 for side,person,change in events[start]:
  active[side][person]+=change
  if not active[side][person]:del active[side][person]
 seconds=points[index+1]-start;truth=len(active['reference'])>=2;predicted=len(active['hypothesis'])>=2
 if truth:total['referenceOverlapSeconds']+=seconds
 if predicted:total['predictedOverlapSeconds']+=seconds
 if truth and predicted:total['truePositiveSeconds']+=seconds
 elif truth:total['missedOverlapSeconds']+=seconds
 elif predicted:total['falseOverlapSeconds']+=seconds
overlap={**total,'recall':total['truePositiveSeconds']/total['referenceOverlapSeconds'] if total['referenceOverlapSeconds'] else None,
 'precision':total['truePositiveSeconds']/total['predictedOverlapSeconds'] if total['predictedOverlapSeconds'] else None,
 'limits':'Temporal detection of two or more active people only. Does not establish each person\'s overlapping words or true word timing.'}
ref_text=normalize(''.join(x['text'] for x in sorted(references,key=lambda x:(x['start'],x['end']))))
hyp_text=normalize(''.join(x['text'] for x in sorted(hypothesis,key=lambda x:(x['start'],x['end']))))
counts=Counter(op.tag for op in Levenshtein.editops(ref_text,hyp_text))
ordinary={'referenceCharacters':len(ref_text),'edits':dict(counts),'ordinaryCer':sum(counts.values())/len(ref_text),
 'scope':'Chronological speaker-ignored diagnostic. Ordering is ambiguous during overlap; cpCER remains the primary full-meeting text metric.'}
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 'referenceParser':PARSER_ID,'rawModelOutputDirectory':str(raw_folder),'referenceSha256':case['referenceSha256'],
 'state':'FULL_REAL_DEVELOPMENT_MEETING_SCORED_PRODUCT_GATES_OPEN','meeting':args.meeting,'corpus':case['corpus'],
 'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],'speakerAttributedCpCer':score['characterErrorRate'],
 'referenceCharacters':score['referenceCharacters'],'textEdits':score['edits'],'ordinaryTextDiagnostic':ordinary,
 'nativeTimingValid':not bool(state.get('invalidNativeTimeRows')),'nativeTimingViolations':state.get('invalidNativeTimeRows',[]),
 'rawTimeOrderingEnvelopeSeconds':ordering_envelope,'sourceAudioSeconds':case['audioSeconds'],'timingInvalidDiagnosticOnly':timing_diagnostic,
 'nativeSentenceDer':der['components']['diarization error rate'],'referenceSpeakers':der['referenceSpeakers'],
 'predictedSpeakers':der['predictedSpeakers'],'uncoveredReferenceSpeakers':der['uncoveredReferenceSpeakers'],
 'macroAttributionRecall':der['macroReferenceAttributionRecall'],'shortReferenceSpans':der['shortReferenceSpans'],
 'overlapActivity':overlap,'runtime':{k:state.get(k) for k in ['actualGpu','gpuIndex','torchVersion','hipVersion','actualDtype',
  'modelLoadSeconds','inputPreparationSeconds','audioEncodingSeconds','firstGeneratedTokenSeconds','generationSeconds',
  'wholeWorkerSeconds','gpuPeakAllocatedBytes','gpuPeakReservedBytes','executionAdapters','cooperativeGpuPacing','resourceLimitsAfterGpuInit']},
 'resources':result,'priorInferenceAttemptProcessFamilySeconds':state.get('priorInferenceAttemptProcessFamilySeconds',0),
 'totalInferenceAttemptProcessFamilySeconds':result['wholeProcessFamilySeconds']+state.get('priorInferenceAttemptProcessFamilySeconds',0),
 'currentAttemptRealTimeFactor':result['wholeProcessFamilySeconds']/case['audioSeconds'],
 'realTimeFactor':(result['wholeProcessFamilySeconds']+state.get('priorInferenceAttemptProcessFamilySeconds',0))/case['audioSeconds'],
 'resumedPrefixTokens':state.get('resumedPrefixTokens',0),
 'timeAccountingScope':'Sum of this exited attempt and verified prior inference attempts, including failed work; excludes between-attempt waiting. Generation timing fields refer to this attempt.',
 'speakerTextUnder5PercentOnThisCase':score['characterErrorRate']<.05,'productQualified':False,
 'limits':'Frozen development recordings, not the final unseen holdout. Full input and all output streams retained, no reference text/count/hotwords in inference. Sentence timestamps are not verified word alignment; physical card, phone, critical-fact/minutes and commercial acceptance are separate.'}
(folder/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
