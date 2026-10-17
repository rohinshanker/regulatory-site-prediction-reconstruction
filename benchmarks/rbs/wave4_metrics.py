"""Outcome-scale-free, paired block rank evaluation; no model imports or fits."""

import math
import random
import statistics
from collections import Counter

from benchmarks.rbs.metrics import correlation, finite_number, ranks

STATUSES = {
    "ok",
    "failed",
    "unsupported",
    "invalid_input",
    "no_candidate",
    "timeout",
    "not_run",
}


def indexed(rows):
    """Require unique nonempty string identities, preserving every source row."""
    result = {}
    for row in rows:
        identity = row["id"]
        if not isinstance(identity, str) or not identity or identity in result:
            raise ValueError("Invalid or duplicate identity")
        result[identity] = row
    return result


def join(inputs, outcomes, predictions):
    """Bind exact identity sets without printing labels or filtering failures."""
    source, measured, inferred = map(indexed, (inputs, outcomes, predictions))
    if source.keys() != measured.keys() or source.keys() != inferred.keys():
        raise ValueError("Input/outcome/prediction identity sets differ")
    rows = []
    for identity, row in source.items():
        observed = measured[identity]["observed"]
        pred = inferred[identity]
        score, status = pred["predicted"], pred["status"]
        seconds = pred["seconds"]
        if observed is not None and not finite_number(observed):
            raise ValueError("Invalid observed value")
        if status not in STATUSES or (
            not finite_number(score) if status == "ok" else score is not None
        ):
            raise ValueError("Invalid prediction status/value")
        if not finite_number(seconds) or seconds < 0:
            raise ValueError("Invalid elapsed time")
        if not isinstance(row["group"], str) or not row["group"]:
            raise ValueError("Missing block identity")
        if not isinstance(pred["reason"], str):
            raise ValueError("Missing categorical prediction reason")
        rows.append(
            {
                **row,
                "observed": observed,
                "predicted": score,
                "status": status,
                "seconds": seconds,
                "reason": pred["reason"],
            }
        )
    return rows


def rho(observed, predicted):
    """Average-rank Spearman; constants/short vectors return None, never zero."""
    return correlation(ranks(observed), ranks(predicted))


def summarize(rows):
    """Separate panel coverage, measured pairs, failure reasons and runtime."""
    usable = [r for r in rows if r["status"] == "ok" and r["observed"] is not None]
    times = sorted(r["seconds"] for r in rows if r["status"] != "not_run")
    success = sum(r["status"] == "ok" for r in rows)
    return {
        "n_inputs": len(rows),
        "n_observed": sum(r["observed"] is not None for r in rows),
        "n_success": success,
        "n_paired": len(usable),
        "coverage": success / len(rows) if rows else None,
        "spearman_rho": rho(
            [r["observed"] for r in usable], [r["predicted"] for r in usable]
        ),
        "status_counts": dict(sorted(Counter(r["status"] for r in rows).items())),
        "failure_reasons": dict(
            sorted(Counter(r["reason"] for r in rows if r["status"] != "ok").items())
        ),
        "runtime_seconds": {
            "n_executed": len(times),
            "sum": sum(times),
            "median": statistics.median(times) if times else None,
            "p95_nearest_rank": times[math.ceil(0.95 * len(times)) - 1]
            if times
            else None,
            "maximum": times[-1] if times else None,
        },
    }


def paired(reference, contender, settings):
    """Resample every original block; re-rank repeated common-success rows.

    Correlations use the identical finite observed pairs for both candidates.
    Blocks lacking usable pairs remain in the resampling population. No outcome
    values, per-case residuals, or group identities are returned in aggregates.
    """
    if any(
        type(settings[k]) is not int
        for k in (
            "draws",
            "seed",
            "minimum_usable_draws",
            "minimum_common_rows",
            "minimum_common_blocks",
        )
    ) or not (
        settings["draws"] >= 2
        and 1 <= settings["minimum_usable_draws"] <= settings["draws"]
        and settings["minimum_common_rows"] >= 2
        and settings["minimum_common_blocks"] >= 2
    ):
        raise ValueError("Invalid block-resampling settings")
    left, right = indexed(reference), indexed(contender)
    if left.keys() != right.keys():
        raise ValueError("Paired panel identities differ")
    groups = {}
    lost, shared_success = 0, 0
    for identity, a in left.items():
        b = right[identity]
        if a["group"] != b["group"] or a["observed"] != b["observed"]:
            raise ValueError("Paired block or outcome mismatch")
        group = groups.setdefault(a["group"], [])
        lost += a["status"] == "ok" and b["status"] != "ok"
        shared_success += a["status"] == b["status"] == "ok"
        if a["status"] == b["status"] == "ok" and a["observed"] is not None:
            group.append((a["observed"], a["predicted"], b["predicted"]))
    keys = sorted(groups)
    common = [p for key in keys for p in groups[key]]

    def difference(pairs):
        observed = [p[0] for p in pairs]
        a = rho(observed, [p[1] for p in pairs])
        b = rho(observed, [p[2] for p in pairs])
        return None if a is None or b is None else b - a

    point = difference(common)
    result = {
        "n_inputs": len(left),
        "n_common_success": shared_success,
        "n_common_measured": len(common),
        "n_blocks": len(keys),
        "n_common_blocks": sum(bool(g) for g in groups.values()),
        "lost_reference_successes": lost,
        "rank_gain": point,
        "requested_draws": settings["draws"],
        "attempted_draws": 0,
        "usable_draws": 0,
        "undefined_draws": 0,
        "interval95": None,
        "interval_status": "insufficient_support",
    }
    if (
        len(common) < settings["minimum_common_rows"]
        or result["n_common_blocks"] < settings["minimum_common_blocks"]
    ):
        return result
    if point is None:
        result["interval_status"] = "undefined_point_correlation"
        return result
    rng, draws = random.Random(settings["seed"]), []
    for _ in range(settings["draws"]):
        sampled = [p for _ in keys for p in groups[rng.choice(keys)]]
        estimate = difference(sampled)
        if estimate is not None:
            draws.append(estimate)
    result.update(
        attempted_draws=settings["draws"],
        usable_draws=len(draws),
        undefined_draws=settings["draws"] - len(draws),
    )
    if len(draws) < settings["minimum_usable_draws"]:
        result["interval_status"] = "insufficient_usable_draws"
        return result
    draws.sort()
    result.update(
        interval_status="ok",
        interval95=[
            draws[math.floor(0.025 * (len(draws) - 1))],
            draws[math.ceil(0.975 * (len(draws) - 1))],
        ],
    )
    return result


def advancement(comparison, candidate_summary, gate, complete, software_ready):
    """One fixed conjunctive gate, with explicit reasons for non-advancement."""
    interval = comparison["interval95"]
    reasons = []
    for accepted, reason in (
        (complete, "collection_incomplete"),
        (software_ready, "software_resource_gate_unmet"),
        (
            candidate_summary["coverage"] is not None
            and candidate_summary["coverage"] >= gate["minimum_coverage"],
            "coverage_below_threshold",
        ),
        (comparison["lost_reference_successes"] == 0, "lost_reference_successes"),
        (
            comparison["rank_gain"] is not None
            and comparison["rank_gain"] >= gate["minimum_rank_gain"],
            "rank_gain_below_threshold_or_undefined",
        ),
        (
            interval is not None and interval[0] > 0,
            "interval_not_above_zero_or_undefined",
        ),
    ):
        if not accepted:
            reasons.append(reason)
    return {"advance": not reasons, "reasons": reasons}
