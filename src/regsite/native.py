"""Portable native-context preparation, scoring and genomic projection.

Source-specific annotation/TSS association and experimental labels belong to
the evidence producer. This module validates those identities and extracts the
declared scenario; it never selects a transcript using a predicted outcome.
"""

import hashlib
import json
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any

from regsite import __version__
from regsite.backend import RnaStructure
from regsite.contracts import RbsRequest
from regsite.genome import GenomicPath
from regsite.profiles import get_profile
from regsite.rbs import predict
from regsite.sequence import InputError, normalize_rna, sequence_hash

INPUT_VERSION = "native-rbs-evidence-1"
RESULT_VERSION = "native-rbs-result-1"
MAX_NATIVE_RECORDS = 10_000


class UnsupportedContext(ValueError):
    """A valid source record lacks a supported transcript/start context."""


def _text(value: object, label: str, limit: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise InputError(f"{label} must be 1..{limit} characters without controls")
    return value


def _integer(value: object, label: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise InputError(f"{label} must be an integer from {low} to {high}")
    return value


@dataclass(frozen=True)
class Genome:
    """A hash-checked, versioned DNA replicon, normalized once per batch."""

    rna: str
    sha256: str
    accession: str
    assembly: str
    annotation: str
    circular: bool

    @classmethod
    def from_dict(cls, value: object) -> "Genome":
        """Require canonical ACGT DNA bytes so the evidence hash is unambiguous."""
        if not isinstance(value, dict):
            raise InputError("genome must be an object")
        sequence = value.get("sequence")
        if (
            not isinstance(sequence, str)
            or not 1 <= len(sequence) <= 20_000_000
            or set(sequence) - set("ACGT")
        ):
            raise InputError("genome sequence must be 1..20M normalized ACGT bases")
        digest = sequence_hash(sequence)
        if value.get("sequence_sha256") != digest:
            raise InputError("genome sequence_sha256 mismatch")
        topology = value.get("topology")
        if topology not in ("linear", "circular"):
            raise InputError("genome topology must be linear or circular")
        return cls(
            sequence.replace("T", "U"),
            digest,
            _text(value.get("accession"), "accession"),
            _text(value.get("assembly"), "assembly"),
            _text(value.get("annotation"), "annotation"),
            topology == "circular",
        )


@dataclass(frozen=True)
class NativeContext:
    """One extracted scenario with a supplied start and exact genomic path."""

    path: GenomicPath
    sequence: str
    start: int
    request: dict
    warnings: tuple[str, ...]
    genome: Genome

    def describe(self) -> dict:
        """Export context hashes and segments separately from scientific evidence."""
        return {
            "genome": {
                "accession": self.genome.accession,
                "assembly": self.genome.assembly,
                "annotation": self.genome.annotation,
                "sequence_sha256": self.genome.sha256,
                "topology": "circular" if self.genome.circular else "linear",
            },
            "sequence": self.sequence,
            "sequence_sha256": sequence_hash(self.sequence),
            "sequence_alphabet": "RNA",
            "start": self.start,
            "path": asdict(self.path),
            "genomic_segments": [
                asdict(p) for p in self.path.project(0, self.path.length)
            ],
            "genomic_start_segments": [
                asdict(p) for p in self.path.project(self.start, self.start + 3)
            ],
        }


def prepare_context(record: object, genome: Genome) -> NativeContext:
    """Validate the native evidence boundary and extract up to 100/100 nt.

    Measured TSSs clip leaders. Missing TSSs use an explicitly unmeasured genomic
    flank. Origin-crossing must be declared; a negative leader never wraps into
    a chromosome-long leader. Unresolved starts/internal TSSs stay unsupported.
    """
    if not isinstance(record, dict):
        raise InputError("native record must be an object")
    identifier = _text(record.get("id"), "id", 128)
    _text(record.get("genome_id"), "genome_id")
    for key in (
        "mapping_status",
        "transcript_start_evidence",
        "translation_start_evidence",
    ):
        _text(record.get(key), key)
    _text(record.get("anti_sd_provenance"), "anti_sd_provenance", 2048)
    host = _text(record.get("host"), "host", 128)
    anti_sd = normalize_rna(record.get("anti_sd"), "anti_sd", max_length=9)
    if len(anti_sd) != 9:
        raise InputError("native anti_sd must contain exactly nine nucleotides")
    temperature = record.get("temperature_c", 37.0)
    if type(temperature) not in (int, float) or not 0 <= temperature <= 100:
        raise InputError("native temperature_c must be finite and between 0 and 100")
    for key in ("conditions", "warnings"):
        if not isinstance(record.get(key), list):
            raise InputError(f"{key} must be an explicit list")
    if any(not isinstance(item, str) for item in record["warnings"]):
        raise InputError("warnings must contain strings")
    for key, expected in (
        ("assembly", genome.assembly),
        ("annotation", genome.annotation),
        ("replicon", genome.accession),
        ("genome_sha256", genome.sha256),
    ):
        if key in record and record[key] != expected:
            raise InputError(f"record {key} disagrees with pinned genome")
    strand = record.get("strand")
    crossing = record.get("origin_crossing")
    if strand not in ("+", "-") or type(crossing) is not bool:
        raise InputError("record requires strand +/- and boolean origin_crossing")
    if crossing and not genome.circular:
        raise InputError("origin_crossing requires a circular genome")
    size, step = len(genome.rna), 1 if strand == "+" else -1
    upstream = _integer(record.get("upstream_limit_nt"), "upstream_limit_nt", 0, 100)
    downstream = _integer(
        record.get("downstream_length_nt"), "downstream_length_nt", 3, 100
    )
    requested_downstream = downstream
    for field in ("tss_zero_based", "cds_start_zero_based", "leader_length_nt"):
        if field not in record:
            raise InputError(f"missing explicit {field} (use null if unknown)")
    tss, start, leader = (
        record[k]
        for k in ("tss_zero_based", "cds_start_zero_based", "leader_length_nt")
    )
    if tss is not None:
        _integer(tss, "tss_zero_based", 0, size - 1)
    if start is None:
        raise UnsupportedContext("unresolved_translation_start")
    _integer(start, "cds_start_zero_based", 0, size - 1)
    warnings = list(record["warnings"])
    if tss is None:
        if leader is not None:
            raise InputError("unknown TSS requires null leader_length_nt")
        warnings.append("unmeasured_transcript_context_assumed_genomic_flank")
        leader = upstream
    else:
        _integer(leader, "leader_length_nt", -size + 1, size - 1)
        distance = (start - tss) * step
        expected = distance % size if crossing else distance
        if leader != expected:
            raise InputError(
                "leader_length_nt disagrees with TSS/start/strand/topology"
            )
        if leader < 0:
            raise UnsupportedContext("tss_inside_current_cds")
    count_up = min(leader, upstream)
    # Circular topology alone is not authority to cross the origin.
    if not crossing:
        count_up = min(count_up, start if step == 1 else size - start - 1)
        downstream = min(downstream, size - start if step == 1 else start + 1)
    if downstream < 3:
        raise UnsupportedContext("start_codon_crosses_undeclared_contig_boundary")
    if count_up + downstream > size:
        raise InputError("native context would traverse the contig more than once")
    path = GenomicPath(
        size,
        (start - step * count_up) % size,
        count_up + downstream,
        strand,
        genome.circular,
    )
    sequence = path.extract(genome.rna)
    request = {
        "id": identifier,
        "sequence": sequence,
        "start_positions": [count_up],
        "anti_sd": anti_sd,
        "temperature_c": temperature,
        "host": host,
    }
    RbsRequest.from_dict(request)
    warnings.extend(
        (
            "supplied_start_evidence_does_not_establish_model_accuracy",
            "operon_coupling_not_modeled",
            "downstream_context_extent_not_experimentally_verified",
        )
    )
    if count_up < leader:
        warnings.append("leader_clipped_by_context_limit_or_contig_boundary")
    if downstream < requested_downstream:
        warnings.append("downstream_context_clipped_at_contig_boundary")
    return NativeContext(path, sequence, count_up, request, tuple(warnings), genome)


def _project_sites(prediction: dict, path: GenomicPath) -> list[dict]:
    sites = []
    successful = sorted(
        (s for s in prediction["sites"] if s["status"] == "ok"),
        key=lambda s: (-s["tir"], s["oriented_start"]),
    )
    ranks = {s["oriented_start"]: rank for rank, s in enumerate(successful, 1)}
    for site in prediction["sites"]:
        mapped: dict[str, Any] = {
            "oriented_start": site["oriented_start"],
            "start_point": path.point(site["oriented_start"]),
            "status": site["status"],
            "rank_among_successful_candidates": ranks.get(site["oriented_start"]),
        }
        for field in (
            "start_codon",
            "binding_interval",
            "standby_interval",
            "coding_footprint",
        ):
            interval = site.get(field)
            mapped[field] = (
                [asdict(p) for p in path.project(interval["start"], interval["end"])]
                if interval is not None
                else None
            )
        mapped["window"] = [
            asdict(p)
            for p in path.project(
                site["window"]["oriented_start"], site["window"]["oriented_end"]
            )
        ]
        sites.append(mapped)
    return sites


def predict_native(
    value: object,
    backend: RnaStructure,
    *,
    profile: str = "context2017",
    mode: str = "supplied_start",
    seconds_per_record: float = 60,
    seconds_per_batch: float = 300,
) -> dict:
    """Score source-neutral records with per-record and total wall-time budgets.

    Setup errors raise InputError. Invalid genomes/records remain explicit rows
    while other records run. Conditional scanning ranks starts only within the
    supplied context; it is not transcript/genome-wide discovery.
    """
    specification = get_profile(profile)
    if mode not in ("supplied_start", "conditional_scan"):
        raise InputError("native mode must be supplied_start or conditional_scan")
    for budget, limit in ((seconds_per_record, 120), (seconds_per_batch, 3600)):
        if type(budget) not in (int, float) or not 0 < budget <= limit:
            raise InputError("invalid native record/batch time budget")
    if not isinstance(value, dict) or value.get("schema_version") != INPUT_VERSION:
        raise InputError("native batch requires schema_version native-rbs-evidence-1")
    records, sources = value.get("records"), value.get("genomes")
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_NATIVE_RECORDS:
        raise InputError("native batch requires 1..10000 records")
    if not isinstance(sources, dict) or not 1 <= len(sources) <= 100:
        raise InputError("native batch requires 1..100 genome objects")
    total_bases = sum(
        len(source["sequence"])
        for source in sources.values()
        if isinstance(source, dict) and isinstance(source.get("sequence"), str)
    )
    if total_bases > 20_000_000:
        raise InputError("native batch exceeds 20M total genome bases")
    identity = {
        "schema_version": RESULT_VERSION,
        "input": value,
        "implementation_version": __version__,
        "backend": backend.identity,
        "profile": specification.model_id,
        "mode": mode,
        "seconds_per_record": float(seconds_per_record),
        "seconds_per_batch": float(seconds_per_batch),
    }
    try:
        encoded = json.dumps(
            identity, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (ValueError, TypeError, RecursionError) as exc:
        raise InputError("native batch must contain finite JSON values") from exc
    if len(encoded) > 40_000_000:
        raise InputError("native batch exceeds 40M encoded bytes")
    digest = hashlib.sha256(encoded).hexdigest()
    genomes: dict[str, Genome | InputError] = {}
    for key, source in sources.items():
        _text(key, "genome_id")
        try:
            genomes[key] = Genome.from_dict(source)
        except InputError as exc:
            genomes[key] = exc
    deadline = time.monotonic() + seconds_per_batch
    results, seen = [], set()
    for record in records:
        result: dict[str, Any] = {
            "id": None,
            "status": "invalid_input",
            "reason": None,
            "context": None,
            "prediction": None,
            "genomic_sites": [],
            "warnings": [],
            "evidence": deepcopy(record),
        }
        try:
            if not isinstance(record, dict):
                raise InputError("native record must be an object")
            identifier = _text(record.get("id"), "id", 128)
            result["id"] = identifier
            if identifier in seen:
                raise InputError("duplicate native record id")
            seen.add(identifier)
            genome_id = _text(record.get("genome_id"), "genome_id")
            if genome_id not in genomes:
                raise InputError("record references unknown genome_id")
            genome = genomes[genome_id]
            if isinstance(genome, InputError):
                raise genome
            context = prepare_context(record, genome)
            result.update(context=context.describe(), warnings=list(context.warnings))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result.update(
                    status="failed", reason="native_batch_time_budget_exhausted"
                )
            else:
                request = dict(context.request)
                if mode == "conditional_scan":
                    request["start_positions"] = None
                prediction = predict(
                    request,
                    backend,
                    seconds=min(seconds_per_record, remaining),
                    profile=profile,
                )
                result.update(
                    status=prediction["status"],
                    reason=prediction["reason"],
                    prediction=prediction,
                    genomic_sites=_project_sites(prediction, context.path),
                )
        except UnsupportedContext as exc:
            result.update(status="unsupported", reason=str(exc))
        except InputError as exc:
            result.update(status="invalid_input", reason=str(exc))
        results.append(result)
    return {
        "schema_version": RESULT_VERSION,
        "batch_id": digest,
        "mode": mode,
        "model_id": specification.model_id,
        "execution": {
            "implementation_version": __version__,
            "backend": deepcopy(backend.identity),
            "seconds_per_record": float(seconds_per_record),
            "seconds_per_batch": float(seconds_per_batch),
        },
        "coordinate_space": (
            "zero-based half-open reference segments in transcript order"
        ),
        "task_scope": "supplied start strength"
        if mode == "supplied_start"
        else "conditional candidate ranking, not genome discovery",
        "results": results,
    }
