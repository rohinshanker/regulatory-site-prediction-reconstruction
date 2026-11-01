"""Public synthetic predictor outputs and malformed portable result contracts.

Uses the existing deterministic FoldingSession fixture, never a real engine.
These tests establish structural transport rules, not scientific accuracy.
"""

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource, Unresolvable
from test_transcript import SyntheticSession, annotation, document, projection
from test_transcript import backend as backend

from regsite import transcript as t
from regsite.backend import RnaStructure
from regsite.structures import BackendError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
SCHEMA = json.loads((SCHEMAS / "supplied-transcript-result-1.schema.json").read_text())


def no_retrieval(uri):
    """Unknown resources fail locally; no retrieval fallback can fetch a URL."""
    raise NoSuchResource(ref=uri)


REGISTRY = Registry(retrieve=no_retrieval).with_resources(
    (path.name, Resource.from_contents(json.loads(path.read_text())))
    for path in SCHEMAS.glob("*.schema.json")
)
VALIDATOR = Draft202012Validator(SCHEMA, registry=REGISTRY)
PROFILE_VERSIONS = (
    ("historical", "1.0"),
    ("footprint2017", "1.1"),
    ("context2017", "1.1"),
    ("standby2014", "1.2"),
    ("joint_standby", "1.3"),
)
OBJECT_PATHS = (
    (),
    ("request",),
    ("settings",),
    ("limits",),
    ("limits", "predictors"),
    ("limits", "predictors", "rbs"),
    ("limits", "predictors", "promoter"),
    ("identities",),
    ("identities", "rbs"),
    ("identities", "rbs", "profile"),
    ("identities", "rbs", "base_parameters"),
    ("identities", "rbs", "base_parameters", "start_energies_kcal_mol"),
    ("identities", "rbs", "standby_parameters"),
    ("identities", "rbs", "joint_parameters"),
    ("identities", "promoter"),
    ("identities", "promoter", "model"),
    ("identities", "promoter", "calibration"),
    ("transcript",),
    ("transcript", "annotation"),
    ("transcript", "annotation", "provenance"),
    ("transcript", "coordinates"),
    ("transcript", "coordinates", "genomic"),
    ("components",),
    ("components", "rbs"),
    ("components", "rbs", "request"),
    ("components", "rbs", "coverage"),
    ("components", "rbs", "prediction"),
    ("components", "rbs", "prediction", "input"),
    ("components", "rbs", "prediction", "model"),
    ("components", "rbs", "prediction", "sites", 0),
    ("components", "promoter"),
    ("components", "promoter", "request"),
    ("components", "promoter", "coverage"),
    ("components", "promoter", "prediction"),
    ("components", "promoter", "prediction", "batch"),
    ("components", "promoter", "prediction", "results", 0),
    ("cds", 0),
    ("cds", 0, "scalars"),
    ("cds", 0, "scalars", "tir"),
    ("cds", 0, "features"),
    ("cds", 0, "features", "start_codon"),
    ("coverage",),
    ("promoter_candidates", 0),
    ("promoter_candidates", 0, "scalars"),
    ("promoter_candidates", 0, "scalars", "hex10"),
    ("promoter_candidates", 0, "features"),
)


def at(value, path):
    for key in path:
        value = value[key]
    return value


def changed(result, path, value):
    result = copy.deepcopy(result)
    at(result, path[:-1])[path[-1]] = value
    return result


def predict(request, backend=None):
    """Validate the actual public JSON form, including tuple-to-array conversion."""
    result = t.predict_transcript(request, backend)
    wire = t.result_bytes(result)
    result = json.loads(wire)
    VALIDATOR.validate(result)
    return result


@pytest.fixture
def complete(backend):
    request = document()
    request["projection"] = projection("-", True)
    return predict(request, backend)


def test_dialect_and_transitive_references_stay_offline(complete):
    Draft202012Validator.check_schema(SCHEMA)
    for name, resource in REGISTRY.items():
        assert name.endswith(".schema.json")

        def check(node):
            if isinstance(node, dict):
                if "$ref" in node:
                    assert node["$ref"].split("#")[0] in ("", *REGISTRY)
                for value in node.values():
                    check(value)
            elif isinstance(node, list):
                for value in node:
                    check(value)

        check(resource.contents)
    with pytest.raises(Unresolvable):
        Draft202012Validator(SCHEMA, registry=Registry(retrieve=no_retrieval)).validate(
            complete
        )


@pytest.mark.parametrize("profile,version", PROFILE_VERSIONS)
def test_every_mechanistic_profile_retains_its_native_schema(backend, profile, version):
    request = document()
    request["rbs"]["profile"] = profile
    result = predict(request, backend)
    native = result["components"]["rbs"]["prediction"]
    assert native["schema_version"] == version
    assert native["status"] == "ok"
    assert result["identities"]["rbs"]["profile"]["model_id"] == native["model"]["id"]
    assert not VALIDATOR.is_valid(
        changed(result, ("components", "rbs", "prediction", "schema_version"), "9.0")
    )
    if version != "1.0":
        assert not VALIDATOR.is_valid(
            changed(result, ("request", "rbs", "profile"), "historical")
        )


def test_request_result_and_native_identities_remain_explicit(complete):
    request = complete["request"]

    def canonical(value):
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")

    assert complete["request_sha256"] == hashlib.sha256(canonical(request)).hexdigest()
    without_hash = {k: v for k, v in complete.items() if k != "prediction_sha256"}
    assert (
        complete["prediction_sha256"]
        == hashlib.sha256(canonical(without_hash)).hexdigest()
    )
    assert (
        complete["transcript"]["sequence_sha256"]
        == hashlib.sha256(request["sequence"][20:180].encode("ascii")).hexdigest()
    )
    for name, native_id in (
        ("rbs", "transcript-rbs"),
        ("promoter", "transcript-promoter"),
    ):
        component = complete["components"][name]
        assert component["request"]["id"] == native_id
        assert (
            component["declared_seconds"]
            == request["settings"][f"seconds_per_{name}_record"]
        )
        assert "execution_seconds" not in component
    rbs = complete["components"]["rbs"]["prediction"]
    assert rbs["backend"] == complete["identities"]["rbs"]["backend"]
    assert (
        rbs["model"]["source_commit"] == complete["identities"]["rbs"]["source_commit"]
    )
    promoter = complete["components"]["promoter"]["prediction"]
    assert promoter["model"] == complete["identities"]["promoter"]["model"]
    assert promoter["batch"]["seconds_per_record"] == 30.0
    assert promoter["batch"]["seconds_per_batch"] == 30.0
    assert promoter["results"][0]["prediction_id"]
    assert rbs["prediction_id"]


def test_both_promoter_strands_and_reverse_circular_runs(complete):
    assert [c["strand"] for c in complete["promoter_candidates"]] == ["+", "-"]
    for candidate in complete["promoter_candidates"]:
        for feature in candidate["features"].values():
            assert feature["local_strand"] == candidate["strand"]
            assert feature["genomic"]["strand"] == (
                "-" if candidate["strand"] == "+" else "+"
            )
    assert complete["transcript"]["coordinates"]["genomic"]["strand"] == "-"
    assert complete["cds"][0]["features"]["start_codon"]["construct_interval"] == [
        40,
        43,
    ]


def test_incompatible_and_clipped_annotations_keep_null_shapes(backend):
    request = document()
    request["cds"] = [
        annotation("before", 19, 30),
        annotation("clipped", 40, 200),
        annotation("edge", 178, 190),
        annotation("after", 180, 200),
    ]
    result = predict(request, backend)
    assert result["status"] == "partial"
    assert [c["reason"] for c in result["cds"]] == [
        "start_before_transcript",
        None,
        "start_codon_after_transcript",
        "start_after_transcript",
    ]
    assert result["cds"][0]["transcript_offset"] == -1
    assert result["cds"][1]["warnings"] == ["downstream_clipped"]
    assert result["components"]["rbs"]["coverage"]["incompatible"] == 3
    for cds in (result["cds"][0], *result["cds"][2:]):
        assert cds["features"] == {}
        assert cds["site_index"] is None
        assert all(s["value"] is None for s in cds["scalars"].values())
        assert not VALIDATOR.is_valid(
            changed(result, ("cds", result["cds"].index(cds), "eligible"), True)
        )


def test_no_eligible_cds_requires_no_backend():
    request = document()
    request["transcript"]["range"] = [0, 1]
    result = predict(request)
    rb = result["components"]["rbs"]
    assert rb["status"] == "not_applicable"
    assert rb["reason"] == "no_eligible_cds"
    assert rb["roster"] == []
    assert rb["declared_seconds"] is None
    assert rb["prediction"] is None
    assert result["identities"]["rbs"]["backend"] is None
    assert result["status"] == "partial"
    assert not VALIDATOR.is_valid(
        changed(result, ("components", "rbs", "declared_seconds"), 30)
    )


def test_unsupported_start_retains_successful_sibling(backend):
    request = document()
    request["cds"].append(annotation("unsupported", 70, 100))
    result = predict(request, backend)
    assert result["status"] == "partial"
    assert [c["status"] for c in result["cds"]] == ["ok", "unsupported"]
    assert result["cds"][1]["reason"] == "unsupported_start_codon"
    assert result["cds"][1]["site_index"] == 1
    assert (
        result["cds"][1]["features"]["binding_interval"]["reason"]
        == "feature_unavailable"
    )


def test_returned_native_failure_retains_features_and_explicit_missing_scalars(
    backend, monkeypatch
):
    def fail(*args):
        raise BackendError("synthetic fold failure")

    monkeypatch.setattr(SyntheticSession, "fold", fail)
    result = predict(document(), backend)
    assert result["components"]["rbs"]["status"] == "failed"
    cds = result["cds"][0]
    assert cds["status"] == "failed" and cds["site_index"] == 0
    assert cds["features"]["start_codon"]["native_interval"] == [20, 23]
    assert cds["scalars"]["tir"] == {
        "value": None,
        "unit": "relative_initiation_score",
        "reason": "synthetic fold failure",
    }


def test_missing_native_site_is_distinct_from_failed_returned_site(
    backend, monkeypatch
):
    def fail(*args):
        raise BackendError("synthetic session failure")

    monkeypatch.setattr(RnaStructure, "session", fail)
    result = predict(document(), backend)
    cds = result["cds"][0]
    assert cds["status"] == "not_evaluated"
    assert cds["reason"] == "missing_native_site"
    assert cds["site_index"] is None and cds["features"] == {}
    assert result["components"]["rbs"]["coverage"] == {
        "requested": 1,
        "returned": 0,
        "scored": 0,
        "not_evaluated": 1,
        "missing": 1,
        "incompatible": 0,
    }
    assert result["components"]["rbs"]["prediction"] is not None
    assert result["status"] == "partial"


@pytest.mark.parametrize("empty", [False, True])
def test_unstarted_components_keep_rosters_and_null_native_payloads(
    backend, monkeypatch, empty
):
    request = document()
    if empty:
        request["promoter"]["scan"] = {"mode": "positions", "positions": []}
    ticks = iter([0.0, 101.0, 102.0])
    monkeypatch.setattr(t.time, "monotonic", lambda: next(ticks))
    result = predict(request, backend)
    assert result["status"] == "unavailable"
    for name in ("rbs", "promoter"):
        component = result["components"][name]
        assert component["status"] == "not_evaluated"
        assert component["reason"] == "deadline_exceeded"
        assert component["prediction"] is None and component["declared_seconds"] is None
        assert not VALIDATOR.is_valid(
            changed(result, ("components", name, "status"), "failed")
        )
    assert len(result["promoter_candidates"]) == (0 if empty else 2)
    assert len(result["components"]["promoter"]["roster"]) == (0 if empty else 2)


def test_empty_scan_started_has_a_real_native_no_candidate_result(backend):
    request = document()
    request["promoter"]["scan"] = {
        "mode": "scan",
        "range": [200, 200],
        "strands": ["-", "+"],
    }
    result = predict(request, backend)
    component = result["components"]["promoter"]
    assert result["status"] == "complete"
    assert component["status"] == "no_candidate"
    assert component["declared_seconds"] == 30.0
    assert component["prediction"]["results"][0]["reasons"] == ["empty_scan"]
    assert result["promoter_candidates"] == []
    assert not VALIDATOR.is_valid(
        changed(result, ("components", "promoter", "prediction"), None)
    )


def test_native_unattempted_promoter_candidates_keep_returned_indices(
    backend, monkeypatch
):
    native = t.promoter_io.predict_batch

    def timeout(*args, **kwargs):
        ticks = iter([0, 0, 1000, 1000])
        kwargs["clock"] = lambda: next(ticks)
        return native(*args, **kwargs)

    monkeypatch.setattr(t.promoter_io, "predict_batch", timeout)
    result = predict(document(), backend)
    assert result["status"] == "partial"
    assert result["components"]["promoter"]["status"] == "failed"
    for index, candidate in enumerate(result["promoter_candidates"]):
        assert candidate["site_index"] == index
        assert candidate["status"] == "not_evaluated"
        assert candidate["reason"] == "deadline_exceeded"
        assert candidate["features"]["tss"]["native_interval"] == [100, 101]
        assert candidate["features"]["UP"]["native_interval"] is None


def test_empty_and_null_intervals_preserve_distinct_geometry(backend):
    result = predict(document(), backend)
    features = result["cds"][0]["features"]
    assert features["standby.hairpin"]["native_interval"] is None
    assert features["standby.hairpin"]["reason"] == "feature_unavailable"
    # Public predictor at a construct boundary retains a TSS feature but no
    # selected Promoter windows, without inventing zero scores.
    request = document()
    request["promoter"]["scan"] = {
        "mode": "positions",
        "positions": [{"strand": "+", "tss": 0}],
    }
    result = predict(request, backend)
    candidate = result["promoter_candidates"][0]
    assert candidate["features"]["tss"]["native_interval"] == [0, 1]
    assert candidate["features"]["hex10"]["native_interval"] is None
    assert (
        candidate["scalars"]["log_relative_transcription_score"]["unit"]
        == "ln_relative_transcription_score"
    )
    request = document()
    request["rbs"]["profile"] = "standby2014"
    request["projection"] = projection("-", True)
    result = predict(request, backend)
    assert result["cds"][0]["features"]["standby.distal"] == {
        "native_interval": [0, 0],
        "construct_interval": [20, 20],
        "local_strand": "+",
        "genomic": {"contig": "synthetic", "strand": "-", "runs": []},
        "reason": None,
    }


@pytest.mark.parametrize("path", OBJECT_PATHS)
def test_known_objects_require_fields_and_reject_extras(complete, path):
    original = at(complete, path)
    assert isinstance(original, dict) and original
    for key in original:
        result = copy.deepcopy(complete)
        del at(result, path)[key]
        assert not VALIDATOR.is_valid(result), (path, "missing", key)
    result = copy.deepcopy(complete)
    at(result, path)["unexpected_field"] = 1
    assert not VALIDATOR.is_valid(result), (path, "extra")
    for value in ([], False, "wrong-object"):
        result = changed(complete, path, value) if path else value
        assert not VALIDATOR.is_valid(result), (path, value)


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "supplied-transcript-result-2"),
        (("request_sha256",), "A" * 64),
        (("prediction_sha256",), "a" * 63),
        (("transcript", "sequence_sha256"), "a" * 64 + "\n"),
        (("components", "rbs", "prediction", "prediction_id"), None),
        (("identities", "rbs", "source_commit"), "missing"),
        (("identities", "rbs", "profile", "name"), "learned"),
        (
            ("identities", "promoter", "model", "parameters", "parameter_json_sha256"),
            "bad",
        ),
        (("components", "rbs", "request", "id"), "caller-override"),
        (("components", "promoter", "request", "output", "states"), "all"),
        (("components", "rbs", "declared_seconds"), None),
        (("components", "promoter", "declared_seconds"), 121),
        (("limits", "max_cds"), 11),
        (("limits", "max_seconds_total"), 120),
        (("coverage", "scored"), -1),
        (("coverage", "cds"), 11),
        (("coverage", "eligible_cds"), True),
        (("coverage", "scored"), 523),
        (("components", "rbs", "coverage", "returned"), 11),
        (("components", "promoter", "coverage", "requested"), 513),
        (("status",), "unavailable"),
        (("coverage", "complete"), False),
        (("cds", 0, "site_index"), -1),
        (("cds", 0, "site_index"), 10),
        (("promoter_candidates", 0, "site_index"), 512),
        (("cds", 0, "status"), "invalid_input"),
        (("promoter_candidates", 0, "status"), "incompatible_transcript"),
        (("cds", 0, "features", "start_codon", "native_interval"), [-1, 23]),
        (("cds", 0, "features", "start_codon", "construct_interval"), [40, 5001]),
        (("cds", 0, "features", "start_codon", "native_interval"), [20]),
        (("cds", 0, "features", "start_codon", "genomic", "runs"), [[-1, 1]]),
        (("cds", 0, "features", "start_codon", "local_strand"), "-"),
        (("cds", 0, "features", "window", "genomic", "runs"), [[0, 1]] * 3),
        (("cds", 0, "features", "standby.hairpin", "reason"), None),
        (("cds", 0, "features", "start_codon", "reason"), "feature_unavailable"),
        (("cds", 0, "scalars", "tir", "unit"), "relative_transcription_score"),
        (("cds", 0, "scalars", "log_tir", "unit"), "relative_initiation_score"),
        (("cds", 0, "scalars", "dG_total", "unit"), "source_dG_units"),
        (("cds", 0, "scalars", "tir", "value"), True),
        (("cds", 0, "scalars", "tir", "value"), None),
        (("cds", 0, "scalars", "dG_standby", "reason"), None),
        (("promoter_candidates", 0, "scalars", "hex10", "unit"), "kcal/mol"),
        (
            (
                "promoter_candidates",
                0,
                "scalars",
                "log_relative_transcription_score",
                "unit",
            ),
            "relative_transcription_score",
        ),
        (("promoter_candidates", 0, "features", "tss", "local_strand"), "-"),
        (("cds",), []),
        (("unsupported_capabilities",), ["coupling"]),
        (("warnings",), []),
        (("settings", "seconds_total"), 0),
    ],
)
def test_malformed_identity_units_counts_intervals_and_nullability(
    complete, path, value
):
    assert not VALIDATOR.is_valid(changed(complete, path, value)), path


def test_candidate_and_feature_list_caps(complete):
    for path, maximum in [
        (("cds",), 10),
        (("promoter_candidates",), 512),
        (("components", "rbs", "roster"), 10),
        (("components", "promoter", "roster"), 512),
    ]:
        assert not VALIDATOR.is_valid(
            changed(complete, path, [at(complete, path)[0]] * (maximum + 1))
        )
    feature = complete["cds"][0]["features"]["start_codon"]
    features = complete["cds"][0]["features"]
    VALIDATOR.validate(
        changed(
            complete,
            ("cds", 0, "features"),
            {**features, "standby.downstream_hairpins.49": feature},
        )
    )
    assert not VALIDATOR.is_valid(
        changed(
            complete,
            ("cds", 0, "features"),
            {**features, "standby.downstream_hairpins.50": feature},
        )
    )


@pytest.mark.parametrize("value", [math.inf, -math.inf, True, "1", []])
def test_wrapper_scalars_require_finite_numbers(complete, value):
    assert not VALIDATOR.is_valid(
        changed(
            complete, ("promoter_candidates", 0, "scalars", "hex10", "value"), value
        )
    )


def test_hash_relations_count_sums_and_integral_float_types_need_adapter(complete):
    # Shape-valid tampering demonstrates the schema's explicit semantic limits.
    for path, value in [
        (("prediction_sha256",), "0" * 64),
        (("request_sha256",), "0" * 64),
        (("coverage", "scored"), 522),
        (("components", "rbs", "coverage", "requested"), 9),
        (("cds", 0, "features", "start_codon", "construct_interval"), [43, 40]),
        (("cds", 0, "features", "start_codon", "native_interval"), [20.0, 23.0]),
        (("cds", 0, "site_index"), 0.0),
        (("components", "promoter", "declared_seconds"), 29),
    ]:
        VALIDATOR.validate(changed(complete, path, value))
    # NaN is not a JSON token; a schema alone is not a strict JSON parser.
    with pytest.raises(ValueError):
        json.dumps(
            changed(complete, ("cds", 0, "scalars", "dG_total", "value"), math.nan),
            allow_nan=False,
        )


def test_host_identity_keeps_native_omission_and_resolved_warning_rules(backend):
    request = document()
    request["rbs"]["host"] = "Example host"
    request["promoter"]["calibration"] = "ecoli_mg1655"
    request["promoter"]["host"] = {"name": "Example host"}
    result = predict(request, backend)
    native_request = result["components"]["promoter"]["request"]
    assert native_request["host"] == {"name": "Example host"}
    assert "projection" not in native_request
    identity = result["identities"]["promoter"]["calibration"]
    assert identity["host"]["taxon_id"] is None
    assert identity["warnings"]
    assert identity["host_status"] == "extrapolated"
    del native_request["host"]
    assert not VALIDATOR.is_valid(result)


def test_no_binding_and_empty_scan_can_be_complete_with_zero_scores(
    backend, monkeypatch
):
    monkeypatch.setattr(SyntheticSession, "cofold", lambda *a: ())
    request = document()
    request["promoter"]["scan"] = {"mode": "positions", "positions": []}
    result = predict(request, backend)
    assert result["status"] == "complete" and result["coverage"]["scored"] == 0
    assert result["coverage"]["complete"] is True
    assert result["components"]["rbs"]["status"] == "no_candidate"
    assert result["cds"][0]["scalars"]["tir"]["value"] is None
    assert result["cds"][0]["features"]["start_codon"]["native_interval"] == [20, 23]


def test_required_feature_intervals_cannot_become_unavailable(complete):
    for path in [
        ("transcript", "coordinates"),
        ("cds", 0, "annotation_coordinates"),
        ("cds", 0, "features", "start_codon"),
        ("cds", 0, "features", "window"),
        ("promoter_candidates", 0, "features", "tss"),
    ]:
        unavailable = {
            "native_interval": None,
            "construct_interval": None,
            "local_strand": "+",
            "genomic": None,
            "reason": "feature_unavailable",
        }
        assert not VALIDATOR.is_valid(changed(complete, path, unavailable))


def test_incompatible_cds_does_not_gain_scores_or_native_correspondence():
    request = document()
    request["transcript"]["range"] = [0, 1]
    result = predict(request)
    for path, value in [
        (("cds", 0, "site_index"), 0),
        (("cds", 0, "scalars", "tir", "value"), 1),
        (("cds", 0, "scalars", "tir", "reason"), "value_unavailable"),
        (
            ("cds", 0, "features"),
            {"start_codon": result["cds"][0]["annotation_coordinates"]},
        ),
        (("components", "rbs", "prediction"), {}),
    ]:
        assert not VALIDATOR.is_valid(changed(result, path, value))


def test_missing_relative_score_can_retain_finite_logarithmic_score(complete):
    result = changed(
        complete,
        ("promoter_candidates", 0, "scalars", "relative_transcription_score"),
        {
            "value": None,
            "unit": "relative_transcription_score",
            "reason": "underflow",
        },
    )
    # Schema preserves native numerical missingness. An adapter must still bind
    # these wrapper scalars to the retained native selected state.
    VALIDATOR.validate(result)
    log_score = result["promoter_candidates"][0]["scalars"][
        "log_relative_transcription_score"
    ]
    assert math.isfinite(log_score["value"])
    assert log_score["unit"] == "ln_relative_transcription_score"
    assert not VALIDATOR.is_valid(
        changed(
            complete,
            (
                "promoter_candidates",
                0,
                "scalars",
                "relative_transcription_score",
                "value",
            ),
            -1,
        )
    )
