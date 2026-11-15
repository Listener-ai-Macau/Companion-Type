"""Bind four headsets and one raw-mic control to the unchanged existing ASR pack."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import subprocess
import sys
import time
import wave
from moss_windows_resource_limits_20261104 import WorkerLimits
from paired_meeting_pcm16_20261109 import info, read
limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024**2)
R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
C = R / 'docs/handoffs/20261109-paired-real-meeting'
D = Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109')
M = R / 'model-research'
ASR = M / 'src/companion_native_asr_20261107.py'
PACK = R / 'docs/handoffs/20261107-model-generation-recovery/practical-qwen-author-boundaries-r6/model-pack.json'
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
started = time.perf_counter()

def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

audit = json.loads((C / 'pair-audit-result.json').read_bytes())
pack = json.loads(PACK.read_bytes())
source = Path(pack['sourceControl'])
for rel, expected in pack['pinnedFiles'].items():
    assert digest(source / rel) == expected, ('Pack binding changed', rel)
assert digest(M / 'src' / pack['workerModule']) == pack['workerSourceSha256']
assert digest(M / 'src/practical_qwen_bounded_decode_20261107.py') == pack['recoverySourceSha256']
protocol = json.loads((source / 'native-protocol.json').read_bytes())
assert protocol['modelId'] == 'Qwen/Qwen3-ASR-1.7B-hf' and protocol['prompt'] is None
assert protocol['language'] == 'Chinese' and protocol['maxNewTokens'] == 512 and not protocol['doSample']
assert protocol['dtype'] == 'bfloat16'

frames = min(p['wave']['frames'] for p in audit['pairedPeople'])
assert all(p['wave']['frames'] == frames for p in audit['pairedPeople'])
assert max(r['end'] for r in __import__('reference_textgrid_20261104').read_reference_intervals(audit['farReference'])) < frames/16000
audio_dir = D / 'fixed-asr-inputs'
audio_dir.mkdir(exist_ok=True)
far_pcm = audio_dir / 'R8001_M8004_mic0_common_1551p82s.wav'
far_meta = audit['farWave']
with wave.open(str(far_pcm), 'wb') as writer:
    writer.setnchannels(1)
    writer.setsampwidth(2)
    writer.setframerate(16000)
    for lo in range(0, frames, 16000*4):
        hi = min(frames, lo+16000*4)
        writer.writeframesraw(read(audit['farAudio'], lo, hi, 0, far_meta).tobytes())
pcm_meta = info(far_pcm)
assert pcm_meta['frames'] == frames
for lo in [0, frames//2, frames-4096]:
    assert (read(far_pcm, lo, lo+4096) == read(audit['farAudio'], lo, lo+4096, 0, far_meta)).all()
cases = [{'id': 'near-'+p['speaker'], 'audio': p['audio'], 'audioSha256': p['audioSha256'],
          'audioSeconds': frames/16000, 'kind': 'individual-headset-entire-recording'} for p in audit['pairedPeople']]
cases.append({'id': 'far-mic0-common-span', 'audio': str(far_pcm), 'audioSha256': digest(far_pcm),
              'audioSeconds': frames/16000, 'kind': 'unseparated-mixed-control',
              'originalFarSeconds': far_meta['seconds'], 'omittedFarTailSeconds': far_meta['seconds'] - frames/16000,
              'scope': 'Matched common span only. This is not the whole original far recording or a sale full-meeting test.'})
for case in cases:
    assert digest(case['audio']) == case['audioSha256']
    assert not any('reference' in key.lower() for key in case)
    case['command'] = [sys.executable, str(ASR), '--audio', case['audio'], '--model-pack', str(PACK),
                       '--work-dir', str(D / 'fixed-asr-runs' / case['id'])]
    case['resumeRule'] = 'Only add --resume for an existing bound task. Never change input, pack, prompt, reference or decoder.'
    case['commandPrerequisite'] = 'Fresh native HIP ordinal verification and private runtime pack binding required. The existing adapter uses the source inventory ordinal; do not assume a historical ordinal remains correct after reconnecting the GPU.'
scoring = {'parser': audit['parser'], 'sourceReferences': [
    {'id': 'near-'+p['speaker'], 'reference': p['reference'], 'referenceSha256': p['referenceSha256'],
     'farTier': p['speaker'], 'scope': 'All source utterances wholly covered; count bleed insertions, but audit unannotated sound rather than declaring every non-reference sound invented.'} for p in audit['pairedPeople']],
    'rawMixedRule': 'Do not score raw mixed control against one speaker. Chronological all-speaker CER has overlap-order limitations and is a separate diagnostic; do not compare it directly with per-person aggregate CER/cpCER.',
    'nextSeparationComparison': 'Only after headset transcription ceiling is measured, compare the same person/time/reference on existing separated far audio; source alignment limitations currently prevent clean-target training/SDR claims.',
    'notSaleEvaluation': True, 'split': 'Eval', 'trainingAllowed': False}
(C / 'fixed-asr-audio-only.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
(C / 'fixed-asr-scoring-only.json').write_text(json.dumps(scoring, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
display = subprocess.run(['pnputil', '/enum-devices', '/class', 'Display', '/connected'], capture_output=True, text=True)
assert display.returncode == 0
connected = '6800 XT' in display.stdout
result = {'at': now(), 'state': 'FIXED_ASR_INPUTS_BOUND_PENDING_FRESH_GPU_RUNTIME_BINDING' if connected else 'FIXED_ASR_INPUTS_BOUND_DEFERRED_EXTERNAL_GPU_ABSENT',
          'audioOnlySha256': digest(C / 'fixed-asr-audio-only.json'),
          'scoringOnlySha256': digest(C / 'fixed-asr-scoring-only.json'),
          'modelPack': str(PACK), 'modelPackSha256': digest(PACK), 'modelId': protocol['modelId'],
          'modelRevision': protocol['revision'], 'caseCount': len(cases),
          'speakerHeadsetCount': 4, 'commonSecondsPerInput': frames/16000,
          'runtimeHardwareRule': 'Freshly identify external RX6800XT in HIP before inference; no old ordinal assumption or integrated fallback.',
          'displayQuery': display.stdout, 'newModelCalls': 0, 'newTrainingRuns': 0,
          'wallSeconds': time.perf_counter()-started, 'limits': limits.query(),
          'sourcePcmUnchanged': True, 'farMic0BoundedSamplesBitExact': True, 'saleQualified': False}
(C / 'fixed-asr-preparation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
print(json.dumps(result), flush=True)
