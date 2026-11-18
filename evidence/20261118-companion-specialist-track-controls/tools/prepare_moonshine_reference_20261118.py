"""Acquire one pinned publisher runtime without changing the system Python."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import sys
import zipfile

import requests

sys.path.insert(0, 'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits

limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024**2)
root = Path('E:/CodexData/Companion/.model-cache/moonshine-voice-0.1.6-reference20261118')
root.mkdir(exist_ok=False)
response = requests.get('https://pypi.org/pypi/moonshine-voice/0.1.6/json', timeout=15)
response.raise_for_status()
wheel = next(item for item in response.json()['urls'] if item['filename'].endswith('win_amd64.whl'))
assert wheel['digests']['sha256'] == '29a54f9249d41735db62b1f97272905cf114554f293c166f0f4f81655a4a2cfc'
response = requests.get(wheel['url'], timeout=45)
response.raise_for_status()
data = response.content
assert len(data) == wheel['size'] and hashlib.sha256(data).hexdigest() == wheel['digests']['sha256']
archive = root / wheel['filename']
archive.write_bytes(data)
runtime = root / 'runtime'
with zipfile.ZipFile(archive) as package:
    assert all((runtime / name).resolve().is_relative_to(runtime.resolve()) for name in package.namelist())
    package.extractall(runtime)
receipt = {
    'at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
    'runtime': 'Moonshine Voice 0.1.6 Windows x64', 'wheel': str(archive),
    'wheelSha256': wheel['digests']['sha256'], 'url': wheel['url'],
    'globalPythonChanged': False, 'newInferenceCalls': 0,
}
(root / 'runtime-acquisition.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt))
