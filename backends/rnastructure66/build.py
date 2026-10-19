#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build a pinned standalone original or repaired engine in a new directory, without root."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import tarfile


COMPONENT = Path(__file__).resolve().parent
ORIGINAL_COMPONENT = "rnastructure-6.6-original"
DEFAULT_COMPONENT = "rnastructure-6.6-traceback-2"
MANIFESTS = {
    ORIGINAL_COMPONENT: "manifest-original.json",
    DEFAULT_COMPONENT: "manifest.json",
    "rnastructure-6.6-linker-3": "manifest-linker-3.json",
}


def sha256(path):
    """Return a file's SHA-256 identity."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_hash(path, expected):
    if sha256(path) != expected:
        raise ValueError(f"SHA-256 mismatch: {path}")


def load_manifest(component=DEFAULT_COMPONENT):
    """Return the pinned manifest of one named component."""
    if component not in MANIFESTS:
        raise ValueError(f"Unknown component: {component}")
    manifest = json.loads((COMPONENT / MANIFESTS[component]).read_text())
    if not isinstance(manifest, dict) or manifest.get("component") != component:
        raise ValueError(f"Manifest component mismatch: {MANIFESTS[component]}")
    allowed = {"schema_version", "component", "license", "upstream", "patch", "provenance"}
    if component != ORIGINAL_COMPONENT:
        allowed.add("predecessor")
    if set(manifest) - allowed:
        raise ValueError("Unexpected manifest fields")
    patch = manifest.get("patch")
    if manifest.get("schema_version") != 1 or manifest.get("license") != "GPL-2.0-only":
        raise ValueError("Unsupported manifest schema or license")
    if component == ORIGINAL_COMPONENT:
        if "patch" not in manifest or patch is not None:
            raise ValueError("Original manifest must declare patch: null and no predecessor")
    elif (
        not isinstance(patch, dict)
        or set(patch) != {"file", "sha256", "patched_source_sha256"}
        or any(not isinstance(value, str) or not value for value in patch.values())
    ):
        raise ValueError("Repaired manifest requires a patch and patched-source identity")
    upstream = manifest.get("upstream")
    if (
        not isinstance(upstream, dict)
        or set(upstream) != {
            "version", "url", "archive_sha256", "archive_bytes", "source_file", "source_sha256"
        }
        or upstream.get("version") != "6.6"
        or upstream.get("source_file") != "src/algorithm.cpp"
        or not isinstance(upstream.get("archive_bytes"), int)
        or upstream["archive_bytes"] <= 0
    ):
        raise ValueError("Invalid upstream manifest metadata")
    return manifest


def install(archive, destination, jobs=2, optimize=True, component=DEFAULT_COMPONENT):
    """Verify inputs, extract pristine source, optionally patch, then compile tools.

    Existing destinations are refused, including partial builds. A failed build
    is retained for diagnosis; retry into another new directory. The component
    selects a pinned cumulative patch or explicitly unmodified original source.
    """
    if jobs not in (1, 2):
        raise ValueError("jobs must be 1 or 2")
    manifest = load_manifest(component)
    archive = Path(archive).resolve(strict=True)
    destination = Path(destination).absolute()
    require_hash(archive, manifest["upstream"]["archive_sha256"])
    patch_info = manifest["patch"]
    patch = COMPONENT / patch_info["file"] if patch_info is not None else None
    if patch is not None:
        require_hash(patch, patch_info["sha256"])
    sdk = None
    compiler = "g++"
    if platform.system() == "Darwin":
        if shutil.which("xcode-select") is None:
            raise RuntimeError("macOS developer tools are absent. Install/select them separately.")
        # This probe fails without opening the macOS developer-tools dialog.
        selected = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True)
        if selected.returncode:
            raise RuntimeError(
                "macOS developer tools are absent. Install/select the Command Line "
                "Tools separately, then retry into a new destination; this builder "
                "does not request installation or permissions."
            )
        if shutil.which("xcrun") is None:
            raise RuntimeError("Missing xcrun; install/select the macOS SDK separately.")
        sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
        if not sdk:
            raise RuntimeError("No macOS SDK selected; install/select developer tools separately.")
        compiler = "clang++"
    prerequisites = [compiler, "make", "file"]
    if patch is not None:
        prerequisites.append("patch")
    for tool in prerequisites:
        if shutil.which(tool) is None:
            raise RuntimeError(f"Missing prerequisite {tool}; install it separately before retrying.")
    compiler_version = subprocess.check_output([compiler, "--version"], text=True).strip()
    # The pinned archive contains only directories and regular files. Validate
    # that property before creating anything, rather than following archive links.
    with tarfile.open(archive) as source:
        members = source.getmembers()
        for member in members:
            path = PurePosixPath(member.name)
            if (
                not path.parts
                or path.parts[0] != "RNAstructure"
                or ".." in path.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError(f"Unsafe archive member: {member.name}")
        destination.mkdir(parents=True, exist_ok=False)
        # data_filter is also backported to maintained Python 3.11 releases.
        # Earlier 3.11 uses the same explicit path/type allowlist above; the
        # new destination and rejection of every link prevent symlink traversal.
        extraction = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
        source.extractall(destination, members=members, **extraction)
    root = destination / "RNAstructure"
    source_file = root / manifest["upstream"]["source_file"]
    require_hash(source_file, manifest["upstream"]["source_sha256"])
    expected_source = manifest["upstream"]["source_sha256"]
    if patch is not None:
        # Zero fuzz plus the postimage hash prevents a patch on another revision.
        with patch.open("rb") as patch_input:
            subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1"],
                cwd=root,
                stdin=patch_input,
                check=True,
            )
        expected_source = patch_info["patched_source_sha256"]
        require_hash(source_file, expected_source)
    command = ["make", f"-j{jobs}", "Fold", "bifold", "efn2"]
    if not optimize:
        command.append("optimize=off")
    if sdk is not None:
        command.append(f"CXX=clang++ -isysroot {sdk} -isystem {sdk}/usr/include/c++/v1")
    # Do not inherit tuning, alternate platforms, parallelism or data-table
    # settings from an interactive shell. Explicit make arguments above govern.
    environment = os.environ.copy()
    for name in (
        "MAKEFLAGS", "GNUMAKEFLAGS", "MAKEFILES", "MFLAGS", "MAKEOVERRIDES",
        "RNA_MAKE_OS", "RNA_MAKE_ARCH", "RNA_INCLUDE_CUDA", "CUDA", "DATAPATH", "CXX", "CXXFLAGS", "CPP_FLAGS", "LDFLAGS", "LDLIBS",
    ):
        environment.pop(name, None)
    subprocess.run(command, cwd=root, env=environment, check=True)
    require_hash(source_file, expected_source)
    files = [root / "exe" / name for name in ("Fold", "bifold", "efn2")]
    tables = sorted((root / "data_tables").glob("*"))
    # Raw receipt bytes are pinned by existing evaluations. Keep repaired
    # identity fields in their original position, including serialization order.
    identity = {} if patch is None else {
        "patch_sha256": sha256(patch),
        "patched_source_sha256": sha256(source_file),
    }
    receipt = {
        "component": manifest["component"],
        "license": manifest["license"],
        "source_archive_sha256": sha256(archive),
        **identity,
        "build_command": command,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "compiler_version": compiler_version,
        "executable_architecture": {
            file.name: subprocess.check_output(["file", "-b", str(file)], text=True).strip()
            for file in files
        },
        "executable_sha256": {file.name: sha256(file) for file in files},
        "table_sha256": {file.name: sha256(file) for file in tables if file.is_file()},
    }
    receipt_name = "traceback-build.json"
    if patch is None:
        receipt_name = "original-build.json"
        receipt.update({
            "patch_applied": False,
            "patch_sha256": None,
            "source_file": manifest["upstream"]["source_file"],
            "source_sha256": sha256(source_file),
            "source_archive_bytes": archive.stat().st_size,
        })
    (root / receipt_name).write_text(json.dumps(receipt, indent=2) + "\n")
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=2)
    parser.add_argument("--no-optimize", action="store_true")
    parser.add_argument("--component", choices=sorted(MANIFESTS), default=DEFAULT_COMPONENT)
    args = parser.parse_args()
    try:
        root = install(args.archive, args.destination, args.jobs, not args.no_optimize, args.component)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, tarfile.TarError) as error:
        parser.exit(1, f"Build failed: {error}\nFailed build directories are retained; use a new destination.\n")
    print(root)


if __name__ == "__main__":
    main()
