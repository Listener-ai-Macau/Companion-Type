from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
BASE=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
C=BASE/'stagea-cpu-composition-r2';assert not C.exists();C.mkdir()
old=BASE/'stagea-cpu-composition-r1';B=read(old/'binding.json')
B.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(S/'cpu_window_joint_worker_20261116.py'),runnerSha256=sha(S/'run_cpu_window_joint_20261116.py'),
 previousAttempt={'control':str(old),'run':str(E/old.name),'reason':'Pinned Python Session has no was_truncated property. One inference returned but adapter failed before materialization was persisted. Correct pinned C API query; inputs/model/limits unchanged. No output quality result claimed.'})
for name in ['predicted-speaker-bindings.json','scoring-binding.json']:(C/name).write_bytes((old/name).read_bytes())
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];o.update(currentCpuWindowControl=str(C),currentCpuWindowRun=str(E/C.name),currentState='DAY_CPU_WINDOW_API_FIX_READY',activePid=None,noOwnNeuralProcessActive=True)
d['state']=o['currentState'];d['logResult']+='\n'+B['at']+' CPU短窗r1加载与首次计算完成后，适配代码错误读取不存在的Session.was_truncated属性，未形成落盘结果；保留失败，不计质量结果。按已固定C API查询截断状态，模型/32原输入/25%与2GiB保护均不改，r2执行。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'run':str(E/C.name)},ensure_ascii=False))
