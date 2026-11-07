"""Freeze post-inference identity policy without reading new predicted timestamps."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
B=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery');C=B/'practical-alignment-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
target=C/'attribution-policy.json';assert not target.exists()
journals={}
for case in read(C/'audio-text-only.json'):
    file=B/'native8-f16-full-r1/results'/case['meeting']/'speaker-journal.json';journal=read(file)
    producer=read(file.parent/'completed-state.json')
    assert producer.get('finishedAt') and producer['allOriginalAudioSamplesSubmitted'] and producer['oneContinuousSpeakerState']
    assert journal['audioSha256']==case['audioSha256'] and journal['audioSeconds']==case['audioSeconds']
    journals[case['meeting']]={'file':str(file),'sha256':sha(file),'producerFile':str(file.parent/'completed-state.json'),'producerSha256':sha(file.parent/'completed-state.json')}
atomic_json(target,{'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'FROZEN_POSTHOC_ATTRIBUTION_NO_NEW_ALIGNMENT_OUTPUTS_READ',
    'speakerJournals':journals,'helperSourceSha256':sha(Path(__file__).with_name('practical_transcript_20261107.py')),
    'uncertaintyMarginSeconds':.06,
    'rule':'For each positive in-bound predicted word interval, require exactly one anonymous predicted speaker with continuous coverage throughout the entire interval plus the inherited60ms margin. Overlap, gaps, speaker changes and invalid/zero-duration intervals stay unknown. No majority/primary-person guess, no person-count hint, no per-meeting threshold selection.',
    'fallbackDisplayTime':'Invalid predicted times retain original word and unknown person; display range is explicitly approximate and bounded inside its source leaf, not verified word duration.',
    'rawTextMustRemainIdentical':True,'standardCpCerAndForcedUnmatchedDiagnosticReportedSeparately':True,
    'trueWordTimeGroundTruthAvailable':False,'noSpeakerLabelsOrReferencePassedToAligner':True,'qualityQualified':False})
print(json.dumps({'state':read(target)['state']}))
