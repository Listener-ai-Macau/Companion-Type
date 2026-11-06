from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, os, shutil, subprocess, psutil, winreg

W = Path(__file__).parent
R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
S = R / 'companion-device-closure055'
rel = Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share069')
O = R / rel
env = {**os.environ, 'GIT_SSH_COMMAND': 'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2', 'GIT_TERMINAL_PROMPT': '0'}

def git(*args):
    p = subprocess.run(['git', '-c', 'maintenance.auto=false', *map(str, args)], cwd=S, env=env, capture_output=True)
    if p.returncode:
        raise RuntimeError((p.stdout + p.stderr).decode('utf8', 'replace')[-3000:])
    return p.stdout.decode('utf8', 'replace').strip()

# Close only the probe with its recorded exact process identity; never other apps.
meta = json.loads((O / 'modern-gui-session.json').read_text(encoding='utf8'))
cleanup = 'ALREADY_EXITED'
try:
    p = psutil.Process(meta['pid'])
    if abs(p.create_time() - meta['createTime']) < .001 and Path(p.exe()).resolve() == Path(meta['exe']).resolve():
        p.terminate()
        p.wait(timeout=10)
        cleanup = 'EXACT_OWN_PROBE_TERMINATED'
    else:
        cleanup = 'PID_REUSED_NOT_TOUCHED'
except psutil.NoSuchProcess:
    pass

source = S / 'apps/windows/src-tauri/src/content_handoff.rs'
expected = 'c5f26bdf995c994c33d7d86869ffd09207c31769141eca2c00491bdb7ea10ec2'
assert hashlib.sha256(source.read_bytes()).hexdigest() == expected, 'Unexpected source; preserve without overwriting'
baseline_commit = '60166fa3bd22cc277d4a6c69962d39fa3c13e9e0'
baseline = subprocess.run(['git', 'show', baseline_commit + ':apps/windows/src-tauri/src/content_handoff.rs'], cwd=S, capture_output=True, check=True).stdout
source.write_bytes(baseline)
baseline_sha = hashlib.sha256(baseline).hexdigest()

commands = {}
base = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\CommandStore\shell'
for name in ('Windows.ModernShare', 'Windows.ModernShareFlyout', 'Windows.Share'):
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base + '\\' + name) as key:
        values = {}
        i = 0
        while True:
            try:
                k, v, _ = winreg.EnumValue(key, i)
                values[k] = v
                i += 1
            except OSError:
                break
        commands[name] = values

now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
actual = json.loads((O / 'actual-dual-picker-result.json').read_text(encoding='utf8'))
record = {
    'at': now, 'state': 'SHARE069_ACTUAL_PICKER_FAILED_CANDIDATE_REVERTED_NO_PRODUCT_REPLACEMENT',
    'ownerQuote': '你来吧', 'manualReplyPending': False,
    'actualDualPicker': actual,
    'shellModernShare': {
        'withoutSite': '0x80070578 invalid window handle',
        'withWindowSite': 'InvokeCommand S_OK, actual SharePicker still Retry/cannot show sharing methods',
        'actualRecipientReceived': False,
        'WindowsShareVerbInvoked': False,
        'WindowsModernShareFlyoutInvoked': False,
        'readOnlyCommandStore': commands,
    },
    'failedCandidateCommit': 'e6a3f63548720b8273841fea4ff2276b91380cd4',
    'failedCandidateSourceSha256': expected,
    'restoredSourceCommit': baseline_commit,
    'restoredSourceSha256': baseline_sha,
    'rollbackReason': 'Source tests and background IPC pass, but the actual system picker remains broken in both minimal methods; do not ship candidate as a fix.',
    'knownWorkingBoundary': 'The same public PDF shows targets from File Explorer toolbar; recipient selection/actual receive not yet performed.',
    'ruledOutThisBatch': ['Normal user-profile environment does not fix it', 'Simple process elevation difference not observed', 'Independent process reads original public PDF byte-identically from both DataPackages'],
    'systemObservation': 'EnableLUA=0 was read only; causality not established. No UAC/security/privacy settings changed.',
    'interruption': 'Computer Use reported physical Escape user stop; no further Computer Use calls or app input.',
    'ownProbeCleanup': cleanup,
    'computerUseThisBatch': True, 'modelsRun': False, 'deviceIo': False,
    'installedProduct': 'Windows0.1.67', 'productBuildOrInstallThisBatch': False,
    'actualSystemShareQualified': False, 'wholeProductQualified': False,
    'next': 'Prefer background investigation of observed Windows.ModernShareFlyout versus old ModernShare, using official supported APIs; Windows.Share is a different Share With command and must not be blindly invoked or change ACLs. If direct system picker cannot be repaired promptly, provide a clearly named Explorer file-sharing route and prove receipt in local QA target. No repeated profile/elevation/IPC checks, no unproven release. UI input stays stopped this turn.',
}
(O / 'actual-continuation-result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

canonical = R / 'docs/product_backlog.json'
raw = canonical.read_bytes()
data = json.loads(raw)
front = data['owner_module_execution']['frontendWindowsMobile20261102']
task = front['ownerDevicePhoneClosure055']
prior = task['windowsShare069']
prior['backgroundChecksPreserved'] = True
prior['actualContinuation'] = record
prior['state'] = record['state']
prior['manualReplyPending'] = False
prior['computerUseThisBatch'] = True
prior['actualSystemShareQualified'] = False
prior['candidateRestoredTo067Source'] = True
task['state'] = record['state']
task['next'] = record['next'] + ' 手机/板继续尊重现有嵌软占用，不安装候选066、不降级当前手机、不抢板；原库切回与未完成真机流程仍保留。'
task['ownerPriority12']['state'] = record['state']
task['ownerPriority12']['next'] = task['next']
task['priority12Actual']['next'] = task['next']
task['ownerPriority12']['latestContinuation'] = {'at': now, 'ownerQuote': '你来吧', 'meaning': 'Authorized limited local sharing UI comparison; stopped when Computer Use reported physical Escape.'}
for item in front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']:
    if item['id'] == 'exports':
        item['engineering']['windowsShare069Actual'] = {'receipt': str(O / 'actual-continuation-result.json'), 'actualSystemShareQualified': False, 'failedCandidateReverted': True, 'installedVersion': '0.1.67'}
assert canonical.read_bytes() == raw, 'Concurrent canonical edit; re-read before retry'
temp = canonical.with_suffix('.share069actual.tmp')
temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
os.replace(temp, canonical)
with (R / 'docs/development_log.md').open('a', encoding='utf8') as f:
    f.write(f'''\n\n## {now}｜Owner“你来吧”后真实对照：两种WinRT方式均失败，ModernShare窗口站点补齐仍失败；候选回到067源码\n\nOwner明确授权本机分享窗口和本机验收应用的小范围操作。冻结旧方式与request.Data候选的普通按钮各自真实打开SharePicker，均显示“重试／无法为你显示所有共享方法”，所以之前通过源码检查和独立进程原文件字节核对不能视作修复。未构建、未安装069，日用仍067。失败源码e6a3f635及测试与IPC原证据保留，content_handoff.rs仅按精确c5f26b…哈希防覆盖后回到60166已安装版本的同一文件，不将候选留作默认交付。\n\n为区别资源管理器已能枚举目标的路径，对同一公开PDF只读查询系统IContextMenu。Windows.ModernShare未设站点时0x80070578；补IObjectWithSite/IOleWindow实际有效HWND后InvokeCommand返回S_OK，但真实面板仍为同一Retry失败，没有收到文件。保留此失败，不写“系统接受调用”等于通过。只读CommandStore另有Windows.ModernShareFlyout，其处理器与ModernShare不同，尚未调用。Windows.Share是另一Share With类，不盲调用或更改文件权限。只读EnableLUA=0的观察保留，未证明因果，未改UAC、安全或隐私设置。\n\n恢复下一次观察时Computer Use明确报告实体Esc由用户中止，立即停止所有UI调用；仅后台核实并关闭有精确PID/创建时间/路径匹配的自建验证程序，保存当前点。没有向联系人或外部应用发送文件，没有模型、训练、手机或板IO。下步优先后台核对真实Shell入口区别，若直开系统面板短期无法修复，改为明确命名的文件夹分享路径并以本机QA真实收件核验，不能重复无改善打包。原手机/板在另一嵌软占用中，原资料库切回及其它售卖缺口继续未完成。\n''')

dest = S / rel
dest.mkdir(parents=True, exist_ok=True)
for name in ('actual-continuation-result.json', 'actual-dual-picker-result.json', 'modern-gui.log', 'modern-invoke-first-error.log', 'shell-verbs-readonly.log'):
    if (O / name).exists():
        shutil.copy2(O / name, dest / name)
qa = S / 'tools/qa/phone_closure059'
for name in ('run_share069_dual_gui.py', 'check_shell_share069.py', 'prepare_modern_share069.py', 'run_modern_share069_gui.py', 'preserve_share069_actual_failures.py'):
    if (W / name).exists():
        shutil.copy2(W / name, qa / name)
for name in ('ModernShareWindow.cpp', 'ShellShareVerbs.cpp', 'ShareReceiver.cpp'):
    shutil.copy2(W / 'windows_shareqa068' / name, qa / 'windows_shareqa068' / name)
for name in ('product_backlog.json', 'development_log.md'):
    shutil.copy2(R / 'docs' / name, S / 'docs' / name)
git('add', '--', 'apps/windows/src-tauri/src/content_handoff.rs', 'docs/product_backlog.json', 'docs/development_log.md', 'tools/qa/phone_closure059')
git('add', '-f', '--', rel / 'actual-continuation-result.json', rel / 'actual-dual-picker-result.json', rel / 'modern-gui.log', rel / 'shell-verbs-readonly.log')
git('diff', '--cached', '--check')
git('commit', '-m', 'Revert unproven share candidate and preserve actual picker failures')
pin = git('rev-parse', 'HEAD')
branch = git('branch', '--show-current')
git('-c', 'pack.threads=1', '-c', 'pack.windowMemory=32m', 'push', 'origin', 'HEAD:refs/heads/' + branch)
assert git('ls-remote', 'origin', 'refs/heads/' + branch).split()[0] == pin
receipt = {'protectedCommit': pin, 'remoteReadbackConfirmed': True, 'installedProduct': '0.1.67', 'actualSystemShareQualified': False, 'sourceRestoredToInstalledBaseline': True, 'probeCleanup': cleanup}
(O / 'actual-remote-readback.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
print(json.dumps(receipt), flush=True)
