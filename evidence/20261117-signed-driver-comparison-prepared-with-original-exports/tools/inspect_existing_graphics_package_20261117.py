"""Inspect both AMD display branches from the existing signed package, without install."""
from pathlib import Path, PureWindowsPath
from datetime import datetime
import base64
import hashlib
import json
import os
import re
import subprocess
import sys

S = Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
sys.path.insert(0, str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json

ROOT = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/system-restart-20261116-2315/graphics-driver-comparison-prepared-r1')
OUT = ROOT / 'inspection-r2'
PACKAGE = ROOT / 'whql-amd-software-adrenalin-edition-26.8.1-win11-c.exe'
SEVEN = 'C:/Program Files/7-Zip/7z.exe'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def ps(code):
    p = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
        '-NoProfile', '-NonInteractive', '-EncodedCommand', base64.b64encode(code.encode('utf-16-le')).decode()],
        capture_output=True, encoding='utf-8', timeout=60)
    assert p.returncode == 0, p.stderr[:2000]
    return json.loads(p.stdout.lstrip('\ufeff'))


def main():
    old = read(ROOT / 'completed.json')
    assert old['state'] == 'FAILED_DRIVER_COMPARISON_PREPARATION_NO_INSTALL_NO_AUTOMATIC_RETRY'
    assert 'Candidate must match both' in old['error']
    assert old['authenticode']['status'] == 'Valid'
    assert not OUT.exists()
    OUT.mkdir()
    limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024 ** 2)
    state = {'state': 'INSPECTING_BOTH_EXISTING_AMD_DISPLAY_BRANCHES_WITHOUT_INSTALL',
             'at': datetime.now().astimezone().isoformat(), 'pid': os.getpid(),
             'createdAt': __import__('psutil').Process().create_time(),
             'priorFailedPreparationPreserved': str(ROOT / 'completed.json'),
             'newDownloadRequests': 0, 'driverInstalledOrRemoved': False,
             'newNeuralCalls': 0, 'newGpuCalls': 0, 'parameterUpdates': 0}

    def save(**v):
        state.update(v, observedAt=datetime.now().astimezone().isoformat(), limits=limits.query())
        atomic_json(OUT / 'state.json', state, progress=True)

    try:
        save(operation='VERIFY_EXISTING_PACKAGE_UNCHANGED')
        assert PACKAGE.stat().st_size == old['expectedDownloadBytes']
        assert sha(PACKAGE) == old['packageSha256']
        devices = ps("""
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$r=@()
foreach($d in Get-PnpDevice -Class Display){if($d.FriendlyName -match '6800|780M'){
 $row=[ordered]@{name=$d.FriendlyName;instanceId=$d.InstanceId}
 foreach($k in @('DEVPKEY_Device_HardwareIds','DEVPKEY_Device_CompatibleIds')){
  $row[$k]=@((Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName $k -ErrorAction Stop).Data)
 };$r+=$row
}};$r|ConvertTo-Json -Depth 5 -Compress
""")
        atomic_json(OUT / 'actual-device-identifiers.json', {'devices': devices})
        actual = {name: {identifier.upper() for d in devices if name in d['name']
                        for key in ['DEVPKEY_Device_HardwareIds', 'DEVPKEY_Device_CompatibleIds']
                        for identifier in d[key]} for name in ['6800', '780M']}
        assert all(actual.values())
        lines = (ROOT / 'package-listing.txt').read_text(encoding='utf-8', errors='replace').splitlines()
        entries = [line[7:] for line in lines if line.startswith('Path = ')]
        # AMD packages contain Display and Display2. Inspect each branch's root
        # display INF, not just the first branch or unrelated extension INFs.
        selected = [n for n in entries if re.fullmatch(r'Packages[\\/]Drivers[\\/]Display\d*[\\/]WT6A_INF[\\/][^\\/]+\.inf', n, re.I)]
        assert len(selected) == 2
        extracted = []

        def extract(member):
            p = PureWindowsPath(member)
            assert not p.is_absolute() and '..' not in p.parts and member in entries
            result = subprocess.run([SEVEN, 'e', '-so', str(PACKAGE), member], capture_output=True, timeout=120)
            assert result.returncode == 0 and len(result.stdout) < 8 * 1024 ** 2
            branch = next(v for v in p.parts if re.fullmatch(r'Display\d*', v, re.I))
            target = OUT / (branch + '-' + p.name)
            target.write_bytes(result.stdout)
            return target, result.stdout

        for member in selected:
            save(operation='READ_DISPLAY_BRANCH', member=member)
            file, raw = extract(member)
            text = raw.decode('utf-16' if raw[:2] in [b'\xff\xfe', b'\xfe\xff'] else 'utf-8-sig')
            ids = {v.upper() for v in re.findall(r'PCI\\VEN_1002&[^\s,;\"]+', text, re.I)}
            matches = {name: sorted(ids & values) for name, values in actual.items()}
            versions = [line.strip() for line in text.splitlines() if line.strip().lower().startswith('driverver')]
            catalog_names = re.findall(r'^\s*CatalogFile[^=]*=\s*([^;\r\n]+)', text, re.I | re.M)
            cats = []
            for name in sorted({v.strip() for v in catalog_names}):
                member_cat = str(PureWindowsPath(member).parent / name)
                cat_file, _ = extract(member_cat)
                signature = ps("$s=Get-AuthenticodeSignature -LiteralPath '" + str(cat_file).replace("'", "''") + "';"
                    "[ordered]@{status=$s.Status.ToString();subject=$s.SignerCertificate.Subject;"
                    "thumbprint=$s.SignerCertificate.Thumbprint}|ConvertTo-Json -Compress")
                assert signature['status'] == 'Valid'
                cats.append({'archiveMember': member_cat, 'file': str(cat_file),
                             'sha256': sha(cat_file), 'signature': signature})
            extracted.append({'archiveMember': member, 'file': str(file), 'sha256': sha(file),
                              'driverVerLines': versions, 'exactHardwareOrCompatibleIdMatches': matches,
                              'catalogs': cats})
            atomic_json(OUT / 'display-branch-inspection.json', {'files': extracted})
        matched = {name: any(row['exactHardwareOrCompatibleIdMatches'][name] for row in extracted)
                   for name in actual}
        assert all(matched.values())
        save(state='PASS_SIGNED_CANDIDATE_BOTH_ACTUAL_GPU_DEVICE_IDS_AND_EXPORTED_ROLLBACK_FILES_NOT_INSTALLED',
             operation=None, packageSha256=old['packageSha256'], packageSignature=old['authenticode'],
             candidateActualDeviceIdMatches=matched,
             preparationBug='The first inspection selected Display but omitted the separate Display2 branch. It was not evidence that AMD26.8.1 lacks RX6800XT support.',
             rollbackFilesExported=True, rollbackActuallyTested=False,
             installerExecuted=False, graphicsDriverInstallationAuthorized=False,
             gpuComputeStabilityProven=False, qualityQualified=False, saleQualified=False)
        atomic_json(OUT / 'completed.json', state)
        print(json.dumps({'state': state['state'], 'matches': matched, 'output': str(OUT)}, ensure_ascii=False))
    except BaseException as error:
        import traceback
        save(state='FAILED_OFFLINE_BRANCH_INSPECTION_NO_INSTALL_NO_AUTOMATIC_RETRY',
             error=repr(error), traceback=traceback.format_exc())
        atomic_json(OUT / 'completed.json', state)
        raise


if __name__ == '__main__':
    main()
