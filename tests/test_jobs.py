"""Offline calculator job runner: contract, failure injection and real smoke."""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from regsite import jobs
from regsite.conditional_math import ConditionalError
from regsite.profiles import PROFILES
from regsite.structures import BackendError

ROOT = Path(__file__).resolve().parents[1]
LIMITS = {
    "seconds_per_job": 30,
    "seconds_total": 120,
    "stdout_bytes_per_job": 65_536,
    "stderr_bytes_per_job": 65_536,
    "output_bytes_total": 1_048_576,
}
# One synthetic calculator: its request selects the behaviour under test.
SCRIPT = r"""
import json, os, signal, subprocess, sys, time
request = json.loads(sys.stdin.buffer.read())
sys.stderr.write(json.dumps(sys.argv[1:]))
sys.stderr.flush()
action = request.get("action")
if action == "env":
    sys.stdout.write(json.dumps(dict(os.environ), sort_keys=True))
elif action == "echo":
    sys.stdin.buffer.seek(0)
    sys.stdout.buffer.write(sys.stdin.buffer.read())
elif action == "flood":
    stream = sys.stdout if request.get("stream", "stdout") == "stdout" else sys.stderr
    stream.write("x" * request["bytes"])
    stream.flush()
elif action == "grandchild":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    sys.stdout.write(str(child.pid))
    sys.stdout.flush()
    time.sleep(request["seconds"])
elif action == "sleep":
    sys.stdout.write(request.get("stdout", ""))
    sys.stdout.flush()
    time.sleep(request["seconds"])
elif action == "marker":
    if not os.path.exists(request["path"]):
        open(request["path"], "w").close()
        time.sleep(60)
elif action == "parent":
    os.kill(os.getppid(), signal.SIGTERM)
    time.sleep(60)
elif action == "ignore":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    sys.stdout.write("ready")
    sys.stdout.flush()
    time.sleep(60)
elif action == "kill":
    os.kill(os.getpid(), signal.SIGKILL)
elif action == "group":
    sys.stdout.write(str(os.getpgrp()))
elif action == "close":
    os.close(1)
    os.close(2)
    time.sleep(0.3)
sys.stdout.write(request.get("stdout", ""))
raise SystemExit(request.get("exit", 0))
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def schema(name: str) -> Draft202012Validator:
    path = ROOT / "schemas" / f"calculator-job-{name}-1.schema.json"
    value = json.loads(path.read_text())
    Draft202012Validator.check_schema(value)
    return Draft202012Validator(value)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


@pytest.fixture
def area(tmp_path: Path) -> Path:
    return tmp_path.resolve()


@pytest.fixture
def synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    for kind in jobs.KINDS:
        monkeypatch.setitem(jobs.ENTRY_POINTS, kind, ("-c", SCRIPT))


@pytest.fixture
def fast_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "TERMINATION_GRACE_SECONDS", 0.3)


def campaign(area: Path, specs: list[dict], **limits: float) -> tuple[str, str]:
    """Write requests and a manifest under area/in; return (manifest, output)."""
    base = area / "in"
    base.mkdir(exist_ok=True)
    rows = []
    for spec in specs:
        raw = spec.get("raw", json.dumps(spec.get("request", {})).encode())
        (base / f"{spec['id']}.json").write_bytes(raw)
        rows.append(
            {
                "id": spec["id"],
                "kind": spec.get("kind", "promoter"),
                "request": {"path": f"{spec['id']}.json", "sha256": sha(raw)},
                "backend": spec.get("backend", False),
                "options": spec.get("options", {}),
            }
        )
    manifest = {
        "schema_version": jobs.MANIFEST_VERSION,
        "limits": {**LIMITS, **limits},
        "jobs": rows,
    }
    dump(base / "manifest.json", manifest)
    return str(base / "manifest.json"), str(area / "out")


def attempt(out: str, job: str, number: int) -> Path:
    return Path(out) / "jobs" / job / f"attempt-{number:04d}"


def receipt(out: str, job: str, number: int = 1) -> dict:
    return load(attempt(out, job, number) / "receipt.json")


def assert_documents(out: str) -> None:
    """Every stored record matches its published schema."""
    root = Path(out)
    schema("campaign").validate(load(root / "campaign.json"))
    if (root / "summary.json").exists():
        schema("summary").validate(load(root / "summary.json"))
    for path in root.glob("jobs/*/attempt-*/receipt.json"):
        schema("receipt").validate(load(path))
    for path in root.glob("jobs/*/attempt-*/launch.json"):
        schema("launch").validate(load(path))


def wait_gone(pid: int) -> None:
    limit = time.monotonic() + 10
    while time.monotonic() < limit:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError(f"process {pid} survived")


def manifest_value() -> dict:
    return {
        "schema_version": jobs.MANIFEST_VERSION,
        "limits": dict(LIMITS),
        "jobs": [
            {
                "id": "a",
                "kind": "promoter",
                "request": {"path": "a.json", "sha256": "0" * 64},
                "backend": False,
                "options": {"calibration": "in_vitro", "seconds_per_batch": 2.5},
            },
            {
                "id": "b",
                "kind": "rbs",
                "request": {"path": "sub/b.json", "sha256": "1" * 64},
                "backend": True,
                "options": {"profile": "historical", "seconds_per_record": 60},
            },
        ],
    }


# Manifest structure ----------------------------------------------------------


def test_valid_manifest_agrees_with_schema() -> None:
    value = manifest_value()
    jobs.validate_manifest(value)
    schema("manifest").validate(value)


def set_path(value: dict, path: tuple, item: object) -> None:
    target = value
    for key in path[:-1]:
        target = target[key]
    if item is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = item


@pytest.mark.parametrize(
    ("path", "item", "code"),
    [
        (("extra",), 1, "manifest_keys"),
        (("jobs",), KeyError, "manifest_keys"),
        (("schema_version",), "calculator-job-manifest-2", "schema_version"),
        (("limits", "extra"), 1, "limits"),
        (("limits", "seconds_total"), KeyError, "limits"),
        (("limits", "seconds_per_job"), True, "limits"),
        (("limits", "seconds_per_job"), "30", "limits"),
        (("limits", "seconds_per_job"), 0, "limits"),
        (("limits", "seconds_per_job"), -1.5, "limits"),
        (("limits", "seconds_per_job"), float("inf"), "limits"),
        (("limits", "seconds_per_job"), 3600.5, "limits"),
        (("limits", "seconds_total"), 86_401, "limits"),
        (("limits", "stdout_bytes_per_job"), 1.0, "limits"),
        (("limits", "stdout_bytes_per_job"), 0, "limits"),
        (("limits", "stdout_bytes_per_job"), 134_217_729, "limits"),
        (("limits", "stderr_bytes_per_job"), 1_048_577, "limits"),
        (("limits", "output_bytes_total"), 131_071, "limits"),
        (("limits", "output_bytes_total"), 17_179_869_185, "limits"),
        (("jobs",), {}, "jobs_count"),
        (("jobs",), [], "jobs_count"),
        (("jobs", 0, "extra"), 1, "job_keys"),
        (("jobs", 0, "options"), KeyError, "job_keys"),
        (("jobs", 0, "id"), ".a", "job_id"),
        (("jobs", 0, "id"), "a/b", "job_id"),
        (("jobs", 0, "id"), "a" * 65, "job_id"),
        (("jobs", 0, "id"), 7, "job_id"),
        (("jobs", 0, "id"), "B", "duplicate_job_id"),
        (("jobs", 0, "kind"), "operon", "kind"),
        (("jobs", 0, "kind"), ["promoter"], "kind"),
        (("jobs", 0, "request", "extra"), 1, "request_keys"),
        (("jobs", 0, "request", "path"), "../a.json", "request_path"),
        (("jobs", 0, "request", "path"), "/a.json", "request_path"),
        (("jobs", 0, "request", "path"), "a\\b.json", "request_path"),
        (("jobs", 0, "request", "path"), "a//b.json", "request_path"),
        (("jobs", 0, "request", "path"), "./a.json", "request_path"),
        (("jobs", 0, "request", "path"), "a/" * 512 + "a", "request_path"),
        (("jobs", 0, "request", "sha256"), "A" * 64, "sha256"),
        (("jobs", 0, "backend"), 0, "backend_flag"),
        (("jobs", 0, "backend"), True, "backend_flag"),
        (("jobs", 1, "backend"), False, "backend_flag"),
        (("jobs", 0, "options"), [], "options"),
        (("jobs", 0, "options", "profile"), "historical", "options"),
        (("jobs", 0, "options", "calibration"), "native", "options"),
        (("jobs", 0, "options", "states"), True, "options"),
        (("jobs", 0, "options", "seconds_per_batch"), 0, "options"),
        (("jobs", 0, "options", "seconds_per_batch"), True, "options"),
        (("jobs", 0, "options", "seconds_per_batch"), "2.5", "options"),
        (("jobs", 0, "options", "seconds_per_batch"), float("nan"), "options"),
    ],
)
def test_manifest_refusals(path: tuple, item: object, code: str) -> None:
    value = manifest_value()
    set_path(value, path, item)
    with pytest.raises(jobs.JobError) as error:
        jobs.validate_manifest(value)
    assert error.value.code == code


def test_manifest_job_count_limit() -> None:
    value = manifest_value()
    row = value["jobs"][0]
    value["jobs"] = [{**row, "id": f"j{index}"} for index in range(256)]
    jobs.validate_manifest(value)
    value["jobs"].append({**row, "id": "extra"})
    with pytest.raises(jobs.JobError, match="jobs_count"):
        jobs.validate_manifest(value)
    assert schema("manifest").is_valid(value) is False


def test_schema_mirrors_runtime_constants() -> None:
    manifest = load(ROOT / "schemas/calculator-job-manifest-1.schema.json")
    variants = manifest["properties"]["jobs"]["items"]["oneOf"]
    assert [v["properties"]["kind"]["const"] for v in variants] == list(jobs.KINDS)
    for variant in variants:
        kind = variant["properties"]["kind"]["const"]
        options = variant["properties"]["options"]["properties"]
        assert set(options) == set(jobs.OPTIONS[kind])
        for name, rule in jobs.OPTIONS[kind].items():
            if rule != jobs.SECONDS:
                assert options[name]["enum"] == list(rule)
    rbs = variants[0]["properties"]["options"]["properties"]["profile"]["enum"]
    assert rbs == [profile.name for profile in PROFILES]
    limits = manifest["properties"]["limits"]["properties"]
    assert {name: limits[name]["maximum"] for name in limits} == jobs.LIMITS
    summary = load(ROOT / "schemas/calculator-job-summary-1.schema.json")
    counts = summary["oneOf"][1]["properties"]["counts"]["properties"]
    assert list(counts) == list(jobs.STATES)
    receipt_schema = load(ROOT / "schemas/calculator-job-receipt-1.schema.json")
    assert receipt_schema["properties"]["outcome"]["enum"] == [
        *jobs.TERMINAL,
        *jobs.UNFINISHED,
    ]


def test_command_template_is_fixed_and_option_ordered() -> None:
    first, second = manifest_value()["jobs"]
    assert jobs.command_template(first) == [
        "{python}",
        "-P",
        "-s",
        "-c",
        "from regsite.promoter_cli import main; raise SystemExit(main())",
        "-",
        "--format",
        "json",
        "--calibration",
        "in_vitro",
        "--seconds-per-batch",
        "2.5",
    ]
    assert jobs.command_template(second) == [
        "{python}",
        "-P",
        "-s",
        "-m",
        "regsite",
        "-",
        "--format",
        "json",
        "--backend-root",
        "{backend_root}",
        "--profile",
        "historical",
        "--seconds-per-record",
        "60",
    ]
    conditional = {**first, "kind": "conditional", "options": {}}
    assert jobs.command_template(conditional)[3:] == [
        "-m",
        "regsite.conditional_cli",
        "-",
    ]


# Manifest and request files -------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"{", "malformed_json"),
        (b"\xef\xbb\xbf{}", "malformed_json"),
        (b'{"a": "\xff"}', "malformed_json"),
        (b'{"a": {"b": 1, "b": 2}}', "duplicate_json_key"),
        (b'{"a": NaN}', "nonfinite_json"),
        (b'{"a": -Infinity}', "nonfinite_json"),
        (b'{"a": 1e999}', "nonfinite_json"),
        (b"[" * 500_000 + b"]" * 500_000, "malformed_json"),
        (b"[]", "manifest_keys"),
        (b" " * (jobs.MAX_MANIFEST_BYTES - 2) + b"{}", "manifest_keys"),
        (b" " * (jobs.MAX_MANIFEST_BYTES - 1) + b"{}", "manifest_too_large"),
    ],
    ids=lambda value: value[:24] if isinstance(value, bytes) else None,
)
def test_manifest_decoding(area: Path, raw: bytes, code: str) -> None:
    (area / "m.json").write_bytes(raw)
    with pytest.raises(jobs.JobError) as error:
        jobs.load_manifest(str(area / "m.json"))
    assert error.value.code == code


def test_manifest_paths_are_absolute_regular_and_unlinked(area: Path) -> None:
    manifest, _ = campaign(area, [{"id": "a"}])
    value, raw = jobs.load_manifest(manifest)
    assert raw == Path(manifest).read_bytes() and value["jobs"][0]["id"] == "a"
    for bad in ("in/manifest.json", "/", "/a/../b", "/a/./b", "/a:b", "/a\\b", 7):
        with pytest.raises(jobs.JobError, match="manifest_path"):
            jobs.load_manifest(bad)  # type: ignore[arg-type]
    (area / "link.json").symlink_to(manifest)
    (area / "linked").symlink_to(area / "in")
    os.mkfifo(area / "fifo")
    for unavailable in ("missing.json", "link.json", "linked/manifest.json"):
        with pytest.raises(jobs.JobError, match="manifest_unavailable"):
            jobs.load_manifest(str(area / unavailable))
    for special in ("in", "fifo"):
        with pytest.raises(jobs.JobError, match="manifest_unavailable"):
            jobs.load_manifest(str(area / special))


def test_request_refusals_leave_no_output(area: Path, synthetic: None) -> None:
    manifest, out = campaign(area, [{"id": "a", "request": {"exit": 0}}])
    request = area / "in" / "a.json"
    original = request.read_bytes()
    request.write_bytes(b'{"exit": 1}')
    with pytest.raises(jobs.JobError, match="request_mismatch"):
        jobs.run_campaign(manifest, out)
    request.unlink()
    with pytest.raises(jobs.JobError, match="request_unavailable"):
        jobs.run_campaign(manifest, out)
    (area / "elsewhere.json").write_bytes(original)
    request.symlink_to(area / "elsewhere.json")
    with pytest.raises(jobs.JobError, match="request_unavailable"):
        jobs.run_campaign(manifest, out)
    request.unlink()
    request.write_bytes(b" " * (jobs.MAX_REQUEST_BYTES + 1))
    with pytest.raises(jobs.JobError, match="request_too_large"):
        jobs.run_campaign(manifest, out)
    assert not Path(out).exists()
    with pytest.raises(jobs.JobError, match="manifest_unavailable"):
        jobs._load_requests(str(area / "gone" / "m.json"), load(Path(manifest)))


def test_request_in_subdirectory_refuses_linked_parent(
    area: Path, synthetic: None
) -> None:
    manifest, out = campaign(area, [{"id": "a", "request": {"stdout": "ok"}}])
    value = load(Path(manifest))
    (area / "in" / "data").mkdir()
    (area / "in" / "a.json").rename(area / "in" / "data" / "a.json")
    value["jobs"][0]["request"]["path"] = "data/a.json"
    dump(Path(manifest), value)
    summary = jobs.run_campaign(manifest, out)
    assert summary["status"] == "complete"
    (area / "real").mkdir()
    (area / "in" / "data" / "a.json").rename(area / "real" / "a.json")
    (area / "in" / "data").rmdir()
    (area / "in" / "data").symlink_to(area / "real")
    with pytest.raises(jobs.JobError, match="request_unavailable"):
        jobs.run_campaign(manifest, str(area / "out2"))


def test_read_errors_are_stable(area: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (area / "f").write_bytes(b"data")

    def fail(*_: object) -> bytes:
        raise OSError("io")

    with jobs._directory(str(area).split("/")[1:]) as fd:
        monkeypatch.setattr(jobs.os, "read", fail)
        with pytest.raises(jobs.JobError, match="request_unavailable"):
            jobs._read(fd, "f", 10, "request")


# Output directory -----------------------------------------------------------


def test_output_directory_refusals(area: Path, synthetic: None) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    Path(out).mkdir()
    (Path(out) / "keep.txt").write_text("unrelated")
    with pytest.raises(jobs.JobError, match="output_exists"):
        jobs.run_campaign(manifest, out)
    assert (Path(out) / "keep.txt").read_text() == "unrelated"
    assert os.listdir(out) == ["keep.txt"]
    for bad in ("out", "/", "/a/../b"):
        with pytest.raises(jobs.JobError, match="output_path"):
            jobs.run_campaign(manifest, bad)
    missing = str(area / "missing" / "out")
    with pytest.raises(jobs.JobError, match="output_parent_unavailable"):
        jobs.run_campaign(manifest, missing)
    with pytest.raises(jobs.JobError, match="output_parent_unavailable"):
        jobs.run_campaign(manifest, missing, allow_repository_output=True)
    for collision in (manifest, str(area / "in"), str(area / "IN")):
        with pytest.raises(jobs.JobError, match="output_input_collision"):
            jobs.run_campaign(manifest, collision)
    with pytest.raises(jobs.JobError, match="output_unavailable"):
        jobs.resume_campaign(manifest, str(area / "never"))
    with pytest.raises(jobs.JobError, match="output_unavailable"):
        jobs.verify_campaign(manifest, str(area / "never"))
    with pytest.raises(jobs.JobError, match="output_path"):
        jobs.verify_campaign(manifest, "relative")


@pytest.mark.parametrize("marker", ["directory", "file"])
def test_output_inside_git_requires_opt_in(
    area: Path, synthetic: None, marker: str
) -> None:
    manifest, _ = campaign(area, [{"id": "a"}])
    repository = area / "repo" / "nested"
    repository.mkdir(parents=True)
    git = area / "repo" / ".git"
    git.mkdir() if marker == "directory" else git.write_text("gitdir: x")
    out = str(repository / "out")
    with pytest.raises(jobs.JobError, match="output_in_repository"):
        jobs.run_campaign(manifest, out)
    assert not Path(out).exists()
    summary = jobs.run_campaign(manifest, out, allow_repository_output=True)
    assert summary["status"] == "complete"
    with pytest.raises(jobs.JobError, match="output_in_repository"):
        jobs.resume_campaign(manifest, out)


# Identity --------------------------------------------------------------------


def test_code_fingerprint(area: Path) -> None:
    package = area / "package"
    (package / "data").mkdir(parents=True)
    (package / "__pycache__").mkdir()
    (package / "__pycache__" / "x.pyc").write_bytes(b"cache")
    (package / "a.py").write_text("a = 1\n")
    (package / "data" / "t.json").write_text("{}")
    first = jobs.code_fingerprint(str(package))
    assert first["files"] == 2
    (package / "__pycache__" / "x.pyc").write_bytes(b"changed cache")
    assert jobs.code_fingerprint(str(package)) == first
    (package / "data" / "t.json").write_text('{"changed": true}')
    changed = jobs.code_fingerprint(str(package))
    assert changed["sha256"] != first["sha256"]
    (package / "data" / "t.json").rename(package / "data" / "u.json")
    renamed = jobs.code_fingerprint(str(package))
    assert renamed["sha256"] not in (first["sha256"], changed["sha256"])
    (package / "link.py").symlink_to(package / "a.py")
    with pytest.raises(jobs.JobError, match="runtime_identity"):
        jobs.code_fingerprint(str(package))
    (package / "link.py").unlink()
    (package / "linked").symlink_to(package / "data")
    with pytest.raises(jobs.JobError, match="runtime_identity"):
        jobs.code_fingerprint(str(package))
    (package / "linked").unlink()
    (package / "a.py").chmod(0)
    try:
        with pytest.raises(jobs.JobError, match="runtime_identity"):
            jobs.code_fingerprint(str(package))
    finally:
        (package / "a.py").chmod(0o600)
    with pytest.raises(jobs.JobError, match="runtime_identity"):
        jobs.code_fingerprint(str(area / "empty-or-missing"))


def test_runtime_identity_binds_installed_code_and_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = jobs.runtime_identity()
    assert identity["code"] == jobs.code_fingerprint(jobs.PACKAGE_DIR)
    assert identity["code"]["files"] > 30
    assert identity["regsite_version"] == jobs.regsite.__version__
    assert identity["python"]["version"] == sys.version
    for executable in ("", "python3", "/nonexistent/python"):
        monkeypatch.setattr(jobs.sys, "executable", executable)
        with pytest.raises(jobs.JobError, match="runtime_identity"):
            jobs.runtime_identity()


class FakeRna:
    identity = {"name": "RNAstructure", "binary_sha256": {"Fold": "1" * 64}}
    roots: list = []

    @classmethod
    def open(cls, root: str) -> SimpleNamespace:
        cls.roots.append(root)
        return SimpleNamespace(identity=dict(cls.identity))


def fake_verify(root: str, parameters: dict, deadline: float) -> tuple:
    assert "backend_pins" in parameters and deadline > time.monotonic()
    return Path(root), {"fold_sha256": "2" * 64}


def test_backend_identity_reuses_verifiers(
    area: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "RnaStructure", FakeRna)
    monkeypatch.setattr(jobs, "verify_backend", fake_verify)
    value = manifest_value()
    rbs, promoter = value["jobs"][1], value["jobs"][0]
    conditional = {**promoter, "id": "c", "kind": "conditional", "backend": True}
    root = str(area)

    def identity(*rows: dict, backend: str | None = root) -> dict:
        return jobs.backend_identity({"jobs": list(rows)}, backend)

    assert identity(promoter, backend=None) == {
        "rnastructure": None,
        "conditional_original": None,
    }
    assert identity(rbs) == {
        "rnastructure": FakeRna.identity,
        "conditional_original": None,
    }
    assert identity(conditional) == {
        "rnastructure": None,
        "conditional_original": {"fold_sha256": "2" * 64},
    }
    assert identity(rbs, conditional)["conditional_original"] is not None
    assert FakeRna.roots[-1] == root
    for rows, backend, code in (
        ((rbs,), None, "backend_root_required"),
        ((promoter,), root, "backend_root_unused"),
        ((rbs,), "relative", "backend_root_path"),
    ):
        with pytest.raises(jobs.JobError, match=code):
            identity(*rows, backend=backend)

    def broken(*_: object) -> None:
        raise BackendError("bad")

    monkeypatch.setattr(FakeRna, "open", broken)
    with pytest.raises(jobs.JobError, match="backend_identity"):
        identity(rbs)

    def refused(*_: object) -> None:
        raise ConditionalError("backend_identity", "patched")

    monkeypatch.setattr(jobs, "verify_backend", refused)
    with pytest.raises(jobs.JobError, match="backend_identity"):
        identity(conditional)
    monkeypatch.setattr(jobs, "verify_backend", fake_verify)
    monkeypatch.setattr(jobs, "PARAMETER_SHA256", "0" * 64)
    with pytest.raises(jobs.JobError, match="backend_identity"):
        identity(conditional)


def test_real_backend_identity_matches_native_verifier(real_backend) -> None:
    value = manifest_value()
    identity = jobs.backend_identity(
        {"jobs": [value["jobs"][1]]}, str(real_backend.root)
    )
    assert identity["rnastructure"] == real_backend.identity


def test_backend_root_reaches_only_requesting_jobs(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "RnaStructure", FakeRna)
    monkeypatch.setattr(jobs, "verify_backend", fake_verify)
    monkeypatch.setenv("REGSITE_RNASTRUCTURE", "/must/not/leak")
    manifest, out = campaign(
        area,
        [
            {
                "id": "r",
                "kind": "rbs",
                "backend": True,
                "options": {"profile": "context2017"},
            },
            {"id": "c", "kind": "conditional", "backend": True},
            {"id": "t", "kind": "transcript", "request": {"action": "env"}},
        ],
    )
    backend = str(area / "backend")
    summary = jobs.run_campaign(manifest, out, backend_root=backend)
    assert summary["status"] == "complete"
    argv = json.loads((attempt(out, "r", 1) / "stderr").read_text())
    assert argv == [
        "-",
        "--format",
        "json",
        "--backend-root",
        backend,
        "--profile",
        "context2017",
    ]
    assert receipt(out, "r")["argv"][5:] == [
        "-",
        "--format",
        "json",
        "--backend-root",
        "{backend_root}",
        "--profile",
        "context2017",
    ]
    assert json.loads((attempt(out, "c", 1) / "stderr").read_text()) == [
        "-",
        "--backend-root",
        backend,
    ]
    environment = json.loads((attempt(out, "t", 1) / "stdout").read_text())
    # Added inside the child by PEP 538 locale coercion and by macOS libc.
    environment.pop("LC_CTYPE", None)
    environment.pop("__CF_USER_TEXT_ENCODING", None)
    assert environment == {
        "PATH": "/bin:/usr/bin",
        "PYTHONPATH": os.path.dirname(jobs.PACKAGE_DIR),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "OMP_NUM_THREADS": "1",
        "TMPDIR": jobs.tempfile.gettempdir(),
    }
    stored = load(Path(out) / "campaign.json")
    assert stored["backend"] == {
        "rnastructure": FakeRna.identity,
        "conditional_original": {"fold_sha256": "2" * 64},
    }
    assert_documents(out)
    monkeypatch.setattr(FakeRna, "identity", {"name": "other"})
    with pytest.raises(jobs.JobError, match="backend_mismatch"):
        jobs.resume_campaign(manifest, out, backend_root=backend)
    with pytest.raises(jobs.JobError, match="backend_root_required"):
        jobs.resume_campaign(manifest, out)


def test_resume_refuses_changed_runtime(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a", "request": {"exit": 1}}])
    jobs.run_campaign(manifest, out)
    real = jobs.runtime_identity()
    monkeypatch.setattr(
        jobs, "runtime_identity", lambda: {**real, "regsite_version": "other"}
    )
    with pytest.raises(jobs.JobError, match="runtime_mismatch"):
        jobs.resume_campaign(manifest, out)


@pytest.mark.parametrize("failure", ["changed", "unverifiable"])
def test_identity_change_during_job_is_not_terminal(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    manifest, out = campaign(area, [{"id": "a"}, {"id": "b"}])
    original, calls = jobs._identity, []

    def drifting(manifest: dict, backend_root: str | None) -> dict:
        value = original(manifest, backend_root)
        calls.append(value)
        if len(calls) > 1 and failure == "changed":
            return {**value, "runtime": {**value["runtime"], "code": {}}}
        if len(calls) > 1:
            raise jobs.JobError("runtime_identity")
        return value

    monkeypatch.setattr(jobs, "_identity", drifting)
    summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "runtime_changed"
    assert receipt(out, "a")["outcome"] == "runtime_changed"
    assert receipt(out, "a")["exit_code"] == 0
    assert [row["state"] for row in summary["jobs"]] == ["unfinished", "unstarted"]
    assert jobs.exit_code(summary) == 3


# Outcomes --------------------------------------------------------------------


def test_native_exit_statuses_and_bytes_are_preserved(
    area: Path, synthetic: None
) -> None:
    specs = [
        {"id": "ok", "request": {"action": "echo", "exit": 0}},
        {"id": "partial", "request": {"stdout": '{"status": "partial"}', "exit": 1}},
        {"id": "refused", "kind": "conditional", "request": {"exit": 2}},
        {"id": "abnormal", "kind": "compare", "request": {"exit": 7}},
        {"id": "killed", "kind": "transcript", "request": {"action": "kill"}},
        {"id": "closed", "request": {"action": "close"}},
    ]
    manifest, out = campaign(area, specs)
    summary = jobs.run_campaign(manifest, out)
    states = {row["id"]: row["state"] for row in summary["jobs"]}
    assert states == {
        "ok": "succeeded",
        "partial": "partial",
        "refused": "refused",
        "abnormal": "abnormal_exit",
        "killed": "abnormal_exit",
        "closed": "succeeded",
    }
    assert summary["counts"] == {
        **{name: 0 for name in jobs.STATES},
        "succeeded": 2,
        "partial": 1,
        "refused": 1,
        "abnormal_exit": 2,
    }
    assert summary["status"] == "complete" and summary["stop_reason"] is None
    assert jobs.exit_code(summary) == 1
    request = (area / "in" / "ok.json").read_bytes()
    assert (attempt(out, "ok", 1) / "stdout").read_bytes() == request
    assert (Path(out) / "jobs" / "ok" / "request.json").read_bytes() == request
    assert (attempt(out, "partial", 1) / "stdout").read_text() == (
        '{"status": "partial"}'
    )
    killed = receipt(out, "killed")
    assert (killed["exit_code"], killed["signal"]) == (None, signal.SIGKILL)
    assert receipt(out, "abnormal")["exit_code"] == 7
    for row in summary["jobs"]:
        stored = receipt(out, row["id"])
        data = (attempt(out, row["id"], 1) / "stdout").read_bytes()
        assert row["stdout"] == {
            "path": f"jobs/{row['id']}/attempt-0001/stdout",
            "sha256": sha(data),
            "bytes": len(data),
        }
        assert stored["terminal"] is True
        assert stored["request"]["bytes"] == len(
            (area / "in" / f"{row['id']}.json").read_bytes()
        )
    assert summary["output_bytes"] == sum(
        path.stat().st_size for path in Path(out).glob("jobs/*/attempt-*/std*")
    )
    assert load(Path(out) / "summary.json") == summary
    assert_documents(out)
    assert jobs.verify_campaign(manifest, out)["jobs"] == summary["jobs"]
    resumed = jobs.resume_campaign(manifest, out)
    assert resumed["attempts"] == 6 and resumed["command"] == "resume"
    assert not attempt(out, "partial", 2).exists()


def test_timeout_kills_process_group(
    area: Path, synthetic: None, fast_stop: None
) -> None:
    manifest, out = campaign(
        area,
        [{"id": "slow", "request": {"action": "grandchild", "seconds": 60}}],
        seconds_per_job=1,
    )
    started = time.monotonic()
    summary = jobs.run_campaign(manifest, out)
    assert time.monotonic() - started < 10
    stored = receipt(out, "slow")
    assert stored["outcome"] == "timed_out" and stored["terminal"]
    assert stored["signal"] == signal.SIGTERM
    grandchild = int((attempt(out, "slow", 1) / "stdout").read_text())
    wait_gone(grandchild)
    assert jobs.exit_code(summary) == 1
    assert_documents(out)


def test_term_ignoring_child_is_killed(
    area: Path, synthetic: None, fast_stop: None
) -> None:
    manifest, out = campaign(
        area, [{"id": "stubborn", "request": {"action": "ignore"}}], seconds_per_job=1
    )
    jobs.run_campaign(manifest, out)
    stored = receipt(out, "stubborn")
    assert (stored["outcome"], stored["signal"]) == ("timed_out", signal.SIGKILL)
    assert (attempt(out, "stubborn", 1) / "stdout").read_text() == "ready"


def test_orphan_left_by_exited_child_is_killed(area: Path, synthetic: None) -> None:
    manifest, out = campaign(
        area, [{"id": "a", "request": {"action": "grandchild", "seconds": 0}}]
    )
    summary = jobs.run_campaign(manifest, out)
    assert summary["jobs"][0]["state"] == "succeeded"
    wait_gone(int((attempt(out, "a", 1) / "stdout").read_text()))


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_cap_keeps_prefix_and_is_terminal(
    area: Path, synthetic: None, stream: str
) -> None:
    manifest, out = campaign(
        area,
        [
            {"id": "exact", "request": {"action": "flood", "bytes": 1000}},
            {
                "id": "over",
                "request": {"action": "flood", "bytes": 5000, "stream": stream},
            },
        ],
        stdout_bytes_per_job=1000,
        stderr_bytes_per_job=1000,
        output_bytes_total=10_000,
    )
    summary = jobs.run_campaign(manifest, out)
    assert [row["state"] for row in summary["jobs"]] == ["succeeded", "output_limit"]
    exact, over = receipt(out, "exact"), receipt(out, "over")
    assert exact["stdout"]["bytes"] == 1000 and not exact["stdout"]["truncated"]
    assert over[stream]["truncated"] and over[stream]["bytes"] == 1000
    prefix = (
        b"" if stream == "stdout" else json.dumps(["-", "--format", "json"]).encode()
    )
    kept = (attempt(out, "over", 1) / stream).read_bytes()
    assert kept == prefix + b"x" * (1000 - len(prefix))
    assert_documents(out)
    assert jobs.verify_campaign(manifest, out)["status"] == "complete"


def test_campaign_deadline_then_resume_keeps_history(
    area: Path, synthetic: None, fast_stop: None
) -> None:
    marker = str(area / "marker")
    manifest, out = campaign(
        area,
        [
            {"id": "first", "request": {"action": "marker", "path": marker}},
            {"id": "second", "request": {"stdout": "done"}},
        ],
        seconds_total=3,
    )
    summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "campaign_deadline"
    assert [row["state"] for row in summary["jobs"]] == ["unfinished", "unstarted"]
    stored = receipt(out, "first")
    assert stored["outcome"] == "campaign_deadline" and not stored["terminal"]
    assert jobs.exit_code(summary) == 3
    assert jobs.verify_campaign(manifest, out)["status"] == "incomplete"
    resumed = jobs.resume_campaign(manifest, out)
    assert resumed["status"] == "complete" and resumed["attempts"] == 3
    assert receipt(out, "first", 1)["outcome"] == "campaign_deadline"
    assert receipt(out, "first", 2)["outcome"] == "succeeded"
    assert resumed["jobs"][0]["receipt"] == "jobs/first/attempt-0002/receipt.json"
    assert jobs.exit_code(resumed) == 0
    assert_documents(out)


def test_campaign_deadline_before_any_job(area: Path, synthetic: None) -> None:
    manifest, out = campaign(area, [{"id": "a"}], seconds_total=1e-9)
    summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "campaign_deadline"
    assert summary["counts"]["unstarted"] == 1 and summary["attempts"] == 0
    assert os.listdir(Path(out) / "jobs" / "a") == ["request.json"]
    assert summary["jobs"][0] == {
        "id": "a",
        "kind": "promoter",
        "state": "unstarted",
        "attempts": 0,
        "receipt": None,
        "exit_code": None,
        "stdout": None,
        "error": None,
    }


def test_output_budget_reserves_full_caps(area: Path, synthetic: None) -> None:
    manifest, out = campaign(
        area,
        [{"id": "a", "request": {"stdout": "0123456789"}}, {"id": "b"}],
        stdout_bytes_per_job=100,
        stderr_bytes_per_job=100,
        output_bytes_total=200,
    )
    summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "output_budget"
    assert [row["state"] for row in summary["jobs"]] == ["succeeded", "unstarted"]
    assert summary["output_bytes"] == 10 + receipt(out, "a")["stderr"]["bytes"]
    resumed = jobs.resume_campaign(manifest, out)
    assert resumed["stop_reason"] == "output_budget" and resumed["attempts"] == 1


def test_launch_failure_is_resumable(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a"}, {"id": "b"}])

    def unavailable(*_: object, **__: object) -> None:
        raise OSError("no interpreter")

    with monkeypatch.context() as patch:
        patch.setattr(jobs.subprocess, "Popen", unavailable)
        summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "launch_failed"
    stored = receipt(out, "a")
    assert stored["outcome"] == "launch_failed"
    assert (stored["exit_code"], stored["signal"]) == (None, None)
    assert not (attempt(out, "a", 1) / "launch.json").exists()
    assert_documents(out)
    resumed = jobs.resume_campaign(manifest, out)
    assert resumed["status"] == "complete" and resumed["attempts"] == 3


def test_capture_write_failure_stops_child(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(
        area,
        [{"id": "a", "request": {"action": "sleep", "seconds": 60, "stdout": "x"}}],
    )

    def full(self: object, chunk: bytes) -> bool:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(jobs._Capture, "accept", full)
    started = time.monotonic()
    summary = jobs.run_campaign(manifest, out)
    assert time.monotonic() - started < 10
    stored = receipt(out, "a")
    assert stored["outcome"] == "storage_error" and stored["signal"] is not None
    assert summary["stop_reason"] == "storage_error"
    wait_gone(load(attempt(out, "a", 1) / "launch.json")["pid"])


def test_fsync_failure_is_not_a_completed_receipt(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a", "request": {"stdout": "y" * 7777}}])
    real = os.fsync

    def failing(fd: int) -> None:
        if os.fstat(fd).st_size == 7777:
            raise OSError(5, "EIO")
        real(fd)

    monkeypatch.setattr(jobs.os, "fsync", failing)
    summary = jobs.run_campaign(manifest, out)
    assert receipt(out, "a")["outcome"] == "storage_error"
    assert receipt(out, "a")["exit_code"] == 0
    assert summary["jobs"][0]["state"] == "unfinished"


def test_unpublished_receipt_leaves_resumable_abandoned_attempt(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a", "request": {"stdout": "abc"}}])
    real = jobs._publish

    def failing(parent: int, name: str, data: bytes, replace: bool = False) -> None:
        if name == "receipt.json":
            raise OSError(28, "No space left on device")
        real(parent, name, data, replace)

    with monkeypatch.context() as patch:
        patch.setattr(jobs, "_publish", failing)
        summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "storage_error"
    assert summary["abandoned_attempts"] == 1
    assert summary["jobs"][0]["state"] == "unfinished"
    assert not (attempt(out, "a", 1) / "receipt.json").exists()
    checked = jobs.verify_campaign(manifest, out)
    assert checked["status"] == "incomplete" and checked["abandoned_attempts"] == 1
    assert (
        checked["output_bytes"] == 3 + (attempt(out, "a", 1) / "stderr").stat().st_size
    )
    resumed = jobs.resume_campaign(manifest, out)
    assert resumed["status"] == "complete" and resumed["attempts"] == 2
    assert (attempt(out, "a", 1) / "stdout").read_text() == "abc"
    assert resumed["abandoned_attempts"] == 1


def test_attempt_directory_failure_stops(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    real = os.mkdir

    def failing(name: str, mode: int = 0o777, *, dir_fd: int | None = None) -> None:
        if name.startswith("attempt-"):
            raise OSError(28, "No space left on device")
        real(name, mode, dir_fd=dir_fd)

    monkeypatch.setattr(jobs.os, "mkdir", failing)
    summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "storage_error"
    assert os.listdir(Path(out) / "jobs" / "a") == ["request.json"]


def test_empty_abandoned_attempt_is_counted(area: Path, synthetic: None) -> None:
    manifest, out = campaign(area, [{"id": "a"}], seconds_total=1e-9)
    jobs.run_campaign(manifest, out)
    attempt(out, "a", 1).mkdir()
    checked = jobs.verify_campaign(manifest, out)
    assert checked["jobs"][0]["state"] == "unfinished"
    assert (checked["abandoned_attempts"], checked["output_bytes"]) == (1, 0)


def test_summary_publication_failure_is_reported(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    real = jobs._publish

    def failing(parent: int, name: str, data: bytes, replace: bool = False) -> None:
        if name == "summary.json":
            raise OSError(28, "No space left on device")
        real(parent, name, data, replace)

    monkeypatch.setattr(jobs, "_publish", failing)
    summary = jobs.run_campaign(manifest, out)
    assert summary["status"] == "complete"
    assert summary["stop_reason"] == "storage_error"
    assert jobs.exit_code(summary) == 3
    assert not (Path(out) / "summary.json").exists()


def test_setup_failure_leaves_uncommitted_directory(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    real = jobs._publish

    def failing(parent: int, name: str, data: bytes, replace: bool = False) -> None:
        if name == "campaign.json":
            raise OSError(28, "No space left on device")
        real(parent, name, data, replace)

    with monkeypatch.context() as patch:
        patch.setattr(jobs, "_publish", failing)
        with pytest.raises(jobs.JobError, match="storage_error"):
            jobs.run_campaign(manifest, out)
    assert sorted(os.listdir(out)) == ["jobs", "lock", "manifest.json"]
    with pytest.raises(jobs.JobError, match="campaign_unavailable"):
        jobs.resume_campaign(manifest, out)
    with pytest.raises(jobs.JobError, match="output_exists"):
        jobs.run_campaign(manifest, out)


def test_publish_is_atomic_and_exclusive(
    area: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with jobs._directory(str(area).split("/")[1:]) as fd:
        jobs._publish(fd, "a", b"one")
        assert (area / "a").read_bytes() == b"one"
        assert (area / "a").stat().st_mode & 0o777 == 0o600
        with pytest.raises(FileExistsError):
            jobs._publish(fd, "a", b"two")
        assert (area / "a").read_bytes() == b"one"
        jobs._publish(fd, "a", b"three", replace=True)
        assert (area / "a").read_bytes() == b"three"

        def failing(_: int) -> None:
            raise OSError(5, "EIO")

        monkeypatch.setattr(jobs.os, "fsync", failing)
        with pytest.raises(OSError):
            jobs._publish(fd, "b", b"partial")
    assert os.listdir(area) == ["a"]


# Signals, exceptions, locks and orphans --------------------------------------


def test_group_signals_only_target_an_owned_unreaped_leader(
    area: Path, synthetic: None, fast_stop: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(
        area,
        [
            {"id": "group", "request": {"action": "group"}},
            {"id": "orphan", "request": {"action": "grandchild", "seconds": 0}},
            {"id": "slow", "request": {"action": "grandchild", "seconds": 60}},
        ],
        seconds_per_job=1,
    )
    real, signalled = jobs._signal_group, []

    def checked(pgid: int, number: int) -> None:
        os.kill(pgid, 0)  # The anchor leader still exists: alive or unreaped.
        signalled.append((pgid, number))
        real(pgid, number)

    monkeypatch.setattr(jobs, "_signal_group", checked)
    summary = jobs.run_campaign(manifest, out)
    assert [row["state"] for row in summary["jobs"]] == [
        "succeeded",
        "succeeded",
        "timed_out",
    ]
    launches = {
        job: load(attempt(out, job, 1) / "launch.json")
        for job in ("group", "orphan", "slow")
    }
    group = int((attempt(out, "group", 1) / "stdout").read_text())
    assert group == launches["group"]["pgid"] != launches["group"]["pid"]
    assert {pgid for pgid, _ in signalled} == {
        launch["pgid"] for launch in launches.values()
    }
    slow = [number for pgid, number in signalled if pgid == launches["slow"]["pgid"]]
    assert slow[0] == signal.SIGTERM and slow[-1] == signal.SIGKILL
    for launch in launches.values():
        for pid in (launch["pgid"], launch["pid"]):
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)
    for job in ("orphan", "slow"):
        wait_gone(int((attempt(out, job, 1) / "stdout").read_text()))


def test_calculator_launch_failure_releases_anchor(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    real, anchors = jobs.subprocess.Popen, []

    def calculator_fails(*args: object, **kwargs: object) -> object:
        if kwargs["process_group"] != 0:
            raise OSError("calculator unavailable")
        anchors.append(real(*args, **kwargs))  # type: ignore[call-overload]
        return anchors[-1]

    monkeypatch.setattr(jobs.subprocess, "Popen", calculator_fails)
    summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "launch_failed"
    assert receipt(out, "a")["outcome"] == "launch_failed"
    assert len(anchors) == 1 and anchors[0].returncode == -signal.SIGKILL
    with pytest.raises(ProcessLookupError):
        os.killpg(anchors[0].pid, 0)


def test_attempts_are_bounded_per_job(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "MAX_ATTEMPTS", 2)
    marker = str(area / "marker")
    manifest, out = campaign(
        area,
        [
            {"id": "stuck", "request": {"action": "sleep", "seconds": 60}},
            {"id": "later", "request": {"action": "marker", "path": marker}},
        ],
        seconds_per_job=30,
        seconds_total=1,
    )
    for _ in range(2):
        summary = (
            jobs.resume_campaign(manifest, out)
            if Path(out).exists()
            else jobs.run_campaign(manifest, out)
        )
        assert summary["stop_reason"] == "campaign_deadline"
    assert summary["jobs"][0]["state"] == "attempts_exhausted"
    summary = jobs.resume_campaign(manifest, out)
    assert [row["state"] for row in summary["jobs"]] == [
        "attempts_exhausted",
        "unfinished",
    ]
    assert summary["stop_reason"] == "campaign_deadline"
    assert not attempt(out, "stuck", 3).exists()
    summary = jobs.resume_campaign(manifest, out)
    assert [row["state"] for row in summary["jobs"]] == [
        "attempts_exhausted",
        "succeeded",
    ]
    assert summary["stop_reason"] == "attempt_limit"
    assert summary["status"] == "incomplete" and jobs.exit_code(summary) == 3
    assert summary["counts"]["attempts_exhausted"] == 1
    schema("summary").validate(summary)
    checked = jobs.verify_campaign(manifest, out)
    assert checked["jobs"][0]["state"] == "attempts_exhausted"
    assert checked["stop_reason"] is None and jobs.exit_code(checked) == 3


def test_signal_stops_running_job_and_restores_handlers(
    area: Path, synthetic: None, fast_stop: None
) -> None:
    before = signal.getsignal(signal.SIGTERM)
    manifest, out = campaign(
        area, [{"id": "a", "request": {"action": "parent"}}, {"id": "b"}]
    )
    started = time.monotonic()
    summary = jobs.run_campaign(manifest, out)
    assert time.monotonic() - started < 10
    assert summary["stop_reason"] == "signal"
    assert receipt(out, "a")["outcome"] == "interrupted"
    assert [row["state"] for row in summary["jobs"]] == ["unfinished", "unstarted"]
    assert signal.getsignal(signal.SIGTERM) is before
    wait_gone(load(attempt(out, "a", 1) / "launch.json")["pid"])
    assert jobs.exit_code(summary) == 3


def test_signal_between_jobs_prevents_next_start(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, out = campaign(area, [{"id": "a"}, {"id": "b"}])
    real = jobs._run_attempt

    def then_signal(*args: object) -> tuple:
        result = real(*args)  # type: ignore[arg-type]
        os.kill(os.getpid(), signal.SIGINT)
        return result

    monkeypatch.setattr(jobs, "_run_attempt", then_signal)
    summary = jobs.run_campaign(manifest, out)
    assert summary["stop_reason"] == "signal"
    assert [row["state"] for row in summary["jobs"]] == ["succeeded", "unstarted"]


def test_library_requires_main_thread(area: Path, synthetic: None) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    errors: list = []

    def target() -> None:
        try:
            jobs.run_campaign(manifest, out)
        except jobs.JobError as error:
            errors.append(error.code)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    assert errors == ["main_thread_required"] and not Path(out).exists()


def test_unexpected_exception_cleans_up(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch, fast_stop: None
) -> None:
    marker = str(area / "marker")
    manifest, out = campaign(
        area, [{"id": "a", "request": {"action": "marker", "path": marker}}]
    )
    before = signal.getsignal(signal.SIGINT)

    def broken(*_: object) -> None:
        while not os.path.exists(marker):
            time.sleep(0.01)
        raise RuntimeError("bug")

    with monkeypatch.context() as patch:
        patch.setattr(jobs, "_pump", broken)
        with pytest.raises(RuntimeError):
            jobs.run_campaign(manifest, out)
    launch = load(attempt(out, "a", 1) / "launch.json")
    for pid in (launch["pgid"], launch["pid"]):
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    with pytest.raises(ProcessLookupError):
        os.killpg(launch["pgid"], 0)
    assert signal.getsignal(signal.SIGINT) is before
    resumed = jobs.resume_campaign(manifest, out)
    assert resumed["status"] == "complete" and resumed["abandoned_attempts"] == 1


def test_resume_refuses_live_orphan_group(
    area: Path, synthetic: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = str(area / "marker")
    manifest, out = campaign(
        area, [{"id": "a", "request": {"action": "marker", "path": marker}}]
    )

    def crash(*_: object) -> None:
        while not os.path.exists(marker):
            time.sleep(0.01)
        raise RuntimeError("runner died")

    with monkeypatch.context() as patch:
        patch.setattr(jobs, "_pump", crash)
        patch.setattr(jobs, "_stop", lambda process, pgid: None)
        patch.setattr(jobs, "_release", lambda anchor: None)
        with pytest.raises(RuntimeError):
            jobs.run_campaign(manifest, out)
    launch = load(attempt(out, "a", 1) / "launch.json")
    try:
        with pytest.raises(jobs.JobError, match="orphan_process"):
            jobs.resume_campaign(manifest, out)
    finally:
        os.killpg(launch["pgid"], signal.SIGKILL)
        for pid in (launch["pid"], launch["pgid"]):
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
    resumed = jobs.resume_campaign(manifest, out)
    assert resumed["status"] == "complete" and resumed["attempts"] == 2


def test_group_probe_treats_foreign_or_missing_groups_as_absent() -> None:
    assert jobs._group_alive(1) is False
    process = subprocess.Popen(["true"], start_new_session=True)
    process.wait()
    assert jobs._group_alive(process.pid) is False


def test_lock_refuses_concurrent_use(area: Path, synthetic: None) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    jobs.run_campaign(manifest, out)
    holder = os.open(Path(out) / "lock", os.O_RDWR)
    try:
        fcntl.flock(holder, fcntl.LOCK_EX)
        with pytest.raises(jobs.JobError, match="locked"):
            jobs.resume_campaign(manifest, out)
        with pytest.raises(jobs.JobError, match="locked"):
            jobs.verify_campaign(manifest, out)
    finally:
        os.close(holder)
    assert jobs.verify_campaign(manifest, out)["status"] == "complete"
    (Path(out) / "lock").unlink()
    with pytest.raises(jobs.JobError, match="layout_invalid"):
        jobs.verify_campaign(manifest, out)


# Tampering and corruption ----------------------------------------------------


@pytest.fixture
def finished(area: Path, synthetic: None) -> tuple[str, str]:
    manifest, out = campaign(
        area,
        [
            {"id": "a", "request": {"stdout": "result", "exit": 1}},
            {"id": "b", "request": {"stdout": "other"}},
        ],
    )
    jobs.run_campaign(manifest, out)
    return manifest, out


def corrupted(manifest: str, out: str) -> str:
    """Verify reports the damaged job only; resume refuses."""
    summary = jobs.verify_campaign(manifest, out)
    assert summary["status"] == "corrupted" and jobs.exit_code(summary) == 2
    assert summary["jobs"][1]["state"] == "succeeded"
    assert summary["counts"]["corrupted"] == 1
    schema("summary").validate(summary)
    with pytest.raises(jobs.JobError, match="corrupted"):
        jobs.resume_campaign(manifest, out)
    return summary["jobs"][0]["error"]


def edit_receipt(out: str, change: dict, job: str = "a", number: int = 1) -> None:
    path = attempt(out, job, number) / "receipt.json"
    value = load(path)
    for key, item in change.items():
        if isinstance(item, dict) and isinstance(value[key], dict):
            value[key] = {**value[key], **item}
        else:
            value[key] = item
    dump(path, value)


@pytest.mark.parametrize(
    "change",
    [
        {"outcome": "succeeded"},
        {"outcome": "succeeded", "exit_code": 0, "terminal": False},
        {"exit_code": -1},
        {"exit_code": 1, "signal": 9},
        {"signal": 0},
        {"outcome": "abnormal_exit"},
        {"outcome": "launch_failed", "terminal": False},
        {"outcome": "output_limit"},
        {"stdout": {"truncated": True}},
        {"attempt": True},
        {"attempt": 2},
        {"job_id": "b"},
        {"kind": "rbs"},
        {"campaign_sha256": "0" * 64},
        {"schema_version": "calculator-job-receipt-2"},
        {"argv": ["{python}"]},
        {"request": {"bytes": 1}},
        {"elapsed_seconds": -1},
        {"elapsed_seconds": "1"},
        {"stdout": {"path": "jobs/b/attempt-0001/stdout"}},
        {"stdout": {"bytes": LIMITS["stdout_bytes_per_job"] + 1}},
        {"stderr": {"sha256": "x"}},
        {"stderr": []},
        {"extra": 1},
    ],
)
def test_receipt_tampering_is_detected(finished: tuple[str, str], change: dict) -> None:
    edit_receipt(finished[1], change)
    assert corrupted(*finished) == "receipt_invalid"


@pytest.mark.parametrize(
    ("damage", "code"),
    [
        ("stdout_bytes", "artifact_changed"),
        ("stdout_link", "artifact_unavailable"),
        ("stdout_large", "artifact_too_large"),
        ("request_copy", "request_copy"),
        ("request_copy_missing", "request_copy_unavailable"),
        ("receipt_json", "malformed_json"),
        ("receipt_large", "record_too_large"),
        ("gap", "attempt_sequence"),
        ("too_many", "attempt_count"),
        ("extra_attempt_file", "attempt_layout"),
        ("launch", "launch_invalid"),
        ("launch_pid", "launch_invalid"),
        ("job_link", "job_unavailable"),
        ("terminal_not_last", "terminal_not_last"),
    ],
)
def test_artifact_corruption_is_detected(
    finished: tuple[str, str], damage: str, code: str
) -> None:
    manifest, out = finished
    first = attempt(out, "a", 1)
    job = Path(out) / "jobs" / "a"
    if damage == "stdout_bytes":
        (first / "stdout").write_text("resulT")
    elif damage == "stdout_link":
        (first / "stdout").unlink()
        (first / "stdout").symlink_to(attempt(out, "b", 1) / "stdout")
    elif damage == "stdout_large":
        (first / "stdout").write_bytes(b"x" * (LIMITS["stdout_bytes_per_job"] + 1))
    elif damage == "request_copy":
        (job / "request.json").write_text("{}")
    elif damage == "request_copy_missing":
        (job / "request.json").unlink()
    elif damage == "receipt_json":
        (first / "receipt.json").write_text("{")
    elif damage == "receipt_large":
        (first / "receipt.json").write_bytes(b" " * (jobs.MAX_RECORD_BYTES + 1))
    elif damage == "gap":
        first.rename(job / "attempt-0002")
    elif damage == "too_many":
        for number in range(2, jobs.MAX_ATTEMPTS + 2):
            (job / f"attempt-{number:04d}").mkdir()
    elif damage == "extra_attempt_file":
        (first / "notes.txt").write_text("x")
    elif damage == "launch":
        (first / "launch.json").write_text('{"pid": 5}')
    elif damage == "launch_pid":
        dump(
            first / "launch.json",
            {"schema_version": jobs.LAUNCH_VERSION, "pgid": 5, "pid": 1},
        )
    elif damage == "job_link":
        job.rename(Path(out).parent / "moved")
        job.symlink_to(Path(out).parent / "moved")
    else:
        second = job / "attempt-0002"
        second.mkdir()
        for name in ("stdout", "stderr"):
            (second / name).write_bytes((first / name).read_bytes())
        value = load(first / "receipt.json")
        value["attempt"] = 2
        for name in ("stdout", "stderr"):
            value[name]["path"] = f"jobs/a/attempt-0002/{name}"
        dump(second / "receipt.json", value)
    assert corrupted(manifest, out) == code


def test_layout_and_campaign_tampering(finished: tuple[str, str]) -> None:
    manifest, out = finished
    root = Path(out)
    (root / ".tmp-leftover").write_text("x")
    (attempt(out, "a", 1) / ".tmp-leftover").write_text("x")
    assert jobs.verify_campaign(manifest, out)["status"] == "complete"
    original = (root / "campaign.json").read_bytes()

    def refused(code: str) -> None:
        for action in (jobs.verify_campaign, jobs.resume_campaign):
            with pytest.raises(jobs.JobError, match=code):
                action(manifest, out)

    (root / "campaign.json").write_text("{")
    refused("malformed_json")
    change: dict
    for change in (
        {"extra": 1},
        {"schema_version": "x"},
        {"runtime": []},
        {"backend": {"rnastructure": None}},
        {"backend": {"rnastructure": 1, "conditional_original": None}},
        {"manifest": {"path": "manifest.json", "sha256": "0" * 64, "bytes": 1}},
    ):
        value = json.loads(original)
        value.update(change)
        dump(root / "campaign.json", value)
        refused("manifest_mismatch" if "manifest" in change else "campaign_invalid")
    (root / "campaign.json").write_bytes(original)
    (root / "manifest.json").write_text("{}")
    refused("manifest_mismatch")
    (root / "manifest.json").write_bytes(Path(manifest).read_bytes())
    (root / "unrelated").write_text("x")
    refused("layout_invalid")
    (root / "unrelated").unlink()
    (root / "jobs" / "c").mkdir()
    refused("layout_invalid")
    (root / "jobs" / "c").rmdir()
    (root / "jobs").rename(root.parent / "elsewhere")
    (root / "jobs").write_text("x")
    refused("layout_invalid")


def test_resume_refuses_changed_manifest_or_inputs(finished: tuple[str, str]) -> None:
    manifest, out = finished
    original = Path(manifest).read_bytes()
    value = json.loads(original)
    value["limits"]["seconds_per_job"] = 31
    dump(Path(manifest), value)
    with pytest.raises(jobs.JobError, match="manifest_mismatch"):
        jobs.resume_campaign(manifest, out)
    Path(manifest).write_bytes(original)
    (Path(manifest).parent / "a.json").write_text('{"exit": 0}')
    with pytest.raises(jobs.JobError, match="request_mismatch"):
        jobs.resume_campaign(manifest, out)


# CLI -------------------------------------------------------------------------


def run_main(capfd: pytest.CaptureFixture, *argv: str) -> tuple[int, dict]:
    code = jobs.main(list(argv))
    return code, json.loads(capfd.readouterr().out)


def test_cli_exit_codes(
    area: Path, synthetic: None, capfd: pytest.CaptureFixture
) -> None:
    manifest, out = campaign(area, [{"id": "a"}])
    code, document = run_main(capfd, "run", "--manifest", manifest, "--output-dir", out)
    assert code == 0 and document == load(Path(out) / "summary.json")
    code, document = run_main(
        capfd, "verify", "--manifest", manifest, "--output-dir", out
    )
    assert (code, document["command"]) == (0, "verify")
    code, document = run_main(
        capfd, "resume", "--manifest", manifest, "--output-dir", out
    )
    assert (code, document["command"]) == (0, "resume")
    code, document = run_main(capfd, "run", "--manifest", manifest, "--output-dir", out)
    assert (code, document) == (
        2,
        {
            "schema_version": jobs.SUMMARY_VERSION,
            "status": "invalid",
            "error": "output_exists",
        },
    )
    schema("summary").validate(document)
    second, third = str(area / "o2"), str(area / "o3")
    (area / "x").mkdir()
    manifest2, _ = campaign(area / "x", [{"id": "p", "request": {"exit": 1}}])
    code, _ = run_main(capfd, "run", "--manifest", manifest2, "--output-dir", second)
    assert code == 1
    value = load(Path(manifest2))
    value["limits"]["seconds_total"] = 1e-9
    dump(Path(manifest2), value)
    code, document = run_main(
        capfd,
        "run",
        "--manifest",
        manifest2,
        "--output-dir",
        third,
        "--allow-repository-output",
    )
    assert (code, document["stop_reason"]) == (3, "campaign_deadline")
    code, document = run_main(
        capfd,
        "resume",
        "--manifest",
        manifest2,
        "--output-dir",
        third,
        "--backend-root",
        str(area),
    )
    assert (code, document["error"]) == (2, "backend_root_unused")
    with pytest.raises(SystemExit) as usage:
        jobs.main(["run", "--manifest", manifest])
    assert usage.value.code == 2


def test_cli_reports_unwritable_stdout(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture
) -> None:
    read, write = os.pipe()
    os.close(read)
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(fileno=lambda: write))
    try:
        code = jobs.main(["verify", "--manifest", "rel", "--output-dir", "/x"])
    finally:
        os.close(write)
    assert code == 2
    assert capfd.readouterr().err == "regsite-jobs: stdout unavailable\n"


def test_exit_code_mapping() -> None:
    base: dict = {"status": "complete", "stop_reason": None, "jobs": [{}, {}]}
    assert jobs.exit_code({**base, "counts": {"succeeded": 2}}) == 0
    assert jobs.exit_code({**base, "counts": {"succeeded": 1}}) == 1
    assert jobs.exit_code({**base, "stop_reason": "storage_error"}) == 3
    assert jobs.exit_code({**base, "status": "incomplete"}) == 3
    assert jobs.exit_code({**base, "status": "corrupted"}) == 2


# Real installed calculators ---------------------------------------------------


def test_real_promoter_and_conditional_jobs(area: Path) -> None:
    example = ROOT / "examples" / "jobs-synthetic" / "manifest.json"
    out = str(area / "out")
    summary = jobs.run_campaign(str(example), out)
    assert summary["status"] == "complete" and jobs.exit_code(summary) == 0
    assert_documents(out)
    for row in load(example)["jobs"]:
        stored = receipt(out, row["id"])
        request = str(example.parent / row["request"]["path"])
        argv = [sys.executable, *stored["argv"][1:5], request, *stored["argv"][6:]]
        direct = subprocess.run(argv, capture_output=True, check=False)
        assert direct.returncode == stored["exit_code"] == 0
        assert (attempt(out, row["id"], 1) / "stdout").read_bytes() == direct.stdout
    promoter = load(attempt(out, "promoter-single", 1) / "stdout")
    conditional = load(attempt(out, "conditional-half-occupancy", 1) / "stdout")
    assert promoter["results"][0]["status"] == "ok"
    assert conditional["schema_version"] == "conditional-aptamer-result-1"
    assert conditional["status"] == "ok"
    assert jobs.verify_campaign(str(example), out)["status"] == "complete"


def test_real_native_refusal_is_preserved(area: Path) -> None:
    manifest, out = campaign(
        area, [{"id": "bad", "kind": "conditional", "raw": b'{"schema_version": 1}'}]
    )
    summary = jobs.run_campaign(manifest, out)
    assert summary["jobs"][0]["state"] == "refused"
    result = load(attempt(out, "bad", 1) / "stdout")
    assert result["status"] == "invalid_input" and result["complete"] is False


def test_examples_are_valid_and_bound(area: Path) -> None:
    for name in ("jobs-synthetic", "jobs-backend"):
        path = ROOT / "examples" / name / "manifest.json"
        value, _ = jobs.load_manifest(str(path))
        schema("manifest").validate(value)
        requests = jobs._load_requests(str(path), value)
        assert set(requests) == {row["id"] for row in value["jobs"]}
