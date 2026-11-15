"""Temporal diagnostic only for a completed compatibility clip, never a CER gate."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,hashlib,subprocess,sys,psutil
from pyannote.core import Annotation,Segment,Timeline
from pyannote.metrics.diarization import DiarizationErrorRate
from full_meeting_transcript_metrics_20261103 import normalize
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID

p=argparse.ArgumentParser();p.add_argument('--control-root',required=True);p.add_argument('--run',required=True)
p.add_argument('--reference-cases',required=True);p.add_argument('--out',required=True);args=p.parse_args()
psutil.Process().cpu_affinity(psutil.Process().cpu_affinity()[-1:]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
read=lambda path:json.loads(Path(path).read_text(encoding='utf8'))
control=Path(args.control_root);run=read(control/args.run)
assert run['state']=='COMPLETE_GPU_INFERENCE_SCORING_REQUIRED' and len(run['results'])==1
result=run['results'][0];state=read(result['receipt']);folder=Path(result['receipt']).parent
assert result['exitCode']==0 and result['smokeOnly'] and state['eosCompleted'] and not state['invalidNativeTimeRows']
case=next(c for c in read(args.reference_cases) if c['meeting']=='S_R004S03C01')
assert state['audioSeconds']==30
assert hashlib.sha256(Path(case['reference']).read_bytes()).hexdigest()==case['referenceSha256']
assert hashlib.sha256((folder/'model-output.json').read_bytes()).hexdigest()==state['modelOutputSha256']
references=[row for row in read_reference_intervals(case['reference']) if normalize(row['text'])]
crossing=[row for row in references if row['start']<30<row['end']]
output=Path(args.out);output.mkdir(exist_ok=False)
scoring_case={**case,'meeting':state['meeting'],'audioSeconds':30,'audioSha256':state['audioSha256'],'corpus':'AISHELL-4','referenceKind':'textgrid_lexical'}
(output/'scoring-case.json').write_text(json.dumps(scoring_case,indent=2),encoding='utf8')
with (output/'der.log').open('xb') as log:
    subprocess.run([sys.executable,str(Path(__file__).with_name('score_cross_corpus_diarization_20261103.py')),
        '--case',str(output/'scoring-case.json'),'--rttm',str(folder/'predicted.rttm'),'--out',str(output/'temporal-der.json')],
        check=True,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
der=read(output/'temporal-der.json')
# Analytic overlapping-speech fixture: reference A[0,2], B[1,3] has4
# speaker-seconds. Missing B[1,2] plus one false-positive second = DER0.5.
truth=Annotation(uri='analytic');truth[Segment(0,2),'a']='A';truth[Segment(1,3),'b']='B'
hyp=Annotation(uri='analytic');hyp[Segment(0,2),'x']='X';hyp[Segment(2,3),'y']='Y';hyp[Segment(3,4),'z']='X'
components=DiarizationErrorRate(collar=0.,skip_overlap=False)(truth,hyp,uem=Timeline([Segment(0,4)],uri='analytic'),detailed=True)
assert abs(components['total']-4)<1e-9 and abs(components['missed detection']-1)<1e-9 and abs(components['false alarm']-1)<1e-9
assert abs(components['diarization error rate']-.5)<1e-9
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
    'state':'COMPLETED_COMPATIBILITY_CLIP_TEMPORAL_DIAGNOSTIC_ONLY_NOT_WHOLE_MEETING_QUALIFICATION',
    'audioSeconds':30,'referenceParser':PARSER_ID,'sourceMeeting':case['meeting'],
    'fullSourceReferenceSha256':case['referenceSha256'],'sourceModelOutputSha256':state['modelOutputSha256'],
    'referenceSpeakersInClip':der['referenceSpeakers'],'predictedSpeakersInClip':der['predictedSpeakers'],
    'sentenceBoundaryDer':der['components']['diarization error rate'],'derComponents':der['components'],
    'macroAttributionRecall':der['macroReferenceAttributionRecall'],'uncoveredReferenceSpeakers':der['uncoveredReferenceSpeakers'],
    'cer':None,'cerNotComputedReason':'One original annotated utterance crosses the30s audio cut and ends at39.93091s; character reference cannot be clipped by time without word alignment. Do not count its missing out-of-clip words, silently omit it, or hand-edit to claim CER.',
    'crossingReferenceIntervals':[{k:row[k] for k in ['start','end','speaker']} for row in crossing],
    'overlapChallengeEvaluated':False,'sourceScope':'Opening speaker introductions only, not the later noisy/overlapping meeting.',
    'analyticOverlapMissAndFalseAlarmScorerFixturePassed':True,'analyticFixtureComponents':{k:float(v) for k,v in components.items()},
    'referenceEnteredModel':False,'productQualified':False,'newWholeMeetingAccuracy':None,'resources':result}
(output/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(report,ensure_ascii=False))
