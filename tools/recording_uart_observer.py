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
                while not self.stop.is_set():
                    data = port.read(4096)
                    if not data:
                        continue
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
