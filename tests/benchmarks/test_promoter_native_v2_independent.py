"""Independent synthetic cardinality check; no native inputs or runtime import."""

import random
import unittest

from benchmarks.promoter import native_metrics as m
from tests.benchmarks.test_promoter_native_metrics import documents


def maximum_matches(labels, selected, tol):
    # Exhaustive bipartite assignment; independent of evaluator's greedy matcher.
    if not labels:
        return 0
    point, *rest = labels
    best = maximum_matches(rest, selected, tol)
    for index, candidate in enumerate(selected):
        if abs(point - candidate) <= tol:
            best = max(
                best,
                1
                + maximum_matches(rest, selected[:index] + selected[index + 1 :], tol),
            )
    return best


def genomic(query, local):
    for segment in query["segments"]:
        a, b = segment["local"]
        if a <= local < b:
            x, y = segment["genomic"]
            return x + local - a if query["strand"] == "+" else y - 1 - (local - a)
    raise AssertionError(local)


class IndependentScoreV2Test(unittest.TestCase):
    def test_random_rosters_against_exhaustive_matching(self):
        rng = random.Random(20261018)
        queries, old_scores, labels, groups = documents()
        settings = m.metric_settings(True, top_k=(1, 2, 5, 10), tolerances_nt=(0, 1, 3))
        statuses = [
            "ok",
            "failed",
            "no_candidate",
            "unsupported",
            "not_run",
            "invalid_input",
            "setup_failed",
            "execution_failed",
        ]
        for iteration in range(1000):
            rows = []
            expected_primary = {
                (k, t): 0 for k in settings["top_k"] for t in settings["tolerances_nt"]
            }
            expected_conditional = expected_primary.copy()
            n_scored = n_complete = 0
            for qi, query in enumerate(queries["queries"]):
                local = list(range(*query["candidate_local_range"]))
                runtime = rng.choice(statuses)
                status = (
                    "failed"
                    if runtime in ("invalid_input", "setup_failed", "execution_failed")
                    else runtime
                )
                if runtime == "ok":
                    states = [rng.choice(["ok", "ok", "no_candidate"]) for _ in local]
                    states[0] = "ok"
                elif runtime == "failed":
                    states = [
                        rng.choice(["ok", "no_candidate", "failed"]) for _ in local
                    ]
                    states[0] = "failed"
                else:
                    states = [status] * len(local)
                candidates = [
                    {
                        "local_index": p,
                        "status": s,
                        "score": rng.randrange(4) if s == "ok" else None,
                    }
                    for p, s in zip(local, states, strict=True)
                ]
                rows.append(
                    {
                        "request_id": f"r{qi}",
                        "query_id": query["query_id"],
                        "status": status,
                        "runtime_status": runtime,
                        "candidates": candidates,
                    }
                )
                scored = [c for c in candidates if c["status"] == "ok"]
                ranked = sorted(
                    scored,
                    key=lambda c: (
                        c["score"],
                        genomic(query, c["local_index"]),
                        c["local_index"],
                    ),
                )
                successful = {c["local_index"] for c in scored}
                positives = [
                    label["local_index"]
                    for label in labels["labels"]
                    if label["query_id"] == query["query_id"]
                    and label["local_index"] in successful
                ]
                n_scored += len(positives)
                complete = status == "ok" and len(scored) == len(candidates)
                if complete:
                    n_complete += len(positives)
                for k, t in expected_primary:
                    selected = [c["local_index"] for c in ranked[:k]]
                    matches = maximum_matches(positives, selected, t)
                    expected_conditional[k, t] += matches
                    if complete:
                        expected_primary[k, t] += matches
            scores = {
                "schema_version": m.SCORE_SCHEMA_V2,
                "query_document_sha256": old_scores["query_document_sha256"],
                "provenance": {"synthetic": True},
                "results": rows,
            }
            result = m.evaluate(queries, scores, labels, groups, settings)["overall"]
            self.assertEqual(result["n_label_candidate_scored"], n_scored, iteration)
            self.assertEqual(result["n_in_complete_query"], n_complete, iteration)
            for target, expected in (
                (result["recovery"], expected_primary),
                (
                    result["conditional_successful_positions"]["recovery"],
                    expected_conditional,
                ),
            ):
                for row in target:
                    self.assertEqual(
                        row["matched"],
                        expected[row["top_k"], row["tolerance_nt"]],
                        (iteration, row),
                    )
