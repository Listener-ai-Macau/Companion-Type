"""Bound local build writes at their entry; no scheduled or implicit deletion.

Shared workspaces retain compiler intermediates. Per-run receipts retain the
deliverables and diagnostics, not another full compiler tree.
"""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import time

GIB = 1024 ** 3


class StorageLimit(RuntimeError):
    pass


@contextmanager
def exclusive_build(path: Path):
    """OS lock, released even if the owner dies. Never allocate another target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'\0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise StorageLimit('Shared build workspace is busy; reuse it after the current job ends.') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def tree_bytes(root: Path) -> int:
    """Logical bytes, excluding junctions/symlinks; refuse incomplete scans."""
    root = root.resolve()
    if not root.exists():
        return 0
    pending = [root]
    total = 0
    while pending:
        directory = str(pending.pop())
        if os.name == 'nt' and not directory.startswith('\\\\?\\'):
            directory = '\\\\?\\' + directory if not directory.startswith('\\\\') else '\\\\?\\UNC\\' + directory[2:]
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    info = entry.stat(follow_symlinks=False)
                    if entry.is_symlink() or getattr(info, 'st_file_attributes', 0) & 1024:
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    else:
                        total += info.st_size
                except FileNotFoundError:
                    # Another compiler can finish/rename an intermediate while observed.
                    continue
    return total


def preflight(cache: Path, *, limit_gib: float = 80, reserve_gib: float = 3,
              min_free_gib: float = 30) -> dict:
    cache = cache.resolve()
    ancestor = cache
    while not ancestor.exists():
        ancestor = ancestor.parent
    used = tree_bytes(cache)
    free = shutil.disk_usage(ancestor).free
    state = dict(cache=str(cache), logicalBytes=used, freeBytes=free,
                 limitBytes=int(limit_gib * GIB), reservedJobBytes=int(reserve_gib * GIB),
                 minimumFreeBytes=int(min_free_gib * GIB), deletedFiles=0)
    if used + state['reservedJobBytes'] > state['limitBytes']:
        raise StorageLimit('Build cache budget exceeded: ' + json.dumps(state))
    if free - state['reservedJobBytes'] < state['minimumFreeBytes']:
        raise StorageLimit('Insufficient free space for this build: ' + json.dumps(state))
    return state


def run_firmware(command: list[str], source: Path, workspace: Path, output: Path,
                 cache: Path) -> int:
    """Reuse validated object identities in the existing firmware builder."""
    workspace, output = workspace.resolve(), output.resolve()
    if output == workspace or output.is_relative_to(workspace) or workspace.is_relative_to(output):
        raise StorageLimit('Receipt directory must be separate from the shared compiler workspace.')
    with exclusive_build(workspace.parent / '.shared-wba-build.lock'):
        storage = preflight(cache, reserve_gib=1)
        if output.exists() and any(output.iterdir()):
            raise StorageLimit('Existing build evidence retained; choose a fresh --output for this attempt: ' + str(output))
        workspace.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        started = time.time_ns()
        # The compiler's existing source/header/flags/object hashes remain the
        # only authority for reuse. No object is trusted just by its filename.
        code = subprocess.call(command, cwd=source)
        copied = []
        for path in workspace.rglob('*'):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(workspace)
            if path.suffix in {'.o', '.su'} or path.name.endswith('.compile.json'):
                continue
            # A command rejected before compilation must not inherit the old
            # successful result, image or diagnostics from the shared target.
            if path.stat().st_mtime_ns < started:
                continue
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied.append(relative.as_posix())
        receipt = dict(schema='denzic.shared-firmware-build.v1', exitCode=code,
                       sharedWorkspace=str(workspace), evidenceDirectory=str(output),
                       command=command, storageBefore=storage, copiedFiles=copied,
                       intermediateCopies=0, deviceAccess=False)
        (output / 'storage-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(preflight(args.cache), indent=2))
    except (StorageLimit, OSError) as error:
        parser.exit(2, str(error) + '\n')
