"""Original file-based adapter to separately installed RNAstructure 6.6 tools.

No RNAstructure library is linked or vendored. Every process uses private
scratch files and explicit parameters. Inputs never appear in shell commands.
"""

import hashlib
import json
import math
import os
import re
import subprocess
import time
from copy import deepcopy
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory

from regsite.structures import BackendError, Structure, parse_ct, to_ct

SOURCE_SHA256 = "1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3"
MAX_STRUCTURES = 100
SETTINGS = {
    "alphabet": "rna",
    "fold_maximum": 1,
    "fold_mfe_only": True,
    "energy_evaluation": "efn2 --simple for every structure",
    "fold_window": 0,
    "maximum_loop": 30,
    "bifold_maximum": MAX_STRUCTURES,
    "bifold_percent": 100,
    "bifold_window": 0,
    "intramolecular_pairs": True,
    "isolated_pairs": False,
    "coaxial_stacking": True,
    "dangles": "RNAstructure 6.6 native; no historical auto-dangle switch",
    "efn2_multibranch_model": "simple",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(executable: Path, args: list[str], tables: Path, timeout: float) -> str:
    """Run one trusted backend executable without a shell or inherited DATAPATH."""
    if timeout <= 0:
        raise BackendError("request folding time budget exhausted")
    env = dict(os.environ, DATAPATH=str(tables), OMP_NUM_THREADS="1")
    try:
        result = subprocess.run(
            [str(executable), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise BackendError(f"{executable.name} unavailable or timed out") from exc
    # RNAstructure returns 1 for --version even on a valid installation.
    if result.returncode and args != ["--version"]:
        raise BackendError(f"{executable.name} failed (exit {result.returncode})")
    return result.stdout


@dataclass(frozen=True)
class RnaStructure:
    """Verified executable/table installation; temperature belongs to a request."""

    root: Path
    identity: dict

    @classmethod
    def open(cls, root: str | Path) -> "RnaStructure":
        """Check the installed version and all pinned RNA parameter tables."""
        root = Path(root).expanduser().resolve()
        manifest_bytes = (
            files("regsite").joinpath("data/rnastructure-tables.json").read_bytes()
        )
        manifest = json.loads(manifest_bytes)
        try:
            for name, expected in manifest.items():
                if _sha256(root / "data_tables" / name) != expected:
                    raise BackendError(f"RNAstructure parameter hash mismatch: {name}")
            binaries = {}
            for program in ("Fold", "bifold", "efn2"):
                executable = root / "exe" / program
                version = _run(executable, ["--version"], root / "data_tables", 10)
                if not re.search(r"\bVersion 6\.6(?:\s|\()", version):
                    raise BackendError(f"{program} is not RNAstructure 6.6")
                binaries[program] = _sha256(executable)
        except OSError as exc:
            raise BackendError("RNAstructure installation is incomplete") from exc
        return cls(
            root,
            {
                "name": "RNAstructure",
                "version": "6.6",
                "interface": "independent executables via sequence/CT files",
                "licence": "GPL-2.0-only (separate installation)",
                "expected_source_archive_sha256": SOURCE_SHA256,
                "binary_sha256": binaries,
                "table_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "settings": deepcopy(SETTINGS),
            },
        )

    def session(self, temperature_c: float, seconds: float = 60) -> "FoldingSession":
        """Create a request-local total wall-time budget, capped at 120 seconds."""
        if not 0 < seconds <= 120 or not 0 <= temperature_c <= 100:
            raise BackendError("invalid folding budget or temperature")
        return FoldingSession(
            self.root, temperature_c + 273.15, time.monotonic() + seconds
        )


@dataclass(frozen=True)
class FoldingSession:
    """Bounded request-local engine operations on at most 82 CT positions."""

    root: Path
    kelvin: float
    deadline: float

    def _call(self, program: str, args: list[str]) -> str:
        return _run(
            self.root / "exe" / program,
            [*args, "--temperature", str(self.kelvin), "--alphabet", "rna"],
            self.root / "data_tables",
            min(15, self.deadline - time.monotonic()),
        )

    def _read(self, path: Path) -> str:
        try:
            with path.open() as stream:
                text = stream.read(2_000_001)
        except (OSError, UnicodeError) as exc:
            raise BackendError("backend output is missing or unreadable") from exc
        if len(text) > 2_000_000:
            raise BackendError("backend output exceeds the resource limit")
        return text

    def evaluate(self, sequence: str, pairs: tuple[int, ...]) -> Structure:
        """Evaluate the supplied structure, preserving its exact base pairs."""
        return self._evaluate_many((Structure(sequence, pairs, None),))[0]

    def _evaluate_many(
        self, structures: tuple[Structure, ...]
    ) -> tuple[Structure, ...]:
        """Use one explicit energy evaluator for folded and constructed states."""
        if not 1 <= len(structures) <= MAX_STRUCTURES:
            raise BackendError("invalid fixed-structure count")
        if any(not 1 <= len(s.sequence) <= 82 for s in structures):
            raise BackendError("fixed structure exceeds the supported window")
        with TemporaryDirectory(prefix="regsite-") as directory:
            ct, output = Path(directory) / "input.ct", Path(directory) / "energy.txt"
            ct.write_text("".join(to_ct(s.sequence, s.pairs) for s in structures))
            self._call("efn2", [str(ct), str(output), "--simple", "--ne"])
            lines = self._read(output).strip().splitlines()
        if len(lines) != len(structures):
            raise BackendError("efn2 structure count mismatch")
        evaluated = []
        for index, (structure, line) in enumerate(
            zip(structures, lines, strict=True), 1
        ):
            match = re.fullmatch(
                rf"\s*Structure:\s*{index}\s+Energy\s*=\s*(\S+)\s*", line
            )
            try:
                energy = float(match.group(1)) if match else float("nan")
            except ValueError as exc:
                raise BackendError("invalid efn2 energy") from exc
            if not math.isfinite(energy):
                raise BackendError("missing/nonfinite efn2 energy")
            evaluated.append(
                replace(structure, energy=energy, prediction_energy=structure.energy)
            )
        return tuple(evaluated)

    def fold(self, sequence: str) -> Structure:
        """Fold an RNA window; an empty mathematical prefix has energy zero."""
        if not sequence:
            return Structure("", (), 0.0)
        if len(sequence) > 70 or set(sequence) - set("ACGU"):
            raise BackendError("fold expects at most 70 normalized RNA bases")
        with TemporaryDirectory(prefix="regsite-") as directory:
            fasta, ct = Path(directory) / "input.fa", Path(directory) / "output.ct"
            fasta.write_text(f">regsite\n{sequence}\n")
            self._call(
                "Fold",
                [
                    str(fasta),
                    str(ct),
                    "--MFE",
                    "--maximum",
                    "1",
                    "--window",
                    "0",
                    "--loop",
                    "30",
                ],
            )
            structures = parse_ct(self._read(ct), sequence)
        if len(structures) != 1:
            raise BackendError("Fold returned more than one requested structure")
        return self._evaluate_many(structures)[0]

    def cofold(self, leader: str, anti_sd: str) -> tuple[Structure, ...]:
        """Bounded cofold search with intramolecular pairing, not exhaustive subopt."""
        if (
            not 1 <= len(leader) <= 35
            or len(anti_sd) != 9
            or set(leader + anti_sd) - set("ACGU")
        ):
            raise BackendError("cofold expects a 1–35 nt leader and 9 nt aSD")
        sequence = leader + "III" + anti_sd
        with TemporaryDirectory(prefix="regsite-") as directory:
            first, second, ct = [
                Path(directory) / name for name in ("leader.fa", "asd.fa", "output.ct")
            ]
            first.write_text(f">leader\n{leader}\n")
            second.write_text(f">asd\n{anti_sd}\n")
            self._call(
                "bifold",
                [
                    str(first),
                    str(second),
                    str(ct),
                    "--maximum",
                    str(MAX_STRUCTURES),
                    "--percent",
                    "100",
                    "--window",
                    "0",
                    "--loop",
                    "30",
                ],
            )
            structures = parse_ct(self._read(ct), sequence)
        return self._evaluate_many(structures)
