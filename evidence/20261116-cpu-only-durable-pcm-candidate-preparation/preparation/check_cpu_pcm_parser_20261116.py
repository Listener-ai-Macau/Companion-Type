from pathlib import Path
import hashlib,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S));sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from companion_moss_raw_output_20261116 import parse_native
from score_joint_whole_meetings_20261115 import parse_native as frozen
R=S.parent.parent;BASE=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';C=BASE/'cpu-pcm-candidate-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/stagea-cpu-composition-r2')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
cases=[]
for item in read(E/'inference-state.json')['completed']:
 assert sha(item['file'])==item['sha256'];raw=read(item['file'])['rawDecoded'];assert parse_native(raw)==frozen(raw)
 cases.append({'id':item['id'],'rawSha256':item['sha256']})
assert len(cases)==32
receipt={'state':'PASS_EXACT_FROZEN_NATIVE_PARSE_ON_ALL32_REAL_OUTPUTS','cases':cases,'newParserSha256':sha(S/'companion_moss_raw_output_20261116.py'),
 'frozenScorerSha256':sha(S/'score_joint_whole_meetings_20261115.py'),'newNeuralCalls':0,'qualityQualified':False,'sourceWordsRewritten':False}
(C/'parser-control.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
B=read(C/'binding.json');assert B['workerSha256']==sha(C/'worker-before-minimal-parser.py')
B['workerSha256']=sha(S/'companion_local_moss_cpu_worker_20261116.py');B['helpers'].pop(str(S/'score_joint_whole_meetings_20261115.py'))
B['helpers'][str(S/'companion_moss_raw_output_20261116.py')]=sha(S/'companion_moss_raw_output_20261116.py')
B['preparationCorrection']='Remove scoring/scipy imports from the candidate inference consumer. Lightweight parser exactly matched the frozen scorer on all32 actual outputs; no neural/model/output-policy change.'
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':receipt['state'],'source':receipt['newParserSha256'],'newNeuralCalls':0}))
