"""Label-free genome-grid Promoter queries and separate positive-TSS projection.

Queries come only from pinned genome sequences, an explicit seed and settings.
Source TSS rows are read solely by the explicitly invoked label projection.
No runtime scoring module is imported. Coordinates are zero-based half-open.
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

from benchmarks.rbs.datasets import digest
from benchmarks.rbs.native import COMPLEMENT

ENVELOPE_SCHEMA = "native-rbs-evidence-1"
QUERY_SCHEMA = "promoter-native-queries-1"
LABEL_SCHEMA = "promoter-native-labels-1"
# All 30 source states: discriminator 10 + hex10 6 + spacer 20 + hex35 6 + gap 1
# + UP 24 upstream of the TSS; the 20-base ITR needs 19 bases after it.
UPSTREAM_NT = 67
DOWNSTREAM_NT = 19
DEFAULT_TILE_WIDTH = 1000
DEFAULT_MAX_TILES = 128
DEFAULT_SEED = "wave5-tan-grid-v1"
MAX_ENVELOPE_BYTES = 64 * 1024 * 1024
MAX_QUERY_DOCUMENT_BYTES = 256 * 1024 * 1024
MAX_GENOMES = 64
MAX_GENOME_LENGTH = 20_000_000
MAX_RECORDS = 200_000
MAX_TILE_WIDTH = 100_000
MAX_TILES_PER_GENOME_STRAND = 100_000
MAX_GRID_TILES = 2_000_000
MAX_QUERY_NT = 100_000_000
MAX_SEED_LENGTH = 256
HEX64 = re.compile(r"[0-9a-f]{64}")
STRANDS = ("+", "-")
STRAND_NAMES = {"+": "plus", "-": "minus"}
GENOME_FIELDS = (
    "sequence",
    "sequence_sha256",
    "accession",
    "assembly",
    "annotation",
    "topology",
)
# Transcription-evidence fields only: no CDS, translation or S2 start proposals.
PRESERVED_ROW_FIELDS = (
    "id",
    "study",
    "source_sheet",
    "source_row",
    "source_file_sha256",
    "tss_type",
    "transcript_start_evidence",
    "original_tss_one_based",
    "source_locus_tag",
    "mapping_status",
    "warnings",
    "conditions",
    "source_tss_nucleotide",
    "reference_tss_nucleotide",
)


def canonical_bytes(value):
    """Canonical finite JSON bytes; tool outputs are written exactly so."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def document_sha256(value):
    """Identity of a parsed document, equal to the file hash of a tool output."""
    return digest(canonical_bytes(value))


def tool_sha256():
    """Identity of this exact builder/projection implementation."""
    return digest(Path(__file__).read_bytes())


def read_bounded(path, limit):
    """Read at most limit bytes and fail rather than truncate a larger file."""
    with open(path, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"Input exceeds {limit} bytes: {path}")
    return raw


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(name):
    raise ValueError(f"Non-finite JSON constant: {name}")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"Non-finite JSON number: {text}")
    return value


def strict_json(raw):
    """Parse UTF-8 JSON rejecting duplicate keys and non-finite numbers."""
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
        parse_float=_finite_float,
    )


def checked_hash(value):
    """Require an explicit lowercase SHA-256 hex identity."""
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ValueError("Expected a lowercase 64-hex SHA-256")
    return value


def load_envelope(raw, expected_sha256):
    """Verify file bytes, genome hashes and record identities of an envelope."""
    if digest(raw) != checked_hash(expected_sha256):
        raise ValueError("Envelope file SHA-256 mismatch")
    envelope = strict_json(raw)
    if (
        not isinstance(envelope, dict)
        or envelope.get("schema_version") != ENVELOPE_SCHEMA
    ):
        raise ValueError("Envelope schema must be " + ENVELOPE_SCHEMA)
    genomes, records = envelope.get("genomes"), envelope.get("records")
    if not isinstance(genomes, dict) or not 0 < len(genomes) <= MAX_GENOMES:
        raise ValueError(f"Envelope needs 1..{MAX_GENOMES} genomes")
    for identity, genome in genomes.items():
        if (
            not identity
            or not isinstance(genome, dict)
            or any(
                not isinstance(genome.get(field), str) or not genome[field]
                for field in GENOME_FIELDS
            )
        ):
            raise ValueError(f"Incomplete genome identity: {identity!r}")
        sequence = genome["sequence"]
        if len(sequence) > MAX_GENOME_LENGTH or set(sequence) - set("ACGT"):
            raise ValueError(f"Genome is not bounded normalized ACGT: {identity}")
        if digest(sequence) != genome["sequence_sha256"]:
            raise ValueError(f"Genome sequence SHA-256 mismatch: {identity}")
        if genome["topology"] not in {"linear", "circular"}:
            raise ValueError(f"Genome topology must be linear or circular: {identity}")
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError(f"Envelope records must be a list of at most {MAX_RECORDS}")
    seen = set()
    for record in records:
        identity = record.get("id") if isinstance(record, dict) else None
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError("Invalid or duplicate record identity")
        seen.add(identity)
    return envelope


def grid_settings(
    tile_width=DEFAULT_TILE_WIDTH,
    max_tiles_per_genome_strand=DEFAULT_MAX_TILES,
    seed=DEFAULT_SEED,
):
    """Validated, complete query settings; freeze these before any scoring."""
    if type(tile_width) is not int or not 0 < tile_width <= MAX_TILE_WIDTH:
        raise ValueError(f"tile_width must be an integer in 1..{MAX_TILE_WIDTH}")
    if (
        type(max_tiles_per_genome_strand) is not int
        or not 0 < max_tiles_per_genome_strand <= MAX_TILES_PER_GENOME_STRAND
    ):
        raise ValueError(
            f"max_tiles_per_genome_strand must be in 1..{MAX_TILES_PER_GENOME_STRAND}"
        )
    if not isinstance(seed, str) or not 0 < len(seed) <= MAX_SEED_LENGTH:
        raise ValueError(f"seed must be a nonempty string of at most {MAX_SEED_LENGTH}")
    return {
        "tile_width": tile_width,
        "max_tiles_per_genome_strand": max_tiles_per_genome_strand,
        "seed": seed,
        "upstream_nt": UPSTREAM_NT,
        "downstream_nt": DOWNSTREAM_NT,
        "strands": list(STRANDS),
        "selection": "sha256(canonical [seed, genome_sha256, strand, tile]) ascending",
    }


def selection_key(seed, genome_sha256, strand, tile):
    """Deterministic label-free tile order key."""
    return digest(canonical_bytes([seed, genome_sha256, strand, tile]))


def padding(length, topology, strand, lower, upper):
    """Return (upstream, downstream) padding in transcript orientation.

    Linear replicons clip at their ends. Circular padding wraps the origin at
    most once and never repeats a base: if the outside-tile allowance is short,
    downstream ITR context is kept first, then upstream.
    """
    if topology == "linear":
        left, right = lower, length - upper
        up_room, down_room = (left, right) if strand == "+" else (right, left)
        return min(UPSTREAM_NT, up_room), min(DOWNSTREAM_NT, down_room)
    allowance = length - (upper - lower)
    downstream = min(DOWNSTREAM_NT, allowance)
    return min(UPSTREAM_NT, allowance - downstream), downstream


def segments(length, strand, start, end):
    """Map a genomic span [start, end), possibly wrapped once, to local segments.

    Segments follow transcript order. Plus local i maps to genomic g0 + (i - l0);
    minus local i maps to g1 - 1 - (i - l0). `oriented` gives the same bases in
    reverse-complement replicon coordinates: [L - g1, L - g0), point t = L - 1 - g.
    """
    if start < 0:
        pieces = [[start + length, length], [0, end]]
    elif end > length:
        pieces = [[start, length], [0, end - length]]
    else:
        pieces = [[start, end]]
    if strand == "-":
        pieces.reverse()
    result, local = [], 0
    for lower, upper in pieces:
        oriented = [lower, upper] if strand == "+" else [length - upper, length - lower]
        result.append(
            {
                "local": [local, local + upper - lower],
                "genomic": [lower, upper],
                "oriented": oriented,
            }
        )
        local += upper - lower
    return result


def local_to_genomic(strand, segment_list, local):
    """Genomic zero-based point of a local query index."""
    for segment in segment_list:
        l0, l1 = segment["local"]
        if l0 <= local < l1:
            g0, g1 = segment["genomic"]
            return g0 + local - l0 if strand == "+" else g1 - 1 - (local - l0)
    raise ValueError("Local index lies outside the query sequence")


def oriented_sequence(sequence, strand, segment_list):
    """Transcript-oriented DNA for already ordered segments."""
    parts = [sequence[a:b] for a, b in (s["genomic"] for s in segment_list)]
    if strand == "-":
        parts = [part.translate(COMPLEMENT)[::-1] for part in parts]
    return "".join(parts)


def tile_query(genome_id, genome, strand, tile, rank, key, settings):
    """Build one query for genomic tile [tile*w, min((tile+1)*w, L))."""
    sequence, topology = genome["sequence"], genome["topology"]
    length, width = len(sequence), settings["tile_width"]
    lower, upper = tile * width, min((tile + 1) * width, length)
    up, down = padding(length, topology, strand, lower, upper)
    start, end = (
        (lower - up, upper + down) if strand == "+" else (lower - down, upper + up)
    )
    mapped = segments(length, strand, start, end)
    dna = oriented_sequence(sequence, strand, mapped)
    first, last = up, up + upper - lower
    full_lower, full_upper = (
        max(first, UPSTREAM_NT),
        min(last, len(dna) - DOWNSTREAM_NT),
    )
    supported = max(0, full_upper - full_lower)
    short_up, short_down = UPSTREAM_NT - up, DOWNSTREAM_NT - down
    reason = None
    if short_up or short_down:
        reason = "linear_edge" if topology == "linear" else "circular_no_repeat_limit"
    status = (
        "complete"
        if supported == last - first
        else "clipped"
        if supported
        else "no_full_state_support"
    )
    return {
        "query_id": f"promoter-grid:{genome_id}:{STRAND_NAMES[strand]}:{tile}",
        "genome_id": genome_id,
        "strand": strand,
        "orientation": "transcript 5'->3'",
        "tile_ordinal": tile,
        "selection_rank": rank,
        "selection_key": key,
        "candidate_genomic_interval": [lower, upper],
        "candidate_local_range": [first, last],
        "n_candidates": last - first,
        "sequence": dna,
        "sequence_sha256": digest(dna),
        "sequence_length": len(dna),
        "segments": mapped,
        "context": {
            "upstream_pad_nt": up,
            "downstream_pad_nt": down,
            "upstream_shortfall_nt": short_up,
            "downstream_shortfall_nt": short_down,
            "limit_reason": reason,
        },
        "context_status": status,
        "full_state_support_local_range": (
            [full_lower, full_upper] if supported else None
        ),
        "n_candidates_full_state_support": supported,
    }


def build_queries(envelope, source_sha256, settings):
    """Select label-free genome-grid queries; never reads envelope records."""
    genomes = envelope["genomes"]
    width, cap = settings["tile_width"], settings["max_tiles_per_genome_strand"]
    counts = {key: math.ceil(len(g["sequence"]) / width) for key, g in genomes.items()}
    if 2 * sum(counts.values()) > MAX_GRID_TILES:
        raise ValueError(f"Genome grid exceeds {MAX_GRID_TILES} tiles")
    padded = (
        2
        * sum(min(n, cap) for n in counts.values())
        * (width + UPSTREAM_NT + DOWNSTREAM_NT)
    )
    if padded > MAX_QUERY_NT:
        raise ValueError(f"Selected query sequence exceeds {MAX_QUERY_NT} nt")
    queries, grid = [], {}
    for genome_id in sorted(genomes):
        genome = genomes[genome_id]
        grid[genome_id] = {}
        for strand in STRANDS:
            order = sorted(
                (
                    selection_key(
                        settings["seed"], genome["sequence_sha256"], strand, k
                    ),
                    k,
                )
                for k in range(counts[genome_id])
            )
            chosen = order[:cap]
            for rank, (key, tile) in enumerate(chosen):
                queries.append(
                    tile_query(genome_id, genome, strand, tile, rank, key, settings)
                )
            selected_nt = sum(
                min((k + 1) * width, len(genome["sequence"])) - k * width
                for _, k in chosen
            )
            grid[genome_id][strand] = {
                "n_grid_tiles": counts[genome_id],
                "n_selected_tiles": len(chosen),
                "n_not_selected_tiles": counts[genome_id] - len(chosen),
                "n_grid_points": len(genome["sequence"]),
                "n_selected_points": selected_nt,
                "n_not_selected_points": len(genome["sequence"]) - selected_nt,
            }
    totals = {
        field: sum(row[field] for strands in grid.values() for row in strands.values())
        for field in next(iter(next(iter(grid.values())).values()))
    }
    statuses = {}
    for query in queries:
        statuses[query["context_status"]] = statuses.get(query["context_status"], 0) + 1
    return {
        "schema_version": QUERY_SCHEMA,
        "label_free": (
            "Built only from genome sequences, seed and settings; no TSS, CDS, "
            "read count, condition or model output selects or centers a query."
        ),
        "source": {"schema_version": ENVELOPE_SCHEMA, "file_sha256": source_sha256},
        "tool_sha256": tool_sha256(),
        "settings": settings,
        "settings_sha256": document_sha256(settings),
        "genomes": {
            key: {
                "accession": genomes[key]["accession"],
                "assembly": genomes[key]["assembly"],
                "annotation": genomes[key]["annotation"],
                "topology": genomes[key]["topology"],
                "sequence_sha256": genomes[key]["sequence_sha256"],
                "length": len(genomes[key]["sequence"]),
            }
            for key in sorted(genomes)
        },
        "grid": grid,
        "grid_totals": totals,
        "context_status_counts": statuses,
        "queries": queries,
        "queries_sha256": document_sha256(queries),
    }


def candidate_index(queries):
    """Map (genome_id, strand, genomic point) to (query_id, local index)."""
    index = {}
    for query in queries:
        lower, upper = query["candidate_local_range"]
        for local in range(lower, upper):
            point = local_to_genomic(query["strand"], query["segments"], local)
            key = (query["genome_id"], query["strand"], point)
            if key in index:
                raise ValueError("Overlapping query candidate universes")
            index[key] = (query["query_id"], local)
    return index


def project_labels(envelope, source_sha256, query_document):
    """Project source TSS rows onto frozen queries as unique positive points.

    Explicitly invoked only for evaluation. Labels preserve every source row,
    type, condition and mapping warning; no negatives, weights or translation
    labels are created. The query document must be exactly reproducible.
    """
    settings = grid_settings(
        query_document["settings"]["tile_width"],
        query_document["settings"]["max_tiles_per_genome_strand"],
        query_document["settings"]["seed"],
    )
    if build_queries(envelope, source_sha256, settings) != query_document:
        raise ValueError("Query document is not reproduced by this envelope/settings")
    index = candidate_index(query_document["queries"])
    genomes, labels, rows = envelope["genomes"], {}, []
    for record in envelope["records"]:
        genome = genomes.get(record.get("genome_id"))
        point, strand = record.get("tss_zero_based"), record.get("strand")
        if genome is None or strand not in STRANDS:
            raise ValueError(f"Record lacks a known genome/strand: {record['id']}")
        if point is None:
            rows.append(
                {
                    "record_id": record["id"],
                    "label_id": None,
                    "window_status": "no_measured_tss",
                    "query_id": None,
                }
            )
            continue
        if type(point) is not int or not 0 <= point < len(genome["sequence"]):
            raise ValueError(f"Record TSS outside its genome: {record['id']}")
        one_based = record.get("original_tss_one_based")
        if one_based is not None and one_based != point + 1:
            raise ValueError(f"One-based/zero-based TSS disagreement: {record['id']}")
        key = (record["genome_id"], strand, point)
        query_id, local = index.get(key, (None, None))
        status = "in_selected_query" if query_id else "out_of_window"
        label_id = f"tss:{record['genome_id']}:{strand}:{point}"
        label = labels.setdefault(
            key,
            {
                "label_id": label_id,
                "genome_id": record["genome_id"],
                "strand": strand,
                "tss_zero_based": point,
                "window_status": status,
                "query_id": query_id,
                "local_index": local,
                "source_rows": [],
            },
        )
        label["source_rows"].append(
            {field: record.get(field) for field in PRESERVED_ROW_FIELDS}
        )
        rows.append(
            {
                "record_id": record["id"],
                "label_id": label_id,
                "window_status": status,
                "query_id": query_id,
            }
        )
    ordered = [labels[key] for key in sorted(labels)]
    for label in ordered:
        label["source_rows"].sort(key=lambda row: row["id"])
    count = {}
    for row in rows:
        count[row["window_status"]] = count.get(row["window_status"], 0) + 1
    return {
        "schema_version": LABEL_SCHEMA,
        "label_kind": (
            "positive measured TSS genomic point/strand; transcription evidence "
            "only; unlabelled points are not negatives"
        ),
        "source": {"schema_version": ENVELOPE_SCHEMA, "file_sha256": source_sha256},
        "query_document_sha256": document_sha256(query_document),
        "tool_sha256": tool_sha256(),
        "counts": {
            "n_records": len(rows),
            "row_window_status": count,
            "n_labels": len(ordered),
            "n_labels_in_selected_query": sum(
                label["query_id"] is not None for label in ordered
            ),
            "n_labels_out_of_window": sum(
                label["query_id"] is None for label in ordered
            ),
        },
        "labels": ordered,
        "rows": sorted(rows, key=lambda row: row["record_id"]),
    }


def write_exclusive(path, value, mode):
    """Create a new canonical JSON file; never overwrite."""
    with os.fdopen(
        os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode), "wb"
    ) as stream:
        stream.write(canonical_bytes(value))


def main(argv=None):
    """Build label-free queries or explicitly project labels; nonzero on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build-queries")
    project = commands.add_parser("project-labels")
    for command in (build, project):
        command.add_argument("envelope", type=Path)
        command.add_argument("--source-sha256", required=True)
    build.add_argument("output", type=Path)
    build.add_argument("--tile-width", type=int, default=DEFAULT_TILE_WIDTH)
    build.add_argument(
        "--max-tiles-per-genome-strand", type=int, default=DEFAULT_MAX_TILES
    )
    build.add_argument("--seed", default=DEFAULT_SEED)
    project.add_argument("queries", type=Path)
    project.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        envelope = load_envelope(
            read_bounded(args.envelope, MAX_ENVELOPE_BYTES), args.source_sha256
        )
        if args.command == "build-queries":
            settings = grid_settings(
                args.tile_width, args.max_tiles_per_genome_strand, args.seed
            )
            result = build_queries(envelope, args.source_sha256, settings)
            write_exclusive(args.output, result, 0o644)
            summary = {
                "n_queries": len(result["queries"]),
                "queries_sha256": result["queries_sha256"],
            }
        else:
            queries = strict_json(read_bounded(args.queries, MAX_QUERY_DOCUMENT_BYTES))
            result = project_labels(envelope, args.source_sha256, queries)
            write_exclusive(args.output, result, 0o600)
            summary = {"n_records": result["counts"]["n_records"]}
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    summary["output_sha256"] = document_sha256(result)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
