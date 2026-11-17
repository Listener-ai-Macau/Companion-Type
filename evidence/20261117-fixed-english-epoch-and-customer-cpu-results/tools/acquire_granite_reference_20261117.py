"""Acquire only the pinned reference assets; no audio, model execution or training."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, os, shutil, sys, time, traceback, urllib.request
import psutil

S = Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
sys.path.insert(0, str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure
from durable_model_state_20261117 import atomic_json

C = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
OUT = C / 'asset-acquisition-r1'
OUT.mkdir(exist_ok=False)
cache = Path('E:/CodexData/Companion/.model-cache/english-granite-official20261117')
cache.mkdir(exist_ok=True)
repo = 'ibm-granite/granite-speech-4.1-2b'
rev = '823ca793aa49925d4eb2e758709b7f2c98513e8e'
limits = WorkerLimits(cpu_percent=5, memory_bytes=256*1024**2)
pressure = SystemRamPressure()
began = time.monotonic()
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
state = {'state': 'PREPARING_PINNED_GRANITE_ASSETS', 'startedAt': now(), 'pid': os.getpid(),
         'createdAt': psutil.Process().create_time(), 'repository': repo, 'revision': rev,
         'cache': str(cache), 'completed': [], 'newNeuralCalls': 0, 'newTrainingUpdates': 0,
         'rawAudioUploaded': False, 'qualityQualified': False, 'saleQualified': False}

def save(**values):
    state.update(values, observedAt=now(), elapsedSeconds=time.monotonic()-began, limits=limits.query())
    atomic_json(OUT/'state.json', state, progress=True)

def check():
    assert not pressure.low() and psutil.virtual_memory().available >= 3414499000, 'Original realRAM floor'
    assert time.monotonic()-began < 1800, 'Bounded30min asset acquisition'
    assert not (OUT/'stop.request').exists(), 'Owned stop request'
    assert shutil.disk_usage(cache).free > 20*1024**3, 'E disk reserve'

def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Companion-pinned-reference/1.0'}), timeout=45)

try:
    save()
    with request(f'https://huggingface.co/api/models/{repo}/revision/{rev}?blobs=true') as response:
        info = json.load(response)
    assert info['sha'] == rev and not info.get('gated')
    entries = {x['rfilename']: x for x in info['siblings']}
    index = json.loads((C/'model.safetensors.index.json').read_text(encoding='utf-8'))
    names = ['README.md', 'config.json', 'model.safetensors.index.json', 'preprocessor_config.json',
             'processor_config.json', 'tokenizer.json', 'tokenizer_config.json',
             'special_tokens_map.json', 'added_tokens.json', 'vocab.json']
    names += sorted(set(index['weight_map'].values()))
    assert all(n in entries for n in names) and 'out_llm.safetensors' not in names
    assets = []
    for name in names:
        entry = entries[name]
        assets.append({'name': name, 'bytes': entry['size'],
                       'expectedSha256': entry.get('lfs', {}).get('sha256'),
                       'url': f'https://huggingface.co/{repo}/resolve/{rev}/{name}'})
    atomic_json(OUT/'asset-plan.json', {'repository': repo, 'revision': rev, 'assets': assets,
                                      'expectedBytes': sum(x['bytes'] for x in assets)})
    for asset in assets:
        check()
        name, expected = asset['name'], asset['expectedSha256']
        dest = cache/name
        assert not dest.exists(), 'Preserve unexpected existing cache file: '+name
        part = dest.with_name(dest.name+'.part')
        assert not part.exists(), 'Preserve interrupted asset; no automatic restart'
        save(state='ACQUIRING_ONE_PINNED_GRANITE_REFERENCE', activeFile=name, fileBytes=0, expectedFileBytes=asset['bytes'])
        count, digest, last = 0, hashlib.sha256(), time.monotonic()
        # Reuse exact pinned metadata already inspected; large assets are streamed.
        if (C/name).is_file():
            raw = (C/name).read_bytes()
            assert len(raw) == asset['bytes']
            part.write_bytes(raw)
            digest.update(raw)
            count = len(raw)
        else:
            with request(asset['url']) as response, part.open('xb') as f:
                while chunk := response.read(1024**2):
                    count += len(chunk)
                    assert count <= asset['bytes']
                    f.write(chunk)
                    digest.update(chunk)
                    check()
                    if time.monotonic()-last >= 5:
                        save(fileBytes=count)
                        last = time.monotonic()
        assert count == asset['bytes'], 'Truncated asset: '+name
        actual = digest.hexdigest()
        assert expected is None or actual == expected, 'PublisherSHA256 mismatch: '+name
        part.replace(dest)
        state['completed'].append({'name': name, 'file': str(dest), 'bytes': count, 'sha256': actual,
                                   'publisherSha256Verified': expected is not None})
        save(fileBytes=count)
    # The metadata used to select the reference stays byte-identical.
    for name in ['config.json', 'model.safetensors.index.json', 'preprocessor_config.json', 'processor_config.json']:
        assert (cache/name).read_bytes() == (C/name).read_bytes()
    save(state='COMPLETE_PINNED_GRANITE_REFERENCE_ASSETS_NO_MODEL_EXECUTION', activeFile=None)
    atomic_json(OUT/'completed.json', state)
    print(json.dumps({'state': state['state'], 'cache': str(cache), 'files': len(state['completed']),
                      'bytes': sum(x['bytes'] for x in state['completed']), 'seconds': time.monotonic()-began}), flush=True)
except BaseException as error:
    save(state='FAILED_PINNED_GRANITE_ASSET_ACQUISITION_RETAINED', error=repr(error), traceback=traceback.format_exc())
    atomic_json(OUT/'completed.json', state)
    raise
finally:
    pressure.close()
