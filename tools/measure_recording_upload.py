"""Measure stored board recordings without START/STOP, ASR, or device consumption.

Use the installed Type path with a fresh receive directory on every invocation.
The first successful result can be passed back with --sample to compare the same
recording IDs, lengths and hashes after the next transport change. Record a
sample once with COMPANION_TYPE_DELETE_AFTER_SYNC=0, or use an existing sealed
recording. This tool never creates a sample when the board catalog is empty.
"""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
BOARD = PROJECT / 'docs/board_operations.md'
OWNER = '01a105e0-7fe5-7cc0-b712-46de75337261'


def open_pair_window(out, guard):
    """Use the normal product's finite PAIR action after an actual unpaired error.

    Never clear bonds or reset a diagnostic image to make this command work.
    UART is closed before the installed Type opens its protected BLE connection.
    """
    import serial
    from serial.tools import list_ports
    ports = [port.device for port in list_ports.comports()
             if port.serial_number == '004400403532510B31333430']
    if len(ports) != 1:
        raise RuntimeError('Fixed V3 UART mapping unavailable; no PAIR or BLE access')
    link = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=1,
                         rtscts=False, dsrdtr=False, xonxoff=False)
    link.dtr = link.rts = False
    link.port = ports[0]
    guard()
    with link, (out / 'pair-window-uart.log').open('wb') as log:
        def command(value):
            for byte in value:
                guard()
                link.write(bytes([byte]))
                link.flush()
                time.sleep(.003)

        command(b'\n?\n')
        raw = bytearray()
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            chunk = link.readline(4096)
            raw.extend(chunk)
            log.write(chunk)
            log.flush()
            if b'DIAG1 END' in raw:
                break
        actual = raw.decode('utf-8', errors='replace')
        if not re.search(r'DIAG1 ID[^\r\n]*\buid=180010000d50335754363720\b', actual):
            raise RuntimeError('Normal product UID not confirmed; no PAIR or BLE access')
        if not re.search(r'DIAG1 AUDIO[^\r\n]*\bmic_run=0\b', actual):
            raise RuntimeError('Microphone not confirmed idle; no PAIR or BLE access')
        command(b'PAIR\n')
        raw = bytearray()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            chunk = link.readline(4096)
            raw.extend(chunk)
            log.write(chunk)
            log.flush()
            if b'PAIR1 OPEN window_ms=120000' in raw:
                return
            if b'PAIR1 REJECTED' in raw:
                raise RuntimeError('Normal product rejected PAIR; no BLE access')
        raise RuntimeError('Finite PAIR acknowledgement unavailable; no BLE access')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True,
                        help='Installed candidate folder containing install/result.json')
    parser.add_argument('--output', type=Path, required=True,
                        help='New folder; previous receive cursors cannot supply measured bytes')
    parser.add_argument('--sample', type=Path,
                        help='Prior upload-only result; require exactly the same ID/length/SHA')
    parser.add_argument('--device-id', default='C8:92:FF:DD:3B:CA')
    parser.add_argument('--open-pair-window', action='store_true',
                        help='After an actual unpaired error, open normal product PAIR; no bond clear or reset')
    parser.add_argument('--observe-uart', action='store_true',
                        help='Passively correlate this same upload with fixed-V3 UART; no serial commands')
    args = parser.parse_args()
    install = json.loads((args.candidate.resolve() / 'install/result.json').read_text(encoding='utf-8-sig'))
    executable = Path(install['installed_exe'])
    assert install['installed_payload_match'] is True
    assert hashlib.sha256(executable.read_bytes()).hexdigest() == install['installed_exe_sha256'], 'Installed Type changed'
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    expected = json.loads(args.sample.read_text(encoding='utf-8-sig'))['samples'] if args.sample else None
    if expected is not None:
        assert expected, 'The prior result contains no fixed sample'
    stage = 'stored-upload-' + datetime.now().strftime('%H%M%S')
    pair_note = '针对Windows未配对错误先用正常产品限时PAIR，不删bond，UART关闭后再接BLE；' if args.open_pair_window else ''
    line = f'- **占用中**：Companion 录音修复（{OWNER}，{datetime.now().isoformat(timespec="seconds")}，{stage}）。{pair_note}只从当前封口录音收取原始字节，不开录/停录/消费/刷写/复位/云端；新主机目录排除缓存计速，样本ID/长度/SHA固定比较。'

    def owners(text):
        section = text.split('## 当前占用', 1)[1].split('## 交接方式', 1)[0]
        return [value for value in section.splitlines() if '**占用中**' in value]

    def guard():
        current = owners(BOARD.read_text(encoding='utf-8-sig'))
        assert len(current) == 1 and OWNER in current[0] and stage in current[0], 'Exclusive board slot changed'

    report = dict(result='NOT_STARTED', scope='STORED_RECORDING_UPLOAD_ONLY',
                  captureCommands=0, consumeCommands=0, cloudCalls=0,
                  fullChainAcceptance='NOT_RUN', samples=[],
                  installedExeSha256=install['installed_exe_sha256'],
                  startedAtLocal=datetime.now().isoformat(timespec='seconds'))
    leased = False
    observer = None
    try:
        text = BOARD.read_text(encoding='utf-8-sig')
        assert not owners(text), 'Another chat owns the board; no interface opened'
        BOARD.write_text(text.replace('## 当前占用', '## 当前占用\n\n' + line, 1), encoding='utf-8')
        leased = True
        guard()
        if args.open_pair_window:
            open_pair_window(out, guard)
            report['finiteProductPairWindowOpened'] = True
            guard()
        if args.observe_uart:
            from recording_uart_observer import RecordingUartObserver
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
        with (out / 'stdout.log').open('w', encoding='utf-8') as stdout, \
                (out / 'stderr.log').open('w', encoding='utf-8') as stderr:
            guard()
            child = subprocess.run([str(executable), '--sync-device-recording',
                                    '--device-id', args.device_id], env=env,
                                   stdout=stdout, stderr=stderr, timeout=120,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        report['exitCode'] = child.returncode
        log = (out / 'stderr.log').read_text(encoding='utf-8', errors='replace')
        report['transportMetrics'] = [value for value in log.splitlines()
                                      if value.startswith(('recording_pull_metrics ', 'recording_pull_target ',
                                                           'recording receive_queue ', 'recording_sync_stage ',
                                                           'recording_pull_arrivals ', 'recording_pull_window ',
                                                           'recording_pull_gap ', 'recording_link_timeline '))]
        rows = [(re.search(r'^sync_device_recording_result_json=(.*)$', value) or [None, None])[1]
                for value in (out / 'stdout.log').read_text(encoding='utf-8', errors='replace').splitlines()
                if value.startswith('sync_device_recording_result_json=')]
        if child.returncode != 0 or not rows:
            raise RuntimeError('Stored receive failed or catalog is empty; no recording was started. See stderr.log')
        result = json.loads(rows[-1])
        sessions = result['sessions']
        assert sessions and result['status'] == 'PASS', 'No durable board recording returned'
        assert all(not session['deviceReclaimed'] for session in sessions), 'Fixed sample was unexpectedly consumed'
        assert 'stage=att_write_begin' not in log and 'recording pull start ' in log, 'Expected real payload pull without consume'
        report['samples'] = sorted([dict(recordingId=session['recordingId'],
                                        totalLength=session['totalLength'], sha256=session['sha256'])
                                   for session in sessions], key=lambda item: item['recordingId'])
        received = [int(match.group(1)) for value in report['transportMetrics']
                    if value.startswith('recording_pull_metrics ')
                    if (match := re.search(r'\breceived_payload_bytes=(\d+)', value))]
        assert received and sum(received) == sum(sample['totalLength'] for sample in report['samples']), 'Cached/incomplete bytes cannot count as a fresh upload'
        if expected is not None:
            assert report['samples'] == expected, 'Sample changed; no same-file comparison claimed'
        report['result'] = 'STORED_ORIGINAL_RECEIVED_SAMPLE_RETAINED'
    except Exception as error:
        report.update(result='UPLOAD_ONLY_NOT_COMPLETED', error=repr(error))
    finally:
        if observer is not None:
            observer.close()
            report['continuousUart'] = observer.summary
        report.update(finishedAtLocal=datetime.now().isoformat(timespec='seconds'), ownedHandlesClosed=True)
        (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if leased:
            text = BOARD.read_text(encoding='utf-8-sig')
            assert line in text, 'Own board stage changed'
            release = f'- **已释放**：Companion 录音修复（{OWNER}，{report["finishedAtLocal"]}，{stage}）。上传专用进程已结束、实际BLE句柄关闭；{report["result"]}，未开录/消费/刷写/复位/云端；原始{out / "result.json"}。'
            BOARD.write_text(text.replace(line, release, 1), encoding='utf-8')
        print(json.dumps({key: report.get(key) for key in ('result', 'error', 'samples', 'transportMetrics')}, ensure_ascii=False), flush=True)
    return 0 if report['result'] == 'STORED_ORIGINAL_RECEIVED_SAMPLE_RETAINED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
