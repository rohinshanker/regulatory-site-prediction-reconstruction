"""Group-bootstrap intervals from a promoter-native-metrics-1 document.

Consumes only the metrics document's overall and per-group sufficient
statistics: no scores, labels or other data are joined. Complete groups are
resampled with replacement and every all-case top-k/tolerance recovery ratio is
recomputed for the all-label and in-window denominators.
"""

import argparse
import json
import math
import platform
import random
import sys
from fractions import Fraction
from pathlib import Path

from benchmarks.promoter.native_inputs import (
    canonical_bytes,
    checked_hash,
    document_sha256,
    read_bounded,
    strict_json,
    write_exclusive,
)
from benchmarks.promoter.native_metrics import (
    MAX_LABELS,
    METRIC_SCHEMA,
    metric_settings,
)
from benchmarks.rbs.datasets import digest

UNCERTAINTY_SCHEMA = "promoter-native-uncertainty-1"
RESAMPLES = 10_000
SEED = 20261018
MIN_ELIGIBLE_GROUPS = 20
QUANTILES = (Fraction(1, 40), Fraction(39, 40))
DENOMINATORS = (("all_labels", "n_labels"), ("in_window_labels", "n_in_window"))
COUNT_FIELDS = (
    "n_labels",
    "n_in_window",
    "n_out_of_window",
    "n_label_candidate_scored",
    "n_in_complete_query",
)
MAX_METRICS_BYTES = 256 * 1024 * 1024
MAX_GROUPS = MAX_LABELS
MAX_RESAMPLED_GROUPS = 100_000_000
MAX_COLUMN_OPERATIONS = 1_000_000_000


def tool_sha256():
    """Identity of this exact uncertainty implementation."""
    return digest(Path(__file__).read_bytes())


def uncertainty_settings():
    """Fixed resampling contract; nothing here is tunable from the command line."""
    return {
        "resamples": RESAMPLES,
        "seed": SEED,
        "resampling": (
            "groups sorted by ID; each draw is random.Random(seed).choices("
            "range(G), k=G) in sequence, shared by every endpoint and denominator"
        ),
        "statistic": "sum of matched / sum of denominator over drawn groups",
        "interval": (
            "percentile: sorted defined values v, h = (n - 1) * q, "
            "v[floor(h)] + (h - floor(h)) * (v[floor(h) + 1] - v[floor(h)])"
        ),
        "quantiles": [str(q) for q in QUANTILES],
        "min_eligible_groups": MIN_ELIGIBLE_GROUPS,
        "eligible_group": "group with a positive denominator",
        "undefined_resample": "zero summed denominator; counted, never set to 0",
        "limits": {
            "max_groups": MAX_GROUPS,
            "max_resampled_groups": MAX_RESAMPLED_GROUPS,
            "max_column_operations": MAX_COLUMN_OPERATIONS,
        },
    }


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def _fraction_field(value, numerator, denominator, name):
    expected = numerator / denominator if denominator else None
    if value != expected or type(value) is not type(expected):
        raise ValueError(f"{name} disagrees with its counts")


def _summary(summary, roster, name):
    """Validated (denominator counts, matched counts) of one metrics summary."""
    if not isinstance(summary, dict):
        raise ValueError(f"{name} summary must be an object")
    counts = {
        field: _count(summary.get(field), f"{name}.{field}") for field in COUNT_FIELDS
    }
    if (
        not (
            counts["n_in_complete_query"]
            <= counts["n_label_candidate_scored"]
            <= counts["n_in_window"]
            <= counts["n_labels"]
        )
        or counts["n_out_of_window"] != counts["n_labels"] - counts["n_in_window"]
    ):
        raise ValueError(f"{name} label counts are inconsistent")
    rows = summary.get("recovery")
    if (
        not isinstance(rows, list)
        or [
            (row.get("top_k"), row.get("tolerance_nt"))
            if isinstance(row, dict)
            else None
            for row in rows
        ]
        != roster
    ):
        raise ValueError(f"{name} endpoint roster differs from the settings")
    matched = []
    for row in rows:
        hits = _count(row.get("matched"), f"{name}.matched")
        if hits > counts["n_in_complete_query"]:
            raise ValueError(f"{name} matched exceeds complete-query labels")
        for label, field in DENOMINATORS:
            _fraction_field(
                row.get(f"fraction_of_{label}"),
                hits,
                counts[field],
                f"{name}.fraction_of_{label}",
            )
        matched.append(hits)
    return counts, matched


def load_statistics(metrics):
    """Validate a metrics document and return its overall and group statistics."""
    if not isinstance(metrics, dict) or metrics.get("schema_version") != METRIC_SCHEMA:
        raise ValueError("Metrics schema must be " + METRIC_SCHEMA)
    settings = metrics.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("Metrics settings must be an object")
    if metric_settings(
        settings.get("lower_is_better"),
        settings.get("top_k", ()),
        settings.get("tolerances_nt", ()),
    ) != settings or metrics.get("settings_sha256") != document_sha256(settings):
        raise ValueError("Metrics settings or settings_sha256 mismatch")
    checked_hash(metrics.get("tool_sha256"))
    sources = metrics.get("inputs")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Metrics inputs must be a nonempty object")
    for value in sources.values():
        checked_hash(value)
    roster = [(k, t) for k in settings["top_k"] for t in settings["tolerances_nt"]]
    overall = _summary(metrics.get("overall"), roster, "overall")
    groups = metrics.get("groups")
    if (
        not isinstance(groups, dict)
        or not 0 < len(groups) <= MAX_GROUPS
        or metrics.get("n_groups") != len(groups)
        or type(metrics.get("n_groups")) is not int
    ):
        raise ValueError(f"Metrics need 1..{MAX_GROUPS} groups matching n_groups")
    rows = []
    for group_id in sorted(groups):
        if not group_id:
            raise ValueError("Group IDs must be nonempty")
        counts, matched = _summary(groups[group_id], roster, f"group {group_id}")
        if counts["n_labels"] == 0:
            raise ValueError(f"group {group_id} has no labels")
        rows.append((counts, matched))
    for field in COUNT_FIELDS:
        if sum(counts[field] for counts, _ in rows) != overall[0][field]:
            raise ValueError(f"Group {field} does not sum to overall")
    for index in range(len(roster)):
        if sum(matched[index] for _, matched in rows) != overall[1][index]:
            raise ValueError("Group matched counts do not sum to overall")
    return roster, overall, rows


def percentile(sorted_values, quantile):
    """Linear interpolation at h = (n - 1) * quantile of nonempty sorted values."""
    position = (len(sorted_values) - 1) * quantile
    lower = math.floor(position)
    if lower + 1 == len(sorted_values):
        return sorted_values[lower]
    low, high = sorted_values[lower], sorted_values[lower + 1]
    return low + float(position - lower) * (high - low)


def _draw(rng, n_groups):
    return rng.choices(range(n_groups), k=n_groups)


def bootstrap(columns, n_groups, settings):
    """Per-draw column sums for complete groups drawn with replacement."""
    if n_groups * settings["resamples"] > MAX_RESAMPLED_GROUPS or (
        n_groups * settings["resamples"] * len(columns) > MAX_COLUMN_OPERATIONS
    ):
        raise ValueError("Bootstrap work exceeds its declared limits")
    rng = random.Random(settings["seed"])
    sums = [[] for _ in columns]
    for _ in range(settings["resamples"]):
        drawn = _draw(rng, n_groups)
        for total, column in zip(sums, columns, strict=True):
            total.append(sum(map(column.__getitem__, drawn)))
    return sums


def summarize(metrics):
    """Point estimates, group counts and eligible bootstrap intervals."""
    settings = uncertainty_settings()
    roster, overall, rows = load_statistics(metrics)
    n_groups = len(rows)
    eligible = {
        label: sum(counts[field] > 0 for counts, _ in rows)
        for label, field in DENOMINATORS
    }
    sufficient = [
        (label, field)
        for label, field in DENOMINATORS
        if eligible[label] >= MIN_ELIGIBLE_GROUPS
    ]
    columns = [[counts[field] for counts, _ in rows] for _, field in sufficient] + [
        [matched[i] for _, matched in rows] for i in range(len(roster))
    ]
    sums = bootstrap(columns, n_groups, settings) if sufficient else []
    denominators = {
        label: {
            "n_labels": overall[0][field],
            "n_eligible_groups": eligible[label],
            "n_zero_denominator_groups": n_groups - eligible[label],
            "status": (
                "interval"
                if eligible[label] >= MIN_ELIGIBLE_GROUPS
                else "insufficient_group_count"
            ),
        }
        for label, field in DENOMINATORS
    }
    endpoints = []
    for label, field in DENOMINATORS:
        for index, (k, tolerance) in enumerate(roster):
            matched, denominator = overall[1][index], overall[0][field]
            row = {
                "top_k": k,
                "tolerance_nt": tolerance,
                "denominator": label,
                "matched": matched,
                "denominator_labels": denominator,
                "point": matched / denominator if denominator else None,
                "n_eligible_groups": eligible[label],
                "status": denominators[label]["status"],
                "n_resamples": 0,
                "n_defined_resamples": 0,
                "n_undefined_resamples": 0,
                "interval": None,
            }
            if (label, field) in sufficient:
                totals = sums[sufficient.index((label, field))]
                hits = sums[len(sufficient) + index]
                values = sorted(h / d for h, d in zip(hits, totals, strict=True) if d)
                row["n_resamples"] = len(totals)
                row["n_defined_resamples"] = len(values)
                row["n_undefined_resamples"] = len(totals) - len(values)
                if values:
                    row["interval"] = {
                        "level": 0.95,
                        "lower": percentile(values, QUANTILES[0]),
                        "upper": percentile(values, QUANTILES[1]),
                    }
                else:
                    row["status"] = "no_defined_resamples"
            endpoints.append(row)
    return {
        "schema_version": UNCERTAINTY_SCHEMA,
        "scope": (
            "group-bootstrap intervals for all-case positive TSS recovery; "
            "conditional on this source's ascertainment, without raw-read "
            "mapping or biological replicate uncertainty; no clinical, "
            "translational or genome-wide precision claim"
        ),
        "settings": settings,
        "settings_sha256": document_sha256(settings),
        "inputs": {
            "metrics_document_sha256": document_sha256(metrics),
            "metrics_settings_sha256": metrics["settings_sha256"],
            "metrics_tool_sha256": metrics["tool_sha256"],
            "metrics_inputs": metrics["inputs"],
        },
        "tool_sha256": tool_sha256(),
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "n_groups": n_groups,
        "denominators": denominators,
        "endpoints": endpoints,
    }


def main(argv=None):
    """Write a new 0600 uncertainty receipt; nonzero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--metrics-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        raw = read_bounded(args.metrics, MAX_METRICS_BYTES)
        if digest(raw) != checked_hash(args.metrics_sha256):
            raise ValueError("Metrics document file SHA-256 mismatch")
        metrics = strict_json(raw)
        if canonical_bytes(metrics) != raw:
            raise ValueError("Metrics document is not canonical tool output")
        result = summarize(metrics)
        write_exclusive(args.output, result, 0o600)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output_sha256": document_sha256(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
