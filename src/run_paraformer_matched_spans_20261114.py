"""Existing installed Paraformer weights on frozen audio-only comparison spans.

Model-level CPU comparator, not an installed application benchmark. Never reads
reference text, VAD labels, speaker labels, or another recognizer's output.
"""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
import wave

from practical_io_20261107 import atomic_json, stop_owned_family
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def worker(control):
    limits = WorkerLimits(cpu_percent=5, memory_bytes=2*1024**3)
    os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    protocol = read(control / 'protocol.json')
    assert sha(__file__) == protocol['workerSourceSha256']
    for path, digest in protocol['inputFiles'].items():
        assert sha(path) == digest
    case, = read(control / 'audio-only.json')
    assert not any('reference' in key.lower() for key in case)
    spans = read(control / 'audio-only-spans.json')
    assert sha(case['audio']) == case['audioSha256']
    assert spans[0]['startSample'] == 0
    assert all(a['endSample'] == b['startSample'] for a, b in zip(spans, spans[1:]))
    with wave.open(case['audio'], 'rb') as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        assert spans[-1]['endSample'] == audio.getnframes()
    binding = {'protocolSha256': sha(control / 'protocol.json'),
               'audioSha256': case['audioSha256'],
               'spansSha256': sha(control / 'audio-only-spans.json')}
    target = control / 'worker-state.json'
    assert not target.exists(), 'Preserve prior attempt; no implicit retries'
    state = {'state': 'LOADING_EXISTING_PARAFORMER', 'startedAt': now(), 'pid': os.getpid(),
             'binding': binding, 'totalSpans': len(spans), 'completedSpans': 0,
             'newNeuralCalls': 0, 'referenceInput': False, 'speakerInput': False,
             'runtimeIsInstalledProduct': False, 'qualityQualified': False}

    def save():
        state['limits'] = limits.query()
        atomic_json(target, state)

    save()
    pressure = SystemRamPressure()
    try:
        import numpy as np
        import sherpa_onnx
        assert sherpa_onnx.__version__ == protocol['sherpaVersion']
        for path, digest in protocol['runtimeFiles'].items():
            assert sha(path) == digest
        for path, digest in protocol['modelFiles'].items():
            assert sha(path) == digest
        assert not pressure.low(), 'Actual Windows low-memory signal'
        started = time.perf_counter()
        recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(**protocol['recognizerArguments'])
        state['modelLoadSeconds'] = time.perf_counter() - started
        state['recognizerConfig'] = str(recognizer.config)
        save()
        nodes = control / 'nodes'
        nodes.mkdir()
        utterances, texts = [], []
        with wave.open(case['audio'], 'rb') as audio:
            for span in spans:
                assert not pressure.low() and not (control / 'stop.request').exists()
                lo, hi = span['startSample'], span['endSample']
                audio.setpos(lo)
                samples = np.frombuffer(audio.readframes(hi-lo), dtype='<i2').astype(np.float32)/32768
                assert len(samples) == hi-lo
                if span['paddingSamples']:
                    samples = np.pad(samples, (0, span['paddingSamples']))
                stream = recognizer.create_stream()
                stream.accept_waveform(16000, samples)
                started = time.perf_counter()
                recognizer.decode_stream(stream)
                elapsed = time.perf_counter() - started
                result = stream.result
                raw = {**span, 'text': result.text, 'tokens': list(result.tokens),
                       'timestamps': list(result.timestamps), 'durations': list(result.durations),
                       'language': result.lang, 'inferenceSeconds': elapsed,
                       'modelInputSamples': len(samples), 'inputNotTruncated': True,
                       'neuralInferencePerformed': True,
                       'nonAutoregressiveRecognizerNoEosClaim': True}
                canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                atomic_json(nodes / ('%06d.json' % span['index']),
                            {'binding': binding, 'raw': raw,
                             'rawSha256': hashlib.sha256(canonical).hexdigest()})
                texts.append(result.text)
                utterances.append({'startMs': round(lo/16), 'endMs': round(hi/16),
                                   'text': result.text, 'speaker': None})
                state.update(state='RUNNING_PARAFORMER_MATCHED_SPANS', completedSpans=len(texts),
                             completedSample=hi, newNeuralCalls=len(texts))
                save()
                del stream, result, samples
                time.sleep(1)
        # Newline is the same inter-root separator used by the other frozen arm.
        document = {'isFinal': True, 'text': '\n'.join(texts), 'utterances': utterances}
        atomic_json(control / 'model-output.json', document)
        state.update(state='COMPLETE_PARAFORMER_MATCHED_SPANS_UNSCORED', finishedAt=now(),
                     modelOutputSha256=sha(control / 'model-output.json'),
                     allOriginalAudioSamplesCoveredOnce=True, allAsrTextPreserved=True)
    except BaseException as error:
        state.update(state='FAILED_PARAFORMER_RETAINED_NO_AUTOMATIC_RETRY',
                     error=repr(error), traceback=traceback.format_exc(), finishedAt=now())
        raise
    finally:
        pressure.close()
        save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--worker', action='store_true')
    args = parser.parse_args()
    control = args.control.resolve()
    if args.worker:
        worker(control)
        return
    import psutil
    from run_paired_fixed_asr_20261109 import resume_resources
    from companion_local_pcm_session_20261114 import exclusive_file
    target = control / 'run.json'
    assert not target.exists()
    state = {'state': 'PREPARING_PARAFORMER_COMPARATOR', 'startedAt': now(),
             'automaticRetries': 0, 'workerSourceSha256': sha(__file__),
             'qualityQualified': False}
    pressure = SystemRamPressure()
    child = owned = None
    peak = 0
    try:
        with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
            worker_names = {'practical_nemotron_worker_20261107.py',
                            'practical_qwen_boundaries_worker_20261107.py',
                            'companion_local_qwen_worker_20261114.py',
                            'practical_alignment_session_worker_20261114.py'}
            for process in psutil.process_iter(['cmdline']):
                try:
                    assert not any(Path(arg).name in worker_names for arg in process.info['cmdline'] or []), 'Another neural worker is active'
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            resources = resume_resources(Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-r2-runs/near-N_SPK8015/task.json'))
            state['resourcesBeforeStage'] = resources
            if not resources['ready']:
                state['state'] = 'DEFERRED_PARAFORMER_ORIGINAL_RAM_GATE'
                return
            started = last_progress = time.perf_counter()
            completed = -1
            with (control / 'worker.log').open('xb') as log:
                child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--control', str(control), '--worker'],
                                         stdout=log, stderr=subprocess.STDOUT,
                                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                owned = psutil.Process(child.pid)
                state.update(state='RUNNING_PARAFORMER_COMPARATOR', activePid=child.pid)
                atomic_json(target, state)
                next_sample = 0
                while child.poll() is None:
                    low = pressure.low()
                    if low or (control / 'stop.request').exists() or time.perf_counter()-last_progress > 600:
                        state.update(state='STOPPED_PARAFORMER_RETAINED',
                                     stopReason='actual_windows_low_ram' if low else 'explicit_stop_or_progress_deadline')
                        stop_owned_family(child, owned)
                        break
                    try:
                        private = sum(p.memory_info().private for p in [owned] + owned.children(recursive=True))
                        peak = max(peak, private)
                        point = read(control / 'worker-state.json').get('completedSpans') if (control / 'worker-state.json').exists() else None
                        if point != completed:
                            completed, last_progress = point, time.perf_counter()
                        if time.perf_counter() >= next_sample:
                            with (control / 'resources.jsonl').open('a', encoding='utf-8') as output:
                                output.write(json.dumps({'at': now(), 'availableBytes': psutil.virtual_memory().available,
                                                         'privateBytes': private, 'completedSpans': completed})+'\n')
                            next_sample = time.perf_counter()+5
                    except psutil.Error:
                        pass
                    time.sleep(.5)
            state.update(exitCode=child.returncode, wholeOwnedProcessSeconds=time.perf_counter()-started)
            terminal = read(control / 'worker-state.json') if (control / 'worker-state.json').exists() else {}
            if not state['state'].startswith('STOPPED_'):
                state['state'] = 'COMPLETE_PARAFORMER_COMPARATOR' if child.returncode == 0 and terminal.get('state') == 'COMPLETE_PARAFORMER_MATCHED_SPANS_UNSCORED' else 'FAILED_PARAFORMER_COMPARATOR_RETAINED'
    except BaseException as error:
        state.update(state='FAILED_PARAFORMER_CONTROLLER_RETAINED', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        if child is not None and child.poll() is None:
            stop_owned_family(child, owned)
        pressure.close()
        state.pop('activePid', None)
        state.update(finishedAt=now(), privatePeakBytes=peak)
        atomic_json(target, state)
        print(json.dumps(state, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
