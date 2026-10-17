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
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, cast

from regsite import __version__
from regsite.backend import MAX_STRUCTURES, RnaStructure
from regsite.contracts import MAX_EXPLICIT_STARTS, RbsRequest
from regsite.profiles import Profile, get_profile
from regsite.sequence import InputError, input_interval
from regsite.standby import PARAMETERS as STANDBY_PARAMETERS
from regsite.standby import StandbyResult, StandbySearchLimit, optimize
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
    "suboptimal_reference": "lowest_interstrand_connected_complex",
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
MAX_JOINT_STATES = 4096
JOINT_PARAMETERS = {
    "objective": "minimum complete initiation energy over eligible returned candidates",
    "energy_summation": "math.fsum(complex, spacing, start, -unbound, standby)",
    "tie_rule": "complete energy, original backend enumeration index",
    "candidate_deduplication": "none; each returned traceback retains its index",
    "maximum_bound_state_attempts_per_site": MAX_JOINT_STATES,
    "incomplete_search": "no winner or site score after any candidate failure or limit",
}
BindingOption = tuple[float, int, int, float, list[tuple[int, int]]]


@dataclass(frozen=True)
class _BoundState:
    """One binding candidate's assembled complex and complete accessibility search."""

    first: int
    last: int
    before: Structure
    after: Structure
    suffix: Structure | None
    suffix_start: int
    standby: StandbyResult | None
    standby_signed: float


def _bound_state(
    window: str,
    leader: str,
    anti_sd: str,
    binding: list[tuple[int, int]],
    folding,
    profile: Profile,
    evaluate: Callable[[str, tuple[int, ...]], Structure],
) -> _BoundState:
    """Preserve the original assembly/arithmetic for both selection procedures."""
    first, last = min(i for i, _ in binding), max(i for i, _ in binding)
    prefix = folding.fold(window[:first])
    suffix_start = min(len(window), len(leader) + profile.footprint_nt)
    suffix = None if profile.historical else folding.fold(window[suffix_start:])
    joined = window + "III" + anti_sd
    before = evaluate(
        joined, _joined_pairs(window, anti_sd, prefix, binding, suffix, suffix_start)
    )
    standby = None
    if profile.standby:
        states = {prefix.pairs: before}

        def evaluate_opening(pairs):
            state_prefix = Structure(prefix.sequence, pairs, None)
            state = evaluate(
                joined,
                _joined_pairs(
                    window, anti_sd, state_prefix, binding, suffix, suffix_start
                ),
            )
            states[pairs] = state
            return state.energy

        standby = optimize(prefix, cast(float, before.energy), evaluate_opening)
        after = states[standby.selected.pairs]
        standby_signed = -standby.selected.total
    else:
        accessible_prefix = folding.fold(window[: max(0, first - 4)])
        after = evaluate(
            joined,
            _joined_pairs(
                window, anti_sd, accessible_prefix, binding, suffix, suffix_start
            ),
        )
        standby_signed = min(
            0.0, cast(float, before.energy) - cast(float, after.energy)
        )
    return _BoundState(
        first, last, before, after, suffix, suffix_start, standby, standby_signed
    )


def _empty_joint_search(returned: int) -> dict:
    """Initialize observable progress; unknown candidate lists remain null instead."""
    return {
        "returned": returned,
        "connected": 0,
        "eligible": 0,
        "evaluated": 0,
        "failed": 0,
        "not_evaluated": 0,
        "state_attempts": 0,
        "states_evaluated": 0,
        "complete": False,
        "selected_index": None,
        "selected_candidate_id": None,
        "greedy_index": None,
        "greedy_candidate_id": None,
        "greedy_total_energy": None,
        "candidates": [],
    }


def _joint_selection(
    viable: list[BindingOption],
    candidates: tuple[Structure, ...],
    window: str,
    leader: str,
    request: RbsRequest,
    codon: str,
    unbound: Structure,
    folding,
    profile: Profile,
    search: dict,
) -> tuple[BindingOption, _BoundState]:
    """Complete all eligible candidates or preserve progress and propagate failure."""
    search.update(eligible=len(viable), not_evaluated=len(viable))
    for preliminary, index, spacing, _penalty, _binding in viable:
        candidate = candidates[index]
        digest = hashlib.sha256(
            json.dumps(
                {"sequence": candidate.sequence, "pairs": candidate.pairs},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        search["candidates"].append(
            {
                "index": index,
                "candidate_id": f"cofold-{index}-{digest}",
                "preliminary_energy": preliminary,
                "aligned_spacing": spacing,
                "status": "not_evaluated",
                "reason": None,
                "total_energy": None,
                "standby_energy": None,
                "state_attempts": 0,
                "states_evaluated": 0,
                "negative_unfolding_seen": None,
            }
        )

    def evaluate(sequence: str, pairs: tuple[int, ...]) -> Structure:
        if search["state_attempts"] >= MAX_JOINT_STATES:
            raise StandbySearchLimit(
                f"joint standby search exceeds {MAX_JOINT_STATES} bound states"
            )
        search["state_attempts"] += 1
        state = folding.evaluate(sequence, pairs)
        if state.energy is None or not math.isfinite(state.energy):
            raise BackendError("nonfinite joint bound-state energy")
        search["states_evaluated"] += 1
        return state

    completed = []
    for option, row in zip(viable, search["candidates"], strict=True):
        preliminary, index, spacing, penalty, binding = option
        attempts, evaluated = search["state_attempts"], search["states_evaluated"]
        search["not_evaluated"] -= 1
        try:
            state = _bound_state(
                window, leader, request.anti_sd, binding, folding, profile, evaluate
            )
            total = _joint_total_energy(
                cast(float, state.before.energy),
                penalty,
                START_ENERGIES[codon],
                cast(float, unbound.energy),
                state.standby_signed,
            )
            row.update(
                status="ok",
                total_energy=total,
                standby_energy=-state.standby_signed,
                negative_unfolding_seen=cast(
                    StandbyResult, state.standby
                ).negative_unfolding_seen,
            )
            search["evaluated"] += 1
            completed.append((total, index, option, state, row))
        except (BackendError, OSError, UnicodeError) as exc:
            row.update(
                status="unsupported"
                if isinstance(exc, StandbySearchLimit)
                else "failed",
                reason=str(exc),
            )
            search["failed"] += 1
            raise
        finally:
            row["state_attempts"] = search["state_attempts"] - attempts
            row["states_evaluated"] = search["states_evaluated"] - evaluated
    selected = min(completed, key=lambda item: (item[0], item[1]))
    greedy = min(completed, key=lambda item: (item[2][0], item[1]))
    search.update(
        complete=True,
        selected_index=selected[1],
        selected_candidate_id=selected[4]["candidate_id"],
        greedy_index=greedy[1],
        greedy_candidate_id=greedy[4]["candidate_id"],
        greedy_total_energy=greedy[0],
    )
    return selected[2], selected[3]


def _joint_total_energy(
    complex_energy: float,
    spacing: float,
    start: float,
    unbound: float,
    standby_signed: float,
) -> float:
    """Sum the five signed terms without order-dependent intermediate rounding."""
    try:
        result = math.fsum((complex_energy, spacing, start, -unbound, -standby_signed))
    except (OverflowError, ValueError) as exc:
        raise BackendError("nonfinite joint candidate total energy") from exc
    if not math.isfinite(result):
        raise BackendError("nonfinite joint candidate total energy")
    return result


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
    window: str,
    anti_sd: str,
    prefix: Structure,
    binding: list[tuple[int, int]],
    suffix: Structure | None = None,
    suffix_start: int = 0,
) -> tuple[int, ...]:
    pairs = [-1] * (len(window) + 3 + len(anti_sd))
    pairs[: len(prefix.pairs)] = prefix.pairs
    if suffix is not None:
        for i, partner in enumerate(suffix.pairs):
            if partner >= 0:
                pairs[suffix_start + i] = suffix_start + partner
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


def _standby_result(result: StandbyResult, begin: int, request: RbsRequest) -> dict:
    """Project module intervals while retaining explicit window-relative pairs."""

    def interval(span):
        return (
            None
            if span is None
            else asdict(
                input_interval(
                    begin + span[0],
                    begin + span[1],
                    len(request.sequence),
                    request.strand,
                )
            )
        )

    chosen = result.selected
    return {
        "original_hairpin": interval(chosen.original_hairpin),
        "hairpin": interval(chosen.module.hairpin),
        "distal": interval(chosen.module.distal),
        "proximal": interval(chosen.module.proximal),
        "height_nt": chosen.module.height,
        "accessibility_height_nt": min(15, chosen.module.height),
        "distal_length_nt": chosen.module.distal[1] - chosen.module.distal[0],
        "proximal_length_nt": chosen.module.proximal[1] - chosen.module.proximal[0],
        "surface_area_nt": chosen.module.area,
        "downstream_height_nt": chosen.module.downstream_height,
        "downstream_hairpins": [
            {"interval": interval((start, end)), "height_nt": height}
            for start, end, height in chosen.module.downstream
        ],
        "opened_pairs": [list(pair) for pair in chosen.opened_pairs],
        "pair_coordinate_space": "zero-based window-relative transcript orientation",
        "evaluated_states": result.evaluated_states,
        "original_modules": result.original_modules,
        "exhaustive_within_declared_opening_states": True,
        "ablations_kcal_mol": result.ablations,
    }


def _score_site(request: RbsRequest, start: int, folding, profile: Profile) -> dict:
    sequence = request.oriented_sequence
    codon = sequence[start : start + 3]
    begin = max(0, start - profile.upstream_nt)
    end = min(len(sequence), start + profile.downstream_nt)
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
    if not profile.historical:
        site.update(coding_footprint=None, post_footprint=None)
    if profile.standby:
        site["standby"] = None
    if profile.joint:
        site["joint_search"] = None
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
        joint_search = None
        if profile.joint:
            joint_search = _empty_joint_search(len(candidates))
            site["joint_search"] = joint_search
        connected = []
        for index, candidate in enumerate(candidates):
            binding = interstrand_pairs(candidate, len(leader))
            if binding:
                connected.append((index, candidate, binding))
        if joint_search is not None:
            joint_search["connected"] = len(connected)
        if not connected:
            if joint_search is not None:
                joint_search["complete"] = True
            return dict(site, reason="no_interstrand_candidate_in_bounded_search")
        lowest = min(candidate.energy for _, candidate, _ in connected)
        viable = []
        for index, candidate, binding in connected:
            spacing = aligned_spacing(binding, len(leader))
            if spacing is not None and candidate.energy <= lowest + 3.0 + 1e-9:
                penalty = spacing_energy(spacing)
                viable.append(
                    (candidate.energy + penalty, index, spacing, penalty, binding)
                )
        if not viable:
            if joint_search is not None:
                joint_search["complete"] = True
            return dict(site, reason="no_interstrand_candidate_in_bounded_search")
        if joint_search is not None:
            option, bound = _joint_selection(
                viable,
                candidates,
                window,
                leader,
                request,
                codon,
                unbound,
                folding,
                profile,
                joint_search,
            )
        else:
            # Source tie policy: first minimum in backend enumeration order.
            option = min(viable, key=lambda x: (x[0], x[1]))
            bound = _bound_state(
                window,
                leader,
                request.anti_sd,
                option[4],
                folding,
                profile,
                folding.evaluate,
            )
        ranking_energy, index, spacing, penalty, binding = option
        first, last = bound.first, bound.last
        before, after = bound.before, bound.after
        suffix, suffix_start = bound.suffix, bound.suffix_start
        standby, standby_signed = bound.standby, bound.standby_signed
        standby_start = max(0, first - 4)
        total = (
            _joint_total_energy(
                cast(float, before.energy),
                penalty,
                START_ENERGIES[codon],
                unbound.energy,
                standby_signed,
            )
            if profile.joint
            else total_energy(
                cast(float, before.energy) + penalty,
                START_ENERGIES[codon],
                unbound.energy,
                standby_signed,
            )
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
        if first < 4 and not profile.standby:
            warnings.append("standby_region_truncated_at_window_boundary")
        if begin == 0 or end == len(sequence):
            warnings.append("folding_window_touches_supplied_sequence_boundary")
        if request.temperature_c != 37:
            warnings.append(
                "historical_scalar_parameters_not_recalibrated_for_temperature"
            )
        result = dict(
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
                "connected_returned": len(connected),
                "band_reference_kcal_mol": lowest,
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
        if standby is not None:
            chosen = standby.selected
            del result["energies"]["dG_standby_signed"]
            result["energies"].update(
                dG_standby=chosen.total,
                dG_distortion=chosen.distortion,
                dG_unfolding=chosen.unfolding,
                dG_unfolding_raw=chosen.unfolding_raw,
                dG_sliding=chosen.sliding,
            )
            result["standby_interval"] = None
            result["standby"] = _standby_result(standby, begin, request)
            if standby.negative_unfolding_seen or (
                joint_search is not None
                and any(
                    c["negative_unfolding_seen"] for c in joint_search["candidates"]
                )
            ):
                warnings.append("negative_fixed_state_unfolding_cost_clamped_to_zero")
            if first == 0:
                warnings.append("no_upstream_standby_context_available")
        if suffix is not None:
            result["energies"]["dG_post_footprint"] = suffix.energy
            result["coding_footprint"] = asdict(
                input_interval(
                    start, begin + suffix_start, len(sequence), request.strand
                )
            )
            result["post_footprint"] = _structure_result(suffix, len(suffix.sequence))
            result["post_footprint"]["coordinate_space"] = (
                "zero-based post-footprint sequence, beginning immediately after "
                "coding_footprint in transcript orientation"
            )
            if (
                suffix.prediction_energy is not None
                and abs(suffix.prediction_energy - cast(float, suffix.energy)) > 1e-9
            ):
                warnings.append("post_footprint_native_energy_differs_from_efn2")
            if end < start + profile.footprint_nt:
                warnings.append("coding_footprint_truncated_at_sequence_boundary")
        return result
    except StandbySearchLimit as exc:
        return dict(site, status="unsupported", reason=str(exc))
    except (BackendError, OSError, UnicodeError) as exc:
        return dict(site, status="failed", reason=str(exc))


def predict(
    value: object,
    backend: RnaStructure,
    *,
    seconds: float = 60,
    profile: str = "historical",
    execution_seconds: float | None = None,
) -> dict:
    """Score one request; validation/backend failures never become zero scores.

    An overall failed or unsupported status can retain successful sites. Inspect
    each site's status; ok means every selected start was successfully scored.
    execution_seconds may shorten an enclosing batch's remaining execution time;
    the declared seconds budget, not elapsed wall time, defines prediction identity.
    """
    specification = get_profile(profile)
    base: dict[str, Any] = {
        "schema_version": specification.schema_version,
        "id": None,
        "status": "invalid_input",
        "reason": None,
        "sites": [],
        "warnings": list(BASE_WARNINGS),
        "model": {
            "id": specification.model_id,
            "source_commit": SOURCE_COMMIT,
            "parameters": deepcopy(MODEL_PARAMETERS),
            "implementation_version": __version__,
        },
        "backend": deepcopy(backend.identity),
        "input": None,
        "prediction_id": None,
    }
    if backend.identity.get("variant"):
        base["warnings"].append("patched_traceback_changes_candidate_search_results")
    if not specification.historical:
        parameters = base["model"]["parameters"]
        del parameters["historical_footprint_nt"]
        parameters.update(
            upstream_nt=specification.upstream_nt,
            downstream_nt=specification.downstream_nt,
            coding_footprint_nt=specification.footprint_nt,
            footprint_coordinate="[start, start+13), first coding nucleotide is start",
            footprint_source="https://doi.org/10.1093/nar/gkx061; Methods equation 3",
            context_source=(
                "published 2014/2017 context-inspired bounded reconstruction; "
                "not a recovered production parameter set"
            ),
            standby_model="historical four-base opening; later geometry unimplemented",
        )
        if specification.standby:
            del parameters["standby_nt"]
            parameters["standby_model"] = deepcopy(STANDBY_PARAMETERS)
            base["warnings"].extend(
                [
                    "standby_geometry_continuation_and_branch_opening_are_reconstructions",
                    "drafting_stacking_and_nonequilibrium_mechanisms_not_implemented",
                ]
            )
            if specification.joint:
                parameters["standby_model"]["binding_candidate_rule"] = (
                    "minimum complete initiation energy across "
                    "eligible returned candidates"
                )
                parameters["joint_search"] = deepcopy(JOINT_PARAMETERS)
                base["warnings"].append(
                    "joint_selection_is_exhaustive_only_within_declared_candidate_states"
                )
            else:
                base["warnings"].insert(
                    -1, "binding_candidate_selected_before_standby_optimization"
                )
        else:
            base["warnings"].append(
                "later_standby_geometry_sliding_drafting_stacking_not_implemented"
            )
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
        "budget_seconds": float(seconds),
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
        if execution_seconds is not None and (
            type(execution_seconds) not in (int, float)
            or not 0 < execution_seconds <= seconds
        ):
            raise BackendError("invalid enclosing execution budget")
        folding = backend.session(
            request.temperature_c,
            seconds if execution_seconds is None else execution_seconds,
        )
    except (BackendError, OSError, UnicodeError) as exc:
        return dict(base, status="failed", reason=str(exc))
    sites = [_score_site(request, start, folding, specification) for start in starts]
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
