"""Frozen arithmetic expectations and independent equilibrium checks."""

import copy
import hashlib
import json
from decimal import ROUND_DOWN, Decimal, localcontext
from pathlib import Path

import pytest

from benchmarks.riboswitch import conditional_reference as reference

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "benchmarks/riboswitch/conditional-fixtures.json"
FIXTURES = json.loads(FIXTURE_PATH.read_text())
FUNCTIONS = {
    "response": reference.response,
    "affinity": reference.affinity,
    "partition": reference.partition,
}
BASE_INPUTS = {name: FIXTURES[f"{name}_cases"][0]["inputs"] for name in FUNCTIONS}


def assert_close(actual, expected, tolerance="1e-58"):
    """Compare in a separate high-precision context, with explicit tolerance."""
    assert isinstance(actual, Decimal)
    assert actual.is_finite()
    with localcontext() as context:
        context.prec = 80
        expected = Decimal(expected)
        assert abs(actual - expected) <= Decimal(tolerance) * max(1, abs(expected))


def residual(inputs, bound):
    """Evaluate D with separately expanded logarithms, independent of the solver."""
    values = {key: Decimal(value) for key, value in inputs.items()}
    mrna_free = values["mrna_total_molar"] - bound
    ligand_free = values["ligand_total_molar"] - bound
    vm, vl = values["mrna_relative_volume"], values["ligand_relative_volume"]
    return (
        vm * (bound.ln() - mrna_free.ln())
        - vl * (vl.ln() + ligand_free.ln() - values["solvent_molar"].ln())
        + values["beta_mol_per_kcal"] * values["switching_kcal_mol"]
    )


def objective(inputs, bound):
    """An antiderivative of the specified D, defined up to an additive constant."""
    values = {key: Decimal(value) for key, value in inputs.items()}
    mrna_free = values["mrna_total_molar"] - bound
    ligand_free = values["ligand_total_molar"] - bound
    vm, vl = values["mrna_relative_volume"], values["ligand_relative_volume"]
    solvent = values["solvent_molar"]
    terms = (
        vm * mrna_free / solvent,
        vl * ligand_free / solvent,
        vm * bound / solvent,
    )
    return solvent * sum(x * (x.ln() - 1) for x in terms) + (
        values["beta_mol_per_kcal"] * values["switching_kcal_mol"] * bound
    )


def test_frozen_fixture_identity():
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == (
        "a4be58ed590267a4d6d3b39e6e456241c92b911beb084bcab3b74c0537df8165"
    )
    assert len(FIXTURES["response_cases"]) == 8
    assert len(FIXTURES["partition_cases"]) == 6
    assert len(FIXTURES["affinity_cases"]) == 3
    assert len(FIXTURES["invalid_cases"]) == 21


@pytest.mark.parametrize("case", FIXTURES["response_cases"], ids=lambda c: c["id"])
def test_response_frozen_expectations(case):
    actual = reference.response(case["inputs"])
    for key, expected in case["expected"].items():
        if isinstance(expected, bool):
            assert actual[key] is expected
        else:
            assert_close(actual[key], expected)
    with localcontext() as context:
        context.prec = 80
        beta = Decimal(case["inputs"]["beta_mol_per_kcal"])
        difference = Decimal(case["inputs"]["ribosome_on_kcal_mol"]) - Decimal(
            case["inputs"]["ribosome_off_kcal_mol"]
        )
        assert actual["log_maximum_ratio"] == -beta * difference
        switching = Decimal(case["inputs"]["rna_structural_cost_kcal_mol"]) + Decimal(
            case["inputs"]["ligand_binding_kcal_mol"]
        )
        assert actual["switching_kcal_mol"] == switching
        expected_factor = (
            1 / (1 + (beta * switching).exp()) if switching > 0 else Decimal(1)
        )
        assert_close(actual["metastability_factor"], expected_factor, "1e-78")


@pytest.mark.parametrize("case", FIXTURES["affinity_cases"], ids=lambda c: c["id"])
def test_affinity_frozen_expectations(case):
    assert_close(reference.affinity(case["inputs"]), case["expected_binding_kcal_mol"])


@pytest.mark.parametrize("case", FIXTURES["partition_cases"], ids=lambda c: c["id"])
def test_partition_frozen_expectations_and_conservation(case):
    result = reference.partition(case["inputs"])
    for key, expected in case["expected"].items():
        if expected is None or key == "status":
            assert result[key] == expected
        else:
            assert_close(result[key], expected, "1e-49")
    with localcontext() as context:
        context.prec = 80
        values = {key: Decimal(value) for key, value in case["inputs"].items()}
        bound = result["complex_molar"]
        assert bound >= 0
        for species in ("mrna", "ligand"):
            free = result[f"{species}_free_molar"]
            assert free >= 0
            assert free + bound == values[f"{species}_total_molar"]
            assert result[f"{species}_free_volume_fraction"] == (
                values[f"{species}_relative_volume"] * free / values["solvent_molar"]
            )
        assert result["complex_volume_fraction"] == (
            values["mrna_relative_volume"] * bound / values["solvent_molar"]
        )
        assert result["volume_fraction_sum"] == sum(
            result[key]
            for key in (
                "mrna_free_volume_fraction",
                "ligand_free_volume_fraction",
                "complex_volume_fraction",
            )
        )
        assert result["volume_fraction_sum_exceeds_one"] is False
        if bound == 0:
            assert result["solver_bracket_molar"] == (0, 0)
            assert result["solver_residual"] is None
            assert result["solver_residual_scale"] is None
            assert result["solver_iterations"] == 0


@pytest.mark.parametrize("case", FIXTURES["partition_cases"][:3], ids=lambda c: c["id"])
def test_partition_stationarity_bracket_and_convex_minimum(case):
    result = reference.partition(case["inputs"])
    with localcontext() as context:
        context.prec = 80
        values = {key: Decimal(value) for key, value in case["inputs"].items()}
        mrna, ligand = values["mrna_total_molar"], values["ligand_total_molar"]
        bound = result["complex_molar"]
        lower, upper = result["solver_bracket_molar"]
        tolerance = result["solver_tolerance"]
        scale = result["solver_residual_scale"]
        assert 0 < lower <= bound <= upper < min(mrna, ligand)
        assert tolerance <= Decimal("1e-40")
        assert (upper - lower) / min(mrna, ligand) <= tolerance
        assert (upper - lower) / mrna <= tolerance
        assert abs(residual(case["inputs"], bound)) / scale <= tolerance
        assert_close(
            result["solver_residual"], residual(case["inputs"], bound), "1e-77"
        )
        assert residual(case["inputs"], lower) <= Decimal("1e-77") * scale
        assert residual(case["inputs"], upper) >= -Decimal("1e-77") * scale
        assert 1 <= result["solver_iterations"] <= 256
        step = min(bound, mrna - bound, ligand - bound) / 1000
        below, at, above = (
            objective(case["inputs"], point)
            for point in (bound - step, bound, bound + step)
        )
        assert below > at < above
        assert below - 2 * at + above > 0
        assert residual(case["inputs"], bound - step) < 0
        assert residual(case["inputs"], bound + step) > 0
        for point in (bound - step, bound, bound + step):
            second_derivative = values["mrna_relative_volume"] * (
                1 / point + 1 / (mrna - point)
            ) + values["ligand_relative_volume"] / (ligand - point)
            assert second_derivative > 0


@pytest.mark.parametrize("case", FIXTURES["invalid_cases"])
def test_frozen_invalid_inputs(case):
    inputs = {**BASE_INPUTS[case["function"]], case["field"]: case["value"]}
    with pytest.raises(ValueError, match=case["field"]):
        FUNCTIONS[case["function"]](inputs)


@pytest.mark.parametrize("name", FUNCTIONS)
@pytest.mark.parametrize("invalid", [None, [], True, 1, "{}", {}, {"unexpected": "1"}])
def test_exact_dictionary_schema(name, invalid):
    with pytest.raises(ValueError, match="exactly the required fields"):
        FUNCTIONS[name](invalid)


@pytest.mark.parametrize("name", FUNCTIONS)
def test_reject_missing_and_extra_keys(name):
    missing = dict(BASE_INPUTS[name])
    del missing[next(iter(missing))]
    for inputs in (missing, {**BASE_INPUTS[name], "extra": "1"}):
        with pytest.raises(ValueError, match="exactly the required fields"):
            FUNCTIONS[name](inputs)


@pytest.mark.parametrize("name", FUNCTIONS)
@pytest.mark.parametrize(
    "invalid",
    [
        True,
        False,
        1,
        1.0,
        Decimal("1"),
        None,
        "",
        "1" * 129,
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        "1_000",
        " 1",
        "1\n",
        "١",
        ".",
        "1e",
        "--1",
    ],
)
def test_decimal_string_validation(name, invalid):
    field = next(iter(BASE_INPUTS[name]))
    with pytest.raises(ValueError, match=f"{field}: expected a finite decimal string"):
        FUNCTIONS[name]({**BASE_INPUTS[name], field: invalid})


@pytest.mark.parametrize("invalid", ["1e1001", "-1e1001", "1e-1001"])
def test_documented_input_exponent_limits(invalid):
    with pytest.raises(ValueError, match="adjusted exponent"):
        reference.affinity({**BASE_INPUTS["affinity"], "kd_molar": invalid})


def test_unrepresentable_decimal_exponent_is_value_error():
    with pytest.raises(
        ValueError, match="affinity: unsafe Decimal numeric range or domain"
    ):
        reference.affinity({**BASE_INPUTS["affinity"], "kd_molar": "1e" + "9" * 100})


@pytest.mark.parametrize("invalid", [True, False, "1", Decimal(2), 1.0, 0, -1, 257])
def test_iteration_limit_type_and_range(invalid):
    with pytest.raises(ValueError, match="max_iterations: must be an integer"):
        reference.partition(BASE_INPUTS["partition"], max_iterations=invalid)


def test_iteration_exhaustion_and_boundary_with_one_iteration():
    with pytest.raises(
        ValueError, match="convergence not reached within max_iterations"
    ):
        reference.partition(BASE_INPUTS["partition"], max_iterations=1)
    result = reference.partition(
        FIXTURES["partition_cases"][3]["inputs"], max_iterations=1
    )
    assert result["status"] == "ok"
    assert result["solver_iterations"] == 0


@pytest.mark.parametrize("energy", ["1e1000", "-1e1000"])
def test_extreme_unresolved_interior_root_is_not_clipped(energy):
    inputs = {**BASE_INPUTS["partition"], "switching_kcal_mol": energy}
    with pytest.raises(ValueError, match="interior root may exceed numeric resolution"):
        reference.partition(inputs)


@pytest.mark.parametrize("energy", ["1e6", "-1e6"])
def test_unsafe_response_exponential_is_explicit_failure(energy):
    inputs = {**BASE_INPUTS["response"], "ribosome_on_kcal_mol": energy}
    with pytest.raises(
        ValueError, match="response: unsafe Decimal numeric range or domain"
    ):
        reference.response(inputs)


def test_unsafe_metastability_exponential_is_explicit_failure():
    inputs = {**BASE_INPUTS["response"], "ligand_binding_kcal_mol": "1e6"}
    with pytest.raises(
        ValueError, match="response: unsafe Decimal numeric range or domain"
    ):
        reference.response(inputs)


@pytest.mark.parametrize("name", FUNCTIONS)
def test_determinism_caller_data_and_global_context_unchanged(name):
    inputs = copy.deepcopy(BASE_INPUTS[name])
    original = copy.deepcopy(inputs)
    expected = FUNCTIONS[name](inputs)
    with localcontext() as hostile:
        hostile.prec = 7
        hostile.rounding = ROUND_DOWN
        hostile.Emin, hostile.Emax = -2, 2
        hostile.clamp = 1
        for signal in hostile.traps:
            hostile.traps[signal] = True
            hostile.flags[signal] = True
        before = str(hostile)
        assert FUNCTIONS[name](inputs) == expected
        assert FUNCTIONS[name](inputs) == expected
        with pytest.raises(ValueError):
            FUNCTIONS[name]({**inputs, "unknown": "1"})
        assert str(hostile) == before
    assert inputs == original


def test_response_strict_zero_discontinuity():
    inputs = FIXTURES["response_cases"][4]["inputs"]
    at_zero = reference.response(inputs)
    above = reference.response(
        {**inputs, "rna_structural_cost_kcal_mol": "1." + "0" * 59 + "1"}
    )
    below = reference.response(
        {**inputs, "rna_structural_cost_kcal_mol": "0." + "9" * 60}
    )
    assert at_zero["metastability_applied"] is False
    assert below["metastability_applied"] is False
    assert above["metastability_applied"] is True
    assert at_zero["metastability_factor"] == below["metastability_factor"] == 1
    assert_close(above["metastability_factor"], "0.5", "1e-59")
    assert_close(at_zero["actual_ratio"], "2.5")
    assert_close(above["actual_ratio"], "1.75")


def test_tiny_repression_ratio_retains_positive_value_and_zero_occupancy_is_one():
    inputs = {
        **BASE_INPUTS["response"],
        "ribosome_on_kcal_mol": "1000",
        "bound_fraction": "1",
    }
    result = reference.response(inputs)
    assert 0 < result["actual_ratio"] < Decimal("1e-400")
    assert (
        result["actual_ratio"]
        == result["concentration_ratio"]
        == result["maximum_ratio"]
    )
    zero = reference.response({**inputs, "bound_fraction": "0"})
    assert zero["actual_ratio"] == zero["concentration_ratio"] == 1
    positive_cost_zero = reference.response(
        {**inputs, "bound_fraction": "0", "ligand_binding_kcal_mol": "1"}
    )
    assert positive_cost_zero["actual_ratio"] == 1


def test_equivalent_affinities_encoded_in_molar_and_explicit_standard_state():
    base = {**BASE_INPUTS["affinity"], "kd_molar": "0.000001"}
    expected = reference.affinity(base)
    # 1 micromolar and 1000 nanomolar, each converted to molar before submission.
    for kd in ("1e-6", "1000e-9", "+0.000001000", "01e-6"):
        assert reference.affinity({**base, "kd_molar": kd}) == expected
    shifted = reference.affinity({**base, "standard_molar": ".001"})
    with localcontext() as context:
        context.prec = 80
        assert_close(shifted * 2, expected, "1e-78")
    assert reference.affinity({**base, "kd_molar": "2"}) > 0
    assert reference.affinity({**base, "kd_molar": "1" + "0" * 127}) > 0


def test_large_affinity_inputs_remain_finite_across_documented_range():
    result = reference.affinity(
        {
            "kd_molar": "1e1000",
            "standard_molar": "1e-1000",
            "temperature_kelvin": "1e1000",
        }
    )
    assert result.is_finite() and result > Decimal("1e1000")


@pytest.mark.parametrize("exponent", [-900, 900])
def test_partition_uniform_concentration_scaling_preserves_occupancy(exponent):
    base = FIXTURES["partition_cases"][2]["inputs"]
    with localcontext() as context:
        context.prec = 80
        scale = Decimal(f"1e{exponent}")
        inputs = {
            **base,
            **{
                key: str(Decimal(base[key]) * scale)
                for key in ("mrna_total_molar", "ligand_total_molar", "solvent_molar")
            },
        }
        result = reference.partition(inputs)
        assert_close(
            result["bound_fraction"],
            FIXTURES["partition_cases"][2]["expected"]["bound_fraction"],
            "1e-49",
        )
        assert result["complex_molar"] > 0
        assert result["complex_molar"] + result["mrna_free_molar"] == scale


def test_no_packing_constraint_and_large_boundary_volumes():
    inputs = {
        **BASE_INPUTS["partition"],
        "mrna_total_molar": "1",
        "ligand_total_molar": "1",
        "mrna_relative_volume": "1",
        "solvent_molar": "0.01",
        "switching_kcal_mol": "0",
    }
    result = reference.partition(inputs)
    assert result["volume_fraction_sum"] > 100
    assert result["volume_fraction_sum_exceeds_one"] is True
    with localcontext() as context:
        context.prec = 80
        assert abs(residual(inputs, result["complex_molar"])) < Decimal("1e-50")
    boundary = reference.partition(
        {
            **inputs,
            "mrna_total_molar": "1e1000",
            "ligand_total_molar": "0",
            "mrna_relative_volume": "1e1000",
            "solvent_molar": "1e-1000",
        }
    )
    assert boundary["volume_fraction_sum"] == Decimal("1e3000")
    assert boundary["bound_fraction"] == 0


def test_unequal_totals_preserve_limiting_ligand():
    inputs = {
        **BASE_INPUTS["partition"],
        "mrna_total_molar": "2",
        "ligand_total_molar": "0.1",
        "ligand_relative_volume": "3",
    }
    result = reference.partition(inputs)
    assert 0 < result["complex_molar"] < Decimal("0.1")
    assert 0 < result["bound_fraction"] < Decimal("0.05")
    with localcontext() as context:
        context.prec = 80
        assert result["complex_molar"] + result["ligand_free_molar"] == Decimal("0.1")
        assert abs(residual(inputs, result["complex_molar"])) < Decimal("1e-49")


def test_existing_five_beta_point_45_fixtures():
    path = ROOT / "benchmarks/other-calculators/riboswitch-scalar-fixtures.json"
    fixtures = json.loads(path.read_text())
    assert len(fixtures["cases"]) == 5
    for case in fixtures["cases"]:
        result = reference.response(
            {
                "beta_mol_per_kcal": case["beta"],
                "rna_structural_cost_kcal_mol": "0",
                "ligand_binding_kcal_mol": case["switching_score"],
                "ribosome_off_kcal_mol": case["score_off"],
                "ribosome_on_kcal_mol": case["score_on"],
                "bound_fraction": case["assumed_bound_fraction"],
            }
        )
        for key in ("maximum_ratio", "concentration_ratio", "actual_ratio"):
            assert_close(result[key], case[key], "1e-47")
