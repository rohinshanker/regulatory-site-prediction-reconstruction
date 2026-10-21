"""Check consumed Wave 4 public receipts without scientific recomputation."""

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

REPORT = "docs/validation/rbs-wave4-results.md"
PROTOCOL = "benchmarks/rbs/wave4-protocol.json"
FREEZE = "benchmarks/rbs/results/wave4-freeze.json"
AGGREGATE = "benchmarks/rbs/results/wave4-aggregate.json"
REVIEW = "benchmarks/rbs/results/wave4-review.json"
INPUTS = (REPORT, PROTOCOL, FREEZE, AGGREGATE, REVIEW)
MAX_BYTES = 2_000_000
MAX_DEPTH = 64
MAX_NODES = 100_000
SCOPE = {
    "check": "public_receipt_consistency",
    "stage": "Wave4",
    "cohort": "consumed_one_study",
    "independent_biological_recomputation": False,
    "markdown_semantics_checked": False,
    "release_or_accuracy_approval": False,
}
ROSTER = {
    "historical-traceback2": "mechanistic",
    "standby2014-traceback2": "mechanistic",
    "joint_standby-traceback2": "mechanistic",
    "historical-linker3": "mechanistic",
    "standby2014-linker3": "mechanistic",
    "joint_standby-linker3": "mechanistic",
    "public2014-sequence-v1": "learned",
    "ostir-1.1.3": "ostir",
    "rebeca-exp67-true": "rebeca",
    "control-constant": "constant",
    "control-gc-content": "gc_content",
}
STATUSES = {
    "ok",
    "failed",
    "unsupported",
    "invalid_input",
    "no_candidate",
    "timeout",
    "not_run",
}
SUMMARY_KEYS = (
    "n_inputs",
    "n_observed",
    "n_success",
    "n_paired",
    "coverage",
    "spearman_rho",
    "status_counts",
    "failure_reasons",
    "runtime_seconds",
)
COMPARISON_KEYS = (
    "n_inputs",
    "n_common_success",
    "n_common_measured",
    "n_blocks",
    "n_common_blocks",
    "lost_reference_successes",
    "rank_gain",
    "requested_draws",
    "attempted_draws",
    "usable_draws",
    "undefined_draws",
    "interval95",
    "interval_status",
)
POINT_ROLE = "descriptive subgroup point only"
SECONDARY_ROLE = (
    "exposed secondary, one connected sequence family; "
    "no promotion or independent-family interval"
)


class ReceiptError(ValueError):
    """Unavailable, malformed, untrusted or inconsistent public input."""


def require(condition, message):
    if not condition:
        raise ReceiptError(message)


def canonical(value):
    """Deterministic compact stdout encoding, including its terminating LF."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def original_bytes(aggregate):
    """Recover the published evaluator encoding, retaining insertion order."""
    value = {k: v for k, v in aggregate.items() if k != "publication_context"}
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def same(actual, expected, where):
    require(canonical(actual) == canonical(expected), f"{where}: mismatch")


def keys(value, expected, where):
    require(
        type(value) is dict and set(value) == set(expected),
        f"{where}: unsupported schema/keys",
    )


def count(value, where):
    require(
        type(value) is int and 0 <= value <= 10**12,
        f"{where}: expected bounded nonnegative integer",
    )
    return value


def number(value, where):
    require(
        type(value) in (int, float) and math.isfinite(value),
        f"{where}: expected finite number",
    )
    return value


def close(actual, expected, where):
    require(
        math.isclose(number(actual, where), expected, rel_tol=1e-12, abs_tol=1e-15),
        f"{where}: arithmetic mismatch",
    )


def bounded(value, limit, where):
    if value is not None:
        require(-limit <= number(value, where) <= limit, f"{where}: bounds")


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "JSON: duplicate key")
        result[key] = value
    return result


def _constant(value):
    raise ReceiptError("JSON: non-finite constant")


def _tree(value):
    pending = [(value, 0)]
    nodes = 0
    while pending:
        child, depth = pending.pop()
        nodes += 1
        require(depth <= MAX_DEPTH and nodes <= MAX_NODES, "JSON: tree limit exceeded")
        if type(child) is dict:
            for key in child:
                key.encode("utf-8", errors="strict")
            pending.extend((v, depth + 1) for v in child.values())
        elif type(child) is list:
            pending.extend((v, depth + 1) for v in child)
        elif type(child) is float:
            require(math.isfinite(child), "JSON: non-finite number")
        elif type(child) is str:
            child.encode("utf-8", errors="strict")


def parse(data):
    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        _tree(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ReceiptError(
            "JSON: malformed, duplicate, non-finite or excessive tree"
        ) from exc


def read_regular(path):
    """Bound bytes using descriptors and no-follow on every path component."""
    require(".." not in Path(path).parts, "input: parent traversal refused")
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = child
        child = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd
        )
        with os.fdopen(child, "rb") as stream:
            info = os.fstat(stream.fileno())
            require(stat.S_ISREG(info.st_mode), "input: expected regular file")
            require(info.st_size <= MAX_BYTES, "input: byte limit exceeded")
            data = stream.read(MAX_BYTES + 1)
            require(len(data) <= MAX_BYTES, "input: byte limit exceeded")
            return data
    finally:
        os.close(fd)


def sha(value):
    require(
        type(value) is str
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value),
        "reference: invalid SHA-256",
    )
    return value


def references(value, pointer=()):
    """Inventory scalar digests and explicit hash maps; never open references."""
    result = []
    # The fixed learned-model command records one artifact digest positionally.
    # Its surrounding command and filenames remain opaque metadata.
    if pointer == ("configurations", 6, "command", 7):
        result.append({"location": list(pointer), "sha256": sha(value)})
    elif type(value) is dict:
        for key, child in sorted(value.items()):
            location = (*pointer, key)
            if key.endswith("sha256") or location in (("identities",), ("artifacts",)):
                if type(child) is dict:
                    for name, hashed in sorted(child.items()):
                        result.append(
                            {"location": [*location, name], "sha256": sha(hashed)}
                        )
                else:
                    result.append({"location": list(location), "sha256": sha(child)})
            else:
                result.extend(references(child, location))
    elif type(value) is list:
        for i, child in enumerate(value):
            result.extend(references(child, (*pointer, i)))
    return result


def inventory(docs):
    public = {
        PROTOCOL: set(),
        FREEZE: {("identities", "protocol_sha256")},
        AGGREGATE: {("identities", "protocol")},
        REVIEW: {("artifacts", REPORT), ("artifacts", AGGREGATE)},
    }
    return {
        p: [r for r in references(docs[p]) if tuple(r["location"]) not in public[p]]
        for p in public
    }


def metadata(docs):
    """Only immutable metadata, never dynamic metric/count/gate output values."""
    a, r = docs[AGGREGATE], docs[REVIEW]
    publication = {
        k: v
        for k, v in a["publication_context"].items()
        if k != "original_evaluator_aggregate_sha256"
    }
    review = {
        k: v
        for k, v in r.items()
        if k
        not in (
            "artifacts",
            "private_original_aggregate_sha256",
            "independent_recomputation",
        )
    }
    return {
        PROTOCOL: docs[PROTOCOL],
        FREEZE: docs[FREEZE],
        "publication_context": publication,
        "review": review,
        "aggregate_scope": a["scope"],
        "primary_endpoint": a["primary"]["endpoint"],
    }


def frequencies(value, total, where, allowed=None):
    require(type(value) is dict, f"{where}: expected count map")
    for key, v in value.items():
        require(type(key) is str and bool(key), f"{where}: category")
        if allowed is not None:
            require(key in allowed, f"{where}: unsupported status")
        require(count(v, where) > 0, f"{where}: positive entries required")
    same(sum(value.values()), total, f"{where}: count total")


def summary(value):
    keys(value, SUMMARY_KEYS, "model")
    n, observed, success, paired = (count(value[k], k) for k in SUMMARY_KEYS[:4])
    require(observed <= n and success <= n, "model: marginal bounds")
    require(
        max(0, success + observed - n) <= paired <= min(success, observed),
        "model: measured-success intersection",
    )
    if n:
        close(value["coverage"], success / n, "coverage")
    else:
        same(value["coverage"], None, "empty coverage")
    bounded(value["spearman_rho"], 1, "correlation")
    if paired < 2:
        same(value["spearman_rho"], None, "insufficient correlation pairs")
    frequencies(value["status_counts"], n, "statuses", STATUSES)
    same(value["status_counts"].get("ok", 0), success, "success count")
    frequencies(value["failure_reasons"], n - success, "failure reasons")
    runtime = value["runtime_seconds"]
    keys(
        runtime,
        ("n_executed", "sum", "median", "p95_nearest_rank", "maximum"),
        "runtime",
    )
    executed = count(runtime["n_executed"], "executed")
    same(executed, n - value["status_counts"].get("not_run", 0), "runtime accounting")
    total = number(runtime["sum"], "runtime sum")
    if executed:
        median, p95, maximum = (
            number(runtime[k], "runtime quantile")
            for k in ("median", "p95_nearest_rank", "maximum")
        )
        require(0 <= median <= p95 <= maximum, "runtime: quantile ordering")
        require(
            maximum <= total + 1e-12 and total <= executed * maximum + 1e-12,
            "runtime: sum bounds",
        )
        if executed == 1:
            close(median, maximum, "singleton runtime median")
            close(p95, maximum, "singleton runtime p95")
        if executed == 2:
            close(total, 2 * median, "two-execution median")
            close(p95, maximum, "two-execution p95")
    else:
        same(total, 0, "empty runtime sum")
        for field in ("median", "p95_nearest_rank", "maximum"):
            same(runtime[field], None, "empty runtime quantile")


def intersection(common, left, right, population, where):
    require(
        max(0, left + right - population) <= count(common, where) <= min(left, right),
        f"{where}: intersection bounds",
    )


def point(value, left, right, minimum, eligible=True):
    """Validate only justified paired-cohort arithmetic, never compute ranks."""
    common = value["n_common_measured"]
    intersection(
        common,
        left["n_paired"],
        right["n_paired"],
        left["n_observed"],
        "common measured",
    )
    gain = value["rank_gain"]
    bounded(gain, 2, "rank gain")
    if not eligible or common < minimum:
        same(gain, None, "unsupported point")
    elif left["n_paired"] == right["n_paired"] == left["n_observed"]:
        # Complete measured cohorts guarantee identical rows. Equal marginal
        # success counts without this guarantee do not justify subtraction.
        a, b = left["spearman_rho"], right["spearman_rho"]
        if a is None or b is None:
            same(gain, None, "undefined point")
        else:
            close(gain, b - a, "common-cohort rank gain")


def comparison(value, left, right, protocol):
    keys(value, COMPARISON_KEYS, "comparison")
    n = left["n_inputs"]
    same(count(value["n_inputs"], "comparison inputs"), n, "comparison inputs")
    common = value["n_common_success"]
    intersection(common, left["n_success"], right["n_success"], n, "common success")
    measured = count(value["n_common_measured"], "common measured")
    require(
        0 <= common - measured <= n - left["n_observed"], "comparison: measured subset"
    )
    unobserved_left = left["n_success"] - left["n_paired"]
    unobserved_right = right["n_success"] - right["n_paired"]
    lower = max(
        0,
        left["n_paired"] + right["n_paired"] - left["n_observed"],
        common - min(unobserved_left, unobserved_right),
    )
    upper = min(
        left["n_paired"],
        right["n_paired"],
        common - max(0, unobserved_left + unobserved_right - (n - left["n_observed"])),
    )
    require(lower <= measured <= upper, "comparison: observed/unobserved intersection")
    same(
        count(value["lost_reference_successes"], "lost successes"),
        left["n_success"] - common,
        "lost successes",
    )
    same(
        count(value["n_blocks"], "blocks"),
        protocol["primary_endpoint"]["n_blocks"],
        "blocks",
    )
    blocks = count(value["n_common_blocks"], "common blocks")
    require(
        blocks <= min(value["n_blocks"], measured) and bool(blocks) == bool(measured),
        "comparison: common blocks",
    )
    settings = protocol["bootstrap"]
    support = (
        measured >= settings["minimum_common_rows"]
        and blocks >= settings["minimum_common_blocks"]
    )
    point(value, left, right, settings["minimum_common_rows"], support)
    requested, attempted, usable, undefined = (
        count(value[k], k)
        for k in (
            "requested_draws",
            "attempted_draws",
            "usable_draws",
            "undefined_draws",
        )
    )
    same(requested, settings["draws"], "requested draws")
    require(
        attempted == usable + undefined and attempted <= requested,
        "bootstrap: draw accounting",
    )
    if not support:
        status = "insufficient_support"
    elif value["rank_gain"] is None:
        status = "undefined_point_correlation"
    elif usable < settings["minimum_usable_draws"]:
        status = "insufficient_usable_draws"
    else:
        status = "ok"
    same(value["interval_status"], status, "interval status")
    same(
        attempted,
        requested if support and value["rank_gain"] is not None else 0,
        "attempted draws",
    )
    interval = value["interval95"]
    if status == "ok":
        require(
            type(interval) is list and len(interval) == 2, "interval: expected pair"
        )
        lo, hi = (number(v, "interval") for v in interval)
        require(-2 <= lo <= hi <= 2, "interval: bounds/order")
    else:
        same(interval, None, "undefined interval")


def models(value, n=None, observed=None):
    keys(value, ROSTER, "model roster")
    counts = set()
    for row in value.values():
        summary(row)
        counts.add((row["n_inputs"], row["n_observed"]))
        if n is not None:
            same(row["n_inputs"], n, "panel inputs")
        if observed is not None:
            same(row["n_observed"], observed, "panel observations")
    require(len(counts) == 1, "panel: shared source counts")


def point_group(group, contrast, secondary=False):
    keys(
        group,
        ("models", "primary_pair", "role") if secondary else ("models", "primary_pair"),
        "point group",
    )
    if secondary:
        same(group["role"], SECONDARY_ROLE, "secondary role")
    pair = group["primary_pair"]
    keys(pair, ("n_common_measured", "rank_gain", "interval95", "role"), "point pair")
    same(pair["role"], POINT_ROLE, "point role")
    same(pair["interval95"], None, "point-only interval")
    point(
        pair,
        group["models"][contrast["reference"]],
        group["models"][contrast["contender"]],
        30,
    )


def gate(comparison_, contender, protocol, complete, software):
    """Reconcile the fixed, ordered advancement conjunction."""
    settings = protocol["advancement"]
    interval, gain = comparison_["interval95"], comparison_["rank_gain"]
    conditions = (
        (complete, "collection_incomplete"),
        (software, "software_resource_gate_unmet"),
        (
            contender["coverage"] is not None
            and contender["coverage"] >= settings["minimum_coverage"],
            "coverage_below_threshold",
        ),
        (
            comparison_["lost_reference_successes"]
            == settings["lost_baseline_successes_allowed"],
            "lost_reference_successes",
        ),
        (
            gain is not None and gain >= settings["minimum_rank_gain"],
            "rank_gain_below_threshold_or_undefined",
        ),
        (
            interval is not None
            and interval[0] > settings["minimum_interval_lower_exclusive"],
            "interval_not_above_zero_or_undefined",
        ),
    )
    reasons = [reason for accepted, reason in conditions if not accepted]
    return {"advance": not reasons, "reasons": reasons}


def protocol_numbers(protocol):
    """Keep published numerical settings fixed and reject Boolean counts."""
    for field, expected in (("n_inputs", 335), ("n_observed", 332), ("n_blocks", 56)):
        same(
            count(protocol["primary_endpoint"][field], "protocol count"),
            expected,
            "frozen primary setting",
        )
    for field, expected in (
        ("draws", 10000),
        ("seed", 20261018),
        ("minimum_usable_draws", 9900),
        ("minimum_common_rows", 30),
        ("minimum_common_blocks", 10),
    ):
        same(
            count(protocol["bootstrap"][field], "bootstrap setting"),
            expected,
            "frozen bootstrap setting",
        )
    same(
        number(protocol["bootstrap"]["interval"], "interval level"),
        0.95,
        "frozen interval level",
    )
    secondary = protocol["secondary_endpoints"]
    same(
        count(secondary["n_inputs_per_context"], "secondary setting"),
        87,
        "frozen secondary setting",
    )
    same(secondary["Kuo2020"], ["arti", "dmsC", "fepB"], "frozen context roster")
    for field, expected in (
        ("minimum_coverage", 0.95),
        ("minimum_rank_gain", 0.05),
        ("minimum_interval_lower_exclusive", 0.0),
    ):
        same(
            number(protocol["advancement"][field], "gate threshold"),
            expected,
            "frozen gate threshold",
        )
    same(
        count(
            protocol["advancement"]["lost_baseline_successes_allowed"], "lost allowance"
        ),
        0,
        "frozen lost allowance",
    )

    for field in ("complete_collection_required", "software_resource_gates_required"):
        same(protocol["advancement"][field], True, "frozen gate requirement")


def reconcile(protocol, freeze, aggregate, review):
    protocol_numbers(protocol)
    keys(
        aggregate,
        (
            "schema_version",
            "panel_consumed",
            "collection_complete",
            "artifacts_unchanged",
            "primary",
            "descriptive_against_primary_reference",
            "descriptive_coding_gc_strata",
            "Kuo2020_secondary",
            "facilitated_cambray_evaluated",
            "calibration_fitted",
            "outliers_removed",
            "scope",
            "identities",
            "evaluator_sha256",
            "metric_code_sha256",
            "publication_context",
        ),
        "aggregate",
    )
    same(aggregate["schema_version"], "rbs-wave4-aggregate-1", "aggregate schema")
    for field, expected in (
        ("panel_consumed", True),
        ("calibration_fitted", False),
        ("outliers_removed", False),
        ("facilitated_cambray_evaluated", False),
    ):
        same(aggregate[field], expected, field)
    for field in ("collection_complete", "artifacts_unchanged"):
        require(type(aggregate[field]) is bool, f"{field}: expected boolean")
    configs = freeze["configurations"]
    require(
        type(configs) is list and len(configs) == len(ROSTER), "configuration roster"
    )
    same({c["id"]: c["kind"] for c in configs}, ROSTER, "configuration roster")
    primary = aggregate["primary"]
    keys(
        primary,
        ("endpoint", "models", "contrast", "comparison", "advancement"),
        "primary",
    )
    contrast = primary["contrast"]
    same(contrast, freeze["primary"], "primary contrast")
    keys(contrast, ("reference", "contender", "mode"), "contrast")
    require(
        contrast["reference"] in ROSTER
        and contrast["contender"] in ROSTER
        and contrast["reference"] != contrast["contender"],
        "contrast roster",
    )
    expected = protocol["primary_endpoint"]
    models(primary["models"], expected["n_inputs"], expected["n_observed"])
    left, right = (primary["models"][contrast[k]] for k in ("reference", "contender"))
    comparison(primary["comparison"], left, right, protocol)
    descriptive = aggregate["descriptive_against_primary_reference"]
    keys(
        descriptive,
        set(ROSTER) - {contrast["reference"], contrast["contender"]},
        "descriptive roster",
    )
    for name, value in descriptive.items():
        comparison(value, left, primary["models"][name], protocol)
    strata = aggregate["descriptive_coding_gc_strata"]
    keys(strata, ("low", "middle", "high"), "GC strata")
    for group in strata.values():
        models(group["models"])
        point_group(group, contrast)
    for name, row in primary["models"].items():
        parts = [group["models"][name] for group in strata.values()]
        for field in SUMMARY_KEYS[:4]:
            same(
                sum(part[field] for part in parts), row[field], f"GC partition {field}"
            )
        for field in ("status_counts", "failure_reasons"):
            combined = {}
            for part in parts:
                for label, n in part[field].items():
                    combined[label] = combined.get(label, 0) + n
            same(combined, row[field], f"GC partition {field}")
        same(
            sum(part["runtime_seconds"]["n_executed"] for part in parts),
            row["runtime_seconds"]["n_executed"],
            "GC partition executions",
        )
        close(
            sum(part["runtime_seconds"]["sum"] for part in parts),
            row["runtime_seconds"]["sum"],
            "GC partition runtime sum",
        )
    secondary = aggregate["Kuo2020_secondary"]
    keys(secondary, protocol["secondary_endpoints"]["Kuo2020"], "secondary roster")
    for group in secondary.values():
        models(group["models"], protocol["secondary_endpoints"]["n_inputs_per_context"])
        point_group(group, contrast, True)
    for name in ROSTER:
        same(
            sum(g["models"][name]["n_observed"] for g in secondary.values()),
            freeze["panels"]["Kuo2020"]["observed"],
            "secondary observations",
        )
    per_config = (
        expected["n_inputs"]
        + len(secondary) * protocol["secondary_endpoints"]["n_inputs_per_context"]
    )
    for field, total in (
        ("scheduled_jobs", len(ROSTER) * per_config),
        ("controls", 2 * per_config),
        ("external_jobs", 9 * per_config),
    ):
        same(count(freeze[field], field), total, field)
    same(
        freeze["panels"]["Cambray2018"]["inputs"], expected["n_inputs"], "frozen inputs"
    )
    same(
        freeze["panels"]["Cambray2018"]["observed"],
        expected["n_observed"],
        "frozen observations",
    )
    same(
        freeze["panels"]["Cambray2018"]["seed_blocks"],
        expected["n_blocks"],
        "frozen blocks",
    )
    same(
        freeze["panels"]["Kuo2020"]["inputs"],
        per_config - expected["n_inputs"],
        "frozen secondary inputs",
    )
    same(freeze["panels"]["Kuo2020"]["contexts"], len(secondary), "frozen contexts")
    require(
        type(freeze["software_resource_gates"]["complete"]) is bool,
        "software gate: expected boolean",
    )
    if aggregate["collection_complete"]:
        require(
            all(
                row["status_counts"].get("not_run", 0) == 0
                for panel in (primary, *secondary.values())
                for row in panel["models"].values()
            ),
            "complete collection contains not_run",
        )
    decision = gate(
        primary["comparison"],
        right,
        protocol,
        aggregate["collection_complete"] and aggregate["artifacts_unchanged"],
        freeze["software_resource_gates"]["complete"],
    )
    same(primary["advancement"], decision, "advancement")
    audit = review["independent_recomputation"]
    keys(
        audit,
        (
            "exact_fields_matched",
            "floating_fields_matched",
            "maximum_absolute_float_difference",
            "jobs_audited",
            "primary_draws",
            "primary_usable_draws",
            "primary_undefined_draws",
            "advance",
        ),
        "review audit",
    )
    for field in ("exact_fields_matched", "floating_fields_matched"):
        count(audit[field], "reported-only review fields")
    require(
        number(
            audit["maximum_absolute_float_difference"],
            "reported-only review difference",
        )
        >= 0,
        "review difference: negative",
    )
    same(
        count(audit["jobs_audited"], "jobs audited"),
        freeze["scheduled_jobs"],
        "jobs audited",
    )
    for field, compared in (
        ("primary_draws", "requested_draws"),
        ("primary_usable_draws", "usable_draws"),
        ("primary_undefined_draws", "undefined_draws"),
    ):
        same(count(audit[field], field), primary["comparison"][compared], field)
    same(audit["advance"], decision["advance"], "review advance")


def check(root, manifest_path):
    """Return a deterministic JSON-compatible result or raise ReceiptError."""
    try:
        raw_manifest = read_regular(manifest_path)
        manifest = parse(raw_manifest)
        keys(
            manifest,
            (
                "schema_version",
                "scope",
                "candidate_commit",
                "artifacts",
                "metadata_contracts",
                "referenced_only",
            ),
            "manifest",
        )
        same(
            manifest["schema_version"],
            "rbs-wave4-public-receipt-manifest-1",
            "manifest schema",
        )
        same(manifest["scope"], SCOPE, "manifest scope")
        candidate = manifest["candidate_commit"]
        require(
            type(candidate) is str
            and len(candidate) == 40
            and all(c in "0123456789abcdef" for c in candidate),
            "candidate: invalid",
        )
        keys(manifest["artifacts"], INPUTS, "allowlist")
        raw = {p: read_regular(Path(root) / p) for p in INPUTS}
        hashes = {p: digest(data) for p, data in raw.items()}
        same(hashes, manifest["artifacts"], "input SHA-256")
        docs = {p: parse(raw[p]) for p in INPUTS if p != REPORT}
        protocol, freeze, aggregate, review = (
            docs[p] for p in (PROTOCOL, FREEZE, AGGREGATE, REVIEW)
        )
        for p in docs:
            require(type(docs[p]) is dict, "artifact: expected object")
        same(metadata(docs), manifest["metadata_contracts"], "trusted metadata")
        same(protocol["schema_version"], "rbs-wave4-protocol-1", "protocol schema")
        same(freeze["schema_version"], "rbs-wave4-public-freeze-1", "freeze schema")
        same(review["schema_version"], "rbs-wave4-review-1", "review schema")
        for value in (
            freeze["scientific_execution_commit"],
            freeze["software_resource_gates"]["scientific_commit"],
            review["scientific_A_candidate"],
        ):
            same(value, candidate, "candidate identity")
        same(
            freeze["identities"]["protocol_sha256"],
            hashes[PROTOCOL],
            "freeze protocol hash",
        )
        ids = aggregate["identities"]
        keys(
            ids,
            ("collection", "inputs", "outcomes", "protocol", "receipt", "split"),
            "aggregate identities",
        )
        for field, expected in (
            ("inputs", protocol["input_file_sha256"]),
            ("outcomes", protocol["private_outcomes_sha256"]),
            ("split", protocol["split_file_sha256"]),
            ("protocol", hashes[PROTOCOL]),
            ("receipt", freeze["collector_receipt_sha256"]),
        ):
            same(ids[field], expected, f"aggregate identity {field}")
        for field, source in (
            ("input_file_sha256", "input_file_sha256"),
            ("input_envelope_sha256", "input_envelope_sha256"),
            ("split_file_sha256", "split_file_sha256"),
            ("private_outcome_sha256", "private_outcomes_sha256"),
        ):
            same(freeze["identities"][field], protocol[source], "freeze input identity")
        for field, source in (
            ("evaluator_sha256", "benchmarks/rbs/wave4_evaluate.py"),
            ("metric_code_sha256", "benchmarks/rbs/wave4_metrics.py"),
        ):
            same(
                aggregate[field],
                freeze["benchmark_code_sha256"][source],
                "code reference agreement",
            )
        keys(
            review["artifacts"],
            (REPORT, AGGREGATE, "docs/validation/rbs-new-evaluation-data.md"),
            "review artifacts",
        )
        for path in (REPORT, AGGREGATE):
            same(review["artifacts"][path], hashes[path], "review public artifact hash")
        recovered = digest(original_bytes(aggregate))
        same(
            aggregate["publication_context"]["original_evaluator_aggregate_sha256"],
            recovered,
            "recovered aggregate hash",
        )
        same(
            review["private_original_aggregate_sha256"],
            recovered,
            "review original hash",
        )
        refs = inventory(docs)
        same(refs, manifest["referenced_only"], "reference inventory")
        reconcile(protocol, freeze, aggregate, review)
        return {
            "schema_version": "rbs-wave4-public-receipt-result-1",
            "status": "consistent",
            "scope": manifest["scope"],
            "candidate_commit": candidate,
            "manifest_sha256": digest(raw_manifest),
            "checked_bytes": hashes,
            "recovered_original_digest": recovered,
            "referenced_only": {"status": "not_checked", "artifacts": refs},
            "review_numerical_agreement": "reported_only",
        }
    except OSError as exc:
        raise ReceiptError(f"input I/O failure ({exc.errno})") from exc
    except (
        KeyError,
        TypeError,
        OverflowError,
        RecursionError,
        NotImplementedError,
    ) as exc:
        raise ReceiptError("unsupported schema/type") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = check(args.root, args.manifest)
    except ReceiptError as exc:
        print(
            canonical(
                {
                    "schema_version": "rbs-wave4-public-receipt-result-1",
                    "status": "failed",
                    "error": str(exc),
                }
            ).decode(),
            end="",
        )
        return 1
    print(canonical(result).decode(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
