"""Download and verify one official CPU candidate using the working model mirror."""

from datetime import datetime
from hashlib import file_digest
import json
from pathlib import Path
from shutil import disk_usage
import subprocess
import sys
import time

import psutil

SRC = Path("C:/Users/Billy/Desktop/Denzic/Companion/model-research/src")
sys.path.insert(0, str(SRC))
from durable_model_state_20261117 import atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure, WorkerLimits

CACHE = Path("E:/CodexData/Companion/.model-cache/granite-speech-5.0-q4-r1")
META = Path("work/granite-5-gguf-publisher-meta-20261118.json")
NAMES = ("granite-speech-5.0-2b-Q4_K_M.gguf", "mmproj-model-f16.gguf")
REPO = "ibm-granite/granite-speech-5.0-2b-GGUF"
REV = "945b4581e2b40cd9a3121de265fd8e387bdf782d"

meta = json.loads(META.read_text(encoding="utf-8"))
assert meta["id"] == REPO and meta["sha"] == REV and not meta["gated"]
assert meta["cardData"]["license"] == "apache-2.0"
entries = {x["rfilename"]: x for x in meta["siblings"]}
needed = sum(entries[name]["size"] for name in NAMES)
CACHE.mkdir(exist_ok=True)
assert disk_usage(CACHE).free > needed + 30 * 1024**3
limits = WorkerLimits(cpu_percent=5, memory_bytes=384 * 1024**2)
pressure = SystemRamPressure()
result = {"repository": REPO, "revision": REV, "expectedBytes": needed, "assets": []}
begin = time.monotonic()


def save(state, **fields):
    result.update(fields, state=state, observedAt=datetime.now().astimezone().isoformat(timespec="seconds"))
    atomic_json(CACHE / "acquisition-state.json", result, progress=True)


try:
    for name in NAMES:
        file = CACHE / name
        part = file.with_suffix(".part")
        asset = entries[name]
        if not file.exists():
            assert not pressure.low() and psutil.virtual_memory().available > 3414499000
            assert not part.exists()
            url = f"https://hf-mirror.com/{REPO}/resolve/{REV}/{name}"
            save("DOWNLOADING", activeFile=name, receivedBytes=0, activeFileBytes=asset["size"])
            child = subprocess.Popen(
                ["curl.exe", "--noproxy", "*", "-fLsS", "--connect-timeout", "18",
                 "--speed-time", "25", "--speed-limit", "102400", "--max-time", "480",
                 "--max-filesize", str(asset["size"]), "-o", str(part), url],
                stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                while child.poll() is None:
                    assert not pressure.low() and psutil.virtual_memory().available > 3414499000
                    assert time.monotonic() - begin < 560
                    save("DOWNLOADING", receivedBytes=part.stat().st_size if part.exists() else 0)
                    time.sleep(2)
                assert child.returncode == 0, f"curl exit {child.returncode} for {name}"
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=5)
        candidate = file if file.exists() else part
        assert candidate.stat().st_size == asset["size"]
        with candidate.open("rb") as stream:
            assert stream.read(4) == b"GGUF"
            stream.seek(0)
            digest = file_digest(stream, "sha256").hexdigest()
        assert digest == asset["lfs"]["sha256"]
        if candidate == part:
            part.replace(file)
        result["assets"].append({"name": name, "bytes": asset["size"], "sha256": digest})
    save("READY_PINNED_GGUF_ASSETS", activeFile=None)
except BaseException as error:
    save("FAILED_GGUF_ACQUISITION_RETAINED", error=repr(error))
    raise
finally:
    pressure.close()
print(json.dumps(result), flush=True)
