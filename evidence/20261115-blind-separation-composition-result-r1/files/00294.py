from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';C=D/'blind-separation-composition-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
old=C/'asr-r1-launch-failure';before=(old/'blind_separation_worker_20261115.py').read_text(encoding='utf-8')
after=(S/'blind_separation_worker_20261115.py').read_text(encoding='utf-8')
assert before.replace('torch.set_num_threads(1);torch.set_num_interop_threads(1)',"torch.set_num_threads(1)\n        if a.phase!='asr':torch.set_num_interop_threads(1)")==after
assert (old/'protocol.json').read_bytes()==(C/'protocol.json').read_bytes()
assert read(old/'failure.json')['explicitNeuralCalls']==0
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
binding=read(C/'worker-binding.json');binding['workerSha256']=sha(S/'blind_separation_worker_20261115.py')
binding['scorerSha256']=sha(S/'score_blind_separation_composition_20261115.py');write(C/'worker-binding.json',binding)
receipt=dict(state='ASR_ONLY_THREAD_OWNERSHIP_FIX_NO_SEPARATOR_OR_MODEL_MATH_CHANGE',at=datetime.now().astimezone().isoformat(),
    run='E:/CodexData/Companion/product-d1d2-20261114/blind-separation-composition-r1/asr-r2',
    protocolSha256=sha(C/'protocol.json'),oldWorkerSha256=sha(old/'blind_separation_worker_20261115.py'),
    workerSha256=binding['workerSha256'],exactOnlySourceChangeVerified=True,
    controlAndSeparatorExecutedCodeSemanticallyUnchanged=True,
    change='NativeDecoder owns the one-time interop thread setter inASR phase. Separator phases still set it exactly once. Original decoder, CPU cap, memory guard, weights, inputs, CSS parameters and scoring unchanged.',
    previousFailureNeuralCalls=0,previousFailureModelLoadCompleted=False,
    separatorResultsReusedWithoutNeuralRerun=True,automaticRetries=0)
write(C/'asr-execution.json',receipt)
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    sourceCommit=read(D/'protection-r14.json')['modelCommit'],sourceRemoteVerified=True,
    blindSeparationComponentProtection=str(D/'protection-r14.json'),
    blindSeparationAsrExecution=str(C/'asr-execution.json'),blindSeparationAsrRun=receipt['run'])
v['logResult']+=' '+receipt['at']+' 分离代码/组件证明/32双路float输出45.377MB共147文件已私有逐字节保护，提交'+e['sourceCommit']+'，独立远端回读匹配。ASR首启动重复设置interop线程，NativeDecoder也设置同项，已在模型加载/0识别前停止；原源文件/绑定/协议/失败已保护。仅ASR分支由原NativeDecoder设置一次，分离分支执行代码等价且参数/协议/评分完全不变，精确文本差已核验；复用239前向产物，不重分离。新asr-r2独立命名，原失败保留，非参数/模型变体。'
write(p,v);print(json.dumps(receipt,ensure_ascii=False))
