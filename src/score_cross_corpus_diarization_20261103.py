"""Score a saved candidate against its frozen corpus reference, after inference."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,re,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
root=Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai')
sys.path.insert(0,str(root/'standard-diarization-eval'))
from pyannote.core import Annotation,Segment,Timeline
from pyannote.metrics.diarization import DiarizationErrorRate
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID

p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--rttm',required=True);p.add_argument('--out',required=True);a=p.parse_args()
case=json.loads(Path(a.case).read_text(encoding='utf8'));grid=Path(case['reference'])
assert hashlib.sha256(grid.read_bytes()).hexdigest()==case['referenceSha256']
reference=Annotation(uri=case['meeting'])
if case['referenceKind']=='rttm_only_words':
 for index,line in enumerate(grid.read_text(encoding='utf8').splitlines()):
  fields=line.split()
  if not fields:continue
  assert len(fields)==10 and fields[0]=='SPEAKER'
  start=float(fields[3]);reference[Segment(start,start+float(fields[4])),str(index)]=fields[7]
else:
 for index,row in enumerate(read_reference_intervals(grid)):
  if re.sub(r'<[^>]*>','',row['text']).strip():
   reference[Segment(row['start'],row['end']),row['speaker']+':'+str(index)]=row['speaker']
uem=Timeline([Segment(0,case['audioSeconds'])],uri=case['meeting'])
reference=reference.support().crop(uem)
assert reference.labels(),'No supported reference speech; inspect source, do not substitute'
hypothesis=Annotation(uri=case['meeting'])
for index,line in enumerate(Path(a.rttm).read_text(encoding='utf8').splitlines()):
 fields=line.split();assert len(fields)==10 and fields[0]=='SPEAKER'
 start=float(fields[3]);duration=float(fields[4]);assert start>=0 and duration>0
 hypothesis[Segment(start,start+duration),str(index)]=fields[7]
hypothesis=hypothesis.support().crop(uem)
metric=DiarizationErrorRate(collar=0.,skip_overlap=False)
components=metric(reference,hypothesis,uem=uem,detailed=True)
mapping=metric.optimal_mapping(reference,hypothesis,uem=uem)
assert set(mapping).issubset(hypothesis.labels())
by_reference={person:group for group,person in mapping.items()}
people={};short=[]
for person in reference.labels():
 ref=reference.label_timeline(person).support();group=by_reference.get(person)
 hyp=Timeline() if group is None else hypothesis.label_timeline(group).support()
 total=ref.duration();correct=ref.crop(hyp).duration()
 people[person]={'referenceSeconds':total,'correctlyAttributedSeconds':correct,'attributionRecall':correct/total if total else None,'matchedAnonymousGroup':group}
 for segment in ref:
  if segment.duration<2:
   hit=hyp.crop(segment).duration();short.append({'referenceSeconds':segment.duration,'correctSeconds':hit,'referenceSpeakerForEvaluationOnly':person})
assert abs(sum(v['correctlyAttributedSeconds'] for v in people.values())-components['correct'])<1e-4,'Coverage disagrees with standard global mapping'
report={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'corpus':case['corpus'],'meeting':case['meeting'],
 'referenceParser':PARSER_ID if case['referenceKind']!='rttm_only_words' else 'original_rttm_parser',
 'audioSeconds':case['audioSeconds'],'audioSha256':case['audioSha256'],'referenceSha256':case['referenceSha256'],'referenceKind':case['referenceKind'],
 'scope':'Frozen validation, full continuous-time DER, zero collar, overlap included. Global anonymous mapping only for evaluation. Not ASR/meeting-minutes or product acceptance. AMI only_words short spans are not directly comparable to TextGrid utterance turns.',
 'referenceSpeakers':len(reference.labels()),'predictedSpeakers':len(hypothesis.labels()),
 'components':{k:float(v) for k,v in components.items()},'perReferenceSpeakerForEvaluationOnly':people,
 'macroReferenceAttributionRecall':sum(v['attributionRecall'] for v in people.values())/len(people),
 'uncoveredReferenceSpeakers':[name for name,value in people.items() if value['correctlyAttributedSeconds']==0],
 'shortReferenceSpans':{'definition':'Reference speech spans shorter than2s under the corpus boundary policy; no per-span remapping.','count':len(short),'referenceSeconds':sum(v['referenceSeconds'] for v in short),'correctSeconds':sum(v['correctSeconds'] for v in short),'zeroCorrectSpans':sum(v['correctSeconds']==0 for v in short)},
 'rttmSha256':hashlib.sha256(Path(a.rttm).read_bytes()).hexdigest()}
output=Path(a.out);assert not output.exists();output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['corpus','meeting','referenceSpeakers','predictedSpeakers','components','uncoveredReferenceSpeakers']},ensure_ascii=False))
