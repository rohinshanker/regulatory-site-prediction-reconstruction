# SPDX-License-Identifier: GPL-2.0-only
"""Installer tests use synthetic archives and subprocesses, never real builds."""

from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


COMPONENT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("installer_under_test", COMPONENT / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
ORIGINAL = builder.ORIGINAL_COMPONENT


def digest(data):
    return hashlib.sha256(data).hexdigest()


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.archive = self.directory / "source.tgz"
        self.destination = self.directory / "build"
        self.component = self.directory / "component"
        self.component.mkdir()
        self.pristine = b"synthetic pristine source\n"
        self.patched = b"synthetic repaired source\n"
        self.files = {
            "RNAstructure/src/algorithm.cpp": self.pristine,
            "RNAstructure/data_tables/rna.dat": b"synthetic table\n",
            "RNAstructure/ReadMe.txt": b"synthetic notice\n",
        }
        self.write_archive()
        self.manifests = {}
        for component, name in builder.MANIFESTS.items():
            manifest = json.loads((COMPONENT / name).read_text())
            manifest["upstream"].update({
                "archive_sha256": builder.sha256(self.archive),
                "archive_bytes": self.archive.stat().st_size,
                "source_sha256": digest(self.pristine),
            })
            if manifest["patch"] is not None:
                patch = self.component / manifest["patch"]["file"]
                patch.write_bytes(b"synthetic patch\n")
                manifest["patch"].update({
                    "sha256": builder.sha256(patch),
                    "patched_source_sha256": digest(self.patched),
                })
            self.manifests[component] = manifest
            self.save_manifest(component)
        self.stack.enter_context(mock.patch.object(builder, "COMPONENT", self.component))
        self.system = self.stack.enter_context(mock.patch.object(builder.platform, "system", return_value="Linux"))
        self.which = self.stack.enter_context(mock.patch.object(builder.shutil, "which", side_effect=lambda name: f"/tools/{name}"))
        self.run = self.stack.enter_context(mock.patch.object(builder.subprocess, "run", side_effect=self.fake_run))
        self.output = self.stack.enter_context(mock.patch.object(builder.subprocess, "check_output", side_effect=self.fake_output))
        self.stack.enter_context(mock.patch.object(builder.platform, "platform", return_value="test-platform"))
        self.stack.enter_context(mock.patch.object(builder.platform, "machine", return_value="test-machine"))

    def write_archive(self, extra=None):
        with tarfile.open(self.archive, "w:gz") as archive:
            directory = tarfile.TarInfo("RNAstructure/data_tables/subdirectory")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            for name, data in self.files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            if extra is not None:
                archive.addfile(extra)

    def save_manifest(self, component):
        (self.component / builder.MANIFESTS[component]).write_text(json.dumps(self.manifests[component]))

    def refresh_archive_hash(self):
        self.manifests[ORIGINAL]["upstream"]["archive_sha256"] = builder.sha256(self.archive)
        self.save_manifest(ORIGINAL)

    def fake_run(self, command, **kwargs):
        if command[0] == "patch":
            self.assertEqual(kwargs["stdin"].read(), b"synthetic patch\n")
            (kwargs["cwd"] / "src/algorithm.cpp").write_bytes(self.patched)
        elif command[0] == "make":
            exe = kwargs["cwd"] / "exe"
            exe.mkdir()
            for name in ("Fold", "bifold", "efn2"):
                (exe / name).write_bytes(name.encode())
        return subprocess.CompletedProcess(command, 0)

    def fake_output(self, command, **kwargs):
        self.assertEqual(kwargs, {"text": True})
        if command[0] == "xcrun":
            return "/test/sdk\n"
        if command[0] == "file":
            return "test executable architecture\n"
        return "test compiler version\n"

    def install(self, **kwargs):
        return builder.install(self.archive, self.destination, component=ORIGINAL, **kwargs)

    def test_original_receipt_and_unchanged_source(self):
        root = self.install(jobs=1)
        self.assertEqual((root / "src/algorithm.cpp").read_bytes(), self.pristine)
        self.assertEqual((root / "ReadMe.txt").read_bytes(), self.files["RNAstructure/ReadMe.txt"])
        self.assertFalse((root / "traceback-build.json").exists())
        self.run.assert_called_once()
        self.assertEqual(self.run.call_args.args[0], ["make", "-j1", "Fold", "bifold", "efn2"])
        receipt = json.loads((root / "original-build.json").read_text())
        self.assertEqual(receipt, {
            "component": ORIGINAL, "license": "GPL-2.0-only",
            "source_archive_sha256": builder.sha256(self.archive),
            "source_archive_bytes": self.archive.stat().st_size,
            "patch_applied": False, "patch_sha256": None,
            "source_file": "src/algorithm.cpp", "source_sha256": digest(self.pristine),
            "build_command": ["make", "-j1", "Fold", "bifold", "efn2"],
            "platform": "test-platform", "machine": "test-machine",
            "compiler_version": "test compiler version",
            "executable_architecture": dict.fromkeys(("Fold", "bifold", "efn2"), "test executable architecture"),
            "executable_sha256": {name: digest(name.encode()) for name in ("Fold", "bifold", "efn2")},
            "table_sha256": {"rna.dat": digest(b"synthetic table\n")},
        })
        self.assertNotIn("patch", [call.args[0][0] for call in self.run.call_args_list])
        self.assertNotIn("patch", [call.args[0] for call in self.which.call_args_list])

    def test_both_repairs_preserve_schema_and_patch_command(self):
        for component in (builder.DEFAULT_COMPONENT, "rnastructure-6.6-linker-3"):
            with self.subTest(component=component):
                destination = self.directory / component
                root = builder.install(self.archive, destination, component=component)
                receipt = json.loads((root / "traceback-build.json").read_text())
                self.assertEqual(receipt["component"], component)
                self.assertEqual(receipt["patch_sha256"], digest(b"synthetic patch\n"))
                self.assertEqual(receipt["patched_source_sha256"], digest(self.patched))
                self.assertEqual(list(receipt), [
                    "component", "license", "source_archive_sha256", "patch_sha256",
                    "patched_source_sha256", "build_command", "platform", "machine",
                    "compiler_version", "executable_architecture", "executable_sha256", "table_sha256",
                ])
                self.assertEqual((root / "traceback-build.json").read_text(), json.dumps(receipt, indent=2) + "\n")
                self.assertFalse((root / "original-build.json").exists())
        patches = [call for call in self.run.call_args_list if call.args[0][0] == "patch"]
        self.assertEqual(len(patches), 2)
        for call in patches:
            self.assertEqual(call.args[0], ["patch", "--batch", "--fuzz=0", "-p1"])
            self.assertTrue(call.kwargs["check"])
        self.assertEqual(builder.load_manifest()["component"], builder.DEFAULT_COMPONENT)

    def test_macos_sdk_diagnostic_command_and_environment(self):
        self.system.return_value = "Darwin"
        dirty = dict.fromkeys(("MAKEFLAGS", "GNUMAKEFLAGS", "MAKEFILES", "MFLAGS", "MAKEOVERRIDES", "RNA_MAKE_OS", "RNA_MAKE_ARCH", "RNA_INCLUDE_CUDA", "CUDA", "DATAPATH", "CXX", "CXXFLAGS", "CPP_FLAGS", "LDFLAGS", "LDLIBS"), "inherited")
        with mock.patch.dict(os.environ, {**dirty, "KEEP_THIS": "yes"}):
            self.install(optimize=False)
        self.assertEqual(self.run.call_args_list[0], mock.call(["xcode-select", "-p"], capture_output=True, text=True))
        call = self.run.call_args
        self.assertEqual(call.args[0], ["make", "-j2", "Fold", "bifold", "efn2", "optimize=off", "CXX=clang++ -isysroot /test/sdk -isystem /test/sdk/usr/include/c++/v1"])
        self.assertTrue(call.kwargs["check"])
        self.assertEqual(call.kwargs["env"]["KEEP_THIS"], "yes")
        self.assertFalse(set(dirty) & set(call.kwargs["env"]))
        self.assertEqual(self.output.call_args_list[1], mock.call(["clang++", "--version"], text=True))

    def test_manifests_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            builder.load_manifest("unsupported")
        original = deepcopy(self.manifests[ORIGINAL])
        cases = [
            {"component": builder.DEFAULT_COMPONENT}, {"schema_version": 2},
            {"license": "other"}, {"patch": {}}, {"predecessor": {}},
            {"patch_applied": True}, {"upstream": None}, {"upstream": {}},
            {"upstream": {**original["upstream"], "version": "other"}},
            {"upstream": {**original["upstream"], "source_file": "../escape"}},
            {"upstream": {**original["upstream"], "archive_bytes": "x"}},
            {"upstream": {**original["upstream"], "archive_bytes": 0}},
        ]
        for update in cases:
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.manifests[ORIGINAL] = {**original, **update}
                self.save_manifest(ORIGINAL)
                self.install()
        self.manifests[ORIGINAL] = original
        del self.manifests[ORIGINAL]["patch"]
        self.save_manifest(ORIGINAL)
        with self.assertRaisesRegex(ValueError, "patch: null"):
            builder.load_manifest(ORIGINAL)
        component = builder.DEFAULT_COMPONENT
        for patch in (None, {}, "patch", {"file": "x", "sha256": "x", "patched_source_sha256": ""}, {"file": 1, "sha256": "x", "patched_source_sha256": "x"}):
            with self.subTest(patch=patch), self.assertRaisesRegex(ValueError, "requires a patch"):
                self.manifests[component]["patch"] = patch
                self.save_manifest(component)
                builder.load_manifest()
        self.assertFalse(self.destination.exists())
        self.run.assert_not_called()

    def test_malformed_manifests_and_archive(self):
        path = self.component / builder.MANIFESTS[ORIGINAL]
        for text in ("[]", "{}", "{invalid json"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                path.write_text(text)
                self.install()
        self.archive.write_bytes(b"not a tar archive")
        self.refresh_archive_hash()
        with self.assertRaises(tarfile.ReadError):
            self.install()
        self.assertFalse(self.destination.exists())

    def test_invalid_jobs_and_missing_archive(self):
        for jobs in (0, 3, -1):
            with self.assertRaisesRegex(ValueError, "jobs"):
                self.install(jobs=jobs)
        self.archive.unlink()
        with self.assertRaises(FileNotFoundError):
            self.install()
        self.assertFalse(self.destination.exists())

    def test_archive_and_patch_hash_failure(self):
        self.archive.write_bytes(b"wrong archive")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.install()
        self.write_archive()
        self.manifests[builder.DEFAULT_COMPONENT]["upstream"]["archive_sha256"] = builder.sha256(self.archive)
        self.save_manifest(builder.DEFAULT_COMPONENT)
        (self.component / "traceback.patch").write_bytes(b"wrong patch")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            builder.install(self.archive, self.destination)
        self.run.assert_not_called()
        self.assertFalse(self.destination.exists())

    def test_unsafe_members_before_destination(self):
        for name, kind in (("", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE), ("other/file", tarfile.REGTYPE), ("RNAstructure/../escape", tarfile.REGTYPE), ("RNAstructure/link", tarfile.SYMTYPE), ("RNAstructure/hard", tarfile.LNKTYPE), ("RNAstructure/device", tarfile.CHRTYPE), ("RNAstructure/fifo", tarfile.FIFOTYPE)):
            with self.subTest(name=name, kind=kind):
                member = tarfile.TarInfo(name)
                member.type = kind
                self.write_archive(member)
                self.refresh_archive_hash()
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    self.install()
                self.assertFalse(self.destination.exists())

    def test_existing_destination_and_symlink_preserved(self):
        sentinel = self.directory / "sentinel"
        sentinel.mkdir()
        (sentinel / "keep").write_text("preserve")
        self.destination.symlink_to(sentinel, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            self.install()
        self.assertEqual((sentinel / "keep").read_text(), "preserve")
        self.run.assert_not_called()

    def test_old_python_extraction_allowlist(self):
        # Modern tarfile's internal implementation still needs data_filter.
        # Hide only the public feature probe, preserving the real extractor.
        real_tarfile = builder.tarfile
        proxy = mock.Mock(spec=["open"])
        proxy.open = real_tarfile.open
        with mock.patch.object(builder, "tarfile", proxy):
            self.install()
        self.assertTrue((self.destination / "RNAstructure/src/algorithm.cpp").is_file())

    def test_missing_prerequisites(self):
        for tool in ("g++", "make", "file", "patch", "xcode-select", "xcrun", "clang++"):
            components = (builder.DEFAULT_COMPONENT,) if tool == "patch" else (builder.DEFAULT_COMPONENT, ORIGINAL)
            for component in components:
                with self.subTest(tool=tool, component=component):
                    self.system.return_value = "Darwin" if tool in ("xcode-select", "xcrun", "clang++") else "Linux"
                    self.which.side_effect = lambda name: None if name == tool else f"/tools/{name}"
                    with self.assertRaises(RuntimeError):
                        builder.install(self.archive, self.destination, component=component)
                    self.assertFalse(self.destination.exists())

    def test_absent_macos_tools_and_empty_sdk(self):
        self.system.return_value = "Darwin"
        self.run.side_effect = None
        self.run.return_value = subprocess.CompletedProcess([], 1)
        with self.assertRaisesRegex(RuntimeError, "Install/select"):
            self.install()
        self.output.assert_not_called()
        self.run.return_value = subprocess.CompletedProcess([], 0)
        self.output.side_effect = None
        self.output.return_value = "\n"
        with self.assertRaisesRegex(RuntimeError, "No macOS SDK"):
            self.install()
        self.assertFalse(self.destination.exists())

    def test_compile_and_patch_failures_retain_source(self):
        for component, failed in ((ORIGINAL, "make"), (builder.DEFAULT_COMPONENT, "patch")):
            with self.subTest(component=component):
                destination = self.directory / component
                def fail(command, **kwargs):
                    if command[0] == failed:
                        raise subprocess.CalledProcessError(2, command)
                    return self.fake_run(command, **kwargs)
                self.run.side_effect = fail
                with self.assertRaises(subprocess.CalledProcessError):
                    builder.install(self.archive, destination, component=component)
                root = destination / "RNAstructure"
                self.assertEqual((root / "src/algorithm.cpp").read_bytes(), self.pristine)
                self.assertFalse((root / "original-build.json").exists())
                self.assertFalse((root / "traceback-build.json").exists())

    def test_source_hash_before_patch_after_patch_and_after_compile(self):
        for phase in ("before", "patch", "make"):
            with self.subTest(phase=phase):
                destination = self.directory / phase
                if phase == "before":
                    self.files["RNAstructure/src/algorithm.cpp"] = b"wrong source"
                    self.write_archive()
                    self.refresh_archive_hash()
                    component = ORIGINAL
                else:
                    self.files["RNAstructure/src/algorithm.cpp"] = self.pristine
                    self.write_archive()
                    component = builder.DEFAULT_COMPONENT if phase == "patch" else ORIGINAL
                    self.manifests[component]["upstream"]["archive_sha256"] = builder.sha256(self.archive)
                    self.save_manifest(component)
                def corrupt(command, **kwargs):
                    result = self.fake_run(command, **kwargs)
                    if command[0] == phase:
                        (kwargs["cwd"] / "src/algorithm.cpp").write_bytes(b"corruption")
                    return result
                self.run.side_effect = corrupt
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    builder.install(self.archive, destination, component=component)
                self.assertTrue(destination.is_dir())
                self.assertFalse(list(destination.rglob("*-build.json")))

    def test_compiler_sdk_and_file_errors_propagate(self):
        for command in ("g++", "xcrun", "file"):
            with self.subTest(command=command):
                destination = self.directory / command
                self.system.return_value = "Darwin" if command == "xcrun" else "Linux"
                def fail(args, **kwargs):
                    if args[0] == command:
                        raise subprocess.CalledProcessError(1, args)
                    return self.fake_output(args, **kwargs)
                self.output.side_effect = fail
                with self.assertRaises(subprocess.CalledProcessError):
                    builder.install(self.archive, destination, component=ORIGINAL)
                self.assertFalse(list(destination.rglob("*-build.json")))


class ManifestAndCliTests(unittest.TestCase):
    def test_real_pins_and_default(self):
        original = builder.load_manifest(ORIGINAL)
        self.assertEqual(original["upstream"], builder.load_manifest()["upstream"])
        self.assertEqual(original["upstream"]["archive_sha256"], "1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3")
        self.assertEqual(original["upstream"]["archive_bytes"], 30765790)
        self.assertEqual(original["upstream"]["source_sha256"], "c024b600aabfad624fa0d4dbcd2297b9aacdb654ad2e491686847b705fa343d8")
        self.assertIsNone(original["patch"])
        self.assertEqual(builder.DEFAULT_COMPONENT, "rnastructure-6.6-traceback-2")

    def test_cli_selection_defaults_errors_and_entrypoint(self):
        base = ["build.py", "--archive", "source.tgz", "--destination", "new"]
        for extra, expected in (([], (2, True, builder.DEFAULT_COMPONENT)), (["--component", ORIGINAL, "--jobs", "1", "--no-optimize"], (1, False, ORIGINAL))):
            with mock.patch.object(sys, "argv", base + extra), mock.patch.object(builder, "install", return_value=Path("installed")) as install, mock.patch("sys.stdout", new_callable=io.StringIO) as output:
                builder.main()
            install.assert_called_once_with(Path("source.tgz"), Path("new"), *expected)
            self.assertEqual(output.getvalue(), "installed\n")
        for extra in (["--component", "unknown"], ["--jobs", "3"], ["--patch", "misleading"]):
            with mock.patch.object(sys, "argv", base + extra), mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as error:
                builder.main()
            self.assertEqual(error.exception.code, 2)
        for failure in (OSError("missing"), ValueError("hash"), RuntimeError("tools"), subprocess.CalledProcessError(2, ["make"]), tarfile.ReadError("archive")):
            with mock.patch.object(sys, "argv", base), mock.patch.object(builder, "install", side_effect=failure), mock.patch("sys.stderr", new_callable=io.StringIO) as output, self.assertRaises(SystemExit) as error:
                builder.main()
            self.assertEqual(error.exception.code, 1)
            self.assertIn("retained", output.getvalue())
        with mock.patch.object(sys, "argv", ["build.py", "--help"]), mock.patch("sys.stdout", new_callable=io.StringIO), self.assertRaises(SystemExit) as error:
            runpy.run_path(str(COMPONENT / "build.py"), run_name="__main__")
        self.assertEqual(error.exception.code, 0)
