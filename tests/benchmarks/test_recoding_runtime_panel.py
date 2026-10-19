"""Literal long pairs exercise real codon universes without invoking a scorer."""

import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from benchmarks.recoding import edit_maps as m

PANEL = Path("benchmarks/recoding/runtime-pair-fixtures.json")


class RuntimePairPanelTest(unittest.TestCase):
    def test_literal_codons_maps_full_context_and_unchanged_controls(self):
        panel = json.loads(PANEL.read_bytes())
        self.assertEqual(len(panel["cases"]), 9)
        identity = {
            key + "_sha256": hashlib.sha256(key.encode()).hexdigest()
            for key in ("model", "settings", "backend", "calibration")
        }
        for case in panel["cases"]:
            with self.subTest(pair=case["input"]["pair_id"]):
                pair = case["input"]
                mapped = m.build_map(pair)
                rosters = {}
                for side in ("current", "recoded"):
                    sequence = pair[side]["sequence"]
                    length = len(sequence)
                    found = []
                    for strand in ("+", "-"):
                        oriented = (
                            sequence
                            if strand == "+"
                            else sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]
                        )
                        for i in range(length - 2):
                            codon = oriented[i : i + 3]
                            if codon in ("ATG", "GTG", "TTG"):
                                found.append(
                                    {
                                        "base": i if strand == "+" else length - 1 - i,
                                        "strand": strand,
                                        "codon": codon,
                                    }
                                )
                    self.assertEqual(found, case["expected_rbs_candidates"][side])
                    rosters[side] = [
                        dict(
                            id=f"{side}:{row['strand']}:{row['base']}",
                            base=row["base"],
                            strand=row["strand"],
                            status="ok",
                            score=0.0,
                        )
                        for row in found
                    ]
                    scan = case["promoter_scan"][side]
                    self.assertEqual(scan["range"], [67, length - 19])
                    self.assertEqual(scan["expected_sites_per_strand"], length - 86)
                    for strand in scan["strands"]:
                        for t in range(*scan["range"]):
                            # Every30-state source window is contained. TSS itself
                            # is part of the20-base ITR, not additional padding.
                            self.assertEqual(
                                sum(
                                    t - 37 - d - s >= 0 and t + 20 <= length
                                    for d in range(6, 11)
                                    for s in range(15, 21)
                                ),
                                30,
                            )
                            local = t if strand == "+" else length - 1 - t
                            projection = case["projection"][side]
                            genomic = m.project_base(projection, local, strand, length)
                            direction = (
                                1 if projection["sequence_strand"] == "+" else -1
                            )
                            self.assertEqual(
                                genomic["base"],
                                (projection["origin"] + direction * local)
                                % projection["contig_length"],
                            )
                audit = m.pair_candidates(
                    mapped, rosters["current"], rosters["recoded"], identity, identity
                )
                counts = Counter(
                    row["status"] + (":" + row["reason"] if row["reason"] else "")
                    for row in audit["results"]
                )
                self.assertEqual(dict(counts), case["expected_rbs_accounting"])
                for row in audit["results"]:
                    self.assertEqual(
                        row["delta"], 0.0 if row["status"] == "paired" else None
                    )
                probe = case["feature_probe"]
                feature = m.map_interval(
                    mapped, "current", *probe["interval"], probe["strand"]
                )
                self.assertEqual(feature["mapped_runs"], probe["expected_mapped_runs"])
                self.assertEqual(
                    feature["unmatched_bases"], probe["expected_unmatched_bases"]
                )
                self.assertEqual(
                    feature["contiguous_target_path"], probe["expected_contiguous"]
                )
                unchanged = pair["current"]["sequence"] == pair["recoded"]["sequence"]
                self.assertEqual(unchanged, case["unchanged_sequence_control"])
                if unchanged:
                    self.assertEqual(
                        mapped["current_to_recoded"],
                        list(range(len(pair["current"]["sequence"]))),
                    )
                    self.assertEqual(
                        case["expected_rbs_candidates"]["current"],
                        case["expected_rbs_candidates"]["recoded"],
                    )
