"""Synthetic-only native recipe, leakage boundaries and frozen-cache admission."""

import hashlib
import json
import runpy
import sys
from copy import deepcopy
from dataclasses import asdict
from statistics import median

import pytest
from test_rbs import AlgebraBackend, request

from experiments.rbs import native_training as recipe
from regsite.features import extract_features
from regsite.learning import RidgeModel
from regsite.provenance import canonical_hash, energy_signature
from regsite.rbs import predict


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value))


@pytest.fixture
def panel(tmp_path, monkeypatch):
    rows, assignments, cached = [], [], []
    for i in range(8):
        identity = f"synthetic:{i}"
        partition = "development_train" if i < 4 else "development_validation"
        if i == 6:
            partition = "final"
        sequence = request()["sequence"].replace("U", "T")
        # Vary features without introducing real data or scientific fits.
        sequence = "ACGT"[i % 4] * 5 + sequence[5:]
        sequence_hash = hashlib.sha256(sequence.encode()).hexdigest()
        row = {
            "id": identity,
            "group": str(i // 2),
            "partition": partition,
            "sequence": sequence,
            "sequence_sha256": sequence_hash,
            "start": 20,
            "observed": i + 1,
            "study": "Karlsen2018",
            "condition": "HC_minus_5_min",
            "measurement_status": "positive",
            "log_eligible": True,
            "quantity": "relative RPF_RPKM/RNA_RPKM TE proxy",
            "host": recipe.HOST,
            "temperature_celsius": 30,
            "anti_sd": "ACCUCCUUU",
        }
        assignment = {
            key: row[key]
            for key in (
                "id",
                "group",
                "partition",
                "sequence_sha256",
            )
        }
        assignment["primary_eligible"] = i != 7
        if i == 7:
            assignment["group"] = "nonprimary"
        assignments.append(assignment)
        if i < 6:
            rows.append(row)
        core = predict(
            request(
                id=identity,
                sequence=sequence.replace("T", "U"),
                host=recipe.HOST,
                temperature_c=30,
                anti_sd="ACCUCCUUU",
            ),
            AlgebraBackend(),
            profile="context2017",
        )
        assert core["status"] == "ok"
        cached.append({"id": identity, "status": "ok", "prediction": core})
    source, splits, cache = (
        tmp_path / name
        for name in (
            "development.json",
            "splits.json",
            "cache.json",
        )
    )
    write(
        source,
        {
            "schema_version": "native-rbs-development-1",
            "records": rows,
            "input_envelope_sha256": "e" * 64,
        },
    )
    write(
        splits,
        {
            "schema_version": "native-rbs-splits-1",
            "records": assignments,
            "input_envelope_sha256": "e" * 64,
        },
    )
    write(cache, {"results": cached})
    monkeypatch.setattr(recipe, "SOURCE_TOTAL", 8)
    monkeypatch.setattr(
        recipe,
        "COUNTS",
        {
            "development_train": 4,
            "development_validation": 2,
        },
    )

    def repin():
        monkeypatch.setattr(recipe, "SPLIT_SHA256", digest(splits))
        data = json.loads(source.read_bytes())
        if isinstance(data, dict):
            data["split_sha256"] = recipe.SPLIT_SHA256
            write(source, data)
        monkeypatch.setattr(recipe, "SOURCE_SHA256", digest(source))

    repin()
    return source, splits, cache, tmp_path / "models", repin


def fit(panel, kind="sequence-v1", **changes):
    source, splits, cache, output, _ = panel
    settings = {
        "source": source,
        "splits": splits,
        "output": output,
        "code_commit": "a" * 40,
        "data_commit": "b" * 40,
        "kind": kind,
    }
    if kind == recipe.KINDS[1]:
        settings.update(context_predictions=cache, predictions_sha256=digest(cache))
    settings.update(changes)
    return recipe.train(**settings)


@pytest.mark.parametrize("kind", recipe.KINDS)
def test_reproducible_artifacts_train_only_grid_and_offset(panel, monkeypatch, kind):
    calls = []
    original = recipe.fit_partitioned

    def spy(*args, **kwargs):
        calls.append((args, deepcopy(kwargs)))
        return original(*args, **kwargs)

    monkeypatch.setattr(recipe, "fit_partitioned", spy)
    report = fit(panel, kind)
    source, _, cache, output, _ = panel
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    assert fit(panel, kind) == report
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before
    assert len(calls) == 2
    args, settings = calls[0]
    assert len(args[0]) == 4 and len(args[2]) == 2
    assert settings["train_ids"] == [f"synthetic:{i}" for i in range(4)]
    assert settings["validation_ids"] == ["synthetic:4", "synthetic:5"]
    assert settings["penalties"] == (0.01, 0.1, 1, 10)
    assert not set(settings["train_groups"]) & set(settings["validation_groups"])
    model = RidgeModel.from_dict(json.loads((output / f"{kind}.json").read_bytes()))
    assert report["weights"] == "train-only; no post-selection refit"
    assert list(model.means) == pytest.approx(
        [sum(row[j] for row in args[0]) / 4 for j in range(len(model.means))]
    )
    chosen = report["configurations"][report["selected_index"]]
    assert chosen["calibration_log2"] == median(
        y - p for y, p in zip(args[1], model.predict(args[0]), strict=True)
    )
    assert model.penalty == chosen["penalty_per_observation"] * 4
    assert chosen["validation_predictions_log2"] == pytest.approx(
        [value + chosen["calibration_log2"] for value in model.predict(args[2])]
    )
    assert report["declared_source_total"] == 8 and report["development_total"] == 6
    assert report["failures"] == report["excluded_development_ids"] == []
    assert {row["id"] for row in report["excluded_source_records"]} == {
        "synthetic:6",
        "synthetic:7",
    }
    assert report["coverage"]["development_train"]["fraction"] == 1
    assert model.provenance["code_commit"] == "a" * 40
    assert model.provenance["data_commit"] == "b" * 40
    assert "CC-BY-4.0" in model.provenance["data_licence"]
    assert "no blanket CC" in model.provenance["sequence_rights"]
    assert "not an initiation rate" in model.provenance["target_units"]
    if kind == recipe.KINDS[1]:
        cores = [r["prediction"] for r in json.loads(cache.read_bytes())["results"][:6]]
        assert model.provenance["context_results_sha256"] == canonical_hash(cores)
        assert (
            model.provenance["energy_model_sha256"]
            == energy_signature(cores[0])["energy_model_sha256"]
        )
        # The cache's derived RNA raw hash intentionally differs from DNA source.
        assert (
            cores[0]["input"]["input_sha256"]
            != json.loads(source.read_bytes())["records"][0]["sequence_sha256"]
        )
    else:
        assert not any(
            key.startswith(("energy_", "context_")) for key in model.provenance
        )
        assert "admitted_cache_sha256" not in report


def test_sequence_has_no_cache_dependency_and_cli(panel, capsys, monkeypatch):
    source, splits, cache, output, _ = panel
    cache.unlink()
    recipe.main(
        [
            str(source),
            str(splits),
            str(output),
            "--kind",
            "sequence-v1",
            "--code-commit",
            "a" * 40,
            "--data-commit",
            "b" * 40,
        ]
    )
    assert json.loads(capsys.readouterr().out) == fit(panel)
    monkeypatch.setattr(sys, "argv", ["native_training", "--help"])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as exc:
        runpy.run_module("experiments.rbs.native_training", run_name="__main__")
    assert exc.value.code == 0


def test_energy_cli_and_errors(panel, capsys):
    source, splits, cache, output, _ = panel
    args = [
        str(source),
        str(splits),
        str(output),
        "--kind",
        recipe.KINDS[1],
        "--code-commit",
        "a" * 40,
        "--data-commit",
        "b" * 40,
        "--context-predictions",
        str(cache),
        "--predictions-sha256",
        digest(cache),
    ]
    recipe.main(args)
    assert json.loads(capsys.readouterr().out)["feature_kind"] == recipe.KINDS[1]
    source.unlink()
    with pytest.raises(SystemExit) as exc:
        recipe.main(args)
    assert exc.value.code == 2
    assert "native training:" in capsys.readouterr().err
    source.write_text("{}")
    with pytest.raises(SystemExit) as exc:
        recipe.main(args)
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "settings",
    [
        {"kind": "unknown"},
        {"code_commit": "main"},
        {"data_commit": None},
        {"kind": recipe.KINDS[1], "context_predictions": None},
        {"kind": recipe.KINDS[1], "predictions_sha256": None},
        {"kind": recipe.KINDS[1], "predictions_sha256": "bad"},
        {"predictions_sha256": "a" * 64},
        {"context_predictions": "unused"},
        {"context_predictions": "unused", "predictions_sha256": "a" * 64},
    ],
)
def test_invocation_boundaries(panel, settings):
    with pytest.raises(ValueError):
        fit(panel, **settings)
    assert not panel[3].exists()


@pytest.mark.parametrize("name", ["source", "split", "cache"])
def test_hash_pins_reject_changed_bytes(panel, name):
    source, splits, cache, output, _ = panel
    expected = digest(cache)
    {"source": source, "split": splits, "cache": cache}[name].write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        fit(panel, recipe.KINDS[1], predictions_sha256=expected)
    assert not output.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("group", "other"),
        ("partition", "final"),
        ("sequence", None),
        ("sequence_sha256", "wrong"),
        ("study", "other"),
        ("condition", "LC"),
        ("measurement_status", "zero"),
        ("log_eligible", False),
        ("quantity", "rate"),
        ("host", "other"),
        ("temperature_celsius", "30"),
        ("temperature_celsius", 37),
        ("anti_sd", "ACCUCCUUA"),
        ("start", True),
        ("start", -1),
        ("observed", 0),
        ("observed", True),
        ("observed", float("inf")),
        ("observed", float("nan")),
        ("observed", "1"),
    ],
)
def test_invalid_source_fails_closed(panel, field, value):
    source, _, _, output, repin = panel
    data = json.loads(source.read_bytes())
    data["records"][0][field] = value
    write(source, data)
    repin()
    with pytest.raises(ValueError):
        fit(panel)
    assert not output.exists()


@pytest.mark.parametrize(
    "target,change",
    [
        ("source", "schema"),
        ("source", "envelope"),
        ("source", "nonobject"),
        ("source", "missing"),
        ("source", "duplicate"),
        ("source", "empty_id"),
        ("source", "nonrow"),
        ("source", "nontext_id"),
        ("source", "empty"),
        ("source", "final"),
        ("split", "schema"),
        ("split", "missing"),
        ("split", "duplicate"),
        ("split", "overlap"),
        ("split", "group"),
        ("split", "partition"),
        ("split", "eligibility"),
        ("split", "counts"),
        ("split", "sequence"),
    ],
)
def test_source_split_identity_boundaries(panel, target, change):
    source, splits, _, output, repin = panel
    path = source if target == "source" else splits
    data = json.loads(path.read_bytes())
    if change == "schema":
        data["schema_version"] = "wrong"
    elif change == "envelope":
        data["input_envelope_sha256"] = None
    elif change == "nonobject":
        data = []
    elif change == "missing":
        data["records"].pop()
    elif change == "duplicate":
        data["records"].append(data["records"][0])
    elif change == "empty_id":
        data["records"][0]["id"] = " "
    elif change == "nonrow":
        data["records"][0] = None
    elif change == "nontext_id":
        data["records"][0]["id"] = []
    elif change == "empty":
        data["records"] = []
    elif change == "final":
        data["records"].append({"id": "synthetic:6", "observed": 100})
    else:
        field, value = {
            "overlap": ("group", "0"),
            "group": ("group", None),
            "partition": ("partition", "unknown"),
            "eligibility": ("primary_eligible", 1),
            "counts": ("primary_eligible", False),
            "sequence": ("sequence_sha256", "bad"),
        }[change]
        data["records"][4][field] = value
    write(path, data)
    repin()
    with pytest.raises(ValueError):
        fit(panel)
    assert not output.exists()


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "extra",
        "not_object",
        "no_results",
        "bad_status",
        "missing_core",
        "bad_core",
        "wrong_id",
        "wrong_status",
        "mixed_backend",
        "mixed_model",
        "bad_model",
        "all_missing",
        "extra_final_mixed_backend",
    ],
)
def test_cache_identity_fails_closed(panel, change):
    _, _, cache, output, _ = panel
    data = json.loads(cache.read_bytes())
    row = data["results"][0]
    if change == "missing":
        data["results"].pop()
    elif change == "duplicate":
        data["results"].append(row)
    elif change == "extra":
        data["results"].append({"id": "foreign"})
    elif change == "not_object":
        data = []
    elif change == "no_results":
        data = {}
    elif change == "bad_status":
        row["status"] = "maybe"
    elif change == "missing_core":
        row["prediction"] = None
    elif change == "bad_core":
        row.update(status="failed", prediction=[])
    elif change == "wrong_id":
        row["prediction"]["id"] = "foreign"
    elif change == "wrong_status":
        row["prediction"]["status"] = "failed"
    elif change in ("mixed_backend", "extra_final_mixed_backend"):
        index = 6 if change.startswith("extra") else 0
        data["results"][index]["prediction"]["backend"]["different"] = True
    elif change == "mixed_model":
        row["prediction"]["model"]["parameters"]["different"] = 1
    elif change == "bad_model":
        row["prediction"]["model"]["id"] = "historical"
    else:
        for row in data["results"]:
            row.update(status="failed", prediction=None)
    write(cache, data)
    with pytest.raises(ValueError):
        fit(panel, recipe.KINDS[1])
    assert not output.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("sequence", "A"),
        ("normalized_sha256", "bad"),
        ("oriented_sequence", "A"),
        ("oriented_sha256", "bad"),
        ("strand", "-"),
        ("anti_sd", "ACCUCCUUA"),
        ("temperature_c", 37),
        ("host", "other"),
        ("start_positions", [21]),
    ],
)
def test_cache_context_matches_normalized_scientific_input(panel, field, value):
    _, _, cache, output, _ = panel
    data = json.loads(cache.read_bytes())
    data["results"][0]["prediction"]["input"][field] = value
    write(cache, data)
    with pytest.raises(ValueError, match="input/settings mismatch"):
        fit(panel, recipe.KINDS[1])
    assert not output.exists()


@pytest.mark.parametrize("change", ["no_input", "nan_energy", "wrong_site"])
def test_malformed_successful_core_is_not_silently_dropped(panel, change):
    _, _, cache, output, _ = panel
    data = json.loads(cache.read_bytes())
    core = data["results"][0]["prediction"]
    if change == "no_input":
        core["input"] = None
    elif change == "nan_energy":
        core["sites"][0]["energies"]["dG_total"] = float("nan")
    else:
        core["sites"][0]["oriented_start"] = 21
    write(cache, data)
    with pytest.raises(ValueError):
        fit(panel, recipe.KINDS[1])
    assert not output.exists()


@pytest.mark.parametrize(
    "status", ["failed", "unsupported", "invalid_input", "no_candidate"]
)
def test_partial_cache_coverage_report_and_no_zero_fill(panel, status):
    _, _, cache, output, _ = panel
    data = json.loads(cache.read_bytes())
    for index in (0, 4):
        row = data["results"][index]
        row.update(status=status, reason="synthetic_failure")
        row["prediction"]["status"] = status
    # A batch deadline may prevent construction of a core result entirely.
    data["results"][4]["prediction"] = None
    write(cache, data)
    report = fit(panel, recipe.KINDS[1])
    assert report["excluded_development_ids"] == ["synthetic:0", "synthetic:4"]
    assert [r["reason"] for r in report["failures"]] == ["synthetic_failure"] * 2
    assert [r["status"] for r in report["failures"]] == [status] * 2
    assert report["coverage"]["development_train"] == {
        "eligible": 4,
        "retained": 3,
        "failed": 1,
        "fraction": 0.75,
    }
    assert report["validation_ids"] == ["synthetic:5"]
    model = json.loads((output / f"{recipe.KINDS[1]}.json").read_bytes())
    assert model["penalty"] in (0.03, 0.3, 3, 30)
    assert "paired_eligibility_requires_coordinator_decision" in report["warnings"]


def test_failure_reason_fallback_and_empty_partition_rejection(panel):
    _, _, cache, output, _ = panel
    data = json.loads(cache.read_bytes())
    data["results"][0].update(status="failed", prediction=None)
    write(cache, data)
    assert (
        fit(panel, recipe.KINDS[1])["failures"][0]["reason"]
        == "native_prediction_unsuccessful"
    )
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    for i in range(4):
        data["results"][i].update(status="failed", prediction=None)
    write(cache, data)
    with pytest.raises(ValueError, match="partition rows"):
        fit(panel, recipe.KINDS[1])
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_sequence_unsupported_context_is_explicit(panel):
    source, splits, _, _, repin = panel
    data, frozen = (json.loads(p.read_bytes()) for p in (source, splits))
    data["records"][0]["start"] = 0
    write(source, data)
    write(splits, frozen)
    repin()
    report = fit(panel)
    assert report["excluded_development_ids"] == ["synthetic:0"]
    assert report["failures"][0]["status"] == "unsupported"


def test_failure_before_publication_preserves_output(panel, monkeypatch):
    fit(panel)
    output = panel[3]
    before = {p.name: p.read_bytes() for p in output.iterdir()}

    def invalid(model):
        raise ValueError("synthetic artifact validation failure")

    monkeypatch.setattr(recipe, "validate_model", invalid)
    with pytest.raises(ValueError, match="artifact validation"):
        fit(panel)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_input_envelope_formatting_and_unselected_final_values_do_not_change_fit(panel):
    _, _, cache, output, _ = panel
    first = fit(panel, recipe.KINDS[1])
    before = (output / f"{recipe.KINDS[1]}.json").read_bytes()
    data = json.loads(cache.read_bytes())
    data["results"][6]["prediction"]["sites"][0]["energies"]["dG_total"] += 123
    data["execution"] = {"seconds_per_batch": 3600}
    data["results"].reverse()
    cache.write_text(json.dumps(data, indent=2))
    second = fit(panel, recipe.KINDS[1])
    assert (output / f"{recipe.KINDS[1]}.json").read_bytes() == before
    first.pop("admitted_cache_sha256")
    second.pop("admitted_cache_sha256")
    assert first == second


def test_extraction_uses_released_sequence_settings(panel):
    source, splits, _ = panel[:3]
    records, _, requests = recipe._development(source, splits)
    for key, req in requests.items():
        assert req.anti_sd == records[key]["anti_sd"]
        assert req.temperature_c == records[key]["temperature_celsius"]
        assert asdict(req)["start_positions"] == (records[key]["start"],)
        assert len(extract_features(req, kind="sequence-v1")) == 19


def test_excluded_source_failures_are_auditable_without_entering_fit(panel):
    _, _, cache, _, _ = panel
    before = fit(panel, recipe.KINDS[1])
    value = json.loads(cache.read_text())
    for row in value["results"][6:]:
        row.update(
            status="failed",
            reason="native_batch_time_budget_exhausted",
            prediction=None,
        )
    write(cache, value)
    after = fit(panel, recipe.KINDS[1])
    assert before["artifact_sha256"] == after["artifact_sha256"]
    assert before["configurations"] == after["configurations"]
    assert after["failures"] == []
    assert {r["reason"] for r in after["excluded_source_records"]} == {
        "final_input_only",
        "nonprimary_input_only",
    }
    assert all(
        r["prediction_status"] == "failed"
        and r["prediction_reason"] == "native_batch_time_budget_exhausted"
        for r in after["excluded_source_records"]
    )
    sequence = fit(panel)
    assert all(
        r["prediction_status"] == "not_requested" and r["prediction_reason"] is None
        for r in sequence["excluded_source_records"]
    )
