"""Acquire only the frozen English Medium streaming asset manifest."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import base64
import hashlib
import json
import shutil
import sys
import time
import zipfile
import requests

sys.path.insert(0, 'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json

limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024**2)
root = Path('E:/CodexData/Companion/.model-cache/moonshine-voice-0.1.6-reference20261118')
model = root / 'medium-streaming-en-quantized-26-11-02'
model.mkdir(exist_ok=False)
manifest = json.loads((root / 'english-medium-manifest.json').read_text(encoding='utf-8'))
group, = manifest['groups']
base = 'https://download.moonshine.ai/model/medium-streaming-en/quantized_26_11_02'
assert group['base_url'] == base
assert shutil.disk_usage(root).free > 30*1024**3 + sum(r['size'] for r in group['files'])
state = {'state':'ACQUIRING_SINGLE_PUBLISHER_MOONSHINE_ENGLISH_MEDIUM_ASSET', 'files':[], 'newInferenceCalls':0}

def save(**values):
    state.update(values,at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'))
    atomic_json(root/'model-acquisition-state.json',state)

def get(url, **options):
    reply=requests.get(url,timeout=(15,35),**options)
    reply.raise_for_status()
    return reply

try:
    save()
    checksum_version='1.8.0'
    meta=get(f'https://pypi.org/pypi/google-crc32c/{checksum_version}/json').json()
    wheel=next((x for x in meta['urls'] if 'cp311-cp311-win_amd64.whl' in x['filename']),None)
    assert wheel is not None, 'Published Windows checksum wheel missing'
    data=get(wheel['url']).content
    assert len(data)==wheel['size'] and hashlib.sha256(data).hexdigest()==wheel['digests']['sha256']
    wheel_file=root/wheel['filename']
    wheel_file.write_bytes(data)
    dep=root/'checksum-dependency'
    with zipfile.ZipFile(wheel_file) as z:
        assert all((dep/name).resolve().is_relative_to(dep.resolve()) for name in z.namelist())
        z.extractall(dep)
    sys.path.insert(0,str(dep))
    from google_crc32c import Checksum
    state['checksumWheelSha256']=wheel['digests']['sha256']
    start=time.monotonic()
    for entry in group['files']:
        name=entry['name']
        assert Path(name).name==name and entry['url']==base+'/'+name and entry['checksum_type']=='crc32c'
        part=model/(name+'.partial')
        count=0;sha=hashlib.sha256();crc=Checksum()
        save(activeFile=name,receivedBytes=0)
        with get(entry['url'],stream=True) as response,part.open('xb') as output:
            for block in response.iter_content(1024**2):
                assert time.monotonic()-start<420
                if block:
                    output.write(block);count+=len(block);sha.update(block);crc.update(block)
                    if count%(16*1024**2)==0:save(receivedBytes=count)
        assert count==entry['size'] and base64.b64encode(crc.digest()).decode()==entry['checksum']
        part.rename(model/name)
        state['files'].append(dict(file=str(model/name),bytes=count,sha256=sha.hexdigest(),publisherChecksumVerified=True))
        save(activeFile=name,receivedBytes=count)
    save(state='COMPLETE_PINNED_PUBLISHER_MOONSHINE_ENGLISH_MEDIUM',modelPath=str(model),modelArch=5,downloadSeconds=time.monotonic()-start)
    atomic_json(root/'model-acquisition-completed.json',state)
    print(json.dumps({'state':state['state'],'modelBytes':sum(r['bytes'] for r in state['files']),'seconds':state['downloadSeconds']}))
except BaseException as error:
    save(state='MODEL_ACQUISITION_FAILED_RETAINED',error=repr(error))
    raise
