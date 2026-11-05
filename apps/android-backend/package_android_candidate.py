"""Create an AAR candidate for integration testing; this does not run Gradle or a phone."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--android-jar", required=True, type=Path)
parser.add_argument("--jni-libs", required=True, type=Path)
parser.add_argument("--workdir", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
parser.add_argument("--external-asr-runtime", action="store_true", help="Host app supplies the matching ASR runtime libraries itself")
args = parser.parse_args()
backend = Path(__file__).resolve().parent
args.workdir.mkdir(parents=True, exist_ok=True)
args.output.parent.mkdir(parents=True, exist_ok=True)
libraries = sorted(args.jni_libs.glob("*/libcompanion_mobile_audio.so"))
if not libraries:
    raise SystemExit("No ABI-matched native library supplied")
if any(lib.parent.name == "arm64-v8a" for lib in libraries):
    # Attribution was missing for the bridge's bundled Opus and Rust inputs.
    # Keep the packaged notice tied to the actual checked-in build inputs.
    from verify_android_native_notices import verify
    try:
        verify(backend.parents[1])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Android ARM64 third-party notices need updating: {error}") from error
if not args.external_asr_runtime:
    # The local-ASR API loads these by name from the host APK. A package with
    # only our JNI bridge compiles successfully but cannot transcribe on phone.
    pinned = {
        "libonnxruntime.so": "4d2318b3849abb8862133d3068fc7e807ed8b2671cc6d83657fff2fcb9e1caad",
        "libsherpa-onnx-c-api.so": "c9d2277b02366fd467ca6f0cde2fc16f8efb69b2fb80cf51e8e3fee0c9f12278",
    }
    companions = list(libraries)
    for bridge in companions:
        if bridge.parent.name != "arm64-v8a":
            raise SystemExit("Bundled ASR runtime is available for arm64-v8a; use --external-asr-runtime for other host-managed ABIs")
        for name, expected in pinned.items():
            runtime = bridge.parent / name
            if not runtime.is_file() or hashlib.sha256(runtime.read_bytes()).hexdigest() != expected:
                raise SystemExit(f"Missing or mismatched pinned Android ASR runtime: {runtime}")
            libraries.append(runtime)
manifest = (backend / "src/main/AndroidManifest.xml").read_text(encoding="utf-8")
if '<manifest xmlns:android=' not in manifest:
    raise SystemExit("Unexpected Android manifest")
manifest = manifest.replace('<manifest xmlns:android=', '<manifest package="com.denzic.companion.mobile" xmlns:android=', 1)
with tempfile.TemporaryDirectory(prefix="companion-aar-", dir=args.workdir) as tmp:
    tmp = Path(tmp)
    classes = tmp / "classes"
    classes.mkdir()
    java = sorted((backend / "src/main/java").rglob("*.java"))
    subprocess.run(["javac", "--release", "8", "-classpath", str(args.android_jar), "-d", str(classes)] + list(map(str, java)), check=True)
    jar = tmp / "classes.jar"
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as out:
        for file in sorted(classes.rglob("*.class")):
            out.write(file, file.relative_to(classes).as_posix())
        resources = backend / "src/main/resources"
        if resources.is_dir():
            for file in sorted(resources.rglob("*")):
                if file.is_file() and not file.name.startswith("."):
                    out.write(file, file.relative_to(resources).as_posix())
    with args.output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr("AndroidManifest.xml", manifest)
        out.writestr("R.txt", "")
        out.write(backend / "consumer-rules.pro", "proguard.txt")
        out.write(jar, "classes.jar")
        assets = backend / "src/main/assets"
        if assets.is_dir():
            for file in sorted(assets.rglob("*")):
                if file.is_file():
                    out.write(file, "assets/" + file.relative_to(assets).as_posix())
        for lib in libraries:
            out.write(lib, "jni/" + lib.parent.name + "/" + lib.name)
print("ANDROID_AAR_CANDIDATE", args.output)
