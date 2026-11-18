"""Compare exact word coverage after the fixed Granite 5 CPU run."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

R = Path("C:/Users/Billy/Desktop/Denzic/Companion")
sys.path.insert(0, str(R / "model-research/src"))
from score_sequential_meetings_20261115 import measure
from moss_windows_resource_limits_20261104 import WorkerLimits

C = Path(
    "E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/"
    "language-specific-adaptation-r1/english-accuracy-reference-20261117"
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def incorrect(reference, hypothesis):
    operations = measure(reference, hypothesis, "English")["editOperations"]
    return {item["referenceIndex"]: item["operation"] for item in operations if item["operation"] != "insert"}


limits = WorkerLimits(cpu_percent=5, memory_bytes=256 * 1024**2)
run = C / "granite5-q4-native-cpu-r2"
protocol = read(run / "protocol.json")
binding = protocol["originalReferences"]
reference_bytes = Path(binding["file"]).read_bytes()
assert sha256(reference_bytes).hexdigest() == binding["sha256"]
references = {row["id"]: row["rawReferenceText"] for row in json.loads(reference_bytes)}
new_score = read(run / "score.json")
old_hypotheses = C / "word-agreement-r1/hypotheses.json"
agreement_score = read(C / "word-agreement-r1/score.json")
assert sha256(old_hypotheses.read_bytes()).hexdigest() == agreement_score["hypothesesSha256"]
old = {row["id"]: row["hypotheses"] for row in read(old_hypotheses)}
new = read(run / "completed.json")
assert new["state"] == "COMPLETE_NATIVE_GRANITE5_CPU" and len(new["completed"]) == 12

summary = Counter()
for entry in new["completed"]:
    packet = Path(entry["file"]).read_bytes()
    assert sha256(packet).hexdigest() == entry["sha256"]
    result = json.loads(packet)
    reference = references[result["id"]]
    older = {name: incorrect(reference, " ".join(text)) for name, text in old[result["id"]].items()}
    shared = set.intersection(*(set(edits) for edits in older.values()))
    after = incorrect(reference, result["text"])
    granite = older["Granite"]
    earlier_deleted = {i for i, operation in granite.items() if operation == "delete"}
    new_deletions = {i for i, operation in after.items() if operation == "delete"}
    summary.update(
        wrongInAllFourEarlierModels=len(shared),
        samePositionsStillWrong=len(shared & set(after)),
        samePositionsNowExact=len(shared - set(after)),
        granite41DeletedNowExact=len(earlier_deleted - set(after)),
        granite5NewDeletionAtPreviouslyExactPosition=len(new_deletions - set(granite)),
    )
assert summary["wrongInAllFourEarlierModels"] == agreement_score["diagnostics"]["allFourIncorrectAtSameReferencePosition"]
report = {
    "alignmentDiagnostic": dict(summary),
    "granite41": agreement_score["totals"]["Granite"],
    "granite5": {"errors": new_score["errors"], "WER": new_score["wer"], "words": 709},
    "scope": "Original public clips and independent Levenshtein alignments; repeated words can shift positions. This is not an audio alignment or an acceptance result.",
    "newInferenceCalls": 0,
}
with (run / "residual-comparison.json").open("x", encoding="utf-8") as target:
    json.dump(report, target, ensure_ascii=False, indent=2)
print(json.dumps(summary))
