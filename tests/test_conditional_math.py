"""Independent frozen arithmetic and binary64 boundary checks; no oracle imports."""

import json
import math
import time
from fractions import Fraction
from pathlib import Path

import pytest

from regsite import conditional_math as cm

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads(
    (ROOT / "benchmarks/riboswitch/conditional-fixtures.json").read_bytes()
)
EXAMPLES = json.loads(
    (ROOT / "benchmarks/riboswitch/conditional-request-examples.json").read_bytes()
)


def response_data(**changes):
    """A small synthetic input independent of sequence/experimental evidence."""
    data = json.loads(json.dumps(EXAMPLES["cases"][1]["request"]["input"]))
    data.update(changes)
    return data


@pytest.mark.parametrize(
    "case", FIXTURES["response_cases"], ids=lambda case: case["id"]
)
def test_frozen_response(case):
    values = {key: float(value) for key, value in case["inputs"].items()}
    data = response_data(beta_mol_per_kcal=values["beta_mol_per_kcal"])
    data["energies"].update(
        rna_off_kcal_mol=0.0,
        rna_on_kcal_mol=values["rna_structural_cost_kcal_mol"],
        ribosome_off_kcal_mol=values["ribosome_off_kcal_mol"],
        ribosome_on_kcal_mol=values["ribosome_on_kcal_mol"],
    )
    data["affinity"]["delta_g_kcal_mol"] = values["ligand_binding_kcal_mol"]
    data["occupancy"]["fraction"] = values["bound_fraction"]
    actual, cost, errors = cm.evaluate_response(
        data, {"max_iterations": 256}, time.monotonic() + 5
    )
    assert errors == []
    assert cost == values["rna_structural_cost_kcal_mol"]
    for key, expected in case["expected"].items():
        name = {
            "maximum_ratio": "ar_max",
            "concentration_ratio": "ar_conc",
            "actual_ratio": "ar_actual",
        }.get(key, key)
        if isinstance(expected, bool):
            assert actual[name] is expected
        else:
            assert actual[name] == pytest.approx(float(expected), rel=1e-13)


@pytest.mark.parametrize(
    "case", FIXTURES["partition_cases"], ids=lambda case: case["id"]
)
def test_frozen_partition(case):
    values = {key: float(value) for key, value in case["inputs"].items()}
    beta, switching = values.pop("beta_mol_per_kcal"), values.pop("switching_kcal_mol")
    actual = cm.solve_occupancy(
        dict(mode="published2015_volume", **values),
        beta,
        switching,
        256,
        time.monotonic() + 5,
    )
    for key, expected in case["expected"].items():
        value = (
            actual["fraction"]
            if key == "bound_fraction"
            else actual["status"]
            if key == "status"
            else actual["concentrations"][key]
        )
        if expected is None or key == "status":
            assert value == expected
        else:
            assert value == pytest.approx(float(expected), rel=1e-12, abs=1e-15)
    assert abs(actual["concentrations"]["mrna_balance_error_molar"]) <= 1e-15
    assert abs(actual["concentrations"]["ligand_balance_error_molar"]) <= 1e-15
    solver = actual["solver"]
    if values["mrna_total_molar"] and values["ligand_total_molar"]:
        low, high = solver["bracket_molar"]
        assert (high - low) / min(
            values["mrna_total_molar"], values["ligand_total_molar"]
        ) <= 1e-12
        assert abs(solver["scaled_residual"]) <= 1e-12
    else:
        assert solver == {
            "iterations": 0,
            "bracket_molar": [0.0, 0.0],
            "scaled_residual": None,
        }


@pytest.mark.parametrize(
    "case", FIXTURES["affinity_cases"], ids=lambda case: case["id"]
)
def test_frozen_affinity(case):
    # The independent fixture's decimal source values are converted only here.
    values = {key: float(value) for key, value in case["inputs"].items()}
    data = response_data(
        temperature_kelvin=values["temperature_kelvin"],
        affinity=dict(
            mode="kd",
            kd_molar=values["kd_molar"],
            standard_molar=values["standard_molar"],
        ),
    )
    actual, _, errors = cm.evaluate_response(
        data, {"max_iterations": 256}, time.monotonic() + 5
    )
    assert not errors
    expected = float(case["expected_binding_kcal_mol"])
    assert actual["ligand_binding_kcal_mol"] == pytest.approx(
        expected, rel=1e-13, abs=1e-15
    )


def test_exact_arithmetic_and_log_mixtures():
    assert cm.difference(1e308, -1e308 / 2) == 1.5e308
    assert cm.represent(Fraction(0)) == 0
    assert cm.mixture(1000, None) == 1
    assert cm.mixture(0, 0) == 1
    assert cm.mixture(800, -800) == pytest.approx(2)
    assert cm.mixture(-800, -800) == pytest.approx(1)
    assert cm.mixture(math.log(0.25), math.log(0.2)) == pytest.approx(0.85)
    assert cm.mixture(math.log(4), math.log(0.5)) == pytest.approx(2.5)
    for value in (Fraction(10) ** 400, Fraction(1, 10**400)):
        with pytest.raises(cm.ConditionalError, match="binary64"):
            cm.represent(value)
    for log in (1000, -1000):
        with pytest.raises(cm.ConditionalError, match="binary64"):
            cm.exponential(log)


def test_solver_exact_zero_small_and_unequal_scales():
    base = dict(
        mode="published2015_volume",
        mrna_total_molar=1.0,
        ligand_total_molar=1.0,
        solvent_molar=0.5,
        mrna_relative_volume=1.0,
        ligand_relative_volume=1.0,
    )
    exact = cm.solve_occupancy(base, 1, 0, 256, time.monotonic() + 5)
    assert exact["solver"] == dict(
        iterations=1, bracket_molar=[0.5, 0.5], scaled_residual=0
    )
    base.update(
        mrna_total_molar=1e-100, ligand_total_molar=1e-100, solvent_molar=1e-100
    )
    tiny = cm.solve_occupancy(base, 1, 0, 256, time.monotonic() + 5)
    assert tiny["fraction"] == pytest.approx((3 - math.sqrt(5)) / 2, rel=1e-12)
    base.update(mrna_total_molar=1e-9, ligand_total_molar=1.0, solvent_molar=1.0)
    unequal = cm.solve_occupancy(base, 1, 0, 256, time.monotonic() + 5)
    low, high = unequal["solver"]["bracket_molar"]
    assert (high - low) / 1e-9 <= 1e-12


@pytest.mark.parametrize(
    "changes,switch,iterations,code",
    [
        ({}, 0, 1, "nonconvergence"),
        ({}, 1e10, 256, "nonconvergence"),
        ({}, -1e10, 256, "numerical_range"),
        (
            {"mrna_total_molar": 5e-324, "ligand_total_molar": 5e-324},
            0,
            256,
            "numerical_range",
        ),
        ({"solvent_molar": 5e-324}, 0, 256, "numerical_range"),
        (
            {"mrna_relative_volume": 5e-324, "ligand_relative_volume": 1e308},
            0,
            256,
            "numerical_range",
        ),
    ],
)
def test_solver_failure(changes, switch, iterations, code):
    base = dict(
        mode="published2015_volume",
        mrna_total_molar=1.0,
        ligand_total_molar=1.0,
        solvent_molar=4.0,
        mrna_relative_volume=1.0,
        ligand_relative_volume=1.0,
    )
    base.update(changes)
    with pytest.raises(cm.ConditionalError) as caught:
        cm.solve_occupancy(base, 1, switch, iterations, time.monotonic() + 5)
    assert caught.value.code == code


def test_deadline_and_partial_response():
    data = response_data()
    actual, cost, errors = cm.evaluate_response(data, {"max_iterations": 256}, 0)
    assert cost is None
    assert actual["log_ar_max"] is None
    assert {error.code for error in errors} == {"deadline_exceeded"}
    data["energies"]["ribosome_on_kcal_mol"] = -800
    data["occupancy"]["fraction"] = math.exp(-740)
    actual, cost, errors = cm.evaluate_response(
        data, {"max_iterations": 256}, time.monotonic() + 5
    )
    assert actual["ar_max"] is None
    assert actual["log_ar_max"] == 800
    assert actual["ar_conc"] > 1e25
    assert cost == 1
    assert [error.code for error in errors] == ["numerical_range"]


@pytest.mark.parametrize(
    "mutation,field",
    [
        (
            lambda d: d["energies"].update(
                rna_off_kcal_mol=-1e308, rna_on_kcal_mol=1e308
            ),
            "switching_kcal_mol",
        ),
        (
            lambda d: (
                d["affinity"].update(mode="kd", kd_molar=1e308, standard_molar=1e-308)
                or d.update(temperature_kelvin=1e308)
            ),
            "ligand_binding_kcal_mol",
        ),
        (
            lambda d: (
                d["energies"].update(rna_on_kcal_mol=1e308)
                or d["affinity"].update(delta_g_kcal_mol=1e308)
            ),
            "switching_kcal_mol",
        ),
        (
            lambda d: (
                d.update(beta_mol_per_kcal=1e308)
                or d["energies"].update(ribosome_on_kcal_mol=10)
            ),
            "log_ar_max",
        ),
        (
            lambda d: (
                d.update(beta_mol_per_kcal=1e308)
                or d["energies"].update(rna_on_kcal_mol=10)
            ),
            "metastability_factor",
        ),
    ],
)
def test_independent_numerical_failures(mutation, field):
    data = response_data()
    mutation(data)
    actual, _, errors = cm.evaluate_response(
        data, {"max_iterations": 256}, time.monotonic() + 5
    )
    assert actual[field] is None
    assert errors and all(error.code == "numerical_range" for error in errors)


def test_metastability_underflow_preserves_actual_log_mixture():
    data = response_data()
    data["energies"].update(
        rna_off_kcal_mol=0, rna_on_kcal_mol=800, ribosome_on_kcal_mol=-800
    )
    data["affinity"]["delta_g_kcal_mol"] = 0
    data["occupancy"]["fraction"] = 1
    actual, _, errors = cm.evaluate_response(
        data, {"max_iterations": 256}, time.monotonic() + 5
    )
    assert actual["ar_max"] is None
    assert actual["ar_conc"] is None
    assert actual["metastability_factor"] is None
    assert actual["ar_actual"] == pytest.approx(2)
    assert len(errors) == 3


def test_near_standard_affinity_never_fabricates_zero():
    for standard in (1e300, 1e-300):
        kd = math.nextafter(standard, math.inf)
        assert math.log(kd) == math.log(standard)
        data = response_data(
            affinity=dict(mode="kd", kd_molar=kd, standard_molar=standard)
        )
        actual, _, errors = cm.evaluate_response(
            data, {"max_iterations": 256}, time.monotonic() + 5
        )
        assert not errors
        expected = (
            cm.GAS_CONSTANT
            * data["temperature_kelvin"]
            * math.log1p((kd - standard) / standard)
        )
        assert actual["ligand_binding_kcal_mol"] == pytest.approx(expected, rel=1e-14)
        assert actual["ligand_binding_kcal_mol"] > 0


def test_volume_range_failure_retains_solved_components():
    data = response_data(
        occupancy=dict(
            mode="published2015_volume",
            mrna_total_molar=1,
            ligand_total_molar=0,
            solvent_molar=5e-324,
            mrna_relative_volume=1,
            ligand_relative_volume=1,
        )
    )
    actual, _, errors = cm.evaluate_response(
        data, {"max_iterations": 256}, time.monotonic() + 5
    )
    assert [error.code for error in errors] == ["numerical_range"]
    occupancy = actual["occupancy"]
    assert occupancy["status"] == "failed"
    assert occupancy["fraction"] == 0
    assert occupancy["concentrations"]["complex_molar"] == 0
    assert occupancy["solver"]["iterations"] == 0
    assert occupancy["volume_fractions"] is None
    assert actual["ar_conc"] == actual["ar_actual"] == 1


def test_nonconvergence_keeps_last_bracket_and_residual():
    data = response_data(
        occupancy=dict(
            mode="published2015_volume",
            mrna_total_molar=1,
            ligand_total_molar=1,
            solvent_molar=4,
            mrna_relative_volume=2,
            ligand_relative_volume=1,
        )
    )
    actual, _, errors = cm.evaluate_response(
        data, {"max_iterations": 1}, time.monotonic() + 5
    )
    assert [error.code for error in errors] == ["nonconvergence"]
    solver = actual["occupancy"]["solver"]
    assert solver["iterations"] == 1
    assert solver["bracket_molar"] == [0, 0.5]
    assert math.isfinite(solver["scaled_residual"])
    assert actual["occupancy"]["concentrations"] is None


def test_certification_uses_bounded_second_precision(monkeypatch):
    calls = []
    original = cm.log_bounds

    def observe(ratio, precision):
        calls.append(precision)
        return original(ratio, precision)

    monkeypatch.setattr(cm, "log_bounds", observe)
    sign, residual, within = cm.certified_stationary(
        0.5, 1, 1e100, 1e100, 1, 1, Fraction(0), time.monotonic() + 5
    )
    assert sign == 1 and 0 < residual < 1e-99 and within
    assert calls == [80, 80, 160, 160]
    with pytest.raises(cm.ConditionalError, match="uncertifiable"):
        cm.certified_stationary(
            0.5, 1, 1e200, 1e200, 1, 1, Fraction(0), time.monotonic() + 5
        )
    assert calls[-4:] == [80, 80, 160, 160]
    with pytest.raises(cm.ConditionalError, match="deadline"):
        cm.certified_stationary(0.5, 1, 1, 1, 1, 1, Fraction(0), 0)


def test_log_interval_encloses_independent_high_precision_value():
    from decimal import Context, Decimal, Inexact, localcontext

    for ratio in (
        Fraction(1),
        Fraction(1, 3),
        Fraction(3),
        Fraction.from_float(1e-300),
        Fraction.from_float(1e300),
    ):
        low, high = cm.log_bounds(ratio, 80)
        with localcontext(Context(prec=220)):
            expected = (Decimal(ratio.numerator) / Decimal(ratio.denominator)).ln()
        assert low <= Fraction(expected) <= high
    with localcontext(Context(prec=2, Emax=2, Emin=-2)) as hostile:
        hostile.traps[Inexact] = True
        assert cm.log_bounds(Fraction(3), 80)[0] > 1


def test_exact_switching_survives_unrepresentable_display_cost():
    data = response_data()
    data["energies"].update(
        rna_off_kcal_mol=-1e308,
        rna_on_kcal_mol=1e308,
        ribosome_off_kcal_mol=0,
        ribosome_on_kcal_mol=0,
    )
    data["affinity"]["delta_g_kcal_mol"] = -1e308
    actual, cost, errors = cm.evaluate_response(
        data, {"max_iterations": 256}, time.monotonic() + 5
    )
    assert cost is None
    assert actual["switching_kcal_mol"] == 1e308
    assert actual["metastability_applied"] is True
    assert actual["ar_actual"] == 1
    assert errors and all(error.code == "numerical_range" for error in errors)
