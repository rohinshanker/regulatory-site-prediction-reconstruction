"""Primary Karlsen TE admission with exact annotation aliases and private outcomes."""

import argparse
import gzip
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

from benchmarks.rbs.datasets import digest, write_json
from benchmarks.rbs.metrics import finite_number
from benchmarks.rbs.native import (
    COMPLEMENT,
    checked_source,
    fasta_records,
    gff_features,
    manifest,
    rrna_tail_evidence,
)

HEADERS = [
    "Name",
    "RPF RPKM, -5 min",
    "RPF RPKM, 24 h",
    "RPF RPKM, absolute change",
    "RNA RPKM, -5 min",
    "RNA RPKM, 24 h",
    "Log2 FC RPF RPKM",
    "Log2 FC RNA RPKM",
    "TE, -5 min",
    "TE, 24 h",
    "Log2 FC TE",
]
PROTEIN_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"


def assay_value(value):
    """Keep missing and reported zero TE distinct; never invent a detection limit."""
    if value is None or value == "NA":
        return {"value": None, "status": "missing", "log_eligible": False}
    if not finite_number(value) or value < 0:
        raise ValueError("TE must be a finite nonnegative number or declared missing")
    return {
        "value": value,
        "status": "positive" if value > 0 else "reported_zero",
        "log_eligible": value > 0,
    }


def annotation_index(features):
    """Index exact current/old locus tags from the same pinned annotation."""
    aliases, cds = defaultdict(set), defaultdict(list)
    for feature in features:
        attrs = feature["attributes"]
        locus = attrs.get("locus_tag")
        if not locus:
            continue
        if feature["type"] in {"gene", "pseudogene"}:
            for alias in attrs.get("old_locus_tag", "").split(","):
                if alias:
                    aliases[alias].add(locus)
        elif feature["type"] == "CDS":
            cds[locus].append(feature)
    return aliases, cds


def genomic_context(sequence, start, strand, upstream=100, downstream=100):
    """Independent supplied-start context for leakage checks, on circular references.

    This does not infer a TSS or implement a scoring/window-selection algorithm.
    Every reference here is explicitly circular; the flanks are assumptions.
    """
    if (
        type(start) is not int
        or not 0 <= start < len(sequence)
        or strand not in {"+", "-"}
        or type(upstream) is not int
        or type(downstream) is not int
        or upstream < 0
        or downstream < 3
        or upstream + downstream > len(sequence)
    ):
        raise ValueError("Invalid independent circular context coordinates")
    sign = 1 if strand == "+" else -1
    result = "".join(
        sequence[(start + sign * offset) % len(sequence)]
        for offset in range(-upstream, downstream)
    )
    return result if strand == "+" else result.translate(COMPLEMENT)


def karlsen_records(rows, sequences, features, proteins):
    """Separate source inputs from measured outcomes before partition assignment."""
    if rows[2][:11] != HEADERS:
        raise ValueError("Unexpected Karlsen Table S2 schema")
    aliases, cds = annotation_index(features)
    inputs, outcomes, seen = [], [], set()
    for index, row in enumerate(rows[3:], start=4):
        name = row[0]
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("Missing or duplicate source ORF identifier")
        seen.add(name)
        identity = "karlsen2018:" + name
        record = {
            "id": identity,
            "study": "Karlsen2018",
            "source_orf": name,
            "source_sheet": "Table S2",
            "source_row": index,
            "host": "Synechocystis sp. PCC 6803",
            "temperature_celsius": 30,
            "tss_zero_based": None,
            "cds_start_zero_based": None,
            "transcript_start_evidence": "unmeasured; 100-nt genomic flank assumption",
            "translation_start_evidence": "current annotation; not measured TIS",
            "upstream_limit_nt": 100,
            "downstream_length_nt": 100,
            "leader_length_nt": None,
            "source_start_zero_based": None,
            "source_start_distance_nt": None,
            "source_current_start_delta_nt": None,
            "origin_crossing": False,
            "mapping_status": "unmatched_identifier",
            "warnings": ["paper_era_annotation_not_recovered"],
            "source_flags": [],
            "primary_eligible": False,
            "current_locus_tag": None,
            "sequence": None,
            "sequence_sha256": None,
            "protein_sha256": None,
            "conditions": ["HC_minus_5_min", "LC_24_h"],
        }
        targets = {name} if name in cds else aliases.get(name, set())
        if len(targets) > 1:
            record["mapping_status"] = "ambiguous_exact_annotation_alias"
        elif targets:
            locus = next(iter(targets))
            record["current_locus_tag"] = locus
            matches = cds.get(locus, [])
            record["join_evidence"] = (
                "current_locus_tag" if locus == name else "GFF_old_locus_tag"
            )
            if not matches:
                record["mapping_status"] = "annotation_alias_without_cds"
            elif len(matches) > 1:
                record["mapping_status"] = "multiple_cds_segments_or_models"
            else:
                feature = matches[0]
                attrs = feature["attributes"]
                replicon, strand = feature["replicon"], feature["strand"]
                start, sequence = feature["start_zero_based"], sequences[replicon]
                context = genomic_context(sequence, start, strand)
                protein = proteins.get(attrs.get("protein_id"))
                record.update(
                    genome_id=replicon,
                    replicon=replicon,
                    strand=strand,
                    cds_start_zero_based=start,
                    current_cds_interval=feature["interval"],
                    current_cds_segments=feature["segments"],
                    current_cds_attributes=attrs,
                    mapping_status="matched_current_annotation",
                    sequence=context,
                    sequence_sha256=digest(context),
                    start_position=100,
                    start_codon=context[100:103],
                    protein_sha256=digest(protein) if protein else None,
                    protein_id=attrs.get("protein_id"),
                )
                sign = 1 if strand == "+" else -1
                endpoints = [start - sign * 100, start + sign * 99]
                record["origin_crossing"] = min(endpoints) < 0 or max(endpoints) >= len(
                    sequence
                )
                if attrs.get("pseudo") == "true":
                    record["mapping_status"] = "current_pseudogene"
                elif (
                    feature["phase"] != "0"
                    or attrs.get("partial") == "true"
                    or attrs.get("exception")
                ):
                    record["mapping_status"] = "partial_or_exceptional_current_cds"
                elif not protein:
                    record["mapping_status"] = "current_protein_sequence_missing"
                else:
                    record["primary_eligible"] = replicon == "NC_000911.1"
                if replicon != "NC_000911.1":
                    record["warnings"].append("plasmid_secondary_domain")
                if protein and finite_number(row[31]) and row[31] != len(protein):
                    record["warnings"].append(
                        "source_uniprot_length_differs_from_current_protein"
                    )
                if feature["interval"][1] - feature["interval"][0] < 100:
                    record["warnings"].append(
                        "assumed_downstream_context_extends_beyond_cds"
                    )
        inputs.append(record)
        for condition, te_column, rpf_column, rna_column in (
            ("HC", 8, 1, 4),
            ("LC", 9, 2, 5),
        ):
            measurement = assay_value(row[te_column])
            rpf, rna = row[rpf_column], row[rna_column]
            if not finite_number(rpf) or not finite_number(rna) or rpf < 0 or rna <= 0:
                raise ValueError(
                    "Source RPKM ratio requires finite nonnegative RPF and positive RNA"
                )
            outcomes.append(
                {
                    "id": identity + ":" + condition,
                    "input_id": identity,
                    "study": "Karlsen2018",
                    "source_row": index,
                    "condition": condition,
                    "observed": measurement["value"],
                    "measurement_status": measurement["status"],
                    "log_eligible": measurement["log_eligible"],
                    "rpf_rpkm": rpf,
                    "rna_rpkm": rna,
                    "ratio_of_rounded_rpkms": rpf / rna,
                    "quantity": "reported relative RPF_RPKM/RNA_RPKM TE proxy",
                    "biological_replicates_per_endpoint": 1,
                    "replicate_limit": (
                        "One sequencing sample/endpoint; nearby HC RPF time points "
                        "are technical proxies, not independent cultures"
                    ),
                }
            )
    audit = {
        "n_source_genes": len(inputs),
        "n_condition_records": len(outcomes),
        "mapping_status": dict(Counter(r["mapping_status"] for r in inputs)),
        "n_primary_chromosomal_contexts": sum(r["primary_eligible"] for r in inputs),
        "measurement_status": dict(Counter(r["measurement_status"] for r in outcomes)),
        "warnings": dict(Counter(warning for r in inputs for warning in r["warnings"])),
        "no_prediction_dependent_exclusions": True,
    }
    return inputs, outcomes, audit


def private_directory(path):
    """Require an evaluator-owned directory outside the repository for raw outcomes."""
    path = Path(path).resolve()
    repository = Path(__file__).resolve().parents[2]
    if path == repository or repository in path.parents:
        raise ValueError("Unpartitioned outcomes must remain outside Git")
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def protein_fasta(features, proteins):
    """Export exact annotation-linked proteins for outcome-blind homology grouping."""
    by_locus = {}
    for feature in features:
        attrs = feature["attributes"]
        locus, protein = attrs.get("locus_tag"), proteins.get(attrs.get("protein_id"))
        if feature["type"] != "CDS" or not locus or protein is None:
            continue
        if locus in by_locus and by_locus[locus] != protein:
            raise ValueError("Conflicting protein sequences for one current locus")
        by_locus[locus] = protein
    return "".join(
        f">{locus}\n{sequence}\n" for locus, sequence in sorted(by_locus.items())
    )


def prepare(root, output):
    """Prepare private source inputs/outcomes; no split or model result is inferred."""
    import openpyxl

    output = private_directory(output)
    source = manifest()
    sequences = fasta_records(
        gzip.decompress(checked_source(root, "pcc6803-genomic.fna.gz")).decode()
    )
    if {key: len(value) for key, value in sequences.items()} != source[
        "pcc6803_identity"
    ]["replicons"]:
        raise ValueError("PCC6803 replicon identity or length mismatch")
    features = gff_features(
        gzip.decompress(checked_source(root, "pcc6803-genomic.gff.gz")).decode(),
        sequences,
    )
    regions = {r["replicon"]: r for r in features if r["type"] == "region"}
    if set(regions) != set(sequences) or any(
        r["attributes"].get("Is_circular") != "true" for r in regions.values()
    ):
        raise ValueError(
            "Circular topology is required for the declared context extraction"
        )
    proteins = fasta_records(
        gzip.decompress(checked_source(root, "pcc6803-protein.faa.gz")).decode(),
        PROTEIN_ALPHABET,
    )
    raw = checked_source(root, "karlsen2018-s2.xlsx")
    workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    rows = [
        list(row)
        for row in workbook["Table S2"].iter_rows(max_col=37, values_only=True)
    ]
    workbook.close()
    inputs, outcomes, audit = karlsen_records(rows, sequences, features, proteins)
    tails = rrna_tail_evidence(sequences, features)
    asds = {r["anti_sd"] for r in tails}
    if len(asds) != 1:
        raise ValueError("No unique annotated PCC6803 16S tail scenario")
    source_hash = digest(raw)
    for row in inputs:
        row.update(
            source_file_sha256=source_hash,
            anti_sd=next(iter(asds)),
            anti_sd_provenance=tails,
        )
    genomes = {
        key: {
            "sequence": value,
            "sequence_sha256": digest(value),
            "accession": key,
            "assembly": source["pcc6803_identity"]["assembly"],
            "annotation": source["pcc6803_identity"]["annotation"],
            "topology": "circular",
        }
        for key, value in sequences.items()
    }
    payloads = {
        "karlsen-inputs.json": {
            "schema_version": "native-rbs-evidence-1",
            "genomes": genomes,
            "records": inputs,
        },
        "karlsen-outcomes-private.json": outcomes,
        "karlsen-admission-audit.json": audit,
    }
    for name, payload in payloads.items():
        write_json(output / name, payload)
        (output / name).chmod(0o600)
    protein_path = output / "all-annotated-proteins.faa"
    protein_path.write_text(protein_fasta(features, proteins))
    protein_path.chmod(0o600)
    return audit


def main(argv=None):
    """Extract a pinned source into the private evaluator directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("private_output", type=Path)
    args = parser.parse_args(argv)
    print(
        json.dumps(prepare(args.root, args.private_output), indent=2, allow_nan=False)
    )


if __name__ == "__main__":
    main()
