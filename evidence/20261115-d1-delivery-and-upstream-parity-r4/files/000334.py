"""Freeze the established point-onset rule before its cached regression control."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-alignment-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert read(C/'decision-r1.json')['state']=='REJECT_FULL_POSITIVE_INTERVAL_IDENTITY_PROMOTION_REGRESSION_RETAINED'
target=C/'onset-attribution-policy.json';assert not target.exists()
policy=read(C/'attribution-policy.json')
policy.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),
    state='FROZEN_BEFORE_ZERO_NEURAL_HISTORICAL_ONSET_REGRESSION_CONTROL',
    postprocessorSourceSha256=sha(Path(__file__).with_name('finish_practical_alignment_onset_20261107.py')),
    rule='Apply unchanged historical onset_attribution with60ms margin to every finite predicted onset strictly inside its original source leaf. Equal start/end classes can have a usable approximate onset, never a verified duration. Stable single-person window only; overlap, gaps, boundaries or out-of-bound onset remain unknown. Display end is onset+60ms clipped, identical established onset-display semantics. Both full meetings, no threshold sweep/per-meeting policy selection.',
    sameAsrTextPredictedTimestampClassesAndSpeakerActivity=True,newNeuralCallsAllowed=0,
    priorFullIntervalReviewSha256=sha(C/'review.json'),priorFailureDecisionSha256=sha(C/'decision-r1.json'))
atomic_json(target,policy);print(json.dumps({'state':policy['state']}))
