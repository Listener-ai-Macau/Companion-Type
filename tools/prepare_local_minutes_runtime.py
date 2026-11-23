"""Stage or verify the pinned local minutes runtimes and their licenses.

Developer staging uses existing SDK/REDIST directories and a local Vulkan archive.
Verification does not download, execute engines, install software or copy weights.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, shutil
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "apps/windows/src-tauri/src/backend/minutes/local/local-runtime-manifest.json"
VULKAN_MANIFEST = MANIFEST.with_name("local-vulkan-runtime-manifest.json")
DEFAULT_OUTPUT = ROOT / "apps/windows/src-tauri/resources/local-minutes"
VULKAN_CRT = {"msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"}


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


def vulkan_files(data, vulkan):
    # The driver supplies vulkan-1.dll. Carry the pinned app-local MSVC imports,
    # and reuse the CPU bundle's byte-identical llama.cpp notices.
    crt = [row for row in data["files"] if row["name"] in VULKAN_CRT]
    return vulkan["files"] + crt + [vulkan["openmpLicense"]]


def verify(output, data, vulkan):
    inputs = {row["name"]: row for row in data["files"]}
    inputs.update({row["path"]: row for row in data["licenses"]})
    if vulkan:
        inputs.update({"vulkan/" + row["name"]: row for row in vulkan_files(data, vulkan)})
    for name, row in inputs.items():
        checked(inside(output, name), row)
    if inside(output, "runtime-manifest.json").read_bytes() != MANIFEST.read_bytes():
        raise ValueError("Staged runtime manifest differs from the compiled input")
    if json.loads(inside(output, "license-inventory.json").read_bytes()) != inventory(data):
        raise ValueError("Staged license inventory differs from the pinned input")
    for name in ("runtime-manifest.json", "license-inventory.json"):
        path = inside(output, name)
        inputs[name] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    expected = inputs.keys() | {".gitignore"}
    unexpected = sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file() and path.relative_to(output).as_posix() not in expected)
    if unexpected:
        raise ValueError("Unlisted files would enter the customer runtime bundle: " + ", ".join(unexpected))
    return {
        "state": ("PINNED_CUSTOMER_CPU_VULKAN_RUNTIMES_VERIFIED_CONTENT_GATE_UNCHANGED"
                  if vulkan else "PINNED_CUSTOMER_CPU_RUNTIME_VERIFIED_CONTENT_GATE_UNCHANGED"),
        "directory": str(output.resolve()), "files": len(data["files"]),
        "licenseTexts": len(data["licenses"]),
        "bytes": sum(row["bytes"] for row in data["files"] + data["licenses"]),
        "manifestSha256": sha(MANIFEST), "modelWeightsBundled": False,
        "vulkan": ({"source": vulkan["source"], "sourceArchiveSha256": vulkan["sourceArchiveSha256"],
                    "manifestSha256": sha(VULKAN_MANIFEST), "engineFiles": len(vulkan["files"]),
                    "appLocalCrt": sorted(VULKAN_CRT), "driverDependency": "vulkan-1.dll"}
                   if vulkan else None),
        "expectedPayloadFiles": [
            {"path": "local-minutes/" + name, "bytes": row["bytes"], "sha256": row["sha256"]}
            for name, row in sorted(inputs.items())
        ],
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


def extract_vulkan(archive, temp, output, data, vulkan, vc_redist_root):
    if sha(archive) != vulkan["sourceArchiveSha256"]:
        raise ValueError("Vulkan archive differs from the pinned Windows x64 release: " + str(archive))
    pending = []
    with ZipFile(archive) as package:
        for row in vulkan["files"] + [vulkan["openmpLicense"]]:
            name = row["name"]
            staged = inside(temp, name)
            with package.open(name) as source, staged.open("xb") as target:
                shutil.copyfileobj(source, target)
            pending.append((staged, inside(output, "vulkan/" + name), row))
    for row in data["files"]:
        if row["name"] in VULKAN_CRT:
            source = inside(vc_redist_root, row["sourceRelativePath"])
            pending.append((source, inside(output, "vulkan/" + row["name"]), row))
    return pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-bin", type=Path)
    parser.add_argument("--sdk-source", type=Path)
    parser.add_argument("--vc-redist-root", type=Path)
    parser.add_argument("--vulkan-archive", type=Path, help="Pinned Windows x64 Vulkan release ZIP")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--require-vulkan", action="store_true", help="Require both engines for delivery")
    args = parser.parse_args()
    data = json.loads(MANIFEST.read_bytes())
    validate_manifest(data)
    has_vulkan = inside(args.output_dir, "vulkan").is_dir()
    if args.require_vulkan and not (has_vulkan or args.vulkan_archive):
        parser.error("Delivery requires the Vulkan runtime. Stage it with --vulkan-archive.")
    vulkan = json.loads(VULKAN_MANIFEST.read_bytes()) if (has_vulkan or args.vulkan_archive) else None
    if args.verify:
        if any([args.runtime_bin, args.sdk_source, args.vc_redist_root, args.vulkan_archive]):
            parser.error("--verify takes no staging inputs")
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
        with TemporaryDirectory(prefix="companion-vulkan-runtime-") as temporary:
            if args.vulkan_archive:
                pending.extend(extract_vulkan(
                    args.vulkan_archive, Path(temporary), args.output_dir, data, vulkan, args.vc_redist_root,
                ))
            # Reject the whole source set before changing the staged runtime.
            for source, _, row in pending:
                checked(source, row)
            for source, target, row in pending:
                copy_checked(source, target, row)
        (args.output_dir / "runtime-manifest.json").write_bytes(MANIFEST.read_bytes())
        (args.output_dir / "license-inventory.json").write_bytes((json.dumps(inventory(data), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(verify(args.output_dir, data, vulkan), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, BadZipFile) as error:
        raise SystemExit("Local minutes runtime preflight failed: " + str(error))
