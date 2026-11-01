"""Paired request/result schemas against real no-fold paired predictor outputs."""

import copy
import itertools
import json
from collections.abc import Callable
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from test_paired import document, edit, projection
from test_rbs import AlgebraBackend

from regsite import paired as p
from regsite import promoter_io, rbs
from regsite.backend import RnaStructure
from regsite.structures import BackendError

SCHEMAS = Path("schemas")
REQUEST = "paired-regulatory-request-1.schema.json"
RESULT = "paired-regulatory-result-1.schema.json"
REGISTRY = Registry().with_resources(
    (path.name, Resource.from_contents(json.loads(path.read_text())))
    for path in SCHEMAS.glob("*.schema.json")
)
ROW_REASONS = {
    None,
    "incompatible_identity",
    "unsuccessful_candidate",
    "counterpart_roster_unknown",
    "unmapped_current_anchor",
    "unmapped_recoded_anchor",
    "mapped_anchor_absent_from_recoded_roster",
    "mapped_anchor_absent_from_current_roster",
    "interrupted_codon",
}
PROFILES = (
    "historical",
    "footprint2017",
    "context2017",
    "standby2014",
    "joint_standby",
    "joint-standby-rnastructure-6.6-reconstruction-1",
)


def validator(name: str, registry: Registry = REGISTRY):
    schema = json.loads((SCHEMAS / name).read_text())
    return jsonschema.Draft202012Validator(schema, registry=registry)


REQUEST_VALIDATOR = validator(REQUEST)
RESULT_VALIDATOR = validator(RESULT)


def valid_result(result: dict) -> dict:
    RESULT_VALIDATOR.validate(result)
    return result


def predict(request: dict, backend: RnaStructure | None = None) -> dict:
    """Run the real wrapper, then require its output to match the result schema."""
    return valid_result(p.predict_pair(request, backend))


@pytest.fixture
def no_fold(monkeypatch):
    """Verified-backend type whose sessions never fold; empty/unsupported rosters."""
    monkeypatch.setattr(RnaStructure, "session", lambda *args: object())
    return RnaStructure(Path("."), {"name": "schema-no-fold"})


@pytest.fixture
def failed_backend(monkeypatch):
    def fail(*args):
        raise BackendError("injected backend session failure")

    monkeypatch.setattr(RnaStructure, "session", fail)
    return RnaStructure(Path("."), {"name": "failure-injection-only"})


@pytest.fixture
def algebra(monkeypatch, no_fold):
    """Native RBS code over the synthetic algebra double; never real folding."""
    native: Callable[..., dict] = rbs.predict

    def scored(value, backend, **kwargs):
        return native(value, AlgebraBackend(), **kwargs)

    monkeypatch.setattr(rbs, "predict", scored)
    return no_fold


def rbs_document(current="A" * 20, edits=None, profile="historical"):
    request = document("rbs", current=current, edits=edits)
    request["settings"]["profile"] = profile
    return request


def scored_rbs_document(profile="historical"):
    request = rbs_document("A" * 20 + "ATG" + "A" * 50, [edit(30, 31, "C")], profile)
    request["projections"] = {
        "current": projection(length=73),
        "recoded": projection(length=73, strand="-", origin=500),
    }
    return request


def late_recoded(free_calls: int) -> Callable[..., dict]:
    """Real Promoter batch whose recoded clock expires after ``free_calls`` reads."""
    native: Callable[..., dict] = promoter_io.predict_batch

    def predict_batch(value: dict, **kwargs: object) -> dict:
        if value["id"] == "recoded":
            calls = itertools.count()
            kwargs["clock"] = lambda: 0.0 if next(calls) < free_calls else 1e9
        return native(value, **kwargs)

    return predict_batch


def refs(value: object) -> list[str]:
    if isinstance(value, dict):
        found = [value["$ref"]] if "$ref" in value else []
        return found + [ref for item in value.values() for ref in refs(item)]
    if isinstance(value, list):
        return [ref for item in value for ref in refs(item)]
    return []


@pytest.mark.parametrize("name", [REQUEST, RESULT])
def test_schemas_are_draft_2020_12_and_registry_local(name):
    schema = json.loads((SCHEMAS / name).read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "$id" not in schema
    siblings = {path.name for path in SCHEMAS.glob("*.schema.json")}
    for ref in refs(schema):
        target = ref.partition("#")[0]
        assert target == "" or target in siblings, ref
    # No implicit retrieval: sibling references require the local registry.
    with pytest.raises(Unresolvable):
        validator(name, Registry()).is_valid(
            document() if name == REQUEST else p.predict_pair(document())
        )


@pytest.mark.parametrize("name", [REQUEST, RESULT])
def test_schemas_document_what_they_cannot_prove(name):
    comment = json.loads((SCHEMAS / name).read_text())["$comment"].lower()
    for phrase in (
        "local registry",
        "cannot prove",
        "hash",
        "coordinate correspondence",
        "integer-versus-float",
        "deadline",
        "biological validity",
        "duplicate keys",
    ):
        assert phrase in comment


def test_contract_example_placeholder_requests_are_not_valid():
    example = {
        "schema_version": "paired-regulatory-request-1",
        "pair": {
            "schema_version": "paired-edit-input-1",
            "pair_id": "synthetic-pair",
            "topology": "linear",
            "current": {"id": "current", "sequence": "ACGT"},
            "recoded": {"id": "recoded", "sequence": "ATGT"},
            "edits": [{"id": "e0", "start": 1, "end": 2, "replacement": "T"}],
        },
        "calculator": "promoter",
        "current_request": {},
        "recoded_request": {},
        "settings": {"seconds_per_side": 30.0},
    }
    assert not REQUEST_VALIDATOR.is_valid(example)
    with pytest.raises(p.PairError):
        p.predict_pair(example)


def promoter_cases() -> dict[str, tuple[dict, str]]:
    changed = document(current="ACGT" * 50, edits=[edit(70, 71, "A")])
    changed["pair"]["topology"] = "circular"
    changed["current_request"]["projection"] = projection(origin=980, circular=True)
    changed["recoded_request"]["projection"] = projection(
        strand="-", origin=10, circular=True
    )
    empty = document()
    for side in p.SIDES:
        empty[side + "_request"]["scan"]["positions"] = []
    boundary = copy.deepcopy(empty)
    boundary["current_request"]["scan"]["positions"] = [{"strand": "+", "tss": 0}]
    mismatch = document()
    mismatch["recoded_request"]["calibration"] = "ecoli_mg1655"
    scanned = document(current="ACGT" * 50)
    for side in p.SIDES:
        scanned[side + "_request"]["scan"] = {
            "mode": "scan",
            "range": [90, 96],
            "strands": ["+", "-"],
        }
    insertion = document(edits=[edit(80, 80, "CG")])
    insertion["recoded_request"]["scan"]["positions"] = [{"strand": "+", "tss": 102}]
    deletion = document(edits=[edit(80, 82, "")])
    deletion["recoded_request"]["scan"]["positions"] = [{"strand": "-", "tss": 98}]
    return {
        "unchanged": (document(), "complete"),
        "circular_projected_substitution": (changed, "complete"),
        "empty_rosters": (empty, "complete"),
        "no_context_unmatched": (boundary, "complete"),
        "calibration_mismatch": (mismatch, "incomparable"),
        "both_strand_scan": (scanned, "complete"),
        "insertion": (insertion, "complete"),
        "deletion": (deletion, "complete"),
    }


@pytest.mark.parametrize("case", sorted(promoter_cases()))
def test_real_promoter_requests_and_results(case):
    request, status = promoter_cases()[case]
    REQUEST_VALIDATOR.validate(request)
    result = predict(request)
    assert result["status"] == status


@pytest.mark.parametrize("profile", PROFILES)
def test_rbs_empty_rosters_for_every_profile(no_fold, profile):
    request = rbs_document(profile=profile)
    request["projections"] = {"current": projection(length=20), "recoded": None}
    REQUEST_VALIDATOR.validate(request)
    result = predict(request, no_fold)
    assert result["status"] == "complete" and result["comparisons"] == []
    assert result["sides"]["current"]["projection"]["sequence_strand"] == "+"


@pytest.mark.parametrize("profile", PROFILES)
def test_rbs_native_scored_sites_with_projections(algebra, profile):
    request = scored_rbs_document(profile)
    REQUEST_VALIDATOR.validate(request)
    result = predict(request, algebra)
    assert result["status"] == "complete"
    row = result["comparisons"][0]
    assert row["status"] == "paired" and row["reason"] is None
    for side in p.SIDES:
        candidate = result["sides"][side]["candidates"][0]
        assert candidate["status"] == "ok" and len(candidate["genomic"]["bases"]) == 1
    standby = any(name.startswith("standby.") for name in row["feature_changes"])
    assert standby == (profile not in PROFILES[:3])


def test_rbs_settings_difference_is_incomparable(no_fold):
    request = rbs_document()
    request["recoded_request"]["temperature_c"] = 25
    REQUEST_VALIDATOR.validate(request)
    assert predict(request, no_fold)["status"] == "incomparable"


def native_rejections() -> dict[str, tuple[str, Callable[[dict], None], str]]:
    def put(side: str, key: str, value: object) -> Callable[[dict], None]:
        return lambda request: request[side + "_request"].__setitem__(key, value)

    def drop(side: str, key: str) -> Callable[[dict], None]:
        return lambda request: request[side + "_request"].pop(key)

    return {
        "promoter_unresolvable_scan": (
            "promoter",
            put("current", "scan", {"mode": "bad"}),
            "invalid_input",
        ),
        "promoter_unknown_control": (
            "promoter",
            put("recoded", "sigma", "unsupported"),
            "unsupported",
        ),
        "promoter_missing_calibration": (
            "promoter",
            drop("current", "calibration"),
            "invalid_input",
        ),
        "rbs_temperature_out_of_range": (
            "rbs",
            put("current", "temperature_c", -1),
            "invalid_input",
        ),
        "rbs_unresolvable_strand": (
            "rbs",
            put("recoded", "strand", "?"),
            "invalid_input",
        ),
    }


@pytest.mark.parametrize("case", sorted(native_rejections()))
def test_native_record_rejections_are_valid_outputs_not_valid_inputs(no_fold, case):
    calculator, mutate, status = native_rejections()[case]
    request = document() if calculator == "promoter" else rbs_document()
    mutate(request)
    assert not REQUEST_VALIDATOR.is_valid(request)
    result = predict(request, no_fold if calculator == "rbs" else None)
    statuses = []
    for side in p.SIDES:
        native = result["sides"][side]["prediction"]
        statuses.append(
            native["status"] if calculator == "rbs" else native["results"][0]["status"]
        )
    assert status in statuses


def test_promoter_pair_beyond_native_length_is_a_native_rejection():
    REQUEST_VALIDATOR.validate(document(current="A" * 5000))
    request = document(current="A" * 5001)
    assert not REQUEST_VALIDATOR.is_valid(request)
    native = predict(request)["sides"]["current"]["prediction"]["results"][0]
    assert native["status"] == "invalid_input"


@pytest.mark.parametrize(
    "free_calls,status,comparable", [(3, "partial", 1), (2, "unavailable", 0)]
)
def test_real_promoter_deadline_failures(monkeypatch, free_calls, status, comparable):
    monkeypatch.setattr(promoter_io, "predict_batch", late_recoded(free_calls))
    result = predict(document())
    assert result["status"] == status
    assert result["coverage"]["comparable"] == comparable
    assert result["warnings"][-1] == "partial_predictions_are_diagnostic_only"


def rbs_accounting_cases() -> list[dict]:
    cases = []
    for strand in "+-":
        request = rbs_document(edits=[edit(5, 5, "C")])
        for side in p.SIDES:
            length = len(request["pair"][side]["sequence"])
            request[side + "_request"]["strand"] = strand
            request[side + "_request"]["start_positions"] = [
                4 if strand == "+" else length - 1 - (6 if side == "current" else 7)
            ]
        cases.append(request)
    for operation, source, target in ((edit(5, 6, ""), 5, 5), (edit(5, 5, "C"), 6, 5)):
        request = rbs_document(edits=[operation])
        request["current_request"]["start_positions"] = [source]
        request["recoded_request"]["start_positions"] = [target]
        cases.append(request)
    for side in p.SIDES:
        request = rbs_document()
        request[side + "_request"]["strand"] = "?"
        other = "recoded" if side == "current" else "current"
        request[other + "_request"]["start_positions"] = [2]
        cases.append(request)
    scanned = rbs_document("AAAGGAGGAAAAAAATG" + "A" * 35)
    scanned["projections"] = {"current": None, "recoded": projection(length=52)}
    cases.append(scanned)
    return cases


def test_every_status_and_row_reason_is_a_valid_real_output(
    monkeypatch, failed_backend
):
    results = [predict(request) for request, _ in promoter_cases().values()]
    for free_calls in (3, 2):
        with monkeypatch.context() as patch:
            patch.setattr(promoter_io, "predict_batch", late_recoded(free_calls))
            results.append(predict(document()))
    results += [predict(request, failed_backend) for request in rbs_accounting_cases()]
    assert {r["status"] for r in results} == {
        "complete",
        "partial",
        "incomparable",
        "unavailable",
    }
    rows = [row for r in results for row in r["comparisons"]]
    assert {row["reason"] for row in rows} == ROW_REASONS
    assert {row["status"] for row in rows} == {"paired", "unmatched", "unavailable"}
    assert any(r["sides"]["recoded"]["roster_status"] == "unknown" for r in results)
    failed = results[-1]["sides"]["current"]
    assert failed["prediction"]["status"] == "failed"
    assert failed["candidates"][0]["status"] == "unavailable"


def outer(key: str, value: object) -> Callable[[dict], None]:
    return lambda request: request.__setitem__(key, value)


def nested(path: str, value: object) -> Callable[[dict], None]:
    *parents, key = path.split(".")

    def mutate(request: dict) -> None:
        target = request
        for parent in parents:
            target = target[int(parent) if isinstance(target, list) else parent]
        if value is KeyError:
            del target[key]
        else:
            target[key] = value

    return mutate


def resequence(sequence: str) -> Callable[[dict], None]:
    def mutate(request: dict) -> None:
        for side in p.SIDES:
            request["pair"][side]["sequence"] = sequence
            request[side + "_request"]["sequence"] = sequence

    return mutate


def many_edits(request: dict) -> None:
    current = "A" * 2002
    request["pair"]["current"]["sequence"] = current
    request["current_request"]["sequence"] = current
    request["pair"]["edits"] = [
        {"id": f"e{i}", "start": 2 * i, "end": 2 * i + 1, "replacement": "C"}
        for i in range(1001)
    ]
    recoded = "CA" * 1001
    request["pair"]["recoded"]["sequence"] = recoded
    request["recoded_request"]["sequence"] = recoded


def explicit_starts(count: int) -> Callable[[dict], None]:
    def mutate(request: dict) -> None:
        resequence("A" * (count + 2))(request)
        for side in p.SIDES:
            request[side + "_request"]["start_positions"] = list(range(count))

    return mutate


def promoter_positions(count: int) -> Callable[[dict], None]:
    def mutate(request: dict) -> None:
        resequence("A" * 600)(request)
        for side in p.SIDES:
            request[side + "_request"]["scan"]["positions"] = [
                {"strand": "+", "tss": i} for i in range(count)
            ]

    return mutate


REQUEST_REFUSALS = {
    "unknown_outer_field": ("promoter", outer("cache", {})),
    "schema_version": ("promoter", outer("schema_version", "paired-request-2")),
    "calculator": ("promoter", outer("calculator", "operon")),
    "pair_field": ("promoter", nested("pair.alignment", [])),
    "pair_id_length": ("promoter", nested("pair.pair_id", "x" * 129)),
    "lowercase_pair": ("promoter", resequence("a" * 200)),
    "trailing_newline_pair": ("promoter", resequence("A" * 199 + "\n")),
    "empty_pair": ("promoter", resequence("")),
    "edit_missing_replacement": (
        "promoter",
        nested("pair.edits", [{"id": "e", "start": 1, "end": 2}]),
    ),
    "edit_ambiguous_base": ("promoter", nested("pair.edits", [edit(1, 2, "N")])),
    "too_many_edits": ("promoter", many_edits),
    "seconds_zero": ("promoter", nested("settings.seconds_per_side", 0)),
    "seconds_over": ("promoter", nested("settings.seconds_per_side", 120.5)),
    "seconds_bool": ("promoter", nested("settings.seconds_per_side", True)),
    "seconds_text": ("promoter", nested("settings.seconds_per_side", "30")),
    "promoter_profile": ("promoter", nested("settings.profile", "historical")),
    "promoter_outer_projections": (
        "promoter",
        outer("projections", {"current": None, "recoded": None}),
    ),
    "promoter_envelope": ("promoter", nested("current_request.records", [])),
    "promoter_version": ("promoter", nested("recoded_request.schema_version", "2.0")),
    "promoter_position_cap": ("promoter", promoter_positions(513)),
    "rbs_missing_profile": ("rbs", nested("settings.profile", KeyError)),
    "rbs_unknown_profile": ("rbs", nested("settings.profile", "fast")),
    "rbs_missing_host": ("rbs", nested("current_request.host", KeyError)),
    "rbs_missing_strand": ("rbs", nested("recoded_request.strand", KeyError)),
    "rbs_projection_strand": (
        "rbs",
        outer(
            "projections",
            {
                "current": {
                    k: v
                    for k, v in projection(length=20).items()
                    if k != "sequence_strand"
                },
                "recoded": None,
            },
        ),
    ),
    "rbs_projection_keys": ("rbs", outer("projections", {"current": None})),
    "rbs_start_cap": ("rbs", explicit_starts(513)),
}


@pytest.mark.parametrize("case", sorted(REQUEST_REFUSALS))
def test_request_refusals_match_atomic_runtime_refusals(no_fold, case):
    calculator, mutate = REQUEST_REFUSALS[case]
    request = document() if calculator == "promoter" else rbs_document()
    mutate(request)
    assert not REQUEST_VALIDATOR.is_valid(request)
    with pytest.raises(p.PairError):
        p.predict_pair(request, no_fold if calculator == "rbs" else None)


def test_cap_boundaries_and_documented_cross_side_feature_budget(no_fold):
    request = document()
    promoter_positions(512)(request)
    REQUEST_VALIDATOR.validate(request)
    request = rbs_document()
    explicit_starts(512)(request)
    REQUEST_VALIDATOR.validate(request)
    # Per-side limits fit; the combined RBS feature budget is runtime-only.
    with pytest.raises(p.PairError, match="max_feature_bases"):
        p.predict_pair(request, no_fold)


def unpaired(result: dict, index: int, reason: str, keep: str) -> dict:
    """Rewrite one paired row into a consistent unpaired row for refusal controls."""
    row = result["comparisons"][index]
    row.update(
        status="unavailable" if reason == "counterpart_roster_unknown" else "unmatched",
        reason=reason,
        identity_mismatches=[],
        feature_changes={},
    )
    row["recoded_candidate_id" if keep == "current" else "current_candidate_id"] = None
    for delta in row["deltas"].values():
        delta.update(value=None, reason=reason)
    return result


def incompatible(result: dict, mismatches: list[str]) -> dict:
    """Mark the first paired row as an identity mismatch with suppressed deltas."""
    row = result["comparisons"][0]
    row.update(reason="incompatible_identity", identity_mismatches=mismatches)
    for delta in row["deltas"].values():
        delta.update(value=None, reason="incompatible_identity")
    return result


@pytest.fixture(scope="module")
def promoter_result():
    request, _ = promoter_cases()["circular_projected_substitution"]
    return valid_result(p.predict_pair(request))


def first(result: dict, side: str = "current") -> dict:
    return result["sides"][side]["candidates"][0]


def promoter_record(result: dict) -> dict:
    return result["sides"]["current"]["prediction"]["results"][0]


PROMOTER_CONTROLS: dict[str, Callable[[dict], object]] = {
    "zero_delta": lambda r: r["comparisons"][1]["deltas"]["total"].update(value=0.0),
    "nonfinite_delta": lambda r: r["comparisons"][0]["deltas"]["total"].update(
        value=None, reason="nonfinite_delta"
    ),
    "unmatched_current": lambda r: unpaired(r, 0, "unmapped_current_anchor", "current"),
    "unmatched_recoded": lambda r: unpaired(
        r, 0, "mapped_anchor_absent_from_current_roster", "recoded"
    ),
    "unknown_counterpart": lambda r: unpaired(
        r, 0, "counterpart_roster_unknown", "recoded"
    ),
    "incompatible": lambda r: incompatible(r, ["model_sha256", "calibration_sha256"]),
    "unavailable_feature": lambda r: first(r)["features"]["UP"].update(
        interval=None, mapping=None, genomic=None, reason="feature_unavailable"
    ),
}


@pytest.mark.parametrize("case", sorted(PROMOTER_CONTROLS))
def test_promoter_result_consistent_rewrites_remain_valid(promoter_result, case):
    result = copy.deepcopy(promoter_result)
    PROMOTER_CONTROLS[case](result)
    RESULT_VALIDATOR.validate(result)


PROMOTER_REFUSALS: dict[str, Callable[[dict], object]] = {
    "extra_field": outer("elapsed_seconds", 1.0),
    "missing_field": lambda r: r.pop("coverage"),
    "schema_version": outer("schema_version", "paired-regulatory-result-2"),
    "unknown_status": outer("status", "done"),
    "status_not_complete": outer("status", "partial"),
    "uppercase_hash": outer("request_sha256", "A" * 64),
    "short_hash": outer("prediction_sha256", "a" * 63),
    "missing_warning": outer("warnings", []),
    "extra_warning": lambda r: r["warnings"].append(
        "partial_predictions_are_diagnostic_only"
    ),
    "settings_profile": nested("settings.profile", "historical"),
    "limit_changed": nested("limits.max_edits", 999),
    "native_limit_changed": nested("limits.predictors.rbs.max_seconds_per_record", 60),
    "edit_map_field": nested("edit_map.alignment", []),
    "edit_map_missing": nested("edit_map.current_unmatched", KeyError),
    "edit_map_version": nested("edit_map.schema_version", "paired-edit-map-2"),
    "identities_field": nested("sides.current.identities.host_sha256", "a" * 64),
    "roster_status": nested("sides.current.roster_status", "partial"),
    "unknown_roster_candidates": nested("sides.current.roster_status", "unknown"),
    "known_roster_null_expected": nested("coverage.recoded.expected", None),
    "coverage_flag": nested("coverage.diagnostic_only", True),
    "coverage_side_incomplete": nested("coverage.current.complete", False),
    "side_field": nested("sides.current.cache", {}),
    "candidate_side": lambda r: first(r).update(
        id=first(r)["id"].replace(":current:", ":recoded:")
    ),
    "candidate_calculator": lambda r: first(r).update(
        id=first(r)["id"].replace(":promoter:", ":rbs:")
    ),
    "candidate_newline": lambda r: first(r).update(id=first(r)["id"] + "\n"),
    "candidate_codon": lambda r: first(r).update(codon_bases=[100, 101, 102]),
    "candidate_status": lambda r: first(r).update(status="unsupported"),
    "unavailable_index": lambda r: first(r).update(
        status="unavailable", reason="prediction_candidate_unavailable"
    ),
    "candidate_genomic_missing": lambda r: first(r).update(genomic=None),
    "candidate_genomic_bases": lambda r: first(r)["genomic"]["bases"].append(1),
    "scalar_unit": lambda r: first(r)["scalars"]["total"].update(unit="kcal/mol"),
    "scalar_null_without_reason": lambda r: first(r)["scalars"]["total"].update(
        value=None
    ),
    "scalar_zero_with_reason": lambda r: first(r)["scalars"]["total"].update(
        value=0, reason="value_unavailable"
    ),
    "scalar_missing": lambda r: first(r)["scalars"].pop("binding"),
    "scalar_extra": lambda r: first(r)["scalars"].update(
        dG_total={"value": 0, "unit": "kcal/mol", "reason": None}
    ),
    "relative_score_reason": lambda r: first(r)["scalars"][
        "log_relative_transcription_score"
    ].update(value=None, reason="overflow"),
    "feature_missing": lambda r: first(r)["features"].pop("hex10"),
    "feature_extra": lambda r: first(r)["features"].update(
        tss=first(r)["features"]["itr"]
    ),
    "feature_unavailable_mapping": lambda r: first(r)["features"]["UP"].update(
        interval=None, genomic=None, reason="feature_unavailable"
    ),
    "feature_genomic_missing": lambda r: first(r)["features"]["UP"].update(
        genomic=None
    ),
    "feature_interval_shape": lambda r: first(r)["features"]["UP"].update(
        interval=[40]
    ),
    "mapping_complete_with_gap": lambda r: first(r)["features"]["UP"]["mapping"][
        "mapped_bases"
    ].__setitem__(0, None),
    "mapping_contiguous_incomplete": lambda r: first(r)["features"]["UP"][
        "mapping"
    ].update(complete_base_mapping=False, unmatched_bases=1),
    "native_prediction_stripped": lambda r: r["sides"]["current"]["prediction"].pop(
        "model"
    ),
    "native_two_records": lambda r: r["sides"]["current"]["prediction"][
        "results"
    ].append(promoter_record(r)),
    "native_record_rewritten": lambda r: promoter_record(r).update(status="done"),
    "request_envelope": nested("sides.current.request.records", []),
    "request_version": nested("sides.current.request.schema_version", "2.0"),
    "validated_request_invalid": nested("sides.current.request.calibration", "bad"),
    "row_field": nested("comparisons.0.cache", {}),
    "row_delta_on_incompatible": nested(
        "comparisons.0.reason", "incompatible_identity"
    ),
    "row_reason_mismatched_delta": lambda r: unpaired(
        r, 0, "unmapped_current_anchor", "current"
    )["comparisons"][0]["deltas"]["total"].update(reason="unmapped_recoded_anchor"),
    "row_unpaired_feature_changes": lambda r: unpaired(
        r, 0, "unmapped_current_anchor", "current"
    )["comparisons"][0].update(feature_changes=r["comparisons"][1]["feature_changes"]),
    "row_wrong_null_side": lambda r: unpaired(
        r, 0, "unmapped_current_anchor", "recoded"
    ),
    "row_unknown_status": lambda r: unpaired(
        r, 0, "counterpart_roster_unknown", "current"
    )["comparisons"][0].update(status="unmatched"),
    "row_interrupted_promoter": lambda r: unpaired(
        r, 0, "interrupted_codon", "current"
    ),
    "row_paired_null_id": nested("comparisons.0.recoded_candidate_id", None),
    "row_id_side": lambda r: r["comparisons"][0].update(
        current_candidate_id=r["comparisons"][0]["recoded_candidate_id"]
    ),
    "row_mismatch_order": lambda r: incompatible(
        r, ["calibration_sha256", "model_sha256"]
    ),
    "row_null_reason_mismatch": nested(
        "comparisons.0.identity_mismatches", ["model_sha256"]
    ),
    "row_delta_unit": nested("comparisons.0.deltas.total.unit", "kcal/mol"),
    "row_delta_missing": lambda r: r["comparisons"][0]["deltas"].pop("up"),
    "row_feature_change_reason": nested(
        "comparisons.0.feature_changes.UP.reason", "feature_unavailable"
    ),
    "row_feature_change_missing": lambda r: r["comparisons"][0]["feature_changes"].pop(
        "itr"
    ),
}


@pytest.mark.parametrize("case", sorted(PROMOTER_REFUSALS))
def test_promoter_result_refusals(promoter_result, case):
    result = copy.deepcopy(promoter_result)
    PROMOTER_REFUSALS[case](result)
    assert not RESULT_VALIDATOR.is_valid(result)


RBS_REFUSALS: dict[str, Callable[[dict], object]] = {
    "profile_schema_version": nested("sides.current.prediction.schema_version", "1.2"),
    "profile_model": nested(
        "sides.recoded.prediction.model.id",
        "context2017-rnastructure-6.6-reconstruction-1",
    ),
    "native_site_rewritten": lambda r: r["sides"]["current"]["prediction"]["sites"][
        0
    ].update(status="done"),
    "settings_missing_profile": nested("settings.profile", KeyError),
    "codon_length": lambda r: first(r).update(codon_bases=[23, 24]),
    "codon_missing": lambda r: first(r).update(codon_bases=None),
    "candidate_calculator": lambda r: first(r).update(
        id=first(r)["id"].replace(":rbs:", ":promoter:")
    ),
    "scalar_unit": lambda r: first(r)["scalars"]["tir"].update(unit="source_dG_units"),
    "scalar_overflow_reason": lambda r: first(r)["scalars"]["tir"].update(
        value=None, reason="overflow"
    ),
    "feature_name": lambda r: first(r)["features"].update(
        **{"standby.loop": first(r)["features"]["window"]}
    ),
    "feature_index_name": lambda r: first(r)["features"].update(
        **{"standby.downstream_hairpins.01": first(r)["features"]["window"]}
    ),
    "feature_missing": lambda r: first(r)["features"].pop("coding_footprint"),
    "projected_feature_genomic_missing": lambda r: first(r)["features"][
        "window"
    ].update(genomic=None),
    "request_missing_host": nested("sides.recoded.request.host", KeyError),
    "validated_request_invalid": nested("sides.current.request.temperature_c", -1),
    "row_feature_change_name": lambda r: r["comparisons"][0]["feature_changes"].update(
        {"standby.loop": {"mapped_bases_equal": True, "reason": None}}
    ),
}


@pytest.mark.parametrize("profile", ["historical", "joint_standby"])
def test_rbs_result_refusals(algebra, profile):
    base = predict(scored_rbs_document(profile), algebra)
    names = set(first(base)["features"])
    assert any(n.startswith("standby.") for n in names) == (profile != "historical")
    for case, mutate in sorted(RBS_REFUSALS.items()):
        result = copy.deepcopy(base)
        mutate(result)
        assert not RESULT_VALIDATOR.is_valid(result), case
