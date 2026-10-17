"""Independent native TE calibration, coverage and paired family comparisons."""

import math
import random
import statistics
from collections import Counter, defaultdict

from benchmarks.rbs.karlsen import assay_value
from benchmarks.rbs.metrics import correlation, finite_number, ranks, summary


def pairs(records, predictions, offset_log2=0.0):
    """Join frozen cases; preserve assay exclusions and every prediction failure."""
    if not finite_number(offset_log2):
        raise ValueError("Calibration offset must be finite")
    source = {row["id"]: row for row in records}
    inferred = {row["id"]: row for row in predictions}
    if (
        len(source) != len(records)
        or len(inferred) != len(predictions)
        or any(not isinstance(key, str) or not key for key in source | inferred)
        or set(inferred) - set(source)
    ):
        raise ValueError("Duplicate, unknown or invalid case identity")
    result, excluded = [], Counter()
    for identity, row in source.items():
        measurement = assay_value(row["observed"])
        if not measurement["log_eligible"]:
            excluded[measurement["status"]] += 1
            continue
        if not isinstance(row["group"], str) or not row["group"]:
            raise ValueError("Every eligible case requires a frozen group")
        prediction = inferred.get(identity, {})
        item = {
            "id": identity,
            "group": row["group"],
            "observed": measurement["value"],
            "predicted": prediction.get("predicted"),
            "status": prediction.get("status", "not_evaluated"),
        }
        summary([item])
        if item["status"] == "ok":
            try:
                item["predicted"] = 2 ** (math.log2(item["predicted"]) + offset_log2)
            except OverflowError as error:
                raise ValueError(
                    "Calibrated value outside positive finite range"
                ) from error
            if not finite_number(item["predicted"]) or item["predicted"] <= 0:
                raise ValueError("Calibrated value outside positive finite range")
        result.append(item)
    return result, dict(sorted(excluded.items()))


def fit_intercept(records, predictions):
    """Fit only median log2 residual, requiring explicit development-train inputs."""
    if not records or any(row["partition"] != "development_train" for row in records):
        raise ValueError("Calibration requires nonempty development-train only")
    joined, excluded = pairs(records, predictions)
    residuals = [
        math.log2(row["observed"]) - math.log2(row["predicted"])
        for row in joined
        if row["status"] == "ok"
    ]
    if not residuals:
        raise ValueError("Calibration requires successful positive training pairs")
    return {
        "method": "development_train_median_log2_residual",
        "offset_log2": statistics.median(residuals),
        "n_training_cases": len(records),
        "n_fitted": len(residuals),
        "assay_exclusions": excluded,
        "final_refit": False,
    }


def evaluate(records, predictions, offset_log2=0.0):
    """Report native-scale coverage and calibrated relative TE errors separately."""
    joined, excluded = pairs(records, predictions, offset_log2)
    return {
        "n_source_cases": len(records),
        "n_log_eligible": len(joined),
        "assay_exclusions": excluded,
        "offset_log2": offset_log2,
        "metrics": summary(joined),
    }


def paired_comparison(
    reference,
    contender,
    repetitions=10000,
    seed=20261017,
    confidence=0.975,
    worthwhile_gain=0.2,
):
    """Paired group bootstrap of reference minus contender absolute log2 error.

    Positive gain favors the contender. A missing baseline-valid prediction
    prevents a superiority claim even when successful-pair errors look better.
    Intervals describe family sampling, never biological replicate uncertainty.
    """
    ref, con = {r["id"]: r for r in reference}, {r["id"]: r for r in contender}
    summary(reference)
    summary(contender)
    if set(ref) != set(con) or any(
        (ref[key]["observed"], ref[key]["group"])
        != (con[key]["observed"], con[key]["group"])
        for key in ref
    ):
        raise ValueError("Paired contrasts require identical cases, labels and groups")
    if (
        type(repetitions) is not int
        or repetitions < 2
        or not finite_number(confidence)
        or not 0 < confidence < 1
        or not finite_number(worthwhile_gain)
        or worthwhile_gain < 0
    ):
        raise ValueError("Invalid bootstrap or practical-gain configuration")
    groups, observed, ref_logs, con_logs = defaultdict(list), [], [], []
    dropped = 0
    for key, row in ref.items():
        if row["status"] != "ok":
            continue
        if con[key]["status"] != "ok":
            dropped += 1
            continue
        target = math.log2(row["observed"])
        first, second = math.log2(row["predicted"]), math.log2(con[key]["predicted"])
        groups[row["group"]].append(abs(first - target) - abs(second - target))
        observed.append(target)
        ref_logs.append(first)
        con_logs.append(second)
    values = [value for group in groups.values() for value in group]
    gain = statistics.mean(values) if values else None
    interval = None
    if len(groups) >= 2:
        sufficient = [(sum(group), len(group)) for _, group in sorted(groups.items())]
        estimates, rng = [], random.Random(seed)
        for _ in range(repetitions):
            selected = [rng.choice(sufficient) for _ in sufficient]
            estimates.append(sum(x[0] for x in selected) / sum(x[1] for x in selected))
        estimates.sort()
        tail = (1 - confidence) / 2
        interval = [
            estimates[math.floor(tail * (repetitions - 1))],
            estimates[math.ceil((1 - tail) * (repetitions - 1))],
        ]
    ref_rho = correlation(ranks(observed), ranks(ref_logs))
    con_rho = correlation(ranks(observed), ranks(con_logs))
    ref_n = sum(row["status"] == "ok" for row in reference)
    con_n = sum(row["status"] == "ok" for row in contender)
    coverage_gate = (
        bool(reference)
        and dropped == 0
        and con_n >= ref_n
        and con_n / len(reference) >= 0.95
    )
    rank_gate = (
        ref_rho is not None and con_rho is not None and con_rho >= ref_rho - 0.05
    )
    return {
        "n_all_cases": len(reference),
        "n_common_success": len(values),
        "n_common_groups": len(groups),
        "baseline_valid_cases_dropped": dropped,
        "mae_log2_gain": gain,
        "confidence": confidence,
        "paired_group_bootstrap_interval": interval,
        "bootstrap_seed": seed,
        "bootstrap_repetitions": repetitions,
        "coverage_gate": coverage_gate,
        "reference_spearman_common": ref_rho,
        "contender_spearman_common": con_rho,
        "spearman_gate": rank_gate,
        "statistical_and_practical_gain": gain is not None
        and gain >= worthwhile_gain
        and interval is not None
        and interval[0] > 0,
        "subgroup_gate_required_separately": True,
    }


def subgroup_gates(reference, contender, memberships, minimum_n=30, tolerance=0.5):
    """Predeclared input-only strata; compare untrimmed common-pair MAE."""
    if (
        type(minimum_n) is not int
        or minimum_n < 1
        or not finite_number(tolerance)
        or tolerance < 0
    ):
        raise ValueError("Invalid subgroup tolerance or denominator")
    ref, con = (
        {row["id"]: row for row in reference},
        {row["id"]: row for row in contender},
    )
    if (
        set(ref) != set(con)
        or set(memberships) != set(ref)
        or any(
            (ref[key]["observed"], ref[key]["group"])
            != (con[key]["observed"], con[key]["group"])
            for key in ref
        )
    ):
        raise ValueError("Subgroups require the same frozen identity set")
    summary(reference)
    summary(contender)
    grouped = defaultdict(list)
    for identity, labels in memberships.items():
        if (
            not isinstance(labels, list)
            or any(not isinstance(label, str) or not label for label in labels)
            or len(set(labels)) != len(labels)
        ):
            raise ValueError("Subgroup labels must be unique nonempty strings")
        for label in labels:
            grouped[label].append(identity)
    result = {}
    for label, identities in sorted(grouped.items()):
        common = [
            key
            for key in identities
            if ref[key]["status"] == con[key]["status"] == "ok"
        ]
        differences = [
            abs(math.log2(con[key]["predicted"]) - math.log2(con[key]["observed"]))
            - abs(math.log2(ref[key]["predicted"]) - math.log2(ref[key]["observed"]))
            for key in common
        ]
        increase = statistics.mean(differences) if differences else None
        result[label] = {
            "n_all": len(identities),
            "n_common": len(common),
            "mae_increase_log2": increase,
            "gate": None if len(common) < minimum_n else increase <= tolerance,
        }
    return result
