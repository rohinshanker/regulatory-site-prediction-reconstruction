"""Independent small-structure oracle and strict CT audit, without runtime imports.

This enumerates topology, not a thermodynamic prediction engine. Fixed structures
are evaluated by the separately installed RNAstructure efn2 executable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PAIRS = {"AU", "UA", "CG", "GC", "GU", "UG"}


@dataclass(frozen=True)
class Structure:
    """CT numbering is one-based; zero means unpaired, including III linkers."""

    sequence: str
    partners: tuple[int, ...]
    native_energy: float | None = None


def validate(structure: Structure) -> None:
    """Reject illegal, nonreciprocal or crossing prediction topologies."""
    sequence, partners = structure.sequence, structure.partners
    n = len(sequence)
    if not n or len(partners) != n or set(sequence) - set("ACGUI"):
        raise ValueError("invalid CT sequence/length")
    if "I" in sequence and (
        sequence.count("I") != 3
        or "III" not in sequence
        or sequence.startswith("I")
        or sequence.endswith("I")
    ):
        raise ValueError("invalid intermolecular linker")
    for i, partner in enumerate(partners, 1):
        if type(partner) is not int or not 0 <= partner <= n or partner == i:
            raise ValueError(f"invalid partner at {i}")
        if partner:
            if partners[partner - 1] != i:
                raise ValueError(f"nonreciprocal pair at {i}:{partner}")
            if sequence[i - 1] + sequence[partner - 1] not in PAIRS:
                raise ValueError(f"noncanonical/linker pair at {i}:{partner}")
            if i < partner and "I" not in sequence[i - 1 : partner] and partner - i < 4:
                raise ValueError(f"short intramolecular loop at {i}:{partner}")
            for j in range(i + 1, partner):
                if partners[j - 1] > partner:
                    raise ValueError(f"crossing pairs at {i}:{partner} and {j}")


def read_ct(text: str, expected_sequence: str) -> list[Structure]:
    """Read full CT collections; malformed members invalidate the collection."""
    lines = text.splitlines()
    if not lines:
        raise ValueError("empty CT output")
    result = []
    cursor = 0
    while cursor < len(lines):
        header = lines[cursor].split()
        if not header:
            raise ValueError("blank CT header")
        n = int(header[0])
        if n != len(expected_sequence) or cursor + n >= len(lines):
            raise ValueError("CT length/truncation")
        match = re.search(r"\bENERGY\s*=\s*(\S+)", lines[cursor])
        energy = float(match.group(1)) if match else None
        if energy is not None and not math.isfinite(energy):
            raise ValueError("nonfinite CT energy")
        sequence, partners = [], []
        for i, row in enumerate(lines[cursor + 1 : cursor + n + 1], 1):
            fields = row.split()
            if len(fields) != 6:
                raise ValueError("CT row must have six columns")
            index, previous, following, partner, natural = (
                int(fields[j]) for j in (0, 2, 3, 4, 5)
            )
            if (index, previous, following) != (i, i - 1, i + 1 if i < n else 0):
                raise ValueError("invalid CT backbone/index")
            if natural < 0:
                raise ValueError("negative natural numbering")
            sequence.append(fields[1].upper())
            partners.append(partner)
        structure = Structure("".join(sequence), tuple(partners), energy)
        if structure.sequence != expected_sequence.upper():
            raise ValueError("CT sequence mismatch")
        validate(structure)
        if any(
            base.islower() and partner
            for base, partner in zip(expected_sequence, structure.partners, strict=True)
        ):
            raise ValueError("paired lowercase-constrained nucleotide")
        result.append(structure)
        cursor += n + 1
    return result


def to_ct(structures: list[Structure]) -> str:
    """Write independently constructed structures, without invented energies."""
    lines = []
    for structure in structures:
        validate(structure)
        n = len(structure.sequence)
        lines.append(f"{n} independent topology")
        for i, (base, partner) in enumerate(
            zip(structure.sequence, structure.partners, strict=True), 1
        ):
            lines.append(f"{i} {base} {i - 1} {i + 1 if i < n else 0} {partner} {i}")
    return "\n".join(lines) + "\n"


def enumerate_small(sequence: str) -> list[Structure]:
    """Exhaust all noncrossing canonical topologies for at most 12 real bases.

    Permit lonely pairs. Intramolecular pairs need at least three enclosed bases.
    An III separator is unpairable and removes that loop-length restriction for
    interstrand pairs. There are no energy, native-output or RBS-model heuristics.
    """
    validate(Structure(sequence, (0,) * len(sequence)))
    if len(sequence.replace("I", "")) > 12:
        raise ValueError("exhaustive oracle limited to 12 real bases")

    @lru_cache(None)
    def interval(left: int, right: int) -> tuple[tuple[tuple[int, int], ...], ...]:
        if left >= right:
            return ((),)
        choices = list(interval(left + 1, right))
        for paired in range(left + 1, right):
            if sequence[left] + sequence[paired] not in PAIRS:
                continue
            if paired - left < 4 and "I" not in sequence[left:paired]:
                continue
            for inside in interval(left + 1, paired):
                for after in interval(paired + 1, right):
                    choices.append(((left, paired),) + inside + after)
        return tuple(choices)

    result = []
    for pairs in interval(0, len(sequence)):
        partners = [0] * len(sequence)
        for left, right in pairs:
            partners[left], partners[right] = right + 1, left + 1
        result.append(Structure(sequence, tuple(partners)))
    return result


def read_energies(text: str, count: int) -> list[float]:
    """Read the --simple --ne efn2 record order, never assume sorted output."""
    lines = text.splitlines()
    if len(lines) != count:
        raise ValueError("efn2 count mismatch")
    values = []
    for index, line in enumerate(lines, 1):
        match = re.fullmatch(r"Structure:\s+(\d+)\s+Energy\s*=\s*(\S+)\s*", line)
        if match is None or int(match.group(1)) != index:
            raise ValueError("efn2 record index/format")
        value = float(match.group(2))
        if not math.isfinite(value):
            raise ValueError("nonfinite efn2 energy")
        values.append(value)
    return values


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(manifest_path: Path, backend: Path, output: Path) -> dict:
    """Run the fixed public diagnostic panel and retain every raw response.

    A new output directory is mandatory: no cached result can hide a missing CT.
    Failure observations are recorded, never discarded or turned into energies.
    """
    manifest = json.loads(manifest_path.read_text())
    table_manifest = manifest_path.parent / manifest["table_manifest"]
    if sha256(table_manifest) != manifest["table_manifest_sha256"]:
        raise ValueError("table manifest changed")
    tables = json.loads(table_manifest.read_text())
    for name, digest in tables.items():
        if sha256(backend / "data_tables" / name) != digest:
            raise ValueError(f"energy table changed: {name}")
    output.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ, DATAPATH=str(backend / "data_tables"))
    binary_hashes = {
        name: sha256(backend / "exe" / name)
        for name in ("Fold", "bifold", "AllSub", "efn2")
    }
    records = []
    for case in manifest["cases"]:
        directory = output / case["id"]
        directory.mkdir()
        sequences = case["sequences"]
        for index, sequence in enumerate(sequences):
            (directory / f"s{index}.fa").write_text(f">s{index}\n{sequence}\n")
        expected = "III".join(sequences)
        executable = case["executable"]
        arguments = [f"s{i}.fa" for i in range(len(sequences))] + ["output.ct"]
        arguments += case["options"] + [
            "--temperature",
            str(case["temperature_kelvin"]),
        ]
        command = [str(backend / "exe" / executable), *arguments]
        record = {"id": case["id"], "command": [executable, *arguments]}
        diagnostic_prefix = ""
        try:
            process = subprocess.run(
                command,
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            (directory / "stdout.txt").write_text(process.stdout)
            (directory / "stderr.txt").write_text(process.stderr)
            record["exit_code"] = process.returncode
            if process.returncode:
                raise ValueError("nonzero process exit")
            if not (directory / "output.ct").is_file():
                raise ValueError("missing CT output")
            structures = read_ct((directory / "output.ct").read_text(), expected)
            if "--intramolecular" in case["options"]:
                boundary = len(sequences[0])
                if any(
                    partner
                    and (
                        (i < boundary and partner <= boundary)
                        or (i >= boundary + 3 and partner > boundary + 3)
                    )
                    for structure in structures
                    for i, partner in enumerate(structure.partners)
                ):
                    raise ValueError("forbidden intramolecular pair")
            fixed = directory / "checked.ct"
            fixed.write_text(to_ct(structures))
            energy_command = [
                str(backend / "exe/efn2"),
                "checked.ct",
                "energies.txt",
                "--simple",
                "--ne",
                "--temperature",
                str(case["temperature_kelvin"]),
            ]
            diagnostic_prefix = "efn2-"
            energy_run = subprocess.run(
                energy_command,
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            (directory / "efn2-stdout.txt").write_text(energy_run.stdout)
            (directory / "efn2-stderr.txt").write_text(energy_run.stderr)
            if energy_run.returncode or not (directory / "energies.txt").is_file():
                raise ValueError("efn2 process/output failure")
            energies = read_energies(
                (directory / "energies.txt").read_text(), len(structures)
            )
            record.update(
                status="ok",
                structures=[
                    {
                        "partners": list(s.partners),
                        "native_energy": s.native_energy,
                        "efn2_simple_energy": energy,
                    }
                    for s, energy in zip(structures, energies, strict=True)
                ],
            )
        except subprocess.TimeoutExpired as error:
            for name, captured in (("stdout", error.stdout), ("stderr", error.stderr)):
                raw = (
                    captured
                    if isinstance(captured, bytes)
                    else (captured or "").encode()
                )
                (directory / f"{diagnostic_prefix}{name}.txt").write_bytes(raw)
            record.update(status="failed", failure=str(error))
        except ValueError as error:
            record.update(status="failed", failure=str(error))
        record["files"] = {p.name: sha256(p) for p in sorted(directory.iterdir())}
        records.append(record)
    report = {
        "schema_version": "rbs-structural-observations-1",
        "manifest_sha256": sha256(manifest_path),
        "binaries": binary_hashes,
        "records": records,
    }
    (output / "observations.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("backend", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = collect(args.manifest, args.backend, args.output)
    print(
        json.dumps(
            {
                "cases": len(report["records"]),
                "failed": sum(x["status"] != "ok" for x in report["records"]),
            }
        )
    )


if __name__ == "__main__":
    main()
