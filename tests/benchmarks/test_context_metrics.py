"""Synthetic paired transcript-context summaries with hand-computed expectations."""

import copy
import hashlib
import io
import json
import runpy
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema

from benchmarks.promoter.native_inputs import canonical_bytes, document_sha256
from benchmarks.rbs import context_metrics as metrics
from benchmarks.rbs import context_panel

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "a" * 40
MODELS = {
    "historical": "v1-rnastructure-6.6-reconstruction-1",
    "context2017": "context2017-rnastructure-6.6-reconstruction-1",
}
BACKEND = {"id": "rnastructure-6.6-traceback-2", "fold_sha256": "b" * 64}
SETTINGS = {
    "mode": "supplied_start",
    "execution": {
        "implementation_version": "0.4.0rc1",
        "backend": BACKEND,
        "seconds_per_record": 60,
        "seconds_per_batch": 3600,
    },
}
SOURCES = ("src-0", "src-1", "src-2", "src-3")
START = 20
AUDIT_MRNA, AUDIT_COFOLD = metrics.AUDIT_TERMS


def sha(value):
    return hashlib.sha256(
        value.encode() if isinstance(value, str) else value
    ).hexdigest()


def envelope():
    """Four ordinary loci plus excluded aTSS and locus-free gTSS rows."""
    genome = "ACGT" * 100
    rows = [
        {
            "id": source,
            "genome_id": "g",
            "strand": "+",
            "tss_type": "gTSS",
            "source_locus_tag": f"locus-{i}",
            "tss_zero_based": 100,
            "cds_start_zero_based": 140,
            "source_start_zero_based": 150,
            "source_start_distance_nt": 50,
            "leader_length_nt": 40,
            "source_current_start_delta_nt": 0,
            "conditions": {"control": [1]},
            "warnings": [],
            "origin_crossing": False,
            "mapping_status": "synthetic",
            "transcript_start_evidence": "synthetic TSS",
            "translation_start_evidence": "synthetic annotation",
            "host": "synthetic",
            "anti_sd": "ACCUCCUUU",
            "anti_sd_provenance": "synthetic tail",
        }
        for i, source in enumerate(SOURCES)
    ]
    rows += [
        {"id": "antisense", "tss_type": "aTSS"},
        {"id": "no-locus", "tss_type": "gTSS"},
    ]
    return {
        "schema_version": "native-rbs-evidence-1",
        "genomes": {
            "g": {
                "sequence": genome,
                "sequence_sha256": sha(genome),
                "accession": "g",
                "assembly": "synthetic-v1",
                "annotation": "synthetic-v1",
                "topology": "linear",
            }
        },
        "records": rows,
    }


PANEL = context_panel.build_panel(envelope(), "f" * 64)
PANEL_RAW = canonical_bytes(PANEL)
PANEL_SHA = sha(PANEL_RAW)
RECORDS = {record["id"]: record for record in PANEL["records"]}


def rna(tag):
    """A distinct 20-nt leader per tag, then AUG and a short coding stretch."""
    leader = "".join("ACGU"[int(c, 16) % 4] for c in sha(tag)[:START])
    return leader + "AUG" + "GCU" * 5


def context(tag):
    sequence = rna(tag)
    genome = PANEL["genomes"]["g"]
    return {
        "genome": {key: genome[key] for key in metrics.GENOME_KEYS},
        "sequence": sequence,
        "sequence_sha256": sha(sequence),
        "sequence_alphabet": "RNA",
        "start": START,
        "path": {
            "contig_length": 400,
            "first": 100,
            "length": len(sequence),
            "strand": "+",
            "circular": False,
        },
        "genomic_segments": [{"start": 100, "end": 100 + len(sequence), "strand": "+"}],
        "genomic_start_segments": [{"start": 120, "end": 123, "strand": "+"}],
    }


def request(prepared):
    """The public core request restating a prepared context and fixed scenario."""
    return {
        "id": "synthetic",
        "oriented_sequence": prepared["sequence"],
        "oriented_sha256": prepared["sequence_sha256"],
        "strand": "+",
        "start_positions": [prepared["start"]],
        "temperature_c": 37.0,
        "anti_sd": "ACCUCCUUU",
        "host": "synthetic",
    }


def ok_row(identity, model, log_tir=0.0, energy=-1.0, audit=(None, None), **opts):
    """Every energy term is energy + its index, so paired offsets cancel."""
    version = opts.get("version", metrics.PROFILE_SCHEMAS[profile_of(model)])
    prepared = context(opts.get("tag", identity))
    terms = metrics.TERMS_BY_SCHEMA[version]
    energies = {term: energy + i for i, term in enumerate(terms)}
    energies.update(
        units="kcal/mol", **dict(zip(metrics.AUDIT_TERMS, audit, strict=True))
    )
    site = {
        "status": "ok",
        "reason": None,
        "oriented_start": START,
        "log_tir": log_tir,
        "tir": 2.0**log_tir,
        "energies": energies,
    }
    return {
        "id": identity,
        "status": "ok",
        "reason": None,
        "context": prepared,
        "prediction": {
            **core(identity, model, "ok", None, [site], request(prepared)),
            "schema_version": version,
        },
        "genomic_sites": [
            {
                "oriented_start": START,
                "start_point": 120,
                "status": "ok",
                "rank_among_successful_candidates": None,
                "start_codon": [{"start": 120, "end": 123, "strand": "+"}],
                "binding_interval": None,
                "standby_interval": None,
                "coding_footprint": None,
                "window": [],
            }
        ],
        "warnings": [],
        "evidence": copy.deepcopy(RECORDS[identity]),
    }


def profile_of(model):
    return next(name for name, value in MODELS.items() if value == model)


def core(identity, model, status, reason, sites, core_request):
    return {
        "schema_version": metrics.PROFILE_SCHEMAS[profile_of(model)],
        "id": identity,
        "status": status,
        "reason": reason,
        "sites": sites,
        "warnings": [],
        "model": {
            "id": model,
            "source_commit": "c" * 40,
            "parameters": {},
            "implementation_version": "0.4.0rc1",
        },
        "backend": copy.deepcopy(BACKEND),
        "input": core_request,
        "prediction_id": "e" * 64,
    }


def other_row(identity, model, status, reason, prepared=False, prediction=False):
    """A prediction restates its request only when a context was prepared."""
    prepared = context(identity) if prepared else None
    core_request = None if prepared is None else request(prepared)
    return {
        "id": identity,
        "status": status,
        "reason": reason,
        "context": prepared,
        "prediction": (
            core(identity, model, status, reason, [], core_request)
            if prediction
            else None
        ),
        "genomic_sites": [],
        "warnings": ["synthetic"],
        "evidence": copy.deepcopy(RECORDS[identity]),
    }


def output(model, rows):
    """A native result; unspecified scenarios succeed with distinct contexts."""
    results = [
        rows[record["id"]](record["id"], model)
        if record["id"] in rows
        else ok_row(record["id"], model)
        for record in PANEL["records"]
    ]
    return {
        "schema_version": "native-rbs-result-1",
        "batch_id": "d" * 64,
        "mode": "supplied_start",
        "model_id": model,
        "execution": copy.deepcopy(SETTINGS["execution"]),
        "coordinate_space": metrics.COORDINATE_SPACE,
        "task_scope": metrics.TASK_SCOPE,
        "results": results,
    }


def ok(log_tir, energy, audit=(None, None), **opts):
    return lambda identity, model: ok_row(
        identity, model, log_tir, energy, audit, **opts
    )


def other(status, reason, **opts):
    return lambda identity, model: other_row(identity, model, status, reason, **opts)


def main_rows():
    """Current: ties, equal contexts, both signs. Historical: partial failures."""
    return {
        "src-0:current:measured_tss": ok(1.0, -10.0, (-1.0, None)),
        "src-0:current:genomic_flank": ok(0.5, -12.0, (-2.0, None)),
        "src-1:current:measured_tss": ok(2.0, -5.0, tag="same"),
        "src-1:current:genomic_flank": ok(2.0, -5.0, (-1.0, None), tag="same"),
        "src-2:current:measured_tss": ok(2.0, -8.0, (-3.0, None)),
        "src-2:current:genomic_flank": ok(3.0, -6.0),
        "src-3:current:measured_tss": ok(-1.0, -2.0, (-4.0, None)),
        "src-3:current:genomic_flank": ok(-1.5, -2.5, (-4.0, None)),
        "src-0:historical:measured_tss": other(
            "unsupported", "leaderless", prepared=True, prediction=True
        ),
        "src-0:historical:genomic_flank": ok(1.0, -3.0),
        "src-1:historical:genomic_flank": other("failed", None),
        "src-2:historical:measured_tss": other(
            "no_candidate", "no interstrand candidate", prepared=True
        ),
        "src-3:historical:measured_tss": ok(0.25, -4.0),
        "src-3:historical:genomic_flank": ok(0.75, -3.0),
    }


def collection(runs=None):
    runs = runs or {
        "historical": {
            "expected_model_id": MODELS["historical"],
            "status": "not_run",
            "reason": "folding slot unavailable",
            "output": None,
        },
        "context2017": {
            "expected_model_id": MODELS["context2017"],
            "status": "completed",
            "reason": None,
            "output": output(MODELS["context2017"], main_rows()),
        },
    }
    return {
        "schema_version": "rbs-context-collection-1",
        "panel_sha256": PANEL_SHA,
        "candidate_commit": COMMIT,
        "settings": copy.deepcopy(SETTINGS),
        "runs": runs,
    }


def run(value, panel_raw=PANEL_RAW, commit=COMMIT, models=MODELS):
    raw = canonical_bytes(value)
    return metrics.summarize(panel_raw, sha(panel_raw), raw, sha(raw), commit, models)


def stats(n, changed, low, q25, median, q75, high):
    return {
        "n": n,
        "changed": changed,
        "min": low,
        "q25": q25,
        "median": median,
        "q75": q75,
        "max": high,
    }


EMPTY = stats(0, 0, None, None, None, None, None)


def status_counts(**values):
    counts = {
        status: {"rows": 0, "with_prepared_context": 0}
        for status in metrics.STATUSES + (metrics.NOT_COLLECTED,)
    }
    for status, (rows, prepared) in values.items():
        counts[status] = {"rows": rows, "with_prepared_context": prepared}
    return counts


class SummaryArithmeticTests(unittest.TestCase):
    def test_quantiles_midranks_and_tolerance(self):
        self.assertEqual(metrics.summary([]), EMPTY)
        self.assertEqual(metrics.summary([3.0]), stats(1, 1, 3.0, 3.0, 3.0, 3.0, 3.0))
        self.assertEqual(
            metrics.summary([4.0, 1.0, 2.0, 3.0, 0.0]),
            stats(5, 4, 0.0, 1.0, 2.0, 3.0, 4.0),
        )
        self.assertEqual(metrics.summary([1e-13, -2e-12])["changed"], 1)
        self.assertEqual(metrics.midranks([]), [])
        self.assertEqual(metrics.midranks([1.0, 1.0, 1.0]), [2.0, 2.0, 2.0])
        self.assertEqual(metrics.midranks([3.0, 1.0, 3.0, 2.0]), [1.5, 4.0, 1.5, 3.0])


class ContextMetricsTests(unittest.TestCase):
    def test_fixtures_follow_public_schemas(self):
        schemas = ROOT / "schemas"
        native = json.loads((schemas / "native-rbs-result-1.schema.json").read_text())
        evidence = json.loads(
            (schemas / "native-rbs-evidence-1.schema.json").read_text()
        )
        jsonschema.validate(PANEL, evidence)
        jsonschema.validate(output(MODELS["context2017"], main_rows()), native)

    def test_partial_failures_ties_equal_contexts_and_whole_profile_not_run(self):
        report = run(collection())
        self.assertEqual(report["schema_version"], "rbs-context-metrics-1")
        self.assertEqual(report["panel"]["sha256"], PANEL_SHA)
        self.assertEqual(report["panel"]["counts"]["input_scenarios"], 16)
        self.assertEqual(report["collection"]["candidate_commit"], COMMIT)
        self.assertEqual(
            report["collection"]["settings_sha256"], document_sha256(SETTINGS)
        )
        refined = report["profiles"]["context2017"]
        self.assertEqual(refined["run_status"], "completed")
        self.assertEqual(
            (
                refined["expected_prediction_schema_version"],
                refined["observed_prediction_schema_version"],
            ),
            ("1.1", "1.1"),
        )
        self.assertEqual(
            refined["output_sha256"],
            document_sha256(collection()["runs"]["context2017"]["output"]),
        )
        self.assertEqual(
            (refined["requested_scenarios"], refined["collected_scenarios"]), (16, 16)
        )
        self.assertEqual(
            refined["repeated_contexts"],
            {
                "rows_with_prepared_context": 15,
                "distinct_prepared_contexts": 14,
                "repeated_prepared_contexts": 1,
                "rows_in_repeated_prepared_contexts": 2,
            },
        )
        current = refined["anchors"]["current"]
        self.assertEqual(
            current["pairs"],
            {
                "eligible": 4,
                "ineligible": 0,
                "identical_prepared_context": 1,
                "status_combinations": [
                    {"measured_tss": "ok", "genomic_flank": "ok", "count": 4}
                ],
            },
        )
        # log_tir changes [0.5, 0, -1, 0.5]; energies [2, 0, -2, 0.5].
        self.assertEqual(
            current["changes"]["log_tir"], stats(4, 3, -1.0, -0.25, 0.25, 0.5, 0.5)
        )
        energy = stats(4, 3, -2.0, -0.5, 0.25, 0.875, 2.0)
        self.assertEqual(
            set(current["changes"]), {"log_tir", *metrics.TERMS_BY_SCHEMA["1.1"]}
        )
        for term in metrics.TERMS_BY_SCHEMA["1.1"]:
            self.assertEqual(current["changes"][term], energy, term)
        self.assertEqual(
            current["audit_changes"],
            {
                AUDIT_MRNA: {
                    "missing_pairs": 2,
                    **stats(2, 1, 0.0, 0.25, 0.5, 0.75, 1.0),
                },
                AUDIT_COFOLD: {"missing_pairs": 4, **EMPTY},
            },
        )
        # Measured ranks [3, 1.5, 1.5, 4]; flank ranks [3, 2, 1, 4].
        self.assertEqual(
            current["log_tir_rank_changes"],
            stats(4, 2, -0.5, -0.125, 0.0, 0.125, 0.5),
        )
        self.assertEqual(
            current["coverage"]["measured_tss"],
            {"requested": 4, "statuses": status_counts(ok=(4, 4)), "reasons": []},
        )
        historical = refined["anchors"]["historical"]
        self.assertEqual(
            historical["pairs"],
            {
                "eligible": 1,
                "ineligible": 3,
                "identical_prepared_context": 0,
                "status_combinations": [
                    {"measured_tss": "no_candidate", "genomic_flank": "ok", "count": 1},
                    {"measured_tss": "ok", "genomic_flank": "failed", "count": 1},
                    {"measured_tss": "ok", "genomic_flank": "ok", "count": 1},
                    {"measured_tss": "unsupported", "genomic_flank": "ok", "count": 1},
                ],
            },
        )
        self.assertEqual(
            historical["changes"]["log_tir"], stats(1, 1, -0.5, -0.5, -0.5, -0.5, -0.5)
        )
        self.assertEqual(
            historical["changes"]["dG_total"],
            stats(1, 1, -1.0, -1.0, -1.0, -1.0, -1.0),
        )
        self.assertEqual(
            historical["log_tir_rank_changes"], stats(1, 0, 0.0, 0.0, 0.0, 0.0, 0.0)
        )
        self.assertEqual(
            historical["audit_changes"][AUDIT_MRNA], {"missing_pairs": 1, **EMPTY}
        )
        self.assertEqual(
            historical["coverage"],
            {
                "measured_tss": {
                    "requested": 4,
                    "statuses": status_counts(
                        ok=(2, 2), unsupported=(1, 1), no_candidate=(1, 1)
                    ),
                    "reasons": [
                        {
                            "status": "no_candidate",
                            "reason_present": True,
                            "count": 1,
                        },
                        {
                            "status": "unsupported",
                            "reason_present": True,
                            "count": 1,
                        },
                    ],
                },
                "genomic_flank": {
                    "requested": 4,
                    "statuses": status_counts(ok=(3, 3), failed=(1, 0)),
                    "reasons": [
                        {"status": "failed", "reason_present": False, "count": 1}
                    ],
                },
            },
        )
        skipped = report["profiles"]["historical"]
        self.assertEqual(
            {
                key: skipped[key]
                for key in ("run_status", "run_reason_present", "batch_id")
            },
            {
                "run_status": "not_run",
                "run_reason_present": True,
                "batch_id": None,
            },
        )
        self.assertEqual(
            (skipped["requested_scenarios"], skipped["collected_scenarios"]), (16, 0)
        )
        self.assertEqual(skipped["expected_prediction_schema_version"], "1.0")
        self.assertIsNone(skipped["observed_prediction_schema_version"])
        self.assertEqual(skipped["repeated_contexts"]["rows_with_prepared_context"], 0)
        for anchor in metrics.ANCHORS:
            summary = skipped["anchors"][anchor]
            self.assertEqual(
                summary["pairs"]["status_combinations"],
                [
                    {
                        "measured_tss": "not_collected",
                        "genomic_flank": "not_collected",
                        "count": 4,
                    }
                ],
            )
            self.assertEqual(
                summary["coverage"]["genomic_flank"]["statuses"],
                status_counts(not_collected=(4, 0)),
            )
            self.assertEqual(
                set(summary["changes"]), {"log_tir", *metrics.ENERGY_TERMS}
            )
            self.assertTrue(all(v == EMPTY for v in summary["changes"].values()))
        text = json.dumps(report)
        self.assertNotIn("src-", text)  # No per-case identities or scores.

    def test_all_tied_schema_1_0_profile_and_completed_run_without_pairs(self):
        tied = {f"{source}:current:measured_tss": ok(1.0, -1.0) for source in SOURCES}
        for value, source in enumerate(SOURCES, start=1):
            tied[f"{source}:current:genomic_flank"] = ok(float(value), -1.0)
            for context_name in metrics.CONTEXTS:
                tied[f"{source}:historical:{context_name}"] = other("failed", "timeout")
        runs = {
            "historical": {
                "expected_model_id": MODELS["historical"],
                "status": "completed",
                "reason": None,
                "output": output(MODELS["historical"], tied),
            },
            "context2017": {
                "expected_model_id": MODELS["context2017"],
                "status": "failed",
                "reason": "backend unavailable",
                "output": None,
            },
        }
        report = run(collection(runs))
        profile = report["profiles"]["historical"]
        self.assertEqual(profile["observed_prediction_schema_version"], "1.0")
        current = profile["anchors"]["current"]
        self.assertEqual(
            set(current["changes"]), {"log_tir", *metrics.TERMS_BY_SCHEMA["1.0"]}
        )
        # Measured all tie at 2.5; flank ranks [4, 3, 2, 1].
        self.assertEqual(
            current["log_tir_rank_changes"],
            stats(4, 4, -1.5, -0.75, 0.0, 0.75, 1.5),
        )
        self.assertEqual(current["changes"]["dG_total"]["changed"], 0)
        empty = profile["anchors"]["historical"]
        self.assertEqual(empty["pairs"]["eligible"], 0)
        self.assertEqual(empty["log_tir_rank_changes"], EMPTY)
        self.assertEqual(
            empty["coverage"]["measured_tss"]["reasons"],
            [{"status": "failed", "reason_present": True, "count": 4}],
        )
        self.assertEqual(report["profiles"]["context2017"]["run_status"], "failed")

    def test_completed_run_without_successes_keeps_expected_term_roster(self):
        rows = {
            record_id: other("unsupported", "unresolved start") for record_id in RECORDS
        }
        value = collection()
        value["runs"]["context2017"]["output"] = output(MODELS["context2017"], rows)
        profile = run(value)["profiles"]["context2017"]
        self.assertEqual(profile["expected_prediction_schema_version"], "1.1")
        self.assertIsNone(profile["observed_prediction_schema_version"])
        self.assertEqual(profile["collected_scenarios"], 16)
        changes = profile["anchors"]["current"]["changes"]
        self.assertEqual(set(changes), {"log_tir", *metrics.TERMS_BY_SCHEMA["1.1"]})
        self.assertTrue(all(value == EMPTY for value in changes.values()))

    def test_unsuccessful_prediction_without_core_request_is_retained(self):
        value = collection()
        replace_row(
            "src-0:historical:measured_tss",
            lambda i, m: {
                **other_row(i, m, "unsupported", "leaderless", True, True),
                "prediction": core(i, m, "unsupported", "leaderless", [], None),
            },
        )(value)
        counts = run(value)["profiles"]["context2017"]["anchors"]["historical"]
        statuses = counts["coverage"]["measured_tss"]["statuses"]
        self.assertEqual(
            statuses["unsupported"], {"rows": 1, "with_prepared_context": 1}
        )

    def test_raw_reasons_never_reach_the_aggregate_report(self):
        private = (
            "failed for private source src-1 with residual 123",
            "context ACGUACGUACGUACGU log_tir 4.5 for locus-2",
        )
        value = collection()
        replace_row("src-1:historical:genomic_flank", other("failed", private[0]))(
            value
        )
        replace_row(
            "src-2:historical:measured_tss",
            other("no_candidate", private[1], prepared=True, prediction=True),
        )(value)
        value["runs"]["historical"]["reason"] = "not run for src-3 residual 0.5"
        report = run(value)
        text = json.dumps(report)
        for reason in private + ("not run for src-3 residual 0.5",):
            self.assertNotIn(reason, text)
            self.assertNotIn(sha(reason), text)
        for fragment in ("src-", "residual", "locus-", "ACGUACGUACGU"):
            self.assertNotIn(fragment, text)
        self.assertIn("reviewed claims", report["definitions"]["reason_presence"])

    def test_different_private_reasons_share_one_presence_count(self):
        value = collection()
        for index, reason in enumerate(("source-0 failed", "source-1 failed", None)):
            replace_row(
                f"src-{index}:historical:measured_tss", other("failed", reason)
            )(value)
        coverage = run(value)["profiles"]["context2017"]["anchors"]["historical"][
            "coverage"
        ]["measured_tss"]
        self.assertEqual(
            coverage["reasons"],
            [
                {"status": "failed", "reason_present": False, "count": 1},
                {"status": "failed", "reason_present": True, "count": 2},
            ],
        )
        self.assertEqual(coverage["statuses"]["failed"]["rows"], 3)


def panel_case(mutate):
    value = copy.deepcopy(PANEL)
    mutate(value)
    return value


def locus(index):
    return lambda value: value["panel"]["selected_loci"][index]


def set_settings(**changes):
    def mutate(value):
        value["panel"]["settings"].update(changes)
        value["panel"]["settings_sha256"] = document_sha256(value["panel"]["settings"])

    return mutate


def set_counts(**changes):
    return lambda value: value["panel"]["counts"].update(changes)


def set_record(index, **changes):
    return lambda value: value["records"][index].update(changes)


def swap_loci(value):
    loci = value["panel"]["selected_loci"]
    loci[0], loci[1] = loci[1], loci[0]


PANEL_TAMPERING = [
    lambda value: value.pop("panel"),
    lambda value: value["panel"].update(schema_version="x"),
    lambda value: value["panel"].update(source_sha256="F" * 64),
    lambda value: value["panel"].update(tool_sha256=None),
    lambda value: value["panel"].update(settings="x"),
    set_settings(per_stratum=5),
    set_settings(per_stratum=True),
    set_settings(temperature_c=30.0),
    lambda value: value["panel"].update(settings_sha256="0" * 64),
    lambda value: value["panel"].update(interpretation=""),
    set_record(0, source_record_id=""),
    set_record(0, anchor_scenario="other"),
    set_record(0, transcript_context_scenario="other"),
    set_record(0, id="renamed"),
    set_record(0, genome_id="missing"),
    set_record(0, genome_id=["g"]),
    set_record(0, anti_sd="ACCUCCUUA"),
    set_record(0, temperature_c=30.0),
    lambda value: value["records"].pop(),
    lambda value: value["panel"].update(selected_loci=[]),
    lambda value: value["panel"].update(selected_loci={}),
    lambda value: locus(0)(value).update(extra=1),
    lambda value: locus(0)(value).update(stratum="other"),
    lambda value: locus(0)(value).update(selection_key="0" * 64),
    lambda value: locus(0)(value).update(genome_id=["g"]),
    lambda value: locus(0)(value).update(genome_id="missing"),
    lambda value: locus(0)(value).update(source_locus_tag=""),
    swap_loci,
    lambda value: locus(0)(value).update(record_ids=[]),
    lambda value: locus(0)(value).update(record_ids="src-0"),
    lambda value: locus(0)(value).update(record_ids=[1]),
    lambda value: locus(0)(value).update(record_ids=["src-1", "src-0"]),
    lambda value: locus(0)(value).update(record_ids=[locus(1)(value)["record_ids"][0]]),
    lambda value: locus(0)(value).update(record_ids=["absent"]),
    lambda value: value["panel"]["selected_loci"].pop(),
    lambda value: value["panel"]["counts"].pop("source_rows"),
    set_counts(source_rows=-1),
    set_counts(source_rows=True),
    lambda value: value["panel"]["counts"]["loci_by_stratum"].pop("ordinary"),
    lambda value: value["panel"]["counts"]["loci_by_stratum"].update(ordinary=3),
    lambda value: value["panel"]["counts"]["loci_by_stratum"].update(short_leader=1),
    lambda value: value["panel"]["counts"]["loci_by_stratum"].update(ordinary=-1),
    lambda value: value["panel"].update(excluded_without_locus_record_ids="x"),
    lambda value: value["panel"].update(excluded_without_locus_record_ids=[1]),
    lambda value: value["panel"].update(excluded_without_locus_record_ids=["b", "a"]),
    lambda value: value["panel"].update(excluded_without_locus_record_ids=["src-0"]),
    set_counts(gtss_rows_without_locus=0),
    set_counts(selected_loci=3),
    set_counts(input_scenarios=15),
    set_counts(profile_jobs=16),
    set_counts(source_loci=5),
    set_counts(source_gtss_rows=4),
    set_counts(source_rows=4),
]


class PanelBoundaryTests(unittest.TestCase):
    def test_baseline_panel_reconciles(self):
        self.assertEqual(metrics.load_panel(PANEL_RAW, PANEL_SHA), PANEL)

    def test_tampered_panel_identity_and_arithmetic(self):
        for index, mutate in enumerate(PANEL_TAMPERING):
            raw = canonical_bytes(panel_case(mutate))
            with self.subTest(index=index), self.assertRaises(ValueError):
                metrics.load_panel(raw, sha(raw))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            metrics.load_panel(PANEL_RAW, "0" * 64)
        with (
            patch.object(metrics, "MAX_INPUT_SCENARIOS", 15),
            self.assertRaisesRegex(ValueError, "input scenarios"),
        ):
            metrics.load_panel(PANEL_RAW, PANEL_SHA)


def refined(value):
    return value["runs"]["context2017"]


def refined_output(value):
    return refined(value)["output"]


def result(value, identity="src-0:current:measured_tss"):
    return next(r for r in refined_output(value)["results"] if r["id"] == identity)


def prediction(value):
    return result(value)["prediction"]


def site(value):
    return prediction(value)["sites"][0]


def energies(value):
    return site(value)["energies"]


def put(get, **changes):
    return lambda value: get(value).update(changes)


def replace_row(identity, make):
    def mutate(value):
        rows = refined_output(value)["results"]
        index = next(i for i, row in enumerate(rows) if row["id"] == identity)
        rows[index] = make(identity, MODELS["context2017"])

    return mutate


def duplicate_row(value):
    rows = refined_output(value)["results"]
    rows[1] = copy.deepcopy(rows[0])


def mixed_versions(value):
    replace_row("src-0:current:measured_tss", ok(0.0, -1.0, version="1.0"))(value)


def all_refined_as_1_0(value):
    """Every successful context2017 row converted to 1.0 without footprint."""
    for identity in RECORDS:
        row = result(value, identity)
        if row["status"] == "ok":
            row["prediction"]["schema_version"] = "1.0"
            row["prediction"]["sites"][0]["energies"].pop("dG_post_footprint")


def historical_as_1_1(value):
    """A completed historical profile emitting refined 1.1 predictions."""
    value["runs"]["historical"] = {
        "expected_model_id": MODELS["historical"],
        "status": "completed",
        "reason": None,
        "output": output(
            MODELS["historical"],
            {"src-0:current:measured_tss": ok(0.0, -1.0, version="1.1")},
        ),
    }


def core_request(value):
    return prediction(value)["input"]


def failed_request(value):
    return result(value, "src-0:historical:measured_tss")["prediction"]["input"]


def wrong_request(value):
    """The reviewer's combined mismatch on a successful row."""
    prediction(value)["input"] = {
        "oriented_sequence": "A" * 38,
        "oriented_sha256": "0" * 64,
        "strand": "-",
        "start_positions": [0],
        "temperature_c": 0,
        "anti_sd": "AAAAAAAAA",
    }


def unprepared_request(value):
    row = result(value, "src-1:historical:genomic_flank")
    request_copy = copy.deepcopy(core_request(value))
    row["prediction"] = core(
        row["id"], MODELS["context2017"], "failed", None, [], request_copy
    )


COLLECTION_TAMPERING = [
    lambda value: value.update(extra=1),
    lambda value: value.update(schema_version="x"),
    lambda value: value.update(panel_sha256="0" * 64),
    lambda value: value.update(candidate_commit="b" * 40),
    lambda value: value["settings"].update(extra=1),
    lambda value: value["settings"].update(mode="conditional_scan"),
    lambda value: value["settings"]["execution"].pop("backend"),
    lambda value: value["settings"]["execution"].update(implementation_version=""),
    lambda value: value["settings"]["execution"].update(backend={}),
    lambda value: value["settings"]["execution"].update(backend=["x"]),
    lambda value: value["settings"]["execution"].update(seconds_per_record=True),
    lambda value: value["settings"]["execution"].update(seconds_per_record=0),
    lambda value: value["settings"]["execution"].update(seconds_per_record=121),
    lambda value: value["settings"]["execution"].update(seconds_per_batch=3601),
    lambda value: value["runs"].pop("historical"),
    lambda value: value["runs"].update(standby2014={}),
    lambda value: value["runs"]["historical"].update(extra=1),
    lambda value: value["runs"]["historical"].update(expected_model_id="other"),
    put(refined, reason="done"),
    lambda value: value["runs"]["historical"].update(output={}),
    lambda value: value["runs"]["historical"].update(reason=""),
    lambda value: value["runs"]["historical"].update(reason=None),
    lambda value: value["runs"]["historical"].update(status="done"),
    put(refined_output, extra=1),
    put(refined_output, schema_version="x"),
    put(refined_output, mode="conditional_scan"),
    put(refined_output, model_id=MODELS["historical"]),
    lambda value: refined_output(value)["execution"].update(seconds_per_record=30),
    lambda value: refined_output(value)["execution"]["backend"].update(id="x"),
    put(refined_output, coordinate_space="x"),
    put(refined_output, task_scope="x"),
    put(refined_output, batch_id="x"),
    put(refined_output, results={}),
    lambda value: refined_output(value)["results"].pop(),
    put(result, extra=1),
    put(result, id=5),
    put(result, id="absent"),
    duplicate_row,
    lambda value: result(value)["evidence"].update(host="other"),
    put(result, status="maybe"),
    replace_row("src-1:historical:genomic_flank", other("failed", 5)),
    replace_row("src-1:historical:genomic_flank", other("failed", "x" * 4097)),
    put(result, warnings=[1]),
    put(result, warnings="x"),
    put(result, genomic_sites="x"),
    lambda value: result(value)["context"].pop("path"),
    put(lambda value: result(value)["context"], sequence="ACGT"),
    put(lambda value: result(value)["context"], sequence=""),
    put(lambda value: result(value)["context"], sequence=5),
    put(lambda value: result(value)["context"], sequence_alphabet="DNA"),
    put(lambda value: result(value)["context"], sequence_sha256="0" * 64),
    put(lambda value: result(value)["context"], start=36),
    put(lambda value: result(value)["context"], start=True),
    lambda value: result(value)["context"]["genome"].update(topology="circular"),
    replace_row(
        "src-0:historical:measured_tss",
        lambda i, m: {**other_row(i, m, "failed", "x"), "prediction": {"status": "ok"}},
    ),
    replace_row(
        "src-0:historical:measured_tss",
        lambda i, m: {**other_row(i, m, "failed", "x"), "prediction": "x"},
    ),
    put(result, context=None),
    put(result, prediction="x"),
    put(prediction, schema_version="1.3"),
    put(prediction, schema_version=["1.1"]),
    mixed_versions,
    all_refined_as_1_0,
    historical_as_1_1,
    wrong_request,
    put(prediction, input=None),
    put(prediction, input={}),
    put(prediction, input="x"),
    lambda value: core_request(value).pop("oriented_sequence"),
    put(core_request, oriented_sequence=5),
    put(core_request, oriented_sequence="A" * 38),
    put(core_request, oriented_sha256="0" * 64),
    put(core_request, strand="-"),
    put(core_request, start_positions=START),
    put(core_request, start_positions=[]),
    put(core_request, start_positions=[START, START]),
    put(core_request, start_positions=[0]),
    put(core_request, start_positions=[float(START)]),
    put(core_request, temperature_c=0.0),
    put(core_request, temperature_c="37"),
    put(core_request, anti_sd="AAAAAAAAA"),
    put(failed_request, strand="-"),
    put(failed_request, oriented_sha256="0" * 64),
    unprepared_request,
    lambda value: prediction(value)["model"].update(implementation_version="0.3"),
    lambda value: prediction(value)["model"].pop("implementation_version"),
    put(prediction, id="other"),
    put(prediction, status="unsupported"),
    put(prediction, model="x"),
    put(prediction, model={"id": MODELS["historical"]}),
    put(prediction, backend={"id": "other"}),
    put(prediction, prediction_id="x"),
    put(prediction, sites="x"),
    lambda value: prediction(value)["sites"].append(copy.deepcopy(site(value))),
    put(result, genomic_sites=[]),
    lambda value: prediction(value)["sites"].__setitem__(0, "x"),
    lambda value: result(value)["genomic_sites"].__setitem__(0, "x"),
    put(site, status="unsupported"),
    lambda value: result(value)["genomic_sites"][0].update(status="failed"),
    put(site, oriented_start=21),
    lambda value: result(value)["genomic_sites"][0].update(oriented_start=21),
    put(site, oriented_start=float(START)),
    put(site, energies=None),
    lambda value: energies(value).pop("dG_post_footprint"),
    put(energies, units="kJ/mol"),
    put(energies, dG_total="x"),
    put(energies, dG_total=True),
    put(energies, dG_total=1e10),
    put(site, log_tir=None),
    put(energies, dG_mRNA_native_prediction="x"),
    put(energies, dG_cofold_native_prediction=-1e10),
]


class CollectionBoundaryTests(unittest.TestCase):
    def test_tampered_collection_and_outputs(self):
        for index, mutate in enumerate(COLLECTION_TAMPERING):
            value = collection()
            mutate(value)
            with self.subTest(index=index), self.assertRaises(ValueError):
                run(value)

    def test_hashes_strict_json_and_caller_identities(self):
        raw = canonical_bytes(collection())
        good = (PANEL_RAW, PANEL_SHA, raw, sha(raw), COMMIT, MODELS)
        self.assertIn("profiles", metrics.summarize(*good))
        bad = [
            (3, "0" * 64, "SHA-256"),
            (3, "x", "SHA-256"),
            (4, "A" * 40, "40 lowercase"),
            (4, None, "40 lowercase"),
            (5, {**MODELS, "historical": ""}, "model ID"),
            (5, {**MODELS, "historical": MODELS["context2017"]}, "must differ"),
            (5, {**MODELS, "context2017": "other"}, "context2017 model ID"),
        ]
        for position, replacement, message in bad:
            args = list(good)
            args[position] = replacement
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                metrics.summarize(*args)
        for text in (b'{"a": 1, "a": 2}', b'{"a": NaN}', b"[1e999]", b"\xff"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                metrics.summarize(PANEL_RAW, PANEL_SHA, text, sha(text), COMMIT, MODELS)


class CommandLineTests(unittest.TestCase):
    def test_cli_pins_exclusive_permissions_and_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panel_path, collection_path = root / "panel.json", root / "collection.json"
            report_path = root / "report.json"
            panel_path.write_bytes(PANEL_RAW)
            raw = canonical_bytes(collection())
            collection_path.write_bytes(raw)
            args = [
                str(panel_path),
                str(collection_path),
                str(report_path),
                "--panel-sha256",
                PANEL_SHA,
                "--collection-sha256",
                sha(raw),
                "--candidate-commit",
                COMMIT,
                "--historical-model-id",
                MODELS["historical"],
                "--context2017-model-id",
                MODELS["context2017"],
            ]
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(metrics.main(args), 0)
            self.assertEqual(
                json.loads(stdout.getvalue())["output_sha256"],
                sha(report_path.read_bytes()),
            )
            self.assertEqual(stat.S_IMODE(report_path.stat().st_mode), 0o600)
            self.assertEqual(
                json.loads(report_path.read_bytes())["tool_sha256"],
                sha((ROOT / "benchmarks/rbs/context_metrics.py").read_bytes()),
            )
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                self.assertEqual(metrics.main(args), 1)  # Never overwrites.
                report_path.unlink()
                wrong = args[:8] + ["b" * 40] + args[9:]
                self.assertEqual(metrics.main(wrong), 1)
                with patch.object(metrics, "MAX_COLLECTION_BYTES", 10):
                    self.assertEqual(metrics.main(args), 1)
            self.assertIn("exceeds", stderr.getvalue())
            self.assertFalse(report_path.exists())
            with (
                patch.object(sys, "argv", ["context_metrics"] + args),
                patch("sys.stdout", new_callable=io.StringIO),
                patch.dict(sys.modules),
                self.assertRaises(SystemExit) as caught,
            ):
                sys.modules.pop("benchmarks.rbs.context_metrics")
                runpy.run_module("benchmarks.rbs.context_metrics", run_name="__main__")
            self.assertEqual(caught.exception.code, 0)
