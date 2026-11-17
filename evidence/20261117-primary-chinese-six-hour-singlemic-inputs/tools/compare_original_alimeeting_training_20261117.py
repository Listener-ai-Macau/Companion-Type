"""Pair one original public train TextGrid with raw, unaugmented conversion rows."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import csv,gzip,hashlib,json,re,sys,unicodedata
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';A=E/'alimeeting-intake-audit-r1'
meeting='R0003_M0046';source=O/'original-textgrids'/(meeting+'.TextGrid');target=O/'first-original-vs-converted.json';assert not target.exists()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
download=read(O/'first-original-textgrid-fetch-r3.json')
assert hashlib.sha256(source.read_bytes()).hexdigest()==download['sha256']
rows=read_reference_intervals(source)
def lexical(text):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC',text) if unicodedata.category(c)[0] in ('L','N'))
def speaker(tier):
    match=re.fullmatch(meeting+r'_[MF]_SPK(\d+)',tier);assert match,tier
    return match.group(1)
original=Counter();original_lex=Counter();empty=0;zero=[]
for r in rows:
    sid=speaker(r['speaker'])
    if not r['text']:empty+=1;continue
    if r['end']<=r['start']:zero.append((sid,r['start'],r['end']));continue
    key=(sid,round(r['start']*16000),round(r['end']*16000))
    original[key+(r['text'],)]+=1;original_lex[key+(lexical(r['text']),)]+=1
converted=Counter();converted_lex=Counter();cut_count=0
with gzip.open(A/'alimeeting-far_cuts_train.jsonl.gz','rt',encoding='utf-8') as stream:
    for line in stream:
        cut=json.loads(line);rec=cut['recording']
        if rec.get('transforms') or rec['id']!=meeting:continue
        cut_count+=1;assert len(cut['supervisions'])==1;s=cut['supervisions'][0]
        key=(s['speaker'],round((cut['start']+s['start'])*16000),round((cut['start']+s['start']+s['duration'])*16000))
        converted[key+(s['text'],)]+=1;converted_lex[key+(lexical(s['text']),)]+=1
near=list(csv.DictReader((O/'Train_Ali_near.csv').open(encoding='utf-8-sig')))
near_people={re.search(r'SPK(\d+)',r['Audio:FILE']).group(1) for r in near if Path(r['Audio:FILE']).name.startswith(meeting+'_')}
times=lambda counter:Counter({k[:3]:sum(v for key,v in counter.items() if key[:3]==k[:3]) for k in counter})
raw_missing=original-converted;raw_extra=converted-original
lex_missing=original_lex-converted_lex;lex_extra=converted_lex-original_lex
result={'at':datetime.now().astimezone().isoformat(),'state':'ORIGINAL_TRAIN_ANNOTATION_PAIRED_WITH_CONVERTED_ROWS',
    'meeting':meeting,'sourceSha256':download['sha256'],'originalTextgridNonemptyIntervals':sum(original.values()),
    'rawConvertedUnaugmentedCuts':cut_count,'emptyOriginalIntervals':empty,'zeroDurationNonemptyOriginalIntervals':zero,
    'originalSpeakerIds':sorted({k[0] for k in original}),'officialNearFileSpeakerIds':sorted(near_people),
    'allOriginalSpeakerIdsMatchOfficialNearFiles':{k[0] for k in original}==near_people,
    'allSourceFrameIntervalsMatch':times(original)==times(converted),
    'rawTextAndTimeMissing':sum(raw_missing.values()),'rawTextAndTimeExtra':sum(raw_extra.values()),
    'lexicalTextAndTimeMissing':sum(lex_missing.values()),'lexicalTextAndTimeExtra':sum(lex_extra.values()),
    'lexicalDiagnosticOnly':'NFKC/lowercase/Unicodeletters+numbers for mismatch diagnosis; no source/target/reference rewritten.',
    'rawMismatchExamplesWithoutText':[{'speaker':k[0],'startFrame':k[1],'endFrame':k[2],'textCharacters':len(k[3]),'copies':v} for k,v in list(raw_missing.items())[:3]],
    'trainingAudioStillNotFullyVerified':True,'evaluationReferenceRead':False,'neuralCalls':0,'parameterUpdates':0,
    'sourceOrTargetTextChanged':False,'qualityQualified':False,'limits':limits.query()}
atomic_json(target,result);print(json.dumps(result,ensure_ascii=False))
