"""Strict receipts and bounded execution of a separately installed TransTermHP."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ARCHIVE_SHA256 = "b636db1c0fe9731cc760d8f3639209d07f7f35309d83013cc9f9e40798ce8be0"
NULL_PATCH_SHA256 = "9bbfc2ced3df5332ec41b61bf23ca9acaf030cce3a3688f6c1c7468a5961ba6c"
PROTOTYPE_PATCH_SHA256 = (
    "5163cfac5056b67f8a0099f0f15fee683e1eb9ffe8842c20b82511d3779c0a75"
)
TABLE_SHA256 = "fce89a92ab487aaea5a54015e859e1fb5e31f4f9985c9df7831ee09a367db1fe"
BUILD_FLAGS = ["-g", "-O3", "-Wall", "-pedantic", "-std=c++11", "-ffp-contract=off"]
SOURCE = {
    "archive_sha256": ARCHIVE_SHA256,
    "null_patch_sha256": NULL_PATCH_SHA256,
    "prototype_patch_sha256": PROTOTYPE_PATCH_SHA256,
}
PROFILE = "transtermhp-2.09-fragment-1"
STDOUT_LIMIT = 262144
STDERR_LIMIT = 65536
BINARY_LIMIT = 32 * 1024 * 1024
STACK_BYTES = 8 * 1024 * 1024
_PROCESS_LOCK = threading.Lock()


class TerminationBackendError(ValueError):
    """A bounded failure; native output belongs in diagnostics, never the message."""

    def __init__(
        self, message: str, *, code: str, diagnostics: dict[str, Any] | None = None
    ):
        # Call sites use fixed messages; do not interpolate OS exceptions/paths.
        super().__init__(message[:240])
        self.code = code
        self.diagnostics = diagnostics


def _error(code: str) -> TerminationBackendError:
    return TerminationBackendError(f"Termination backend failure: {code}.", code=code)


def _file_state(info: os.stat_result) -> tuple[int, ...]:
    # A read may update atime; identity and modification metadata must stay fixed.
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_regular(path: Path, limit: int, *, executable: bool = False) -> bytes:
    """Read a bounded, stable regular file without following its final symlink."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or not 0 < before.st_size <= limit
                or (executable and not before.st_mode & 0o111)
            ):
                raise _error("backend_identity")
            data = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        if (
            _file_state(before) != _file_state(after)
            or len(data) != before.st_size
            or _file_state(path.lstat()) != _file_state(after)
        ):
            raise _error("backend_identity")
        return data
    except OSError as exc:
        raise _error("backend_unavailable") from exc


def _reject_number(_: str) -> None:
    raise ValueError("Manifest numbers must be finite integers.")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _error("backend_manifest")
        result[key] = value
    return result


def _keys(value: Any, names: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == names


def _hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _artifact(value: Any, limit: int) -> bool:
    return (
        _keys(value, {"bytes", "sha256"})
        and type(value["bytes"]) is int
        and 0 < value["bytes"] <= limit
        and _hash(value["sha256"])
    )


def _manifest(value: Any) -> None:
    if not _keys(
        value, {"schema_version", "profile", "source", "build", "binary", "table"}
    ):
        raise _error("backend_manifest")
    build = value["build"]
    if (
        value["schema_version"] != "termination-backend-1"
        or value["profile"] != PROFILE
        or value["source"] != SOURCE
        or not _keys(
            build,
            {
                "compiler",
                "compiler_sha256",
                "compiler_version",
                "platform",
                "machine",
                "standard_library",
                "flags",
                "extra_flags_sha256",
            },
        )
    ):
        raise _error("backend_manifest")
    for key in (
        "compiler",
        "compiler_version",
        "platform",
        "machine",
        "standard_library",
    ):
        # Provenance contains labels, never compiler paths or multiline diagnostics.
        item = build[key]
        if (
            not isinstance(item, str)
            or not 1 <= len(item) <= 256
            or any(ord(c) < 32 or ord(c) > 126 or c in "/\\" for c in item)
        ):
            raise _error("backend_manifest")
    if (
        build["flags"] != BUILD_FLAGS
        or not _hash(build["compiler_sha256"])
        or not _hash(build["extra_flags_sha256"])
        or not _artifact(value["binary"], BINARY_LIMIT)
        or not _artifact(value["table"], 45788)
        or value["table"] != {"bytes": 45788, "sha256": TABLE_SHA256}
    ):
        raise _error("backend_manifest")


def _verify(data: bytes, identity: dict[str, Any]) -> None:
    if (
        len(data) != identity["bytes"]
        or hashlib.sha256(data).hexdigest() != identity["sha256"]
    ):
        raise _error("backend_identity")


def load_backend(path: str | Path) -> TerminationBackend:
    """Load an explicit receipt, checking all pins and both local artifacts."""
    if os.name != "posix":
        raise _error("unsupported_platform")
    manifest_path = Path(path).absolute()
    raw = _read_regular(manifest_path, 32768)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=_reject_number,
            parse_float=_reject_number,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise _error("backend_manifest") from exc
    _manifest(value)
    backend = TerminationBackend(manifest_path.parent, value)
    backend._artifacts()
    return backend


@dataclass(frozen=True)
class NativeRun:
    """Complete bounded native streams and their capture identities."""

    stdout: bytes
    stderr: bytes
    diagnostics: dict[str, Any]


class TerminationBackend:
    """One fixed external engine profile; no engine or table is distributed here."""

    def __init__(self, directory: Path, identity: dict[str, Any]):
        self._directory = directory
        self._identity = copy.deepcopy(identity)

    @property
    def identity(self) -> dict[str, Any]:
        """Return JSON provenance without local paths or execution timing."""
        return copy.deepcopy(self._identity)

    def _artifacts(self) -> bytes:
        binary = _read_regular(
            self._directory / "transterm", BINARY_LIMIT, executable=True
        )
        table = _read_regular(self._directory / "expterm.dat", 45788)
        _verify(binary, self._identity["binary"])
        _verify(table, self._identity["table"])
        return table

    def run(self, sequence: str, *, timeout_seconds: float) -> NativeRun:
        """Execute one admitted fragment, raising on any incomplete capture."""
        if os.name != "posix":
            raise _error("unsupported_platform")
        if (
            not isinstance(sequence, str)
            or not 76 <= len(sequence) <= 100000
            or re.fullmatch(r"[ACGT]+", sequence) is None
        ):
            raise _error("native_input")
        for group in (sequence[2:-2], sequence[:2] + sequence[-2:]):
            if not 0 < sum(c in "AT" for c in group) < len(group):
                raise _error("native_input")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 60
        ):
            raise _error("native_input")
        deadline = time.monotonic() + timeout_seconds
        if not _PROCESS_LOCK.acquire(timeout=timeout_seconds):
            raise _error("native_timeout")
        try:
            table = self._artifacts()
            import resource

            try:
                soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
            except (OSError, ValueError) as exc:
                raise _error("insufficient_stack") from exc
            if hard != resource.RLIM_INFINITY and hard < STACK_BYTES:
                raise _error("insufficient_stack")

            def child_stack() -> None:
                target = (
                    soft if soft == resource.RLIM_INFINITY else max(soft, STACK_BYTES)
                )
                resource.setrlimit(resource.RLIMIT_STACK, (target, hard))

            diagnostics = None
            try:
                with tempfile.TemporaryDirectory(prefix="regsite-termination-") as temp:
                    directory = Path(temp)
                    (directory / "input.fasta").write_text(
                        f">fragment\n{sequence}\n", encoding="ascii"
                    )
                    (directory / "input.coords").write_text(
                        "boundary_left 1 2 fragment\n"
                        f"boundary_right {len(sequence) - 1} {len(sequence)} "
                        "fragment\n",
                        encoding="ascii",
                    )
                    (directory / "expterm.dat").write_bytes(table)
                    try:
                        result = _execute(
                            self._directory / "transterm",
                            directory,
                            deadline,
                            child_stack,
                        )
                    except TerminationBackendError as exc:
                        diagnostics = exc.diagnostics
                        raise
                    diagnostics = result.diagnostics
                    return result
            except OSError as exc:
                raise TerminationBackendError(
                    "Termination process failure: native_io.",
                    code="native_io",
                    diagnostics=diagnostics,
                ) from exc
        finally:
            _PROCESS_LOCK.release()


def _execute(
    executable: Path,
    directory: Path,
    deadline: float,
    child_stack: Any,
    *,
    arguments: list[str] | None = None,
    environment: dict[str, str] | None = None,
    own_process_group: bool = False,
) -> NativeRun:
    captures = [bytearray(), bytearray()]
    complete = [False, False]
    limits = [STDOUT_LIMIT, STDERR_LIMIT]
    process = None
    failure = None
    try:
        argv = (
            arguments
            if arguments is not None
            else [
                "-p",
                "expterm.dat",
                "--all-context",
                "-c",
                "0",
                "-S",
                "input.fasta",
                "input.coords",
            ]
        )
        process = subprocess.Popen(
            [str(executable), *argv],
            cwd=directory,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=child_stack,
            start_new_session=own_process_group,
            env=environment
            if environment is not None
            else {"LC_ALL": "C", "LANG": "C"},
        )
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate((process.stdout, process.stderr)):
                assert stream is not None
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, index)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _error("native_timeout")
                for key, _ in selector.select(remaining):
                    index = key.data
                    chunk = os.read(
                        key.fd, min(65536, limits[index] - len(captures[index]) + 1)
                    )
                    if not chunk:
                        complete[index] = True
                        selector.unregister(key.fileobj)
                    elif len(captures[index]) + len(chunk) > limits[index]:
                        captures[index].extend(
                            chunk[: limits[index] - len(captures[index])]
                        )
                        raise _error("native_output_limit")
                    else:
                        captures[index].extend(chunk)
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise _error("native_timeout") from exc
            if process.returncode != 0:
                raise _error("native_exit")
    except TerminationBackendError as exc:
        failure = exc.code
    except subprocess.SubprocessError:
        failure = "insufficient_stack"
    except OSError:
        failure = "native_io"
    finally:
        if process is not None:
            try:
                # Only the offline builder owns a process group (make plus its
                # compilers). Signal it before poll/wait can reap the leader.
                if own_process_group and process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except OSError:
                        failure = "native_io"
                if process.poll() is None:
                    process.kill()
            finally:
                process.wait()
                for stream in (process.stdout, process.stderr):
                    assert stream is not None
                    try:
                        stream.close()
                    except OSError:
                        failure = "native_io"
    diagnostics: dict[str, Any] = {
        "returncode": None if process is None else process.returncode
    }
    for index, name in enumerate(("stdout", "stderr")):
        diagnostics.update(
            {
                f"{name}_sha256": hashlib.sha256(captures[index]).hexdigest(),
                f"{name}_bytes": len(captures[index]),
                f"{name}_complete": complete[index],
            }
        )
    if failure:
        raise TerminationBackendError(
            f"Termination process failure: {failure}.",
            code=failure,
            diagnostics=diagnostics,
        )
    return NativeRun(bytes(captures[0]), bytes(captures[1]), diagnostics)
