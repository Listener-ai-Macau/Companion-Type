"""Evaluate a minutes receipt against a frozen, source-reviewed case.

The rubric describes visible meaning and placement. Keyword checks are a
repeatable regression guard for the reviewed case; new cases need source review.
"""
from argparse import ArgumentParser
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
import re


def display_path(pointer):
    return re.sub(r"/(\d+)", r"[\1]", pointer).lstrip("/").replace("/", ".")


def matches(rule, entry):
    return (not rule.get("kind") or entry.get("kind") in rule["kind"]) and all(
        word in entry["text"] for word in rule["all"]
    )


def score(case, receipt, source):
    source_hash = sha256(source).hexdigest()
    if len({source_hash, receipt["sourceSha256"], case["sourceSha256"]}) != 1:
        raise ValueError("The case, receipt and input must bind to the same normalized transcript")
    document = receipt["document"]
    visible = {
        f"/topics/{index}/points/{point}": entry
        for index, topic in enumerate(document["topics"])
        for point, entry in enumerate(topic["points"])
    }
    for field, kind in (("decisions", "decision"), ("actionItems", "action"), ("questions", "question")):
        visible.update({f"/{field}/{index}": {**entry, "kind": kind}
                        for index, entry in enumerate(document[field])})
    supplemental = {
        f"/topics/{index}/details/{detail}": entry
        for index, topic in enumerate(document["topics"])
        for detail, entry in enumerate(topic["details"])
    }
    facts = {fact["id"]: set(fact["evidence"]) for fact in receipt["facts"]}
    bindings = dict(receipt["layoutBindings"])
    if set(bindings) != visible.keys() | supplemental.keys():
        raise ValueError("The review requires a source fact binding for every minutes row")
    units = {unit["id"]: unit["text"].encode("utf-8") for unit in receipt["sourceUnits"]}
    if b"".join(units.values()) != source:
        raise ValueError("The ordered source units must reproduce the full transcript")
    anchors = defaultdict(list)
    for anchor in receipt["evidenceAnchors"]:
        start, end = anchor["startByte"], anchor["endByte"]
        unit = units[anchor["source"]]
        exact = 0 <= start < end <= len(unit) and unit[start:end] == anchor["quote"].encode("utf-8")
        anchors[anchor["path"]].append((anchor["source"], exact))

    def traceable(path, entry):
        cited = anchors[display_path(path)]
        return bool(entry["sources"]) and (
            set(entry["sources"]) == {source for source, _ in cited}
            and all(exact for _, exact in cited)
        )

    findings = []
    for rule in case["reference"]:
        expected = set(re.findall(r"e[0-9]{4,}", " ".join(rule["source"])))
        hits = [path for path, entry in visible.items() if matches(rule, entry)
                and (not expected or expected & facts[bindings[path]]) and traceable(path, entry)]
        other = [path for path, entry in supplemental.items()
                 if matches({"all": rule["all"]}, entry)
                 and (not expected or expected & facts[bindings[path]]) and traceable(path, entry)]
        findings.append({"id": rule["id"], "label": rule["label"], "source": rule["source"],
                         "critical": rule.get("critical", False), "visiblePaths": hits,
                         "supplementalPaths": other})
    errors = [
        {"id": rule["id"], "label": rule["label"], "critical": rule.get("critical", False),
         "paths": [path for path, entry in visible.items() if matches(rule, entry)]}
        for rule in case["rejected"]
    ]
    errors = [item for item in errors if item["paths"]]
    for kind, expected in case["expectedEventCounts"].items():
        actual = len(document[kind])
        if expected != actual:
            errors.append({"id": kind, "critical": True, "expected": expected, "actual": actual})
    critical = [row for row in findings if row["critical"]]
    covered = sum(bool(row["visiblePaths"]) for row in findings)
    critical_covered = sum(bool(row["visiblePaths"]) for row in critical)
    traced = sum(traceable(path, entry) for path, entry in visible.items())
    critical_errors = sum(row["critical"] for row in errors)
    metrics = {
        "keyCoverage": {"hit": covered, "total": len(findings)},
        "criticalCoverage": {"hit": critical_covered, "total": len(critical)},
        "literalTraceability": {"hit": traced, "total": len(visible)},
        "criticalErrorTypes": critical_errors,
    }
    gates = case["gates"]

    def at_least(hit, total, minimum):
        return total > 0 and hit / total >= minimum

    passed = all((
        at_least(covered, len(findings), gates["minKeyCoverage"]),
        at_least(critical_covered, len(critical), gates["minCriticalCoverage"]),
        at_least(traced, len(visible), gates["minLiteralTraceability"]),
        critical_errors <= gates["maxCriticalErrors"],
    ))
    return {"metrics": metrics, "gates": gates, "casePassed": passed,
            "findings": findings, "knownErrors": errors, "events": {
                kind: len(document[kind]) for kind in case["expectedEventCounts"]
            }}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-pass", action="store_true", help="Exit with status 1 when the scored candidate fails")
    args = parser.parse_args()
    case = json.loads(args.case.read_text(encoding="utf-8"))
    source = args.source.read_text(encoding="utf-8-sig").encode("utf-8")

    def from_path(path):
        return score(case, json.loads(path.read_text(encoding="utf-8"))["receipt"], source)

    report = {"case": case["case"], "assessment": case["assessment"],
              "sourceSha256": case["sourceSha256"], "before": from_path(args.before)}
    if args.after is not None:
        report["after"] = from_path(args.after)
    if args.report is not None:
        with args.report.open("x", encoding="utf-8") as file:
            json.dump(report, file, ensure_ascii=False, indent=2)
            file.write("\n")
    print(json.dumps({label: report[label]["metrics"] | {"casePassed": report[label]["casePassed"]}
                      for label in ("before", "after") if label in report}, ensure_ascii=False))
    if args.require_pass and not report.get("after", report["before"])["casePassed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
