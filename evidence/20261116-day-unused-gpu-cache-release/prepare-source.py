"""Continue the same complete recording after observed real GPU residency pressure."""
from pathlib import Path
from datetime import datetime
import json,hashlib,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');C=BASE/'staged-r6'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not (E/'staged-r6').exists();C.mkdir()
old=read(E/'staged-r5/run.json');assert old['finishedAt'] and not psutil.pid_exists(old['pid'])
B=read(BASE/'staged-r5/staged-binding.json');prefix=E/'staged-r5/ES2003b-partial-ids.json';ids=read(prefix)['generatedIds'];assert len(ids)==5181
B.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(S/'moss_staged_meeting_worker_20261115.py'),
 decodeReleaseUnusedInterval=64,
 change='Release only unreferenced PyTorch GPU allocator blocks after exact retained-prefix replay and every64 decoder forwards, retaining all live full-context BF16 KV and raw generated IDs. Record allocated/reserved before and after each release. Real native16-token control exercises release EVERY forward. No attention math/dtype/word/label/driver/OS/resource-cap change.',
 oldResults='Post-reboot staged-r5 native16 control passed and ES continued4064to5181 IDs. Throughput initially about1.9newtokens/s then about0.18 while own GPU dedicated15.00GiB and adapter15.69GiB/physical16GiB, family private1.13GiB. Read-only PDH captured other apps dedicated onlyabout1GiB and3D40%; no new GPU/runtime/system error. Voluntary owned stop retained evidence. GPU cached allocation/residency pressure is now a discriminable explanation; CPU-RAM or a proved32k attention cutoff is not established. This allocator release is distinct from changing model or retrying a prior fatal path.')
B['helpers'][str(S/'moss_native_greedy_20261115.py')]=sha(S/'moss_native_greedy_20261115.py')
B['cases'][0]['releaseUnusedInterval']=1
B['cases'][1]['resumeGeneratedPrefix']={'file':str(prefix),'sha256':sha(prefix),'tokens':len(ids)}
B['priorPressureEvidence']={'memory':str(E/'staged-r5/owned-gpu-memory-samples.jsonl'),'engines':str(E/'staged-r5/owned-gpu-counter-samples.jsonl'),
 'timing':str(E/'staged-r5/observation-only.jsonl'),'stopRequest':str(E/'staged-r5/stop.request'),'crashCauseStillNotProven':True,
 'originalPrefillReencoded':False,'priorGeneratedIdsPreserved':True}
for f,h in B['helpers'].items():assert sha(f)==h,f
(C/'staged-binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);d['state']='DAY_GPU_RESIDENCY_PRESSURE_IDENTIFIED_UNUSED_CACHE_RELEASE_CONTROL_PENDING'
o=d['ownerOvernightRun20261115'];o.update(currentState=d['state'],currentStagedControl=str(C),currentStagedRun=str(E/'staged-r6'),retainedRealGeneratedPrefixTokens=len(ids),activePid=None,
 gpuResidencyPressureEvidence=B['priorPressureEvidence'],actualSystemRebootAfterDayResume=False)
d['next']='继续至16:00：实际发现自有GPU专用15.00GiB/全卡15.69GiB时原解码由约1.9降0.18token/s，正常保留5181原ID退出。新增只释放未引用GPU缓存、每64forward及前缀回放后执行，原61s16token控制每步实际释放；通过才从5181原ID/原完整缓存继续同4整会并冻结CPU评分。不得据此声称0x101根因已解决；无新内核/系统异常，原CPU5%/族2GiB/低RAM/15:40截止/质量门不动。'
d['jointArchitecture20261115'].update(state=d['state'],nextExecutableGate=d['next'])
d['logResult']+='\n'+B['at']+' 下午续作r5短控制通过，ES从4064续至5181原ID；实际斜率约1.9→0.18token/s。PDH自有GPU专用15.0039GiB、全卡15.6901GiB、其它程序专用约0.9935GiB，非族私有1.13GiB触门；自有计算引擎约88%，另有3D合计40%，不能只凭此断言32k算法阈值或0x101根因。07:54正常自有stop退出，无新kernel/系统异常。下一唯一因果变化为释放未引用GPU分配块并记录allocated/reserved，原61s16token每步释放严格控制，再保留5181全部原ID续写；原音/字门/权重/参考/资源保护不动。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'run':str(E/'staged-r6'),'retainedTokens':len(ids)},ensure_ascii=False))
