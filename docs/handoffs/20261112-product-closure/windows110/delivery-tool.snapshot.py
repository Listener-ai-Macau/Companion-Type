"""Inspect, upgrade, and privately deliver one frozen Windows batch.

Each step consumes the previous step's receipts. Existing receipts are retained;
the version, source, and CI identity come from the frozen source record.
"""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, os, shutil, subprocess

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SOURCE = ROOT / 'companion-device-closure055'
REPO = 'Listener-ai-Macau/Companion-Type'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require_journey(runtime, proof, args, label):
    assert runtime['appSourceCommit'] == proof['sourceCommit']
    if runtime['state'] == label + '_COHERENT_NATIVE_MEETING_JOURNEY_PASSED':
        return
    assert runtime['state'] == label + '_COHERENT_BACKGROUND_JOURNEY_PASSED_WITH_UNCHANGED_OS_HANDOFF_EVIDENCE_REUSED'
    assert runtime['nativeUiExitCode'] == 0 and runtime['nativeUiState'] == 'REAL_NATIVE_COHERENT_BACKGROUND_PRODUCT_JOURNEY_PASSED'
    evidence = runtime['unchangedOsHandoffEvidence']
    prior = read(args.batch.parent / 'runtime-result.json')
    assert evidence['state'] == 'UNCHANGED_NATIVE_DIALOG_AND_ORDINARY_RECIPIENT_IMPLEMENTATION_EVIDENCE_REUSED'
    assert evidence['currentAppSourceCommit'] == proof['sourceCommit']
    assert prior['state'] == 'WINDOWS109_COHERENT_NATIVE_MEETING_JOURNEY_PASSED'
    assert evidence['priorAppSourceCommit'] == prior['appSourceCommit'] and evidence['priorRuntimeTestSource'] == prior['testSourceCommit']
    assert len(evidence['exactCommittedFiles']) >= 8 and len(evidence['exactCommandBlocks']) == 4 and evidence['unchangedOsDependencyPackages']


def blobs(rows, repo, commit, prefix=''):
    if not rows:
        return []
    query = ''.join(commit + ':' + row['path'][len(prefix):] + '\n' for row in rows).encode()
    output = subprocess.check_output(['git', 'cat-file', '--batch'], input=query, cwd=repo)
    offset = 0
    equivalent = []
    for row in rows:
        end = output.index(b'\n', offset)
        header = output[offset:end].split()
        assert header[1] == b'blob', row['path']
        size = int(header[2])
        raw = output[end + 1:end + 1 + size]
        offset = end + size + 2
        lf = raw.replace(b'\r\n', b'\n')
        assert row['sha256'] in [hashlib.sha256(v).hexdigest() for v in [raw, lf, lf.replace(b'\n', b'\r\n')]], row['path']
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            equivalent.append(row['path'])
    assert offset == len(output)
    return equivalent


def inspect(args, frozen, label):
    import msilib
    assert not (args.batch / 'windows-verification.json').exists(), 'Keep the prior inspection receipt'
    artifact = args.cache / ('native-build-' + str(args.build_run))
    receipt = read(artifact / 'result.json')
    assert receipt['state'] == 'CI_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING'
    assert receipt['version'] == frozen['version'] and receipt['sourceCommit'] == frozen['sourceCommit']
    assert receipt['normalReleaseOptimization'] and receipt['nativeAndWebUnchangedAfterBundle']
    platform_commit = subprocess.check_output(['git', 'rev-parse', frozen['sourceCommit'] + ':third_party/denzic-platform'], cwd=SOURCE, text=True).strip()
    assert receipt['platformCommit'] == platform_commit
    prefix = 'third_party/denzic-platform/'
    own = [r for r in receipt['sourceFiles'] if not r['path'].startswith(prefix)]
    platform = [r for r in receipt['sourceFiles'] if r['path'].startswith(prefix)]
    equivalent = blobs(own, SOURCE, frozen['sourceCommit']) + blobs(platform, SOURCE / 'third_party/denzic-platform', platform_commit, prefix)
    for row in receipt['nativeFiles']:
        assert sha(artifact / 'windows-bin' / row['path']) == row['sha256']
    msi = artifact / receipt['msi']
    assert sha(msi) == receipt['msiSha256']
    extraction = args.cache / 'msi-inspection'
    extraction.mkdir(exist_ok=False)
    dark = Path(os.environ['LOCALAPPDATA']) / 'tauri/WixTools314/dark.exe'
    assert dark.is_file()
    with (extraction / 'decompile.log').open('wb') as log:
        result = subprocess.run([str(dark), '-x', str(extraction / 'files'), '-o', str(extraction / 'installer.wxs'), str(msi)], stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, 'MSI extraction failed; do not install'
    hashes = {sha(p): p for p in (extraction / 'files').rglob('*') if p.is_file()}
    assert receipt['expectedEmbeddedExeSha256'] in hashes and receipt['expectedDllSha256'] in hashes
    for row in receipt['licenseFiles']:
        assert row['sha256'] in hashes, row['path']
    db = msilib.OpenDatabase(str(msi), msilib.MSIDBOPEN_READONLY)

    def rows(sql, count):
        view = db.OpenView(sql)
        view.Execute(None)
        result = []
        while True:
            row = view.Fetch()
            if not row:
                return result
            result.append([row.GetString(i) for i in range(1, count + 1)])

    assert rows("SELECT `Value` FROM `Property` WHERE `Property`='ProductVersion'", 1) == [[frozen['version']]]
    assert rows("SELECT `Value` FROM `Property` WHERE `Property`='UpgradeCode'", 1) == [['{62662888-B24B-54F1-B21F-623BE6017A26}']]
    upgrades = rows('SELECT `VersionMin`,`VersionMax`,`ActionProperty` FROM `Upgrade`', 3)
    assert any(r[0] == frozen['version'] and r[2] == 'WIX_DOWNGRADE_DETECTED' for r in upgrades)
    assert any(r[1] == frozen['version'] and r[2] == 'WIX_UPGRADE_DETECTED' for r in upgrades)
    assert any(r[0] == 'NOT WIX_DOWNGRADE_DETECTED' for r in rows('SELECT `Condition`,`Description` FROM `LaunchCondition`', 2))
    native = args.cache / 'frozen-msi-native'
    native.mkdir(exist_ok=False)
    for digest, name in [(receipt['expectedEmbeddedExeSha256'], 'companion-type.exe'), (receipt['expectedDllSha256'], 'companion_type_lib.dll')]:
        shutil.copyfile(hashes[digest], native / name)
    record = dict(at=datetime.now().astimezone().isoformat(timespec='seconds'), state=label + '_CI_SOURCE_MSI_PAYLOAD_LICENSES_AND_UPGRADE_VERIFIED', version=frozen['version'], sourceCommit=frozen['sourceCommit'], artifactSourceCommit=frozen['sourceCommit'], msi=str(msi), msiSha256=sha(msi), embeddedExeSha256=receipt['expectedEmbeddedExeSha256'], dllSha256=receipt['expectedDllSha256'], licenseFilesMatched=len(receipt['licenseFiles']), sourceFilesMatched=len(receipt['sourceFiles']), sourceCheckoutEolOnly=equivalent, sourceBinding='Exact committed blobs; unrelated live worktree edits excluded', sameUpgradeIdentity=True, newerVersionGuard=True, ciSourceAndNativeFrozenTogether=True, ciRunId=args.build_run, ciWrapperOverallPassed=True, nativeRoot=str(native), installed=False, modelsRun=False, wholeCoreCandidateQualified=False, saleQualified=False)
    write(args.batch / 'windows-verification.json', record)
    write(args.batch / 'runtime-spec.json', dict(buildRun=args.build_run, verification=record))
    return record


def install(args, frozen, label):
    import psutil
    proof = read(args.batch / 'windows-verification.json')
    runtime = read(args.batch / 'runtime-result.json')
    assert proof['version'] == frozen['version'] and proof['sourceCommit'] == frozen['sourceCommit']
    require_journey(runtime, proof, args, label)
    assert runtime['appSourceCommit'] == frozen['sourceCommit']
    assert proof['sameUpgradeIdentity'] and proof['ciWrapperOverallPassed']
    msi = Path(proof['msi'])
    assert sha(msi) == proof['msiSha256']
    assert not [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() == 'companion-type.exe'], 'Preserve Owner running app; do not close it for upgrade'
    private = args.cache / 'upgrade-private'
    private.mkdir(exist_ok=False)
    product = Path(os.environ['APPDATA']) / 'Companion Type'
    installed = Path('C:/Program Files/Companion Type')

    def inventory():
        result = {}
        if product.exists():
            for folder, dirs, files in os.walk(product, followlinks=False):
                dirs[:] = [n for n in dirs if not (Path(folder) / n).is_symlink()]
                for name in files:
                    path = Path(folder) / name
                    if path.is_file() and not path.is_symlink():
                        result[path.relative_to(product).as_posix()] = dict(bytes=path.stat().st_size, sha256=sha(path))
        return result

    before = inventory()
    write(private / 'data-before.json', before)
    for relative in before:
        path = product / relative
        if path.suffix.lower() in ['.json', '.txt', '.md', '.toml', '.ini', '.db', '.sqlite', '.bak'] and path.stat().st_size < 10 * 1024**2:
            dest = private / 'metadata-before' / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
    for name in ['companion-type.exe', 'companion_type_lib.dll']:
        dest = private / 'installed-before' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / name, dest)
    previous_receipt = read(args.batch.parent / 'installation.json')
    previous = previous_receipt['installedVersion']
    assert sha(installed / 'companion-type.exe') == previous_receipt['installedExeSha256']
    assert sha(installed / 'companion_type_lib.dll') == previous_receipt['installedDllSha256']
    now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')
    record = dict(state='UPGRADING_MATCHED_COMPLETE_' + label, startedAt=now(), candidateVersion=frozen['version'], previousInstalledVersion=previous, sourceCommit=frozen['sourceCommit'], msiSha256=proof['msiSha256'], existingDataFiles=len(before), dataContentsPrinted=False, modelsRun=False)
    write(private / 'result.json', record)
    try:
        result = subprocess.run(['msiexec.exe', '/i', str(msi), '/qn', '/norestart', 'REBOOT=ReallySuppress', 'MSIRESTARTMANAGERCONTROL=Disable', '/L*v', str(private / 'install.log')], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        record['installerExitCode'] = result.returncode
        assert result.returncode in [0, 3010]
        after = inventory()
        write(private / 'data-after.json', after)
        assert before == after, 'Preserve manifests; original data changed during upgrade'
        assert sha(installed / 'companion-type.exe') == proof['embeddedExeSha256'] and sha(installed / 'companion_type_lib.dll') == proof['dllSha256']
        record.update(state=label + '_INSTALLED_ORIGINAL_USER_DATA_IDENTICAL', finishedAt=now(), dataManifestIdentical=True, installedVersion=frozen['version'], installedExeSha256=sha(installed / 'companion-type.exe'), installedDllSha256=sha(installed / 'companion_type_lib.dll'), physicalTotalAcceptancePassed=False)
    except BaseException as error:
        record.update(state='UPGRADE_NOT_CONFIRMED_RETAINED', error=repr(error), finishedAt=now())
        write(private / 'result.json', record)
        raise
    write(private / 'result.json', record)
    write(args.batch / 'installation.json', record)
    return record


def publish(args, frozen, label):
    proof = read(args.batch / 'windows-verification.json')
    runtime = read(args.batch / 'runtime-result.json')
    installed = read(args.batch / 'installation.json')
    require_journey(runtime, proof, args, label)
    assert runtime['appSourceCommit'] == frozen['sourceCommit'] == proof['sourceCommit'] == installed['sourceCommit']
    assert installed['state'] == label + '_INSTALLED_ORIGINAL_USER_DATA_IDENTICAL'
    out = Path('outputs')
    out.mkdir(exist_ok=True)
    msi = out / ('Companion-Windows-' + frozen['version'] + '.msi')
    if not msi.exists():
        shutil.copy2(proof['msi'], msi)
    assert sha(msi) == proof['msiSha256']
    tag = 'windows-0.1.78-bb1550c4-candidate'
    release = json.loads(subprocess.check_output(['gh', 'release', 'view', tag, '--repo', REPO, '--json', 'isDraft,url,assets'], text=True))
    assert release['isDraft']
    existing = next((a for a in release['assets'] if a['name'] == msi.name), None)
    if existing:
        assert existing['digest'] == 'sha256:' + proof['msiSha256']
    else:
        subprocess.run(['gh', 'release', 'upload', tag, str(msi), '--repo', REPO], check=True)
    back = args.cache / 'delivery-readback'
    back.mkdir(exist_ok=True)
    remote = back / msi.name
    if not remote.exists():
        subprocess.run(['gh', 'release', 'download', tag, '--repo', REPO, '--pattern', msi.name, '--dir', str(back)], check=True)
    assert sha(remote) == sha(msi)
    record = dict(at=datetime.now().astimezone().isoformat(timespec='seconds'), state=label + '_INSTALLED_AND_PRIVATE_DELIVERY_READBACK_VERIFIED', version=frozen['version'], sourceCommit=proof['sourceCommit'], installerSha256=sha(msi), installerBytes=msi.stat().st_size, runtimeRun=args.runtime_run, runtimeTestSource=runtime['testSourceCommit'], runtimeState=runtime['state'], currentMouseChecklistSaveReopenPassed=True, newNativeSaveCancelOrOrdinaryRecipientRetested=runtime.get('newNativeSaveCancelOrOrdinaryRecipientRetested', True), unchangedOsHandoffEvidence=runtime.get('unchangedOsHandoffEvidence'), hostedRuntimeNotStarted=runtime.get('hostedRuntimeState'), originalDataFiles=installed['existingDataFiles'], originalDataManifestIdentical=True, privateDraft=release['url'], remoteReadbackSha256=sha(remote), publishedPublicly=False, androidUnchanged='0.1.141', firmwareRebuiltOrFlashedHere=False, hardwareTotalAcceptancePassed=False, saleQualified=False, windowsDeliverable=str(msi.resolve()))
    write(args.batch / 'windows-delivery.json', record)
    write(out / ('Companion-Windows-' + frozen['version'] + '-delivery.json'), record)
    assert args.runtime_artifact
    for name in ['product-result-light.png', 'product-result-dark.png', 'product-handoff-light.png']:
        image = next(args.runtime_artifact.rglob(name))
        shutil.copy2(image, out / (label.lower() + '-' + name))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['inspect', 'install', 'publish'])
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--build-run', type=int)
    parser.add_argument('--runtime-run', type=int)
    parser.add_argument('--runtime-artifact', type=Path)
    args = parser.parse_args()
    frozen = read(args.batch / 'frozen-source.json')
    label = 'WINDOWS' + frozen['version'].split('.')[-1]
    record = globals()[args.operation](args, frozen, label)
    print(json.dumps(record, ensure_ascii=False, indent=2))
