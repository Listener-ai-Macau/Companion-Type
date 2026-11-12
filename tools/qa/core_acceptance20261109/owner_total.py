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
from owner_total_guide import STEPS, NEXT, BACK, RESTART_INDEX, navigation_requested

TZ = timezone(timedelta(hours=8))
START = '开始'
APP_NAME = 'companion-type.exe'
BOARD_BUSY = 'Shared board is currently occupied; do not interrupt its actual operation.'
FIRMWARE_PENDING = 'The known firmware/IMU repair and its matching physical receipt are unfinished.'
UI_REWORK_PENDING = 'Owner rejected the product and guidance UI; finish and install the coherent usability repair before another walkthrough.'
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


def current_batch(project):
    data = json.loads((project / 'docs/product_backlog.json').read_text(encoding='utf-8'))
    active = data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']
    receipt = Path(active['lastWindowsSoftwareDeliveryReceipt']).resolve()
    if not receipt.is_relative_to((project / 'docs/handoffs').resolve()) or not receipt.is_file():
        raise ValueError('Current Windows delivery receipt is missing or outside this project.')
    return receipt.parent


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
    closure = active['ownerProductClosure20261112']
    ui_rework = closure.get('ownerUiUsabilityRework20261112')
    if ui_rework and not (ui_rework.get('installedAndEngineeringReviewed') is True
                          and ui_rework.get('candidateVersion') == version):
        blockers.append(UI_REWORK_PENDING)
    dependency = closure.get('physicalAcceptanceDependency', {})
    firmware = dependency.get('ordinaryFirmwareInstallation', {})
    firmware_ready = (dependency.get('state') not in {
        'WAITING_SHARED_BOARD_FIRMWARE_WORK',
        'BOARD_RELEASED_MATCHED_FIRMWARE_RECEIPT_AND_IMU_REPAIR_PENDING',
        'CURRENT_EMBEDDED_WORKPOINT_MUST_BIND_LATEST_NORMAL_FIRMWARE_BEFORE_PHYSICAL_TOTAL_ONLY'}
        and dependency.get('firmwareIdentityVerifiedByOriginalInstaller') is True
        and firmware.get('bootAndNormalApplicationVerified') is True
        and type(firmware.get('firmware')) is int and firmware['firmware'] > 0
        and type(firmware.get('ui')) is int)
    if not firmware_ready:
        blockers.append(FIRMWARE_PENDING)
    board = json.loads((project / 'docs/board_turn.json').read_text(encoding='utf-8'))
    if board.get('holder') is not None:
        blockers.append(BOARD_BUSY)
    return dict(at=now(), state='READY_FOR_ONE_TOTAL_USE' if not blockers else 'FINISH_CURRENT_BATCH_BEFORE_OWNER_TOTAL_USE',
                ready=not blockers, version=version, sourceCommit=verification['sourceCommit'],
                softwareReady=not any(item not in {FIRMWARE_PENDING, BOARD_BUSY} for item in blockers),
                firmwareIdentityBindingReady=firmware_ready,
                firmwareVersion=firmware.get('firmware') if firmware_ready else None,
                uiVersion=firmware.get('ui') if firmware_ready else None,
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
    batch = (args.batch or current_batch(project)).resolve()
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
                                enabledActions=list(actions), visibleActions=list(actions),
                                visibleReviews=['通过', '遇到问题', '稍后'] if review else ['遇到问题', '稍后'],
                                reviewAllowed=review))

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
    consumed_navigation_chars = 0
    guide_index = 0
    navigation_not_before = 0
    record.update(guidedStepsTotal=len(STEPS), guidedStepsVisited=[], guidedRouteReachedEnd=False)
    message = ('我会带你逐步验收，每次只看当前这一步。\n\n'
               '点“开始”打开软件，从连接录音卡开始。每一步都有操作和预期结果，用“下一步”继续。问题先记在下方，最后一起提交。\n\n'
               '录音由你按卡片实体键开始，这个窗口不会开录。')

    def show_guide():
        nonlocal navigation_not_before
        navigation_not_before = time.time() + .8
        record['guidedStepIndex'] = guide_index
        if guide_index not in record['guidedStepsVisited']:
            record['guidedStepsVisited'].append(guide_index)
        record['guidedRouteReachedEnd'] = guide_index == len(STEPS) - 1
        save()
        actions = ([BACK] if guide_index else []) + ([NEXT] if guide_index < len(STEPS) - 1 else [])
        update(f'{guide_index + 1}/{len(STEPS)} · {STEPS[guide_index][0]}', STEPS[guide_index][1],
               actions, review=bool(record.get('appClosedAt')) and record['guidedRouteReachedEnd'])
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
               '-Title', 'Companion 功能验收', '-Message', message,
               '-ScopeText', '同一轮连续验收 · 最后统一反馈',
               '-ActionButtons', ','.join((START, BACK, NEXT)), '-Buttons', '通过,遇到问题,稍后',
               '-RequireReviewAllowed', '-LiveUpdates', '-UpdatePath', str(updates),
               '-EventPath', str(events), '-TextInput', '-ObservationLabel', '问题先记在这里，最后一起提交',
               '-OutputPath', str(cache / 'owner-feedback.txt'), '-Json', '-NoActivate', '-NoTopMost',
               '-Width', '760', '-Height', '580', '-MessageHeight', '230']
    app = None
    app_log = None

    def launch_product():
        nonlocal app_log
        app_env = dict(os.environ)
        for key in APP_ENV:
            app_env.pop(key, None)
        app_log = (cache / 'normal-product.log').open('ab')
        return subprocess.Popen([str(args.installed_dir / APP_NAME)], env=app_env,
                                stdout=app_log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
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
                    if record.get('closedAtGuidedStep') == RESTART_INDEX:
                        record['guidedReopenObserved'] = True
                    show_guide()
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
                    app = launch_product()
                    record.update(state='OWNER_USING_NORMAL_PRODUCT', ownerStartedAt=now(), appPid=app.pid)
                    consumed_navigation_chars = event_text.rfind('\n') + 1
                    show_guide()
                if (app is not None and record.get('appClosedAt') and not running and prompt.poll() is None
                        and start_requested(event_text[consumed_start_chars:], prompt.pid)):
                    consumed_start_chars = len(event_text)
                    current = json.loads((project / 'docs/board_turn.json').read_text(encoding='utf-8'))
                    if current.get('holder') != 'codex' or current.get('item') != lease_item:
                        raise RuntimeError('Preserve the changed board lease; do not resume another operation.')
                    for name, expected in [(APP_NAME, readiness['installedExeSha256']),
                                           ('companion_type_lib.dll', readiness['installedDllSha256'])]:
                        if sha(args.installed_dir / name) != expected:
                            raise RuntimeError('Installed bytes changed during this guided round.')
                    app = launch_product()
                    record.setdefault('previousAppClosures', []).append(record.pop('appClosedAt'))
                    record.update(state='OWNER_CONTINUING_SAME_TOTAL_USE', appPid=app.pid)
                    if record.get('closedAtGuidedStep') == RESTART_INDEX:
                        record['guidedReopenObserved'] = True
                    consumed_navigation_chars = event_text.rfind('\n') + 1
                    show_guide()
                if app is not None and prompt.poll() is None and not record.get('appClosedAt'):
                    complete_events = event_text.rfind('\n') + 1
                    action = navigation_requested(event_text[consumed_navigation_chars:complete_events], prompt.pid, navigation_not_before)
                    consumed_navigation_chars = complete_events
                    if action == BACK:
                        guide_index = max(0, guide_index - 1)
                        show_guide()
                    elif action == NEXT:
                        if guide_index == RESTART_INDEX and not record.get('guidedReopenObserved'):
                            update(f'{guide_index + 1}/{len(STEPS)} · 先退出再重开',
                                   STEPS[guide_index][1] + '\n\n当前还没有观察到这一步的退出重开；先关闭产品，原窗口会提供继续入口。', (BACK, NEXT))
                        else:
                            guide_index = min(len(STEPS) - 1, guide_index + 1)
                            show_guide()
                running = (app is not None and app.poll() is None) or bool(app_pids())
                if app is not None and not running and not record.get('appClosedAt'):
                    app_log.close()
                    record['appClosedAt'] = now()
                    record['closedAtGuidedStep'] = guide_index
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
                    if guide_index == len(STEPS) - 1:
                        update('本轮产品已关闭，提交一次整体结论', STEPS[-1][1], review=True)
                    else:
                        update(f'{guide_index + 1}/{len(STEPS)} · 产品已退出，本轮保留',
                               '软件已退出，已保存结果保留。点“开始”重新打开并继续当前步骤。\n\n'
                               + STEPS[guide_index][1] + '\n\n如果不继续，可以在下方集中说明问题后选“遇到问题”或“稍后”。', (START,))
                if prompt.poll() is not None and not running and (app is None or record.get('appClosedAt')):
                    break
                time.sleep(.4)
            response = json.loads(stdout.read_text(encoding='utf-8-sig').strip())
            record['ownerResponse'] = response  # Private local output only.
            record['softwareOwnerAccepted'] = (response.get('selected') == '通过'
                and bool(record.get('appClosedAt')) and not record.get('promptClosedBeforeAppExit')
                and record['guidedRouteReachedEnd'])
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
               'physicalTotalAcceptancePassed', 'saleQualified', 'boardLease', 'hostStartCommands',
               'guidedStepsTotal', 'guidedStepsVisited', 'guidedRouteReachedEnd', 'guidedReopenObserved']}
    public['privateEvidenceDirectory'] = str(cache)
    write_json(batch / 'owner-total-result.json', public)
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
