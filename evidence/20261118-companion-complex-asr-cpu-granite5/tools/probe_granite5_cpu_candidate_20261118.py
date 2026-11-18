"""One bounded native CPU screen using original fixed public meeting inputs."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event
import time
import urllib.error
import urllib.request
from uuid import uuid4
import wave

import psutil

R = Path("C:/Users/Billy/Desktop/Denzic/Companion")
sys.path.insert(0, str(R / "model-research/src"))
from companion_local_pcm_session_20261114 import SessionConflict, exclusive_file
from durable_model_state_20261117 import atomic_json
from meeting_acoustic_worker_20261116 import own_limits
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure

BASE = Path("E:/CodexData/Companion")
ASSETS = BASE / ".model-cache/granite-speech-5.0-q4-r1"
CONTROL = BASE / (
    "product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/"
    "english-accuracy-reference-20261117"
)
OLD = CONTROL / "moonshine-english-medium-reference-protocol-r2.json"
OUT = CONTROL / "granite5-q4-native-cpu-r2"
SCORER_BINDING = R / (
    "docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/"
    "joint-architecture-r1/english-transducer-r1/scoring-control.json"
)
RUNTIME = BASE / (
    "real-acoustic20261115/vcsum125/overnight-content-closure20261116/"
    "native-local-minutes20261118/customer-runtime-staging-r1"
)
PROMPT = "transcribe the speech with proper punctuation and capitalization."
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def prepare(protocol):
    downloaded = read(ASSETS / "acquisition-state.json")
    assert downloaded["state"] == "READY_PINNED_GGUF_ASSETS"
    assert len(downloaded["assets"]) == 2
    for asset in downloaded["assets"]:
        path = ASSETS / asset["name"]
        assert path.stat().st_size == asset["bytes"] and digest(path) == asset["sha256"]
    runtime = read(RUNTIME / "runtime-manifest.json")
    assert runtime["cpuOnly"] and (RUNTIME / "llama-server.exe").is_file()
    input_binding = read(SCORER_BINDING)
    ref = Path(protocol["originalReferences"])
    assert ref == Path(input_binding["references"])
    ref_hash = next(f["sha256"] for f in input_binding["files"] if Path(f["file"]) == ref)
    protocol.update(
        state="READY_NATIVE_GRANITE5_CPU_FIXED_ENGLISH_PROBE",
        originalReferences={"file": str(ref), "sha256": ref_hash},
        modelRevision=downloaded["revision"], weights=downloaded["assets"],
        runtimeManifestSha256=digest(RUNTIME / "runtime-manifest.json"),
        runtimeExeSha256=digest(RUNTIME / "llama-server.exe"),
        workerSha256=digest(__file__), prompt=PROMPT, cpuThreads=4,
        cpuLimitPercent=25, maximumSeconds=520, contextTokens=2048,
        route="/v1/audio/transcriptions", noGpu=True, repackCpuWeights=False,
    )
    OUT.mkdir(exist_ok=False)
    atomic_json(OUT / "protocol.json", protocol)
    print(json.dumps({"state": protocol["state"], "cases": len(protocol["cases"])}), flush=True)


def port_number():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def transcribe(url, path):
    boundary = uuid4().hex
    fields = {"model": "companion-granite5-r1", "prompt": PROMPT, "temperature": "0",
              "response_format": "json"}
    encoded_fields = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    header = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
              'Content-Type: audio/wav\r\n\r\n').encode()
    request = urllib.request.Request(
        url, b"".join(encoded_fields + [header, path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()]),
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with HTTP.open(request, timeout=95) as response:
        body = json.load(response)
    assert isinstance(body.get("text"), str)
    return body["text"]


def execute(protocol):
    assert not (OUT / "completed.json").exists() and digest(__file__) == protocol["workerSha256"]
    assert digest(RUNTIME / "runtime-manifest.json") == protocol["runtimeManifestSha256"]
    assert digest(RUNTIME / "llama-server.exe") == protocol["runtimeExeSha256"]
    runtime = read(RUNTIME / "runtime-manifest.json")
    for file in runtime["files"]:
        assert digest(RUNTIME / file["name"]) == file["sha256"]
    limits = own_limits(protocol["cpuLimitPercent"])
    pressure = SystemRamPressure()
    stopped = Event()
    monitor_result = {"minimumAvailableBytes": psutil.virtual_memory().available}
    state = {
        "state": "WAITING_FOR_SHARED_MODEL_LEASE", "at": now(), "completed": [],
        "trainingUpdates": 0, "referenceRead": False, "gpuInitialized": False,
        "protocolSha256": digest(OUT / "protocol.json"),
    }

    def save(state_name, **extra):
        state.update(state=state_name, observedAt=now(), **extra)
        atomic_json(OUT / "state.json", state, progress=True)

    def monitor(child, started):
        while child.poll() is None and not stopped.wait(0.5):
            available = psutil.virtual_memory().available
            monitor_result["minimumAvailableBytes"] = min(monitor_result["minimumAvailableBytes"], available)
            if pressure.low() or available < protocol["minimumAvailableBytes"]:
                monitor_result["stop"] = "LOW_MEMORY"
            elif time.monotonic() - started > protocol["maximumSeconds"]:
                monitor_result["stop"] = "TIME_LIMIT"
            if monitor_result.get("stop"):
                child.terminate()
                return

    save("WAITING_FOR_SHARED_MODEL_LEASE")
    try:
        with ExitStack() as resources:
            lease_deadline = time.monotonic() + protocol["maximumLeaseWaitSeconds"]
            while True:
                try:
                    resources.enter_context(exclusive_file(Path(protocol["neuralLock"])))
                    break
                except SessionConflict:
                    if time.monotonic() >= lease_deadline:
                        raise
                    time.sleep(2)
            assert not pressure.low() and psutil.virtual_memory().available >= protocol["minimumAvailableBytes"]
            port = port_number()
            base_url = f"http://127.0.0.1:{port}"
            args = [
                str(RUNTIME / "llama-server.exe"), "--model", str(ASSETS / protocol["weights"][0]["name"]),
                "--mmproj", str(ASSETS / protocol["weights"][1]["name"]),
                "--host", "127.0.0.1", "--port", str(port), "--device", "none", "--n-gpu-layers", "0",
                "--no-mmproj-offload", "--threads", str(protocol["cpuThreads"]),
                "--ctx-size", str(protocol["contextTokens"]), "--parallel", "1", "--fit", "off",
                "--alias", "companion-granite5-r1", "--temp", "0", "--top-k", "1",
                "--no-webui", "--no-warmup", "--no-context-shift", "--predict", "384", "--no-repack",
                "--verbosity", "4",
            ]
            env = {key: value for key, value in os.environ.items() if not key.startswith(("LLAMA_ARG_", "GGML_"))}
            env.update(OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="1", CUDA_VISIBLE_DEVICES="-1")
            started = time.monotonic()
            with (OUT / "native.log").open("xb") as log:
                child = subprocess.Popen(
                    args, cwd=RUNTIME, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
                )
                try:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pool.submit(monitor, child, started)
                        try:
                            save("LOADING_NATIVE_CPU", nativePid=child.pid)
                            startup = time.monotonic() + 90
                            while time.monotonic() < startup and child.poll() is None:
                                try:
                                    with HTTP.open(base_url + "/health", timeout=2) as response:
                                        if json.load(response).get("status") == "ok":
                                            break
                                except (OSError, urllib.error.URLError):
                                    time.sleep(0.4)
                            else:
                                raise RuntimeError(f"Native runtime did not become ready; exit={child.poll()}")
                            clip = Path(protocol["publisherControl"])
                            assert digest(clip) == protocol["publisherControlSha256"]
                            # Keep the reference-control call short without changing any scored PCM.
                            with wave.open(str(clip), "rb") as source, wave.open(str(OUT / "publisher-control.wav"), "wb") as short:
                                short.setparams(source.getparams())
                                short.writeframes(source.readframes(8 * source.getframerate()))
                            control_text = transcribe(base_url + protocol["route"], OUT / "publisher-control.wav")
                            assert "best of times" in control_text.lower()
                            state["publisherControlPassed"] = True
                            for case in protocol["cases"]:
                                wav = Path(case["audio"])
                                assert digest(wav) == case["audioSha256"]
                                with wave.open(str(wav), "rb") as audio:
                                    assert (audio.getnchannels(), audio.getframerate(), audio.getsampwidth(), audio.getnframes()) == (1, 16000, 2, case["frames"])
                                    assert sha256(audio.readframes(audio.getnframes())).hexdigest() == case["pcmSha256"]
                                save("DECODING_FIXED_CLIP", activeCase=case["id"])
                                began = time.monotonic()
                                text = transcribe(base_url + protocol["route"], wav)
                                packet = OUT / (case["id"] + ".json")
                                atomic_json(packet, {
                                    "id": case["id"], "text": text, "pcmSha256": case["pcmSha256"],
                                    "seconds": time.monotonic() - began, "audioSeconds": case["frames"] / 16000,
                                })
                                state["completed"].append({"file": str(packet), "sha256": digest(packet)})
                            save("COMPLETE_NATIVE_GRANITE5_CPU", elapsedSeconds=time.monotonic() - started)
                        finally:
                            stopped.set()
                finally:
                    if child.poll() is None:
                        child.terminate()
                    child.wait(timeout=8)
    except BaseException as error:
        save("GRANITE5_CPU_PROBE_FAILED_RETAINED", error=repr(error))
        raise
    finally:
        pressure.close()
        state["resourceMonitor"] = monitor_result
        state["limits"] = limits.query()
        atomic_json(OUT / "completed.json", state)


def score(protocol):
    from score_sequential_meetings_20261115 import measure

    state = read(OUT / "completed.json")
    assert state["state"] == "COMPLETE_NATIVE_GRANITE5_CPU" and state["publisherControlPassed"]
    assert state["protocolSha256"] == digest(OUT / "protocol.json")
    binding = protocol["originalReferences"]
    assert digest(binding["file"]) == binding["sha256"]
    cases = {c["id"]: c for c in read(binding["file"])}
    meetings = defaultdict(int)
    rows = []
    for row in state["completed"]:
        assert digest(row["file"]) == row["sha256"]
        result = read(row["file"])
        case = cases[result["id"]]
        assert case["pcmSha256"] == result["pcmSha256"] and case["language"] == "English"
        raw = measure(case["rawReferenceText"], result["text"], "English")
        meetings[case["meeting"]] += raw["errors"]
        rows.append({**{key: raw[key] for key in ("errors", "referenceUnits", "deletions", "substitutions", "insertions")},
                     "id": case["id"], "audioSeconds": result["audioSeconds"], "seconds": result["seconds"]})
    assert len(rows) == 12 and sum(row["referenceUnits"] for row in rows) == 709
    errors = sum(row["errors"] for row in rows)
    gate = protocol["unchangedScreen"]
    report = {
        "at": now(), "errors": errors, "referenceWords": 709, "wer": errors / 709,
        "meetings": meetings, "cases": rows,
        "rtf": sum(r["seconds"] for r in rows) / sum(r["audioSeconds"] for r in rows),
        "privatePeakBytes": state["limits"]["jobPeakPrivateCommitBytes"],
        "screenPassed": (errors <= gate["maximumErrors"] and
                         all(meetings[m] <= n for m, n in gate["maximumPerMeeting"].items())),
        "trainingUpdates": 0, "qualityQualified": False, "saleQualified": False,
    }
    atomic_json(OUT / "score.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "execute", "score"))
    stage = parser.parse_args().stage
    if stage == "execute":
        execute(read(OUT / "protocol.json"))
    else:
        admission = WorkerLimits(cpu_percent=5, memory_bytes=256 * 1024**2)
        if stage == "prepare":
            prepare(read(OLD))
        else:
            score(read(OUT / "protocol.json"))
