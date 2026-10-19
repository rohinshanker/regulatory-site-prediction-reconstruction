"""Public raw-document validation, partial results, identities and refusal checks."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from regsite import conditional as c
from regsite.conditional_backend import canonical_bytes
from regsite.conditional_math import ConditionalError

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = json.loads(
    (ROOT / "benchmarks/riboswitch/conditional-request-examples.json").read_bytes()
)["cases"]
FIXTURES = json.loads(
    (ROOT / "benchmarks/riboswitch/conditional-fixtures.json").read_bytes()
)


def request(structural=False):
    return copy.deepcopy(EXAMPLES[0 if structural else 1]["request"])


def replace(document, path, value):
    parts = path.split(".")
    for part in parts[:-1]:
        document = document[int(part)] if type(document) is list else document[part]
    if value is DELETE:
        del document[parts[-1]]
    elif type(document) is list:
        document[int(parts[-1])] = value
    else:
        document[parts[-1]] = value


DELETE = object()


@pytest.mark.parametrize(
    "path,value,code",
    [
        ("extra", 1, "unexpected_field"),
        ("id", DELETE, "missing_field"),
        ("schema_version", "other", "unsupported_schema"),
        ("id", "", "invalid_string"),
        ("id", "x" * 129, "invalid_string"),
        ("id", True, "invalid_string"),
        ("profile", "kinetic", "unsupported_profile"),
        ("provenance", [], "invalid_object"),
        ("provenance.kind", "measured", "invalid_provenance"),
        ("provenance.reference", "", "invalid_string"),
        ("provenance.reference", "x" * 1025, "invalid_string"),
        ("settings.max_iterations", True, "invalid_position"),
        ("settings.max_iterations", 0, "position_out_of_range"),
        ("settings.max_iterations", 257, "position_out_of_range"),
        ("settings.seconds_total", 30.01, "invalid_number"),
        ("settings.seconds_total", False, "invalid_number"),
        ("input.temperature_kelvin", 0, "invalid_number"),
        ("input.beta_mol_per_kcal", -1, "invalid_number"),
        ("input.energies.rna_on_kcal_mol", -3, "negative_structural_cost"),
        ("input.energies.rna_on_kcal_mol", 10**309, "invalid_number"),
        ("input.energy_basis", [], "invalid_object"),
        ("input.energy_basis.rna.model_id", 3, "invalid_string"),
        ("input.energy_basis.rna.parameter_sha256", "A" * 64, "invalid_hash"),
        ("input.energy_basis.rna.backend_sha256", False, "invalid_hash"),
        ("input.affinity", None, "invalid_object"),
        ("input.affinity.mode", "hill", "unsupported_affinity"),
        ("input.affinity.standard_molar", 0, "invalid_number"),
        ("input.occupancy", None, "invalid_object"),
        ("input.occupancy.mode", "hill", "unsupported_occupancy"),
        ("input.occupancy.fraction", 1.1, "invalid_number"),
        ("input.occupancy.fraction", -0.1, "invalid_number"),
    ],
)
def test_public_invalid_before_backend(monkeypatch, path, value, code):
    monkeypatch.setattr(
        c, "verify_backend", lambda *_: pytest.fail("Invalid request ran backend")
    )
    document = request()
    replace(document, path, value)
    actual = c.predict_conditional(document)
    assert code in actual["reasons"]
    assert actual["status"] in ("invalid_input", "unsupported")
    assert not actual["complete"]
    assert actual["states"] == []
    assert actual["response"] is None
    assert (
        actual["request_sha256"]
        == hashlib.sha256(canonical_bytes(document)).hexdigest()
    )
    assert actual["provenance"] is not None or path.startswith("provenance")


@pytest.mark.parametrize(
    "value,code",
    [
        (float("nan"), "invalid_json"),
        (float("inf"), "invalid_json"),
        ({1: "x"}, "invalid_json"),
        ({"a": {1, 2}}, "invalid_json"),
        ({"a": (1, 2)}, "invalid_json"),
        ({"a": b"x"}, "invalid_json"),
        ({"a": "x" * 65537}, "input_limit"),
        ({"a": "x" * 65530}, "input_limit"),
        ({"a": 1 << 200001}, "input_limit"),
        ({"a": 1 << 15000}, "invalid_json"),
        ([None] * 20000, "input_limit"),
    ],
)
def test_non_json_and_byte_limits(value, code):
    actual = c.predict_conditional(value)
    assert actual["reasons"] == [code]
    assert actual["request_sha256"] is None


def test_parsed_scalars_nesting_cycles_and_inclusive_caps(monkeypatch):
    for scalar in (None, True, False, 1, 2.5, "x", []):
        actual = c.predict_conditional(scalar)
        assert actual["request_sha256"] is not None
        assert actual["reasons"] == ["invalid_object"]
    deep = []
    for _ in range(18):
        deep = [deep]
    cycle = []
    cycle.append(cycle)
    for value in (deep, cycle):
        assert c.predict_conditional(value)["reasons"] == ["input_limit"]
    assert len(c._parsed_bytes("x" * 65534)) == 65536
    assert (
        c._parsed_bytes({"z": False, "x": None, "a": "é"})
        == b'{"a":"\\u00e9","x":null,"z":false}'
    )
    raw = c.result_bytes(c.invalid_result())
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    monkeypatch.setattr(c, "RESULT_LIMIT", len(raw))
    assert c.result_bytes(c.invalid_result()) == raw
    monkeypatch.setattr(c, "RESULT_LIMIT", len(raw) - 1)
    with pytest.raises(ConditionalError, match="authoritative bytes"):
        c.result_bytes(c.invalid_result())


@pytest.mark.parametrize(
    "path,value,code",
    [
        ("input.sequence", "GGGn", "unsupported_base"),
        ("input.sequence", "A" * 201, "invalid_string"),
        ("input.aptamer.range", {}, "invalid_range"),
        ("input.aptamer.range", [0], "invalid_range"),
        ("input.aptamer.range.0", True, "invalid_position"),
        ("input.aptamer.range.1", 0, "position_out_of_range"),
        ("input.aptamer.constraint", [], "invalid_object"),
        ("input.aptamer.constraint.mode", "soft", "invalid_mode"),
        ("input.aptamer.constraint.structure", ")" * 16, "unbalanced_structure"),
        ("input.aptamer.constraint.structure", "(" * 16, "unbalanced_structure"),
        ("input.aptamer.constraint.structure", "." * 15, "structure_length_mismatch"),
        (
            "input.aptamer.constraint.structure",
            "[" * 16,
            "unsupported_structure_symbol",
        ),
        ("input.temperature_kelvin", 300, "unsupported_temperature"),
        ("settings.seconds_total", 481, "invalid_number"),
        ("settings.seconds_per_job", 121, "invalid_number"),
        ("settings.seconds_total", 1, "invalid_number"),
    ],
)
def test_structural_validation(monkeypatch, path, value, code):
    document = request(True)
    replace(document, path, value)
    monkeypatch.setattr(
        c, "verify_backend", lambda *_: pytest.fail("Invalid request ran backend")
    )
    actual = c.predict_conditional(document)
    assert code in actual["reasons"]
    assert actual["structural_cost_kcal_mol"] is None


@pytest.mark.parametrize(
    "constraint,code",
    [
        ({"mode": "partial", "pairs": None, "unpaired": []}, "invalid_constraint"),
        ({"mode": "partial", "pairs": [], "unpaired": {}}, "invalid_constraint"),
        ({"mode": "partial", "pairs": [[0]], "unpaired": []}, "invalid_pair"),
        (
            {"mode": "partial", "pairs": [[True, 15]], "unpaired": []},
            "invalid_position",
        ),
        ({"mode": "partial", "pairs": [], "unpaired": [16]}, "position_out_of_range"),
    ],
)
def test_partial_validation(constraint, code):
    document = request(True)
    document["input"]["aptamer"]["constraint"] = constraint
    assert c.predict_conditional(document)["reasons"] == [code]


@pytest.mark.parametrize(
    "case",
    FIXTURES["invalid_cases"],
    ids=lambda case: f"{case['function']}-{case['field']}-{case['value']}",
)
def test_frozen_21_refusals(case):
    document = request()
    values = case["value"]
    value = values if isinstance(values, bool) else float(values)
    field = case["field"]
    if case["function"] == "affinity":
        document["input"]["affinity"] = dict(mode="kd", kd_molar=1, standard_molar=1)
        path = (
            "input.temperature_kelvin"
            if field == "temperature_kelvin"
            else "input.affinity." + field
        )
    elif case["function"] == "partition":
        document["input"]["occupancy"] = dict(
            mode="published2015_volume",
            mrna_total_molar=1,
            ligand_total_molar=1,
            solvent_molar=4,
            mrna_relative_volume=2,
            ligand_relative_volume=1,
        )
        path = (
            "input.beta_mol_per_kcal"
            if field == "beta_mol_per_kcal"
            else "input.affinity.delta_g_kcal_mol"
            if field == "switching_kcal_mol"
            else "input.occupancy." + field
        )
    else:
        path = {
            "beta_mol_per_kcal": "input.beta_mol_per_kcal",
            "bound_fraction": "input.occupancy.fraction",
            "rna_structural_cost_kcal_mol": "input.energies.rna_on_kcal_mol",
        }.get(field, "input.energies." + field)
        if field == "rna_structural_cost_kcal_mol":
            document["input"]["energies"]["rna_off_kcal_mol"] = 0
    replace(document, path, value)
    actual = c.predict_conditional(document)
    assert actual["status"] in ("invalid_input", "unsupported")
    assert not actual["complete"]


def test_results_identity_settings_and_mutability():
    document = request()
    document["settings"]["seconds_total"] = 30
    actual = c.predict_conditional(document)
    assert set(actual) == set(
        (
            "schema_version id profile input provenance settings model request_sha256 "
            "status reasons warnings errors states structural_cost_kcal_mol "
            "response complete"
        ).split()
    )
    assert actual["status"] == "ok" and actual["complete"]
    assert type(actual["settings"]["seconds_total"]) is float
    assert actual["response"]["ar_actual"] == 2.5
    assert (
        actual["request_sha256"]
        == hashlib.sha256(canonical_bytes(document)).hexdigest()
    )
    assert actual == c.predict_conditional(document)
    actual["input"]["energies"]["rna_off_kcal_mol"] = 100
    assert document["input"]["energies"]["rna_off_kcal_mol"] == -2
    c._warn(actual, "supplied_energies", "deduplicated")
    assert sum(w["code"] == "supplied_energies" for w in actual["warnings"]) == 1
    assert (
        hashlib.sha256(
            (ROOT / "src/regsite/data/conditional-parameters-1.json").read_bytes()
        ).hexdigest()
        == c.PARAMETER_SHA256
    )
    assert (
        hashlib.sha256(
            (ROOT / "benchmarks/other-calculators/source-manifest.json").read_bytes()
        ).hexdigest()
        == c.SOURCE_MANIFEST_SHA256
    )
    for basis in document["input"]["energy_basis"].values():
        basis.update(
            model_id=None,
            parameter_sha256="0" * 64,
            backend_sha256="1" * 64,
            sequence_sha256="2" * 64,
        )
    assert c.predict_conditional(document)["status"] == "ok"
    for basis in document["input"]["energy_basis"].values():
        basis["model_id"] = "known"
    assert "unverified_energy_basis" not in [
        w["code"] for w in c.predict_conditional(document)["warnings"]
    ]


def test_no_mrna_and_volume_warning():
    document = copy.deepcopy(EXAMPLES[2]["request"])
    document["input"]["occupancy"]["mrna_total_molar"] = 0
    actual = c.predict_conditional(document)
    assert actual["status"] == "no_mrna" and not actual["complete"]
    assert actual["reasons"] == ["no_mrna"]
    assert actual["response"]["ar_conc"] is actual["response"]["ar_actual"] is None
    document["input"]["occupancy"].update(mrna_total_molar=10, ligand_total_molar=0)
    actual = c.predict_conditional(document)
    assert actual["status"] == "ok"
    assert actual["response"]["ar_actual"] == 1
    assert "volume_sum_above_one" in [w["code"] for w in actual["warnings"]]


def test_failed_numerical_and_deadlines(monkeypatch):
    document = request()
    document["input"]["energies"]["ribosome_on_kcal_mol"] = -1000
    actual = c.predict_conditional(document)
    assert actual["status"] == "failed"
    assert actual["reasons"] == ["numerical_range"]
    assert actual["response"]["log_ar_max"] == 1000
    assert actual["response"]["ar_max"] is None
    document = copy.deepcopy(EXAMPLES[2]["request"])
    document["settings"]["max_iterations"] = 1
    assert c.predict_conditional(document)["reasons"] == ["nonconvergence"]
    document = request()
    document["settings"]["seconds_total"] = 1e-300
    assert c.predict_conditional(document)["reasons"] == ["deadline_exceeded"]

    def fail(_):
        raise ConditionalError("deadline_exceeded", "Injected final deadline")

    monkeypatch.setattr(c, "check_deadline", fail)
    assert c.predict_conditional(request())["reasons"] == ["deadline_exceeded"]


def test_parameter_integrity_and_missing_resource(monkeypatch):
    monkeypatch.setattr(c, "PARAMETER_SHA256", "0" * 64)
    assert c.predict_conditional(request())["reasons"] == ["parameter_integrity"]

    def missing(_):
        raise OSError("missing")

    monkeypatch.setattr(c, "files", missing)
    assert c.predict_conditional(request())["reasons"] == ["backend_unavailable"]


def fake_backend(monkeypatch):
    monkeypatch.setattr(
        c,
        "verify_backend",
        lambda *_: (
            Path("/unused"),
            dict(
                fold_sha256="0" * 64,
                efn2_sha256="1" * 64,
                table_manifest_sha256="2" * 64,
            ),
        ),
    )


@pytest.mark.parametrize(
    "failure",
    [
        ConditionalError("backend_timeout", "injected"),
        OSError(),
        UnicodeError(),
        ValueError(),
    ],
)
@pytest.mark.parametrize("failed_index", [0, 1])
def test_partial_states_and_failed_jobs(monkeypatch, failure, failed_index):
    fake_backend(monkeypatch)

    def fold(_root, _sequence, _required, state, *_):
        index = 0 if state["id"] == "unconstrained" else 1
        if index == failed_index:
            state.update(structure="." * 16, pairs=[])
            raise failure
        state.update(status="ok", structure="." * 16, pairs=[], efn2_energy_kcal_mol=0)

    monkeypatch.setattr(c, "fold_state", fold)
    actual = c.predict_conditional(request(True))
    assert actual["status"] == "failed"
    assert actual["states"][failed_index]["status"] == "failed"
    assert actual["states"][failed_index]["structure"] == "." * 16
    if failed_index == 0:
        assert actual["states"][1]["status"] == "not_run"
    else:
        assert actual["states"][0]["status"] == "ok"
    assert actual["response"] is actual["structural_cost_kcal_mol"] is None


def test_relative_demands_warnings_and_negative_difference(monkeypatch):
    fake_backend(monkeypatch)
    document = request(True)
    document["input"].update(sequence="AA" + document["input"]["sequence"] + "AA")
    document["input"]["aptamer"].update(
        range=[2, 18], constraint=dict(mode="partial", pairs=[[0, 15]], unpaired=[6])
    )

    def fold(_root, sequence, demands, state, *_):
        if demands is not None:
            assert demands == dict(pairs=[[2, 17]], unpaired=[8])
        state.update(
            status="ok",
            structure="." * len(sequence),
            pairs=[],
            fold_energy_kcal_mol=-1,
            efn2_energy_kcal_mol=-2 if demands is None else -1,
        )

    monkeypatch.setattr(c, "fold_state", fold)
    actual = c.predict_conditional(document)
    assert actual["structural_cost_kcal_mol"] == 1
    assert "fold_efn2_difference" in [w["code"] for w in actual["warnings"]]
    document = request(True)
    document["input"]["aptamer"]["constraint"] = dict(
        mode="partial", pairs=[], unpaired=[]
    )

    def negative(_root, _sequence, demands, state, *_):
        state.update(status="ok", efn2_energy_kcal_mol=0 if demands is None else -1)

    monkeypatch.setattr(c, "fold_state", negative)
    actual = c.predict_conditional(document)
    assert actual["status"] == "failed" and actual["structural_cost_kcal_mol"] is None
    assert actual["reasons"] == ["negative_structural_cost"]
    assert "empty_constraint" in [w["code"] for w in actual["warnings"]]


def test_status_precedence_retains_valid_components():
    document = request()
    document["id"] = False
    document["schema_version"] = "unadmitted"
    document["input"]["affinity"]["mode"] = "hill"
    actual = c.predict_conditional(document)
    assert actual["status"] == "invalid_input"
    assert actual["id"] is None
    assert actual["provenance"] == document["provenance"]
    assert actual["settings"] == document["settings"]
    assert actual["input"] is None
    assert actual["reasons"] == [
        "unsupported_schema",
        "invalid_string",
        "unsupported_affinity",
    ]
