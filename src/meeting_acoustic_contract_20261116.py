"""Lightweight contracts for one native acoustic/bridge SFT candidate.

This module imports no neural runtime. All labels remain verbatim; validation
references are held by the independent scorer and never enter the GPU worker.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import random
import struct

PREFIXES = ('model.audio_tower.', 'model.multi_modal_projector.')
TRAINABLE_PARAMETERS = 317477504


def accepted_output(output):
    if output.get('exactDigitalSilence'):
        return (output.get('text') == '' and output.get('generatedIds') == []
                and output.get('neuralInferencePerformed') is False
                and output.get('naturalEos') is None)
    return output.get('naturalEos') is True and output.get('neuralInferencePerformed') is True


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def select_gpu(devices):
    matches = [d for d in devices if 'RX 6800 XT' in d['name']
               and d.get('architecture', '').startswith('gfx1030')]
    require(len(matches) == 1, 'Exactly one actual RX6800XT/gfx1030 required; no CPU/iGPU fallback')
    return matches[0]


def balanced_order(rows, seed):
    buckets = {lang: [i for i,r in enumerate(rows) if r['language'] == lang]
               for lang in ['English', 'Chinese']}
    require(sum(map(len,buckets.values())) == len(rows), 'Unexpected training language')
    rng = random.Random(seed)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    result = []
    for n in range(max(map(len,buckets.values()))):
        for lang in ['English', 'Chinese']:
            if n < len(buckets[lang]):
                result.append(buckets[lang][n])
    require(sorted(result) == list(range(len(rows))), 'Training order duplicated/dropped an example')
    return result


def padded_labels(prefixes, targets, pad_id, side='right'):
    """Explicit target-only masking, including unequal left/right padding."""
    require(side in ('left', 'right'), 'Invalid padding side')
    require(len(prefixes) == len(targets) > 0, 'Unequal/empty training batch')
    require(all(prefixes) and all(targets), 'Empty prefix or target')
    width = max(len(p)+len(t) for p,t in zip(prefixes, targets))
    ids, masks, labels = [], [], []
    for prefix, target in zip(prefixes, targets):
        values = list(prefix)+list(target)
        padding = width-len(values)
        label = [-100]*len(prefix)+list(target)
        attention = [1]*len(values)
        if side == 'right':
            ids.append(values+[pad_id]*padding)
            labels.append(label+[-100]*padding)
            masks.append(attention+[0]*padding)
        else:
            ids.append([pad_id]*padding+values)
            labels.append([-100]*padding+label)
            masks.append([0]*padding+attention)
    return {'input_ids': ids, 'attention_mask': masks, 'labels': labels}


def training_rows(packet):
    for key in ['trainJsonl', 'provenance']:
        require(sha(packet[key]['file']) == packet[key]['sha256'], key+' changed')
    examples = read(packet['provenance']['file'])
    lines = [json.loads(line) for line in Path(packet['trainJsonl']['file']).read_text(encoding='utf-8').splitlines()]
    require(len(examples) == len(lines) == 944, 'Frozen944-example pilot required')
    require(Counter(r['language'] for r in examples) == {'English':475, 'Chinese':469}, 'Language coverage changed')
    for example,line in zip(examples,lines):
        require(example['role'] == 'train-only', 'Evaluation example in training')
        require(not example['referenceOverlapPresent'] and not example['labelWordsEdited'], 'Altered/overlap labels')
        require(line == {'audio': example['audio'], 'text': 'language '+example['language']+'<asr_text>'+example['text']}, 'Training target/audio changed')
    return examples


def verify_bindings(packet):
    for item in packet['files']:
        require(sha(item['file']) == item['sha256'], 'Frozen source/config changed: '+item['file'])
    require(packet['training']['trainablePrefixes'] == list(PREFIXES), 'Training scope changed')
    require(packet['training']['epochs'] == 1 and packet['training']['gradientAccumulation'] == 2, 'Fixed pilot recipe changed')
    require(packet['resources']['privateMemoryBytes'] == 2*1024**3, 'Original private RAM guard changed')
    require(packet['resources']['minimumAvailableBytes'] == int(3.18*1024**3), 'RAM recovery floor changed')
    require(packet['resources']['stableRamSeconds'] == 60, 'RAM recovery stability changed')
    require(packet['target']['accuracy'] == .98 and packet['target']['floorAccuracy'] == .95, 'Owner quality target changed')


def tensor_header(path):
    path = Path(path)
    with path.open('rb') as stream:
        raw = stream.read(8)
        require(len(raw) == 8, 'Truncated tensor header')
        size = struct.unpack('<Q', raw)[0]
        require(0 < size <= 16*1024**2, 'Invalid tensor header size')
        header_bytes = stream.read(size)
        require(len(header_bytes) == size, 'Truncated tensor JSON')
        header = json.loads(header_bytes)
    return header, 8+size


def write_float_checkpoint(path, tensors, chunk_reader, check_stop=lambda:None):
    """Stream F32 tensors without constructing a full host-side state_dict.

``tensors`` holds name/shape only. ``chunk_reader(name, first, count)`` returns
    at most1MiB of raw little-endian F32 bytes. Publication of the receipt is the
    caller's final commit, after this immutable tensor file is complete.
    """
    path = Path(path)
    require(not path.exists(), 'Checkpoint is immutable')
    header, offset = {}, 0
    for name,shape in tensors:
        count = 1
        for dim in shape:
            require(isinstance(dim,int) and dim > 0, 'Invalid tensor dimensions')
            count *= dim
        require(name not in header and name != '__metadata__', 'Duplicate tensor key')
        header[name] = {'dtype':'F32', 'shape':list(shape), 'data_offsets':[offset,offset+count*4]}
        offset += count*4
    encoded = json.dumps(header,separators=(',',':')).encode()
    encoded += b' '*((-len(encoded)) % 8)
    pending = path.with_name(path.name+'.pending')
    with pending.open('xb') as stream:
        stream.write(struct.pack('<Q',len(encoded))); stream.write(encoded)
        for name,meta in header.items():
            count = (meta['data_offsets'][1]-meta['data_offsets'][0])//4
            for start in range(0,count,262144):
                check_stop()
                n = min(262144,count-start)
                block = chunk_reader(name,start,n)
                require(len(block) == n*4, 'Truncated checkpoint tensor chunk')
                stream.write(block)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    require(pending.stat().st_size == 8+len(encoded)+offset, 'Incomplete checkpoint')
    pending.rename(path)
    return {'sha256':sha(path), 'bytes':path.stat().st_size, 'tensors':len(header)}


def committed_checkpoint(run, binding):
    pointer = read(Path(run)/'latest-checkpoint.json')
    require(pointer['binding'] == binding, 'Checkpoint belongs to a different recipe/data/source')
    name = pointer['receipt']
    require(Path(name).name == name, 'Checkpoint receipt escaped run')
    require(sha(Path(run)/name) == pointer['receiptSha256'], 'Checkpoint progress/RNG receipt changed')
    receipt = read(Path(run)/name)
    require(receipt['binding'] == binding, 'Checkpoint receipt binding mismatch')
    require(Path(receipt['file']).name == receipt['file'], 'Checkpoint escaped run')
    path = Path(run)/receipt['file']
    require(sha(path) == receipt['sha256'], 'Committed checkpoint is missing or corrupted')
    return path,receipt
