"""Register explicit opaque local files and check their declared byte identities.

Standard library only; no calculator imports or payload decoding. See
docs/validation/calculator-artifact-storage.md for limits and trust boundaries.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

VERSION = "calculator-artifact-manifest-1.0"
REPORT_VERSION = "calculator-artifact-verification-1.0"
REPOSITORY = "https://github.com/rohinshanker/regulatory-site-prediction-reconstruction"
ROLES = ("request", "result", "benchmark", "report", "parameter")
MAX_MANIFEST_BYTES = 1_048_576
MAX_ENTRIES = 256
MAX_PATH = 1024
CHUNK_BYTES = 65_536
END = r"(?![\s\S])"
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}" + END
PATH_PATTERN = (
    r"^(?!(?:\.|\.\.)(?:/|$))[A-Za-z0-9._-]{1,255}"
    r"(?:/(?!(?:\.|\.\.)(?:/|$))[A-Za-z0-9._-]{1,255})*" + END
)


class ArtifactError(ValueError):
    """Stable, path-free error suitable for deterministic JSON reports."""

    def __init__(self, status: str, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ArtifactError("invalid", code)


def _matches(value: Any, pattern: str) -> bool:
    return isinstance(value, str) and re.search(pattern, value) is not None


def _keys(value: Any, keys: set[str]) -> None:
    _require(type(value) is dict and set(value) == keys, "object_keys")


def _roster(entries: Any, *, hashed: bool) -> None:
    _require(type(entries) is list, "artifacts_type")
    _require(1 <= len(entries) <= MAX_ENTRIES, "artifacts_count")
    ids, paths = set(), set()
    for entry in entries:
        keys = {"id", "role", "path"}
        if hashed:
            keys |= {"sha256", "bytes"}
        _keys(entry, keys)
        _require(_matches(entry["id"], ID_PATTERN), "artifact_id")
        _require(type(entry["role"]) is str and entry["role"] in ROLES, "role")
        _require(
            _matches(entry["path"], PATH_PATTERN) and len(entry["path"]) <= MAX_PATH,
            "artifact_path",
        )
        _require(entry["id"] not in ids, "duplicate_id")
        _require(entry["path"] not in paths, "duplicate_path")
        ids.add(entry["id"])
        paths.add(entry["path"])
        if hashed:
            _require(_matches(entry["sha256"], "^[0-9a-f]{64}" + END), "sha256")
            _require(type(entry["bytes"]) is int and entry["bytes"] >= 0, "bytes")


def validate_manifest(value: Any) -> None:
    """Validate strict versioned structure, including unique IDs and paths."""
    _keys(
        value,
        {"schema_version", "producer_repository", "producer_commit", "artifacts"},
    )
    _require(value["schema_version"] == VERSION, "schema_version")
    _require(value["producer_repository"] == REPOSITORY, "producer_repository")
    _require(_matches(value["producer_commit"], "^[0-9a-f]{40}" + END), "commit")
    _roster(value["artifacts"], hashed=True)


def _absolute(path: str) -> list[str]:
    _require(
        isinstance(path, str)
        and path.startswith("/")
        and not any(c in path for c in ("\\", "\0", ":")),
        "absolute_local_path_required",
    )
    parts = path.split("/")[1:]
    if parts == [""]:
        return []
    _require(all(part not in ("", ".", "..") for part in parts), "local_path")
    return parts


def _io_error(error: OSError) -> ArtifactError:
    if error.errno == errno.ENOENT:
        return ArtifactError("missing", "not_found")
    if error.errno in (errno.ELOOP, errno.ENOTDIR):
        return ArtifactError("invalid", "link_or_non_directory")
    return ArtifactError("unreadable", "io_error")


@contextmanager
def _directory(parts: Sequence[str], base: int | None = None) -> Iterator[int]:
    """Open each directory separately; never follow intermediate symlinks."""
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


@contextmanager
def _file(root: int, path: str) -> Iterator[int]:
    parts = path.split("/")
    with _directory(parts[:-1], root) as parent:
        info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        _require(stat.S_ISREG(info.st_mode), "not_regular")
        fd = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        try:
            _require(stat.S_ISREG(os.fstat(fd).st_mode), "not_regular")
            _require_unchanged(_identity(info) == _identity(os.fstat(fd)))
            yield fd
        finally:
            os.close(fd)


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (*_identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _check_path(root: int, path: str, before: os.stat_result) -> None:
    try:
        with _file(root, path) as current:
            _require_unchanged(_stamp(before) == _stamp(os.fstat(current)))
    except (ArtifactError, OSError) as error:
        raise ArtifactError("changed", "mutated_during_read") from error


def _hash(root: int, path: str) -> tuple[dict, tuple[int, int]]:
    try:
        with _file(root, path) as fd:
            before = os.fstat(fd)
            digest, size = hashlib.sha256(), 0
            while chunk := os.read(fd, min(CHUNK_BYTES, before.st_size - size + 1)):
                size += len(chunk)
                if size > before.st_size:
                    raise ArtifactError("changed", "mutated_during_read")
                digest.update(chunk)
            _require_unchanged(size == before.st_size)
            _require_unchanged(_stamp(before) == _stamp(os.fstat(fd)))
            _check_path(root, path, before)
            return {"sha256": digest.hexdigest(), "bytes": size}, _identity(before)
    except OSError as error:
        raise _io_error(error) from error


def _require_unchanged(condition: bool) -> None:
    if not condition:
        raise ArtifactError("changed", "mutated_during_read")


def _pairs(pairs: list[tuple[str, Any]]) -> dict:
    value: dict = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _constant(value: str) -> None:
    raise ArtifactError("invalid", "nonfinite_json")


def _float(value: str) -> None:
    # No manifest field accepts floats; also rejects overflow such as 1e999.
    raise ArtifactError("invalid", "json_float")


def _load(path: str) -> tuple[dict, tuple[int, int]]:
    parts = _absolute(path)
    _require(bool(parts), "manifest_file_required")
    with _directory(parts[:-1]) as parent, _file(parent, parts[-1]) as fd:
        before = os.fstat(fd)
        _require(before.st_size <= MAX_MANIFEST_BYTES, "manifest_too_large")
        data = bytearray()
        while chunk := os.read(
            fd, min(CHUNK_BYTES, MAX_MANIFEST_BYTES + 1 - len(data))
        ):
            data.extend(chunk)
            _require(len(data) <= MAX_MANIFEST_BYTES, "manifest_too_large")
        _require_unchanged(_stamp(before) == _stamp(os.fstat(fd)))
        _require_unchanged(len(data) == before.st_size)
        _check_path(parent, parts[-1], before)
        try:
            value = json.loads(
                data.decode("utf-8"),
                object_pairs_hook=_pairs,
                parse_constant=_constant,
                parse_float=_float,
            )
        except (ValueError, RecursionError) as error:
            if isinstance(error, ArtifactError):
                raise
            raise ArtifactError("invalid", "malformed_json") from error
        validate_manifest(value)
        return value, _identity(before)


def _encoded(value: dict) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def _collides(output: str, source: str) -> bool:
    """Conservatively reject aliases and outputs replacing an input's parent."""
    output_key = unicodedata.normalize("NFC", output).casefold()
    source_key = unicodedata.normalize("NFC", source).casefold()
    return source_key == output_key or source_key.startswith(output_key + "/")


def _output_check(output: str, root: str, entries: list[dict]) -> None:
    _require(bool(_absolute(output)), "output_file_required")
    _require(
        not any(
            _collides(output, root.rstrip("/") + "/" + entry["path"])
            for entry in entries
        ),
        "output_input_collision",
    )


def _write(output: str, value: dict) -> None:
    """Publish a complete private temporary output using atomic exclusive link."""
    parts = _absolute(output)
    with _directory(parts[:-1]) as parent:
        name = ".calculator-artifacts-" + secrets.token_hex(16)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(_encoded(value))
                stream.flush()
                os.fsync(stream.fileno())
            os.link(name, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
        finally:
            os.close(fd)
            os.unlink(name, dir_fd=parent)


def create_manifest(
    root: str, producer_commit: str, entries: list[dict], output: str
) -> dict:
    """Hash only selected files and exclusively publish a deterministic manifest.

    Entries contain exactly id, role, path. All paths/roots must be explicit;
    artifact paths are relative, root/output are absolute local paths.
    """
    parts = _absolute(root)
    _require(_matches(producer_commit, "^[0-9a-f]{40}" + END), "commit")
    _roster(entries, hashed=False)
    _output_check(output, root, entries)
    artifacts, identities = [], set()
    with _directory(parts) as directory:
        for entry in sorted(entries, key=lambda row: row["id"]):
            observed, identity = _hash(directory, entry["path"])
            _require(identity not in identities, "input_alias")
            identities.add(identity)
            artifacts.append({**entry, **observed})
    manifest = {
        "schema_version": VERSION,
        "producer_repository": REPOSITORY,
        "producer_commit": producer_commit,
        "artifacts": artifacts,
    }
    _require(len(_encoded(manifest)) <= MAX_MANIFEST_BYTES, "manifest_too_large")
    _write(output, manifest)
    return manifest


def verify_manifest(root: str, manifest_path: str, output: str | None = None) -> dict:
    """Check every valid manifest entry; no artifact payload is decoded.

    A malformed manifest has no trusted roster and raises ArtifactError. For a
    valid manifest, file failures are preserved per entry, including root errors.
    """
    parts = _absolute(root)
    manifest, manifest_identity = _load(manifest_path)
    entries = manifest["artifacts"]
    if output is not None:
        _output_check(output, root, entries)
        _require(not _collides(output, manifest_path), "output_input_collision")
    rows, identities = [], {manifest_identity}

    def check(directory: int, entry: dict) -> dict:
        observed, identity = _hash(directory, entry["path"])
        _require(identity not in identities, "input_alias")
        identities.add(identity)
        status = (
            "matching" if observed == {k: entry[k] for k in observed} else "changed"
        )
        return {**entry, "status": status, "observed": observed, "error": None}

    try:
        with _directory(parts) as directory:
            for entry in sorted(entries, key=lambda row: row["id"]):
                try:
                    rows.append(check(directory, entry))
                except ArtifactError as error:
                    rows.append(
                        {
                            **entry,
                            "status": error.status,
                            "observed": None,
                            "error": error.code,
                        }
                    )
    except OSError as error:
        problem = _io_error(error)
        rows = [
            {**entry, "status": problem.status, "observed": None, "error": problem.code}
            for entry in sorted(entries, key=lambda row: row["id"])
        ]
    report = {
        "schema_version": REPORT_VERSION,
        "producer_repository": REPOSITORY,
        "producer_commit": manifest["producer_commit"],
        "status": "complete"
        if all(r["status"] == "matching" for r in rows)
        else "incomplete",
        "artifacts": rows,
    }
    if output is not None:
        _write(output, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: JSON on stdout; 0 complete, 1 incomplete, 2 invalid/IO failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--root", required=True)
    create.add_argument("--producer-commit", required=True)
    create.add_argument(
        "--entry",
        nargs=3,
        action="append",
        required=True,
        metavar=("ID", "ROLE", "PATH"),
    )
    create.add_argument("--output", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            result = create_manifest(
                args.root,
                args.producer_commit,
                [
                    dict(zip(("id", "role", "path"), entry, strict=True))
                    for entry in args.entry
                ],
                args.output,
            )
            exit_code = 0
        else:
            result = verify_manifest(args.root, args.manifest, args.output)
            exit_code = 0 if result["status"] == "complete" else 1
    except (ArtifactError, OSError) as error:
        problem = error if isinstance(error, ArtifactError) else _io_error(error)
        result = {"status": "invalid", "error": problem.code}
        exit_code = 2
    sys.stdout.write(_encoded(result).decode())
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
