"""Derive the admitted historical parameters without executing upstream code.

Usage: python tools/derive_promoter_parameters.py SOURCE_DIRECTORY OUTPUT_JSON
SOURCE_DIRECTORY contains the seven flat files named in the source manifest.
All source pins are checked before parsing. Output is deterministic UTF-8 JSON;
the printed SHA256 identifies compact canonical JSON, without a trailing LF.
Original parameter/table copyright: La Fleur, Hossain, Salis (2021), GPL-3.0+.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import math
import re
import struct
from pathlib import Path

SOURCE_COMMIT = "46da9132740bce30bccd107f02808adf2215e2f0"
SOURCE_HASHES = {
    "LICENSE": "45d25f34fe826d27d344175bd622cbf3d35cbf53bd993d1350d44ee706571ffd",
    "Promoter_Calculator_v1_0.py": (
        "67d2733b0be1968668c6710e56262b00d9b4725b98b4f94749519591b48d1cdb"
    ),
    "README.md": "a5f3269206f5425e2c21ca58d9cb638fe87a4cbb1dbdff537a676747dc4b26d2",
    "__init__.py": "04e3ef58dfe74117dcccacddbd0f13d28611a3d71020f060d69d64bb33407afe",
    "free_energy_coeffs.npy": (
        "fddf16b38bf29799481e8a45890b669111e16cf2e3448e99d1934d19a8f0b8e9"
    ),
    "model_intercept.npy": (
        "f7c66a8d838da71a6b2ab17936cd6ff2564e446af8c0676fba95de2116e99a7b"
    ),
    "util.py": "abd561c6f1a4669dace3f783903f2779133cdc4ce5319919302303982eba23cc",
}
TABLE_NAMES = ("groove_access", "persistence", "DNA_DNA_hybrids", "RNA_DNA_hybrids")


def canonical_bytes(value: object) -> bytes:
    """Return the public compact JSON encoding used for parameter identity."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def read_npy(data: bytes, count: int) -> list[float]:
    """Read precisely a version-1, one-dimensional little-endian float64 NPY."""
    if len(data) < 10 or data[:8] != b"\x93NUMPY\x01\x00":
        raise ValueError("Expected NPY version 1.0")
    size = struct.unpack("<H", data[8:10])[0]
    if size > len(data) - 10:
        raise ValueError("Truncated NPY header")
    header = ast.literal_eval(data[10 : 10 + size].decode("ascii").strip())
    if header != {"descr": "<f8", "fortran_order": False, "shape": (count,)}:
        raise ValueError("Unexpected NPY layout")
    payload = data[10 + size :]
    if len(payload) != count * 8:
        raise ValueError("Unexpected NPY payload size")
    values = list(struct.unpack(f"<{count}d", payload))
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Nonfinite NPY value")
    return values


def literal_tables(source: str) -> dict[str, dict[str, float]]:
    """Extract only literal table assignments; imports/functions are never run."""
    tables = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in TABLE_NAMES:
                    if target.id in tables:
                        raise ValueError("Duplicate table assignment")
                    tables[target.id] = ast.literal_eval(node.value)
    dimers = {"".join(k) for k in itertools.product("ACGT", repeat=2)}
    if set(tables) != set(TABLE_NAMES):
        raise ValueError("Missing utility table")
    for table in tables.values():
        if not isinstance(table, dict) or set(table) != dimers:
            raise ValueError("Invalid dimer table")
        if not all(
            type(v) in (int, float) and math.isfinite(v) for v in table.values()
        ):
            raise ValueError("Invalid table number")
    return tables


def literal_normalizers(source: str) -> list[float]:
    """Extract the one literal normalizer list, including from Python 2 source."""
    matches = re.findall(r"^\s*normalizing_values\s*=\s*(\[.*\])\s*$", source, re.M)
    if len(matches) != 1:
        raise ValueError("Expected exactly one normalizer assignment")
    values = ast.literal_eval(matches[0])
    if len(values) != 4 or not all(
        type(v) is float and math.isfinite(v) and v > 0 for v in values
    ):
        raise ValueError("Invalid normalizers")
    return values


def derive(source_directory: Path, manifest_path: Path) -> dict[str, object]:
    """Recheck every manifest/source identity and derive the complete object."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pins = {Path(e["path"]).name: e["sha256"] for e in manifest["sources"]}
    if manifest["historical_commit"] != SOURCE_COMMIT or pins != SOURCE_HASHES:
        raise ValueError("Source manifest identity mismatch")
    assets = {}
    for name, pin in SOURCE_HASHES.items():
        data = (source_directory / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != pin:
            raise ValueError(f"Source hash mismatch: {name}")
        assets[name] = data
    return {
        "array_sha256": {
            "coefficients": SOURCE_HASHES["free_energy_coeffs.npy"],
            "intercept": SOURCE_HASHES["model_intercept.npy"],
        },
        "coefficients": read_npy(assets["free_energy_coeffs.npy"], 343),
        "intercept": read_npy(assets["model_intercept.npy"], 1)[0],
        "license": "GPL-3.0-or-later; see NOTICE and COPYING",
        "normalizers": literal_normalizers(
            assets["Promoter_Calculator_v1_0.py"].decode("utf-8")
        ),
        "source_commit": SOURCE_COMMIT,
        "tables": literal_tables(assets["util.py"].decode("utf-8")),
    }


def main(argv: list[str] | None = None) -> int:
    """Write reproducible parameter JSON and print its canonical SHA256."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "benchmarks/promoter/source-manifest.json",
    )
    args = parser.parse_args(argv)
    parameters = derive(args.source_directory, args.manifest)
    args.output_json.write_text(
        json.dumps(parameters, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(hashlib.sha256(canonical_bytes(parameters)).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
