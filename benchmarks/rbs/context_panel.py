"""Select deterministic transcript-context diagnostics without model outcomes."""

import argparse
import copy
import json
import sys
from pathlib import Path

from benchmarks.promoter.native_inputs import (
    MAX_ENVELOPE_BYTES,
    canonical_bytes,
    document_sha256,
    load_envelope,
    read_bounded,
    write_exclusive,
)
from benchmarks.rbs.datasets import digest

STRATA = (
    "internal",
    "leaderless",
    "short_leader",
    "start_disagreement",
    "ordinary",
    "unresolved",
)
SEED = "wave5-tan-context-v1"
PROFILES = ("historical", "context2017")
MAX_SELECTED_ROWS = 1024
# Preserve supplied coordinate evidence, not expression/count fields.
FIELDS = (
    "id",
    "study",
    "source_sheet",
    "source_row",
    "source_file_sha256",
    "source_locus_tag",
    "genome_id",
    "replicon",
    "strand",
    "tss_type",
    "tss_zero_based",
    "original_tss_one_based",
    "cds_start_zero_based",
    "source_start_zero_based",
    "source_start_distance_nt",
    "leader_length_nt",
    "source_current_start_delta_nt",
    "origin_crossing",
    "mapping_status",
    "transcript_start_evidence",
    "translation_start_evidence",
    "host",
    "anti_sd_provenance",
    "warnings",
    "source_flags",
)


def _optional_int(value, name):
    if value is not None and type(value) is not int:
        raise ValueError(f"{name} must be an integer or null")


def stratum(rows):
    """Choose the first declared input stratum represented by a locus."""
    leaders = [r.get("leader_length_nt") for r in rows]
    deltas = [r.get("source_current_start_delta_nt") for r in rows]
    for value in leaders + deltas:
        _optional_int(value, "leader/delta")
    values = [v for v in leaders if v is not None]
    if any(v < 0 for v in values):
        return "internal"
    if 0 in values:
        return "leaderless"
    if any(1 <= v <= 20 for v in values):
        return "short_leader"
    if any(v is not None and v != 0 for v in deltas):
        return "start_disagreement"
    if any(v > 20 for v in values):
        return "ordinary"
    return "unresolved"


def selection_key(genome_id, locus):
    """Hash the declared compact UTF-8 JSON tuple, with no trailing newline."""
    value = json.dumps([SEED, genome_id, locus], separators=(",", ":"))
    return digest(value.encode())


def scenarios(row):
    """Retain all four coordinate/context alternatives for a source association."""
    conditions = row.get("conditions", {})
    if not isinstance(conditions, (dict, list)):
        raise ValueError("conditions must be an object or list")
    if any(not isinstance(name, str) or not name for name in conditions):
        raise ValueError("conditions must have nonempty string identities")
    for anchor in ("current", "historical"):
        for context in ("measured_tss", "genomic_flank"):
            record = {key: copy.deepcopy(row.get(key)) for key in FIELDS}
            record.update(
                id=f"{row['id']}:{anchor}:{context}",
                source_record_id=row["id"],
                anchor_scenario=anchor,
                transcript_context_scenario=context,
                measured_tss_zero_based=row.get("tss_zero_based"),
                conditions=sorted(conditions)
                if isinstance(conditions, dict)
                else copy.deepcopy(conditions),
                upstream_limit_nt=100,
                downstream_length_nt=100,
                temperature_c=37.0,
                anti_sd="ACCUCCUUU",
            )
            warnings = row.get("warnings", [])
            if not isinstance(warnings, list) or any(
                not isinstance(v, str) for v in warnings
            ):
                raise ValueError("warnings must be an array of strings")
            record["warnings"] = warnings + [
                "Input sensitivity only; no native translation accuracy label.",
                "Fixed 37C scenario does not represent every source condition.",
            ]
            if anchor == "historical":
                record["cds_start_zero_based"] = row.get("source_start_zero_based")
                record["leader_length_nt"] = row.get("source_start_distance_nt")
                record["translation_start_evidence"] = (
                    "historical start inferred from published gTSS distance"
                )
            if record["cds_start_zero_based"] is None:
                record["leader_length_nt"] = None
            if context == "genomic_flank":
                record["tss_zero_based"] = None
                record["leader_length_nt"] = None
                record["transcript_start_evidence"] = (
                    "unmeasured 100-nt genomic-flank assumption"
                )
            yield record


def build_panel(envelope, source_sha256, per_stratum=4):
    """Build a portable input envelope; no scoring or read-count weighting."""
    if type(per_stratum) is not int or not 1 <= per_stratum <= 4:
        raise ValueError("per_stratum must be an integer in 1..4")
    loci, excluded, gtss_count = {}, [], 0
    for row in envelope["records"]:
        if row.get("tss_type") != "gTSS":
            continue
        gtss_count += 1
        locus = row.get("source_locus_tag")
        if not isinstance(locus, str) or not locus:
            excluded.append(row["id"])
            continue
        genome_id = row.get("genome_id")
        if genome_id not in envelope["genomes"] or row.get("strand") not in {"+", "-"}:
            raise ValueError("gTSS association needs an explicit genome and strand")
        length = len(envelope["genomes"][genome_id]["sequence"])
        for field in (
            "tss_zero_based",
            "cds_start_zero_based",
            "source_start_zero_based",
        ):
            value = row.get(field)
            _optional_int(value, field)
            if value is not None and not 0 <= value < length:
                raise ValueError(f"{field} lies outside supplied genome")
        _optional_int(row.get("source_start_distance_nt"), "source_start_distance_nt")
        loci.setdefault((genome_id, locus), []).append(row)
    by_stratum = {key: [] for key in STRATA}
    for (genome, locus), rows in loci.items():
        key = stratum(rows)
        by_stratum[key].append((selection_key(genome, locus), genome, locus))
    selected = []
    for name in STRATA:
        for key, genome, locus in sorted(by_stratum[name])[:per_stratum]:
            rows = sorted(loci[(genome, locus)], key=lambda row: row["id"])
            selected.append(
                {
                    "stratum": name,
                    "selection_key": key,
                    "genome_id": genome,
                    "source_locus_tag": locus,
                    "record_ids": [r["id"] for r in rows],
                }
            )
    selected_rows = sum(len(row["record_ids"]) for row in selected)
    if selected_rows > MAX_SELECTED_ROWS:
        raise ValueError("Selected alternatives exceed row cap; no truncation allowed")
    records = [
        scenario
        for item in selected
        for row in sorted(
            loci[(item["genome_id"], item["source_locus_tag"])], key=lambda r: r["id"]
        )
        for scenario in scenarios(row)
    ]
    settings = {
        "seed": SEED,
        "per_stratum": per_stratum,
        "stratum_priority": list(STRATA),
        "upstream_limit_nt": 100,
        "downstream_length_nt": 100,
        "temperature_c": 37.0,
        "anti_sd": "ACCUCCUUU",
        "profiles": list(PROFILES),
        "maximum_selected_source_rows": MAX_SELECTED_ROWS,
    }
    return {
        "schema_version": "native-rbs-evidence-1",
        "genomes": copy.deepcopy(envelope["genomes"]),
        "records": records,
        "panel": {
            "schema_version": "rbs-context-panel-1",
            "source_sha256": source_sha256,
            "tool_sha256": digest(Path(__file__).read_bytes()),
            "settings": settings,
            "settings_sha256": document_sha256(settings),
            "selected_loci": selected,
            "counts": {
                "source_rows": len(envelope["records"]),
                "source_gtss_rows": gtss_count,
                "gtss_rows_without_locus": len(excluded),
                "source_loci": len(loci),
                "loci_by_stratum": {k: len(v) for k, v in by_stratum.items()},
                "selected_loci": len(selected),
                "selected_source_rows": selected_rows,
                "input_scenarios": len(records),
                "profile_jobs": len(records) * 2,
            },
            "excluded_without_locus_record_ids": sorted(excluded),
            "interpretation": (
                "Input sensitivity only. All selected gTSS alternatives retained; "
                "no translation labels, count weights or model-driven selection."
            ),
        },
    }


def main(argv=None):
    """Create an exclusively written, hash-addressed panel in private storage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("envelope", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--per-stratum", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        envelope = load_envelope(
            read_bounded(args.envelope, MAX_ENVELOPE_BYTES), args.source_sha256
        )
        result = build_panel(envelope, args.source_sha256, args.per_stratum)
        write_exclusive(args.output, result, 0o600)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output_sha256": digest(canonical_bytes(result)),
                "counts": result["panel"]["counts"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
