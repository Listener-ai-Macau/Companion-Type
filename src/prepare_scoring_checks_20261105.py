from pathlib import Path
import ast,json
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=r/'docs/handoffs/20261105-model-resume';q=r/'model-research/src'
source=Path('work/check_reference_textgrid_20261104.py').read_text(encoding='utf8')
source=source.replace('import hashlib,json,re,tempfile','import argparse,hashlib,json,re,tempfile')
old="root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')\ncases=json.loads((root/'frozen-scoring-only.json').read_text(encoding='utf8'))"
new="""parser=argparse.ArgumentParser()
parser.add_argument('--control-root',required=True)
parser.add_argument('--cases',required=True)
args=parser.parse_args()
root=Path(args.control_root)
cases=json.loads(Path(args.cases).read_text(encoding='utf8'))"""
assert source.count(old)==1
source=source.replace(old,new).replace("target=root/'reference-parser-audit-r6.json'","target=root/'reference-parser-audit-restored-20261105.json'")
ast.parse(source);(q/'check_reference_textgrid_restored_20261105.py').write_text(source,encoding='utf8')
cases=json.loads((m/'public-audio-restore-r5.json').read_text(encoding='utf8'))['cases']
(m/'restored-references-scoring-only.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Reference parser regression checker prepared for two restored development references only.')
