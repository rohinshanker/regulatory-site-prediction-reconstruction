"""Primary Thiel reporter contexts, preserving absent numerical assay outcomes."""

import argparse
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.native import checked_source

PDF_PREFIX = "12934_2018_882_MOESM"


def parse_rbs(xml):
    """Read Table2 typography so an italic insulator suffix is not duplicated."""
    tree = ET.fromstring(xml)
    method = tree.find(".//sec[title='Generating the RBS library']/p")
    if method is None:
        raise ValueError("Missing published RBS assembly method")
    match = re.search(r"5′-([ACGT]{27})-3′", "".join(method.itertext()))
    if match is None:
        raise ValueError("Missing exact published 27nt insulator")
    insulator = match.group(1)
    result = {}
    for index, row in enumerate(tree.findall(".//table-wrap[@id='Tab2']//tbody/tr"), 1):
        cell = row.find("td")
        name = cell.text
        sequence = "".join(list(cell.itertext())[1:])
        italic = cell.find("italic")
        suffix = "".join(italic.itertext()) if italic is not None else ""
        if (
            name in result
            or not re.fullmatch("[ACGT]{25}", sequence)
            or not sequence.endswith("ATG")
            or not insulator.endswith(suffix)
        ):
            raise ValueError("Unexpected Table2 sequence, identity or italic suffix")
        leader = insulator + sequence[:-3][len(suffix) :]
        result[name] = {
            "rbs_id": name,
            "source_table_row": index,
            "upstream22": sequence[:-3],
            "italic_insulator_suffix": suffix,
            "leader": leader,
            "leader_sha256": digest(leader),
        }
    if not result:
        raise ValueError("Missing Table2 RBS rows")
    return result


def parse_insert(text):
    """Extract the published contiguous insert; expose the conditional GFP boundary."""
    insert = "".join(
        line.strip()
        for line in text.splitlines()
        if re.fullmatch("[ACGT]+", line.strip())
    )
    if (
        len(insert) != 1514
        or not insert.startswith("ATGCAT")
        or insert[720:726] != "GCTAGC"
        or insert[-6:] != "CTCGAG"
    ):
        raise ValueError("Published synthetic insert boundaries differ")
    gfp = insert[:720]
    stops = [
        i for i in range(0, len(gfp), 3) if gfp[i : i + 3] in {"TAA", "TAG", "TGA"}
    ]
    if stops != [717]:
        raise ValueError("Conditional GFP CDS must have only its terminal stop")
    return gfp, {
        "insert_sha256": digest(insert),
        "gfp_cds_sha256": digest(gfp),
        "gfp_interval": [0, 720],
        "start_interpretation": (
            "leading ATG overlaps NsiI; clone-specific sequence verification absent"
        ),
    }


def construct_records(rbs, gfp, text):
    """Retain all constructed reporter combinations and unavailable measurements."""
    records, seen = [], set()
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0] not in rbs:
            continue
        if len(fields) not in {3, 4}:
            raise ValueError("Unexpected construct-table column count")
        identity = fields[0]
        for reporter, name in zip(
            ("sYFP2", "GFPmut3b", "efe"), fields[1:], strict=False
        ):
            key = "Thiel2018:" + identity + ":" + reporter
            if key in seen or "(" + identity + ")" not in name:
                raise ValueError("Duplicate or inconsistent construct identity")
            seen.add(key)
            leader = rbs[identity]["leader"]
            sequence = leader + gfp if reporter == "GFPmut3b" else None
            records.append(
                {
                    "id": key,
                    "rbs_id": identity,
                    "reporter": reporter,
                    "source_construct_name": name,
                    "source_table_row": rbs[identity]["source_table_row"],
                    "host": "Synechocystis sp. PCC6803",
                    "sequence": sequence,
                    "full_transcript_sequence": None,
                    "sequence_sha256": digest(sequence) if sequence else None,
                    "start": len(leader) if sequence else None,
                    "window_35up_70cds": leader[-35:] + gfp[:70] if sequence else None,
                    "sequence_status": "assembly_interpretation_not_clone_verified"
                    if sequence
                    else "exact_synthesized_reporter_junction_unavailable",
                    "family": "shared_" + reporter + "_reporter",
                    "borrowed_series": identity in {"A", "B", "C", "D", "E", "Z"},
                    "observed": None,
                    "measurement_status": "not_tabulated",
                    "quantity": (
                        "OD750-normalized reporter fluorescence or product; "
                        "not matched RNA-normalized TE"
                    ),
                    "no_plot_digitization": True,
                }
            )
    return sorted(records, key=lambda row: row["id"])


def prepare(root, output):
    """Verify article/all7 supplements and extract contexts using system Poppler."""
    xml = checked_source(root, "thiel2018-article.xml")
    for i in range(1, 8):
        checked_source(root, f"{PDF_PREFIX}{i}_ESM.pdf")
    texts = [
        subprocess.check_output(
            ["pdftotext", "-layout", str(Path(root) / f"{PDF_PREFIX}{i}_ESM.pdf"), "-"],
            text=True,
        )
        for i in (1, 2)
    ]
    rbs = parse_rbs(xml)
    gfp, boundaries = parse_insert(texts[0])
    records = construct_records(rbs, gfp, texts[1])
    counts = dict(Counter(row["reporter"] for row in records))
    if len(rbs) != 13 or counts != {"sYFP2": 13, "GFPmut3b": 13, "efe": 6}:
        raise ValueError("Published reporter construct universe differs")
    result = {
        "schema_version": "rbs-reporter-context-1",
        "study": "Thiel2018",
        "doi": "10.1186/s12934-018-0882-2",
        "source_article_sha256": digest(xml),
        "rights": (
            "CC-BY-4.0 article/supplements; "
            "cite Thiel et al.2018; original source preserved"
        ),
        "admission": "context/provenance only; no exact tabulated strength outcomes",
        "n_constructs": len(records),
        "reporter_counts": counts,
        "boundaries": boundaries,
        "rbs": list(rbs.values()),
        "records": records,
    }
    write_json(output, result)
    return {
        "n_constructs": len(records),
        "n_assembly_interpreted_contexts": 13,
        "n_numerical_measurements": 0,
        "output_sha256": digest(Path(output).read_bytes()),
    }


def main(argv=None):
    """Create a redistributable context manifest, never invented fluorescence values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.root, args.output)))


if __name__ == "__main__":
    main()
