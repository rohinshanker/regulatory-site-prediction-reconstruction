"""Hand-computed positional recovery, tie bounds and one-to-one matching."""

import contextlib
import io
import itertools
import json
import os
import random
import runpy
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from benchmarks.promoter import native_inputs as n
from benchmarks.promoter import native_metrics as m


def query(identity, strand, local_range, genomic):
    length = genomic[1] - genomic[0]
    return {
        "query_id": identity,
        "genome_id": "g",
        "strand": strand,
        "candidate_local_range": list(local_range),
        "segments": [{"local": [0, length], "genomic": list(genomic)}],
    }


def queries_document():
    # Q1 plus: local i -> 100 + i. Q2 minus: local i -> 209 - i. Q3 plus: 300 + i.
    return {
        "schema_version": n.QUERY_SCHEMA,
        "genomes": {"g": {"length": 1000}},
        "queries": [
            query("Q1", "+", (0, 10), (100, 110)),
            query("Q2", "-", (2, 8), (200, 210)),
            query("Q3", "+", (0, 4), (300, 304)),
        ],
    }


def label(identity, strand, point, query_id, local):
    return {
        "label_id": identity,
        "genome_id": "g",
        "strand": strand,
        "tss_zero_based": point,
        "query_id": query_id,
        "local_index": local,
    }


def labels_document(queries):
    return {
        "schema_version": n.LABEL_SCHEMA,
        "query_document_sha256": n.document_sha256(queries),
        "labels": [
            label("A", "+", 103, "Q1", 3),
            label("B", "+", 104, "Q1", 4),
            label("C", "-", 205, "Q2", 4),
            label("D", "+", 301, "Q3", 1),
            label("E", "+", 500, None, None),
            label("F", "+", 107, "Q1", 7),
        ],
    }


def groups_document(labels, mapping=None):
    return {
        "schema_version": m.GROUP_SCHEMA,
        "labels_document_sha256": n.document_sha256(labels),
        "groups": mapping
        or {
            "A": "grp1",
            "B": "grp1",
            "C": "grp2",
            "D": "grp3",
            "E": "grp3",
            "F": "grp3",
        },
    }


def candidates(scores):
    return [
        {
            "local_index": local,
            "status": "ok" if score is not None else "unsupported",
            "score": score,
        }
        for local, score in scores.items()
    ]


def scores_document(queries):
    q1 = {0: 5, 1: 1.0, 2: 3, 3: 2, 4: 2, 5: 0.5, 6: 9, 7: None, 8: 4, 9: 8}
    return {
        "schema_version": m.SCORE_SCHEMA,
        "query_document_sha256": n.document_sha256(queries),
        "results": [
            {
                "request_id": "r1",
                "query_id": "Q1",
                "status": "ok",
                "candidates": candidates(q1),
            },
            {
                "request_id": "r2",
                "query_id": "Q2",
                "status": "ok",
                "candidates": candidates({i: 1.0 for i in range(2, 8)}),
            },
            {
                "request_id": "r3",
                "query_id": "Q3",
                "status": "failed",
                "candidates": [],
            },
        ],
    }


def documents():
    queries = queries_document()
    labels = labels_document(queries)
    return queries, scores_document(queries), labels, groups_document(labels)


def keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def recovery(summary):
    return {(r["top_k"], r["tolerance_nt"]): r["matched"] for r in summary["recovery"]}


class SubgroupTest(unittest.TestCase):
    def test_shared_matches_and_overlapping_source_membership(self):
        queries, scores, labels, _ = documents()
        queries["genomes"]["empty"] = {"length": 100}
        query_hash = n.document_sha256(queries)
        labels["query_document_sha256"] = query_hash
        scores["query_document_sha256"] = query_hash
        scores["results"][0]["candidates"] = candidates(
            {i: -1 if i == 4 else 10 for i in range(10)}
        )
        source_types = {
            "A": ["gTSS", "gTSS"],
            "B": ["aTSS"],
            "C": ["iTSS"],
            "D": ["nTSS"],
            "E": ["gTSS", "not-a-source-class", None],
        }
        for row in labels["labels"]:
            row["source_rows"] = [
                {"tss_type": category}
                for category in source_types.get(row["label_id"], [])
            ]
        result = m.evaluate(
            queries,
            scores,
            labels,
            groups_document(labels),
            m.metric_settings(True, [1], [1]),
        )
        subgroups = result["subgroups"]
        self.assertEqual(subgroups["labels_with_multiple_source_categories"], 1)
        self.assertEqual(subgroups["replicons"]["g"], result["overall"])
        empty = subgroups["replicons"]["empty"]
        self.assertEqual(empty["n_labels"], 0)
        self.assertIsNone(empty["recovery"][0]["fraction_of_all_labels"])
        categories = subgroups["source_categories"]
        self.assertEqual(categories["gTSS"]["n_labels"], 2)
        self.assertEqual(categories["unclassified"]["n_labels"], 2)
        self.assertEqual(recovery(categories["gTSS"]), {(1, 1): 1})
        # A takes the one top prediction before B in the global matching.
        # Evaluating the aTSS subset alone would incorrectly give B a hit.
        self.assertEqual(recovery(categories["aTSS"]), {(1, 1): 0})
        self.assertEqual(recovery(result["overall"]), {(1, 1): 1})

    def test_source_rows_shape(self):
        for rows in (None, {}, ["not-an-object"]):
            with self.subTest(rows=rows):
                queries, scores, labels, _ = documents()
                labels["labels"][0]["source_rows"] = rows
                with self.assertRaisesRegex(ValueError, "source_rows"):
                    m.evaluate(
                        queries,
                        scores,
                        labels,
                        groups_document(labels),
                        m.metric_settings(True),
                    )


class SettingsTest(unittest.TestCase):
    def test_defaults_and_validation(self):
        settings = m.metric_settings(True)
        self.assertEqual(settings["top_k"], [1, 5, 10])
        self.assertEqual(settings["tolerances_nt"], [0, 3])
        self.assertEqual(m.metric_settings(False, (10, 1), (3,))["top_k"], [1, 10])
        for direction in (None, 1, "lower"):
            with self.assertRaisesRegex(ValueError, "explicitly"):
                m.metric_settings(direction)
        for top_k in (
            (),
            (0,),
            (1, 1),
            (True,),
            (1.0,),
            (m.MAX_TOP_K + 1,),
            range(1, 10),
        ):
            with self.assertRaisesRegex(ValueError, "top_k"):
                m.metric_settings(True, top_k)
        for tolerance in ((-1,), (m.MAX_TOLERANCE + 1,), (0, 0)):
            with self.assertRaisesRegex(ValueError, "tolerances_nt"):
                m.metric_settings(True, (1,), tolerance)


class MatchingTest(unittest.TestCase):
    def test_competing_labels_are_not_double_counted(self):
        self.assertEqual(m.max_matching([(3, "A"), (4, "B")], [5], 3), ["A"])
        self.assertEqual(m.max_matching([(3, "A"), (4, "B")], [5, 2], 3), ["A", "B"])
        # Greedy-by-score would pair A with 1 and strand B; maximum matching does not.
        self.assertEqual(m.max_matching([(0, "A"), (4, "B")], [1, 3], 3), ["A", "B"])
        self.assertEqual(m.max_matching([(0, "A")], [4], 3), [])
        self.assertEqual(m.max_matching([], [1], 3), [])

    def test_against_brute_force(self):
        generator = random.Random(20261018)
        for _ in range(400):
            labels = [
                (p, f"L{i}")
                for i, p in enumerate(
                    generator.sample(range(15), generator.randint(0, 5))
                )
            ]
            predictions = generator.sample(range(15), generator.randint(0, 5))
            tolerance = generator.randint(0, 3)
            best = 0
            for size in range(min(len(labels), len(predictions)), -1, -1):
                if any(
                    all(
                        abs(a[0] - b) <= tolerance
                        for a, b in zip(chosen, order, strict=True)
                    )
                    for chosen in itertools.combinations(labels, size)
                    for order in itertools.permutations(predictions, size)
                ):
                    best = size
                    break
            self.assertEqual(len(m.max_matching(labels, predictions, tolerance)), best)


def bounds(section):
    return {
        b["top_k"]: (b["optimistic_rank_within_k"], b["pessimistic_rank_within_k"])
        for b in section["exact_rank_tie_bounds"]
    }


def complete_documents():
    """Fixture with Q1 fully scored: local 7 (label F) gets score 7."""
    queries, scores, labels, groups = documents()
    scores["results"][0]["candidates"][7] = {
        "local_index": 7,
        "status": "ok",
        "score": 7,
    }
    return queries, scores, labels, groups


class EvaluateTest(unittest.TestCase):
    def test_incomplete_query_contributes_zero_all_case_recovery(self):
        result = m.evaluate(*documents(), m.metric_settings(True))
        overall = result["overall"]
        self.assertEqual(
            (overall["n_labels"], overall["n_in_window"], overall["n_out_of_window"]),
            (6, 5, 1),
        )
        self.assertEqual(
            (overall["n_label_candidate_scored"], overall["n_in_complete_query"]),
            (3, 1),
        )
        # Q1 has an unsupported candidate, so only complete Q2 (label C) counts.
        self.assertEqual(
            recovery(overall),
            {(1, 0): 0, (1, 3): 1, (5, 0): 1, (5, 3): 1, (10, 0): 1, (10, 3): 1},
        )
        row = next(
            r for r in overall["recovery"] if (r["top_k"], r["tolerance_nt"]) == (1, 3)
        )
        self.assertEqual(row["fraction_of_all_labels"], 1 / 6)
        self.assertEqual(row["fraction_of_in_window_labels"], 1 / 5)
        self.assertEqual(bounds(overall), {1: (1, 0), 5: (1, 0), 10: (1, 1)})
        self.assertEqual(
            overall["conditional_rank"],
            {
                "n_ranked": 1,
                "n_tied_with_other_candidates": 1,
                "rank_sum_optimistic": 1,
                "rank_sum_midrank": 3.5,
                "rank_sum_pessimistic": 6,
                "mean_optimistic": 1,
                "mean_midrank": 3.5,
                "mean_pessimistic": 6,
                "median_midrank": 3.5,
                "mean_ranked_window_size": 6,
            },
        )
        # Secondary summary: labels whose own candidate scored (A, B, C), with
        # Q1 ranked ascending l5, l1, l3, l4, l2, l8, l0, l9, l6; F is unscored.
        successful = overall["conditional_successful_positions"]
        self.assertEqual(
            recovery(successful),
            {(1, 0): 0, (1, 3): 2, (5, 0): 3, (5, 3): 3, (10, 0): 3, (10, 3): 3},
        )
        self.assertEqual(successful["recovery"][1]["fraction_of_scored_labels"], 2 / 3)
        self.assertEqual(bounds(successful), {1: (1, 0), 5: (3, 2), 10: (3, 3)})
        self.assertEqual(
            successful["exact_rank_tie_bounds"][1][
                "pessimistic_fraction_of_scored_labels"
            ],
            2 / 3,
        )
        rank = successful["conditional_rank"]
        self.assertEqual(
            (
                rank["rank_sum_optimistic"],
                rank["rank_sum_midrank"],
                rank["rank_sum_pessimistic"],
            ),
            (7, 10.5, 14),
        )
        self.assertEqual(
            (rank["mean_midrank"], rank["mean_ranked_window_size"]), (3.5, 8)
        )
        self.assertEqual(
            result["coverage"],
            {
                "n_queries": 3,
                "request_status": {
                    "ok": 2,
                    "failed": 1,
                    "not_run": 0,
                    "unsupported": 0,
                    "no_candidate": 0,
                },
                "n_complete_queries": 1,
                "n_incomplete_ok_queries": 1,
                "n_candidates": 20,
                "candidate_status_in_ok_requests": {
                    "ok": 15,
                    "failed": 0,
                    "not_run": 0,
                    "unsupported": 1,
                    "no_candidate": 0,
                },
                "n_queries_with_labels": 3,
                "n_queries_with_labels_ok": 2,
            },
        )
        groups = result["groups"]
        self.assertEqual(result["n_groups"], 3)
        self.assertEqual(set(recovery(groups["grp1"]).values()), {0})
        self.assertEqual(
            recovery(groups["grp1"]["conditional_successful_positions"]),
            {(1, 0): 0, (1, 3): 1, (5, 0): 2, (5, 3): 2, (10, 0): 2, (10, 3): 2},
        )
        self.assertEqual(
            recovery(groups["grp2"]),
            {(1, 0): 0, (1, 3): 1, (5, 0): 1, (5, 3): 1, (10, 0): 1, (10, 3): 1},
        )
        grp3 = groups["grp3"]
        self.assertEqual((grp3["n_labels"], grp3["n_in_window"]), (3, 2))
        self.assertEqual(set(recovery(grp3).values()), {0})
        self.assertEqual(grp3["conditional_rank"]["n_ranked"], 0)
        self.assertIsNone(grp3["conditional_rank"]["mean_midrank"])
        self.assertIsNone(grp3["conditional_rank"]["median_midrank"])
        self.assertIsNone(
            grp3["conditional_successful_positions"]["recovery"][0][
                "fraction_of_scored_labels"
            ]
        )
        self.assertFalse(
            {"precision", "pr_auc", "fdr", "negatives"} & set(keys(result)),
            "positive-only evaluator must not emit negative-dependent metrics",
        )

    def test_complete_query_competing_labels(self):
        result = m.evaluate(*complete_documents(), m.metric_settings(True))
        overall = result["overall"]
        # Q1 ascending: l5, l1, l3, l4, l2, l8, l0, l7, l9, l6; labels A3, B4, F7.
        # top1 {5} with +/-3 reaches A, B and F but recovers only one of them.
        self.assertEqual(
            recovery(overall),
            {(1, 0): 0, (1, 3): 2, (5, 0): 3, (5, 3): 4, (10, 0): 4, (10, 3): 4},
        )
        self.assertEqual(bounds(overall), {1: (1, 0), 5: (3, 2), 10: (4, 4)})
        rank = overall["conditional_rank"]
        self.assertEqual(
            (
                rank["n_ranked"],
                rank["n_tied_with_other_candidates"],
                rank["rank_sum_optimistic"],
                rank["rank_sum_midrank"],
                rank["rank_sum_pessimistic"],
                rank["median_midrank"],
                rank["mean_ranked_window_size"],
            ),
            (4, 3, 15, 18.5, 22, 3.5, 9),
        )
        self.assertEqual(result["coverage"]["n_complete_queries"], 2)
        self.assertEqual(
            recovery(result["groups"]["grp3"]),
            {(1, 0): 0, (1, 3): 0, (5, 0): 0, (5, 3): 1, (10, 0): 1, (10, 3): 1},
        )
        # With every ok query complete, both summaries match the same labels.
        self.assertEqual(
            recovery(overall), recovery(overall["conditional_successful_positions"])
        )

    def test_higher_is_better(self):
        result = m.evaluate(*complete_documents(), m.metric_settings(False))
        overall = result["overall"]
        # Q1 descending: l6, l9, l7, l0, l8, l2, l3, l4, l1, l5.
        rank = overall["conditional_rank"]
        self.assertEqual(rank["rank_sum_optimistic"], 7 + 7 + 3 + 1)
        self.assertEqual(rank["rank_sum_pessimistic"], 8 + 8 + 3 + 6)
        self.assertEqual(
            recovery(overall),
            {(1, 0): 0, (1, 3): 2, (5, 0): 2, (5, 3): 4, (10, 0): 4, (10, 3): 4},
        )

    def test_all_ties_order_by_genomic_point(self):
        queries, scores, labels, groups = documents()
        for row in scores["results"][0]["candidates"]:
            if row["status"] == "ok":
                row["score"] = 0
        result = m.evaluate(
            queries, scores, labels, groups, m.metric_settings(True, (1,), (0,))
        )
        # Genomic-first ties: Q2 ranks local 7 (point 202) first, Q1 local 0.
        self.assertEqual(recovery(result["overall"]), {(1, 0): 0})
        self.assertEqual(bounds(result["overall"]), {1: (1, 0)})
        successful = result["overall"]["conditional_successful_positions"]
        self.assertEqual(recovery(successful), {(1, 0): 0})
        self.assertEqual(bounds(successful), {1: (3, 0)})
        self.assertEqual(
            successful["conditional_rank"]["rank_sum_midrank"], 5 + 5 + 3.5
        )

    def test_no_success_and_empty(self):
        queries, scores, labels, groups = documents()
        for row in scores["results"]:
            row["status"], row["candidates"] = "not_run", []
        result = m.evaluate(queries, scores, labels, groups, m.metric_settings(True))
        overall = result["overall"]
        self.assertEqual(set(recovery(overall).values()), {0})
        self.assertEqual(overall["recovery"][0]["fraction_of_all_labels"], 0)
        self.assertIsNone(overall["conditional_rank"]["mean_optimistic"])
        self.assertIsNone(
            overall["conditional_successful_positions"]["recovery"][0][
                "fraction_of_scored_labels"
            ]
        )
        self.assertEqual(result["coverage"]["request_status"]["not_run"], 3)
        self.assertEqual(result["coverage"]["n_complete_queries"], 0)
        labels["labels"] = []
        groups = groups_document(labels, {})
        groups["groups"] = {}
        result = m.evaluate(queries, scores, labels, groups, m.metric_settings(True))
        overall = result["overall"]
        self.assertEqual((overall["n_labels"], result["n_groups"]), (0, 0))
        self.assertIsNone(overall["recovery"][0]["fraction_of_all_labels"])
        self.assertIsNone(overall["recovery"][0]["fraction_of_in_window_labels"])
        self.assertIsNone(
            overall["exact_rank_tie_bounds"][0]["optimistic_fraction_of_all_labels"]
        )

    def test_deterministic_identity(self):
        first = m.evaluate(*documents(), m.metric_settings(True))
        second = m.evaluate(*documents(), m.metric_settings(True))
        self.assertEqual(n.canonical_bytes(first), n.canonical_bytes(second))
        queries, scores, labels, groups = documents()
        self.assertEqual(
            first["inputs"],
            {
                "query_document_sha256": n.document_sha256(queries),
                "scores_sha256": n.document_sha256(scores),
                "labels_sha256": n.document_sha256(labels),
                "groups_sha256": n.document_sha256(groups),
            },
        )
        self.assertEqual(
            first["settings_sha256"], n.document_sha256(m.metric_settings(True))
        )
        self.assertEqual(first["tool_sha256"], m.tool_sha256())

    def test_real_builder_documents(self):
        sequence = "".join("ACGT"[(i * 5 + i // 7) % 4] for i in range(240))
        envelope = {
            "schema_version": n.ENVELOPE_SCHEMA,
            "genomes": {
                "g": {
                    "sequence": sequence,
                    "sequence_sha256": n.digest(sequence),
                    "accession": "a",
                    "assembly": "b",
                    "annotation": "c",
                    "topology": "circular",
                }
            },
            "records": [
                {"id": "x", "genome_id": "g", "strand": "-", "tss_zero_based": 0},
                {"id": "y", "genome_id": "g", "strand": "+", "tss_zero_based": 239},
            ],
        }
        raw = json.dumps(envelope).encode()
        digest = n.digest(raw)
        loaded = n.load_envelope(raw, digest)
        queries = n.build_queries(loaded, digest, n.grid_settings(80, 128, "metric"))
        labels = n.project_labels(loaded, digest, queries)
        groups = groups_document(labels, {"tss:g:+:239": "a", "tss:g:-:0": "b"})
        results = []
        for q in queries["queries"]:
            lower, upper = q["candidate_local_range"]
            results.append(
                {
                    "request_id": "req-" + q["query_id"],
                    "query_id": q["query_id"],
                    "status": "ok",
                    "candidates": [
                        {
                            "local_index": i,
                            "status": "ok",
                            "score": abs(
                                n.local_to_genomic(q["strand"], q["segments"], i)
                                - (0 if q["strand"] == "-" else 239)
                            ),
                        }
                        for i in range(lower, upper)
                    ],
                }
            )
        scores = {
            "schema_version": m.SCORE_SCHEMA,
            "query_document_sha256": n.document_sha256(queries),
            "results": results,
        }
        result = m.evaluate(queries, scores, labels, groups, m.metric_settings(True))
        self.assertEqual(recovery(result["overall"])[(1, 0)], 2)
        self.assertEqual(result["overall"]["conditional_rank"]["mean_pessimistic"], 1)


class RejectionTest(unittest.TestCase):
    def check(self, mutate, message):
        queries, scores, labels, groups = documents()
        mutate(queries, scores, labels, groups)
        with self.assertRaisesRegex(ValueError, message):
            m.evaluate(queries, scores, labels, groups, m.metric_settings(True))

    def test_query_universe(self):
        with self.assertRaisesRegex(ValueError, "Query document schema"):
            m.evaluate([], {}, {}, {}, m.metric_settings(True))
        self.check(
            lambda q, s, lab, g: q.update(schema_version="x"), "Query document schema"
        )
        self.check(lambda q, s, lab, g: q.update(queries={}), "list of at most")
        with mock.patch.object(m, "MAX_QUERIES", 2):
            self.check(lambda q, s, lab, g: None, "list of at most 2")
        with mock.patch.object(m, "MAX_CANDIDATES", 19):
            self.check(lambda q, s, lab, g: None, "exceeds 19")
        self.check(
            lambda q, s, lab, g: q["queries"][1].update(query_id="Q1"),
            "Duplicate query",
        )
        self.check(
            lambda q, s, lab, g: q["queries"][2].update(candidate_local_range=[3, 2]),
            "invalid candidate range",
        )
        self.check(
            lambda q, s, lab, g: q["queries"][2].update(candidate_local_range=[-1, 2]),
            "invalid candidate range",
        )
        for change in ({"genome_id": "h"}, {"strand": "."}):
            self.check(
                lambda q, s, lab, g, change=change: q["queries"][0].update(change),
                "declared genome/strand",
            )
        self.check(
            lambda q, s, lab, g: q["queries"][2].update(
                segments=[{"local": [0, 4], "genomic": [100, 104]}]
            ),
            "Overlapping",
        )

    def test_labels_and_groups(self):
        for change in (
            {"genome_id": "h"},
            {"strand": "."},
            {"tss_zero_based": 1000},
            {"tss_zero_based": -1},
            {"tss_zero_based": 500.0},
        ):
            self.check(
                lambda q, s, lab, g, change=change: lab["labels"][4].update(change),
                "declared genome/strand/point",
            )
        self.check(
            lambda q, s, lab, g: lab.update(schema_version="x"), "Label document schema"
        )
        self.check(
            lambda q, s, lab, g: lab.update(query_document_sha256="0" * 64),
            "different query",
        )
        self.check(lambda q, s, lab, g: lab.update(labels={}), "Labels must be a list")
        with mock.patch.object(m, "MAX_LABELS", 5):
            self.check(lambda q, s, lab, g: None, "at most 5")
        self.check(
            lambda q, s, lab, g: lab["labels"][1].update(label_id="A"),
            "duplicate label",
        )
        self.check(
            lambda q, s, lab, g: lab["labels"][1].update(label_id=""),
            "Invalid or duplicate label",
        )
        self.check(
            lambda q, s, lab, g: lab["labels"][0].update(local_index=4),
            "membership disagrees",
        )
        self.check(
            lambda q, s, lab, g: lab["labels"][4].update(query_id="Q1"),
            "membership disagrees",
        )
        self.check(lambda q, s, lab, g: g.update(schema_version="x"), "Group document")
        self.check(
            lambda q, s, lab, g: g.update(labels_document_sha256="0" * 64),
            "label binding",
        )
        self.check(lambda q, s, lab, g: g["groups"].pop("A"), "exactly one supplied")
        self.check(lambda q, s, lab, g: g.update(groups=[]), "exactly one supplied")
        self.check(
            lambda q, s, lab, g: g["groups"].update(A=""), "exactly one supplied"
        )
        self.check(lambda q, s, lab, g: g["groups"].update(A=1), "exactly one supplied")

    def test_scores(self):
        def result(s, index=0):
            return s["results"][index]

        def candidate(s, index=0):
            return result(s)["candidates"][index]

        self.check(
            lambda q, s, lab, g: s.update(schema_version="x"), "Score document schema"
        )
        self.check(
            lambda q, s, lab, g: s.update(query_document_sha256="0" * 64),
            "different query",
        )
        self.check(
            lambda q, s, lab, g: result(s).update(reason="x"), "exactly request_id"
        )
        self.check(
            lambda q, s, lab, g: result(s, 1).update(request_id="r1"),
            "duplicate request",
        )
        self.check(
            lambda q, s, lab, g: result(s).update(request_id=""), "duplicate request"
        )
        self.check(
            lambda q, s, lab, g: result(s).update(query_id="Q9"), "Unknown or repeated"
        )
        self.check(
            lambda q, s, lab, g: result(s, 1).update(query_id="Q1"),
            "Unknown or repeated",
        )
        self.check(
            lambda q, s, lab, g: result(s).update(status="timeout"),
            "Unknown request status",
        )
        self.check(
            lambda q, s, lab, g: candidate(s).update(extra=1), "exactly local_index"
        )
        self.check(
            lambda q, s, lab, g: candidate(s).update(local_index="0"), "local index"
        )
        self.check(
            lambda q, s, lab, g: candidate(s, 1).update(local_index=0),
            "duplicate candidate",
        )
        self.check(
            lambda q, s, lab, g: candidate(s).update(score=None), "finite scores"
        )
        self.check(
            lambda q, s, lab, g: candidate(s).update(score=True), "finite scores"
        )
        self.check(
            lambda q, s, lab, g: candidate(s).update(status="weird"), "finite scores"
        )
        self.check(
            lambda q, s, lab, g: candidate(s, 7).update(score=1.0), "finite scores"
        )
        self.check(
            lambda q, s, lab, g: result(s)["candidates"].pop(),
            "differ from the declared",
        )
        self.check(
            lambda q, s, lab, g: result(s, 2)["candidates"].append(
                {"local_index": 0, "status": "failed", "score": None}
            ),
            "differ from the declared",
        )
        self.check(lambda q, s, lab, g: s["results"].pop(), "exactly one explicit")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name)
        names = ("queries", "scores", "labels", "groups")
        for name, value in zip(names, documents(), strict=True):
            (self.path / f"{name}.json").write_bytes(n.canonical_bytes(value))
        self.query_sha = n.digest((self.path / "queries.json").read_bytes())

    def argv(self, output="metrics.json", sha=None, direction="lower"):
        return [
            *(
                str(self.path / f"{name}.json")
                for name in ("queries", "scores", "labels", "groups")
            ),
            str(self.path / output),
            "--direction",
            direction,
            "--queries-sha256",
            sha or self.query_sha,
        ]

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = m.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_success_and_no_overwrite(self):
        code, out, _ = self.run_main(
            self.argv() + ["--top-k", "1", "5", "--tolerance-nt", "3"]
        )
        self.assertEqual(code, 0)
        output = self.path / "metrics.json"
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
        raw = output.read_bytes()
        self.assertEqual(json.loads(out)["output_sha256"], n.digest(raw))
        document = json.loads(raw)
        self.assertEqual(document["settings"]["top_k"], [1, 5])
        self.assertEqual(recovery(document["overall"]), {(1, 3): 1, (5, 3): 1})
        code, out, err = self.run_main(self.argv())
        self.assertEqual((code, out), (1, ""))
        self.assertIn("error:", err)
        self.assertEqual(output.read_bytes(), raw)

    def test_failures(self):
        code, _, err = self.run_main(self.argv(sha="0" * 64))
        self.assertEqual(code, 1)
        self.assertIn("file SHA-256 mismatch", err)
        code, _, err = self.run_main(self.argv(sha="bad"))
        self.assertIn("lowercase", err)
        raw = json.dumps(
            json.loads((self.path / "queries.json").read_bytes()), indent=1
        ).encode()
        (self.path / "queries.json").write_bytes(raw)
        code, _, err = self.run_main(self.argv(sha=n.digest(raw)))
        self.assertEqual(code, 1)
        self.assertIn("not canonical", err)
        self.assertFalse((self.path / "metrics.json").exists())
        code, _, err = self.run_main(self.argv() + ["--top-k", "0"])
        self.assertIn("top_k", err)

    def test_module_entry_point(self):
        with (
            mock.patch.object(
                sys, "argv", ["native_metrics", *self.argv(sha="0" * 64)]
            ),
            contextlib.redirect_stderr(io.StringIO()),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module(
                    "benchmarks.promoter.native_metrics", run_name="__main__"
                )
        self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
