"""Preserve475 frozen examples and add omitted natural nonoverlap training audio."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
import os
import shutil
import sys
import wave

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
S = R / 'model-research/src';sys.path.insert(0, str(S))
# Reuse the installed Rust tokenizer only; no Transformers or torch import.
sys.path.append('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
from tokenizers import Tokenizer
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
from english_nonoverlap_training_windows_20261117 import omitted_nonoverlap_windows, regression_examples
from score_sequential_meetings_20261115 import tokens
import psutil

D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
DATA = E / 'meeting-domain-data-r1'
OUT = DATA / 'english-word-nonoverlap-r3'
CONTROL = J / 'language-specific-adaptation-r1/expanded-data-r3'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert not OUT.exists() and not CONTROL.exists(), 'Retain any prior attempt rather than overwrite it.'
    assert shutil.disk_usage('E:/').free > 50*1024**3
    OUT.mkdir();CONTROL.mkdir()
    limits = WorkerLimits(cpu_percent=5, memory_bytes=256*1024**2)
    old_plan_file = J / 'language-specific-adaptation-r1/english-data-plan.json'
    old = read(old_plan_file)
    old_manifest = Path(old['trainingManifest']);old_bytes = old_manifest.read_bytes()
    assert sha(old_manifest) == old['trainingManifestSha256'] and old_bytes.endswith(b'\n')
    base = [json.loads(line) for line in old_bytes.decode().splitlines() if line]
    provenance_file = DATA / 'acoustic-nonoverlap-r2/example-provenance.json'
    assert sha(provenance_file) == old['sourceProvenanceSha256']
    base_provenance = {r['id']: r for r in read(provenance_file) if r['language'] == 'English'}
    assert len(base) == len(base_provenance) == 475
    assert old['englishGlobalParticipantsDisjointFromSeenValidationVerified']
    tokenizer_file = Path(old['modelRoot']) / 'tokenizer.json'
    assert sha(tokenizer_file) == old['tokenizerSha256']
    tokenizer = Tokenizer.from_file(str(tokenizer_file))
    assert all(tokenizer.encode(r['text'], add_special_tokens=False).ids == r['targetIds'] for r in base)
    assert all(math.ceil((r['frames']//160)/8) == r['encoderFramesUpperBound'] for r in base)
    plan = read(J / 'meeting-domain-data-r1/plan.json')
    assert not set(old['meetings']) & set(plan['existingDevelopmentSourcesExcluded'])
    tests = regression_examples()
    selections = []
    for meeting in sorted(old['meetings']):
        assert 'L_R003' not in meeting
        original_file = DATA / 'acoustic-nonoverlap' / meeting / 'original-reference-events.json'
        doc = read(original_file);assert doc['trainingOnly'] and not doc['modified']
        source = read(DATA / meeting / 'receipt.json')
        retained = [base_provenance[r['id']] for r in base if r['meeting'] == meeting]
        windows, stats = omitted_nonoverlap_windows(doc['events'], retained, source['frames'])
        selections.append({'meeting': meeting, 'source': source, 'windows': windows, 'stats': stats,
                           'originalReferenceSha256': sha(original_file)})
    expected_new = sum(len(r['windows']) for r in selections)
    assert expected_new == 1353
    protocol = {'state': 'FROZEN_TRAINING_ONLY_NONOVERLAP_SUPPLEMENT_EXISTING475_RETAINED_EXACTLY',
        'at': datetime.now().astimezone().isoformat(), 'sourceSha256': sha(__file__),
        'selectorSha256': sha(S / 'english_nonoverlap_training_windows_20261117.py'),
        'oldPlanSha256': sha(old_plan_file), 'oldManifestSha256': old['trainingManifestSha256'],
        'meetings': old['meetings'], 'preservedExamples': 475, 'supplementExamples': expected_new,
        'selection': 'Word-level overlap before grouping; old475clip PCM ranges are immutable barriers. Same2-30s speech span,3s maximum gap and100ms pad; no waveformVAD/denoise/gain/resample. Only omitted complete lexical annotations are eligible.',
        'sourceLabels': 'Existing10 English public training meetings with previously verified global participant separation. No validation/final labels are read by this exporter.',
        'targetProjection': 'Original training text retained; underscore-to-space only, canonical lexical sequence unchanged.',
        'regressionCases': tests, 'trainingStarted': False, 'newNeuralCalls': 0, 'parameterUpdates': 0}
    atomic_json(CONTROL / 'export-protocol.json', protocol)
    state = {'state': 'EXPORTING_TRAINING_ONLY_ENGLISH_SUPPLEMENT_NO_MODEL_COMPUTE',
        'at': protocol['at'], 'pid': os.getpid(), 'createdAt': psutil.Process().create_time(),
        'completed': [], 'expectedSupplementExamples': expected_new,
        'newNeuralCalls': 0, 'parameterUpdates': 0, 'qualityQualified': False}

    def save(**values):
        state.update(values, observedAt=datetime.now().astimezone().isoformat(), limits=limits.query())
        atomic_json(OUT / 'run.json', state, progress=True)

    all_provenance = [base_provenance[r['id']] for r in base]
    additions = []
    try:
        save()
        for item in selections:
            assert psutil.virtual_memory().available >= 3414499000 and shutil.disk_usage(OUT).free > 50*1024**3
            source = item['source'];meeting = item['meeting'];folder = OUT / meeting;folder.mkdir()
            assert sha(source['audio']) == source['audioSha256']
            with wave.open(source['audio'], 'rb') as original:
                assert (original.getnchannels(), original.getsampwidth(), original.getframerate(), original.getnframes()) == (1, 2, 16000, source['frames'])
                for index, window in enumerate(item['windows']):
                    assert psutil.virtual_memory().available >= 3414499000
                    identity = meeting + '-word-nonoverlap-r3-' + format(index, '04d')
                    target = folder / (format(index, '04d') + '.wav')
                    frames = window['endFrame']-window['startFrame'];original.setpos(window['startFrame'])
                    digest = hashlib.sha256()
                    with wave.open(str(target), 'wb') as output:
                        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'));remaining = frames
                        while remaining:
                            raw = original.readframes(min(32000, remaining));assert raw
                            remaining -= len(raw)//2;output.writeframesraw(raw);digest.update(raw)
                    raw_text = window['text'];text = raw_text.replace('_', ' ')
                    assert tokens(text, 'English') == tokens(raw_text, 'English')
                    ids = tokenizer.encode(text, add_special_tokens=False).ids;assert ids
                    encoder_frames = math.ceil((frames//160)/8)
                    row = {'id': identity, 'meeting': meeting, 'language': 'English', 'role': 'train-only',
                        'audio': str(target), 'audioSha256': sha(target), 'frames': frames, 'text': text,
                        'originalTrainingText': raw_text, 'targetIds': ids,
                        'encoderFramesUpperBound': encoder_frames, 'jointTokenCells': encoder_frames*(len(ids)+1)}
                    voices = [r['speaker'] for r in window['events']]
                    turns = [s for i, s in enumerate(voices) if i == 0 or s != voices[i-1]]
                    provenance = {'id': identity, 'meeting': meeting, 'language': 'English', 'corpus': 'AMI',
                        'role': 'train-only', 'audio': str(target), 'audioSha256': row['audioSha256'],
                        'pcmSha256': digest.hexdigest(), 'startFrame': window['startFrame'], 'endFrame': window['endFrame'],
                        'audioSeconds': frames/16000, 'text': raw_text, 'events': window['events'],
                        'localSpeakerIds': sorted(set(voices)), 'turns': turns,
                        'speakerReturn': len(turns) != len(set(turns)),
                        'sourceAudio': source['audio'], 'sourceAudioSha256': source['audioSha256'],
                        'referenceOverlapPresent': False, 'labelWordsEdited': False, 'addedNoise': False, 'resampled': False,
                        'supplementToFrozen475': True}
                    additions.append(row);all_provenance.append(provenance)
            summary = {'meeting': meeting, 'examples': len(item['windows']),
                'audioSeconds': sum(w['endFrame']-w['startFrame'] for w in item['windows'])/16000,
                'lexicalWords': sum(len(tokens(w['text'], 'English')) for w in item['windows']),
                'selectionStats': item['stats'], 'originalReferenceSha256': item['originalReferenceSha256']}
            state['completed'].append(summary);save(supplementExamplesExported=len(additions))
            print(json.dumps(summary), flush=True)
        assert len(additions) == expected_new
        manifest = OUT / 'english-tdt-train.jsonl'
        with manifest.open('xb') as stream:
            stream.write(old_bytes)
            for row in additions:
                stream.write((json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8'))
            stream.flush();os.fsync(stream.fileno())
        with manifest.open('rb') as stream:
            assert hashlib.sha256(stream.read(len(old_bytes))).hexdigest() == old['trainingManifestSha256']
        assert sha(old_manifest) == old['trainingManifestSha256']
        provenance = OUT / 'example-provenance.json';atomic_json(provenance, all_provenance)
        all_rows = base + additions;assert len({r['id'] for r in all_rows}) == len(all_rows) == 1828
        expanded = dict(old)
        expanded.update(state='EXPANDED_ENGLISH_TRAINING_DATA_EXPORTED_INDEPENDENT_INTEGRITY_PENDING',
            at=datetime.now().astimezone().isoformat(), priorDataPlan=str(old_plan_file),
            priorDataPlanSha256=sha(old_plan_file), trainingManifest=str(manifest), trainingManifestSha256=sha(manifest),
            sourceProvenance=str(provenance), sourceProvenanceSha256=sha(provenance),
            sourceManifestSha256=sha(manifest), examples=len(all_rows),
            preservedExamples=475, supplementExamples=len(additions),
            original475ManifestBytePrefixPreserved=True,
            audioSeconds=sum(r['frames'] for r in all_rows)/16000,
            targetTokens=sum(len(r['targetIds']) for r in all_rows),
            maximumTargetTokens=max(len(r['targetIds']) for r in all_rows),
            largestJointCase={k:max(all_rows, key=lambda r:r['jointTokenCells'])[k] for k in ['id','frames','encoderFramesUpperBound','jointTokenCells']},
            longestCase={k:max(all_rows, key=lambda r:r['frames'])[k] for k in ['id','frames','encoderFramesUpperBound','jointTokenCells']},
            trainingLexicalWords=sum(len(tokens(r['text'], 'English')) for r in all_rows),
            independentIntegrityPassed=False, gpuPreflightPassed=False, trainingStarted=False,
            plannedOneEpoch={**old['plannedOneEpoch'], 'examples': len(all_rows),
                             'optimizerUpdates': math.ceil(len(all_rows)/4)},
            next='Independent sourcePCM/complete-word/nonoverlap/no-duplicate/old475prefix/participant checks, then bind the expanded fixed one-epoch training recipe. No training by this exporter.')
        config = read(Path(old['modelRoot']) / 'config.json')
        expanded['largestDenseJointF32Bytes'] = expanded['largestJointCase']['jointTokenCells']*(config['vocab_size']+len(config['durations']))*4
        atomic_json(CONTROL / 'english-data-plan.json', expanded)
        assert 'torch' not in sys.modules and 'transformers' not in sys.modules
        save(state='COMPLETE_EXPANDED_ENGLISH_TRAINING_EXPORT_NO_MODEL_EXECUTION', examples=len(all_rows),
             supplementExamples=len(additions), trainingManifestSha256=sha(manifest),
             dataPlan=str(CONTROL / 'english-data-plan.json'), torchImported=False,
             original475ManifestUnchanged=True, originalValidationOrFinalInputsRead=False)
        atomic_json(OUT / 'completed.json', state)
        print(json.dumps({'state': state['state'], 'examples': len(all_rows),
            'audioHours': expanded['audioSeconds']/3600, 'trainingLexicalWords': expanded['trainingLexicalWords'],
            'maxTokens': expanded['maximumTargetTokens'], 'plannedUpdates': expanded['plannedOneEpoch']['optimizerUpdates']}))
    except BaseException as error:
        import traceback
        save(state='FAILED_EXPANDED_ENGLISH_EXPORT_RETAINED_NO_MODEL_TRAINING', error=repr(error), traceback=traceback.format_exc())
        atomic_json(OUT / 'completed.json', state)
        raise


if __name__ == '__main__':
    main()
