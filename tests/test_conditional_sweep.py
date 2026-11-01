"""Concentration roster, independent algebra controls and failure accounting."""

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from regsite import conditional
from regsite import conditional_sweep as sweep
from regsite.conditional_math import ConditionalError


def example():
    return json.loads(Path("examples/conditional-sweep.json").read_text())


def assert_hashes(result):
    raw = json.dumps(
        {k: v for k, v in result.items() if k != "result_sha256"},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert result["result_sha256"] == hashlib.sha256(raw).hexdigest()
    for row in result["points"]:
        if row["native"] is not None:
            assert (
                row["native_json_sha256"]
                == hashlib.sha256(conditional.result_bytes(row["native"])).hexdigest()
            )


def test_exact_native_equivalence_order_duplicates_and_no_mutation():
    request = example()
    request["ligand_total_molar"] = [2, 0, 1, 1.0, 0.1]
    before = copy.deepcopy(request)
    result = sweep.sweep(request)
    assert request == before and result["status"] == "complete"
    assert [r["ligand_total_molar"] for r in result["points"]] == [
        2.0,
        0.0,
        1.0,
        1.0,
        0.1,
    ]
    assert [r["index"] for r in result["points"]] == list(range(5))
    for row in result["points"]:
        native_request = copy.deepcopy(request["template"])
        native_request["input"]["occupancy"]["ligand_total_molar"] = row[
            "ligand_total_molar"
        ]
        expected = conditional.predict_conditional(native_request)
        assert row["native"] == expected
        assert row["point_request_sha256"] == expected["request_sha256"]
    assert (
        result["points"][2]["native_json_sha256"]
        == result["points"][3]["native_json_sha256"]
    )
    assert result["coverage"]["attempted"] == 5 and result["coverage"]["not_run"] == 0
    assert_hashes(result)


def test_independent_equal_volume_quadratic_and_direction():
    request = example()
    data = request["template"]["input"]
    data["energies"].update(
        rna_off_kcal_mol=0,
        rna_on_kcal_mol=0,
        ribosome_off_kcal_mol=0,
        ribosome_on_kcal_mol=-math.log(4),
    )
    data["affinity"].update(delta_g_kcal_mol=0)
    data["occupancy"].update(
        mrna_total_molar=1,
        solvent_molar=4,
        mrna_relative_volume=1,
        ligand_relative_volume=1,
    )
    request["ligand_total_molar"] = [0, 0.1, 0.5, 1, 2, 10]
    result = sweep.sweep(request)
    assert result["status"] == "complete"
    amounts = []
    ratios = []
    for row, ligand in zip(
        result["points"], request["ligand_total_molar"], strict=True
    ):
        # Equal-volume and zero switching: 4b=(1-b)(l-b).
        expected = (
            0
            if ligand == 0
            else 2 * ligand / (5 + ligand + math.sqrt((5 + ligand) ** 2 - 4 * ligand))
        )
        occupancy = row["native"]["response"]["occupancy"]
        actual = occupancy["concentrations"]["complex_molar"]
        assert actual == pytest.approx(expected, rel=1e-10, abs=1e-12)
        assert 4 * actual == pytest.approx((1 - actual) * (ligand - actual), abs=1e-10)
        assert occupancy["fraction"] == pytest.approx(expected, abs=1e-12)
        assert row["native"]["response"]["ar_actual"] == pytest.approx(
            1 + 3 * expected, abs=1e-11
        )
        assert abs(occupancy["concentrations"]["mrna_balance_error_molar"]) < 1e-12
        assert abs(occupancy["concentrations"]["ligand_balance_error_molar"]) < 1e-12
        amounts.append(actual)
        ratios.append(row["native"]["response"]["ar_actual"])
    assert amounts == sorted(amounts) and ratios == sorted(ratios)
    data["energies"]["ribosome_on_kcal_mol"] = math.log(4)
    repressed = sweep.sweep(request)
    repression = [r["native"]["response"]["ar_actual"] for r in repressed["points"]]
    assert repression == sorted(repression, reverse=True)
    assert all(0.25 <= r <= 1 for r in repression)


def test_zero_rna_is_all_case_partial_with_null_response():
    request = example()
    request["template"]["input"]["occupancy"]["mrna_total_molar"] = 0
    result = sweep.sweep(request)
    assert result["status"] == "partial" and result["reason"] == "point_failures"
    assert result["coverage"]["attempted"] == 6 and result["coverage"]["failed"] == 6
    assert all(
        r["status"] == "no_mrna" and r["native"]["response"]["ar_actual"] is None
        for r in result["points"]
    )
    assert all(
        r["native"]["response"]["occupancy"]["concentrations"]["complex_molar"] == 0
        for r in result["points"]
    )


def test_solver_exhaustion_retains_successful_boundary():
    request = example()
    request["template"]["settings"]["max_iterations"] = 1
    result = sweep.sweep(request)
    assert result["status"] == "partial"
    assert result["points"][0]["status"] == "ok"
    assert any(r["status"] == "failed" for r in result["points"][1:])
    assert result["coverage"]["attempted"] == 6
    assert all(r["native"] is not None for r in result["points"])


@pytest.mark.parametrize(
    "path,bad",
    [
        ([], None),
        ([], []),
        (["schema_version"], "wrong"),
        (["template"], {}),
        (["template", "schema_version"], "wrong"),
        (["template", "profile"], "canonical_structure_pair"),
        (
            ["template", "input", "occupancy"],
            {"mode": "supplied_fraction", "fraction": 0.5},
        ),
        (["template", "id"], ""),
        (["template", "provenance", "kind"], "bad"),
        (["template", "settings", "max_iterations"], True),
        (["template", "input", "energies", "rna_on_kcal_mol"], -10),
        (["template", "input", "affinity", "standard_molar"], 0),
        (["ligand_total_molar"], []),
        (["ligand_total_molar"], None),
        (["ligand_total_molar"], [0] * 65),
        (["ligand_total_molar"], [-1]),
        (["ligand_total_molar"], [True]),
        (["ligand_total_molar"], ["1"]),
        (["ligand_total_molar"], [math.inf]),
        (["ligand_total_molar"], [math.nan]),
        (["ligand_total_molar"], [10**400]),
        (["seconds_total"], 0),
        (["seconds_total"], 120.1),
        (["seconds_total"], False),
        (["seconds_total"], "30"),
    ],
)
def test_complete_admission_precedes_any_prediction(monkeypatch, path, bad):
    def forbidden(*args, **kwargs):
        raise AssertionError("prediction before admission")

    monkeypatch.setattr(conditional, "predict_conditional", forbidden)
    value = example()
    if path:
        target = value
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = bad
    else:
        value = bad
    result = sweep.sweep(value)
    assert (
        result["status"] == "invalid_input"
        and result["points"] == []
        and result["coverage"] is None
    )
    assert_hashes(result)


@pytest.mark.parametrize("nested", [False, True])
def test_unknown_fields_and_nonjson_library_values(monkeypatch, nested):
    value = example()
    (value["template"] if nested else value)["unknown"] = 1
    assert sweep.sweep(value)["status"] == "invalid_input"
    value = example()
    value["ligand_total_molar"] = (0, 1)
    assert sweep.sweep(value)["status"] == "invalid_input"


def test_exact_roster_boundary_and_finite_extremes():
    value = example()
    value["ligand_total_molar"] = [0] * 64
    value["seconds_total"] = 120
    result = sweep.sweep(value)
    assert result["status"] == "complete" and len(result["points"]) == 64
    for point in [math.ulp(0.0), 1.7976931348623157e308]:
        value["ligand_total_molar"] = [point]
        _, generated = sweep.parse_request(value)
        assert generated[0]["input"]["occupancy"]["ligand_total_molar"] == point


@pytest.mark.parametrize("code", ["numerical_range", "deadline", "parameter_integrity"])
def test_native_exception_accounting(monkeypatch, code):
    def fail(*args, **kwargs):
        raise ConditionalError(code, "artificial")

    monkeypatch.setattr(conditional, "predict_conditional", fail)
    result = sweep.sweep(example())
    assert result["status"] == "partial" and result["coverage"]["attempted"] == 6
    assert all(r["reasons"] == [code] and r["native"] is None for r in result["points"])


@pytest.mark.parametrize("exception", [OSError("x"), UnicodeError("x")])
def test_native_unavailable(monkeypatch, exception):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(conditional, "predict_conditional", fail)
    result = sweep.sweep(example())
    assert all(
        r["reasons"] == ["prediction_execution_failed"] for r in result["points"]
    )


@pytest.mark.parametrize(
    "path,bad",
    [
        ([], []),
        ([], {}),
        (["request_sha256"], "0" * 64),
        (["model", "parameter_sha256"], "0" * 64),
        (["profile"], "canonical_structure_pair"),
        (["id"], "different"),
        (["input"], {}),
        (["provenance"], {}),
        (["settings"], {}),
        (["states"], [{}]),
        (["status"], "invalid"),
        (["status"], []),
        (["reasons"], None),
        (["reasons"], [""]),
        (["complete"], 1),
        (["complete"], False),
        (["response"], None),
        (["reasons"], ["bad"]),
    ],
)
def test_native_shape_or_identity_stops_without_losing_roster(monkeypatch, path, bad):
    original = conditional.predict_conditional

    def modified(request):
        native = original(request)
        if not path:
            return bad
        cursor = native
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = bad
        return native

    monkeypatch.setattr(conditional, "predict_conditional", modified)
    result = sweep.sweep(example())
    assert (
        result["status"] == "partial"
        and result["coverage"]["attempted"] == 1
        and result["coverage"]["not_run"] == 5
    )
    assert result["points"][0]["status"] == "failed"
    assert all(r["status"] == "not_run" for r in result["points"][1:])
    assert_hashes(result)


@pytest.mark.parametrize("kind", ["nonfinite", "recursive", "missing"])
def test_unserializable_or_missing_native(monkeypatch, kind):
    def broken(request):
        if kind == "missing":
            return {"model": {}}
        value = {"x": math.inf}
        if kind == "recursive":
            value["x"] = value
        return value

    monkeypatch.setattr(conditional, "predict_conditional", broken)
    result = sweep.sweep(example())
    assert result["coverage"]["attempted"] == 1
    sweep.result_bytes(result)


@pytest.mark.parametrize("status", ["failed", "unsupported", "invalid_input"])
def test_native_status_remains_visible(monkeypatch, status):
    original = conditional.predict_conditional

    def change(request):
        native = original(request)
        native.update(
            status=status, complete=False, reasons=["artificial"], response=None
        )
        return native

    monkeypatch.setattr(conditional, "predict_conditional", change)
    result = sweep.sweep(example())
    assert result["coverage"]["attempted"] == 6
    assert all(
        r["status"] == status and r["native"]["status"] == status
        for r in result["points"]
    )


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.mark.parametrize("phase", ["preflight", "between", "final_late", "exact_final"])
def test_cooperative_deadline_retains_every_point(monkeypatch, phase):
    # Replace only the sweep module's clock, leaving native numerical clocks intact.
    clock = Clock()
    monkeypatch.setattr(sweep, "time", type("Time", (), {"monotonic": clock}))
    original_parse = sweep.parse_request
    original_predict = conditional.predict_conditional
    calls = []

    def parse(value):
        result = original_parse(value)
        if phase == "preflight":
            clock.now = 1.0
        return result

    def predict(request):
        calls.append(copy.deepcopy(request))
        result = original_predict(request)
        if phase == "between":
            clock.now = 2.0
        elif len(calls) == 6:
            clock.now = 2.0 if phase == "final_late" else 1.0
        return result

    monkeypatch.setattr(sweep, "parse_request", parse)
    monkeypatch.setattr(conditional, "predict_conditional", predict)
    request = example()
    request["seconds_total"] = 1
    result = sweep.sweep(request)
    assert len(result["points"]) == 6
    assert (
        len(calls)
        == {"preflight": 0, "between": 1, "final_late": 6, "exact_final": 6}[phase]
    )
    assert all(c["settings"] == request["template"]["settings"] for c in calls)
    assert result["status"] == ("complete" if phase == "exact_final" else "partial")
    assert result["coverage"]["deadline_exceeded"] == (phase != "exact_final")
    if phase == "final_late":
        assert all(r["status"] == "ok" for r in result["points"])


def test_native_cap_and_hash_retention(monkeypatch):
    value = example()
    value["ligand_total_molar"] = [0]
    _, requests = sweep.parse_request(value)
    native = conditional.predict_conditional(requests[0])
    raw = conditional.result_bytes(native)
    size = len(raw) + 6 * len(raw.splitlines())
    monkeypatch.setattr(sweep, "NATIVE_LIMIT", size)
    assert sweep.sweep(value)["status"] == "complete"
    monkeypatch.setattr(sweep, "NATIVE_LIMIT", size - 1)
    result = sweep.sweep(value)
    row = result["points"][0]
    assert (
        row["native"] is None
        and row["native_json_sha256"] == hashlib.sha256(raw).hexdigest()
    )
    assert row["reasons"] == ["native_result_limit"]


def test_authoritative_result_bytes_caps_and_unsupported_values(monkeypatch):
    value = sweep.invalid_result("test")
    raw = (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode()
    monkeypatch.setattr(sweep, "OUTPUT_LIMIT", len(raw))
    assert sweep.result_bytes(value) == raw
    monkeypatch.setattr(sweep, "OUTPUT_LIMIT", len(raw) - 1)
    with pytest.raises(sweep.SweepError, match="output_byte_limit"):
        sweep.result_bytes(value)
    for bad in [float("nan"), object()]:
        with pytest.raises(sweep.SweepError, match="result_serialization_failure"):
            sweep.result_bytes({"x": bad})
