"""Private v3 small-protein TIS admission and outcome-blind stop-query export."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.karlsen import private_directory
from benchmarks.rbs.position import STOPS, stop_query, true_index

SOURCE_SHA256 = "c5ce6b83aae56f696a936f31af244277511115947e6003fb8ec4bcff3bee569a"
SOURCE_URL = "https://www.biorxiv.org/content/biorxiv/early/2026/07/30/2025.12.20.695498/DC4/embed/media-4.xlsx"


def extract(rows, genomes):
    """Keep author evidence tiers separate and derive queries using terminal stops."""
    queries, labels, audit = [], [], Counter()
    seen = set()
    for row_number, row in enumerate(rows, 4):
        identifier = row[0]
        match = re.fullmatch(r"([^:]+):(\d+)-(\d+):([+-])", identifier)
        if not match:
            raise ValueError("Unexpected source coordinate identifier")
        replicon, left, right, strand = match.groups()
        left, right = int(left), int(right)
        if (left, right, strand) != (row[2], row[3], row[4]):
            raise ValueError("Source identifier and coordinate columns disagree")
        reference = genomes[replicon]["sequence"]
        if not 1 <= left <= right <= len(reference):
            raise ValueError("Source interval outside pinned genome")
        stop = right - 3 if strand == "+" else left + 1
        key = f"{replicon}:{strand}:{stop}"
        identity = "tis-stop:" + digest(key)
        if identity in seen:
            raise ValueError(
                "Duplicate source stop query requires explicit adjudication"
            )
        seen.add(identity)
        sign = 1 if strand == "+" else -1
        terminal = "".join(
            reference[(stop + sign * i) % len(reference)] for i in range(3)
        )
        if strand == "-":
            terminal = terminal.translate(str.maketrans("ACGT", "TGCA"))
        if terminal in STOPS:
            query = stop_query(reference, stop, strand)
            query["admission_status"] = "extractable"
        else:
            query = {
                "sequence": None,
                "start_positions": [],
                "genomic_stop_first_zero_based": stop,
                "genomic_strand": strand,
                "admission_status": "unsupported_nonstop_source_anchor",
            }
            audit["unsupported_nonstop_source_anchor"] += 1
        query.update(
            id=identity,
            genome_id=replicon,
            host="Synechocystis PCC6803 PCC-M",
            temperature_c=30,
            anti_sd="ACCUCCUUU",
        )
        queries.append(query)
        start = left - 1 if strand == "+" else right - 1
        position = (
            true_index(query, start, len(reference))
            if query["admission_status"] == "extractable"
            else None
        )
        length = right - left + 1
        sequence = "".join(
            reference[(start + sign * i) % len(reference)] for i in range(length)
        )
        if strand == "-":
            sequence = sequence.translate(str.maketrans("ACGT", "TGCA"))
        matches = (
            row[69] is not None and sequence == row[69] and sequence[:3] == row[66]
        )
        raw_tier = str(row[41]).strip().lower()
        tiers = {"yes": "plain", "yes (weak)": "weak", "no": "unlabelled"}
        if raw_tier not in tiers:
            raise ValueError("Unknown author TIS support flag")
        tier = tiers[raw_tier]
        eligible = matches and sequence[-3:] in STOPS and length % 3 == 0
        labels.append(
            {
                "id": identity,
                "tier": "positive"
                if tier != "unlabelled" and eligible
                else "unlabelled",
                "starts": [position] if position is not None else [],
                "source_tier": tier,
                "source_sequence_verified": eligible,
                "source_row": row_number,
                "source_identifier": identifier,
                "source_locus_tag": row[5],
                "source_file_sha256": SOURCE_SHA256,
                "genomic_start_zero_based": start,
                "negative_label": None,
                "evidence": (
                    "author reported support at annotated start; "
                    "no raw-read revalidation"
                ),
            }
        )
        audit[tier] += 1
        audit[tier + "_verified_sequence"] += eligible
        audit["positive_outside_candidates"] += (
            tier != "unlabelled"
            and eligible
            and position not in query["start_positions"]
        )
    queries.sort(key=lambda row: row["id"])
    labels.sort(key=lambda row: row["id"])
    return queries, labels, dict(audit)


def prepare(workbook_path, genome_envelope, output):
    """Preserve restricted raw evidence privately; export no outcome-bearing IDs."""
    import openpyxl

    output = private_directory(output)
    raw = Path(workbook_path).read_bytes()
    if digest(raw) != SOURCE_SHA256:
        raise ValueError("TIS workbook differs from pinned v3 artifact")
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    rows = list(workbook["Table_S4"].values)[3:]
    workbook.close()
    envelope = json.loads(Path(genome_envelope).read_text())
    if any(
        digest(row["sequence"]) != row["sequence_sha256"]
        for row in envelope["genomes"].values()
    ):
        raise ValueError("Genome sequence differs from declared hash")
    queries, labels, counts = extract(rows, envelope["genomes"])
    inputs = {
        "schema_version": "rbs-stop-query-1",
        "records": queries,
        "source_sha256": SOURCE_SHA256,
        "source_url": SOURCE_URL,
        "labels_withheld": True,
        "source_row_order_withheld": True,
        "ascertainment": (
            "all165 source annotated-small-protein stop anchors, including unlabelled"
        ),
        "input_genome_sha256": {
            key: row["sequence_sha256"] for key, row in envelope["genomes"].items()
        },
    }
    for name, payload in [
        ("tis-inputs.json", inputs),
        ("tis-labels-private.json", labels),
        ("tis-admission-audit.json", counts),
    ]:
        write_json(output / name, payload)
        (output / name).chmod(0o600)
    return {
        "counts": counts,
        "input_sha256": digest((output / "tis-inputs.json").read_bytes()),
        "n_queries": len(queries),
        "n_candidates": sum(len(r["start_positions"]) for r in queries),
    }


def main(argv=None):
    """Read pinned v3 evidence without rewriting it or executing a prediction model."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("workbook", "genome_envelope", "private_output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.workbook, args.genome_envelope, args.private_output)))


if __name__ == "__main__":
    main()
