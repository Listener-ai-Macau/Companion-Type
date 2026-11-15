"""Write-ahead ownership for private generated files in one native job root.

The native owner creates/leases the root before any audio is accepted. The
scoped startup hook propagates into Python descendants without changing their
inference code. Reads and paths outside this job are not recorded or changed.
"""
import json
import os
from pathlib import Path
import sys
import threading


def install():
    value = os.environ.get('COMPANION_LOCAL_ARTIFACT_ROOT')
    if not value or getattr(sys, '_companion_cache_audit', False):
        return
    root = Path(value).absolute()
    assert root.is_dir() and (root/'.owner').is_file(), 'Native cache ownership is required'
    prefix = os.path.normcase(str(root))+os.sep
    local, seen = threading.local(), set()
    ledger, gate = root/'.artifact-writes.jsonl', root/'.artifact-writes.lock'

    def record(path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        path = os.path.abspath(os.fsdecode(path))
        if not os.path.normcase(path).startswith(prefix):
            return
        name = os.path.relpath(path, root).replace('\\', '/')
        if name in {'.artifact-writes.jsonl', '.artifact-writes.lock'} or name in seen:
            return
        local.busy = True
        try:
            import msvcrt
            with gate.open('a+b') as lock:
                if lock.seek(0, 2) == 0:
                    lock.write(b'0'); lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    with ledger.open('ab') as output:
                        output.write((json.dumps(name, ensure_ascii=True)+'\n').encode('ascii'))
                        output.flush(); os.fsync(output.fileno())
                finally:
                    lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            seen.add(name)
        finally:
            local.busy = False

    def hook(event, args):
        if getattr(local, 'busy', False):
            return
        if event == 'open':
            path, mode, flags = args
            if (mode and any(x in mode for x in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                record(path)
        elif event == 'os.rename':
            record(args[1])

    sys.addaudithook(hook)
    sys._companion_cache_audit = True


def activate(root, hook_directory):
    os.environ['COMPANION_LOCAL_ARTIFACT_ROOT'] = str(Path(root).absolute())
    previous = os.environ.get('PYTHONPATH')
    os.environ['PYTHONPATH'] = str(hook_directory)+(os.pathsep+previous if previous else '')
    install()
