"""Frozen, label-independent features from a validated oriented RBS request.

Exact sequence matches describe sequence context, not biological binding
intervals or energies. Energy features require an explicit matching prediction.
"""

import math

from regsite.contracts import RbsRequest
from regsite.sequence import reverse_complement

_SEQUENCE_KIND = "sequence-v1"
_ENERGY_KIND = "context-energy-sequence-v1"
_ENERGY_MODEL = "context2017-rnastructure-6.6-reconstruction-1"
_START_CODONS = ("AUG", "GUG", "UUG", "CUG")
_SEQUENCE_NAMES = (
    "clipped_leader_length",
    "clipped_downstream_length",
    *(
        f"{region}_{base}_proportion"
        for region in ("up35", "up100", "coding13", "post13to35")
        for base in "ACG"
    ),
    "start_GUG",
    "start_UUG",
    "start_CUG",
    "sd_longest_exact_run",
    "sd_gap_of_best_run",
)
_ENERGY_NAMES = (
    "dG_total",
    "dG_mRNA",
    "dG_spacing",
    "dG_standby_signed",
    "dG_post_footprint",
)


class FeatureError(ValueError):
    """The requested feature kind or its input context is unsupported/invalid."""


def feature_names(kind: str) -> tuple[str, ...]:
    """Return the frozen feature order for an explicitly supported kind."""
    if kind == _SEQUENCE_KIND:
        return _SEQUENCE_NAMES
    if kind == _ENERGY_KIND:
        return _SEQUENCE_NAMES + _ENERGY_NAMES
    raise FeatureError(f"unsupported feature kind: {kind!r}")


def _exact_sd_match(leader: str, target: str) -> tuple[float, float]:
    """Rank shared runs by length, distance to gap 5, then smaller gap."""
    for length in range(min(len(leader), len(target)), 0, -1):
        gaps = [
            len(leader) - end
            for end in range(length, len(leader) + 1)
            if leader[end - length : end] in target
        ]
        if gaps:
            return float(length), float(min(gaps, key=lambda gap: (abs(gap - 5), gap)))
    return 0.0, 36.0


def _energy_features(
    request: RbsRequest, start: int, prediction: dict | None
) -> tuple[float, ...]:
    if len(request.oriented_sequence) - start <= 13:
        raise FeatureError("coding footprint or post-footprint context is truncated")
    if not isinstance(prediction, dict) or prediction.get("status") != "ok":
        raise FeatureError("energy features require an explicit successful prediction")
    model = prediction.get("model")
    if not isinstance(model, dict) or model.get("id") != _ENERGY_MODEL:
        raise FeatureError(f"energy features require model {_ENERGY_MODEL}")
    context = prediction.get("input")
    if not isinstance(context, dict):
        raise FeatureError("prediction input context is missing")
    expected = {
        "sequence": request.sequence,
        "normalized_sha256": request.normalized_sha256,
        "oriented_sequence": request.oriented_sequence,
        "oriented_sha256": request.oriented_sha256,
        "anti_sd": request.anti_sd,
        "strand": request.strand,
    }
    if any(context.get(key) != value for key, value in expected.items()):
        raise FeatureError("prediction sequence, hash, anti_sd or strand mismatch")
    temperature = context.get("temperature_c")
    if type(temperature) not in (int, float) or temperature != request.temperature_c:
        raise FeatureError("prediction temperature mismatch")
    starts = context.get("start_positions")
    if (
        not isinstance(starts, (list, tuple))
        or len(starts) != 1
        or type(starts[0]) is not int
        or starts[0] != start
    ):
        raise FeatureError("prediction must use the matching explicit start")
    sites = prediction.get("sites")
    if not isinstance(sites, list) or len(sites) != 1:
        raise FeatureError("prediction must contain exactly one matching site")
    site = sites[0]
    if (
        not isinstance(site, dict)
        or site.get("status") != "ok"
        or type(site.get("oriented_start")) is not int
        or site["oriented_start"] != start
        or site.get("codon") != request.oriented_sequence[start : start + 3]
    ):
        raise FeatureError("prediction site is unsuccessful or does not match start")
    energies = site.get("energies")
    if not isinstance(energies, dict):
        raise FeatureError("prediction energy terms are missing")
    if energies.get("units") != "kcal/mol":
        raise FeatureError("prediction energy units must be kcal/mol")
    result = []
    for name in _ENERGY_NAMES:
        value = energies.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise FeatureError(f"prediction energy {name} must be a finite number")
        try:
            numeric = float(value)
        except OverflowError as exc:
            raise FeatureError(f"prediction energy {name} exceeds float range") from exc
        if not math.isfinite(numeric):
            raise FeatureError(f"prediction energy {name} must be finite")
        result.append(numeric)
    return tuple(result)


def extract_features(
    request: RbsRequest, *, kind: str, prediction: dict | None = None
) -> tuple[float, ...]:
    """Extract frozen sequence features and optionally validated energy terms.

    The request must already be validated by ``RbsRequest.from_dict``. Exactly
    one explicit supported start and at least one upstream base are required.
    Sequence-only extraction does not depend on a prediction, id or host label.
    """
    feature_names(kind)
    starts = request.start_positions
    if starts is None or len(starts) != 1:
        raise FeatureError("features require exactly one explicit start")
    start = starts[0]
    sequence = request.oriented_sequence
    codon = sequence[start : start + 3]
    if codon not in _START_CODONS:
        raise FeatureError(f"unsupported start codon: {codon!r}")
    if start == 0:
        raise FeatureError("leaderless initiation is unsupported")
    regions = (
        sequence[max(0, start - 35) : start],
        sequence[max(0, start - 100) : start],
        sequence[start : start + 13],
        sequence[start + 13 : start + 35],
    )
    features = (
        float(min(start, 100)),
        float(min(len(sequence) - start, 100)),
        *(
            region.count(base) / len(region) if region else 0.0
            for region in regions
            for base in "ACG"
        ),
        *(float(codon == alternative) for alternative in _START_CODONS[1:]),
        *_exact_sd_match(regions[0], reverse_complement(request.anti_sd)),
    )
    if kind == _ENERGY_KIND:
        return features + _energy_features(request, start, prediction)
    return features
