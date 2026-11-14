"""Read-only reuse of completed evidence; no model calls or parameter changes."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import re
import sys

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
C = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
sys.path.insert(0, str(SRC))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
from reference_textgrid_20261104 import read_reference_intervals
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
policy = read(C / 'alignment/join-policy.json')
assert sha(policy['speakerJournal']) == policy['speakerJournalSha256']
assert sha(policy['producerFile']) == policy['producerSha256']
producer = read(policy['producerFile'])
assert producer['oneContinuousSpeakerState'] and producer['allOriginalAudioSamplesSubmitted']
journal = read(policy['speakerJournal'])
case, = read(C / 'scoring-only.json')
assert sha(case['reference']) == case['referenceSha256']
diagnosis_path = C / 'native8/results' / case['meeting'] / 'failure-diagnosis.json'
diagnosis = read(diagnosis_path)
assert diagnosis['wholeComponentsReproduced']
assert diagnosis['fixedFullMeetingMappingForEvaluationOnly']['speaker_2'] == '003-M'
last_predicted = max(row['end'] for row in journal['segments'] if row['speaker'] == 2)
refs = [r for r in read_reference_intervals(case['reference'])
        if r['speaker'] == '003-M' and re.sub(r'<[^>]*>', '', r['text']).strip()]
after = [r for r in refs if r['start'] > last_predicted]
before = [r for r in refs if r['start'] <= last_predicted]
return_start = min(r['start'] for r in after)
last_reference_before_gap = max(r['end'] for r in before)
assert return_start-last_reference_before_gap > 400
assert all(r['start'] > last_predicted for r in after)
result = {
    'at': datetime.now().astimezone().isoformat(timespec='seconds'),
    'state': 'ONE_PRIORITY_SPEAKER_IDENTITY_RETENTION_ISSUE_NO_NEW_INFERENCE',
    'ownerLatest': '好的, 就是要快点收敛',
    'baselineCommit': '05d173a403603b614ac37077d6cabd9583372bc4',
    'meeting': case['meeting'], 'referenceSpeakerForScoringOnly': '003-M',
    'nativeSpeakerForScoringOnly': 2, 'lastPredictedActivitySeconds': last_predicted,
    'lastReferenceBeforeGapSeconds': last_reference_before_gap,
    'referenceReturnSeconds': return_start,
    'referenceSilenceGapSeconds': return_start-last_reference_before_gap,
    'referenceSpansAfterReturn': len(after),
    'referenceSpanSecondsAfterReturn': sum(r['end']-r['start'] for r in after),
    'referenceSpansAtLeastTwoSecondsAfterReturn': sum(r['end']-r['start'] >= 2 for r in after),
    'matchingOriginalNativeSpeakerSegmentsAfterReturn': 0,
    'confirmedBoundary': 'The preserved raw speaker journal already loses this anonymous identity after a long absence. This particular failure precedes ASR-to-speaker alignment and includes longer utterances; a short-response-only explanation is insufficient.',
    'notYetProven': 'Why the native model merges the returning voice: cache/identity memory versus acoustic input conditions is unresolved. No native cache bug, automatic fix, new model or quality improvement is claimed.',
    'nextSingleWorkItem': 'Inspect the existing native speaker state/update implementation against this one returning-speaker failure before proposing one fixed identity-retention change. Keep ASR, aligner and attribution thresholds frozen.',
    'nextValidationRule': 'Only after a concrete cause and implementation exist: one fixed full-meeting validation batch covering the prior ordinary case and this failure case. Require returning-speaker improvement without worsening other people, deletions or prior ordinary performance. A failure retains evidence, restores the proven baseline and ends that candidate; no automatic variants.',
    'fullProductGatesUnchanged': 'Raw CER<5%, DER<=10%, facts/multiple meetings/unseen rooms/English/real-card acceptance still open; a component improvement alone cannot qualify delivery.',
    'evidence': {str(p): sha(p) for p in [Path(policy['speakerJournal']), Path(policy['producerFile']),
                                           Path(case['reference']), diagnosis_path, C/'result.json']},
    'newNeuralCalls': 0, 'newWeightUpdates': 0, 'sourceOrDefaultProductChanged': False,
    'limits': limits.query(), 'qualityQualified': False}
target = C / 'convergence-review-r1.json'
assert not target.exists()
target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
out = Path(__file__).resolve().parent.parent / 'outputs/Companion-人物身份收敛定位-20261114.json'
assert not out.exists()
out.write_bytes(target.read_bytes())
p = Path(__file__).resolve().with_name('bilingual_progress.json')
data = read(p)
data['state'] = 'ONE_CONFIRMED_UPSTREAM_SPEAKER_RETENTION_ISSUE_NO_NEW_INFERENCE'
data['ownerConvergeQuickly20261114'] = result['ownerLatest']
data['speakerIdentityConvergence20261114'] = result
data['next'] = ('Owner明确快点收敛。当前只留一项优先：长时间不发言后重新开口的原始人物身份丢失。'
                '先核原生分人状态/更新实现与该失败，不再改ASR、对齐、归属阈值或跑新模型/训练；'
                '具体根因和固定实现成立后，只做一次覆盖原普通会及当前失败场的完整验证，不改善即保留失败、回到已验基线并结束该候选。'
                '原中英、复杂重叠、事实、实卡增量/离线及质量合同继续未完成。')
data['logResult'] += (f' {result["at"]} Owner进一步要求快点收敛；复用已退出原分人日志和官方参考，0新神经/0调参定位到更具体边界：'
                     f'评分003-M对应原native2声部最后在{last_predicted:.6f}s出现，参考最后1041.14708s后间隔{result["referenceSilenceGapSeconds"]:.6f}s，'
                     f'1484.118704s回来，此后{len(after)}条参考发言共{result["referenceSpanSecondsAfterReturn"]:.6f}s，含14条>=2s，原native2始终无活动。'
                     '因此不是只靠短回应边界修补可闭环，该故障在原分人输出里已经存在；底层身份记忆/输入声学具体根因仍未证明，不冒称缓存bug已修。'
                     '优先项收成原生人物身份长间隔保持，只允许有具体根因的一项固定干预、一次固定整会验证，失败结束候选不自动变体。')
p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ['state', 'lastPredictedActivitySeconds', 'referenceSilenceGapSeconds',
                                        'referenceSpansAfterReturn', 'referenceSpanSecondsAfterReturn',
                                        'referenceSpansAtLeastTwoSecondsAfterReturn', 'newNeuralCalls']}, ensure_ascii=False))
