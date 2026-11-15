from pathlib import Path
from datetime import datetime
import hashlib,json,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'joint-architecture-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
base=read(D/'official-native-parity-r1/audio-only.json')
zh=[r for r in base if r['meeting'] in ['S_R004S03C01','20200623_S_R001S07C01']]
en1={'meeting':'ES2003b','audio':'E:/CodexData/Companion/product-d1d2-20261114/ordinary-english-r1/ES2003b.Array1-01.wav'}
en2=read(D/'reference-annotation-audit-en2002a-r1/original-case.json')
sources=[en1,zh[0],en2,zh[1]];cases=[]
for source in sources:
 digest=sha(source['audio'])
 if source.get('audioSha256'):assert digest==source['audioSha256']
 with wave.open(source['audio'],'rb') as wav:
  assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000);frames=wav.getnframes()
 cases.append({'meeting':source['meeting'],'audio':source['audio'],'audioSha256':digest,'audioSeconds':frames/16000,'frames':frames})
assert len(cases)==4;write(C/'full-audio-only.json',cases)
helpers=read(C/'pilot-binding.json')['helpers']
for name in ['moss_native_full_execution_20261115.py','moss_amd_execution_20261104.py','moss_key_streamed_attention_20261104.py']:
 helpers[str(S/name)]=sha(S/name)
old=read(C/'pilot-binding.json')
write(C/'full-binding.json',{'at':datetime.now().astimezone().isoformat(),'workerSha256':sha(S/'moss_native_full_worker_20261115.py'),
 'runnerSha256':sha(S/'run_moss_native_full_20261115.py'),'audioManifestSha256':sha(C/'full-audio-only.json'),
 'helpers':helpers,'blas':old['blas'],'blasSha256':old['blasSha256'],
 'reason':'Whole-session quality comparison, fixed4 complete original recordings. Baseline results reused, not re-run or trained. Bounded native math SDPA/independent acoustic-window execution needs separate GPU mathematical and full request frontend controls before large inference.',
 'qualityQualified':False,'originalGatesChanged':False,'finalHoldoutOpened':False})
print(json.dumps({'wholeMeetings':len(cases),'minutes':sum(r['audioSeconds'] for r in cases)/60,'order':[r['meeting'] for r in cases]},ensure_ascii=False))
