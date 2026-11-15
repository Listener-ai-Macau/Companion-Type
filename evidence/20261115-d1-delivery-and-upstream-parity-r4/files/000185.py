"""Acquire official public paired Eval data, with bounded RAM and resumable IO."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import sys
import time

from moss_windows_resource_limits_20261104 import WorkerLimits

limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024**2)
import requests

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
C = R / 'docs/handoffs/20261109-paired-real-meeting'
D = Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109')
URL = 'https://speech-lab-share-data.oss-cn-shanghai.aliyuncs.com/AliMeeting/openlr/Eval_Ali.tar.gz'
EXPECTED_BYTES = 3673718355
EXPECTED_SHA256 = 'dc47343b2474b5ebcf458927e878155f6ddeb59c85e685b3645c32a1f9578d92'
C.mkdir(parents=True, exist_ok=True)
D.mkdir(parents=True, exist_ok=True)
part = D / 'Eval_Ali.tar.gz.part'
dest = D / 'Eval_Ali.tar.gz'
started = time.perf_counter()

def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')

def save(name, item):
    path = C / name
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(item, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    os.replace(tmp, path)

session = requests.Session()
session.trust_env = False  # Ordinary official Chinese source: direct, no route changes.
headers = {'Accept-Encoding': 'identity'}
head = session.head(URL, headers=headers, timeout=(15, 30))
head.raise_for_status()
size = int(head.headers['Content-Length'])
assert size == EXPECTED_BYTES, 'Pinned public archive size changed; preserve old inputs'
etag = head.headers.get('ETag')
source = {'at': now(), 'officialDescription': 'https://www.openslr.org/119/', 'url': URL,
          'method': 'HEAD', 'status': head.status_code, 'contentLength': size, 'etag': etag,
          'licenseAsPublished': 'CC BY-SA 4.0', 'split': 'Eval',
          'purpose': 'Exposed diagnostic pairing only; NOT training or untouched final evaluation.',
          'lastModified': head.headers.get('Last-Modified'), 'limits': limits.query()}
save('source.json', source)
if dest.exists():
    assert dest.stat().st_size == size
    with dest.open('rb') as handle:
        actual = hashlib.file_digest(handle, 'sha256').hexdigest()
    assert actual == EXPECTED_SHA256, 'Existing public archive bytes changed'
    result = {'at': now(), 'state': 'EXISTING_PINNED_ARCHIVE_VERIFIED_NOT_YET_PAIR_VERIFIED',
              'path': str(dest), 'bytes': size, 'sha256': actual, 'etag': etag,
              'wallSeconds': time.perf_counter()-started, 'limits': limits.query(),
              'archiveCrcVerified': False, 'pairedSessionVerified': False,
              'newModelCalls': 0, 'newTrainingRuns': 0, 'saleQualified': False}
    save('download-reuse-result.json', result)
    if not (C / 'download-result.json').exists():
        save('download-result.json', result)
    print(json.dumps(result), flush=True)
    sys.exit(0)

done = part.stat().st_size if part.exists() else 0
assert done <= size
sha = hashlib.sha256()
if done:
    with part.open('rb') as handle:
        for block in iter(lambda: handle.read(1024**2), b''):
            sha.update(block)
last_report = 0
for attempt in range(3):
    try:
        request_headers = dict(headers)
        if done:
            request_headers.update(Range=f'bytes={done}-', **{'If-Range': etag})
        with session.get(URL, headers=request_headers, stream=True, timeout=(15, 45)) as response:
            response.raise_for_status()
            if done:
                assert response.status_code == 206, 'Server did not honor pinned resume; keep partial without overwrite'
                assert response.headers.get('Content-Range', '').startswith(f'bytes {done}-')
            assert response.headers.get('ETag') == etag, 'Source changed; keep existing bytes for diagnosis'
            with part.open('ab') as handle:
                for block in response.iter_content(chunk_size=256 * 1024):
                    if not block:
                        continue
                    handle.write(block)
                    sha.update(block)
                    done += len(block)
                    assert done <= size
                    elapsed = time.perf_counter() - started
                    # Avoid saturating user network; this is an upper bound, not a throughput claim.
                    if attempt == 0 and elapsed < done / (12 * 1024**2):
                        time.sleep(min(.05, done / (12 * 1024**2) - elapsed))
                    if elapsed - last_report >= 15:
                        item = {'at': now(), 'state': 'DOWNLOADING_OFFICIAL_EVAL', 'bytes': done,
                                'totalBytes': size, 'fraction': done / size, 'wallSeconds': elapsed,
                                'pid': os.getpid(), 'limits': limits.query()}
                        save('download-progress.json', item)
                        print(json.dumps(item), flush=True)
                        last_report = elapsed
                handle.flush()
                os.fsync(handle.fileno())
        break
    except (requests.RequestException, OSError) as error:
        save(f'download-attempt-{attempt + 1}-failure.json', {'at': now(), 'error': repr(error), 'bytes': done})
        if attempt == 2:
            raise
        time.sleep(1)
assert done == size, (done, size)
assert sha.hexdigest() == EXPECTED_SHA256, 'Downloaded archive differs from frozen development source; keep partial'
os.replace(part, dest)
result = {'at': now(), 'state': 'ARCHIVE_BYTES_COMPLETE_NOT_YET_PAIR_VERIFIED', 'path': str(dest),
          'bytes': done, 'sha256': sha.hexdigest(), 'etag': etag,
          'wallSeconds': time.perf_counter() - started, 'limits': limits.query(),
          'archiveCrcVerified': False, 'pairedSessionVerified': False, 'newModelCalls': 0,
          'newTrainingRuns': 0, 'saleQualified': False}
save('download-result.json', result)
print(json.dumps(result), flush=True)
