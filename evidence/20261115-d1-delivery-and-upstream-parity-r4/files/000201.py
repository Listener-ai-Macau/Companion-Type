"""Posthoc literal other-speaker evidence; no inference, text filtering or identity claim."""
from pathlib import Path
from datetime import datetime
import argparse,ast,difflib,hashlib,json,re,sys,unicodedata
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-paired-real-meeting'
sys.path.insert(0,str(R/'model-research/src'));sys.path.insert(0,'E:/CodexData/Companion/.build-cache/core-acceptance20261109/quality-deps')
from reference_textgrid_20261104 import read_reference_intervals
p=argparse.ArgumentParser();p.add_argument('--artifact',required=True);a=p.parse_args();root=Path(a.artifact)
module=ast.parse((R/'model-research/src/full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf8'));scope={'re':re,'unicodedata':unicodedata}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'frozen-normalizer','exec'),scope);normalize=scope['normalize']
refs=json.loads((C/'fixed-asr-scoring-only.json').read_text())['sourceReferences'];by={r['id']:[x for x in read_reference_intervals(r['reference']) if normalize(x['text'])] for r in refs};results=[]
for ident,own in by.items():
    doc=json.loads((root/(ident+'-output.json')).read_text(encoding='utf8'));examples=[];absent=0
    for u in doc['utterances']:
        start,end=u['startMs']/1000,u['endMs']/1000
        if any(x['start']<end+.1 and x['end']>start-.1 for x in own):continue
        absent+=1;hyp=normalize(u['text']);best=None
        for other,rows in by.items():
            if other==ident:continue
            for row in rows:
                if row['start']>=end+.1 or row['end']<=start-.1:continue
                text=normalize(row['text']);m=difflib.SequenceMatcher(None,hyp,text,autojunk=False).find_longest_match()
                if m.size>=12 and (best is None or m.size>best['literalCharacters']):
                    quote=hyp[m.a:m.a+m.size];assert quote==text[m.b:m.b+m.size]
                    best={'inputWindowStartSeconds':start,'inputWindowEndSeconds':end,'approximateInputWindowNotWordAlignment':True,'targetSource':ident,'otherSource':other,'literalCharacters':m.size,'normalizedLiteralQuote':quote,'reference':row,'modelWindowText':u['text']}
        if best:examples.append(best)
    results.append({'id':ident,'transcribedInputWindowsWithNoTargetReferenceSpeech':absent,'suchWindowsWithAtLeastTwelveLiteralOtherSpeakerCharacters':len(examples),'examples':sorted(examples,key=lambda x:x['inputWindowStartSeconds'])[:4]})
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'POSTHOC_LITERAL_OTHER_SPEAKER_CONTAMINATION_DOCUMENTED','results':results,'minimumLiteralCharacters':12,'annotationWindowToleranceSeconds':.1,'protocolType':'posthoc diagnostic examples; not preregistered acceptance or exhaustive insertion accounting','limits':['Input windows have approximate times; this is not verified word-level attribution.','Literal overlap with other speakers supports real crosstalk for these examples, not every insertion.','Headset channels are not isolated target truth; original words/output remain untouched.'],'modelOrCloudCalls':0,'productChanged':False,'speakerQualityQualified':False}
(C/'product-five-source-ci/crosstalk-audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'state':record['state'],'counts':[{k:v for k,v in r.items() if k!='examples'} for r in results]},ensure_ascii=False))
