# SPDX-License-Identifier: GPL-2.0-only
"""Standalone structural checks; deliberately does not import regsite."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


@dataclass(frozen=True)
class Structure:
    sequence: str
    pairs: tuple
    energy: Decimal | None


def verify_installation(root, manifest):
    """Bind the real tools and source to the declared component build receipt."""
    root = Path(root)
    receipt = json.loads((root / "traceback-build.json").read_text())
    expected = {
        "component": manifest["component"],
        "source_archive_sha256": manifest["upstream"]["archive_sha256"],
        "patch_sha256": manifest["patch"]["sha256"],
        "patched_source_sha256": manifest["patch"]["patched_source_sha256"],
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ValueError(f"Build receipt mismatch: {field}")
    files = {manifest["upstream"]["source_file"]: expected["patched_source_sha256"]}
    for name in ("Fold", "bifold", "efn2"):
        files[f"exe/{name}"] = receipt["executable_sha256"][name]
    for name, digest in files.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Installed file hash mismatch: {name}")


def parse_ct(text):
    """Parse CT while independently enforcing reciprocal, nested base pairs."""
    lines = text.splitlines()
    structures = []
    cursor = 0
    while cursor < len(lines):
        header = lines[cursor]
        size = int(header.split()[0])
        if size < 1 or cursor + size >= len(lines):
            raise ValueError("Truncated CT")
        rows = [line.split() for line in lines[cursor + 1:cursor + size + 1]]
        sequence = "".join(row[1] for row in rows)
        partners = [0]
        for index, row in enumerate(rows, 1):
            # CT's final column is historical numbering: bifold resets it
            # on strand two and uses zero for the artificial linker.
            if len(row) != 6 or int(row[0]) != index or int(row[5]) < 0:
                raise ValueError("Invalid CT index")
            if int(row[2]) != index - 1 or int(row[3]) != (index + 1 if index < size else 0):
                raise ValueError("Invalid CT neighbor")
            partner = int(row[4])
            if partner < 0 or partner > size or partner == index:
                raise ValueError("Invalid CT partner")
            partners.append(partner)
        pairs = []
        stack = []
        for index, partner in enumerate(partners[1:], 1):
            if partner and partners[partner] != index:
                raise ValueError("Nonreciprocal CT pair")
            if sequence[index - 1] == "I" and partner:
                raise ValueError("Paired linker")
            if index < partner:
                if sequence[index - 1] + sequence[partner - 1] not in ("AU", "UA", "GC", "CG", "GU", "UG"):
                    raise ValueError("Noncanonical pair")
                stack.append(partner)
                pairs.append((index, partner))
            elif partner and (not stack or stack.pop() != index):
                raise ValueError("Crossing CT pairs")
        if stack:
            raise ValueError("Unclosed CT pairs")
        match = re.search(r"ENERGY\s*=\s*(-?\d+(?:\.\d+)?)", header)
        energy = Decimal(match.group(1)) if match else None
        structures.append(Structure(sequence, tuple(pairs), energy))
        cursor += size + 1
    if not structures:
        raise ValueError("Empty CT")
    return structures


def identity(structures, energies=None):
    """Hash canonical biological structures/energies, excluding CT labels/paths."""
    data = [
        {"sequence": item.sequence, "pairs": item.pairs,
         "native_energy": str(item.energy) if item.energy is not None else None}
        for item in structures
    ]
    if energies is not None:
        data = {"structures": data, "evaluated": [str(value) for value in energies]}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def linker_topology(structure):
    """Return connectedness and immediate branches in the linker-containing loop.

    Count children of the innermost pair enclosing the three linker bases;
    nested stems inside a child are not additional branches in that loop.
    Disconnected structures instead count top-level stems in the exterior.
    """
    if "I" not in structure.sequence:
        return "single", 0
    linker = structure.sequence.index("I") + 1
    enclosing = [(i, j) for i, j in structure.pairs if i < linker and j > linker + 2]
    lo, hi = max(enclosing) if enclosing else (0, len(structure.sequence) + 1)
    children = [(i, j) for i, j in structure.pairs if lo < i < j < hi]
    branches = 0
    end = lo
    for i, j in children:
        if i > end:
            branches += 1
            end = j
    return "connected" if enclosing else "disconnected", branches


def energy_census(structures, energies):
    """Count exact efn2-minus-native deltas by connectedness and loop branches."""
    census = Counter()
    for structure, energy in zip(structures, energies, strict=True):
        connected, branches = linker_topology(structure)
        delta = f"{energy - structure.energy:.1f}" if structure.energy is not None else "missing"
        census[f"{connected}/{branches}/{delta}"] += 1
    return dict(sorted(census.items()))


def run_engine(root, directory, leader, anti_sd=None, temperature="303.15",
               fold_arguments=("--MFE",), bifold_arguments=(), constraint=None):
    """Run all requested tracebacks and independently reevaluate every structure.

    ``constraint`` is folding-constraint file text, applied with Fold only.
    ``bifold_arguments`` adds flags such as ``--intramolecular`` to bifold.
    """
    root = Path(root).resolve()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    first = directory / "leader.fa"
    first.write_text(">leader\n" + leader + "\n")
    output = directory / "output.ct"
    environment = dict(os.environ, DATAPATH=str(root / "data_tables"))
    if anti_sd is None:
        command = [str(root / "exe/Fold"), str(first), str(output), *fold_arguments]
        if constraint is not None:
            constraints = directory / "constraints.con"
            constraints.write_text(constraint)
            command.extend(["--constraint", str(constraints)])
    else:
        if constraint is not None:
            raise ValueError("Constraint files apply to Fold only")
        second = directory / "asd.fa"
        second.write_text(">asd\n" + anti_sd + "\n")
        command = [str(root / "exe/bifold"), str(first), str(second), str(output),
                   "--maximum", "100", "--percent", "100", "--window", "0", "--loop", "30",
                   *bifold_arguments]
    command.extend(["--temperature", temperature, "--alphabet", "rna"])
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=30)
    if result.returncode or result.stderr.strip() or not output.exists():
        raise ValueError(f"Folding failed: exit {result.returncode}; {result.stderr.strip()}")
    structures = parse_ct(output.read_text())
    expected_sequence = leader if anti_sd is None else leader + "III" + anti_sd
    if any(item.sequence != expected_sequence for item in structures):
        raise ValueError("Output sequence differs from input")
    evaluation = directory / "energy.txt"
    result = subprocess.run(
        [str(root / "exe/efn2"), str(output), str(evaluation), "--simple",
         "--temperature", temperature, "--alphabet", "rna"],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    if result.returncode or result.stderr.strip() or not evaluation.exists():
        raise ValueError("Energy evaluation failed")
    energies = [Decimal(value) for value in re.findall(
        r"^Structure:\s*\d+\s+Energy\s*=\s*(-?\d+(?:\.\d+)?)", evaluation.read_text(), re.MULTILINE)]
    if len(energies) != len(structures):
        raise ValueError("Incomplete energy evaluation")
    return structures, energies
