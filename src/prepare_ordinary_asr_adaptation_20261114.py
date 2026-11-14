"""Freeze complete natural non-overlap Train utterances for one ASR pilot.

Training and validation use separate existing source meetings. Evaluation
recordings and the final holdout never enter the training set. Padding cannot
include another annotated utterance, including one by the same speaker.
"""
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import hashlib
import json
import math
import random
import re
import sys
import wave

# Reuse the existing parser installation while the existing AMD environment
# supplies its own soundfile/numpy. No packages in either runtime are changed.
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/ordinary-asr-adaptation-r1'
CACHE = Path('E:/CodexData/Companion/.model-cache/ordinary-asr-adaptation-20261114')
SOURCES = ROOT / 'docs/handoffs/20261108-tse-source-supervision/sources.json'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def category(text):
    if '儿' in text:
        return 'erhua'
    if re.search('[嗯呃啊哎唉]', text):
        return 'filler'
    if re.search(r'\d|零|百|千|万|元|块|百分|价格|售价|成本', text):
        return 'number_or_unit'
    return 'other'


def balanced_pick(candidates, total, rng):
    buckets = defaultdict(list)
    for row in candidates:
        buckets[row['category']].append(row)
    for rows in buckets.values():
        rng.shuffle(rows)
        by_person = defaultdict(list)
        for row in rows:
            by_person[row['speaker']].append(row)
        rows.clear()
        while any(by_person.values()):
            for person in sorted(by_person):
                if by_person[person]:
                    rows.append(by_person[person].pop())
    selected = []
    while len(selected) < total:
        changed = False
        for name in ['erhua', 'filler', 'number_or_unit', 'other']:
            if buckets[name] and len(selected) < total:
                selected.append(buckets[name].pop(0))
                changed = True
        if not changed:
            raise ValueError(f'Not enough complete non-overlap utterances: {len(selected)}/{total}')
    rng.shuffle(selected)
    return selected


def main():
    limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
    import numpy as np
    import soundfile as sf
    assert not CONTROL.exists() and not CACHE.exists(), 'Keep frozen source selections and attempts'
    sources = read(SOURCES)
    assert len(sources) == 4
    assert len({s['meeting'] for s in sources}) == 4
    assert {s['role'] for s in sources} == {'train', 'validation'}
    assert all(s['sourcePath'].startswith(('train_L/', 'train_S/')) for s in sources)
    assert not any(x in s['meeting'] for s in sources for x in ['L_R003S03C02', 'S_R004S03C01', 'L_R003S01C02'])
    CONTROL.mkdir(parents=True)
    CACHE.mkdir(parents=True)
    state = {'at': datetime.now().astimezone().isoformat(timespec='seconds'),
             'state': 'VERIFYING_EXISTING_REAL_TRAIN_SOURCES', 'sources': [], 'newNeuralCalls': 0}
    write(CONTROL / 'preparation.json', state)
    training, validation, scoring = [], [], []
    try:
        for source in sources:
            assert sha(source['localFlac']) == source['expectedWholeFileLfsSha256']
            assert sha(source['reference']) == source['referenceSha256']
            rows = [r for r in read_reference_intervals(source['reference']) if r['text'].strip()]
            candidates = []
            info = sf.info(source['localFlac'])
            assert info.samplerate == 16000 and info.channels == 8 and info.subtype == 'PCM_16'
            for index, row in enumerate(rows):
                text = row['text'].strip()
                lexical = ''.join(c for c in text if c.isalnum())
                duration = row['end']-row['start']
                if not (2 <= duration <= 12 and 4 <= len(lexical) <= 96) or '<' in text or '>' in text:
                    continue
                if any(i != index and min(row['end'], other['end']) > max(row['start'], other['start'])
                       for i, other in enumerate(rows)):
                    continue
                previous = max((r['end'] for i, r in enumerate(rows) if i != index and r['end'] <= row['start']), default=0.)
                following = min((r['start'] for i, r in enumerate(rows) if i != index and r['start'] >= row['end']), default=info.frames/16000)
                start = max(0, math.floor(max(row['start']-.12, previous)*16000))
                end = min(info.frames, math.ceil(min(row['end']+.12, following)*16000))
                assert start <= row['start']*16000 and end >= row['end']*16000
                candidates.append({'sourceRowIndex': index, 'speaker': row['speaker'], 'text': text,
                                   'referenceStartSeconds': row['start'], 'referenceEndSeconds': row['end'],
                                   'startSample': start, 'endSample': end, 'category': category(text)})
            seed = int(hashlib.sha256((source['meeting']+'20261114').encode()).hexdigest()[:8], 16)
            count = 64 if source['role'] == 'train' else 16
            selected = balanced_pick(candidates, count, random.Random(seed))
            per_source = []
            with sf.SoundFile(source['localFlac']) as audio:
                for index, row in enumerate(selected):
                    audio.seek(row['startSample'])
                    pcm = audio.read(row['endSample']-row['startSample'], dtype='int16', always_2d=True)[:, 0].copy()
                    assert len(pcm) == row['endSample']-row['startSample']
                    ident = source['meeting']+f'-{index:03d}'
                    dest = CACHE / 'audio' / source['role'] / (ident+'.wav')
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with wave.open(str(dest), 'wb') as output:
                        output.setnchannels(1)
                        output.setsampwidth(2)
                        output.setframerate(16000)
                        output.writeframes(pcm.astype('<i2', copy=False).tobytes())
                    with wave.open(str(dest), 'rb') as check:
                        assert check.readframes(len(pcm)) == pcm.astype('<i2', copy=False).tobytes()
                    packet = {'id': ident, 'meeting': source['meeting'], 'audio': str(dest), 'audioSha256': sha(dest),
                              'audioSeconds': len(pcm)/16000, 'sourceWholeSha256': source['expectedWholeFileLfsSha256'],
                              'sourceReferenceSha256': source['referenceSha256'], **row}
                    per_source.append(packet)
                    if source['role'] == 'train':
                        training.append(packet)
                    else:
                        validation.append({k: packet[k] for k in ['id', 'meeting', 'audio', 'audioSha256', 'audioSeconds']})
                        scoring.append(packet)
            state['sources'].append({'meeting': source['meeting'], 'role': source['role'],
                                     'sourceWholeSha256': source['expectedWholeFileLfsSha256'],
                                     'referenceSha256': source['referenceSha256'], 'sourcePath': source['sourcePath'],
                                     'eligibleCompleteUtterances': len(candidates), 'selectedUtterances': len(selected),
                                     'categoryCounts': dict(Counter(r['category'] for r in selected)),
                                     'selectedSpeakerCountsForConstructionOnly': dict(Counter(r['speaker'] for r in selected)),
                                     'selectedSeconds': sum(r['audioSeconds'] for r in per_source)})
            write(CONTROL / 'preparation.json', state)
        assert len(training) == 128 and len(validation) == len(scoring) == 32
        assert not {r['meeting'] for r in training} & {r['meeting'] for r in validation}
        write(CONTROL / 'train.json', training)
        write(CONTROL / 'validation-audio-only.json', validation)
        write(CONTROL / 'validation-scoring-only.json', scoring)
        write(CONTROL / 'source-provenance.json', sources)
        protocol = {'at': state['at'], 'state': 'FROZEN_ONE_BOUNDED_ASR_ADAPTER_PILOT_BEFORE_BASELINE_OR_TRAINING',
                    'baseModel': 'Qwen/Qwen3-ASR-1.7B-hf', 'baseRevision': 'bcd2b5b7f32b480ab5790554cfa8347f246a14f3',
                    'baseWeightsSha256': '2db53c7d81bd9b8cbc6a074e89be2c968a0d373fb4ee68bb1b1e14f7042dfee1',
                    'trainManifestSha256': sha(CONTROL / 'train.json'),
                    'validationAudioManifestSha256': sha(CONTROL / 'validation-audio-only.json'),
                    'validationScoringManifestSha256': sha(CONTROL / 'validation-scoring-only.json'),
                    'trainUtterances': 128, 'validationUtterances': 32, 'sources': state['sources'],
                    'training': {'method': 'PEFT LoRA, frozen backbone and frozen audio encoder', 'rank': 8, 'alpha': 16,
                                 'targetModules': 'Only language-model self-attention q_proj/v_proj', 'dropout': 0.,
                                 'learningRate': 2e-5, 'epochs': 1, 'batchSize': 1, 'gradientAccumulation': 4,
                                 'optimizer': 'AdamW betas(0.9,0.999), weight_decay0', 'gradientClip': 1.,
                                 'seed': 20261114, 'savedCheckpoints': 'Final adapter only; no validation-based epoch or lr selection'},
                    'inference': {'language': 'Chinese', 'maxNewTokens': 512, 'doSample': False, 'sameBaseMathAndLoader': True},
                    'keepRule': 'Candidate must reduce strict total CER on independent32 validation utterances without regressing either validation meeting; English/ordinary existing controls must retain capability. Otherwise reject this one trial, preserve failure, no tuning sweep.',
                    'beforeUpdates': 'Verify exact no-op initial adapter inference, masked training labels, finite nonzero adapter gradients and all frozen parameter bytes unchanged.',
                    'rawTextPreserved': True, 'fillerErhuaAndNumbersRetainedInLabelsAndScoring': True,
                    'trainingSelectionUsesOnlyTrainTranscripts': True, 'validationReferencesPassedToInference': False,
                    'evalOrFinalHoldoutUsedForTraining': False, 'fullQualificationHoldoutOpened': False,
                    'selection': 'Complete annotated nonoverlap utterances2-12s, channel0. Up to120ms original padding bounded by every neighboring annotation. Deterministic category/speaker balancing before inference.',
                    'limitations': ['Small adaptation pilot, not large-scale training or sale qualification.',
                                    'All four are original training-split sessions; two held out for this adaptation only.',
                                    'Physical speaker and room independence is not fully established. Some source material was previously used for TSE diagnostics.',
                                    'No noisy/overlapping source is represented as clean-source ground truth.'],
                    'license': 'Original AISHELL4 CC-BY-SA-4.0; retain attribution. No mirror relicensing claim.',
                    'officialDataSource': 'https://www.openslr.org/111/',
                    'officialSftReference': 'https://github.com/QwenLM/Qwen3-ASR/blob/main/finetuning/qwen3_asr_sft.py',
                    'cpuPercentMaximum': 5, 'privateCommitLimitBytes': 2147483648,
                    'actualWindowsLowRamStop': True, 'automaticRetries': 0, 'qualityQualified': False}
        write(CONTROL / 'protocol.json', protocol)
        state.update(state='COMPLETE_FROZEN_FULL_UTTERANCE_ASR_PILOT_DATA', finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),
                     trainUtterances=128, validationUtterances=32, limits=limits.query(), newAudioDownloaded=False)
    except BaseException as error:
        state.update(state='DATA_PREPARATION_FAILED_RETAINED', error=repr(error))
        raise
    finally:
        write(CONTROL / 'preparation.json', state)
    print(json.dumps(state, ensure_ascii=False))


if __name__ == '__main__':
    main()
