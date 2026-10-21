"""Kernel parity of the reconstructed Promoter core against an original-source pilot.

The reference is the schema-1 native localization report written by the pinned
historical source runner. Each native and shuffled 128-nt window is rescored at
all 41 candidate starts with the existing regsite.promoter core and the explicit
E. coli MG1655 calibration. The check reports arithmetic agreement only: not
biological accuracy, hosted-tool equivalence or runtime-release admission. It
imports no source code, runs no subprocess, uses no network and reads no genome.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import statistics
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from regsite import promoter as core
from regsite import promoter_io

SCHEMA = "regsite-promoter-pilot-parity-1"
CLAIM = (
    "Kernel arithmetic parity of the reconstructed core with the original-source "
    "report only; not biological accuracy, hosted equivalence or runtime-release "
    "admission. Source-original and reconstructed model identities stay distinct."
)
MAX_INPUT_BYTES = 128 * 1024 * 1024
REL_TOL = 1e-12
ABS_TOL = 1e-12
TIE_ABS_TOL = 1e-12
UPSTREAM = 87
DOWNSTREAM = 40
LENGTH = UPSTREAM + 1 + DOWNSTREAM
RADIUS = 20
OFFSETS = tuple(range(-RADIUS, RADIUS + 1))
LAYOUTS = 30
LOCAL_NT = 5
FULL_MAX_SITES = 2475
# Outcome-free full-pilot population: the original pre-scoring input-only cohort,
# independently recomputed by selection alone (no model import or scoring).
FULL_COHORT = {
    "input_anchors": 2475,
    "selected": 1597,
    "excluded": {
        "identical_or_reverse_complement_window": 1,
        "overlapping_window": 264,
        "same_locus": 613,
    },
    "strands": {"+": 823, "-": 774},
    "replicons": {"NZ_CP006471.1": 1580, "NZ_CP006472.1": 17},
    "ordered_selected_ids_sha256": (
        "da8dab4627396d7ffe75aa120a438a01925fb9447438f785cbf210015ebb1923"
    ),
}

# Frozen source protocol, consumer commit f80836248243983beefbfe3f85c83914e5f9d01b.
PRODUCER_SHA256 = "7d3440ad5239f216ec072dbaac49b430bbaa17d7b28674e18effadcc131f4766"
SCOPE = "Exploratory native-UTEX localization pilot; no regulatory site admission"
REPLICON_LENGTHS = {
    "NZ_CP006471.1": 2_690_418,
    "NZ_CP006472.1": 46_366,
    "NZ_CP006473.1": 7_842,
}
SOURCE_INPUTS = {
    "fasta_sha256": "22a2b07881c1099c32454778de0e90b1c40f74f44c0f59e000507106c0deb567",
    "tss_sha256": "d06524cf492aa8f009bf004c596a5d305ac54acbe7537ec98bbc7992ce164bff",
    "upstream_commit": core.SOURCE_COMMIT,
    "prepared_files_sha256": {
        "Promoter_Calculator_v1_0.py": (
            "142823781d1ef70eaf3a1fe6be9e4e005c73edf78b9f8bef9a3e12b86d9849ff"
        ),
        "util.py": "f80c4bec9b0922e9ed92645bc68343f811ac713e6107343463a1747c16345b74",
        "free_energy_coeffs.npy": core.COEFFICIENT_ARRAY_SHA256,
        "model_intercept.npy": core.INTERCEPT_ARRAY_SHA256,
        "LICENSE": "45d25f34fe826d27d344175bd622cbf3d35cbf53bd993d1350d44ee706571ffd",
        "README.md": "a5f3269206f5425e2c21ca58d9cb638fe87a4cbb1dbdff537a676747dc4b26d2",
    },
}
FIXED_PARAMETERS = {
    "locus_basis": "Tan Table S1 source locus tags; no current-CDS join",
    "upstream_nt": UPSTREAM,
    "downstream_nt": DOWNSTREAM,
    "candidate_offset_range_inclusive": [-RADIUS, RADIUS],
    "coordinate_basis": "1-based circular native positions in transcription order",
    "layouts_per_candidate": LAYOUTS,
    "energy_tie_absolute_tolerance": TIE_ABS_TOL,
    "optimum": "minimum dG_total (maximum E. coli model Tx_rate)",
    "control": "One mononucleotide shuffle per oriented window",
}
CONTROL_KIND = "mononucleotide shuffle; no native coordinates"
EXCLUSIONS = frozenset(
    {
        "same_locus",
        "overlapping_window",
        "identical_or_reverse_complement_window",
        "sample_limit",
    }
)
TOP_KEYS = frozenset(
    {
        "schema_version",
        "scope",
        "model_host",
        "limitations",
        "inputs",
        "runtime",
        "parameters",
        "cohort",
        "summary",
        "results",
    }
)
RUNTIME_KEYS = frozenset(
    {"python", "producer_sha256", "numpy", "sklearn", "scipy", "Bio"}
)
LOCALIZATION_KEYS = (
    "best_offsets_nt",
    "anchor_energy_rank_best",
    "anchor_energy_rank_worst",
    "best_distance_min_nt",
    "best_distance_max_nt",
)
ARM_KEYS = frozenset({"score_curve", *LOCALIZATION_KEYS})
CONTROL_KEYS = ARM_KEYS | {"sequence", "sequence_sha256", "kind", "identical_to_native"}
CASE_KEYS = frozenset(
    {
        "id",
        "replicon",
        "strand",
        "position",
        "locus",
        "sequence",
        "native_positions",
        "sequence_sha256",
        "native",
        "best_native_tss_positions",
        "control",
    }
)
ARM_SUMMARY_KEYS = frozenset(
    {
        "any_best_within_5nt",
        "all_best_within_5nt",
        "median_anchor_rank_best",
        "median_anchor_rank_worst",
    }
)
ARMS = ("native", "control")
FIELDS = ("dG_total", "ecoli_model_Tx_rate")
CATEGORIES = (
    "calculation_failure",
    "numeric_mismatch",
    "source_summary_mismatch",
    "reconstructed_summary_mismatch",
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_COMPLEMENT = str.maketrans("ACGT", "TGCA")
Scorer = Callable[..., core.SiteResult]


class IntegrityError(ValueError):
    """Reference bytes or content cannot be trusted as the frozen source report."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _same(left: object, right: object) -> bool:
    """Exact JSON value equality; distinguishes int, float and bool."""
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _require(condition: bool, code: str, path: str) -> None:
    if not condition:
        raise IntegrityError(code, path)


def _object(value: object, keys: frozenset[str], path: str) -> dict:
    _require(isinstance(value, dict) and set(value) == keys, "object_keys", path)
    assert isinstance(value, dict)
    return value


def _integer(value: object, path: str, low: int, high: int | None = None) -> int:
    _require(
        type(value) is int and low <= value and (high is None or value <= high),
        "invalid_integer",
        path,
    )
    assert isinstance(value, int)
    return value


def _text(value: object, path: str) -> str:
    _require(isinstance(value, str) and bool(value), "invalid_text", path)
    assert isinstance(value, str)
    return value


def _number(value: object, path: str) -> float:
    """Accept an int or float within the finite float range (no huge ints)."""
    _require(type(value) in (int, float), "invalid_number", path)
    assert isinstance(value, (int, float))
    limit = sys.float_info.max
    _require(-limit <= value <= limit, "invalid_number", path)
    return value


def _dna(value: object, path: str) -> str:
    _require(
        isinstance(value, str) and len(value) == LENGTH and not value.strip("ACGT"),
        "invalid_sequence",
        path,
    )
    assert isinstance(value, str)
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_key", key)
        result[key] = value
    return result


def _finite_float(token: str) -> float:
    value = float(token)
    _require(math.isfinite(value), "nonfinite_number", token)
    return value


def _reject_constant(token: str) -> None:
    raise IntegrityError("nonfinite_number", token)


def parse_reference(raw: bytes) -> object:
    """Decode strict UTF-8 JSON without duplicate keys or nonfinite numbers."""
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_float=_finite_float,
            parse_constant=_reject_constant,
        )
    except IntegrityError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise IntegrityError("invalid_json", type(exc).__name__) from exc


def native_positions(replicon: str, strand: str, position: int) -> list[int]:
    """Return 1-based circular positions of an oriented window, upstream first."""
    size = REPLICON_LENGTHS[replicon]
    step = 1 if strand == "+" else -1
    return [
        (position - 1 + step * offset) % size + 1
        for offset in range(-UPSTREAM, DOWNSTREAM + 1)
    ]


def _validate_arm(value: object, keys: frozenset[str], path: str) -> dict:
    """Check one arm's shape and exact ordered offset roster."""
    arm = _object(value, keys, path)
    curve = arm["score_curve"]
    _require(isinstance(curve, list), "invalid_curve", f"{path}.score_curve")
    rows = [
        _object(row, frozenset({"offset_nt", *FIELDS}), f"{path}.score_curve[{i}]")
        for i, row in enumerate(curve)
    ]
    _require(
        _same([row["offset_nt"] for row in rows], list(OFFSETS)),
        "curve_offsets",
        f"{path}.score_curve",
    )
    for row in rows:
        where = f"{path}.score_curve[{row['offset_nt']}]"
        _number(row["dG_total"], f"{where}.dG_total")
        rate = _number(row["ecoli_model_Tx_rate"], f"{where}.ecoli_model_Tx_rate")
        _require(rate > 0, "invalid_rate", where)
    best = arm["best_offsets_nt"]
    _require(isinstance(best, list) and bool(best), "invalid_best", path)
    for i, offset in enumerate(best):
        _integer(offset, f"{path}.best_offsets_nt[{i}]", -RADIUS, RADIUS)
    for key in LOCALIZATION_KEYS[1:]:
        _integer(arm[key], f"{path}.{key}", 0)
    return arm


def _validate_control(value: object, native: str, path: str) -> str:
    """Check a synthetic control: same composition, own hash, no coordinates."""
    control = _validate_arm(value, CONTROL_KEYS, path)
    sequence = _dna(control["sequence"], f"{path}.sequence")
    _require(Counter(sequence) == Counter(native), "control_composition", path)
    _require(
        control["sequence_sha256"] == _sha256(sequence.encode()),
        "sequence_hash_mismatch",
        path,
    )
    _require(control["kind"] == CONTROL_KIND, "control_kind", path)
    _require(
        control["identical_to_native"] is (sequence == native),
        "control_identity_flag",
        path,
    )
    return sequence


def _validate_case(value: object, path: str) -> dict:
    """Check one case's identity, sequence, coordinates and both arms."""
    case = _object(value, CASE_KEYS, path)
    _text(case["id"], f"{path}.id")
    _text(case["locus"], f"{path}.locus")
    replicon = case["replicon"]
    _require(
        isinstance(replicon, str) and replicon in REPLICON_LENGTHS,
        "unknown_replicon",
        path,
    )
    _require(case["strand"] in ("+", "-"), "invalid_strand", path)
    size = REPLICON_LENGTHS[case["replicon"]]
    _integer(case["position"], f"{path}.position", 1, size)
    sequence = _dna(case["sequence"], f"{path}.sequence")
    _require(
        case["sequence_sha256"] == _sha256(sequence.encode()),
        "sequence_hash_mismatch",
        path,
    )
    expected = native_positions(case["replicon"], case["strand"], case["position"])
    _require(
        _same(case["native_positions"], expected), "native_positions_mismatch", path
    )
    best_native = case["best_native_tss_positions"]
    _require(isinstance(best_native, list), "invalid_best_native", path)
    for i, coordinate in enumerate(best_native):
        _integer(coordinate, f"{path}.best_native_tss_positions[{i}]", 1, size)
    _validate_arm(case["native"], ARM_KEYS, f"{path}.native")
    _validate_control(case["control"], sequence, f"{path}.control")
    return case


def _validate_cohort(cases: list[dict]) -> None:
    """Enforce the source selection invariants across all selected cases."""
    ids, sites, loci, windows = set(), set(), set(), set()
    occupied: dict[str, set[int]] = {name: set() for name in REPLICON_LENGTHS}
    for i, case in enumerate(cases):
        path = f"results[{i}]"
        site = (case["replicon"], case["strand"], case["position"])
        window = min(case["sequence"], case["sequence"].translate(_COMPLEMENT)[::-1])
        _require(case["id"] not in ids, "duplicate_id", path)
        _require(site not in sites, "duplicate_site", path)
        _require(case["locus"] not in loci, "duplicate_locus", path)
        _require(window not in windows, "duplicate_window_sequence", path)
        positions = set(case["native_positions"])
        _require(
            occupied[case["replicon"]].isdisjoint(positions), "overlapping_window", path
        )
        ids.add(case["id"])
        sites.add(site)
        loci.add(case["locus"])
        windows.add(window)
        occupied[case["replicon"]].update(positions)


def ordered_ids_sha256(ids: list[str]) -> str:
    """Hash UTF-8 json.dumps(ids, ensure_ascii, ", "/": " separators), no newline."""
    text = json.dumps(ids, ensure_ascii=True, separators=(", ", ": "), allow_nan=False)
    return _sha256(text.encode("utf-8"))


def cohort_identity(cases: list[dict], input_anchors: int, excluded: dict) -> dict:
    """Return the outcome-free population identity of a validated report."""
    return {
        "input_anchors": input_anchors,
        "selected": len(cases),
        "excluded": dict(excluded),
        "strands": dict(Counter(case["strand"] for case in cases)),
        "replicons": dict(Counter(case["replicon"] for case in cases)),
        "ordered_selected_ids_sha256": ordered_ids_sha256(
            [case["id"] for case in cases]
        ),
    }


def classify_cohort(max_sites: int, identity: dict, expected: dict) -> str:
    """Classify a population; a complete claim must equal the frozen identity.

    A report claims the full pilot when it uses the 2475-site ceiling and the
    expected input total. Such a claim with any other selected roster, order,
    exclusion or tally is refused; every other population is "bounded_sample".
    """
    claims_full = (
        max_sites == FULL_MAX_SITES
        and identity["input_anchors"] == expected["input_anchors"]
    )
    if not claims_full:
        return "bounded_sample"
    _require(_same(identity, expected), "full_cohort_identity", "cohort")
    return "full_eligible"


def validate_reference(document: object) -> tuple[dict, str, dict]:
    """Validate the complete frozen-protocol report.

    Returns the report, its completeness class and its population identity.
    """
    report = _object(document, TOP_KEYS, "$")
    _require(_same(report["schema_version"], 1), "schema_version", "schema_version")
    _require(report["scope"] == SCOPE, "scope", "scope")
    _require(report["model_host"] == core.NATIVE_HOST, "model_host", "model_host")
    limitations = report["limitations"]
    _require(
        isinstance(limitations, list) and bool(limitations),
        "limitations",
        "limitations",
    )
    for i, item in enumerate(limitations):
        _text(item, f"limitations[{i}]")
    _require(_same(report["inputs"], SOURCE_INPUTS), "source_pins", "inputs")
    runtime = _object(report["runtime"], RUNTIME_KEYS, "runtime")
    for key in sorted(RUNTIME_KEYS):
        _text(runtime[key], f"runtime.{key}")
    _require(
        runtime["producer_sha256"] == PRODUCER_SHA256,
        "producer_sha256",
        "runtime.producer_sha256",
    )
    parameters = _object(
        report["parameters"],
        frozenset({*FIXED_PARAMETERS, "max_sites", "seed"}),
        "parameters",
    )
    for key, value in FIXED_PARAMETERS.items():
        _require(_same(parameters[key], value), "protocol_parameter", key)
    max_sites = _integer(
        parameters["max_sites"], "parameters.max_sites", 1, FULL_MAX_SITES
    )
    _integer(parameters["seed"], "parameters.seed", 0)
    cohort = _object(
        report["cohort"], frozenset({"input_anchors", "excluded"}), "cohort"
    )
    _integer(cohort["input_anchors"], "cohort.input_anchors", 1)
    excluded = cohort["excluded"]
    _require(
        isinstance(excluded, dict) and set(excluded) <= EXCLUSIONS,
        "exclusion_reasons",
        "cohort.excluded",
    )
    for key, count in excluded.items():
        _integer(count, f"cohort.excluded.{key}", 1)
    results = report["results"]
    _require(isinstance(results, list) and bool(results), "empty_results", "results")
    cases = [_validate_case(case, f"results[{i}]") for i, case in enumerate(results)]
    _validate_cohort(cases)
    _require(
        len(cases) + sum(excluded.values()) == cohort["input_anchors"],
        "cohort_total",
        "cohort",
    )
    _require(
        len(cases) == max_sites
        if "sample_limit" in excluded
        else len(cases) <= max_sites,
        "sample_limit",
        "cohort",
    )
    summary = _object(
        report["summary"],
        frozenset({"anchors", "strands", "replicons", *ARMS}),
        "summary",
    )
    for arm in ARMS:
        _object(summary[arm], ARM_SUMMARY_KEYS, f"summary.{arm}")
    identity = cohort_identity(cases, cohort["input_anchors"], excluded)
    return report, classify_cohort(max_sites, identity, FULL_COHORT), identity


def localization(energies: list[float]) -> dict:
    """Recompute tied optima and anchor ranks at abs 1e-12, rel 0 tolerance.

    Ties are never broken toward the anchor; ranks span the whole tie class.
    """

    def tied(left: float, right: float) -> bool:
        return math.isclose(left, right, rel_tol=0.0, abs_tol=TIE_ABS_TOL)

    best = min(energies)
    offsets = [o for o, e in zip(OFFSETS, energies, strict=True) if tied(e, best)]
    anchor = energies[RADIUS]
    distances = [abs(offset) for offset in offsets]
    return {
        "best_offsets_nt": offsets,
        "anchor_energy_rank_best": 1
        + sum(e < anchor and not tied(e, anchor) for e in energies),
        "anchor_energy_rank_worst": sum(
            e < anchor or tied(e, anchor) for e in energies
        ),
        "best_distance_min_nt": min(distances),
        "best_distance_max_nt": max(distances),
    }


def aggregate(cases: list[dict], localizations: list[dict]) -> dict:
    """Recompute cohort counts, strand/replicon tallies and per-arm summaries."""
    summary: dict[str, Any] = {
        "anchors": len(cases),
        "strands": dict(Counter(case["strand"] for case in cases)),
        "replicons": dict(Counter(case["replicon"] for case in cases)),
    }
    for arm in ARMS:
        rows = [item[arm] for item in localizations]
        summary[arm] = {
            "any_best_within_5nt": sum(
                r["best_distance_min_nt"] <= LOCAL_NT for r in rows
            ),
            "all_best_within_5nt": sum(
                r["best_distance_max_nt"] <= LOCAL_NT for r in rows
            ),
            "median_anchor_rank_best": statistics.median(
                r["anchor_energy_rank_best"] for r in rows
            ),
            "median_anchor_rank_worst": statistics.median(
                r["anchor_energy_rank_worst"] for r in rows
            ),
        }
    return summary


def _equal(reported: object, recomputed: object) -> bool:
    """Numbers compare by value (median 2 == 2.0); everything else exactly."""
    numbers = (int, float)
    if type(reported) in numbers and type(recomputed) in numbers:
        return reported == recomputed
    return _same(reported, recomputed)


def _failure(
    category: str,
    field: str,
    reference: object,
    observed: object,
    *,
    source_id: str | None = None,
    arm: str | None = None,
    offset: int | None = None,
    detail: str | None = None,
) -> dict:
    return {
        "category": category,
        "source_id": source_id,
        "arm": arm,
        "offset_nt": offset,
        "field": field,
        "reference": reference,
        "observed": observed,
        "detail": detail,
    }


def differences(
    observed: float, expected: float
) -> tuple[float | None, float | None, str | None]:
    """Return finite absolute/relative differences, or null plus the reason.

    Diagnostics only: the tolerance decision never uses these values.
    """
    absolute = abs(observed - expected)
    if not math.isfinite(absolute):
        return None, None, "abs_diff_overflow"
    if not expected:
        return absolute, None, "rel_diff_zero_reference"
    relative = absolute / abs(expected)
    if not math.isfinite(relative):
        return absolute, None, "rel_diff_overflow"
    return absolute, relative, None


DIFFERENCE_FLAGS = ("abs_diff_overflow", "rel_diff_overflow", "rel_diff_zero_reference")


def _score(
    scorer: Scorer,
    sequence: str,
    offset: int,
    params: core.PromoterParameters,
    calibration: core.Calibration,
) -> tuple[tuple[float, float] | None, str | None]:
    """Score one start; return (dG_total, rate) or a retained failure detail."""
    try:
        site = scorer(
            sequence, "+", UPSTREAM + offset, params, calibration, keep_states=False
        )
        if site.state_count != LAYOUTS:
            return None, f"state_coverage:{site.state_count}"
        if site.status != "ok" or site.selected is None:
            return None, f"kernel_status:{site.status}:{site.reason}"
        scored = site.selected.to_dict(LENGTH, "+", calibration, elements=False)
    except Exception as exc:  # Every kernel error stays a counted failure.
        return None, f"kernel_exception:{type(exc).__name__}"
    if scored["score_status"] != "ok":
        return None, f"score_status:{scored['score_status']}"
    return (site.selected.terms["total"], scored["relative_transcription_score"]), None


class _Evaluation:
    """Accumulate every failure, difference and denominator for one reference."""

    def __init__(self) -> None:
        self.failures: list[dict] = []
        self.positions = 0
        self.reconstructed_arms = 0
        self.abs_diff: dict[str, list[float]] = {field: [] for field in FIELDS}
        self.rel_diff: dict[str, list[float]] = {field: [] for field in FIELDS}
        self.flags: dict[str, Counter] = {field: Counter() for field in FIELDS}

    def localization(
        self, category: str, reported: dict, recomputed: dict, case: dict, arm: str
    ) -> None:
        for key in LOCALIZATION_KEYS:
            if not _same(reported[key], recomputed[key]):
                self.failures.append(
                    _failure(
                        category,
                        key,
                        reported[key],
                        recomputed[key],
                        source_id=case["id"],
                        arm=arm,
                    )
                )
        if arm == "native":
            positions = case["native_positions"]
            mapped = [positions[UPSTREAM + o] for o in recomputed["best_offsets_nt"]]
            if not _same(case["best_native_tss_positions"], mapped):
                self.failures.append(
                    _failure(
                        category,
                        "best_native_tss_positions",
                        case["best_native_tss_positions"],
                        mapped,
                        source_id=case["id"],
                        arm=arm,
                    )
                )

    def summary(self, category: str, reported: dict, recomputed: dict) -> None:
        for key in ("anchors", "strands", "replicons"):
            if not _equal(reported[key], recomputed[key]):
                self.failures.append(
                    _failure(category, f"summary.{key}", reported[key], recomputed[key])
                )
        for arm in ARMS:
            for key in sorted(ARM_SUMMARY_KEYS):
                left, right = reported[arm][key], recomputed[arm][key]
                if not _equal(left, right):
                    self.failures.append(
                        _failure(category, f"summary.{key}", left, right, arm=arm)
                    )

    def arm(
        self,
        case: dict,
        arm: str,
        scorer: Scorer,
        params: core.PromoterParameters,
        calibration: core.Calibration,
    ) -> dict | None:
        """Compare all 41 starts; return reconstructed localization if complete."""
        reference = case[arm]
        sequence = case["sequence"] if arm == "native" else reference["sequence"]
        energies = []
        for row in reference["score_curve"]:
            offset = row["offset_nt"]
            values, detail = _score(scorer, sequence, offset, params, calibration)
            if values is None:
                self.failures.append(
                    _failure(
                        "calculation_failure",
                        "score",
                        None,
                        None,
                        source_id=case["id"],
                        arm=arm,
                        offset=offset,
                        detail=detail,
                    )
                )
                continue
            self.positions += 1
            energies.append(values[0])
            for field, observed in zip(FIELDS, values, strict=True):
                expected = row[field]
                absolute, relative, flag = differences(observed, expected)
                if absolute is not None:
                    self.abs_diff[field].append(absolute)
                if relative is not None:
                    self.rel_diff[field].append(relative)
                self.flags[field][flag] += 1
                if not math.isclose(
                    observed, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL
                ):
                    self.failures.append(
                        _failure(
                            "numeric_mismatch",
                            field,
                            expected,
                            observed,
                            source_id=case["id"],
                            arm=arm,
                            offset=offset,
                            detail=flag,
                        )
                    )
        if len(energies) != len(OFFSETS):
            return None
        self.reconstructed_arms += 1
        result = localization(energies)
        self.localization(
            "reconstructed_summary_mismatch", reference, result, case, arm
        )
        return result


def evaluate(
    report: dict,
    scorer: Scorer,
    params: core.PromoterParameters,
    calibration: core.Calibration,
) -> dict:
    """Rescore every case, arm and start; keep every failure in the denominators."""
    cases = report["results"]
    run = _Evaluation()
    source, reconstructed = [], []
    for case in cases:
        source_case, rebuilt = {}, {}
        for arm in ARMS:
            energies = [row["dG_total"] for row in case[arm]["score_curve"]]
            source_case[arm] = localization(energies)
            run.localization(
                "source_summary_mismatch", case[arm], source_case[arm], case, arm
            )
            result = run.arm(case, arm, scorer, params, calibration)
            if result is not None:
                rebuilt[arm] = result
        source.append(source_case)
        reconstructed.append(rebuilt)
    run.summary("source_summary_mismatch", report["summary"], aggregate(cases, source))
    complete = all(len(item) == len(ARMS) for item in reconstructed)
    if complete:
        run.summary(
            "reconstructed_summary_mismatch",
            report["summary"],
            aggregate(cases, reconstructed),
        )
    count = len(cases)
    tally = Counter(failure["category"] for failure in run.failures)
    return {
        "denominators": {
            "cases": count,
            "arms": count * len(ARMS),
            "positions": count * len(ARMS) * len(OFFSETS),
            "numeric_comparisons": count * len(ARMS) * len(OFFSETS) * len(FIELDS),
        },
        "evaluated": {
            "positions": run.positions,
            "numeric_comparisons": run.positions * len(FIELDS),
            "arms_with_reconstructed_localization": run.reconstructed_arms,
            "reconstructed_cohort_summary": complete,
        },
        "failures_by_category": {name: tally[name] for name in CATEGORIES},
        "maxima": {
            field: {
                "abs_diff": max(run.abs_diff[field], default=None),
                "rel_diff": max(run.rel_diff[field], default=None),
                **{flag: run.flags[field][flag] for flag in DIFFERENCE_FLAGS},
            }
            for field in FIELDS
        },
        "failures": run.failures,
    }


def _core_identity(params: core.PromoterParameters) -> dict:
    """Return the reconstructed model identity and hashes of the loaded files."""
    identity, _ = promoter_io.model_identity(params)
    parameter_file = Path(core.__file__).parent / "data/promoter-parameters-1.json"
    return {
        "model_identity": identity,
        "core_files_sha256": {
            "regsite/promoter.py": _sha256(Path(core.__file__).read_bytes()),
            "regsite/data/promoter-parameters-1.json": _sha256(
                parameter_file.read_bytes()
            ),
        },
        "kernel": "regsite.promoter.score_site on transcription-oriented '+' input",
        "layouts_required": LAYOUTS,
        "python": platform.python_version(),
    }


def check(
    reference: Path,
    expected_sha256: str,
    *,
    scorer: Scorer = core.score_site,
    max_bytes: int = MAX_INPUT_BYTES,
) -> dict:
    """Return the deterministic parity report for one external reference file.

    Raises OSError for an unreadable file and ParameterError for a broken core.
    """
    params = core.load_parameters()
    calibration = core.resolve_calibration("ecoli_mg1655", {"name": core.NATIVE_HOST})
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "claim": CLAIM,
        "status": "input_integrity_failure",
        "tool": {
            "module": __name__,
            "sha256": _sha256(Path(__file__).read_bytes()),
        },
        "input": {
            "expected_sha256": expected_sha256,
            "sha256": None,
            "bytes": None,
            "max_bytes": max_bytes,
        },
        "tolerances": {
            "numeric": {"rel_tol": REL_TOL, "abs_tol": ABS_TOL, "fields": FIELDS},
            "tie": {"rel_tol": 0.0, "abs_tol": TIE_ABS_TOL},
            "basis": "Predeclared before any native comparison; never tuned.",
        },
        "reconstruction": {
            **_core_identity(params),
            "calibration": calibration.to_dict(),
        },
        "integrity_failure": None,
        "reference": None,
        "cohort": None,
        "comparison": None,
    }
    with reference.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    try:
        _require(len(raw) <= max_bytes, "input_too_large", "$")
        result["input"].update(bytes=len(raw), sha256=_sha256(raw))
        _require(
            result["input"]["sha256"] == expected_sha256, "input_sha256_mismatch", "$"
        )
        document, completeness, identity = validate_reference(parse_reference(raw))
    except IntegrityError as exc:
        result["integrity_failure"] = {"code": exc.code, "path": exc.path}
        return result
    result["reference"] = {
        "schema_version": document["schema_version"],
        "model_host": document["model_host"],
        "source_inputs": document["inputs"],
        "declared_runtime": document["runtime"],
        "declared_runtime_note": "Recorded as declared; not independently verified.",
    }
    result["cohort"] = {
        "completeness": completeness,
        "max_sites": document["parameters"]["max_sites"],
        "seed": document["parameters"]["seed"],
        **identity,
    }
    comparison = evaluate(document, scorer, params, calibration)
    result["comparison"] = comparison
    result["status"] = "parity_failure" if comparison["failures"] else "pass"
    return result


def report_bytes(report: dict) -> bytes:
    """Serialize deterministically; nonfinite values are a programming error."""
    return (
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def _sha256_argument(value: str) -> str:
    if not SHA256_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("expected 64 lowercase hexadecimal digits")
    return value


def main(argv: list[str] | None = None) -> int:
    """Run the check; exit 0 pass, 1 parity failure, 2 input/setup, 3 bounded."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--sha256", required=True, type=_sha256_argument)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--allow-bounded-cohort",
        action="store_true",
        help="exit 0 for a passing bounded sample; it is never a full-pilot result",
    )
    args = parser.parse_args(argv)
    if args.output.is_symlink() or args.output.exists():
        print(f"Refusing to overwrite {args.output}", file=sys.stderr)
        return 2
    try:
        report = check(args.reference, args.sha256)
        data = report_bytes(report)  # Serialize before creating the output.
        with args.output.open("xb") as handle:
            handle.write(data)
    except (OSError, ValueError) as exc:  # ValueError includes ParameterError.
        print(f"Promoter pilot parity failed to run: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "cohort": report["cohort"]}))
    if report["status"] == "input_integrity_failure":
        return 2
    if report["status"] == "parity_failure":
        return 1
    if report["cohort"]["completeness"] != "full_eligible":
        if not args.allow_bounded_cohort:
            print("Bounded cohort is not a full-pilot parity result", file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
