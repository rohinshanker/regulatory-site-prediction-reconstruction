"""Artificial native-development requests, identities and rank endpoints."""

import copy
import io
import json
import runpy
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import native_development_recheck as n


class NativeDevelopmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.protocol = json.loads(n.PROTOCOL.read_bytes())
        p = self.protocol
        rows = []
        for i in range(4):
            sequence = "ACGT" * 25 + "ATG" + "A" * 97
            rows.append(
                {
                    "id": f"synthetic-{i}",
                    "group": f"group-{i // 2}",
                    "sequence": sequence,
                    "sequence_sha256": n.digest(sequence),
                    "start": 100,
                    "host": p["cohort"]["host"],
                    "temperature_celsius": 30,
                    "anti_sd": "ACCUCCUUU",
                    "condition": p["cohort"]["condition"],
                    "quantity": p["cohort"]["source_quantity"],
                    "partition": "development_validation",
                    "observed": i + 1,
                    "source_row": 99 - i,
                }
            )
        self.development = {
            "schema_version": "native-rbs-development-1",
            "input_envelope_sha256": "synthetic-source",
            "records": rows,
        }
        self.split = {
            "schema_version": "native-rbs-splits-1",
            "input_envelope_sha256": "synthetic-source",
            "records": [
                {
                    **{
                        k: r[k] for k in ("id", "group", "sequence_sha256", "partition")
                    },
                    "primary_eligible": True,
                }
                for r in rows
            ],
        }
        p["cohort"].update(
            records=4,
            homology_groups=2,
            ordered_ids_sha256=n.compact_hash([r["id"] for r in rows]),
            ordered_id_group_sequence_start_sha256=n.compact_hash(
                [
                    {k: r[k] for k in ("id", "group", "sequence_sha256", "start")}
                    for r in rows
                ]
            ),
        )
        p["execution"].update(
            batch_records=2,
            last_batch_records=2,
            batches_per_configuration=2,
            jobs=8,
            record_predictions=16,
        )
        p["execution"]["campaigns"]["original"]["jobs"] = 2
        p["execution"]["campaigns"]["linker3"]["jobs"] = 6
        p["uncertainty"].update(draws=20, minimum_usable_draws=18)
        self.candidate = {
            "schema_version": "native-rbs-recheck-candidate-provisional-1",
            "candidate_source": p["candidate"]["source_commit"],
            "package_version": p["candidate"]["version"],
            "archives": [{"sha256": p["candidate"]["wheel_sha256"]}],
            "runtime_executable": {"sha256": "b" * 64},
            "backends": {
                name: {"backend": {"name": name}, "profiles": {}}
                for name in ("original", "linker3")
            },
        }
        for config in p["configurations"]:
            self.candidate["backends"][config["backend"]]["profiles"][
                config["profile"]
            ] = {
                "schema_version": config["result_schema_version"],
                "model": {
                    "id": (
                        "salis-v1"
                        if config["profile"] == "historical"
                        else config["profile"]
                    )
                    + "-rnastructure-6.6-reconstruction-1",
                    "implementation_version": "0.12.0rc1",
                    "source_commit": "artificial",
                    "parameters": {},
                },
            }
        self.rows = n.select_inputs(self.development, self.split, p["cohort"])
        self.labels = {r["id"]: i + 1 for i, r in enumerate(self.rows)}
        self.predictions = {
            config["id"]: [
                {"id": r["id"], "status": "ok", "predicted": float(i + 1), "reason": ""}
                for i, r in enumerate(self.rows)
            ]
            for config in p["configurations"]
        }

    def select(self, development=None, split=None, cohort=None):
        return n.select_inputs(
            development or self.development,
            split or self.split,
            cohort or self.protocol["cohort"],
        )

    def test_selected_inputs_omit_measurements_and_source_order(self):
        self.development["records"].reverse()
        rows = self.select()
        self.assertEqual([r["id"] for r in rows], sorted(self.labels))
        self.assertTrue(all(set(r) == set(n.INPUT_FIELDS) for r in rows))
        extra = copy.deepcopy(self.development["records"][0])
        extra.update(id="train", partition="development_train", observed="unused")
        self.development["records"].append(extra)
        self.assertEqual(self.select(), rows)

    def test_input_metadata_and_roster_mutations(self):
        mutations = [
            lambda d, s, c: d.update(schema_version="unsupported"),
            lambda d, s, c: s.update(schema_version="unsupported"),
            lambda d, s, c: d.update(input_envelope_sha256="different"),
            lambda d, s, c: d["records"].append(copy.deepcopy(d["records"][0])),
            lambda d, s, c: d["records"].pop(),
            lambda d, s, c: d["records"][0].update(partition="final"),
            lambda d, s, c: s["records"][0].update(primary_eligible=False),
            lambda d, s, c: s["records"][0].update(group="different"),
            lambda d, s, c: c.update(records=5),
            lambda d, s, c: c.update(homology_groups=3),
            lambda d, s, c: c.update(ordered_ids_sha256="different"),
            lambda d, s, c: c.update(
                ordered_id_group_sequence_start_sha256="different"
            ),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                d, s, c = copy.deepcopy(
                    (self.development, self.split, self.protocol["cohort"])
                )
                change(d, s, c)
                with self.assertRaises(ValueError):
                    self.select(d, s, c)

    def test_input_context_mutations(self):
        changes = {
            "sequence": "N" * 200,
            "sequence_sha256": "bad",
            "start": True,
            "host": "other",
            "temperature_celsius": 31,
            "anti_sd": "ACCUCCUUA",
            "condition": "LC",
            "quantity": "other",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                d = copy.deepcopy(self.development)
                d["records"][0][field] = value
                with self.assertRaises(ValueError):
                    self.select(d)
        d = copy.deepcopy(self.development)
        s = copy.deepcopy(self.split)
        d["records"][0]["group"] = s["records"][0]["group"] = ""
        with self.assertRaisesRegex(ValueError, "Group identity"):
            self.select(d, s)
        for position in (-1, 198):
            d = copy.deepcopy(self.development)
            c = copy.deepcopy(self.protocol["cohort"])
            d["records"][0]["start"] = c["start"] = position
            with self.assertRaises(ValueError):
                self.select(d, cohort=c)
        d = copy.deepcopy(self.development)
        s = copy.deepcopy(self.split)
        d["records"][0]["sequence"] = "A" * 200
        d["records"][0]["sequence_sha256"] = s["records"][0]["sequence_sha256"] = (
            n.digest("A" * 200)
        )
        with self.assertRaisesRegex(ValueError, "start codon"):
            self.select(d, s)

    def test_pinned_json_is_strict_and_bounded(self):
        p = self.root / "input.json"
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b"{", b"\xff"):
            p.write_bytes(raw)
            with self.assertRaises(ValueError):
                n.checked_json(p, n.digest(raw), 100)
        p.write_bytes(b"{}")
        self.assertEqual(n.checked_json(p, n.digest(b"{}"), 2), {})
        with self.assertRaisesRegex(ValueError, "hash"):
            n.checked_json(p, "0" * 64, 100)
        with self.assertRaisesRegex(ValueError, "byte limit"):
            n.checked_json(p, n.digest(b"{}"), 1)

    def test_exact_public_inputs_and_no_scoring_modules(self):
        import sys

        before = {name for name in sys.modules if name.startswith("regsite")}
        protocol = json.loads(n.PROTOCOL.read_bytes())
        rows = n.load_inputs(protocol)
        self.assertEqual((len(rows), len({r["group"] for r in rows})), (479, 423))
        self.assertEqual(
            {name for name in sys.modules if name.startswith("regsite")}, before
        )
        protocol["inputs"]["split"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pins"):
            n.load_inputs(protocol)

    def test_public_split_reference_guard(self):
        docs = [{**self.development, "split_sha256": "wrong"}, self.split]
        with patch.object(n, "checked_json", side_effect=docs):
            with self.assertRaisesRegex(ValueError, "Split reference"):
                n.load_inputs(self.protocol)

    def test_plan_packing_rotation_and_no_label_leakage(self):
        plan = n.build_plan(self.protocol, self.candidate, self.rows)
        jobs = plan["campaigns"]["linker3"]["manifest"]["jobs"]
        self.assertEqual(
            [j["options"]["profile"] for j in jobs],
            [
                "historical",
                "context2017",
                "standby2014",
                "context2017",
                "standby2014",
                "historical",
            ],
        )
        self.assertEqual(len(plan["campaigns"]["original"]["manifest"]["jobs"]), 2)
        for path, batch in plan["requests"].items():
            self.assertTrue(
                all(
                    set(r)
                    == {
                        "schema_version",
                        "id",
                        "sequence",
                        "host",
                        "anti_sd",
                        "temperature_c",
                        "strand",
                        "start_positions",
                    }
                    for r in batch
                )
            )
            self.assertEqual([r["start_positions"] for r in batch], [[100], [100]])
            matches = [
                j
                for c in plan["campaigns"].values()
                for j in c["manifest"]["jobs"]
                if j["request"]["path"] == path
            ]
            self.assertEqual(len(matches), 4)
            self.assertTrue(
                all(
                    j["request"]["sha256"] == n.digest(n.canonical(batch))
                    for j in matches
                )
            )
        self.assertEqual(plan, n.build_plan(self.protocol, self.candidate, self.rows))

    def test_plan_identity_and_counts_mutations(self):
        for field, value in [
            ("schema_version", "bad"),
            ("candidate_source", "bad"),
            ("package_version", "bad"),
            ("archives", []),
        ]:
            candidate = copy.deepcopy(self.candidate)
            candidate[field] = value
            with self.assertRaises(ValueError):
                n.build_plan(self.protocol, candidate, self.rows)
        candidate = copy.deepcopy(self.candidate)
        candidate["backends"]["original"]["profiles"]["historical"][
            "schema_version"
        ] = "bad"
        with self.assertRaises(ValueError):
            n.build_plan(self.protocol, candidate, self.rows)
        for field, value in [
            ("batches_per_configuration", 3),
            ("last_batch_records", 1),
            ("jobs", 9),
            ("record_predictions", 17),
        ]:
            protocol = copy.deepcopy(self.protocol)
            protocol["execution"][field] = value
            with self.assertRaises(ValueError):
                n.build_plan(protocol, self.candidate, self.rows)
        protocol = copy.deepcopy(self.protocol)
        protocol["execution"]["campaigns"]["original"]["jobs"] = 3
        with self.assertRaises(ValueError):
            n.build_plan(protocol, self.candidate, self.rows)
        protocol = copy.deepcopy(self.protocol)
        protocol["configurations"][0]["backend"] = "linker3"
        with self.assertRaises(ValueError):
            n.build_plan(protocol, self.candidate, self.rows)

    def test_rank_endpoints_are_deterministic_and_keep_failed_denominators(self):
        self.predictions["context2017-linker3"][0].update(
            status="failed", predicted=None, reason="synthetic"
        )
        result = n.analyze(self.rows, self.labels, self.predictions, self.protocol)
        self.assertEqual(
            result, n.analyze(self.rows, self.labels, self.predictions, self.protocol)
        )
        summary = result["configurations"]["context2017-linker3"]
        self.assertEqual(
            (summary["n_inputs"], summary["n_success"], summary["coverage"]),
            (4, 3, 0.75),
        )
        self.assertEqual(summary["failure_reasons"], {"synthetic": 1})
        self.assertEqual(summary["rank"]["n_groups"], 2)
        contrast = result["contrasts"][1]
        self.assertEqual(
            (
                contrast["n_inputs"],
                contrast["n_common_success"],
                contrast["lost_reference_successes"],
            ),
            (4, 3, 1),
        )
        self.assertEqual(contrast["rank_gain"], 0)
        # Draws containing only the failed row's group have constant remaining
        # observations; the fixed usable-draw threshold must withhold an interval.
        self.assertIsNone(contrast["interval95"])
        self.assertEqual(contrast["interval_status"], "insufficient_usable_draws")
        self.assertGreater(contrast["undefined_draws"], 0)

    def test_rank_ties_constants_and_undefined_draws(self):
        rows = [
            {
                "group": str(i // 2),
                "observed": float(i + 1),
                "predicted": float(i // 2),
                "status": "ok",
            }
            for i in range(4)
        ]
        result = n.rank_interval(rows, self.protocol["uncertainty"])
        self.assertAlmostEqual(result["spearman_rho"], 0.8944271909999159)
        self.assertGreater(result["undefined_draws"], 0)
        self.assertEqual(result["interval_status"], "insufficient_usable_draws")
        settings = {**self.protocol["uncertainty"], "minimum_usable_draws": 1}
        self.assertEqual(n.rank_interval(rows, settings)["interval_status"], "ok")
        for row in rows:
            row["predicted"] = 1
        self.assertEqual(
            n.rank_interval(rows, settings)["interval_status"],
            "undefined_point_correlation",
        )
        for row in rows:
            row["status"] = "failed"
        result = n.rank_interval(rows, settings)
        self.assertIsNone(result["spearman_rho"])
        self.assertEqual(result["n_groups"], 2)
        self.assertEqual(result["attempted_draws"], 0)

    def test_all_failed_and_empty_metrics_stay_explicit(self):
        for group in self.predictions.values():
            for row in group:
                row.update(status="not_run", predicted=None, reason="unstarted")
        report = n.analyze(self.rows, self.labels, self.predictions, self.protocol)
        self.assertTrue(
            all(
                v["coverage"] == 0 and v["rank"]["spearman_rho"] is None
                for v in report["configurations"].values()
            )
        )
        empty = {key: [] for key in self.predictions}
        report = n.analyze([], {}, empty, self.protocol)
        self.assertTrue(
            all(v["coverage"] is None for v in report["configurations"].values())
        )

    def test_metric_identity_type_and_failure_mutations(self):
        for labels in (
            {},
            {**self.labels, "extra": 1},
            {**self.labels, "synthetic-0": True},
            {**self.labels, "synthetic-0": 0},
        ):
            with self.assertRaises(ValueError):
                n.analyze(self.rows, labels, self.predictions, self.protocol)
        with self.assertRaises(ValueError):
            n.analyze(self.rows, self.labels, {}, self.protocol)
        for change in [
            lambda r: r.pop(),
            lambda r: r.append(copy.deepcopy(r[0])),
            lambda r: r[0].update(status="bad"),
            lambda r: r[0].update(reason=None),
            lambda r: r[0].update(predicted=True),
            lambda r: r[0].update(predicted=float("inf")),
            lambda r: r[0].update(predicted=-1),
            lambda r: r[0].update(status="failed"),
        ]:
            predictions = copy.deepcopy(self.predictions)
            change(predictions["historical-original"])
            with self.assertRaises(ValueError):
                n.analyze(self.rows, self.labels, predictions, self.protocol)

    def prepared_files(self):
        """Return patched synthetic trust inputs; real committed pins stay intact."""
        protocol = copy.deepcopy(self.protocol)
        development = copy.deepcopy(self.development)
        split_path = self.root / n.INPUT_PINS["split"]["path"]
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_path.write_bytes(n.canonical(self.split))
        development["split_sha256"] = n.digest(split_path.read_bytes())
        development_path = self.root / n.INPUT_PINS["development"]["path"]
        development_path.write_bytes(n.canonical(development))
        pins = {
            name: {
                "path": pin["path"],
                "sha256": n.digest((self.root / pin["path"]).read_bytes()),
            }
            for name, pin in n.INPUT_PINS.items()
        }
        candidate_path = self.root / "candidate.json"
        candidate_path.write_bytes(n.canonical(self.candidate))
        protocol["candidate"]["provisional_receipt_sha256"] = n.digest(
            candidate_path.read_bytes()
        )
        protocol["inputs"] = pins
        protocol_path = self.root / "protocol.json"
        protocol_path.write_bytes(n.canonical(protocol))
        for name in n.CODE_FILES:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            if name.startswith("schemas/"):
                p.write_bytes((n.ROOT / name).read_bytes())
            else:
                p.write_text("# Artificial code identity; never imported.\n")
        return patch.multiple(
            n, ROOT=self.root, PROTOCOL=protocol_path, INPUT_PINS=pins
        )

    def test_prepare_publishes_complete_plan_last_and_refuses_collision(self):
        with self.prepared_files():
            output = self.root / "prepared"
            plan = n.prepare(self.root / "candidate.json", output)
            self.assertEqual(json.loads((output / "plan.json").read_bytes()), plan)
            self.assertEqual(plan["protocol_sha256"], n.digest(n.PROTOCOL.read_bytes()))
            snapshot = {
                str(p.relative_to(output)): p.read_bytes()
                for p in output.rglob("*")
                if p.is_file()
            }
            for name, campaign in plan["campaigns"].items():
                self.assertEqual(
                    (output / name / "manifest.json").read_bytes(),
                    n.canonical(campaign["manifest"]),
                )
                for job in campaign["manifest"]["jobs"]:
                    self.assertEqual(
                        n.digest((output / name / job["request"]["path"]).read_bytes()),
                        job["request"]["sha256"],
                    )
            for p in output.rglob("*"):
                self.assertEqual(
                    p.stat().st_mode & 0o777, 0o600 if p.is_file() else 0o700
                )
            with self.assertRaises(FileExistsError):
                n.prepare(self.root / "candidate.json", output)
            self.assertEqual(
                snapshot,
                {
                    str(p.relative_to(output)): p.read_bytes()
                    for p in output.rglob("*")
                    if p.is_file()
                },
            )

    def test_partial_preparation_retains_evidence_without_plan_or_resume(self):
        with self.prepared_files():
            output = self.root / "partial"
            writer = n.publish
            count = 0

            def write(path, value):
                nonlocal count
                count += 1
                if count == 3:
                    raise OSError("artificial storage failure")
                writer(path, value)

            with patch.object(n, "publish", side_effect=write):
                with self.assertRaises(OSError):
                    n.prepare(self.root / "candidate.json", output)
            self.assertTrue((output / "protocol.json").is_file())
            self.assertFalse((output / "plan.json").exists())
            with self.assertRaises(FileExistsError):
                n.prepare(self.root / "candidate.json", output)

    def test_preparation_protocol_and_candidate_guards(self):
        with self.prepared_files():
            original = n.PROTOCOL.read_bytes()
            for field, value in (
                ("schema_version", "unknown"),
                ("stage", "held-out"),
                ("inputs", {}),
            ):
                doc = json.loads(original)
                doc[field] = value
                n.PROTOCOL.write_bytes(n.canonical(doc))
                with self.assertRaises(ValueError):
                    n.load_protocol()
            n.PROTOCOL.write_bytes(original)
            (self.root / "candidate.json").write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "hash"):
                n.prepare(self.root / "candidate.json", self.root / "new")
            self.assertFalse((self.root / "new").exists())

    def test_external_destination_guards(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            n.external_directory("relative")
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            n.external_directory(link / "child")
        repo = self.root / "repo"
        repo.mkdir()
        (repo / ".git").write_text("synthetic git marker")
        with self.assertRaisesRegex(ValueError, "repositories"):
            n.external_directory(repo / "child")

    def test_prepare_cli_summary_and_failure(self):
        with self.prepared_files():
            argv = [
                "prepare",
                "--candidate",
                str(self.root / "candidate.json"),
                "--output",
                str(self.root / "cli"),
            ]
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(n.main(argv), 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["predictions_executed"], 0)
            self.assertEqual((summary["records"], summary["jobs"]), (4, 8))
            with patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(n.main(argv), 2)
        argv = [
            "native_development_recheck",
            "prepare",
            "--candidate",
            str(self.root / "missing-candidate"),
            "--output",
            str(self.root / "module"),
        ]
        with (
            warnings.catch_warnings(action="ignore", category=RuntimeWarning),
            patch.object(sys, "argv", argv),
            patch("sys.stderr", new_callable=io.StringIO),
            self.assertRaises(SystemExit) as error,
        ):
            runpy.run_module(
                "benchmarks.rbs.native_development_recheck", run_name="__main__"
            )
        self.assertEqual(error.exception.code, 2)

    def schema_value(self, schema, root):
        """Minimal artificial schema witness, not a producer/scientific fixture."""
        if "$ref" in schema:
            target = root
            for part in schema["$ref"].split("/")[1:]:
                target = target[part]
            return self.schema_value(target, root)
        if "const" in schema:
            return schema["const"]
        if "enum" in schema:
            return schema["enum"][0]
        for choice in ("oneOf", "anyOf"):
            if choice in schema:
                return self.schema_value(schema[choice][0], root)
        kind = schema.get("type", "object")
        if isinstance(kind, list):
            kind = kind[0]
        if kind == "object":
            value = {
                k: self.schema_value(schema.get("properties", {}).get(k, {}), root)
                for k in schema.get("required", [])
            }
            for clause in schema.get("allOf", []):
                condition = clause.get("if", {})
                branch = clause.get(
                    "then"
                    if n.Draft202012Validator(condition).is_valid(value)
                    else "else",
                    {},
                )
                for key, specification in branch.get("properties", {}).items():
                    if key not in value or specification != {"type": "object"}:
                        value[key] = self.schema_value(specification, root)
            return value
        if kind == "array":
            return [
                self.schema_value(schema.get("items", {}), root)
                for _ in range(schema.get("minItems", 0))
            ]
        return {
            "string": "artificial",
            "number": 0.0,
            "integer": max(0, schema.get("minimum", 0)),
            "boolean": True,
            "null": None,
        }[kind]

    def native_result(self, rows, expected, statuses=None):
        version = expected["schema_version"]
        schema = json.loads(
            (n.ROOT / f"schemas/rbs-result-{version}.schema.json").read_bytes()
        )
        record_schema = schema["properties"]["results"]["items"]
        results = []
        for number, row in enumerate(rows):
            value = self.schema_value(record_schema, schema)
            sequence = row["sequence"].replace("T", "U")
            status = statuses[number] if statuses else "ok"
            value.update(
                id=row["id"],
                model=expected["model"],
                backend=expected["backend"],
                status=status,
                reason=None if status == "ok" else "artificial_failure",
                prediction_id="a" * 64,
                input={
                    "id": row["id"],
                    "host": row["host"],
                    "sequence": sequence,
                    "oriented_sequence": sequence,
                    "input_sha256": row["sequence_sha256"],
                    "normalized_sha256": n.digest(sequence),
                    "oriented_sha256": n.digest(sequence),
                    "start_positions": [row["start"]],
                    "strand": "+",
                    "anti_sd": row["anti_sd"],
                    "temperature_c": float(row["temperature_celsius"]),
                },
            )
            site_schema = record_schema["properties"]["sites"]["items"]
            site = self.schema_value(site_schema, schema)
            site.update(
                status=status,
                reason=value["reason"],
                codon=sequence[row["start"] : row["start"] + 3],
                oriented_start=row["start"],
                start_codon={
                    "start": row["start"],
                    "end": row["start"] + 3,
                    "strand": "+",
                },
            )
            if status == "ok":
                site.update(tir=float(number + 1), log_tir=float(number))
            else:
                for key in (
                    "energies",
                    "tir",
                    "log_tir",
                    "structures",
                    "binding_interval",
                    "standby_interval",
                    "aligned_spacing",
                    "candidate_search",
                    "coding_footprint",
                    "post_footprint",
                    "standby",
                ):
                    if key in site:
                        site[key] = None
            value["sites"] = [site]
            results.append(value)
        return {"schema_version": version, "results": results}

    def test_native_schemas_all_profiles_and_failure_nulls(self):
        plan = n.build_plan(self.protocol, self.candidate, self.rows)
        for expected in plan["expected"].values():
            with self.subTest(version=expected["schema_version"]):
                document = self.native_result(self.rows, expected)
                scores = n.native_scores(n.canonical(document), self.rows, expected, 0)
                self.assertEqual(scores[0]["predicted"], 1)
                document = self.native_result(
                    self.rows, expected, ["failed", "no_candidate", "unsupported", "ok"]
                )
                scores = n.native_scores(n.canonical(document), self.rows, expected, 1)
                self.assertEqual(
                    [r["status"] for r in scores],
                    ["failed", "no_candidate", "unsupported", "ok"],
                )
                document["results"][0]["sites"] = []
                self.assertIsNone(
                    n.native_scores(n.canonical(document), self.rows, expected, 1)[0][
                        "predicted"
                    ]
                )

    def test_invalid_input_retains_request_accounting_without_fake_echo(self):
        expected = n.build_plan(self.protocol, self.candidate, self.rows)["expected"][
            "historical-original"
        ]
        doc = self.native_result(self.rows, expected)
        doc["results"][0].update(
            status="invalid_input",
            reason="artificial_validation_failure",
            input=None,
            prediction_id=None,
            sites=[],
        )
        scores = n.native_scores(n.canonical(doc), self.rows, expected, 1)
        self.assertEqual(scores[0]["status"], "invalid_input")
        self.assertIsNone(scores[0]["predicted"])
        doc["results"][0]["prediction_id"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "Invalid-input provenance"):
            n.native_scores(n.canonical(doc), self.rows, expected, 1)

    def test_native_semantic_mutations_after_valid_serialization(self):
        expected = n.build_plan(self.protocol, self.candidate, self.rows)["expected"][
            "historical-original"
        ]
        original = self.native_result(self.rows, expected)
        changes = [
            lambda d: d.update(schema_version="9"),
            lambda d: d["results"].reverse(),
            lambda d: d["results"][0]["model"].update(id="other"),
            lambda d: d["results"][0].update(backend={}),
            lambda d: d["results"][0]["input"].update(start_positions=None),
            lambda d: d["results"][0].update(prediction_id=None),
            lambda d: d["results"][0]["sites"].clear(),
            lambda d: d["results"][0]["sites"][0].update(oriented_start=99),
            lambda d: d["results"][0]["sites"][0]["start_codon"].update(strand="-"),
            lambda d: d["results"][0]["sites"][0].update(codon="GUG"),
            lambda d: d["results"][0].update(status="failed", reason="failure"),
            lambda d: d["results"][0]["sites"][0].update(tir=-1),
            lambda d: d["results"][0].update(reason="failure"),
            lambda d: d["results"][0].update(extra=1),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                doc = copy.deepcopy(original)
                change(doc)
                with self.assertRaises(ValueError):
                    n.native_scores(n.canonical(doc), self.rows, expected, 0)
        with self.assertRaisesRegex(ValueError, "exit/status"):
            n.native_scores(n.canonical(original), self.rows, expected, 1)

    def campaign(self, plan, name, modes=None):
        folder = self.root / f"evidence-{name}"
        folder.mkdir(exist_ok=True)
        pins = {}

        def save(path, value, raw=False):
            data = value if raw else n.canonical(value)
            file = folder / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
            pins[path] = {"bytes": len(data), "sha256": n.digest(data)}

        expected_campaign = plan["campaigns"][name]
        manifest = expected_campaign["manifest"]
        save("campaign/manifest.json", manifest)
        first = expected_campaign["job_roster"][0]["configuration"]
        self.runtime = {
            "regsite_version": "0.12.0rc1",
            "code": self.protocol["candidate"]["runtime_code"],
            "python": {
                "cache_tag": "cpython-314",
                "executable_sha256": "b" * 64,
                "implementation": "cpython",
                "machine": "arm64",
                "platform": "darwin",
                "version": "artificial",
            },
        }
        campaign = {
            "schema_version": "calculator-job-campaign-1",
            "runtime": self.runtime,
            "backend": {
                "rnastructure": plan["expected"][first]["backend"],
                "conditional_original": None,
            },
            "manifest": {"path": "manifest.json", **pins["campaign/manifest.json"]},
        }
        save("campaign/campaign.json", campaign)
        campaign_sha = pins["campaign/campaign.json"]["sha256"]
        jobs, output_bytes, abandoned = [], 0, 0
        for index, (roster, spec) in enumerate(
            zip(expected_campaign["job_roster"], manifest["jobs"], strict=True)
        ):
            identity, config = roster["id"], roster["configuration"]
            rows = [r for r in plan["rows"] if r["id"] in roster["record_ids"]]
            request_path = f"jobs/{identity}/request.json"
            save("campaign/" + request_path, [n.request(r) for r in rows])
            mode = modes[index] if modes else "succeeded"
            row = {
                "id": identity,
                "kind": "rbs",
                "state": mode,
                "attempts": int(mode != "unstarted"),
                "receipt": None,
                "stdout": None,
                "error": None,
                "exit_code": None,
            }
            if mode != "unstarted":
                prefix = f"jobs/{identity}/attempt-0001"
                statuses = (
                    ["failed"] + ["ok"] * (len(rows) - 1) if mode == "partial" else None
                )
                document = self.native_result(rows, plan["expected"][config], statuses)
                save("campaign/" + prefix + "/stdout", document)
                save("campaign/" + prefix + "/stderr", b"", True)
                save(
                    "campaign/" + prefix + "/launch.json",
                    {"schema_version": "calculator-job-launch-1", "pgid": 999999},
                )
                streams = {
                    stream: {
                        "path": prefix + "/" + stream,
                        **pins["campaign/" + prefix + "/" + stream],
                        "truncated": mode == "output_limit",
                    }
                    for stream in ("stdout", "stderr")
                }
                output_bytes += sum(s["bytes"] for s in streams.values())
                if mode == "abandoned":
                    row["state"] = "unfinished"
                    abandoned += 1
                else:
                    terminal = mode not in {
                        "interrupted",
                        "campaign_deadline",
                        "launch_failed",
                        "storage_error",
                        "runtime_changed",
                    }
                    exit_code = {
                        "succeeded": 0,
                        "partial": 1,
                        "refused": 2,
                        "abnormal_exit": 9,
                    }.get(mode)
                    receipt = {
                        "schema_version": "calculator-job-receipt-1",
                        "campaign_sha256": campaign_sha,
                        "job_id": identity,
                        "kind": "rbs",
                        "attempt": 1,
                        "request": {
                            "path": request_path,
                            **pins["campaign/" + request_path],
                        },
                        "argv": [
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
                            spec["options"]["profile"],
                            "--seconds-per-record",
                            "60",
                        ],
                        "outcome": mode,
                        "terminal": terminal,
                        "exit_code": exit_code,
                        "signal": None,
                        "elapsed_seconds": 0.5,
                        **streams,
                    }
                    save("campaign/" + prefix + "/receipt.json", receipt)
                    row.update(
                        state=mode if terminal else "unfinished",
                        exit_code=exit_code,
                        receipt=prefix + "/receipt.json",
                        stdout={
                            k: streams["stdout"][k] for k in ("path", "sha256", "bytes")
                        },
                    )
            jobs.append(row)
        states = [
            "abnormal_exit",
            "attempts_exhausted",
            "corrupted",
            "output_limit",
            "partial",
            "refused",
            "succeeded",
            "timed_out",
            "unfinished",
            "unstarted",
        ]
        counts = {state: sum(j["state"] == state for j in jobs) for state in states}
        summary = {
            "schema_version": "calculator-job-summary-1",
            "command": "verify",
            "stop_reason": None,
            "status": "incomplete"
            if counts["unfinished"] + counts["unstarted"]
            else "complete",
            "campaign_sha256": campaign_sha,
            "manifest_sha256": pins["campaign/manifest.json"]["sha256"],
            "counts": counts,
            "jobs": jobs,
            "attempts": sum(j["attempts"] for j in jobs),
            "abandoned_attempts": abandoned,
            "output_bytes": output_bytes,
        }
        save("verification.json", summary)
        save("run-summary.json", {**summary, "command": "run"})
        return {"root": str(folder), "files": pins}, save

    def test_campaign_admission_and_failure_denominators(self):
        plan = n.build_plan(self.protocol, self.candidate, self.rows)
        for modes in (
            ["succeeded", "partial"],
            ["unstarted", "timed_out"],
            ["abandoned", "interrupted"],
            ["output_limit", "refused"],
            ["abnormal_exit", "runtime_changed"],
        ):
            with self.subTest(modes=modes):
                acquisition, _ = self.campaign(plan, "original", modes)
                predictions, report = n.admit_campaign(
                    plan, "original", acquisition, self.runtime, self.protocol
                )
                self.assertEqual(len(predictions["historical-original"]), 4)
                self.assertEqual([j["outcome"] for j in report["jobs"]], modes)
                if modes[0] != "succeeded":
                    self.assertTrue(
                        all(
                            r["predicted"] is None
                            for r in predictions["historical-original"]
                        )
                    )
        acquisition, _ = self.campaign(plan, "linker3")
        scores, _ = n.admit_campaign(
            plan, "linker3", acquisition, self.runtime, self.protocol
        )
        self.assertEqual(
            set(scores),
            {"historical-linker3", "context2017-linker3", "standby2014-linker3"},
        )

    def test_artifact_guards(self):
        p = self.root / "artifact"
        p.write_bytes(b"{}")
        pins = {"artifact": {"bytes": 2, "sha256": n.digest(b"{}")}}
        a = n.Artifacts(self.root, pins)
        self.assertEqual(a.json("artifact"), {})
        with self.assertRaises(ValueError):
            n.Artifacts("relative", pins)
        for path in ("../artifact", "/absolute", "a//b", ""):
            with self.assertRaises(ValueError):
                a.read(path, 10)
        link = self.root / "link"
        link.symlink_to(p)
        with self.assertRaises(ValueError):
            a.read("link", 10)
        for pin in (
            {"bytes": True, "sha256": "a"},
            {"bytes": 11, "sha256": "a"},
            {"bytes": 2, "sha256": "a"},
            {"bytes": 1, "sha256": n.digest(b"{}")},
            {"bytes": 2, "sha256": "a", "extra": 0},
        ):
            with self.assertRaises(ValueError):
                n.Artifacts(self.root, {"artifact": pin}).read("artifact", 10)

    def test_campaign_semantic_failure_after_updated_synthetic_hashes(self):
        plan = n.build_plan(self.protocol, self.candidate, self.rows)
        mutations = [
            (
                "campaign/campaign.json",
                lambda d: d["runtime"].update(regsite_version="other"),
            ),
            (
                "campaign/campaign.json",
                lambda d: d["backend"].update(conditional_original={}),
            ),
            ("campaign/campaign.json", lambda d: d["manifest"].update(bytes=1)),
            ("verification.json", lambda d: d.update(command="resume")),
            ("verification.json", lambda d: d.update(campaign_sha256="a" * 64)),
            ("verification.json", lambda d: d.update(manifest_sha256="a" * 64)),
            ("verification.json", lambda d: d.update(status="corrupted")),
            ("verification.json", lambda d: d["jobs"].reverse()),
            ("verification.json", lambda d: d["jobs"][0].update(attempts=2)),
            ("verification.json", lambda d: d["counts"].update(succeeded=1)),
            ("verification.json", lambda d: d.update(attempts=1)),
            ("verification.json", lambda d: d.update(output_bytes=0)),
        ]
        for path, change in mutations:
            with self.subTest(path=path, mutation=mutations.index((path, change))):
                acq, save = self.campaign(plan, "original")
                doc = json.loads((Path(acq["root"]) / path).read_bytes())
                change(doc)
                save(path, doc)
                if path == "verification.json":
                    save("run-summary.json", {**doc, "command": "run"})
                with self.assertRaises(ValueError):
                    n.admit_campaign(plan, "original", acq, self.runtime, self.protocol)
        acq, save = self.campaign(plan, "original")
        save("unexpected.json", {})
        with self.assertRaisesRegex(ValueError, "Unconsumed"):
            n.admit_campaign(plan, "original", acq, self.runtime, self.protocol)

    def evaluation_files(self):
        plan = n.prepare(
            self.root / "candidate.json", self.root / "prepared-evaluation"
        )
        campaigns = {name: self.campaign(plan, name)[0] for name in plan["campaigns"]}
        freeze = {
            "schema_version": "native-rbs-development-freeze-1",
            "execution_authorized": True,
            "protocol_sha256": n.digest(n.PROTOCOL.read_bytes()),
            "candidate_receipt_sha256": plan["candidate_receipt_sha256"],
            "plan_sha256": n.digest(n.canonical(plan)),
            "runtime": self.runtime,
        }
        fp = self.root / "freeze.json"
        fp.write_bytes(n.canonical(freeze))
        acq = {
            "schema_version": "native-rbs-development-acquisition-1",
            "freeze_sha256": n.digest(fp.read_bytes()),
            "campaigns": campaigns,
        }
        ap = self.root / "acquisition.json"
        ap.write_bytes(n.canonical(acq))
        return [
            self.root / "candidate.json",
            self.root / "prepared-evaluation/plan.json",
            fp,
            n.digest(fp.read_bytes()),
            ap,
            n.digest(ap.read_bytes()),
            self.root / "evaluated",
        ]

    def test_evaluate_complete_external_roundtrip_and_cli(self):
        with self.prepared_files():
            args = self.evaluation_files()
            report = n.evaluate(*args)
            self.assertEqual(
                report, json.loads((args[-1] / "report.json").read_bytes())
            )
            self.assertEqual(report["stage"], "exploratory_consumed_development")
            self.assertTrue(
                all(r["coverage"] == 1 for r in report["configurations"].values())
            )
            args[-1] = self.root / "cli-evaluation"
            argv = [
                "evaluate",
                "--candidate",
                str(args[0]),
                "--plan",
                str(args[1]),
                "--freeze",
                str(args[2]),
                "--freeze-sha256",
                args[3],
                "--acquisition",
                str(args[4]),
                "--acquisition-sha256",
                args[5],
                "--output",
                str(args[6]),
            ]
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(n.main(argv), 0)
            self.assertEqual(json.loads(output.getvalue())["predictions_executed"], 0)
            with self.assertRaises(FileExistsError):
                n.evaluate(*args)

    def test_evaluate_identity_failures_before_analysis(self):
        with self.prepared_files():
            args = self.evaluation_files()
            originals = {2: args[2].read_bytes(), 4: args[4].read_bytes()}
            changes = [
                (2, lambda d: d.update(execution_authorized=False)),
                (2, lambda d: d.update(protocol_sha256="a" * 64)),
                (2, lambda d: d.update(candidate_receipt_sha256="a" * 64)),
                (2, lambda d: d["runtime"].update(regsite_version="bad")),
                (
                    2,
                    lambda d: d["runtime"]["python"].update(executable_sha256="a" * 64),
                ),
                (2, lambda d: d["runtime"]["code"].update(files=53)),
                (4, lambda d: d.update(schema_version="bad")),
                (4, lambda d: d.update(freeze_sha256="a" * 64)),
                (4, lambda d: d["campaigns"].pop("original")),
            ]
            for index, change in changes:
                with self.subTest(index=index, change=changes.index((index, change))):
                    for i, raw in originals.items():
                        args[i].write_bytes(raw)
                        args[i + 1] = n.digest(raw)
                    doc = json.loads(originals[index])
                    change(doc)
                    args[index].write_bytes(n.canonical(doc))
                    args[index + 1] = n.digest(args[index].read_bytes())
                    with patch.object(
                        n,
                        "analyze",
                        side_effect=AssertionError("Must not join outcomes"),
                    ):
                        with self.assertRaises(ValueError):
                            n.evaluate(*args)
            self.assertFalse(args[-1].exists())

    def test_abandoned_attempt_missing_stream_keeps_all_cases(self):
        plan = n.build_plan(self.protocol, self.candidate, self.rows)
        acq, save = self.campaign(plan, "original", ["abandoned", "unstarted"])
        identity = plan["campaigns"]["original"]["job_roster"][0]["id"]
        path = f"campaign/jobs/{identity}/attempt-0001/stdout"
        size = acq["files"].pop(path)["bytes"]
        (Path(acq["root"]) / path).unlink()
        for name in ("verification.json", "run-summary.json"):
            doc = json.loads((Path(acq["root"]) / name).read_bytes())
            doc["output_bytes"] -= size
            save(name, doc)
        scores, report = n.admit_campaign(
            plan, "original", acq, self.runtime, self.protocol
        )
        self.assertEqual(len(scores["historical-original"]), 4)
        self.assertEqual(report["output_bytes"], 0)
        self.assertEqual(report["jobs"][0]["outcome"], "abandoned")

    def test_receipt_mutations_reach_semantic_guards(self):
        plan = n.build_plan(self.protocol, self.candidate, self.rows)
        identity = plan["campaigns"]["original"]["job_roster"][0]["id"]
        path = f"campaign/jobs/{identity}/attempt-0001/receipt.json"
        mutations = [
            lambda d: d.update(campaign_sha256="a" * 64),
            lambda d: d.update(job_id="other"),
            lambda d: d.update(kind="promoter"),
            lambda d: d.update(attempt=2),
            lambda d: d["request"].update(sha256="a" * 64),
            lambda d: d["argv"].__setitem__(-1, "61"),
            lambda d: d.update(outcome="partial", exit_code=1),
            lambda d: d.update(exit_code=1),
            lambda d: d["stdout"].update(path="../outside"),
            lambda d: d["stderr"].update(sha256="a" * 64),
            lambda d: d["stderr"].update(truncated=True),
            lambda d: d.update(signal=9),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                acq, save = self.campaign(plan, "original")
                doc = json.loads((Path(acq["root"]) / path).read_bytes())
                change(doc)
                save(path, doc)
                with self.assertRaises(ValueError):
                    n.admit_campaign(plan, "original", acq, self.runtime, self.protocol)

    def test_job_and_campaign_failure_accounting_mutations(self):
        plan = n.build_plan(self.protocol, self.candidate, self.rows)
        changes = [
            lambda d: d.update(abandoned_attempts=1),
            lambda d: d.update(status="incomplete"),
            lambda d: d["jobs"][0].update(kind="promoter"),
            lambda d: d["jobs"][0].update(error="missing"),
            lambda d: d["jobs"][0].update(receipt="elsewhere"),
            lambda d: d["jobs"][0]["stdout"].update(bytes=0),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                acq, save = self.campaign(plan, "original")
                doc = json.loads((Path(acq["root"]) / "verification.json").read_bytes())
                change(doc)
                save("verification.json", doc)
                save("run-summary.json", {**doc, "command": "run"})
                with self.assertRaises(ValueError):
                    n.admit_campaign(plan, "original", acq, self.runtime, self.protocol)
        acq, save = self.campaign(plan, "original")
        doc = json.loads((Path(acq["root"]) / "verification.json").read_bytes())
        doc["stop_reason"] = "campaign_deadline"
        save("verification.json", doc)
        with self.assertRaisesRegex(ValueError, "Verify stop"):
            n.admit_campaign(plan, "original", acq, self.runtime, self.protocol)
        acq, save = self.campaign(plan, "original", ["unstarted", "unstarted"])
        doc = json.loads((Path(acq["root"]) / "verification.json").read_bytes())
        doc["jobs"][0]["exit_code"] = 0
        save("verification.json", doc)
        save("run-summary.json", {**doc, "command": "run"})
        with self.assertRaisesRegex(ValueError, "Unstarted"):
            n.admit_campaign(plan, "original", acq, self.runtime, self.protocol)
        acq, save = self.campaign(plan, "original", ["abandoned", "unstarted"])
        doc = json.loads((Path(acq["root"]) / "verification.json").read_bytes())
        doc["jobs"][0]["exit_code"] = 0
        save("verification.json", doc)
        save("run-summary.json", {**doc, "command": "run"})
        with self.assertRaisesRegex(ValueError, "Abandoned attempt"):
            n.admit_campaign(plan, "original", acq, self.runtime, self.protocol)

    def test_evaluate_all_unstarted_keeps_empty_runtime_diagnostics(self):
        with self.prepared_files():
            args = self.evaluation_files()
            doc = json.loads(args[4].read_bytes())
            plan = json.loads(args[1].read_bytes())
            for name, value in plan["campaigns"].items():
                doc["campaigns"][name] = self.campaign(
                    plan, name, ["unstarted"] * len(value["job_roster"])
                )[0]
            args[4].write_bytes(n.canonical(doc))
            args[5] = n.digest(args[4].read_bytes())
            report = n.evaluate(*args)
            self.assertTrue(
                all(
                    v["runtime_diagnostic"]["elapsed_max_seconds"] is None
                    and v["coverage"] == 0
                    for v in report["configurations"].values()
                )
            )


if __name__ == "__main__":
    unittest.main()
