"""Owner extended the original whole-meeting comparison to 16:00, retaining all old evidence."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');C=BASE/'staged-r5'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not (E/'staged-r5').exists();C.mkdir()
B=read(BASE/'staged-r4/staged-binding.json')
B.update(at=datetime.now().astimezone().isoformat(),neuralDeadline='2026-11-16T15:40:00+08:00',reportDeadline='2026-11-16T16:00:00+08:00',
 workerSha256=sha(S/'moss_staged_meeting_worker_20261115.py'),runnerSha256=sha(S/'run_moss_staged_meetings_20261115.py'),
 decodeStepPauseSeconds=.05,synchronizeEachDecodeForward=True,
 change='Owner explicitly extended the interrupted job to Nov16 16:00. Fresh post-reboot device/process state, reuse unchanged full27924-token prefill, preserve all4064 previously generated IDs. Synchronize each decoder forward then pause50ms; same argmax/EOS/weights and frozen native control. No OS/driver/power/global changes or automatic retries.',
 oldResults='Prior staged-r2 HIP abort left a failed GPU context before staged-r4; staged-r4 was then interrupted by whole-system0x101 at00:16. The cause is unknown and context persistence is a hypothesis, not a proven explanation. A fresh OS/device context plus per-forward sync/pacing changes execution conditions. Short native16-token control must pass before completing original first meeting; halt on any new kernel/runtime failure rather than blindly retry.')
B['helpers'][str(S/'moss_native_greedy_20261115.py')]=sha(S/'moss_native_greedy_20261115.py')
p=E/'staged-r4/ES2003b-partial-ids.json';ids=read(p)['generatedIds'];assert len(ids)==4064
B['cases'][1]['resumeGeneratedPrefix']={'file':str(p),'sha256':sha(p),'tokens':len(ids)}
B['postRebootObservation']={'bootAt':datetime.fromtimestamp(psutil.boot_time()).astimezone().isoformat(),'availableMemoryBytes':psutil.virtual_memory().available,
 'systemBugcheckCauseProven':False,'minidumpAtStandardConfiguredPaths':False,'newDriverOrPackageInstalled':False,
 'integrityCheck':str(BASE/'overnight-system-interruption-r1/retained-integrity-check.json')}
for f,h in B['helpers'].items():assert sha(f)==h,f
assert psutil.disk_usage('E:/').free>50*1024**3
assert not psutil.pid_exists(14144) and not psutil.pid_exists(11636)
(C/'staged-binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p)
quote='没事啊，你异常重启，那就继续跟着搞，延长对应的时间。现在看一下，搞到中午，今天中午，晚上晚上对应可能搞到晚上4点，下午4点吧。去搞一下。'
d['state']='DAY_RESUME_AUTHORIZED_TO_1600_NATIVE_CONTROL_PENDING'
o=d['ownerOvernightRun20261115'];o['extension20261116']={'at':B['at'],'quote':quote,'reportDeadline':B['reportDeadline'],'neuralDeadline':B['neuralDeadline'],
 'previousDeadlinePreserved':'2026-11-16T07:30:00+08:00','sourceOfPermission':'Owner current message explicitly continues after unexpected reboot',
 'changedExecutionConditions':B['change'],'failedKernelOrSystemCrashAutomaticRetries':0}
o.update(currentState=d['state'],currentStagedControl=str(C),currentStagedRun=str(E/'staged-r5'),activePid=None,retainedRealGeneratedPrefixTokens=4064,
 currentNeuralDeadline=B['neuralDeadline'],currentReportDeadline=B['reportDeadline'])
d['next']='按Owner最后明确延至11月16日16:00：重启后新设备/进程状态，逐forward同步并留50ms间隔，先原61s/16token严格控制；复用完整预填充及4064原ID续完ES2003b，再原四完整开发会逐场CPU评分。15:40停止神经推理留评分保护；若再出内核/系统异常即保留，不自动重试。CPU5%/族2GiB/真实低RAM/原质量门/留出不动，不改驱动/系统保护/全局电源/产品默认。'
d['jointArchitecture20261115'].update(state=d['state'],nextExecutableGate=d['next'])
d['logResult']+='\n'+B['at']+' Owner原话：'+quote+' 已按最终下午16:00承接原模型任务，不另建Goal/聊天/定时任务。07:30中断交付与0x101未知根因保留。当前可用RAM约'+str(round(psutil.virtual_memory().available/2**30,2))+'GiB；真正新条件为整机重启后干净设备/进程状态、逐解码forward同步及50ms间隔，先16原token控制，4064原ID与27924全上下文全部保留。此为明确授权后的受控续作，不声称已修复系统根因；新内核/系统异常不自动重试，15:40推理截止/16:00结果，原所有质量与资源门保留。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
subprocess.run([sys.executable,'work/record_bilingual_progress.py',str(p)],check=True)
print(json.dumps({'control':str(C),'run':str(E/'staged-r5'),'resumeTokens':4064,'deadline':B['reportDeadline']},ensure_ascii=False))
