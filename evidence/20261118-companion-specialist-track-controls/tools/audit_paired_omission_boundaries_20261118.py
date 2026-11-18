"""Check short turns and clip edges on already-scored public paired audio."""

from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys

from rapidfuzz.distance import Levenshtein


ROOT = Path("C:/Users/Billy/Desktop/Denzic/Companion")
sys.path.insert(0, str(ROOT / "model-research/src"))
from score_sequential_meetings_20261115 import tokens


D = ROOT / (
    "docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/"
    "d1d2-execution"
)
JOINT = D / "joint-architecture-r1"
RUN = Path(
    "E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/"
    "microphone-diagnostic-r1/gpu-run"
)


def read(path):
    return path.read_bytes()


reference_path = D / "sequential-meeting-stageA-r2/scoring-only.json"
review_path = JOINT / "english-acoustic-omission-review20261116.json"
run_path = RUN / "completed.json"
paired_score = JOINT / "microphone-diagnostic-r1/error-decomposition.json"
cases = {case["id"]: case for case in json.loads(read(reference_path))}
review = json.loads(read(review_path))
words_by_case = defaultdict(list)
for word in review["wordInspection"]:
    words_by_case[word["id"]].append(word)

short_turns = {
    (row["id"], row["speaker"], row["start"], row["end"])
    for row in review["shortTurns"]
}
groups = defaultdict(Counter)
run = json.loads(read(run_path))
assert run["nativeControlExact"] and len(run["completed"]) == 13
for item in run["completed"]:
    result = read(Path(item["file"]))
    assert sha256(result).hexdigest() == item["sha256"]
    packet = json.loads(result)
    if packet["kind"] == "native-distant-control":
        continue
    case_id = packet["caseId"]
    case = cases[case_id]
    assert case["language"] == "English" and not case["overlapPresentByReference"]
    ref = tokens(case["rawReferenceText"], "English")
    near_edits = {
        edit.src_pos: edit.tag
        for edit in Levenshtein.editops(ref, tokens(packet["text"], "English"))
        if edit.tag != "insert"
    }
    atoms = [
        (token, event)
        for event in case["referenceEvents"]
        for token in tokens(event["text"], "English")
    ]
    assert [token for token, _ in atoms] == ref
    start, end = (case[key] / 16000 for key in ("sourceStartFrame", "sourceEndFrame"))
    for word in words_by_case[case_id]:
        if word["edit"] != "delete":
            continue
        index = word["referenceIndex"]
        token, event = atoms[index]
        assert token == word["token"]
        group = groups[near_edits.get(index, "equal")]
        midpoint = (event["start"] + event["end"]) / 2
        at_edge = min(midpoint - start, end - midpoint) <= 1
        in_short_turn = any(
            case_id == turn_case and event["speaker"] == speaker and
            turn_start <= midpoint <= turn_end
            for turn_case, speaker, turn_start, turn_end in short_turns
        )
        relative_rms = word["relativeToClipMedianRms"]
        group.update(
            words=1,
            withinOneSecondOfClipEdge=int(at_edge),
            shortTurnAtMostTwoSeconds=int(in_short_turn),
            eitherBoundary=int(at_edge or in_short_turn),
            lowestRmsQuartile=int(relative_rms is not None and
                                  relative_rms <= review["lowerQuartileThresholdRelativeRms"]),
        )

previous = json.loads(read(paired_score))
assert {status: row["words"] for status, row in groups.items()} == {
    row["headset"]: row["words"] for row in previous["referenceWordTransitions"]
    if row["far"] == "delete"
}
report = {
    "at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "state": "PAIRED_FAR_FIELD_OMISSION_LOCATION_AUDITED",
    "groupsByNearEditAfterFarDeletion": groups,
    "sources": {str(path): sha256(read(path)).hexdigest()
                for path in (reference_path, review_path, run_path, paired_score)},
    "scope": "Reference midpoint within one second of an original clip edge, or in a contiguous turn of at most two seconds. RMS quartile is based on the earlier unchanged far-field audit.",
    "limitations": "Two exposed AMI meetings. Word times and Levenshtein alignments are diagnostic. Neither reference boundaries nor mic pairing are proposed as product inputs.",
    "newInferenceCalls": 0,
    "trainingUpdates": 0,
    "qualityQualified": False,
}
target = JOINT / "paired-far-field-omission-boundaries-20261118.json"
with target.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
print(json.dumps(groups, ensure_ascii=False))
