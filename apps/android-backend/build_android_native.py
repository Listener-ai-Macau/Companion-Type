"""Build the Android decoder for one ABI using an installed, verified NDK."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--ndk", required=True, type=Path)
parser.add_argument("--workdir", required=True, type=Path)
parser.add_argument("--target-dir", type=Path, help="reuse an existing Cargo target directory")
parser.add_argument("--abi", choices=("arm64-v8a", "x86_64"), default="arm64-v8a")
args = parser.parse_args()
backend = Path(__file__).resolve().parent
work = args.workdir.resolve()
target = args.target_dir.resolve() if args.target_dir else work / "target"
bin_dir = args.ndk.resolve() / "toolchains/llvm/prebuilt/windows-x86_64/bin"
triple = {"arm64-v8a": "aarch64-linux-android", "x86_64": "x86_64-linux-android"}[args.abi]
clang = bin_dir / (triple + "26-clang.cmd")
ar = bin_dir / "llvm-ar.exe"
if not clang.is_file() or not ar.is_file():
    raise SystemExit("A complete Android NDK for Windows is required")
installed = subprocess.check_output(["rustup", "target", "list", "--installed"], text=True).splitlines()
if triple not in installed:
    raise SystemExit("Install the Rust target " + triple + " before building")
work.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(CARGO_TARGET_DIR=str(target), CARGO_INCREMENTAL="0", TEMP=str(work), TMP=str(work))
name = triple.replace("-", "_")
env["CC_" + name] = str(clang)
env["AR_" + name] = str(ar)
env["CARGO_TARGET_" + name.upper() + "_LINKER"] = str(clang)
subprocess.run(["cargo", "build", "--offline", "--locked", "--release", "--features", "mobile-asr,mobile-calendar,mobile-control", "--target", triple,
                "--manifest-path", str(backend / "native/Cargo.toml")], env=env, check=True)
source = target / triple / "release/libcompanion_mobile_audio.so"
destination = work / "jniLibs" / args.abi / source.name
destination.parent.mkdir(parents=True, exist_ok=True)
with source.open("rb") as src, destination.open("xb") as dst:
    shutil.copyfileobj(src, dst)
print("ANDROID_NATIVE_LIBRARY", destination)
