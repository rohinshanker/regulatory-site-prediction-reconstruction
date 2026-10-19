"""Positive-only positional recovery for frozen genome-grid Promoter queries.

Ranks are within each declared query window. Unlabelled points are never
negatives, so no precision, PR-AUC or FDR is reported. No runtime import.
"""

import argparse
import bisect
import json
import statistics
import sys
from pathlib import Path

from benchmarks.promoter.native_inputs import (
    LABEL_SCHEMA,
    MAX_QUERY_DOCUMENT_BYTES,
    QUERY_SCHEMA,
    STRANDS,
    candidate_index,
    canonical_bytes,
    checked_hash,
    document_sha256,
    local_to_genomic,
    read_bounded,
    strict_json,
    write_exclusive,
)
from benchmarks.rbs.datasets import digest
from benchmarks.rbs.metrics import finite_number

SCORE_SCHEMA = "promoter-native-scores-1"
SCORE_SCHEMA_V2 = "promoter-native-scores-2"
GROUP_SCHEMA = "promoter-native-groups-1"
METRIC_SCHEMA = "promoter-native-metrics-1"
STATUSES = ("ok", "failed", "not_run", "unsupported", "no_candidate")
# v2 retains the raw runtime/collection status beside its request status.
RUNTIME_STATUS_TO_REQUEST = {
    "ok": "ok",
    "no_candidate": "no_candidate",
    "unsupported": "unsupported",
    "invalid_input": "failed",
    "failed": "failed",
    "setup_failed": "failed",
    "execution_failed": "failed",
    "not_run": "not_run",
}
V2_KEYS = ("schema_version", "query_document_sha256", "provenance", "results")
V2_ROW_KEYS = ("request_id", "query_id", "status", "runtime_status", "candidates")
DEFAULT_TOP_K = (1, 5, 10)
DEFAULT_TOLERANCES = (0, 3)
SOURCE_CATEGORIES = ("gTSS", "aTSS", "iTSS", "nTSS", "unclassified")
MAX_SETTING_VALUES = 8
MAX_TOP_K = 1000
MAX_TOLERANCE = 100
MAX_SCORE_BYTES = 512 * 1024 * 1024
MAX_LABEL_BYTES = 128 * 1024 * 1024
MAX_QUERIES = 200_000
MAX_CANDIDATES = 10_000_000
MAX_LABELS = 500_000
TIE_RULE = "score, then genomic point ascending, then local index ascending"


def tool_sha256():
    """Identity of this exact evaluator implementation."""
    return digest(Path(__file__).read_bytes())


def _int_set(values, lower, upper, name):
    values = list(values)
    if (
        not 0 < len(values) <= MAX_SETTING_VALUES
        or any(type(v) is not int or not lower <= v <= upper for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError(f"{name} needs 1..{MAX_SETTING_VALUES} unique integers")
    return sorted(values)


def metric_settings(
    lower_is_better, top_k=DEFAULT_TOP_K, tolerances_nt=DEFAULT_TOLERANCES
):
    """Validated predeclared metric settings; score direction has no default."""
    if type(lower_is_better) is not bool:
        raise ValueError("lower_is_better must be explicitly true or false")
    return {
        "lower_is_better": lower_is_better,
        "top_k": _int_set(top_k, 1, MAX_TOP_K, "top_k"),
        "tolerances_nt": _int_set(tolerances_nt, 0, MAX_TOLERANCE, "tolerances_nt"),
        "tie_rule": TIE_RULE,
        "matching": "one-to-one maximum-cardinality within tolerance, per query",
    }


def max_matching(labels, predictions, tolerance):
    """Maximum one-to-one label/prediction matching on a line.

    labels: (local index, label id); predictions: local indices. Each label's
    acceptable positions form an equal-width interval, so assigning labels in
    interval order to the leftmost free acceptable prediction is optimal and
    deterministic. Returns matched label ids.
    """
    free = sorted(predictions)
    matched = []
    for position, label_id in sorted(labels):
        slot = bisect.bisect_left(free, position - tolerance)
        if slot < len(free) and free[slot] <= position + tolerance:
            matched.append(label_id)
            del free[slot]
    return matched


def _query_universe(queries):
    if not isinstance(queries, dict) or queries.get("schema_version") != QUERY_SCHEMA:
        raise ValueError("Query document schema must be " + QUERY_SCHEMA)
    rows = queries["queries"]
    if not isinstance(rows, list) or len(rows) > MAX_QUERIES:
        raise ValueError(f"Queries must be a list of at most {MAX_QUERIES}")
    lengths = {key: genome["length"] for key, genome in queries["genomes"].items()}
    universe = {}
    for query in rows:
        lower, upper = query["candidate_local_range"]
        if query["query_id"] in universe or not 0 <= lower <= upper:
            raise ValueError("Duplicate query identity or invalid candidate range")
        if query["genome_id"] not in lengths or query["strand"] not in STRANDS:
            raise ValueError(
                f"Query lacks a declared genome/strand: {query['query_id']}"
            )
        universe[query["query_id"]] = query
    if (
        sum(b - a for a, b in (q["candidate_local_range"] for q in rows))
        > MAX_CANDIDATES
    ):
        raise ValueError(f"Candidate universe exceeds {MAX_CANDIDATES}")
    return universe, candidate_index(rows), lengths


def _labels(labels, query_sha256, index, lengths):
    if labels.get("schema_version") != LABEL_SCHEMA:
        raise ValueError("Label document schema must be " + LABEL_SCHEMA)
    if labels.get("query_document_sha256") != query_sha256:
        raise ValueError("Labels are bound to a different query document")
    rows = labels["labels"]
    if not isinstance(rows, list) or len(rows) > MAX_LABELS:
        raise ValueError(f"Labels must be a list of at most {MAX_LABELS}")
    result = {}
    for label in rows:
        identity = label["label_id"]
        genome, strand, point = (
            label[k] for k in ("genome_id", "strand", "tss_zero_based")
        )
        if not isinstance(identity, str) or not identity or identity in result:
            raise ValueError("Invalid or duplicate label identity")
        if (
            genome not in lengths
            or strand not in STRANDS
            or type(point) is not int
            or not 0 <= point < lengths[genome]
        ):
            raise ValueError(f"Label lacks a declared genome/strand/point: {identity}")
        query_id, local = index.get((genome, strand, point), (None, None))
        if (label["query_id"], label["local_index"]) != (query_id, local):
            raise ValueError(f"Label window membership disagrees: {identity}")
        result[identity] = (query_id, local)
    return result


def _groups(groups, labels_sha256, label_ids):
    if (
        groups.get("schema_version") != GROUP_SCHEMA
        or groups.get("labels_document_sha256") != labels_sha256
    ):
        raise ValueError("Group document schema or label binding mismatch")
    mapping = groups["groups"]
    if (
        not isinstance(mapping, dict)
        or set(mapping) != set(label_ids)
        or any(not isinstance(g, str) or not g for g in mapping.values())
    ):
        raise ValueError("Every label needs exactly one supplied nonempty group")
    return mapping


def _roster_v2(status, runtime_status, states):
    """Whether a full v2 candidate roster agrees with its request status.

    ok: at least one ok, the rest no_candidate. failed: ok/no_candidate/failed
    with a failed candidate in any nonempty roster, and only failed candidates
    when nothing usable ran (invalid_input/setup_failed/execution_failed).
    no_candidate, unsupported and
    not_run: every candidate carries the request status.
    """
    present = set(states)
    if status == "ok":
        return "ok" in present and present <= {"ok", "no_candidate"}
    if status == "failed":
        allowed = (
            {"ok", "no_candidate", "failed"}
            if runtime_status == "failed"
            else {"failed"}
        )
        return present <= allowed and (not states or "failed" in present)
    return present <= {status}


def _scores_v2(scores, query_sha256, universe):
    if set(scores) != set(V2_KEYS) or not isinstance(scores["provenance"], dict):
        raise ValueError("Score document v2 needs exactly: " + ", ".join(V2_KEYS))
    if scores["query_document_sha256"] != query_sha256:
        raise ValueError("Scores are bound to a different query document")
    rows = scores["results"]
    if not isinstance(rows, list) or len(rows) != len(universe):
        raise ValueError("Every query needs exactly one explicit score result")
    results, requests = {}, set()
    for row, (query_id, query) in zip(rows, universe.items(), strict=True):
        if not isinstance(row, dict) or set(row) != set(V2_ROW_KEYS):
            raise ValueError("Score result v2 needs exactly " + "/".join(V2_ROW_KEYS))
        request, status, runtime = (
            row["request_id"],
            row["status"],
            row["runtime_status"],
        )
        if not isinstance(request, str) or not request or request in requests:
            raise ValueError("Invalid or duplicate request identity")
        if row["query_id"] != query_id:
            raise ValueError("Score results must list every query once, in order")
        if (
            not isinstance(runtime, str)
            or RUNTIME_STATUS_TO_REQUEST.get(runtime) != status
        ):
            raise ValueError(f"Runtime/request status disagree: {runtime!r}/{status!r}")
        requests.add(request)
        lower, upper = query["candidate_local_range"]
        listed = row["candidates"]
        if not isinstance(listed, list) or len(listed) != upper - lower:
            raise ValueError(
                f"Candidates differ from the declared universe: {query_id}"
            )
        candidates = {}
        for local, candidate in zip(range(lower, upper), listed, strict=True):
            if not isinstance(candidate, dict) or set(candidate) != {
                "local_index",
                "status",
                "score",
            }:
                raise ValueError("Candidate needs exactly local_index/status/score")
            state, score = candidate["status"], candidate["score"]
            if type(candidate["local_index"]) is not int or (
                candidate["local_index"] != local
            ):
                raise ValueError(
                    f"Candidates must list every local index in order: {query_id}"
                )
            if state not in STATUSES or (
                not finite_number(score) if state == "ok" else score is not None
            ):
                raise ValueError("ok candidates need finite scores; others null")
            candidates[local] = (state, score)
        if not _roster_v2(status, runtime, [s for s, _ in candidates.values()]):
            raise ValueError(
                f"Candidate statuses disagree with request {status}: {query_id}"
            )
        results[query_id] = (status, candidates)
    return results


def _scores(scores, query_sha256, universe):
    if isinstance(scores, dict) and scores.get("schema_version") == SCORE_SCHEMA_V2:
        return _scores_v2(scores, query_sha256, universe)
    if scores.get("schema_version") != SCORE_SCHEMA:
        raise ValueError(
            f"Score document schema must be {SCORE_SCHEMA} or {SCORE_SCHEMA_V2}"
        )
    if scores.get("query_document_sha256") != query_sha256:
        raise ValueError("Scores are bound to a different query document")
    results, requests = {}, set()
    for row in scores["results"]:
        if set(row) != {"request_id", "query_id", "status", "candidates"}:
            raise ValueError(
                "Score result needs exactly request_id/query_id/status/candidates"
            )
        request, query_id = row["request_id"], row["query_id"]
        if not isinstance(request, str) or not request or request in requests:
            raise ValueError("Invalid or duplicate request identity")
        if query_id not in universe or query_id in results:
            raise ValueError("Unknown or repeated query in score results")
        if row["status"] not in STATUSES:
            raise ValueError(f"Unknown request status: {row['status']!r}")
        requests.add(request)
        lower, upper = universe[query_id]["candidate_local_range"]
        expected = range(lower, upper) if row["status"] == "ok" else range(0)
        candidates = {}
        for candidate in row["candidates"]:
            if set(candidate) != {"local_index", "status", "score"}:
                raise ValueError("Candidate needs exactly local_index/status/score")
            local, status, score = (
                candidate[k] for k in ("local_index", "status", "score")
            )
            if type(local) is not int or local in candidates:
                raise ValueError("Invalid or duplicate candidate local index")
            if status not in STATUSES or (
                not finite_number(score) if status == "ok" else score is not None
            ):
                raise ValueError("ok candidates need finite scores; others null")
            candidates[local] = (status, score)
        if set(candidates) != set(expected):
            raise ValueError(
                f"Candidates differ from the declared universe: {query_id}"
            )
        results[query_id] = (row["status"], candidates)
    if set(results) != set(universe):
        raise ValueError("Every query needs exactly one explicit score result")
    return results


def _fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def _mean(values):
    return statistics.fmean(values) if values else None


def _median(values):
    return statistics.median(values) if values else None


def _recovery(ids, hits, pairs, denominators):
    rows = []
    for k, tolerance in pairs:
        matched = len(hits[(k, tolerance)] & ids)
        row = {"top_k": k, "tolerance_nt": tolerance, "matched": matched}
        for name, value in denominators.items():
            row[f"fraction_of_{name}"] = _fraction(matched, value)
        rows.append(row)
    return rows


def _tie_bounds(held, top_k, denominators):
    rows = []
    for k in top_k:
        row = {
            "top_k": k,
            "optimistic_rank_within_k": sum(r[0] <= k for r in held),
            "pessimistic_rank_within_k": sum(r[2] <= k for r in held),
        }
        for bound in ("optimistic", "pessimistic"):
            for name, value in denominators.items():
                row[f"{bound}_fraction_of_{name}"] = _fraction(
                    row[f"{bound}_rank_within_k"], value
                )
        rows.append(row)
    return rows


def _rank_summary(held):
    return {
        "n_ranked": len(held),
        "n_tied_with_other_candidates": sum(r[2] > r[0] for r in held),
        "rank_sum_optimistic": sum(r[0] for r in held),
        "rank_sum_midrank": sum(r[1] for r in held),
        "rank_sum_pessimistic": sum(r[2] for r in held),
        "mean_optimistic": _mean([r[0] for r in held]),
        "mean_midrank": _mean([r[1] for r in held]),
        "mean_pessimistic": _mean([r[2] for r in held]),
        "median_midrank": _median([r[1] for r in held]),
        "mean_ranked_window_size": _mean([r[3] for r in held]),
    }


def evaluate(queries, scores, labels, groups, settings):
    """Evaluate supplied scores against supplied positive labels.

    The all-case endpoint keeps every label in its denominator and credits
    only complete queries (ok request, every candidate ok): out-of-window
    labels, failed requests and partially scored queries count as unrecovered.
    `conditional_successful_positions` separately ranks labels whose own
    candidate scored, including partially scored queries and, for
    `promoter-native-scores-2`, scored candidates of failed requests. Group
    counts are sufficient statistics for an external group-level uncertainty
    tool. Scores-1 output is unchanged; scores-2 adds coverage fields.
    """
    query_sha = document_sha256(queries)
    universe, index, lengths = _query_universe(queries)
    membership = _labels(labels, query_sha, index, lengths)
    group_of = _groups(groups, document_sha256(labels), membership)
    results = _scores(scores, query_sha, universe)
    sign = 1 if settings["lower_is_better"] else -1
    by_query = {}
    for label_id, (query_id, local) in membership.items():
        if query_id is not None:
            by_query.setdefault(query_id, []).append((local, label_id))
    pairs = [(k, t) for k in settings["top_k"] for t in settings["tolerances_nt"]]
    matched = {pair: set() for pair in pairs}
    conditional = {pair: set() for pair in pairs}
    ranks, scored, complete = {}, set(), set()
    n_complete = n_incomplete = n_non_ok_scored = 0
    request_status, candidate_status, candidate_status_all = (
        {s: 0 for s in STATUSES},
        {s: 0 for s in STATUSES},
        {s: 0 for s in STATUSES},
    )
    for query_id, query in universe.items():
        status, candidates = results[query_id]
        request_status[status] += 1
        states = [state for state, _ in candidates.values()]
        for state in states:
            candidate_status_all[state] += 1
            if status == "ok":
                candidate_status[state] += 1
        is_complete = status == "ok" and all(state == "ok" for state in states)
        if status == "ok":
            n_complete += is_complete
            n_incomplete += not is_complete
        elif "ok" in states:
            n_non_ok_scored += 1
        if "ok" not in states:
            continue
        positives = [
            (local, label_id)
            for local, label_id in by_query.get(query_id, [])
            if candidates[local][0] == "ok"
        ]
        if not positives:
            continue
        ranked = sorted(
            (
                sign * score,
                local_to_genomic(query["strand"], query["segments"], local),
                local,
            )
            for local, (state, score) in candidates.items()
            if state == "ok"
        )
        values = [row[0] for row in ranked]
        for local, label_id in positives:
            score = candidates[local][1]
            scored.add(label_id)
            if is_complete:
                complete.add(label_id)
            better = bisect.bisect_left(values, sign * score)
            tied = bisect.bisect_right(values, sign * score) - better
            ranks[label_id] = (
                better + 1,
                better + (tied + 1) / 2,
                better + tied,
                len(values),
            )
        for k, tolerance in pairs:
            top = [row[2] for row in ranked[:k]]
            hits = max_matching(positives, top, tolerance)
            conditional[(k, tolerance)].update(hits)
            if is_complete:
                matched[(k, tolerance)].update(hits)

    def summary(ids):
        ids = set(ids)
        in_window = sum(membership[i][0] is not None for i in ids)
        primary = {"all_labels": len(ids), "in_window_labels": in_window}
        successful = {"scored_labels": len(ids & scored)}
        return {
            "n_labels": len(ids),
            "n_in_window": in_window,
            "n_out_of_window": len(ids) - in_window,
            "n_label_candidate_scored": len(ids & scored),
            "n_in_complete_query": len(ids & complete),
            "recovery": _recovery(ids, matched, pairs, primary),
            "exact_rank_tie_bounds": _tie_bounds(
                [ranks[i] for i in sorted(ids & complete)], settings["top_k"], primary
            ),
            "conditional_rank": _rank_summary(
                [ranks[i] for i in sorted(ids & complete)]
            ),
            "conditional_successful_positions": {
                "scope": (
                    "labels whose own candidate scored, including partially "
                    "scored queries; not the all-case endpoint"
                ),
                "recovery": _recovery(ids, conditional, pairs, successful),
                "exact_rank_tie_bounds": _tie_bounds(
                    [ranks[i] for i in sorted(ids & scored)],
                    settings["top_k"],
                    successful,
                ),
                "conditional_rank": _rank_summary(
                    [ranks[i] for i in sorted(ids & scored)]
                ),
            },
        }

    group_ids = {}
    for label_id, group in group_of.items():
        group_ids.setdefault(group, []).append(label_id)
    replicon_ids = {genome: [] for genome in sorted(lengths)}
    category_ids = {category: [] for category in SOURCE_CATEGORIES}
    multiple_categories = 0
    for label in labels["labels"]:
        identity = label["label_id"]
        replicon_ids[label["genome_id"]].append(identity)
        rows = label.get("source_rows", [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Label source_rows must be a list of objects")
        categories = {
            category if category in SOURCE_CATEGORIES else "unclassified"
            for category in (row.get("tss_type") for row in rows)
        } or {"unclassified"}
        multiple_categories += len(categories) > 1
        for category in categories:
            category_ids[category].append(identity)
    coverage = {
        "n_queries": len(universe),
        "request_status": request_status,
        "n_complete_queries": n_complete,
        "n_incomplete_ok_queries": n_incomplete,
        "n_candidates": sum(
            b - a for a, b in (q["candidate_local_range"] for q in universe.values())
        ),
        "candidate_status_in_ok_requests": candidate_status,
        "n_queries_with_labels": len(by_query),
        "n_queries_with_labels_ok": sum(results[q][0] == "ok" for q in by_query),
    }
    if scores["schema_version"] == SCORE_SCHEMA_V2:
        runtime_status = dict.fromkeys(RUNTIME_STATUS_TO_REQUEST, 0)
        for row in scores["results"]:
            runtime_status[row["runtime_status"]] += 1
        coverage.update(
            score_schema=SCORE_SCHEMA_V2,
            runtime_status=runtime_status,
            candidate_status_all_requests=candidate_status_all,
            n_non_ok_queries_with_scored_candidates=n_non_ok_scored,
        )
    return {
        "schema_version": METRIC_SCHEMA,
        "scope": (
            "positive TSS recovery within declared genome-grid windows; not "
            "genome-wide precision, PR-AUC or FDR; no inferred negatives"
        ),
        "settings": settings,
        "settings_sha256": document_sha256(settings),
        "inputs": {
            "query_document_sha256": query_sha,
            "scores_sha256": document_sha256(scores),
            "labels_sha256": document_sha256(labels),
            "groups_sha256": document_sha256(groups),
        },
        "tool_sha256": tool_sha256(),
        "coverage": coverage,
        "overall": summary(membership),
        "n_groups": len(group_ids),
        "groups": {g: summary(ids) for g, ids in sorted(group_ids.items())},
        "subgroups": {
            "scope": (
                "descriptive summaries of the same global one-to-one matches; "
                "source-category memberships may overlap; no subgroup intervals"
            ),
            "labels_with_multiple_source_categories": multiple_categories,
            "replicons": {g: summary(ids) for g, ids in replicon_ids.items()},
            "source_categories": {c: summary(ids) for c, ids in category_ids.items()},
        },
    }


def main(argv=None):
    """Evaluate exactly bound documents into a new 0600 metrics file."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("queries", "scores", "labels", "groups", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--direction", choices=("lower", "higher"), required=True)
    parser.add_argument("--top-k", type=int, nargs="+", default=list(DEFAULT_TOP_K))
    parser.add_argument(
        "--tolerance-nt", type=int, nargs="+", default=list(DEFAULT_TOLERANCES)
    )
    parser.add_argument("--queries-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        settings = metric_settings(
            args.direction == "lower", args.top_k, args.tolerance_nt
        )
        raw = read_bounded(args.queries, MAX_QUERY_DOCUMENT_BYTES)
        if digest(raw) != checked_hash(args.queries_sha256):
            raise ValueError("Query document file SHA-256 mismatch")
        documents = [
            strict_json(raw),
            strict_json(read_bounded(args.scores, MAX_SCORE_BYTES)),
            strict_json(read_bounded(args.labels, MAX_LABEL_BYTES)),
            strict_json(read_bounded(args.groups, MAX_LABEL_BYTES)),
        ]
        if canonical_bytes(documents[0]) != raw:
            raise ValueError("Query document is not canonical tool output")
        queries, scores, labels, groups = documents
        result = evaluate(queries, scores, labels, groups, settings)
        write_exclusive(args.output, result, 0o600)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"output_sha256": document_sha256(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
