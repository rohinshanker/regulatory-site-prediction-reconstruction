"""Schema, source integrity, licence boundary and frozen split checks."""

import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from benchmarks.rbs import datasets
from benchmarks.rbs.fetch import fetch

ROOT = Path(__file__).resolve().parents[2]


def standby_rows():
    rows = [[""] * 33 for _ in range(9)]
    rows[2][1] = "ATGAAA"
    rows[4][0], rows[4][5] = "Name", "mRNA sequence (from +1 to ATG)"
    rows[6][1] = "Source-design family"
    rows[7][0], rows[7][5], rows[7][9] = "5'UTR_1", "AAATG", 3
    rows[7][6], rows[7][7] = 10, 2
    return rows


def footprint_rows():
    rows = [[None] * 35 for _ in range(6)]
    rows[4][0], rows[4][3] = "ID", "5'UTR Sequence"
    rows[5][0:6] = ["AEB-1", "control", "1", "AAAA", "ATG", "CCC"]
    return rows


class DataTest(unittest.TestCase):
    def test_dna_and_hash(self):
        self.assertEqual(datasets.dna("aug"), "ATG")
        self.assertEqual(datasets.digest("a"), datasets.digest(b"a"))
        for seq in ("", "A N", "AX", "AA\n"):
            with self.assertRaises(ValueError):
                datasets.dna(seq)

    def test_source_hash_and_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.json"
            datasets.write_json(path, {"a": 1})
            self.assertEqual(path.read_text(), '{\n  "a": 1\n}\n')
            with patch.dict(
                datasets.PINS, test=("x.json", datasets.digest(path.read_bytes()))
            ):
                self.assertEqual(datasets.source_path(temporary, "test"), path)
                path.write_text("changed")
                with self.assertRaises(ValueError):
                    datasets.source_path(temporary, "test")
            with self.assertRaises(ValueError):
                datasets.write_json(path, {"a": float("nan")})

    def test_primary_schema_extraction(self):
        rows = standby_rows()
        result = datasets.standby_records(rows)[0]
        self.assertEqual(result["sequence"], "AAATGAAA")
        self.assertEqual(result["start"], 2)
        self.assertEqual(result["source_row"], 8)
        self.assertEqual(result["family"], "standby2014:family-01")
        changed = copy.deepcopy(rows)
        changed[4][0] = "changed"
        with self.assertRaises(ValueError):
            datasets.standby_records(changed)
        rows[7][5] = "AAATA"
        with self.assertRaises(ValueError):
            datasets.standby_records(rows)
        rows = footprint_rows()
        self.assertEqual(datasets.footprint_records(rows)[0]["sequence"], "AAAAATGCCC")
        rows[5][15] = "N/A"
        self.assertEqual(
            datasets.footprint_records(rows)[0]["measurement_status"], "not_measured"
        )
        rows[5][4] = "AAA"
        with self.assertRaises(ValueError):
            datasets.footprint_records(rows)
        rows[4][0] = "changed"
        with self.assertRaises(ValueError):
            datasets.footprint_records(rows)

    def test_quarantine_entire_development_family(self):
        def row(key, sequence, family):
            return dict(id=key, sequence=sequence, start=0, source_row=1, family=family)

        dev = [
            row("a", "ATGAAAA", "x"),
            row("b", "CCCCCCC", "x"),
            row("c", "GGGGGGG", "y"),
        ]
        heldout = [row("d", "ATGAAAA", "z")]
        result = datasets.freeze(dev, heldout)
        self.assertEqual(
            [r["partition"] for r in result["records"]],
            ["quarantine", "quarantine", "development", "heldout"],
        )
        self.assertNotIn("observed", json.dumps(result))
        with self.assertRaises(ValueError):
            datasets.freeze(dev, dev)

    def test_shipped_split_and_open_data(self):
        split_bytes = (ROOT / "benchmarks/rbs/experimental-split.json").read_bytes()
        self.assertEqual(
            datasets.digest(split_bytes),
            "2e07f821019e1e295b39bf8c70bd123b80d3b4625639b762cbf9a6474af02e93",
        )
        split = json.loads(split_bytes)
        self.assertEqual(len(split["records"]), 163)
        self.assertEqual(split["cross_partition_hits"], [])
        data = json.loads((ROOT / "benchmarks/rbs/standby2014.json").read_text())
        self.assertEqual(data["licence"], "CC-BY-3.0")
        self.assertEqual(len(data["records"]), 136)
        identities = {r["id"]: r for r in split["records"]}
        for row in data["records"]:
            self.assertEqual(
                datasets.digest(row["sequence"]),
                identities[row["id"]]["sequence_sha256"],
            )
            self.assertEqual(row["sequence"][row["start"] : row["start"] + 3], "ATG")

    def test_fetch_integrity_and_cached_no_network(self):
        payload = b"test artifact"
        blob = io.BytesIO()
        with zipfile.ZipFile(blob, "w") as archive:
            archive.writestr("chosen.txt", payload)
            archive.writestr("../do-not-extract", b"unselected")
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(datasets.PINS, test=("nested/source", datasets.digest(payload))),
            patch(
                "benchmarks.rbs.fetch.SOURCES",
                {"test": ("https://example.test", ("chosen.txt",))},
            ),
            patch(
                "urllib.request.urlopen", return_value=io.BytesIO(blob.getvalue())
            ) as get,
        ):
            self.assertEqual(
                fetch(temporary, ["test"])["test"], datasets.digest(payload)
            )
            self.assertEqual((Path(temporary) / "nested/source").read_bytes(), payload)
            fetch(temporary, ["test"])
            self.assertEqual(get.call_count, 1)
            (Path(temporary) / "nested/source").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                fetch(temporary, ["test"])
        with self.assertRaises(ValueError):
            fetch(ROOT / "restricted", [])

    def test_live_panel_coordinates_and_hashes(self):
        panel = json.loads(
            (ROOT / "benchmarks/rbs/live-diagnostic-panel.json").read_text()
        )
        self.assertEqual(len(panel["records"]), panel["maximum_jobs"])
        self.assertEqual(len({r["id"] for r in panel["records"]}), 12)
        for row in panel["records"]:
            self.assertEqual(datasets.digest(row["sequence"]), row["sequence_sha256"])
            start = row["selected_start_zero_based"]
            if start is not None:
                self.assertIn(
                    row["sequence"][start : start + 3], ["ATG", "GTG", "TTG", "CTG"]
                )
            else:
                self.assertFalse(
                    any(c in row["sequence"] for c in ["ATG", "GTG", "TTG", "CTG"])
                )


if __name__ == "__main__":
    unittest.main()
