# SPDX-License-Identifier: GPL-2.0-only
"""Run with unittest discovery; both real installations are mandatory."""

from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import tarfile
import tempfile
import unittest
from unittest import mock

from engine import identity, parse_ct, run_engine


COMPONENT = Path(__file__).resolve().parents[1]
REPOSITORY = COMPONENT.parents[1]
SPEC = importlib.util.spec_from_file_location("component_build", COMPONENT / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
FIXTURES = json.loads((COMPONENT / "tests/fixtures.json").read_text())["fixtures"]


class BuildContractTests(unittest.TestCase):
    def test_manifest_hashes(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text())
        builder.require_hash(COMPONENT / manifest["patch"]["file"], manifest["patch"]["sha256"])
        self.assertEqual(manifest["license"], "GPL-2.0-only")

    def test_wrong_archive_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "wrong.tgz"
            archive.write_bytes(b"wrong source")
            destination = Path(directory) / "new"
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                builder.install(archive, destination)
            self.assertFalse(destination.exists())

    def test_excess_parallelism_refused(self):
        for jobs in (0, 3):
            with self.subTest(jobs=jobs), self.assertRaisesRegex(ValueError, "jobs"):
                builder.install("unused", "unused", jobs)

    def test_existing_destination_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "empty.tgz"
            with tarfile.open(archive, "w:gz"):
                pass
            destination = Path(directory) / "existing"
            destination.mkdir()
            sentinel = destination / "keep"
            sentinel.write_text("preserve")
            with mock.patch.object(builder, "require_hash"), self.assertRaises(FileExistsError):
                builder.install(archive, destination)
            self.assertEqual(sentinel.read_text(), "preserve")

    def test_archive_traversal_and_links_refused(self):
        for name, member_type in (("RNAstructure/../../escape", tarfile.REGTYPE),
                                  ("RNAstructure/link", tarfile.SYMTYPE),
                                  ("/absolute", tarfile.REGTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                archive = Path(directory) / "unsafe.tgz"
                member = tarfile.TarInfo(name)
                member.type = member_type
                with tarfile.open(archive, "w:gz") as output:
                    output.addfile(member)
                with mock.patch.object(builder, "require_hash"), self.assertRaisesRegex(ValueError, "Unsafe"):
                    builder.install(archive, Path(directory) / "new")
                self.assertFalse((Path(directory) / "new").exists())


class StructuralCheckerTests(unittest.TestCase):
    def test_empty_and_truncated(self):
        for text in ("", "4 test\n1 A 0 2 0 1\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_ct(text)

    def test_pair_invariants(self):
        def ct(sequence, partners):
            size = len(sequence)
            return f"{size} test\n" + "".join(
                f"{i} {base} {i-1} {i+1 if i<size else 0} {partners[i-1]} {i}\n"
                for i, base in enumerate(sequence, 1))
        cases = (("GCGC", [4, 3, 2, 1], None),
                 ("GCGC", [4, 3, 2, 0], "Nonreciprocal"),
                 ("GGCC", [3, 4, 1, 2], "Crossing"),
                 ("AIAA", [0, 4, 0, 2], "Paired linker"),
                 ("AAAA", [4, 0, 0, 1], "Noncanonical"),
                 ("GCGC", [5, 0, 0, 0], "Invalid CT partner"))
        for sequence, partners, error in cases:
            with self.subTest(sequence=sequence, partners=partners):
                if error:
                    with self.assertRaisesRegex(ValueError, error):
                        parse_ct(ct(sequence, partners))
                else:
                    self.assertEqual(parse_ct(ct(sequence, partners))[0].pairs, ((1, 4), (2, 3)))


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing engines must fail the gate, never silently skip it.
        cls.patched = Path(os.environ["RNASTRUCTURE66_PATCHED"])
        cls.original = Path(os.environ["RNASTRUCTURE66_ORIGINAL"])

    def test_frozen_structures_and_independent_energies(self):
        records = json.loads((REPOSITORY / "benchmarks/rbs/karlsen2018-development.json").read_text())["records"]
        for fixture in FIXTURES:
            with self.subTest(case=fixture["id"]), tempfile.TemporaryDirectory() as directory:
                if "leader" in fixture:
                    sequence = fixture["leader"]
                else:
                    sequence = next(row["sequence"] for row in records if row["id"] == fixture["id"])
                    sequence = sequence[:fixture["leader_bases"]].upper().replace("T", "U")
                    self.assertEqual(hashlib.sha256(sequence.encode()).hexdigest(), fixture["leader_sha256"])
                structures, energies = run_engine(self.patched, directory, sequence,
                                                  fixture["anti_sd"], fixture["temperature"])
                self.assertEqual(len(structures), fixture["structure_count"])
                self.assertEqual(identity(structures), fixture["structure_sha256"])
                self.assertEqual(identity(structures, energies), fixture["evaluated_sha256"])
                self.assertEqual(sum(item.energy is not None and item.energy != energy
                                     for item, energy in zip(structures, energies)),
                                 fixture["native_evaluation_mismatches"])
                if "manual_energy" in fixture:
                    self.assertEqual(energies[0], Decimal(fixture["manual_energy"]))
                    if structures[0].energy is not None:
                        self.assertEqual(structures[0].energy, energies[0])
                if "manual_pairs" in fixture:
                    self.assertEqual(structures[0].pairs, tuple(map(tuple, fixture["manual_pairs"])))

    def test_synthetic_inputs_independent_of_development(self):
        generator = random.Random(6603)
        generated = ["".join(generator.choice("ACGU") for _ in range(60 if i < 30 else 100))
                     for i in range(60)]
        for fixture in FIXTURES:
            if "seed" in fixture:
                self.assertEqual(fixture["leader"], generated[fixture["index"]])

    def test_original_reproduces_synthetic_defects_and_unaffected_controls(self):
        for fixture in FIXTURES:
            if "leader" not in fixture:
                continue
            with self.subTest(case=fixture["id"]), tempfile.TemporaryDirectory() as directory:
                if fixture["original_status"] != "valid":
                    with self.assertRaisesRegex(ValueError, fixture["original_status"].split(":")[0]):
                        run_engine(self.original, directory, fixture["leader"], fixture["anti_sd"], fixture["temperature"])
                else:
                    structures, energies = run_engine(self.original, directory, fixture["leader"], fixture["anti_sd"], fixture["temperature"])
                    self.assertEqual(identity(structures), fixture["original_structure_sha256"])
                    self.assertEqual(identity(structures), fixture["structure_sha256"])
                    self.assertEqual(identity(structures, energies), fixture["evaluated_sha256"])

    def test_deterministic_synthetic_panel(self):
        generator = random.Random(6603)
        unchanged = changed = original_failed = 0
        for index in range(60):
            sequence = "".join(generator.choice("ACGU") for _ in range(60 if index < 30 else 100))
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                patched, energies = run_engine(self.patched, Path(directory) / "patched", sequence, "ACCUCCUUU")
                self.assertEqual(len(patched), len(energies))
                try:
                    original, _ = run_engine(self.original, Path(directory) / "original", sequence, "ACCUCCUUU")
                except ValueError:
                    original_failed += 1
                else:
                    if identity(original) == identity(patched):
                        unchanged += 1
                    else:
                        changed += 1
        self.assertEqual((unchanged, changed, original_failed), (44, 10, 6))
        print("Synthetic panel: 60/60 patched valid; 54/60 original valid; 44 unchanged; 10 valid outputs changed.")

    def test_representative_development_inputs(self):
        records = json.loads((REPOSITORY / "benchmarks/rbs/karlsen2018-development.json").read_text())["records"]
        # Select only by normalized sequence hash, without consulting outcomes.
        sequences = sorted({row["sequence"][:100].upper().replace("T", "U") for row in records},
                           key=lambda sequence: hashlib.sha256(sequence.encode()).hexdigest())[:12]
        self.assertEqual(len(sequences), 12)
        original_failed = changed = 0
        for index, sequence in enumerate(sequences):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                patched, _ = run_engine(self.patched, Path(directory) / "patched", sequence, "ACCUCCUUU")
                try:
                    original, _ = run_engine(self.original, Path(directory) / "original", sequence, "ACCUCCUUU")
                except ValueError:
                    original_failed += 1
                else:
                    changed += identity(original) != identity(patched)
        print(f"Development sequence panel: 12/12 patched valid; {12-original_failed}/12 original valid; {changed} valid outputs changed.")


if __name__ == "__main__":
    unittest.main()
