"""Prepare read-only rollback/package evidence; never install or launch the installer."""
from pathlib import Path, PureWindowsPath
from datetime import datetime
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

S = Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
sys.path.insert(0, str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json

OUT = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/system-restart-20261116-2315/graphics-driver-comparison-prepared-r1')
URL = 'https://drivers.amd.com/drivers/whql-amd-software-adrenalin-edition-26.8.1-win11-c.exe'
SOURCE = 'https://www.amd.com/en/resources/support-articles/release-notes/RN-RAD-WIN-26-8-1.html'
EXPECTED_BYTES = 1669192200
SEVEN = Path('C:/Program Files/7-Zip/7z.exe')
sha = lambda p: hashlib.file_digest(Path(p).open('rb'), 'sha256').hexdigest()


def powershell(code, timeout=45):
    raw = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                          '-NoProfile', '-NonInteractive', '-EncodedCommand',
                          base64.b64encode(code.encode('utf-16-le')).decode()],
                         capture_output=True, encoding='utf-8', timeout=timeout)
    if raw.returncode:
        raise RuntimeError('Read-onlyPowerShell failed: ' + raw.stderr[:2000])
    return json.loads(raw.stdout.lstrip('\ufeff'))


def main():
    assert not OUT.exists(), 'One isolated preparation only; inspect existing state instead of restarting.'
    assert shutil.disk_usage('E:/').free >= 56 * 1024 ** 3
    OUT.mkdir(parents=True)
    limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024 ** 2)
    state = {'state': 'PREPARING_GRAPHICS_DRIVER_COMPARISON_FILES_ONLY',
             'at': datetime.now().astimezone().isoformat(), 'pid': os.getpid(),
             'createdAt': __import__('psutil').Process().create_time(),
             'installerExecuted': False, 'driverRegisteredOrChanged': False,
             'newNeuralCalls': 0, 'newGpuCalls': 0, 'parameterUpdates': 0,
             'source': SOURCE, 'downloadUrl': URL, 'expectedDownloadBytes': EXPECTED_BYTES,
             'limits': limits.query()}

    def save(**values):
        state.update(values, observedAt=datetime.now().astimezone().isoformat(), limits=limits.query())
        atomic_json(OUT / 'state.json', state, progress=True)

    try:
        save()
        ps = """
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$out=@()
foreach($d in Get-PnpDevice -Class Display){
 if($d.FriendlyName -match '6800|780M'){
  $r=[ordered]@{name=$d.FriendlyName;status=$d.Status;instanceId=$d.InstanceId}
  foreach($k in @('DEVPKEY_Device_DriverInfPath','DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverProvider','DEVPKEY_Device_IsPresent')){
   $r[$k]=(Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName $k -ErrorAction Stop).Data
  };$out+=$r
 }
};$out|ConvertTo-Json -Depth 4 -Compress
"""
        devices = powershell(ps)
        assert isinstance(devices, list)
        infs = sorted({d['DEVPKEY_Device_DriverInfPath'] for d in devices})
        assert infs == ['oem0.inf', 'oem1.inf'], 'Do not export guessed or unrelated driver packages.'
        assert all(not d['DEVPKEY_Device_IsPresent'] for d in devices if '6800' in d['name'])
        atomic_json(OUT / 'devices-before.json', {'devices': devices})
        backup = OUT / 'existing-driver-export';backup.mkdir()
        exports = []
        for inf in infs:
            target = backup / Path(inf).stem;target.mkdir()
            save(operation='EXPORT_EXISTING_DRIVER_FILES_' + inf)
            result = subprocess.run(['C:/Windows/System32/pnputil.exe', '/export-driver', inf, str(target)],
                                    capture_output=True, timeout=120)
            (OUT / (inf + '-export-output.bin')).write_bytes(result.stdout + result.stderr)
            entries = []
            for path in target.rglob('*'):
                if path.is_file():
                    entries.append({'file': path.relative_to(target).as_posix(),
                                    'bytes': path.stat().st_size, 'sha256': sha(path)})
            exports.append({'publishedInf': inf, 'exitCode': result.returncode,
                            'files': entries, 'totalBytes': sum(r['bytes'] for r in entries)})
            atomic_json(OUT / 'existing-driver-export.json', {'exports': exports,
                'driverInstallationOrRemovalPerformed': False,
                'restorationActuallyTested': False})
            if result.returncode or not entries:
                save(state='STOPPED_DRIVER_EXPORT_FAILED_NO_INSTALL_OR_DOWNLOAD', exports=exports)
                atomic_json(OUT / 'completed.json', state);return

        package = OUT / 'whql-amd-software-adrenalin-edition-26.8.1-win11-c.exe'
        save(operation='DOWNLOADING_ONE_OFFICIAL_CANDIDATE', bytesDownloaded=0)
        with (OUT / 'download.log').open('wb') as log:
            process = subprocess.Popen(['curl.exe', '--location', '--fail', '--silent', '--show-error',
                '--connect-timeout', '12', '--max-time', '900', '--max-filesize', str(EXPECTED_BYTES),
                '--limit-rate', '8M', '--referer', SOURCE, '--dump-header', str(OUT / 'download-headers.txt'),
                '--output', str(package), URL], stdout=log, stderr=log,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            state['downloadPid'] = process.pid
            while process.poll() is None:
                if shutil.disk_usage(OUT).free < 50 * 1024 ** 3:
                    process.terminate();raise RuntimeError('Original50GiB free-disk reserve reached')
                if (OUT / 'stop.request').exists():
                    process.terminate();raise RuntimeError('Owned preparation stop requested')
                save(bytesDownloaded=package.stat().st_size if package.exists() else 0)
                time.sleep(5)
            assert process.returncode == 0, 'Official download failed; no automatic retry.'
        assert package.stat().st_size == EXPECTED_BYTES
        with package.open('rb') as f:
            assert f.read(2) == b'MZ', 'Received a web error page instead ofPE package.'
        save(operation='VERIFYING_EXACT_PACKAGE_SIGNATURE_AND_HASH', bytesDownloaded=EXPECTED_BYTES)
        signature = powershell("$s=Get-AuthenticodeSignature -LiteralPath '" + str(package).replace("'", "''") + "';"
            "[ordered]@{status=$s.Status.ToString();subject=$s.SignerCertificate.Subject;"
            "thumbprint=$s.SignerCertificate.Thumbprint;timestampSubject=$s.TimeStamperCertificate.Subject}"
            "|ConvertTo-Json -Compress", timeout=120)
        assert signature['status'] == 'Valid' and 'Advanced Micro Devices' in signature['subject']
        package_sha = sha(package)
        save(operation='READING_DISPLAY_INF_FILES_WITHOUT_RUNNING_INSTALLER', packageSha256=package_sha,
             authenticode=signature)
        listing = subprocess.run([str(SEVEN), 'l', '-slt', str(package)], capture_output=True, timeout=120)
        assert listing.returncode == 0, 'Archive listing failed; do not execute package to extract.'
        (OUT / 'package-listing.txt').write_bytes(listing.stdout)
        archive_paths = [line[7:] for line in listing.stdout.decode('utf-8', 'replace').splitlines()
                         if line.startswith('Path = ')]
        candidates = [p for p in archive_paths if '/drivers/display/' in p.replace('\\', '/').lower()
                      and p.lower().endswith('.inf')]
        assert 0 < len(candidates) <= 30
        inf_dir = OUT / 'display-inf-inspection-only';inf_dir.mkdir()
        inspected = []
        for index, original in enumerate(candidates):
            path = PureWindowsPath(original)
            assert not path.is_absolute() and '..' not in path.parts
            # Stream a single exact member to stdout, so archive paths cannot write outsideOUT.
            extracted = subprocess.run([str(SEVEN), 'e', '-so', str(package), original],
                                       capture_output=True, timeout=120)
            assert extracted.returncode == 0 and len(extracted.stdout) < 8 * 1024 ** 2
            raw = extracted.stdout
            text = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8-sig')
            f = inf_dir / (format(index, '02d') + '-' + path.name);f.write_bytes(raw)
            matched = {device: [line.strip() for line in text.splitlines()
                               if ('VEN_1002&DEV_' + device) in line.upper()]
                       for device in ['73BF', '15BF']}
            versions = [line.strip() for line in text.splitlines() if line.strip().lower().startswith('driverver')]
            inspected.append({'archiveMember': original, 'inspectionFile': str(f),
                              'bytes': len(raw), 'sha256': sha(f), 'driverVerLines': versions,
                              'matchingDeviceLines': matched})
        atomic_json(OUT / 'candidate-display-inf.json', {'files': inspected,
            'originalArchivePathsUsedOnlyAsMemberSelectors': True, 'infInstalled': False})
        has_rx = any(v['matchingDeviceLines']['73BF'] for v in inspected)
        has_apu = any(v['matchingDeviceLines']['15BF'] for v in inspected)
        assert has_rx and has_apu, 'Candidate must match both externalRX6800XT and internal780M devices.'
        save(state='PREPARED_SIGNED_CANDIDATE_AND_EXPORTED_EXISTING_DRIVERS_NOT_INSTALLED',
             operation=None, exportsSummary=[{k:v for k,v in row.items() if k != 'files'} for row in exports],
             candidateDeviceMatches={'rx6800xt': has_rx, 'radeon780m': has_apu},
             rollbackFilesExported=True, rollbackRestorationTested=False,
             graphicsDriverInstallationAuthorized=False,
             gpuStillDisconnectedAtStart=True,
             wholeStackStabilityProven=False, qualityQualified=False, saleQualified=False)
        atomic_json(OUT / 'completed.json', state)
        print(json.dumps({'state': state['state'], 'output': str(OUT), 'packageSha256': package_sha,
                          'matches': state['candidateDeviceMatches']}, ensure_ascii=False))
    except BaseException as error:
        import traceback
        save(state='FAILED_DRIVER_COMPARISON_PREPARATION_NO_INSTALL_NO_AUTOMATIC_RETRY',
             error=repr(error), traceback=traceback.format_exc())
        atomic_json(OUT / 'completed.json', state)
        raise


if __name__ == '__main__':
    main()
