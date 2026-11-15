"""Restore one predeclared real session; never extract arbitrary tar paths."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import json
import os
import shutil
import tarfile
import time
from moss_windows_resource_limits_20261104 import WorkerLimits
from paired_meeting_pcm16_20261109 import info

limits = WorkerLimits(cpu_percent=5, memory_bytes=768 * 1024**2)
R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
C = R / 'docs/handoffs/20261109-paired-real-meeting'
D = Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109')
selection = 'R8001_M8004'
out = D / 'paired-session' / selection
out.mkdir(parents=True, exist_ok=True)
archive = D / 'Eval_Ali.tar.gz'
receipt = json.loads((C / 'download-result.json').read_bytes())
assert archive.stat().st_size == receipt['bytes']
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
start = time.perf_counter()
members, files = [], []
protocol = {'at': now(), 'selectedSession': selection,
            'selectionRule': 'First official far recording, also one of the two exposed November4 paired meetings; fixed before new ASR. Restore missing cache, not a new independent meeting.',
            'archive': receipt, 'split': 'Eval', 'trainingAllowed': False,
            'output': str(out), 'limits': limits.query(), 'newModelCalls': 0}
(C / 'pair-extraction-protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
with gzip.open(archive, 'rb') as gz:
    with tarfile.open(fileobj=gz, mode='r|', bufsize=1024**2) as tar:
        for member in tar:
            item = {'name': member.name, 'bytes': member.size, 'regularFile': member.isfile()}
            members.append(item)
            posix = PurePosixPath(member.name)
            assert not posix.is_absolute() and '..' not in posix.parts and '\\' not in member.name
            if not member.isfile() or not (posix.name.startswith(selection + '_') or posix.stem == selection):
                continue
            if posix.suffix.lower() not in ['.wav', '.textgrid', '.rttm', '.txt']:
                continue
            # Keep far/near annotation sets distinct even if their filenames overlap.
            side = 'near' if 'Eval_Ali_near' in posix.parts else 'far' if 'Eval_Ali_far' in posix.parts else 'other'
            target = out / side / posix.name
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            assert source is not None
            temp = target.with_suffix(target.suffix + '.partial')
            sha = hashlib.sha256()
            count = 0
            with temp.open('wb') as handle:
                while True:
                    block = source.read(1024**2)
                    if not block:
                        break
                    handle.write(block)
                    sha.update(block)
                    count += len(block)
            assert count == member.size
            os.replace(temp, target)
            file = dict(item, path=str(target), sha256=sha.hexdigest(), side=side)
            if target.suffix.lower() == '.wav':
                file['wave'] = info(target)
            files.append(file)
            print(json.dumps({'state': 'SELECTED_MEMBER_RESTORED', 'file': file}), flush=True)
    # Consume through the gzip trailer: tar EOF alone does not prove gzip CRC.
    while gz.read(1024**2):
        pass
result = {'at': now(), 'state': 'ONE_REAL_SESSION_RESTORED_CRC_VERIFIED_NOT_YET_ALIGNED',
          'selectedSession': selection, 'files': files, 'archiveMembers': members,
          'archiveSha256': receipt['sha256'], 'gzipCrcVerified': True,
          'wallSeconds': time.perf_counter() - start, 'limits': limits.query(),
          'newModelCalls': 0, 'newTrainingRuns': 0, 'saleQualified': False}
(C / 'pair-extraction-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
assert len([f for f in files if f['side'] == 'far' and f['name'].endswith('.wav')]) == 1
assert len([f for f in files if f['side'] == 'near' and f['name'].endswith('.wav')]) == 4
assert len([f for f in files if f['side'] == 'far' and f['name'].endswith('.TextGrid')]) == 1
print(json.dumps({'state': result['state'], 'files': len(files), 'wallSeconds': result['wallSeconds'], 'limits': result['limits']}), flush=True)
