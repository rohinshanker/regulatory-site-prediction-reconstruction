"""Receipt validation and tiny Python process doubles for process controls."""

import hashlib
import json
import os
import resource
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from regsite import termination_backend as backend
from regsite.termination_backend import TerminationBackendError

SEQUENCE = "AC" + "ACGT" * 25 + "AC"


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def installation(tmp_path, monkeypatch):
    table = b"x" * 45788
    monkeypatch.setattr(backend, "TABLE_SHA256", digest(table))
    binary = f"#!{sys.executable}\nprint('complete')\n".encode()
    identity = {
        "schema_version": "termination-backend-1",
        "profile": backend.PROFILE,
        "source": dict(backend.SOURCE),
        "build": {
            "compiler": "fake-compiler",
            "compiler_sha256": "0" * 64,
            "compiler_version": "fixture 1",
            "platform": "test",
            "machine": "test",
            "standard_library": "test",
            "flags": list(backend.BUILD_FLAGS),
            "extra_flags_sha256": "0" * 64,
        },
        "binary": {"bytes": len(binary), "sha256": digest(binary)},
        "table": {"bytes": len(table), "sha256": digest(table)},
    }
    (tmp_path / "expterm.dat").write_bytes(table)
    (tmp_path / "transterm").write_bytes(binary)
    (tmp_path / "transterm").chmod(0o755)
    manifest = tmp_path / "backend.json"
    manifest.write_text(json.dumps(identity))
    return manifest, identity


def script(installation, body):
    path, identity = installation
    raw = f"#!{sys.executable}\n{body}\n".encode()
    (path.parent / "transterm").write_bytes(raw)
    identity["binary"] = {"bytes": len(raw), "sha256": digest(raw)}
    path.write_text(json.dumps(identity))
    return backend.load_backend(path)


def test_load_identity_and_success(installation):
    path, identity = installation
    model = backend.load_backend(path)
    assert model.identity == identity
    model.identity["source"].clear()
    assert model.identity == identity
    old_limits = resource.getrlimit(resource.RLIMIT_STACK)
    result = model.run(SEQUENCE, timeout_seconds=2)
    assert result.stdout == b"complete\n" and result.stderr == b""
    assert result.diagnostics == {
        "returncode": 0,
        "stdout_sha256": digest(b"complete\n"),
        "stdout_bytes": 9,
        "stdout_complete": True,
        "stderr_sha256": digest(b""),
        "stderr_bytes": 0,
        "stderr_complete": True,
    }
    assert resource.getrlimit(resource.RLIMIT_STACK) == old_limits


def test_fixed_command_inputs_and_stack(installation, tmp_path):
    marker = tmp_path / "cwd.txt"
    model = script(
        installation,
        f"""
import pathlib, resource, sys
p = pathlib.Path.cwd()
assert sys.argv[1:] == ['-p','expterm.dat','--all-context','-c','0','-S',
                       'input.fasta','input.coords']
assert p.joinpath('input.fasta').read_text() == '>fragment\\n{SEQUENCE}\\n'
assert p.joinpath('input.coords').read_text() == (
    'boundary_left 1 2 fragment\\n'
    'boundary_right {len(SEQUENCE) - 1} {len(SEQUENCE)} fragment\\n')
assert p.joinpath('expterm.dat').read_bytes() == b'x' * 45788
assert resource.getrlimit(resource.RLIMIT_STACK)[0] >= 8388608
pathlib.Path({str(marker)!r}).write_text(str(p))
print('ok')
""",
    )
    assert model.run(SEQUENCE, timeout_seconds=2).stdout == b"ok\n"
    assert not Path(marker.read_text()).exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x.update(extra=1),
        lambda x: x.update(profile="wrong"),
        lambda x: x.update(schema_version="wrong"),
        lambda x: x.update(source={}),
        lambda x: x.update(build=[]),
        lambda x: x["build"].update(flags=["-ffast-math"]),
        lambda x: x["build"].update(compiler="/tmp/cc"),
        lambda x: x["build"].update(compiler=""),
        lambda x: x["build"].update(compiler_version="x\ny"),
        lambda x: x["build"].update(compiler_sha256="z" * 64),
        lambda x: x["build"].update(extra_flags_sha256=2),
        lambda x: x.update(binary={}),
        lambda x: x["binary"].update(bytes=True),
        lambda x: x["binary"].update(bytes=0),
        lambda x: x["binary"].update(bytes=2**30),
        lambda x: x["binary"].update(sha256="00"),
        lambda x: x["table"].update(bytes=1),
        lambda x: x["table"].update(bytes=45788.0),
    ],
)
def test_manifest_rejects_contract_changes(installation, mutate):
    path, identity = installation
    mutate(identity)
    path.write_text(json.dumps(identity))
    with pytest.raises(TerminationBackendError, match="backend_manifest"):
        backend.load_backend(path)


@pytest.mark.parametrize(
    "raw",
    [b'{"x":1,"x":2}', b'{"x":NaN}', b"\xff", b"[]", b"{", b"[" * 2000 + b"]" * 2000],
)
def test_malformed_manifest(installation, raw):
    path, _ = installation
    path.write_bytes(raw)
    with pytest.raises(TerminationBackendError, match="backend_manifest"):
        backend.load_backend(path)


@pytest.mark.parametrize("name", ["backend.json", "transterm", "expterm.dat"])
def test_no_symlinks(installation, name):
    path, _ = installation
    target = path.parent / name
    renamed = target.with_suffix(".original")
    target.rename(renamed)
    target.symlink_to(renamed)
    with pytest.raises(TerminationBackendError, match="backend_unavailable"):
        backend.load_backend(path)


@pytest.mark.parametrize(
    "change", ["bytes", "sha", "executable", "empty", "directory", "large"]
)
def test_artifact_identity(installation, change):
    path, identity = installation
    binary = path.parent / "transterm"
    if change == "bytes":
        binary.write_bytes(b"changed")
    elif change == "sha":
        identity["binary"]["sha256"] = "0" * 64
        path.write_text(json.dumps(identity))
    elif change == "executable":
        binary.chmod(0o644)
    elif change == "empty":
        binary.write_bytes(b"")
    elif change == "directory":
        binary.unlink()
        binary.mkdir()
    else:
        path.write_bytes(b" " * 32769)
    with pytest.raises(TerminationBackendError):
        backend.load_backend(path)


def test_reverify_before_run(installation):
    path, _ = installation
    model = backend.load_backend(path)
    (path.parent / "expterm.dat").write_bytes(b"wrong")
    with pytest.raises(TerminationBackendError, match="backend_identity"):
        model.run(SEQUENCE, timeout_seconds=1)


@pytest.mark.parametrize(
    "sequence",
    [
        None,
        "ACGT",
        "AC" * 50001,
        "ac" * 50,
        "N" * 100,
        "AC" + "C" * 100 + "AC",
        "AA" + "AC" * 50 + "TT",
    ],
)
def test_input_preconditions(installation, sequence):
    model = backend.load_backend(installation[0])
    with pytest.raises(TerminationBackendError, match="native_input"):
        model.run(sequence, timeout_seconds=1)


@pytest.mark.parametrize(
    "timeout", [True, None, "1", 0, -1, 61, float("nan"), float("inf")]
)
def test_timeout_preconditions(installation, timeout):
    with pytest.raises(TerminationBackendError, match="native_input"):
        backend.load_backend(installation[0]).run(SEQUENCE, timeout_seconds=timeout)


@pytest.mark.parametrize(
    "body,code",
    [
        ("import time; time.sleep(5)", "native_timeout"),
        ("import sys; print('failed'); sys.exit(3)", "native_exit"),
        ("import os; os.write(1, b'x'*262145)", "native_output_limit"),
        ("import os; os.write(2, b'x'*65537)", "native_output_limit"),
        ("import os,time; os.close(1); os.close(2); time.sleep(5)", "native_timeout"),
    ],
)
def test_process_failures(installation, body, code):
    model = script(installation, body)
    with pytest.raises(TerminationBackendError) as error:
        model.run(SEQUENCE, timeout_seconds=0.6 if code == "native_timeout" else 2)
    assert error.value.code == code
    d = error.value.diagnostics
    assert d is not None and d["returncode"] is not None
    assert d["stdout_bytes"] <= backend.STDOUT_LIMIT
    assert d["stderr_bytes"] <= backend.STDERR_LIMIT
    if code == "native_exit":
        assert d["stdout_complete"] and d["stderr_complete"]
        assert d["returncode"] == 3
    if code == "native_output_limit":
        assert not (d["stdout_complete"] and d["stderr_complete"])
    assert "/" not in str(error.value)


def test_dual_stream_complete_at_limits(installation):
    model = script(
        installation, "import os; os.write(1,b'x'*262144); os.write(2,b'y'*65536)"
    )
    result = model.run(SEQUENCE, timeout_seconds=2)
    assert result.stdout == b"x" * 262144 and result.stderr == b"y" * 65536
    assert (
        result.diagnostics["stdout_complete"] and result.diagnostics["stderr_complete"]
    )


def test_unsupported_platform(installation, monkeypatch):
    model = backend.load_backend(installation[0])
    # Patch a module-local os proxy so pathlib/pytest still see the real OS.
    proxy = Mock(wraps=os)
    proxy.name = "nt"
    monkeypatch.setattr(backend, "os", proxy)
    for action in (
        lambda: backend.load_backend(installation[0]),
        lambda: model.run(SEQUENCE, timeout_seconds=1),
    ):
        with pytest.raises(TerminationBackendError, match="unsupported_platform"):
            action()


def test_low_stack_and_setup_errors(installation, monkeypatch):
    model = backend.load_backend(installation[0])
    monkeypatch.setattr(resource, "getrlimit", lambda _: (10, 100))
    with pytest.raises(TerminationBackendError, match="insufficient_stack"):
        model.run(SEQUENCE, timeout_seconds=1)
    monkeypatch.setattr(resource, "getrlimit", lambda _: (10, resource.RLIM_INFINITY))
    monkeypatch.setattr(
        backend.subprocess, "Popen", Mock(side_effect=subprocess.SubprocessError())
    )
    with pytest.raises(TerminationBackendError, match="insufficient_stack") as error:
        model.run(SEQUENCE, timeout_seconds=1)
    assert error.value.diagnostics is not None
    assert error.value.diagnostics["returncode"] is None


def test_spawn_io_failure(installation, monkeypatch):
    model = backend.load_backend(installation[0])
    monkeypatch.setattr(
        backend.subprocess, "Popen", Mock(side_effect=OSError("private/path"))
    )
    with pytest.raises(TerminationBackendError, match="native_io") as error:
        model.run(SEQUENCE, timeout_seconds=1)
    assert error.value.diagnostics is not None
    assert error.value.diagnostics["stdout_complete"] is False


def test_capture_read_failure(installation, monkeypatch):
    model = backend.load_backend(installation[0])
    real_read = os.read

    def failed_read(fd, size):
        # Popen itself reads its exec-error pipe before returning.
        if size == 50000:
            return real_read(fd, size)
        raise OSError("read fixture")

    monkeypatch.setattr(backend.os, "read", failed_read)
    with pytest.raises(TerminationBackendError, match="native_io") as error:
        model.run(SEQUENCE, timeout_seconds=1)
    assert error.value.diagnostics is not None


def test_private_input_write_failure(installation, monkeypatch):
    model = backend.load_backend(installation[0])
    monkeypatch.setattr(Path, "write_text", Mock(side_effect=OSError()))
    with pytest.raises(TerminationBackendError, match="native_io") as error:
        model.run(SEQUENCE, timeout_seconds=1)
    assert error.value.diagnostics is None


def test_busy_runner_timeout(installation, monkeypatch):
    lock = Mock()
    lock.acquire.return_value = False
    monkeypatch.setattr(backend, "_PROCESS_LOCK", lock)
    with pytest.raises(TerminationBackendError, match="native_timeout"):
        backend.load_backend(installation[0]).run(SEQUENCE, timeout_seconds=0.001)
    lock.release.assert_not_called()


def test_changing_file_rejected(tmp_path, monkeypatch):
    path = tmp_path / "file"
    path.write_bytes(b"test")
    actual = os.fstat
    calls = 0

    def changed(fd):
        nonlocal calls
        calls += 1
        result = actual(fd)
        if calls == 2:
            values = list(result)
            values[6] += 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(backend.os, "fstat", changed)
    with pytest.raises(TerminationBackendError, match="backend_identity"):
        backend._read_regular(path, 10)


def test_error_message_bounded():
    error = TerminationBackendError("x" * 1000, code="test")
    assert len(str(error)) == 240
    assert error.diagnostics is None


def test_stack_read_failure(installation, monkeypatch):
    model = backend.load_backend(installation[0])
    monkeypatch.setattr(resource, "getrlimit", Mock(side_effect=ValueError()))
    with pytest.raises(TerminationBackendError, match="insufficient_stack"):
        model.run(SEQUENCE, timeout_seconds=1)


@pytest.mark.parametrize(
    "soft,hard",
    [
        (1000, backend.STACK_BYTES * 2),
        (backend.STACK_BYTES * 2, backend.STACK_BYTES * 3),
        (resource.RLIM_INFINITY, resource.RLIM_INFINITY),
    ],
)
def test_child_stack_policy_without_changing_parent(
    installation, monkeypatch, soft, hard
):
    model = backend.load_backend(installation[0])
    monkeypatch.setattr(resource, "getrlimit", lambda _: (soft, hard))
    set_limit = Mock()
    monkeypatch.setattr(resource, "setrlimit", set_limit)
    original = backend._execute

    def execute(path, directory, deadline, setup):
        # Exercise the closure synchronously with setrlimit mocked. Never change
        # the running parent's actual limits; process tests check the real child.
        setup()
        return original(path, directory, deadline, None)

    monkeypatch.setattr(backend, "_execute", execute)
    assert model.run(SEQUENCE, timeout_seconds=2).diagnostics["returncode"] == 0
    target = soft if soft == resource.RLIM_INFINITY else max(soft, backend.STACK_BYTES)
    set_limit.assert_called_once_with(resource.RLIMIT_STACK, (target, hard))


@pytest.mark.parametrize("fails", [False, True])
def test_temporary_cleanup_failure_keeps_attempt_diagnostics(
    installation, monkeypatch, fails
):
    model = script(installation, "import sys; sys.exit(3)" if fails else "print('ok')")
    original = backend.tempfile.TemporaryDirectory

    class CleanupFailure:
        def __init__(self, **kwargs):
            self.context = original(**kwargs)

        def __enter__(self):
            return self.context.__enter__()

        def __exit__(self, *args):
            self.context.__exit__(*args)
            raise OSError("cleanup fixture")

    monkeypatch.setattr(backend.tempfile, "TemporaryDirectory", CleanupFailure)
    with pytest.raises(TerminationBackendError, match="native_io") as error:
        model.run(SEQUENCE, timeout_seconds=2)
    assert error.value.diagnostics is not None
    assert error.value.diagnostics["returncode"] == (3 if fails else 0)


def test_pipe_close_failure_is_typed_and_reaped(installation, monkeypatch):
    model = backend.load_backend(installation[0])
    original = subprocess.Popen
    processes = []

    def spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        processes.append(child)
        stream = child.stdout

        def failed_close():
            assert stream is not None
            stream.close()
            raise OSError("close fixture")

        child.stdout = Mock(wraps=stream)
        child.stdout.close.side_effect = failed_close
        return child

    monkeypatch.setattr(backend.subprocess, "Popen", spawn)
    with pytest.raises(TerminationBackendError, match="native_io") as error:
        model.run(SEQUENCE, timeout_seconds=2)
    assert error.value.diagnostics is not None
    assert error.value.diagnostics["returncode"] == 0
    assert processes[0].poll() == 0


@pytest.mark.parametrize("signal_failure", [None, ProcessLookupError, PermissionError])
def test_build_group_cleanup_before_leader_reap(tmp_path, monkeypatch, signal_failure):
    import time

    processes = []
    original_spawn = subprocess.Popen
    original_signal = os.killpg
    signals = []

    def spawn(*args, **kwargs):
        child = original_spawn(*args, **kwargs)
        processes.append(child)
        assert kwargs["start_new_session"] is True
        return child

    def signal_group(pid, sig):
        assert pid == processes[0].pid
        assert processes[0].returncode is None
        signals.append(pid)
        if signal_failure is not None:
            raise signal_failure()
        original_signal(pid, sig)

    monkeypatch.setattr(backend.subprocess, "Popen", spawn)
    monkeypatch.setattr(backend.os, "killpg", signal_group)
    with pytest.raises(TerminationBackendError) as error:
        backend._execute(
            Path(sys.executable),
            tmp_path,
            time.monotonic() + 0.6,
            None,
            arguments=["-c", "import time; time.sleep(5)"],
            own_process_group=True,
        )
    assert error.value.code == (
        "native_io" if signal_failure is PermissionError else "native_timeout"
    )
    assert len(signals) == 1
    assert processes[0].returncode is not None


def test_exec_uses_verified_bytes_after_installation_replacement(
    installation, monkeypatch
):
    path, identity = installation
    model = backend.load_backend(path)
    original = backend._execute
    captured = []

    def execute(executable, directory, *args, **kwargs):
        replacement = f"#!{sys.executable}\nprint('replacement')\n".encode()
        (path.parent / "transterm").write_bytes(replacement)
        assert executable == directory / "transterm"
        assert executable.stat().st_mode & 0o777 == 0o700
        assert digest(executable.read_bytes()) == identity["binary"]["sha256"]
        captured.append(directory)
        return original(executable, directory, *args, **kwargs)

    monkeypatch.setattr(backend, "_execute", execute)
    result = model.run(SEQUENCE, timeout_seconds=2)
    assert result.stdout == b"complete\n"
    assert model.identity == identity
    assert not captured[0].exists()
    with pytest.raises(TerminationBackendError) as error:
        model.run(SEQUENCE, timeout_seconds=2)
    assert error.value.code == "backend_identity"


@pytest.mark.parametrize("operation", ["write_bytes", "chmod"])
def test_private_executable_failure_removes_temporary_directory(
    installation, monkeypatch, operation
):
    path, _ = installation
    model = backend.load_backend(path)
    original = getattr(Path, operation)
    directories = []

    def fail(executable, *args, **kwargs):
        if executable.name == "transterm" and executable.parent != path.parent:
            directories.append(executable.parent)
            raise OSError("synthetic private executable failure")
        return original(executable, *args, **kwargs)

    monkeypatch.setattr(Path, operation, fail)
    with pytest.raises(TerminationBackendError) as error:
        model.run(SEQUENCE, timeout_seconds=2)
    assert error.value.code == "native_io"
    assert error.value.diagnostics is None
    assert directories and all(not directory.exists() for directory in directories)


def test_expired_deadline_never_spawns(tmp_path, monkeypatch):
    monkeypatch.setattr(backend.time, "monotonic", lambda: 10)
    spawn = Mock(side_effect=AssertionError("expired work must not spawn"))
    monkeypatch.setattr(backend.subprocess, "Popen", spawn)
    with pytest.raises(TerminationBackendError) as error:
        backend._execute(Path(sys.executable), tmp_path, 10, None)
    spawn.assert_not_called()
    assert error.value.code == "native_timeout"
    assert error.value.diagnostics["returncode"] is None
    for stream in ("stdout", "stderr"):
        assert error.value.diagnostics[f"{stream}_bytes"] == 0
        assert error.value.diagnostics[f"{stream}_complete"] is False
