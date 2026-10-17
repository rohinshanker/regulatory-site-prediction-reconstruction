"""Independent topology, known-failure and thermodynamic fixture checks."""

import contextlib
import io
import json
import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import structural as s

ROOT = Path(__file__).resolve().parents[2] / "benchmarks/rbs"
ARCHIVE = ROOT / "structural-fixtures"


class TopologyTest(unittest.TestCase):
    def test_exhaustive_ground_states_and_hand_arithmetic(self):
        manifest = json.loads((ARCHIVE / "manifest.json").read_text())
        for case, name in zip(
            manifest["manual_checks"], ("hairpin", "duplex"), strict=True
        ):
            structures = s.enumerate_small(case["sequence"])
            self.assertEqual(len(structures), case["all_topologies"])
            self.assertEqual(len({x.partners for x in structures}), len(structures))
            raw = (ARCHIVE / "oracle" / f"{name}.ct").read_text()
            self.assertEqual(raw, s.to_ct(structures))
            self.assertEqual(s.read_ct(raw, case["sequence"]), structures)
            energies = s.read_energies(
                (ARCHIVE / "oracle" / f"{name}.energies").read_text(), len(structures)
            )
            self.assertEqual(min(energies), case["expected_energy"])
            terms = case["terms_kcal_mol"]
            total = sum(terms["GG_CC_stacks"]) + terms.get(
                "hairpin3", terms.get("association")
            )
            self.assertAlmostEqual(total, min(energies))
            self.assertEqual(
                sum(x <= min(energies) + 3 for x in energies),
                case["topologies_within_3"],
            )
            self.assertEqual(energies.count(min(energies)), 1)
        self.assertEqual(len(s.enumerate_small("AAAA")), 1)
        self.assertEqual(len(s.enumerate_small("GAC")), 1)
        with self.assertRaisesRegex(ValueError, "limited"):
            s.enumerate_small("A" * 13)

    def test_exhaustion_by_independent_combinatorics(self):
        # Each duplex topology selects k of four Gs and k of four Cs; the
        # noncrossing reverse matching is unique. Sum C(4,k)^2 = C(8,4) = 70.
        from math import comb

        collection = s.enumerate_small("GGGGIIICCCC")
        for k in range(5):
            self.assertEqual(
                sum(sum(bool(x) for x in a.partners) == 2 * k for a in collection),
                comb(4, k) ** 2,
            )

    def test_invalid_topologies(self):
        bad = [
            s.Structure("", ()),
            s.Structure("A", ()),
            s.Structure("N", (0,)),
            s.Structure("AIA", (0,) * 3),
            s.Structure("IIIA", (0,) * 4),
            s.Structure("AIII", (0,) * 4),
            s.Structure("AIAIIA", (0,) * 6),
            s.Structure("A", (True,)),
            s.Structure("A", (-1,)),
            s.Structure("A", (2,)),
            s.Structure("A", (1,)),
            s.Structure("GAAAC", (5, 0, 0, 0, 0)),
            s.Structure("AAAAA", (5, 0, 0, 0, 1)),
            s.Structure("GAC", (3, 0, 1)),
            s.Structure("GGAAAACC", (7, 8, 0, 0, 0, 0, 1, 2)),
        ]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                s.validate(item)

    def test_ct_mutations(self):
        valid = s.to_ct([s.Structure("AAAAA", (0,) * 5)])
        mutations = [
            "",
            "\n",
            valid.replace("5 independent", "4 independent"),
            "\n".join(valid.splitlines()[:-1]),
            valid.replace("independent topology", "ENERGY = NaN"),
            valid.replace("1 A 0 2 0 1", "1 A 0 2 0"),
            valid.replace("1 A 0 2 0 1", "1 A 1 2 0 1"),
            valid.replace("1 A 0 2 0 1", "1 A 0 2 0 -1"),
            valid.replace("1 A 0 2 0 1", "1 C 0 2 0 1"),
        ]
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(ValueError):
                s.read_ct(value, "AAAAA")

    def test_lowercase_constraints(self):
        raw = (ARCHIVE / "baseline/hairpin37/output.ct").read_text()
        with self.assertRaisesRegex(ValueError, "lowercase-constrained"):
            s.read_ct(raw, "gggAAACCC")

    def test_energy_records(self):
        self.assertEqual(
            s.read_energies("Structure: 1 Energy = 2\nStructure: 2 Energy = -3\n", 2),
            [2, -3],
        )
        for value in (
            "",
            "bad",
            "Structure: 2 Energy = 0",
            "Structure: 1 Energy = inf",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                s.read_energies(value, 1)


class ArchiveTest(unittest.TestCase):
    def test_all_pins_and_baseline_failures(self):
        archive = json.loads((ARCHIVE / "manifest.json").read_text())
        for name, digest in archive["files"].items():
            self.assertEqual(s.sha256(ARCHIVE / name), digest)
        panel = json.loads((ROOT / "structural-panel.json").read_text())
        observed = json.loads((ARCHIVE / "baseline/observations.json").read_text())
        self.assertEqual(
            s.sha256(ROOT / "structural-panel.json"), observed["manifest_sha256"]
        )
        self.assertEqual(len(observed["records"]), 14)
        cases = {x["id"]: x for x in panel["cases"]}
        failures = []
        for row in observed["records"]:
            folder = ARCHIVE / "baseline" / row["id"]
            for name, digest in row["files"].items():
                self.assertEqual(s.sha256(folder / name), digest)
            if row["status"] == "failed":
                failures.append(row["id"])
                if row["id"] == "missing-native":
                    self.assertEqual(row["exit_code"], 0)
                    self.assertFalse((folder / "output.ct").exists())
                    self.assertIn("traceback", (folder / "stderr.txt").read_text())
                else:
                    with self.assertRaisesRegex(ValueError, "nonreciprocal"):
                        s.read_ct(
                            (folder / "output.ct").read_text(),
                            "III".join(cases[row["id"]]["sequences"]).upper(),
                        )
            else:
                structures = s.read_ct(
                    (folder / "output.ct").read_text(),
                    "III".join(cases[row["id"]]["sequences"]).upper(),
                )
                self.assertEqual(
                    [list(x.partners) for x in structures],
                    [x["partners"] for x in row["structures"]],
                )
        self.assertEqual(
            failures,
            ["short-traceback-regression", "nonreciprocal-native", "missing-native"],
        )

    def test_heuristic_is_not_exhaustive_and_native_energy_is_distinct(self):
        seq = "GGGGIIICCCC"
        all_structures = s.read_ct((ARCHIVE / "oracle/duplex.ct").read_text(), seq)
        energies = s.read_energies((ARCHIVE / "oracle/duplex.energies").read_text(), 70)
        native = s.read_ct((ARCHIVE / "baseline/gc-duplex/output.ct").read_text(), seq)
        omitted = [
            e
            for x, e in zip(all_structures, energies, strict=True)
            if e <= -2.8 + 1e-9 and x.partners not in {y.partners for y in native}
        ]
        self.assertEqual(sorted(omitted), [-4.0, -3.5])
        native = s.read_ct(
            (ARCHIVE / "baseline/hairpin-allsub/output.ct").read_text(), "GGGAAACCC"
        )
        self.assertEqual(len(native), 9)
        self.assertEqual(len({x.partners for x in native}), 6)
        self.assertEqual(native[1].partners, native[2].partners)
        self.assertEqual((native[1].native_energy, native[2].native_energy), (-1, -0.2))


class CollectorTest(unittest.TestCase):
    def test_success_and_process_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend = root / "backend"
            (backend / "exe").mkdir(parents=True)
            (backend / "data_tables").mkdir()
            for exe in ("Fold", "bifold", "AllSub", "efn2"):
                (backend / "exe" / exe).write_text("not executed")
            table = backend / "data_tables/rna.test"
            table.write_text("table")
            (root / "tables.json").write_text(json.dumps({table.name: s.sha256(table)}))
            case = {
                "id": "one",
                "sequences": ["AAAAA"],
                "executable": "Fold",
                "options": ["--MFE"],
                "temperature_kelvin": 310.15,
            }
            manifest = root / "panel.json"
            manifest.write_text(
                json.dumps(
                    {
                        "table_manifest": "tables.json",
                        "table_manifest_sha256": s.sha256(root / "tables.json"),
                        "cases": [case],
                    }
                )
            )
            for failure in (
                None,
                "exit",
                "missing",
                "timeout",
                "timeout-text",
                "efn-timeout",
                "efn-exit",
                "efn-missing",
                "malformed",
            ):

                def run(command, *, cwd, failure=failure, **kwargs):
                    tool = Path(command[0]).name
                    if failure in ("timeout", "timeout-text"):
                        raise subprocess.TimeoutExpired(
                            command,
                            30,
                            output=b"partial stdout"
                            if failure == "timeout"
                            else "partial stdout",
                            stderr=b"traceback diagnostic"
                            if failure == "timeout"
                            else None,
                        )
                    if failure == "efn-timeout" and tool == "efn2":
                        raise subprocess.TimeoutExpired(
                            command,
                            30,
                            output=b"energy partial",
                            stderr=b"energy error",
                        )
                    if tool == "Fold":
                        if failure not in ("missing", "exit"):
                            (cwd / "output.ct").write_text(
                                ""
                                if failure == "malformed"
                                else s.to_ct([s.Structure("AAAAA", (0,) * 5)])
                            )
                        return subprocess.CompletedProcess(
                            command, 1 if failure == "exit" else 0, "output", ""
                        )
                    if failure != "efn-missing":
                        (cwd / "energies.txt").write_text("Structure: 1 Energy = 0\n")
                    return subprocess.CompletedProcess(
                        command, 1 if failure == "efn-exit" else 0, "", ""
                    )

                with (
                    self.subTest(failure=failure),
                    patch.object(s.subprocess, "run", side_effect=run),
                ):
                    report = s.collect(manifest, backend, root / str(failure))
                    self.assertEqual(
                        report["records"][0]["status"],
                        "ok" if failure is None else "failed",
                    )
            case["sequences"] = ["GGGAAACCC", "GGGAAACCC"]
            case["options"] = ["--intramolecular"]
            manifest.write_text(
                json.dumps(
                    {
                        "table_manifest": "tables.json",
                        "table_manifest_sha256": s.sha256(root / "tables.json"),
                        "cases": [case],
                    }
                )
            )
            for paired_strand in (None, 0, 1):
                partners = [0] * 21
                if paired_strand is not None:
                    offset = 12 * paired_strand
                    for left, right in [(1, 9), (2, 8), (3, 7)]:
                        partners[offset + left - 1], partners[offset + right - 1] = (
                            offset + right,
                            offset + left,
                        )
                raw_ct = s.to_ct(
                    [s.Structure("GGGAAACCCIIIGGGAAACCC", tuple(partners))]
                )

                def run_intra(command, *, cwd, raw_ct=raw_ct, **kwargs):
                    if Path(command[0]).name == "Fold":
                        (cwd / "output.ct").write_text(raw_ct)
                    else:
                        (cwd / "energies.txt").write_text("Structure: 1 Energy = 0\n")
                    return subprocess.CompletedProcess(command, 0, "", "")

                with patch.object(s.subprocess, "run", side_effect=run_intra):
                    report = s.collect(
                        manifest, backend, root / f"intramolecular-{paired_strand}"
                    )
                self.assertEqual(
                    report["records"][0]["status"],
                    "ok" if paired_strand is None else "failed",
                )
                if paired_strand is not None:
                    self.assertEqual(
                        report["records"][0]["failure"], "forbidden intramolecular pair"
                    )
            self.assertEqual(
                (root / "timeout/one/stdout.txt").read_bytes(), b"partial stdout"
            )
            self.assertEqual(
                (root / "timeout/one/stderr.txt").read_bytes(), b"traceback diagnostic"
            )
            self.assertEqual(
                (root / "timeout-text/one/stdout.txt").read_text(), "partial stdout"
            )
            self.assertEqual((root / "timeout-text/one/stderr.txt").read_text(), "")
            self.assertEqual(
                (root / "efn-timeout/one/efn2-stdout.txt").read_bytes(), b"energy partial"
            )
            self.assertEqual(
                (root / "efn-timeout/one/efn2-stderr.txt").read_bytes(), b"energy error"
            )
            with self.assertRaises(FileExistsError):
                s.collect(manifest, backend, root / "None")
            table.write_text("changed")
            with self.assertRaisesRegex(ValueError, "table changed"):
                s.collect(manifest, backend, root / "changed")
            (root / "tables.json").write_text("changed manifest")
            with self.assertRaisesRegex(ValueError, "manifest changed"):
                s.collect(manifest, backend, root / "changed-manifest")

    def test_cli(self):
        with (
            patch("sys.argv", ["structural", "panel", "backend", "output"]),
            patch.object(
                s,
                "collect",
                return_value={"records": [{"status": "ok"}, {"status": "failed"}]},
            ),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            s.main()
        self.assertEqual(json.loads(out.getvalue()), {"cases": 2, "failed": 1})
        with (
            patch("sys.argv", ["structural", "--help"]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            runpy.run_path(s.__file__, run_name="__main__")


if __name__ == "__main__":
    unittest.main()
