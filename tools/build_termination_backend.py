#!/usr/bin/env python3
"""Build the pinned external engine offline, outside the Python distribution."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from regsite.termination_backend import (
    ARCHIVE_SHA256,
    BINARY_LIMIT,
    BUILD_FLAGS,
    NULL_PATCH_SHA256,
    PROFILE,
    PROTOTYPE_PATCH_SHA256,
    SOURCE,
    TABLE_SHA256,
    TerminationBackendError,
    _error,
    _execute,
    _manifest,
    _read_regular,
    _verify,
)

# Member identities are metadata only: no engine source/table is in this package.
MEMBERS = {
    "seq.cc": (
        21734,
        "e4191d4e3413225b3c094ab8cbf90a5f18f8b6147bf62d04b5006063dba72fc9",
    ),
    "distr.cc": (
        1796,
        "a4904dddd89540659aaf9163de5ed45f16d6f89c9138a2e44fc4356716af2bb6",
    ),
    "util.cc": (
        1380,
        "ac96c5a7d74b84375c1be6f5e0b481f8ff9b5c0b40f6fc97387e3a04333fc0af",
    ),
    "map-output.cc": (
        11307,
        "7625987cea806fa3ac275b75d106604daedc289206c42298481c203b3e1ac916",
    ),
    "gene-reader.cc": (
        4322,
        "24f9c7c4646e46d74c8c31ddedd01930dbbf95ad05966756349e1b07b2d72561",
    ),
    "search.cc": (
        26860,
        "99485a83b2c7aa27ab7bc9e5e81c0a7abd55b9c02f3bd873d4d1ba29ebe366ce",
    ),
    "conf.cc": (
        22919,
        "7d516630057b9a00d75d53cc68e4469a936bad74ef4947ce2c85a507177283c9",
    ),
    "ermolaeva-score.cc": (
        2561,
        "b510b6957d2b76de57b35ad78eec96143d4322ab4c8da932ce26d9ba1ac29cc1",
    ),
    "ermolaeva-oldconf.cc": (
        11391,
        "17754139153a74a8631e07c69867a4bec6a8cc2926ca0a30c7b848e05c3a2ec2",
    ),
    "analysis.cc": (
        12913,
        "c85f4f989cc94be0ca643734dd16d409d34835c1de155d00bf9706a5e7022e42",
    ),
    "anti.cc": (
        1837,
        "da0d46b687dc9c70ebfb91c426c576645bf9342de74ee5b6497ce7a59be8a77d",
    ),
    "transterm.cc": (
        10652,
        "e4d3012ed66c8ae997431a3be0cfd2a93c2a08262574aaa3a552e0a5dc13971a",
    ),
    "2ndscore.cc": (
        7315,
        "dabbde3411c4b33d02f8d2cc6050bdd55068401aa80ba0c697da8cfc2ab29f74",
    ),
    "analysis.h": (
        382,
        "d148da0cc74d9190571a4f7c97d3ba7d350e51e1dc3f494bbfa5337967ca293f",
    ),
    "conf.h": (
        2770,
        "55ff2f6b7c2a3fb87f29b2b4f3a516f57c3cc1a4e4b7ba149a18a8d23b15ec7d",
    ),
    "distr.h": (
        1989,
        "83f192627886cd18477606faf3835eafa197eb1193d67207c68e3808c13caf2a",
    ),
    "ermolaeva-score.h": (
        3127,
        "118cf5cf3e581e61d5d15714c9f19d31db489e845d469574b916351fdb936f88",
    ),
    "gene-reader.h": (
        1101,
        "aed58d1d784db0a450997087cd7e4819220136b41e2edf2dfd029cfc54d08446",
    ),
    "map-output.h": (
        405,
        "8b20f0969c73b5896e8f1739929b843d86c7a876f53784d2a8d5f7464ced5ce4",
    ),
    "search.h": (
        199,
        "52f25b356ade6f666286e402373c323811d159f4d3b8338d29dac18925d5b2c6",
    ),
    "seq.h": (8112, "f082110f14faf61de918b4a18884feb536e10fbef95691f6fcc22c145644a8a9"),
    "transterm.h": (
        374,
        "d7aad871e12bd7c5b322b2965449d2b7c26eca025b8f629964344356ab1aa426",
    ),
    "util.h": (479, "9f0efef911c924ce19cc44dd638e44412e8af7dcda4cb1cfa93ff8743fb77d9b"),
    "USAGE.txt": (
        15919,
        "277728b462800a2cbae32587382e360c9d72bc41ae07674001324c6343679b3d",
    ),
    "expterm.dat": (
        45788,
        "fce89a92ab487aaea5a54015e859e1fb5e31f4f9985c9df7831ee09a367db1fe",
    ),
    "LICENSE.txt": (
        18009,
        "204d8eff92f95aac4df6c8122bc1505f468f3a901e5a4cc08940e0ede1938994",
    ),
    "RELEASE-NOTES.txt": (
        617,
        "6da090a4dab80c1b9f677ef360e46a46cca40ea0e2728e051d27ecb7edd19ec1",
    ),
    "calibrate.sh": (
        3314,
        "5b403e6093ff781479079448e680a750642eb4c219b3f9de3c41e6f95917fe9a",
    ),
    "random_fasta.py": (
        1016,
        "b9e889df172566d592d83e0e722f41b701b0639451c2cbbc99742a3825f15c15",
    ),
    "make_expterm.py": (
        5627,
        "1b8512f78ff243613e99b384423e885edd21f9ce3b65a8afd8f578f770071785",
    ),
    "mfold_rna.sh": (
        277,
        "f530db9743a3c369dd7571994a99ea63cc753d2b99fcb41f4f058a0b8d0f272b",
    ),
    "Makefile": (
        2432,
        "7f2bc92d9a024da22e5c160558adf42608c524b27a592c469d17b09e1d32f247",
    ),
}
ARCHIVE_BYTES = 1827662
PATCH_BYTES = 1000
HEADER_RESULT = "bf40c7d715f3c2a6541dda8a1a48808c6b9baa6a690b1124f0d8ab8f1644b690"
SEQ_RESULT = "41aa581280e38186acc4938a5723cc4c7fc6d63a809881baee01ade9e807c21f"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract(raw: bytes, destination: Path) -> None:
    """Extract exactly the pinned text roster, never archive-supplied executables."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        root = "transterm_hp_v2.09/"
        expected = {root} | {
            root + name for name in (*MEMBERS, "transterm", "2ndscore")
        }
        names = [item.filename for item in infos]
        if len(names) != len(expected) or set(names) != expected:
            raise _error("builder_archive")
        for item in infos:
            mode = item.external_attr >> 16
            if item.filename == root:
                if not item.is_dir() or item.file_size != 0 or stat.S_ISLNK(mode):
                    raise _error("builder_archive")
                continue
            if (
                item.is_dir()
                or stat.S_ISLNK(mode)
                or item.flag_bits & 1
                or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
            ):
                raise _error("builder_archive")
            name = item.filename[len(root) :]
            if name not in MEMBERS:
                continue
            size, sha256 = MEMBERS[name]
            if item.file_size != size:
                raise _error("builder_archive")
            with archive.open(item) as stream:
                content = stream.read(size + 1)
            _verify(content, {"bytes": size, "sha256": sha256})
            content.decode("ascii")
            (destination / name).write_bytes(content)


def _patch(source: Path, patch: bytes, output: Path) -> None:
    """Apply only the admitted NULL substitutions and one-token declaration fix."""
    # The exact Debian patch was already hash-checked, so no external patch utility
    # or general patch interpreter is needed for these three pinned substitutions.
    seq = source / "seq.cc"
    original = seq.read_bytes()
    if original.count(b"if(i == EOF) return false;") != 3:
        raise _error("builder_patch")
    corrected = original.replace(
        b"if(i == EOF) return false; \n", b"if(i == EOF) return NULL;\n"
    ).replace(b"if(i == EOF) return false;", b"if(i == EOF) return NULL;")
    if _digest(corrected) != SEQ_RESULT:
        raise _error("builder_patch")
    seq.write_bytes(corrected)
    header = source / "search.h"
    original = header.read_bytes()
    corrected = original.replace(
        b"int set_max_len_loop(int, int);", b"void set_max_len_loop(int, int);"
    )
    if (
        _digest(original) != MEMBERS["search.h"][1]
        or _digest(corrected) != HEADER_RESULT
    ):
        raise _error("builder_patch")
    header.write_bytes(corrected)
    prototype = "".join(
        difflib.unified_diff(
            original.decode("ascii").splitlines(keepends=True),
            corrected.decode("ascii").splitlines(keepends=True),
            fromfile="a/search.h",
            tofile="b/search.h",
        )
    ).encode("ascii")
    if _digest(prototype) != PROTOTYPE_PATCH_SHA256:
        raise _error("builder_patch")
    (output / "null-pointer.patch").write_bytes(patch)
    (output / "prototype-return-type.patch").write_bytes(prototype)


def _tool(path: Path) -> tuple[Path, bytes]:
    selected = path.absolute()
    # Explicit compiler symlinks (e.g. clang++ -> clang) preserve driver mode.
    data = _read_regular(
        selected.resolve(strict=True), 512 * 1024 * 1024, executable=True
    )
    # Make expands CXX inside a shell recipe even though make itself uses argv.
    if re.fullmatch(r"/[A-Za-z0-9_./+-]+", str(selected)) is None:
        raise _error("builder_tool")
    return selected, data


def _extra(
    arch: str | None, sysroot: Path | None, cxx_include: Path | None
) -> list[str]:
    flags: list[str] = []
    if arch is not None:
        if arch not in ("arm64", "x86_64"):
            raise _error("builder_flags")
        flags += ["-arch", arch]
    for option, path in (("-isysroot", sysroot), ("-isystem", cxx_include)):
        if path is not None:
            absolute = path.resolve(strict=True)
            if (
                not absolute.is_dir()
                or re.fullmatch(r"/[A-Za-z0-9_./+-]+", str(absolute)) is None
            ):
                raise _error("builder_flags")
            flags += [option, str(absolute)]
    return flags


def build_backend(
    *,
    archive: Path,
    patch: Path,
    compiler: Path,
    output: Path,
    make: Path = Path("/usr/bin/make"),
    arch: str | None = None,
    sysroot: Path | None = None,
    cxx_include: Path | None = None,
    standard_library: str = "compiler-default",
) -> dict[str, Any]:
    """Create a new external installation, issuing its receipt only on success."""
    if os.name != "posix":
        raise _error("unsupported_platform")
    try:
        raw = _read_regular(archive, ARCHIVE_BYTES)
        _verify(raw, {"bytes": ARCHIVE_BYTES, "sha256": ARCHIVE_SHA256})
        patch_bytes = _read_regular(patch, PATCH_BYTES)
        _verify(patch_bytes, {"bytes": PATCH_BYTES, "sha256": NULL_PATCH_SHA256})
        compiler_path, compiler_bytes = _tool(compiler)
        make_path, _ = _tool(make)
        extras = _extra(arch, sysroot, cxx_include)
        output = output.resolve()
        # An installation must remain external even if invoked from another cwd.
        repository = Path(__file__).resolve().parents[1]
        if output.is_relative_to(repository):
            raise _error("builder_output")
        output.mkdir(exist_ok=False)
        original = output / "source-original"
        original.mkdir()
        _extract(raw, original)
        source = output / "source-build"
        shutil.copytree(original, source)
        _patch(source, patch_bytes, output)
        env = {"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin"}
        version = _execute(
            compiler_path,
            output,
            time.monotonic() + 10,
            None,
            arguments=["--version"],
            environment=env,
            own_process_group=True,
        )
        version_text = version.stdout.decode("ascii")
        version_label = version_text.splitlines()[0]
        identity: dict[str, Any] = {
            "schema_version": "termination-backend-1",
            "profile": PROFILE,
            "source": dict(SOURCE),
            "build": {
                "compiler": compiler_path.name,
                "compiler_sha256": _digest(compiler_bytes),
                "compiler_version": version_label,
                "platform": platform.system() + "-" + platform.release(),
                "machine": arch or platform.machine(),
                "standard_library": standard_library,
                "flags": list(BUILD_FLAGS),
                "extra_flags_sha256": _digest(
                    json.dumps(extras, separators=(",", ":")).encode()
                ),
            },
            "binary": {"bytes": 1, "sha256": "0" * 64},
            "table": {"bytes": 45788, "sha256": TABLE_SHA256},
        }
        _manifest(identity)
        command = [
            str(make_path),
            "-j1",
            "transterm",
            f"CXX={compiler_path}",
            "CXXFLAGS=" + " ".join(BUILD_FLAGS + extras),
            "CPPFLAGS=",
            "LDFLAGS=",
        ]
        start = time.monotonic()
        result = _execute(
            make_path,
            source,
            start + 180,
            None,
            arguments=command[1:],
            environment=env,
            own_process_group=True,
        )
        binary = _read_regular(source / "transterm", BINARY_LIMIT, executable=True)
        table = _read_regular(source / "expterm.dat", 45788)
        _verify(table, identity["table"])
        identity["binary"] = {"bytes": len(binary), "sha256": _digest(binary)}
        _manifest(identity)
        (output / "transterm").write_bytes(binary)
        (output / "transterm").chmod(0o755)
        (output / "expterm.dat").write_bytes(table)
        (output / "build.stdout").write_bytes(result.stdout)
        (output / "build.stderr").write_bytes(result.stderr)
        (output / "compiler.stdout").write_bytes(version.stdout)
        receipt = {
            "command": command,
            "compiler_version": version_text,
            "elapsed_seconds": time.monotonic() - start,
            "diagnostics": result.diagnostics,
            "original_header_sha256": MEMBERS["search.h"][1],
            "patched_header_sha256": HEADER_RESULT,
            "patched_seq_sha256": SEQ_RESULT,
        }
        (output / "build-receipt.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        # Last write: no success receipt exists for any preceding failure.
        receipt_path = output / ".backend.json.tmp"
        receipt_path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
        receipt_path.replace(output / "backend.json")
        return identity
    except TerminationBackendError:
        raise
    except (OSError, ValueError, IndexError, zipfile.BadZipFile, RuntimeError) as exc:
        raise _error("builder_io") from exc


def main(argv: list[str] | None = None) -> int:
    """Offline command line; all source and compiler selection is explicit."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "patch", "compiler", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--make", type=Path, default=Path("/usr/bin/make"))
    parser.add_argument("--arch", choices=("arm64", "x86_64"))
    parser.add_argument("--sysroot", type=Path)
    parser.add_argument("--cxx-include", type=Path)
    parser.add_argument("--standard-library", default="compiler-default")
    args = parser.parse_args(argv)
    try:
        build_backend(**vars(args))
    except TerminationBackendError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("External termination backend built and identified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
