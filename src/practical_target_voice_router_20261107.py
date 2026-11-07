"""Model-independent dispatch and target-identity admission, without reference labels."""
import math

def route_kind(predicted_people,predicted_overlap_seconds):
    if not math.isfinite(predicted_overlap_seconds) or predicted_overlap_seconds<0:raise ValueError('Invalid predicted overlap duration')
    return 'retain_original' if len(set(predicted_people))<2 or predicted_overlap_seconds==0 else 'verify_extracted_targets'

def admits_target(target,same_meeting_cosines):
    scores={int(k):float(v) for k,v in same_meeting_cosines.items()}
    if target not in scores or not scores or any(not math.isfinite(v) or not -1.00001<=v<=1.00001 for v in scores.values()):
        raise ValueError('Invalid matching-encoder identity scores')
    ranked=sorted(scores,key=lambda person:(-scores[person],person))
    # This is the predeclared top1 rule, not a fitted cosine cutoff. Keep raw
    # rejected audio for review; do not reassign it to another target lane.
    return ranked[0]==target
