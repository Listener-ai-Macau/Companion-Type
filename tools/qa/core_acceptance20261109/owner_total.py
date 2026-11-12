"""One continuous Owner acceptance using the original shared Denzic window.

--prepare is read-only. --run opens the original prompt only after the installed
candidate and the current repair workpoint are ready. No MIC or firmware command,
UI automation, background mutable-index read, or automatic whole-product PASS.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse, hashlib, json, os, re, subprocess, time
import psutil

TZ = timezone(timedelta(hours=8))
START = '开始整体验收'
APP_NAME = 'companion-type.exe'
BOARD_BUSY = 'Shared board is currently occupied; do not interrupt its actual operation.'
ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
PRODUCT_PATHS = ('apps/windows/src/', 'apps/windows/src-tauri/', 'packages/ui/src/',
                 'packages/core/src/', 'packages/desktop-input/', 'third_party/imu-pointer/')
APP_ENV = ('COMPANION_TYPE_STATE_PATH', 'COMPANION_TYPE_STATE_DIR',
           'COMPANION_TYPE_RECORDING_DIR', 'COMPANION_TYPE_PRODUCT_SETTINGS_PATH',
           'COMPANION_TYPE_TRANSCRIPT_TEXT', 'COMPANION_TYPE_ASR_COMMAND',
           'COMPANION_TYPE_DISABLE_AUTO_RECOVERY', 'COMPANION_TYPE_DISABLE_AUTO_RECONNECT',
           'COMPANION_TYPE_BLE_NATIVE_DISABLED', 'COMPANION_TYPE_BACKGROUND_WINDOW',
           'WEBVIEW2_USER_DATA_FOLDER', 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS')


def now():
    return datetime.now(TZ).isoformat(timespec='milliseconds')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def app_pids():
    return [p.pid for p in psutil.process_iter(['name'])
            if (p.info['name'] or '').lower() == APP_NAME]


def start_requested(events, prompt_pid):
    """Only the actual auxiliary-button event grants readiness, never its text."""
    for line in events.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue  # A trailing append may still be incomplete.
        if event.get('event') == 'action_button|' + START and event.get('processId') == prompt_pid:
            return True
    return False


def only_board_blocked(readiness):
    return not readiness.get('ready') and readiness.get('blockers') == [BOARD_BUSY]


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (TypeError, AttributeError, ValueError):
        return None


def physical_facts(before_ids, rows, owner_started, closed_at):
    """Report actual metadata, not accuracy, continuity, or hardware qualification."""
    start, end = timestamp(owner_started), timestamp(closed_at)
    facts = []
    for row in rows:
        if row.get('id') in before_ids or row.get('source') != 'deviceFlash' or not row.get('deviceRecordingKey'):
            continue
        duration = row.get('durationMs')
        valid_duration = type(duration) is int and duration >= 0
        recorded_start = timestamp(row.get('startedAt'))
        during = bool(start is not None and end is not None and recorded_start is not None
                      and start - 2 <= recorded_start <= end
                      and valid_duration and duration <= (end - recorded_start + 30) * 1000)
        facts.append(dict(id=row['id'], deviceRecordingKey=row['deviceRecordingKey'],
                          durationMs=duration if valid_duration else None,
                          audioStored=row.get('audioStored') is True,
                          transcriptFinal=row.get('transcriptFinal') is True,
                          transcriptCharacters=len(row.get('transcriptText') or ''),
                          captureIncomplete=row.get('captureIncomplete'),
                          beganDuringOwnerWindow=during))
    return facts


def prepare(project, batch, installed_dir):
    blockers = []
    verification = json.loads((batch / 'windows-verification.json').read_text(encoding='utf-8'))
    installation = json.loads((batch / 'installation.json').read_text(encoding='utf-8'))
    runtime = json.loads((batch / 'runtime-result.json').read_text(encoding='utf-8'))
    version = verification['version']
    if not re.fullmatch(r'0\.1\.\d+', version):
        blockers.append('Candidate version is not a known Windows product version.')
    if runtime.get('appVersion') != version or runtime.get('appSourceCommit') != verification['sourceCommit']:
        blockers.append('Native journey and inspected candidate do not match.')
    direct_journey = runtime.get('nativeUiState') == 'REAL_NATIVE_COHERENT_PRODUCT_JOURNEY_PASSED'
    scoped_journey = False
    if runtime.get('nativeUiState') == 'REAL_NATIVE_COHERENT_BACKGROUND_PRODUCT_JOURNEY_PASSED':
        reused = runtime.get('unchangedOsHandoffEvidence', {})
        prior_path = batch.parent / 'runtime-result.json'
        prior = json.loads(prior_path.read_text(encoding='utf-8')) if prior_path.is_file() else {}
        scoped_journey = (runtime.get('state') == 'WINDOWS' + version.split('.')[-1] + '_COHERENT_BACKGROUND_JOURNEY_PASSED_WITH_UNCHANGED_OS_HANDOFF_EVIDENCE_REUSED'
            and reused.get('state') == 'UNCHANGED_NATIVE_DIALOG_AND_ORDINARY_RECIPIENT_IMPLEMENTATION_EVIDENCE_REUSED'
            and reused.get('currentAppSourceCommit') == verification['sourceCommit']
            and prior.get('state') == 'WINDOWS109_COHERENT_NATIVE_MEETING_JOURNEY_PASSED'
            and reused.get('priorAppSourceCommit') == prior.get('appSourceCommit')
            and reused.get('priorRuntimeTestSource') == prior.get('testSourceCommit')
            and len(reused.get('exactCommittedFiles', [])) >= 8
            and len(reused.get('exactCommandBlocks', [])) == 4
            and bool(reused.get('unchangedOsDependencyPackages')))
    if runtime.get('nativeUiExitCode') != 0 or not (direct_journey or scoped_journey):
        blockers.append('The continuous native software journey has not passed.')
    if installation.get('installedVersion') != version or not installation.get('dataManifestIdentical'):
        blockers.append('Installed version or original-data preservation is not confirmed.')
    for name, expected in [('companion-type.exe', verification['embeddedExeSha256']),
                           ('companion_type_lib.dll', verification['dllSha256'])]:
        path = installed_dir / name
        if not path.is_file() or sha(path) != expected:
            blockers.append('Installed candidate bytes differ: ' + name)
    if app_pids():
        blockers.append('Preserve the current running Owner app; do not start a competing session.')
    source = project / 'companion-device-closure055'
    diff = subprocess.run(['git', '-c', 'core.quotePath=false', 'diff', '--name-only',
                           verification['sourceCommit'], '--', *PRODUCT_PATHS],
                          cwd=source, capture_output=True, text=True, encoding='utf-8')
    if diff.returncode:
        blockers.append('Current product-source difference could not be established.')
    changed = diff.stdout.splitlines()
    untracked = subprocess.run(['git', '-c', 'core.quotePath=false', 'ls-files', '--others',
                                '--exclude-standard', '--', *PRODUCT_PATHS],
                               cwd=source, capture_output=True, text=True, encoding='utf-8', check=True)
    changed = sorted(set(changed + untracked.stdout.splitlines()))
    if changed:
        blockers.append('Product repairs are still in flight or are not in the installed candidate.')
    backlog = json.loads((project / 'docs/product_backlog.json').read_text(encoding='utf-8'))
    active = backlog['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']
    dependency = active['ownerProductClosure20261112'].get('physicalAcceptanceDependency', {})
    if dependency.get('state') in {'WAITING_SHARED_BOARD_FIRMWARE_WORK',
                                  'BOARD_RELEASED_MATCHED_FIRMWARE_RECEIPT_AND_IMU_REPAIR_PENDING'}:
        blockers.append('The known firmware/IMU repair and its matching physical receipt are unfinished.')
    board = json.loads((project / 'docs/board_turn.json').read_text(encoding='utf-8'))
    if board.get('holder') is not None:
        blockers.append(BOARD_BUSY)
    return dict(at=now(), state='READY_FOR_ONE_TOTAL_USE' if not blockers else 'FINISH_CURRENT_BATCH_BEFORE_OWNER_TOTAL_USE',
                ready=not blockers, version=version, sourceCommit=verification['sourceCommit'],
                firmwareVersion=dependency.get('ordinaryFirmwareInstallation', {}).get('firmware'),
                uiVersion=dependency.get('ordinaryFirmwareInstallation', {}).get('ui'),
                installedExeSha256=verification['embeddedExeSha256'],
                installedDllSha256=verification['dllSha256'], blockers=blockers,
                currentProductDifferences=changed, readOnly=True, ownerPromptStarted=False,
                boardClaimed=False, modelsRun=False, hostMicCommands=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=ROOT)
    parser.add_argument('--batch', type=Path)
    parser.add_argument('--installed-dir', type=Path, default=Path('C:/Program Files/Companion Type'))
    parser.add_argument('--output', type=Path, default=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/owner-total'))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--run', action='store_true')
    args = parser.parse_args()
    project = args.project_root.resolve()
    batch = (args.batch or project / 'docs/handoffs/20261112-product-closure').resolve()
    readiness = prepare(project, batch, args.installed_dir)
    if not args.run or not readiness['ready']:
        print(json.dumps(readiness, ensure_ascii=False, indent=2))
        return 0 if readiness['ready'] else 2
    if os.name != 'nt':
        parser.error('Owner normal-product use requires Windows.')
    cache = args.output.resolve()
    cache.mkdir(parents=True, exist_ok=False)  # Never overwrite a previous actual attempt.
    state_path = Path(os.environ['APPDATA']) / 'Companion Type/state/sessions.json'
    if app_pids():
        raise RuntimeError('Owner app opened during preparation; preserve it.')
    before = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else []
    before_ids = {row['id'] for row in before}
    events, updates = cache / 'events.jsonl', cache / 'updates.json'
    stdout = cache / 'prompt-output.json'
    lease_item = 'Companion集中总验收：' + cache.name + ':' + now()
    record = dict(at=now(), state='WAITING_OWNER_START', version=readiness['version'],
                  firmwareVersion=readiness.get('firmwareVersion'), uiVersion=readiness.get('uiVersion'),
                  sourceCommit=readiness['sourceCommit'], controllerPid=os.getpid(),
                  boardLease=False, hostStartCommands=0, privateContentPrinted=False,
                  physicalTotalAcceptancePassed=False, saleQualified=False,
                  softwareOwnerAccepted=False, twoHourRecordingObserved=False)

    def save():
        write_json(cache / 'progress.json', record)

    def update(stage, message, actions=(), review=False):
        write_json(updates, dict(progressText=stage, message=message,
                                enabledActions=list(actions), reviewAllowed=review))

    def board(action, **kwargs):
        command = ['python', str(project / 'tools/board_turn.py'), action, '--side', 'codex']
        for key, value in kwargs.items():
            command += ['--' + key, value]
        result = subprocess.run(command, cwd=project, capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Board ownership action did not complete; no forced takeover.')
        return json.loads(result.stdout)

    def release():
        if record['boardLease']:
            current = json.loads((project / 'docs/board_turn.json').read_text(encoding='utf-8'))
            if current.get('holder') != 'codex' or current.get('item') != lease_item:
                raise RuntimeError('Board lease no longer matches this attempt; do not release another operation.')
            board('release', result='本轮自有普通产品已实际退出，未发主机START；集中反馈及未验范围保留。')
            record['boardLease'] = False

    version = readiness['version']
    waiting_for_board = only_board_blocked(readiness)
    consumed_start_chars = 0
    message = (f'本轮使用已安装的 Companion {version}，只集中验收一次。\n\n'
               '点“开始整体验收”后打开正常产品。选一场你本来就想保留的内容，按卡片开始录音，正常接收、看文字、核对来源、留下跟进并带走结果；按你的目的连续使用，不用遍历每个按钮。\n\n'
               '要覆盖当前长录可靠性，请让同一场实卡录音持续至少2小时，期间可以继续做自己的事。录音只由你操作卡片开始，本窗口不会开录。\n\n'
               '用完关闭 Companion，再在这里集中写下整体感受并选择结论。只有产品实际关闭后，“通过”才可用；遇到阻断可随时写明问题，不用重录。没空可以选“稍后”。')
    def wait_for_board():
        nonlocal waiting_for_board
        waiting_for_board = True
        record['state'] = 'WAITING_SHARED_BOARD_IN_SAME_WINDOW'
        save()
        update('等待当前设备工程检查结束',
               '这一套候选已经准备好，实卡当前正被另一项工程检查占用。请先继续做自己的事，本窗口不会打开产品或开始录音。\n\n'
               '设备空闲并重新核对版本后，原窗口会启用“开始整体验收”；届时再点一次开始即可。最后只在这里集中反馈，不用重开验收。')
    if waiting_for_board:
        wait_for_board()
    else:
        update('整批准备完成，等待你开始', message, (START,))
    shell = Path('C:/Users/Billy/AppData/Local/Microsoft/WindowsApps/pwsh.exe')
    shared = project.parent / 'ai-collaboration-workflow/scripts/operator_prompt.ps1'
    environment = dict(os.environ)
    environment.pop('PSModulePath', None)
    command = [str(shell), '-NoLogo', '-NoProfile', '-File', str(shared),
               '-Title', 'Companion 集中总验收', '-Message', message,
               '-ScopeText', f'Windows {version}；普通固件 FW{readiness.get("firmwareVersion")} / UI{readiness.get("uiVersion")}；原音只保留本机。',
               '-ActionButtons', START, '-Buttons', '通过,遇到问题,稍后',
               '-RequireReviewAllowed', '-LiveUpdates', '-UpdatePath', str(updates),
               '-EventPath', str(events), '-TextInput', '-ObservationLabel', '整体感受、卡住之处和未用部分（集中写一次即可）',
               '-OutputPath', str(cache / 'owner-feedback.txt'), '-Json', '-NoActivate', '-NoTopMost',
               '-Width', '760', '-Height', '690', '-MessageHeight', '310']
    app = None
    app_log = None
    save()
    with stdout.open('wb') as prompt_log:
        prompt = subprocess.Popen(command, env=environment, stdout=prompt_log,
                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        record['promptPid'] = prompt.pid
        save()
        try:
            # Closing the prompt early never skips waiting for the actual app
            # exit and reading its final metadata. It also never stops recording.
            while True:
                running = (app is not None and app.poll() is None) or bool(app_pids())
                if app is not None and record.get('appClosedAt') and running:
                    record.setdefault('previousAppClosures', []).append(record.pop('appClosedAt'))
                    record['state'] = 'OWNER_CONTINUING_SAME_TOTAL_USE'
                    save()
                    update('继续同一轮完整使用',
                           'Companion 已重新打开，继续完成同一目的即可，不用重新开始验收。用完关闭产品，再在这里集中提交感受。')
                if prompt.poll() is not None and app is not None and running:
                    record['promptClosedBeforeAppExit'] = True
                if app is None and waiting_for_board and prompt.poll() is None:
                    try:
                        current_board = json.loads((project / 'docs/board_turn.json').read_text(encoding='utf-8'))
                    except json.JSONDecodeError:
                        time.sleep(.4)
                        continue
                    if current_board.get('holder') is None:
                        fresh = prepare(project, batch, args.installed_dir)
                        if fresh['ready']:
                            waiting_for_board = False
                            record['state'] = 'WAITING_OWNER_START'
                            save()
                            update('同一套候选与设备已就绪，等待你开始', message, (START,))
                        elif not only_board_blocked(fresh):
                            raise RuntimeError('Batch preparation changed while waiting: ' + '; '.join(fresh['blockers']))
                event_text = events.read_text(encoding='utf-8-sig') if events.exists() else ''
                if app is None and prompt.poll() is None and start_requested(event_text[consumed_start_chars:], prompt.pid):
                    consumed_start_chars = len(event_text)
                    fresh = prepare(project, batch, args.installed_dir)
                    if not fresh['ready']:
                        if only_board_blocked(fresh):
                            wait_for_board()
                            continue
                        raise RuntimeError('Preparation changed before the Owner start: ' + '; '.join(fresh['blockers']))
                    if board('status')['holder'] is not None:
                        wait_for_board()
                        continue
                    try:
                        claim = board('claim', item=lease_item)
                    except RuntimeError:
                        current_board = json.loads((project / 'docs/board_turn.json').read_text(encoding='utf-8'))
                        if current_board.get('holder') is not None:
                            wait_for_board()
                            continue
                        raise
                    if claim.get('result') != 'TURN_CLAIMED':
                        raise RuntimeError('Board claim not confirmed.')
                    record['boardLease'] = True
                    app_env = dict(os.environ)
                    for key in APP_ENV:
                        app_env.pop(key, None)
                    app_log = (cache / 'normal-product.log').open('wb')
                    app = subprocess.Popen([str(args.installed_dir / APP_NAME)], env=app_env,
                                           stdout=app_log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
                    record.update(state='OWNER_USING_NORMAL_PRODUCT', ownerStartedAt=now(), appPid=app.pid)
                    save()
                    update('在 Companion 中完成自己的完整目的',
                           '正常产品已由你的点击启动。按自己的目的录音和使用；长录覆盖需要同一场实际录音至少2小时。\n\n'
                           '这段时间不用盯此窗口，不用逐功能打勾。遇到问题保留当前结果、集中写在这里即可，不用为同一问题反复录。用完关闭 Companion 后提交整体结论。')
                running = (app is not None and app.poll() is None) or bool(app_pids())
                if app is not None and not running and not record.get('appClosedAt'):
                    app_log.close()
                    record['appClosedAt'] = now()
                    after = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else []
                    facts = physical_facts(before_ids, after, record['ownerStartedAt'], record['appClosedAt'])
                    record['newCardResults'] = facts
                    complete = [row for row in facts if row['beganDuringOwnerWindow'] and row['audioStored']
                                and row['captureIncomplete'] is False]
                    record['twoHourRecordingObserved'] = any(row['durationMs'] >= 7200000 for row in complete)
                    record['newPhysicalToTextObserved'] = any(row['transcriptFinal'] and row['transcriptCharacters'] > 0
                                                              for row in complete)
                    record['state'] = 'PRODUCT_CLOSED_WAITING_CONCENTRATED_FEEDBACK'
                    save()
                    update('本轮产品已关闭，集中反馈',
                           '本轮产品已退出，实际保存结果已记录。请集中写下是否顺手、哪里卡住、还有哪些没用到，再选择整体结论。\n\n'
                           '未实际覆盖的长录、准确率或其它条件会如实保留，不会仅凭点“通过”认定整机合格。', review=True)
                if prompt.poll() is not None and not running and (app is None or record.get('appClosedAt')):
                    break
                time.sleep(.4)
            response = json.loads(stdout.read_text(encoding='utf-8-sig').strip())
            record['ownerResponse'] = response  # Private local output only.
            record['softwareOwnerAccepted'] = (response.get('selected') == '通过'
                and bool(record.get('appClosedAt')) and not record.get('promptClosedBeforeAppExit'))
            record['state'] = 'OWNER_FEEDBACK_RECEIVED_REQUIRES_EVIDENCE_REVIEW' if app else 'OWNER_DEFERRED_WITHOUT_START'
        except BaseException as error:
            record.update(state='TOTAL_USE_NEEDS_ATTENTION', error=str(error))
            save()
            update('本轮保留，先处理实际问题',
                   '准备或本轮使用遇到实际问题，已保留状态。请不用重复录音或按键，可集中写下看到的情况后选“遇到问题”或“稍后”。')
            while prompt.poll() is None or (app is not None and app.poll() is None):
                time.sleep(.5)
        finally:
            if app_log and not app_log.closed:
                app_log.close()
            release()
            record['finishedAt'] = now()
            save()
    # Owner private text is deliberately not copied into the repository batch.
    public = {key: record.get(key) for key in ['state', 'version', 'firmwareVersion', 'uiVersion', 'sourceCommit', 'ownerStartedAt', 'appClosedAt',
               'finishedAt', 'softwareOwnerAccepted', 'twoHourRecordingObserved', 'newPhysicalToTextObserved',
               'physicalTotalAcceptancePassed', 'saleQualified', 'boardLease', 'hostStartCommands']}
    public['privateEvidenceDirectory'] = str(cache)
    write_json(batch / 'owner-total-result.json', public)
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
