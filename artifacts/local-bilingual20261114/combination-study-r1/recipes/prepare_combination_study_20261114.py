from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
CACHE = Path('E:/CodexData/Companion/.model-cache/ordinary-combination-study-20261114')
sys.path.insert(0, str(SRC))
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    import psutil
    limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
    assert not CONTROL.exists() and not CACHE.exists()
    assert psutil.disk_usage('E:/').free > 30*1024**3
    CONTROL.mkdir(parents=True)
    CACHE.mkdir()
    folder = Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/official-annotations')
    candidates = []
    for path in sorted(folder.glob('20200623_S_*.TextGrid')):
        rows = [r for r in read_reference_intervals(path) if any(c.isalnum() for c in r['text'])]
        events = {}
        for row in rows:
            events[row['start']] = events.get(row['start'], 0)+1
            events[row['end']] = events.get(row['end'], 0)-1
        count, previous, overlap = 0, 0., 0.
        for point, delta in sorted(events.items()):
            if count >= 2:
                overlap += point-previous
            count += delta
            previous = point
        end = max(r['end'] for r in rows)
        candidates.append({'meeting': path.stem, 'reference': str(path), 'referenceSha256': sha(path),
                           'people': len({r['speaker'] for r in rows}), 'utterances': len(rows),
                           'lastReferenceEnd': end, 'overlapSeconds': overlap, 'overlapFractionOfAnnotatedExtent': overlap/end})
    chosen = next(row for row in candidates if row['lastReferenceEnd'] >= 1800 and row['people'] >= 4
                  and row['overlapFractionOfAnnotatedExtent'] <= .02 and row['meeting'] != '20200623_S_R001S01C01')
    assert chosen['meeting'] == '20200623_S_R001S07C01'
    metadata = read(ROOT / 'docs/handoffs/20261108-target-activity-adaptation/pinned-source-file-metadata.json')
    entry = next(row for row in metadata['train_S/wav'] if chosen['meeting'] in row['path'])
    selection = {'at': datetime.now().astimezone().isoformat(timespec='seconds'),
                 'state': 'FROZEN_BEFORE_NEW_AUDIO_INFERENCE', 'candidateOrder': candidates, 'selected': chosen,
                 'rule': 'First official first-day Train_S entry with annotated extent>=30min,>=4people,<=2%annotated overlap, excluding the old S01 adaptation session. Selection never uses model output.',
                 'sourceMetadata': entry, 'fullAudioWillBeKept': True, 'finalHoldoutOpened': False,
                 'notPretrainingIndependentOrSaleHoldout': True}
    write(CONTROL / 'selection.json', selection)
    revision = 'aada72727856313b19d4a030383c426364931dbf'
    source = {'meeting': chosen['meeting'], 'fileSize': entry['size'], 'expectedWholeFileLfsSha256': entry['lfs']['oid'],
              'url': 'https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+revision+'/'+entry['path']}
    protocol = {'at': selection['at'], 'state': 'FROZEN_TWO_EXISTING_MODEL_COMBINATIONS_NO_TRAINING',
                'source': source, 'selectionSha256': sha(CONTROL / 'selection.json'),
                'arms': [
                    {'id': 'qwen', 'asr': 'Qwen/Qwen3-ASR-1.7B-hf', 'weightsSha256': '2db53c7d81bd9b8cbc6a074e89be2c968a0d373fb4ee68bb1b1e14f7042dfee1', 'runtime': 'Existing native Transformers/HIP'},
                    {'id': 'paraformer', 'asr': 'Existing funasr-paraformer-large-zh-2024 int8 weights', 'weightsSha256': '8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54', 'runtime': 'Existing Python sherpa-onnx CPU; model-level comparator, not installed product benchmark'}],
                'shared': {'diarization': 'Existing FP16 native8 with original geometry/0.5 posterior threshold; no true speaker count input',
                           'alignment': 'Existing Qwen3-ForcedAligner-0.6B-hf unchanged',
                           'fusion': 'Fixed exclusive posterior view + original60ms onset rule, preserving raw multivoice journal',
                           'asrBoundaries': 'Same existing audio-only low-energy30s target spans for both arms; no VAD deletion',
                           'normalizationSha256': '45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'},
                'metrics': ['Complete raw chronologicalCER, with overlap-order limitations', 'Complete anonymous cpCER and unknown-forced-unmatched diagnostic',
                            'Raw multivoice DER, zero collar/overlap included', 'Short reference spans and silence insertions',
                            'Whole input sample coverage, source text preservation, observed time/private memory'],
                'rule': 'Compare complete frozen arms. No per-word/per-meeting best-output picking, new checkpoints, thresholds or training. Retain failures and component-level scores. Exclusive labels do not recover overlapped voices.',
                'cpuMaximumPercent': 5, 'privateModelLimitBytes': 2147483648, 'oneNeuralModelAtATime': True,
                'qualification': {'strictCerExclusiveMax': .05, 'derMax': .10, 'factsAndMultipleFullMeetingsAndRealCardRemainOpen': True},
                'newWeightUpdates': 0, 'realCardOrInstalledProductTested': False, 'qualityQualified': False,
                'license': 'Original AISHELL4 CC-BY-SA-4.0; retain source attribution, no mirror relicensing.'}
    write(CONTROL / 'protocol.json', protocol)
    write(CONTROL / 'source-provenance.json', {'source': source, 'reference': chosen,
                                             'officialData': 'https://www.openslr.org/111/', 'repositoryRevision': revision})
    state = {'state': 'FETCHING_FROZEN_NEW_ORDINARY_MEETING', 'startedAt': datetime.now().astimezone().isoformat(timespec='seconds'),
             'newModelInference': 0, 'newWeightUpdates': 0}
    write(CONTROL / 'preparation.json', state)
    try:
        import prepare_joint_neural_spatial_training_pairs_20261108 as transfer
        transfer.E = CACHE
        audio = transfer.fetch(source)
        assert audio.stat().st_size == source['fileSize'] and sha(audio) == source['expectedWholeFileLfsSha256']
        # The existing AMD environment supplies soundfile/numpy, while no
        # Torch model is imported. Export the complete first physical channel.
        import soundfile as sf
        import wave
        target = CACHE / 'ordinary-mic0.wav'
        with sf.SoundFile(str(audio)) as stream, wave.open(str(target), 'wb') as output:
            assert stream.samplerate == 16000 and stream.channels == 8 and stream.subtype == 'PCM_16'
            frames = stream.frames
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            while stream.tell() < frames:
                block = stream.read(min(16000*4, frames-stream.tell()), dtype='int16', always_2d=True)[:, 0].copy()
                output.writeframesraw(block.astype('<i2', copy=False).tobytes())
        with sf.SoundFile(str(audio)) as original, wave.open(str(target), 'rb') as exported:
            assert exported.getnframes() == frames
            for start in [0, frames//2, frames-4096]:
                original.seek(start)
                exported.setpos(start)
                expected = original.read(4096, dtype='int16', always_2d=True)[:, 0].copy().astype('<i2', copy=False).tobytes()
                assert exported.readframes(4096) == expected
        case = {'meeting': chosen['meeting'], 'audio': str(target), 'audioSha256': sha(target), 'audioSeconds': frames/16000}
        assert chosen['lastReferenceEnd'] <= case['audioSeconds']
        write(CONTROL / 'audio-only.json', [case])
        write(CONTROL / 'qwen-input.json', [{'id': 'ordinary-qwen', **{k: case[k] for k in ['audio', 'audioSha256', 'audioSeconds']}}])
        write(CONTROL / 'scoring-only.json', [{**case, 'corpus': 'AISHELL4-Train-development-only',
                                              'reference': chosen['reference'], 'referenceSha256': chosen['referenceSha256'],
                                              'referenceKind': 'textgrid_lexical'}])
        from practical_qwen_audio_boundaries_20261107 import quiet_wav_spans
        spans = quiet_wav_spans(target)
        write(CONTROL / 'audio-only-spans.json', spans)
        state.update(state='COMPLETE_FROZEN_FULL_MONO_MEETING_AND_MATCHED_ASR_SPANS', case=case,
                     totalSpans=len(spans), allOriginalSamplesCoveredOnce=True,
                     noOverlapAudioRemoved=True, sourceSamplesBitExactAtThreeLocations=True)
    except BaseException as error:
        state.update(state='SOURCE_PREPARATION_FAILED_RETAINED', error=repr(error))
        raise
    finally:
        state.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'), limits=limits.query())
        write(CONTROL / 'preparation.json', state)
    print(json.dumps(state, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
