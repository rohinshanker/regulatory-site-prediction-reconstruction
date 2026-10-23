"""Validate explicitly supplied adjacent CDSs on a linear RNA segment."""

import re

from regsite.sequence import (
    InputError,
    normalize_rna,
    reverse_complement,
    sequence_hash,
)


class CouplingGeometryError(ValueError):
    """An invalid input or unsupported CDS geometry, identified by ``code``."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize the machine-readable code and explanatory message."""
        super().__init__(message)
        self.code = code


def _parse_cds(
    value: object, length: int, strand: str
) -> tuple[str, list[int], list[int]]:
    """Validate a CDS object and map its interval to transcript orientation."""
    if not isinstance(value, dict) or value.keys() != {"id", "interval"}:
        raise CouplingGeometryError(
            "invalid_input", "each CDS must have exactly id and interval keys"
        )
    cds_id = value["id"]
    if (
        not isinstance(cds_id, str)
        or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", cds_id) is None
    ):
        raise CouplingGeometryError("invalid_input", "invalid CDS id")
    bounds = value["interval"]
    if (
        not isinstance(bounds, list)
        or len(bounds) != 2
        or any(type(bound) is not int for bound in bounds)
        or not 0 <= bounds[0] < bounds[1] <= length
    ):
        raise CouplingGeometryError("invalid_input", "invalid CDS interval")
    start, end = bounds
    oriented = [length - end, length - start] if strand == "-" else [start, end]
    return cds_id, [start, end], oriented


def _annotate_cds(
    cds_id: str, interval: list[int], oriented: list[int], sequence: str
) -> dict:
    """Check complete in-frame CDS codons and return explicit annotations."""
    start, end = oriented
    if end - start < 6 or (end - start) % 3 != 0:
        raise CouplingGeometryError(
            "unsupported_geometry", "complete CDS length must be >=6 and divisible by 3"
        )
    start_codon, stop_codon = sequence[start : start + 3], sequence[end - 3 : end]
    if start_codon not in ("AUG", "GUG", "UUG"):
        raise CouplingGeometryError(
            "unsupported_geometry", "unsupported CDS start codon"
        )
    if stop_codon not in ("UAA", "UAG", "UGA"):
        raise CouplingGeometryError(
            "unsupported_geometry", "missing terminal stop codon"
        )
    for position in range(start + 3, end - 3, 3):
        if sequence[position : position + 3] in ("UAA", "UAG", "UGA"):
            raise CouplingGeometryError(
                "unsupported_geometry", "internal in-frame stop"
            )
    return {
        "id": cds_id,
        "interval": interval,
        "oriented_interval": oriented,
        "start_codon": start_codon,
        "stop_codon": stop_codon,
    }


def validate_pair_geometry(
    sequence: object, strand: object, upstream: object, downstream: object
) -> dict:
    """Validate two explicitly ordered complete CDSs without inferring a model.

    Args:
        sequence: DNA/RNA text normalized using the shared sequence contract.
        strand: Exactly '+' or '-', selecting transcript orientation.
        upstream: A dict with exactly id and interval in normalized input coordinates.
        downstream: The analogous dict for the downstream CDS, with a distinct id.

    Returns:
        Normalized and oriented RNA, their SHA-256 hashes, strand, distance_nt,
        and upstream/downstream annotations. All intervals are ascending,
        zero-based and half-open, including the complete terminal stop codon.
        Distance is downstream oriented start minus upstream oriented end;
        negative distances denote overlap and have no model-specific limit.

    Raises:
        CouplingGeometryError: With code invalid_input for malformed inputs, or
            unsupported_geometry for incomplete CDSs, unsupported codons,
            internal stops, nesting, reversed order or same-frame overlaps.
    """
    try:
        normalized = normalize_rna(sequence, "sequence", max_length=100000)
    except InputError as exc:
        raise CouplingGeometryError("invalid_input", str(exc)) from exc
    if not isinstance(strand, str) or strand not in ("+", "-"):
        raise CouplingGeometryError("invalid_input", "strand must be '+' or '-'")
    oriented = reverse_complement(normalized) if strand == "-" else normalized
    up_id, up_interval, up_oriented = _parse_cds(upstream, len(normalized), strand)
    down_id, down_interval, down_oriented = _parse_cds(
        downstream, len(normalized), strand
    )
    if up_id == down_id:
        raise CouplingGeometryError("invalid_input", "CDS ids must be distinct")
    if up_oriented[0] >= down_oriented[0] or up_oriented[1] >= down_oriented[1]:
        raise CouplingGeometryError(
            "unsupported_geometry", "CDSs must have increasing oriented starts and ends"
        )
    distance = down_oriented[0] - up_oriented[1]
    if distance < 0 and (down_oriented[0] - up_oriented[0]) % 3 == 0:
        raise CouplingGeometryError(
            "unsupported_geometry", "same-frame overlapping CDSs"
        )
    return {
        "sequence": normalized,
        "oriented_sequence": oriented,
        "sequence_sha256": sequence_hash(normalized),
        "oriented_sequence_sha256": sequence_hash(oriented),
        "strand": strand,
        "distance_nt": distance,
        "upstream": _annotate_cds(up_id, up_interval, up_oriented, oriented),
        "downstream": _annotate_cds(down_id, down_interval, down_oriented, oriented),
    }
