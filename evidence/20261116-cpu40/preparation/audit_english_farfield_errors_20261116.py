"""Describe retained errors only: no rescoring gate change, denoise or new inference."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
import ctypes,hashlib,json,math,os,sys,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
from score_sequential_meetings_20261115 import tokens
from rapidfuzz.distance import Levenshtein
import numpy as np
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';C=B/'english-asr-specialist-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
reference={r['id']:r for r in read(D/'sequential-meeting-stageA-r2/scoring-only.json')}
qwen={r['id']:r for r in read(D/'sequential-meeting-stageA-r2/raw-text-baseline.json')['cases']}
moss={r['id']:r for r in read(B/'stagea-cpu-composition-r2/score.json')['cases']}
composed={r['id']:r for r in read(E/'stagea-cpu-composition-r2/composition-state.json')['completed']}
whisper=read(C/'score.json');rows=[];totals=defaultdict(Counter)
fillers={'um','uh','erm','er','hmm','mm','ah','eh','mhm','hm'}
for scored in whisper['cases']:
 case=reference[scored['id']];ref=tokens(case['rawReferenceText'],'English');persons=[]
 for event in case['referenceEvents']:persons.extend([(event['speaker'],t) for t in tokens(event['text'],'English')])
 assert [t for _,t in persons]==ref
 assert sha(case['wav'])==case['wavSha256']
 with wave.open(case['wav'],'rb') as w:pcm=w.readframes(case['frames'])
 assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256'];samples=np.frombuffer(pcm,dtype='<i2').astype(np.float64)/32768
 acoustic={}
 for speaker in sorted({p for p,_ in persons}):
  mask=np.zeros(len(samples),dtype=bool)
  for event in case['referenceEvents']:
   if event['speaker']!=speaker:continue
   first=max(0,int(event['start']*16000)-case['sourceStartFrame']);last=min(len(samples),math.ceil(event['end']*16000)-case['sourceStartFrame'])
   mask[first:last]=True
  energy=float(np.mean(samples[mask]**2)) if mask.any() else None
  acoustic[speaker]={'referenceUnits':sum(p==speaker for p,_ in persons),'wordIntervalSamples':int(mask.sum()),
   'pcmRmsDbfs':10*math.log10(energy) if energy and energy>0 else None}
 doc=read(composed[case['id']]['file']);hypotheses={'qwen':qwen[case['id']]['hypothesis'],'moss':' '.join(r['text'] for r in doc['rows']),'whisper':scored['hypothesis']}
 errors={}
 for model,hypothesis in hypotheses.items():
  hyp=tokens(hypothesis,'English');ops=Levenshtein.editops(ref,hyp);counts=Counter();people=defaultdict(Counter);details=[]
  expected=qwen[case['id']]['errors'] if model=='qwen' else moss[case['id']]['raw']['errors'] if model=='moss' else scored['errors']
  assert len(ops)==expected
  for op in ops:
   token=hyp[op.dest_pos] if op.tag=='insert' else ref[op.src_pos]
   category='filler' if token in fillers else 'digit' if any(c.isdigit() for c in token) else 'otherLexical'
   counts[op.tag]+=1;counts[category]+=1
   if op.tag!='insert':people[persons[op.src_pos][0]][op.tag]+=1
   details.append({'operation':op.tag,'token':token,'category':category,'referenceSpeaker':None if op.tag=='insert' else persons[op.src_pos][0]})
  counts.update(errors=len(ops),referenceUnits=len(ref));totals[model].update(counts)
  errors[model]={'hypothesis':hypothesis,'counts':dict(counts),'referenceSideErrorsBySpeaker':{k:dict(v) for k,v in people.items()},'operations':details}
 rows.append({'id':case['id'],'meeting':case['meeting'],'reference':case['rawReferenceText'],'speakers':acoustic,'models':errors})
result={'state':'ERROR_DIAGNOSTIC_ONLY_ORIGINAL_ALL_WORD_SCORES_UNCHANGED','at':datetime.now().astimezone().isoformat(),
 'totals':{k:dict(v) for k,v in totals.items()},'cases':rows,'newNeuralCalls':0,'weightsChanged':False,'qualityQualified':False,
 'notes':['All195/124/141 errors remain in original strict scores; filler/digit tags are descriptive only.',
  'Reference-side lexical edit attribution uses one Levenshtein alignment and is a diagnostic, not person-attributed WER or inferred speaker identity.',
  'PCM RMS on official word intervals is an acoustic level indicator, not measured SNR, microphone distance or proof of causality.',
  'These12 clips were annotation-selected nonoverlap development cases; no blind/generalization claim.'],
 'sources':{str(p):sha(p) for p in [C/'score.json',B/'stagea-cpu-composition-r2/score.json',D/'sequential-meeting-stageA-r2/raw-text-baseline.json',D/'sequential-meeting-stageA-r2/scoring-only.json']},'limits':limits.query()}
target=C/'retained-error-diagnostic.json';assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result['totals']))
