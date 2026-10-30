"""Run synthetic V2 tests without a phone. Supply an external work directory."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--workdir", required=True, type=Path)
parser.add_argument("--saved-synthetic-wire", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
backend = Path(__file__).resolve().parent
args.workdir.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="companion-wire-", dir=args.workdir) as tmp:
    tmp = Path(tmp)
    golden = json.loads((root / "apps/windows/src-tauri/src/backend/recording_wire/golden.json").read_text(encoding="utf-8"))
    for name, data in [("descriptor0.bin", golden["descriptorsHex"][0]),
                       ("page0.bin", golden["pagesHex"][0]), ("page1.bin", golden["pagesHex"][1]),
                       ("payload.bin", golden["payloadHex"])]:
        (tmp / name).write_bytes(bytes.fromhex(data))
    source = backend / "src/main/java/com/denzic/companion/mobile"
    test = backend / "src/test/java/com/denzic/companion/mobile"
    files = [source / (name + ".java") for name in ("RecorderWire", "SegmentReceiver", "RecordingLibrary", "RecordingClient")]
    files += [test / "RecorderWireTest.java", test / "SavedSyntheticWireReplay.java"]
    subprocess.run(["javac", "--release", "8", "-d", str(tmp)] + list(map(str, files)), check=True)
    subprocess.run(["java", "-cp", str(tmp), "com.denzic.companion.mobile.RecorderWireTest", str(tmp)], check=True)
    if args.saved_synthetic_wire:
        subprocess.run(["java", "-cp", str(tmp), "com.denzic.companion.mobile.SavedSyntheticWireReplay", str(args.saved_synthetic_wire)], check=True)
