"""Read installed package metadata; record version-specific upstream compatibility limits."""
from pathlib import Path
from datetime import datetime
import base64
import hashlib
import importlib.metadata
import json
import subprocess
import winreg
import zipfile

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
J = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
SITE = Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
WHEELS = Path('E:/CodexData/Companion/.model-cache/amd-wheelhouse-20261105')
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha = lambda b: hashlib.sha256(b).hexdigest()


def main():
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion')
    os_version = {name: winreg.QueryValueEx(key, name)[0]
                  for name in ['DisplayVersion', 'CurrentBuildNumber', 'UBR']}
    winreg.CloseKey(key)
    ps = "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,SystemType | ConvertTo-Json -Compress"
    raw = subprocess.run([
        'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile',
        '-NonInteractive', '-EncodedCommand', base64.b64encode(ps.encode('utf-16-le')).decode()],
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert raw.returncode == 0, raw.stderr
    installed = {d.metadata['Name'].lower(): d for d in importlib.metadata.distributions(path=[str(SITE)])}
    names = ['torch', 'amd-torch-device-gfx1030', 'rocm', 'rocm-sdk-core',
             'rocm-sdk-device-gfx1030', 'rocm-sdk-libraries']
    packages = [{'name': name, 'version': installed[name].version} for name in names]
    assert installed['torch'].version == '2.11.0+rocm10.0.0'
    assert all(installed[name].version == '10.0.0' for name in names if name.startswith('rocm'))
    wheel_checks = []
    for name, wheel in [
        ('torch', 'torch-2.11.0+rocm10.0.0-cp311-cp311-win_amd64.whl'),
        ('rocm-sdk-core', 'rocm_sdk_core-10.0.0-py3-none-win_amd64.whl'),
        ('amd-torch-device-gfx1030', 'amd_torch_device_gfx1030-2.11.0+rocm10.0.0-cp311-cp311-win_amd64.whl')]:
        with zipfile.ZipFile(WHEELS / wheel) as archive:
            metadata = archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA')))
        # read_text preserves the same metadata content as imported distribution metadata;
        # LF-only comparison is provenance checking, not a model or text normalization.
        actual = installed[name].read_text('METADATA').encode('utf-8')
        same = actual.replace(b'\r\n', b'\n') == metadata.replace(b'\r\n', b'\n')
        assert same, name
        wheel_checks.append({'name': name, 'wheel': wheel,
                             'wheelMetadataSha256': sha(metadata),
                             'installedMetadataSha256': sha(actual),
                             'metadataLfEquivalent': same})
    at = datetime.now().astimezone().isoformat(timespec='seconds')
    report = {
        'at': at, 'state': 'VERSION_SPECIFIC_DRIVER_ALIGNMENT_GAP_FOUND_NOT_A_PROVEN_RESTART_CAUSE',
        'os': os_version, 'computerModelWithoutSerialOrUuid': json.loads(raw.stdout),
        'installedPackagesReadWithoutImportingTorch': packages,
        'cachedWheelMetadataChecks': wheel_checks,
        'installedDriverStoreVersionsFromRetainedPnpEvidence': {
            'rx6800xt': '32.0.21043.19003', 'radeon780m': '32.0.31021.5001'},
        'officialSources': [
            {'url': 'https://rocm.docs.amd.com/en/docs-10.0.0/compatibility/compatibility-matrix.html',
             'scope': 'Version-specific10.0.0 matrix, rather than the older7.2.1 site or latest10.1 matrix.',
             'facts': ['RadeonWindows configuration listsWindows11 25H2 andAdrenalin26.8.1.',
                       'RX6800XT is not individually listed in this matrix; PROV620/W6800 gfx1030 entries cannot qualify the consumer card plusUSB4dock.']},
            {'url': 'https://www.amd.com/en/resources/support-articles/release-notes/rn-rad-win-26-6-4.html',
             'facts': ['Both installed driver-store versions occur inAdrenalin26.6.4. Different numbers are expected for its different driver branches; they do not establish mixed-install corruption.']},
            {'url': 'https://www.amd.com/en/resources/support-articles/release-notes/RN-RAD-WIN-26-8-1.html',
             'facts': ['The26.8.1 graphics driver product list includesRX6800series.',
                       'Its package contains32.0.31041.1004 and32.0.21045.5002, differing from this machine.',
                       'The graphics-driver product list is not itself qualification ofROCmtraining or aUSB4eGPUconfiguration.',
                       'AMD recommendsOEM-specific drivers for laptop-specific features.']},
            {'url': 'https://github.com/ROCm/TheRock/blob/main/RELEASES.md',
             'facts': ['TheRock publishes stable10.0 and nightly artifacts; it mapsRX6800XT todevice-gfx1030.',
                       'The installed10.0.0 version string alone does not prove a nightly or release-candidate install. Originaldownload-index provenance is not recovered by the localfile direct_url.']},
            {'url': 'https://github.com/ROCm/TheRock/blob/main/docs/development/windows_support.md',
             'facts': ['The Windows development-support maturity warning remains relevant, but it does not by itself identify this incident or prove every installed stable artifact is a nightly build.']}],
        'findings': {
            'osVersionMatchesDocumentedWindowsVersion': os_version['DisplayVersion'] == '25H2',
            'observedRocmComponentVersionsInternallyAgree': True,
            'installedDriverMatchesDocumented26_8_1Configuration': False,
            'installedDriverProvenIncompatible': False,
            'installedPackageProvenNightly': False,
            'usb4Rx6800xtWholeStackQualified': False,
            'rootCauseIdentified': False},
        'decision': 'Use the actual10.0/26.6.4 versus documented26.8.1 alignment difference as one concrete future discrimination condition. Do not conclude that upgrading will fix the reboots, install blindly, change runtime and driver together, or restart the unchanged long model batch.',
        'futureReviewableDriverComparisonBoundary': {
            'candidate': 'Adrenalin26.8.1 is a documented comparison candidate, not an approved installation or guaranteed fix.',
            'beforeAnyDriverChange': ['VerifyRX6800XT is actually present and exact currentINF/driver identities.',
                                    'Prepare a working existing-driver backup/rollback and checkOEM laptop support.',
                                    'Prepare and verify the exact signed official candidate package and affectedGPUINFs.',
                                    'Keep the existing runtime, original failed audio and model fixed; change a single driver condition.',
                                    'Review the concrete machine-wide driver action withOwner before installation. Sensor-driver consent is not graphics-driver consent.'],
            'gpuJobLaunchedByThisAudit': False,
            'candidateDownloadedOrInstalledByThisAudit': False},
        'newNeuralCalls': 0, 'newGpuCalls': 0, 'parameterUpdates': 0,
        'driverTdrPowerBiosNetworkChanged': False, 'qualityQualified': False, 'saleQualified': False}
    target = J / 'gpu-compatibility-r1/rocm10-driver-alignment-20261117.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    p = Path('work/bilingual_progress.json')
    progress = read(p)
    own = progress['jointArchitecture20261115']['overnightExecution20261116']
    own['rocmDriverAlignment20261117'] = {'receipt': str(target), 'state': report['state'],
                                        'rootCauseIdentified': False, 'driverChanged': False}
    progress['at'] = at
    progress['next'] = progress['next'].replace('先沿compute-only-trigger-review定位兼容栈单变量条件',
        '兼容性已有具体对照差异：ROCm10官方列26.8.1，现驱动属26.6.4；OS25H2与包内10.0版本一致，未证明nightly/混装/根因。仅在GPU接回且完整备好签名包与回退、Owner同意图形驱动动作后考虑单变量对照，不自动升级')
    progress['logResult'] += '\n\n' + at + '｜按ROCm10.0实际版本收敛GPU兼容性：只读确认Win11 25H2/build26200.8875、WOOKING X14 Pro，torch2.11+ROCm10.0各组件版本一致，3个缓存wheel与已装METADATA核对一致，未导入torch/初始化GPU。版本专属官方矩阵列Win25H2/Adrenalin26.8.1；本机两驱动号都属于26.6.4，26.8.1确有RX6800图形驱动支持及不同驱动分支，但矩阵未单列RX6800XT/USB4组合，不能承诺升级修复。修正此前宽泛“开发版”表述：TheRock发布stable10.0与nightly，本地10.0字符串/文件wheel来源不能证明nightly；Windows成熟度警告仍不是本次根因证明。保留明确单变量候选及签名包/OEM/回退/Owner图形驱动授权前置，本轮未下载/安装图形驱动、0神经调用0更新。结果' + str(target) + '。\n'
    p.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(target), 'findings': report['findings']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
