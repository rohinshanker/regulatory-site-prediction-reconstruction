"""Offline contract, parser, runner and receipt checks for constrained Fold.

Every executor here is a deterministic synthetic stand-in that exercises
plumbing and failure propagation. None of these tests is backend verification;
the separately executed real-backend evidence is canonical-receipt.json.
"""

import contextlib
import copy
import io
import json
import runpy
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.riboswitch import constrained_reference as c

REPO = Path(__file__).resolve().parents[2]
FIXTURES_PATH = REPO / "benchmarks/riboswitch/canonical-fixtures.json"
RECEIPT_PATH = REPO / "benchmarks/riboswitch/canonical-receipt.json"
AUDIT_PATH = REPO / "benchmarks/riboswitch/canonical-reaudit.json"
MODULE_PATH = REPO / "benchmarks/riboswitch/constrained_reference.py"
TABLES_PATH = REPO / "src/regsite/data/rnastructure-tables.json"
HAIRPIN = "GGGAGCGAAAGCUCCC"
HAIRPIN_PAIRS = ((1, 16), (2, 15), (3, 14), (4, 13), (5, 12), (6, 11))


def ct_text(sequence, pairs, energy="-1.0", name="synthetic"):
    """Synthetic CT text in RNAstructure's six-column layout."""
    partner = {i: j for i, j in pairs} | {j: i for i, j in pairs}
    header = f"{len(sequence):5d}  " + (
        f"ENERGY = {energy}  {name}" if energy is not None else name
    )
    n = len(sequence)
    rows = [
        f"{i:5d} {base} {i - 1:5d} {(i + 1) % (n + 1):5d} {partner.get(i, 0):5d} {i:5d}"
        for i, base in enumerate(sequence, 1)
    ]
    return "\n".join([header, *rows]) + "\n"


def request(sequence=HAIRPIN, mode="partial", **fields):
    return c.build_request({"id": "case", "sequence": sequence, "mode": mode, **fields})


def make_installation(base):
    """Synthetic installation tree with arbitrary bytes and its matching pins."""
    root = base / "RNAstructure"
    for relative, content in {
        "exe/Fold": "fold",
        "exe/efn2": "efn2",
        "src/algorithm.cpp": "source",
        "ReadMe.txt": "readme",
        "gpl.txt": "gpl",
        "data_tables/rna.stack.dg": "stack",
        "data_tables/rna.loop.dg": "loop",
        "data_tables/dna.stack.dg": "ignored",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    archive = base / "source.tgz"
    archive.write_text("archive")
    tables = {
        name: c._sha256(name.split(".")[1].encode())
        for name in ("rna.loop.dg", "rna.stack.dg")
    }
    pins = {
        "fold_sha256": c._sha256(b"fold"),
        "efn2_sha256": c._sha256(b"efn2"),
        "algorithm_cpp_sha256": c._sha256(b"source"),
        "readme_sha256": c._sha256(b"readme"),
        "gpl_sha256": c._sha256(b"gpl"),
        "source_archive_sha256": c._sha256(b"archive"),
        "table_manifest_sha256": c.table_manifest_sha256(tables),
    }
    return root, archive, pins


def fixtures_with(pins, executed, relations=(), rejected=()):
    return {
        "schema_version": c.SCHEMA_VERSION,
        "backend_pins": pins,
        "executed": list(executed),
        "relations": list(relations),
        "rejected": list(rejected),
    }


class FakeEngine:
    """In-process synthetic executor keyed by case directory name.

    ``structures`` maps case ids to returned pairs; ``behaviour`` selects a
    failure mode. Energies are -1 per pair so equal structures agree.
    """

    def __init__(self, structures, behaviour=None, clock=None, version="6.6"):
        self.structures = structures
        self.behaviour = behaviour or {}
        self.clock = clock
        self.version = version
        self.commands = []

    def __call__(self, command, cwd, env, timeout, stdout, stderr):
        self.commands.append((Path(command[0]).name, command[1:], env, timeout))
        program, args = Path(command[0]).name, command[1:]
        if args == ["--version"]:
            stdout.write(f"{program}: Version {self.version} (synthetic).\n".encode())
            return "exited", 1
        mode = self.behaviour.get((cwd.name, program))
        if self.clock is not None and mode == "expire":
            self.clock.now += 1000
        if mode == "exit":
            return "exited", 1
        if mode == "timeout":
            return "timed_out", None
        if mode == "silent":
            return "exited", 0
        if program == "Fold":
            return self.fold(cwd, mode)
        return self.efn2(cwd, mode)

    def fold(self, cwd, mode):
        sequence = (cwd / "input.fa").read_text().split()[1]
        pairs = self.structures[cwd.name]
        if mode == "garbage":
            (cwd / "output.ct").write_text("not a ct\n")
            return "exited", 0
        energy = None if mode == "no_energy" else f"{-1.0 * len(pairs)}"
        (cwd / "output.ct").write_text(ct_text(sequence, pairs, energy))
        return "exited", 0

    def efn2(self, cwd, mode):
        rows = (cwd / "output.ct").read_text().splitlines()[1:]
        count = sum(1 for row in rows if int(row.split()[4]) > int(row.split()[0]))
        energy = -1.0 * count + (0.5 if mode == "mismatch" else 0.0)
        text = (
            "garbage\n" if mode == "garbage" else f"Structure: 1   Energy = {energy}\n"
        )
        (cwd / "energy.txt").write_text(text)
        return "exited", 0


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class ContractTest(unittest.TestCase):
    def test_partial_full_and_unconstrained_requests(self):
        partial = request(forced_pairs=[[2, 15], [1, 16]], forced_unpaired=[8, 7])
        self.assertEqual(partial.pairs, ((1, 16), (2, 15)))
        self.assertEqual(partial.unpaired, (7, 8))
        full = request(mode="full", structure="((((((....))))))")
        self.assertEqual(full.pairs, HAIRPIN_PAIRS)
        self.assertEqual(full.unpaired, (7, 8, 9, 10))
        self.assertEqual(request(mode="unconstrained").pairs, ())
        self.assertEqual(request().unpaired, ())

    def test_every_refusal_code(self):
        cases = {
            "invalid_id": {"id": "Bad-id"},
            "invalid_sequence_length": {"sequence": ""},
            "unsupported_base": {"sequence": "ggg"},
            "invalid_mode": {"mode": None},
            "unexpected_field": {"mode": "full", "forced_pairs": []},
            "invalid_structure": {"mode": "full", "structure": 3},
            "unsupported_structure_symbol": {"mode": "full", "structure": "<>"},
            "structure_length_mismatch": {"mode": "full", "structure": "."},
            "unbalanced_structure": {"mode": "full", "structure": ")" + "." * 15},
            "invalid_pair_list": {"forced_pairs": {}},
            "invalid_pair": {"forced_pairs": [[1, 2, 3]]},
            "invalid_position_list": {"forced_unpaired": 3},
            "invalid_position": {"forced_pairs": [[1, 16.0]]},
            "position_out_of_range": {"forced_unpaired": [0]},
            "pair_not_5prime_first": {"forced_pairs": [[5, 5]]},
            "duplicate_pair": {"forced_pairs": [[1, 16], [1, 16]]},
            "position_in_multiple_pairs": {"forced_pairs": [[1, 16], [2, 16]]},
            "crossing_pairs": {"forced_pairs": [[1, 12], [6, 16]]},
            "duplicate_unpaired": {"forced_unpaired": [2, 2]},
            "paired_and_unpaired": {"forced_pairs": [[1, 16]], "forced_unpaired": [1]},
            "noncanonical_pair": {"forced_pairs": [[4, 10]]},
            "hairpin_too_short": {"forced_pairs": [[6, 7]]},
        }
        for code, fields in cases.items():
            case = {"id": "case", "sequence": HAIRPIN, "mode": "partial", **fields}
            with self.subTest(code), self.assertRaises(c.ContractError) as caught:
                c.build_request(case)
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(request(forced_pairs=[[2, 6]]).pairs, ((2, 6),))

    def test_exact_constraint_bytes_and_arguments(self):
        unconstrained = request(mode="unconstrained")
        self.assertIsNone(c.constraint_text(unconstrained))
        self.assertNotIn("--constraint", c.fold_args(unconstrained))
        self.assertEqual(
            c.constraint_text(request()),
            "DS:\n-1\nSS:\n-1\nMod:\n-1\nPairs:\n-1 -1\nFMN:\n-1\nForbids:\n-1 -1\n",
        )
        mixed = request(forced_pairs=[[1, 16]], forced_unpaired=[8, 9])
        self.assertEqual(
            c.constraint_text(mixed),
            "DS:\n-1\nSS:\n8\n9\n-1\nMod:\n-1\nPairs:\n1 16\n-1 -1\n"
            "FMN:\n-1\nForbids:\n-1 -1\n",
        )
        self.assertEqual(c.fold_args(mixed)[-2:], ("--constraint", "constraint.con"))
        self.assertEqual(c.fold_args(mixed)[:2], ("input.fa", "output.ct"))
        self.assertIn("310.15", c.fold_args(mixed))

    def test_dot_bracket_and_crossing(self):
        self.assertEqual(c.dot_bracket(HAIRPIN_PAIRS, 16), "((((((....))))))")
        self.assertTrue(c.has_crossing([(1, 10), (5, 15)]))
        self.assertFalse(c.has_crossing([(1, 10), (2, 9), (11, 15)]))

    def test_audit_lists_every_unmet_demand(self):
        partial = request(forced_pairs=[[1, 16]], forced_unpaired=[7])
        self.assertEqual(c.audit_constraints(partial, ((1, 16), (2, 15))), [])
        self.assertEqual(
            c.audit_constraints(partial, ((2, 15), (7, 12))),
            ["missing_pair:1-16", "paired_forced_unpaired:7"],
        )
        full = request(mode="full", structure="(((..........)))")
        self.assertEqual(
            c.audit_constraints(full, ((1, 16), (2, 15), (3, 14), (4, 13))),
            [
                "paired_forced_unpaired:4",
                "paired_forced_unpaired:13",
                "extra_pair:4-13",
            ],
        )


class ParserTest(unittest.TestCase):
    def test_valid_ct_with_and_without_energy(self):
        pairs, energy = c.parse_ct(ct_text(HAIRPIN, HAIRPIN_PAIRS, "-8.5"), HAIRPIN)
        self.assertEqual((pairs, energy), (HAIRPIN_PAIRS, -8.5))
        self.assertEqual(c.parse_ct(ct_text("AAAA", (), None), "AAAA"), ((), None))

    def test_invalid_ct_output(self):
        good = ct_text("GGGAAACCC", ((1, 9), (2, 8)))
        rows = good.splitlines()
        cases = {
            "empty_ct": "\n\n",
            "invalid_ct_header": "x\n",
            "ct_shape_mismatch": good + ct_text("GGGAAACCC", ()),
            "invalid_ct_energy": good.replace("-1.0", "nan"),
            "invalid_ct_row": "\n".join([rows[0], "1 G 0 2 9", *rows[2:]]),
            "ct_sequence_mismatch": good.replace(" G ", " A ", 1),
            "nonreciprocal_ct": "\n".join(
                [
                    *rows[:2],
                    "    2 G     1     3     8     2",
                    *rows[3:8],
                    "    8 C     7     9     0     8",
                    rows[9],
                ]
            ),
            "crossing_ct": ct_text("GGGGAAACCCC", ((1, 9), (4, 11))),
            "noncanonical_ct": ct_text("AAAAAAAAA", ((1, 9),)),
        }
        for code, text in cases.items():
            sequence = "GGGGAAACCCC" if code == "crossing_ct" else "GGGAAACCC"
            sequence = "AAAAAAAAA" if code == "noncanonical_ct" else sequence
            with self.subTest(code), self.assertRaises(c.OutputError) as caught:
                c.parse_ct(text, sequence)
            self.assertEqual(caught.exception.code, code)
        rows_with = {
            "invalid_ct_row": ("1 G 0 2 9 x", "1 G 0 x 9 1", "1 G x 2 9 1"),
            "invalid_ct_backbone": ("1 G 99 99 9 1", "1 G 0 3 9 1", "1 G 1 2 9 1"),
        }
        for code, replacements in rows_with.items():
            for row in replacements:
                text = "\n".join([rows[0], row, *rows[2:]])
                with self.subTest(row), self.assertRaises(c.OutputError) as caught:
                    c.parse_ct(text, "GGGAAACCC")
                self.assertEqual(caught.exception.code, code)
        for index, row in (
            (5, "    5 A     4     7     0     5"),
            (9, "    9 C     8    10     1     9"),
        ):
            text = "\n".join([*rows[:index], row, *rows[index + 1 :]])
            with self.subTest(row), self.assertRaises(c.OutputError) as caught:
                c.parse_ct(text, "GGGAAACCC")
            self.assertEqual(caught.exception.code, "invalid_ct_backbone")
        # Natural numbering is ignored by RNAstructure; only its integer form counts.
        renumbered = "\n".join([rows[0], "1 G 0 2 9 500", *rows[2:]])
        self.assertEqual(c.parse_ct(renumbered, "GGGAAACCC")[0], ((1, 9), (2, 8)))
        for row in ("1 G 0 2 x 1", "2 G 0 2 9 1", "1 G 0 2 99 1", "1 G 0 2 1 1"):
            text = "\n".join([rows[0], row, *rows[2:]])
            with self.subTest(row), self.assertRaises(c.OutputError) as caught:
                c.parse_ct(text, "GGGAAACCC")
            self.assertEqual(caught.exception.code, "invalid_ct_row")
        with self.assertRaises(c.OutputError) as caught:
            c.parse_ct(good.replace("-1.0", "low"), "GGGAAACCC")
        self.assertEqual(caught.exception.code, "invalid_ct_energy")

    def test_efn2_simple_list(self):
        self.assertEqual(c.parse_efn2("Structure: 1   Energy = -8.5\n"), -8.5)
        for text, code in (
            ("", "invalid_efn2_output"),
            (
                "Structure: 1 Energy = 1\nStructure: 2 Energy = 2\n",
                "invalid_efn2_output",
            ),
            ("Structure: 2   Energy = 1\n", "invalid_efn2_output"),
            ("Structure: 1   Energy = inf\n", "invalid_efn2_energy"),
        ):
            with self.subTest(text), self.assertRaises(c.OutputError) as caught:
                c.parse_efn2(text)
            self.assertEqual(caught.exception.code, code)

    def test_bounded_text_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.txt"
            self.assertIsNone(c._read_text(path))
            self.assertIsNone(c._file_sha256(path))
            path.write_bytes(b"\xff")
            with self.assertRaises(c.OutputError) as caught:
                c._read_text(path)
            self.assertEqual(caught.exception.code, "output_not_utf8")
            path.write_text("abc")
            with (
                patch.object(c, "MAX_TEXT_BYTES", 2),
                self.assertRaises(c.OutputError) as caught,
            ):
                c._read_text(path)
            self.assertEqual(caught.exception.code, "output_too_large")
            self.assertEqual(c._read_text(path), "abc")


class ExecutionTest(unittest.TestCase):
    def test_budget_counts_jobs_and_deadline(self):
        clock = Clock()
        budget = c.Budget(c.Limits(max_jobs=2, job_seconds=5, total_seconds=7), clock)
        self.assertEqual(budget.claim(), 5)
        clock.now = 4
        self.assertEqual(budget.claim(), 3)
        self.assertIsNone(budget.claim())
        late = c.Budget(c.Limits(total_seconds=1), clock)
        clock.now = 10
        self.assertIsNone(late.claim())

    def test_real_subprocess_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            script = base / "tool"
            script.write_text(
                f"#!{sys.executable}\nimport sys, time\n"
                "print('out'); print('err', file=sys.stderr)\n"
                "time.sleep(float(sys.argv[1])); sys.exit(int(sys.argv[2]))\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            with (base / "o").open("wb") as out, (base / "e").open("wb") as err:
                result = c.execute([str(script), "0", "3"], base, {}, 30, out, err)
            self.assertEqual(result, ("exited", 3))
            self.assertEqual((base / "o").read_text(), "out\n")
            self.assertEqual((base / "e").read_text(), "err\n")
            with (base / "o2").open("wb") as out, (base / "e2").open("wb") as err:
                result = c.execute([str(script), "5", "0"], base, {}, 0.3, out, err)
            self.assertEqual(result, ("timed_out", None))
            with (base / "o3").open("wb") as out, (base / "e3").open("wb") as err:
                result = c.execute([str(base / "missing")], base, {}, 5, out, err)
            self.assertEqual(result, ("launch_failed", None))

    def test_backend_identity_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root, archive, pins = make_installation(Path(directory))
            identity = c.backend_identity(root, archive, pins)
            self.assertEqual(identity["table_count"], 2)
            self.assertEqual(identity["licence"], "GPL-2.0-only")
            self.assertEqual(identity["fold_sha256"], pins["fold_sha256"])
            (root / "gpl.txt").unlink()
            (root / "exe/efn2").write_text("other")
            with self.assertRaisesRegex(c.SetupError, "efn2_sha256, gpl_sha256"):
                c.backend_identity(root, archive, pins)


class FixtureValidationTest(unittest.TestCase):
    def setUp(self):
        self.base = json.loads(FIXTURES_PATH.read_text())

    def test_canonical_fixtures_are_bounded_and_rejections_exact(self):
        requests = c.validate_fixtures(self.base, c.Limits())
        self.assertEqual(len(requests), 9)
        self.assertLessEqual(2 + 2 * len(requests), 30)
        self.assertEqual(
            {request.mode for request in requests}, {"unconstrained", "partial", "full"}
        )
        for case in self.base["rejected"]:
            with self.subTest(case["id"]):
                self.assertTrue(c.assess_rejected(case)["expectation_met"])
        accepted = c.assess_rejected(
            {**self.base["executed"][0], "expected_error": "x"}
        )
        self.assertEqual(
            (accepted["error"], accepted["expectation_met"]), (None, False)
        )

    def test_fixture_refusals(self):
        def broken(change):
            fixtures = copy.deepcopy(self.base)
            change(fixtures)
            return fixtures

        cases = [
            lambda f: f.update(schema_version="other"),
            lambda f: f["backend_pins"].pop("gpl_sha256"),
            lambda f: f["backend_pins"].update(gpl_sha256="ABC"),
            lambda f: f.update(rejected={}),
            lambda f: f.update(executed=[]),
            lambda f: f.update(executed=f["executed"] * 2),
            lambda f: f["executed"].__setitem__(0, "case"),
            lambda f: f["executed"][0].update(sequence="T"),
            lambda f: f["executed"][0].update(expected_pairs=[[1, 1]]),
            lambda f: f["executed"][0].update(expected_status="maybe"),
            lambda f: f["rejected"].append({"id": 1, "expected_error": "x"}),
            lambda f: f["rejected"].append("case"),
            lambda f: f["rejected"].append(
                {"id": "hairpin_noop", "expected_error": "x"}
            ),
            lambda f: f["relations"].append("relation"),
            lambda f: f["relations"].append({"kind": "other", "cases": ["a", "b"]}),
            lambda f: f["relations"].append(
                {"kind": "different_pairs", "cases": ["hairpin_noop"]}
            ),
            lambda f: f["relations"].append(
                {"kind": "different_pairs", "cases": ["hairpin_noop", "crossing"]}
            ),
        ]
        for index, change in enumerate(cases):
            with self.subTest(index), self.assertRaises(c.SetupError):
                c.validate_fixtures(broken(change), c.Limits())
        with self.assertRaises(c.SetupError):
            c.validate_fixtures([], c.Limits())


class RunTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root, self.archive, self.pins = make_installation(self.base)

    def tearDown(self):
        self.temp.cleanup()

    def write_fixtures(self, fixtures, name="fixtures.json"):
        path = self.base / name
        path.write_text(json.dumps(fixtures))
        return path

    def standard(self):
        executed = [
            {
                "id": "open",
                "sequence": "AAAAAAAA",
                "mode": "unconstrained",
                "expected_status": "ok",
                "expected_pairs": [],
            },
            {
                "id": "hairpin",
                "sequence": HAIRPIN,
                "mode": "unconstrained",
                "expected_status": "ok",
            },
            {
                "id": "noop",
                "sequence": HAIRPIN,
                "mode": "partial",
                "expected_status": "ok",
            },
            {
                "id": "full",
                "sequence": HAIRPIN,
                "mode": "full",
                "structure": "((((((....))))))",
                "expected_status": "ok",
            },
            {
                "id": "forced",
                "sequence": HAIRPIN,
                "mode": "partial",
                "forced_pairs": [[1, 16]],
                "expected_status": "not_ok",
            },
        ]
        relations = [
            {"kind": "same_structure_and_energy", "cases": ["hairpin", "noop"]},
            {"kind": "same_structure_and_energy", "cases": ["hairpin", "full"]},
            {"kind": "different_pairs", "cases": ["open", "hairpin"]},
            {"kind": "energy_not_below", "cases": ["open", "hairpin"]},
        ]
        rejected = [
            {
                "id": "bad",
                "sequence": "N",
                "mode": "unconstrained",
                "expected_error": "unsupported_base",
            }
        ]
        structures = {
            "open": (),
            "hairpin": HAIRPIN_PAIRS,
            "noop": HAIRPIN_PAIRS,
            "full": HAIRPIN_PAIRS,
            "forced": ((2, 15), (3, 14)),
        }
        return fixtures_with(self.pins, executed, relations, rejected), structures

    def test_successful_run_receipt_and_reaudit(self):
        fixtures, structures = self.standard()
        path = self.write_fixtures(fixtures)
        engine = FakeEngine(structures)
        output = self.base / "run"
        receipt = c.run(path, self.root, self.archive, output, engine)
        self.assertTrue(receipt["all_expectations_met"])
        self.assertEqual(receipt["total_jobs"], 12)
        self.assertEqual(receipt["limits"]["retries"], 0)
        self.assertEqual(
            receipt["backend"]["versions"]["Fold"], "Fold: Version 6.6 (synthetic)."
        )
        self.assertIn("FakeEngine", receipt["executor"])
        cases = {case["id"]: case for case in receipt["cases"]}
        self.assertEqual(cases["forced"]["status"], c.CONSTRAINT_VIOLATED)
        self.assertEqual(cases["forced"]["violations"], ["missing_pair:1-16"])
        self.assertEqual(cases["hairpin"]["dot_bracket"], "((((((....))))))")
        self.assertEqual(cases["hairpin"]["energy_consistency"], "match")
        self.assertIsNone(cases["hairpin"]["constraint_text"])
        self.assertEqual(
            cases["noop"]["constraint_sha256"],
            c._sha256(c.constraint_text(request()).encode()),
        )
        self.assertTrue(all(item["holds"] for item in receipt["relations"]))
        self.assertTrue(receipt["rejected"][0]["expectation_met"])
        for _, _, env, timeout in engine.commands:
            self.assertEqual(set(env), {"DATAPATH", "OMP_NUM_THREADS", "LC_ALL"})
            self.assertLessEqual(timeout, 120)
        self.assertEqual(json.loads((output / "receipt.json").read_text()), receipt)
        report = c.reaudit(path, output)
        self.assertEqual((report["reproduced"], report["problems"]), (True, []))
        self.assertEqual(report["backend_calls"], 0)
        self.assertEqual(report["auditor_sha256"], c._sha256(MODULE_PATH.read_bytes()))
        self.assertEqual(report["execution_runner_sha256"], receipt["runner_sha256"])
        self.assertEqual(
            report["execution_receipt_sha256"],
            c._sha256((output / "receipt.json").read_bytes()),
        )
        self.assertNotIn("receipt.json", report["saved_files"])
        self.assertEqual(
            report["saved_files"]["cases/noop/constraint.con"],
            cases["noop"]["constraint_sha256"],
        )
        self.assertNotIn("cases/hairpin/constraint.con", report["saved_files"])
        with self.assertRaises(c.SetupError):
            c.run(path, self.root, self.archive, output, engine)

    def test_reaudit_detects_tampering(self):
        fixtures, structures = self.standard()
        path = self.write_fixtures(fixtures)
        pristine = self.base / "run"
        c.run(path, self.root, self.archive, pristine, FakeEngine(structures))
        original = json.loads((pristine / "receipt.json").read_text())

        def problems(change):
            copy_dir = self.base / "mutated"
            shutil.rmtree(copy_dir, ignore_errors=True)
            shutil.copytree(pristine, copy_dir)
            receipt = copy.deepcopy(original)
            change(copy_dir, receipt)
            (copy_dir / "receipt.json").write_text(json.dumps(receipt))
            return c.reaudit(path, copy_dir)["problems"]

        def edit(relative, text):
            return lambda d, r: (d / relative).write_text(text)

        def job(position, **fields):
            return lambda d, r: r["jobs"][position].update(fields)

        hairpin_ct = (pristine / "cases/hairpin/output.ct").read_text()
        expected = [
            (lambda d, r: None, []),
            (edit("cases/open/fold.stdout", "changed"), ["job_2_stdout"]),
            (
                edit("cases/hairpin/output.ct", hairpin_ct.replace("-6.0", "-7.0")),
                ["cases"],
            ),
            (
                edit("cases/noop/constraint.con", "corrupted\n"),
                ["case_noop_constraint.con", "cases"],
            ),
            (
                lambda d, r: (d / "cases/noop/constraint.con").unlink(),
                ["case_noop_constraint.con", "cases"],
            ),
            (
                edit("cases/hairpin/constraint.con", "DS:\n-1\n"),
                ["case_hairpin_constraint.con"],
            ),
            (
                edit("cases/open/input.fa", ">open\nAAAAAAAU\n"),
                ["case_open_input.fa", "cases"],
            ),
            (
                lambda d, r: r["settings"].update(temperature_k="300"),
                ["settings"],
            ),
            (lambda d, r: r["limits"].update(job_seconds=500), ["limits"]),
            (lambda d, r: r.update(total_jobs=5), ["total_jobs"]),
            (lambda d, r: r.update(schema_version="x"), ["schema_version"]),
            (
                lambda d, r: r["backend"]["versions"].update(Fold="Fold 6.5"),
                ["backend"],
            ),
            (lambda d, r: r["backend"].update(fold_sha256="0"), ["backend"]),
            (job(2, args=["changed"]), ["job_2_record"]),
            (job(2, timeout_seconds=500), ["job_2_record"]),
            (job(2, exit_code=None), ["job_2_record"]),
            (job(2, outcome="crashed"), ["job_2_record"]),
            (job(2, index=7), ["job_2_record"]),
            (job(2, seconds=10_000), ["total_jobs"]),
            (job(2, seconds=-1), ["job_2_record"]),
            (job(2, seconds=float("nan")), ["job_2_record"]),
            (job(2, seconds=float("inf")), ["job_2_record"]),
            (job(2, seconds=True), ["job_2_record"]),
            (job(2, seconds="0.1"), ["job_2_record"]),
            (job(2, timeout_seconds=float("nan")), ["job_2_record"]),
            (job(2, timeout_seconds=0), ["job_2_record"]),
            (job(2, timeout_seconds=True), ["job_2_record"]),
            (job(2, timeout_seconds="60"), ["job_2_record"]),
            (job(2, exit_code=True), ["job_2_record"]),
            (job(2, exit_code=0.0), ["job_2_record"]),
            (job(2, outcome="timed_out"), ["job_2_record"]),
            (
                lambda d, r: r["cases"][0].update(fold_job=3, efn2_job=2),
                ["job_accounting"],
            ),
            (
                lambda d, r: r.update(jobs=r["jobs"][:-1], total_jobs=11),
                ["job_accounting", "cases"],
            ),
        ]
        for index, (change, wanted) in enumerate(expected):
            with self.subTest(index):
                found = problems(change)
                # Each mutation must name its own check; derived sections may cascade.
                self.assertEqual(found[: len(wanted)] if wanted else found, wanted)
        self.assertEqual(problems(lambda d, r: r.pop("jobs")), ["malformed_receipt"])
        mutated = self.base / "mutated"
        (mutated / "receipt.json").write_text("[]")
        report = c.reaudit(path, mutated)
        self.assertEqual(report["problems"], ["malformed_receipt"])
        self.assertIsNone(report["execution_runner_sha256"])
        other = self.write_fixtures({**fixtures, "scope": "changed"}, "other.json")
        self.assertIn("fixtures_sha256", c.reaudit(other, pristine)["problems"])

    def test_inputs_are_verified_before_launch(self):
        fixtures, structures = self.standard()
        path = self.write_fixtures(fixtures)
        engine = FakeEngine(structures)

        def corrupt(request, directory):
            (directory / "input.fa").write_text(">x\nA\n")

        with (
            patch.object(c, "_write_inputs", corrupt),
            self.assertRaisesRegex(c.SetupError, "case_open_input.fa"),
        ):
            c.run(path, self.root, self.archive, self.base / "run", engine)
        self.assertEqual([cmd[1] for cmd in engine.commands], [["--version"]] * 2)
        unconstrained = request(mode="unconstrained")
        directory = self.base / "inputs"
        directory.mkdir()
        c._write_inputs(unconstrained, directory)
        self.assertEqual(c.input_problems(unconstrained, directory), [])
        self.assertFalse((directory / "constraint.con").exists())

    def test_failure_modes_propagate_without_retry(self):
        executed = [
            {
                "id": name,
                "sequence": HAIRPIN,
                "mode": "partial",
                "forced_pairs": [[1, 16]],
                "expected_status": "not_ok",
            }
            for name in ("exit", "timeout", "silent", "garbage")
        ] + [
            {
                "id": name,
                "sequence": HAIRPIN,
                "mode": "unconstrained",
                "expected_status": "ok",
            }
            for name in (
                "efn2_exit",
                "efn2_silent",
                "efn2_garbage",
                "mismatch",
                "no_energy",
            )
        ]
        behaviour = {
            ("exit", "Fold"): "exit",
            ("timeout", "Fold"): "timeout",
            ("silent", "Fold"): "silent",
            ("garbage", "Fold"): "garbage",
            ("efn2_exit", "efn2"): "exit",
            ("efn2_silent", "efn2"): "silent",
            ("efn2_garbage", "efn2"): "garbage",
            ("mismatch", "efn2"): "mismatch",
            ("no_energy", "Fold"): "no_energy",
        }
        structures = {case["id"]: HAIRPIN_PAIRS for case in executed}
        path = self.write_fixtures(fixtures_with(self.pins, executed))
        engine = FakeEngine(structures, behaviour)
        receipt = c.run(path, self.root, self.archive, self.base / "run", engine)
        cases = {case["id"]: case for case in receipt["cases"]}
        expected = {
            "exit": (c.BACKEND_FAILED, "fold_exit_1", None, True),
            "timeout": (c.BACKEND_FAILED, "fold_timed_out", None, True),
            "silent": (c.BACKEND_FAILED, "missing_ct", None, True),
            "garbage": (c.BACKEND_FAILED, "invalid_ct_header", None, True),
            "efn2_exit": (c.EVALUATION_FAILED, None, "efn2_exit_1", False),
            "efn2_silent": (c.EVALUATION_FAILED, None, "missing_energy", False),
            "efn2_garbage": (c.EVALUATION_FAILED, None, "invalid_efn2_output", False),
            "mismatch": (c.OK, None, None, False),
            "no_energy": (c.OK, None, None, True),
        }
        for name, (status, failure, efn2_failure, met) in expected.items():
            with self.subTest(name):
                case = cases[name]
                self.assertEqual(
                    (
                        case["status"],
                        case["failure"],
                        case["efn2_failure"],
                        case["expectation_met"],
                    ),
                    (status, failure, efn2_failure, met),
                )
        self.assertEqual(cases["mismatch"]["energy_consistency"], "mismatch")
        self.assertEqual(cases["no_energy"]["energy_consistency"], "fold_energy_absent")
        self.assertIsNone(cases["exit"]["efn2_job"])
        self.assertEqual(receipt["total_jobs"], 2 + 4 + 2 * 5)
        self.assertFalse(receipt["all_expectations_met"])

    def test_budget_exhaustion_marks_not_run(self):
        executed = [
            {
                "id": "first",
                "sequence": HAIRPIN,
                "mode": "unconstrained",
                "expected_status": "ok",
            },
            {
                "id": "second",
                "sequence": HAIRPIN,
                "mode": "unconstrained",
                "expected_status": "not_ok",
            },
        ]
        relations = [{"kind": "different_pairs", "cases": ["first", "second"]}]
        structures = {"first": HAIRPIN_PAIRS, "second": HAIRPIN_PAIRS}
        path = self.write_fixtures(fixtures_with(self.pins, executed, relations))
        clock = Clock()
        engine = FakeEngine(structures, {("first", "Fold"): "expire"}, clock)
        receipt = c.run(
            path, self.root, self.archive, self.base / "run", engine, clock=clock
        )
        first, second = receipt["cases"]
        self.assertEqual(
            (first["status"], first["efn2_failure"]), (c.NOT_RUN, "budget_exhausted")
        )
        self.assertEqual(
            (second["status"], second["failure"]), (c.NOT_RUN, "budget_exhausted")
        )
        self.assertFalse(second["expectation_met"])
        self.assertEqual(receipt["relations"][0]["evaluable"], False)
        self.assertEqual(c.reaudit(path, self.base / "run")["problems"], [])

    def test_setup_refusals(self):
        fixtures, structures = self.standard()
        path = self.write_fixtures(fixtures)
        with self.assertRaisesRegex(c.SetupError, "must be new"):
            c.run(path, self.root, self.archive, self.base / "a/b", FakeEngine({}))
        with self.assertRaisesRegex(c.SetupError, "not RNAstructure 6.6"):
            c.run(
                path,
                self.root,
                self.archive,
                self.base / "v",
                FakeEngine(structures, version="6.5"),
            )
        with self.assertRaisesRegex(c.SetupError, "before version checks"):
            c.run(
                path,
                self.root,
                self.archive,
                self.base / "t",
                FakeEngine({}),
                c.Limits(total_seconds=0),
            )


class CommandLineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root, self.archive, pins = make_installation(self.base)
        for program, body in (
            ("Fold", "open(a[1], 'w').write(ct)"),
            ("efn2", "open(a[1], 'w').write('Structure: 1   Energy = 0\\n')"),
        ):
            script = self.root / "exe" / program
            script.write_text(
                f"#!{sys.executable}\nimport sys\na = sys.argv[1:]\n"
                "ct = '    4  ENERGY = 0  x\\n' + ''.join("
                "f'{i} A {i-1} {(i+1) % 5} 0 {i}\\n' for i in range(1, 5))\n"
                f"if a == ['--version']:\n    print('{program}: Version 6.6 (x).')\n"
                f"    sys.exit(1)\n{body}\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
        pins["fold_sha256"] = c._file_sha256(self.root / "exe/Fold")
        pins["efn2_sha256"] = c._file_sha256(self.root / "exe/efn2")
        case = {
            "id": "open",
            "sequence": "AAAA",
            "mode": "unconstrained",
            "expected_status": "ok",
            "expected_pairs": [],
        }
        self.fixtures = self.base / "fixtures.json"
        self.fixtures.write_text(json.dumps(fixtures_with(pins, [case])))
        unmet = dict(case, expected_pairs=[[1, 4]])
        self.unmet = self.base / "unmet.json"
        self.unmet.write_text(json.dumps(fixtures_with(pins, [unmet])))

    def tearDown(self):
        self.temp.cleanup()

    def main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = c.main([str(arg) for arg in args])
        return code, out.getvalue(), err.getvalue()

    def run_args(self, fixtures, output):
        return (
            "run",
            "--rnastructure",
            self.root,
            "--source-archive",
            self.archive,
            "--output",
            output,
            "--fixtures",
            fixtures,
        )

    def test_run_and_reaudit_through_real_subprocesses(self):
        output = self.base / "run"
        code, out, _ = self.main(*self.run_args(self.fixtures, output))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["statuses"], {"open": "ok"})
        receipt = json.loads((output / "receipt.json").read_text())
        self.assertTrue(receipt["executor"].endswith("constrained_reference.execute"))
        self.assertEqual(receipt["jobs"][0]["exit_code"], 1)
        audit = self.base / "audit.json"
        args = ("reaudit", "--output", output, "--fixtures", self.fixtures)
        code, out, _ = self.main(*args, "--audit-receipt", audit)
        self.assertEqual((code, json.loads(out)["reproduced"]), (0, True))
        self.assertEqual(json.loads(audit.read_text())["problems"], [])
        code, _, err = self.main(*args, "--audit-receipt", audit)
        self.assertEqual(code, 2)
        self.assertEqual(self.main(*args)[0], 0)
        code, _, _ = self.main("reaudit", "--output", output, "--fixtures", self.unmet)
        self.assertEqual(code, 1)
        code, _, err = self.main(*self.run_args(self.fixtures, output))
        self.assertEqual(code, 2)
        self.assertIn("must be new", err)

    def test_unmet_expectation_and_missing_receipt(self):
        code, _, _ = self.main(*self.run_args(self.unmet, self.base / "unmet"))
        self.assertEqual(code, 1)
        code, _, err = self.main("reaudit", "--output", self.base / "none")
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_module_entry_point(self):
        argv = [
            "constrained_reference",
            *map(str, self.run_args(self.fixtures, self.base / "module")),
        ]
        module = "benchmarks.riboswitch.constrained_reference"
        with (
            patch.object(sys, "argv", argv),
            patch.dict(sys.modules),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as caught,
        ):
            sys.modules.pop(module)
            runpy.run_module(module, run_name="__main__")
        self.assertEqual(caught.exception.code, 0)


class CommittedReceiptTest(unittest.TestCase):
    """Consistency of the separately executed real-backend receipt."""

    def setUp(self):
        self.fixtures = json.loads(FIXTURES_PATH.read_text())
        self.receipt = json.loads(RECEIPT_PATH.read_text())

    def test_receipt_identity_matches_pins(self):
        receipt = self.receipt
        self.assertEqual(receipt["schema_version"], c.RECEIPT_VERSION)
        self.assertEqual(
            receipt["fixtures_sha256"], c._sha256(FIXTURES_PATH.read_bytes())
        )
        # The CLI runs as ``-m``, so the real subprocess executor reports __main__.
        self.assertIn(
            receipt["executor"],
            {"__main__.execute", "benchmarks.riboswitch.constrained_reference.execute"},
        )
        for key, value in self.fixtures["backend_pins"].items():
            self.assertEqual(receipt["backend"][key], value)
        tables = receipt["backend"]["tables"]
        self.assertEqual(tables, json.loads(TABLES_PATH.read_text()))
        self.assertEqual(
            c.table_manifest_sha256(tables),
            self.fixtures["backend_pins"]["table_manifest_sha256"],
        )
        self.assertLessEqual(receipt["total_jobs"], 30)
        self.assertLessEqual(sum(job["seconds"] for job in receipt["jobs"]), 900)
        self.assertTrue(all(job["timeout_seconds"] <= 120 for job in receipt["jobs"]))
        self.assertEqual(receipt["settings"]["fold_flags"], list(c.FOLD_FLAGS))
        self.assertEqual(receipt["settings"]["efn2_flags"], list(c.EFN2_FLAGS))

    def test_receipt_conclusions_recompute(self):
        requests = c.validate_fixtures(self.fixtures, c.Limits())
        cases = self.receipt["cases"]
        for request, case in zip(requests, cases, strict=True):
            self.assertEqual(case["id"], request.case_id)
            self.assertEqual(case["constraint_text"], c.constraint_text(request))
            job = self.receipt["jobs"][case["fold_job"]]
            self.assertEqual(job["args"], list(c.fold_args(request)))
            if case["pairs"] is not None:
                pairs = tuple(map(tuple, case["pairs"]))
                self.assertEqual(
                    case["violations"], c.audit_constraints(request, pairs)
                )
        derived = c._conclusions(self.fixtures, cases)
        for key in ("rejected", "relations", "all_expectations_met"):
            self.assertEqual(self.receipt[key], derived[key])


class CommittedAuditTest(unittest.TestCase):
    """The offline audit receipt binds the frozen run to the current auditor."""

    def test_audit_binds_execution_and_saved_files(self):
        audit = json.loads(AUDIT_PATH.read_text())
        receipt = json.loads(RECEIPT_PATH.read_text())
        fixtures = json.loads(FIXTURES_PATH.read_text())
        self.assertEqual(audit["schema_version"], c.AUDIT_VERSION)
        self.assertEqual((audit["reproduced"], audit["problems"]), (True, []))
        self.assertEqual(audit["backend_calls"], 0)
        self.assertEqual(
            audit["execution_receipt_sha256"], c._sha256(RECEIPT_PATH.read_bytes())
        )
        self.assertEqual(audit["execution_runner_sha256"], receipt["runner_sha256"])
        self.assertNotEqual(audit["auditor_sha256"], receipt["runner_sha256"])
        self.assertEqual(audit["auditor_sha256"], c._sha256(MODULE_PATH.read_bytes()))
        self.assertEqual(audit["fixtures_sha256"], receipt["fixtures_sha256"])
        self.assertEqual(audit["checked"], list(c.CHECKED))
        self.assertEqual(audit["not_validated"], list(c.NOT_VALIDATED))
        saved = audit["saved_files"]
        requests = c.validate_fixtures(fixtures, c.Limits())
        for request, case in zip(requests, receipt["cases"], strict=True):
            for name, raw in c.expected_inputs(request).items():
                key = f"cases/{request.case_id}/{name}"
                self.assertEqual(
                    saved.get(key), None if raw is None else c._sha256(raw)
                )
            self.assertEqual(
                saved.get(f"cases/{case['id']}/output.ct"), case["ct_sha256"]
            )
            self.assertEqual(
                saved.get(f"cases/{case['id']}/energy.txt"), case["energy_sha256"]
            )
        for job in receipt["jobs"]:
            folder = "identity" if job["case"] is None else f"cases/{job['case']}"
            for stream in ("stdout", "stderr"):
                key = f"{folder}/{job['program'].lower()}.{stream}"
                self.assertEqual(saved[key], job[f"{stream}_sha256"])


if __name__ == "__main__":
    unittest.main()
