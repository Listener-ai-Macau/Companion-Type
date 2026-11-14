from pathlib import Path
import hashlib
import json
import shutil
import wave

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
C = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/ordinary-asr-adaptation-r1'
K = Path('E:/CodexData/Companion/.model-cache/ordinary-asr-adaptation-20261114')
OLD = Path('E:/CodexData/Companion/.model-cache/local-bilingual-20261114')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
assert not (C / 'capability-controls-audio-only.json').exists()
source = OLD / 'public-probe90.wav'
assert sha(source) == 'dea1f9d47d753e6b626614a87ef163e48f21657d51303f4cffc182845dbd79a8'
english = K / 'audio/control/english-first30.wav'
english.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(source), 'rb') as audio:
    assert (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) == (1, 16000, 2)
    audio.setpos(480000)
    pcm = audio.readframes(480000)
with wave.open(str(english), 'wb') as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(16000)
    audio.writeframes(pcm)
mixed = OLD / 'natural-ascend-first-mixed/00009.wav'
assert sha(mixed) == '7317a4752e95039e6f6c345ef5b15fdd18fc7f48353cc893e6f99218a682c9a3'
controls = [{'id': 'existing-English-first30', 'audio': str(english), 'audioSha256': sha(english),
             'audioSeconds': 30., 'language': 'auto'},
            {'id': 'existing-natural-mixed-00009', 'audio': str(mixed), 'audioSha256': sha(mixed),
             'audioSeconds': 4.03, 'language': 'auto'}]
(C / 'capability-controls-audio-only.json').write_text(json.dumps(controls, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
natural_reference = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/natural-ascend-first-mixed/scoring-only.json'
shutil.copy2(natural_reference, C / 'mixed-control-scoring-only.json')
(C / 'capability-control-rule.json').write_text(json.dumps({
    'state': 'FROZEN_BEFORE_ANY_ADAPTER_INFERENCE_OR_UPDATES',
    'englishRule': 'Candidate must preserve the baseline English output under the existing strict case/punctuation/whitespace normalization; do not claim whole-English-meeting qualification.',
    'naturalMixedRule': 'Candidate strict CER must not exceed this same4.03s natural reference baseline, no reference supplied to inference.',
    'newOrdinaryEvalTraining': False, 'parameterSweepAllowed': False,
    'naturalReferenceSha256': sha(natural_reference)}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'state': 'FROZEN_EXISTING_CAPABILITY_CONTROLS', 'controls': len(controls)}))
