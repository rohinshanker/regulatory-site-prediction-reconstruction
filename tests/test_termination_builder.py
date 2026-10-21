"""Offline build controls with tiny Python tool doubles, no compiler/native run."""

import difflib
import hashlib
import io
import json
import os
import runpy
import stat
import sys
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from regsite import termination_backend as backend
from tools import build_termination_backend as builder


def digest(data):
    return hashlib.sha256(data).hexdigest()


def zip_bytes(members, *, extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        root = "transterm_hp_v2.09/"
        archive.writestr(root, b"")
        for name, content in members.items():
            archive.writestr(root + name, content)
        archive.writestr(root + "transterm", b"excluded upstream binary")
        archive.writestr(root + "2ndscore", b"excluded upstream binary")
        if extra:
            archive.writestr(root + extra[0], extra[1])
    return stream.getvalue()


@pytest.fixture
def build_inputs(tmp_path, monkeypatch):
    members = {
        name: (f"Original fixture {name}\n").encode() for name in builder.MEMBERS
    }
    members["seq.cc"] = b"if(i == EOF) return false;\n" * 3
    members["search.h"] = b"int set_max_len_loop(int, int);\n"
    members["expterm.dat"] = b"x" * 45788
    prototype = "".join(
        difflib.unified_diff(
            members["search.h"].decode().splitlines(keepends=True),
            members["search.h"]
            .replace(b"int ", b"void ")
            .decode()
            .splitlines(keepends=True),
            fromfile="a/search.h",
            tofile="b/search.h",
        )
    ).encode()
    monkeypatch.setattr(builder, "PROTOTYPE_PATCH_SHA256", digest(prototype))
    raw = zip_bytes(members)
    pins = {name: (len(content), digest(content)) for name, content in members.items()}
    monkeypatch.setattr(builder, "MEMBERS", pins)
    monkeypatch.setattr(
        builder,
        "SEQ_RESULT",
        digest(members["seq.cc"].replace(b"return false", b"return NULL")),
    )
    monkeypatch.setattr(
        builder, "HEADER_RESULT", digest(members["search.h"].replace(b"int ", b"void "))
    )
    monkeypatch.setattr(builder, "ARCHIVE_BYTES", len(raw))
    monkeypatch.setattr(builder, "ARCHIVE_SHA256", digest(raw))
    monkeypatch.setattr(builder, "PATCH_BYTES", 7)
    monkeypatch.setattr(builder, "NULL_PATCH_SHA256", digest(b"fixture"))
    monkeypatch.setattr(builder, "TABLE_SHA256", digest(members["expterm.dat"]))
    monkeypatch.setattr(backend, "TABLE_SHA256", digest(members["expterm.dat"]))
    archive_path = tmp_path / "source.zip"
    archive_path.write_bytes(raw)
    patch_path = tmp_path / "null.patch"
    patch_path.write_bytes(b"fixture")
    compiler = tmp_path / "compiler"
    compiler.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "assert sys.argv[1:] == ['--version']\nprint('Fixture compiler 1')\n"
    )
    compiler.chmod(0o755)
    make = tmp_path / "make"
    make.write_text(f"""#!{sys.executable}
from pathlib import Path
import os,sys
assert sys.argv[1:3] == ['-j1','transterm']
assert '-ffp-contract=off' in sys.argv[4]
assert 'MAKEFLAGS' not in os.environ
p = Path('transterm')
p.write_bytes(b'fake built binary')
p.chmod(0o755)
print('fixture build log')
""")
    make.chmod(0o755)
    return {
        "archive": archive_path,
        "patch": patch_path,
        "compiler": compiler,
        "make": make,
        "output": tmp_path / "external-output",
    }, members


def test_successful_offline_pipeline(build_inputs):
    args, members = build_inputs
    identity = builder.build_backend(**args, standard_library="fixture")
    output = args["output"]
    assert backend.load_backend(output / "backend.json").identity == identity
    assert (output / "source-original" / "seq.cc").read_bytes() == members["seq.cc"]
    assert (output / "source-build" / "seq.cc").read_bytes().count(b"return NULL") == 3
    assert (output / "source-build" / "search.h").read_bytes().startswith(b"void ")
    assert not (output / "source-original" / "transterm").exists()
    assert not (output / "source-original" / "2ndscore").exists()
    assert (output / "prototype-return-type.patch").stat().st_size > 0
    receipt = json.loads((output / "build-receipt.json").read_text())
    assert receipt["diagnostics"]["returncode"] == 0
    assert receipt["elapsed_seconds"] >= 0
    assert str(output) not in json.dumps(identity)
    assert "elapsed" not in json.dumps(identity)


@pytest.mark.parametrize("field", ["archive", "patch"])
def test_source_identity_failure(build_inputs, field):
    args, _ = build_inputs
    args[field].write_bytes(b"corrupt")
    with pytest.raises(backend.TerminationBackendError, match="backend_identity"):
        builder.build_backend(**args)
    assert not (args["output"] / "backend.json").exists()


def test_failing_build_has_no_success_receipt(build_inputs):
    args, _ = build_inputs
    args["make"].write_text(f"#!{sys.executable}\nimport sys\nsys.exit(2)\n")
    with pytest.raises(backend.TerminationBackendError, match="native_exit") as error:
        builder.build_backend(**args)
    assert error.value.diagnostics is not None
    assert error.value.diagnostics["returncode"] == 2
    assert not (args["output"] / "backend.json").exists()


@pytest.mark.parametrize(
    "body",
    [
        "print('no binary')",
        "from pathlib import Path; Path('expterm.dat').write_bytes(b'bad')",
        "import sys; sys.stdout.buffer.write(b'x'*262145)",
    ],
)
def test_incomplete_builds(build_inputs, body):
    args, _ = build_inputs
    args["make"].write_text(f"#!{sys.executable}\n{body}\n")
    with pytest.raises(backend.TerminationBackendError):
        builder.build_backend(**args)
    assert not (args["output"] / "backend.json").exists()


def test_explicit_platform_flags(build_inputs, tmp_path):
    args, _ = build_inputs
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    includes = tmp_path / "include"
    includes.mkdir()
    identity = builder.build_backend(
        **args, arch="arm64", sysroot=sdk, cxx_include=includes
    )
    receipt = json.loads((args["output"] / "build-receipt.json").read_text())
    flags = receipt["command"][4]
    assert "-arch arm64" in flags and f"-isysroot {sdk}" in flags
    assert identity["build"]["machine"] == "arm64"
    assert identity["build"]["extra_flags_sha256"] != digest(b"[]")


def test_invalid_options_and_existing_output(build_inputs, tmp_path):
    args, _ = build_inputs
    for kwargs in (
        {"arch": "-ffast-math"},
        {"sysroot": args["archive"]},
        {"standard_library": "bad/path"},
    ):
        with pytest.raises(backend.TerminationBackendError):
            builder.build_backend(**args, **kwargs)
        assert not (args["output"] / "backend.json").exists()
        if args["output"].exists():
            import shutil

            shutil.rmtree(args["output"])
    args["output"].mkdir()
    with pytest.raises(backend.TerminationBackendError, match="builder_io"):
        builder.build_backend(**args)
    args["output"] = Path(__file__).parents[1] / "new-backend"
    with pytest.raises(backend.TerminationBackendError, match="builder_output"):
        builder.build_backend(**args)


def test_explicit_compiler_symlink_and_unsafe_path(build_inputs):
    args, _ = build_inputs
    link = args["compiler"].with_name("clang++")
    link.symlink_to(args["compiler"])
    args["compiler"] = link
    assert builder.build_backend(**args)["build"]["compiler"] == "clang++"
    invalid = link.with_name("bad compiler")
    invalid.symlink_to(link)
    with pytest.raises(backend.TerminationBackendError, match="builder_tool"):
        builder._tool(invalid)


def test_unsafe_extraction_and_identity(build_inputs, tmp_path):
    _, members = build_inputs
    target = tmp_path / "extract"
    target.mkdir()
    for extra in (("../escape", b"bad"), ("seq.cc", b"duplicate")):
        with pytest.raises(backend.TerminationBackendError, match="builder_archive"):
            builder._extract(zip_bytes(members, extra=extra), target)
    bad = dict(members, **{"seq.cc": b"x"})
    with pytest.raises(backend.TerminationBackendError, match="builder_archive"):
        builder._extract(zip_bytes(bad), target)
    bad["seq.cc"] = b"x" * len(members["seq.cc"])
    with pytest.raises(backend.TerminationBackendError, match="backend_identity"):
        builder._extract(zip_bytes(bad), target)
    for mode in (stat.S_IFLNK | 0o777, stat.S_IFDIR | 0o755, stat.S_IFIFO | 0o600):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            root = "transterm_hp_v2.09/"
            archive.writestr(root, b"")
            for name, content in members.items():
                info = zipfile.ZipInfo(root + name)
                info.external_attr = (
                    mode if name == "seq.cc" else stat.S_IFREG | 0o600
                ) << 16
                archive.writestr(info, content)
            archive.writestr(root + "transterm", b"excluded")
            archive.writestr(root + "2ndscore", b"excluded")
        with pytest.raises(backend.TerminationBackendError, match="builder_archive"):
            builder._extract(stream.getvalue(), target)


def test_patch_failures(build_inputs, tmp_path, monkeypatch):
    _, members = build_inputs
    for name, value in members.items():
        (tmp_path / name).write_bytes(value)
    (tmp_path / "seq.cc").write_bytes(b"no sites")
    with pytest.raises(backend.TerminationBackendError, match="builder_patch"):
        builder._patch(tmp_path, b"fixture", tmp_path)
    (tmp_path / "seq.cc").write_bytes(members["seq.cc"])
    monkeypatch.setattr(builder, "SEQ_RESULT", "0" * 64)
    with pytest.raises(backend.TerminationBackendError, match="builder_patch"):
        builder._patch(tmp_path, b"fixture", tmp_path)
    monkeypatch.setattr(
        builder,
        "SEQ_RESULT",
        digest(members["seq.cc"].replace(b"return false", b"return NULL")),
    )
    (tmp_path / "search.h").write_bytes(b"bad")
    with pytest.raises(backend.TerminationBackendError, match="builder_patch"):
        builder._patch(tmp_path, b"fixture", tmp_path)
    (tmp_path / "seq.cc").write_bytes(members["seq.cc"])
    (tmp_path / "search.h").write_bytes(members["search.h"])
    monkeypatch.setattr(builder, "PROTOTYPE_PATCH_SHA256", "0" * 64)
    with pytest.raises(backend.TerminationBackendError, match="builder_patch"):
        builder._patch(tmp_path, b"fixture", tmp_path)


def test_builder_os_errors_and_invalid_zip(build_inputs, monkeypatch):
    args, _ = build_inputs
    monkeypatch.setattr(builder, "_extract", Mock(side_effect=zipfile.BadZipFile()))
    with pytest.raises(backend.TerminationBackendError, match="builder_io"):
        builder.build_backend(**args)
    proxy = Mock(wraps=os)
    proxy.name = "nt"
    monkeypatch.setattr(builder, "os", proxy)
    with pytest.raises(backend.TerminationBackendError, match="unsupported_platform"):
        builder.build_backend(**args)


def test_cli_success_and_failure(build_inputs, capsys):
    args, _ = build_inputs
    argv = [value for name, path in args.items() for value in ("--" + name, str(path))]
    assert builder.main(argv) == 0
    assert "built and identified" in capsys.readouterr().out
    assert builder.main(argv) == 1
    assert "builder_io" in capsys.readouterr().err
    with pytest.raises(SystemExit) as error:
        builder.main([])
    assert error.value.code == 2


def test_script_entrypoint(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["builder", "--help"])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(Path(builder.__file__)), run_name="__main__")
    assert error.value.code == 0


def test_invalid_root_entry(build_inputs, tmp_path):
    _, members = build_inputs
    stream = io.BytesIO()
    root = "transterm_hp_v2.09/"
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(root, b"unexpected directory data")
        for name, content in members.items():
            archive.writestr(root + name, content)
        archive.writestr(root + "transterm", b"excluded")
        archive.writestr(root + "2ndscore", b"excluded")
    with pytest.raises(backend.TerminationBackendError, match="builder_archive"):
        builder._extract(stream.getvalue(), tmp_path)
