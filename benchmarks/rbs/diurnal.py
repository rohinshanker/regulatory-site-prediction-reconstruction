"""Private secondary diurnal TE proxy with source-boundary and frozen-group joins."""

import argparse
import csv
import gzip
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.karlsen import annotation_index, genomic_context, private_directory
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.native import checked_source, gff_features

PHASES = ("BRISE", "ARISE", "MDAY", "BSET", "ASET")
WORKBOOK_SHA256 = "38b907068044f28030d7e7e029e9bc35441a18548ae3ebc0ff56c45c956a54c4"


def source_coordinates(text):
    """Use coordinate facts only; reject conflicting repeated gene/sample records."""
    result = {}
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        identity = (
            row["Sequence"],
            int(row["Start"]),
            int(row["End"]),
            row["strand"],
            int(row["Length"]),
        )
        if row["Name"] in result and result[row["Name"]] != identity:
            raise ValueError("Conflicting source gene boundaries")
        result[row["Name"]] = identity
    return result


def source_measurements(rna_rows, rpf_rows):
    """Derive geometric-mean abundance ratios, never claim paired-replicate TE."""
    expected = ["Name"] + ["Mean_log2RPKM_" + phase for phase in PHASES]
    if rna_rows[0][:6] != expected or rpf_rows[0][:6] != expected:
        raise ValueError("Unexpected diurnal workbook headers")
    rna = {row[0]: (index, row) for index, row in enumerate(rna_rows[1:], 2)}
    rpf = {row[0]: (index, row) for index, row in enumerate(rpf_rows[1:], 2)}
    if (
        len(rna) != len(rna_rows) - 1
        or len(rpf) != len(rpf_rows) - 1
        or set(rna) != set(rpf)
    ):
        raise ValueError("Duplicate or mismatched RNA/RPF gene identities")
    result = []
    for name in sorted(rna):
        for column, phase in enumerate(PHASES, 1):
            first, second = rna[name][1][column], rpf[name][1][column]
            if first is None or second is None:
                observed = None
            else:
                if not finite_number(first) or not finite_number(second):
                    raise ValueError(
                        "Source log abundances must be finite numeric values"
                    )
                try:
                    observed = 2 ** (second - first)
                except OverflowError as error:
                    raise ValueError("Derived abundance ratio overflow") from error
                if not finite_number(observed) or observed <= 0:
                    raise ValueError(
                        "Derived abundance ratio outside positive finite range"
                    )
            result.append(
                {
                    "id": "diurnal2021:" + name + ":" + phase,
                    "input_id": "diurnal2021:" + name,
                    "source_orf": name,
                    "condition": phase,
                    "observed": observed,
                    "measurement_status": "positive"
                    if observed is not None
                    else "missing",
                    "source_rna_row": rna[name][0],
                    "source_rpf_row": rpf[name][0],
                    "source_column": column + 1,
                    "source_file_sha256": WORKBOOK_SHA256,
                    "quantity": (
                        "ratio of condition-level geometric means of "
                        "sum-scaled RPF and RNA abundance"
                    ),
                    "paired_replicate_ratio": False,
                }
            )
    return result


def input_records(names, coordinates, genomes, features, splits):
    """Require exact original/current CDS bounds; inherit full-annotation groups."""
    aliases, cds = annotation_index(features)
    groups = {
        member: {"group": group["id"], "partition": group["partition"]}
        for group in splits["groups"]
        for member in group["members"]
    }
    result = []
    for name in sorted(names):
        record = {
            "id": "diurnal2021:" + name,
            "source_orf": name,
            "study": "Karlsen2021_diurnal",
            "host": "Synechocystis sp. PCC6803",
            "temperature_celsius": 30,
            "anti_sd": "ACCUCCUUU",
            "anti_sd_provenance": "pinned current annotated 16S terminal9nt scenario",
            "tss_zero_based": None,
            "cds_start_zero_based": None,
            "upstream_limit_nt": 100,
            "downstream_length_nt": 100,
            "conditions": list(PHASES),
            "primary_eligible": False,
            "sequence": None,
            "sequence_sha256": None,
            "strand": "+",
            "genomic_strand": None,
            "current_locus_tag": None,
            "group": None,
            "partition": None,
            "mapping_status": "unmatched_identifier",
            "warnings": ["genomic_flanks_not_measured_transcript_boundaries"],
        }
        targets = {name} if name in cds else aliases.get(name, set())
        if len(targets) > 1:
            record["mapping_status"] = "ambiguous_identifier"
        elif targets:
            locus = next(iter(targets))
            record["current_locus_tag"] = locus
            if locus not in groups:
                raise ValueError("Current locus absent from frozen annotation groups")
            record.update(groups[locus])
            models = cds.get(locus, [])
            if len(models) != 1:
                record["mapping_status"] = "nonunique_or_absent_current_cds"
            else:
                feature = models[0]
                lower, upper = feature["interval"]
                attrs = feature["attributes"]
                current = (
                    feature["replicon"],
                    lower + 1,
                    upper,
                    feature["strand"],
                    upper - lower,
                )
                if coordinates.get(name) != current:
                    record["mapping_status"] = "source_current_bounds_disagree"
                elif (
                    attrs.get("pseudo") == "true"
                    or feature["phase"] != "0"
                    or attrs.get("partial") == "true"
                    or attrs.get("exception")
                ):
                    record["mapping_status"] = "exceptional_current_cds"
                else:
                    replicon = feature["replicon"]
                    start = feature["start_zero_based"]
                    strand = feature["strand"]
                    context = genomic_context(
                        genomes[replicon]["sequence"], start, strand
                    )
                    record.update(
                        mapping_status="exact_source_and_current_cds",
                        genome_id=replicon,
                        genomic_strand=strand,
                        cds_start_zero_based=start,
                        sequence=context,
                        sequence_sha256=digest(context),
                        start_position=100,
                        primary_eligible=replicon == "NC_000911.1",
                    )
        result.append(record)
    return result


def prepare(root, genome_envelope, split_path, output):
    """Keep all secondary outcomes private; freeze eligibility before model results."""
    import openpyxl

    output = private_directory(output)
    archive = checked_source(root, "diurnal2021-supp.zip")
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        raw = zipped.read("Table_1.xlsx")
    if digest(raw) != WORKBOOK_SHA256:
        raise ValueError("Diurnal workbook member identity mismatch")
    workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    rna = [list(row) for row in workbook["RNA seq"].values]
    rpf = [list(row) for row in workbook["Ribosome profiling"].values]
    workbook.close()
    measurements = source_measurements(rna, rpf)
    coordinates = source_coordinates(
        checked_source(root, "diurnal2021-source-coordinates.tab").decode()
    )
    envelope = json.loads(Path(genome_envelope).read_text())
    genomes = envelope["genomes"]
    if any(
        digest(row["sequence"]) != row["sequence_sha256"] for row in genomes.values()
    ):
        raise ValueError("Genome sequence hash mismatch")
    features = gff_features(
        gzip.decompress(checked_source(root, "pcc6803-genomic.gff.gz")).decode(),
        {key: r["sequence"] for key, r in genomes.items()},
    )
    split_bytes = Path(split_path).read_bytes()
    splits = json.loads(split_bytes)
    inputs = input_records(
        {row["source_orf"] for row in measurements},
        coordinates,
        genomes,
        features,
        splits,
    )
    index = {r["id"]: r for r in inputs}
    for row in measurements:
        for key in ("group", "partition", "primary_eligible"):
            row[key] = index[row["input_id"]][key]
    audit = {
        "n_source_genes": len(inputs),
        "n_condition_records": len(measurements),
        "mapping_status": dict(Counter(r["mapping_status"] for r in inputs)),
        "primary_partition_counts": dict(
            Counter(r["partition"] for r in inputs if r["primary_eligible"])
        ),
        "n_primary_genes": sum(r["primary_eligible"] for r in inputs),
        "frozen_split_sha256": digest(split_bytes),
        "eligibility_independent_of_model_output": True,
    }
    payload = {
        "schema_version": "rbs-diurnal-contexts-1",
        "sequence_orientation": (
            "transcript; strand is scoring orientation, genomic_strand is provenance"
        ),
        "genomes": genomes,
        "records": inputs,
        "source_workbook_sha256": WORKBOOK_SHA256,
        "frozen_split_sha256": digest(split_bytes),
    }
    for name, value in [
        ("diurnal-inputs.json", payload),
        ("diurnal-outcomes-private.json", measurements),
        ("diurnal-admission-audit.json", audit),
    ]:
        write_json(output / name, value)
        (output / name).chmod(0o600)
    return {
        **audit,
        "input_sha256": digest((output / "diurnal-inputs.json").read_bytes()),
    }


def main(argv=None):
    """Prepare the pinned secondary study without exposing labels to training."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "genome_envelope", "splits", "private_output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            prepare(args.root, args.genome_envelope, args.splits, args.private_output)
        )
    )


if __name__ == "__main__":
    main()
