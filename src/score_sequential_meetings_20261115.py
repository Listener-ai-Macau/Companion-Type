"""Strict raw text scoring; training and development, languages kept separate."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,hashlib,json,re,unicodedata
from rapidfuzz.distance import Levenshtein
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def tokens(text,language):
 if language=='English':return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*",unicodedata.normalize('NFKC',text).lower().replace('\u2019',"'"))
 assert language=='Chinese'
 return list(''.join(c for c in re.sub(r'<[^>]*>','',text) if not c.isspace() and not unicodedata.category(c).startswith(('P','S'))).lower())
def measure(reference,hypothesis,language):
 ref,hyp=tokens(reference,language),tokens(hypothesis,language);ops=Levenshtein.editops(ref,hyp);counts=Counter(x.tag for x in ops)
 return {'errors':len(ops),'referenceUnits':len(ref),'hypothesisUnits':len(hyp),'rate':len(ops)/len(ref) if ref else None,
  'substitutions':counts['replace'],'deletions':counts['delete'],'insertions':counts['insert'],
  'editOperations':[{'operation':op.tag,'referenceIndex':op.src_pos,'hypothesisIndex':op.dest_pos,
    'reference':ref[max(0,op.src_pos-4):op.src_pos+5],'hypothesis':hyp[max(0,op.dest_pos-4):op.dest_pos+5]} for op in ops]}
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 protocol=read(a.control/'protocol.json');assert sha(a.control/'scoring-only.json')==protocol['scoringOnlyManifestSha256']
 state=read(a.run/'baseline-state.json');assert state['state']=='COMPLETE_STAGE_A_RAW_ASR_UNQUALIFIED'
 by_id={r['id']:r for r in state['completed']};rows=[];groups=defaultdict(list)
 for case in read(a.control/'scoring-only.json'):
  entry=by_id[case['id']];assert sha(entry['document'])==entry['documentSha256'] and entry['pcmSha256']==case['pcmSha256']
  doc=read(entry['document']);assert doc['isFinal'] and doc['confirmedAudioFrames']==case['frames']
  raw=read(entry['rawResult']);assert raw['inferenceBinding']['languagePolicy']==case['language']
  result=measure(case['rawReferenceText'],doc['text'],case['language'])
  row={'id':case['id'],'meeting':case['meeting'],'language':case['language'],'role':case['role'],
   'audioSeconds':case['audioSeconds'],'speakers':case['speakers'],'speakerReturn':case['speakerReturn'],
   'reference':case['rawReferenceText'],'hypothesis':doc['text'],**result,'reviewRequired':doc['reviewRequired']}
  rows.append(row);groups[(case['language'],case['role'])].append(row)
 totals=[]
 for (language,role),items in groups.items():
  units=sum(r['referenceUnits'] for r in items);errors=sum(r['errors'] for r in items)
  totals.append({'language':language,'role':role,'metric':'WER' if language=='English' else 'CER',
   'cases':len(items),'seconds':sum(r['audioSeconds'] for r in items),'errors':errors,'referenceUnits':units,
   'rate':errors/units,'rawTextGatePass':errors/units<.05,'speakerReturnCases':sum(r['speakerReturn'] for r in items),
   **{k:sum(r[k] for r in items) for k in ['substitutions','deletions','insertions']}})
 report={'state':'STAGE_A_RAW_TEXT_BASELINE_SCORED_NOT_PRODUCT_QUALIFIED','scorerSourceSha256':sha(__file__),'protocolSha256':sha(a.control/'protocol.json'),
  'sourceRun':str(a.run),'sourceStateSha256':sha(a.run/'baseline-state.json'),'groups':totals,'cases':rows,
  'normalization':'Existing strict Chinese lexical normalization / English NFKC lowercase lexical tokens; all fillers, partial words and numbers retained. No reference corrections or synonym/number rewriting.',
  'speakerAttributionEvaluated':False,'wholeMeetingAcceptance':False,'qualityQualified':False,'gatesChanged':False}
 target=a.control/'raw-text-baseline.json'
 with target.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({'state':report['state'],'groups':totals},ensure_ascii=False))
if __name__=='__main__':main()
