"""Canonical constrained RNAstructure Fold reference for specified-structure states.

GPL-3.0-or-later; see NOTICE. RNAstructure 6.6 (GPL-2.0-only) is a separately
installed program reached only through files and standalone processes; no engine
code is copied, linked or bundled.

The contract writes exact one-based Fold constraint files for forced canonical
pairs and forced-unpaired positions, runs the original Fold and efn2 executables
one process at a time under fixed job and wall-time budgets, and audits every
returned CT against its request. Requests the engine would silently weaken are
refused before execution. Results are structural feasibility evidence only: no
ligand binding, occupancy, kinetics, pseudoknot or biological-accuracy claim.
"""

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

SCHEMA_VERSION = "riboswitch-canonical-constraint-fixtures-1"
RECEIPT_VERSION = "riboswitch-canonical-constraint-receipt-1"
FIXTURES = Path(__file__).with_name("canonical-fixtures.json")
CANONICAL_PAIRS = frozenset({"AU", "UA", "GC", "CG", "GU", "UG"})
MIN_HAIRPIN_LOOP = 3
MAX_SEQUENCE_NT = 200
MAX_TEXT_BYTES = 1_000_000
ENERGY_TOLERANCE = 1e-9
TEMPERATURE_K = "310.15"
FOLD_FLAGS = (
    "--MFE",
    "--loop",
    "30",
    "--temperature",
    TEMPERATURE_K,
    "--alphabet",
    "rna",
)
EFN2_FLAGS = ("--simple", "--ne", "--temperature", TEMPERATURE_K, "--alphabet", "rna")
CONSTRAINT_FLAG = ("--constraint", "constraint.con")
EFN2_ARGS = ("output.ct", "energy.txt", *EFN2_FLAGS)
VERSION_PATTERN = re.compile(r"\bVersion 6\.6\b")
CASE_ID = re.compile(r"[a-z][a-z0-9_]{0,63}")
COMMON_FIELDS = frozenset(
    {
        "id",
        "purpose",
        "sequence",
        "mode",
        "expected_status",
        "expected_pairs",
        "expected_error",
    }
)
MODE_FIELDS = {
    "unconstrained": frozenset(),
    "partial": frozenset({"forced_pairs", "forced_unpaired"}),
    "full": frozenset({"structure"}),
}
PIN_KEYS = frozenset(
    {
        "fold_sha256",
        "efn2_sha256",
        "table_manifest_sha256",
        "source_archive_sha256",
        "algorithm_cpp_sha256",
        "readme_sha256",
        "gpl_sha256",
    }
)
RELATION_KINDS = frozenset(
    {"same_structure_and_energy", "different_pairs", "energy_not_below"}
)
OK = "ok"
BACKEND_FAILED = "backend_failed"
CONSTRAINT_VIOLATED = "constraint_violated"
EVALUATION_FAILED = "evaluation_failed"
NOT_RUN = "not_run"
TIE_SELECTION = (
    "Fold --MFE returns one structure from RNAstructure's deterministic traceback; "
    "among equal-energy minima the traceback's choice is recorded, not proven unique."
)

Pair = tuple[int, int]
Executor = Callable[[list[str], Path, dict, float, IO[bytes], IO[bytes]], tuple]


class ContractError(ValueError):
    """A request the contract refuses instead of silently weakening it."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OutputError(ValueError):
    """Backend output that cannot be accepted as a valid result."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SetupError(RuntimeError):
    """Fixtures, installation or output directory are not admissible."""


@dataclass(frozen=True)
class Request:
    """A validated constraint request; positions are one-based and inclusive."""

    case_id: str
    sequence: str
    mode: str
    pairs: tuple[Pair, ...]
    unpaired: tuple[int, ...]


@dataclass(frozen=True)
class Limits:
    """Process count and wall-time bounds for one run."""

    max_jobs: int = 30
    job_seconds: float = 120.0
    total_seconds: float = 900.0


class Budget:
    """Counts processes and enforces one total wall-time deadline."""

    def __init__(self, limits: Limits, clock: Callable[[], float] = time.monotonic):
        self._limits = limits
        self._clock = clock
        self._deadline = clock() + limits.total_seconds
        self.jobs = 0

    def claim(self) -> float | None:
        """Reserve one process and return its timeout, or None when exhausted."""
        remaining = self._deadline - self._clock()
        if self.jobs >= self._limits.max_jobs or remaining <= 0:
            return None
        self.jobs += 1
        return min(self._limits.job_seconds, remaining)


@dataclass
class _Context:
    root: Path
    executor: Executor
    budget: Budget
    jobs: list = field(default_factory=list)


def has_crossing(pairs) -> bool:
    """Return whether any two pairs interleave (a pseudoknot)."""
    return any(a < c < b < d for a, b in pairs for c, d in pairs)


def _position(value, length: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError("invalid_position")
    if not 1 <= value <= length:
        raise ContractError("position_out_of_range")
    return value


def _positions(values, length: int) -> tuple[int, ...]:
    if not isinstance(values, list):
        raise ContractError("invalid_position_list")
    return tuple(_position(value, length) for value in values)


def _pairs(values, length: int) -> tuple[Pair, ...]:
    if not isinstance(values, list):
        raise ContractError("invalid_pair_list")
    pairs = []
    for value in values:
        if not isinstance(value, list) or len(value) != 2:
            raise ContractError("invalid_pair")
        i, j = (_position(item, length) for item in value)
        if i >= j:
            raise ContractError("pair_not_5prime_first")
        pairs.append((i, j))
    if len(set(pairs)) != len(pairs):
        raise ContractError("duplicate_pair")
    ends = [position for pair in pairs for position in pair]
    if len(set(ends)) != len(ends):
        raise ContractError("position_in_multiple_pairs")
    if has_crossing(pairs):
        raise ContractError("crossing_pairs")
    return tuple(pairs)


def parse_dot_bracket(structure, length: int) -> tuple[tuple[Pair, ...], tuple]:
    """Convert a full nested structure into forced pairs and forced-unpaired bases.

    Only ``(``, ``)`` and ``.`` are accepted; pseudoknot bracket families fail.
    """
    if not isinstance(structure, str):
        raise ContractError("invalid_structure")
    if set(structure) - set("()."):
        raise ContractError("unsupported_structure_symbol")
    if len(structure) != length:
        raise ContractError("structure_length_mismatch")
    stack, pairs = [], []
    for position, symbol in enumerate(structure, 1):
        if symbol == "(":
            stack.append(position)
        elif symbol == ")":
            if not stack:
                raise ContractError("unbalanced_structure")
            pairs.append((stack.pop(), position))
    if stack:
        raise ContractError("unbalanced_structure")
    unpaired = tuple(i for i, symbol in enumerate(structure, 1) if symbol == ".")
    return tuple(sorted(pairs)), unpaired


def build_request(case: dict) -> Request:
    """Validate one fixture case into an exact request or raise ContractError."""
    case_id = case.get("id")
    if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
        raise ContractError("invalid_id")
    sequence = case.get("sequence")
    if not isinstance(sequence, str) or not 1 <= len(sequence) <= MAX_SEQUENCE_NT:
        raise ContractError("invalid_sequence_length")
    if set(sequence) - set("ACGU"):
        raise ContractError("unsupported_base")
    mode = case.get("mode")
    if mode not in MODE_FIELDS:
        raise ContractError("invalid_mode")
    if set(case) - COMMON_FIELDS - MODE_FIELDS[mode]:
        raise ContractError("unexpected_field")
    if mode == "full":
        pairs, unpaired = parse_dot_bracket(case.get("structure"), len(sequence))
    elif mode == "partial":
        pairs = _pairs(case.get("forced_pairs", []), len(sequence))
        unpaired = _positions(case.get("forced_unpaired", []), len(sequence))
        if len(set(unpaired)) != len(unpaired):
            raise ContractError("duplicate_unpaired")
        if {i for pair in pairs for i in pair} & set(unpaired):
            raise ContractError("paired_and_unpaired")
    else:
        pairs, unpaired = (), ()
    for i, j in pairs:
        if sequence[i - 1] + sequence[j - 1] not in CANONICAL_PAIRS:
            raise ContractError("noncanonical_pair")
        if j - i - 1 < MIN_HAIRPIN_LOOP:
            raise ContractError("hairpin_too_short")
    return Request(
        case_id, sequence, mode, tuple(sorted(pairs)), tuple(sorted(unpaired))
    )


def constraint_text(request: Request) -> str | None:
    """Exact Fold constraint bytes; None means no --constraint flag at all."""
    if request.mode == "unconstrained":
        return None
    lines = [
        "DS:",
        "-1",
        "SS:",
        *map(str, request.unpaired),
        "-1",
        "Mod:",
        "-1",
        "Pairs:",
        *(f"{i} {j}" for i, j in request.pairs),
        "-1 -1",
        "FMN:",
        "-1",
        "Forbids:",
        "-1 -1",
    ]
    return "\n".join(lines) + "\n"


def fold_args(request: Request) -> tuple[str, ...]:
    """Exact Fold arguments, relative to the case directory."""
    constraint = CONSTRAINT_FLAG if request.mode != "unconstrained" else ()
    return ("input.fa", "output.ct", *FOLD_FLAGS, *constraint)


def dot_bracket(pairs, length: int) -> str:
    """Render nested one-based pairs as dot-bracket text."""
    symbols = ["."] * length
    for i, j in pairs:
        symbols[i - 1], symbols[j - 1] = "(", ")"
    return "".join(symbols)


def _finite(text: str, code: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise OutputError(code) from exc
    if not math.isfinite(value):
        raise OutputError(code)
    return value


def parse_ct(text: str, sequence: str) -> tuple[tuple[Pair, ...], float | None]:
    """Parse exactly one CT structure and check it against the request sequence.

    Returns one-based pairs and the header energy, or None when no energy is
    reported. Nonreciprocal, crossing or noncanonical output is rejected.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise OutputError("empty_ct")
    try:
        length = int(lines[0].split()[0])
    except ValueError as exc:
        raise OutputError("invalid_ct_header") from exc
    if length != len(sequence) or len(lines) != length + 1:
        raise OutputError("ct_shape_mismatch")
    match = re.search(r"\bENERGY\s*=\s*(\S+)", lines[0])
    energy = _finite(match.group(1), "invalid_ct_energy") if match else None
    bases, partner = [], {}
    for index, line in enumerate(lines[1:], 1):
        columns = line.split()
        if len(columns) != 6:
            raise OutputError("invalid_ct_row")
        try:
            number, mate = int(columns[0]), int(columns[4])
        except ValueError as exc:
            raise OutputError("invalid_ct_row") from exc
        if number != index or not 0 <= mate <= length or mate == index:
            raise OutputError("invalid_ct_row")
        bases.append(columns[1])
        partner[index] = mate
    if "".join(bases) != sequence:
        raise OutputError("ct_sequence_mismatch")
    if any(mate and partner[mate] != index for index, mate in partner.items()):
        raise OutputError("nonreciprocal_ct")
    pairs = tuple((i, j) for i, j in partner.items() if i < j)
    if has_crossing(pairs):
        raise OutputError("crossing_ct")
    if any(sequence[i - 1] + sequence[j - 1] not in CANONICAL_PAIRS for i, j in pairs):
        raise OutputError("noncanonical_ct")
    return pairs, energy


def parse_efn2(text: str) -> float:
    """Parse the single-structure efn2 simple-list energy."""
    lines = [line for line in text.splitlines() if line.strip()]
    pattern = r"\s*Structure:\s*1\s+Energy\s*=\s*(\S+)\s*"
    match = re.fullmatch(pattern, lines[0]) if len(lines) == 1 else None
    if not match:
        raise OutputError("invalid_efn2_output")
    return _finite(match.group(1), "invalid_efn2_energy")


def audit_constraints(request: Request, pairs) -> list[str]:
    """List every unmet demand; a full request must also match exactly."""
    present = set(pairs)
    paired = {i for pair in pairs for i in pair}
    violations = [
        f"missing_pair:{i}-{j}" for i, j in request.pairs if (i, j) not in present
    ]
    violations += [
        f"paired_forced_unpaired:{i}" for i in request.unpaired if i in paired
    ]
    if request.mode == "full":
        violations += [
            f"extra_pair:{i}-{j}" for i, j in pairs if (i, j) not in set(request.pairs)
        ]
    return violations


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    except FileNotFoundError:
        return None


def _read_text(path: Path) -> str | None:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_TEXT_BYTES + 1)
    except FileNotFoundError:
        return None
    if len(raw) > MAX_TEXT_BYTES:
        raise OutputError("output_too_large")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OutputError("output_not_utf8") from exc


def table_manifest_sha256(tables: dict) -> str:
    """Hash a name-to-SHA-256 table map as compact sorted JSON."""
    text = json.dumps(tables, sort_keys=True, separators=(",", ":"))
    return _sha256(text.encode())


def backend_identity(root: Path, archive: Path, pins: dict) -> dict:
    """Hash the installation, source archive and notices; refuse any pin mismatch."""
    paths = {
        "fold_sha256": root / "exe" / "Fold",
        "efn2_sha256": root / "exe" / "efn2",
        "algorithm_cpp_sha256": root / "src" / "algorithm.cpp",
        "readme_sha256": root / "ReadMe.txt",
        "gpl_sha256": root / "gpl.txt",
        "source_archive_sha256": archive,
    }
    actual = {key: _file_sha256(path) for key, path in paths.items()}
    tables = {
        path.name: _file_sha256(path)
        for path in sorted((root / "data_tables").glob("rna.*"))
    }
    actual["table_manifest_sha256"] = table_manifest_sha256(tables)
    mismatched = sorted(key for key in PIN_KEYS if actual[key] != pins[key])
    if mismatched:
        raise SetupError("backend pin mismatch: " + ", ".join(mismatched))
    return {
        "name": "RNAstructure",
        "licence": "GPL-2.0-only",
        "licence_notice": "ReadMe.txt: covered by the GNU GENERAL PUBLIC LICENSE "
        "Version 2 (see gpl.txt for the full license)",
        **dict(sorted(actual.items())),
        "table_count": len(tables),
        "tables": tables,
    }


def validate_fixtures(fixtures: dict, limits: Limits) -> list[Request]:
    """Check the fixed fixture list before any process can run."""
    if (
        not isinstance(fixtures, dict)
        or fixtures.get("schema_version") != SCHEMA_VERSION
    ):
        raise SetupError("unsupported fixture schema")
    pins = fixtures.get("backend_pins")
    if (
        not isinstance(pins, dict)
        or set(pins) != PIN_KEYS
        or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in pins.values()
        )
    ):
        raise SetupError("backend pins must be exactly the seven SHA-256 values")
    executed, rejected = fixtures.get("executed"), fixtures.get("rejected")
    relations = fixtures.get("relations")
    if not all(isinstance(item, list) for item in (executed, rejected, relations)):
        raise SetupError("executed, rejected and relations must be lists")
    if not executed or 2 + 2 * len(executed) > limits.max_jobs:
        raise SetupError("executed case count exceeds the process budget")
    requests = []
    for case in executed:
        if not isinstance(case, dict):
            raise SetupError("executed fixtures must be objects")
        try:
            request = build_request(case)
            if case.get("expected_pairs") is not None:
                _pairs(case["expected_pairs"], len(request.sequence))
        except ContractError as exc:
            raise SetupError(f"executed fixture is invalid: {exc.code}") from exc
        if case.get("expected_status") not in (OK, "not_ok"):
            raise SetupError("expected_status must be ok or not_ok")
        requests.append(request)
    for case in rejected:
        if not isinstance(case, dict) or not all(
            isinstance(case.get(key), str) for key in ("id", "expected_error")
        ):
            raise SetupError("rejected fixtures need string id and expected_error")
    ids = [case["id"] for case in executed + rejected]
    if len(set(ids)) != len(ids):
        raise SetupError("fixture ids must be unique")
    names = {request.case_id for request in requests}
    for relation in relations:
        cases = relation.get("cases") if isinstance(relation, dict) else None
        if (
            not isinstance(cases, list)
            or relation.get("kind") not in RELATION_KINDS
            or len(cases) != 2
            or not set(cases) <= names
        ):
            raise SetupError("relations need a known kind and two executed cases")
    return requests


def execute(
    command: list[str],
    cwd: Path,
    env: dict,
    timeout: float,
    stdout: IO[bytes],
    stderr: IO[bytes],
) -> tuple[str, int | None]:
    """Run one process without a shell, retries or inherited environment."""
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "timed_out", None
    except OSError:
        return "launch_failed", None
    return "exited", result.returncode


def _environment(root: Path) -> dict:
    return {
        "DATAPATH": str(root / "data_tables"),
        "OMP_NUM_THREADS": "1",
        "LC_ALL": "C",
    }


def _run_job(context: _Context, program: str, args, cwd: Path, case_id) -> dict | None:
    timeout = context.budget.claim()
    if timeout is None:
        return None
    stem = program.lower()
    command = [str(context.root / "exe" / program), *args]
    started = time.monotonic()
    with (
        (cwd / f"{stem}.stdout").open("xb") as out,
        (cwd / f"{stem}.stderr").open("xb") as err,
    ):
        outcome, exit_code = context.executor(
            command, cwd, _environment(context.root), timeout, out, err
        )
    record = {
        "index": len(context.jobs),
        "case": case_id,
        "program": program,
        "args": list(args),
        "timeout_seconds": timeout,
        "outcome": outcome,
        "exit_code": exit_code,
        "seconds": round(time.monotonic() - started, 3),
        "stdout_sha256": _file_sha256(cwd / f"{stem}.stdout"),
        "stderr_sha256": _file_sha256(cwd / f"{stem}.stderr"),
    }
    context.jobs.append(record)
    return record


def _job_failure(program: str, job: dict | None) -> str | None:
    if job is None:
        return "budget_exhausted"
    if job["outcome"] != "exited":
        return f"{program}_{job['outcome']}"
    if job["exit_code"] != 0:
        return f"{program}_exit_{job['exit_code']}"
    return None


def assess_fold(request: Request, job: dict | None, ct_path: Path) -> dict:
    """Classify the Fold stage from its process record and written CT."""
    failure = _job_failure("fold", job)
    if failure:
        return {
            "status": NOT_RUN if job is None else BACKEND_FAILED,
            "failure": failure,
        }
    try:
        text = _read_text(ct_path)
        if text is None:
            raise OutputError("missing_ct")
        pairs, energy = parse_ct(text, request.sequence)
    except OutputError as exc:
        return {"status": BACKEND_FAILED, "failure": exc.code}
    violations = audit_constraints(request, pairs)
    return {
        "status": CONSTRAINT_VIOLATED if violations else OK,
        "failure": CONSTRAINT_VIOLATED if violations else None,
        "violations": violations,
        "pairs": pairs,
        "fold_energy": energy,
    }


def assess_energy(
    job: dict | None, energy_path: Path
) -> tuple[float | None, str | None]:
    """Return the efn2 energy of the returned CT, or the reason it is missing."""
    failure = _job_failure("efn2", job)
    if failure:
        return None, failure
    try:
        text = _read_text(energy_path)
        if text is None:
            raise OutputError("missing_energy")
        return parse_efn2(text), None
    except OutputError as exc:
        return None, exc.code


def _consistency(fold_energy, efn2_energy) -> str | None:
    if efn2_energy is None:
        return None
    if fold_energy is None:
        return "fold_energy_absent"
    return "match" if abs(fold_energy - efn2_energy) <= ENERGY_TOLERANCE else "mismatch"


def _assess_case(request, case, directory, fold_job, efn2_job) -> dict:
    stage = assess_fold(request, fold_job, directory / "output.ct")
    status, pairs = stage["status"], stage.get("pairs")
    efn2_energy, efn2_failure = None, None
    if pairs is not None:
        efn2_energy, efn2_failure = assess_energy(efn2_job, directory / "energy.txt")
        if status == OK and efn2_failure:
            status = NOT_RUN if efn2_job is None else EVALUATION_FAILED
    consistency = _consistency(stage.get("fold_energy"), efn2_energy)
    expected_pairs = case.get("expected_pairs")
    if case["expected_status"] == OK:
        met = (
            status == OK
            and consistency != "mismatch"
            and (
                expected_pairs is None
                or sorted(map(list, pairs)) == sorted(expected_pairs)
            )
        )
    else:
        met = status in (BACKEND_FAILED, CONSTRAINT_VIOLATED)
    constraint = constraint_text(request)
    return {
        "id": request.case_id,
        "mode": request.mode,
        "sequence": request.sequence,
        "sequence_sha256": _sha256(request.sequence.encode()),
        "fasta_sha256": _file_sha256(directory / "input.fa"),
        "constraint_text": constraint,
        "constraint_sha256": None
        if constraint is None
        else _sha256(constraint.encode()),
        "forced_pairs": [list(pair) for pair in request.pairs],
        "forced_unpaired": list(request.unpaired),
        "fold_job": None if fold_job is None else fold_job["index"],
        "efn2_job": None if efn2_job is None else efn2_job["index"],
        "status": status,
        "failure": stage["failure"],
        "efn2_failure": efn2_failure,
        "violations": stage.get("violations", []),
        "ct_sha256": _file_sha256(directory / "output.ct"),
        "energy_sha256": _file_sha256(directory / "energy.txt"),
        "pairs": None if pairs is None else [list(pair) for pair in pairs],
        "dot_bracket": None
        if pairs is None
        else dot_bracket(pairs, len(request.sequence)),
        "fold_energy": stage.get("fold_energy"),
        "efn2_energy": efn2_energy,
        "energy_consistency": consistency,
        "expected_status": case["expected_status"],
        "expected_pairs": expected_pairs,
        "expectation_met": met,
    }


def evaluate_relation(relation: dict, cases: dict) -> dict:
    """Check one declared cross-case invariant; both cases must be ok."""
    first, second = (cases[name] for name in relation["cases"])
    evaluable = first["status"] == OK and second["status"] == OK
    holds = False
    if evaluable and relation["kind"] == "same_structure_and_energy":
        holds = all(
            first[key] == second[key] for key in ("pairs", "fold_energy", "efn2_energy")
        )
    elif evaluable and relation["kind"] == "different_pairs":
        holds = first["pairs"] != second["pairs"]
    elif evaluable:
        holds = first["efn2_energy"] >= second["efn2_energy"] - ENERGY_TOLERANCE
    return {
        "kind": relation["kind"],
        "cases": relation["cases"],
        "evaluable": evaluable,
        "holds": holds,
    }


def assess_rejected(case: dict) -> dict:
    """Confirm the contract refuses a case with its declared error code."""
    try:
        build_request(case)
        error = None
    except ContractError as exc:
        error = exc.code
    return {
        "id": case["id"],
        "expected_error": case["expected_error"],
        "error": error,
        "expectation_met": error == case["expected_error"],
    }


def _conclusions(fixtures: dict, cases: list) -> dict:
    by_id = {case["id"]: case for case in cases}
    rejected = [assess_rejected(case) for case in fixtures["rejected"]]
    relations = [evaluate_relation(item, by_id) for item in fixtures["relations"]]
    met = all(item["expectation_met"] for item in cases + rejected) and all(
        item["holds"] for item in relations
    )
    return {
        "cases": cases,
        "rejected": rejected,
        "relations": relations,
        "all_expectations_met": met,
    }


def _versions(context: _Context, directory: Path) -> dict:
    directory.mkdir()
    versions = {}
    for program in ("Fold", "efn2"):
        if _run_job(context, program, ("--version",), directory, None) is None:
            raise SetupError("process budget exhausted before version checks")
        lines = [
            line
            for stream in ("stdout", "stderr")
            for line in (directory / f"{program.lower()}.{stream}")
            .read_bytes()[:4096]
            .decode("utf-8", "replace")
            .splitlines()
        ]
        line = next(
            (item.strip() for item in lines if VERSION_PATTERN.search(item)), None
        )
        if line is None:
            raise SetupError(f"{program} is not RNAstructure 6.6")
        versions[program] = line
    return versions


def _run_case(context: _Context, request: Request, case: dict, directory: Path) -> dict:
    directory.mkdir(parents=True)
    (directory / "input.fa").write_text(f">{request.case_id}\n{request.sequence}\n")
    constraint = constraint_text(request)
    if constraint is not None:
        (directory / "constraint.con").write_text(constraint)
    fold_job = _run_job(context, "Fold", fold_args(request), directory, request.case_id)
    efn2_job = None
    if "pairs" in assess_fold(request, fold_job, directory / "output.ct"):
        efn2_job = _run_job(context, "efn2", EFN2_ARGS, directory, request.case_id)
    return _assess_case(request, case, directory, fold_job, efn2_job)


def run(
    fixtures_path: Path,
    root: Path,
    archive: Path,
    output: Path,
    executor: Executor = execute,
    limits: Limits | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """Execute the fixed fixtures once into a new output directory.

    Returns the receipt, also written exclusively as ``output/receipt.json``.
    """
    limits = limits or Limits()
    raw = fixtures_path.read_bytes()
    fixtures = json.loads(raw)
    requests = validate_fixtures(fixtures, limits)
    root = root.resolve()
    backend = backend_identity(root, archive, fixtures["backend_pins"])
    try:
        output.mkdir()
    except OSError as exc:
        raise SetupError("output directory must be new; parent must exist") from exc
    context = _Context(root, executor, Budget(limits, clock))
    backend["versions"] = _versions(context, output / "identity")
    cases = [
        _run_case(context, request, case, output / "cases" / request.case_id)
        for request, case in zip(requests, fixtures["executed"], strict=True)
    ]
    receipt = {
        "schema_version": RECEIPT_VERSION,
        "fixtures_sha256": _sha256(raw),
        "runner_sha256": _sha256(Path(__file__).read_bytes()),
        "executor": f"{executor.__module__}."
        + getattr(executor, "__qualname__", type(executor).__qualname__),
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.machine()}",
        "backend": backend,
        "settings": {
            "temperature_k": TEMPERATURE_K,
            "fold_flags": list(FOLD_FLAGS),
            "constraint_flag": list(CONSTRAINT_FLAG),
            "efn2_flags": list(EFN2_FLAGS),
            "environment": {**_environment(Path("<installation>")), "inherited": False},
            "tie_selection": TIE_SELECTION,
            "energy_tolerance_kcal_per_mol": ENERGY_TOLERANCE,
        },
        "limits": {
            "max_jobs": limits.max_jobs,
            "job_seconds": limits.job_seconds,
            "total_seconds": limits.total_seconds,
            "retries": 0,
        },
        "total_jobs": len(context.jobs),
        "jobs": context.jobs,
        **_conclusions(fixtures, cases),
    }
    with (output / "receipt.json").open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    return receipt


def reaudit(fixtures_path: Path, output: Path) -> list[str]:
    """Recompute every conclusion from stored outputs; return any discrepancies."""
    raw = fixtures_path.read_bytes()
    fixtures = json.loads(raw)
    requests = validate_fixtures(fixtures, Limits())
    receipt = json.loads((output / "receipt.json").read_text())
    try:
        problems = (
            [] if receipt["fixtures_sha256"] == _sha256(raw) else ["fixtures_sha256"]
        )
        jobs = receipt["jobs"]
        for job in jobs:
            case_id = job["case"]
            directory = (
                output / "identity" if case_id is None else output / "cases" / case_id
            )
            for stream in ("stdout", "stderr"):
                path = directory / f"{job['program'].lower()}.{stream}"
                if _file_sha256(path) != job[f"{stream}_sha256"]:
                    problems.append(f"job_{job['index']}_{stream}")
        recorded = {case["id"]: case for case in receipt["cases"]}
        cases = []
        for request, case in zip(requests, fixtures["executed"], strict=True):
            prior = recorded[request.case_id]
            fold_job = None if prior["fold_job"] is None else jobs[prior["fold_job"]]
            efn2_job = None if prior["efn2_job"] is None else jobs[prior["efn2_job"]]
            if fold_job is not None and fold_job["args"] != list(fold_args(request)):
                problems.append(f"job_{fold_job['index']}_args")
            if efn2_job is not None and efn2_job["args"] != list(EFN2_ARGS):
                problems.append(f"job_{efn2_job['index']}_args")
            directory = output / "cases" / request.case_id
            cases.append(_assess_case(request, case, directory, fold_job, efn2_job))
        derived = _conclusions(fixtures, cases)
        problems += [key for key, value in derived.items() if receipt[key] != value]
    except (KeyError, TypeError, IndexError):
        return ["malformed_receipt"]
    return problems


def main(argv=None) -> int:
    """Command-line entry point; exit 0 met, 1 unmet/discrepant, 2 setup error."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="execute the fixed fixtures once")
    run_parser.add_argument("--rnastructure", type=Path, required=True)
    run_parser.add_argument("--source-archive", type=Path, required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    audit_parser = commands.add_parser("reaudit", help="recheck stored outputs offline")
    audit_parser.add_argument("--output", type=Path, required=True)
    audit_parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            receipt = run(
                args.fixtures, args.rnastructure, args.source_archive, args.output
            )
            summary = {
                "all_expectations_met": receipt["all_expectations_met"],
                "total_jobs": receipt["total_jobs"],
                "statuses": {case["id"]: case["status"] for case in receipt["cases"]},
            }
            print(json.dumps(summary, indent=2))
            return 0 if receipt["all_expectations_met"] else 1
        problems = reaudit(args.fixtures, args.output)
        print(json.dumps({"reproduced": not problems, "problems": problems}, indent=2))
        return 1 if problems else 0
    except (SetupError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
