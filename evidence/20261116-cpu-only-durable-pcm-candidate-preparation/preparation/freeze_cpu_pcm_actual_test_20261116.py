from pathlib import Path
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');BASE=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';C=BASE/'cpu-pcm-candidate-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
state=read(Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-fixed-whole-r2/inference-state.json'));items={r['id']:r for r in state['completed']}
p=C/'dualroute-protocol.json';P=read(p);assert 'actualTestScriptSha256' not in P
P['originalFullCandidateFirstTwoChunks']={c['meeting']:[items[c['meeting']+'-fixed30-'+str(i).zfill(4)] for i in range(2)] for c in P['cases']}
P['actualTestScriptSha256']=sha('work/run_cpu_pcm_dualroute_20261116.py')
p.write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'scriptSha256':P['actualTestScriptSha256'],'originalFullOutputControls':4,'newNeuralCalls':0}))
