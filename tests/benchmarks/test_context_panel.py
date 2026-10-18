"""Synthetic checks of deterministic context selection and scenario identity."""

import copy
import hashlib
import io
import json
import runpy
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.promoter.native_inputs import canonical_bytes, document_sha256
from benchmarks.rbs import context_panel as panel


def envelope():
    """One locus in each stratum, with a retained alternative at the first."""
    genome = "ACGT" * 100
    rows = []
    for i, leader in enumerate((-1, 0, 5, 30, 40, None)):
        rows.append(
            {
                "id": f"row-{i}",
                "genome_id": "g",
                "strand": "+",
                "tss_type": "gTSS",
                "source_locus_tag": f"locus-{i}",
                "tss_zero_based": 100,
                "cds_start_zero_based": 100 + leader if leader is not None else None,
                "source_start_zero_based": 150,
                "source_start_distance_nt": 50,
                "leader_length_nt": leader,
                "source_current_start_delta_nt": 20 if i == 3 else 0,
                "conditions": {"control": [12, 35]},
                "warnings": ["source warning"],
                "origin_crossing": False,
                "source_flags": [],
            }
        )
    alternate = copy.deepcopy(rows[0])
    alternate.update(id="alternate", leader_length_nt=50, cds_start_zero_based=150)
    rows.append(alternate)
    rows.append({"id": "antisense", "tss_type": "aTSS"})
    rows.append({"id": "missing-locus", "tss_type": "gTSS"})
    return {
        "schema_version": "native-rbs-evidence-1",
        "genomes": {
            "g": {
                "sequence": genome,
                "sequence_sha256": hashlib.sha256(genome.encode()).hexdigest(),
                "accession": "g",
                "assembly": "synthetic-v1",
                "annotation": "synthetic-v1",
                "topology": "linear",
            }
        },
        "records": rows,
    }


class ContextPanelTests(unittest.TestCase):
    def test_selection_and_all_alternatives(self):
        source = envelope()
        original = copy.deepcopy(source)
        result = panel.build_panel(source, "f" * 64)
        self.assertEqual(source, original)
        details = result["panel"]
        self.assertEqual(
            details["counts"],
            {
                "source_rows": 9,
                "source_gtss_rows": 8,
                "gtss_rows_without_locus": 1,
                "source_loci": 6,
                "loci_by_stratum": dict.fromkeys(panel.STRATA, 1),
                "selected_loci": 6,
                "selected_source_rows": 7,
                "input_scenarios": 28,
                "profile_jobs": 56,
            },
        )
        self.assertEqual(
            details["selected_loci"][0]["record_ids"], ["alternate", "row-0"]
        )
        self.assertEqual(
            details["excluded_without_locus_record_ids"], ["missing-locus"]
        )
        self.assertEqual(len({r["id"] for r in result["records"]}), 28)
        self.assertEqual(
            details["settings_sha256"], document_sha256(details["settings"])
        )
        for record in result["records"]:
            self.assertEqual(record["conditions"], ["control"])
            self.assertEqual(record["temperature_c"], 37)
            self.assertEqual(record["anti_sd"], "ACCUCCUUU")
        source["records"].reverse()
        self.assertEqual(result, panel.build_panel(source, "f" * 64))

    def test_hash_selection_is_not_row_or_response_order(self):
        source = envelope()
        for i in range(10):
            row = copy.deepcopy(source["records"][4])
            row.update(id=f"extra-{i}", source_locus_tag=f"extra-locus-{i}")
            source["records"].append(row)
        names = ["locus-4"] + [f"extra-locus-{i}" for i in range(10)]
        expected = sorted(
            names,
            key=lambda name: hashlib.sha256(
                json.dumps(
                    ["wave5-tan-context-v1", "g", name], separators=(",", ":")
                ).encode()
            ).hexdigest(),
        )[:4]
        result = panel.build_panel(source, "f" * 64)
        selected = [
            r["source_locus_tag"]
            for r in result["panel"]["selected_loci"]
            if r["stratum"] == "ordinary"
        ]
        self.assertEqual(selected, expected)
        for row in source["records"]:
            row["ignored_score"] = -1000
        self.assertEqual(panel.build_panel(source, "f" * 64), result)

    def test_scenarios_keep_anchor_and_context_distinct(self):
        row = envelope()["records"][3]
        rows = list(panel.scenarios(row))
        self.assertEqual(
            [r["cds_start_zero_based"] for r in rows], [130, 130, 150, 150]
        )
        self.assertEqual([r["tss_zero_based"] for r in rows], [100, None, 100, None])
        self.assertEqual([r["leader_length_nt"] for r in rows], [30, None, 50, None])
        self.assertTrue(all(r["measured_tss_zero_based"] == 100 for r in rows))
        row["source_start_zero_based"] = None
        row["conditions"] = ["control"]
        self.assertIsNone(list(panel.scenarios(row))[2]["leader_length_nt"])
        del row["conditions"]
        del row["warnings"]
        self.assertEqual(list(panel.scenarios(row))[0]["conditions"], [])

    def test_explicit_invalid_inputs(self):
        for value in [True, 0, 5, "4"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                panel.build_panel(envelope(), "f" * 64, value)
        for field, value in [
            ("leader_length_nt", True),
            ("source_current_start_delta_nt", "2"),
            ("tss_zero_based", 400),
            ("cds_start_zero_based", -1),
            ("source_start_zero_based", 2.5),
            ("source_start_distance_nt", False),
            ("genome_id", "absent"),
            ("strand", "?"),
            ("conditions", None),
            ("conditions", [12]),
            ("conditions", [""]),
            ("warnings", None),
            ("warnings", [1]),
        ]:
            source = envelope()
            source["records"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                panel.build_panel(source, "f" * 64)
        with patch.object(panel, "MAX_SELECTED_ROWS", 6), self.assertRaises(ValueError):
            panel.build_panel(envelope(), "f" * 64)

    def test_empty_source_and_nonempty_condition_list(self):
        source = envelope()
        source["records"] = []
        result = panel.build_panel(source, "f" * 64)
        self.assertEqual(result["records"], [])
        self.assertEqual(
            result["panel"]["counts"]["loci_by_stratum"], dict.fromkeys(panel.STRATA, 0)
        )
        row = envelope()["records"][0]
        row["conditions"] = ["dark", "control"]
        self.assertEqual(
            list(panel.scenarios(row))[0]["conditions"], ["dark", "control"]
        )

    def test_cli_hash_binding_exclusive_permissions_and_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "source.json", root / "panel.json"
            raw = canonical_bytes(envelope())
            source.write_bytes(raw)
            args = [
                str(source),
                str(output),
                "--source-sha256",
                hashlib.sha256(raw).hexdigest(),
            ]
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(panel.main(args), 0)
                self.assertEqual(
                    json.loads(stdout.getvalue())["output_sha256"],
                    hashlib.sha256(output.read_bytes()).hexdigest(),
                )
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            with patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(panel.main(args), 1)
                self.assertEqual(panel.main(args[:-1] + ["a" * 64]), 1)
            output.unlink()
            with (
                patch.object(sys, "argv", ["context_panel"] + args),
                patch("sys.stdout", new_callable=io.StringIO),
                patch.dict(sys.modules),
                self.assertRaises(SystemExit) as caught,
            ):
                sys.modules.pop("benchmarks.rbs.context_panel")
                runpy.run_module("benchmarks.rbs.context_panel", run_name="__main__")
            self.assertEqual(caught.exception.code, 0)
