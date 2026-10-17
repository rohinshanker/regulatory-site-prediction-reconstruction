#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the pinned, patched standalone engine in a new directory, without root."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import tarfile


COMPONENT = Path(__file__).resolve().parent


def sha256(path):
    """Return a file's SHA-256 identity."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_hash(path, expected):
    if sha256(path) != expected:
        raise ValueError(f"SHA-256 mismatch: {path}")


def install(archive, destination, jobs=2, optimize=True):
    """Verify inputs, extract and patch pristine source, then compile serial tools.

    Existing destinations are refused, including partial builds. A failed build
    is retained for diagnosis; retry into another new directory.
    """
    if jobs not in (1, 2):
        raise ValueError("jobs must be 1 or 2")
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    archive = Path(archive).resolve(strict=True)
    destination = Path(destination).absolute()
    require_hash(archive, manifest["upstream"]["archive_sha256"])
    patch = COMPONENT / manifest["patch"]["file"]
    require_hash(patch, manifest["patch"]["sha256"])
    sdk = None
    compiler = "g++"
    if platform.system() == "Darwin":
        # This probe fails without opening the macOS developer-tools dialog.
        selected = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True)
        if selected.returncode:
            raise RuntimeError(
                "macOS developer tools are absent. Install/select the Command Line "
                "Tools separately, then retry into a new destination; this builder "
                "does not request installation or permissions."
            )
        sdk = subprocess.check_output(["xcrun", "--show-sdk-path"], text=True).strip()
        compiler = "clang++"
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
    # --fuzz=0 plus the postimage hash prevents a patch on another source revision.
    with patch.open("rb") as patch_input:
        subprocess.run(
            ["patch", "--batch", "--fuzz=0", "-p1"],
            cwd=root,
            stdin=patch_input,
            check=True,
        )
    require_hash(source_file, manifest["patch"]["patched_source_sha256"])
    command = ["make", f"-j{jobs}", "Fold", "bifold", "efn2"]
    if not optimize:
        command.append("optimize=off")
    if sdk is not None:
        command.append(f"CXX=clang++ -isysroot {sdk} -isystem {sdk}/usr/include/c++/v1")
    # Do not inherit tuning, alternate platforms, parallelism or data-table
    # settings from an interactive shell. Explicit make arguments above govern.
    environment = os.environ.copy()
    for name in (
        "MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "RNA_MAKE_OS", "RNA_MAKE_ARCH",
        "CUDA", "DATAPATH", "CXX", "CXXFLAGS", "CPP_FLAGS", "LDFLAGS", "LDLIBS",
    ):
        environment.pop(name, None)
    subprocess.run(command, cwd=root, env=environment, check=True)
    files = [root / "exe" / name for name in ("Fold", "bifold", "efn2")]
    tables = sorted((root / "data_tables").glob("*"))
    receipt = {
        "component": manifest["component"],
        "license": manifest["license"],
        "source_archive_sha256": sha256(archive),
        "patch_sha256": sha256(patch),
        "patched_source_sha256": sha256(source_file),
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
    (root / "traceback-build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=2)
    parser.add_argument("--no-optimize", action="store_true")
    args = parser.parse_args()
    print(install(args.archive, args.destination, args.jobs, not args.no_optimize))


if __name__ == "__main__":
    main()
