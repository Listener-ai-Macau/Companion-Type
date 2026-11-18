"""Screen the publisher-recommended Q8 TurboCTC route on the same PCM."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import threading
import time
import wave

from probe_granite5_cpu_candidate_20261118 import (
    BASE, CONTROL, OUT as AR_RUN, digest, now, read, SessionConflict,
    SystemRamPressure, WorkerLimits, atomic_json, exclusive_file, own_limits, psutil,
)

CACHE = BASE / ".model-cache/granite-turboctc-q8-r1"
WEIGHT = CACHE / "granite-speech-5.0-470m-turboctc-Q8_0.gguf"
EXPECTED = "fc34cbe71f979a6aeb8bea08bfac88d5c62c1736c0bc845827e37c90f28e336c"
JOINT = CONTROL.parents[1]
NATIVE = JOINT / "cpu-pcm-candidate-r1/runtime-cpu-only"
PYTHON = JOINT / "cpp-r1/python"
OUT = CONTROL / "granite-turboctc-q8-cpu-r1"


def run():
    limits = own_limits(25)
    assert WEIGHT.is_file() and digest(WEIGHT) == EXPECTED
    old = read(AR_RUN / "protocol.json")
    OUT.mkdir(exist_ok=False)
    atomic_json(OUT / "protocol.json", {
        "sameInputs": old["cases"], "publisherControlSha256": old["publisherControlSha256"],
        "modelSha256": EXPECTED, "quantization": "Q8_0", "device": "cpu",
        "sourceSha256": digest(__file__), "secondsLimit": 260,
        "runtimeDlls": {p.name: digest(p) for p in sorted(NATIVE.glob("*.dll"))},
        "sourcePublisher": "https://huggingface.co/ibm-granite/granite-speech-5.0-470m-turboctc",
    })
    assert not (NATIVE / "ggml-vulkan.dll").exists()
    result = {"state": "WAITING_FOR_SHARED_MODEL_LEASE", "at": now(), "completed": [], "referenceRead": False}
    pressure = SystemRamPressure()
    halted = threading.Event()
    deadline = time.monotonic() + 380

    def save(state, **extra):
        result.update(state=state, observedAt=now(), **extra)
        atomic_json(OUT / "state.json", result, progress=True)

    def watch():
        while not halted.wait(.5):
            if time.monotonic() > deadline or pressure.low() or psutil.virtual_memory().available < old["minimumAvailableBytes"]:
                save("CPU_TURBOCTC_STOPPED_AT_MEMORY_OR_TIME_BOUNDARY")
                atomic_json(OUT / "completed.json", result)
                os._exit(76)

    save("WAITING_FOR_SHARED_MODEL_LEASE")
    try:
        with ExitStack() as stack:
            lease = time.monotonic() + 120
            while True:
                try:
                    stack.enter_context(exclusive_file(Path(old["neuralLock"])))
                    break
                except SessionConflict:
                    if time.monotonic() >= lease:
                        raise
                    time.sleep(2)
            deadline = time.monotonic() + 260
            threading.Thread(target=watch, daemon=True).start()
            stack.enter_context(os.add_dll_directory(str(NATIVE)))
            os.environ.update(TRANSCRIBE_LIBRARY=str(NATIVE / "transcribe.dll"),
                              OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="4")
            sys.path.insert(0, str(PYTHON))
            import numpy as np
            import transcribe_cpp as cpp

            assert cpp.native_version() == "0.4.2" and cpp.native_commit().startswith("275cd50")
            with cpp.Model(str(WEIGHT), backend="cpu", no_mmap=False) as model:
                assert model.device.kind == "cpu"
                save("MODEL_READY", backend=model.backend, architecture=model.arch, nativeCommit=cpp.native_commit())
                inputs = [{"id": "publisher-control", "audio": old["publisherControl"],
                           "audioSha256": old["publisherControlSha256"]}, *old["cases"]]
                for case in inputs:
                    path = Path(case["audio"])
                    assert digest(path) == case["audioSha256"]
                    with wave.open(str(path), "rb") as source:
                        control = case["id"] == "publisher-control"
                        sample_rate = source.getframerate()
                        assert (source.getnchannels(), source.getsampwidth()) == (1, 2)
                        assert sample_rate == (48000 if control else 16000)
                        pcm = source.readframes(8 * sample_rate if control else case["frames"])
                    if not control:
                        from hashlib import sha256
                        assert sha256(pcm).hexdigest() == case["pcmSha256"] and len(pcm) == case["frames"] * 2
                    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
                    if control:
                        samples = samples.reshape(-1, 3).mean(axis=1)
                    started = time.monotonic()
                    save("DECODING_FIXED_CLIP", activeCase=case["id"])
                    with model.session(n_threads=4) as session:
                        output = session.run(samples, timestamps="none")
                    if control:
                        assert "best of times" in output.text.lower(), "publisher speech positive control failed"
                        result["publisherControlPassed"] = True
                    else:
                        packet = OUT / (case["id"] + ".json")
                        atomic_json(packet, {"id": case["id"], "text": output.text,
                                             "pcmSha256": case["pcmSha256"], "seconds": time.monotonic()-started,
                                             "audioSeconds": case["frames"]/16000})
                        result["completed"].append({"file": str(packet), "sha256": digest(packet)})
            save("COMPLETE_CPU_TURBOCTC", activeCase=None)
    except BaseException as error:
        save("CPU_TURBOCTC_FAILURE_RETAINED", error=repr(error))
        raise
    finally:
        halted.set()
        pressure.close()
        result["limits"] = limits.query()
        atomic_json(OUT / "completed.json", result)


def score():
    from collections import defaultdict
    from score_sequential_meetings_20261115 import measure

    state = read(OUT / "completed.json")
    assert state["state"] == "COMPLETE_CPU_TURBOCTC" and not state["referenceRead"]
    assert state["publisherControlPassed"] and len(state["completed"]) == 12
    old = read(AR_RUN / "protocol.json")
    reference = old["originalReferences"]
    assert digest(reference["file"]) == reference["sha256"]
    cases = {case["id"]: case for case in read(reference["file"])}
    meetings = defaultdict(int)
    rows = []
    for entry in state["completed"]:
        assert digest(entry["file"]) == entry["sha256"]
        out = read(entry["file"])
        case = cases[out["id"]]
        assert out["pcmSha256"] == case["pcmSha256"] and case["language"] == "English"
        m = measure(case["rawReferenceText"], out["text"], "English")
        meetings[case["meeting"]] += m["errors"]
        rows.append({k: m[k] for k in ("errors", "referenceUnits", "deletions", "substitutions", "insertions")})
        rows[-1].update(id=out["id"], seconds=out["seconds"], audioSeconds=out["audioSeconds"])
    assert sum(row["referenceUnits"] for row in rows) == 709
    errors = sum(row["errors"] for row in rows)
    report = {"at": now(), "errors": errors, "referenceWords": 709, "wer": errors/709,
              "meetings": meetings, "cases": rows,
              "screenPassed": errors <= 70 and meetings["ES2003b"] <= 46 and meetings["EN2001a"] <= 67,
              "rtf": sum(row["seconds"] for row in rows)/sum(row["audioSeconds"] for row in rows),
              "privatePeakBytes": state["limits"]["jobPeakPrivateCommitBytes"],
              "trainingUpdates": 0, "qualityQualified": False, "saleQualified": False}
    atomic_json(OUT / "score.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run()
    else:
        assert sys.argv[1] == "score"
        scoring_limits = WorkerLimits(cpu_percent=5, memory_bytes=256 * 1024**2)
        score()
