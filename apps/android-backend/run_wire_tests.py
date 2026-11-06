"""Run synthetic V2 tests without a phone. Supply an external work directory."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--workdir", required=True, type=Path)
parser.add_argument("--saved-synthetic-wire", type=Path)
parser.add_argument("--retain-fixture", action="store_true", help="Keep exact host fixtures and results; no Windows temporary cleanup")
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
backend = Path(__file__).resolve().parent
args.workdir.mkdir(parents=True, exist_ok=True)
fixture = (nullcontext(tempfile.mkdtemp(prefix="companion-wire-", dir=args.workdir))
           if args.retain_fixture else tempfile.TemporaryDirectory(prefix="companion-wire-", dir=args.workdir))
with fixture as tmp:
    tmp = Path(tmp)
    golden = json.loads((root / "apps/windows/src-tauri/src/backend/recording_wire/golden.json").read_text(encoding="utf-8"))
    for name, data in [("descriptor0.bin", golden["descriptorsHex"][0]),
                       ("page0.bin", golden["pagesHex"][0]), ("page1.bin", golden["pagesHex"][1]),
                       ("payload.bin", golden["payloadHex"])]:
        (tmp / name).write_bytes(bytes.fromhex(data))
    source = backend / "src/main/java/com/denzic/companion/mobile"
    test = backend / "src/test/java/com/denzic/companion/mobile"
    files = [source / (name + ".java") for name in ("RecorderWire", "DeviceRecordings", "DeviceMaintenance", "SegmentReceiver", "RecordingLibrary", "RecordingClient", "NativeRecordingControl", "DurableConsume", "MeetingStore", "NativeAudio", "DecodedAudioParts", "DeviceBookmarkCache", "RecordingSyncRunner")]
    files += [source / "InitialConnectionRetry.java", source / "RecordingTransferMetrics.java", test / "InitialConnectionRetryTest.java", test / "RecorderWireTest.java", test / "SavedSyntheticWireReplay.java", test / "MeetingStoreTest.java"]
    stub = tmp / "AndroidDirectorySync.java"
    stub.write_text("package com.denzic.companion.mobile; final class AndroidDirectorySync { "
                    "static void sync(java.nio.file.Path p) throws java.io.IOException { "
                    "throw new java.io.IOException(\"Android directory sync unavailable in host test\"); }}", encoding="utf8")
    subprocess.run(["javac", "--release", "8", "-encoding", "UTF-8", "-d", str(tmp)] + list(map(str, files)) + [str(stub)], check=True)
    subprocess.run(["java", "-cp", str(tmp), "com.denzic.companion.mobile.RecorderWireTest", str(tmp)], check=True)
    subprocess.run(["java", "-cp", str(tmp), "com.denzic.companion.mobile.InitialConnectionRetryTest"], check=True)
    subprocess.run(["java", "-cp", str(tmp), "com.denzic.companion.mobile.MeetingStoreTest", str(tmp)], check=True)
    if args.saved_synthetic_wire:
        subprocess.run(["java", "-cp", str(tmp), "com.denzic.companion.mobile.SavedSyntheticWireReplay", str(args.saved_synthetic_wire)], check=True)
