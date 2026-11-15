"""Same frozen sherpa diarizer through its pointer C ABI, avoiding Python's
std::vector<float> copy of an entire meeting. PCM stays in a mapped float file.
The models, clustering and duration policy remain explicit and unchanged.
"""
from pathlib import Path
from datetime import datetime
import argparse
import ctypes as ct
import hashlib
import json
import os
import time
import traceback
import wave

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json


class SegModel(ct.Structure):
    _fields_ = [('model', ct.c_char_p)]


class Segmentation(ct.Structure):
    _fields_ = [('pyannote', SegModel), ('num_threads', ct.c_int32),
                ('debug', ct.c_int32), ('provider', ct.c_char_p)]


class Embedding(ct.Structure):
    _fields_ = [('model', ct.c_char_p), ('num_threads', ct.c_int32),
                ('debug', ct.c_int32), ('provider', ct.c_char_p)]


class Clustering(ct.Structure):
    _fields_ = [('num_clusters', ct.c_int32), ('threshold', ct.c_float)]


class Configuration(ct.Structure):
    _fields_ = [('segmentation', Segmentation), ('embedding', Embedding),
                ('clustering', Clustering), ('min_duration_on', ct.c_float),
                ('min_duration_off', ct.c_float)]


class Segment(ct.Structure):
    _fields_ = [('start', ct.c_float), ('end', ct.c_float), ('speaker', ct.c_int32)]


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    args = parser.parse_args()
    control = args.control.resolve()
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')
    protocol = read(control / 'protocol.json')
    case = read(control / 'audio-only.json')[args.index]
    assert not any('reference' in key.lower() for key in case)
    assert protocol['runtime']['cpuPercent'] == 5 and protocol['runtime']['privateBudgetBytes'] == 2*1024**3
    assert protocol['pointerWorkerSha256'] == sha(__file__)
    assert protocol['clustering'] == {'numClusters': -1, 'threshold': .5}
    limits = WorkerLimits(cpu_percent=5, memory_bytes=2*1024**3)
    out = control / 'results' / case['meeting']
    out.mkdir(parents=True, exist_ok=False)
    state = {'state': 'LOADING_CPU_POINTER_DIARIZATION', 'startedAt': now(),
             'pid': os.getpid(), 'meeting': case['meeting'], 'audioSha256': case['audioSha256'],
             'referencePassedToWorker': False, 'modelGpuUsed': False,
             'sourceSha256': sha(__file__), 'pythonWholeAudioVectorCopy': False,
             'inputFloatBufferMapped': True, 'qualityQualified': False}

    def save():
        state['limits'] = limits.query()
        atomic_json(out / 'state.json', state, progress=True)

    started = time.perf_counter()
    lib = cookie = audio = None
    diarizer = result = segments = None
    save()
    try:
        assert sha(case['audio']) == case['audioSha256']
        for key in ['segmentation', 'embedding']:
            assert sha(protocol[key]['model']) == protocol[key]['sha256']
        for path, digest in protocol['cAbiRuntime']['files'].items():
            assert sha(path) == digest
        import numpy as np
        runtime = protocol['cAbiRuntime']
        cookie = os.add_dll_directory(str(Path(runtime['library']).parent))
        lib = ct.CDLL(runtime['library'])
        void = ct.c_void_p
        fptr = ct.POINTER(ct.c_float)
        callback_type = ct.CFUNCTYPE(ct.c_int32, ct.c_int32, ct.c_int32, void)
        definitions = {
            'SherpaOnnxGetVersionStr': ([], ct.c_char_p),
            'SherpaOnnxCreateOfflineSpeakerDiarization': ([ct.POINTER(Configuration)], void),
            'SherpaOnnxDestroyOfflineSpeakerDiarization': ([void], None),
            'SherpaOnnxOfflineSpeakerDiarizationGetSampleRate': ([void], ct.c_int32),
            'SherpaOnnxOfflineSpeakerDiarizationProcessWithCallback': ([void, fptr, ct.c_int32, callback_type, void], void),
            'SherpaOnnxOfflineSpeakerDiarizationResultGetNumSegments': ([void], ct.c_int32),
            'SherpaOnnxOfflineSpeakerDiarizationResultSortByStartTime': ([void], ct.POINTER(Segment)),
            'SherpaOnnxOfflineSpeakerDiarizationDestroySegment': ([ct.POINTER(Segment)], None),
            'SherpaOnnxOfflineSpeakerDiarizationDestroyResult': ([void], None)}
        for name, (argtypes, restype) in definitions.items():
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = argtypes, restype
        assert lib.SherpaOnnxGetVersionStr().decode() == '1.13.4'
        config = Configuration(
            Segmentation(SegModel(protocol['segmentation']['model'].encode()), 1, 0, b'cpu'),
            Embedding(protocol['embedding']['model'].encode(), 1, 0, b'cpu'),
            Clustering(-1, .5), protocol['minDurationOn'], protocol['minDurationOff'])
        diarizer = lib.SherpaOnnxCreateOfflineSpeakerDiarization(ct.byref(config))
        assert diarizer, 'Native diarizer creation failed'
        assert lib.SherpaOnnxOfflineSpeakerDiarizationGetSampleRate(diarizer) == 16000
        state.update(modelLoadSeconds=time.perf_counter()-started, actualConfig={
            'numThreads': 1, 'provider': 'cpu', 'numClusters': -1, 'threshold': .5,
            'minDurationOn': protocol['minDurationOn'], 'minDurationOff': protocol['minDurationOff']})
        save()
        mapped = Path(protocol['mappedInputRoot']) / (case['meeting']+'.float32.npy')
        mapped.parent.mkdir(parents=True, exist_ok=True)
        assert not mapped.exists()
        with wave.open(case['audio'], 'rb') as source:
            assert (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) == (1, 2, 16000, 'NONE')
            count = source.getnframes()
            assert count/16000 == case['audioSeconds'] and count < 2**31
            audio = np.lib.format.open_memmap(mapped, mode='w+', dtype=np.float32, shape=(count,))
            for offset in range(0, count, 65536):
                values = np.frombuffer(source.readframes(min(65536, count-offset)), dtype='<i2')
                np.divide(values, 32768., out=audio[offset:offset+len(values)], casting='unsafe')
            audio.flush()
        assert audio.dtype == np.float32 and audio.flags.c_contiguous and audio.strides == (4,)
        state.update(state='DIARIZING_FULL_AUDIO', inputSamples=count, audioSeconds=count/16000,
                     mappedInputBytes=audio.nbytes, mappedInputSha256=sha(mapped))
        save()
        tick = last_save = time.perf_counter()

        @callback_type
        def progress(done, total, _):
            nonlocal last_save
            state.update(embeddingChunksCompleted=done, embeddingChunksTotal=total,
                         inferenceElapsedSeconds=time.perf_counter()-tick)
            if done == total or time.perf_counter()-last_save >= 2:
                save()
                last_save = time.perf_counter()
            # This ABI's callback is progress-only. The outer owned controller
            # enforces cancellation/low-RAM even during native computation.
            return 0

        result = lib.SherpaOnnxOfflineSpeakerDiarizationProcessWithCallback(
            diarizer, audio.ctypes.data_as(fptr), count, progress, None)
        assert result, 'Native complete-meeting processing failed'
        size = lib.SherpaOnnxOfflineSpeakerDiarizationResultGetNumSegments(result)
        segments = lib.SherpaOnnxOfflineSpeakerDiarizationResultSortByStartTime(result)
        assert segments and size > 0
        rows = [{'start': float(segments[i].start), 'end': float(segments[i].end),
                 'speaker': int(segments[i].speaker)} for i in range(size)]
        assert all(0 <= r['start'] < r['end'] <= case['audioSeconds']+.1 for r in rows)
        assert not (control / 'stop.request').exists()
        atomic_json(out / 'speaker-journal.json', {**case, 'segments': rows,
                    'scope': 'Same published segmentation/embedding and fixed complete-link policy; pointer ABI and mapped input remove whole-audio host copies. Anonymous identities, no reference input.'})
        rttm = out / 'predicted.rttm'
        rttm.write_text(''.join(f"SPEAKER {case['meeting']} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> speaker_{r['speaker']} <NA> <NA>\n" for r in rows), encoding='utf-8')
        if 'cachedControlJournal' in protocol:
            prior = read(protocol['cachedControlJournal'])
            assert sha(protocol['cachedControlJournal']) == protocol['cachedControlJournalSha256']
            assert prior['audioSha256'] == case['audioSha256'] and prior['segments'] == rows, 'Pointer ABI differs from original cached Python output'
            state['exactCachedPythonSegmentParity'] = True
        state.update(state='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED', inferenceSeconds=time.perf_counter()-tick,
                     predictedSpeakers=len({r['speaker'] for r in rows}), segments=len(rows), rttmSha256=sha(rttm),
                     allOriginalAudioSamplesSubmitted=True)
    except BaseException as error:
        state.update(state='FAILED_RETAINED', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        if lib is not None:
            if segments: lib.SherpaOnnxOfflineSpeakerDiarizationDestroySegment(segments)
            if result: lib.SherpaOnnxOfflineSpeakerDiarizationDestroyResult(result)
            if diarizer: lib.SherpaOnnxDestroyOfflineSpeakerDiarization(diarizer)
        if audio is not None:
            audio.flush()
            audio._mmap.close()
        if cookie is not None: cookie.close()
        state.update(finishedAt=now(), wholeWorkerSeconds=time.perf_counter()-started)
        save()
        atomic_json(out / 'completed-state.json', state)
        print(json.dumps(state, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
