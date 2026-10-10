"""Capture one real five-minute board sample and retain it for upload changes.

Explicit preparation only: the upload tool must never start a recording when
its catalog is empty. The installed product keeps its ordinary CRC/SHA and
durable file/index path. DELETE_AFTER_SYNC=0 prevents physical consumption.
"""
from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import winsound

from measure_recording_upload import BOARD, OWNER, PROJECT
from recording_uart_observer import RecordingUartObserver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--firmware', default='00010197')
    args = parser.parse_args()
    install = json.loads((args.candidate.resolve() / 'install/result.json').read_text(encoding='utf-8-sig'))
    executable = Path(install['installed_exe'])
    assert install['installed_payload_match']
    assert hashlib.sha256(executable.read_bytes()).hexdigest() == install['installed_exe_sha256']
    stimulus_dir = PROJECT / 'Companion-Type/.cache/meeting-speaker-timing-20261007/three-voice-stimulus-v2'
    stimulus = json.loads((stimulus_dir / 'stimulus.json').read_text(encoding='utf-8-sig'))
    audio = stimulus_dir / 'meeting.wav'
    assert hashlib.sha256(audio.read_bytes()).hexdigest() == stimulus['wavSha256'].lower()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    stage = 'prepare-fixed-upload-sample-' + datetime.now().strftime('%H%M%S')
    line = f'- **占用中**：Companion 录音修复（{OWNER}，{datetime.now().isoformat(timespec="seconds")}，{stage}）。目录已实际确认空，仅准备一次300秒真实板麦样本，电脑播放已有机械语音；正常START/STOP和耐久保存，DELETE_AFTER_SYNC=0保留板端样本供以后上传修改，不消费/刷写/复位/云端；持续被动UART，约6分钟后关闭接口交回。'
    report = dict(result='NOT_STARTED', scope='PREPARE_ONE_RETAINED_BOARD_SAMPLE',
                  installedExeSha256=install['installed_exe_sha256'], samples=[],
                  captureSource='board_device', hostMic=False, seed=False,
                  cloudCalls=0, fullChainAcceptance='NOT_RUN',
                  startedAtLocal=datetime.now().isoformat(timespec='seconds'))
    leased = False
    child = None
    observer = None

    def owners(text):
        return [entry for entry in text.split('## 当前占用', 1)[1].split('## 交接方式', 1)[0].splitlines()
                if '**占用中**' in entry]

    def guard():
        entries = owners(BOARD.read_text(encoding='utf-8-sig'))
        assert len(entries) == 1 and OWNER in entries[0] and stage in entries[0], 'Board lease changed'

    def save():
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    try:
        text = BOARD.read_text(encoding='utf-8-sig')
        assert not owners(text), 'Other chat owns the board; no interface opened'
        BOARD.write_text(text.replace('## 当前占用', '## 当前占用\n\n' + line, 1), encoding='utf-8')
        leased = True
        # Verify only the idle application needed for the upcoming START;
        # diagnostic RAM images and missing responses are never reset away.
        import serial
        from serial.tools import list_ports
        ports = [port.device for port in list_ports.comports()
                 if port.serial_number == '004400403532510B31333430']
        assert len(ports) == 1, 'Fixed V3 UART mapping unavailable'
        link = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=1)
        link.dtr = link.rts = False
        link.port = ports[0]
        guard()
        with link:
            link.write(b'\n?\n')
            link.flush()
            raw = bytearray()
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                raw.extend(link.readline(4096))
                if b'DIAG1 END' in raw:
                    break
        (out / 'before-uart.log').write_bytes(raw)
        actual = raw.decode('utf-8', errors='replace')
        assert re.search(r'DIAG1 ID[^\r\n]*\bfw=' + re.escape(args.firmware) + r'\b[^\r\n]*\buid=180010000d50335754363720\b', actual), 'Normal firmware/UID not confirmed; no START'
        assert re.search(r'DIAG1 AUDIO[^\r\n]*\bmic_run=0\b', actual), 'Microphone not confirmed idle; no START'
        observer = RecordingUartObserver(out, guard)
        observer.start()
        env = os.environ.copy()
        for key in list(env):
            if key.startswith(('COMPANION_TYPE_BLE_', 'COMPANION_TYPE_TEST_')) or key in (
                    'COMPANION_TYPE_DEVICE_RECORDING_PATH', 'COMPANION_TYPE_TRANSCRIPT_TEXT',
                    'COMPANION_TYPE_ASR_COMMAND', 'COMPANION_TYPE_MINUTES_COMMAND'):
                env.pop(key, None)
        env.update(COMPANION_TYPE_STATE_PATH=str(out / 'sessions.json'),
                   COMPANION_TYPE_RECORDING_DIR=str(out / 'recordings'),
                   COMPANION_TYPE_DELETE_AFTER_SYNC='0',
                   COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',
                   COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED='0')
        guard()
        save()
        with (out / 'stdout.log').open('w', encoding='utf-8') as stdout, \
                (out / 'stderr.log').open('w', encoding='utf-8') as stderr:
            child = subprocess.Popen([str(executable), '--v1-real-meeting', '--device-id',
                                      'C8:92:FF:DD:3B:CA', '--seconds', '300', '--output',
                                      str(out / 'control-receive.json')], env=env, stdout=stdout,
                                     stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
            deadline = time.monotonic() + 430
            while child.poll() is None:
                guard()
                if time.monotonic() >= deadline:
                    raise TimeoutError('Sample preparation exceeded its bounded deadline')
                if 'recordingId' not in report and (out / 'sessions.json').exists():
                    try:
                        sessions = json.loads((out / 'sessions.json').read_text(encoding='utf-8-sig'))
                    except (OSError, ValueError):
                        sessions = []
                    active = next((session for session in sessions if session.get('source') == 'boardDevice'
                                   and session.get('status') == 'recording'
                                   and session.get('deviceRecordingId') is not None), None)
                    if active:
                        report['recordingId'] = active['deviceRecordingId']
                        winsound.PlaySound(str(audio), winsound.SND_FILENAME | winsound.SND_ASYNC)
                        save()
                        print(f'One retained board sample START acknowledged: id={report["recordingId"]}; recording 300 seconds.', flush=True)
                time.sleep(.1)
        report['exitCode'] = child.returncode
        winsound.PlaySound(None, 0)
        observer.close()
        report['continuousUart'] = observer.summary
        control = json.loads((out / 'control-receive.json').read_text(encoding='utf-8-sig'))
        # The normal full control probe intentionally reports FAIL when a
        # development sample is retained. Preserve that raw result; only the
        # explicit sample-preparation scope may accept the intentional hold.
        checks = control['checks']
        assert checks['durableDeviceConsume'] is False, 'Sample was consumed'
        assert all(value is True for name, value in checks.items() if name != 'durableDeviceConsume'), 'Capture/durable path failed beyond intentional retention'
        assert control['durationMs'] >= 300000 and control['totalLength'] >= 524288
        log = (out / 'stderr.log').read_text(encoding='utf-8', errors='replace')
        assert 'stage=att_write_begin' not in log and 'recording pull start ' in log
        report['samples'] = [dict(recordingId=control['recordingId'], totalLength=control['totalLength'], sha256=control['sha256'])]
        report['transportMetrics'] = [entry for entry in log.splitlines() if entry.startswith(('recording_pull_metrics ', 'recording_sync_stage '))]
        report['result'] = 'RETAINED_REAL_BOARD_SAMPLE_PREPARED'
    except Exception as error:
        report.update(result='SAMPLE_PREPARATION_NOT_COMPLETED', error=repr(error))
    finally:
        winsound.PlaySound(None, 0)
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
            report['captureCleanup'] = 'Host closed; normal board recording duration limit remains, no synthetic STOP'
        if observer is not None:
            observer.close()
            report['continuousUart'] = observer.summary
        report.update(finishedAtLocal=datetime.now().isoformat(timespec='seconds'), ownedHandlesClosed=True)
        save()
        if leased:
            text = BOARD.read_text(encoding='utf-8-sig')
            assert line in text, 'Own board stage changed'
            release = f'- **已释放**：Companion 录音修复（{OWNER}，{report["finishedAtLocal"]}，{stage}）。样本准备进程及被动UART均实际关闭；{report["result"]}，已保留样本身份／原失败于{out / "result.json"}，未消费/刷写/复位/云端。'
            BOARD.write_text(text.replace(line, release, 1), encoding='utf-8')
        print(json.dumps({name: report.get(name) for name in ('result', 'error', 'samples', 'transportMetrics')}, ensure_ascii=False), flush=True)
    return 0 if report['result'] == 'RETAINED_REAL_BOARD_SAMPLE_PREPARED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
