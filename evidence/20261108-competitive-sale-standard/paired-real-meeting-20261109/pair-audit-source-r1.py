"""Measure real paired source identity, acoustic delays and bleed; no model."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import time
os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits = WorkerLimits(cpu_percent=5, memory_bytes=768 * 1024**2)
import numpy as np
from scipy import signal
from scipy.io import wavfile
from paired_meeting_pcm16_20261109 import info, read
from reference_textgrid_20261104 import read_reference_intervals, PARSER_ID

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
C = R / 'docs/handoffs/20261109-paired-real-meeting'
manifest = json.loads((C / 'pair-extraction-result.json').read_bytes())
assert manifest['gzipCrcVerified']
started = time.perf_counter()
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
protocol = {
    'at': now(), 'selection': 'Restore exposed R8001_M8004; no new independent meeting claim.',
    'speakerMapping': 'Each near reference nonempty (start,end,text) sequence must match exactly one far tier; preserve original names. Then inspect own/other solo energy and same-utterance acoustic correlation, rather than trusting filenames alone.',
    'frameSeconds': .02,
    'fineClock': {'fractions': [.2, .5, .8], 'selection': 'Nearest distinct whole non-overlap utterance of >=1.5s at each fixed fraction; +/-0.1s guard against other annotated speakers.',
                  'windowMaxSeconds': 4, 'lagSearchSeconds': [-.5, .5],
                  'filterHz': [100, 3800], 'method': 'Bandpass normalized cross-correlation over actual overlapping PCM; maximize absolute coefficient, retain polarity. Acoustic propagation is included in measured lag.',
                  'lagSign': 'Positive means near time t corresponds to far time t+lag.',
                  'noAutomaticClockCorrection': True},
    'bleed': 'Median RMS on annotated own-only, each other-only, true-overlap, and no-annotated-speech 20ms frames within annotation scope. This is relative leakage evidence, not clean-source SDR or measured transcription accuracy.',
    'rawPcmCheck': 'Compare bounded first/middle/last sample reads with scipy WAV mmap reader, including extensible PCM16 header. No audio recoding.',
    'newModelCalls': 0, 'newTrainingRuns': 0, 'qualityQualified': False,
}
(C / 'pair-audit-protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
files = manifest['files']
far_file = next(f for f in files if f['side'] == 'far' and f['name'].endswith('.wav'))
far = Path(far_file['path'])
far_meta = info(far)
far_ref = next(Path(f['path']) for f in files if f['side'] == 'far' and f['name'].endswith('.TextGrid'))
far_rows = [r for r in read_reference_intervals(far_ref) if r['text'].strip() and r['end'] > r['start']]
speakers = sorted({r['speaker'] for r in far_rows})
assert len(speakers) == 4
by_speaker = {s: sorted([r for r in far_rows if r['speaker'] == s], key=lambda r: r['start']) for s in speakers}
triples = lambda rows: [(r['start'], r['end'], r['text']) for r in rows]
near_files = sorted([f for f in files if f['side'] == 'near' and f['name'].endswith('.wav')], key=lambda f: f['name'])
paired = []
for file in near_files:
    audio = Path(file['path'])
    ref = next(Path(f['path']) for f in files if f['side'] == 'near' and Path(f['path']).stem == audio.stem and f['name'].endswith('.TextGrid'))
    rows = sorted([r for r in read_reference_intervals(ref) if r['text'].strip() and r['end'] > r['start']], key=lambda r: r['start'])
    matches = [s for s in speakers if triples(by_speaker[s]) == triples(rows)]
    assert len(matches) == 1, (audio.name, matches)
    paired.append({'speaker': matches[0], 'audio': str(audio), 'audioSha256': file['sha256'],
                   'reference': str(ref), 'referenceSha256': sha(ref), 'wave': info(audio),
                   'referenceUtterances': len(rows), 'referenceExactlyMatchesFarTier': True})
assert {p['speaker'] for p in paired} == set(speakers)

pcm_checks = []
for path, meta in [(far, far_meta)] + [(Path(p['audio']), p['wave']) for p in paired]:
    sr, mm = wavfile.read(path, mmap=True)
    assert sr == meta['rate'] and mm.dtype == np.dtype('<i2')
    for start in [0, meta['frames'] // 2, meta['frames'] - 1024]:
        own = read(path, start, start + 1024, channel=None, metadata=meta)
        expected = mm[start:start + 1024]
        if expected.ndim == 1:
            expected = expected[:, None]
        assert np.array_equal(own, expected), 'Raw PCM interpretation differs'
    pcm_checks.append({'audio': str(path), 'checkedFrames': 3072, 'bitExactAgainstScipy': True})
    del mm

duration = min([far_meta['seconds']] + [p['wave']['seconds'] for p in paired])
scope_end = min(duration, max(r['end'] for r in far_rows))
frame = 320
n_frames = int(scope_end / .02)
times = (np.arange(n_frames) + .5) * .02
active = {}
for s in speakers:
    mask = np.zeros(n_frames, dtype=bool)
    for row in by_speaker[s]:
        mask |= (times >= row['start']) & (times < row['end'])
    active[s] = mask
activity_count = np.stack([active[s] for s in speakers]).sum(axis=0)

def envelope(path, meta):
    result = np.zeros(n_frames, dtype=np.float64)
    for begin in range(0, n_frames, 4096):
        end = min(n_frames, begin + 4096)
        x = read(path, begin * frame, end * frame, channel=0, metadata=meta).astype(np.float64) / 32768
        result[begin:end] = np.sqrt(np.mean(x.reshape(-1, frame)**2, axis=1))
    return result

def energy_summary(values, mask):
    part = values[mask]
    return {'seconds': len(part) * .02, 'medianRms': float(np.median(part)) if len(part) else None,
            'medianDbfs': float(20 * np.log10(max(float(np.median(part)), 1/32768))) if len(part) else None,
            'p90Rms': float(np.quantile(part, .9)) if len(part) else None}

def peak_delay(x, y, max_lag):
    sos = signal.butter(4, [100, 3800], btype='bandpass', fs=16000, output='sos')
    x = signal.sosfiltfilt(sos, x)
    y = signal.sosfiltfilt(sos, y)
    corr = signal.correlate(x, y, method='fft', mode='full')
    lags = np.arange(-max_lag, max_lag + 1)
    a, b = np.maximum(0, lags), np.maximum(0, -lags)
    count = np.minimum(len(x)-a, len(y)-b)
    px, py = np.r_[0., np.cumsum(x)], np.r_[0., np.cumsum(y)]
    sx, sy = np.r_[0., np.cumsum(x*x)], np.r_[0., np.cumsum(y*y)]
    mx, my = px[a+count]-px[a], py[b+count]-py[b]
    vx, vy = sx[a+count]-sx[a]-mx*mx/count, sy[b+count]-sy[b]-my*my/count
    denom = np.sqrt(np.maximum(vx*vy, 1e-30))
    scores = (corr[lags + len(y)-1] - mx*my/count) / denom
    ix = int(np.argmax(np.abs(scores)))
    lag = int(lags[ix])
    distant = np.abs(lags-lag) >= 160  # Alternative >=10ms away, reported without tuning.
    return {'lagSamples': lag, 'lagSeconds': lag/16000, 'coefficient': float(scores[ix]),
            'absoluteCoefficient': float(abs(scores[ix])), 'searchBoundaryHit': abs(lag) == max_lag,
            'bestAbsoluteAlternativeAtLeast10msAway': float(np.max(np.abs(scores[distant]))) if distant.any() else None}

for pair in paired:
    s = pair['speaker']
    e = envelope(pair['audio'], pair['wave'])
    energy = {'ownOnly': energy_summary(e, active[s] & (activity_count == 1)),
              'otherOnly': energy_summary(e, ~active[s] & (activity_count == 1)),
              'overlapWithTarget': energy_summary(e, active[s] & (activity_count >= 2)),
              'noAnnotatedSpeech': energy_summary(e, activity_count == 0),
              'eachOtherOnly': {other: energy_summary(e, active[other] & (activity_count == 1)) for other in speakers if other != s}}
    energy['ownVsOtherMedianDb'] = energy['ownOnly']['medianDbfs'] - energy['otherOnly']['medianDbfs']
    pair['relativeLeakage'] = energy
    solo = [r for r in by_speaker[s] if r['end'] - r['start'] >= 1.5 and not any(
        other['speaker'] != s and other['start'] < r['end'] + .1 and other['end'] > r['start'] - .1 for other in far_rows)]
    local, used = [], set()
    for fraction in [.2, .5, .8]:
        candidates = [r for r in solo if (r['start'], r['end']) not in used]
        if not candidates:
            local.append({'fraction': fraction, 'state': 'NO_DISTINCT_ISOLATED_UTTERANCE'})
            continue
        row = min(candidates, key=lambda r: (abs((r['start']+r['end'])/2 - fraction*scope_end), r['start']))
        used.add((row['start'], row['end']))
        center = (row['start'] + row['end']) / 2
        seconds = min(4., row['end'] - row['start'])
        lo, hi = round((center-seconds/2)*16000), round((center+seconds/2)*16000)
        x = read(far, lo, hi, 0, far_meta).astype(np.float64) / 32768
        y = read(pair['audio'], lo, hi, 0, pair['wave']).astype(np.float64) / 32768
        local.append({'fraction': fraction, 'start': lo/16000, 'end': hi/16000,
                      'utteranceStart': row['start'], 'utteranceEnd': row['end'],
                      **peak_delay(x, y, 8000)})
    pair['fineAcousticDelayChecks'] = local
    known = [r for r in local if 'lagSamples' in r]
    pair['fineDelaySummary'] = {'measuredWindows': len(known),
        'medianLagSeconds': float(np.median([r['lagSeconds'] for r in known])) if known else None,
        'lagSpreadMilliseconds': (max(r['lagSeconds'] for r in known)-min(r['lagSeconds'] for r in known))*1000 if known else None,
        'minimumAbsoluteCorrelation': min(r['absoluteCoefficient'] for r in known) if known else None,
        'searchBoundaryHit': any(r['searchBoundaryHit'] for r in known),
        'sampleAccurateCleanSourceClaimed': False}
    print(json.dumps({'speaker': s, 'relativeOwnVsOtherDb': energy['ownVsOtherMedianDb'], 'fineDelay': pair['fineDelaySummary']}), flush=True)

result = {'at': now(), 'state': 'REAL_PAIR_IDENTITY_AND_ACOUSTIC_LEAKAGE_AUDITED_NO_NEW_ASR',
          'session': manifest['selectedSession'], 'archiveSha256': manifest['archiveSha256'],
          'farAudio': str(far), 'farAudioSha256': far_file['sha256'], 'farWave': far_meta,
          'farReference': str(far_ref), 'farReferenceSha256': sha(far_ref), 'parser': PARSER_ID,
          'referenceUtterances': len(far_rows), 'annotationScopeSeconds': scope_end,
          'annotatedOverlapSeconds': float((activity_count >= 2).sum() * .02),
          'rawPcmChecks': pcm_checks, 'pairedPeople': paired,
          'limits': limits.query(), 'wallSeconds': time.perf_counter() - started,
          'interpretationLimits': ['Relative other-only energy is leakage evidence, not a clean source guarantee.',
              'Acoustic delays include room propagation and cannot by themselves establish a unique digital clock offset or resampling rate.',
              'Do not align by the total-length difference; preserve each recording and annotation timeline.',
              'This exposed26min diagnostic does not meet the >=30min full-meeting sale gate and is not a new independent heldout.',
              'No oracle annotation or near headset is available to the ordinary product; this diagnostic is not a deployable speaker enrollment claim.'],
          'newModelCalls': 0, 'newTrainingRuns': 0, 'newAccuracyGain': False, 'saleQualified': False}
(C / 'pair-audit-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'state': result['state'], 'wallSeconds': result['wallSeconds'], 'limits': result['limits']}), flush=True)
