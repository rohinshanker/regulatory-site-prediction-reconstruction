"""Offline schema checks over public arithmetic and simulated structural jobs."""

import copy
import json
import math
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

from regsite import conditional as c
from regsite import conditional_backend as cb
from regsite.conditional_math import ConditionalError

ROOT = Path(__file__).resolve().parents[1]
REQUEST = "conditional-aptamer-request-1.schema.json"
RESULT = "conditional-aptamer-result-1.schema.json"
SCHEMAS = {
    name: json.loads((ROOT / "schemas" / name).read_text())
    for name in (REQUEST, RESULT)
}
REGISTRY = Registry().with_resources(
    (name, Resource.from_contents(schema)) for name, schema in SCHEMAS.items()
)
VALIDATORS = {
    name: jsonschema.Draft202012Validator(schema, registry=REGISTRY)
    for name, schema in SCHEMAS.items()
}
EXAMPLES = json.loads(
    (ROOT / "benchmarks/riboswitch/conditional-request-examples.json").read_text()
)["cases"]
PARAMETERS = json.loads(
    (ROOT / "src/regsite/data/conditional-parameters-1.json").read_text()
)
DELETE = object()


def request(index=1):
    return copy.deepcopy(EXAMPLES[index]["request"])


def replace(document, path, value):
    *parents, key = path.split(".")
    for parent in parents:
        document = document[int(parent) if isinstance(document, list) else parent]
    key = int(key) if isinstance(document, list) else key
    if value is DELETE:
        del document[key]
    else:
        document[key] = value


def predict(document):
    """Require real public outputs to satisfy the schema and finite serializer."""
    actual = c.predict_conditional(document)
    VALIDATORS[RESULT].validate(actual)
    assert json.loads(c.result_bytes(actual)) == actual
    return actual


@pytest.fixture(autouse=True)
def no_executable_jobs(monkeypatch):
    """Fail closed if a schema test accidentally attempts actual folding."""
    monkeypatch.setattr(cb, "run_job", lambda *_: pytest.fail("Real job attempted"))
    monkeypatch.setattr(
        c, "verify_backend", lambda *_: pytest.fail("Real backend inspection attempted")
    )


@pytest.fixture
def structural_jobs(monkeypatch):
    """Exercise real state/CT handling; replace only backend admission and OS jobs."""
    identity = {
        key: PARAMETERS["backend_pins"][key]
        for key in ("fold_sha256", "efn2_sha256", "table_manifest_sha256")
    }
    monkeypatch.setattr(c, "verify_backend", lambda *_: (Path("/unused"), identity))
    options = dict(
        fail=None,
        failed_state=0,
        exit_code=2,
        timed_out=False,
        before_spawn=False,
        unavailable=False,
        header_energy=-11.2,
        energy=-11.2,
        constrained_energy=-11.2,
    )
    calls = []

    def job(executable, args, _root, _timeout, receipt):
        state = len(calls) // 2
        calls.append((state, executable.name))
        failed = options["fail"] == executable.name and state == options["failed_state"]
        if not (failed and options["before_spawn"]):
            receipt.update(
                exit_code=options["exit_code"] if failed else 0,
                timed_out=options["timed_out"] if failed else False,
                stdout_sha256=cb.digest(b""),
                stderr_sha256=cb.digest(b"diagnostic"),
            )
        if failed:
            raise ConditionalError(
                "deadline_exceeded"
                if options["before_spawn"]
                else "backend_timeout"
                if options["timed_out"]
                else "backend_unavailable"
                if options["unavailable"]
                else "backend_failed",
                "Simulated OS job",
            )
        receipt["status"] = "ok"
        if executable.name == "Fold":
            sequence = Path(args[0]).read_text().splitlines()[1]
            # A canonical nested fixture, used for both full/partial constraints.
            partners = {left: right for left, right in enumerate(range(15, 9, -1))}
            partners.update({right: left for left, right in list(partners.items())})
            energy = options["header_energy"]
            header = f"{len(sequence)}" + (
                "" if energy is None else f" ENERGY = {energy}"
            )
            rows = [
                f"{i + 1} {base} {i} {i + 2 if i + 1 < len(sequence) else 0} "
                f"{partners.get(i, -1) + 1} {i + 1}"
                for i, base in enumerate(sequence)
            ]
            Path(args[1]).write_text("\n".join([header, *rows]) + "\n")
        else:
            energy = options["energy"] if state == 0 else options["constrained_energy"]
            Path(args[1]).write_text(f"Structure: 1 Energy = {energy}\n")

    monkeypatch.setattr(cb, "run_job", job)
    return options, calls


def refs(value):
    if isinstance(value, dict):
        return ([value["$ref"]] if "$ref" in value else []) + [
            ref for child in value.values() for ref in refs(child)
        ]
    if isinstance(value, list):
        return [ref for child in value for ref in refs(child)]
    return []


@pytest.mark.parametrize("name", [REQUEST, RESULT])
def test_schema_dialect_local_references_and_limitations(name):
    schema = SCHEMAS[name]
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "$id" not in schema
    for ref in refs(schema):
        assert ref.partition("#")[0] in ("", REQUEST)
    for phrase in (
        "cannot prove",
        "hash",
        "biological validity",
        "deadline",
        "integer-versus-float",
        "duplicate keys",
    ):
        assert phrase in schema["$comment"]
    if name == RESULT:
        with pytest.raises(Unresolvable):
            jsonschema.Draft202012Validator(schema).validate(
                c.predict_conditional(request())
            )


@pytest.mark.parametrize("index", [0, 1, 2])
def test_admitted_examples(index, structural_jobs):
    document = request(index)
    VALIDATORS[REQUEST].validate(document)
    actual = predict(document)
    assert actual["status"] == "ok" and actual["complete"]
    if index == 0:
        assert actual["structural_cost_kcal_mol"] == 0
        assert [s["status"] for s in actual["states"]] == ["ok", "ok"]
        assert len(structural_jobs[1]) == 4
    else:
        assert actual["response"]["ar_actual"] == pytest.approx(
            2.5 if index == 1 else 8 / 7
        )


@pytest.mark.parametrize("mode", ["full", "partial"])
def test_structural_constraint_branches_and_missing_fold_energy(mode, structural_jobs):
    document = request(0)
    if mode == "partial":
        document["input"]["aptamer"]["constraint"] = {
            "mode": "partial",
            "pairs": [[0, 15]],
            "unpaired": [6],
        }
    structural_jobs[0]["header_energy"] = None
    VALIDATORS[REQUEST].validate(document)
    actual = predict(document)
    assert actual["status"] == "ok"
    assert all(s["fold_energy_kcal_mol"] is None for s in actual["states"])
    assert "fold_energy_absent" in [w["code"] for w in actual["warnings"]]


@pytest.mark.parametrize("mode", ["delta_g", "kd"])
@pytest.mark.parametrize("fraction", [0, 0.5, 1])
def test_affinity_fraction_and_known_unknown_bases(mode, fraction):
    document = request()
    document["provenance"]["kind"] = "user_supplied"
    document["input"]["occupancy"]["fraction"] = fraction
    if mode == "kd":
        document["input"]["affinity"] = {
            "mode": "kd",
            "kd_molar": 0.01,
            "standard_molar": 1,
        }
        for basis in document["input"]["energy_basis"].values():
            basis.update(
                model_id=None,
                parameter_sha256="0" * 64,
                backend_sha256="1" * 64,
                sequence_sha256="2" * 64,
            )
    VALIDATORS[REQUEST].validate(document)
    actual = predict(document)
    assert actual["status"] == "ok"
    assert actual["response"]["occupancy"]["fraction"] == fraction


@pytest.mark.parametrize(
    "mrna,ligand,status",
    [(0, 0, "no_mrna"), (0, 1, "no_mrna"), (1, 0, "ok"), (10, 0, "ok"), (1, 1, "ok")],
)
def test_volume_boundaries(mrna, ligand, status):
    document = request(2)
    document["input"]["occupancy"].update(
        mrna_total_molar=mrna, ligand_total_molar=ligand
    )
    VALIDATORS[REQUEST].validate(document)
    actual = predict(document)
    assert actual["status"] == status
    occupancy = actual["response"]["occupancy"]
    assert occupancy["status"] == status
    if status == "no_mrna":
        assert occupancy["fraction"] is None
        assert actual["response"]["ar_conc"] is actual["response"]["ar_actual"] is None
    if mrna == 0 or ligand == 0:
        assert occupancy["solver"]["iterations"] == 0
        assert occupancy["solver"]["scaled_residual"] is None


REQUEST_REFUSALS = [
    (1, "schema_version", "other"),
    (1, "profile", "kinetic"),
    (1, "id", ""),
    (1, "id", "x" * 129),
    (1, "provenance.kind", "measured"),
    (1, "provenance.reference", "x" * 1025),
    (1, "input.energy_basis.rna.parameter_sha256", "A" * 64),
    (1, "input.energy_basis.rna.backend_sha256", "0" * 63),
    (1, "input.energy_basis.rna.sequence_sha256", "0" * 64 + "\n"),
    (1, "input.affinity.mode", "hill"),
    (1, "input.affinity.standard_molar", 0),
    (1, "input.occupancy.mode", "hill"),
    (1, "input.occupancy.fraction", -0.01),
    (1, "input.occupancy.fraction", 1.01),
    (1, "input.beta_mol_per_kcal", 0),
    (1, "input.temperature_kelvin", -1),
    (1, "settings.seconds_total", 30.01),
    (1, "settings.max_iterations", 0),
    (1, "settings.max_iterations", 257),
    (1, "settings.max_iterations", 1.5),
    (1, "settings.seconds_total", 0),
    (0, "input.sequence", ""),
    (0, "input.sequence", "A" * 201),
    (0, "input.sequence", "ACGT"),
    (0, "input.sequence", "acgu"),
    (0, "input.sequence", "ACGU\n"),
    (0, "input.temperature_kelvin", 300),
    (0, "input.aptamer.constraint.mode", "soft"),
    (0, "input.aptamer.constraint.structure", "[" * 16),
    (0, "input.aptamer.constraint.structure", "." * 15 + "\n"),
    (0, "input.aptamer.range", [0]),
    (0, "input.aptamer.range", [0, 16, 17]),
    (0, "input.aptamer.range.0", -1),
    (0, "input.aptamer.range.1", 201),
    (0, "settings.seconds_total", 481),
    (0, "settings.seconds_per_job", 121),
    (0, "settings.seconds_per_job", 0),
    (2, "input.occupancy.mrna_total_molar", -1),
    (2, "input.occupancy.ligand_total_molar", -1),
    (2, "input.occupancy.solvent_molar", 0),
    (2, "input.occupancy.mrna_relative_volume", 0),
    (2, "input.occupancy.ligand_relative_volume", 0),
]


@pytest.mark.parametrize("index,path,value", REQUEST_REFUSALS)
def test_request_rejections_are_valid_diagnostic_results(index, path, value):
    document = request(index)
    replace(document, path, value)
    assert not VALIDATORS[REQUEST].is_valid(document)
    actual = predict(document)
    assert actual["status"] in ("invalid_input", "unsupported")
    assert not actual["complete"]


def locations(value, path=()):
    """Enumerate every object/leaf, including objects in nested arrays."""
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from locations(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from locations(child, (*path, index))


def at(document, path):
    for key in path:
        document = document[key]
    return document


def request_variants():
    variants = [request(i) for i in range(3)]
    partial = request(0)
    partial["input"]["aptamer"]["constraint"] = {
        "mode": "partial",
        "pairs": [[0, 15]],
        "unpaired": [6],
    }
    kd = request()
    kd["input"]["affinity"] = dict(mode="kd", kd_molar=1, standard_molar=1)
    return [*variants, partial, kd]


@pytest.mark.parametrize("document", request_variants())
def test_every_request_object_has_exact_mandatory_keys_and_types(document):
    VALIDATORS[REQUEST].validate(document)
    for path, value in locations(document):
        if not isinstance(value, dict):
            continue
        for key in value:
            edited = copy.deepcopy(document)
            del at(edited, path)[key]
            assert not VALIDATORS[REQUEST].is_valid(edited), (*path, key)
            assert predict(edited)["status"] in ("invalid_input", "unsupported")
        for replacement in (None, [], True, "object"):
            if not path:
                edited = replacement
            else:
                edited = copy.deepcopy(document)
                at(edited, path[:-1])[path[-1]] = replacement
            assert not VALIDATORS[REQUEST].is_valid(edited), path
            assert predict(edited)["status"] in ("invalid_input", "unsupported")
        edited = copy.deepcopy(document)
        at(edited, path)["unexpected"] = 1
        assert not VALIDATORS[REQUEST].is_valid(edited), path
        assert predict(edited)["status"] in ("invalid_input", "unsupported")


@pytest.mark.parametrize("document", request_variants())
def test_request_leaf_types_and_nulls(document):
    for path, value in locations(document):
        if not path or value is None or isinstance(value, dict):
            continue
        replacements = [
            None,
            True,
            {},
            "number" if isinstance(value, (int, float)) else 3,
        ]
        # Unknown energy basis identifiers/hashes are explicitly nullable.
        if "energy_basis" in path and path[-1] != "source_id":
            replacements.remove(None)
        for replacement in replacements:
            edited = copy.deepcopy(document)
            at(edited, path[:-1])[path[-1]] = replacement
            assert not VALIDATORS[REQUEST].is_valid(edited), (path, replacement)
            actual = predict(edited)
            assert actual["status"] in ("invalid_input", "unsupported")


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_is_not_json_and_runtime_returns_valid_refusal(value):
    document = request()
    document["input"]["energies"]["rna_on_kcal_mol"] = value
    with pytest.raises(ValueError):
        json.dumps(document, allow_nan=False)
    actual = predict(document)
    assert actual["reasons"] == ["invalid_json"]
    assert actual["request_sha256"] is None
    if not math.isnan(value):
        assert not VALIDATORS[REQUEST].is_valid(document)


@pytest.mark.parametrize(
    "document", [None, True, 1, 1.5, "text", [], {"x": 1}, {"id": "x" * 65537}]
)
def test_raw_rejections_and_independently_retained_fields(document):
    assert not VALIDATORS[REQUEST].is_valid(document)
    assert predict(document)["status"] == "invalid_input"
    document = request()
    document["id"] = False
    document["settings"]["seconds_total"] = 31
    actual = predict(document)
    assert actual["id"] is actual["settings"] is None
    assert actual["profile"] == document["profile"]
    assert actual["input"] == document["input"]
    assert actual["provenance"] == document["provenance"]


@pytest.mark.parametrize(
    "code", ["invalid_json", "input_limit", "duplicate_key", "transport_refusal"]
)
def test_transport_factory_diagnostics_remain_extensible(code):
    actual = c.invalid_result(code, "")
    VALIDATORS[RESULT].validate(actual)
    assert actual["errors"] == [{"code": code, "message": ""}]


@pytest.mark.parametrize(
    "case",
    [
        "overflow",
        "underflow",
        "solver",
        "late_volume",
        "switching",
        "binding",
        "log_ratio",
        "correction",
        "cost",
        "deadline",
    ],
)
def test_real_scalar_failed_partial_shapes(case):
    document = request(2 if case in ("solver", "late_volume") else 1)
    data = document["input"]
    if case in ("overflow", "underflow"):
        data["energies"]["ribosome_on_kcal_mol"] = -1000 if case == "overflow" else 1000
    elif case == "solver":
        document["settings"]["max_iterations"] = 1
    elif case == "late_volume":
        data["occupancy"].update(
            mrna_total_molar=1e308,
            ligand_total_molar=0,
            mrna_relative_volume=1e308,
            solvent_molar=1,
        )
    elif case == "switching":
        data["energies"]["rna_on_kcal_mol"] = 1e308
        data["affinity"]["delta_g_kcal_mol"] = 1e308
    elif case == "binding":
        data["temperature_kelvin"] = 1e308
        data["affinity"] = dict(mode="kd", kd_molar=1e308, standard_molar=1e-308)
    elif case == "log_ratio":
        data["beta_mol_per_kcal"] = 1e308
        data["energies"]["ribosome_on_kcal_mol"] = 10
    elif case == "correction":
        data["beta_mol_per_kcal"] = 1e308
        data["energies"]["rna_on_kcal_mol"] = 10
    elif case == "cost":
        data["energies"].update(rna_off_kcal_mol=-1e308, rna_on_kcal_mol=1e308)
    else:
        document["settings"]["seconds_total"] = 1e-300
    VALIDATORS[REQUEST].validate(document)
    actual = predict(document)
    assert actual["status"] == "failed" and not actual["complete"]
    if case == "solver":
        assert actual["response"]["occupancy"]["solver"]["iterations"] == 1
    elif case == "late_volume":
        occupancy = actual["response"]["occupancy"]
        assert occupancy["status"] == "failed"
        assert occupancy["fraction"] == 0 and occupancy["concentrations"] is not None
        assert occupancy["volume_fractions"] is None
    elif case == "deadline":
        assert actual["response"] is None
    else:
        assert actual["reasons"] == ["numerical_range"]


@pytest.mark.parametrize("state_index", [0, 1])
@pytest.mark.parametrize("program", ["Fold", "efn2"])
@pytest.mark.parametrize(
    "failure", ["nonzero", "timeout", "signal", "spawn", "deadline"]
)
def test_explicit_failed_job_receipts(structural_jobs, state_index, program, failure):
    options, _ = structural_jobs
    options.update(
        fail=program,
        failed_state=state_index,
        timed_out=failure == "timeout",
        exit_code=-9
        if failure in ("timeout", "signal")
        else None
        if failure == "spawn"
        else 2,
        before_spawn=failure == "deadline",
        unavailable=failure == "spawn",
    )
    actual = predict(request(0))
    assert actual["status"] == "failed"
    state = actual["states"][state_index]
    assert state["status"] == "failed"
    receipt = state["jobs"][-1]
    assert receipt["program"] == program and receipt["status"] == "failed"
    assert receipt["timed_out"] == (failure == "timeout")
    assert receipt["exit_code"] == (
        None if failure == "deadline" else options["exit_code"]
    )
    assert (state["structure"] is None) == (program == "Fold")
    if state_index == 0:
        assert actual["states"][1]["status"] == "not_run"
    assert actual["structural_cost_kcal_mol"] is actual["response"] is None


@pytest.mark.parametrize(
    "code",
    [
        "backend_unavailable",
        "backend_identity",
        "parameter_integrity",
        "deadline_exceeded",
        "resource_limit",
    ],
)
def test_structural_failure_before_jobs(monkeypatch, code):
    def fail(*_):
        raise ConditionalError(code, "Simulated admission failure")

    monkeypatch.setattr(c, "verify_backend", fail)
    actual = predict(request(0))
    assert actual["status"] == "failed"
    assert all(state["status"] == "not_run" for state in actual["states"])
    assert actual["model"]["backend"] is None


def test_structural_negative_difference_and_empty_demands(structural_jobs):
    structural_jobs[0]["constrained_energy"] = -20
    document = request(0)
    document["input"]["aptamer"]["constraint"] = dict(
        mode="partial", pairs=[], unpaired=[]
    )
    VALIDATORS[REQUEST].validate(document)
    actual = predict(document)
    assert actual["status"] == "failed" and actual["reasons"] == [
        "negative_structural_cost"
    ]
    assert all(state["status"] == "ok" for state in actual["states"])
    assert "empty_constraint" in [warning["code"] for warning in actual["warnings"]]


def result_variants():
    return [
        c.invalid_result(),
        c.predict_conditional(request()),
        c.predict_conditional(request(2)),
    ]


@pytest.mark.parametrize("actual", result_variants())
def test_every_result_object_has_exact_mandatory_keys(actual):
    VALIDATORS[RESULT].validate(actual)
    for path, value in locations(actual):
        if not isinstance(value, dict):
            continue
        for key in value:
            edited = copy.deepcopy(actual)
            del at(edited, path)[key]
            assert not VALIDATORS[RESULT].is_valid(edited), (*path, key)
        edited = copy.deepcopy(actual)
        at(edited, path)["unexpected"] = 1
        assert not VALIDATORS[RESULT].is_valid(edited), path


RESULT_REFUSALS = [
    ("schema_version", "other"),
    ("id", ""),
    ("profile", "kinetic"),
    ("model.id", "other"),
    ("model.parameter_sha256", "0" * 64),
    ("model.source_manifest_sha256", "0" * 64),
    ("model.convention_id", "other"),
    ("model.implementation_version", ""),
    ("request_sha256", "x" * 64),
    ("status", "partial"),
    ("complete", 1),
    ("complete", False),
    ("warnings", ["code"]),
    ("errors", [{}]),
    ("reasons", ["duplicate", "duplicate"]),
    ("structural_cost_kcal_mol", -1),
    ("structural_cost_kcal_mol", True),
    ("response.ar_max", 0),
    ("response.ar_actual", -1),
    ("response.ar_conc", "2"),
    ("response.log_ar_max", math.inf),
    ("response.metastability_factor", 1.1),
    ("response.metastability_applied", 1),
    ("response.occupancy.status", "unknown"),
    ("response.occupancy.mode", "hill"),
    ("response.occupancy.fraction", 1.1),
    ("response.occupancy.solver.iterations", 257),
    ("response.occupancy.solver.bracket_molar", [0]),
    ("response.occupancy.solver.bracket_molar.0", -1),
    ("response.occupancy.volume_fractions.sum", -1),
    ("response.occupancy.concentrations.complex_molar", True),
    ("settings", request(0)["settings"]),
    ("input", request(0)["input"]),
]


@pytest.mark.parametrize("path,value", RESULT_REFUSALS)
def test_result_rejects_unknown_enums_identity_changes_types_and_bounds(path, value):
    actual = c.predict_conditional(request(2))
    replace(actual, path, value)
    assert not VALIDATORS[RESULT].is_valid(actual)


def test_success_nulls_and_profile_specific_result_fields(structural_jobs):
    for document in (request(), request(2), request(0)):
        actual = predict(document)
        for key in (
            "id",
            "profile",
            "input",
            "settings",
            "provenance",
            "model",
            "request_sha256",
            "structural_cost_kcal_mol",
        ):
            edited = copy.deepcopy(actual)
            edited[key] = None
            assert not VALIDATORS[RESULT].is_valid(edited), key
        if document["profile"] == "supplied_energy_response":
            for key in actual["response"]:
                edited = copy.deepcopy(actual)
                edited["response"][key] = None
                assert not VALIDATORS[RESULT].is_valid(edited), key
        else:
            edited = copy.deepcopy(actual)
            edited["response"] = c.predict_conditional(request())["response"]
            assert not VALIDATORS[RESULT].is_valid(edited)


@pytest.mark.parametrize(
    "path,value",
    [
        ("states", []),
        ("states", [{}]),
        ("states.0.status", "unknown"),
        ("states.0.id", "constraint_compatible"),
        ("states.1.id", "unconstrained"),
        ("states.0.constraint_sha256", "0" * 64),
        ("states.1.constraint_sha256", None),
        ("states.0.sequence_sha256", "0" * 64 + "\n"),
        ("states.0.structure", "[....]"),
        ("states.0.pairs", [[0]]),
        ("states.0.pairs", [[0, True]]),
        ("states.0.efn2_energy_kcal_mol", None),
        ("states.0.jobs.0.program", "other"),
        ("states.0.jobs.0.status", "unknown"),
        ("states.0.jobs.0.exit_code", True),
        ("states.0.jobs.0.exit_code", 1),
        ("states.0.jobs.0.timed_out", True),
        ("states.0.jobs.0.timed_out", 0),
        ("states.0.jobs.0.stdout_sha256", None),
        ("states.0.jobs.1.program", "Fold"),
        ("model.backend.fold_sha256", "0" * 64),
        ("model.backend.efn2_sha256", None),
        ("model.backend.table_manifest_sha256", "0" * 64),
    ],
)
def test_structural_result_contract_rejections(structural_jobs, path, value):
    actual = predict(request(0))
    replace(actual, path, value)
    assert not VALIDATORS[RESULT].is_valid(actual)


def test_every_structural_object_has_exact_keys(structural_jobs):
    actual = predict(request(0))
    for path, value in locations(actual):
        if not isinstance(value, dict):
            continue
        for key in value:
            edited = copy.deepcopy(actual)
            del at(edited, path)[key]
            assert not VALIDATORS[RESULT].is_valid(edited), (*path, key)
        edited = copy.deepcopy(actual)
        at(edited, path)["unexpected"] = 1
        assert not VALIDATORS[RESULT].is_valid(edited), path


@pytest.mark.parametrize(
    "path,value",
    [
        ("input.energies.rna_on_kcal_mol", -3),
        ("settings.max_iterations", 1.0),
    ],
)
def test_schema_limits_do_not_replace_runtime_validation(path, value):
    document = request()
    replace(document, path, value)
    VALIDATORS[REQUEST].validate(document)
    assert predict(document)["status"] in ("invalid_input", "unsupported")


def test_structural_relations_remain_runtime_obligations():
    for path, value in (
        ("input.aptamer.range", [0, 17]),
        ("input.aptamer.constraint.structure", "." * 15),
        ("settings.seconds_total", 1),
    ):
        document = request(0)
        replace(document, path, value)
        VALIDATORS[REQUEST].validate(document)
        assert predict(document)["status"] == "invalid_input"


@pytest.mark.parametrize("index", [0, 1])
def test_settings_and_input_cannot_cross_profiles(index):
    document = request(index)
    for field in ("input", "settings"):
        edited = copy.deepcopy(document)
        edited[field] = request(1 - index)[field]
        assert not VALIDATORS[REQUEST].is_valid(edited)
        assert predict(edited)["status"] == "invalid_input"


def test_binary64_conversion_ceiling_includes_roundable_integers():
    ceiling = 2**1024 - 2**970 - 1
    for sign in (-1, 1):
        document = request()
        document["input"]["energies"].update(
            ribosome_off_kcal_mol=sign * ceiling, ribosome_on_kcal_mol=sign * ceiling
        )
        VALIDATORS[REQUEST].validate(document)
        assert predict(document)["status"] == "ok"
        document["input"]["energies"]["ribosome_on_kcal_mol"] = sign * (ceiling + 1)
        assert not VALIDATORS[REQUEST].is_valid(document)
        assert predict(document)["reasons"] == ["invalid_number"]


def test_no_mrna_retained_inside_failed_numerical_result():
    document = request(2)
    document["input"]["occupancy"]["mrna_total_molar"] = 0
    document["input"]["energies"]["ribosome_on_kcal_mol"] = -1000
    actual = predict(document)
    assert actual["status"] == "failed"
    assert actual["response"]["occupancy"]["status"] == "no_mrna"
    assert actual["response"]["ar_max"] is None
    assert actual["response"]["ar_conc"] is actual["response"]["ar_actual"] is None


def test_result_leaf_types_including_nulls(structural_jobs):
    actuals = [*result_variants(), predict(request(0))]
    structural_jobs[0].update(fail="efn2", failed_state=2, before_spawn=True)
    actuals.append(predict(request(0)))
    for actual in actuals:
        for path, value in locations(actual):
            if not path or isinstance(value, (dict, list)):
                continue
            edited = copy.deepcopy(actual)
            # Arrays are invalid for every scalar field, even nullable fields.
            at(edited, path[:-1])[path[-1]] = []
            assert not VALIDATORS[RESULT].is_valid(edited), path
            if type(value) in (int, float):
                at(edited, path[:-1])[path[-1]] = True
                assert not VALIDATORS[RESULT].is_valid(edited), path


@pytest.mark.parametrize(
    "constraint",
    [
        dict(mode="partial", pairs=[[0]], unpaired=[]),
        dict(mode="partial", pairs=[[0, 15], [0, 15]], unpaired=[]),
        dict(mode="partial", pairs=[], unpaired=[0, 0]),
        dict(mode="partial", pairs=[], unpaired=[200]),
        dict(mode="partial", pairs=None, unpaired=[]),
        dict(mode="full", structure="." * 201),
    ],
)
def test_constraint_array_shapes_and_bounds(constraint):
    document = request(0)
    document["input"]["aptamer"]["constraint"] = constraint
    assert not VALIDATORS[REQUEST].is_valid(document)
    assert predict(document)["status"] == "invalid_input"


FIXTURES = json.loads(
    (ROOT / "benchmarks/riboswitch/conditional-fixtures.json").read_text()
)


@pytest.mark.parametrize(
    "kind,case",
    [
        (kind, case)
        for kind in ("response_cases", "partition_cases", "affinity_cases")
        for case in FIXTURES[kind]
    ],
    ids=lambda value: value["id"] if isinstance(value, dict) else value,
)
def test_all_frozen_scalar_cases_through_public_schema(kind, case):
    document = request()
    data = document["input"]
    values = {key: float(value) for key, value in case["inputs"].items()}
    if kind == "response_cases":
        data["beta_mol_per_kcal"] = values["beta_mol_per_kcal"]
        data["energies"].update(
            rna_off_kcal_mol=0,
            rna_on_kcal_mol=values["rna_structural_cost_kcal_mol"],
            ribosome_off_kcal_mol=values["ribosome_off_kcal_mol"],
            ribosome_on_kcal_mol=values["ribosome_on_kcal_mol"],
        )
        data["affinity"]["delta_g_kcal_mol"] = values["ligand_binding_kcal_mol"]
        data["occupancy"]["fraction"] = values["bound_fraction"]
    elif kind == "partition_cases":
        data["beta_mol_per_kcal"] = values.pop("beta_mol_per_kcal")
        data["affinity"]["delta_g_kcal_mol"] = values.pop("switching_kcal_mol")
        data["energies"].update(rna_off_kcal_mol=0, rna_on_kcal_mol=0)
        data["occupancy"] = dict(mode="published2015_volume", **values)
    else:
        data["temperature_kelvin"] = values.pop("temperature_kelvin")
        data["affinity"] = dict(mode="kd", **values)
    VALIDATORS[REQUEST].validate(document)
    actual = predict(document)
    assert actual["status"] == case.get("expected", {}).get("status", "ok")
