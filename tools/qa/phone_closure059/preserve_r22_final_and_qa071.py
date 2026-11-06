from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, os, subprocess, shutil, hashlib

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
M = R / 'model-research'
S = R / 'companion-device-closure055'
W = Path(__file__).parent
H = R / 'docs/handoffs/20261105-model-resume'
D = H / 'full-L-staged-inputs-20261106-r22'
REL = Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/android-trash071')
O = R / REL
now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
supervisor = json.loads((D / 'full-L-owner-resume.json').read_text(encoding='utf8'))
batch = json.loads((D / 'batch-state.json').read_text(encoding='utf8'))
last = json.loads((D / 'results/L_R003S01C02-20261106-r22/state.json').read_text(encoding='utf8'))
resource = json.loads((D / 'full-L-owner-resume-resources.jsonl').read_text(encoding='utf8').splitlines()[-1])
assert supervisor['state'] == 'STOPPED_DURING_WORKER_WINDOWS_LOW_SYSTEM_RAM'
assert batch['state'] == 'FULL_MEETING_INCOMPLETE_EVIDENCE_RETAINED_NO_AUTOMATIC_RETRY'
assert last['completedAcousticChunks'] == last['totalAcousticChunks'] == 79
assert last['decoderPrefillLayersCompleted'] == 3 and last['generatedTokens'] == 0
import psutil
assert not psutil.pid_exists(last['pid']), 'Worker is still live; do not publish stopped state'
record = {
    'at': now, 'state': supervisor['state'], 'control': str(D),
    'ownerQuote': '另外现在显卡重新可以用了', 'activeWorkerPid': None,
    'startedAt': supervisor['startedAt'], 'finishedAt': supervisor['finishedAt'],
    'actualGpu': last['actualGpu'], 'audioSeconds': batch['audioSeconds'],
    'completeExactAuthorInputStagingPassed': True,
    'completedAcousticChunks': 79, 'totalAcousticChunks': 79,
    'decoderPrefillLayersCompleted': 3, 'decoderPrefillLayerTotal': 28,
    'generatedTokens': 0, 'newWholeMeetingQualityScore': None,
    'supervisorResult': supervisor['results'][0], 'lastResourceSample': resource,
    'gpuAllocatorSnapshot': {key: last[key] for key in ['gpuAllocatedBytes', 'gpuReservedBytes', 'gpuPeakAllocatedBytes', 'gpuPeakReservedBytes']},
    'preparedInputCache': last['preparedInputCache'],
    'reason': supervisor['stopReason'], 'automaticInferenceRetries': 0,
    'interpretation': 'Exact author preprocessing separation passed the previous PREPARING_COMPLETE_AUDIO stop and all 79 acoustic chunks. The separate whole-context decoder did not finish; low system RAM is observed, its global root cause is not established. FAILED_BEFORE_RECEIPT means the stopped worker could not write its final receipt, not a newly diagnosed model-math failure.',
    'unchangedGuards': {'cpuPercentMaximum': 5, 'privateMemoryGiB': 2, 'gpuPriority': 'IDLE', 'cooperativeDuty': .1, 'actualWindowsLowMemoryStop': True, 'oneModelAtATime': True},
    'otherAppsClosed': False, 'driverSettingsChanged': False,
    'productModelChanged': False, 'computerUse': False, 'phoneIo': False,
    'next': '不在相同全局低内存条件下盲重跑R22，不放宽既有保护。保留已验证独立输入准备及完整上下文/权重；下一次须有可区分的内存条件或实现变化后再整会验证，完整输出退出后才独立评分。当前推进原安卓回收站/Word受影响验收及Windows文件夹实际分享，等待共享手机占用释放。'
}
(D / 'final-observed-result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
env = {**os.environ, 'GIT_SSH_COMMAND': 'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2', 'GIT_TERMINAL_PROMPT': '0'}
def git(repo, *args):
    q = subprocess.run(['git', '-c', 'maintenance.auto=false', *map(str, args)], cwd=repo, env=env, capture_output=True, text=True, encoding='utf8', errors='replace')
    assert q.returncode == 0, q.stdout + q.stderr
    return q.stdout.strip()
def protect(repo, message):
    git(repo, '-c', 'core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof', 'diff', '--cached', '--check')
    git(repo, 'commit', '-m', message)
    pin = git(repo, 'rev-parse', 'HEAD')
    branch = git(repo, 'branch', '--show-current')
    git(repo, '-c', 'pack.threads=1', '-c', 'pack.windowMemory=32m', 'push', 'origin', 'HEAD:refs/heads/' + branch)
    assert git(repo, 'ls-remote', 'origin', 'refs/heads/' + branch).split()[0] == pin
    return pin
dest = M / 'evidence/20261106-staged-full-L-r22'
for name in ['final-observed-result.json', 'batch-state.json', 'full-L-owner-resume.json', 'full-L-owner-resume-resources.jsonl', 'supervisor.log', 'L_R003S01C02-20261106-r22.log']:
    shutil.copy2(D / name, dest / name)
shutil.copy2(D / 'results/L_R003S01C02-20261106-r22/state.json', dest / 'last-worker-state.json')
git(M, 'add', '--', 'evidence/20261106-staged-full-L-r22')
model_pin = protect(M, 'Preserve low-memory stopped full-meeting run without quality claims')
qa = json.loads((O / 'native-qa-prepared.json').read_text(encoding='utf8'))
assert qa['builtOnly'] and not qa['installed'] and not qa['hasActivityOrUi']
assert hashlib.sha256(Path(qa['apk']).read_bytes()).hexdigest() == qa['apkSha256']
apk_dest = S / REL
shutil.copy2(O / 'native-qa-prepared.json', apk_dest / 'native-qa-prepared.json')
shutil.copy2(Path(qa['apk']), apk_dest / Path(qa['apk']).name)
qa_dest = S / 'tools/qa/phone_closure059'
shutil.copy2(W / 'build_lifecycleqa071.py', qa_dest / 'build_lifecycleqa071.py')
(qa_dest / 'lifecycleqa071').mkdir(exist_ok=True)
shutil.copy2(W / 'lifecycleqa071/LifecycleQa071.java', qa_dest / 'lifecycleqa071/LifecycleQa071.java')
shutil.copy2(Path(__file__), qa_dest / Path(__file__).name)
p = R / 'docs/product_backlog.json'
raw = p.read_bytes()
d = json.loads(raw)
front = d['owner_module_execution']['frontendWindowsMobile20261102']
task = front['ownerDevicePhoneClosure055']
night = front['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
night['ownerGpuReconnected20261106'].update(state='R22_STOPPED_ACTUAL_WINDOWS_LOW_SYSTEM_RAM_AFTER_79_CHUNKS_NO_OUTPUT', r22FinalResult=str(D / 'final-observed-result.json'), r22Final=record, newAccuracyScore=None)
night['inputStagingR19'].update(state='EXACT_FULL_INPUT_PREPARATION_R21_PASSED_R22_STOPPED_LOW_SYSTEM_RAM', latestResult=str(D / 'final-observed-result.json'), finalEvidenceCommit=model_pin)
night['ownerContinueFullMeeting20261106'].update(state=supervisor['state'], control=str(D), activeWorkerPid=None, finishedAt=supervisor['finishedAt'], next=record['next'])
night['restoredSpeechResult20261106']['longGpuValidationState'] = 'R22_STOPPED_LOW_SYSTEM_RAM_NO_COMPLETE_OUTPUT_NO_NEW_SCORE'
night['status'] = 'FULL_L_R22_STOPPED_LOW_SYSTEM_RAM_EXACT_INPUT_STAGING_RETAINED'
night['next'] = record['next']
task['androidTrash071']['nativeQaPrepared'] = {**qa, 'at': now, 'actualAndroidFilesystemQualified': False}
task['androidTrash071']['otherPhoneFlowObservation'] = {'at': now, 'reportedVersion': '0.1.69', 'sourceApkMatchUnknown': True, 'state': 'Other embedded chat reports installation; this work did not query or replace the phone. Verify exact APK/source after lease release, no blind same-version overwrite.'}
task['next'] = '共享手机/板仍由FW66692配对/OTA流程占用。本侧已准备无界面、独立UID的虚构文件回收站真Android验收包，等释放后核真实APK身份再执行；不得盲装同号069。Word、普通界面与原库切回以及Windows068实际文件夹收件仍开放。R22因实际Windows低RAM停止且无活模型，不在相同条件下盲重跑。'
task['ownerPriority12']['next'] = task['next']
task['priority12Actual']['next'] = task['next']
assert p.read_bytes() == raw, 'Concurrent canonical edit; restart from fresh current file'
tmp = p.with_suffix('.r22-final.tmp')
tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
os.replace(tmp, p)
with (R / 'docs/development_log.md').open('a', encoding='utf8') as stream:
    stream.write(f'''\n\n## {now}｜R22完整声学编码通过但低RAM停止；安卓回收站独立后台真机验收候选保留\n\nOwner接回6800XT后的原完整2362.945秒L会议，独立原作者输入预处理R21已通过并退出释放临时数组；R22真实选择RX6800XT/gfx1030、全部权重回读哈希一致，跨过R18音频准备内存阻断，79/79声学块实际编码完成。22:05:54至22:16:20（族626.090464秒）在完整上下文第3/28层时Windows实际LowMemoryResourceNotification触发，仅结束本实验族，private峰1401982976B、RSS峰1322315776B、末样本可用837869568B。GPU allocator peak reserved3772776448B并非物理显存测量，也没有证据说16GB显存已满。无完整转写、0生成标记、无新准确率或说话人分数；worker被停止前无法写final receipt而显示FAILED_BEFORE_RECEIPT，不据此另诊断模型数学失败。输入分阶段实际有效范围与整会未完分开；真实原因仅确认系统低RAM，来源未定。当前worker不存在，CPU5%/private2GiB/IDLE+duty.1与低RAM保护未放宽、无其它应用关闭、无自动重试。研究终态证据{model_pin}已上传并读回，原运行快照保留为历史，当前原待办已纠正为停止。\n\nAndroid069本机保护/回收站可恢复删除源码fb4d80e与候选23cdacd6已保留。新准备独立包com.denzic.companion.lifecycleqa071，SHA{qa['apkSha256']}，同生产生命周期类及原pin备份class，在自己的UID/私有虚构目录分create/reopen/interrupt/retry阶段验真实目录fsync、跨进程恢复、中断清除继续及另一UID录音不受影响；无Activity/蓝牙/网络，不访问Companion原资料。仅编译验包，未安装或执行，不代替普通App界面/确认取消/原资料保护验收。准备器首编译因IOException回调签名失败已修，rawbytes哈希校验保持，不计作用户功能进展。共享手机仍在FW66692配对路径工作，原聊天报告已装Android069但source/APK匹配未知，本侧未查询/覆盖，不冒充本候选已装，也不盲同号升级。Windows068实际文件夹选中/本机收件、手机Word/回收站普通流程及原资料库切回仍留未完成。本批无Computer Use或手机/板IO。\n''')
for name in ['product_backlog.json', 'development_log.md']:
    shutil.copy2(R / 'docs' / name, S / 'docs' / name)
git(S, 'add', '--', 'docs/product_backlog.json', 'docs/development_log.md', 'tools/qa/phone_closure059')
git(S, 'add', '-f', '--', REL / 'native-qa-prepared.json', REL / Path(qa['apk']).name)
main_pin = protect(S, 'Protect background Android lifecycle QA and final stopped model workpoint')
print(json.dumps({'modelEvidenceCommit': model_pin, 'mainCommit': main_pin, 'remoteReadbackConfirmed': True, 'modelRunning': False, 'newFullMeetingQuality': None, 'qaInstalled': False}, ensure_ascii=False), flush=True)
