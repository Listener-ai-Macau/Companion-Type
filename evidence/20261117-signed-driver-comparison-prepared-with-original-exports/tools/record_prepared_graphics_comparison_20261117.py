"""Freeze the concrete driver comparison preparation in the existing model workpoint."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import psutil

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
ROOT = E / 'system-restart-20261116-2315/graphics-driver-comparison-prepared-r1'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


old = read(ROOT / 'completed.json')
final = read(ROOT / 'inspection-r2/completed.json')
assert final['state'] == 'PASS_SIGNED_CANDIDATE_BOTH_ACTUAL_GPU_DEVICE_IDS_AND_EXPORTED_ROLLBACK_FILES_NOT_INSTALLED'
assert all(final['candidateActualDeviceIdMatches'].values())
def original_process_identity(record):
    try:
        p = psutil.Process(record['pid'])
        created = p.create_time()
        same = abs(created - record['createdAt']) < .01
        return {'pid': record['pid'], 'expectedCreatedAt': record['createdAt'],
                'pidCurrentlyExists': True, 'currentCreatedAt': created,
                'sameOriginalProcessStillLive': same and p.is_running()}
    except psutil.NoSuchProcess:
        return {'pid': record['pid'], 'expectedCreatedAt': record['createdAt'],
                'pidCurrentlyExists': False, 'sameOriginalProcessStillLive': False}

identities = [original_process_identity(row) for row in [old, final]]
assert not any(r['sameOriginalProcessStillLive'] for r in identities)
exports = read(ROOT / 'existing-driver-export.json')['exports']
assert len(exports) == 2 and all(row['exitCode'] == 0 for row in exports)
backup_signatures = read(ROOT / 'existing-driver-catalog-signatures.json')['signatures']
assert len(backup_signatures) == 2 and all(r['status'] == 'Valid' for r in backup_signatures)
byte_matches = []
for row in exports:
    original = Path('C:/Windows/INF') / row['publishedInf']
    copied = next((ROOT / 'existing-driver-export' / original.stem).glob('*.inf'))
    assert original.read_bytes() == copied.read_bytes()
    byte_matches.append({'publishedInf': original.name, 'exportedInfSha256': sha(copied),
                         'originalWindowsInfSha256': sha(original), 'exactBytesEqual': True})
inspection = read(ROOT / 'inspection-r2/display-branch-inspection.json')
assert all(c['signature']['status'] == 'Valid' for row in inspection['files'] for c in row['catalogs'])
owned_remaining = []
for p in psutil.process_iter(['pid', 'cmdline']):
    try:
        command = ' '.join(p.info.get('cmdline') or []).replace('\\', '/').lower()
        if p.pid != __import__('os').getpid() and str(ROOT).replace('\\', '/').lower() in command:
            owned_remaining.append({'pid': p.pid, 'name': p.name()})
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
assert not owned_remaining
at = datetime.now().astimezone().isoformat(timespec='seconds')
paths = ['completed.json', 'existing-driver-export.json', 'existing-driver-catalog-signatures.json',
         'devices-before.json', 'candidate-display-inf.json', 'download-headers.txt',
         'inspection-r2/completed.json', 'inspection-r2/actual-device-identifiers.json',
         'inspection-r2/display-branch-inspection.json']
report = {
    'at': at, 'state': 'SIGNED_OFFICIAL_DRIVER_COMPARISON_AND_EXISTING_DRIVER_EXPORTS_PREPARED_NOT_INSTALLED',
    'root': str(ROOT), 'modelSourceCommitBeforeThisPreparation': '78c35093941e27aab63c2880d7720b22a52072c9',
    'candidate': {'release': 'Adrenalin26.8.1', 'url': old['downloadUrl'], 'publisherPage': old['source'],
                  'bytes': old['bytesDownloaded'], 'sha256': old['packageSha256'],
                  'authenticode': old['authenticode'], 'installerExecuted': False,
                  'deviceMatchingIsNotGpuComputeStabilityQualification': True},
    'deviceSpecificBranches': [{
        'archiveMember': row['archiveMember'], 'driverVerLines': row['driverVerLines'],
        'exactHardwareOrCompatibleIdMatches': row['exactHardwareOrCompatibleIdMatches'],
        'infSha256': row['sha256'],
        'catalogs': [{'sha256': c['sha256'], 'signature': c['signature']} for c in row['catalogs']]
    } for row in inspection['files']],
    'rollbackFiles': {'packages': [{'publishedInf': row['publishedInf'], 'files': len(row['files']),
                                    'bytes': row['totalBytes'], 'exportExitCode': row['exitCode']} for row in exports],
                      'totalBytes': sum(row['totalBytes'] for row in exports),
                      'windowsInfExactByteMatches': byte_matches, 'catalogSignatures': backup_signatures,
                      'restorationActuallyTested': False, 'fullApplicationOrSystemSnapshot': False},
    'originalPreparationFailure': {'receipt': str(ROOT / 'completed.json'), 'error': old['error'],
        'cause': 'The first inspector considered Display but omitted the separateDisplay2 driver branch.',
        'resolvedByOfflineInspection': str(ROOT / 'inspection-r2/completed.json'),
        'originalFailureAndSourcePreserved': True, 'originalPackageDownloadedAgain': False},
    'closedOwnedJobs': [{'pid': old['pid'], 'session': 54541, 'originalProcessNotLiveVerified': True,
                         'processIdentityCheck': identities[0],
                         'terminal': 'Preparation failed only at incomplete device-match inspection; no driver install.'},
                        {'pid': final['pid'], 'session': 82082, 'originalProcessNotLiveVerified': True,
                         'processIdentityCheck': identities[1],
                         'terminal': 'Offline full-branch inspection passed.'}],
    'ownedPreparationCommandsStillLive': owned_remaining,
    'evidenceSha256': {name: sha(ROOT / name) for name in paths},
    'sourceSha256': {name: sha(Path('work') / name) for name in [
        'prepare_graphics_driver_comparison_20261117.py', 'inspect_existing_graphics_package_20261117.py',
        'record_prepared_graphics_comparison_20261117.py']},
    'graphicsDriverInstallationAuthorized': False, 'gpuWasDisconnectedDuringPreparation': True,
    'originalGraphicsDriversChanged': False, 'tdrBiosPowerNetworkChanged': False,
    'newNeuralCalls': 0, 'newGpuCalls': 0, 'parameterUpdates': 0,
    'restartRootCauseIdentified': False, 'qualityQualified': False, 'saleQualified': False,
    'next': 'Candidate and old-driver exports are ready for review. WhenRX6800XT is connected, verify exact current device/driver identity and choose the single driver comparison only after Owner authorizes that concrete graphics-driver action; do not automatically install, reboot, extend the old execution window or launch the old failing long batch. Keep the existingTorch/ROCm/model/audio fixed. Afterwards actual compute stability and original English adaptation preflight are still required.'}
target = J / 'gpu-compatibility-r1/driver-comparison-prepared-20261117.json'
target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
p = Path('work/bilingual_progress.json')
x = read(p)
own = x['jointArchitecture20261115']['overnightExecution20261116']
own['preparedGraphicsDriverComparison20261117'] = {'receipt': str(target), 'state': report['state'],
    'candidateSha256': old['packageSha256'], 'rollbackBytes': report['rollbackFiles']['totalBytes'],
    'actualBothDeviceIdsMatched': True, 'graphicsDriverInstalled': False,
    'rollbackActuallyTested': False, 'ownedJobsTerminal': True}
x['at'] = at
x['state'] = own['state'] = 'GPU_UNDOCKED_SIGNED_DRIVER_COMPARISON_FILES_PREPARED_MODEL_PREFLIGHT_PENDING'
x['next'] = '驱动对照文件已具体准备：AMD26.8.1完整包签名Valid、两分支目录签名Valid，分别精确匹配本机780M及6800XT硬件/兼容ID；现oem0/oem1共1938307502B已导出、INF与Windows原件字节相同、目录签名Valid，恢复本身未测试。首次检查漏Display2导致失败已保留并在同包离线补读修正，无重下/无安装/无GPU调用。当前独显仍拔，待接回核身份并获本次具体图形驱动动作授权后才考虑固定运行环境的单变量对照，不自动改驱动或重启。英文475片/119更新实际梯度/最大形状/检查点预检仍待GPU执行，中文全局人员隔离仍未证实；95/98/整源/逐人/事实/盲测开放。'
x['logResult'] += '\n\n' + at + '｜继续原模型GPU兼容性项，把26.8.1对照从泛泛建议做成实际文件：只读核6800XT断开、780M在场，PnpUtil/export-driver导出oem0(126文件782127114B)/oem1(134文件1156180388B)，两INF与Windows原件字节相同、两目录Microsoft硬件签名Valid，恢复未实测。AMD官方同一候选包只下载1次1669192200B，SHA00c416cd...、AMD数字签名Valid；只用7z读数据，未运行安装器。首准备器漏Display2分支而匹配失败，原源/失败终态保留；同包补查根INF/目录后两个实际兼容ID均匹配：内显32.0.31041.1004/外显32.0.21045.5002，目录签名均Valid，无重复下载或注册驱动。收尾记录首次用PID存在判断被WindowsPID复用挡住，未写项目结果；已保留失败并按创建时间核对原两个作业确已结束，不杀复用PID对应的其它程序。原驱动/TDR/BIOS/功耗/网络未变，0神经调用0参数更新。只形成可审查候选与回退文件，不宣称已修重启或模型质量改善；GPU接回及具体图形驱动动作授权/实际稳定性仍是依赖。结果' + str(target) + '。\n'
p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'receipt': str(target), 'state': report['state'], 'rollbackBytes': report['rollbackFiles']['totalBytes'], 'ownedJobsStillLive': owned_remaining}, ensure_ascii=False))
