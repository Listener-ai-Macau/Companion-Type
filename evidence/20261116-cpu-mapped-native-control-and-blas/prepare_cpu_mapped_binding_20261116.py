from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,argparse
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
p=argparse.ArgumentParser();p.add_argument('--attempt',type=int,default=1);args=p.parse_args();assert args.attempt in [1,2]
name='cpu-mapped-r'+str(args.attempt)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');C=BASE/name
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not (E/name).exists();C.mkdir()
B=read(BASE/'staged-r6/staged-binding.json')
prefix=E/'staged-r6/ES2003b-partial-ids.json';ids=read(prefix)['generatedIds'];assert len(ids)==6501
B.update(at=datetime.now().astimezone().isoformat(),workerPython=B['gpuPython'],executionDevice='cpu',
 workerSha256=sha(S/'moss_cpu_mapped_meeting_worker_20261116.py'),runnerSha256=sha(S/'run_moss_cpu_mapped_meetings_20261116.py'),
 decodeStepPauseSeconds=0.,synchronizeEachDecodeForward=False,decodeReleaseUnusedInterval=0,
 change='Owner confirmed the6800XT was unplugged/powered off. Native CPU continuation maps the unchanged checkpoint read-only, and full BF16 KV into shared real-file mappings instead of private heap. No weights/dtype/context/word/reference/quality-gate or resource-cap change. Actual mapped working RAM remains separately guarded. Reuse original27924 prompt KV, retain/replay6501 own generated IDs. Mandatory original61s16-token cross-device control before whole continuation.',
 oldResults='r6 unusedGPUcache release controlled the observed15GiB residency growth, sustained about1.9tokens/s beyond former slowdown, preserved6501IDs. Device removal at08:12 then surfaced as HIP C++ abort; Windows/Vulkan both saw no6800XT and Owner confirmed unplug/poweroff. Do not classify that exit as a spontaneous model stability failure or reassign the earlier00:16 bugcheck cause. CPU execution has not yet passed the new control or whole meeting.')
B['cases'][0].pop('releaseUnusedInterval',None)
B['cases'][1]['resumeGeneratedPrefix']={'file':str(prefix),'sha256':sha(prefix),'tokens':len(ids)}
B['helpers'][str(S/'moss_native_greedy_20261115.py')]=sha(S/'moss_native_greedy_20261115.py')
B['helpers'][str(S/'moss_cpu_mapped_runtime_20261116.py')]=sha(S/'moss_cpu_mapped_runtime_20261116.py')
B['cpuFileMapping']={'weights':'mmap.ACCESS_READ, all exact original BF16 tensor views, no copy-on-write commit',
 'kv':'mmap.ACCESS_WRITE on real E-drive files, full capacity and every used cell retained',
 'privateCommitNotEqualMappedWorkingRam':True,'actualWindowsLowMemoryStop':True,'threads':1,'mappedDiskEstimateGiB':65}
if args.attempt==2:
 assert read(E/'cpu-mapped-r1/run.json')['finishedAt']
 B['priorCpuFailure']='r1 loaded all683 exact read-only mapped tensors successfully, then OpenBLAS default runtime threads caused repeated allocation failure before any generated token. Environment thread limits alone were insufficient. Restore the already verified process-private rocm-openblas16to1 runtime pin; same2GiB guard, no same-condition retry.'
 B['change']+=' Restore existing verified runtime BLAS thread pin in CPU process; pin is CPU-library configuration and performs no GPU inference.'
for f,h in B['helpers'].items():assert sha(f)==h,f
assert psutil.disk_usage('E:/').free>100*1024**3
(C/'staged-binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115']
o['ownerGpuDisconnectedReply20261116']={'at':B['at'],'quote':'已经拔下或断电','appliesTo':'08:12 device removal/process exit, not earlier00:16 system bugcheck'}
d['state']='DAY_CPU_MAPPED_CONTINUATION_PREPARING_OWNER_CONFIRMED_GPU_UNPLUGGED'
o.update(currentState=d['state'],currentStagedControl=str(C),currentStagedRun=str(E/name),activePid=None,
 currentExecutionDevice='cpu',retainedRealGeneratedPrefixTokens=len(ids),noOwnNeuralProcessActive=True)
d['next']='继续至16:00：Owner确认6800XT已拔下/断电，08:12按设备移除退出记录，不算模型自发故障。先原61s16token CPU严格控制，再以只读映射原BF16权重、共享文件映射完整KV从6501原ID/27924原输入缓存继续原会及同4会冻结评分。CPU5%/私有2GiB不动，映射工作集实际占RAM另监控真实低RAM；15:40推理截止。无量化/新训练/原字门变更/驱动重启。更早00:16错误根因保持未知。'
d['jointArchitecture20261115'].update(state=d['state'],nextExecutableGate=d['next'])
d['logResult']+='\n'+B['at']+' Owner确认原话：已经拔下或断电。08:12后Windows6800XT Disconnected和Vulkan仅780M与该实际动作对应，本次退出不按模型自发故障计；先前00:16系统错误不追改。当前无自有神经进程。为继续16:00任务，准备CPU原生文件映射部署：权重只读真实文件映射避免Windows写时复制全视图提交，KV用真实E盘共享映射保留全部原精度/全上下文，不放宽私有2GiB/CPU5%门，实际映射RAM仍受低RAM停止。先原61s16token跨设备控制，后完整原会，不新增量化或训练。'
if args.attempt==2:d['logResult']+='\n'+B['at']+' CPU r1已在2.415秒完成683原权重只读映射，但首个控制生成前OpenBLAS分配失败/exit1，未产生token。CPU版遗漏GPU版既有runtime BLAS线程钉住，环境变量未足够限制其原生线程；补回已验同DLL SHA/16→1调用，只作用本进程，不提高2GiB门。失败保留，不算模型效果结果。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'run':str(E/name),'resumeTokens':len(ids),'device':'cpu'},ensure_ascii=False))
