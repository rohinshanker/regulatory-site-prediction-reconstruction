"""Exact original RNAstructure admission and isolated canonical-state jobs.

This adapter deliberately does not use the RBS adapter's patched variants,
inherited environment, sequence normalization, or duplex CT conventions.
"""

import hashlib
import json
import math
import os
import re
import selectors
import subprocess
import time
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import IO, cast

from regsite.conditional_math import ConditionalError, check_deadline

CANONICAL = {"AU", "UA", "GC", "CG", "GU", "UG"}
PROCESS_LOCK = Lock()
OUTPUT_LIMIT = 1_000_000


def canonical_bytes(value: object) -> bytes:
    """The scientific identity representation has no newline."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def digest(value: bytes) -> str:
    """Hash bytes, without recording an installation path."""
    return hashlib.sha256(value).hexdigest()


def refuse(code: str, message: str, unsupported: bool = False) -> None:
    """Refuse a constraint before any filesystem or process operation."""
    raise ConditionalError(
        code, message, "unsupported" if unsupported else "invalid_input"
    )


def validate_demands(sequence: str, pairs: list, unpaired: list) -> dict:
    """Validate full-sequence zero-based demands and return their sorted identity."""
    used: set[int] = set()
    seen: set[tuple[int, int]] = set()
    singles: set[int] = set()

    def point(value):
        if type(value) is not int:
            refuse("invalid_position", "Positions must be genuine integers")
        if not 0 <= value < len(sequence):
            refuse("position_out_of_range", "Constraint position outside sequence")

    for pair in pairs:
        if type(pair) is not list or len(pair) != 2:
            refuse("invalid_pair", "Pairs must contain two positions")
        left, right = pair
        point(left)
        point(right)
        if left >= right:
            refuse("pair_not_5prime_first", "Pairs must be ascending")
        if (left, right) in seen:
            refuse("duplicate_pair", "Repeated pair")
        if left in used or right in used:
            refuse("position_in_multiple_pairs", "Base has competing partners")
        if right - left < 4:
            refuse("hairpin_too_short", "Pairs require three enclosed bases")
        if sequence[left] + sequence[right] not in CANONICAL:
            refuse("noncanonical_pair", "Only AU, GC and GU pairs are admitted", True)
        seen.add((left, right))
        used.update((left, right))
    ordered = sorted(seen)
    stack: list[int] = []
    for left, right in ordered:
        while stack and left > stack[-1]:
            stack.pop()
        if stack and right > stack[-1]:
            refuse("crossing_pairs", "Pseudoknots are not admitted", True)
        stack.append(right)
    for value in unpaired:
        point(value)
        if value in singles:
            refuse("duplicate_unpaired", "Repeated unpaired demand")
        if value in used:
            refuse("paired_and_unpaired", "Base required paired and unpaired")
        singles.add(value)
    return {"pairs": [list(pair) for pair in ordered], "unpaired": sorted(singles)}


def constraint_text(demands: dict) -> str:
    """Convert to one-based only at the RNAstructure file boundary."""
    singles = "".join(f"{point + 1}\n" for point in demands["unpaired"])
    pairs = "".join(f"{left + 1} {right + 1}\n" for left, right in demands["pairs"])
    return (
        f"DS:\n-1\nSS:\n{singles}-1\nMod:\n-1\nPairs:\n{pairs}-1 -1\n"
        "FMN:\n-1\nForbids:\n-1 -1\n"
    )


def parse_ct(raw: bytes, sequence: str, demands: dict | None) -> dict:
    """Require exactly one reciprocal, canonical, nested CT with a linear backbone."""
    try:
        lines = raw.decode("ascii").splitlines()
        header, *rows = lines
        if int(header.split()[0]) != len(sequence) or len(rows) != len(sequence):
            raise ValueError("CT length")
        energy_match = re.search(r"\bENERGY\s*=\s*(\S+)", header)
        energy = float(energy_match[1]) if energy_match else None
        if energy is not None and not math.isfinite(energy):
            raise ValueError("CT energy")
        partners = []
        for index, row in enumerate(rows, 1):
            columns = row.split()
            if len(columns) != 6:
                raise ValueError("CT columns")
            number, prev, next_, partner, _natural = (
                int(columns[i]) for i in (0, 2, 3, 4, 5)
            )
            if (
                number != index
                or columns[1] != sequence[index - 1]
                or prev != index - 1
                or next_ != (index + 1 if index < len(sequence) else 0)
                or not 0 <= partner <= len(sequence)
                or partner == index
            ):
                raise ValueError("CT backbone/sequence/index")
            partners.append(partner - 1)
        if any(p >= 0 and partners[p] != i for i, p in enumerate(partners)):
            raise ValueError("CT reciprocal")
        pairs = [[i, p] for i, p in enumerate(partners) if p > i]
        validate_demands(sequence, pairs, [])
    except (ValueError, IndexError) as exc:
        raise ConditionalError(
            "invalid_ct", "Backend returned an invalid canonical CT"
        ) from exc
    if demands is not None and (
        any(pair not in pairs for pair in demands["pairs"])
        or any(partners[i] >= 0 for i in demands["unpaired"])
    ):
        raise ConditionalError("constraint_violated", "CT violates supplied demands")
    structure = "".join(
        "." if p < 0 else "(" if p > i else ")" for i, p in enumerate(partners)
    )
    return dict(structure=structure, pairs=pairs, fold_energy_kcal_mol=energy)


def read_bounded(path: Path, limit: int = OUTPUT_LIMIT) -> bytes:
    """Bound every installation and generated-file read before decoding."""
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ConditionalError("resource_limit", "Backend file exceeds byte limit")
    return raw


def verify_backend(
    root: str | Path | None, parameters: dict, deadline: float
) -> tuple[Path, dict]:
    """Admit only the independently executed original binaries, source and tables."""
    selected = root if root is not None else os.environ.get("REGSITE_RNASTRUCTURE")
    if not selected:
        raise ConditionalError(
            "backend_unavailable", "Supply the original RNAstructure root"
        )
    path = Path(selected).expanduser().resolve()
    pins = parameters["backend_pins"]
    if (path / "traceback-build.json").exists():
        raise ConditionalError("backend_identity", "Patched backends are not admitted")
    identities = {}
    for relative, expected in (
        ("exe/Fold", pins["fold_sha256"]),
        ("exe/efn2", pins["efn2_sha256"]),
        ("src/algorithm.cpp", pins["algorithm_cpp_sha256"]),
        ("ReadMe.txt", pins["readme_sha256"]),
        ("gpl.txt", pins["gpl_sha256"]),
    ):
        check_deadline(deadline)
        actual = digest(read_bounded(path / relative, 100_000_000))
        if actual != expected:
            raise ConditionalError(
                "backend_identity", "Original backend identity mismatch"
            )
        identities[relative] = actual
    tables = json.loads(
        files("regsite").joinpath("data/rnastructure-tables.json").read_bytes()
    )
    if digest(canonical_bytes(tables)) != pins["table_manifest_sha256"]:
        raise ConditionalError(
            "parameter_integrity", "Table manifest integrity mismatch"
        )
    for name, expected in tables.items():
        check_deadline(deadline)
        if digest(read_bounded(path / "data_tables" / name, 10_000_000)) != expected:
            raise ConditionalError("backend_identity", "RNA table identity mismatch")
    return path, dict(
        fold_sha256=identities["exe/Fold"],
        efn2_sha256=identities["exe/efn2"],
        table_manifest_sha256=pins["table_manifest_sha256"],
    )


def run_job(
    executable: Path, args: list[str], root: Path, timeout: float, job: dict
) -> None:
    """Drain bounded binary pipes and kill/reap exactly this child on any failure."""
    if timeout <= 0:
        raise ConditionalError("deadline_exceeded", "No time remains for backend job")
    stdout, stderr = bytearray(), bytearray()
    deadline = time.monotonic() + timeout
    try:
        with subprocess.Popen(
            [str(executable), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "DATAPATH": str(root / "data_tables"),
                "OMP_NUM_THREADS": "1",
                "LC_ALL": "C",
            },
        ) as process:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(
                        cast(IO[bytes], process.stdout), selectors.EVENT_READ, stdout
                    )
                    selector.register(
                        cast(IO[bytes], process.stderr), selectors.EVENT_READ, stderr
                    )
                    while selector.get_map():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(str(executable), timeout)
                        for key, _ in selector.select(remaining):
                            chunk = os.read(key.fd, 8192)
                            if not chunk:
                                selector.unregister(key.fileobj)
                            else:
                                key.data.extend(chunk)
                                if len(stdout) + len(stderr) > OUTPUT_LIMIT:
                                    raise ConditionalError(
                                        "resource_limit",
                                        "Backend output exceeds byte limit",
                                    )
                process.wait(timeout=max(0, deadline - time.monotonic()))
            finally:
                if process.poll() is None:
                    process.kill()
                job["exit_code"] = process.wait()
        if job["exit_code"] != 0:
            raise ConditionalError(
                "backend_failed", "Backend process exited unsuccessfully"
            )
        job["status"] = "ok"
    except subprocess.TimeoutExpired as exc:
        job["timed_out"] = True
        raise ConditionalError(
            "backend_timeout", "Backend process exceeded deadline"
        ) from exc
    except OSError as exc:
        raise ConditionalError(
            "backend_unavailable", "Backend process unavailable"
        ) from exc
    finally:
        job["stdout_sha256"], job["stderr_sha256"] = digest(stdout), digest(stderr)


def new_state(name: str, sequence: str, demands: dict | None) -> dict:
    """Create a complete state roster before any job starts."""
    return dict(
        id=name,
        status="not_run",
        reasons=[],
        sequence_sha256=digest(sequence.encode("ascii")),
        constraint_sha256=None if demands is None else digest(canonical_bytes(demands)),
        structure=None,
        pairs=None,
        fold_energy_kcal_mol=None,
        efn2_energy_kcal_mol=None,
        jobs=[],
    )


def fold_state(
    root: Path,
    sequence: str,
    demands: dict | None,
    state: dict,
    settings: dict,
    deadline: float,
) -> None:
    """Populate a state incrementally; a failed efn2 preserves its validated CT."""
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not PROCESS_LOCK.acquire(timeout=max(0, remaining)):
        raise ConditionalError(
            "deadline_exceeded", "Request deadline exhausted waiting for backend"
        )
    try:
        check_deadline(deadline)
        with TemporaryDirectory(prefix="regsite-conditional-") as temporary:
            scratch = Path(temporary)
            fasta, ct, constraint, energy = [
                scratch / name
                for name in ("input.fa", "output.ct", "constraint.con", "energy.txt")
            ]
            fasta.write_bytes(f">id\n{sequence}\n".encode("ascii"))
            fold_args = [str(fasta), str(ct), "--MFE", "--loop", "30"]
            if demands is not None:
                constraint.write_bytes(constraint_text(demands).encode("ascii"))
                fold_args.extend(("--constraint", str(constraint)))
            flags = ["--temperature", "310.15", "--alphabet", "rna"]
            for program, args in (
                ("Fold", fold_args),
                ("efn2", [str(ct), str(energy), "--simple", "--ne"]),
            ):
                check_deadline(deadline)
                job = dict(
                    program=program,
                    status="failed",
                    exit_code=None,
                    timed_out=False,
                    stdout_sha256=None,
                    stderr_sha256=None,
                )
                state["jobs"].append(job)
                run_job(
                    root / "exe" / program,
                    args + flags,
                    root,
                    min(settings["seconds_per_job"], deadline - time.monotonic()),
                    job,
                )
                check_deadline(deadline)
                if program == "Fold":
                    state.update(parse_ct(read_bounded(ct), sequence, demands))
                else:
                    text = read_bounded(energy).decode("ascii")
                    match = re.fullmatch(
                        r"\s*Structure:\s*1\s+Energy\s*=\s*(\S+)\s*", text
                    )
                    if match is None:
                        raise ConditionalError(
                            "invalid_energy", "Expected exactly one efn2 energy"
                        )
                    value = float(match[1])
                    if not math.isfinite(value):
                        raise ConditionalError(
                            "invalid_energy", "efn2 energy is nonfinite"
                        )
                    state["efn2_energy_kcal_mol"] = value
            state["status"] = "ok"
    finally:
        PROCESS_LOCK.release()
