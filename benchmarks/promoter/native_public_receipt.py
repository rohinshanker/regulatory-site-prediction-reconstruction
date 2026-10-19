"""Public Wave 5 receipt consistency; no prediction or private artifact access."""

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

REPORT = "docs/validation/promoter-wave5-results.md"
FREEZE = "benchmarks/promoter/wave5-native-evaluation-freeze.json"
ACK = "benchmarks/promoter/wave5-collection-ack.json"
AGGREGATE = "benchmarks/promoter/wave5-native-aggregates.json"
INPUTS = (REPORT, FREEZE, ACK, AGGREGATE)
MAX_BYTES = 2_000_000
SCOPE = {
    "check": "public_receipt_consistency",
    "cohort": "consumed",
    "endpoint": "positive_TSS_localization",
    "independent_biological_recomputation": False,
    "markdown_semantics_checked": False,
    "release_or_calibration_approval": False,
}
LABEL_COUNTS = (
    "n_labels",
    "n_in_window",
    "n_out_of_window",
    "n_in_complete_query",
    "n_label_candidate_scored",
)
STATUSES = ("failed", "no_candidate", "not_run", "ok", "unsupported")
RUNTIME_STATUSES = (*STATUSES, "execution_failed", "invalid_input", "setup_failed")
RANK_KEYS = (
    "n_ranked",
    "n_tied_with_other_candidates",
    "rank_sum_optimistic",
    "rank_sum_midrank",
    "rank_sum_pessimistic",
    "mean_optimistic",
    "mean_midrank",
    "mean_pessimistic",
    "median_midrank",
    "mean_ranked_window_size",
)


class ReceiptError(ValueError):
    """An input is unavailable, malformed, untrusted or inconsistent."""


def require(condition, message):
    if not condition:
        raise ReceiptError(message)


def canonical(value):
    """Canonical public settings serialization, including its trailing LF."""
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode()


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


def fraction(value, numerator, denominator, where):
    if denominator == 0:
        require(value is None, f"{where}: zero denominator requires null")
    else:
        require(0 <= numerator <= denominator, f"{where}: numerator out of range")
        require(
            math.isclose(
                number(value, where),
                numerator / denominator,
                rel_tol=1e-12,
                abs_tol=1e-15,
            ),
            f"{where}: fraction/denominator mismatch",
        )


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "JSON: duplicate key")
        result[key] = value
    return result


def _constant(value):
    raise ReceiptError("JSON: non-finite constant")


def parse(data):
    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        # Also catches numeric overflow such as 1e999 and excessive nesting.
        canonical(value)
        _finite(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ReceiptError(
            "JSON: malformed, duplicate, non-finite or too deep"
        ) from exc


def _finite(value):
    if isinstance(value, dict):
        for child in value.values():
            _finite(child)
    elif isinstance(value, list):
        for child in value:
            _finite(child)
    elif type(value) is float:
        require(math.isfinite(value), "JSON: non-finite number")


def read_regular(path):
    """Open each component without following symlinks, then bound regular bytes.

    dir_fd and O_NOFOLLOW prevent both parent and final-component symlink races.
    No referenced artifact names ever reach this function.
    """
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


def references(value, pointer=()):
    """Inventory structural hash fields, with their locations, never paths to open."""
    result = []
    if type(value) is dict:
        for key, child in sorted(value.items()):
            location = (*pointer, key)
            if key.endswith("sha256") and type(child) is str:
                require(
                    len(child) == 64 and all(c in "0123456789abcdef" for c in child),
                    "reference: invalid SHA-256",
                )
                result.append({"location": list(location), "sha256": child})
            elif key.endswith("sha256") and type(child) is dict:
                for name, sha in sorted(child.items()):
                    require(
                        type(sha) is str
                        and len(sha) == 64
                        and all(c in "0123456789abcdef" for c in sha),
                        "reference: invalid SHA-256 map",
                    )
                    result.append({"location": [*location, name], "sha256": sha})
            else:
                result.extend(references(child, location))
    elif type(value) is list:
        for i, child in enumerate(value):
            result.extend(references(child, (*pointer, i)))
    return result


def status_counts(value, roster, total, where):
    keys(value, roster, where)
    require(
        sum(count(v, where) for v in value.values()) == total,
        f"{where}: status total mismatch",
    )


def roster(rows, expected, fields, where):
    require(type(rows) is list, f"{where}: expected endpoint list")
    actual = []
    for row in rows:
        require(type(row) is dict, f"{where}: expected endpoint object")
        actual.append(tuple(row.get(f) for f in fields))
    same(actual, expected, f"{where}: endpoint roster")


def ranks(value, n, where):
    keys(value, RANK_KEYS, where)
    same(count(value["n_ranked"], where), n, where)
    require(
        count(value["n_tied_with_other_candidates"], where) <= n, f"{where}: tied count"
    )
    for side in ("optimistic", "pessimistic"):
        count(value[f"rank_sum_{side}"], where)
    sums = [
        number(value[f"rank_sum_{s}"], where)
        for s in ("optimistic", "midrank", "pessimistic")
    ]
    require(0 <= sums[0] <= sums[1] <= sums[2], f"{where}: rank ordering")
    require(math.isclose(sums[1], (sums[0] + sums[2]) / 2), f"{where}: rank midpoint")
    for label, total in zip(
        ("optimistic", "midrank", "pessimistic"), sums, strict=True
    ):
        if n:
            require(
                math.isclose(number(value[f"mean_{label}"], where), total / n),
                f"{where}: rank mean",
            )
        else:
            same(value[f"mean_{label}"], None, where)
            same(total, 0, where)
    for label in ("median_midrank", "mean_ranked_window_size"):
        if n:
            require(1 <= number(value[label], where), f"{where}: rank/window bound")
        else:
            same(value[label], None, where)
    if n:
        require(
            n <= sums[0] and sums[2] <= n * value["mean_ranked_window_size"],
            f"{where}: rank sum bound",
        )


def endpoints(value, denominators, maximum, settings, where):
    recovery = value["recovery"]
    expected = [(k, t) for k in settings["top_k"] for t in settings["tolerances_nt"]]
    roster(recovery, expected, ("top_k", "tolerance_nt"), where)
    for row in recovery:
        keys(row, ("top_k", "tolerance_nt", "matched", *denominators), where)
        matched = count(row["matched"], where)
        require(matched <= maximum, f"{where}: recovery exceeds eligible labels")
        for field, denominator in denominators.items():
            fraction(row[field], matched, denominator, where)
    bounds = value["exact_rank_tie_bounds"]
    roster(bounds, [(k,) for k in settings["top_k"]], ("top_k",), where)
    for row in bounds:
        keys(
            row,
            (
                "top_k",
                "optimistic_rank_within_k",
                "pessimistic_rank_within_k",
                *(
                    f"{side}_{field}"
                    for side in ("optimistic", "pessimistic")
                    for field in denominators
                ),
            ),
            where,
        )
        optimistic = count(row["optimistic_rank_within_k"], where)
        pessimistic = count(row["pessimistic_rank_within_k"], where)
        require(pessimistic <= optimistic <= maximum, f"{where}: tie bounds")
        for side, numerator in (
            ("optimistic", optimistic),
            ("pessimistic", pessimistic),
        ):
            for field, denominator in denominators.items():
                fraction(row[f"{side}_{field}"], numerator, denominator, where)
        exact = next(
            r["matched"]
            for r in recovery
            if r["top_k"] == row["top_k"] and r["tolerance_nt"] == 0
        )
        require(pessimistic <= exact <= optimistic, f"{where}: exact recovery/ties")
    for k, t in expected:
        matched = next(
            r["matched"] for r in recovery if (r["top_k"], r["tolerance_nt"]) == (k, t)
        )
        require(
            all(
                r["matched"] <= matched
                for r in recovery
                if r["top_k"] <= k and r["tolerance_nt"] <= t
            ),
            f"{where}: recovery monotonicity",
        )


def summary(value, settings, where):
    keys(
        value,
        (
            *LABEL_COUNTS,
            "conditional_rank",
            "conditional_successful_positions",
            "recovery",
            "exact_rank_tie_bounds",
        ),
        where,
    )
    for field in LABEL_COUNTS:
        count(value[field], where)
    n, inside, outside, complete, scored = (value[k] for k in LABEL_COUNTS)
    require(
        n == inside + outside and complete <= scored <= inside,
        f"{where}: label partition",
    )
    ranks(value["conditional_rank"], complete, where)
    endpoints(
        value,
        {"fraction_of_all_labels": n, "fraction_of_in_window_labels": inside},
        complete,
        settings,
        where,
    )
    conditional = value["conditional_successful_positions"]
    keys(
        conditional,
        ("conditional_rank", "recovery", "exact_rank_tie_bounds", "scope"),
        where,
    )
    require(type(conditional["scope"]) is str, f"{where}: conditional scope")
    ranks(conditional["conditional_rank"], scored, where)
    endpoints(
        conditional, {"fraction_of_scored_labels": scored}, scored, settings, where
    )
    if scored == complete:
        same(conditional["conditional_rank"], value["conditional_rank"], where)
        same(
            [r["matched"] for r in conditional["recovery"]],
            [r["matched"] for r in value["recovery"]],
            where,
        )


def partitions(overall, groups, where):
    for field in LABEL_COUNTS:
        same(sum(v[field] for v in groups.values()), overall[field], where)
    for conditional in (False, True):
        rows = [overall, *groups.values()]
        if conditional:
            rows = [r["conditional_successful_positions"] for r in rows]
        first, *rest = rows
        for field in (
            "n_ranked",
            "n_tied_with_other_candidates",
            "rank_sum_optimistic",
            "rank_sum_midrank",
            "rank_sum_pessimistic",
        ):
            same(
                sum(r["conditional_rank"][field] for r in rest),
                first["conditional_rank"][field],
                where,
            )
        for field in ("recovery", "exact_rank_tie_bounds"):
            numerators = (
                ("matched",)
                if field == "recovery"
                else ("optimistic_rank_within_k", "pessimistic_rank_within_k")
            )
            for i, row in enumerate(first[field]):
                for numerator in numerators:
                    same(
                        sum(g[field][i][numerator] for g in rest), row[numerator], where
                    )


def uncertainty(value, metrics, freeze, hashes, where):
    keys(
        value,
        (
            "denominators",
            "endpoints",
            "inputs",
            "n_groups",
            "python",
            "schema_version",
            "scope",
            "settings",
            "settings_sha256",
            "tool_sha256",
        ),
        where,
    )
    same(value["schema_version"], "promoter-native-uncertainty-1", where)
    same(value["settings"], freeze["uncertainty_settings"], f"{where}: settings")
    same(value["settings_sha256"], digest(canonical(value["settings"])), where)
    same(
        value["tool_sha256"],
        freeze["tool_and_protocol_sha256"]["benchmarks/promoter/native_uncertainty.py"],
        where,
    )
    same(
        value["inputs"],
        {
            "metrics_document_sha256": hashes["metrics_sha256"],
            "metrics_inputs": metrics["inputs"],
            "metrics_settings_sha256": digest(canonical(metrics["settings"])),
            "metrics_tool_sha256": metrics["tool_sha256"],
        },
        f"{where}: input references",
    )
    same(count(value["n_groups"], where), metrics["n_groups"], where)
    keys(value["python"], ("implementation", "version"), where)
    require(
        all(type(v) is str for v in value["python"].values())
        and type(value["scope"]) is str,
        f"{where}: metadata types",
    )
    denominators = {
        "all_labels": metrics["overall"]["n_labels"],
        "in_window_labels": metrics["overall"]["n_in_window"],
    }
    keys(value["denominators"], denominators, where)
    for name, n in denominators.items():
        d = value["denominators"][name]
        keys(
            d,
            ("n_eligible_groups", "n_labels", "n_zero_denominator_groups", "status"),
            where,
        )
        same(count(d["n_labels"], where), n, where)
        eligible = count(d["n_eligible_groups"], where)
        require(eligible <= n, f"{where}: eligible groups")
        same(
            eligible + count(d["n_zero_denominator_groups"], where),
            metrics["n_groups"],
            where,
        )
        same(d["status"], "interval", where)
        require(
            eligible >= value["settings"]["min_eligible_groups"],
            f"{where}: insufficient groups",
        )
    expected = [
        (d, k, t)
        for d in denominators
        for k in metrics["settings"]["top_k"]
        for t in metrics["settings"]["tolerances_nt"]
    ]
    roster(
        value["endpoints"], expected, ("denominator", "top_k", "tolerance_nt"), where
    )
    for row in value["endpoints"]:
        keys(
            row,
            (
                "denominator",
                "denominator_labels",
                "interval",
                "matched",
                "n_defined_resamples",
                "n_eligible_groups",
                "n_resamples",
                "n_undefined_resamples",
                "point",
                "status",
                "tolerance_nt",
                "top_k",
            ),
            where,
        )
        name = row["denominator"]
        d = value["denominators"][name]
        for field in (
            "denominator_labels",
            "matched",
            "n_defined_resamples",
            "n_eligible_groups",
            "n_resamples",
            "n_undefined_resamples",
        ):
            count(row[field], where)
        same(row["denominator_labels"], denominators[name], where)
        same(row["n_eligible_groups"], d["n_eligible_groups"], where)
        same(row["n_resamples"], value["settings"]["resamples"], where)
        same(
            row["n_defined_resamples"] + row["n_undefined_resamples"],
            row["n_resamples"],
            where,
        )
        require(row["n_defined_resamples"] > 0, f"{where}: no defined resamples")
        same(row["status"], "interval", where)
        recovery = next(
            r
            for r in metrics["overall"]["recovery"]
            if (r["top_k"], r["tolerance_nt"]) == (row["top_k"], row["tolerance_nt"])
        )
        same(row["matched"], recovery["matched"], where)
        fraction(row["point"], row["matched"], denominators[name], where)
        keys(row["interval"], ("level", "lower", "upper"), where)
        same(row["interval"]["level"], 0.95, where)
        require(
            0
            <= number(row["interval"]["lower"], where)
            <= number(row["interval"]["upper"], where)
            <= 1,
            f"{where}: interval bounds",
        )


def reconcile(freeze, ack, aggregate):
    """Reconcile public arithmetic and repeated references without outcome joins."""
    totals = ack["totals"]
    keys(totals, ("n_bases", "n_batches", "n_requests", "n_sites"), "totals")
    for v in totals.values():
        count(v, "totals")
    same(aggregate["collection"]["totals"], totals, "collection totals")
    collection = aggregate["collection"]
    keys(
        collection,
        (
            "adapter_counts",
            "duration_seconds",
            "stage_seconds",
            "stop_reason",
            "totals",
            "validation_failure_present",
        ),
        "collection",
    )
    same(collection["stage_seconds"], ack["execution"]["stage_seconds"], "stage")
    require(
        0
        <= number(collection["duration_seconds"], "duration")
        <= number(collection["stage_seconds"], "stage"),
        "collection: duration",
    )
    same(collection["stop_reason"], None, "collection stop")
    same(collection["validation_failure_present"], False, "collection validation")
    adapter = collection["adapter_counts"]
    keys(
        adapter,
        (
            "batch_status",
            "candidate_status",
            "n_complete_requests",
            "n_incomplete_ok_requests",
            "n_non_ok_requests_with_scored_candidates",
            "n_partial_state_sites",
            "n_tied_selected_sites",
            "n_unattempted_sites",
            "request_status",
            "runtime_status",
            "selected_score_status",
            "site_reason",
        ),
        "adapter",
    )
    for field in (
        "n_complete_requests",
        "n_incomplete_ok_requests",
        "n_non_ok_requests_with_scored_candidates",
        "n_partial_state_sites",
        "n_tied_selected_sites",
        "n_unattempted_sites",
    ):
        require(
            count(adapter[field], field)
            <= totals["n_requests" if "requests" in field else "n_sites"],
            f"{field}: bound",
        )
    status_counts(
        adapter["batch_status"],
        ("completed", "execution_failed", "not_run", "setup_failed"),
        totals["n_batches"],
        "batches",
    )
    for field, roster_, total in (
        ("candidate_status", STATUSES, totals["n_sites"]),
        ("request_status", STATUSES, totals["n_requests"]),
        ("runtime_status", RUNTIME_STATUSES, totals["n_requests"]),
        (
            "selected_score_status",
            ("ok", "overflow", "underflow"),
            adapter["candidate_status"]["ok"],
        ),
    ):
        status_counts(adapter[field], roster_, total, field)
    keys(
        adapter["site_reason"],
        ("deadline_exceeded", "insufficient_context", "nonfinite_arithmetic"),
        "site reasons",
    )
    for v in adapter["site_reason"].values():
        require(count(v, "site reasons") <= totals["n_sites"], "site reason bound")
    require(
        adapter["n_complete_requests"] + adapter["n_incomplete_ok_requests"]
        == adapter["request_status"]["ok"],
        "complete request partition",
    )
    keys(aggregate["results"], ("constant-control", "native"), "results")
    keys(aggregate["artifact_hashes"], aggregate["results"], "artifact hashes")
    for name, metrics in aggregate["results"].items():
        keys(
            metrics,
            (
                "coverage",
                "inputs",
                "n_groups",
                "overall",
                "settings",
                "subgroups",
                "tool_sha256",
                "uncertainty",
            ),
            name,
        )
        hashes = aggregate["artifact_hashes"][name]
        keys(hashes, ("metrics_sha256", "scores_sha256", "uncertainty_sha256"), name)
        same(metrics["settings"], freeze["metric_settings"], f"{name}: metric settings")
        same(
            metrics["tool_sha256"],
            freeze["tool_and_protocol_sha256"]["benchmarks/promoter/native_metrics.py"],
            f"{name}: metric tool",
        )
        same(
            metrics["inputs"],
            {
                "groups_sha256": freeze["native_groups_sha256"],
                "labels_sha256": freeze["native_labels_sha256"],
                "query_document_sha256": freeze["native_queries_sha256"],
                "scores_sha256": hashes["scores_sha256"],
            },
            f"{name}: metric inputs",
        )
        count(metrics["n_groups"], name)
        c = metrics["coverage"]
        keys(
            c,
            (
                "candidate_status_all_requests",
                "candidate_status_in_ok_requests",
                "n_candidates",
                "n_complete_queries",
                "n_incomplete_ok_queries",
                "n_non_ok_queries_with_scored_candidates",
                "n_queries",
                "n_queries_with_labels",
                "n_queries_with_labels_ok",
                "request_status",
                "runtime_status",
                "score_schema",
            ),
            name,
        )
        same(c["score_schema"], "promoter-native-scores-2", name)
        for field in (k for k in c if k.startswith("n_")):
            count(c[field], name)
        for field, expected in (
            ("n_candidates", totals["n_sites"]),
            ("n_queries", totals["n_requests"]),
            ("n_complete_queries", adapter["n_complete_requests"]),
            ("n_incomplete_ok_queries", adapter["n_incomplete_ok_requests"]),
            (
                "n_non_ok_queries_with_scored_candidates",
                adapter["n_non_ok_requests_with_scored_candidates"],
            ),
            ("candidate_status_all_requests", adapter["candidate_status"]),
            ("request_status", adapter["request_status"]),
            ("runtime_status", adapter["runtime_status"]),
        ):
            same(c[field], expected, f"{name}: coverage {field}")
        require(
            c["n_queries_with_labels_ok"]
            <= c["n_queries_with_labels"]
            <= c["n_queries"]
            and c["n_queries_with_labels_ok"] <= c["request_status"]["ok"],
            f"{name}: labelled query bound",
        )
        keys(c["candidate_status_in_ok_requests"], STATUSES, name)
        for status, v in c["candidate_status_in_ok_requests"].items():
            require(
                count(v, name) <= c["candidate_status_all_requests"][status],
                f"{name}: scored status bound",
            )
        if c["request_status"]["ok"] == c["n_queries"]:
            same(
                c["candidate_status_in_ok_requests"],
                c["candidate_status_all_requests"],
                name,
            )
        summary(metrics["overall"], metrics["settings"], name)
        sub = metrics["subgroups"]
        keys(
            sub,
            (
                "labels_with_multiple_source_categories",
                "replicons",
                "scope",
                "source_categories",
            ),
            name,
        )
        require(
            count(sub["labels_with_multiple_source_categories"], name)
            <= metrics["overall"]["n_labels"]
            and type(sub["scope"]) is str,
            f"{name}: subgroup metadata",
        )
        keys(
            sub["replicons"], ("NZ_CP006471.1", "NZ_CP006472.1", "NZ_CP006473.1"), name
        )
        keys(
            sub["source_categories"],
            ("aTSS", "gTSS", "iTSS", "nTSS", "unclassified"),
            name,
        )
        for group in ("replicons", "source_categories"):
            for label, value in sub[group].items():
                summary(value, metrics["settings"], f"{name}/{group}/{label}")
                require(
                    all(value[k] <= metrics["overall"][k] for k in LABEL_COUNTS),
                    f"{name}: subgroup bound",
                )
        # Source-category memberships may overlap: only replicons partition labels.
        partitions(metrics["overall"], sub["replicons"], f"{name}: replicon partition")
        uncertainty(metrics["uncertainty"], metrics, freeze, hashes, name)
    for field in LABEL_COUNTS:
        same(
            aggregate["results"]["native"]["overall"][field],
            aggregate["results"]["constant-control"]["overall"][field],
            "shared labels",
        )
    same(
        aggregate["results"]["native"]["n_groups"],
        aggregate["results"]["constant-control"]["n_groups"],
        "shared groups",
    )
    native = aggregate["results"]["native"]
    control = aggregate["results"]["constant-control"]
    same(
        native["uncertainty"]["denominators"],
        control["uncertainty"]["denominators"],
        "shared denominator groups",
    )
    for group in ("replicons", "source_categories"):
        for label, value in native["subgroups"][group].items():
            for field in LABEL_COUNTS:
                same(
                    value[field],
                    control["subgroups"][group][label][field],
                    "shared subgroup labels",
                )
    for field in ("n_queries_with_labels", "n_queries_with_labels_ok"):
        same(
            native["coverage"][field], control["coverage"][field], "shared query labels"
        )


def check(root, manifest_path):
    """Check four fixed paths against an explicitly chosen trusted manifest.

    Raises ReceiptError on validation or I/O failure; never writes any file.
    """
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
            manifest["schema_version"], "promoter-public-receipt-manifest-1", "manifest"
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
        keys(manifest["metadata_contracts"], (FREEZE, ACK), "metadata contracts")
        keys(
            manifest["referenced_only"], (FREEZE, ACK, AGGREGATE), "reference inventory"
        )
        raw = {p: read_regular(Path(root) / p) for p in INPUTS}
        hashes = {p: digest(data) for p, data in raw.items()}
        same(hashes, manifest["artifacts"], "input SHA-256")
        docs = {p: parse(raw[p]) for p in (FREEZE, ACK, AGGREGATE)}
        freeze, ack, aggregate = (docs[p] for p in (FREEZE, ACK, AGGREGATE))
        for path, schema in (
            (FREEZE, "promoter-native-evaluation-freeze-1"),
            (ACK, "promoter-native-protocol-acknowledgement-1"),
            (AGGREGATE, "promoter-native-aggregate-report-1"),
        ):
            require(type(docs[path]) is dict, f"{path}: expected object")
            same(docs[path].get("schema_version"), schema, f"{path}: schema")
            same(docs[path].get("candidate_commit"), candidate, f"{path}: candidate")
        for path in (FREEZE, ACK):
            # Trusted stage metadata is explicit, never inferred from report prose.
            metadata = {
                k: v for k, v in docs[path].items() if k != "evaluation_freeze_sha256"
            }
            same(metadata, manifest["metadata_contracts"][path], f"{path}: metadata")
        keys(
            aggregate,
            (
                "artifact_hashes",
                "candidate_commit",
                "collection",
                "collection_sha256",
                "evaluation_freeze_sha256",
                "execution_receipt_sha256",
                "journal_sha256",
                "protocol_acknowledgement_sha256",
                "results",
                "schema_version",
                "scope",
            ),
            "aggregate",
        )
        require(type(aggregate["scope"]) is str, "aggregate scope type")
        same(ack["evaluation_freeze_sha256"], hashes[FREEZE], "ack freeze hash")
        same(
            aggregate["evaluation_freeze_sha256"],
            hashes[FREEZE],
            "aggregate freeze hash",
        )
        same(
            aggregate["protocol_acknowledgement_sha256"],
            hashes[ACK],
            "aggregate ack hash",
        )
        inventories = {}
        for path, value in docs.items():
            inventory = references(value)
            # Public links are verified bytes; remaining references are never read.
            public_locations = {
                ("evaluation_freeze_sha256",),
                ("protocol_acknowledgement_sha256",),
            }
            inventories[path] = [
                r for r in inventory if tuple(r["location"]) not in public_locations
            ]
        same(inventories, manifest["referenced_only"], "reference inventory")
        reconcile(freeze, ack, aggregate)
        return {
            "schema_version": "promoter-public-receipt-result-1",
            "status": "consistent",
            "scope": manifest["scope"],
            "candidate_commit": candidate,
            "manifest_sha256": digest(raw_manifest),
            "checked_bytes": hashes,
            "referenced_only": {"status": "not_checked", "artifacts": inventories},
        }
    except OSError as exc:
        raise ReceiptError(f"input I/O failure ({exc.errno})") from exc
    except (
        KeyError,
        TypeError,
        OverflowError,
        RecursionError,
        StopIteration,
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
        result = {
            "schema_version": "promoter-public-receipt-result-1",
            "status": "failed",
            "error": str(exc),
        }
        print(canonical(result).decode(), end="")
        return 1
    print(canonical(result).decode(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
