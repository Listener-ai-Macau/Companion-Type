"""Stage or verify the pinned CPU runtime, its transitive CRT and licenses.

Developer staging requires explicit existing SDK/REDIST directories. Verification
does not download, execute the engine, install software or copy model weights.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, shutil

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "apps/windows/src-tauri/src/backend/minutes/local/local-runtime-manifest.json"
DEFAULT_OUTPUT = ROOT / "apps/windows/src-tauri/resources/local-minutes"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(root, name):
    relative = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid runtime relative path: " + name)
    root = root.resolve()
    result = root.joinpath(*relative.parts).resolve()
    if not result.is_relative_to(root):
        raise ValueError("Runtime path leaves its explicit root: " + name)
    return result


def checked(path, row):
    if not path.is_file() or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
        raise ValueError("Missing or unverified local runtime input: " + str(path))


def inventory(data):
    return {
        "source": data["source"],
        "sourceArchiveSha256": data["sourceArchiveSha256"],
        "additionalSources": data["additionalSources"],
        "licenses": data["licenses"],
    }


def validate_manifest(data):
    if not data["cpuOnly"] or len(data["files"]) != 12:
        raise ValueError("Expected the pinned CPU SDK and four REDIST dependencies")
    paths = [row["name"] for row in data["files"]] + [row["path"] for row in data["licenses"]]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate runtime or license path")
    if any(row["origin"] not in {"sdk", "msvc"} for row in data["files"]) or any(row["origin"] not in {"sdk", "bundled"} for row in data["licenses"]):
        raise ValueError("Unknown runtime or license origin")
    for name in paths:
        inside(DEFAULT_OUTPUT, name)
    if {row["name"] for row in data["files"] if row["origin"] == "msvc"} != {
        "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "vcomp140.dll"
    }:
        raise ValueError("Incomplete MSVC runtime dependency closure")
    required = {"licenses/LICENSE", "licenses/microsoft/license-en.rtf", "licenses/microsoft/license-zh-CN.rtf", "licenses/qwen/LICENSE"}
    if not required.issubset({row["path"] for row in data["licenses"]}):
        raise ValueError("Required upstream license text absent")


def verify(output, data):
    for row in data["files"]:
        checked(inside(output, row["name"]), row)
    for row in data["licenses"]:
        checked(inside(output, row["path"]), row)
    if inside(output, "runtime-manifest.json").read_bytes() != MANIFEST.read_bytes():
        raise ValueError("Staged runtime manifest differs from the compiled input")
    if json.loads(inside(output, "license-inventory.json").read_bytes()) != inventory(data):
        raise ValueError("Staged license inventory differs from the pinned input")
    expected = {row["name"] for row in data["files"]} | {row["path"] for row in data["licenses"]} | {"runtime-manifest.json", "license-inventory.json", ".gitignore"}
    unexpected = sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file() and path.relative_to(output).as_posix() not in expected)
    if unexpected:
        raise ValueError("Unlisted files would enter the customer runtime bundle: " + ", ".join(unexpected))
    return {
        "state": "PINNED_CUSTOMER_CPU_RUNTIME_VERIFIED_CONTENT_GATE_UNCHANGED",
        "directory": str(output.resolve()), "files": len(data["files"]),
        "licenseTexts": len(data["licenses"]),
        "bytes": sum(row["bytes"] for row in data["files"] + data["licenses"]),
        "manifestSha256": sha(MANIFEST), "modelWeightsBundled": False,
        "engineExecuted": False, "newNeuralCalls": 0, "contentQualified": False,
        "installed": False,
    }


def copy_checked(source, target, row):
    if target.is_file() and target.stat().st_size == row["bytes"] and sha(target) == row["sha256"]:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".stage.tmp")
    shutil.copyfile(source, temporary)
    checked(temporary, row)
    os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-bin", type=Path)
    parser.add_argument("--sdk-source", type=Path)
    parser.add_argument("--vc-redist-root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    data = json.loads(MANIFEST.read_bytes())
    validate_manifest(data)
    if args.verify:
        if any([args.runtime_bin, args.sdk_source, args.vc_redist_root]):
            parser.error("--verify takes no staging input directories")
    else:
        if not all([args.runtime_bin, args.sdk_source, args.vc_redist_root]):
            parser.error("Staging requires --runtime-bin, --sdk-source and --vc-redist-root")
        pending = []
        for row in data["files"]:
            base = args.runtime_bin if row["origin"] == "sdk" else args.vc_redist_root
            pending.append((inside(base, row["sourceRelativePath"]), inside(args.output_dir, row["name"]), row))
        for row in data["licenses"]:
            base = args.sdk_source if row["origin"] == "sdk" else DEFAULT_OUTPUT
            pending.append((inside(base, row["sourceRelativePath"]), inside(args.output_dir, row["path"]), row))
        # Reject the whole source set before changing the staged runtime.
        for source, _, row in pending:
            checked(source, row)
        for source, target, row in pending:
            copy_checked(source, target, row)
        (args.output_dir / "runtime-manifest.json").write_bytes(MANIFEST.read_bytes())
        (args.output_dir / "license-inventory.json").write_bytes((json.dumps(inventory(data), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(verify(args.output_dir, data), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit("Local minutes runtime preflight failed: " + str(error))
