"""Check proposed synthetic requests without importing a production predictor."""

import hashlib
import json
import math
from pathlib import Path

import pytest

ROOT = Path("benchmarks/riboswitch")
EXAMPLES = json.loads((ROOT / "conditional-request-examples.json").read_bytes())


def test_examples_are_explicit_synthetic_single_profile_requests():
    assert EXAMPLES["runtime_executed"] is False
    assert len(EXAMPLES["cases"]) == 3
    for case in EXAMPLES["cases"]:
        request = case["request"]
        assert set(request) == {
            "schema_version",
            "id",
            "profile",
            "input",
            "provenance",
            "settings",
        }
        assert request["schema_version"] == "conditional-aptamer-request-1"
        assert request["provenance"]["kind"] == "synthetic"
        assert set(request["provenance"]) == {"kind", "reference"}
        assert request["input"]["temperature_kelvin"] == 310.15
        # This also refuses any accidental JSON nonfinite numerical value.
        json.dumps(request, allow_nan=False)


def test_structural_example_reuses_exact_existing_backend_control():
    raw = (ROOT / "canonical-receipt.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "7c474565160ba5fad4011769c3dad56018241e92e2bf9212f5855a172a99ef20"
    )
    receipt = {case["id"]: case for case in json.loads(raw)["cases"]}
    example = EXAMPLES["cases"][0]
    request, expected = example["request"], example["expected_slice"]
    data = request["input"]
    assert request["profile"] == "canonical_structure_pair"
    assert set(data) == {"sequence", "aptamer", "temperature_kelvin"}
    assert set(data["aptamer"]) == {"id", "range", "constraint"}
    assert data["aptamer"]["range"] == [0, len(data["sequence"])]
    assert data["aptamer"]["constraint"] == {
        "mode": "full",
        "structure": "((((((....))))))",
    }
    assert request["settings"] == {
        "seconds_per_job": 120.0,
        "seconds_total": 480.0,
    }
    for key in ("hairpin_unconstrained", "hairpin_full"):
        state = receipt[key]
        assert state["status"] == "ok"
        assert data["sequence"] == state["sequence"]
        assert [[i - 1, j - 1] for i, j in state["pairs"]] == (
            expected["zero_based_pairs"]
        )
        assert state["efn2_energy"] == -11.2
    assert [i - 1 for i in receipt["hairpin_full"]["forced_unpaired"]] == (
        expected["forced_unpaired"]
    )
    assert expected["unconstrained_efn2_kcal_mol"] == -11.2
    assert expected["constraint_compatible_efn2_kcal_mol"] == -11.2
    assert expected["structural_cost_kcal_mol"] == 0
    assert expected["response"] is None


@pytest.mark.parametrize("index", [1, 2])
def test_supplied_energy_examples_have_independent_scalar_expectations(index):
    case = EXAMPLES["cases"][index]
    request = case["request"]
    assert request["profile"] == "supplied_energy_response"
    data = request["input"]
    assert set(data) == {
        "temperature_kelvin",
        "beta_mol_per_kcal",
        "energies",
        "energy_basis",
        "affinity",
        "occupancy",
    }
    assert request["settings"] == {"seconds_total": 30.0, "max_iterations": 256}
    assert set(data["energy_basis"]) == {"rna", "ribosome"}
    for basis in data["energy_basis"].values():
        assert set(basis) == {
            "source_id",
            "model_id",
            "parameter_sha256",
            "backend_sha256",
            "sequence_sha256",
        }
        assert basis["source_id"] == "synthetic-explicit-energies"
        assert basis["parameter_sha256"] is None
        assert basis["backend_sha256"] is None
        assert basis["sequence_sha256"] is None
    energy = data["energies"]
    beta = data["beta_mol_per_kcal"]
    maximum = math.exp(
        -beta * (energy["ribosome_on_kcal_mol"] - energy["ribosome_off_kcal_mol"])
    )
    assert math.isclose(maximum, 4, rel_tol=1e-14)
    switching = (
        energy["rna_on_kcal_mol"]
        - energy["rna_off_kcal_mol"]
        + data["affinity"]["delta_g_kcal_mol"]
    )
    if index == 1:
        assert data["occupancy"] == {"mode": "supplied_fraction", "fraction": 0.5}
        assert switching < 0
        assert case["expected_slice"]["ar_conc"] == (1 + maximum) / 2
        assert case["expected_slice"]["ar_actual"] == 2.5
        assert case["expected_slice"]["metastability_applied"] is False
    else:
        volume = data["occupancy"]
        assert volume == {
            "mode": "published2015_volume",
            "mrna_total_molar": 1.0,
            "ligand_total_molar": 1.0,
            "solvent_molar": 4.0,
            "mrna_relative_volume": 2.0,
            "ligand_relative_volume": 1.0,
        }
        # b=1/5 gives D=2ln(1/4)-ln(1/5)+ln(16/5)=0.
        assert abs(2 * math.log(1 / 4) - math.log(1 / 5) + beta * switching) < 1e-14
        factor = 1 / (1 + math.exp(beta * switching))
        actual = 1 + factor * (0.2 * (maximum - 1))
        assert math.isclose(factor, 5 / 21, rel_tol=1e-14)
        assert math.isclose(actual, 8 / 7, rel_tol=1e-14)
        assert case["expected_slice"]["ar_actual"] == "8/7"
        assert case["expected_slice"]["metastability_factor"] == "5/21"
        assert case["expected_slice"]["bound_fraction"] == 0.2
        assert case["expected_slice"]["ar_conc"] == 1.6
        assert case["expected_slice"]["metastability_applied"] is True
