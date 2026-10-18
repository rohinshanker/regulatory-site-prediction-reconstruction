"""Outcome-free adapter between native Promoter queries and the public runtime.

`prepare` turns a frozen `promoter-native-queries-1` document and an explicit
identity/settings manifest into an immutable request plan. `adapt` checks an
explicit collection of public `promoter-result-1.0` documents against that plan
and emits `promoter-native-scores-2` rows plus an aggregate audit. The adapter
never runs the runtime, computes scores or model terms, or reads labels.
Coordinates are zero-based half-open, following docs/validation/promoter-runtime.md
at 5b890a3c307d366a828d95812f22a2b9975e6cfe. Candidate commit and wheel hash are
caller assertions: matching result identities does not prove which binary ran.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from benchmarks.promoter.native_inputs import (
    DOWNSTREAM_NT,
    MAX_GENOME_LENGTH,
    MAX_GENOMES,
    MAX_QUERY_DOCUMENT_BYTES,
    QUERY_SCHEMA,
    STRANDS,
    UPSTREAM_NT,
    canonical_bytes,
    checked_hash,
    document_sha256,
    read_bounded,
    strict_json,
    write_exclusive,
)
from benchmarks.promoter.native_metrics import (
    MAX_QUERIES,
    RUNTIME_STATUS_TO_REQUEST,
    SCORE_SCHEMA_V2,
)
from benchmarks.promoter.native_metrics import STATUSES as CANDIDATE_STATUSES
from benchmarks.rbs.datasets import digest
from benchmarks.rbs.metrics import finite_number

MANIFEST_SCHEMA = "promoter-runtime-manifest-1"
PLAN_SCHEMA = "promoter-runtime-plan-1"
COLLECTION_SCHEMA = "promoter-runtime-collection-1"
AUDIT_SCHEMA = "promoter-runtime-adapter-audit-1"
CONTRACT_VERSION = "1.0"
# Reviewed public ceilings; a manifest may only lower them.
LIMIT_CEILINGS = {
    "request_bytes": 4_000_000,
    "records_per_batch": 100,
    "bases_per_record": 5_000,
    "bases_per_batch": 100_000,
    "sites_per_record": 5_000,
    "sites_per_batch": 20_000,
}
# Published effective-limit ceilings (a986722): the receipt supplies the exact
# object, which may lower any value. This table is not a candidate receipt.
RUNTIME_LIMIT_CEILINGS = {
    "max_input_json_bytes": 4_000_000,
    "max_records_per_batch": 100,
    "max_id_chars": 128,
    "max_host_name_chars": 200,
    "max_contig_chars": 128,
    "max_raw_sequence_chars_per_record": 50_000,
    "max_normalized_bases_per_record": 5_000,
    "max_normalized_bases_per_batch": 100_000,
    "max_planned_sites_per_record": 5_000,
    "max_planned_sites_per_batch": 20_000,
    "max_all_state_sites_per_record": 100,
    "max_all_states_per_record": 3_000,
    "max_all_states_per_batch": 10_000,
    "max_result_json_bytes": 67_108_864,
    "max_metadata_json_bytes": 4_096,
    "max_metadata_depth": 4,
    "default_seconds_per_record": 30.0,
    "max_seconds_per_record": 120.0,
    "default_seconds_per_batch": 300.0,
    "max_seconds_per_batch": 3600.0,
}
DEADLINES = (
    ("seconds_per_record", "default_seconds_per_record", "max_seconds_per_record"),
    ("seconds_per_batch", "default_seconds_per_batch", "max_seconds_per_batch"),
)
# Each packing limit must fit within these runtime effective limits.
PACKING_RUNTIME_LIMITS = {
    "request_bytes": ("max_input_json_bytes",),
    "records_per_batch": ("max_records_per_batch",),
    "bases_per_record": (
        "max_normalized_bases_per_record",
        "max_raw_sequence_chars_per_record",
    ),
    "bases_per_batch": ("max_normalized_bases_per_batch",),
    "sites_per_record": ("max_planned_sites_per_record",),
    "sites_per_batch": ("max_planned_sites_per_batch",),
}
NORMALIZATION = "ascii-whitespace-uppercase-u-to-t-1"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_PLAN_BYTES = 512 * 1024 * 1024
MAX_COLLECTION_BYTES = 64 * 1024 * 1024
MAX_RESULT_BYTES = 64 * 1024 * 1024
OUTPUT_OPTIONS = {"states": "selected", "legacy_keys": False, "elements": False}
SCAN_STRANDS = ["+"]
NATIVE_HOST = "Escherichia coli str. K-12 substr. MG1655"
IN_VITRO_HOST = "in vitro"
CALIBRATIONS = {
    "ecoli_mg1655": {"K": 42, "beta": 1.636217004872062, "native_host": NATIVE_HOST},
    "in_vitro": {"K": 42, "beta": 0.81632623, "native_host": None},
}
DISCRIMINATORS = range(6, 11)
SPACERS = range(15, 21)
FULL_STATE_COUNT = len(DISCRIMINATORS) * len(SPACERS)
# UP.start = t - d - s - 37: hex10 6 + hex35 6 + gap 1 + UP 24.
FIXED_UPSTREAM_NT = 37
ITR_NT = 20
TERM_KEYS = (
    "hex10",
    "hex35",
    "discriminator",
    "extended10",
    "itr",
    "up",
    "spacer",
    "intercept",
    "total",
    "binding",
    "source_apparent",
)
NOT_MODELED = [
    "sigma_factor",
    "temperature",
    "host_specific_calibration",
    "probability",
    "absolute_rate",
    "free_energy",
]
CLAIMS = {
    "physical_free_energy": False,
    "absolute_rate": False,
    "probability": False,
    "native_accuracy_evaluated": False,
    "hosted_parity": False,
}
MODEL_KIND = "historical_equation_reconstruction"
TERMS_UNIT = "source_dG_units"
RECORD_STATUSES = ("ok", "no_candidate", "unsupported", "invalid_input", "failed")
BATCH_STATUSES = ("completed", "setup_failed", "execution_failed", "not_run")
SETUP_EXIT_CODE = 2
FAILURE_REASONS = ("deadline_exceeded", "nonfinite_arithmetic")
SITE_REASONS = ("insufficient_context", *FAILURE_REASONS)
SCORE_STATUSES = ("ok", "overflow", "underflow")
SCORE_FIELD = "selected.terms.total"
HEX40 = re.compile(r"[0-9a-f]{40}")
SITE_ID = re.compile(r"psite1:([0-9a-f]{32}):\+:(0|[1-9][0-9]*)")
MAX_TEXT = 200
MAX_CONTIG = 128
IDENTITY_KEYS = (
    "candidate_commit",
    "public_contract_commit",
    "wheel_sha256",
    "identity_model",
    "expected_model",
)
IDENTITY_MODEL_KEYS = (
    "id",
    "implementation_version",
    "parameter_json_sha256",
    "coefficient_array_sha256",
    "intercept_array_sha256",
    "source_commit",
)
SETTINGS_KEYS = (
    "calibration",
    "host",
    "limits",
    "runtime_limits",
    "seconds_per_record",
    "seconds_per_batch",
    "cli_calibration",
    "cli_states",
)
QUERY_DOCUMENT_KEYS = (
    "schema_version",
    "label_free",
    "source",
    "tool_sha256",
    "settings",
    "settings_sha256",
    "genomes",
    "grid",
    "grid_totals",
    "context_status_counts",
    "queries",
    "queries_sha256",
)
GENOME_KEYS = (
    "accession",
    "assembly",
    "annotation",
    "topology",
    "sequence_sha256",
    "length",
)
QUERY_KEYS = (
    "query_id",
    "genome_id",
    "strand",
    "orientation",
    "tile_ordinal",
    "selection_rank",
    "selection_key",
    "candidate_genomic_interval",
    "candidate_local_range",
    "n_candidates",
    "sequence",
    "sequence_sha256",
    "sequence_length",
    "segments",
    "context",
    "context_status",
    "full_state_support_local_range",
    "n_candidates_full_state_support",
)
CONTEXT_KEYS = (
    "upstream_pad_nt",
    "downstream_pad_nt",
    "upstream_shortfall_nt",
    "downstream_shortfall_nt",
    "limit_reason",
)
COLLECTION_KEYS = ("schema_version", "plan_sha256", "batches")
COLLECTED_BATCH_KEYS = (
    "batch_index",
    "request_sha256",
    "status",
    "exit_code",
    "result_sha256",
)
RESULT_KEYS = ("schema_version", "model", "batch", "results")
MODEL_KEYS = (
    "id",
    "implementation_version",
    "kind",
    "source",
    "licence",
    "parameters",
    "term_source_names",
    "terms_unit",
    "terms_semantics",
    "source_quirks",
    "not_modeled",
    "claims",
)
BATCH_SUMMARY_KEYS = (
    "batch_id",
    "record_count",
    "status_counts",
    "complete",
    "limits",
    "seconds_per_record",
    "seconds_per_batch",
)
RECORD_KEYS = (
    "id",
    "status",
    "reasons",
    "prediction_id",
    "input",
    "calibration",
    "scan",
    "coverage",
    "sites",
    "projection",
    "warnings",
    "errors",
    "metadata",
)
INPUT_KEYS = ("raw_sha256", "normalized_dna_sha256", "length", "normalization")
COVERAGE_KEYS = (
    "planned_sites",
    "scored_sites",
    "partial_state_sites",
    "insufficient_context_sites",
    "failed_sites",
    "unattempted_sites",
    "complete_context",
    "complete",
    "truncation",
)
TRUNCATION_KEYS = ("reason", "attempted_sites", "planned_sites")
SITE_KEYS = (
    "site_id",
    "strand",
    "tss",
    "genomic",
    "status",
    "reason",
    "context",
    "state_count",
    "complete_state_set",
    "attempted",
    "tie_count",
    "selected",
)
SELECTED_KEYS = (
    "state_id",
    "discriminator_length",
    "spacer_length",
    "terms",
    "log_relative_transcription_score",
    "relative_transcription_score",
    "score_status",
    "intervals",
    "oriented_intervals",
    "genomic_intervals",
)
# Serialized envelope around comma-joined compact records (sorted keys).
REQUEST_PREFIX = b'{"defaults":{},"records":['
REQUEST_SUFFIX = b'],"schema_version":"1.0"}\n'


def tool_sha256():
    """Identity of this exact adapter implementation."""
    return digest(Path(__file__).read_bytes())


def _exact_keys(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{name} needs exactly: {', '.join(keys)}")
    return value


def _int(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer in {lower}..{upper}")
    return value


def _pair(value, name, lower, upper):
    """Validated ascending integer pair [a, b) with lower <= a <= b <= upper."""
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a [start, end) pair")
    start = _int(value[0], f"{name} start", lower, upper)
    return start, _int(value[1], f"{name} end", start, upper)


def _text(value, name, limit=MAX_TEXT):
    if not isinstance(value, str) or not 0 < len(value) <= limit:
        raise ValueError(f"{name} must be a nonempty string of at most {limit}")
    return value


def _commit(value, name):
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase 40-hex commit")
    return value


def _seconds(value, name, ceiling):
    if type(value) is not float or not 0 < value <= ceiling:
        raise ValueError(f"{name} must be a positive float of at most {ceiling}")
    return value


def runtime_canonical_bytes(value):
    """Public runtime hash encoding: sorted, compact, ASCII-escaped, no newline."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def runtime_sha256(value):
    """Lowercase SHA-256 of the public runtime canonical bytes."""
    return hashlib.sha256(runtime_canonical_bytes(value)).hexdigest()


def _same(observed, expected, name):
    if canonical_bytes(observed) != canonical_bytes(expected):
        raise ValueError(f"{name} disagrees with the plan")


def _host(value):
    if value is None:
        return None
    host = _exact_keys(value, ("name", "taxon_id"), "host")
    name = _text(host["name"], "host.name")
    if unicodedata.normalize("NFC", name) != name:
        raise ValueError("host.name must already be Unicode NFC")
    if host["taxon_id"] is not None:
        _int(host["taxon_id"], "host.taxon_id", 1, 2**63 - 1)
    return host


def check_manifest(manifest):
    """Validate an explicit identity/settings manifest; no value is defaulted."""
    _exact_keys(manifest, ("schema_version", "identity", "settings"), "manifest")
    if manifest["schema_version"] != MANIFEST_SCHEMA:
        raise ValueError("Manifest schema must be " + MANIFEST_SCHEMA)
    identity = _exact_keys(manifest["identity"], IDENTITY_KEYS, "identity")
    for field in ("candidate_commit", "public_contract_commit"):
        _commit(identity[field], field)
    checked_hash(identity["wheel_sha256"])
    check_identity_model(identity["identity_model"])
    check_expected_model(identity["expected_model"], identity["identity_model"])
    settings = _exact_keys(manifest["settings"], SETTINGS_KEYS, "settings")
    if settings["calibration"] not in CALIBRATIONS:
        raise ValueError("calibration must be explicitly ecoli_mg1655 or in_vitro")
    runtime = check_runtime_limits(settings["runtime_limits"])
    host = _host(settings["host"])
    if host is not None and len(host["name"]) > runtime["max_host_name_chars"]:
        raise ValueError("host.name exceeds the effective max_host_name_chars")
    limits = _exact_keys(settings["limits"], LIMIT_CEILINGS, "limits")
    for field, ceiling in LIMIT_CEILINGS.items():
        bound = min([ceiling, *(runtime[key] for key in PACKING_RUNTIME_LIMITS[field])])
        _int(limits[field], f"limits.{field}", 1, bound)
    for field, _, maximum in DEADLINES:
        _seconds(settings[field], field, runtime[maximum])
    if settings["cli_calibration"] not in (None, settings["calibration"]):
        raise ValueError("cli_calibration must be null or the record calibration")
    if settings["cli_states"] not in (None, OUTPUT_OPTIONS["states"]):
        raise ValueError("cli_states must be null or selected")
    return manifest


def check_identity_model(model):
    """The receipt's exact six-key identity_model used in scope and batch IDs."""
    _exact_keys(model, IDENTITY_MODEL_KEYS, "identity_model")
    _text(model["id"], "identity_model.id", 128)
    _text(model["implementation_version"], "identity_model.implementation_version")
    for field in (
        "parameter_json_sha256",
        "coefficient_array_sha256",
        "intercept_array_sha256",
    ):
        checked_hash(model[field])
    _commit(model["source_commit"], "identity_model.source_commit")
    return model


def check_expected_model(model, identity_model):
    """Receipt's exact emitted model object; only public named fields are read."""
    _exact_keys(model, MODEL_KEYS, "expected_model")
    parameters = model["parameters"]
    if (
        model["id"] != identity_model["id"]
        or model["implementation_version"] != identity_model["implementation_version"]
        or not isinstance(parameters, dict)
        or parameters.get("parameter_json_sha256")
        != identity_model["parameter_json_sha256"]
    ):
        raise ValueError("expected_model id/version/parameter hash disagree")
    if (
        model["kind"] != MODEL_KIND
        or model["terms_unit"] != TERMS_UNIT
        or model["not_modeled"] != NOT_MODELED
        or canonical_bytes(model["claims"]) != canonical_bytes(CLAIMS)
    ):
        raise ValueError("expected_model public kind/unit/claims disagree")


def check_runtime_limits(limits):
    """The receipt's complete effective batch.limits object (20 public keys)."""
    _exact_keys(limits, RUNTIME_LIMIT_CEILINGS, "runtime_limits")
    for field, ceiling in RUNTIME_LIMIT_CEILINGS.items():
        if isinstance(ceiling, float):
            _seconds(limits[field], f"runtime_limits.{field}", ceiling)
        else:
            _int(limits[field], f"runtime_limits.{field}", 1, ceiling)
    for _, default, maximum in DEADLINES:
        if limits[default] > limits[maximum]:
            raise ValueError(f"runtime_limits.{default} exceeds {maximum}")
    return limits


def build_manifest(identity, settings):
    """Assemble and validate a manifest from explicit identity and settings."""
    return check_manifest(
        {"schema_version": MANIFEST_SCHEMA, "identity": identity, "settings": settings}
    )


def expected_calibration(profile, host):
    """Result calibration object implied by the public profile/host registry."""
    entry = CALIBRATIONS[profile]
    name = host["name"] if host else None
    if profile == "ecoli_mg1655":
        status = (
            "unspecified"
            if name is None
            else "calibration_native"
            if name == NATIVE_HOST
            else "extrapolated"
        )
    else:
        status = (
            "in_vitro_reference" if name in (None, IN_VITRO_HOST) else ("extrapolated")
        )
    return {
        "profile": profile,
        "K": entry["K"],
        "beta": entry["beta"],
        "native_host": entry["native_host"],
        "host": host,
        "host_status": status,
    }


def state_count(length, tss):
    """Complete coordinate states of an oriented TSS (coordinate math only)."""
    if tss + ITR_NT > length:
        return 0
    return sum(
        d + s <= tss - FIXED_UPSTREAM_NT for d in DISCRIMINATORS for s in SPACERS
    )


def state_windows(tss, discriminator, spacer):
    """Oriented state intervals defined backward from the first ITR base."""
    disc = [tss - discriminator, tss]
    hex10 = [disc[0] - 6, disc[0]]
    spacer_window = [hex10[0] - spacer, hex10[0]]
    hex35 = [spacer_window[0] - 6, spacer_window[0]]
    gap = [hex35[0] - 1, hex35[0]]
    return {
        "UP": [gap[0] - 24, gap[0]],
        "gap": gap,
        "hex35": hex35,
        "spacer": spacer_window,
        "extended10": [spacer_window[1] - 3, spacer_window[1] - 1],
        "hex10": hex10,
        "discriminator": disc,
        "itr": [tss, tss + ITR_NT],
    }


def project_base(projection, local):
    """Genomic base of a local base: (origin + dir*f) mod contig_length."""
    direction = 1 if projection["sequence_strand"] == "+" else -1
    return (projection["origin"] + direction * local) % projection["contig_length"]


def genomic_strand(site_strand, sequence_strand):
    """Composed genomic strand: equal signs give +, different signs give -."""
    return "+" if site_strand == sequence_strand else "-"


def project_interval(projection, site_strand, interval):
    """Ascending genomic runs of a local interval, listed along transcription."""
    lower, upper = interval
    size = projection["contig_length"]
    start = (
        projection["origin"] + lower
        if projection["sequence_strand"] == "+"
        else projection["origin"] - upper + 1
    )
    first = start % size
    end = first + upper - lower
    runs = [[first, end]] if end <= size else [[first, size], [0, end - size]]
    strand = genomic_strand(site_strand, projection["sequence_strand"])
    return strand, runs[::-1] if strand == "-" else runs


def _segments(query, length, size):
    segments = query["segments"]
    if not isinstance(segments, list) or not 0 < len(segments) <= 2:
        raise ValueError("segments must list one or two runs")
    local = 0
    for segment in segments:
        _exact_keys(segment, ("local", "genomic", "oriented"), "segment")
        l0, l1 = _pair(segment["local"], "segment local", local, length)
        g0, g1 = _pair(segment["genomic"], "segment genomic", 0, size)
        if l0 != local or l1 - l0 != g1 - g0 or g1 == g0:
            raise ValueError("segments must be nonempty contiguous equal-length runs")
        oriented = [g0, g1] if query["strand"] == "+" else [size - g1, size - g0]
        if segment["oriented"] != oriented:
            raise ValueError("segment oriented interval disagrees with its genomic run")
        local = l1
    if local != length:
        raise ValueError("segments must cover the query sequence contiguously")
    return segments


def query_projection(query, genome):
    """Explicit projection of a transcript-oriented query, validated per base.

    The origin is the first segment's genomic start (plus) or end - 1 (minus).
    Each segment must equal the public contract's map of its local run, so every
    local base maps to the query's own genomic coordinate.
    """
    length, size, topology = (
        len(query["sequence"]),
        genome["length"],
        genome["topology"],
    )
    segments = _segments(query, length, size)
    g0, g1 = segments[0]["genomic"]
    origin = g0 if query["strand"] == "+" else g1 - 1
    crossing = (
        origin + length > size if query["strand"] == "+" else origin - (length - 1) < 0
    )
    if topology == "linear" and crossing:
        raise ValueError(f"Linear query maps outside its replicon: {query['query_id']}")
    if length > size:
        raise ValueError(f"Circular query repeats replicon bases: {query['query_id']}")
    projection = {
        "contig": query["genome_id"],
        "origin": origin,
        "contig_length": size,
        "sequence_strand": query["strand"],
        "topology": topology,
        "origin_crossing": crossing,
    }
    for segment in segments:
        if project_interval(projection, "+", segment["local"]) != (
            query["strand"],
            [segment["genomic"]],
        ):
            raise ValueError(f"Segment map disagrees: {query['query_id']}")
    return projection


def _check_context(query, length, lower, upper):
    context = _exact_keys(query["context"], CONTEXT_KEYS, "context")
    up, down = lower, length - upper
    if (
        _int(context["upstream_pad_nt"], "upstream_pad_nt", up, up) > UPSTREAM_NT
        or _int(context["downstream_pad_nt"], "downstream_pad_nt", down, down)
        > DOWNSTREAM_NT
    ):
        raise ValueError("Query padding exceeds the 67/19-nt context")
    short_up, short_down = UPSTREAM_NT - up, DOWNSTREAM_NT - down
    _int(context["upstream_shortfall_nt"], "upstream_shortfall_nt", short_up, short_up)
    _int(
        context["downstream_shortfall_nt"],
        "downstream_shortfall_nt",
        short_down,
        short_down,
    )
    full_lower, full_upper = max(lower, UPSTREAM_NT), min(upper, length - DOWNSTREAM_NT)
    supported = max(0, full_upper - full_lower)
    status = (
        "complete"
        if supported == upper - lower
        else "clipped"
        if supported
        else "no_full_state_support"
    )
    if (
        query["context_status"] != status
        or query["n_candidates_full_state_support"] != supported
        or query["full_state_support_local_range"]
        != ([full_lower, full_upper] if supported else None)
    ):
        raise ValueError(f"Query context support disagrees: {query['query_id']}")


def _check_candidates(query, projection, lower, upper):
    start, end = _pair(
        query["candidate_genomic_interval"],
        "candidate_genomic_interval",
        0,
        projection["contig_length"],
    )
    if end - start != upper - lower:
        raise ValueError("Candidate genomic and local ranges differ in size")
    if upper > lower:
        ends = [project_base(projection, lower), project_base(projection, upper - 1)]
        expected = [start, end - 1]
        if ends != (expected if query["strand"] == "+" else expected[::-1]):
            raise ValueError(
                f"Candidate genomic interval disagrees: {query['query_id']}"
            )


def check_query(query, genomes):
    """Validate one label-free query and return its explicit projection."""
    _exact_keys(query, QUERY_KEYS, "query")
    identity = _text(query["query_id"], "query_id", 256)
    genome_id = _text(query["genome_id"], "genome_id", MAX_CONTIG)
    if genome_id not in genomes or query["strand"] not in STRANDS:
        raise ValueError(f"Query lacks a declared genome/strand: {identity}")
    if query["orientation"] != "transcript 5'->3'":
        raise ValueError("Query sequence must be transcript-oriented")
    for field in ("tile_ordinal", "selection_rank"):
        _int(query[field], field, 0, MAX_GENOME_LENGTH)
    checked_hash(query["selection_key"])
    sequence = query["sequence"]
    if (
        not isinstance(sequence, str)
        or not sequence
        or set(sequence) - set("ACGT")
        or query["sequence_length"] != len(sequence)
        or digest(sequence) != query["sequence_sha256"]
    ):
        raise ValueError(f"Query sequence is not hash-bound uppercase ACGT: {identity}")
    lower, upper = _pair(
        query["candidate_local_range"], "candidate_local_range", 0, len(sequence)
    )
    _int(query["n_candidates"], "n_candidates", upper - lower, upper - lower)
    projection = query_projection(query, genomes[query["genome_id"]])
    _check_context(query, len(sequence), lower, upper)
    _check_candidates(query, projection, lower, upper)
    return projection


def check_query_document(queries):
    """Validate a canonical label-free query document; returns its genomes."""
    _exact_keys(queries, QUERY_DOCUMENT_KEYS, "query document")
    if queries["schema_version"] != QUERY_SCHEMA:
        raise ValueError("Query document schema must be " + QUERY_SCHEMA)
    genomes = queries["genomes"]
    if not isinstance(genomes, dict) or not 0 < len(genomes) <= MAX_GENOMES:
        raise ValueError(f"Query document needs 1..{MAX_GENOMES} genomes")
    for genome in genomes.values():
        _exact_keys(genome, GENOME_KEYS, "genome")
        _int(genome["length"], "genome length", 1, MAX_GENOME_LENGTH)
        checked_hash(genome["sequence_sha256"])
        if genome["topology"] not in ("linear", "circular"):
            raise ValueError("Genome topology must be linear or circular")
    rows = queries["queries"]
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_QUERIES:
        raise ValueError(f"Query document needs 1..{MAX_QUERIES} queries")
    if queries["queries_sha256"] != document_sha256(rows) or queries[
        "settings_sha256"
    ] != document_sha256(queries["settings"]):
        raise ValueError("Query document queries/settings hashes disagree")
    return genomes


def request_record(index, query, projection, manifest):
    """Exact runtime request record for one query: local '+' scan only."""
    settings, identity = manifest["settings"], manifest["identity"]
    record = {
        "id": f"q{index:06d}",
        "sequence": query["sequence"],
        "calibration": settings["calibration"],
        "scan": {
            "mode": "scan",
            "range": list(query["candidate_local_range"]),
            "strands": list(SCAN_STRANDS),
        },
        "projection": projection,
        "output": dict(OUTPUT_OPTIONS),
        "model": {
            "id": identity["identity_model"]["id"],
            "parameter_json_sha256": identity["identity_model"][
                "parameter_json_sha256"
            ],
        },
    }
    host = settings["host"]
    if host is not None:
        record["host"] = {"name": host["name"]}
        if host["taxon_id"] is not None:
            record["host"]["taxon_id"] = host["taxon_id"]
    return record


def _compact(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def pack(records, limits):
    """Pack records deterministically in order under every aggregate limit.

    records: (record, bases, sites) tuples. A record exceeding a per-record or
    whole-batch limit fails preparation rather than being dropped or clipped.
    Byte sizes are of the exact canonical request file.
    """
    fixed = len(REQUEST_PREFIX) + len(REQUEST_SUFFIX)
    batches, current = [], None
    for record, bases, sites in records:
        size = len(_compact(record))
        for name, value, limit in (
            ("bases_per_record", bases, limits["bases_per_record"]),
            ("sites_per_record", sites, limits["sites_per_record"]),
            ("bases_per_batch", bases, limits["bases_per_batch"]),
            ("sites_per_batch", sites, limits["sites_per_batch"]),
            ("request_bytes", fixed + size, limits["request_bytes"]),
        ):
            if value > limit:
                raise ValueError(
                    f"Request {record['id']} exceeds {name}: {value} > {limit}"
                )
        if current is None or (
            len(current["records"]) + 1 > limits["records_per_batch"]
            or current["bases"] + bases > limits["bases_per_batch"]
            or current["sites"] + sites > limits["sites_per_batch"]
            or current["bytes"] + 1 + size > limits["request_bytes"]
        ):
            current = {"records": [], "bases": 0, "sites": 0, "bytes": fixed - 1}
            batches.append(current)
        current["records"].append(record)
        current["bases"] += bases
        current["sites"] += sites
        current["bytes"] += 1 + size
    return batches


def batch_id(document, settings, identity):
    """Public batch_id over the exact parsed request and runtime settings."""
    model = identity["identity_model"]
    payload = {
        "input": document,
        "model": {
            "id": model["id"],
            "implementation_version": model["implementation_version"],
            "parameter_json_sha256": model["parameter_json_sha256"],
        },
        "limits": settings["runtime_limits"],
        "seconds_per_record": settings["seconds_per_record"],
        "seconds_per_batch": settings["seconds_per_batch"],
        "cli_calibration": settings["cli_calibration"],
        "cli_states": settings["cli_states"],
    }
    return runtime_sha256(payload)


def prediction_identity(record, calibration, identity_model):
    """(scope_id, prediction_id) from the literal public payloads of a request."""
    scope_id = runtime_sha256(
        {
            "schema_version": CONTRACT_VERSION,
            "model": identity_model,
            "calibration": {
                "profile": calibration["profile"],
                "host": calibration["host"],
            },
            "normalized_dna_sha256": digest(record["sequence"]),
            "projection": record["projection"],
        }
    )
    prediction_id = runtime_sha256(
        {"scope_id": scope_id, "scan": record["scan"], "output": record["output"]}
    )
    return scope_id, prediction_id


def request_document(records):
    """Runtime request envelope; serialized with canonical_bytes."""
    return {"defaults": {}, "records": records, "schema_version": CONTRACT_VERSION}


def prepare(queries, manifest):
    """Immutable request plan from label-free queries and an explicit manifest."""
    manifest = check_manifest(manifest)
    genomes = check_query_document(queries)
    runtime = manifest["settings"]["runtime_limits"]
    entries, query_ids = [], []
    for index, query in enumerate(queries["queries"]):
        projection = check_query(query, genomes)
        if query["query_id"] in query_ids:
            raise ValueError(f"Duplicate query identity: {query['query_id']}")
        record = request_record(index, query, projection, manifest)
        if len(record["id"]) > runtime["max_id_chars"] or (
            len(projection["contig"]) > runtime["max_contig_chars"]
        ):
            raise ValueError("Request ID or contig exceeds the effective field limits")
        entries.append((record, len(query["sequence"]), query["n_candidates"]))
        query_ids.append(query["query_id"])
    packed = pack(entries, manifest["settings"]["limits"])
    batches, offset = [], 0
    for batch_index, batch in enumerate(packed):
        document = request_document(batch["records"])
        raw = canonical_bytes(document)
        count = len(batch["records"])
        batches.append(
            {
                "batch_index": batch_index,
                "request_sha256": digest(raw),
                "request_bytes": len(raw),
                "batch_id": batch_id(
                    document, manifest["settings"], manifest["identity"]
                ),
                "n_records": count,
                "n_bases": batch["bases"],
                "n_sites": batch["sites"],
                "records": [
                    {"request_id": record["id"], "query_id": query_id}
                    for record, query_id in zip(
                        batch["records"],
                        query_ids[offset : offset + count],
                        strict=True,
                    )
                ],
                "request": document,
            }
        )
        offset += count
    settings = manifest["settings"]
    return {
        "schema_version": PLAN_SCHEMA,
        "scope": (
            "outcome-free runtime request plan; no labels, scores or runtime "
            "execution; transcript-oriented local '+' scans only"
        ),
        "tool_sha256": tool_sha256(),
        "query_document_sha256": document_sha256(queries),
        "query_source": queries["source"],
        "query_settings_sha256": queries["settings_sha256"],
        "queries_sha256": queries["queries_sha256"],
        "manifest": manifest,
        "manifest_sha256": document_sha256(manifest),
        "identity_sha256": document_sha256(manifest["identity"]),
        "settings_sha256": document_sha256(settings),
        "public_contract_commit": manifest["identity"]["public_contract_commit"],
        "request_contract": {
            "request_schema_version": CONTRACT_VERSION,
            "result_schema_version": CONTRACT_VERSION,
            "scan_strands": list(SCAN_STRANDS),
            "output": dict(OUTPUT_OPTIONS),
        },
        "expected_calibration": expected_calibration(
            settings["calibration"], settings["host"]
        ),
        "totals": {
            "n_requests": len(entries),
            "n_batches": len(batches),
            "n_bases": sum(bases for _, bases, _ in entries),
            "n_sites": sum(sites for _, _, sites in entries),
        },
        "batches": batches,
    }


def plan_request_bytes(plan, batch_index):
    """Exact request file bytes of one planned batch, verified against its hash."""
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("Plan schema must be " + PLAN_SCHEMA)
    batches = plan["batches"]
    _int(batch_index, "batch index", 0, len(batches) - 1)
    batch = batches[batch_index]
    raw = canonical_bytes(batch["request"])
    if digest(raw) != batch["request_sha256"]:
        raise ValueError("Planned request bytes disagree with request_sha256")
    return raw


def check_model(model, identity):
    """Fail closed unless the result model equals the receipt's exact object."""
    if canonical_bytes(model) != canonical_bytes(identity["expected_model"]):
        raise ValueError("Result model identity disagrees with the plan")


def _check_selected(selected, site_id, tss, length, projection):
    _exact_keys(selected, SELECTED_KEYS, "selected state")
    d = _int(selected["discriminator_length"], "discriminator_length", 6, 10)
    s = _int(selected["spacer_length"], "spacer_length", 15, 20)
    if d + s > tss - FIXED_UPSTREAM_NT or tss + ITR_NT > length:
        raise ValueError("Selected state lacks complete context")
    if selected["state_id"] != f"{site_id}:d{d}s{s}":
        raise ValueError("Selected state_id disagrees with its site and state")
    terms = _exact_keys(selected["terms"], TERM_KEYS, "terms")
    if not all(finite_number(terms[key]) for key in TERM_KEYS) or not finite_number(
        selected["log_relative_transcription_score"]
    ):
        raise ValueError("Selected terms and log score must be finite numbers")
    score_status, relative = (
        selected["score_status"],
        selected["relative_transcription_score"],
    )
    # ok relative scores are exp() within the normal binary64 range: finite,
    # positive and never zero or subnormal; other statuses carry null.
    if score_status not in SCORE_STATUSES or (
        not (finite_number(relative) and relative >= sys.float_info.min)
        if score_status == "ok"
        else relative is not None
    ):
        raise ValueError("Relative score and score_status disagree")
    windows = state_windows(tss, d, s)
    _same(selected["intervals"], windows, "Selected local intervals")
    _same(selected["oriented_intervals"], windows, "Selected oriented intervals")
    _same(
        selected["genomic_intervals"],
        {
            name: project_interval(projection, "+", window)[1]
            for name, window in windows.items()
        },
        "Selected genomic intervals",
    )
    return terms["total"], score_status


def check_site(site, local, length, projection):
    """Validate one listed local '+' site; returns its candidate outcome."""
    _exact_keys(site, SITE_KEYS, "site")
    match = (
        SITE_ID.fullmatch(site["site_id"]) if isinstance(site["site_id"], str) else None
    )
    if match is None or int(match.group(2)) != local:
        raise ValueError(f"Site identity disagrees with planned base {local}")
    _same(site["strand"], "+", "Site strand")
    _same(site["tss"], {"forward_base": local, "oriented_base": local}, "Site TSS")
    strand = projection["sequence_strand"]
    _same(
        site["genomic"],
        {
            "contig": projection["contig"],
            "base": project_base(projection, local),
            "strand": strand,
            "sequence_strand": strand,
        },
        "Site genomic point",
    )
    _same(
        site["context"],
        {
            "required_upstream": UPSTREAM_NT,
            "required_downstream": DOWNSTREAM_NT,
            "available_upstream": local,
            "available_downstream": length - 1 - local,
        },
        "Site context",
    )
    count = state_count(length, local)
    _same(site["state_count"], count, "Site state_count")
    _same(site["complete_state_set"], count == FULL_STATE_COUNT, "complete_state_set")
    status, reason, attempted = site["status"], site["reason"], site["attempted"]
    if type(attempted) is not bool:
        raise ValueError("Site attempted must be a boolean")
    outcome = {
        "status": status,
        "reason": reason,
        "attempted": attempted,
        "state_count": count,
        "score": None,
        "score_status": None,
        "tied": False,
        "scope": match.group(1),
    }
    if status == "ok":
        tie = site["tie_count"]
        if reason is not None or not attempted or count == 0:
            raise ValueError("ok sites need an attempted complete state, no reason")
        _int(tie, "tie_count", 1, count)
        outcome["score"], outcome["score_status"] = _check_selected(
            site["selected"], site["site_id"], local, length, projection
        )
        outcome["tied"] = tie > 1
        return outcome
    if site["selected"] is not None or site["tie_count"] is not None:
        raise ValueError("Non-ok sites need null selected and tie_count")
    if status == "no_candidate":
        # Unattempted sites are failed; an evaluated no_candidate is attempted.
        if reason != "insufficient_context" or count or not attempted:
            raise ValueError(
                "no_candidate sites need attempted insufficient_context, 0 states"
            )
    elif (
        status != "failed"
        or reason not in FAILURE_REASONS
        or (not attempted and reason != "deadline_exceeded")
        or (reason == "nonfinite_arithmetic" and count == 0)
    ):
        raise ValueError(f"Invalid site status/reason: {status!r}/{reason!r}")
    return outcome


def check_coverage(coverage, status, sites):
    """Coverage must be the exact summary of the listed sites."""
    _exact_keys(coverage, COVERAGE_KEYS, "coverage")
    failed = [site for site in sites if site["status"] == "failed"]
    expected = {
        "planned_sites": len(sites),
        "scored_sites": sum(site["status"] == "ok" for site in sites),
        "partial_state_sites": sum(
            site["status"] == "ok" and site["state_count"] < FULL_STATE_COUNT
            for site in sites
        ),
        "insufficient_context_sites": sum(
            site["status"] == "no_candidate" for site in sites
        ),
        "failed_sites": sum(site["attempted"] for site in failed),
        "unattempted_sites": sum(not site["attempted"] for site in failed),
        "complete_context": all(
            site["state_count"] == FULL_STATE_COUNT for site in sites
        ),
        "complete": not failed,
    }
    _same({key: coverage[key] for key in expected}, expected, "Coverage")
    truncation = coverage["truncation"]
    if status != "failed":
        _same(truncation, None, "Coverage truncation")
        return
    _exact_keys(truncation, TRUNCATION_KEYS, "truncation")
    if truncation["reason"] not in {site["reason"] for site in failed}:
        raise ValueError("Truncation reason must be an actual failed-site reason")
    _same(
        [truncation["attempted_sites"], truncation["planned_sites"]],
        [sum(site["attempted"] for site in sites), len(sites)],
        "Truncation counts",
    )


def _check_input(value, sequence):
    # Planned sequences are strings of valid uppercase ACGT within limits, so
    # the public rules leave no null raw hash or normalization triplet.
    _exact_keys(value, INPUT_KEYS, "record input")
    _same(
        [value[key] for key in INPUT_KEYS],
        [digest(sequence), digest(sequence), len(sequence), NORMALIZATION],
        "Record input identity",
    )


def check_record(record, request, calibration, identity_model):
    """Validate one result record against its exact planned request."""
    _exact_keys(record, RECORD_KEYS, "result record")
    if record["id"] != request["id"]:
        raise ValueError("Result records are missing, extra or reordered")
    status = record["status"]
    if status not in RECORD_STATUSES:
        raise ValueError(f"Unknown record status: {status!r}")
    for field in ("reasons", "warnings", "errors"):
        if not isinstance(record[field], list):
            raise ValueError(f"Record {field} must be a list")
    if not all(isinstance(code, str) for code in record["reasons"]):
        raise ValueError("Record reasons must be stable code strings")
    sequence = request["sequence"]
    echoes = {
        "calibration": calibration,
        "scan": request["scan"],
        "projection": request["projection"],
    }
    _same(record["metadata"], None, "Record metadata")
    if status in ("invalid_input", "unsupported"):
        if (
            record["sites"] != []
            or record["prediction_id"] is not None
            or record["coverage"] is not None
        ):
            raise ValueError(f"{status} records need no sites, prediction or coverage")
        # Rejected records echo only fields that passed validation; each echo
        # present must still be the planned value.
        for field, expected in echoes.items():
            if record[field] is not None:
                _same(record[field], expected, f"Record {field}")
        _check_input(record["input"], sequence)
        return {"status": status, "sites": None}
    scope_id, prediction_id = prediction_identity(request, calibration, identity_model)
    if record["prediction_id"] != prediction_id:
        raise ValueError("Record prediction_id disagrees with its public payload")
    _check_input(record["input"], sequence)
    for field, expected in echoes.items():
        _same(record[field], expected, f"Record {field}")
    lower, upper = request["scan"]["range"]
    if not isinstance(record["sites"], list) or len(record["sites"]) != upper - lower:
        raise ValueError("Every planned site must be listed exactly once")
    sites = [
        check_site(site, lower + offset, len(sequence), request["projection"])
        for offset, site in enumerate(record["sites"])
    ]
    if any(site["scope"] != scope_id[:32] for site in sites):
        raise ValueError("Site IDs disagree with the record scope_id")
    implied = (
        "failed"
        if any(site["status"] == "failed" for site in sites)
        else "ok"
        if any(site["status"] == "ok" for site in sites)
        else "no_candidate"
    )
    if status != implied:
        raise ValueError(f"Record status {status!r} disagrees with its sites")
    # Valid empty scans finalize in preflight, before any deadline handling.
    if not sites and (record["reasons"] != ["empty_scan"] or record["errors"]):
        raise ValueError("Empty scans need exactly reasons [empty_scan], no errors")
    if sites and status == "no_candidate":
        if "insufficient_context" not in record["reasons"]:
            raise ValueError("no_candidate records need insufficient_context")
    check_coverage(record["coverage"], status, sites)
    return {"status": status, "sites": sites}


def check_batch_summary(summary, outcomes, settings, planned_batch_id):
    """Batch summary must restate the records and the exact planned identity."""
    _exact_keys(summary, BATCH_SUMMARY_KEYS, "result batch")
    if summary["batch_id"] != planned_batch_id:
        raise ValueError("Result batch_id disagrees with the planned batch payload")
    counts = summary["status_counts"]
    if not isinstance(counts, dict) or set(counts) - set(RECORD_STATUSES):
        raise ValueError("status_counts must use record statuses")
    observed = [counts.get(status, 0) for status in RECORD_STATUSES]
    expected = [
        sum(outcome["status"] == status for outcome in outcomes)
        for status in RECORD_STATUSES
    ]
    _same(
        [summary["record_count"], summary["complete"], *observed],
        [len(outcomes), expected[-1] == 0, *expected],
        "Result batch summary",
    )
    _same(summary["limits"], settings["runtime_limits"], "Result batch limits")
    for field in ("seconds_per_record", "seconds_per_batch"):
        if type(summary[field]) is not float or summary[field] != settings[field]:
            raise ValueError(f"Result {field} disagrees with the manifest")


def check_result(raw, batch, plan):
    """Validate one completed batch's exact result bytes; returns record outcomes."""
    limit = plan["manifest"]["settings"]["runtime_limits"]["max_result_json_bytes"]
    if len(raw) > limit:
        raise ValueError(f"Result exceeds the effective {limit} bytes")
    result = _exact_keys(strict_json(raw), RESULT_KEYS, "result")
    authoritative = (
        json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    if len(authoritative) > limit:
        raise ValueError(f"Authoritative result exceeds the effective {limit} bytes")
    if result["schema_version"] != CONTRACT_VERSION:
        raise ValueError("Result schema_version must be " + CONTRACT_VERSION)
    check_model(result["model"], plan["manifest"]["identity"])
    records, requests = result["results"], batch["request"]["records"]
    if not isinstance(records, list) or len(records) != len(requests):
        raise ValueError("Result records are missing, extra or reordered")
    outcomes = [
        check_record(
            record,
            request,
            plan["expected_calibration"],
            plan["manifest"]["identity"]["identity_model"],
        )
        for record, request in zip(records, requests, strict=True)
    ]
    check_batch_summary(
        result["batch"], outcomes, plan["manifest"]["settings"], batch["batch_id"]
    )
    return outcomes


def candidate_rows(runtime_status, outcome, lower, upper):
    """Full candidate roster; null scores for every non-ok candidate."""
    if outcome is None or outcome["sites"] is None:
        status = {
            "invalid_input": "failed",
            "setup_failed": "failed",
            "execution_failed": "failed",
            "unsupported": "unsupported",
            "not_run": "not_run",
        }[runtime_status]
        return [
            {"local_index": local, "status": status, "score": None}
            for local in range(lower, upper)
        ]
    return [
        {"local_index": local, "status": site["status"], "score": site["score"]}
        for local, site in zip(range(lower, upper), outcome["sites"], strict=True)
    ]


def _collected_batch(entry, index, planned):
    _exact_keys(entry, COLLECTED_BATCH_KEYS, "collected batch")
    if (
        type(entry["batch_index"]) is not int
        or entry["batch_index"] != index
        or entry["request_sha256"] != planned
    ):
        raise ValueError("Collected batches are missing, extra or reordered")
    status, code, result = entry["status"], entry["exit_code"], entry["result_sha256"]
    if status == "completed":
        if type(code) is not int or code not in (0, 1):
            raise ValueError("completed batches need runtime exit code 0 or 1")
        return checked_hash(result)
    if status == "setup_failed":
        valid = type(code) is int and code == SETUP_EXIT_CODE
    elif status == "execution_failed":
        valid = type(code) is int and code not in (0, SETUP_EXIT_CODE)
    elif status == "not_run":
        valid = code is None
    else:
        raise ValueError(f"Unknown batch status: {status!r}")
    if not valid or result is not None:
        raise ValueError(
            f"{status} batches need a null result and exit code 2 (setup_failed), "
            "another nonzero code (execution_failed) or null (not_run)"
        )
    return None


def _counter(keys):
    return dict.fromkeys(keys, 0)


def adapt(
    queries, manifest, plan_sha256, collection_raw, collection_sha256, load_result
):
    """Validate collection bytes against the rebuilt plan; return (scores, audit).

    collection_raw is the exact collection file, verified against
    collection_sha256. load_result(sha256) returns the exact bytes of a
    completed batch result. Every planned batch appears exactly once. Identity,
    coordinate or summary disagreement raises; it is never converted into a
    missing or failed row.
    """
    plan = prepare(queries, manifest)
    if document_sha256(plan) != checked_hash(plan_sha256):
        raise ValueError("Rebuilt plan differs from the supplied plan hash")
    if len(collection_raw) > MAX_COLLECTION_BYTES:
        raise ValueError(f"Collection exceeds {MAX_COLLECTION_BYTES} bytes")
    if digest(collection_raw) != checked_hash(collection_sha256):
        raise ValueError("Collection file SHA-256 mismatch")
    collection = _exact_keys(strict_json(collection_raw), COLLECTION_KEYS, "collection")
    if (
        collection["schema_version"] != COLLECTION_SCHEMA
        or collection["plan_sha256"] != plan_sha256
    ):
        raise ValueError("Collection schema or plan binding mismatch")
    entries, batches = collection["batches"], plan["batches"]
    if not isinstance(entries, list) or len(entries) != len(batches):
        raise ValueError("Collected batches are missing, extra or reordered")
    lookup = {query["query_id"]: query for query in queries["queries"]}
    rows = []
    counts = {
        "batch_status": _counter(BATCH_STATUSES),
        "runtime_status": _counter(RUNTIME_STATUS_TO_REQUEST),
        "request_status": _counter(CANDIDATE_STATUSES),
        "candidate_status": _counter(CANDIDATE_STATUSES),
        "site_reason": _counter(SITE_REASONS),
        "selected_score_status": _counter(SCORE_STATUSES),
        "n_partial_state_sites": 0,
        "n_unattempted_sites": 0,
        "n_tied_selected_sites": 0,
        "n_complete_requests": 0,
        "n_incomplete_ok_requests": 0,
        "n_non_ok_requests_with_scored_candidates": 0,
    }
    seen_results = set()
    for index, (entry, batch) in enumerate(zip(entries, batches, strict=True)):
        result_sha = _collected_batch(entry, index, batch["request_sha256"])
        counts["batch_status"][entry["status"]] += 1
        outcomes = [None] * batch["n_records"]
        if result_sha is not None:
            if result_sha in seen_results:
                raise ValueError("A result file is bound to two batches")
            seen_results.add(result_sha)
            raw = load_result(result_sha)
            if digest(raw) != result_sha:
                raise ValueError(f"Result bytes disagree with batch {index} hash")
            outcomes = check_result(raw, batch, plan)
            failed = any(o["status"] in ("failed", "invalid_input") for o in outcomes)
            if entry["exit_code"] != int(failed):
                raise ValueError("Runtime exit code disagrees with record statuses")
        for planned, outcome in zip(batch["records"], outcomes, strict=True):
            runtime_status = outcome["status"] if outcome else entry["status"]
            lower, upper = lookup[planned["query_id"]]["candidate_local_range"]
            candidates = candidate_rows(runtime_status, outcome, lower, upper)
            status = RUNTIME_STATUS_TO_REQUEST[runtime_status]
            counts["runtime_status"][runtime_status] += 1
            counts["request_status"][status] += 1
            states = [candidate["status"] for candidate in candidates]
            for state in states:
                counts["candidate_status"][state] += 1
            if status == "ok":
                complete = all(state == "ok" for state in states)
                counts["n_complete_requests"] += complete
                counts["n_incomplete_ok_requests"] += not complete
            elif "ok" in states:
                counts["n_non_ok_requests_with_scored_candidates"] += 1
            for site in outcome["sites"] or () if outcome else ():
                if site["reason"] is not None:
                    counts["site_reason"][site["reason"]] += 1
                if site["score_status"] is not None:
                    counts["selected_score_status"][site["score_status"]] += 1
                counts["n_partial_state_sites"] += (
                    site["status"] == "ok" and site["state_count"] < FULL_STATE_COUNT
                )
                counts["n_unattempted_sites"] += not site["attempted"]
                counts["n_tied_selected_sites"] += site["tied"]
            rows.append(
                {
                    "request_id": planned["request_id"],
                    "query_id": planned["query_id"],
                    "status": status,
                    "runtime_status": runtime_status,
                    "candidates": candidates,
                }
            )
    scores = {
        "schema_version": SCORE_SCHEMA_V2,
        "query_document_sha256": plan["query_document_sha256"],
        "provenance": {
            "adapter_tool_sha256": plan["tool_sha256"],
            "plan_sha256": plan_sha256,
            "collection_sha256": collection_sha256,
            "score_field": SCORE_FIELD,
            "score_unit": TERMS_UNIT,
        },
        "results": rows,
    }
    audit = {
        "schema_version": AUDIT_SCHEMA,
        "scope": (
            "aggregate collection audit; per-case scores, reasons and runtime "
            "messages stay in the private collection and score document"
        ),
        "tool_sha256": plan["tool_sha256"],
        "plan_sha256": plan_sha256,
        "collection_sha256": collection_sha256,
        "scores_sha256": document_sha256(scores),
        "query_document_sha256": plan["query_document_sha256"],
        "manifest_sha256": plan["manifest_sha256"],
        "identity": plan["manifest"]["identity"],
        "settings_sha256": plan["settings_sha256"],
        "score_field": SCORE_FIELD,
        "totals": plan["totals"],
        "counts": counts,
    }
    return scores, audit


def _canonical_document(raw, name):
    document = strict_json(raw)
    if canonical_bytes(document) != raw:
        raise ValueError(f"{name} is not canonical tool output")
    return document


def _pinned(path, limit, expected, name):
    raw = read_bounded(path, limit)
    if digest(raw) != checked_hash(expected):
        raise ValueError(f"{name} file SHA-256 mismatch")
    return _canonical_document(raw, name)


RECEIPT_OBJECTS = ("identity_model", "expected_model", "runtime_limits")


def _receipt_object(path):
    return strict_json(read_bounded(path, MAX_MANIFEST_BYTES))


def _manifest_from_args(args):
    if args.host_taxon_id is not None and args.host_name is None:
        raise ValueError("--host-taxon-id requires --host-name")
    host = (
        None
        if args.no_host
        else {"name": args.host_name, "taxon_id": args.host_taxon_id}
    )
    identity = {field: getattr(args, field) for field in IDENTITY_KEYS[:3]}
    for field in RECEIPT_OBJECTS[:2]:
        identity[field] = _receipt_object(getattr(args, field))
    return build_manifest(
        identity,
        {
            "calibration": args.calibration,
            "host": host,
            "limits": {
                field: getattr(args, f"max_{field}") for field in LIMIT_CEILINGS
            },
            "runtime_limits": _receipt_object(args.runtime_limits),
            "seconds_per_record": args.seconds_per_record,
            "seconds_per_batch": args.seconds_per_batch,
            "cli_calibration": _none(args.cli_calibration),
            "cli_states": _none(args.cli_states),
        },
    )


def _none(text):
    return None if text == "none" else text


def _result_loader(paths):
    index = {}
    for path in paths:
        sha = digest(read_bounded(path, MAX_RESULT_BYTES))
        if sha in index:
            raise ValueError("Duplicate result file content")
        index[sha] = path
    used = set()

    def load(sha):
        if sha not in index:
            raise ValueError(f"No supplied result file has SHA-256 {sha}")
        used.add(sha)
        return read_bounded(index[sha], MAX_RESULT_BYTES)

    return load, index, used


def _write_pair(first, second, documents):
    if first.resolve() == second.resolve():
        raise ValueError("Score and audit outputs must differ")
    for path in (first, second):
        if os.path.lexists(path):
            raise ValueError(f"Output already exists: {path}")
    write_exclusive(first, documents[0], 0o600)
    try:
        write_exclusive(second, documents[1], 0o600)
    except OSError:
        os.unlink(first)
        raise


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    manifest = commands.add_parser("manifest")
    manifest.add_argument("output", type=Path)
    for field in IDENTITY_KEYS[:3]:
        manifest.add_argument("--" + field.replace("_", "-"), required=True)
    for field in RECEIPT_OBJECTS:
        manifest.add_argument("--" + field.replace("_", "-"), type=Path, required=True)
    manifest.add_argument("--calibration", choices=tuple(CALIBRATIONS), required=True)
    manifest.add_argument(
        "--cli-calibration", choices=("none", *CALIBRATIONS), required=True
    )
    manifest.add_argument("--cli-states", choices=("none", "selected"), required=True)
    host = manifest.add_mutually_exclusive_group(required=True)
    host.add_argument("--host-name")
    host.add_argument("--no-host", action="store_true")
    manifest.add_argument("--host-taxon-id", type=int)
    for field in LIMIT_CEILINGS:
        manifest.add_argument(
            "--max-" + field.replace("_", "-"), type=int, required=True
        )
    for field in ("seconds_per_record", "seconds_per_batch"):
        manifest.add_argument("--" + field.replace("_", "-"), type=float, required=True)
    prepare_command = commands.add_parser("prepare")
    adapt_command = commands.add_parser("adapt")
    for command in (prepare_command, adapt_command):
        command.add_argument("queries", type=Path)
        command.add_argument("manifest", type=Path)
        command.add_argument("--queries-sha256", required=True)
        command.add_argument("--manifest-sha256", required=True)
    prepare_command.add_argument("plan", type=Path)
    export = commands.add_parser("export-request")
    export.add_argument("plan", type=Path)
    export.add_argument("batch_index", type=int)
    export.add_argument("output", type=Path)
    for command in (export, adapt_command):
        command.add_argument("--plan-sha256", required=True)
    adapt_command.add_argument("collection", type=Path)
    adapt_command.add_argument("scores", type=Path)
    adapt_command.add_argument("audit", type=Path)
    adapt_command.add_argument("--collection-sha256", required=True)
    adapt_command.add_argument("--result", type=Path, action="append", default=[])
    return parser


def _run(args):
    if args.command == "manifest":
        document = _manifest_from_args(args)
        write_exclusive(args.output, document, 0o644)
        return {"output_sha256": document_sha256(document)}
    if args.command == "export-request":
        plan = _pinned(args.plan, MAX_PLAN_BYTES, args.plan_sha256, "Plan")
        raw = plan_request_bytes(plan, args.batch_index)
        with os.fdopen(
            os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644), "wb"
        ) as stream:
            stream.write(raw)
        return {"request_sha256": digest(raw)}
    queries = _pinned(
        args.queries, MAX_QUERY_DOCUMENT_BYTES, args.queries_sha256, "Query document"
    )
    manifest = _pinned(
        args.manifest, MAX_MANIFEST_BYTES, args.manifest_sha256, "Manifest"
    )
    if args.command == "prepare":
        plan = prepare(queries, manifest)
        write_exclusive(args.plan, plan, 0o644)
        return {
            "n_batches": plan["totals"]["n_batches"],
            "output_sha256": document_sha256(plan),
        }
    collection = read_bounded(args.collection, MAX_COLLECTION_BYTES)
    load, supplied, used = _result_loader(args.result)
    scores, audit = adapt(
        queries, manifest, args.plan_sha256, collection, args.collection_sha256, load
    )
    if used != set(supplied):
        raise ValueError("Supplied result files are not all bound to the collection")
    _write_pair(args.scores, args.audit, (scores, audit))
    return {
        "scores_sha256": document_sha256(scores),
        "audit_sha256": document_sha256(audit),
    }


def main(argv=None):
    """Write a manifest, plan, request or score/audit pair; nonzero on failure."""
    args = _parser().parse_args(argv)
    try:
        summary = _run(args)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
