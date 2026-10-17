"""Explicit all-case metrics for paired positive-scale measurements.

This module never fits or rescales predictions. Callers must supply a previously
frozen calibration or a documented reference normalization. No runtime calculator
code is imported. Undefined correlations are represented by None.
"""

import math
import random
import statistics
from collections import Counter, defaultdict


def finite_number(value):
    """Return whether a value is a finite JSON number, explicitly excluding bool."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def correlation(x, y):
    """Return Pearson r, or None for fewer than two or constant observations."""
    if len(x) != len(y):
        raise ValueError("Paired vectors must have equal length")
    if any(not finite_number(v) for v in [*x, *y]):
        raise ValueError("Correlation inputs must be finite")
    if len(x) < 2:
        return None
    mx, my = statistics.mean(x), statistics.mean(y)
    dx, dy = [v - mx for v in x], [v - my for v in y]
    denominator = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if denominator == 0:
        return None
    return max(
        -1.0, min(1.0, sum(a * b for a, b in zip(dx, dy, strict=True)) / denominator)
    )


def ranks(values):
    """Return one-based average ranks, including ties."""
    if any(not finite_number(value) for value in values):
        raise ValueError("Rank inputs must be finite numbers, not booleans")
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i + 1
        while j < len(values) and values[ordered[j]] == values[ordered[i]]:
            j += 1
        for index in ordered[i:j]:
            result[index] = (i + 1 + j) / 2
        i = j
    return result


def wilson(successes, total):
    """Return a descriptive 95% binomial Wilson interval; no independence claim."""
    if (
        type(successes) is not int
        or type(total) is not int
        or not 0 <= successes <= total
    ):
        raise ValueError("Invalid binomial counts")
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    )
    return [max(0.0, center - half), min(1.0, center + half)]


def summary(rows):
    """Summarize paired rows while counting every submitted measurement.

    Args:
        rows: Dictionaries with unique id, positive observed, status and predicted.
            Missing predictions count against all-case fold-accuracy fractions.
            group is used by the separate clustered interval helper.

    Returns:
        JSON-safe metrics with explicit denominators and failure counts.

    Raises:
        ValueError: If IDs, observations, statuses or predictions are invalid.
    """
    seen, failed, pairs = set(), Counter(), []
    statuses = {
        "ok",
        "failed",
        "no_candidate",
        "unsupported",
        "invalid_input",
        "not_evaluated",
    }
    for row in rows:
        if not row["id"] or row["id"] in seen:
            raise ValueError("Measurement IDs must be unique and nonempty")
        seen.add(row["id"])
        observed = row["observed"]
        if not finite_number(observed) or observed <= 0:
            raise ValueError("Observed values must be finite and positive")
        if row["status"] not in statuses:
            raise ValueError("Unknown prediction status")
        if row["status"] != "ok":
            failed[row["status"]] += 1
            continue
        predicted = row["predicted"]
        if not finite_number(predicted) or predicted <= 0:
            raise ValueError("Successful predictions must be finite and positive")
        pairs.append((math.log2(observed), math.log2(predicted)))
    errors = [p - o for o, p in pairs]
    r = correlation([x[0] for x in pairs], [x[1] for x in pairs])
    rho = correlation(ranks([x[0] for x in pairs]), ranks([x[1] for x in pairs]))
    result = {
        "n_submitted": len(rows),
        "n_success": len(pairs),
        "failures": dict(sorted(failed.items())),
        "coverage": len(pairs) / len(rows) if rows else None,
        "pearson_r_log": r,
        "pearson_r2_log": r * r if r is not None else None,
        "spearman_rho": rho,
        "rmse_log2": math.sqrt(statistics.mean(e * e for e in errors))
        if errors
        else None,
        "mae_log2": statistics.mean(abs(e) for e in errors) if errors else None,
        "median_absolute_log2": statistics.median(abs(e) for e in errors)
        if errors
        else None,
        "bias_log2": statistics.mean(errors) if errors else None,
    }
    for factor in (2, 5):
        successes = sum(abs(e) <= math.log2(factor) + 1e-12 for e in errors)
        result[f"within_{factor}fold"] = {
            "n": successes,
            "all_case_fraction": successes / len(rows) if rows else None,
            "successful_pair_fraction": successes / len(pairs) if pairs else None,
            "all_case_wilson95": wilson(successes, len(rows)),
        }
    return result


def cluster_mae_interval(rows, repetitions=2000, seed=20261016):
    """Percentile interval resampling entire supplied groups, never individual rows."""
    summary(rows)  # Enforce the same input and failure contract.
    if type(repetitions) is not int or repetitions < 2:
        raise ValueError("At least two bootstrap repetitions are required")
    groups = defaultdict(list)
    for row in rows:
        if row["status"] == "ok":
            groups[row["group"]].append(
                abs(math.log2(row["predicted"]) - math.log2(row["observed"]))
            )
    if len(groups) < 2:
        return None
    keys, rng, estimates = sorted(groups), random.Random(seed), []
    for _ in range(repetitions):
        selected = [value for _ in keys for value in groups[rng.choice(keys)]]
        estimates.append(statistics.mean(selected))
    estimates.sort()
    return [
        estimates[math.floor(0.025 * (repetitions - 1))],
        estimates[math.ceil(0.975 * (repetitions - 1))],
    ]


def edit_distance(left, right):
    """Levenshtein distance for outcome-free sequence-family auditing."""
    previous = list(range(len(right) + 1))
    for i, base in enumerate(left, start=1):
        current = [i]
        for j, other in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (base != other),
                )
            )
        previous = current
    return previous[-1]


def cross_partition_overlap(development, heldout, threshold=0.85):
    """Return exact/window similarity flags; reads only ids, sequence and start."""
    if not finite_number(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Similarity threshold must be between zero and one")
    hits = []
    for dev in development:
        for test in heldout:
            a = dev["sequence"][max(0, dev["start"] - 35) : dev["start"] + 70]
            b = test["sequence"][max(0, test["start"] - 35) : test["start"] + 70]
            if not a or not b:
                raise ValueError("Regulatory windows must be nonempty")
            similarity = 1 - edit_distance(a, b) / max(len(a), len(b))
            if dev["sequence"] == test["sequence"] or similarity >= threshold:
                hits.append(
                    {
                        "development_id": dev["id"],
                        "heldout_id": test["id"],
                        "exact_sequence": dev["sequence"] == test["sequence"],
                        "window_similarity": similarity,
                    }
                )
    return hits
