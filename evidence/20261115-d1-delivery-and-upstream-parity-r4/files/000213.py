"""Bounded CPU validation of frozen author speaker encoder on audio-only inputs.

This measures reference usability, not diarization or word recovery accuracy.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import wave

for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure

read = lambda p: json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def write(p, value):
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    os.replace(temp, p)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', required=True)
    args = parser.parse_args()
    control = Path(args.control)
    inputs = read(control / 'audio-only.json')
    protocol = read(control / 'protocol.json')
    assert sha(__file__) == protocol['workerSha256']
    assert sha(control / 'audio-only.json') == protocol['audioOnlySha256']
    limits = WorkerLimits(cpu_percent=5, memory_bytes=2 * 1024**3)
    pressure = SystemRamPressure()
    started = time.perf_counter()
    result = {'state': 'STARTED', 'inputsSha256': protocol['audioOnlySha256'],
              'workerSha256': protocol['workerSha256'], 'vectors': [],
              'modelDevice': 'cpu', 'weightsChanged': False, 'answersRead': False}
    path = control / 'encoder-result.json'
    write(path, result)
    def check():
        if pressure.low():
            raise RuntimeError('Windows reports actual low physical memory; stop this worker')
    try:
        check()
        sys.path.insert(0, inputs['torchaudioSource'])
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        import numpy as np
        ready = read(inputs['modelReady'])
        assert sha(inputs['modelReady']) == protocol['modelReadySha256']
        for entry in ready['files']:
            assert sha(entry['file']) == entry['sha256'], entry['file']
        spec = importlib.util.spec_from_file_location('pinned_ps4_author', Path(ready['sourceRoot']) / 'inference.py')
        author = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(author)
        check()
        base = author.build_model(torch.device('cpu'))
        checkpoint = torch.load(ready['weight'], map_location='cpu', weights_only=True, mmap=True)
        state = checkpoint.get('model', checkpoint.get('state_dict', checkpoint))
        if all(key.startswith('module.') for key in state):
            state = {key[7:]: value for key, value in state.items()}
        base.load_state_dict(state, strict=True)
        assert all(torch.equal(value, state[key]) for key, value in base.state_dict().items())
        base.eval().requires_grad_(False)
        del checkpoint, state
        gc.collect()
        from companion_tse_reference_bank_20261108 import encode_reference
        def load(packet):
            check()
            assert sha(packet['audio']) == packet['audioSha256']
            with wave.open(packet['audio'], 'rb') as audio:
                assert (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) == (1, 16000, 2)
                value = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype('float32') / 32768.0
            return torch.from_numpy(value).unsqueeze(0)
        prototypes = {}
        for kind in ('profiles', 'queries', 'calibration'):
            for packet in inputs[kind]:
                at = time.perf_counter()
                embedding = encode_reference(base, load(packet), torch=torch)
                row = {'kind': kind, 'id': packet['id'], 'audioSha256': packet['audioSha256'],
                       'vector': embedding.flatten().tolist(), 'seconds': time.perf_counter() - at}
                if kind == 'profiles':
                    group = packet['nativePerson']
                    prototypes.setdefault(group, []).append(embedding)
                    row['nativePerson'] = group
                elif kind == 'queries':
                    scores = {key: float(torch.nn.functional.cosine_similarity(
                        embedding, torch.stack(values).mean(0)).item()) for key, values in prototypes.items()}
                    ranked = sorted(scores, key=scores.get, reverse=True)
                    row.update(predictedNativePerson=ranked[0], cosineByPerson=scores,
                               topTwoMargin=scores[ranked[0]] - scores[ranked[1]])
                result['vectors'].append(row)
                result.update(state='RUNNING', elapsedSeconds=time.perf_counter() - started, limits=limits.query())
                write(path, result)
                print(json.dumps({'id': packet['id'], 'kind': kind, 'seconds': round(row['seconds'], 3)}, ensure_ascii=False), flush=True)
        result.update(state='COMPLETE', elapsedSeconds=time.perf_counter() - started, limits=limits.query())
        write(path, result)
    except BaseException as exc:
        result.update(state='FAILED', error=type(exc).__name__ + ': ' + str(exc),
                      elapsedSeconds=time.perf_counter() - started, limits=limits.query())
        write(path, result)
        raise

if __name__ == '__main__':
    main()
