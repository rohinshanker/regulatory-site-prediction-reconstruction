"""Group-bootstrap intervals checked against hand values and a plain reference."""

import contextlib
import copy
import hashlib
import io
import json
import math
import os
import platform
import random
import runpy
import sys
import tempfile
import unittest
import warnings
from fractions import Fraction
from pathlib import Path
from unittest import mock

from benchmarks.promoter import native_groups as g
from benchmarks.promoter import native_inputs as n
from benchmarks.promoter import native_metrics as m
from benchmarks.promoter import native_uncertainty as u


def summary(n_labels, n_in_window, matched, pairs):
    return {
        "n_labels": n_labels,
        "n_in_window": n_in_window,
        "n_out_of_window": n_labels - n_in_window,
        "n_label_candidate_scored": n_in_window,
        "n_in_complete_query": n_in_window,
        "recovery": [
            {
                "top_k": k,
                "tolerance_nt": t,
                "matched": hits,
                "fraction_of_all_labels": hits / n_labels if n_labels else None,
                "fraction_of_in_window_labels": (
                    hits / n_in_window if n_in_window else None
                ),
            }
            for (k, t), hits in zip(pairs, matched, strict=True)
        ],
    }


def metrics_document(stats, top_k=(1,), tolerances=(0,)):
    """stats: list of (n_labels, n_in_window, [matched per endpoint])."""
    settings = m.metric_settings(True, top_k, tolerances)
    pairs = [(k, t) for k in settings["top_k"] for t in settings["tolerances_nt"]]
    groups = {
        f"grp{i:03d}": summary(a, b, hits, pairs)
        for i, (a, b, hits) in enumerate(stats)
    }
    totals = [sum(hits[i] for _, _, hits in stats) for i in range(len(pairs))]
    return {
        "schema_version": m.METRIC_SCHEMA,
        "settings": settings,
        "settings_sha256": n.document_sha256(settings),
        "inputs": {name: "a" * 64 for name in u.INPUT_HASH_FIELDS},
        "tool_sha256": "c" * 64,
        "overall": summary(
            sum(a for a, _, _ in stats), sum(b for _, b, _ in stats), totals, pairs
        ),
        "n_groups": len(groups),
        "groups": groups,
    }


def endpoint(result, denominator, k=1, tolerance=0):
    (row,) = [
        row
        for row in result["endpoints"]
        if (row["denominator"], row["top_k"], row["tolerance_nt"])
        == (denominator, k, tolerance)
    ]
    return row


def reference_percentile(values, quantile):
    position = (len(values) - 1) * Fraction(quantile)
    lower = math.floor(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + float(position - lower) * (values[upper] - values[lower])


def reference_bootstrap(stats, resamples, seed, endpoint_index, use_window):
    """Plain loops over draws, independent of the tool's column layout."""
    rng = random.Random(seed)
    values, undefined = [], 0
    for _ in range(resamples):
        drawn = rng.choices(range(len(stats)), k=len(stats))
        hits = sum(stats[i][2][endpoint_index] for i in drawn)
        den = sum(stats[i][1 if use_window else 0] for i in drawn)
        if den:
            values.append(hits / den)
        else:
            undefined += 1
    values.sort()
    return values, undefined


class PercentileTest(unittest.TestCase):
    def test_known_values(self):
        values = [10, 20, 30, 40, 50]
        self.assertEqual(u.percentile(values, Fraction(1, 40)), 11.0)
        self.assertEqual(u.percentile(values, Fraction(39, 40)), 49.0)
        self.assertEqual(u.percentile(values, Fraction(1, 2)), 30)
        self.assertEqual(u.percentile([7], Fraction(39, 40)), 7)
        self.assertEqual(u.percentile([1, 2], Fraction(1)), 2)
        big = list(range(10_000))
        self.assertAlmostEqual(u.percentile(big, Fraction(1, 40)), 249.975, 12)
        self.assertAlmostEqual(u.percentile(big, Fraction(39, 40)), 9749.025, 12)


class SummarizeTest(unittest.TestCase):
    def test_settings_are_pinned(self):
        settings = u.uncertainty_settings()
        self.assertEqual(settings["resamples"], 10_000)
        self.assertEqual(settings["seed"], 20261018)
        self.assertEqual(settings["quantiles"], ["1/40", "39/40"])
        self.assertEqual(settings["min_eligible_groups"], 20)

    def test_constant_all_zero_and_all_hit(self):
        for hits, expected in ((1, 0.5), (0, 0.0), (2, 1.0)):
            result = u.summarize(metrics_document([(2, 2, [hits])] * 25))
            for denominator in ("all_labels", "in_window_labels"):
                row = endpoint(result, denominator)
                self.assertEqual(row["point"], expected)
                self.assertEqual(row["status"], "interval")
                self.assertEqual(
                    row["interval"],
                    {"level": 0.95, "lower": expected, "upper": expected},
                )
                self.assertEqual(row["n_resamples"], 10_000)
                self.assertEqual(row["n_defined_resamples"], 10_000)
                self.assertEqual(row["n_eligible_groups"], 25)

    def test_all_zero_window_is_insufficient_not_zero(self):
        result = u.summarize(metrics_document([(3, 0, [0])] * 25))
        row = endpoint(result, "in_window_labels")
        self.assertIsNone(row["point"])
        self.assertIsNone(row["interval"])
        self.assertEqual(row["status"], "insufficient_group_count")
        self.assertEqual(row["denominator_labels"], 0)
        self.assertEqual(
            result["denominators"]["in_window_labels"],
            {
                "n_labels": 0,
                "n_eligible_groups": 0,
                "n_zero_denominator_groups": 25,
                "status": "insufficient_group_count",
            },
        )
        self.assertEqual(endpoint(result, "all_labels")["interval"]["upper"], 0.0)

    def test_fewer_than_twenty_groups(self):
        stats = [(1, 1, [i % 2]) for i in range(19)]
        with mock.patch.object(u, "bootstrap", side_effect=AssertionError):
            result = u.summarize(metrics_document(stats))
        for denominator in ("all_labels", "in_window_labels"):
            row = endpoint(result, denominator)
            self.assertEqual(row["status"], "insufficient_group_count")
            self.assertEqual((row["matched"], row["denominator_labels"]), (9, 19))
            self.assertEqual(row["point"], 9 / 19)
            self.assertIsNone(row["interval"])
            self.assertEqual(row["n_resamples"], 0)
        self.assertEqual(result["n_groups"], 19)

    def test_matches_plain_reference_with_zero_window_groups(self):
        rng = random.Random(5)
        stats = []
        for _ in range(20):
            window = rng.randrange(1, 4)
            stats.append(
                (
                    window + rng.randrange(2),
                    window,
                    [rng.randrange(window + 1) for _ in range(4)],
                )
            )
        stats += [(rng.randrange(1, 3), 0, [0, 0, 0, 0]) for _ in range(7)]
        document = metrics_document(stats, top_k=(1, 5), tolerances=(0, 3))
        with mock.patch.object(u, "RESAMPLES", 300):
            result = u.summarize(document)
        order = sorted(range(len(stats)), key=lambda i: f"grp{i:03d}")
        ordered = [stats[i] for i in order]
        self.assertEqual(
            result["denominators"]["in_window_labels"]["n_eligible_groups"], 20
        )
        self.assertEqual(
            result["denominators"]["in_window_labels"]["n_zero_denominator_groups"], 7
        )
        for index, (k, t) in enumerate([(1, 0), (1, 3), (5, 0), (5, 3)]):
            for denominator, use_window in (
                ("all_labels", False),
                ("in_window_labels", True),
            ):
                values, undefined = reference_bootstrap(
                    ordered, 300, 20261018, index, use_window
                )
                row = endpoint(result, denominator, k, t)
                self.assertEqual(row["n_undefined_resamples"], undefined)
                self.assertEqual(row["n_defined_resamples"], len(values))
                self.assertEqual(
                    row["interval"]["lower"],
                    reference_percentile(values, Fraction(1, 40)),
                )
                self.assertEqual(
                    row["interval"]["upper"],
                    reference_percentile(values, Fraction(39, 40)),
                )
                self.assertLessEqual(row["interval"]["lower"], row["interval"]["upper"])

    def test_seed_repeat_and_receipt(self):
        rng = random.Random(9)
        sizes = [rng.randrange(1, 10) for _ in range(30)]
        stats = [(a, a, [rng.randrange(a + 1)]) for a in sizes]
        document = metrics_document(stats)
        first, second = u.summarize(document), u.summarize(copy.deepcopy(document))
        self.assertEqual(n.canonical_bytes(first), n.canonical_bytes(second))
        interval = endpoint(first, "all_labels")["interval"]
        self.assertLess(interval["lower"], interval["upper"])
        with mock.patch.object(u, "SEED", 1):
            other = u.summarize(document)
        self.assertNotEqual(other["endpoints"], first["endpoints"])
        self.assertNotEqual(other["settings_sha256"], first["settings_sha256"])
        self.assertEqual(
            first["python"],
            {
                "implementation": platform.python_implementation(),
                "version": platform.python_version(),
            },
        )
        self.assertEqual(
            first["inputs"],
            {
                "metrics_document_sha256": n.document_sha256(document),
                "metrics_settings_sha256": document["settings_sha256"],
                "metrics_tool_sha256": "c" * 64,
                "metrics_inputs": document["inputs"],
            },
        )
        self.assertEqual(first["tool_sha256"], u.tool_sha256())
        self.assertEqual(
            first["tool_sha256"],
            hashlib.sha256(Path(u.__file__).read_bytes()).hexdigest(),
        )
        self.assertEqual(first["settings_sha256"], n.document_sha256(first["settings"]))
        text = json.dumps(first)
        self.assertNotIn("grp0", text)  # no per-group or per-label output

    def test_undefined_resamples_are_counted_not_zeroed(self):
        stats = [(1, 1, [1])] * 20 + [(1, 0, [0])]
        document = metrics_document(stats)
        zero_group = len(stats) - 1
        with (
            mock.patch.object(u, "RESAMPLES", 10),
            mock.patch.object(
                u, "_draw", side_effect=lambda rng, size: [zero_group] * size
            ),
        ):
            result = u.summarize(document)
        row = endpoint(result, "in_window_labels")
        self.assertEqual(row["n_undefined_resamples"], 10)
        self.assertEqual(row["n_defined_resamples"], 0)
        self.assertIsNone(row["interval"])
        self.assertEqual(row["status"], "no_defined_resamples")
        self.assertEqual(row["point"], 1.0)
        self.assertEqual(endpoint(result, "all_labels")["interval"]["upper"], 0.0)
        draws = iter([[zero_group] * 21, list(range(21))] * 5)
        with (
            mock.patch.object(u, "RESAMPLES", 10),
            mock.patch.object(u, "_draw", side_effect=lambda rng, size: next(draws)),
        ):
            result = u.summarize(document)
        row = endpoint(result, "in_window_labels")
        self.assertEqual(
            (row["n_undefined_resamples"], row["n_defined_resamples"]), (5, 5)
        )
        self.assertEqual(row["interval"]["lower"], 1.0)

    def test_draw_uses_documented_choices(self):
        self.assertEqual(
            u._draw(random.Random(3), 7), random.Random(3).choices(range(7), k=7)
        )

    def test_bootstrap_limits(self):
        settings = u.uncertainty_settings()
        with mock.patch.object(u, "MAX_RESAMPLED_GROUPS", 10_000 * 3 - 1):
            with self.assertRaisesRegex(ValueError, "declared limits"):
                u.bootstrap([[1, 1, 1]], 3, settings)
        with mock.patch.object(u, "MAX_COLUMN_OPERATIONS", 10_000 * 3 * 2 - 1):
            with self.assertRaisesRegex(ValueError, "declared limits"):
                u.bootstrap([[1, 1, 1], [0, 0, 0]], 3, settings)
        sums = u.bootstrap([[1, 1, 1], [0, 1, 2]], 3, dict(settings, resamples=4))
        self.assertEqual(sums[0], [3, 3, 3, 3])
        self.assertEqual(len(sums[1]), 4)


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.document = metrics_document(
            [(2, 1, [1, 0]), (1, 1, [0, 1])], tolerances=(0, 3)
        )

    def check(self, change, message):
        document = copy.deepcopy(self.document)
        change(document)
        with self.assertRaisesRegex(ValueError, message):
            u.load_statistics(document)

    def test_valid(self):
        roster, overall, rows = u.load_statistics(self.document)
        self.assertEqual(roster, [(1, 0), (1, 3)])
        self.assertEqual(overall[1], [1, 1])
        self.assertEqual([matched for _, matched in rows], [[1, 0], [0, 1]])

    def test_document_level(self):
        self.check(lambda d: d.update(schema_version="x"), "Metrics schema")
        with self.assertRaisesRegex(ValueError, "Metrics schema"):
            u.load_statistics([])
        self.check(lambda d: d.update(settings=[]), "settings must be an object")
        self.check(
            lambda d: d["settings"].update(top_k=[5]), "settings_sha256 mismatch"
        )
        self.check(lambda d: d.update(settings_sha256="0" * 64), "settings_sha256")
        self.check(lambda d: d["settings"].update(tie_rule="other"), "settings_sha256")
        self.check(lambda d: d.update(tool_sha256="bad"), "lowercase 64-hex")
        self.check(lambda d: d.update(inputs={}), "inputs must identify")
        self.check(lambda d: d.update(inputs=[]), "inputs must identify")
        self.check(lambda d: d["inputs"].update(groups_sha256="0"), "lowercase 64-hex")
        self.check(lambda d: d["inputs"].update(x="a" * 64), "inputs must identify")
        self.check(lambda d: d.update(n_groups=3), "matching n_groups")
        self.check(lambda d: d.update(groups={}, n_groups=0), "1..")
        self.check(lambda d: d.update(groups=[]), "matching n_groups")
        with mock.patch.object(u, "MAX_GROUPS", 1):
            self.check(lambda d: None, "1..1 groups")
        one = metrics_document([(1, 1, [1])])
        one["n_groups"] = True
        with self.assertRaisesRegex(ValueError, "matching n_groups"):
            u.load_statistics(one)
        self.check(
            lambda d: d["groups"].update({"": d["groups"].pop("grp001")}),
            "Group IDs must be nonempty",
        )

    def test_summary_arithmetic(self):
        group = lambda d: d["groups"]["grp000"]  # noqa: E731
        self.check(lambda d: d.update(overall=[]), "overall summary must be")
        for field in u.COUNT_FIELDS:
            for bad in (-1, True, 1.0, None):
                self.check(
                    lambda d, f=field, b=bad: group(d).update({f: b}),
                    "nonnegative integer",
                )
        self.check(lambda d: group(d).update(n_out_of_window=0), "inconsistent")
        self.check(
            lambda d: group(d).update(n_in_window=3, n_out_of_window=-1),
            "nonnegative",
        )
        self.check(lambda d: group(d).update(n_in_complete_query=2), "inconsistent")
        self.check(lambda d: group(d).update(recovery={}), "roster")
        self.check(lambda d: group(d)["recovery"].pop(), "roster")
        self.check(lambda d: group(d)["recovery"].reverse(), "roster")
        self.check(lambda d: group(d)["recovery"].__setitem__(0, 1), "roster")
        self.check(lambda d: group(d)["recovery"][0].update(top_k=True), "roster")
        self.check(
            lambda d: group(d)["recovery"][0].update(tolerance_nt=False), "roster"
        )
        self.check(
            lambda d: group(d)["recovery"][0].update(matched=False),
            "nonnegative integer",
        )
        self.check(
            lambda d: group(d)["recovery"][1].update(
                matched=2, fraction_of_all_labels=1.0, fraction_of_in_window_labels=2.0
            ),
            "exceeds complete-query",
        )
        self.check(
            lambda d: group(d)["recovery"][0].update(fraction_of_all_labels=0.4),
            "fraction_of_all_labels disagrees",
        )
        self.check(
            lambda d: group(d)["recovery"][1].update(fraction_of_all_labels=0),
            "disagrees",
        )
        self.check(
            lambda d: group(d)["recovery"][1].update(fraction_of_in_window_labels=None),
            "fraction_of_in_window_labels disagrees",
        )
        empty = summary(0, 0, [0, 0], [(1, 0), (1, 3)])
        self.check(
            lambda d: (
                d["groups"].update(grp002=empty),
                d.update(n_groups=3),
            ),
            "grp002 has no labels",
        )

    def test_group_sums_must_match_overall(self):
        self.check(
            lambda d: d.update(overall=summary(4, 2, [1, 1], [(1, 0), (1, 3)])),
            "n_labels does not sum",
        )
        self.check(
            lambda d: d.update(overall=summary(3, 2, [2, 1], [(1, 0), (1, 3)])),
            "matched counts do not sum",
        )


def pipeline_metrics():
    """Real builder, projection, groups and evaluator on a synthetic genome."""
    rng = random.Random(41)
    sequence = "".join(rng.choice("ACGT") for _ in range(30_000))
    records = [
        {
            "id": f"r{i}",
            "genome_id": "g",
            "strand": "+" if i % 2 else "-",
            "tss_zero_based": 400 * i + rng.randrange(100),
        }
        for i in range(70)
    ]
    value = {
        "schema_version": n.ENVELOPE_SCHEMA,
        "genomes": {
            "g": {
                "sequence": sequence,
                "sequence_sha256": n.digest(sequence),
                "accession": "synthetic",
                "assembly": "synthetic-v1",
                "annotation": "synthetic-annotation-v1",
                "topology": "circular",
            }
        },
        "records": records,
    }
    raw = json.dumps(value).encode()
    digest = n.digest(raw)
    envelope = n.load_envelope(raw, digest)
    queries = n.build_queries(envelope, digest, n.grid_settings(100, 40, "unc"))
    labels = n.project_labels(envelope, digest, queries)
    groups = g.build_groups(envelope, digest, queries, labels)
    positive = {
        (x["query_id"], x["local_index"]) for x in labels["labels"] if x["query_id"]
    }
    results = []
    for i, q in enumerate(queries["queries"]):
        lower, upper = q["candidate_local_range"]
        results.append(
            {
                "request_id": f"r{i}",
                "query_id": q["query_id"],
                "status": "ok",
                "candidates": [
                    {
                        "local_index": local,
                        "status": "ok",
                        "score": 0.0 if (q["query_id"], local) in positive else 1.0,
                    }
                    for local in range(lower, upper)
                ],
            }
        )
    scores = {
        "schema_version": m.SCORE_SCHEMA,
        "query_document_sha256": n.document_sha256(queries),
        "results": results,
    }
    return m.evaluate(queries, scores, labels, groups, m.metric_settings(True))


class PipelineTest(unittest.TestCase):
    def test_real_metrics_document(self):
        metrics = pipeline_metrics()
        self.assertGreaterEqual(metrics["n_groups"], 20)
        result = u.summarize(metrics)
        overall = metrics["overall"]
        for row in result["endpoints"]:
            source = next(
                r
                for r in overall["recovery"]
                if (r["top_k"], r["tolerance_nt"])
                == (row["top_k"], row["tolerance_nt"])
            )
            self.assertEqual(row["matched"], source["matched"])
            self.assertEqual(row["point"], source[f"fraction_of_{row['denominator']}"])
        window = endpoint(result, "in_window_labels")
        self.assertEqual(window["point"], 1.0)
        self.assertLess(endpoint(result, "all_labels")["point"], 1.0)
        self.assertEqual(result["n_groups"], metrics["n_groups"])


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name)
        self.document = metrics_document([(1, 1, [i % 2]) for i in range(5)])
        self.raw = n.canonical_bytes(self.document)
        (self.path / "metrics.json").write_bytes(self.raw)
        self.digest = n.digest(self.raw)

    def argv(self, output="unc.json", digest=None, metrics="metrics.json"):
        return [
            str(self.path / metrics),
            str(self.path / output),
            "--metrics-sha256",
            digest or self.digest,
        ]

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = u.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_success_and_no_overwrite(self):
        code, out, _ = self.run_main(self.argv())
        self.assertEqual(code, 0)
        output = self.path / "unc.json"
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
        raw = output.read_bytes()
        self.assertEqual(json.loads(out)["output_sha256"], n.digest(raw))
        self.assertEqual(json.loads(raw), u.summarize(self.document))
        code, out, err = self.run_main(self.argv())
        self.assertEqual((code, out), (1, ""))
        self.assertIn("error:", err)
        self.assertEqual(output.read_bytes(), raw)

    def test_failures(self):
        code, _, err = self.run_main(self.argv(digest="0" * 64))
        self.assertEqual(code, 1)
        self.assertIn("file SHA-256 mismatch", err)
        code, _, err = self.run_main(self.argv(digest="bad"))
        self.assertIn("lowercase", err)
        pretty = json.dumps(self.document, indent=1).encode()
        (self.path / "pretty.json").write_bytes(pretty)
        code, _, err = self.run_main(
            self.argv(metrics="pretty.json", digest=n.digest(pretty))
        )
        self.assertEqual(code, 1)
        self.assertIn("not canonical", err)
        broken = copy.deepcopy(self.document)
        broken["n_groups"] = 9
        raw = n.canonical_bytes(broken)
        (self.path / "broken.json").write_bytes(raw)
        code, _, err = self.run_main(
            self.argv(metrics="broken.json", digest=n.digest(raw))
        )
        self.assertEqual(code, 1)
        self.assertIn("n_groups", err)
        code, _, err = self.run_main(self.argv(metrics="missing.json"))
        self.assertEqual(code, 1)
        self.assertFalse((self.path / "unc.json").exists())

    def test_module_entry_point(self):
        with (
            mock.patch.object(
                sys, "argv", ["native_uncertainty", *self.argv(digest="0" * 64)]
            ),
            contextlib.redirect_stderr(io.StringIO()),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module(
                    "benchmarks.promoter.native_uncertainty", run_name="__main__"
                )
        self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
