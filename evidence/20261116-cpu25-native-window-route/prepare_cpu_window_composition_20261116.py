from pathlib import Path
from datetime import datetime
import json,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
C=BASE/'stagea-cpu-composition-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/stagea-cpu-composition-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not E.exists();C.mkdir()
old=D/'sequential-meeting-stageA-r2';protocol=read(old/'protocol.json');audio=read(old/'audio-only.json');gold=read(old/'scoring-only.json')
assert sha(old/'audio-only.json')==protocol['audioOnlyManifestSha256'] and sha(old/'scoring-only.json')==protocol['scoringOnlyManifestSha256']
meta={r['id']:r for r in gold};groups={key:[r for r in audio if meta[r['id']]['role']==role and r['language']==lang] for key,role,lang in [('en','validation','English'),('zh','validation','Chinese'),('train','train','Chinese')]}
cases=[r for i in range(12) for r in [groups['en'][i],groups['zh'][i]]]+groups['train'];assert len(cases)==32 and len({r['id'] for r in cases})==32
for r in cases:assert sha(r['wav'])==r['wavSha256']
prior=read(BASE/'cpu-mapped-r4/staged-binding.json')
B={'at':datetime.now().astimezone().isoformat(),'workerPython':'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',
 'workerSha256':sha(S/'cpu_window_joint_worker_20261116.py'),'runnerSha256':sha(S/'run_cpu_window_joint_20261116.py'),
 'cppControl':str(BASE/'cpp-r1'),'neuralDeadline':prior['neuralDeadline'],'reportDeadline':prior['reportDeadline'],
 'ownerCpuBudgetPermission':prior['ownerCpuBudgetPermission'],'cpuPercent':25,'computeThreads':4,'privateBytes':2147483648,
 'cases':cases,'helpers':{str(S/n):sha(S/n) for n in ['moss_windows_resource_limits_20261104.py','practical_io_20261107.py']},
 'scope':'Exact prior32 natural non-overlap multi-speaker windows, validation balanced before training-role diagnostic; not complete meeting or blind final acceptance.',
 'modelCandidate':'Unchanged pinned MOSS BF16 GGUF, explicit CPU/mmap, f16 native KV as pinned C++ port; no quantization or new weights.',
 'compositionFrozenBeforeOutputs':'MOSS raw words and segment times; infer native local Sxx-to-global Nemotron IDs by maximum overlap against the unchanged predicted full-source exclusive journal. No reference labels/counts/text used; unmatched/residual words remain UNKNOWN. Scoring uses the already frozen whole-meeting Nemotron-to-reference mapping, no per-window reference remapping.',
 'productDefaultChanged':False,'newTraining':False,'qualityQualified':False,'wholeMeetingAcceptance':False}
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
speaker=read(old/'speaker-baseline.json');bindings={r['meeting']:r['probabilities'] for r in speaker['meetingIdentities']}
(C/'predicted-speaker-bindings.json').write_text(json.dumps({'source':str(old/'speaker-baseline.json'),'sourceSha256':sha(old/'speaker-baseline.json'),'probabilitiesOnly':bindings,'noGoldLabelMappingInThisFile':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(C/'scoring-binding.json').write_text(json.dumps({'sourceControl':str(old),'audioManifestSha256':sha(old/'audio-only.json'),'scoringManifestSha256':sha(old/'scoring-only.json'),'rawBaselineSha256':sha(old/'raw-text-baseline.json'),'speakerBaselineSha256':sha(old/'speaker-baseline.json'),'composition':B['compositionFrozenBeforeOutputs'],'qualityQualified':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];d['state']='DAY_CPU_WINDOW_COMPOSITION_FROZEN_NATIVE_CANDIDATE_PENDING'
o.update(currentState=d['state'],activePid=None,noOwnNeuralProcessActive=True,currentCpuWindowControl=str(C),currentCpuWindowRun=str(E),
 wholeMeetingResumeStillPending=True,wholeMeetingRetainedOriginalTokens=6501)
d['next']='16:00目标保持：无独显默认产品不采用大整会KV常驻。Owner授权CPU25%/4线程下原16token控制通过，但整会映射真实RAM吃紧且前缀仍慢；已保存6501原ID/完整缓存及CPU失败，原4整会不取消。当前执行已冻结32原多人不重叠窗口（英文/中文验证交替，再8训练角色诊断）：原MOSS BF16 GGUF在CPU C++/mmap短窗识别，配原整会Nemotron预测身份，词/数字/口头词全保留。按原参考/固定全会身份映射独立评分，短窗不代整会或售卖。无新训练/默认替换，2GiB私有与低RAM保护不变。'
d['jointArchitecture20261115']['nextExecutableGate']=d['next']
d['logResult']+='\n'+B['at']+' 无独显产品条件继续收敛：25%/4计算线程原16token严格通过，CPU长整会KV恢复期间真实可用RAM曾约4.03GiB，不能用低私有占用冒充低实际RAM；9:42仅回放128/6501，正常自有stop保留，四整会仍未完成。转为冻结CPU组合候选：同原32自然多人不重叠窗口、验证中英交替/8训练诊断后置；严格CPU C++只读mmap原BF16权重+短窗native KV，配原全会Nemotron预测身份，规则在输出前冻结，无GT输入/每窗GT重映射/删词/新权重。此为同一模型目标的可执行A阶段，不取消原整会依赖和门槛。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'run':str(E),'cases':len(cases),'firstTwo':[r['id'] for r in cases[:2]]},ensure_ascii=False))
