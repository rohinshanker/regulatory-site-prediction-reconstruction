"""Checked connectivity tables for RNAstructure command-line results.

The CT interchange format uses one-based pair indices and zero for unpaired
bases. Internally pairs are zero-based, with -1 denoting an unpaired base.
"""

import math
import re
from dataclasses import dataclass


class BackendError(RuntimeError):
    """A folding backend failed or returned an invalid/inconsistent result."""


@dataclass(frozen=True)
class Structure:
    """A validated secondary structure and its energy in kcal/mol."""

    sequence: str
    pairs: tuple[int, ...]
    energy: float | None

    def dot_bracket(self) -> str:
        """Render a pseudoknot-free structure; fail rather than misrender pairs."""
        stack = []
        symbols = []
        for index, partner in enumerate(self.pairs):
            if partner < 0:
                symbols.append(".")
            elif partner > index:
                symbols.append("(")
                stack.append(partner)
            else:
                if not stack or stack.pop() != index:
                    raise BackendError("crossing or inconsistent pairs in CT output")
                symbols.append(")")
        if stack:
            raise BackendError("unclosed pairs in CT output")
        return "".join(symbols)


def parse_ct(text: str, expected_sequence: str) -> tuple[Structure, ...]:
    """Parse and validate complete CT structures against the submitted sequence.

    The expected sequence includes RNAstructure's III linker for a duplex.
    Missing energies remain None for explicit evaluation by efn2. Malformed
    rows, nonreciprocal pairs and extra sequence content are errors.
    """
    if len(text) > 2_000_000:
        raise BackendError("CT output exceeds the resource limit")
    lines = text.splitlines()
    structures = []
    offset = 0
    while offset < len(lines):
        if not lines[offset].strip():
            offset += 1
            continue
        header = lines[offset]
        match = re.search(r"\bENERGY\s*=\s*(\S+)", header)
        try:
            length = int(header.split()[0])
            energy = float(match.group(1)) if match else None
        except ValueError as exc:
            raise BackendError("invalid CT header") from exc
        if length != len(expected_sequence) or (
            energy is not None and not math.isfinite(energy)
        ):
            raise BackendError("CT length or energy does not match the request")
        rows = lines[offset + 1 : offset + length + 1]
        if len(rows) != length:
            raise BackendError("truncated CT structure")
        sequence = []
        pairs = []
        for index, row in enumerate(rows, 1):
            columns = row.split()
            if len(columns) != 6:
                raise BackendError("CT row must contain six columns")
            try:
                number, partner = int(columns[0]), int(columns[4])
                tuple(int(columns[i]) for i in (2, 3, 5))
            except ValueError as exc:
                raise BackendError("noninteger CT coordinate") from exc
            if number != index or not 0 <= partner <= length or partner == index:
                raise BackendError("invalid CT pair/index")
            sequence.append(columns[1].upper().replace("T", "U"))
            pairs.append(partner - 1)
        if "".join(sequence) != expected_sequence:
            raise BackendError("CT sequence differs from the submitted sequence")
        if any(base == "I" and pairs[i] != -1 for i, base in enumerate(sequence)):
            raise BackendError("CT linker bases cannot pair")
        if any(partner >= 0 and pairs[partner] != i for i, partner in enumerate(pairs)):
            raise BackendError("CT pairs are not reciprocal")
        structure = Structure(expected_sequence, tuple(pairs), energy)
        structure.dot_bracket()
        structures.append(structure)
        if len(structures) > 100:
            raise BackendError("CT structure count exceeds the resource limit")
        offset += length + 1
    if not structures:
        raise BackendError("backend produced no CT structures")
    return tuple(structures)


def to_ct(sequence: str, pairs: tuple[int, ...]) -> str:
    """Encode a structure for independent fixed-structure energy evaluation."""
    length = len(sequence)
    if length != len(pairs):
        raise BackendError("sequence/pair lengths differ")
    rows = [f"{length} regsite"]
    natural = 0
    for i, (base, partner) in enumerate(zip(sequence, pairs, strict=True), 1):
        natural = 0 if base == "I" else natural + 1
        rows.append(
            f"{i} {base} {i - 1} {i + 1 if i < length else 0} {partner + 1} {natural}"
        )
    text = "\n".join(rows) + "\n"
    parse_ct(text, sequence)
    return text
