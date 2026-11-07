"""Exited full-text error inventory, never a reference-conditioned inference input."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,re
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from full_meeting_transcript_metrics_20261103 import normalize,Levenshtein

p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--meeting',required=True);p.add_argument('--output',required=True);a=p.parse_args()
C=Path(a.control);out=C/'transcripts'/a.meeting;read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();assert not pressure.low()
state=read(out/'completed-state.json');quality=read(out/'quality-review.json')
assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED' and state['finishedAt']
assert sha(out/'model-output.json')==state['modelOutputSha256'] and sha(out/'attribution-review.json')==state['attributionReviewSha256']
case=next(c for c in read(C/'scoring-only.json') if c['meeting']==a.meeting)
assert sha(case['reference'])==case['referenceSha256'] and case['audioSha256']==state['audioSha256']
reference=sorted(read_reference_intervals(case['reference']),key=lambda r:(r['start'],r['end']))
ref='';ref_rows=[]
for row in reference:
    text=normalize(row['text']);ref+=text;ref_rows.extend([row]*len(text))
raw=[read(out/'windows'/('%06d.raw.json'%i))['raw'] for i in range(state['totalWindows'])]
hyp='';hyp_rows=[]
for row in raw:
    text=normalize(row['text']);hyp+=text;hyp_rows.extend([row]*len(text))
assert hyp==normalize(read(out/'attribution-review.json')['rawWindowText'])
ops=Levenshtein.editops(ref,hyp);assert len(ops)/len(ref)==quality['chronologicalTextDiagnostic']['cer']
groups=[]
for op in ops:
    if groups and op.src_pos<=groups[-1]['lastRef']+2 and op.dest_pos<=groups[-1]['lastHyp']+2:
        group=groups[-1]
    else:
        group={'firstRef':op.src_pos,'firstHyp':op.dest_pos,'operations':[]};groups.append(group)
    group.update(lastRef=op.src_pos,lastHyp=op.dest_pos)
    group['operations'].append({'tag':op.tag,'referenceCharacter':ref[op.src_pos:op.src_pos+1] if op.tag!='insert' else '',
      'hypothesisCharacter':hyp[op.dest_pos:op.dest_pos+1] if op.tag!='delete' else ''})
for group in groups:
    lo,hi=group['firstRef'],group['lastRef']+1;hl,hh=group['firstHyp'],group['lastHyp']+1
    group['referenceContext']=ref[max(0,lo-10):hi+10];group['hypothesisContext']=hyp[max(0,hl-10):hh+10]
    rr=ref_rows[min(lo,len(ref_rows)-1)];hr=hyp_rows[min(hl,len(hyp_rows)-1)]
    group['referenceUtterance']={k:rr[k] for k in ['start','end','speaker','text']}
    group['hypothesisWindow']={k:hr[k] for k in ['index','startSample','endSample','text']}
    affected=''.join(v['referenceCharacter']+v['hypothesisCharacter'] for v in group['operations'])
    # These are inspection tags, never verified causes or corrected words.
    group['inspectionTags']=[tag for tag,pattern in [('number_or_unit',r'[0-9零〇一二两三四五六七八九十百千万亿块元角毛点分%]'),('filler',r'[嗯呃啊哎唉]'),('negation',r'[不没无未别]'),('er_suffix',r'儿')] if re.search(pattern,affected)] or ['other_lexical']
    group['editCount']=len(group['operations']);group['verifiedByListening']=False
assert sum(g['editCount'] for g in groups)==len(ops)
counts={tag:sum(g['editCount'] for g in groups if tag in g['inspectionTags']) for tag in ['number_or_unit','filler','negation','er_suffix','other_lexical']}
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'COMPLETE_EXISTING_FULL_TEXT_ERROR_INVENTORY_NO_NEW_INFERENCE',
  'meeting':a.meeting,'referenceParser':PARSER_ID,'audioSha256':case['audioSha256'],'referenceSha256':case['referenceSha256'],
  'modelOutputSha256':state['modelOutputSha256'],'referenceCharacters':len(ref),'hypothesisCharacters':len(hyp),'strictEdits':len(ops),
  'strictCerUnchanged':len(ops)/len(ref),'editsByInspectionTag':counts,'inspectionTagsMayOverlap':True,
  'tagsAreCauses':False,'newNeuralInference':0,'rawTextOrScoringChanged':False,'referenceNeverReturnedToInference':True,
  'groups':groups,'qualified':False,'scope':'Complete exposed meeting. Global textual alignment is for error inspection; reference utterance times are not proven word alignment. Numeric inspection tags do not mean harmless formatting. No filler deletion or numeric rewrite affects CER.'}
atomic_json(Path(a.output),result);pressure.close()
print(json.dumps({k:result[k] for k in ['meeting','referenceCharacters','strictEdits','strictCerUnchanged','editsByInspectionTag']},ensure_ascii=False))
print(json.dumps(sorted(groups,key=lambda g:-g['editCount'])[:12],ensure_ascii=False))
