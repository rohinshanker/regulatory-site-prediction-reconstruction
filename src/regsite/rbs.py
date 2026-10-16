"""Salis v1 equations with an explicitly different RNAstructure backend.

Adapted equation/structural procedure: RBS_Calculator.py, commit
8a9c1de1bdd847bb90d2ab6ceaa3c20feceda307.
Copyright 2008–2009 University of California Regents. All rights reserved.
GPL-3.0-or-later; distributed without warranty. See LICENSE and NOTICE.
The adapter and result contracts are original implementations.
"""

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from regsite import __version__
from regsite.backend import MAX_STRUCTURES, RnaStructure
from regsite.contracts import MAX_EXPLICIT_STARTS, SCHEMA_VERSION, RbsRequest
from regsite.sequence import InputError, input_interval
from regsite.structures import BackendError, Structure

MODEL_ID = "salis-v1-rnastructure-6.6-reconstruction-1"
SOURCE_COMMIT = "8a9c1de1bdd847bb90d2ab6ceaa3c20feceda307"
START_ENERGIES = {"AUG": -1.194, "GUG": -0.0748, "UUG": -0.0435, "CUG": -0.03406}
SCAN_CODONS = frozenset(("AUG", "GUG", "UUG"))
MODEL_PARAMETERS = {
    "upstream_nt": 35,
    "downstream_nt": 35,
    "standby_nt": 4,
    "historical_footprint_nt": 1000,
    "suboptimal_filter_kcal_mol": 3.0,
    "energy_comparison_tolerance_kcal_mol": 1e-9,
    "optimal_aligned_spacing": 5,
    "spacing_push": [12.2, 2.5, 2.0, 3.0],
    "spacing_pull": [0.048, 0.24, 0.0],
    "rate_scale": 2500.0,
    "effective_RT": 2.222,
    "start_energies_kcal_mol": START_ENERGIES,
}
BASE_WARNINGS = [
    "reconstruction_not_historical_or_hosted_equivalence",
    "RNAstructure_parameters_and_dangles_differ_from_NUPACK_rna1999",
    "bounded_bifold_tracebacks_not_exhaustive_suboptimal_enumeration",
    "relative_initiation_score_not_absolute_rate_or_probability",
    "host_configuration_is_not_host_calibration",
]


def spacing_energy(aligned_spacing: int) -> float:
    """Salis v1 push/pull spacing penalty, kcal/mol (not the iDOG table)."""
    distance = aligned_spacing - 5
    if distance < 0:
        return 12.2 / (1 + math.exp(2.5 * (distance + 2))) ** 3
    return 0.048 * distance * distance + 0.24 * distance


def initiation_rate(total_energy: float) -> float:
    """Historical relative scale; numerical overflow/underflow is a failure."""
    if not math.isfinite(total_energy):
        raise BackendError("nonfinite total initiation energy")
    try:
        rate = 2500.0 * math.exp(-total_energy / 2.222)
    except OverflowError as exc:
        raise BackendError("initiation score exceeds floating-point range") from exc
    if not math.isfinite(rate) or rate == 0:
        raise BackendError("initiation score exceeds floating-point range")
    return rate


def total_energy(
    complex_with_spacing: float, start: float, unbound: float, standby_signed: float
) -> float:
    """Executable v1 algebra: no separately subtracted rRNA energy."""
    return complex_with_spacing + start - unbound - standby_signed


def interstrand_pairs(
    structure: Structure, leader_length: int
) -> list[tuple[int, int]]:
    """Return zero-based (mRNA, aSD) pairs, omitting the three CT linker bases."""
    offset = leader_length + 3
    return [
        (i, partner - offset)
        for i, partner in enumerate(structure.pairs[:leader_length])
        if partner >= offset
    ]


def aligned_spacing(pairs: list[tuple[int, int]], start: int) -> int | None:
    """Use the most 3′ paired aSD base and historical strict upstream boundary."""
    if not pairs:
        return None
    mrna, rrna = max(pairs, key=lambda pair: pair[1])
    if mrna + 1 >= start:
        return None
    return start - mrna - (rrna + 1)


def _joined_pairs(
    window: str, anti_sd: str, prefix: Structure, binding: list[tuple[int, int]]
) -> tuple[int, ...]:
    pairs = [-1] * (len(window) + 3 + len(anti_sd))
    pairs[: len(prefix.pairs)] = prefix.pairs
    for mrna, rrna in binding:
        target = len(window) + 3 + rrna
        pairs[mrna] = target
        pairs[target] = mrna
    return tuple(pairs)


def _structure_result(structure: Structure, mrna_length: int) -> dict:
    """Separate biological strands rather than exposing artificial CT positions."""
    has_asd = len(structure.sequence) != mrna_length
    offset = mrna_length + 3
    return {
        "mrna_dot_bracket": structure.dot_bracket()[:mrna_length],
        "anti_sd_dot_bracket": structure.dot_bracket()[offset:] if has_asd else None,
        "mrna_intramolecular_pairs": [
            [i, j]
            for i, j in enumerate(structure.pairs[:mrna_length])
            if i < j < mrna_length
        ],
        "mrna_anti_sd_pairs": [
            list(pair) for pair in interstrand_pairs(structure, mrna_length)
        ]
        if has_asd
        else [],
        "coordinate_space": (
            "zero-based window-relative mRNA and 5-prime-to-3-prime anti_sd"
        ),
        "energy_kcal_mol": structure.energy,
        "prediction_energy_kcal_mol": structure.prediction_energy,
    }


def _score_site(request: RbsRequest, start: int, folding) -> dict:
    sequence = request.oriented_sequence
    codon = sequence[start : start + 3]
    begin, end = max(0, start - 35), min(len(sequence), start + 35)
    site: dict[str, Any] = {
        "status": "no_candidate",
        "reason": None,
        "codon": codon,
        "start_codon": asdict(
            input_interval(start, start + 3, len(sequence), request.strand)
        ),
        "oriented_start": start,
        "window": {
            "oriented_start": begin,
            "oriented_end": end,
            "input_interval": asdict(
                input_interval(begin, end, len(sequence), request.strand)
            ),
        },
        "energies": None,
        "tir": None,
        "log_tir": None,
        "aligned_spacing": None,
        "candidate_search": None,
        "structures": None,
        "binding_interval": None,
        "standby_interval": None,
        "warnings": [],
    }
    if codon not in START_ENERGIES:
        return dict(site, status="unsupported", reason="unsupported_start_codon")
    if start == 0:
        return dict(
            site, status="unsupported", reason="leaderless_initiation_not_modeled"
        )
    window, leader = sequence[begin:end], sequence[begin:start]
    try:
        unbound = folding.fold(window)
        candidates = folding.cofold(leader, request.anti_sd)
        lowest = min(candidate.energy for candidate in candidates)
        viable = []
        for index, candidate in enumerate(candidates):
            binding = interstrand_pairs(candidate, len(leader))
            spacing = aligned_spacing(binding, len(leader))
            if spacing is not None and candidate.energy <= lowest + 3.0 + 1e-9:
                penalty = spacing_energy(spacing)
                viable.append(
                    (candidate.energy + penalty, index, spacing, penalty, binding)
                )
        if not viable:
            return dict(site, reason="no_interstrand_candidate_in_bounded_search")
        # Source tie policy: first minimum in backend enumeration order.
        ranking_energy, index, spacing, penalty, binding = min(
            viable, key=lambda x: (x[0], x[1])
        )
        first, last = min(i for i, _ in binding), max(i for i, _ in binding)
        prefix = folding.fold(window[:first])
        joined = window + "III" + request.anti_sd
        before = folding.evaluate(
            joined, _joined_pairs(window, request.anti_sd, prefix, binding)
        )
        standby_start = max(0, first - 4)
        accessible_prefix = folding.fold(window[:standby_start])
        after = folding.evaluate(
            joined, _joined_pairs(window, request.anti_sd, accessible_prefix, binding)
        )
        standby_signed = min(0.0, before.energy - after.energy)
        total = total_energy(
            before.energy + penalty,
            START_ENERGIES[codon],
            unbound.energy,
            standby_signed,
        )
        rate = initiation_rate(total)
        warnings = []
        if any(
            s.prediction_energy is not None
            and abs(s.prediction_energy - s.energy) > 1e-9
            for s in (unbound, *candidates)
        ):
            warnings.append("native_prediction_energy_differs_from_efn2_evaluation")
        if penalty > 3:
            warnings.append("spacing_penalty_exceeds_suboptimal_energy_band")
        if len(candidates) == MAX_STRUCTURES:
            warnings.append("bifold_traceback_count_reached_limit")
        if first < 4:
            warnings.append("standby_region_truncated_at_window_boundary")
        if begin == 0 or end == len(sequence):
            warnings.append("folding_window_touches_supplied_sequence_boundary")
        if request.temperature_c != 37:
            warnings.append(
                "historical_scalar_parameters_not_recalibrated_for_temperature"
            )
        return dict(
            site,
            status="ok",
            reason=None,
            tir=rate,
            log_tir=math.log(2500) - total / 2.222,
            energies={
                "dG_mRNA": unbound.energy,
                "dG_mRNA_native_prediction": unbound.prediction_energy,
                "dG_cofold_native_prediction": candidates[index].prediction_energy,
                "dG_cofold_search": candidates[index].energy,
                "dG_search_with_spacing": ranking_energy,
                "dG_complex": before.energy,
                "dG_spacing": penalty,
                "dG_start": START_ENERGIES[codon],
                "dG_standby_signed": standby_signed,
                "dG_accessible_complex": after.energy,
                "dG_total": total,
                "units": "kcal/mol",
            },
            aligned_spacing=spacing,
            candidate_search={
                "returned": len(candidates),
                "viable_in_band": len(viable),
                "selected_index": index,
                "exhaustive": False,
            },
            structures={
                "unbound": _structure_result(unbound, len(window)),
                "bound_before_standby": _structure_result(before, len(window)),
                "bound_after_standby": _structure_result(after, len(window)),
            },
            binding_interval=asdict(
                input_interval(
                    begin + first, begin + last + 1, len(sequence), request.strand
                )
            ),
            standby_interval=asdict(
                input_interval(
                    begin + standby_start, begin + first, len(sequence), request.strand
                )
            ),
            warnings=warnings,
        )
    except (BackendError, OSError, UnicodeError) as exc:
        return dict(site, status="failed", reason=str(exc))


def predict(value: object, backend: RnaStructure, *, seconds: float = 60) -> dict:
    """Score one request; validation/backend failures never become zero scores.

    An overall failed or unsupported status can retain successful sites. Inspect
    each site's status; ok means every selected start was successfully scored.
    """
    base = {
        "schema_version": SCHEMA_VERSION,
        "id": None,
        "status": "invalid_input",
        "reason": None,
        "sites": [],
        "warnings": list(BASE_WARNINGS),
        "model": {
            "id": MODEL_ID,
            "source_commit": SOURCE_COMMIT,
            "parameters": deepcopy(MODEL_PARAMETERS),
            "implementation_version": __version__,
        },
        "backend": deepcopy(backend.identity),
        "input": None,
        "prediction_id": None,
    }
    try:
        request = RbsRequest.from_dict(value)
    except InputError as exc:
        return dict(base, reason=str(exc))
    starts = request.start_positions
    if starts is None:
        starts = tuple(
            i
            for i in range(len(request.sequence) - 2)
            if request.oriented_sequence[i : i + 3] in SCAN_CODONS
        )
    provenance = asdict(request)
    stable = {
        "input": provenance,
        "model": base["model"],
        "backend": deepcopy(backend.identity),
        "budget_seconds": seconds,
    }
    identifier = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    base.update(id=request.id, input=provenance, prediction_id=identifier)
    if len(starts) > MAX_EXPLICIT_STARTS:
        return dict(
            base, status="unsupported", reason="scanned_start_count_exceeds_1000"
        )
    try:
        folding = backend.session(request.temperature_c, seconds)
    except (BackendError, OSError, UnicodeError) as exc:
        return dict(base, status="failed", reason=str(exc))
    sites = [_score_site(request, start, folding) for start in starts]
    statuses = {site["status"] for site in sites}
    # Failures take precedence; successful predictions remain individually visible.
    status = next(
        (s for s in ("failed", "unsupported", "no_candidate") if s in statuses), "ok"
    )
    if not sites:
        status = "no_candidate"
    return dict(
        base,
        status=status,
        sites=sites,
        reason="no_selected_start_codons" if not sites else None,
    )
