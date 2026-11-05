"""Exercise the shared decoder and Java bridge on this host; not Android acceptance."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--workdir", required=True, type=Path)
args = parser.parse_args()
work = args.workdir.resolve()
work.mkdir(parents=True, exist_ok=True)
backend = Path(__file__).resolve().parent
env = os.environ.copy()
env.update(CARGO_TARGET_DIR=str(work / "target"), CARGO_INCREMENTAL="0", TEMP=str(work), TMP=str(work))
manifest = str(backend / "native/Cargo.toml")
subprocess.run(["cargo", "test", "--offline", "--manifest-path", manifest, "mobile_tests"], env=env, check=True)
subprocess.run(["cargo", "build", "--offline", "--manifest-path", manifest], env=env, check=True)
with tempfile.TemporaryDirectory(prefix="companion-jni-", dir=work) as tmp:
    tmp = Path(tmp)
    source = backend / "src/main/java/com/denzic/companion/mobile"
    test = backend / "src/test/java/com/denzic/companion/mobile/NativeAudioJvmTest.java"
    files = [source / (name + ".java") for name in (
        "RecorderWire", "SegmentReceiver", "RecordingLibrary", "NativeAudio", "DecodedAudioParts", "DeviceBookmarkCache",
        "MeetingStore", "RecordingClient", "DurableConsume", "NativeRecordingControl", "NativeLocalTranscription", "NativeTranscription")]
    # The host fixture injects its own directory-sync function. It must never
    # mistake a desktop stub for Android's real durable directory sync.
    stub = tmp / "AndroidDirectorySync.java"
    stub.write_text("package com.denzic.companion.mobile; final class AndroidDirectorySync { "
                    "static void sync(java.nio.file.Path p) throws java.io.IOException { "
                    "throw new java.io.IOException(\"Android directory sync unavailable in host test\"); }}", encoding="utf8")
    subprocess.run(["javac", "--release", "8", "-encoding", "UTF-8", "-d", str(tmp)] + list(map(str, files)) + [str(stub), str(test)], check=True)
    subprocess.run(["java", "-Djava.library.path=" + str(work / "target/debug"), "-cp", str(tmp),
                    "com.denzic.companion.mobile.NativeAudioJvmTest", str(tmp)], env=env, check=True)
