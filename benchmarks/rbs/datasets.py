"""Extract pinned primary measurements without consulting calculator internals.

Optional source-ingestion dependencies: xlrd==2.0.2 and openpyxl==3.1.5. They are
not runtime calculator dependencies. Public fixture evaluation is stdlib only.
"""

import hashlib
import json
from pathlib import Path

from benchmarks.rbs.metrics import cross_partition_overlap

PINS = {
    "standby2014": ("papers/PMC3936740/supp_gkt1139_nar-02492-r-2013-File010.xls",
                    "ee4117e073dcfbc4fad88ff877bf981ad140a0bfa14ee8ae61eb673c4a245345"),
    "salis2009": ("synbiomts/examples/RBS/datasets/Salis_Nat_Biotech_2009.xls",
                  "bd473f0e5ff088f9aa0d9a4c249f8e7188e006c2badd6def8b20efd2dcba2b6c"),
    "footprint2017": ("papers/PMC5435973/supp/nar-03716-r-2016-File008.xlsx",
                      "c4eba651e85ff6cb7802df92d9f68fd5ea5a4ad137697f15c4d22db2967aa243"),
    "mts2020_ic": ("papers/sb0c00394_si_002.xlsx",
                   "b36fed7a13eb2421874f0d9bc52d76866cc64fbd5a94ffc05115f3759210455b"),
    "mts2020_fs": ("papers/sb0c00394_si_003.xlsx",
                   "00446e97b2df76a52c45dce66ec7c9faf1abbbcd2b9a5562c4bbfbf9a2897d75"),
}


def digest(value):
    """SHA-256 of exact bytes, or UTF-8 text without implicit normalization."""
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def write_json(path, value):
    """Write a stable, finite JSON artifact, creating its output directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def source_path(root, identity):
    """Fail closed when a required source is missing or has changed."""
    relative, expected = PINS[identity]
    path = Path(root) / relative
    if digest(path.read_bytes()) != expected:
        raise ValueError(f"Source hash mismatch: {identity}")
    return path


def dna(sequence):
    """Normalize case and RNA U only; reject absent, ambiguous or spaced input."""
    result = sequence.upper().replace("U", "T")
    if not result or set(result) - set("ACGT"):
        raise ValueError("Sequence must contain only A/C/G/T/U")
    return result


def standby_records(rows):
    """Read the 2014 supplement's explicit positions, preserving source row IDs."""
    if rows[4][0] != "Name" or rows[4][5] != "mRNA sequence (from +1 to ATG)":
        raise ValueError("Unexpected 2014 spreadsheet schema")
    cds = dna(rows[2][1])
    result, group, label = [], 0, ""
    for index, row in enumerate(rows[6:], start=7):
        if row[1] and not row[5]:
            group += 1
            label = row[1]
        if not row[5]:
            continue
        leader_start = dna(row[5])
        if not leader_start.endswith("ATG") or not cds.startswith("ATG") or not group:
            raise ValueError("Missing start codon or source family")
        leader = leader_start[:-3]
        result.append({
            "id": "standby2014:" + row[0], "source_row": index,
            "family": f"standby2014:family-{group:02d}", "family_description": label,
            "sequence": leader + cds, "start": len(leader), "utr": leader, "cds": cds,
            "observed": row[6], "observed_sd": row[7], "replicates": int(row[9]),
            "figure_labels": row[3], "published_dg_total": row[13],
            "published_dg_standby": row[18], "apparent_dg_standby": row[10],
            "source_comment": row[32],
        })
    return result


def footprint_records(rows):
    """Extract one copy of 2017 measurements; never multiply across footprint tabs."""
    if rows[4][0] != "ID" or rows[4][3] != "5'UTR Sequence":
        raise ValueError("Unexpected 2017 spreadsheet schema")
    result = []
    for index, row in enumerate(rows[5:32], start=6):
        utr, cds = dna(row[3]), dna(row[4] + row[5])
        if not cds.startswith("ATG"):
            raise ValueError("Unexpected footprint start codon")
        result.append({
            "id": "footprint2017:" + row[0], "source_row": index,
            "family": "footprint2017:shared-template", "description": row[1],
            "sequence": utr + cds, "start": len(utr), "utr": utr, "cds": cds,
            "observed": row[15], "observed_sd": row[16],
            "measurement_status": "not_measured" if row[15] == "N/A" else "available",
            "fluorescence_mean": row[9], "fluorescence_sd": row[10],
            "fluorescence_n": row[11], "mrna_mean": row[12], "mrna_sd": row[13],
            "mrna_n": row[14],
        })
    return result


def freeze(development, heldout):
    """Create an outcome-free study split and quarantine overlapping dev families."""
    ids = [row["id"] for row in development + heldout]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate construct IDs in split")
    hits = cross_partition_overlap(development, heldout)
    flagged_ids = {hit["development_id"] for hit in hits}
    flagged_families = {row["family"] for row in development if row["id"] in flagged_ids}
    records = []
    for partition, rows in [("development", development), ("heldout", heldout)]:
        for row in rows:
            label = "quarantine" if partition == "development" and row["family"] in flagged_families else partition
            window = row["sequence"][max(0, row["start"] - 35):row["start"] + 70]
            records.append({"id": row["id"], "partition": label, "family": row["family"],
                            "source_row": row["source_row"], "start": row["start"],
                            "length": len(row["sequence"]), "sequence_sha256": digest(row["sequence"]),
                            "regulatory_window_sha256": digest(window)})
    return {"schema_version": 1, "protocol": "rbs-evaluation-protocol-20261016-v1",
            "source_sha256": {name: PINS[name][1] for name in ("standby2014", "footprint2017")},
            "similarity_rule": "1 - Levenshtein/max_length >= 0.85 on [-35,+70) from start",
            "cross_partition_hits": hits, "records": records}


def prepare(source_root, public_dir, private_dir):
    """Produce open development data and outcome-free split; seal test data locally."""
    # Imported only for optional ingestion, not public evaluation/tests.
    import openpyxl
    import xlrd

    private_dir = Path(private_dir).resolve()
    repository = Path(__file__).resolve().parents[2]
    if private_dir == repository or repository in private_dir.parents:
        raise ValueError("Restricted measurements must stay outside the repository")
    sheet = xlrd.open_workbook(source_path(source_root, "standby2014")).sheet_by_index(0)
    development = standby_records([sheet.row_values(i) for i in range(sheet.nrows)])
    workbook = openpyxl.load_workbook(source_path(source_root, "footprint2017"), read_only=True, data_only=True)
    heldout = footprint_records(list(workbook["FP = 13"].values))
    workbook.close()
    if len(development) != 136 or len(heldout) != 27:
        raise ValueError("Source construct counts changed")
    split = freeze(development, heldout)
    write_json(Path(public_dir) / "experimental-split.json", split)
    write_json(Path(public_dir) / "standby2014.json", {
        "schema_version": 1, "doi": "10.1093/nar/gkt1139", "licence": "CC-BY-3.0",
        "attribution": "Espah Borujeni, Channarasappa and Salis (2014); Supplementary Data",
        "source_sha256": PINS["standby2014"][1],
        "records": [row for row in development if row["family"] not in {
            item["family"] for item in split["records"] if item["partition"] == "quarantine"}],
    })
    private_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_json(private_dir / "footprint2017.json", {"source_sha256": PINS["footprint2017"][1], "records": heldout})
    (private_dir / "footprint2017.json").chmod(0o600)
    write_json(private_dir / "footprint2017-inputs.json", [
        {key: row[key] for key in ("id", "sequence", "start", "family")} for row in heldout])
    (private_dir / "footprint2017-inputs.json").chmod(0o600)
    return {"development": len(development), "heldout": len(heldout),
            "cross_partition_hits": len(split["cross_partition_hits"]),
            "split_sha256": digest((Path(public_dir) / "experimental-split.json").read_bytes())}
