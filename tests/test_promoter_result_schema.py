"""Outcome-free structural tests; all identities and scores are synthetic.

Builders follow the public contract without importing scoring code, parameters,
scientific expectations or private outcomes. Hash-shaped strings are not receipts.
"""

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas/promoter-result-1.0.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)
NATIVE_HOST = "Escherichia coli str. K-12 substr. MG1655"
NORMALIZATION = "ascii-whitespace-uppercase-u-to-t-1"
STATUSES = ("ok", "no_candidate", "unsupported", "invalid_input", "failed")
TERMS = (
    "hex10",
    "hex35",
    "discriminator",
    "extended10",
    "itr",
    "up",
    "spacer",
    "intercept",
    "total",
    "binding",
    "source_apparent",
)
# Published ceilings, independently transcribed; never candidate measurements.
LIMITS = {
    "max_input_json_bytes": 4_000_000,
    "max_records_per_batch": 100,
    "max_id_chars": 128,
    "max_host_name_chars": 200,
    "max_contig_chars": 128,
    "max_raw_sequence_chars_per_record": 50_000,
    "max_normalized_bases_per_record": 5_000,
    "max_normalized_bases_per_batch": 100_000,
    "max_planned_sites_per_record": 5_000,
    "max_planned_sites_per_batch": 20_000,
    "max_all_state_sites_per_record": 100,
    "max_all_states_per_record": 3_000,
    "max_all_states_per_batch": 10_000,
    "max_result_json_bytes": 67_108_864,
    "max_metadata_json_bytes": 4_096,
    "max_metadata_depth": 4,
    "default_seconds_per_record": 30.0,
    "max_seconds_per_record": 120.0,
    "default_seconds_per_batch": 300.0,
    "max_seconds_per_batch": 3_600.0,
}


def model():
    """Synthetic receipt-shaped metadata with no invented candidate provenance."""
    source_names = (
        "dG_10",
        "dG_35",
        "dG_disc",
        "dG_ext10",
        "dG_ITR",
        "dG_UP",
        "dG_spacer",
        "intercept",
        "dG_total",
        "dG_bind",
        "dG_apparent",
    )
    return {
        "id": "promoter-lafleur2022-historical-1",
        "implementation_version": "0.0.0+synthetic-contract-test",
        "kind": "historical_equation_reconstruction",
        "source": {"synthetic_only": {"receipt": None}},
        "licence": "GPL-3.0-or-later",
        "parameters": {"parameter_json_sha256": "a" * 64},
        "term_source_names": dict(zip(TERMS, source_names, strict=True)),
        "terms_unit": "source_dG_units",
        "terms_semantics": (
            "learned regression score contributions; "
            "not independently established free energies"
        ),
        "source_quirks": [{"id": "synthetic", "behavior": "fixture only"}],
        "not_modeled": [
            "sigma_factor",
            "temperature",
            "host_specific_calibration",
            "probability",
            "absolute_rate",
            "free_energy",
        ],
        "claims": dict.fromkeys(
            [
                "physical_free_energy",
                "absolute_rate",
                "probability",
                "native_accuracy_evaluated",
                "hosted_parity",
            ],
            False,
        ),
    }


def calibration(profile="ecoli_mg1655", host_status="unspecified"):
    names = {
        "calibration_native": NATIVE_HOST,
        "in_vitro_reference": "in vitro",
        "extrapolated": "synthetic-host",
    }
    return {
        "profile": profile,
        "K": 42,
        "beta": 1.636217004872062 if profile == "ecoli_mg1655" else 0.81632623,
        "native_host": NATIVE_HOST if profile == "ecoli_mg1655" else None,
        "host": None
        if host_status == "unspecified"
        else {
            "name": names[host_status],
            "taxon_id": None,
        },
        "host_status": host_status,
    }


def projection(sequence_strand="+", circular=False):
    return {
        "contig": "synthetic-contig",
        "contig_length": 1000,
        "origin": (950 if sequence_strand == "+" else 50) if circular else 500,
        "sequence_strand": sequence_strand,
        "topology": "circular" if circular else "linear",
        "origin_crossing": circular,
    }


def state(site_id, strand="+", mapping=None, listed=False, d=6, s=17, t=100):
    """Manually located synthetic windows, with per-base genomic runs."""
    start = t - (24 + 1 + 6 + s + 6 + d)
    windows = {
        "UP": [start, start + 24],
        "gap": [start + 24, start + 25],
        "hex35": [start + 25, start + 31],
        "spacer": [start + 31, t - 6 - d],
        "extended10": [t - 9 - d, t - 7 - d],
        "hex10": [t - 6 - d, t - d],
        "discriminator": [t - d, t],
        "itr": [t, t + 20],
    }
    local = {
        name: bounds[:] if strand == "+" else [200 - bounds[1], 200 - bounds[0]]
        for name, bounds in windows.items()
    }
    result = {
        "state_id": f"{site_id}:d{d}s{s}",
        "discriminator_length": d,
        "spacer_length": s,
        "terms": dict.fromkeys(TERMS, 0.0),
        "log_relative_transcription_score": 0.0,
        "relative_transcription_score": 1.0,
        "score_status": "ok",
        "intervals": local,
        "oriented_intervals": windows,
    }
    if mapping is not None:
        direction = 1 if mapping["sequence_strand"] == "+" else -1
        genomic = {}
        for name, (start, end) in local.items():
            points = [
                (mapping["origin"] + direction * base) % mapping["contig_length"]
                for base in range(start, end)
            ]
            if strand == "-":
                points.reverse()
            runs = []
            step = direction if strand == "+" else -direction
            for point in points:
                if runs and point == runs[-1][-1] + step:
                    runs[-1].append(point)
                else:
                    runs.append([point])
            genomic[name] = [[min(run), max(run) + 1] for run in runs]
        result["genomic_intervals"] = genomic
    if listed:
        result["selected"] = True
    else:
        result["elements"] = {
            "UP": "A" * 24,
            "hex35": "A" * 6,
            "spacer": "A" * s,
            "hex10": "A" * 6,
            "discriminator": "A" * d,
            "itr": "A" * 20,
        }
    return result


def site(status="ok", strand="+", mapping=None, all_states=False):
    base = 100 if strand == "+" else 99
    if status == "no_candidate":
        base = 0 if strand == "+" else 199
    site_id = f"psite1:{'b' * 32}:{strand}:{base}"
    result = {
        "site_id": site_id,
        "strand": strand,
        "tss": {
            "forward_base": base,
            "oriented_base": 0 if status == "no_candidate" else 100,
        },
        "genomic": None,
        "status": status,
        "reason": {
            "ok": None,
            "no_candidate": "insufficient_context",
            "failed": "deadline_exceeded",
        }[status],
        "context": {
            "required_upstream": 67,
            "required_downstream": 19,
            "available_upstream": 0 if status == "no_candidate" else 100,
            "available_downstream": 199 if status == "no_candidate" else 99,
        },
        "state_count": 0 if status == "no_candidate" else 30,
        "complete_state_set": status != "no_candidate",
        "attempted": True,
        "tie_count": 1 if status == "ok" else None,
        "selected": state(site_id, strand, mapping) if status == "ok" else None,
    }
    if mapping is not None:
        direction = 1 if mapping["sequence_strand"] == "+" else -1
        result["genomic"] = {
            "contig": mapping["contig"],
            "base": (mapping["origin"] + direction * base) % mapping["contig_length"],
            "strand": "+" if strand == mapping["sequence_strand"] else "-",
            "sequence_strand": mapping["sequence_strand"],
        }
    if all_states:
        # Synthetic all-state branch: independent copies, one selected marker.
        result["states"] = []
        if status == "ok":
            for d in range(6, 11):
                for s in range(15, 21):
                    item = state(site_id, strand, mapping, listed=True, d=d, s=s)
                    item["selected"] = (d, s) == (6, 17)
                    result["states"].append(item)
    return result


def coverage(sites):
    failed = [item for item in sites if item["status"] == "failed"]
    return {
        "planned_sites": len(sites),
        "scored_sites": sum(item["status"] == "ok" for item in sites),
        "partial_state_sites": sum(
            item["status"] == "ok" and item["state_count"] < 30 for item in sites
        ),
        "insufficient_context_sites": sum(
            item["status"] == "no_candidate" for item in sites
        ),
        "failed_sites": sum(item["attempted"] for item in failed),
        "unattempted_sites": sum(not item["attempted"] for item in failed),
        "complete_context": all(item["state_count"] == 30 for item in sites),
        "complete": not failed,
        "truncation": None
        if not failed
        else {
            "reason": failed[0]["reason"],
            "attempted_sites": sum(item["attempted"] for item in sites),
            "planned_sites": len(sites),
        },
    }


def record(status="ok", *, strand="+", mapping=None, all_states=False, empty=False):
    rejected = status in ("invalid_input", "unsupported")
    sites = [] if rejected or empty else [site(status, strand, mapping, all_states)]
    return {
        "id": "synthetic",
        "status": status,
        "reasons": (
            ["limit_exceeded"]
            if status == "invalid_input"
            else ["unsupported_control"]
            if status == "unsupported"
            else ["empty_scan" if empty else "insufficient_context"]
            if status == "no_candidate"
            else []
        ),
        "prediction_id": None if rejected else "c" * 64,
        "input": {
            "raw_sha256": "d" * 64,
            "normalized_dna_sha256": "d" * 64,
            "length": 200,
            "normalization": NORMALIZATION,
        },
        "calibration": calibration(),
        "scan": {
            "mode": "positions",
            "positions": [
                {"strand": item["strand"], "tss": item["tss"]["forward_base"]}
                for item in sites
            ],
        },
        "coverage": None if rejected else coverage(sites),
        "sites": sites,
        "projection": mapping,
        "warnings": [],
        "errors": [{"code": "synthetic", "field": "$.sequence", "message": "fixture"}]
        if rejected
        else [],
        "metadata": None,
    }


def document(*records):
    records = list(records)
    return {
        "schema_version": "1.0",
        "model": model(),
        "batch": {
            "batch_id": "e" * 64,
            "record_count": len(records),
            "status_counts": {
                status: sum(r["status"] == status for r in records)
                for status in STATUSES
            },
            "complete": all(r["status"] != "failed" for r in records),
            "limits": dict(LIMITS),
            "seconds_per_record": 30.0,
            "seconds_per_batch": 300.0,
        },
        "results": records,
    }


def at(value, path):
    for key in path:
        value = value[key]
    return value


def reject(path, value, original=None):
    payload = copy.deepcopy(original if original is not None else document(record()))
    at(payload, path[:-1])[path[-1]] = value
    assert not VALIDATOR.is_valid(payload), (path, value)


def test_schema_and_zero_record_batch():
    Draft202012Validator.check_schema(SCHEMA)
    VALIDATOR.validate(document())
    value = document()
    value["batch"]["status_counts"] = {}
    VALIDATOR.validate(value)
    reject(("batch", "complete"), False, document())
    reject(("batch", "record_count"), 1, document())
    reject(("batch", "status_counts", "ok"), 1, document())


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("all_states", [False, True])
def test_record_and_site_status_branches(status, all_states):
    VALIDATOR.validate(document(record(status, all_states=all_states)))


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("sequence_strand", ["+", "-"])
@pytest.mark.parametrize("circular", [False, True])
def test_both_strands_and_linear_circular_projection(strand, sequence_strand, circular):
    mapping = projection(sequence_strand, circular)
    value = document(record(strand=strand, mapping=mapping, all_states=True))
    VALIDATOR.validate(value)
    selected = value["results"][0]["sites"][0]["selected"]
    if circular and strand == "+":
        assert len(selected["genomic_intervals"]["UP"]) == 2


@pytest.mark.parametrize(
    "profile,status",
    [
        ("ecoli_mg1655", "calibration_native"),
        ("ecoli_mg1655", "unspecified"),
        ("ecoli_mg1655", "extrapolated"),
        ("in_vitro", "in_vitro_reference"),
        ("in_vitro", "extrapolated"),
    ],
)
def test_calibration_host_matrix(profile, status):
    row = record()
    row["calibration"] = calibration(profile, status)
    VALIDATOR.validate(document(row))
    if status in ("calibration_native", "extrapolated"):
        row["calibration"]["host"]["taxon_id"] = 1
        VALIDATOR.validate(document(row))
    if status == "in_vitro_reference":
        row["calibration"]["host"] = None
        VALIDATOR.validate(document(row))


@pytest.mark.parametrize("status", ["overflow", "underflow"])
@pytest.mark.parametrize("container", ["selected", "states"])
def test_relative_score_missingness(status, container):
    value = document(record(all_states=True))
    path = ("results", 0, "sites", 0, container)
    if container == "states":
        path = (*path, 0)
    selected = at(value, path)
    selected.update(score_status=status, relative_transcription_score=None)
    VALIDATOR.validate(value)
    reject((*path, "relative_transcription_score"), 1, value)


@pytest.mark.parametrize(
    "attempted,reason",
    [
        (True, "deadline_exceeded"),
        (False, "deadline_exceeded"),
        (True, "nonfinite_arithmetic"),
    ],
)
def test_failed_site_attempts_and_truncation(attempted, reason):
    row = record("failed", all_states=True)
    row["sites"][0].update(attempted=attempted, reason=reason)
    row["coverage"] = coverage(row["sites"])
    VALIDATOR.validate(document(row))


def test_partial_state_set_legacy_elements_and_mixed_batch():
    row = record()
    item = row["sites"][0]
    site_id = f"psite1:{'b' * 32}:+:58"
    item.update(
        site_id=site_id,
        state_count=1,
        complete_state_set=False,
        legacy_source_key=58,
        tss={"forward_base": 58, "oriented_base": 58},
        selected=state(site_id, d=6, s=15, t=58),
    )
    item["context"].update(available_upstream=58, available_downstream=141)
    row["scan"]["positions"][0]["tss"] = 58
    del item["selected"]["elements"]
    row["warnings"] = [{"code": "legacy_key_not_coordinate", "message": "fixture"}]
    row["coverage"] = coverage(row["sites"])
    VALIDATOR.validate(document(row, *(record(status) for status in STATUSES)))


@pytest.mark.parametrize("status", ["invalid_input", "unsupported"])
@pytest.mark.parametrize("normalized", [False, True])
def test_rejected_nullable_echoes_and_surviving_normalization(status, normalized):
    row = record(status)
    row.update(id=None, calibration=None, scan=None, projection=None, metadata=None)
    if not normalized:
        row["input"].update(normalized_dna_sha256=None, length=None, normalization=None)
        VALIDATOR.validate(document(row))
        row["input"]["raw_sha256"] = None
    VALIDATOR.validate(document(row))
    row.update(id="valid-echo", calibration=calibration(), metadata={})
    VALIDATOR.validate(document(row))


def test_empty_scan_precedence_and_zero_coverage():
    row = record("no_candidate", empty=True)
    VALIDATOR.validate(document(row, record("failed")))
    row["scan"] = {"mode": "scan", "range": [200, 200], "strands": ["-", "+"]}
    value = document(row)
    VALIDATOR.validate(value)
    for key, replacement in [
        ("reasons", []),
        ("reasons", ["empty_scan", "deadline_exceeded"]),
        ("prediction_id", None),
        ("errors", [{"code": "x"}]),
        ("status", "failed"),
        ("status", "ok"),
    ]:
        reject(("results", 0, key), replacement, value)
    for key in (
        "planned_sites",
        "scored_sites",
        "partial_state_sites",
        "insufficient_context_sites",
        "failed_sites",
        "unattempted_sites",
    ):
        reject(("results", 0, "coverage", key), 1, value)
    for key in ("complete", "complete_context"):
        reject(("results", 0, "coverage", key), False, value)
    reject(
        ("results", 0, "coverage", "truncation"),
        {
            "reason": "deadline_exceeded",
            "attempted_sites": 0,
            "planned_sites": 1,
        },
        value,
    )


# Every exact-key object in representative branches: remove each required key,
# then add an unknown field. Extensible interiors are tested separately below.
EXACT_PATHS = [
    (),
    ("model",),
    ("model", "claims"),
    ("model", "source_quirks", 0),
    ("batch",),
    ("batch", "limits"),
    ("results", 0),
    ("results", 0, "input"),
    ("results", 0, "calibration"),
    ("results", 0, "calibration", "host"),
    ("results", 0, "scan"),
    ("results", 0, "scan", "positions", 0),
    ("results", 0, "coverage"),
    ("results", 0, "projection"),
    ("results", 0, "sites", 0),
    ("results", 0, "sites", 0, "tss"),
    ("results", 0, "sites", 0, "genomic"),
    ("results", 0, "sites", 0, "context"),
    ("results", 0, "sites", 0, "selected"),
    ("results", 0, "sites", 0, "selected", "terms"),
    ("results", 0, "sites", 0, "selected", "intervals"),
    ("results", 0, "sites", 0, "selected", "oriented_intervals"),
    ("results", 0, "sites", 0, "selected", "genomic_intervals"),
    ("results", 0, "sites", 0, "selected", "elements"),
    ("results", 0, "sites", 0, "states", 0),
]


@pytest.mark.parametrize("path", EXACT_PATHS)
def test_exact_object_keys_and_required_fields(path):
    row = record(mapping=projection(), all_states=True)
    row["calibration"] = calibration(host_status="calibration_native")
    original = document(row)
    VALIDATOR.validate(original)
    reject((*path, "typo"), True, original)
    optional = {"states", "legacy_source_key", "elements"}
    for key in at(original, path):
        if key in optional:
            continue
        value = copy.deepcopy(original)
        del at(value, path)[key]
        assert not VALIDATOR.is_valid(value), (path, key)


@pytest.mark.parametrize("key,ceiling", LIMITS.items())
def test_every_effective_limit_ceiling_and_type(key, ceiling):
    path = ("batch", "limits", key)
    original = document(record())
    VALIDATOR.validate(original)
    lower = copy.deepcopy(original)
    at(lower, path[:-1])[key] = 0.5 if isinstance(ceiling, float) else 1
    VALIDATOR.validate(lower)
    for value in [0, -1, True, False, "1", None, ceiling + 1]:
        reject(path, value, original)
    if isinstance(ceiling, int):
        reject(path, 1.5, original)


@pytest.mark.parametrize(
    "path,values",
    [
        (("schema_version",), [None, 1, "2.0"]),
        (("model", "id"), ["synthetic-other-model", "", None]),
        (("model", "implementation_version"), ["", None, 1]),
        (("model", "kind"), ["physical_model", None]),
        (("model", "licence"), ["proprietary", None]),
        (("model", "terms_unit"), ["kcal/mol", None]),
        (("model", "terms_semantics"), ["", 1, None]),
        (("model", "source"), [None, [], "commit"]),
        (("model", "parameters"), [None, [], {}, {"other": "digest"}]),
        (("model", "source_quirks"), [None, ["quirk"], [{}]]),
        (("model", "term_source_names"), [None, [], {"hex10": 0}]),
        (
            ("model", "not_modeled"),
            [[], ["sigma_factor"], ["temperature", "sigma_factor"]],
        ),
        (("batch", "record_count"), [-1, 101, True, 0.5, None]),
        (
            ("batch", "status_counts"),
            [None, [], {"invented": 1}, {"ok": True}, {"ok": -1}],
        ),
        (("batch", "seconds_per_record"), [0, -1, True, "30", None, 120.00001]),
        (("batch", "seconds_per_batch"), [0, -1, False, "300", None, 3600.00001]),
        (("results", 0, "id"), ["", "bad id", "a" * 129, "valid\n", 1]),
        (("results", 0, "status"), ["success", None]),
        (("results", 0, "reasons"), [None, ["invented"], ["empty_scan", "empty_scan"]]),
        (("results", 0, "input", "length"), [0, True, 1.5, "200", 5001]),
        (("results", 0, "input", "normalization"), [[], "none", "uppercase", 1]),
        (("results", 0, "calibration", "K"), [True, 41, "42", None]),
        (("results", 0, "calibration", "beta"), [1, None, True, "1.636217004872062"]),
        (("results", 0, "calibration", "native_host"), [None, "in vitro", 1]),
        (("results", 0, "calibration", "profile"), ["custom", None]),
        (
            ("results", 0, "calibration", "host_status"),
            ["native", None, "extrapolated"],
        ),
        (("results", 0, "metadata"), [[], "text", True, 1]),
        (("results", 0, "warnings"), [None, ["warning"], [{}], [{"code": 1}]]),
        (("results", 0, "errors"), [None, ["error"], [{}], [{"code": "x"}]]),
        (("results", 0, "coverage", "planned_sites"), [-1, True, 0.5, 5001]),
        (("results", 0, "coverage", "complete"), [None, 1, False]),
        (("results", 0, "sites", 0, "strand"), ["both", None]),
        (("results", 0, "sites", 0, "tss", "forward_base"), [-1, True, 0.5, "100"]),
        (("results", 0, "sites", 0, "context", "required_upstream"), [66, True]),
        (("results", 0, "sites", 0, "context", "required_downstream"), [20, None]),
        (("results", 0, "sites", 0, "context", "available_upstream"), [-1, True, 0.5]),
        (("results", 0, "sites", 0, "state_count"), [0, 31, True, 1.5]),
        (("results", 0, "sites", 0, "complete_state_set"), [False, 1, None]),
        (("results", 0, "sites", 0, "attempted"), [False, 1, None]),
        (("results", 0, "sites", 0, "tie_count"), [None, 0, 31, True, 1.5]),
        (("results", 0, "sites", 0, "reason"), ["deadline_exceeded", "invented"]),
        (("results", 0, "sites", 0, "selected"), [None, {}, []]),
        (
            ("results", 0, "sites", 0, "selected", "discriminator_length"),
            [5, 11, True, 6.5],
        ),
        (
            ("results", 0, "sites", 0, "selected", "spacer_length"),
            [14, 21, False, 17.5],
        ),
        (
            ("results", 0, "sites", 0, "selected", "relative_transcription_score"),
            [None, 0, -1, 1e-310, True],
        ),
        (("results", 0, "sites", 0, "selected", "score_status"), ["clipped", None]),
        (
            ("results", 0, "sites", 0, "selected", "intervals", "gap"),
            [[], [1], [1, 2, 3], [-1, 2], [True, 2], [1.5, 2], "1,2"],
        ),
        (
            ("results", 0, "sites", 0, "selected", "elements", "UP"),
            ["", "a" * 24, "N" * 24, "A" * 23, "A" * 25, None],
        ),
    ],
)
def test_negative_contract_mutations(path, values):
    for value in values:
        reject(path, value)


@pytest.mark.parametrize(
    "key",
    [
        "physical_free_energy",
        "absolute_rate",
        "probability",
        "native_accuracy_evaluated",
        "hosted_parity",
    ],
)
@pytest.mark.parametrize("value", [True, 0, None, "false"])
def test_claims_are_exact_false_booleans(key, value):
    reject(("model", "claims", key), value)


@pytest.mark.parametrize(
    "path",
    [
        ("batch", "batch_id"),
        ("model", "parameters", "parameter_json_sha256"),
        ("results", 0, "prediction_id"),
        ("results", 0, "input", "raw_sha256"),
        ("results", 0, "input", "normalized_dna_sha256"),
    ],
)
@pytest.mark.parametrize(
    "value", [None, 1, "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n"]
)
def test_canonical_digest_patterns(path, value):
    reject(path, value)


@pytest.mark.parametrize(
    "tail",
    ["", ":d5s17", ":d11s17", ":d6s14", ":d6s21", ":d06s17", ":d6s017", ":d6s17\n"],
)
def test_state_id_suffix_pattern(tail):
    reject(
        ("results", 0, "sites", 0, "selected", "state_id"),
        f"psite1:{'b' * 32}:+:100{tail}",
    )


@pytest.mark.parametrize(
    "value",
    [
        f"psite1:{'b' * 31}:+:100",
        f"psite1:{'B' * 32}:+:100",
        f"psite1:{'b' * 32}:both:100",
        f"psite1:{'b' * 32}:+:-1",
        f"psite1:{'b' * 32}:+:01",
        f"psite1:{'b' * 32}:+:100\n",
    ],
)
def test_site_id_pattern(value):
    reject(("results", 0, "sites", 0, "site_id"), value)


@pytest.mark.parametrize("term", TERMS)
@pytest.mark.parametrize("value", [None, True, "0", float("inf"), -float("inf")])
def test_all_terms_are_finite_numeric_scalars(term, value):
    reject(("results", 0, "sites", 0, "selected", "terms", term), value)


def test_score_finite_extremes_and_strict_json_boundary():
    value = document(record())
    selected = value["results"][0]["sites"][0]["selected"]
    selected.update(
        log_relative_transcription_score=-sys.float_info.max,
        relative_transcription_score=sys.float_info.min,
    )
    VALIDATOR.validate(value)
    selected["relative_transcription_score"] = sys.float_info.max
    VALIDATOR.validate(value)
    for field in ("log_relative_transcription_score", "relative_transcription_score"):
        for invalid in (float("inf"), -float("inf"), True, None, "0"):
            reject(("results", 0, "sites", 0, "selected", field), invalid)
    for token in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError):
            json.dumps({"not_json": token}, allow_nan=False)


def test_extensible_model_interiors_and_metadata_are_explicit():
    value = document(record())
    value["model"]["source"] = {"alternative_layout": ["synthetic", 0, None, True]}
    value["model"]["parameters"].update(nested={"count": 343}, labels=[336, 337, 338])
    value["results"][0]["metadata"] = {
        "unicode": "é",
        "nested": [{"n": 1.5}],
        "null": None,
    }
    VALIDATOR.validate(value)
    for path in [
        ("model", "source"),
        ("model", "parameters"),
        ("results", 0, "metadata"),
    ]:
        reject((*path, "non_json"), object(), value)
    for key in ("code", "field", "message"):
        original = document(record("invalid_input"))
        del original["results"][0]["errors"][0][key]
        assert not VALIDATOR.is_valid(original)


def test_public_adapter_synthetic_shape_with_public_model_id():
    # Public outcome-free test helpers only; no source fixtures or model internals.
    from tests.benchmarks.test_promoter_runtime_adapter import Fixture

    value = Fixture().result(0)
    value["model"]["id"] = "promoter-lafleur2022-historical-1"
    # All other fields remain untouched, including deliberately fake hashes/scores.
    VALIDATOR.validate(value)


@pytest.mark.parametrize(
    "field", ["calibration", "scan", "coverage", "id", "prediction_id"]
)
def test_supported_records_require_valid_resolved_fields(field):
    reject(("results", 0, field), None)


@pytest.mark.parametrize(
    "field,value",
    [
        ("normalized_dna_sha256", None),
        ("raw_sha256", None),
        ("length", None),
        ("normalization", None),
    ],
)
def test_normalization_information_is_an_atomic_result(field, value):
    original = document(record("invalid_input"))
    reject(("results", 0, "input", field), value, original)


@pytest.mark.parametrize("status", ["invalid_input", "unsupported"])
def test_rejected_records_cannot_keep_sites_prediction_or_coverage(status):
    original = document(record(status))
    for field, value in [
        ("sites", [site()]),
        ("prediction_id", "a" * 64),
        ("coverage", coverage([])),
    ]:
        reject(("results", 0, field), value, original)


@pytest.mark.parametrize(
    "host",
    [
        {},
        {"name": ""},
        {"name": "a" * 201},
        {"name": 1},
        {"name": "synthetic", "taxon_id": 0},
        {"name": "synthetic", "taxon_id": True},
        {"name": "synthetic", "taxon_id": 0.5},
        {"name": "synthetic", "taxon_id": "1"},
        {"name": "synthetic", "taxon_id": None, "extra": True},
    ],
)
def test_host_requires_name_and_nullable_taxon(host):
    original = document(record())
    original["results"][0]["calibration"] = calibration(host_status="extrapolated")
    reject(("results", 0, "calibration", "host"), host, original)


@pytest.mark.parametrize(
    "profile,status,host",
    [
        ("ecoli_mg1655", "in_vitro_reference", None),
        ("in_vitro", "unspecified", None),
        ("in_vitro", "calibration_native", {"name": NATIVE_HOST, "taxon_id": None}),
        ("ecoli_mg1655", "calibration_native", {"name": "synthetic", "taxon_id": None}),
        ("ecoli_mg1655", "extrapolated", {"name": NATIVE_HOST, "taxon_id": None}),
        ("in_vitro", "extrapolated", {"name": "in vitro", "taxon_id": None}),
        ("in_vitro", "in_vitro_reference", {"name": "synthetic", "taxon_id": None}),
        ("ecoli_mg1655", "unspecified", {"name": "synthetic", "taxon_id": None}),
    ],
)
def test_calibration_rejects_inconsistent_host_status(profile, status, host):
    original = document(record())
    resolved = calibration(profile, "extrapolated")
    resolved.update(host_status=status, host=host)
    reject(("results", 0, "calibration"), resolved, original)


@pytest.mark.parametrize(
    "scan",
    [
        {},
        [],
        {"mode": "scan"},
        {"mode": "scan", "range": [0, 1]},
        {"mode": "scan", "range": [0, 1], "strands": []},
        {"mode": "scan", "range": [0, 1], "strands": ["+", "+"]},
        {"mode": "scan", "range": [0, 1], "strands": ["both"]},
        {"mode": "scan", "range": [True, 1], "strands": ["+"]},
        {"mode": "scan", "range": [0, 1, 2], "strands": ["+"]},
        {"mode": "scan", "range": [0, 1], "strands": ["+"], "typo": True},
        {"mode": "positions"},
        {"mode": "positions", "positions": [{}]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": True}]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": -1}]},
        {"mode": "positions", "positions": [{"strand": "+", "tss": 1}] * 2},
        {"mode": "positions", "positions": [], "range": [0, 1]},
        {"mode": "positions", "positions": []},
    ],
)
def test_resolved_scan_shape_and_empty_positions_consistency(scan):
    reject(("results", 0, "scan"), scan)


def test_resolved_scan_and_array_boundaries():
    row = record()
    row["scan"] = {"mode": "scan", "range": [0, 200], "strands": ["-", "+"]}
    VALIDATOR.validate(document(row))
    original = document(row)
    del original["results"][0]["scan"]["range"]
    assert not VALIDATOR.is_valid(original)
    row["scan"] = {
        "mode": "positions",
        "positions": [{"strand": "+", "tss": i} for i in range(5000)],
    }
    VALIDATOR.validate(document(row))
    row["scan"]["positions"].append({"strand": "+", "tss": 5000})
    assert not VALIDATOR.is_valid(document(row))
    value = document(*(record() for _ in range(100)))
    VALIDATOR.validate(value)
    value["results"].append(record())
    assert not VALIDATOR.is_valid(value)
    # Isolate the result-site array cap without spending time on 5000 states.
    row = record("no_candidate")
    row["sites"] = [site("no_candidate")] * 5000
    row["coverage"] = coverage(row["sites"])
    VALIDATOR.validate(document(row))
    row["sites"].append(site("no_candidate"))
    assert not VALIDATOR.is_valid(document(row))


@pytest.mark.parametrize(
    "field,value",
    [
        ("contig", ""),
        ("contig", "a" * 129),
        ("origin", -1),
        ("origin", True),
        ("origin", 0.5),
        ("contig_length", 0),
        ("contig_length", False),
        ("sequence_strand", "both"),
        ("topology", "unknown"),
        ("origin_crossing", 1),
        ("origin_crossing", True),
    ],
)
def test_resolved_projection_types(field, value):
    original = document(record(mapping=projection()))
    reject(("results", 0, "projection", field), value, original)


@pytest.mark.parametrize(
    "field,value",
    [
        ("contig", ""),
        ("contig", "a" * 129),
        ("base", -1),
        ("base", True),
        ("base", 0.5),
        ("strand", "both"),
        ("sequence_strand", None),
    ],
)
def test_genomic_point_types(field, value):
    original = document(record(mapping=projection()))
    reject(("results", 0, "sites", 0, "genomic", field), value, original)


@pytest.mark.parametrize("interval", [[], [[1, 2]] * 3, [1, 2], [[-1, 2]], [[1, True]]])
def test_genomic_runs_shape(interval):
    original = document(record(mapping=projection()))
    reject(
        ("results", 0, "sites", 0, "selected", "genomic_intervals", "UP"),
        interval,
        original,
    )


def test_projection_fields_must_agree_about_presence():
    original = document(record(mapping=projection(), all_states=True))
    for path in [
        ("results", 0, "sites", 0, "genomic"),
        ("results", 0, "sites", 0, "selected", "genomic_intervals"),
        ("results", 0, "sites", 0, "states", 0, "genomic_intervals"),
    ]:
        reject(path, None, original)
    for path in [
        ("results", 0, "sites", 0, "selected"),
        ("results", 0, "sites", 0, "states", 0),
    ]:
        value = copy.deepcopy(original)
        del at(value, path)["genomic_intervals"]
        assert not VALIDATOR.is_valid(value)
    reject(("results", 0, "projection"), None, original)
    original = document(record(all_states=True))
    projected = site(mapping=projection(), all_states=True)
    reject(("results", 0, "sites", 0, "genomic"), projected["genomic"], original)
    for path in [
        ("results", 0, "sites", 0, "selected"),
        ("results", 0, "sites", 0, "states", 0),
    ]:
        reject(
            (*path, "genomic_intervals"),
            projected["selected"]["genomic_intervals"],
            original,
        )


def test_optional_states_elements_legacy_scope_and_selection_marker():
    original = document(record(all_states=True))
    path = ("results", 0, "sites", 0)
    too_many = copy.deepcopy(at(original, (*path, "states")))
    too_many.append(copy.deepcopy(too_many[0]))
    for states in [[], too_many]:
        reject((*path, "states"), states, original)
    for marker in [None, 1, "true"]:
        reject((*path, "states", 0, "selected"), marker, original)
    for count in [0, 2]:
        value = copy.deepcopy(original)
        for i, item in enumerate(at(value, (*path, "states"))):
            item["selected"] = i < count
        assert not VALIDATOR.is_valid(value)
    reject(
        (*path, "states", 0, "elements"),
        at(original, (*path, "selected", "elements")),
        original,
    )
    reject((*path, "selected", "selected"), True, original)
    for value in [None, True, -1, 1.5]:
        reject((*path, "legacy_source_key"), value, original)


@pytest.mark.parametrize("status", ["no_candidate", "failed"])
def test_non_ok_sites_have_no_selected_state_scores_or_states(status):
    original = document(record(status, all_states=True))
    for field, value in [
        ("selected", site()["selected"]),
        ("tie_count", 1),
        ("states", site(all_states=True)["states"]),
        ("relative_transcription_score", 1.0),
    ]:
        reject(("results", 0, "sites", 0, field), value, original)
    reject(("results", 0, "sites", 0, "reason"), None, original)
    if status == "no_candidate":
        reject(("results", 0, "sites", 0, "attempted"), False, original)
        reject(("results", 0, "sites", 0, "state_count"), 1, original)
    else:
        reject(("results", 0, "coverage", "truncation"), None, original)
        value = copy.deepcopy(original)
        value["results"][0]["sites"][0].update(
            attempted=False, reason="nonfinite_arithmetic"
        )
        assert not VALIDATOR.is_valid(value)


@pytest.mark.parametrize("field", ["reason", "attempted_sites", "planned_sites"])
def test_truncation_exact_fields(field):
    original = document(record("failed"))
    value = copy.deepcopy(original)
    del value["results"][0]["coverage"]["truncation"][field]
    assert not VALIDATOR.is_valid(value)
    reject(("results", 0, "coverage", "truncation", "typo"), 1, original)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reason", "insufficient_context"),
        ("reason", None),
        ("attempted_sites", -1),
        ("attempted_sites", True),
        ("planned_sites", 0),
        ("planned_sites", 5001),
    ],
)
def test_truncation_field_types(field, value):
    reject(
        ("results", 0, "coverage", "truncation", field),
        value,
        document(record("failed")),
    )


def test_semantic_acceptance_is_deliberately_limited():
    value = document(record(all_states=True))
    # Schema has no original request, receipt, clock or scientific computation.
    value["batch"]["record_count"] = 99
    value["batch"]["status_counts"]["ok"] = 0
    value["batch"]["limits"]["max_planned_sites_per_record"] = 1
    row = value["results"][0]
    row["coverage"]["planned_sites"] = 100
    row["sites"][0]["tss"]["forward_base"] = 99999
    row["sites"][0]["selected"]["intervals"]["UP"] = [90, 1]
    row["sites"][0]["selected"]["terms"]["total"] = 99.0
    row["sites"][0]["states"].reverse()
    VALIDATOR.validate(value)
    # Integer-vs-float representation must be checked at serialization/runtime.
    value["batch"]["seconds_per_record"] = 30
    row["sites"][0]["tss"]["oriented_base"] = 100.0
    VALIDATOR.validate(value)
