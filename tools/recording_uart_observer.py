"""Passive, bounded UART evidence for one actual BLE recording operation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

import serial
from serial.tools import list_ports


class RecordingUartObserver:
    def __init__(self, output: Path, lease_guard):
        self.output = output
        self.lease_guard = lease_guard
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.setup_query = threading.Event()
        self.setup_query_sent = threading.Event()
        self.setup_pair = threading.Event()
        self.setup_pair_sent = threading.Event()
        self.payload_started = False
        self.error = None
        self.thread = None
        self.summary = {'bytes': 0, 'chunks': 0, 'closed': True,
                        'commandsSent': 0, 'scope': 'passive_actual_operation',
                        'readTimeoutMs': 100,
                        'timestampScope': 'host read completion; not per-byte arrival or BLE throughput'}

    def start(self):
        self.output.mkdir(parents=True, exist_ok=True)
        self.thread = threading.Thread(target=self._read, name='recording-uart', daemon=True)
        self.thread.start()
        if not self.ready.wait(3):
            self.close()
            raise RuntimeError('UART observer did not open within 3 seconds')
        if self.error:
            self.close()
            raise RuntimeError(self.error)

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                raise RuntimeError('UART observer has not closed; do not release the board lease')

    def request_setup_snapshot_once(self):
        """Only the explicit pre-payload barrier may request this one query."""
        if self.setup_query.is_set() or self.setup_query_sent.is_set():
            raise RuntimeError('Setup query already requested; no repeated diagnostic')
        self.lease_guard()
        self.setup_query.set()

    def request_guarded_pair_window_once(self):
        """Explicit recovery of a recorded pairing failure, before BLE payload.

        PAIR invokes the same finite, busy-guarded window as the device menu.
        It does not clear bonds, pair a host or weaken the protected channel.
        """
        if self.payload_started or not self.setup_query_sent.is_set():
            raise RuntimeError('Pair window is only available after idle setup and before payload')
        if self.setup_pair.is_set() or self.setup_pair_sent.is_set():
            raise RuntimeError('Pair window already requested; no repeated recovery')
        self.lease_guard()
        self.setup_pair.set()

    def begin_payload(self):
        self.payload_started = True

    def _read(self):
        try:
            ports = [p.device for p in list_ports.comports()
                     if p.serial_number == '004400403532510B31333430']
            if len(ports) != 1:
                raise RuntimeError('Fixed V3 UART mapping is not unique')
            port = serial.Serial(port=None, baudrate=115200, timeout=.1,
                                 write_timeout=1, rtscts=False, dsrdtr=False, xonxoff=False)
            port.dtr = port.rts = False
            port.port = ports[0]
            self.lease_guard()
            with port, (self.output / 'live-uart.log').open('wb') as raw, \
                    (self.output / 'uart-read-timeline.jsonl').open('w', encoding='utf-8') as timing:
                self.summary.update(closed=False, port=ports[0],
                    startedAt=datetime.now(timezone.utc).isoformat(),
                    startedMonotonicNs=time.monotonic_ns())
                self.ready.set()
                last_received = time.monotonic()
                while not self.stop.is_set():
                    if self.setup_query.is_set() and not self.setup_query_sent.is_set():
                        self.lease_guard()
                        port.write(b'?')
                        port.flush()
                        self.summary.update(commandsSent=1,
                            scope='one_explicit_pre_payload_setup_query_then_passive',
                            setupQueryStartByteOffset=self.summary['bytes'],
                            setupQuerySentAt=datetime.now(timezone.utc).isoformat())
                        self.setup_query_sent.set()
                    if self.setup_pair.is_set() and not self.setup_pair_sent.is_set() and time.monotonic() - last_received >= .150:
                        self.lease_guard()
                        # Polling RX cannot safely accept a burst during the
                        # target's blocking diagnostic output. Idle first,
                        # then one paced, newline-delimited service command.
                        for byte in b'\nPAIR\n':
                            port.write(bytes([byte]))
                            port.flush()
                            time.sleep(.020)
                        self.summary.update(commandsSent=self.summary['commandsSent'] + 1,
                            scope='one_idle_setup_query_and_explicit_guarded_pair_window_then_passive',
                            guardedPairWindowSentAt=datetime.now(timezone.utc).isoformat())
                        self.setup_pair_sent.set()
                    data = port.read(4096)
                    if not data:
                        continue
                    last_received = time.monotonic()
                    if self.summary['bytes'] + len(data) > 8 * 1024 * 1024:
                        raise RuntimeError('UART evidence exceeded its 8 MiB bound')
                    arrival = {'readCompletedAt': datetime.now(timezone.utc).isoformat(),
                               'readCompletedMonotonicNs': time.monotonic_ns(),
                               'offset': self.summary['bytes'], 'bytes': len(data)}
                    raw.write(data)
                    raw.flush()
                    timing.write(json.dumps(arrival, separators=(',', ':')) + '\n')
                    timing.flush()
                    self.summary['bytes'] += len(data)
                    self.summary['chunks'] += 1
        except Exception as exc:
            self.error = repr(exc)
            self.summary['error'] = self.error
        finally:
            self.summary.update(closed=True, finishedAt=datetime.now(timezone.utc).isoformat())
            (self.output / 'uart-observer.json').write_text(
                json.dumps(self.summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            self.ready.set()
