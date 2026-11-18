"""Trace frozen meeting evidence into the saved reading layer without inference."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def document_receipt(report):
    receipt = report.get("receipt", report)
    return receipt.get("documentReceipt", receipt)


def source_bytes(path):
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").encode("utf-8")


def pointer(path):
    return "/" + re.sub(r"\[(\d+)\]", r"/\1", path.replace(".", "/"))


def visible(path):
    return ".points[" in path or path.startswith(("decisions[", "actionItems[", "questions["))


def field_at(document, path):
    value = document
    for key in path.split("/")[1:]:
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def compact(text):
    return "".join(text.split())


def reference_claims(reference, source):
    text = source.decode("utf-8")
    offsets = [0]
    for letter in text:
        offsets.append(offsets[-1] + len(letter.encode("utf-8")))
    for check in reference["checks"]:
        for number, claim in enumerate(check["evidence"], start=1):
            start, end = claim["startCharacter"], claim["endCharacter"]
            if not 0 <= start < end <= len(text) or text[start:end] != claim["quote"]:
                raise ValueError(f'{check["id"]}/{number} does not match the frozen transcript')
            yield check["id"], number, claim["quote"], offsets[start], offsets[end]


def evidence_spans(receipt, source):
    bindings = dict(receipt["layoutBindings"])
    candidates = {
        fact_id
        for chapter in receipt["atomicFactBank"]["plannedChapters"]
        for fact_id in chapter.get("mainFactChoices", [])
    }
    units = {}
    offset = 0
    for unit in receipt["sourceUnits"]:
        data = unit["text"].encode("utf-8")
        end = offset + len(data)
        if unit["id"] in units or source[offset:end] != data:
            raise ValueError(f'Invalid transcript unit {unit["id"]}')
        units[unit["id"]] = (offset, data)
        offset = end
    if offset != len(source):
        raise ValueError("Transcript units do not cover the whole source")

    spans = []
    for anchor in receipt["evidenceAnchors"]:
        path = anchor["path"]
        unit_start, data = units[anchor["source"]]
        start, end = anchor["startByte"], anchor["endByte"]
        original = anchor["quote"].encode("utf-8")
        if not 0 <= start < end <= len(data) or data[start:end] != original:
            raise ValueError(f"Invalid source span at {path}")
        location = pointer(path)
        fact_id = bindings[location]
        text = field_at(receipt["document"], location)["text"]
        spans.append((unit_start + start, unit_start + end, fact_id, path,
                      fact_id in candidates, visible(path), compact(text)))
    return spans


def evaluate(report, claims, source, fingerprint):
    receipt = document_receipt(report)
    if receipt["sourceSha256"] != fingerprint:
        raise ValueError("Receipt belongs to a different transcript")
    spans = evidence_spans(receipt, source)
    rows = []
    for check, number, quote, start, end in claims:
        hits = [span for span in spans if span[0] <= start and span[1] >= end]
        if any(span[5] and compact(quote) in span[6] for span in hits):
            stage = "primary"
        elif any(span[5] for span in hits):
            stage = "context_only"
        elif any(span[4] for span in hits):
            stage = "candidate_only"
        elif hits:
            stage = "details_only"
        else:
            stage = "no_bound_evidence"
        rows.append({
            "id": f"{check}/{number}", "quote": quote, "stage": stage,
            "placements": sorted({span[3] for span in hits}),
            "factIds": sorted({span[2] for span in hits}),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--require-visible", action="append", default=[], metavar="CHECK/NUMBER",
                        help="Fail if this specific frozen evidence span stays out of the reading layer")
    parser.add_argument("receipts", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        source = source_bytes(args.source)
        fingerprint = hashlib.sha256(source).hexdigest()
        reference = read(args.reference)
        if reference["sourceSha256"] != fingerprint:
            raise ValueError("Reference belongs to a different transcript")
        claims = list(reference_claims(reference, source))
        keys = {f"{check}/{number}" for check, number, *_ in claims}
        unknown = set(args.require_visible) - keys
        if unknown:
            raise ValueError(f'Unknown required evidence: {", ".join(sorted(unknown))}')
        reports = []
        for path in args.receipts:
            rows = evaluate(read(path), claims, source, fingerprint)
            failures = [row["id"] for row in rows if row["id"] in args.require_visible and row["stage"] != "primary"]
            reports.append({"receipt": str(path), "requiredVisibleMissing": failures, "claims": rows})
    except (KeyError, IndexError, OSError, ValueError) as error:
        parser.exit(2, f"Evidence review could not run. {error}\n")
    print(json.dumps({
        "sourceSha256": fingerprint, "mechanicalEvidenceReview": True,
        "semanticOrReleaseQualification": False, "newInferenceRequests": 0, "reports": reports,
    }, ensure_ascii=False, indent=2))
    return int(any(report["requiredVisibleMissing"] for report in reports))


if __name__ == "__main__":
    raise SystemExit(main())
