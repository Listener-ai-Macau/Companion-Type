"""Create an AAR candidate for integration testing; this does not run Gradle or a phone."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--android-jar", required=True, type=Path)
parser.add_argument("--jni-libs", required=True, type=Path)
parser.add_argument("--workdir", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
backend = Path(__file__).resolve().parent
args.workdir.mkdir(parents=True, exist_ok=True)
args.output.parent.mkdir(parents=True, exist_ok=True)
libraries = sorted(args.jni_libs.glob("*/libcompanion_mobile_audio.so"))
if not libraries:
    raise SystemExit("No ABI-matched native library supplied")
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
    with args.output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr("AndroidManifest.xml", manifest)
        out.writestr("R.txt", "")
        out.write(backend / "consumer-rules.pro", "proguard.txt")
        out.write(jar, "classes.jar")
        for lib in libraries:
            out.write(lib, "jni/" + lib.parent.name + "/" + lib.name)
print("ANDROID_AAR_CANDIDATE", args.output)
