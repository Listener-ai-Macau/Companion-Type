"""Merge the observed second reboot into the original Companion workpoint."""
from pathlib import Path
from datetime import datetime
import hashlib
import json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
scene=E/'system-restart-20261116-2315'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
at=datetime.now().astimezone().isoformat(timespec='seconds')
sources=['durable_model_state_20261117.py','tdt_adaptation_checkpoint_20261116.py','tdt_domain_adaptation_20261116.py']
for name in sources:compile((S/name).read_bytes(),str(S/name),'exec')
proof=read(scene/'journal-verification-r2/result.json')
assert proof['sourceSha256']==digest(S/sources[0])
for name in sources[1:]:
    assert 'from durable_model_state_20261117 import atomic_json' in (S/name).read_text(encoding='utf-8')
integration={'at':at,'state':'CPU_VERIFIED_DURABLE_JOURNAL_IN_UNEXECUTED_TDT_SOURCE_GPU_CAUSE_UNFIXED',
    'sourceSha256':{n:digest(S/n) for n in sources},'corruptStateSimulation':proof,
    'integratedIntoUnexecutedTdtWorkerAndCheckpoint':True,'oldFrozenMossWorkerModified':False,
    'gpuOrTrainingExecutedByVerification':False,'actualPowerLossTested':False,
    'tdtWorkerGpuPreflightAndResumeReviewPending':True}
target=J/'gpu-compatibility-r1/journal-integration-20261117.json'
target.write_text(json.dumps(integration,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
chronology=read(scene/'recent-chronology.json')
topology=read(scene/'egpu-topology.json')
analysis={'at':at,'state':'OWNED_GPU_WORKLOAD_LEADING_TRIGGER_ROOT_CAUSE_NOT_IDENTIFIED',
    'ownerQuote':'通常这个重启现象只发现在我接显卡坞的时候。然后不知道为什么。已经连续几天发生这个现象了。以前好像都不会有这种现象。',
    'incident':str(J/'gpu-compatibility-r1/second-restart-20261117.json'),
    'runtimeDirectoryTimestamps':chronology['runtimeDirectoryTimestamps'],
    'recentRestartEvents':chronology['events'],
    'timestampAssociationIsNotCausation':True,
    'gpuParentBridges':[{'name':p['Name'],'id':p['InstanceId']} for p in topology['Parents'][:6]],
    'connectionTypeAwaitingOwnerAnswer':True,
    'unresolved':['compute runtime/driver interaction','external PCIe bridge/link','power','thermal'],
    'newMatchedBugcheckOrDump':False,'vramOrRamExhaustionSupportedBySamples':False,
    'pastMIOpenBypassDidNotEstablishLongRunStability':True,
    'relatedUpstreamSources':[
        {'url':'https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/event-id-41-restart','scope':'Event41 alone does not establish a cause'},
        {'url':'https://github.com/ROCm/TheRock/blob/main/SUPPORTED_GPUS.md','scope':'Development support status is not qualification of this exact driver/eGPU stack'},
        {'url':'https://github.com/ROCm/TheRock/issues/9475','scope':'Related Windows RX6800 hostcall issue; our workload is not shown to use the trigger, not a matched diagnosis'},
        {'url':'https://github.com/ROCm/TheRock/issues/9306','scope':'Different Linux dual-V620 compute queue stall; not a Windows/eGPU remedy'}],
    'driverTdrPowerBiosNetworkChanged':False,'newGpuWorkLaunched':False,
    'next':'Read-only driver-install/runtime provenance and dock-type comparison; do not replay unchanged failing GPU batch. Continue CPU code/data work; any GPU isolation must change one discriminating condition and preserve durable evidence.'}
analysis_path=J/'gpu-compatibility-r1/dock-recurrence-analysis-20261117.json'
analysis_path.write_text(json.dumps(analysis,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);j=x['jointArchitecture20261115'];o=j['overnightExecution20261116']
incident=read(J/'gpu-compatibility-r1/second-restart-20261117.json')
record={**incident,'ownerLatestDockPattern':analysis['ownerQuote'],'analysis':str(analysis_path),
    'journalIntegration':str(target),'observedAt':at,'overnightDeadlineMet':False,
    'workContinuedAfterRebootUntilMorning':False,'currentOwnedGpuWorkerRunning':False,
    'trainingStillNotStarted':True,'noNewQualityClaimFromPartialSource':True}
o['secondRestartInvestigation20261117']=record
o['state']='SECOND_GPU_RESTART_INCOMPLETE_OVERNIGHT_CPU_CONTINUATION'
o['lastInterruptedOwnedNeuralWorker']={'pid':19924,'createdAt':1794841006.001557,'session':5200,'run':incident['ownedRun']}
o['currentOwnedNeuralWorker']=None;o['pid']=None;o['currentWorkerState']='NOT_RUNNING_AFTER_SYSTEM_RESTART'
g=o['guardedNativeContext20261116']
g.update(state='INTERRUPTED_BY_SECOND_SYSTEM_RESTART_TWO_BLOCKS_NO_COMPLETE_SOURCE',pidBeforeRestart=19924,
    pid=None,lastObserved=at,currentWorkerState='NOT_RUNNING_AFTER_SYSTEM_RESTART',
    completedOriginalBlocks=2,completedOriginalAudioSeconds=360,completedWholeSources=0,
    independentWholeSourceScoreAvailable=False,sourceByteEvidence=str(scene/'owned-run-original-bytes'))
a=o['languageSpecificAdaptation20261116']
a.update(trainingStarted=False,trainingUpdates=0,
    workerSource=str(S/'tdt_domain_adaptation_20261116.py'),checkpointSource=str(S/'tdt_adaptation_checkpoint_20261116.py'),
    sourceState='WIP_CPU_SYNTAX_AND_JOURNAL_CHECKED_GPU_LOSS_LARGEST_SHAPE_CHECKPOINT_RESUME_NOT_PROVEN',
    gpuTrainingAdmissionReady=False)
x['state']=o['state']
x['next']='先完成显卡坞/计算运行时复发的可区分定位，不原样重放两次重启时在跑的GPU批次；显卡仍需使用，但长期稳定尚未建立。白天继续TDT英文119M适配实现的预检/续作/独立评分及数据工作，CPU/核显不训练；当前0活GPU任务、2段6分钟不当整会成绩，原95/98和说话人门不变，07:30目标未完成。'
entry=(at+'｜早晨承接Owner“昨晚为啥又重启”“通常只在接显卡坞、连续几天、以前不会”。'
    '第二次异常约11月16日23:15，23:16:08重新启动；当时本任务MOSS0.9B/RX6800XT固定权重识别推理在跑，非训练。'
    '两段各180秒原帧输出和2024行算子记录完整保留并逐文件核SHA，两个3875字节最新进度文件全零原件未覆盖。'
    '末次显存峰值预留3.7559GiB、驱动空闲11.9805GiB、系统可用9.9514GiB，非保证崩溃瞬时采样；暂无耗尽证据。'
    'Kernel41码0/电源键0，无匹配新转储/崩前显卡恢复或资源耗尽事件；旧1cc确属11月12日，不混本次。'
    '绕过MIOpen、换模型后仍重启，短测不代表长稳，本任务GPU负载仍列首要触发嫌疑，计算运行时/驱动/显卡坞链路/供电/温度尚未区分。'
    '近31天现存最早异常为11月5日22:57，本地ROCm/PyTorch目录22:29–22:31建立，仅时间关联不认定因果。'
    '现场在'+str(scene)+'，摘要'+str(analysis_path)+'。'
    '后续未执行TDT源码接入fsync/上一版备份/损坏原件归档，模拟全零及恢复验证通过、真实断电未测、GPU根因未修。'
    '原冻结MOSS源码未热改，0新GPU调用、0参数更新、0驱动/TDR/功耗/网络修改；119M训练及第二源整会验证未完成，重启后无模型进程，未持续跑到07:30、原夜间交付目标未达，不改分数/门槛，不认定售卖。')
if entry not in x['logResult']:x['logResult']+='\n\n'+entry+'\n'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':x['state'],'analysis':str(analysis_path),'journal':str(target),'trainingUpdates':0,'newNeuralCalls':0},ensure_ascii=False))
