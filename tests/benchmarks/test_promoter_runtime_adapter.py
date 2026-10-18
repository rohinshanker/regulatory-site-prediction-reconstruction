"""Outcome-free runtime adapter: plans, batching, collections and scores-2.

Every runtime result here is a synthetic, contract-shaped fake built by this
test from independent per-base coordinate math. Fake identities and scores are
not candidate receipts and say nothing about the Promoter model.
"""

import contextlib
import copy
import hashlib
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from benchmarks.promoter import native_inputs as n
from benchmarks.promoter import native_metrics as m
from benchmarks.promoter import runtime_adapter as a

ROOT = Path(__file__).resolve().parents[2]
HOST = {"name": "synthetic-extrapolated-host", "taxon_id": None}
# A synthetic receipt-shaped model object; nested key names are illustrative
# only, which is why the adapter compares the whole object exactly.
MODEL = {
    "id": "synthetic-promoter-model",
    "implementation_version": "0.0.0+synthetic",
    "kind": "historical_equation_reconstruction",
    "source": {"historical": {"commit": "7" * 40}},
    "licence": "GPL-3.0-or-later",
    "parameters": {
        "coefficients": {"sha256": "5" * 64, "count": 343},
        "intercept": {"sha256": "6" * 64, "count": 1},
        "unused_indices": [336, 337, 338],
        "parameter_json_sha256": "4" * 64,
    },
    "term_source_names": {},
    "terms_unit": "source_dG_units",
    "terms_semantics": "learned regression score contributions",
    "source_quirks": [],
    "not_modeled": [
        "sigma_factor",
        "temperature",
        "host_specific_calibration",
        "probability",
        "absolute_rate",
        "free_energy",
    ],
    "claims": {
        "physical_free_energy": False,
        "absolute_rate": False,
        "probability": False,
        "native_accuracy_evaluated": False,
        "hosted_parity": False,
    },
}
IDENTITY = {
    "candidate_commit": "1" * 40,
    "public_contract_commit": "2" * 40,
    "wheel_sha256": "3" * 64,
    "implementation_version": "0.0.0+synthetic",
    "model_id": "synthetic-promoter-model",
    "parameter_json_sha256": "4" * 64,
    "expected_model": MODEL,
}
RUNTIME_LIMITS = {"synthetic_effective": {"sites_per_batch": 20_000}}
CEILINGS = {
    "request_bytes": 4_000_000,
    "records_per_batch": 100,
    "bases_per_record": 5_000,
    "bases_per_batch": 100_000,
    "sites_per_record": 5_000,
    "sites_per_batch": 20_000,
}
# Hand-copied from the public calibration table, not from the adapter.
EXTRAPOLATED_CALIBRATION = {
    "profile": "ecoli_mg1655",
    "K": 42,
    "beta": 1.636217004872062,
    "native_host": "Escherichia coli str. K-12 substr. MG1655",
    "host": HOST,
    "host_status": "extrapolated",
}


def sequence(length, salt):
    return "".join(
        "ACGT"[int(hashlib.sha256(f"{salt}:{i}".encode()).hexdigest(), 16) % 4]
        for i in range(length)
    )


def query_document(genomes=None, width=100):
    genomes = genomes or {"circ": (300, "circular"), "lin": (260, "linear")}
    envelope = {
        "schema_version": n.ENVELOPE_SCHEMA,
        "genomes": {
            key: {
                "sequence": sequence(length, key),
                "sequence_sha256": n.digest(sequence(length, key)),
                "accession": key,
                "assembly": "synthetic",
                "annotation": "synthetic",
                "topology": topology,
            }
            for key, (length, topology) in genomes.items()
        },
        "records": [],
    }
    raw = json.dumps(envelope).encode()
    source = n.digest(raw)
    loaded = n.load_envelope(raw, source)
    return n.build_queries(loaded, source, n.grid_settings(width, 128, "adapter"))


def manifest(calibration="ecoli_mg1655", host=HOST, limits=None, **settings):
    return a.build_manifest(
        copy.deepcopy(IDENTITY),
        {
            "calibration": calibration,
            "host": host,
            "limits": dict(limits or CEILINGS),
            "runtime_limits": copy.deepcopy(RUNTIME_LIMITS),
            "seconds_per_record": settings.get("seconds_per_record", 30),
            "seconds_per_batch": settings.get("seconds_per_batch", 300),
            "cli_calibration": settings.get("cli_calibration"),
            "cli_states": settings.get("cli_states"),
        },
    )


def public_batch_id(request, settings):
    """batch_id payload written out from the b8ef835 contract text."""
    payload = {
        "input": request,
        "model": {
            "id": MODEL["id"],
            "implementation_version": MODEL["implementation_version"],
            "parameter_json_sha256": MODEL["parameters"]["parameter_json_sha256"],
        },
        "limits": settings["runtime_limits"],
        "seconds_per_record": settings["seconds_per_record"],
        "seconds_per_batch": settings["seconds_per_batch"],
        "cli_calibration": settings["cli_calibration"],
        "cli_states": settings["cli_states"],
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def rehash(document):
    document["queries_sha256"] = n.document_sha256(document["queries"])
    return document


def brute_states(length, tss):
    """Complete (d, s) states built forward from UP.start, independently."""
    return [
        (d, s)
        for d in range(6, 11)
        for s in range(15, 21)
        if tss - d - 6 - s - 6 - 1 - 24 >= 0 and tss + 20 <= length
    ]


def forward_windows(tss, d, s):
    up = tss - d - 6 - s - 6 - 1 - 24
    spacer = up + 31
    return {
        "UP": [up, up + 24],
        "gap": [up + 24, up + 25],
        "hex35": [up + 25, up + 31],
        "spacer": [spacer, spacer + s],
        "extended10": [spacer + s - 3, spacer + s - 1],
        "hex10": [tss - d - 6, tss - d],
        "discriminator": [tss - d, tss],
        "itr": [tss, tss + 20],
    }


def per_base_runs(points, step):
    """Group points listed along transcription into ascending genomic runs."""
    runs = []
    for point in points:
        if runs and point == runs[-1][-1] + step:
            runs[-1].append(point)
        else:
            runs.append([point])
    return [[min(run), max(run) + 1] for run in runs]


def query_runs(query, interval):
    points = [
        n.local_to_genomic(query["strand"], query["segments"], i)
        for i in range(*interval)
    ]
    return per_base_runs(points, 1 if query["strand"] == "+" else -1)


def synthetic_total(local):
    # Synthetic lower-better values with deliberate exact ties.
    return ((local * 7919) % 13) / 4 - 1.5


def fake_site(query, local, scope, attempted=True, failure=None):
    length = len(query["sequence"])
    states = brute_states(length, local)
    site_id = f"psite1:{scope}:+:{local}"
    site = {
        "site_id": site_id,
        "strand": "+",
        "tss": {"forward_base": local, "oriented_base": local},
        "genomic": {
            "contig": query["genome_id"],
            "base": n.local_to_genomic(query["strand"], query["segments"], local),
            "strand": query["strand"],
            "sequence_strand": query["strand"],
        },
        "status": "ok",
        "reason": None,
        "context": {
            "required_upstream": 67,
            "required_downstream": 19,
            "available_upstream": local,
            "available_downstream": length - 1 - local,
        },
        "state_count": len(states),
        "complete_state_set": len(states) == 30,
        "attempted": attempted,
        "tie_count": None,
        "selected": None,
    }
    if failure:
        site.update(status="failed", reason=failure)
    elif not states:
        site.update(status="no_candidate", reason="insufficient_context")
    else:
        d, s = states[-1]
        windows = forward_windows(local, d, s)
        terms = dict.fromkeys(a.TERM_KEYS, 0.0)
        terms["total"] = synthetic_total(local)
        site.update(
            tie_count=1,
            selected={
                "state_id": f"{site_id}:d{d}s{s}",
                "discriminator_length": d,
                "spacer_length": s,
                "terms": terms,
                "log_relative_transcription_score": 1.25,
                "relative_transcription_score": 3.5,
                "score_status": "ok",
                "intervals": copy.deepcopy(windows),
                "oriented_intervals": copy.deepcopy(windows),
                "genomic_intervals": {
                    name: query_runs(query, window) for name, window in windows.items()
                },
            },
        )
    return site


def fake_coverage(status, sites):
    failed = [site for site in sites if site["status"] == "failed"]
    coverage = {
        "planned_sites": len(sites),
        "scored_sites": sum(site["status"] == "ok" for site in sites),
        "partial_state_sites": sum(
            site["status"] == "ok" and site["state_count"] < 30 for site in sites
        ),
        "insufficient_context_sites": sum(
            site["status"] == "no_candidate" for site in sites
        ),
        "failed_sites": sum(site["attempted"] for site in failed),
        "unattempted_sites": sum(not site["attempted"] for site in failed),
        "complete_context": all(site["state_count"] == 30 for site in sites),
        "complete": not failed,
        "truncation": None,
    }
    if status == "failed":
        coverage["truncation"] = {
            "reason": failed[0]["reason"],
            "attempted_sites": sum(site["attempted"] for site in sites),
            "planned_sites": len(sites),
        }
    return coverage


def fake_record(request, query, calibration, behavior=None):
    behavior = behavior or {}
    digest = n.digest(request["sequence"])
    if behavior.get("status") in ("invalid_input", "unsupported"):
        # Rejected records: null prediction/coverage; invalid input keeps only
        # the raw hash, unsupported echoes the fields that passed validation.
        invalid = behavior["status"] == "invalid_input"
        return {
            "id": request["id"],
            "status": behavior["status"],
            "reasons": ["limit_exceeded" if invalid else "unsupported_control"],
            "prediction_id": None,
            "input": {
                "raw_sha256": digest,
                "normalized_dna_sha256": None if invalid else digest,
                "length": None if invalid else len(request["sequence"]),
                "normalization": "remove ASCII whitespace; uppercase; U->T",
            },
            "calibration": None if invalid else calibration,
            "scan": None if invalid else request["scan"],
            "coverage": None,
            "sites": [],
            "projection": None if invalid else request["projection"],
            "warnings": [],
            "errors": [{"code": "x", "field": "$", "message": "private text"}],
            "metadata": None,
        }
    scope = hashlib.sha256(request["id"].encode()).hexdigest()[:32]
    lower, upper = request["scan"]["range"]
    sites = []
    for offset, local in enumerate(range(lower, upper)):
        if "deadline_after" in behavior and offset >= behavior["deadline_after"]:
            sites.append(fake_site(query, local, scope, False, "deadline_exceeded"))
        elif behavior.get("nonfinite_at") == local:
            sites.append(fake_site(query, local, scope, True, "nonfinite_arithmetic"))
        else:
            sites.append(fake_site(query, local, scope))
    statuses = {site["status"] for site in sites}
    status = (
        "failed"
        if "failed" in statuses
        else "ok"
        if "ok" in statuses
        else "no_candidate"
    )
    reasons = []
    if status == "no_candidate":
        reasons = ["insufficient_context"] if sites else ["empty_scan"]
    return {
        "id": request["id"],
        "status": status,
        "reasons": reasons,
        "prediction_id": hashlib.sha256(request["id"].encode()).hexdigest(),
        "input": {
            "raw_sha256": digest,
            "normalized_dna_sha256": digest,
            "length": len(request["sequence"]),
            "normalization": "remove ASCII whitespace; uppercase; U->T",
        },
        "calibration": calibration,
        "scan": request["scan"],
        "coverage": fake_coverage(status, sites),
        "sites": sites,
        "projection": request["projection"],
        "warnings": [{"code": "host_extrapolation"}],
        "errors": [],
        "metadata": None,
    }


class Fixture:
    """Queries, manifest, plan and synthetic results for one test."""

    def __init__(self, queries=None, limits=None, calibration=None, **kwargs):
        self.queries = queries or query_document()
        limits = limits or dict(CEILINGS, records_per_batch=4)
        self.manifest = manifest(limits=limits, **kwargs)
        self.calibration = calibration or EXTRAPOLATED_CALIBRATION
        self.plan = a.prepare(self.queries, self.manifest)
        self.plan_sha = n.document_sha256(self.plan)
        self.by_request = {
            record["request_id"]: query
            for _, query_rows in self._pairs()
            for record, query in query_rows
        }

    def _pairs(self):
        lookup = {query["query_id"]: query for query in self.queries["queries"]}
        for batch in self.plan["batches"]:
            yield (
                batch,
                [(record, lookup[record["query_id"]]) for record in batch["records"]],
            )

    def result(self, index, behaviors=None):
        behaviors = behaviors or {}
        request = self.plan["batches"][index]["request"]
        records = [
            fake_record(
                record,
                self.by_request[record["id"]],
                self.calibration,
                behaviors.get(record["id"]),
            )
            for record in request["records"]
        ]
        counts = {}
        for record in records:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        settings = self.manifest["settings"]
        return copy.deepcopy(
            {
                "schema_version": "1.0",
                "model": MODEL,
                "batch": {
                    "batch_id": public_batch_id(request, settings),
                    "record_count": len(records),
                    "status_counts": counts,
                    "complete": "failed" not in counts,
                    "limits": settings["runtime_limits"],
                    "seconds_per_record": settings["seconds_per_record"],
                    "seconds_per_batch": settings["seconds_per_batch"],
                },
                "results": records,
            }
        )

    def collection(self, overrides=None, behaviors=None, mutate=None):
        """Collection with every batch completed unless overridden."""
        overrides = overrides or {}
        entries, files = [], {}
        for batch in self.plan["batches"]:
            index = batch["batch_index"]
            status = overrides.get(index, "completed")
            entry = {
                "batch_index": index,
                "request_sha256": batch["request_sha256"],
                "status": status,
                "exit_code": {
                    "setup_failed": 2,
                    "execution_failed": -9,
                    "not_run": None,
                }.get(status),
                "result_sha256": None,
            }
            if status == "completed":
                result = self.result(index, behaviors)
                if mutate and index == 0:
                    mutate(result)
                raw = json.dumps(result, indent=2).encode()
                failed = any(
                    r["status"] in ("failed", "invalid_input")
                    for r in result["results"]
                )
                entry.update(exit_code=int(failed), result_sha256=n.digest(raw))
                files[entry["result_sha256"]] = raw
            entries.append(entry)
        collection = {
            "schema_version": a.COLLECTION_SCHEMA,
            "plan_sha256": self.plan_sha,
            "batches": entries,
        }
        return collection, files

    def adapt(self, collection, files):
        raw = json.dumps(collection).encode()
        return a.adapt(
            self.queries,
            self.manifest,
            self.plan_sha,
            raw,
            n.digest(raw),
            files.__getitem__,
        )


class CoordinateTest(unittest.TestCase):
    def test_tiny_fixtures(self):
        plus = {"origin": 95, "contig_length": 101, "sequence_strand": "+"}
        minus = {"origin": 5, "contig_length": 101, "sequence_strand": "-"}
        self.assertEqual(a.project_base(plus, 10), 4)
        self.assertEqual(
            a.project_interval(plus, "+", [3, 10]), ("+", [[98, 101], [0, 4]])
        )
        self.assertEqual(a.project_base(minus, 10), 96)
        self.assertEqual(
            a.project_interval(minus, "+", [3, 10]), ("-", [[0, 3], [97, 101]])
        )

    def test_contract_worked_examples(self):
        rows = [
            ("+", 500, "+", 100, 600, [65, 71], [[565, 571]]),
            ("+", 500, "-", 129, 629, [166, 190], [[666, 690]]),
            ("-", 700, "+", 100, 600, [65, 71], [[630, 636]]),
            ("-", 700, "-", 129, 571, [166, 190], [[511, 535]]),
            ("+", 950, "+", 100, 50, [40, 64], [[990, 1000], [0, 14]]),
            ("+", 830, "-", 129, 959, [166, 190], [[0, 20], [996, 1000]]),
            ("-", 50, "+", 100, 950, [40, 64], [[0, 11], [987, 1000]]),
            ("-", 180, "-", 129, 51, [166, 190], [[991, 1000], [0, 15]]),
        ]
        for sequence_strand, origin, site, local, base, interval, runs in rows:
            projection = {
                "origin": origin,
                "contig_length": 1000,
                "sequence_strand": sequence_strand,
            }
            with self.subTest(origin=origin, site=site):
                self.assertEqual(a.project_base(projection, local), base)
                self.assertEqual(
                    a.project_interval(projection, site, interval)[1], runs
                )
        self.assertEqual(a.genomic_strand("-", "+"), "-")
        self.assertEqual(a.genomic_strand("-", "-"), "+")

    def test_projection_matches_per_base_map(self):
        for size in range(1, 8):
            for origin in range(size):
                for strand in ("+", "-"):
                    projection = {
                        "origin": origin,
                        "contig_length": size,
                        "sequence_strand": strand,
                    }
                    direction = 1 if strand == "+" else -1
                    for lower in range(size):
                        for upper in range(lower + 1, size + 1):
                            for site in ("+", "-"):
                                bases = range(lower, upper)
                                order = bases if site == "+" else reversed(bases)
                                points = [
                                    (origin + direction * f) % size for f in order
                                ]
                                step = 1 if site == strand else -1
                                self.assertEqual(
                                    a.project_interval(
                                        projection, site, [lower, upper]
                                    ),
                                    (
                                        "+" if site == strand else "-",
                                        per_base_runs(points, step),
                                    ),
                                )

    def test_states_and_windows(self):
        self.assertEqual(a.state_windows(100, 6, 17), forward_windows(100, 6, 17))
        self.assertEqual(
            a.state_windows(100, 6, 17)["extended10"], [85, 87]
        )  # contract fixture
        self.assertEqual(
            [a.state_count(200, t) for t in (56, 57, 58, 59)], [0, 0, 1, 3]
        )
        self.assertEqual(a.state_count(90, 67), 30)
        self.assertEqual(a.state_count(90, 71), 0)
        for length in (77, 78, 87, 120):
            for t in range(length):
                for d, s in brute_states(length, t):
                    self.assertEqual(a.state_windows(t, d, s), forward_windows(t, d, s))
                self.assertEqual(a.state_count(length, t), len(brute_states(length, t)))
        evaluable = [t for t in range(200) if a.state_count(200, t)]
        self.assertEqual((evaluable[0], evaluable[-1], len(evaluable)), (58, 180, 123))


class ManifestTest(unittest.TestCase):
    def test_valid_boundaries(self):
        document = manifest(seconds_per_record=120, seconds_per_batch=3600.0)
        self.assertEqual(document["settings"]["limits"], CEILINGS)
        self.assertEqual(a.check_manifest(copy.deepcopy(document)), document)
        manifest(host=None, limits=dict.fromkeys(CEILINGS, 1), seconds_per_record=0.5)
        manifest(host={"name": "h", "taxon_id": 1})

    def test_rejections(self):
        def broken(path, value):
            document = copy.deepcopy(manifest())
            target = document
            for key in path[:-1]:
                target = target[key]
            if value is KeyError:
                del target[path[-1]]
            else:
                target[path[-1]] = value
            return document

        cases = [
            (("schema_version",), "x", "schema"),
            (("extra",), 1, "manifest needs"),
            (("identity", "extra"), 1, "identity needs"),
            (("identity", "candidate_commit"), "A" * 40, "40-hex"),
            (("identity", "public_contract_commit"), "1" * 39, "40-hex"),
            (("identity", "expected_model"), [], "expected_model needs"),
            (("identity", "expected_model", "backend"), {}, "expected_model needs"),
            (("identity", "expected_model", "id"), "other", "id/version"),
            (
                ("identity", "expected_model", "implementation_version"),
                "9",
                "id/version",
            ),
            (("identity", "expected_model", "parameters"), [], "id/version"),
            (
                ("identity", "expected_model", "parameters", "parameter_json_sha256"),
                "0" * 64,
                "id/version",
            ),
            (("identity", "expected_model", "source"), {}, "source and parameter"),
            (
                ("identity", "expected_model", "parameters"),
                {"parameter_json_sha256": "4" * 64},
                "source and parameter",
            ),
            (("identity", "expected_model", "kind"), "retrained", "public kind"),
            (("identity", "expected_model", "terms_unit"), "kcal/mol", "public kind"),
            (("identity", "expected_model", "not_modeled"), [], "public kind"),
            (
                ("identity", "expected_model", "claims", "hosted_parity"),
                True,
                "public kind",
            ),
            (("settings", "runtime_limits"), {}, "runtime_limits"),
            (("settings", "runtime_limits"), [1], "runtime_limits"),
            (("settings", "cli_calibration"), "in_vitro", "cli_calibration"),
            (("settings", "cli_states"), "all", "cli_states"),
            (("identity", "wheel_sha256"), "x", "64-hex"),
            (("identity", "parameter_json_sha256"), "F" * 64, "64-hex"),
            (("identity", "implementation_version"), "", "implementation_version"),
            (
                ("identity", "implementation_version"),
                "v" * 65,
                "implementation_version",
            ),
            (("identity", "model_id"), 1, "model_id"),
            (("settings", "calibration"), None, "explicitly"),
            (("settings", "calibration"), "auto", "explicitly"),
            (("settings", "host"), {"name": "h"}, "host needs"),
            (("settings", "host"), {"name": "", "taxon_id": None}, "host.name"),
            (("settings", "host"), {"name": "é", "taxon_id": None}, "NFC"),
            (("settings", "host"), {"name": "h", "taxon_id": 0}, "taxon_id"),
            (("settings", "host"), {"name": "h", "taxon_id": True}, "taxon_id"),
            (("settings", "limits", "request_bytes"), KeyError, "limits needs"),
            (("settings", "limits", "records_per_batch"), 0, "records_per_batch"),
            (("settings", "limits", "records_per_batch"), 101, "records_per_batch"),
            (("settings", "limits", "sites_per_batch"), 20_001, "sites_per_batch"),
            (("settings", "limits", "bases_per_record"), True, "bases_per_record"),
            (("settings", "limits", "request_bytes"), 4_000_001, "request_bytes"),
            (("settings", "seconds_per_record"), 0, "seconds_per_record"),
            (("settings", "seconds_per_record"), 120.5, "seconds_per_record"),
            (("settings", "seconds_per_record"), True, "seconds_per_record"),
            (("settings", "seconds_per_record"), float("nan"), "seconds_per_record"),
            (("settings", "seconds_per_batch"), 3601, "seconds_per_batch"),
            (("settings", "seconds_per_batch"), None, "seconds_per_batch"),
            (("settings", "extra"), 1, "settings needs"),
        ]
        for path, value, message in cases:
            with self.subTest(path=path, value=value):
                with self.assertRaisesRegex(ValueError, message):
                    a.check_manifest(broken(path, value))
        with self.assertRaisesRegex(ValueError, "manifest needs"):
            a.check_manifest([])

    def test_calibration_registry(self):
        native = {"name": a.NATIVE_HOST, "taxon_id": 511145}
        cases = [
            ("ecoli_mg1655", None, "unspecified"),
            ("ecoli_mg1655", native, "calibration_native"),
            ("ecoli_mg1655", HOST, "extrapolated"),
            ("in_vitro", None, "in_vitro_reference"),
            ("in_vitro", {"name": "in vitro", "taxon_id": None}, "in_vitro_reference"),
            ("in_vitro", native, "extrapolated"),
        ]
        for profile, host, status in cases:
            with self.subTest(profile=profile, host=host):
                calibration = a.expected_calibration(profile, host)
                self.assertEqual(calibration["host_status"], status)
                self.assertEqual(calibration["host"], host)
        self.assertEqual(
            a.expected_calibration("ecoli_mg1655", HOST), EXTRAPOLATED_CALIBRATION
        )
        self.assertEqual(
            a.expected_calibration("in_vitro", None),
            {
                "profile": "in_vitro",
                "K": 42,
                "beta": 0.81632623,
                "native_host": None,
                "host": None,
                "host_status": "in_vitro_reference",
            },
        )


def empty_range_document():
    """Hand-built 86-nt circular query whose candidate range is empty."""
    queries = query_document({"tiny": (200, "circular")})
    query = queries["queries"][0]
    sequence_text = query["sequence"][:86]
    g0 = query["segments"][0]["genomic"][0]
    query.update(
        sequence=sequence_text,
        sequence_sha256=n.digest(sequence_text),
        sequence_length=86,
        candidate_local_range=[67, 67],
        n_candidates=0,
        context=dict(query["context"], downstream_pad_nt=19),
        context_status="complete",
        full_state_support_local_range=None,
        n_candidates_full_state_support=0,
    )
    assert query["strand"] == "+" and g0 + 86 <= 200, "non-wrapping plus query"
    query["segments"] = [
        {"local": [0, 86], "genomic": [g0, g0 + 86], "oriented": [g0, g0 + 86]}
    ]
    query["candidate_genomic_interval"] = [g0 + 67, g0 + 67]
    queries["queries"] = [query]
    return rehash(queries)


class PrepareTest(unittest.TestCase):
    def test_plan_preserves_queries_and_projects_every_base(self):
        fixture = Fixture()
        queries, plan = fixture.queries, fixture.plan
        self.assertEqual(plan["query_document_sha256"], n.document_sha256(queries))
        self.assertEqual(plan["manifest_sha256"], n.document_sha256(fixture.manifest))
        self.assertEqual(plan["public_contract_commit"], "2" * 40)
        self.assertEqual(plan["expected_calibration"], EXTRAPOLATED_CALIBRATION)
        self.assertEqual(plan["tool_sha256"], a.tool_sha256())
        records = [r for b in plan["batches"] for r in b["request"]["records"]]
        self.assertEqual(len(records), len(queries["queries"]))
        self.assertEqual(
            [r["query_id"] for b in plan["batches"] for r in b["records"]],
            [q["query_id"] for q in queries["queries"]],
        )
        crossing = clipped = 0
        for record, query in zip(records, queries["queries"], strict=True):
            self.assertEqual(record["sequence"], query["sequence"])
            self.assertEqual(
                record["scan"],
                {
                    "mode": "scan",
                    "range": query["candidate_local_range"],
                    "strands": ["+"],
                },
            )
            self.assertEqual(record["output"], a.OUTPUT_OPTIONS)
            self.assertEqual(
                record["model"],
                {"id": "synthetic-promoter-model", "parameter_json_sha256": "4" * 64},
            )
            self.assertEqual(record["host"], {"name": HOST["name"]})
            projection = record["projection"]
            self.assertEqual(projection["sequence_strand"], query["strand"])
            for local in range(len(query["sequence"])):
                self.assertEqual(
                    a.project_base(projection, local),
                    n.local_to_genomic(query["strand"], query["segments"], local),
                )
            crossing += projection["origin_crossing"]
            clipped += query["context_status"] != "complete"
            if projection["topology"] == "linear":
                self.assertFalse(projection["origin_crossing"])
        self.assertEqual((crossing, clipped), (4, 5))
        self.assertEqual(plan["totals"]["n_sites"], 2 * (300 + 260))
        again = a.prepare(copy.deepcopy(queries), copy.deepcopy(fixture.manifest))
        self.assertEqual(n.canonical_bytes(again), n.canonical_bytes(plan))

    def test_request_bytes_are_exact(self):
        plan = Fixture().plan
        for batch in plan["batches"]:
            raw = a.plan_request_bytes(plan, batch["batch_index"])
            joined = b",".join(
                json.dumps(r, sort_keys=True, separators=(",", ":")).encode()
                for r in batch["request"]["records"]
            )
            self.assertEqual(raw, a.REQUEST_PREFIX + joined + a.REQUEST_SUFFIX)
            self.assertEqual(raw, n.canonical_bytes(batch["request"]))
            self.assertEqual(len(raw), batch["request_bytes"])
            self.assertEqual(n.digest(raw), batch["request_sha256"])
            self.assertEqual(json.loads(raw)["defaults"], {})
        tampered = copy.deepcopy(plan)
        tampered["batches"][0]["request"]["records"][0]["sequence"] += "A"
        with self.assertRaisesRegex(ValueError, "disagree with request_sha256"):
            a.plan_request_bytes(tampered, 0)
        with self.assertRaisesRegex(ValueError, "batch index"):
            a.plan_request_bytes(plan, len(plan["batches"]))
        with self.assertRaisesRegex(ValueError, "Plan schema"):
            a.plan_request_bytes({}, 0)

    def test_requests_satisfy_public_request_schema(self):
        schema = json.loads(
            (ROOT / "schemas/promoter-request-1.0.schema.json").read_text("utf-8")
        )
        validator = Draft202012Validator(schema)
        plans = [
            Fixture().plan,
            a.prepare(empty_range_document(), manifest(host=None)),
            a.prepare(
                query_document({"g": (120, "linear")}),
                manifest("in_vitro", host={"name": "in vitro", "taxon_id": 9}),
            ),
        ]
        for plan in plans:
            for batch in plan["batches"]:
                raw = a.plan_request_bytes(plan, batch["batch_index"])
                validator.validate(json.loads(raw))
                validator.validate(batch["request"])

    def test_planned_batch_id_payload(self):
        fixture = Fixture()
        settings = fixture.manifest["settings"]
        for batch in fixture.plan["batches"]:
            self.assertEqual(
                batch["batch_id"], public_batch_id(batch["request"], settings)
            )
        cli = Fixture(cli_calibration="ecoli_mg1655", cli_states="selected")
        self.assertNotEqual(
            cli.plan["batches"][0]["batch_id"], fixture.plan["batches"][0]["batch_id"]
        )
        cli.adapt(*cli.collection())
        stale = public_batch_id(fixture.plan["batches"][0]["request"], settings)
        collection, files = cli.collection(
            mutate=lambda r: r["batch"].update(batch_id=stale)
        )
        with self.assertRaisesRegex(ValueError, "batch_id disagrees"):
            cli.adapt(collection, files)

    def test_host_variants(self):
        queries = query_document({"g": (120, "circular")})
        no_host = a.prepare(queries, manifest(host=None))
        record = no_host["batches"][0]["request"]["records"][0]
        self.assertNotIn("host", record)
        self.assertEqual(no_host["expected_calibration"]["host_status"], "unspecified")
        taxon = a.prepare(queries, manifest(host={"name": "h", "taxon_id": 7}))
        self.assertEqual(
            taxon["batches"][0]["request"]["records"][0]["host"],
            {"name": "h", "taxon_id": 7},
        )
        in_vitro = a.prepare(queries, manifest("in_vitro", host=None))
        self.assertEqual(
            in_vitro["batches"][0]["request"]["records"][0]["calibration"], "in_vitro"
        )

    def test_empty_range_query(self):
        plan = a.prepare(empty_range_document(), manifest())
        record = plan["batches"][0]["request"]["records"][0]
        self.assertEqual(record["scan"]["range"], [67, 67])
        self.assertEqual(plan["totals"]["n_sites"], 0)


class BatchingTest(unittest.TestCase):
    def setUp(self):
        # Eight circular queries of 50 candidates and 136 bases each.
        self.queries = query_document({"g": (200, "circular")}, width=50)
        self.size = 136

    def batches(self, **limits):
        plan = a.prepare(self.queries, manifest(limits=dict(CEILINGS, **limits)))
        self.assertEqual(
            [r["query_id"] for b in plan["batches"] for r in b["records"]],
            [q["query_id"] for q in self.queries["queries"]],
        )
        return [batch["n_records"] for batch in plan["batches"]], plan

    def test_count_limits_exact_boundary_and_one_past(self):
        self.assertEqual(self.batches(records_per_batch=3)[0], [3, 3, 2])
        self.assertEqual(self.batches(sites_per_batch=100)[0], [2, 2, 2, 2])
        self.assertEqual(self.batches(sites_per_batch=99)[0], [1] * 8)
        self.assertEqual(self.batches(bases_per_batch=3 * self.size)[0], [3, 3, 2])
        self.assertEqual(self.batches(bases_per_batch=3 * self.size - 1)[0], [2] * 4)
        self.assertEqual(
            self.batches(sites_per_record=50, bases_per_record=136)[0], [8]
        )
        for limit, message in (
            ({"sites_per_record": 49}, "sites_per_record: 50 > 49"),
            ({"bases_per_record": 135}, "bases_per_record: 136 > 135"),
            ({"sites_per_batch": 49}, "sites_per_batch: 50 > 49"),
            ({"bases_per_batch": 135}, "bases_per_batch: 136 > 135"),
        ):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(ValueError, message):
                    self.batches(**limit)

    def test_serialized_byte_limit(self):
        _, plan = self.batches()
        records = plan["batches"][0]["request"]["records"]
        sizes = [
            len(json.dumps(r, sort_keys=True, separators=(",", ":"))) for r in records
        ]
        fixed = len(a.REQUEST_PREFIX) + len(a.REQUEST_SUFFIX)
        two = fixed + sizes[0] + 1 + sizes[1]
        counts, plan = self.batches(request_bytes=two)
        self.assertEqual(counts[0], 2)
        self.assertEqual(plan["batches"][0]["request_bytes"], two)
        self.assertEqual(self.batches(request_bytes=two - 1)[0][0], 1)
        self.assertEqual(self.batches(request_bytes=fixed + max(sizes))[0], [1] * 8)
        with self.assertRaisesRegex(ValueError, "request_bytes"):
            self.batches(request_bytes=fixed + max(sizes) - 1)
        for batch in plan["batches"]:
            self.assertLessEqual(batch["request_bytes"], two)


def query_variants():
    """(mutation, message) pairs applied to a fresh real-builder document."""

    def q(doc, index=0):
        return doc["queries"][index]

    def first_crossing(doc):
        return next(
            row
            for row in doc["queries"]
            if len(row["segments"]) == 2 and row["genome_id"] == "circ"
        )

    def linear_plus(doc):
        return next(
            row
            for row in doc["queries"]
            if row["genome_id"] == "lin" and row["context"]["upstream_shortfall_nt"]
        )

    return [
        (lambda d: d.update(schema_version="x"), "schema must be"),
        (lambda d: d.update(labels=[]), "query document needs"),
        (lambda d: d["genomes"]["circ"].update(extra=1), "genome needs"),
        (lambda d: d["genomes"]["circ"].update(length=0), "genome length"),
        (lambda d: d["genomes"]["circ"].update(topology="x"), "topology"),
        (lambda d: d["genomes"]["circ"].update(sequence_sha256="x"), "64-hex"),
        (lambda d: d.update(genomes={}), "1..64 genomes"),
        (lambda d: d.update(queries=[]), "queries"),
        (lambda d: d.update(queries_sha256="0" * 64), "hashes disagree"),
        (lambda d: d.update(settings_sha256="0" * 64), "hashes disagree"),
        (lambda d: q(d).update(label="x"), "query needs"),
        (lambda d: q(d, 1).update(query_id=q(d)["query_id"]), "Duplicate query"),
        (lambda d: q(d).update(query_id=""), "query_id"),
        (lambda d: q(d).update(genome_id="other"), "declared genome"),
        (lambda d: q(d).update(genome_id=["circ"]), "genome_id"),
        (lambda d: q(d).update(strand="."), "declared genome/strand"),
        (lambda d: q(d).update(orientation="genomic"), "transcript-oriented"),
        (lambda d: q(d).update(tile_ordinal=True), "tile_ordinal"),
        (lambda d: q(d).update(selection_key="x"), "64-hex"),
        (lambda d: q(d).update(sequence=q(d)["sequence"].lower()), "uppercase"),
        (lambda d: q(d).update(sequence_length=1), "uppercase"),
        (lambda d: q(d).update(sequence_sha256="0" * 64), "hash-bound"),
        (lambda d: q(d).update(sequence=""), "hash-bound"),
        (lambda d: q(d).update(candidate_local_range=[5, 4]), "candidate_local_range"),
        (lambda d: q(d).update(candidate_local_range=[0, 10**6]), "candidate_local"),
        (lambda d: q(d).update(candidate_local_range=7), "pair"),
        (lambda d: q(d).update(n_candidates=1), "n_candidates"),
        (lambda d: q(d).update(segments=[]), "one or two runs"),
        (lambda d: q(d)["segments"][0].update(extra=1), "segment needs"),
        (lambda d: q(d)["segments"][0].update(local=[1, 187]), "segment local"),
        (lambda d: q(d)["segments"][-1].update(local=[0, 5]), "segment"),
        (lambda d: q(d)["segments"][0].update(genomic=[-1, 5]), "segment genomic"),
        (
            lambda d: first_crossing(d)["segments"][0].update(oriented=[0, 1]),
            "oriented",
        ),
        (
            lambda d: first_crossing(d).update(
                segments=first_crossing(d)["segments"][:1]
            ),
            "cover the query",
        ),
        (lambda d: d["genomes"]["circ"].update(topology="linear"), "outside"),
        (lambda d: q(d)["context"].update(upstream_pad_nt=66), "upstream_pad_nt"),
        (lambda d: q(d)["context"].update(extra=1), "context needs"),
        (
            lambda d: linear_plus(d)["context"].update(upstream_shortfall_nt=0),
            "upstream_shortfall_nt",
        ),
        (
            lambda d: linear_plus(d)["context"].update(downstream_shortfall_nt=1),
            "downstream_shortfall_nt",
        ),
        (lambda d: linear_plus(d).update(context_status="complete"), "support"),
        (lambda d: q(d).update(n_candidates_full_state_support=1), "support"),
        (lambda d: q(d).update(full_state_support_local_range=None), "support"),
        (
            lambda d: q(d).update(
                candidate_genomic_interval=[
                    q(d)["candidate_genomic_interval"][0] + 1,
                    q(d)["candidate_genomic_interval"][1] + 1,
                ]
            ),
            "Candidate genomic interval",
        ),
        (
            lambda d: q(d).update(candidate_genomic_interval=[0, 1]),
            "differ in size",
        ),
        (lambda d: q(d).update(candidate_genomic_interval=None), "pair"),
    ]


class QueryValidationTest(unittest.TestCase):
    def test_rejections(self):
        for index, (mutate, message) in enumerate(query_variants()):
            with self.subTest(index=index, message=message):
                document = query_document()
                mutate(document)
                if not message.startswith("hashes"):
                    rehash(document)
                with self.assertRaisesRegex(ValueError, message):
                    a.prepare(document, manifest())

    def test_padding_beyond_context_rejected(self):
        document = query_document()
        query = document["queries"][0]
        query["context"].update(upstream_pad_nt=68)
        query["candidate_local_range"][0] = 68
        query["n_candidates"] -= 1
        with self.assertRaisesRegex(ValueError, "upstream_pad_nt|exceeds"):
            a.check_query(query, document["genomes"])

    def test_handcrafted_segment_maps(self):
        genomes = {"g": {"length": 10, "topology": "circular"}}

        def query(length, segments):
            return {
                "query_id": "x",
                "genome_id": "g",
                "strand": "+",
                "sequence": "A" * length,
                "segments": [
                    {"local": loc, "genomic": gen, "oriented": gen}
                    for loc, gen in segments
                ],
            }

        with self.assertRaisesRegex(ValueError, "repeats replicon bases"):
            a.query_projection(
                query(12, [([0, 10], [0, 10]), ([10, 12], [0, 2])]), genomes["g"]
            )
        with self.assertRaisesRegex(ValueError, "Segment map disagrees"):
            a.query_projection(
                query(4, [([0, 2], [5, 7]), ([2, 4], [0, 2])]), genomes["g"]
            )
        with self.assertRaisesRegex(ValueError, "nonempty contiguous"):
            a.query_projection(query(2, [([0, 2], [5, 6])]), genomes["g"])
        crossing = a.query_projection(
            query(4, [([0, 2], [8, 10]), ([2, 4], [0, 2])]), genomes["g"]
        )
        self.assertEqual((crossing["origin"], crossing["origin_crossing"]), (8, True))


def keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


def find_site(result, status, record_status=None):
    for r, record in enumerate(result["results"]):
        if record_status and record["status"] != record_status:
            continue
        for s, site in enumerate(record["sites"]):
            if site["status"] == status:
                return r, s
    raise AssertionError(status)  # pragma: no cover


class AdaptTest(unittest.TestCase):
    def test_complete_collection(self):
        fixture = Fixture()
        collection, files = fixture.collection()
        scores, audit = fixture.adapt(collection, files)
        self.assertEqual(scores["schema_version"], m.SCORE_SCHEMA_V2)
        self.assertEqual(
            scores["provenance"],
            {
                "adapter_tool_sha256": a.tool_sha256(),
                "plan_sha256": fixture.plan_sha,
                "collection_sha256": n.digest(json.dumps(collection).encode()),
                "score_field": "selected.terms.total",
                "score_unit": "source_dG_units",
            },
        )
        queries = fixture.queries["queries"]
        self.assertEqual(
            [r["query_id"] for r in scores["results"]], [q["query_id"] for q in queries]
        )
        for row, query in zip(scores["results"], queries, strict=True):
            lower, upper = query["candidate_local_range"]
            self.assertEqual(
                [c["local_index"] for c in row["candidates"]], list(range(lower, upper))
            )
            for candidate in row["candidates"]:
                states = brute_states(len(query["sequence"]), candidate["local_index"])
                if states:
                    self.assertEqual(candidate["status"], "ok")
                    self.assertEqual(
                        candidate["score"], synthetic_total(candidate["local_index"])
                    )
                else:
                    self.assertEqual(
                        (candidate["status"], candidate["score"]),
                        ("no_candidate", None),
                    )
        counts = audit["counts"]
        self.assertEqual(
            counts["batch_status"],
            {"completed": 3, "setup_failed": 0, "execution_failed": 0, "not_run": 0},
        )
        self.assertEqual(counts["runtime_status"]["ok"], 12)
        no_candidate = counts["candidate_status"]["no_candidate"]
        self.assertEqual(counts["site_reason"]["insufficient_context"], no_candidate)
        self.assertEqual(counts["candidate_status"]["ok"] + no_candidate, 1120)
        # Partial-state ok sites are scored candidates; trailing/leading
        # insufficient-context candidates make four ok requests incomplete.
        self.assertEqual(counts["n_complete_requests"], 8)
        self.assertEqual(counts["n_incomplete_ok_requests"], 4)
        self.assertGreater(counts["n_partial_state_sites"], 0)
        self.assertEqual(
            counts["selected_score_status"]["ok"], counts["candidate_status"]["ok"]
        )
        self.assertEqual(audit["scores_sha256"], n.document_sha256(scores))
        self.assertEqual(audit["identity"], IDENTITY)
        text = json.dumps(audit)
        for leak in ("private text", "host_extrapolation", "synthetic-0"):
            self.assertNotIn(leak, text)
        self.assertFalse({"candidates", "sites", "score", "reasons"} & set(keys(audit)))
        again = fixture.adapt(*fixture.collection())
        self.assertEqual(n.canonical_bytes(again[0]), n.canonical_bytes(scores))

    def test_partial_failures_retain_every_candidate(self):
        fixture = Fixture()
        first = fixture.plan["batches"][0]["records"]
        behaviors = {
            first[0]["request_id"]: {"deadline_after": 30},
            first[1]["request_id"]: {"status": "invalid_input"},
            first[2]["request_id"]: {"status": "unsupported"},
            first[3]["request_id"]: {"nonfinite_at": 100},
        }
        collection, files = fixture.collection(
            {1: "setup_failed", 2: "not_run"}, behaviors
        )
        self.assertEqual(collection["batches"][0]["exit_code"], 1)
        scores, audit = fixture.adapt(collection, files)
        rows = scores["results"]
        statuses = [(r["status"], r["runtime_status"]) for r in rows]
        self.assertEqual(
            statuses,
            [
                ("failed", "failed"),
                ("failed", "invalid_input"),
                ("unsupported", "unsupported"),
                ("failed", "failed"),
            ]
            + [("failed", "setup_failed")] * 4
            + [("not_run", "not_run")] * 4,
        )
        deadline = [c["status"] for c in rows[0]["candidates"]]
        self.assertEqual(deadline[:30], ["ok"] * 30)
        self.assertEqual(deadline[30:], ["failed"] * 70)
        self.assertEqual({c["status"] for c in rows[1]["candidates"]}, {"failed"})
        self.assertEqual({c["status"] for c in rows[2]["candidates"]}, {"unsupported"})
        nonfinite = rows[3]["candidates"]
        self.assertEqual([c["status"] for c in nonfinite].count("failed"), 1)
        self.assertTrue(
            all(c["score"] is None for row in rows[4:] for c in row["candidates"])
        )
        self.assertEqual(
            sum(len(r["candidates"]) for r in rows), fixture.plan["totals"]["n_sites"]
        )
        counts = audit["counts"]
        self.assertEqual(counts["n_non_ok_requests_with_scored_candidates"], 2)
        self.assertEqual(counts["site_reason"]["deadline_exceeded"], 70)
        self.assertEqual(counts["site_reason"]["nonfinite_arithmetic"], 1)
        self.assertEqual(counts["n_unattempted_sites"], 70)
        self.assertEqual(
            counts["batch_status"],
            {"completed": 1, "setup_failed": 1, "execution_failed": 0, "not_run": 1},
        )
        # No per-batch ledger: a singleton batch status would link to a case.
        self.assertNotIn("batches", audit)
        self.assertNotIn("private text", json.dumps(audit))
        self.assertNotIn("private text", json.dumps(scores))

    def test_empty_range_no_candidate(self):
        fixture = Fixture(queries=empty_range_document())
        scores, audit = fixture.adapt(*fixture.collection())
        self.assertEqual(scores["results"][0]["status"], "no_candidate")
        self.assertEqual(scores["results"][0]["candidates"], [])
        self.assertEqual(audit["counts"]["n_incomplete_ok_requests"], 0)

    def test_metrics_integration_on_synthetic_labels(self):
        fixture = Fixture()
        queries = fixture.queries
        target = queries["queries"][0]
        lower = target["candidate_local_range"][0]
        # Synthetic labels: the window's lowest synthetic total and one more point.
        best = min(range(lower, lower + 100), key=lambda i: (synthetic_total(i), i))
        points = [best, lower + 5]
        labels = {
            "schema_version": n.LABEL_SCHEMA,
            "query_document_sha256": n.document_sha256(queries),
            "labels": [
                {
                    "label_id": f"L{p}",
                    "genome_id": target["genome_id"],
                    "strand": target["strand"],
                    "tss_zero_based": n.local_to_genomic(
                        target["strand"], target["segments"], p
                    ),
                    "query_id": target["query_id"],
                    "local_index": p,
                    "source_rows": [],
                }
                for p in points
            ],
        }
        groups = {
            "schema_version": m.GROUP_SCHEMA,
            "labels_document_sha256": n.document_sha256(labels),
            "groups": {f"L{p}": "grp" for p in points},
        }
        settings = m.metric_settings(True, (1,), (0,))
        complete, _ = fixture.adapt(*fixture.collection())
        result = m.evaluate(queries, complete, labels, groups, settings)
        self.assertEqual(result["overall"]["recovery"][0]["matched"], 1)
        self.assertEqual(result["coverage"]["runtime_status"]["ok"], 12)
        request = fixture.plan["batches"][0]["records"][0]["request_id"]
        partial, _ = fixture.adapt(
            *fixture.collection(behaviors={request: {"deadline_after": 50}})
        )
        result = m.evaluate(queries, partial, labels, groups, settings)
        overall = result["overall"]
        self.assertEqual(overall["recovery"][0]["matched"], 0)
        self.assertEqual(overall["n_in_complete_query"], 0)
        self.assertEqual(overall["n_label_candidate_scored"], 2)
        self.assertEqual(
            overall["conditional_successful_positions"]["recovery"][0]["matched"],
            1 if best < lower + 50 else 0,
        )
        self.assertEqual(
            result["coverage"]["n_non_ok_queries_with_scored_candidates"], 1
        )
        setup, _ = fixture.adapt(*fixture.collection({0: "setup_failed"}))
        result = m.evaluate(queries, setup, labels, groups, settings)
        self.assertEqual(result["overall"]["n_label_candidate_scored"], 0)
        self.assertEqual(result["coverage"]["request_status"]["failed"], 4)


def site_path(result, record, site, *keys):
    target = result["results"][record]["sites"][site]
    for key in keys:
        target = target[key]
    return target


class CollectionRejectionTest(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()

    def reject(self, message, mutate=None, collection_mutate=None, behaviors=None):
        collection, files = self.fixture.collection(behaviors=behaviors, mutate=mutate)
        if collection_mutate:
            collection_mutate(collection, files)
        with self.assertRaisesRegex(ValueError, message):
            self.fixture.adapt(collection, files)

    def test_plan_and_collection_binding(self):
        collection, files = self.fixture.collection()
        with self.assertRaisesRegex(ValueError, "Rebuilt plan differs"):
            a.adapt(
                self.fixture.queries,
                self.fixture.manifest,
                "0" * 64,
                collection,
                "1" * 64,
                files.get,
            )
        other = manifest(
            seconds_per_record=31, limits=dict(CEILINGS, records_per_batch=4)
        )
        with self.assertRaisesRegex(ValueError, "Rebuilt plan differs"):
            a.adapt(
                self.fixture.queries,
                other,
                self.fixture.plan_sha,
                collection,
                "1" * 64,
                files.get,
            )
        batches = lambda c: c["batches"]  # noqa: E731
        cases = [
            ("collection needs", lambda c, f: c.update(extra=1)),
            ("plan binding", lambda c, f: c.update(schema_version="x")),
            ("plan binding", lambda c, f: c.update(plan_sha256="0" * 64)),
            ("missing, extra", lambda c, f: batches(c).pop()),
            ("missing, extra", lambda c, f: batches(c).append(batches(c)[0])),
            ("missing, extra", lambda c, f: c.update(batches={})),
            ("missing, extra", lambda c, f: batches(c).reverse()),
            ("missing, extra", lambda c, f: batches(c)[1].update(batch_index=True)),
            (
                "missing, extra",
                lambda c, f: batches(c)[0].update(request_sha256="0" * 64),
            ),
            ("collected batch needs", lambda c, f: batches(c)[0].update(extra=1)),
            ("Unknown batch status", lambda c, f: batches(c)[0].update(status="done")),
            ("exit code 0 or 1", lambda c, f: batches(c)[0].update(exit_code=2)),
            ("exit code 0 or 1", lambda c, f: batches(c)[0].update(exit_code=False)),
            ("64-hex", lambda c, f: batches(c)[0].update(result_sha256=None)),
            (
                "need a null result",
                lambda c, f: batches(c)[0].update(
                    status="setup_failed", exit_code=1, result_sha256=None
                ),
            ),
            (
                "need a null result",
                lambda c, f: batches(c)[0].update(status="setup_failed", exit_code=2),
            ),
            (
                "need a null result",
                lambda c, f: batches(c)[0].update(
                    status="not_run", exit_code=0, result_sha256=None
                ),
            ),
            ("exit code disagrees", lambda c, f: batches(c)[0].update(exit_code=1)),
            (
                "two batches",
                lambda c, f: batches(c)[1].update(
                    result_sha256=batches(c)[0]["result_sha256"]
                ),
            ),
            (
                "Result bytes disagree",
                lambda c, f: f.update({batches(c)[0]["result_sha256"]: b"{}"}),
            ),
        ]
        for message, mutate in cases:
            with self.subTest(message=message):
                self.reject(message, collection_mutate=mutate)

    def test_result_document(self):
        def raw_override(raw):
            def mutate(collection, files):
                sha = n.digest(raw)
                collection["batches"][0]["result_sha256"] = sha
                files[sha] = raw

            return mutate

        self.reject(
            "Duplicate JSON key", collection_mutate=raw_override(b'{"a":1,"a":2}')
        )
        self.reject("Non-finite", collection_mutate=raw_override(b'{"a":NaN}'))
        self.reject("result needs", collection_mutate=raw_override(b"[]"))
        with mock.patch.object(a, "MAX_RESULT_BYTES", 10):
            self.reject("exceeds 10 bytes")
        records = lambda r: r["results"]  # noqa: E731
        model = lambda r: r["model"]  # noqa: E731
        summary = lambda r: r["batch"]  # noqa: E731
        cases = [
            ("schema_version must be", lambda r: r.update(schema_version="1.1")),
            ("model identity", lambda r: model(r).update(backend={})),
            # Expected strings present only in unrelated notes are not identity.
            (
                "model identity",
                lambda r: model(r).update(
                    source={"actual_commit": "e" * 40, "note": "7" * 40}
                ),
            ),
            (
                "model identity",
                lambda r: model(r)["parameters"].update(
                    coefficients={"sha256": "f" * 64},
                    notes=["5" * 64, "6" * 64],
                ),
            ),
            ("model identity", lambda r: model(r).update(licence="other")),
            ("model identity", lambda r: model(r).update(id="other")),
            ("model identity", lambda r: model(r).update(implementation_version="9")),
            ("model identity", lambda r: model(r).update(kind="retrained")),
            ("model identity", lambda r: model(r).update(terms_unit="kcal/mol")),
            ("model identity", lambda r: model(r).update(not_modeled=[])),
            ("model identity", lambda r: model(r)["claims"].update(hosted_parity=True)),
            ("model identity", lambda r: model(r).update(parameters=[])),
            (
                "model identity",
                lambda r: model(r)["parameters"].update(parameter_json_sha256="0" * 64),
            ),
            (
                "model identity",
                lambda r: model(r)["parameters"]["intercept"].update(sha256="0" * 64),
            ),
            ("missing, extra", lambda r: records(r).pop()),
            ("missing, extra", lambda r: r.update(results={})),
            ("missing, extra", lambda r: records(r).reverse()),
            ("result record needs", lambda r: records(r)[0].update(extra=1)),
            ("Unknown record status", lambda r: records(r)[0].update(status="done")),
            ("reasons must be a list", lambda r: records(r)[0].update(reasons="x")),
            ("warnings must be a list", lambda r: records(r)[0].update(warnings=None)),
            ("stable code", lambda r: records(r)[0].update(reasons=[1])),
            ("64-hex", lambda r: records(r)[0].update(prediction_id=None)),
            ("record input needs", lambda r: records(r)[0]["input"].update(extra=1)),
            (
                "input.normalization",
                lambda r: records(r)[0]["input"].update(normalization=""),
            ),
            ("input identity", lambda r: records(r)[0]["input"].update(length=1)),
            (
                "input identity",
                lambda r: records(r)[0]["input"].update(raw_sha256="0" * 64),
            ),
            (
                "calibration",
                lambda r: records(r)[0]["calibration"].update(beta=0.81632623),
            ),
            (
                "calibration",
                lambda r: records(r)[0]["calibration"].update(
                    host_status="unspecified"
                ),
            ),
            ("calibration", lambda r: records(r)[0]["calibration"].update(K=42.0)),
            ("calibration", lambda r: records(r)[0]["calibration"].update(host=None)),
            ("scan", lambda r: records(r)[0]["scan"].update(strands=["+", "-"])),
            ("projection", lambda r: records(r)[0]["projection"].update(origin=0)),
            (
                "projection",
                lambda r: records(r)[0]["projection"].update(origin_crossing=True),
            ),
            ("metadata", lambda r: records(r)[0].update(metadata={})),
            ("exactly once", lambda r: records(r)[0]["sites"].pop()),
            ("exactly once", lambda r: records(r)[0].update(sites={})),
            ("result batch needs", lambda r: summary(r).update(extra=1)),
            ("batch_id", lambda r: summary(r).update(batch_id="")),
            (
                "batch_id",
                lambda r: summary(r).update(
                    batch_id=public_batch_id(
                        self.fixture.plan["batches"][0]["request"],
                        {**self.fixture.manifest["settings"], "cli_states": "selected"},
                    )
                ),
            ),
            ("status_counts", lambda r: summary(r).update(status_counts={"done": 1})),
            ("status_counts", lambda r: summary(r).update(status_counts=[])),
            ("batch summary", lambda r: summary(r).update(status_counts={"ok": 3})),
            (
                "batch summary",
                lambda r: summary(r).update(status_counts={"ok": True, **{}}),
            ),
            ("batch summary", lambda r: summary(r).update(record_count=5)),
            ("batch summary", lambda r: summary(r).update(complete=False)),
            ("batch limits", lambda r: summary(r).update(limits=None)),
            (
                "batch limits",
                lambda r: summary(r)["limits"]["synthetic_effective"].update(
                    sites_per_batch=19_999
                ),
            ),
            ("batch_id disagrees", lambda r: summary(r).update(batch_id="not a hash")),
            ("batch_id disagrees", lambda r: summary(r).update(batch_id="0" * 64)),
            ("seconds_per_record", lambda r: summary(r).update(seconds_per_record=31)),
            ("seconds_per_batch", lambda r: summary(r).update(seconds_per_batch=True)),
        ]
        for message, mutate in cases:
            with self.subTest(message=message):
                self.reject(message, mutate)
        # Equal numeric echo of the deadline is accepted (30 == 30.0).
        collection, files = self.fixture.collection(
            mutate=lambda r: summary(r).update(seconds_per_record=30.0)
        )
        self.fixture.adapt(collection, files)

    def test_invalid_and_unsupported_records(self):
        first = self.fixture.plan["batches"][0]["records"][0]["request_id"]

        def record(**values):
            return lambda r: r["results"][0].update(values)

        def field(name, **values):
            return lambda r: r["results"][0][name].update(values)

        need = "need no sites, prediction or coverage"
        cases = [
            ("invalid_input", record(prediction_id="8" * 64), need),
            ("invalid_input", record(sites=[{}]), need),
            ("invalid_input", record(coverage={}), need),
            ("unsupported", record(prediction_id="8" * 64), need),
            ("unsupported", record(coverage={}), need),
            ("unsupported", field("calibration", beta=1.0), "Record calibration"),
            ("unsupported", field("scan", range=[0, 1]), "Record scan"),
            ("unsupported", field("projection", origin=1), "Record projection"),
            ("invalid_input", record(scan={"mode": "scan"}), "Record scan"),
            ("invalid_input", field("input", raw_sha256="0" * 64), "input identity"),
            ("unsupported", field("input", length=1), "input identity"),
            ("invalid_input", field("input", normalization=""), "normalization"),
            ("invalid_input", field("input", extra=1), "record input needs"),
            ("invalid_input", record(metadata={}), "Record metadata"),
        ]
        for status, mutate, message in cases:
            with self.subTest(status=status, message=message):
                self.reject(message, mutate, behaviors={first: {"status": status}})
        # Nullable echoes are accepted when the field failed validation.
        nulls = record(input=None, calibration=None, scan=None, projection=None)
        for status in ("invalid_input", "unsupported"):
            collection, files = self.fixture.collection(
                behaviors={first: {"status": status}}, mutate=nulls
            )
            self.assertEqual(
                self.fixture.adapt(collection, files)[0]["results"][0]["status"],
                "failed" if status == "invalid_input" else "unsupported",
            )
        collection, files = self.fixture.collection(
            behaviors={first: {"status": "invalid_input"}},
            mutate=field("input", raw_sha256=None, normalization=None),
        )
        self.fixture.adapt(collection, files)

    def test_execution_failed_batches(self):
        collection, files = self.fixture.collection({1: "execution_failed"})
        scores, audit = self.fixture.adapt(collection, files)
        rows = scores["results"][4:8]
        self.assertEqual(
            {(r["status"], r["runtime_status"]) for r in rows},
            {("failed", "execution_failed")},
        )
        self.assertEqual(
            {(c["status"], c["score"]) for r in rows for c in r["candidates"]},
            {("failed", None)},
        )
        self.assertEqual(audit["counts"]["batch_status"]["execution_failed"], 1)
        self.assertEqual(audit["counts"]["runtime_status"]["execution_failed"], 4)
        for code in (124, 1, -9):
            collection, files = self.fixture.collection({1: "execution_failed"})
            collection["batches"][1]["exit_code"] = code
            self.fixture.adapt(collection, files)
        for change in (
            {"exit_code": 0},
            {"exit_code": 2},
            {"exit_code": None},
            {"exit_code": True},
            {"result_sha256": "0" * 64},
        ):
            with self.subTest(change=change):
                collection, files = self.fixture.collection({1: "execution_failed"})
                collection["batches"][1].update(change)
                with self.assertRaisesRegex(ValueError, "need a null result"):
                    self.fixture.adapt(collection, files)
        # Identity-invalid completed JSON never becomes an execution failure.
        self.reject("model identity", lambda r: r["model"].update(id="other"))

    def test_collection_bytes(self):
        collection, files = self.fixture.collection()
        raw = json.dumps(collection).encode()
        arguments = (self.fixture.queries, self.fixture.manifest, self.fixture.plan_sha)
        with self.assertRaisesRegex(ValueError, "Collection file SHA-256 mismatch"):
            a.adapt(*arguments, raw, "0" * 64, files.get)
        with self.assertRaisesRegex(ValueError, "lowercase"):
            a.adapt(*arguments, raw, "bad", files.get)
        with mock.patch.object(a, "MAX_COLLECTION_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "exceeds 10 bytes"):
                a.adapt(*arguments, raw, n.digest(raw), files.get)
        duplicate = b'{"schema_version":1,"schema_version":2}'
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            a.adapt(*arguments, duplicate, n.digest(duplicate), files.get)

    def test_sites(self):
        self.fixture = Fixture(limits=dict(CEILINGS))
        result = self.fixture.result(0)
        ok = find_site(result, "ok")
        empty = find_site(result, "no_candidate")

        def at(position, *keys, **values):
            def mutate(r):
                site_path(r, *position, *keys).update(values)

            return mutate

        def set_site(position, key, value):
            def mutate(r):
                site_path(r, *position)[key] = value

            return mutate

        def selected(key, value):
            def mutate(r):
                site_path(r, *ok, "selected")[key] = value

            return mutate

        def scope(r):
            site = site_path(r, ok[0], 1)
            site["site_id"] = "psite1:" + "f" * 32 + site["site_id"][39:]
            if site["selected"]:
                d, s = (
                    site["selected"]["discriminator_length"],
                    site["selected"]["spacer_length"],
                )
                site["selected"]["state_id"] = f"{site['site_id']}:d{d}s{s}"

        cases = [
            ("site needs", set_site(ok, "extra", 1)),
            ("planned base", set_site(ok, "site_id", None)),
            ("planned base", set_site(ok, "site_id", "psite1:x:+:1")),
            ("planned base", set_site(ok, "site_id", "psite1:" + "a" * 32 + ":+:0")),
            ("one scope", scope),
            ("Site strand", set_site(ok, "strand", "-")),
            ("Site TSS", at(ok, "tss", oriented_base=-1)),
            ("genomic point", at(ok, "genomic", base=-1)),
            ("genomic point", at(ok, "genomic", strand="?")),
            ("Site context", at(ok, "context", available_downstream=0)),
            ("state_count", set_site(ok, "state_count", 29.0)),
            ("state_count", set_site(empty, "state_count", 1)),
            ("complete_state_set", set_site(ok, "complete_state_set", None)),
            ("attempted must be", set_site(ok, "attempted", 1)),
            ("ok sites need", set_site(ok, "reason", "insufficient_context")),
            ("ok sites need", set_site(ok, "attempted", False)),
            (
                "ok sites need",
                lambda r: site_path(r, *empty).update(status="ok", reason=None),
            ),
            ("tie_count", set_site(ok, "tie_count", 0)),
            ("tie_count", set_site(ok, "tie_count", 31)),
            ("tie_count", set_site(ok, "tie_count", True)),
            ("selected state needs", selected("elements", {})),
            ("discriminator_length", selected("discriminator_length", 11)),
            ("spacer_length", selected("spacer_length", 14)),
            ("state_id", selected("state_id", "x")),
            (
                "terms needs",
                lambda r: site_path(r, *ok, "selected", "terms").pop("total"),
            ),
            (
                "finite",
                lambda r: site_path(r, *ok, "selected", "terms").update(total="1"),
            ),
            ("finite", selected("log_relative_transcription_score", None)),
            ("score_status", selected("score_status", "clipped")),
            ("score_status", selected("relative_transcription_score", None)),
            ("score_status", selected("score_status", "overflow")),
            (
                "local intervals",
                lambda r: site_path(r, *ok, "selected", "intervals").update(gap=[0, 1]),
            ),
            (
                "oriented intervals",
                lambda r: site_path(r, *ok, "selected", "oriented_intervals").pop(
                    "itr"
                ),
            ),
            (
                "genomic intervals",
                lambda r: site_path(r, *ok, "selected", "genomic_intervals").update(
                    UP=[[0, 24]]
                ),
            ),
            ("Non-ok sites need", set_site(empty, "tie_count", 1)),
            ("Non-ok sites need", set_site(empty, "selected", {})),
            ("no_candidate sites need", set_site(empty, "reason", "deadline_exceeded")),
            ("no_candidate sites need", set_site(empty, "attempted", False)),
            (
                "Invalid site status",
                lambda r: site_path(r, *empty).update(
                    status="failed", reason="nonfinite_arithmetic"
                ),
            ),
            ("score_status", selected("relative_transcription_score", 0.0)),
            ("score_status", selected("relative_transcription_score", -1.0)),
            ("score_status", selected("relative_transcription_score", 5e-324)),
            ("score_status", selected("relative_transcription_score", True)),
            ("Invalid site status", set_site(empty, "status", "skipped")),
            (
                "Invalid site status",
                lambda r: site_path(r, *empty).update(
                    status="failed", reason="insufficient_context"
                ),
            ),
            (
                "Invalid site status",
                lambda r: site_path(r, *empty).update(
                    status="failed", reason="nonfinite_arithmetic", attempted=False
                ),
            ),
            (
                "disagrees with its sites",
                lambda r: site_path(r, *empty).update(
                    status="failed", reason="deadline_exceeded"
                ),
            ),
            ("Coverage", lambda r: r["results"][0]["coverage"].update(planned_sites=1)),
            (
                "Coverage",
                lambda r: r["results"][0]["coverage"].update(complete_context=1),
            ),
            ("coverage needs", lambda r: r["results"][0]["coverage"].pop("truncation")),
            ("truncation", lambda r: r["results"][0]["coverage"].update(truncation={})),
        ]
        for message, mutate in cases:
            with self.subTest(message=message):
                self.reject(message, mutate)

    def test_incomplete_state_and_record_status(self):
        # A partial-state site (count < 30) cannot select d=10, s=20.
        self.fixture = Fixture(limits=dict(CEILINGS))
        result = self.fixture.result(0)
        partial = next(
            (r, s)
            for r, record in enumerate(result["results"])
            for s, site in enumerate(record["sites"])
            if site["status"] == "ok" and site["state_count"] < 30
        )

        def mutate(r):
            selected = site_path(r, *partial, "selected")
            selected.update(discriminator_length=10, spacer_length=20)
            selected["state_id"] = site_path(r, *partial, "site_id") + ":d10s20"

        self.reject("lacks complete context", mutate)
        self.reject(
            "Record status", lambda r: r["results"][0].update(status="no_candidate")
        )

    def test_no_candidate_and_failed_records(self):
        fixture = Fixture(queries=empty_range_document())
        collection, files = fixture.collection(
            mutate=lambda r: r["results"][0].update(reasons=[])
        )
        with self.assertRaisesRegex(ValueError, "empty_scan"):
            fixture.adapt(collection, files)
        first = self.fixture.plan["batches"][0]["records"][0]["request_id"]
        deadline = {first: {"deadline_after": 10}}

        def truncation(**values):
            return lambda r: r["results"][0]["coverage"]["truncation"].update(values)

        for message, mutate in (
            ("Truncation reason", truncation(reason="insufficient_context")),
            # Every failed site hit the deadline; nonfinite never occurred.
            ("Truncation reason", truncation(reason="nonfinite_arithmetic")),
            ("Truncation counts", truncation(attempted_sites=9)),
            ("Truncation counts", truncation(planned_sites=1)),
            ("truncation needs", truncation(extra=1)),
            (
                "Coverage truncation",
                lambda r: r["results"][1]["coverage"].update(truncation={}),
            ),
        ):
            with self.subTest(message=message):
                self.reject(message, mutate, behaviors=deadline)

    def test_linear_clipped_no_candidate_record(self):
        # A query whose every planned site lacks context is no_candidate.
        queries = query_document({"lin": (130, "linear")}, width=20)
        target = next(
            i
            for i, q in enumerate(queries["queries"])
            if all(
                not brute_states(len(q["sequence"]), f)
                for f in range(*q["candidate_local_range"])
            )
        )
        fixture = Fixture(queries=queries, limits=dict(CEILINGS))
        self.assertEqual(len(fixture.plan["batches"]), 1)
        scores, _ = fixture.adapt(*fixture.collection())
        row = scores["results"][target]
        self.assertEqual(
            (row["status"], row["runtime_status"]), ("no_candidate", "no_candidate")
        )
        self.assertEqual({c["status"] for c in row["candidates"]}, {"no_candidate"})
        collection, files = fixture.collection(
            mutate=lambda r: r["results"][target].update(reasons=[])
        )
        with self.assertRaisesRegex(ValueError, "insufficient_context"):
            fixture.adapt(collection, files)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name)
        self.fixture = Fixture()
        (self.path / "model.json").write_text(json.dumps(MODEL, indent=2))
        (self.path / "limits.json").write_text(json.dumps(RUNTIME_LIMITS))
        queries = n.canonical_bytes(self.fixture.queries)
        (self.path / "queries.json").write_bytes(queries)
        self.queries_sha = n.digest(queries)

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = a.main([str(item) for item in argv])
        return code, out.getvalue(), err.getvalue()

    def manifest_argv(self, output="manifest.json", **overrides):
        values = {
            **{
                key.replace("_", "-"): value
                for key, value in IDENTITY.items()
                if key != "expected_model"
            },
            "calibration": "ecoli_mg1655",
            "host-name": HOST["name"],
            **{
                f"max-{key.replace('_', '-')}": value for key, value in CEILINGS.items()
            },
            "max-records-per-batch": 4,
            "seconds-per-record": "30",
            "seconds-per-batch": "300",
            "expected-model": self.path / "model.json",
            "runtime-limits": self.path / "limits.json",
            "cli-calibration": "none",
            "cli-states": "none",
        }
        values.update(overrides)
        argv = ["manifest", self.path / output]
        for key, value in values.items():
            if value is True:
                argv.append(f"--{key}")
            elif value is not None:
                argv += [f"--{key}", value]
        return argv

    def write_manifest(self):
        code, out, err = self.run_main(self.manifest_argv())
        self.assertEqual((code, err), (0, ""))
        raw = (self.path / "manifest.json").read_bytes()
        self.assertEqual(json.loads(out)["output_sha256"], n.digest(raw))
        self.assertEqual(json.loads(raw), self.fixture.manifest)
        return n.digest(raw)

    def prepare(self):
        manifest_sha = self.write_manifest()
        code, out, err = self.run_main(
            [
                "prepare",
                self.path / "queries.json",
                self.path / "manifest.json",
                self.path / "plan.json",
                "--queries-sha256",
                self.queries_sha,
                "--manifest-sha256",
                manifest_sha,
            ]
        )
        self.assertEqual((code, err), (0, ""))
        plan_sha = json.loads(out)["output_sha256"]
        self.assertEqual(plan_sha, self.fixture.plan_sha)
        self.assertEqual(n.digest((self.path / "plan.json").read_bytes()), plan_sha)
        return manifest_sha, plan_sha

    def test_manifest_command(self):
        self.write_manifest()
        code, _, err = self.run_main(self.manifest_argv())
        self.assertEqual(code, 1)
        self.assertIn("exists", err)
        code, _, err = self.run_main(
            self.manifest_argv(
                "b.json", **{"host-taxon-id": "5", "host-name": None, "no-host": True}
            )
        )
        self.assertIn("requires --host-name", err)
        code, _, err = self.run_main(
            self.manifest_argv("c.json", **{"candidate-commit": "x"})
        )
        self.assertIn("40-hex", err)
        code, _, err = self.run_main(
            self.manifest_argv(
                "d.json",
                **{"seconds-per-batch": "0.5", "no-host": True, "host-name": None},
            )
        )
        self.assertEqual(code, 0)
        document = json.loads((self.path / "d.json").read_bytes())
        self.assertEqual(document["settings"]["seconds_per_batch"], 0.5)
        self.assertIsNone(document["settings"]["host"])
        code, _, err = self.run_main(
            self.manifest_argv("e.json", **{"host-taxon-id": "5"})
        )
        self.assertEqual(
            json.loads((self.path / "e.json").read_bytes())["settings"]["host"][
                "taxon_id"
            ],
            5,
        )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            a.main([str(x) for x in self.manifest_argv("f.json", **{"no-host": True})])

    def test_prepare_export_and_adapt(self):
        manifest_sha, plan_sha = self.prepare()
        code, _, err = self.run_main(
            [
                "prepare",
                self.path / "queries.json",
                self.path / "manifest.json",
                self.path / "plan.json",
                "--queries-sha256",
                self.queries_sha,
                "--manifest-sha256",
                manifest_sha,
            ]
        )
        self.assertEqual(code, 1)
        self.assertIn("exists", err)
        code, out, _ = self.run_main(
            [
                "export-request",
                self.path / "plan.json",
                1,
                self.path / "req.json",
                "--plan-sha256",
                plan_sha,
            ]
        )
        self.assertEqual(code, 0)
        raw = (self.path / "req.json").read_bytes()
        self.assertEqual(raw, a.plan_request_bytes(self.fixture.plan, 1))
        self.assertEqual(json.loads(out)["request_sha256"], n.digest(raw))
        code, _, err = self.run_main(
            [
                "export-request",
                self.path / "plan.json",
                9,
                self.path / "r9.json",
                "--plan-sha256",
                plan_sha,
            ]
        )
        self.assertIn("batch index", err)
        code, _, err = self.run_main(
            [
                "export-request",
                self.path / "plan.json",
                0,
                self.path / "r0.json",
                "--plan-sha256",
                "0" * 64,
            ]
        )
        self.assertIn("Plan file SHA-256 mismatch", err)

        first = self.fixture.plan["batches"][0]["records"][0]["request_id"]
        collection, files = self.fixture.collection(
            {2: "not_run"}, {first: {"deadline_after": 3}}
        )
        (self.path / "collection.json").write_text(json.dumps(collection, indent=2))
        collection_sha = n.digest((self.path / "collection.json").read_bytes())
        results = []
        for index, raw_result in enumerate(files.values()):
            (self.path / f"result{index}.json").write_bytes(raw_result)
            results += ["--result", self.path / f"result{index}.json"]

        def adapt_argv(
            scores="scores.json", audit="audit.json", extra=(), sha=collection_sha
        ):
            return [
                "adapt",
                self.path / "queries.json",
                self.path / "manifest.json",
                self.path / "collection.json",
                self.path / scores,
                self.path / audit,
                "--queries-sha256",
                self.queries_sha,
                "--manifest-sha256",
                manifest_sha,
                "--plan-sha256",
                plan_sha,
                "--collection-sha256",
                sha,
                *extra,
            ]

        code, _, err = self.run_main(adapt_argv(extra=results[:2]))
        self.assertIn("No supplied result file", err)
        (self.path / "extra.json").write_bytes(b"{}")
        code, _, err = self.run_main(
            adapt_argv(extra=[*results, "--result", self.path / "extra.json"])
        )
        self.assertIn("not all bound", err)
        code, _, err = self.run_main(adapt_argv(extra=[*results, *results[:2]]))
        self.assertIn("Duplicate result file", err)
        code, _, err = self.run_main(adapt_argv("same.json", "same.json", results))
        self.assertIn("must differ", err)
        code, _, err = self.run_main(adapt_argv(extra=results, sha="0" * 64))
        self.assertIn("Collection file SHA-256 mismatch", err)
        self.assertFalse((self.path / "scores.json").exists())
        code, out, err = self.run_main(adapt_argv(extra=results))
        self.assertEqual((code, err), (0, ""))
        hashes = json.loads(out)
        for name in ("scores", "audit"):
            path = self.path / f"{name}.json"
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(hashes[f"{name}_sha256"], n.digest(path.read_bytes()))
        expected = a.adapt(
            self.fixture.queries,
            self.fixture.manifest,
            plan_sha,
            (self.path / "collection.json").read_bytes(),
            collection_sha,
            files.__getitem__,
        )
        self.assertEqual(
            (self.path / "scores.json").read_bytes(), n.canonical_bytes(expected[0])
        )
        scores_bytes = (self.path / "scores.json").read_bytes()
        code, _, err = self.run_main(adapt_argv(extra=results))
        self.assertIn("already exists", err)
        self.assertEqual((self.path / "scores.json").read_bytes(), scores_bytes)
        # A failed second write removes the first output.
        real = n.write_exclusive
        calls = []

        def flaky(path, value, mode):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("disk full")
            real(path, value, mode)

        with mock.patch.object(a, "write_exclusive", flaky):
            code, _, err = self.run_main(adapt_argv("s2.json", "a2.json", results))
        self.assertEqual(code, 1)
        self.assertIn("disk full", err)
        self.assertFalse((self.path / "s2.json").exists())
        # Metrics consume the adapted v2 scores through the unchanged CLI path.
        self.assertEqual(json.loads(scores_bytes)["schema_version"], m.SCORE_SCHEMA_V2)

    def test_noncanonical_and_mismatched_inputs(self):
        manifest_sha = self.write_manifest()
        (self.path / "pretty.json").write_text(
            json.dumps(self.fixture.queries, indent=1)
        )
        pretty_sha = n.digest((self.path / "pretty.json").read_bytes())
        for queries, sha, message in (
            ("pretty.json", pretty_sha, "not canonical"),
            ("queries.json", "0" * 64, "Query document file SHA-256 mismatch"),
            ("queries.json", "bad", "lowercase"),
            ("missing.json", self.queries_sha, "No such file"),
        ):
            with self.subTest(message=message):
                code, _, err = self.run_main(
                    [
                        "prepare",
                        self.path / queries,
                        self.path / "manifest.json",
                        self.path / "p.json",
                        "--queries-sha256",
                        sha,
                        "--manifest-sha256",
                        manifest_sha,
                    ]
                )
                self.assertEqual(code, 1)
                self.assertIn(message, err)
        broken = dict(self.fixture.queries, queries=[{"query_id": "x"}])
        raw = n.canonical_bytes(rehash(broken))
        (self.path / "broken.json").write_bytes(raw)
        code, _, err = self.run_main(
            [
                "prepare",
                self.path / "broken.json",
                self.path / "manifest.json",
                self.path / "p.json",
                "--queries-sha256",
                n.digest(raw),
                "--manifest-sha256",
                manifest_sha,
            ]
        )
        self.assertIn("query needs", err)

    def test_module_entry_point(self):
        with (
            mock.patch.object(
                sys,
                "argv",
                [
                    "runtime_adapter",
                    "export-request",
                    "missing",
                    "0",
                    "out",
                    "--plan-sha256",
                    "0" * 64,
                ],
            ),
            contextlib.redirect_stderr(io.StringIO()),
            warnings.catch_warnings(),
        ):
            warnings.simplefilter("ignore", RuntimeWarning)
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module(
                    "benchmarks.promoter.runtime_adapter", run_name="__main__"
                )
        self.assertEqual(raised.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
