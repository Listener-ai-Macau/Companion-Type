"""Independent PCM, annotation, source-frame and participant audit of expanded English data."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
import sys
import wave
import zipfile
import xml.etree.ElementTree as ET

R = Path('C:/Users/Billy/Desktop/Denzic/Companion');S = R / 'model-research/src'
sys.path.insert(0, str(S))
sys.path.append('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
from tokenizers import Tokenizer
from moss_windows_resource_limits_20261104 import WorkerLimits
from score_sequential_meetings_20261115 import tokens
from ami_reference_coverage_20261115 import official_speakers
from durable_model_state_20261117 import atomic_json

D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1';E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
DATA = E / 'meeting-domain-data-r1';OUT = DATA / 'english-word-nonoverlap-r3'
CONTROL = J / 'language-specific-adaptation-r1/expanded-data-r3'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
    assert not (CONTROL / 'integrity.json').exists()
    plan_file = CONTROL / 'english-data-plan.json';plan = read(plan_file)
    original = read(plan['priorDataPlan'])
    assert sha(plan['priorDataPlan']) == plan['priorDataPlanSha256']
    assert sha(plan['trainingManifest']) == plan['trainingManifestSha256']
    assert sha(plan['sourceProvenance']) == plan['sourceProvenanceSha256']
    rows = [json.loads(l) for l in Path(plan['trainingManifest']).read_text().splitlines() if l]
    provenance = {r['id']: r for r in read(plan['sourceProvenance'])}
    assert len(rows) == len(provenance) == 1828 and {r['meeting'] for r in rows} == set(original['meetings'])
    prefix = Path(original['trainingManifest']).read_bytes()
    with Path(plan['trainingManifest']).open('rb') as stream:
        assert stream.read(len(prefix)) == prefix
    assert hashlib.sha256(prefix).hexdigest() == original['trainingManifestSha256']
    assert rows[:475] == [json.loads(l) for l in prefix.decode().splitlines() if l]
    tokenizer = Tokenizer.from_file(str(Path(plan['modelRoot']) / 'tokenizer.json'))
    source_plan = read(J / 'meeting-domain-data-r1/plan.json')
    sources = {r['meeting']: r for r in source_plan['sources'] if r['language'] == 'English'}
    archive_path = Path(sources[original['meetings'][0]]['annotationArchive'])
    assert sha(archive_path) == sources[original['meetings'][0]]['annotationArchiveSha256']
    meetings, train_people = [], set()
    with zipfile.ZipFile(archive_path) as archive:
        metadata_bytes = archive.read('corpusResources/meetings.xml')
        metadata = {r.attrib['observation']: r for r in ET.fromstring(metadata_bytes).findall('meeting')}
        seen_ids = [name for name in source_plan['existingDevelopmentSourcesExcluded'] if name in metadata]
        seen_people = {s.attrib['global_name'] for name in seen_ids for s in metadata[name].findall('speaker')}
        assert {'ES2003b', 'EN2001a', 'EN2002a'} <= set(seen_ids)
        for meeting in sorted(original['meetings']):
            assert meeting not in seen_ids and 'L_R003' not in meeting
            people = {s.attrib['global_name'] for s in metadata[meeting].findall('speaker')}
            assert not people & seen_people;train_people.update(people)
            # Read only word annotation members for the selected training meeting.
            official = []
            for speaker in official_speakers(archive, meeting):
                member = 'words/' + meeting + '.' + speaker + '.words.xml'
                for index, node in enumerate(ET.fromstring(archive.read(member)).iter('w')):
                    official.append({'start': float(node.attrib['starttime']), 'end': float(node.attrib['endtime']),
                        'speaker': speaker, 'text': ''.join(node.itertext()), 'index': index, 'annotationFile': member})
            official.sort(key=lambda r: (r['start'], r['end'], r['speaker']))
            cached = read(DATA / 'acoustic-nonoverlap' / meeting / 'original-reference-events.json')['events']
            assert official == cached, 'Cached training words differ from officialXML'
            source = read(DATA / meeting / 'receipt.json')
            assert sha(source['audio']) == source['audioSha256']
            candidates = sorted([r for r in rows if r['meeting'] == meeting],
                                key=lambda r: provenance[r['id']]['startFrame'])
            used_words = set();previous_end = 0;word_count = 0
            lexical = {i: r for i, r in enumerate(official)
                if tokens(r['text'], 'English') and not ('<' in r['text'] and '>' in r['text'])
                and 0 <= r['start'] < r['end'] <= source['audioSeconds']}
            unclear = [r for r in official if tokens(r['text'], 'English') and
                       (('<' in r['text'] and '>' in r['text']) or r['start'] == r['end']
                        or r['end'] > source['audioSeconds'])]
            with wave.open(source['audio'], 'rb') as original_audio:
                for row in candidates:
                    p = provenance[row['id']]
                    assert row['role'] == p['role'] == 'train-only' and row['language'] == 'English'
                    assert p['startFrame'] >= previous_end and p['endFrame']-p['startFrame'] == row['frames']
                    previous_end = p['endFrame']
                    assert p['sourceAudioSha256'] == source['audioSha256']
                    selected = [i for event in p['events'] for i in event['sourceIndices']]
                    assert len(selected) == len(set(selected)) and not used_words & set(selected)
                    used_words.update(selected)
                    for event in p['events']:
                        group = [official[i] for i in event['sourceIndices']]
                        assert all(r['speaker'] == event['speaker'] for r in group)
                        assert ' '.join(r['text'] for r in group) == event['text']
                        assert min(r['start'] for r in group) == event['start'] and max(r['end'] for r in group) == event['end']
                    a, b = p['startFrame']/16000, p['endFrame']/16000
                    inside = {i for i, r in lexical.items() if r['start'] < b-1e-9 and r['end'] > a+1e-9}
                    assert inside == set(selected), 'Unlabelled or missing lexical event in trainingPCM'
                    assert not any(r['start'] < b-1e-9 and r['end'] > a+1e-9 for r in unclear)
                    active = []
                    for i in sorted(selected):
                        event = official[i];active = [r for r in active if r['end'] > event['start']+1e-9]
                        assert all(r['speaker'] == event['speaker'] for r in active), 'True cross-speaker overlap inStageA'
                        active.append(event)
                    raw_text = ' '.join(official[i]['text'] for i in selected)
                    assert tokens(raw_text, 'English') == tokens(row['text'], 'English')
                    assert row['originalTrainingText'] == p['text']
                    assert row['text'] == row['originalTrainingText'].replace('_', ' ')
                    assert tokenizer.encode(row['text'], add_special_tokens=False).ids == row['targetIds']
                    assert math.ceil((row['frames']//160)/8) == row['encoderFramesUpperBound']
                    assert sha(row['audio']) == row['audioSha256'] == p['audioSha256']
                    original_audio.setpos(p['startFrame']);digest = hashlib.sha256()
                    with wave.open(row['audio'], 'rb') as exported:
                        assert (exported.getnchannels(), exported.getsampwidth(), exported.getframerate(), exported.getnframes()) == (1, 2, 16000, row['frames'])
                        remaining = row['frames']
                        while remaining:
                            take = min(32000, remaining);expected = original_audio.readframes(take)
                            actual = exported.readframes(take);assert actual == expected and len(actual) == take*2
                            digest.update(actual);remaining -= take
                    assert digest.hexdigest() == p['pcmSha256']
                    word_count += len(tokens(row['text'], 'English'))
            meetings.append({'meeting': meeting, 'examples': len(candidates), 'uniqueOriginalWordEvents': len(used_words),
                             'lexicalWords': word_count, 'participants': sorted(people),
                             'allOriginalPcmSlicesAndLabelsExact': True, 'repeatedAudioFrames': 0})
    assert sum(r['lexicalWords'] for r in meetings) == 41952
    receipt = {'state': 'PASS_EXPANDED_ENGLISH_DATA_PCM_WORDS_TOKENS_NONOVERLAP_AND_PARTICIPANT_INTEGRITY',
        'at': datetime.now().astimezone().isoformat(), 'examples': len(rows), 'preservedExamples': 475,
        'supplementExamples': 1353, 'audioSeconds': sum(r['frames'] for r in rows)/16000,
        'lexicalWords': 41952, 'trainingGlobalParticipants': sorted(train_people),
        'seenDevelopmentGlobalParticipants': sorted(seen_people), 'globalParticipantIntersection': [],
        'seenDevelopmentMeetings': sorted(seen_ids), 'meetings': meetings,
        'metadataSha256': hashlib.sha256(metadata_bytes).hexdigest(), 'dataPlanInputSha256': sha(plan_file),
        'manifestSha256': sha(plan['trainingManifest']), 'provenanceSha256': sha(plan['sourceProvenance']),
        'verifierSha256': sha(__file__), 'all475OriginalRowsAndBytePrefixPreserved': True,
        'all1828PcmSourceFrameSlicesCheckedByteForByte': True,
        'allSelectedWordMetadataMatchedOfficialTrainingXml': True,
        'unlabelledLexicalEventsInSelectedAudio': 0, 'repeatedPcmFramesOrWordSupervision': 0,
        'trueCrossSpeakerOverlapFound': False, 'tokenizerTargetsAllExact': True,
        'validationWordLabelsRead': False, 'finalHoldoutOpened': False,
        'newNeuralCalls': 0, 'parameterUpdates': 0, 'torchImported': 'torch' in sys.modules,
        'qualityQualified': False, 'saleQualified': False, 'limits': limits.query()}
    assert not receipt['torchImported']
    (OUT / 'plan-before-independent-integrity.json').write_bytes(plan_file.read_bytes())
    atomic_json(CONTROL / 'integrity.json', receipt)
    plan.update(state='EXPANDED_ENGLISH_DATA_INDEPENDENT_INTEGRITY_PASSED_GPU_EXECUTION_UNPROVEN',
                independentIntegrityPassed=True, integrityReceipt=str(CONTROL / 'integrity.json'),
                integrityReceiptSha256=sha(CONTROL / 'integrity.json'),
                next='Bind this verified1828-example dataset into the fixed one-epoch adaptation recipe, retaining original12clip/whole-meeting/person/facts/final gates. No CPU/iGPUtraining.')
    atomic_json(plan_file, plan)
    print(json.dumps({k: receipt[k] for k in ['state','examples','lexicalWords','audioSeconds',
        'all1828PcmSourceFrameSlicesCheckedByteForByte','globalParticipantIntersection','newNeuralCalls']}))


if __name__ == '__main__':
    main()
