"""Pin one official reference; inspect small metadata, never fetch weights/code."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib, json, urllib.request

root = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
root.mkdir(parents=True, exist_ok=False)
api_path = Path('work/english_accuracy_reference_api_20261117.json')
api = json.loads(api_path.read_text(encoding='utf-8'))
repo, revision = api['id'], api['sha']
assert repo == 'ibm-granite/granite-speech-4.1-2b' and api['license'] == 'apache-2.0'
names = ['config.json', 'model.safetensors.index.json', 'preprocessor_config.json', 'processor_config.json', 'README.md']

def get(name):
    url = f'https://huggingface.co/{repo}/resolve/{revision}/{name}'
    request = urllib.request.Request(url, headers={'User-Agent': 'Companion-evidence-inspection/1.0'})
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read(2 * 1024**2 + 1)
    assert len(body) <= 2 * 1024**2, 'Metadata unexpectedly large'
    path = root / name
    path.write_bytes(body)
    return {'file': str(path), 'url': url, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

with ThreadPoolExecutor(max_workers=3) as pool:
    files = list(pool.map(get, names))
config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
index = json.loads((root / 'model.safetensors.index.json').read_text(encoding='utf-8'))
processor = json.loads((root / 'processor_config.json').read_text(encoding='utf-8'))
site = Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
local_model_file = site / 'transformers/models/granite_speech/modeling_granite_speech.py'
local_config_file = site / 'transformers/models/granite_speech/configuration_granite_speech.py'
receipt = {
    'at': datetime.now().astimezone().isoformat(timespec='seconds'),
    'state': 'ONE_ENGLISH_ACCURACY_REFERENCE_PINNED_METADATA_ONLY_NO_MODEL_EXECUTION',
    'repository': repo, 'revision': revision, 'licenseIdentifier': api['license'],
    'apiSnapshotSha256': hashlib.sha256(api_path.read_bytes()).hexdigest(),
    'files': files, 'architecture': config.get('architectures'), 'modelType': config.get('model_type'),
    'publishedDtype': config.get('dtype', config.get('torch_dtype')),
    'totalCheckpointTensorBytes': index['metadata']['total_size'],
    'checkpointShards': sorted(set(index['weight_map'].values())),
    'processorClass': processor.get('processor_class'),
    'existingTransformersImplementationFiles': [
        {'file': str(p), 'exists': p.is_file(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}
        for p in (local_model_file, local_config_file)
    ],
    'referenceFrameworkDeclaredByPublisher': 'Native Transformers and llama.cpp, per pinned README. Existence of source does not prove the new checkpoint runs unchanged here.',
    'privateMemoryLimitBytes': 2 * 1024**3, 'minimumAvailableRamBytes': 3414499000,
    'admission': 'Check dtype/parameter handling, audio coverage and actual memory with an original fixed clip before any all-clip run. Do not initialize GPU or implement a custom engine port during metadata inspection.',
    'largeWeightsDownloaded': False, 'remotePythonExecuted': False,
    'torchImported': False, 'newNeuralCalls': 0, 'newTrainingUpdates': 0,
    'qualityQualified': False, 'saleQualified': False,
}
(root / 'metadata-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in receipt.items() if k != 'files'}, ensure_ascii=False, indent=2))
