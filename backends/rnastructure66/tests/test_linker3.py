# SPDX-License-Identifier: GPL-2.0-only
"""Version-3 (linker-3) regressions; all three real installations are mandatory."""

from decimal import Decimal
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import tempfile
import unittest
from unittest import mock

from engine import energy_census, identity, linker_topology, run_engine, verify_installation


COMPONENT = Path(__file__).resolve().parents[1]
REPOSITORY = COMPONENT.parents[1]
SPEC = importlib.util.spec_from_file_location("component_build", COMPONENT / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
LINKER3 = "rnastructure-6.6-linker-3"
TRACEBACK2 = "rnastructure-6.6-traceback-2"
SNAPSHOTS = json.loads((COMPONENT / "tests/fixtures-linker3.json").read_text())
PREVIOUS = json.loads((COMPONENT / "tests/fixtures-traceback2.json").read_text())
LEADER_484_17 = SNAPSHOTS["linker_484_17"]["leader"]
ANTI_SD = "ACCUCCUUU"
SUBOPTIMAL = ("--maximum", "20", "--percent", "10", "--window", "0")
GUARD_REMOVED = [
    "\t\t\t\t\tif (!lfce[i]) wmb.f(i, j) = min(wmb.f(i, j), wmb.f(i + 1, j) + mbl_nucleotide + ct->SHAPEss_give_value(i));",
    "\t\t\t\t\tif (!lfce[j]) wmb.f(i, j) = min(wmb.f(i, j), wmb.f(i, j - 1) + mbl_nucleotide + ct->SHAPEss_give_value(j));",
]
GUARD_ADDED = [
    "\t\t\t\t// The linker centre carries the same INFINITE_ENERGY marker as the",
    "\t\t\t\t// ordinary W strips above: a multibranch fragment may not leave it",
    "\t\t\t\t// unpaired. Only W2/WMB2 represent that intermolecular exterior loop.",
    "\t\t\t\t\tif (!lfce[i]) wmb.f(i, j) = min(wmb.f(i, j), wmb.f(i + 1, j) + mbl_nucleotide + ct->SHAPEss_give_value(i)",
    "\t\t\t\t\t\t+ ((fce.f(i, i) & INTER) ? INFINITE_ENERGY : 0));",
    "\t\t\t\t\tif (!lfce[j]) wmb.f(i, j) = min(wmb.f(i, j), wmb.f(i, j - 1) + mbl_nucleotide + ct->SHAPEss_give_value(j)",
    "\t\t\t\t\t\t+ ((fce.f(j, j) & INTER) ? INFINITE_ENERGY : 0));",
]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hunks(patch_text):
    """Split a unified diff body into its hunks, each starting at its header."""
    return [part for part in re.split(r"(?m)^(?=@@ )", patch_text) if part.startswith("@@")]


def panel_6603():
    generator = random.Random(6603)
    return ["".join(generator.choice("ACGU") for _ in range(60 if i < 30 else 100)) for i in range(60)]


def panel_fresh():
    generator = random.Random(26003)
    return ["".join(generator.choice("ACGU") for _ in range(generator.choice((60, 80, 100))))
            for _ in range(40)]


def development_leaders():
    records = json.loads((REPOSITORY / "benchmarks/rbs/karlsen2018-development.json").read_text())["records"]
    return sorted({row["sequence"][:100].upper().replace("T", "U") for row in records},
                  key=lambda sequence: hashlib.sha256(sequence.encode()).hexdigest())[:12]


def resolve_sequence(name, reference):
    """Resolve a fixture sequence: literal, panel_6603:<index>, or a traceback-2 control id."""
    if reference is None:
        return next(fixture["leader"] for fixture in PREVIOUS["fixtures"] if fixture["id"] == name)
    if reference.startswith("panel_6603:"):
        return panel_6603()[int(reference.split(":")[1])]
    return reference


def snapshot(structures, energies):
    """Structural/energy identity of one ordered output, as frozen in the fixtures."""
    anomalies = sum(linker_topology(item)[0] == "connected" and linker_topology(item)[1] >= 2
                    and energy - item.energy > Decimal("0.2")
                    for item, energy in zip(structures, energies, strict=True))
    return {"structure_count": len(structures), "structure_sha256": identity(structures),
            "evaluated_sha256": identity(structures, energies),
            "native_evaluation_mismatches": sum(item.energy is not None and item.energy != energy
                                                for item, energy in zip(structures, energies, strict=True)),
            "energy_census": energy_census(structures, energies), "multibranch_anomalies": anomalies,
            "first_energy": str(energies[0]), "first_pairs": [list(pair) for pair in structures[0].pairs]}


def control_snapshot(structures, energies):
    return {"n": len(structures), "structure_sha256": identity(structures),
            "evaluated_sha256": identity(structures, energies),
            "mfe_pairs": [list(pair) for pair in structures[0].pairs],
            "native": str(structures[0].energy), "efn2": str(energies[0])}


def describe_change(before, after):
    """Describe ordered-output differences between two engines on one input."""
    first = {item.pairs: (item, energy) for item, energy in zip(*before, strict=True)}
    second = {item.pairs: (item, energy) for item, energy in zip(*after, strict=True)}

    def entries(source, other):
        return [{"native": str(item.energy), "evaluated": str(energy), "topology": list(linker_topology(item))}
                for pairs, (item, energy) in source.items() if pairs not in other]

    return {"mfe_same": before[0][0].pairs == after[0][0].pairs,
            "v2_mfe": [str(before[0][0].energy), str(before[1][0])],
            "v3_mfe": [str(after[0][0].energy), str(after[1][0])],
            "only_traceback2": entries(first, second), "only_linker3": entries(second, first),
            "common_native_energy_changed": [
                {"traceback2": str(first[pairs][0].energy), "linker3": str(second[pairs][0].energy)}
                for pairs in first if pairs in second and first[pairs][0].energy != second[pairs][0].energy]}


class Linker3BuildContractTests(unittest.TestCase):
    def test_manifest_and_fixture_pins(self):
        manifest = builder.load_manifest(LINKER3)
        previous = builder.load_manifest(TRACEBACK2)
        self.assertEqual(manifest["license"], "GPL-2.0-only")
        self.assertEqual(manifest["upstream"], previous["upstream"])
        self.assertEqual(manifest["patch"]["file"], "linker.patch")
        builder.require_hash(COMPONENT / manifest["patch"]["file"], manifest["patch"]["sha256"])
        self.assertEqual(manifest["predecessor"], {
            "component": TRACEBACK2, "manifest": "manifest.json",
            "patch_sha256": previous["patch"]["sha256"],
            "patched_source_sha256": previous["patch"]["patched_source_sha256"]})
        self.assertEqual(SNAPSHOTS["component"], LINKER3)
        self.assertEqual(SNAPSHOTS["patch_sha256"], manifest["patch"]["sha256"])
        self.assertEqual(SNAPSHOTS["patched_source_sha256"], manifest["patch"]["patched_source_sha256"])
        self.assertEqual(SNAPSHOTS["predecessor"], {
            "component": TRACEBACK2, "manifest_sha256": sha256(COMPONENT / "manifest.json"),
            "patch_sha256": previous["patch"]["sha256"],
            "patched_source_sha256": previous["patch"]["patched_source_sha256"],
            "fixtures_sha256": sha256(COMPONENT / "tests/fixtures-traceback2.json")})
        self.assertEqual(builder.DEFAULT_COMPONENT, TRACEBACK2)
        self.assertEqual(builder.load_manifest(), previous)

    def test_unknown_or_mismatched_component_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown component"):
            builder.load_manifest("rnastructure-6.6-unknown")
        with mock.patch.dict(builder.MANIFESTS, {LINKER3: "manifest.json"}):
            with self.assertRaisesRegex(ValueError, "Manifest component mismatch"):
                builder.load_manifest(LINKER3)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "new"
            with self.assertRaisesRegex(ValueError, "Unknown component"):
                builder.install(Path(directory) / "missing.tgz", destination, component="rnastructure-6.6-unknown")
            self.assertFalse(destination.exists())
        arguments = ["build.py", "--archive", "x", "--destination", "y", "--component", "rnastructure-6.6-unknown"]
        with mock.patch("sys.argv", arguments), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
            builder.main()

    def test_cumulative_patch_is_traceback2_plus_guard_hunk(self):
        previous = (COMPONENT / "traceback.patch").read_text()
        current = (COMPONENT / "linker.patch").read_text()
        self.assertEqual(current.splitlines()[:2], ["--- a/src/algorithm.cpp", "+++ b/src/algorithm.cpp"])
        old_hunks, new_hunks = hunks(previous), hunks(current)
        self.assertEqual((len(old_hunks), len(new_hunks)), (5, 6))
        for hunk in old_hunks:
            self.assertIn(hunk, new_hunks)
        extra = [hunk for hunk in new_hunks if hunk not in old_hunks]
        self.assertEqual(len(extra), 1)
        body = extra[0].splitlines()[1:]
        self.assertEqual([line[1:] for line in body if line.startswith("-")], GUARD_REMOVED)
        self.assertEqual([line[1:] for line in body if line.startswith("+")], GUARD_ADDED)


class Linker3EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing engines must fail the gate, never silently skip it.
        cls.engines = {"original": Path(os.environ["RNASTRUCTURE66_ORIGINAL"]),
                       "traceback2": Path(os.environ["RNASTRUCTURE66_PATCHED"]),
                       "linker3": Path(os.environ["RNASTRUCTURE66_LINKER3"])}
        verify_installation(cls.engines["linker3"], builder.load_manifest(LINKER3))
        verify_installation(cls.engines["traceback2"], builder.load_manifest(TRACEBACK2))
        upstream = builder.load_manifest(TRACEBACK2)["upstream"]
        if sha256(cls.engines["original"] / upstream["source_file"]) != upstream["source_sha256"]:
            raise ValueError("Original source hash mismatch")

    def fold(self, engine, sequence, anti_sd=None, **arguments):
        with tempfile.TemporaryDirectory() as directory:
            return run_engine(self.engines[engine], directory, sequence, anti_sd, **arguments)

    def try_fold(self, engine, sequence, anti_sd=None, **arguments):
        try:
            return self.fold(engine, sequence, anti_sd, **arguments)
        except ValueError as error:
            return str(error)

    def test_source_differs_from_traceback2_only_by_guard(self):
        before = (self.engines["traceback2"] / "src/algorithm.cpp").read_text().splitlines()
        after = (self.engines["linker3"] / "src/algorithm.cpp").read_text().splitlines()
        diff = list(difflib.unified_diff(before, after, n=0, lineterm=""))[2:]
        headers = [line for line in diff if line.startswith("@@")]
        self.assertTrue(headers)
        for header in headers:
            start = int(re.match(r"@@ -(\d+)", header).group(1))
            self.assertTrue(5100 <= start <= 5120, header)
        self.assertEqual([line[1:] for line in diff if line.startswith("-")], GUARD_REMOVED)
        self.assertEqual([line[1:] for line in diff if line.startswith("+")], GUARD_ADDED)

    def test_linker_484_17_repaired(self):
        generator = random.Random(484)
        sequences = ["".join(generator.choice("ACGU") for _ in range(generator.choice((60, 80, 100))))
                     for _ in range(18)]
        self.assertEqual(sequences[17], LEADER_484_17)
        for engine in ("original", "traceback2"):
            with self.subTest(engine=engine), self.assertRaisesRegex(ValueError, "Folding failed: exit 0;"):
                self.fold(engine, LEADER_484_17, ANTI_SD)
        structures, energies = self.fold("linker3", LEADER_484_17, ANTI_SD)
        self.assertEqual(snapshot(structures, energies), SNAPSHOTS["linker_484_17"]["linker3"])
        self.assertEqual(structures[0].energy, energies[0])
        self.assertEqual(SNAPSHOTS["linker_484_17"]["linker3"]["multibranch_anomalies"], 0)

    def test_traceback2_fixtures_unchanged_on_linker3(self):
        records = json.loads((REPOSITORY / "benchmarks/rbs/karlsen2018-development.json").read_text())["records"]
        expectations = {entry["id"]: entry for entry in SNAPSHOTS["traceback2_fixtures_on_linker3"]}
        for fixture in PREVIOUS["fixtures"]:
            with self.subTest(case=fixture["id"]):
                if "leader" in fixture:
                    sequence = fixture["leader"]
                else:
                    sequence = next(row["sequence"] for row in records if row["id"] == fixture["id"])
                    sequence = sequence[:fixture["leader_bases"]].upper().replace("T", "U")
                structures, energies = self.fold("linker3", sequence, fixture["anti_sd"],
                                                 temperature=fixture["temperature"])
                result = snapshot(structures, energies)
                self.assertEqual(result["structure_count"], fixture["structure_count"])
                self.assertEqual(result["structure_sha256"], fixture["structure_sha256"])
                self.assertEqual(result["evaluated_sha256"], fixture["evaluated_sha256"])
                self.assertEqual(result["energy_census"], fixture["energy_census"])
                self.assertEqual(result["native_evaluation_mismatches"], fixture["native_evaluation_mismatches"])
                self.assertEqual(result["multibranch_anomalies"], 0)
                self.assertEqual(expectations[fixture["id"]],
                                 {"id": fixture["id"], "status": "valid", "changed_from_traceback2": False,
                                  "evaluated_changed": False, "multibranch_anomalies": 0})

    def compare_panel(self, prefix, sequences, expected, engines):
        results = {engine: [self.try_fold(engine, sequence, ANTI_SD) for sequence in sequences]
                   for engine in engines}
        failed = {engine: [i for i, result in enumerate(outputs) if isinstance(result, str)]
                  for engine, outputs in results.items()}
        before, after = results["traceback2"], results["linker3"]
        both = [i for i in range(len(sequences)) if i not in failed["traceback2"] and i not in failed["linker3"]]
        changed = [i for i in both if identity(before[i][0]) != identity(after[i][0])]
        summary = {"count": len(sequences),
                   "valid": {("v2" if engine == "traceback2" else "v3" if engine == "linker3" else engine):
                             len(sequences) - len(indices) for engine, indices in failed.items()},
                   "v3_identical_to_v2": len(both) - len(changed),
                   "v3_changed_from_v2": len(changed),
                   "v3_eval_changed_from_v2": sum(identity(*before[i]) != identity(*after[i]) for i in both),
                   "v3_anomalies": sum(snapshot(*after[i])["multibranch_anomalies"]
                                       for i in range(len(sequences)) if i not in failed["linker3"]),
                   "v2_failed_indices": failed["traceback2"], "v3_failed_indices": failed["linker3"],
                   "changed_indices": changed}
        if "original" in engines:
            summary["original_failed_indices"] = failed["original"]
            summary["v3_identical_to_original"] = sum(
                identity(results["original"][i][0]) == identity(after[i][0])
                for i in range(len(sequences)) if i not in failed["original"] and i not in failed["linker3"])
        expectation = {key: expected[key] for key in summary}
        expectation["valid"] = {key: expected["valid"][key] for key in summary["valid"]}
        self.assertEqual(summary, expectation)
        self.assertEqual(summary["v3_failed_indices"], [])
        self.assertEqual(summary["v3_anomalies"], 0)
        for index in changed:
            with self.subTest(index=index):
                description = describe_change(before[index], after[index])
                self.assertEqual(description, expected["changed"][f"{prefix}/{index}"])
                self.assertTrue(description["mfe_same"])
                # Every structure that version 3 no longer emits was an ordinary
                # multibranch loop wrapped around the linker: connected, at least
                # three branches, and its native energy well above efn2's.
                for entry in description["only_traceback2"]:
                    self.assertEqual(entry["topology"][0], "connected")
                    self.assertGreaterEqual(entry["topology"][1], 3)
                    self.assertLessEqual(Decimal(entry["evaluated"]) - Decimal(entry["native"]), Decimal("-1.9"))
        return summary

    def test_panel_6603_traceback2_versus_linker3(self):
        summary = self.compare_panel("6603", panel_6603(), SNAPSHOTS["panel_6603"], ("traceback2", "linker3"))
        print(f"Synthetic 6603 panel: 60/60 linker-3 valid; {summary['v3_identical_to_v2']} identical to traceback-2; "
              f"{summary['v3_changed_from_v2']} valid outputs changed.")

    def test_panel_development_traceback2_versus_linker3(self):
        summary = self.compare_panel("dev", development_leaders(), SNAPSHOTS["panel_development"],
                                     ("traceback2", "linker3"))
        print(f"Development panel: 12/12 linker-3 valid; {summary['v3_changed_from_v2']} valid output changed.")

    def test_panel_fresh_26003_three_engines(self):
        expected = SNAPSHOTS["panel_fresh_26003"]
        sequences = panel_fresh()
        self.assertEqual([len(sequence) for sequence in sequences], expected["lengths"])
        summary = self.compare_panel("fresh", sequences, expected, ("original", "traceback2", "linker3"))
        print(f"Fresh 26003 panel: original {summary['valid']['original']}/40, traceback-2 {summary['valid']['v2']}/40, "
              f"linker-3 {summary['valid']['v3']}/40 valid; {summary['v3_changed_from_v2']} valid outputs changed.")

    def test_boundary_strands_identical_across_engines(self):
        for name, entry in SNAPSHOTS["boundary"].items():
            with self.subTest(case=name):
                outputs = {engine: snapshot(*self.fold(engine, entry["leader"], entry["anti_sd"]))
                           for engine in self.engines}
                self.assertEqual(outputs["linker3"], entry["linker3"])
                self.assertEqual(outputs["original"], outputs["linker3"])
                self.assertEqual(outputs["traceback2"], outputs["linker3"])
        tiny = SNAPSHOTS["boundary"]["tiny-duplex"]["linker3"]
        self.assertEqual((tiny["first_pairs"], tiny["first_energy"]), ([[1, 11], [2, 10], [3, 9], [4, 8]], "-6.4"))
        empty = SNAPSHOTS["boundary"]["no-pairs"]["linker3"]
        self.assertEqual((empty["structure_count"], empty["first_pairs"], empty["first_energy"]), (1, [], "0.0"))

    def test_ordinary_fold_identical_across_engines(self):
        for name, entry in SNAPSHOTS["fold"].items():
            sequence = resolve_sequence(name, entry["sequence"])
            for mode, arguments in (("mfe", ("--MFE",)), ("suboptimal", SUBOPTIMAL)):
                with self.subTest(case=name, mode=mode):
                    outputs = {engine: control_snapshot(*self.fold(
                        engine, sequence, temperature=entry["temperature"], fold_arguments=arguments))
                        for engine in self.engines}
                    self.assertEqual(outputs["linker3"], entry[mode])
                    self.assertEqual(outputs["original"], outputs["linker3"])
                    self.assertEqual(outputs["traceback2"], outputs["linker3"])
        hairpin = SNAPSHOTS["fold"]["hairpin"]["mfe"]
        self.assertEqual((hairpin["mfe_pairs"], hairpin["native"], hairpin["efn2"]), ([[1, 9], [2, 8], [3, 7]], "-1.2", "-1.2"))

    def test_fold_constraints_identical_across_engines(self):
        for name, entry in SNAPSHOTS["fold_constraint"].items():
            with self.subTest(case=name):
                sequence = resolve_sequence(name, entry["sequence"])
                outputs = {}
                for engine in self.engines:
                    structures, energies = self.fold(engine, sequence, temperature=entry["temperature"],
                                                     constraint=entry["constraint"])
                    outputs[engine] = control_snapshot(structures, energies)
                    pairs = structures[0].pairs
                    paired = {base for pair in pairs for base in pair}
                    self.assertNotIn(tuple(entry["forbidden_pair"]), pairs)
                    self.assertIn(entry["double_stranded"], paired)
                    self.assertNotIn(entry["single_stranded"], paired)
                self.assertEqual(outputs["linker3"], entry["result"])
                self.assertEqual(outputs["original"], outputs["linker3"])
                self.assertEqual(outputs["traceback2"], outputs["linker3"])

    def test_intramolecular_constraint_identical_across_engines(self):
        for name, entry in SNAPSHOTS["intramolecular"].items():
            with self.subTest(case=name):
                sequence = resolve_sequence(name, entry["sequence"])
                outputs = {}
                for engine in self.engines:
                    structures, energies = self.fold(engine, sequence, entry["anti_sd"],
                                                     bifold_arguments=("--intramolecular",))
                    outputs[engine] = control_snapshot(structures, energies)
                    for item in structures:
                        for i, j in item.pairs:
                            self.assertTrue(i <= len(sequence) < len(sequence) + 3 < j, (i, j))
                self.assertEqual(outputs["linker3"], entry["result"])
                self.assertEqual(outputs["original"], outputs["linker3"])
                self.assertEqual(outputs["traceback2"], outputs["linker3"])


if __name__ == "__main__":
    unittest.main()
