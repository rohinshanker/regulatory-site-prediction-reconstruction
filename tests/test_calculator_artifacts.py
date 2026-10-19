"""Artificial opaque bytes only; no predictions, private data or source retrieval."""

import errno
import hashlib
import json
import os
import runpy
import socket
import stat
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from tools import calculator_artifacts as tool

COMMIT = "a" * 40
SCHEMA = json.loads(
    (
        Path(__file__).parents[1]
        / "schemas/calculator-artifact-manifest-1.0.schema.json"
    ).read_text()
)


@pytest.fixture
def storage(tmp_path):
    root = tmp_path / "storage"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested" / "opaque.bin").write_bytes(b"\x00\xffnot biological JSON\r\n")
    (root / "empty").write_bytes(b"")
    entries = [
        {"id": "z", "role": "result", "path": "nested/opaque.bin"},
        {"id": "a", "role": "request", "path": "empty"},
    ]
    return str(root), entries, str(tmp_path / "manifest.json")


def create(storage):
    root, entries, output = storage
    return tool.create_manifest(root, COMMIT, entries, output)


def save(path, value):
    Path(path).write_text(json.dumps(value))


def expect_invalid(value, code=None):
    with pytest.raises(tool.ArtifactError, match=code):
        tool.validate_manifest(value)


def test_create_verify_relocation_determinism(storage, tmp_path):
    root, entries, path = storage
    untouched = deepcopy(entries)
    manifest = create(storage)
    assert entries == untouched
    assert [entry["id"] for entry in manifest["artifacts"]] == ["a", "z"]
    assert manifest["producer_commit"] == COMMIT
    assert manifest["producer_repository"] == tool.REPOSITORY
    tool.validate_manifest(manifest)
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    jsonschema.validate(manifest, SCHEMA)
    assert str(tmp_path) not in Path(path).read_text()
    for row in manifest["artifacts"]:
        original = (Path(root) / row["path"]).read_bytes()
        assert row["sha256"] == hashlib.sha256(original).hexdigest()
        assert row["bytes"] == len(original)
    second = str(tmp_path / "second.json")
    assert (
        tool.create_manifest(root, COMMIT, list(reversed(entries)), second) == manifest
    )
    assert Path(second).read_bytes() == Path(path).read_bytes()
    report = tool.verify_manifest(root, path, str(tmp_path / "report.json"))
    assert report == json.loads((tmp_path / "report.json").read_text())
    assert report["status"] == "complete"
    assert all(row["status"] == "matching" for row in report["artifacts"])
    assert tool.verify_manifest(root, path) == report
    # Relocation is caller-managed: the tool never copies/moves source artifacts.
    relocated = tmp_path / "elsewhere"
    Path(root).rename(relocated)
    assert tool.verify_manifest(str(relocated), path) == report
    # Entry order in a loaded manifest also cannot change the deterministic report.
    manifest["artifacts"].reverse()
    save(path, manifest)
    assert tool.verify_manifest(str(relocated), path) == report


@pytest.mark.parametrize("changed", [b"x", b"\x01\xffnot biological JSON\r\n"])
def test_corruption_size_and_hash(storage, changed):
    root, _, path = storage
    manifest = create(storage)
    (Path(root) / "nested/opaque.bin").write_bytes(changed)
    report = tool.verify_manifest(root, path)
    assert report["status"] == "incomplete"
    assert report["artifacts"][0]["status"] == "matching"
    row = report["artifacts"][1]
    assert row["status"] == "changed"
    assert row["observed"] == {
        "bytes": len(changed),
        "sha256": hashlib.sha256(changed).hexdigest(),
    }
    assert {k: row[k] for k in manifest["artifacts"][1]} == manifest["artifacts"][1]


def test_missing_unreadable_and_invalid_each_preserved(storage, monkeypatch):
    root, _, path = storage
    create(storage)
    (Path(root) / "empty").unlink()
    original = tool.os.read

    # Use the selected artifact identity, independent of its artificial byte size.
    inode = os.stat(Path(root) / "nested/opaque.bin").st_ino

    def denied(fd, count):
        if os.fstat(fd).st_ino == inode:
            raise PermissionError(errno.EACCES, "no permission")
        return original(fd, count)

    monkeypatch.setattr(tool.os, "read", denied)
    report = tool.verify_manifest(root, path)
    assert [row["status"] for row in report["artifacts"]] == ["missing", "unreadable"]
    assert [row["error"] for row in report["artifacts"]] == ["not_found", "io_error"]
    assert all(row["observed"] is None for row in report["artifacts"])
    monkeypatch.setattr(tool.os, "read", original)
    (Path(root) / "empty").mkdir()
    assert tool.verify_manifest(root, path)["artifacts"][0]["status"] == "invalid"


@pytest.mark.parametrize("problem", ["missing", "link", "file", "denied"])
def test_root_failure_preserves_all_entries(storage, tmp_path, monkeypatch, problem):
    root, _, path = storage
    manifest = create(storage)
    replacement = tmp_path / "replacement"
    if problem == "link":
        replacement.symlink_to(root, target_is_directory=True)
    elif problem == "file":
        replacement.write_bytes(b"x")
    elif problem == "denied":
        real_open = tool.os.open

        def denied(name, *args, **kwargs):
            if name == "replacement":
                raise PermissionError(errno.EACCES, "denied")
            return real_open(name, *args, **kwargs)

        monkeypatch.setattr(tool.os, "open", denied)
    report = tool.verify_manifest(str(replacement), path)
    expected = {
        "missing": "missing",
        "link": "invalid",
        "file": "invalid",
        "denied": "unreadable",
    }[problem]
    assert report["status"] == "incomplete"
    assert [row["status"] for row in report["artifacts"]] == [expected, expected]
    for row, entry in zip(report["artifacts"], manifest["artifacts"], strict=True):
        assert {key: row[key] for key in entry} == entry


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "2"),
        ("schema_version", None),
        ("producer_repository", "https://other.invalid"),
        ("producer_commit", "A" * 40),
        ("producer_commit", "a" * 39),
        ("producer_commit", "a" * 40 + "\n"),
        ("producer_commit", True),
        ("artifacts", {}),
        ("artifacts", None),
        ("artifacts", []),
        ("extra", "x"),
    ],
)
def test_manifest_strict_fields(storage, field, value):
    manifest = create(storage)
    manifest[field] = value
    expect_invalid(manifest)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, SCHEMA)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", ""),
        ("id", "x" * 129),
        ("id", "x\n"),
        ("id", []),
        ("role", "unknown"),
        ("role", []),
        ("role", 1),
        ("path", ""),
        ("path", "/absolute"),
        ("path", "../x"),
        ("path", "a/../b"),
        ("path", "a/./b"),
        ("path", "."),
        ("path", ".."),
        ("path", "x//y"),
        ("path", "x/"),
        ("path", "x\\y"),
        ("path", "https://example.invalid/x"),
        ("path", "file:///x"),
        ("path", "C:/x"),
        ("path", "x\0"),
        ("path", "x\n"),
        ("path", "x" * 256),
        ("path", []),
        ("sha256", "a" * 63),
        ("sha256", "A" * 64),
        ("sha256", "a" * 64 + "\n"),
        ("sha256", None),
        ("bytes", -1),
        ("bytes", True),
        ("bytes", "2"),
        ("bytes", 1.5),
        ("extra", 0),
    ],
)
def test_entry_strict_fields(storage, field, value):
    manifest = create(storage)
    manifest["artifacts"][0][field] = value
    expect_invalid(manifest)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, SCHEMA)


def test_structural_runtime_constraints(storage):
    manifest = create(storage)
    for value in (None, [], 0, True, "manifest"):
        expect_invalid(value)
    for key in manifest:
        reduced = {k: v for k, v in manifest.items() if k != key}
        expect_invalid(reduced, "object_keys")
    for entry in (None, [], {}, "entry"):
        bad = {**manifest, "artifacts": [entry]}
        expect_invalid(bad, "object_keys")
    for key in ("id", "path"):
        bad = deepcopy(manifest)
        bad["artifacts"][1][key] = bad["artifacts"][0][key]
        expect_invalid(bad, "duplicate_" + key)
    # JSON Schema's mathematical integer type accepts 1.0; the loader requires
    # JSON integer syntax and the library rejects Python float/bool counts.
    bad = deepcopy(manifest)
    bad["artifacts"][0]["bytes"] = 0.0
    expect_invalid(bad, "bytes")


@pytest.mark.parametrize(
    "payload,code",
    [
        (b"{", "malformed_json"),
        (b"\xff", "malformed_json"),
        (b"{} {}", "malformed_json"),
        (b"\xef\xbb\xbf{}", "malformed_json"),
        (b'{"x":1,"x":2}', "duplicate_json_key"),
        (b'{"x":{"a":1,"a":2}}', "duplicate_json_key"),
        (b'{"x":NaN}', "nonfinite_json"),
        (b'{"x":Infinity}', "nonfinite_json"),
        (b'{"x":-Infinity}', "nonfinite_json"),
        (b'{"x":1e999}', "json_float"),
        (b'{"x":1.0}', "json_float"),
        (b"null", "object_keys"),
        (b"[" * 2000, "malformed_json"),
        (b'{"x":' + b"9" * 5000 + b"}", "malformed_json"),
    ],
    ids=lambda value: value if isinstance(value, str) else f"bytes-{len(value)}",
)
def test_json_loader_rejections(storage, payload, code):
    root, _, path = storage
    Path(path).write_bytes(payload)
    with pytest.raises(tool.ArtifactError, match=code):
        tool.verify_manifest(root, path)


@pytest.mark.parametrize(
    "path",
    [
        ".",
        "relative",
        "file:///x",
        "https://x",
        "",
        "/x/../y",
        "/x/./y",
        "/x//y",
        "/x/",
        "/x\\y",
        "/x\0y",
        "/x:y",
        None,
    ],
)
def test_local_paths_are_explicit(storage, path):
    root, entries, output = storage
    with pytest.raises(tool.ArtifactError):
        tool.create_manifest(path, COMMIT, entries, output)
    create(storage)
    with pytest.raises(tool.ArtifactError):
        tool.verify_manifest(path, output)
    with pytest.raises(tool.ArtifactError):
        tool.create_manifest(root, COMMIT, entries, path)
    with pytest.raises(tool.ArtifactError):
        tool.verify_manifest(root, path)


def test_root_slash_and_missing_manifest_file(storage):
    root, entries, path = storage
    # '/' is an explicit local root; no scan is performed.
    entries = [{**row, "path": root.lstrip("/") + "/" + row["path"]} for row in entries]
    tool.create_manifest("/", COMMIT, entries, path)
    assert tool.verify_manifest("/", path)["status"] == "complete"
    with pytest.raises(tool.ArtifactError, match="manifest_file_required"):
        tool.verify_manifest(root, "/")
    with pytest.raises(tool.ArtifactError, match="output_file_required"):
        tool.create_manifest(root, COMMIT, entries, "/")


@pytest.mark.parametrize(
    "target",
    ["leaf", "intermediate", "root", "manifest", "manifest_parent", "output_parent"],
)
def test_symlinks_rejected(storage, tmp_path, target):
    root, entries, path = storage
    create(storage)
    alias = tmp_path / "alias"
    if target == "leaf":
        file = Path(root) / "empty"
        file.unlink()
        file.symlink_to(Path(root) / "nested/opaque.bin")
        assert tool.verify_manifest(root, path)["artifacts"][0]["status"] == "invalid"
    elif target == "intermediate":
        (Path(root) / "nested").rename(Path(root) / "moved")
        (Path(root) / "nested").symlink_to(
            Path(root) / "moved", target_is_directory=True
        )
        assert tool.verify_manifest(root, path)["artifacts"][1]["status"] == "invalid"
    elif target == "root":
        alias.symlink_to(root, target_is_directory=True)
        assert tool.verify_manifest(str(alias), path)["status"] == "incomplete"
    elif target == "manifest":
        alias.symlink_to(path)
        with pytest.raises(tool.ArtifactError, match="not_regular"):
            tool.verify_manifest(root, str(alias))
    elif target == "manifest_parent":
        alias.symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(OSError):
            tool.verify_manifest(root, str(alias / "manifest.json"))
    else:
        alias.symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(OSError):
            tool.create_manifest(root, COMMIT, entries, str(alias / "new.json"))


@pytest.mark.parametrize("kind", ["directory", "fifo", "socket"])
def test_special_files_rejected_without_blocking(storage, monkeypatch, kind):
    root, _, path = storage
    create(storage)
    file = Path(root) / "empty"
    file.unlink()
    with socket.socket(socket.AF_UNIX) as sock:
        if kind == "directory":
            file.mkdir()
        elif kind == "fifo":
            os.mkfifo(file)
        else:
            monkeypatch.chdir(file.parent)
            sock.bind(file.name)
        row = tool.verify_manifest(root, path)["artifacts"][0]
        assert row["status"] == "invalid" and row["error"] == "not_regular"


def test_aliases_duplicates_and_output_collisions(storage, tmp_path):
    root, entries, path = storage
    os.link(Path(root) / "empty", Path(root) / "alias")
    aliased = entries + [{"id": "b", "role": "parameter", "path": "alias"}]
    with pytest.raises(tool.ArtifactError, match="input_alias"):
        tool.create_manifest(root, COMMIT, aliased, path)
    assert not Path(path).exists()
    manifest = create(storage)
    manifest["artifacts"].append(
        {**manifest["artifacts"][0], "id": "b", "path": "alias"}
    )
    save(path, manifest)
    assert tool.verify_manifest(root, path)["artifacts"][1]["error"] == "input_alias"
    # A manifest cannot be one of its own artifact byte references, even if a
    # fabricated declaration claims an impossible self-hash.
    os.link(path, Path(root) / "self.json")
    manifest["artifacts"].append(
        {**manifest["artifacts"][0], "id": "self", "path": "self.json"}
    )
    save(path, manifest)
    report = tool.verify_manifest(root, path)
    assert (
        next(r for r in report["artifacts"] if r["id"] == "self")["error"]
        == "input_alias"
    )
    for output in (str(Path(root) / "empty"), path):
        with pytest.raises(tool.ArtifactError, match="output_input_collision"):
            tool.verify_manifest(root, path, output)
    with pytest.raises(tool.ArtifactError, match="output_input_collision"):
        tool.create_manifest(root, COMMIT, entries, str(Path(root) / "empty"))
    (Path(root) / "empty").unlink()
    with pytest.raises(tool.ArtifactError, match="output_input_collision"):
        tool.verify_manifest(root, path, str(Path(root) / "empty"))
    for existing in (path, str(Path(root) / "alias")):
        with pytest.raises(FileExistsError):
            tool.create_manifest(root, COMMIT, entries[0:1], existing)
    link = tmp_path / "output-link"
    link.symlink_to(path)
    with pytest.raises(FileExistsError):
        tool.verify_manifest(root, path, str(link))


def test_exact_structural_limits(storage, tmp_path):
    root, _, path = storage
    manifest = create(storage)
    full_path = "/".join(["x" * 255] * 3 + ["x" * 254, "x"])
    assert len(full_path) == tool.MAX_PATH
    row = {**manifest["artifacts"][0], "id": "i" * 128, "path": full_path}
    boundary = {**manifest, "artifacts": [row]}
    tool.validate_manifest(boundary)
    jsonschema.validate(boundary, SCHEMA)
    boundary["artifacts"][0]["path"] += "x"
    expect_invalid(boundary, "artifact_path")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(boundary, SCHEMA)
    entries = []
    for index in range(tool.MAX_ENTRIES):
        name = f"file-{index}"
        (Path(root) / name).write_bytes(b"x")
        entries.append(
            {"id": name, "role": tool.ROLES[index % len(tool.ROLES)], "path": name}
        )
    path2 = str(tmp_path / "max.json")
    maximum = tool.create_manifest(root, COMMIT, entries, path2)
    assert tool.verify_manifest(root, path2)["status"] == "complete"
    jsonschema.validate(maximum, SCHEMA)
    with pytest.raises(tool.ArtifactError, match="artifacts_count"):
        tool.create_manifest(
            root, COMMIT, entries + entries[:1], str(tmp_path / "no.json")
        )
    maximum["artifacts"].append(maximum["artifacts"][0])
    expect_invalid(maximum, "artifacts_count")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(maximum, SCHEMA)


def test_manifest_byte_limit_and_bounded_reads(storage, tmp_path, monkeypatch):
    root, _, path = storage
    create(storage)
    raw = Path(path).read_bytes()
    limit = tool.MAX_MANIFEST_BYTES
    Path(path).write_bytes(raw + b" " * (limit - len(raw)))
    original = tool.os.read
    counts = []

    def tracked(fd, count):
        counts.append(count)
        return original(fd, count)

    monkeypatch.setattr(tool.os, "read", tracked)
    assert tool.verify_manifest(root, path)["status"] == "complete"
    assert max(counts) <= tool.CHUNK_BYTES and min(counts) >= 1
    Path(path).write_bytes(raw + b" " * (limit + 1 - len(raw)))
    with pytest.raises(tool.ArtifactError, match="manifest_too_large"):
        tool.verify_manifest(root, path)
    # Exact output bound, independent of the larger fixed production ceiling.
    other = str(tmp_path / "other.json")
    monkeypatch.setattr(tool, "MAX_MANIFEST_BYTES", len(raw))
    tool.create_manifest(root, COMMIT, storage[1], other)
    monkeypatch.setattr(tool, "MAX_MANIFEST_BYTES", len(raw) - 1)
    with pytest.raises(tool.ArtifactError, match="manifest_too_large"):
        tool.create_manifest(root, COMMIT, storage[1], str(tmp_path / "no.json"))
    assert not (tmp_path / "no.json").exists()


def test_large_artifact_streaming_and_no_discovery(storage, tmp_path, monkeypatch):
    root, entries, output = storage
    file = Path(root) / "nested/opaque.bin"
    block = bytes(range(256)) * 256
    with file.open("wb") as stream:
        for _ in range(20):
            stream.write(block)
    (Path(root) / "unselected-link").symlink_to(tmp_path / "absent")

    def prohibited(*args, **kwargs):
        raise AssertionError("no directory discovery or whole-payload reads")

    original = tool.os.read
    counts = []

    def tracked(fd, count):
        counts.append(count)
        return original(fd, count)

    monkeypatch.setattr(tool.os, "read", tracked)
    monkeypatch.setattr(tool.os, "listdir", prohibited)
    monkeypatch.setattr(tool.os, "scandir", prohibited)
    monkeypatch.setattr(Path, "read_bytes", prohibited)
    manifest = tool.create_manifest(root, COMMIT, entries, output)
    assert manifest["artifacts"][1]["bytes"] == 20 * len(block)
    assert manifest["artifacts"][1]["sha256"] == hashlib.sha256(block * 20).hexdigest()
    assert tool.verify_manifest(root, output)["status"] == "complete"
    assert len(counts) > 40 and max(counts) <= tool.CHUNK_BYTES


@pytest.mark.parametrize(
    "mutation",
    [
        "grow",
        "shrink",
        "rewrite",
        "replace",
        "remove",
        "symlink",
        "directory",
        "after_stat",
    ],
)
def test_artifact_mutation_is_explicit(storage, monkeypatch, mutation):
    root, _, path = storage
    create(storage)
    file = Path(root) / "nested/opaque.bin"
    inode = file.stat().st_ino
    original_read = tool.os.read
    changed = False

    def mutate(fd, count):
        nonlocal changed
        data = original_read(fd, count)
        if os.fstat(fd).st_ino == inode and not changed:
            changed = True
            if mutation == "grow":
                with file.open("ab") as stream:
                    stream.write(b"more")
            elif mutation == "shrink":
                file.write_bytes(b"")
            elif mutation == "rewrite":
                file.write_bytes(b"x" * len(data))
            elif mutation == "after_stat":
                # Trigger the identity check against a freshly opened pathname.
                pass
            else:
                file.unlink()
                if mutation == "replace":
                    file.write_bytes(data)
                elif mutation == "symlink":
                    file.symlink_to(Path(root) / "empty")
                elif mutation == "directory":
                    file.mkdir()
        return data

    monkeypatch.setattr(tool.os, "read", mutate)
    if mutation == "after_stat":
        original_stat = tool.os.fstat
        count = 0

        def altered(fd):
            nonlocal count
            info = original_stat(fd)
            if info.st_ino == inode and changed:
                count += 1
                if count == 2:
                    file.unlink()
                    file.write_bytes(b"replacement")
            return info

        monkeypatch.setattr(tool.os, "fstat", altered)
    row = tool.verify_manifest(root, path)["artifacts"][1]
    assert row["status"] == "changed" and row["error"] == "mutated_during_read"
    assert row["observed"] is None


@pytest.mark.parametrize("mutation", ["grow_limit", "truncate", "rewrite", "replace"])
def test_manifest_read_mutation(storage, monkeypatch, mutation):
    root, _, path = storage
    create(storage)
    original = tool.os.read
    manifest_inode = os.stat(path).st_ino
    once = False

    def mutate(fd, count):
        nonlocal once
        data = original(fd, count)
        if os.fstat(fd).st_ino == manifest_inode and not once:
            once = True
            if mutation == "grow_limit":
                with open(path, "ab") as stream:
                    stream.write(b" " * tool.MAX_MANIFEST_BYTES)
            elif mutation == "truncate":
                Path(path).write_bytes(b"")
            elif mutation == "rewrite":
                Path(path).write_bytes(data)
            else:
                Path(path).unlink()
                Path(path).write_bytes(data)
        return data

    monkeypatch.setattr(tool.os, "read", mutate)
    code = "manifest_too_large" if mutation == "grow_limit" else "mutated_during_read"
    with pytest.raises(tool.ArtifactError, match=code):
        tool.verify_manifest(root, path)


def test_open_races_reject_special_or_replaced_file(storage, monkeypatch):
    root, _, path = storage
    create(storage)
    original = tool.os.fstat
    inode = os.stat(Path(root) / "empty").st_ino

    def special(fd):
        info = original(fd)
        return SimpleNamespace(st_mode=stat.S_IFDIR) if info.st_ino == inode else info

    monkeypatch.setattr(tool.os, "fstat", special)
    assert tool.verify_manifest(root, path)["artifacts"][0]["error"] == "not_regular"
    monkeypatch.setattr(tool.os, "fstat", original)
    real_open = tool.os.open
    once = False

    def replace(name, *args, **kwargs):
        nonlocal once
        if name == "empty" and not once:
            once = True
            (Path(root) / "empty").rename(Path(root) / "previous")
            (Path(root) / "empty").write_bytes(b"x")
        return real_open(name, *args, **kwargs)

    monkeypatch.setattr(tool.os, "open", replace)
    assert tool.verify_manifest(root, path)["artifacts"][0]["status"] == "changed"


@pytest.mark.parametrize(
    "operation", ["open", "fdopen", "write", "flush", "fsync", "link"]
)
def test_output_failures_leave_no_partial_output(
    storage, tmp_path, monkeypatch, operation
):
    root, entries, output = storage
    original_open = tool.os.open
    original_fdopen = tool.os.fdopen

    def fail(*args, **kwargs):
        raise OSError(errno.EIO, "artificial output failure")

    if operation == "open":

        def failing_open(name, *args, **kwargs):
            if str(name).startswith(".calculator-artifacts-"):
                fail()
            return original_open(name, *args, **kwargs)

        monkeypatch.setattr(tool.os, "open", failing_open)
    elif operation == "fdopen":
        monkeypatch.setattr(tool.os, "fdopen", fail)
    elif operation in ("write", "flush"):

        class BrokenStream:
            def __init__(self, fd):
                self.stream = original_fdopen(fd, "wb", closefd=False)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def write(self, data):
                if operation == "write":
                    self.stream.write(data[:10])
                    fail()
                return self.stream.write(data)

            def flush(self):
                fail()

        monkeypatch.setattr(tool.os, "fdopen", lambda fd, *a, **kw: BrokenStream(fd))
    else:
        monkeypatch.setattr(tool.os, operation, fail)
    with pytest.raises(OSError):
        tool.create_manifest(root, COMMIT, entries, output)
    assert not Path(output).exists()
    assert not list(tmp_path.glob(".calculator-artifacts-*"))


def test_no_clobber_publication_race(storage, monkeypatch):
    root, entries, output = storage
    original = tool.os.link

    def raced(*args, **kwargs):
        Path(output).write_bytes(b"another writer")
        return original(*args, **kwargs)

    monkeypatch.setattr(tool.os, "link", raced)
    with pytest.raises(FileExistsError):
        tool.create_manifest(root, COMMIT, entries, output)
    assert Path(output).read_bytes() == b"another writer"
    assert not list(Path(output).parent.glob(".calculator-artifacts-*"))


def test_create_input_failures_never_publish(storage, tmp_path):
    root, entries, output = storage
    for broken, commit in [
        ([], COMMIT),
        (entries, "bad"),
        (entries + entries[:1], COMMIT),
        ([{**entries[0], "path": "not-found"}], COMMIT),
    ]:
        with pytest.raises(tool.ArtifactError):
            tool.create_manifest(root, commit, broken, output)
        assert not Path(output).exists()
    with pytest.raises(FileNotFoundError):
        tool.create_manifest(root, COMMIT, entries, str(tmp_path / "absent/out"))


def test_short_reads_and_unexpected_eof(storage, monkeypatch):
    root, _, path = storage
    create(storage)
    original = tool.os.read

    def short(fd, count):
        return original(fd, min(count, 3))

    monkeypatch.setattr(tool.os, "read", short)
    assert tool.verify_manifest(root, path)["status"] == "complete"
    artifact_inode = os.stat(Path(root) / "nested/opaque.bin").st_ino

    def artifact_eof(fd, count):
        return b"" if os.fstat(fd).st_ino == artifact_inode else original(fd, count)

    monkeypatch.setattr(tool.os, "read", artifact_eof)
    row = tool.verify_manifest(root, path)["artifacts"][1]
    assert row["status"] == "changed" and row["error"] == "mutated_during_read"
    monkeypatch.setattr(tool.os, "read", lambda fd, count: b"")
    with pytest.raises(tool.ArtifactError, match="mutated_during_read"):
        tool.verify_manifest(root, path)


def test_case_variant_output_collisions_include_missing_inputs(storage):
    root, entries, path = storage
    create(storage)
    (Path(root) / "empty").unlink()
    with pytest.raises(tool.ArtifactError, match="output_input_collision"):
        tool.verify_manifest(root, path, str(Path(root) / "EMPTY"))
    with pytest.raises(tool.ArtifactError, match="output_input_collision"):
        tool.create_manifest(root, COMMIT, entries, str(Path(root) / "EMPTY"))
    with pytest.raises(tool.ArtifactError, match="output_input_collision"):
        tool.verify_manifest(root, path, str(Path(path).with_name("MANIFEST.JSON")))


def test_json_recursion_failure_is_an_invalid_manifest(storage, monkeypatch):
    root, _, path = storage
    create(storage)

    def exceeds_depth(*args, **kwargs):
        raise RecursionError("artificial interpreter depth failure")

    monkeypatch.setattr(tool.json, "loads", exceeds_depth)
    with pytest.raises(tool.ArtifactError, match="malformed_json"):
        tool.verify_manifest(root, path)


def test_cli_success_incomplete_and_errors(storage, tmp_path, capsys):
    root, entries, output = storage
    args = ["create", "--root", root, "--producer-commit", COMMIT, "--output", output]
    for row in entries:
        args += ["--entry", row["id"], row["role"], row["path"]]
    assert tool.main(args) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(Path(output).read_text())
    verify = ["verify", "--root", root, "--manifest", output]
    assert tool.main(verify) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    (Path(root) / "empty").unlink()
    assert tool.main(verify + ["--output", str(tmp_path / "report.json")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "incomplete"
    assert report == json.loads((tmp_path / "report.json").read_text())
    assert tool.main(args) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "not_found"
    (Path(root) / "empty").write_bytes(b"")
    assert tool.main(args) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "io_error"
    assert (
        tool.main(["verify", "--root", root, "--manifest", str(tmp_path / "absent")])
        == 2
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "invalid",
        "error": "not_found",
    }
    Path(output).write_text("{}")
    assert tool.main(verify) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "object_keys"
    assert not capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["create"],
        ["verify"],
        ["create", "--root", "/", "--producer-commit", COMMIT, "--output", "/x"],
        ["verify", "--manifest", "/x"],
    ],
)
def test_cli_required_arguments(args, capsys):
    with pytest.raises(SystemExit) as result:
        tool.main(args)
    assert result.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_script_entrypoint(storage, monkeypatch, capsys):
    root, _, path = storage
    create(storage)
    monkeypatch.setattr(
        sys, "argv", [tool.__file__, "verify", "--root", root, "--manifest", path]
    )
    with pytest.raises(SystemExit) as result:
        runpy.run_path(tool.__file__, run_name="__main__")
    assert result.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
