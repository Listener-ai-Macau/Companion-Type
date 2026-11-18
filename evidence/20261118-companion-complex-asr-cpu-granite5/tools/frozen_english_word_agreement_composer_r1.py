"""Evaluate one fixed word-agreement rule on cached public AMI hypotheses."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys

from rapidfuzz.distance import Levenshtein

ROOT = Path("C:/Users/Billy/Desktop/Denzic/Companion")
SOURCE = ROOT / "model-research/src"
sys.path.insert(0, str(SOURCE))
from score_sequential_meetings_20261115 import measure, tokens
from moss_windows_resource_limits_20261104 import WorkerLimits

D = ROOT / (
    "docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution"
)
J = D / "joint-architecture-r1"
E = Path("E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1")
C = E / "language-specific-adaptation-r1/english-accuracy-reference-20261117"
OUTPUT = C / "word-agreement-r1"
GRANITE = C / "native-gpu-r1/completed.json"
PARAKEET = E / "english-transducer-r1/run-r1/completed.json"
MOSS = E / "stagea-cpu-composition-r2/inference-state.json"
QWEN = E.parent / "sequential-meeting-stageA-r2/asr-r2/baseline-state.json"
INPUTS = {"Granite": GRANITE, "Parakeet": PARAKEET, "MOSS": MOSS, "Qwen": QWEN}
REFERENCE = D / "sequential-meeting-stageA-r2/scoring-only.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def get_bound_packet(row, file_key="file", hash_key="sha256"):
    path = Path(row[file_key])
    content = path.read_bytes()
    assert sha256(content).hexdigest() == row[hash_key], path
    return json.loads(content)


def proposals(primary, alternate):
    opcodes = Levenshtein.opcodes(primary, alternate)
    for index, (tag, start, end, alt_start, alt_end) in enumerate(opcodes):
        if tag not in ("insert", "replace") or index == 0 or index == len(opcodes) - 1:
            continue
        if opcodes[index - 1].tag == opcodes[index + 1].tag == "equal":
            yield start, end, tuple(alternate[alt_start:alt_end])


def fuse(primary, alternates):
    counts = Counter(edit for alternate in alternates for edit in set(proposals(primary, alternate)))
    supported = [edit for edit, count in counts.items() if count >= 2]
    # Require compatibility even at a shared insertion boundary.
    accepted = sorted(edit for edit in supported if not any(
        other != edit and max(other[0], edit[0]) <= min(other[1], edit[1])
        for other in supported
    ))
    output = []
    cursor = 0
    for start, end, replacement in accepted:
        output.extend(primary[cursor:start])
        output.extend(replacement)
        cursor = end
    output.extend(primary[cursor:])
    return output, accepted


def compose():
    states = {model: read(path) for model, path in INPUTS.items()}
    assert not states["Granite"]["referenceRead"] and states["Qwen"]["allLabelsOutsideInference"]
    granite_entries = {row["id"]: row for row in states["Granite"]["completed"]}
    ids = set(granite_entries)
    assert len(ids) == 12 and all(key.startswith(("ES2003b-", "EN2001a-")) for key in ids)
    sets = {
        name: {row["id"]: row for row in state["completed"] if row["id"] in ids}
        for name, state in states.items()
    }
    assert all(set(group) == ids for group in sets.values())
    results = []
    for case_id in sorted(ids):
        granite = get_bound_packet(sets["Granite"][case_id])
        para = get_bound_packet(sets["Parakeet"][case_id])
        moss = get_bound_packet(sets["MOSS"][case_id])
        qwen_entry = sets["Qwen"][case_id]
        qwen = get_bound_packet(qwen_entry, "document", "documentSha256")
        assert granite["id"] == para["id"] == moss["case"]["id"] == case_id
        assert granite["pcmSha256"] == qwen_entry["pcmSha256"] == moss["case"]["pcmSha256"]
        assert granite["audioSha256"] == para["audioSha256"] == moss["case"]["wavSha256"]
        assert granite["frames"] == qwen["confirmedAudioFrames"] == moss["case"]["frames"]
        assert not granite["referenceUsed"] and not para["referenceUsed"] and not moss["referenceRead"]
        assert qwen["isFinal"] and moss["originalClipComplete"] and para["allInputFramesPreserved"]
        texts = {
            "Granite": granite["text"], "Parakeet": para["text"],
            "MOSS": moss["result"]["text"], "Qwen": qwen["text"],
        }
        words = {model: tokens(text, "English") for model, text in texts.items()}
        fused, edits = fuse(words["Granite"], [words[n] for n in ("Parakeet", "MOSS", "Qwen")])
        results.append({
            "id": case_id, "pcmSha256": granite["pcmSha256"],
            "hypotheses": words, "fusedHypothesis": fused,
            "appliedEdits": [{"start": s, "end": e, "replacement": list(text)} for s, e, text in edits],
        })
    OUTPUT.mkdir(exist_ok=False)
    write(OUTPUT / "protocol.json", {
        "inputStateDigests": {str(path): digest(path) for path in INPUTS.values()},
        "sourceDigest": digest(Path(__file__)),
        "rule": "An insertion or substitution in Granite requires two decoders to propose the identical span with equal immediately adjacent words on both sides. Conflicting proposals stay with Granite. No standalone deletion.",
        "cohort": "Original fixed 12 English non-overlap clips, unchanged raw PCM",
        "maximumTotalErrors": 70,
        "maximumMeetingErrors": {"ES2003b": 46, "EN2001a": 67},
        "referenceReadByComposer": False,
    })
    write(OUTPUT / "hypotheses.json", results)
    print(json.dumps({"clips": len(results), "appliedEdits": sum(len(x["appliedEdits"]) for x in results)}))


def score():
    protocol = read(OUTPUT / "protocol.json")
    assert digest(Path(__file__)) == protocol["sourceDigest"]
    for path, value in protocol["inputStateDigests"].items():
        assert digest(Path(path)) == value
    cohort = read(OUTPUT / "hypotheses.json")
    control = read(J / "english-transducer-r1/scoring-control.json")
    assert Path(control["references"]) == REFERENCE
    for file in control["files"]:
        assert digest(Path(file["file"])) == file["sha256"]
    ids = {row["id"] for row in cohort}
    cases = {row["id"]: row for row in read(REFERENCE) if row["id"] in ids}
    assert set(cases) == ids
    graphite = read(C / "score.json")
    assert digest(GRANITE) == graphite["completedInferenceSha256"]
    granite_rows = {row["id"]: row for row in graphite["cases"]}
    edits = ("errors", "substitutions", "deletions", "insertions")
    totals = defaultdict(Counter)
    meetings = defaultdict(Counter)
    diagnostics = Counter()
    by_meeting = defaultdict(Counter)
    rows = []
    for out in cohort:
        case = cases[out["id"]]
        assert case["pcmSha256"] == out["pcmSha256"] and case["role"] == "validation"
        assert case["language"] == "English" and not case["overlapPresentByReference"]
        ref_text = case["rawReferenceText"]
        ref = tokens(ref_text, "English")
        words = {**out["hypotheses"], "agreement": out["fusedHypothesis"]}
        scored = {
            name: measure(ref_text, " ".join(hypothesis), "English")
            for name, hypothesis in words.items()
        }
        assert scored["Granite"]["errors"] == granite_rows[case["id"]]["errors"]
        for model, result in scored.items():
            totals[model].update({key: result[key] for key in (*edits, "referenceUnits")})
            meetings[case["meeting"]][model] += result["errors"]
        missed = {
            name: {op["referenceIndex"] for op in result["editOperations"] if op["operation"] == "delete"}
            for name, result in scored.items()
        }
        incorrect = {
            name: {op["referenceIndex"] for op in result["editOperations"] if op["operation"] != "insert"}
            for name, result in scored.items()
        }
        alt = ("Parakeet", "MOSS", "Qwen")
        granite_deletions = missed["Granite"]
        recovered_by_one = {pos for pos in granite_deletions if any(pos not in incorrect[m] for m in alt)}
        recovered_by_two = {pos for pos in granite_deletions if sum(pos not in incorrect[m] for m in alt) >= 2}
        group = {
            "referenceWords": len(ref),
            "graniteDeletions": len(granite_deletions),
            "graniteDeletedButExactInOneAlternate": len(recovered_by_one),
            "graniteDeletedButExactInTwoAlternates": len(recovered_by_two),
            "allFourIncorrectAtSameReferencePosition": len(set.intersection(*(incorrect[m] for m in INPUTS))),
            "graniteDeletedAndFusedExact": len(granite_deletions - incorrect["agreement"]),
            "newlyIncorrectGraniteExactPositions": len(incorrect["agreement"] - incorrect["Granite"]),
        }
        diagnostics.update(group)
        by_meeting[case["meeting"]].update(group)
        rows.append({
            "id": case["id"], "meeting": case["meeting"], "appliedEdits": len(out["appliedEdits"]),
            "granite": {key: scored["Granite"][key] for key in edits},
            "agreement": {key: scored["agreement"][key] for key in edits}, **group,
        })
    assert diagnostics["referenceWords"] == 709
    assert [totals[key]["errors"] for key in INPUTS] == [113, 123, 141, 147]
    accepted = (
        totals["agreement"]["errors"] <= protocol["maximumTotalErrors"] and
        all(group["agreement"] <= protocol["maximumMeetingErrors"][name] for name, group in meetings.items())
    )
    result = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "state": "WORD_AGREEMENT_PASS_SCREEN" if accepted else "WORD_AGREEMENT_REJECT_FIXED_SCHEME",
        "totals": {k: {**v, "WER": v["errors"] / v["referenceUnits"]} for k, v in totals.items()},
        "meetingErrors": meetings,
        "diagnostics": diagnostics,
        "diagnosticsByMeeting": by_meeting,
        "cases": rows,
        "sourceSha256": digest(Path(__file__)),
        "hypothesesSha256": digest(OUTPUT / "hypotheses.json"),
        "referenceSha256": digest(REFERENCE),
        "scope": "Aligned public reference positions are diagnostic. Edit alignments can differ for repeated words. Evidence does not measure full meetings, streaming, speaker attribution or product latency.",
        "advanceToWholeMeetings": accepted,
        "newInferenceCalls": 0,
        "trainingUpdates": 0,
        "qualityQualified": False,
        "saleQualified": False,
    }
    write(OUTPUT / "score.json", result)
    print(json.dumps({k: result[k] for k in ("state", "totals", "meetingErrors", "diagnostics")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("compose", "score"))
    args = parser.parse_args()
    limits = WorkerLimits(cpu_percent=5, memory_bytes=256 * 1024**2)
    (compose if args.stage == "compose" else score)()
