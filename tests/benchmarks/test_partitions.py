"""Outcome-blind graph, similarity and deterministic split tests."""

import gzip
import io
import json
import runpy
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import partitions


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.features = [
            {
                "type": "CDS",
                "attributes": {"locus_tag": name},
                "replicon": "chr",
                "start_zero_based": 100 + index * 50,
                "strand": "+",
            }
            for index, name in enumerate(("a", "b", "c"))
        ]
        self.envelope = {
            "genomes": {"chr": {"sequence": "ACGT" * 100}},
            "records": [
                {
                    "id": "source:" + name,
                    "source_orf": name,
                    "current_locus_tag": locus,
                    "sequence_sha256": "hash",
                    "mapping_status": "matched" if locus else "unmatched",
                    "primary_eligible": bool(locus),
                }
                for name, locus in (("a", "a"), ("b", "b"), ("unknown", None))
            ],
        }

    def test_similarity_is_exact_and_nonempty(self):
        self.assertEqual(partitions.normalized_edit_similarity("ACGT", "ACGT"), 1)
        self.assertEqual(partitions.normalized_edit_similarity("ACGT", "AGT"), 0.75)
        self.assertEqual(partitions.normalized_edit_similarity("ACGT", "ACGA"), 0.75)
        for a, b in (("", "A"), ("A", "")):
            with self.assertRaises(ValueError):
                partitions.normalized_edit_similarity(a, b)
        self.assertEqual(
            partitions.sequence_edges(
                {"a": "ACGT", "b": "ACGA", "c": "TTTT"}, threshold=0.75
            ),
            [("a", "b")],
        )
        for bad in (True, -1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                partitions.sequence_edges({}, threshold=bad)

    def test_homology_thresholds_self_hits_and_invalid_values(self):
        good = "a\tb\t30\t0.8\t0.8\t0.00001\t10"
        text = "\n".join(
            [
                good,
                good.replace("a\tb", "b\ta"),
                good.replace("a\tb", "a\ta"),
                good.replace("\t30\t", "\t29\t"),
                good.replace("0.8", "0.79", 1),
                good.replace("0.00001", "0.001"),
            ]
        )
        self.assertEqual(partitions.homology_edges(text), [("a", "b")])
        bad = [
            "",
            "a\tb",
            good.replace("a\tb", "\tb"),
            good.replace("30", "nan"),
            good.replace("30", "101"),
            good.replace("0.8", "2", 1),
            good.replace("0.00001", "-1"),
            good[:-2] + "0",
            "a\tb\t30\t0.8\t2\t0\t10",
        ]
        for value in bad[1:]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                partitions.homology_edges(value)
        self.assertEqual(partitions.homology_edges(""), [])

    def test_connected_components_include_transitive_bridges_and_singletons(self):
        groups = partitions.components(
            ["d", "c", "b", "a"], [("c", "b"), ("a", "b"), ("c", "a"), ("c", "c")]
        )
        self.assertEqual(groups, [["a", "b", "c"], ["d"]])
        for nodes, edges in [
            (["a", "a"], []),
            ([""], []),
            ([1], []),
            (["a"], [("a", "b")]),
        ]:
            with self.assertRaises(ValueError):
                partitions.components(nodes, edges)
        self.assertEqual(partitions.components([], []), [])

    def test_component_hashes_and_all_three_partitions_are_repeatable(self):
        groups = [[f"gene{i}"] for i in range(100)]
        assignments, records = partitions.partition_components(groups)
        self.assertEqual(
            set(r["partition"] for r in records),
            {"development_train", "development_validation", "final"},
        )
        self.assertEqual(
            partitions.partition_components(groups), (assignments, records)
        )
        self.assertTrue(all(len(r["id"]) == 64 for r in records))

    def test_full_annotation_bridges_and_unknowns_are_frozen_without_outcomes(self):
        text = "a\tc\t50\t1\t1\t0\t100\nc\tb\t50\t1\t1\t0\t100"
        result = partitions.freeze(
            self.envelope, self.features, text, similarity=lambda a, b: 0
        )
        self.assertEqual(result["n_annotation_loci"], 3)
        self.assertEqual(result["n_groups"], 2)
        self.assertEqual(result["n_homology_edges"], 2)
        self.assertEqual(result["n_near_context_edges"], 0)
        self.assertEqual(result["records"][0]["group"], result["records"][1]["group"])
        self.assertTrue(result["no_outcome_values_read"])
        other = deepcopy(self.envelope)
        for row in other["records"]:
            row["hidden_outcome"] = 1e9
        self.assertEqual(
            result,
            partitions.freeze(other, self.features, text, similarity=lambda a, b: 0),
        )
        self.assertEqual(sum(result["primary_partition_counts"].values()), 2)
        self.assertEqual(sum(result["primary_group_counts"].values()), 1)

    def test_duplicate_inputs_and_compound_models(self):
        self.features.append(self.features[0])
        result = partitions.freeze(
            self.envelope, self.features, "", similarity=lambda a, b: 1
        )
        self.assertEqual(result["n_contexts_compared"], 2)
        self.assertEqual(result["n_near_context_edges"], 1)
        self.assertEqual(
            result["near_context_edges_by_window"], {"200nt": 1, "105nt": 1, "30nt": 1}
        )
        self.envelope["records"].append(self.envelope["records"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            partitions.freeze(
                self.envelope, self.features, "", similarity=lambda a, b: 0
            )

    def test_cli_regular_optional_acceleration_and_entrypoint(self):
        inputs, homology, output = [
            self.root / name for name in ("inputs.json", "homology.tsv", "splits.json")
        ]
        inputs.write_text(json.dumps(self.envelope))
        homology.write_text("")
        module = types.ModuleType("rapidfuzz.distance.Levenshtein")
        module.normalized_similarity = partitions.normalized_edit_similarity
        modules = {
            "rapidfuzz": types.ModuleType("rapidfuzz"),
            "rapidfuzz.distance": types.ModuleType("rapidfuzz.distance"),
            "rapidfuzz.distance.Levenshtein": module,
        }
        hashes = []
        for flag in ([], ["--rapidfuzz"]):
            with (
                patch.object(
                    partitions, "checked_source", return_value=gzip.compress(b"gff")
                ),
                patch.object(partitions, "gff_features", return_value=self.features),
                patch.dict(sys.modules, modules),
                redirect_stdout(io.StringIO()) as result,
            ):
                partitions.main(
                    [str(self.root), str(inputs), str(homology), str(output), *flag]
                )
            self.assertEqual(json.loads(result.getvalue())["n_homology_edges"], 0)
            hashes.append(output.read_bytes())
        self.assertEqual(hashes[0], hashes[1])
        with (
            patch.object(sys, "argv", ["partitions", "--help"]),
            redirect_stdout(io.StringIO()),
            self.assertWarns(RuntimeWarning),
            self.assertRaises(SystemExit) as context,
        ):
            runpy.run_module("benchmarks.rbs.partitions", run_name="__main__")
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
