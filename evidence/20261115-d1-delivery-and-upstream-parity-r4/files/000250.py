from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,re,tempfile
import psutil
psutil.Process().cpu_affinity([10]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID

parser=argparse.ArgumentParser()
parser.add_argument('--control-root',required=True)
parser.add_argument('--cases',required=True)
args=parser.parse_args()
root=Path(args.control_root)
cases=json.loads(Path(args.cases).read_text(encoding='utf8'))
normalize=lambda t:''.join(re.sub(r'<[^>]*>','',t).split())
audit=[]
for case in cases:
    p=Path(case['reference']);assert hashlib.sha256(p.read_bytes()).hexdigest()==case['referenceSha256']
    new=read_reference_intervals(p);old=[]
    for block in re.split(r'^\s*item \[\d+\]:\s*$',p.read_text(encoding='utf-8-sig'),flags=re.M)[1:]:
        name=re.search(r'^\s*name\s*=\s*"([^"]+)"',block,re.M)
        if not name:continue
        for start,end,text in re.findall(r'intervals\s*\[\d+\]:\s*xmin\s*=\s*([\d.]+)\s*xmax\s*=\s*([\d.]+)\s*text\s*=\s*"([^\r\n]*)"',block):
            old.append({'start':float(start),'end':float(end),'speaker':name[1],'text':text})
    identity=lambda r:(r['start'],r['end'],r['speaker'],normalize(r['text']))
    old_keys={identity(r) for r in old}
    recovered=[r for r in new if identity(r) not in old_keys]
    new_keys={identity(r) for r in new}
    assert all(identity(r) in new_keys for r in old),'New reader must retain all old recognized content'
    if case['meeting']=='20200708_L_R002S01C01':
        assert any(r['speaker']=='003-M' and '零二二我是教务处' in r['text'] for r in recovered)
        assert any(r['speaker']=='007-F' and '零幺四' in r['text'] for r in recovered)
    audit.append({'meeting':case['meeting'],'referenceSha256':case['referenceSha256'],'oldIntervals':len(old),'newIntervals':len(new),
      'recoveredIntervals':recovered,'prefixOldLexicalSpeakers':len({r['speaker'] for r in old if r['start']<120 and normalize(r['text'])}),
      'prefixNewLexicalSpeakers':len({r['speaker'] for r in new if r['start']<120 and normalize(r['text'])}),
      'affected':bool(recovered)})
# A regression fixture with a label that contains an actual newline and escaped
# quotes, plus an empty interval. These must not silently disappear.
fixture='''File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0
xmax = 3
tiers? <exists>
size = 1
item []:
    item [1]:
        class = "IntervalTier"
        name = "speaker"
        xmin = 0
        xmax = 3
        intervals: size = 2
        intervals [1]:
            xmin = 0
            xmax = 2
            text = "第一行
第二行说""你好"""
        intervals [2]:
            xmin = 2
            xmax = 3
            text = ""
'''
with tempfile.TemporaryDirectory(prefix='textgrid-r6-',dir=root) as temp:
    path=Path(temp)/'regression.TextGrid';path.write_text(fixture,encoding='utf8')
    rows=read_reference_intervals(path)
    assert len(rows)==2 and rows[0]['text']=='第一行\n第二行说"你好"' and rows[1]['text']==''
    assert rows[0]['start']==0 and rows[0]['end']==2
    path.write_text(fixture.replace('intervals: size = 2','intervals: size = 3'),encoding='utf8')
    try:read_reference_intervals(path)
    except AssertionError:pass
    else:raise AssertionError('Malformed counts must fail instead of omitting text')
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'REFERENCE_PARSER_SOURCE_FIX_VERIFIED',
 'parser':PARSER_ID,'corpusAudit':audit,'multilineEscapedQuoteAndEmptyRegressionPassed':True,'declaredCountMismatchRejected':True,
 'sourceReferencesModified':False,'modelInferenceRepeated':False,'oldScoresRetainedButAffectedReportsNotForDirectionDecisions':True}
target=root/'reference-parser-audit-restored-20261105.json';assert not target.exists();target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'state':report['state'],'parser':PARSER_ID,'cases':[{k:v for k,v in x.items() if k!='recoveredIntervals'} for x in audit]},ensure_ascii=False))
