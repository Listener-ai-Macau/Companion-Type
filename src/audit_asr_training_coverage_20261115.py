"""Audit whether the frozen training cohort covers observed meeting failures.

Counts and natural-context plans use disjoint existing training/validation
sources only. This does not train, generate speech output, alter a scoring
reference, or make a new quality claim.
"""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from reference_textgrid_20261104 import read_reference_intervals
import soundfile as sf

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
D=C/'d1d2-execution/asr-training-coverage-audit-r1';D.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sources=read(R/'docs/handoffs/20261108-tse-source-supervision/sources.json')
old=read(C/'ordinary-asr-adaptation-r1/train.json')
assert len(old)==128
exposed={'S_R004S03C01','20200623_S_R001S07C01','L_R003S01C02','L_R003S03C02'}
assert not exposed&{s['meeting'] for s in sources}
assert not {s['meeting'] for s in sources if s['role']=='train'}&{s['meeting'] for s in sources if s['role']=='validation'}
results=[]
for source in sources:
 assert sha(source['reference'])==source['referenceSha256']
 assert sha(source['localFlac'])==source['expectedWholeFileLfsSha256']
 info=sf.info(source['localFlac']);assert info.samplerate==16000 and info.channels==8 and info.subtype=='PCM_16'
 rows=[row for row in read_reference_intervals(source['reference']) if row['text'].strip()]
 rows=sorted(rows,key=lambda x:(x['start'],x['end'],x['speaker']))
 assert all(row['end']>=row['start'] for row in rows)
 short=[];previous_end=0.
 for i,row in enumerate(rows):
  duration=row['end']-row['start'];lexical=''.join(c for c in row['text'] if c.isalnum())
  overlaps=(previous_end>row['start']+1e-9 or (i+1<len(rows) and rows[i+1]['start']<row['end']-1e-9))
  if 0<duration<2 and 1<=len(lexical)<=8 and '<' not in row['text'] and '>' not in row['text'] and not overlaps:
   short.append({'start':row['start'],'end':row['end'],'seconds':duration,'speaker':row['speaker'],
                 'text':row['text'],'lexicalCharacters':len(lexical)})
  previous_end=max(previous_end,row['end'])
 # Connected components prevent a natural-context plan from cutting through
 # an annotated utterance or an overlapping utterance. Every component is
 # retained or explicitly reported as too long, never silently shortened.
 components=[]
 for row in rows:
  if components and row['start']<components[-1]['end']-1e-9:
   components[-1]['end']=max(components[-1]['end'],row['end']);components[-1]['rows'].append(row)
  else:components.append({'start':row['start'],'end':row['end'],'rows':[row]})
 chunks=[];pending=[];oversized=[]
 def emit():
  if not pending:return
  words=[r for component in pending for r in component['rows']]
  start,end=pending[0]['start'],pending[-1]['end']
  chunks.append({'start':start,'end':end,'seconds':end-start,'speakers':sorted({r['speaker'] for r in words}),
    'utterances':len(words),'shortUtterances':sum(0<r['end']-r['start']<2 and bool(''.join(c for c in r['text'] if c.isalnum())) for r in words),
    'hasTaggedText':any('<' in r['text'] or '>' in r['text'] for r in words),
    'allContainedAnnotatedUtterancesComplete':True})
 for component in components:
  if component['end']-component['start']>35:
   emit();pending=[];oversized.append({'start':component['start'],'end':component['end']});continue
  if pending and component['end']-pending[0]['start']>35:emit();pending=[]
  pending.append(component)
  if pending[-1]['end']-pending[0]['start']>=25:emit();pending=[]
 emit()
 eligible=[chunk for chunk in chunks if 10<=chunk['seconds']<=35 and len(chunk['speakers'])>=2 and chunk['shortUtterances']>0 and not chunk['hasTaggedText']]
 results.append({'meeting':source['meeting'],'role':source['role'],'sourceFlacSha256':source['expectedWholeFileLfsSha256'],
  'referenceSha256':source['referenceSha256'],'audioSeconds':info.frames/info.samplerate,
  'nonemptyReferenceUtterances':len(rows),'cleanCompleteShortUtterances':len(short),
  'shortDurationBins':{'under0.3':sum(r['seconds']<.3 for r in short),
                      '0.3to1':sum(.3<=r['seconds']<1 for r in short),
                      '1to2':sum(1<=r['seconds']<2 for r in short)},
  'shortBySpeaker':dict(Counter(r['speaker'] for r in short)),
  'shortByLexicalLength':dict(Counter(r['lexicalCharacters'] for r in short)),
  'completeNaturalContextPlans':len(chunks),'eligibleMultiTurnShortResponseContextPlans':len(eligible),
  'oversizedOverlapComponentsNotCut':oversized,'eligibleContextPlans':eligible,
  'shortExamples':short})
old_report={'examples':len(old),'minAudioSeconds':min(r['audioSeconds'] for r in old),
 'shorterThan2sReferenceUtterances':sum(r['referenceEndSeconds']-r['referenceStartSeconds']<2 for r in old),
 'minimumLexicalCharacters':min(sum(c.isalnum() for c in r['text']) for r in old),
 'wholeNaturalMultiTurnContexts':0,'selectionSource':'Original preparation selects isolated complete non-overlap2–12s utterances,>=4lexical chars. Selected cohort actually has>=7chars.'}
omission=read(C/'d1d2-execution/asr-omission-audit-r1.json')
report={'state':'FROZEN_TRAINING_COHORT_OMITS_OBSERVED_SHORT_RESPONSE_AND_MULTI_TURN_CONDITIONS',
 'at':datetime.now().astimezone().isoformat(),'originalTraining':old_report,'sources':results,
 'existingExposedFailureForDiagnosisOnly':omission['groups']['<2s/006-M'],
 'newNeuralCalls':0,'newParameterUpdates':0,'newAudioExports':0,'qualityQualified':False,
 'fullMeetingGatesChanged':False,'finalHoldoutOpened':False,
 'interpretation':'The failed clean-utterance pilot did not cover the short backchannels or multi-turn windows prominent in the exposed failure. This is a training-coverage mismatch, not proof that a new cohort will improve the model. No further training should be launched until a source-disjoint, context-matched baseline demonstrates the target weakness.',
 'nextAction':'Prepare a single bounded context-matched validation cohort from these disjoint sources, preserving whole annotated utterances and all voices. Measure the existing base first; retain original long controls, background false-acceptance and bilingual controls. Freeze any subsequent data-only intervention before new updates; no hyperparameter sweep.',
 'limits':limits.query()}
(D/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':report['state'],'oldTraining':old_report,'sources':[{k:r[k] for k in ['meeting','role','cleanCompleteShortUtterances','eligibleMultiTurnShortResponseContextPlans','shortDurationBins']} for r in results]},ensure_ascii=False))
