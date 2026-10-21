"""Run explicit calculator requests offline with bounded resources and receipts.

Each job runs one fixed installed calculator entry point on caller-authored
request bytes. Native outputs stay opaque. See
docs/validation/offline-calculator-jobs.md for the contract and trust limits.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import marshal
import math
import os
import platform
import re
import secrets
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.resources import files
from typing import IO, Any, cast

import regsite
from regsite.backend import RnaStructure
from regsite.conditional import PARAMETER_SHA256
from regsite.conditional_backend import verify_backend
from regsite.conditional_math import ConditionalError
from regsite.profiles import PROFILES
from regsite.structures import BackendError

MANIFEST_VERSION = "calculator-job-manifest-1"
CAMPAIGN_VERSION = "calculator-job-campaign-1"
LAUNCH_VERSION = "calculator-job-launch-1"
RECEIPT_VERSION = "calculator-job-receipt-1"
SUMMARY_VERSION = "calculator-job-summary-1"
KINDS = ("rbs", "promoter", "compare", "transcript", "conditional")
MAX_MANIFEST_BYTES = 1_048_576
MAX_RECORD_BYTES = 1_048_576
MAX_REQUEST_BYTES = 4_000_000
MAX_CACHE_BYTES = 67_108_864
MAX_JOBS = 256
MAX_ATTEMPTS = 8
MAX_PATH = 1024
CHUNK_BYTES = 65_536
POLL_SECONDS = 0.05
# Owned process-group leader. It blocks on a pipe held by the runner (EOF if the
# runner dies) and is reaped only after the final group kill, so the group ID
# cannot be recycled while the runner may still signal it.
ANCHOR = ("-I", "-S", "-c", "import os; os.read(0, 1)")
TERMINATION_GRACE_SECONDS = 2.0
LIMITS = {
    "seconds_per_job": 3_600,
    "seconds_total": 86_400,
    "stdout_bytes_per_job": 134_217_728,
    "stderr_bytes_per_job": 1_048_576,
    "output_bytes_total": 17_179_869_184,
}
SECONDS_LIMITS = ("seconds_per_job", "seconds_total")
# Fixed interpreter arguments per kind. regsite.cli and regsite.promoter_cli have
# no main guard: RBS runs the package entry module, Promoter a fixed call.
ENTRY_POINTS = {
    "rbs": ("-m", "regsite"),
    "promoter": (
        "-c",
        "from regsite.promoter_cli import main; raise SystemExit(main())",
    ),
    "compare": ("-m", "regsite.paired_cli"),
    "transcript": ("-m", "regsite.transcript_cli"),
    "conditional": ("-m", "regsite.conditional_cli"),
}
SECONDS = "seconds"
OPTIONS: dict[str, dict[str, tuple[str, ...] | str]] = {
    "rbs": {
        "profile": tuple(profile.name for profile in PROFILES),
        "seconds_per_record": SECONDS,
    },
    "promoter": {
        "calibration": ("ecoli_mg1655", "in_vitro"),
        "states": ("selected", "all"),
        "seconds_per_record": SECONDS,
        "seconds_per_batch": SECONDS,
    },
    "compare": {},
    "transcript": {},
    "conditional": {},
}
BACKEND = {
    "rbs": (True,),
    "promoter": (False,),
    "compare": (False, True),
    "transcript": (False, True),
    "conditional": (False, True),
}
EXIT_OUTCOMES = {0: "succeeded", 1: "partial", 2: "refused"}
TERMINAL = (
    "succeeded",
    "partial",
    "refused",
    "abnormal_exit",
    "timed_out",
    "output_limit",
)
UNFINISHED = (
    "interrupted",
    "campaign_deadline",
    "launch_failed",
    "storage_error",
    "runtime_changed",
)
STATES = (*TERMINAL, "attempts_exhausted", "unfinished", "unstarted", "corrupted")
STOP_REASONS = {
    "interrupted": "signal",
    "campaign_deadline": "campaign_deadline",
    "launch_failed": "launch_failed",
    "storage_error": "storage_error",
    "runtime_changed": "runtime_changed",
}
TOP_FILES = {"lock", "manifest.json", "campaign.json", "summary.json", "jobs"}
ATTEMPT_FILES = {"stdout", "stderr", "launch.json", "receipt.json"}
# Outcomes whose stop may follow a capped capture or discard shutdown output.
TRUNCATABLE = (
    "output_limit",
    "timed_out",
    "interrupted",
    "campaign_deadline",
    "storage_error",
    "runtime_changed",
)
PYTHON_KEYS = {
    "implementation",
    "version",
    "cache_tag",
    "platform",
    "machine",
    "executable_sha256",
}
PACKAGE_DIR = os.path.dirname(os.path.abspath(regsite.__file__))
END = r"(?![\s\S])"
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}" + END
PATH_PATTERN = (
    r"^(?!(?:\.|\.\.)(?:/|$))[A-Za-z0-9._-]{1,255}"
    r"(?:/(?!(?:\.|\.\.)(?:/|$))[A-Za-z0-9._-]{1,255})*" + END
)
SHA_PATTERN = r"^[0-9a-f]{64}" + END


class JobError(ValueError):
    """Stable, path-free refusal code suitable for deterministic JSON output."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise JobError(code)


def _matches(value: Any, pattern: str) -> bool:
    return isinstance(value, str) and re.search(pattern, value) is not None


def _object(value: Any, keys: set[str], code: str) -> None:
    _require(type(value) is dict and set(value) == keys, code)


def _integer(value: Any) -> bool:
    return type(value) is int


def _finite(value: Any) -> bool:
    """Accept any JSON integer or finite float without converting the integer."""
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _check_time(deadline: float | None) -> None:
    _require(deadline is None or time.monotonic() < deadline, "campaign_deadline")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    value: dict = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _constant(_: str) -> None:
    raise JobError("nonfinite_json")


def _float(text: str) -> float:
    value = float(text)
    _require(math.isfinite(value), "nonfinite_json")
    return value


def _decode(raw: bytes) -> Any:
    """Strict UTF-8 JSON without BOM, duplicate keys or nonfinite numbers."""
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_float,
        )
    except JobError:
        raise
    except (ValueError, RecursionError) as error:
        raise JobError("malformed_json") from error


def _encode(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def _limits(value: Any) -> None:
    _object(value, set(LIMITS), "limits")
    for name, ceiling in LIMITS.items():
        number = value[name]
        valid = _finite(number) if name in SECONDS_LIMITS else _integer(number)
        _require(valid and 0 < number <= ceiling, "limits")
    _require(
        value["output_bytes_total"]
        >= value["stdout_bytes_per_job"] + value["stderr_bytes_per_job"],
        "limits",
    )


def _options(kind: str, value: Any) -> None:
    allowed = OPTIONS[kind]
    _require(type(value) is dict and set(value) <= set(allowed), "options")
    for name, item in value.items():
        rule = allowed[name]
        valid = _finite(item) and item > 0 if rule == SECONDS else item in rule
        _require(valid, "options")


def validate_manifest(value: Any) -> None:
    """Validate the strict manifest structure, limits and per-kind whitelist."""
    _object(value, {"schema_version", "limits", "jobs"}, "manifest_keys")
    _require(value["schema_version"] == MANIFEST_VERSION, "schema_version")
    _limits(value["limits"])
    jobs = value["jobs"]
    _require(type(jobs) is list and 1 <= len(jobs) <= MAX_JOBS, "jobs_count")
    seen: set[str] = set()
    for job in jobs:
        _object(job, {"id", "kind", "request", "backend", "options"}, "job_keys")
        _require(_matches(job["id"], ID_PATTERN), "job_id")
        folded = unicodedata.normalize("NFC", job["id"]).casefold()
        _require(folded not in seen, "duplicate_job_id")
        seen.add(folded)
        _require(type(job["kind"]) is str and job["kind"] in KINDS, "kind")
        request = job["request"]
        _object(request, {"path", "sha256"}, "request_keys")
        _require(
            _matches(request["path"], PATH_PATTERN)
            and len(request["path"]) <= MAX_PATH,
            "request_path",
        )
        _require(_matches(request["sha256"], SHA_PATTERN), "sha256")
        _require(
            type(job["backend"]) is bool and job["backend"] in BACKEND[job["kind"]],
            "backend_flag",
        )
        _options(job["kind"], job["options"])


def command_template(job: dict) -> list[str]:
    """Return the recorded argv with interpreter/backend placeholders."""
    argv = ["{python}", "-P", "-s", *ENTRY_POINTS[job["kind"]], "-"]
    if job["kind"] != "conditional":
        argv += ["--format", "json"]
    if job["backend"]:
        argv += ["--backend-root", "{backend_root}"]
    for name in sorted(job["options"]):
        item = job["options"][name]
        argv += [
            "--" + name.replace("_", "-"),
            item if type(item) is str else repr(item),
        ]
    return argv


def _parts(path: Any, code: str) -> list[str]:
    _require(
        isinstance(path, str)
        and path.startswith("/")
        and not any(c in path for c in ("\\", "\0", ":")),
        code,
    )
    parts = path.split("/")[1:]
    _require(all(part not in ("", ".", "..") for part in parts), code)
    return parts


@contextmanager
def _directory(parts: Sequence[str], base: int | None = None) -> Iterator[int]:
    """Open each directory separately; never follow a symlink component."""
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY) if base is None else os.dup(base)
    try:
        for part in parts:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _chunks(parent: int, name: str, limit: int, prefix: str) -> Iterator[bytes]:
    """Yield a regular file's bytes; refuse links, special files and excess."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    except OSError as error:
        raise JobError(prefix + "_unavailable") from error
    try:
        _require(stat.S_ISREG(os.fstat(fd).st_mode), prefix + "_unavailable")
        size = 0
        while True:
            try:
                chunk = os.read(fd, min(CHUNK_BYTES, limit + 1 - size))
            except OSError as error:
                raise JobError(prefix + "_unavailable") from error
            if not chunk:
                return
            size += len(chunk)
            _require(size <= limit, prefix + "_too_large")
            yield chunk
    finally:
        os.close(fd)


def _read(parent: int, name: str, limit: int, prefix: str) -> bytes:
    return b"".join(_chunks(parent, name, limit, prefix))


def _digest(parent: int, name: str, limit: int) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    for chunk in _chunks(parent, name, limit, "artifact"):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def _create(parent: int, name: str) -> int:
    return os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
    )


def _publish(parent: int, name: str, data: bytes, replace: bool = False) -> None:
    """Publish complete fsynced bytes atomically; only replace when asked."""
    temporary = ".tmp-" + secrets.token_hex(16)
    fd = _create(parent, temporary)
    try:
        try:
            _write_all(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        if replace:
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        else:
            os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
    finally:
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass


def _names(fd: int) -> set[str]:
    return {name for name in os.listdir(fd) if not name.startswith(".tmp-")}


def load_manifest(path: str) -> tuple[dict, bytes]:
    """Read and validate a manifest given by an absolute symlink-free path."""
    parts = _parts(path, "manifest_path")
    try:
        with _directory(parts[:-1]) as parent:
            raw = _read(parent, parts[-1], MAX_MANIFEST_BYTES, "manifest")
    except OSError as error:
        raise JobError("manifest_unavailable") from error
    value = _decode(raw)
    validate_manifest(value)
    return value, raw


def _load_requests(manifest_path: str, manifest: dict) -> dict[str, bytes]:
    """Read every declared request relative to the manifest; check its hash."""
    requests = {}
    try:
        with _directory(manifest_path.split("/")[1:-1]) as root:
            for job in manifest["jobs"]:
                parts = job["request"]["path"].split("/")
                try:
                    with _directory(parts[:-1], root) as parent:
                        raw = _read(parent, parts[-1], MAX_REQUEST_BYTES, "request")
                except OSError as error:
                    raise JobError("request_unavailable") from error
                _require(_sha256(raw) == job["request"]["sha256"], "request_mismatch")
                requests[job["id"]] = raw
    except OSError as error:
        raise JobError("manifest_unavailable") from error
    return requests


def _folded(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _output_parts(
    output_dir: str, manifest_path: str, manifest: dict, allow_repository: bool
) -> list[str]:
    """Refuse output paths that hold inputs or sit inside a Git working tree."""
    parts = _parts(output_dir, "output_path")
    base = manifest_path.rsplit("/", 1)[0]
    inputs = [manifest_path] + [
        base + "/" + job["request"]["path"] for job in manifest["jobs"]
    ]
    output = _folded(output_dir)
    _require(
        not any(
            _folded(path) == output or _folded(path).startswith(output + "/")
            for path in inputs
        ),
        "output_input_collision",
    )
    if not allow_repository:
        try:
            _require(not _inside_repository(parts[:-1]), "output_in_repository")
        except OSError as error:
            raise JobError("output_parent_unavailable") from error
    return parts


def _inside_repository(parts: Sequence[str]) -> bool:
    """Check each ancestor for a .git entry without following symlinks."""
    for depth in range(len(parts) + 1):
        with _directory(parts[:depth]) as fd:
            try:
                os.stat(".git", dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            return True
    return False


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_accepted(data: bytes, info: os.stat_result, source: bytes) -> bool:
    """Mirror importlib's acceptance of a cached .pyc for this source."""
    if len(data) < 16 or data[:4] != importlib.util.MAGIC_NUMBER:
        return False
    flags = int.from_bytes(data[4:8], "little")
    if flags & ~0b11:
        return False
    if flags & 0b1:
        return not flags & 0b10 or data[8:16] == importlib.util.source_hash(source)
    stamp = (int(info.st_mtime) & 0xFFFFFFFF, info.st_size & 0xFFFFFFFF)
    return data[8:16] == b"".join(value.to_bytes(4, "little") for value in stamp)


_EQUIVALENT: dict[tuple[str, str, int], bool] = {}


def _read_cache(cache: str) -> bytes | None:
    """Read a cache that exists without blocking or following a final symlink.

    A missing cache or cache directory is None. Anything Python might read but
    this cannot verify (FIFO, directory, symlink, oversized) refuses.
    """
    directory, name = os.path.split(cache)
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise JobError("bytecode_unavailable") from error
    try:
        try:
            os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        return _read(fd, name, MAX_CACHE_BYTES, "bytecode")
    finally:
        os.close(fd)


def _check_bytecode(path: str, source: bytes) -> None:
    """Refuse a cache import would accept unless its code equals the source's."""
    directory, name = os.path.split(path)
    default = os.path.join(
        directory, "__pycache__", f"{name[:-3]}.{sys.implementation.cache_tag}.pyc"
    )
    info = os.stat(path)
    for cache, optimize in {
        (default, 0),
        (importlib.util.cache_from_source(path), sys.flags.optimize),
    }:
        data = _read_cache(cache)
        if data is None or not _cache_accepted(data, info, source):
            continue
        key = (_sha256(source), _sha256(data), optimize)
        if key not in _EQUIVALENT:
            try:
                cached = marshal.loads(data[16:])
            except (EOFError, ValueError, TypeError):
                cached = None
            _EQUIVALENT[key] = cached == compile(
                source, path, "exec", dont_inherit=True, optimize=optimize
            )
        _require(_EQUIVALENT[key], "stale_bytecode")


def code_fingerprint(directory: str, deadline: float | None = None) -> dict:
    """Hash every regular package file except __pycache__; refuse other types.

    Caches that Python would accept must hold code equal to compiling their
    source, so the source hash also binds the bytecode actually executed.
    """
    rows = []
    try:
        for current, directories, names in os.walk(directory):
            directories[:] = sorted(d for d in directories if d != "__pycache__")
            for name in [*directories, *names]:
                _check_time(deadline)
                path = os.path.join(current, name)
                mode = os.lstat(path).st_mode
                if name in directories:
                    _require(stat.S_ISDIR(mode), "runtime_identity")
                    continue
                _require(stat.S_ISREG(mode), "runtime_identity")
                with open(path, "rb") as stream:
                    data = stream.read()
                if name.endswith(".py"):
                    _check_bytecode(path, data)
                relative = os.path.relpath(path, directory).replace(os.sep, "/")
                rows.append(f"{relative}\0{_sha256(data)}\n")
    except OSError as error:
        raise JobError("runtime_identity") from error
    _require(bool(rows), "runtime_identity")
    return {
        "sha256": _sha256("".join(sorted(rows)).encode()),
        "files": len(rows),
    }


def runtime_identity(deadline: float | None = None) -> dict:
    """Identify the installed regsite code/data and the running interpreter."""
    executable = sys.executable
    _require(bool(executable) and os.path.isabs(executable), "runtime_identity")
    try:
        executable_sha256 = _file_sha256(os.path.realpath(executable))
    except OSError as error:
        raise JobError("runtime_identity") from error
    return {
        "regsite_version": regsite.__version__,
        "code": code_fingerprint(PACKAGE_DIR, deadline),
        "python": {
            "implementation": sys.implementation.name,
            "version": sys.version,
            "cache_tag": sys.implementation.cache_tag,
            "platform": sys.platform,
            "machine": platform.machine(),
            "executable_sha256": executable_sha256,
        },
    }


def backend_identity(
    manifest: dict, backend_root: str | None, deadline: float | None = None
) -> dict:
    """Reuse the unchanged RNAstructure and conditional exact-original verifiers.

    The deadline is checked between verifier steps and passed to the conditional
    verifier; one RnaStructure.open step is bounded only by its own timeouts.
    """
    used = [job["kind"] for job in manifest["jobs"] if job["backend"]]
    _require(backend_root is not None or not used, "backend_root_required")
    _require(backend_root is None or bool(used), "backend_root_unused")
    identity: dict[str, dict | None] = {
        "rnastructure": None,
        "conditional_original": None,
    }
    if backend_root is None:
        return identity
    _require(os.path.isabs(backend_root), "backend_root_path")
    limit = time.monotonic() + 120 if deadline is None else deadline
    try:
        if any(kind != "conditional" for kind in used):
            _check_time(deadline)
            identity["rnastructure"] = RnaStructure.open(backend_root).identity
        if "conditional" in used:
            _check_time(deadline)
            raw = (
                files("regsite")
                .joinpath("data/conditional-parameters-1.json")
                .read_bytes()
            )
            _require(_sha256(raw) == PARAMETER_SHA256, "backend_identity")
            identity["conditional_original"] = verify_backend(
                backend_root, json.loads(raw), min(limit, time.monotonic() + 120)
            )[1]
    except (BackendError, ConditionalError, OSError) as error:
        _check_time(deadline)
        raise JobError("backend_identity") from error
    return identity


def _identity(
    manifest: dict, backend_root: str | None, deadline: float | None = None
) -> dict:
    return {
        "runtime": runtime_identity(deadline),
        "backend": backend_identity(manifest, backend_root, deadline),
    }


def _environment() -> dict[str, str]:
    return {
        "PATH": "/bin:/usr/bin",
        "PYTHONPATH": os.path.dirname(PACKAGE_DIR),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "OMP_NUM_THREADS": "1",
        "TMPDIR": tempfile.gettempdir(),
    }


class _Signals:
    """Turn SIGINT/SIGTERM/SIGHUP into a flag polled by the supervisor."""

    NAMES = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)

    def __init__(self) -> None:
        self.received: int | None = None
        self.previous: dict = {}

    def __enter__(self) -> _Signals:
        _require(
            threading.current_thread() is threading.main_thread(),
            "main_thread_required",
        )
        for name in self.NAMES:
            self.previous[name] = signal.signal(name, self._handle)
        return self

    def _handle(self, number: int, _frame: object) -> None:
        self.received = number

    def __exit__(self, *_: object) -> None:
        for name, handler in self.previous.items():
            signal.signal(name, handler)


class _Capture:
    """Stream one child pipe to its file up to a byte cap, hashing what is kept."""

    def __init__(self, fd: int, limit: int, path: str) -> None:
        self.fd, self.limit, self.path = fd, limit, path
        self.size, self.truncated = 0, False
        self.digest = hashlib.sha256()

    def accept(self, chunk: bytes) -> bool:
        """Store up to the cap, accounting each successful (possibly short) write."""
        room = self.limit - self.size
        view = memoryview(chunk)[:room]
        while view:
            written = os.write(self.fd, view)
            self.digest.update(view[:written])
            self.size += written
            view = view[written:]
        if len(chunk) > room:
            self.truncated = True
        return len(chunk) <= room

    def record(self) -> dict:
        return {
            "path": self.path,
            "sha256": self.digest.hexdigest(),
            "bytes": self.size,
            "truncated": self.truncated,
        }


def _signal_group(pgid: int, number: int) -> None:
    try:
        os.killpg(pgid, number)
    except (ProcessLookupError, PermissionError):
        # Gone, or (macOS) only an unreaped/foreign member remains.
        pass


def _read_ready(selector: selectors.BaseSelector, timeout: float) -> bool:
    """Read each ready pipe once; return False if a capture exceeded its cap."""
    within = True
    for key, _ in selector.select(timeout):
        chunk = os.read(key.fd, CHUNK_BYTES)
        if not chunk:
            selector.unregister(key.fileobj)
        elif not key.data.accept(chunk):
            within = False
    return within


def _drain(
    selector: selectors.BaseSelector,
    process: subprocess.Popen | None,
    until: float,
) -> None:
    """Keep capturing until EOF (or until process exits, if given) or until."""
    while time.monotonic() < until and (process is None or process.poll() is None):
        if not selector.get_map():
            if process is None:
                return
            time.sleep(POLL_SECONDS)
            continue
        _read_ready(selector, min(POLL_SECONDS, max(0.0, until - time.monotonic())))


def _stop(
    process: subprocess.Popen, pgid: int, selector: selectors.BaseSelector
) -> bool:
    """Terminate the group, capture shutdown output and reap the calculator.

    Returns False if storing drained output failed. Termination and reaping
    happen regardless; the unreaped anchor keeps pgid owned throughout.
    """
    stored = True
    try:
        if process.poll() is None:
            _signal_group(pgid, signal.SIGTERM)
            _drain(selector, process, time.monotonic() + TERMINATION_GRACE_SECONDS)
    except OSError:
        stored = False
    _signal_group(pgid, signal.SIGKILL)
    process.wait()
    if stored:
        try:
            _drain(selector, None, time.monotonic() + TERMINATION_GRACE_SECONDS)
        except OSError:
            stored = False
    cast(IO[bytes], process.stdout).close()
    cast(IO[bytes], process.stderr).close()
    return stored


def _pump(
    process: subprocess.Popen,
    pgid: int,
    selector: selectors.BaseSelector,
    deadline: float,
    signals: _Signals,
) -> str | None:
    """Capture both pipes until exit and EOF; return a stop reason or None."""
    exited = False
    while selector.get_map() or not exited:
        if signals.received is not None:
            return "interrupted"
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "deadline"
        if not exited and process.poll() is not None:
            exited = True
            _signal_group(pgid, signal.SIGKILL)
        if not selector.get_map():
            time.sleep(min(POLL_SECONDS, remaining))
            continue
        if not _read_ready(selector, min(POLL_SECONDS, remaining)):
            return "output_limit"
    return None


@dataclass
class _JobState:
    """Verified on-disk state of one job's attempts."""

    attempts: int = 0
    abandoned: int = 0
    used: int = 0
    last: dict | None = None
    pids: list[int] = field(default_factory=list)
    error: str | None = None

    @property
    def state(self) -> str:
        if self.error is not None:
            return "corrupted"
        if self.last is not None and self.last["terminal"]:
            return self.last["outcome"]
        if self.attempts >= MAX_ATTEMPTS:
            return "attempts_exhausted"
        return "unfinished" if self.attempts else "unstarted"

    def record(self, receipt: dict | None, used: int) -> None:
        self.attempts += 1
        self.abandoned += receipt is None
        self.used += used
        self.last = receipt

    def row(self, job: dict) -> dict:
        last = self.last
        return {
            "id": job["id"],
            "kind": job["kind"],
            "state": self.state,
            "attempts": self.attempts,
            "receipt": None
            if last is None
            else f"jobs/{job['id']}/attempt-{last['attempt']:04d}/receipt.json",
            "exit_code": None if last is None else last["exit_code"],
            "stdout": None
            if last is None
            else {key: last["stdout"][key] for key in ("path", "sha256", "bytes")},
            "error": self.error,
        }


def _stream_ok(value: Any, path: str, limit: int) -> bool:
    return (
        type(value) is dict
        and set(value) == {"path", "sha256", "bytes", "truncated"}
        and value["path"] == path
        and _matches(value["sha256"], SHA_PATTERN)
        and _integer(value["bytes"])
        and 0 <= value["bytes"] <= limit
        and type(value["truncated"]) is bool
    )


def _exit_ok(receipt: dict) -> bool:
    code, number, outcome = receipt["exit_code"], receipt["signal"], receipt["outcome"]
    if not (
        (code is None or (_integer(code) and code >= 0))
        and (number is None or (_integer(number) and number > 0))
        and (code is None or number is None)
    ):
        return False
    truncated = receipt["stdout"]["truncated"] or receipt["stderr"]["truncated"]
    if outcome == "output_limit":
        return truncated
    if truncated and outcome not in TRUNCATABLE:
        return False
    if outcome in EXIT_OUTCOMES.values():
        return EXIT_OUTCOMES.get(code) == outcome  # type: ignore[arg-type]
    if outcome == "abnormal_exit":
        return number is not None or (code is not None and code not in EXIT_OUTCOMES)
    if outcome == "launch_failed":
        return (
            code is None
            and number is None
            and receipt["stdout"]["bytes"] == receipt["stderr"]["bytes"] == 0
        )
    return True


def _check_receipt(
    receipt: Any, job: dict, number: int, campaign: str, limits: dict, request: int
) -> None:
    base = f"jobs/{job['id']}/"
    attempt = f"{base}attempt-{number:04d}/"
    _object(
        receipt,
        {
            "schema_version",
            "campaign_sha256",
            "job_id",
            "kind",
            "attempt",
            "request",
            "argv",
            "outcome",
            "terminal",
            "exit_code",
            "signal",
            "elapsed_seconds",
            "stdout",
            "stderr",
        },
        "receipt_invalid",
    )
    _require(
        receipt["schema_version"] == RECEIPT_VERSION
        and receipt["campaign_sha256"] == campaign
        and receipt["job_id"] == job["id"]
        and receipt["kind"] == job["kind"]
        and _integer(receipt["attempt"])
        and receipt["attempt"] == number
        and receipt["request"]
        == {
            "path": base + "request.json",
            "sha256": job["request"]["sha256"],
            "bytes": request,
        }
        and _integer(receipt["request"]["bytes"])
        and receipt["argv"] == command_template(job)
        and receipt["outcome"] in (*TERMINAL, *UNFINISHED)
        and receipt["terminal"] is (receipt["outcome"] in TERMINAL)
        and _finite(receipt["elapsed_seconds"])
        and receipt["elapsed_seconds"] >= 0
        and _stream_ok(
            receipt["stdout"], attempt + "stdout", limits["stdout_bytes_per_job"]
        )
        and _stream_ok(
            receipt["stderr"], attempt + "stderr", limits["stderr_bytes_per_job"]
        )
        and _exit_ok(receipt),
        "receipt_invalid",
    )


def _record(fd: int, name: str) -> Any:
    return _decode(_read(fd, name, MAX_RECORD_BYTES, "record"))


def _inspect_attempt(
    job_fd: int, job: dict, number: int, campaign: str, limits: dict, request: int
) -> tuple[dict | None, int, int | None]:
    """Return (verified receipt or None, stored output bytes, launch PID)."""
    with _directory([f"attempt-{number:04d}"], job_fd) as fd:
        names = _names(fd)
        _require(names <= ATTEMPT_FILES, "attempt_layout")
        pid = None
        if "launch.json" in names:
            launch = _record(fd, "launch.json")
            _object(launch, {"schema_version", "pgid"}, "launch_invalid")
            _require(
                launch["schema_version"] == LAUNCH_VERSION
                and _integer(launch["pgid"])
                and launch["pgid"] > 1,
                "launch_invalid",
            )
            pid = launch["pgid"]
        if "receipt.json" not in names:
            used = 0
            for name, limit in (
                ("stdout", limits["stdout_bytes_per_job"]),
                ("stderr", limits["stderr_bytes_per_job"]),
            ):
                if name in names:
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    _require(
                        stat.S_ISREG(info.st_mode) and info.st_size <= limit,
                        "abandoned_output",
                    )
                    used += info.st_size
            return None, used, pid
        receipt = _record(fd, "receipt.json")
        _check_receipt(receipt, job, number, campaign, limits, request)
        for name, limit in (
            ("stdout", limits["stdout_bytes_per_job"]),
            ("stderr", limits["stderr_bytes_per_job"]),
        ):
            observed = _digest(fd, name, limit)
            _require(
                observed == (receipt[name]["sha256"], receipt[name]["bytes"]),
                "artifact_changed",
            )
        return receipt, receipt["stdout"]["bytes"] + receipt["stderr"]["bytes"], pid


def _inspect_job(jobs_fd: int, job: dict, campaign: str, limits: dict) -> _JobState:
    state = _JobState()
    try:
        with _directory([job["id"]], jobs_fd) as job_fd:
            names = _names(job_fd)
            request = _read(job_fd, "request.json", MAX_REQUEST_BYTES, "request_copy")
            _require(_sha256(request) == job["request"]["sha256"], "request_copy")
            count = len(names) - 1
            _require(count <= MAX_ATTEMPTS, "attempt_count")
            _require(
                names
                == {"request.json"}
                | {f"attempt-{index:04d}" for index in range(1, count + 1)},
                "attempt_sequence",
            )
            for number in range(1, count + 1):
                receipt, used, pid = _inspect_attempt(
                    job_fd, job, number, campaign, limits, len(request)
                )
                _require(
                    state.last is None or not state.last["terminal"],
                    "terminal_not_last",
                )
                state.record(receipt, used)
                if receipt is None and pid is not None:
                    state.pids.append(pid)
    except JobError as error:
        return _JobState(error=error.code)
    except OSError:
        return _JobState(error="job_unavailable")
    return state


def _inspect(out: int, manifest: dict, campaign: str) -> dict[str, _JobState]:
    """Check the whole layout and verify every job's stored artifacts."""
    try:
        top = _names(out)
        _require(
            top <= TOP_FILES and top >= TOP_FILES - {"summary.json"}, "layout_invalid"
        )
        with _directory(["jobs"], out) as jobs_fd:
            _require(
                _names(jobs_fd) == {job["id"] for job in manifest["jobs"]},
                "layout_invalid",
            )
            return {
                job["id"]: _inspect_job(jobs_fd, job, campaign, manifest["limits"])
                for job in manifest["jobs"]
            }
    except OSError as error:
        raise JobError("layout_invalid") from error


def _runtime_ok(value: Any) -> bool:
    """Structural check of a stored runtime identity, without comparing values."""
    if not (
        type(value) is dict
        and set(value) == {"regsite_version", "code", "python"}
        and type(value["code"]) is dict
        and set(value["code"]) == {"sha256", "files"}
        and type(value["python"]) is dict
        and set(value["python"]) == PYTHON_KEYS
    ):
        return False
    return (
        type(value["regsite_version"]) is str
        and _matches(value["code"]["sha256"], SHA_PATTERN)
        and _integer(value["code"]["files"])
        and value["code"]["files"] >= 1
        and all(type(item) is str for item in value["python"].values())
        and _matches(value["python"]["executable_sha256"], SHA_PATTERN)
    )


def _read_campaign(out: int, raw: bytes) -> tuple[dict, str]:
    """Load campaign.json and require it to bind exactly these manifest bytes."""
    data = _read(out, "campaign.json", MAX_RECORD_BYTES, "campaign")
    campaign = _decode(data)
    _object(
        campaign,
        {"schema_version", "manifest", "runtime", "backend"},
        "campaign_invalid",
    )
    _require(
        campaign["schema_version"] == CAMPAIGN_VERSION
        and _runtime_ok(campaign["runtime"]),
        "campaign_invalid",
    )
    _object(
        campaign["backend"],
        {"rnastructure", "conditional_original"},
        "campaign_invalid",
    )
    _require(
        all(
            value is None or type(value) is dict
            for value in campaign["backend"].values()
        ),
        "campaign_invalid",
    )
    _require(
        campaign["manifest"]
        == {"path": "manifest.json", "sha256": _sha256(raw), "bytes": len(raw)}
        and _read(out, "manifest.json", MAX_MANIFEST_BYTES, "manifest_copy") == raw,
        "manifest_mismatch",
    )
    return campaign, _sha256(data)


def _lock(out: int, shared: bool = False) -> int:
    """Take the campaign flock; refuse rather than wait when it is held."""
    flags = os.O_RDONLY if shared else os.O_RDWR | os.O_CREAT
    try:
        fd = os.open("lock", flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=out)
    except OSError as error:
        raise JobError("layout_invalid") from error
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise JobError("layout_invalid")
    try:
        fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    except OSError as error:
        os.close(fd)
        raise JobError("locked") from error
    return fd


@contextmanager
def _output(parts: list[str], create: bool) -> Iterator[int]:
    """Open the output directory, creating it exclusively for a new campaign."""
    try:
        with _directory(parts[:-1]) as parent:
            if create:
                try:
                    os.mkdir(parts[-1], 0o700, dir_fd=parent)
                except FileExistsError as error:
                    raise JobError("output_exists") from error
            fd = os.open(
                parts[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
            )
    except OSError as error:
        code = "output_parent_unavailable" if create else "output_unavailable"
        raise JobError(code) from error
    try:
        yield fd
    finally:
        os.close(fd)


@dataclass
class _Context:
    out: int
    manifest: dict
    campaign: str
    identity: dict
    backend_root: str | None
    deadline: float
    signals: _Signals


def _argv(job: dict, backend_root: str | None) -> list[str]:
    values = {"{python}": sys.executable, "{backend_root}": backend_root}
    return [values.get(item) or item for item in command_template(job)]


def _launch(
    context: _Context, job: dict, fd: int, stdin: int, captures: tuple
) -> tuple[str | None, int | None]:
    """Start and supervise the child; return (stop reason, return code)."""
    job_deadline = time.monotonic() + context.manifest["limits"]["seconds_per_job"]
    try:
        anchor = subprocess.Popen(
            [sys.executable, *ANCHOR],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd="/",
            env=_environment(),
            close_fds=True,
            process_group=0,
        )
    except OSError:
        return "launch_failed", None
    reason: str | None
    try:
        # Commit group ownership before any calculator work can start, so an
        # attempt without launch.json never ran a calculator.
        try:
            record = {"schema_version": LAUNCH_VERSION, "pgid": anchor.pid}
            _publish(fd, "launch.json", _encode(record))
        except OSError:
            return "storage_error", None
        try:
            process = subprocess.Popen(
                _argv(job, context.backend_root),
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd="/",
                env=_environment(),
                close_fds=True,
                process_group=anchor.pid,
            )
        except OSError:
            return "launch_failed", None
        with selectors.DefaultSelector() as selector:
            for stream, capture in zip(
                (process.stdout, process.stderr), captures, strict=True
            ):
                selector.register(stream, selectors.EVENT_READ, capture)  # type: ignore[arg-type]
            try:
                reason = _pump(
                    process,
                    anchor.pid,
                    selector,
                    min(job_deadline, context.deadline),
                    context.signals,
                )
            except OSError:
                reason = "storage_error"
            finally:
                stored = _stop(process, anchor.pid, selector)
        if not stored:
            reason = "storage_error"
    finally:
        _release(anchor)
    if reason == "deadline":
        reason = (
            "timed_out" if job_deadline <= context.deadline else "campaign_deadline"
        )
    return reason, process.returncode


def _release(anchor: subprocess.Popen) -> None:
    """Kill the anchor's group while the anchor is unreaped, then reap it."""
    _signal_group(anchor.pid, signal.SIGKILL)
    cast(IO[bytes], anchor.stdin).close()
    anchor.wait()


def _run_attempt(
    context: _Context, job: dict, job_fd: int, number: int
) -> tuple[dict, int]:
    """Run one attempt in its new directory and publish its receipt last."""
    name = f"attempt-{number:04d}"
    base = f"jobs/{job['id']}/{name}/"
    limits = context.manifest["limits"]
    os.mkdir(name, 0o700, dir_fd=job_fd)
    with _directory([name], job_fd) as fd:
        stdout = _Capture(
            _create(fd, "stdout"), limits["stdout_bytes_per_job"], base + "stdout"
        )
        try:
            stderr = _Capture(
                _create(fd, "stderr"), limits["stderr_bytes_per_job"], base + "stderr"
            )
            try:
                stdin = os.open(
                    "request.json", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=job_fd
                )
                request_bytes = os.fstat(stdin).st_size
                started = time.monotonic()
                try:
                    reason, code = _launch(context, job, fd, stdin, (stdout, stderr))
                finally:
                    os.close(stdin)
                elapsed = time.monotonic() - started
                try:
                    os.fsync(stdout.fd)
                    os.fsync(stderr.fd)
                except OSError:
                    reason = "storage_error"
            finally:
                os.close(stderr.fd)
        finally:
            os.close(stdout.fd)
        outcome = _verified(
            context,
            reason or EXIT_OUTCOMES.get(code, "abnormal_exit"),  # type: ignore[arg-type]
        )
        receipt = {
            "schema_version": RECEIPT_VERSION,
            "campaign_sha256": context.campaign,
            "job_id": job["id"],
            "kind": job["kind"],
            "attempt": number,
            "request": {
                "path": f"jobs/{job['id']}/request.json",
                "sha256": job["request"]["sha256"],
                "bytes": request_bytes,
            },
            "argv": command_template(job),
            "outcome": outcome,
            "terminal": outcome in TERMINAL,
            "exit_code": code if code is not None and code >= 0 else None,
            "signal": -code if code is not None and code < 0 else None,
            "elapsed_seconds": round(elapsed, 6),
            "stdout": stdout.record(),
            "stderr": stderr.record(),
        }
        _publish(fd, "receipt.json", _encode(receipt))
        return receipt, stdout.size + stderr.size


def _verified(context: _Context, outcome: str) -> str:
    """Recheck identity within the campaign time before a terminal outcome stands."""
    if outcome not in TERMINAL:
        return outcome
    try:
        same = (
            _identity(context.manifest, context.backend_root, context.deadline)
            == context.identity
        )
    except JobError as error:
        late = error.code == "campaign_deadline"
        return "campaign_deadline" if late else "runtime_changed"
    if not same:
        return "runtime_changed"
    return outcome if time.monotonic() < context.deadline else "campaign_deadline"


def _reinspect(context: _Context, job: dict) -> _JobState:
    """Account a failed attempt from what is actually stored on disk."""
    try:
        with _directory(["jobs"], context.out) as jobs_fd:
            return _inspect_job(
                jobs_fd, job, context.campaign, context.manifest["limits"]
            )
    except OSError:
        return _JobState(error="job_unavailable")


def _execute(context: _Context, states: dict[str, _JobState]) -> str | None:
    """Run unfinished jobs in manifest order; return a stop reason or None."""
    limits = context.manifest["limits"]
    reserve = limits["stdout_bytes_per_job"] + limits["stderr_bytes_per_job"]
    exhausted = False
    for job in context.manifest["jobs"]:
        state = states[job["id"]]
        if state.state in TERMINAL:
            continue
        if state.state == "attempts_exhausted":
            exhausted = True
            continue
        if context.signals.received is not None:
            return "signal"
        if time.monotonic() >= context.deadline:
            return "campaign_deadline"
        used = sum(item.used for item in states.values())
        if used + reserve > limits["output_bytes_total"]:
            return "output_budget"
        try:
            with _directory(["jobs", job["id"]], context.out) as job_fd:
                receipt, size = _run_attempt(context, job, job_fd, state.attempts + 1)
        except OSError:
            states[job["id"]] = _reinspect(context, job)
            return "storage_error"
        state.record(receipt, size)
        if receipt["outcome"] in STOP_REASONS:
            return STOP_REASONS[receipt["outcome"]]
    return "attempt_limit" if exhausted else None


def _summary(
    command: str,
    manifest: dict,
    raw: bytes,
    campaign: str,
    states: dict[str, _JobState],
    stop_reason: str | None,
) -> dict:
    rows = [states[job["id"]].row(job) for job in manifest["jobs"]]
    counts = {name: 0 for name in STATES}
    for row in rows:
        counts[row["state"]] += 1
    terminal = sum(counts[name] for name in TERMINAL)
    status = (
        "corrupted"
        if counts["corrupted"]
        else "complete"
        if terminal == len(rows)
        else "incomplete"
    )
    return {
        "schema_version": SUMMARY_VERSION,
        "command": command,
        "status": status,
        "stop_reason": stop_reason,
        "campaign_sha256": campaign,
        "manifest_sha256": _sha256(raw),
        "counts": counts,
        "attempts": sum(state.attempts for state in states.values()),
        "abandoned_attempts": sum(state.abandoned for state in states.values()),
        "output_bytes": sum(state.used for state in states.values()),
        "jobs": rows,
    }


def _create_campaign(
    out: int, manifest: dict, raw: bytes, requests: dict[str, bytes], identity: dict
) -> None:
    """Write manifest/request copies, then campaign.json as the commit marker."""
    try:
        _publish(out, "manifest.json", raw)
        os.mkdir("jobs", 0o700, dir_fd=out)
        with _directory(["jobs"], out) as jobs_fd:
            for job in manifest["jobs"]:
                os.mkdir(job["id"], 0o700, dir_fd=jobs_fd)
                with _directory([job["id"]], jobs_fd) as job_fd:
                    _publish(job_fd, "request.json", requests[job["id"]])
        campaign = {
            "schema_version": CAMPAIGN_VERSION,
            "manifest": {
                "path": "manifest.json",
                "sha256": _sha256(raw),
                "bytes": len(raw),
            },
            **identity,
        }
        _publish(out, "campaign.json", _encode(campaign))
    except OSError as error:
        raise JobError("storage_error") from error


def _store_summary(out: int, summary: dict, deadline: float) -> dict:
    """Persist the summary; a deadline crossed while storing is never success.

    A late publication is rewritten once with campaign_deadline. If that rewrite
    fails, the stale stored success claim is removed (best effort); receipts stay
    authoritative and the returned summary reports the deadline either way.
    """
    try:
        _publish(out, "summary.json", _encode(summary), replace=True)
    except OSError:
        summary["stop_reason"] = summary["stop_reason"] or "storage_error"
        return summary
    if summary["stop_reason"] is None and time.monotonic() >= deadline:
        summary["stop_reason"] = "campaign_deadline"
        try:
            _publish(out, "summary.json", _encode(summary), replace=True)
        except OSError:
            try:
                os.unlink("summary.json", dir_fd=out)
            except OSError:
                pass
    return summary


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _drive(
    command: str,
    manifest_path: str,
    output_dir: str,
    backend_root: str | None,
    allow_repository_output: bool,
) -> dict:
    started = time.monotonic()
    with _Signals() as signals:
        manifest, raw = load_manifest(manifest_path)
        requests = _load_requests(manifest_path, manifest)
        parts = _output_parts(
            output_dir, manifest_path, manifest, allow_repository_output
        )
        deadline = started + manifest["limits"]["seconds_total"]
        identity = _identity(manifest, backend_root, deadline)
        with _output(parts, create=command == "run") as out:
            lock = _lock(out)
            try:
                if command == "run":
                    _create_campaign(out, manifest, raw, requests, identity)
                stored, campaign = _read_campaign(out, raw)
                _require(stored["runtime"] == identity["runtime"], "runtime_mismatch")
                _require(stored["backend"] == identity["backend"], "backend_mismatch")
                states = _inspect(out, manifest, campaign)
                _require(
                    all(state.error is None for state in states.values()), "corrupted"
                )
                _require(
                    not any(
                        _group_alive(pid)
                        for state in states.values()
                        for pid in state.pids
                    ),
                    "orphan_process",
                )
                context = _Context(
                    out,
                    manifest,
                    campaign,
                    identity,
                    backend_root,
                    deadline,
                    signals,
                )
                stop = _execute(context, states)
                if stop is None and time.monotonic() >= deadline:
                    stop = "campaign_deadline"
                summary = _summary(command, manifest, raw, campaign, states, stop)
                return _store_summary(out, summary, deadline)
            finally:
                os.close(lock)


def run_campaign(
    manifest_path: str,
    output_dir: str,
    *,
    backend_root: str | None = None,
    allow_repository_output: bool = False,
) -> dict:
    """Create a new campaign directory and run every job; return the summary."""
    return _drive(
        "run", manifest_path, output_dir, backend_root, allow_repository_output
    )


def resume_campaign(
    manifest_path: str,
    output_dir: str,
    *,
    backend_root: str | None = None,
    allow_repository_output: bool = False,
) -> dict:
    """Verify an existing campaign, then run only its unfinished/unstarted jobs."""
    return _drive(
        "resume", manifest_path, output_dir, backend_root, allow_repository_output
    )


def verify_campaign(manifest_path: str, output_dir: str) -> dict:
    """Read-only verification of layout, copies, receipts and artifact bytes."""
    manifest, raw = load_manifest(manifest_path)
    with _output(_parts(output_dir, "output_path"), create=False) as out:
        lock = _lock(out, shared=True)
        try:
            _, campaign = _read_campaign(out, raw)
            states = _inspect(out, manifest, campaign)
            return _summary("verify", manifest, raw, campaign, states, None)
        finally:
            os.close(lock)


def exit_code(summary: dict) -> int:
    """Map a summary to the documented process exit status."""
    if summary["status"] == "corrupted":
        return 2
    if summary["status"] == "incomplete" or summary["stop_reason"] is not None:
        return 3
    return 0 if summary["counts"]["succeeded"] == len(summary["jobs"]) else 1


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: one JSON document on stdout; exit 0/1/2/3 as documented."""
    parser = argparse.ArgumentParser(prog="regsite-jobs", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--manifest", required=True)
        command.add_argument("--output-dir", required=True)
        if name != "verify":
            command.add_argument("--backend-root")
            command.add_argument("--allow-repository-output", action="store_true")
    args = parser.parse_args(argv)
    action: Callable[..., dict]
    try:
        if args.command == "verify":
            document = verify_campaign(args.manifest, args.output_dir)
        else:
            action = run_campaign if args.command == "run" else resume_campaign
            document = action(
                args.manifest,
                args.output_dir,
                backend_root=args.backend_root,
                allow_repository_output=args.allow_repository_output,
            )
        code = exit_code(document)
    except JobError as error:
        document = {
            "schema_version": SUMMARY_VERSION,
            "status": "invalid",
            "error": error.code,
        }
        code = 2
    try:
        _write_all(sys.stdout.fileno(), _encode(document))
    except OSError:
        sys.stderr.write("regsite-jobs: stdout unavailable\n")
        return 2
    return code
