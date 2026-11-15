"""Explain annotation-dependent DER without replacing frozen qualification.

All inference outputs remain byte-identical. The external MFA annotations are
an independent diagnostic, not new ground truth or permission to pass D2.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
from pyannote.core import Annotation,Segment,Timeline

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
out=D/'reference-annotation-audit-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old_case=read('E:/CodexData/Companion/product-d1d2-20261114/ordinary-english-r1/speaker-scoring-only.json')
new_case=read(out/'alternate-case.json');hyp_binding=read(out/'hypothesis-binding.json')
old_score=read(hyp_binding['originalQualificationScore'])
new_score=read(out/'alternate-score-diagnostic-only.json')
assert old_case['audioSha256']==new_case['audioSha256']==old_score['audioSha256']==new_score['audioSha256']
assert old_case['audioSeconds']==new_case['audioSeconds']
assert sha(hyp_binding['file'])==hyp_binding['sha256']==old_score['rttmSha256']==new_score['rttmSha256']
assert sha(old_case['reference'])==old_case['referenceSha256']==old_score['referenceSha256']
assert sha(new_case['reference'])==new_case['referenceSha256']==new_score['referenceSha256']
duration=old_case['audioSeconds'];uem=Timeline([Segment(0,duration)])
def annotation(path):
 value=Annotation(uri=old_case['meeting'])
 for i,line in enumerate(Path(path).read_text(encoding='utf-8').splitlines()):
  f=line.split();assert f[0]=='SPEAKER' and len(f)==10
  start,length=float(f[3]),float(f[4]);assert start>=0 and length>0
  value[Segment(start,start+length),str(i)]=f[7]
 return value.support().crop(uem)
old,new,hyp=map(annotation,[old_case['reference'],new_case['reference'],hyp_binding['file']])
rows=[]
for person in old.labels():
 alt=old_case['meeting']+'.'+person
 assert alt in new.labels()
 group=old_score['perReferenceSpeakerForEvaluationOnly'][person]['matchedAnonymousGroup']
 assert group==new_score['perReferenceSpeakerForEvaluationOnly'][alt]['matchedAnonymousGroup']
 O=old.label_timeline(person).support();N=new.label_timeline(alt).support()
 H=hyp.label_timeline(group).support()
 common=O.crop(N).support();old_only=O.extrude(N).support();new_only=N.extrude(O).support()
 nonmatched=lambda reference:reference.duration()-reference.crop(H).duration()
 assert abs(common.duration()+old_only.duration()-O.duration())<1e-6
 assert abs(common.duration()+new_only.duration()-N.duration())<1e-6
 assert abs(nonmatched(O)-(O.duration()-old_score['perReferenceSpeakerForEvaluationOnly'][person]['correctlyAttributedSeconds']))<1e-6
 rows.append({'referencePersonForEvaluationOnly':person,'sameAnonymousMappingInBoth':group,
  'originalReferenceSeconds':O.duration(),'mfaReferenceSeconds':N.duration(),
  'commonReferenceSeconds':common.duration(),'originalOnlyReferenceSeconds':old_only.duration(),
  'mfaOnlyReferenceSeconds':new_only.duration(),
  'originalNonAttributedSeconds':nonmatched(O),
  'originalNonAttributedSecondsInCommonReference':nonmatched(common),
  'originalNonAttributedSecondsOutsideMfaReference':nonmatched(old_only),
  'mfaNonAttributedSeconds':nonmatched(N)})
total_nonmatch=sum(r['originalNonAttributedSeconds'] for r in rows)
outside_nonmatch=sum(r['originalNonAttributedSecondsOutsideMfaReference'] for r in rows)
# pyannote's segment operations use1us precision. The aggregate metric's
# cropping loses exactly1us relative to four per-person durations here.
# Match the original scorer's100us consistency check; no scoring tolerance
# or reference boundary is changed.
metric_nonmatch=old_score['components']['total']-old_score['components']['correct']
assert abs(total_nonmatch-metric_nonmatch)<1e-4
report={'state':'ANNOTATION_PROTOCOL_EXPLAINS_MUCH_OF_ENGLISH_ACTIVITY_SCORE_DIFFERENCE',
 'at':datetime.now().astimezone().isoformat(),'meeting':old_case['meeting'],'audioSeconds':duration,
 'originalReferenceDer':old_score['components']['diarization error rate'],
 'externalMfaDiagnosticDer':new_score['components']['diarization error rate'],
 'identicalPredictionSha256':hyp_binding['sha256'],'rows':rows,
 'originalNonAttributedSeconds':total_nonmatch,
 'originalNonAttributedSecondsOutsideMfaReference':outside_nonmatch,
 'aggregateVersusPerPersonRoundingDifferenceSeconds':total_nonmatch-metric_nonmatch,
 'fractionOriginalNonAttributedTimeOutsideMfaReference':outside_nonmatch/total_nonmatch,
 'originalReferenceQualificationStillFails':True,'originalQualificationScoreChanged':False,
 'd2Complete':False,'qualityQualified':False,'newNeuralCalls':0,'wordsOrModelOutputChanged':False,
 'scope':'Same complete recording and prediction, zero collar, overlap included, no time shifts/padding/threshold changes. Anonymous global mapping identical in both. Non-attributed time includes missed and confused reference activity; this decomposition is not a new DER definition.',
 'limits':['External force-aligned annotations also contain errors and are not independently human-verified here.',
  'Reference-only regions are annotation disagreements, not proved acoustic silence.',
  'Original whole English WER23.9405% remains unchanged. No new words or identity ability were learned.',
  'This English audit does not resolve the Chinese returning-speaker failure or qualify unseen rooms/devices.'],
 'nextAction':'Keep original failures and acceptance gates. Correct the prior diagnosis that English missed-activity seconds alone prove the same amount of lost speech; distinguish reference-protocol mismatch from missing lexical content and actual speaker confusion.',
 'limitsApplied':limits.query()}
target=out/'comparison.json';assert not target.exists()
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ['state','originalReferenceDer','externalMfaDiagnosticDer','originalNonAttributedSeconds','originalNonAttributedSecondsOutsideMfaReference','fractionOriginalNonAttributedTimeOutsideMfaReference','d2Complete']}))
