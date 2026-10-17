"""Synthetic-only diagnostics: no public or private scientific fitting."""

import hashlib
import json
import math
import runpy
import sys
from copy import deepcopy
from statistics import median

import pytest
import test_native_training_recipe
from test_native_training_recipe import digest, write

from experiments.rbs import learning_curve as recipe
from experiments.rbs import native_training as native
from regsite.provenance import canonical_hash

native_panel = test_native_training_recipe.panel


@pytest.fixture
def panel(native_panel):
    source, splits, _, _, repin = native_panel
    data, frozen = (json.loads(path.read_bytes()) for path in (source, splits))
    # Four training groups, with multiple rows in one group. Validation remains
    # fixed and no final/nonprimary outcomes are released by the parent fixture.
    for i in range(4):
        data["records"][i]["group"] = frozen["records"][i]["group"] = f"train:{i}"
    row, assignment = deepcopy(data["records"][0]), deepcopy(frozen["records"][0])
    row["id"] = assignment["id"] = "synthetic:8"
    row["observed"] = 2.5
    data["records"].append(row)
    frozen["records"].append(assignment)
    cache = native_panel[2]
    envelope = json.loads(cache.read_bytes())
    prediction = deepcopy(envelope["results"][0])
    prediction["id"] = prediction["prediction"]["id"] = "synthetic:8"
    prediction["prediction"]["input"]["id"] = "synthetic:8"
    envelope["results"].append(prediction)
    write(cache, envelope)
    write(source, data)
    write(splits, frozen)
    # Preserve the fixture's source pins and exact helper admission machinery.
    repin()
    return native_panel


def select(panel, monkeypatch, kind="sequence-v1"):
    source, splits, cache, models, _ = panel
    monkeypatch.setattr(native, "SOURCE_TOTAL", 9)
    monkeypatch.setattr(
        native, "COUNTS", {"development_train": 5, "development_validation": 2}
    )
    settings = {"kind": kind}
    if kind == native.KINDS[1]:
        settings.update(context_predictions=cache, predictions_sha256=digest(cache))
    native.train(source, splits, models, "a" * 40, "b" * 40, **settings)
    return {
        "source": source,
        "splits": splits,
        "output": source.parent / "curve.json",
        "model_path": models / f"{kind}.json",
        "selection": models / f"{kind}-selection.json",
        "model_sha256": digest(models / f"{kind}.json"),
        "selection_sha256": digest(models / f"{kind}-selection.json"),
        "code_commit": "c" * 40,
        **settings,
    }


def edit(settings, name, change):
    path = settings[name]
    data = json.loads(path.read_bytes())
    change(data)
    if name == "model_path":
        payload = {k: v for k, v in data.items() if k != "artifact_sha256"}
        data["artifact_sha256"] = canonical_hash(payload)
    write(path, data)
    pin = {
        "model_path": "model_sha256",
        "selection": "selection_sha256",
        "context_predictions": "predictions_sha256",
    }[name]
    settings[pin] = digest(path)


def assert_rejected(settings, monkeypatch, match=None):
    def forbidden(*args, **kwargs):
        pytest.fail("admission failure must precede every diagnostic fit")

    monkeypatch.setattr(recipe, "fit_partitioned", forbidden)
    with pytest.raises(ValueError, match=match):
        recipe.diagnose(**settings)
    assert not settings["output"].exists()


@pytest.mark.parametrize("kind", native.KINDS)
def test_fixed_nested_curve_and_stable_output(panel, monkeypatch, kind):
    settings = select(panel, monkeypatch, kind)
    selected = json.loads(settings["selection"].read_bytes())
    calls = []
    fit = recipe.fit_partitioned

    def spy(*args, **kwargs):
        model, report = fit(*args, **kwargs)
        calls.append(
            (
                deepcopy(args),
                deepcopy({**kwargs, "provenance": dict(kwargs["provenance"])}),
                model,
            )
        )
        return model, report

    monkeypatch.setattr(recipe, "fit_partitioned", spy)
    result = recipe.diagnose(**settings)
    contents = settings["output"].read_bytes()
    assert recipe.diagnose(**settings) == result
    assert settings["output"].read_bytes() == contents
    assert len(calls) == 6  # Exactly three per invocation, never a full-size fit.
    assert sorted(path.name for path in panel[0].parent.iterdir()) == [
        "cache.json",
        "curve.json",
        "development.json",
        "models",
        "splits.json",
    ]
    assert len(list(panel[3].iterdir())) == 2  # No new model files.
    expected_groups = sorted(
        set(selected["train_groups"]),
        key=lambda g: (
            hashlib.sha256(("wave2-learning-curve-20261017:" + g).encode()).hexdigest(),
            g,
        ),
    )
    assert result["ordered_training_groups"] == expected_groups
    assert result["selected_artifact_sha256"] == selected["artifact_sha256"]
    assert result["selected_model_sha256"] == settings["model_sha256"]
    assert result["selection_report_sha256"] == settings["selection_sha256"]
    assert result["full_training_reference"]["row_count"] == 5
    for key, value in selected["configurations"][selected["selected_index"]].items():
        assert result["full_training_reference"][key] == value
    assert result["warnings"] == [
        "one_deterministic_subsampling_curve",
        "not_independent_test_accuracy",
        "not_new_model_selection",
        "no_new_finalist_or_weights",
    ]
    previous = set()
    for i, (point, (args, kwargs, model)) in enumerate(
        zip(result["points"], calls[:3], strict=True)
    ):
        assert point["fraction"] == (i + 1) / 4
        assert point["group_count"] == i + 1
        assert point["train_groups"] == expected_groups[: i + 1]
        assert point["train_ids"] == sorted(kwargs["train_ids"])
        assert previous < set(point["train_ids"])
        previous = set(point["train_ids"])
        assert point["row_count"] == len(args[0]) < 5
        assert kwargs["validation_ids"] == selected["validation_ids"]
        assert kwargs["validation_groups"] == selected["validation_groups"]
        assert args[2:] == calls[0][0][2:]
        assert not set(kwargs["train_groups"]) & set(kwargs["validation_groups"])
        assert not set(kwargs["train_ids"]) & set(kwargs["validation_ids"])
        assert set(kwargs["train_ids"]) <= set(selected["train_ids"])
        assert kwargs["penalties"] == (result["penalty_per_observation"],)
        assert model.penalty == result["penalty_per_observation"] * len(args[0])
        assert model.means == pytest.approx(
            [sum(column) / len(args[0]) for column in zip(*args[0], strict=True)]
        )
        assert point["calibration_log2"] == median(
            y - p for y, p in zip(args[1], model.predict(args[0]), strict=True)
        )
        assert point["validation_predictions_log2"] == [
            p + point["calibration_log2"] for p in model.predict(args[2])
        ]
        # Every retained row of a chosen group is included, even duplicates.
        assert kwargs["train_ids"] == [
            key
            for key, group in zip(
                selected["train_ids"], selected["train_groups"], strict=True
            )
            if group in point["train_groups"]
        ]


def test_sequence_needs_no_cache_and_cli(panel, monkeypatch, capsys):
    settings = select(panel, monkeypatch)
    panel[2].unlink()
    args = cli_args(settings)
    recipe.main(args)
    assert json.loads(capsys.readouterr().out) == recipe.diagnose(**settings)
    monkeypatch.setattr(sys, "argv", ["learning_curve", "--help"])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as exc:
        runpy.run_module("experiments.rbs.learning_curve", run_name="__main__")
    assert exc.value.code == 0


def cli_args(settings):
    args = [
        str(settings[name])
        for name in ("source", "splits", "model_path", "selection", "output")
    ]
    for name in (
        "kind",
        "model_sha256",
        "selection_sha256",
        "code_commit",
        "context_predictions",
        "predictions_sha256",
    ):
        if name in settings:
            args.extend(["--" + name.replace("_", "-"), str(settings[name])])
    return args


def test_energy_cli_and_error_exit(panel, monkeypatch, capsys):
    settings = select(panel, monkeypatch, native.KINDS[1])
    recipe.main(cli_args(settings))
    assert json.loads(capsys.readouterr().out)["admitted_cache_sha256"] == digest(
        panel[2]
    )
    settings["source"].unlink()
    with pytest.raises(SystemExit) as exc:
        recipe.main(cli_args(settings))
    assert exc.value.code == 2
    assert "native learning curve:" in capsys.readouterr().err
    settings["source"].write_text("{}")
    with pytest.raises(SystemExit) as exc:
        recipe.main(cli_args(settings))
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "unknown"},
        {"code_commit": "main"},
        {"code_commit": None},
        {"model_sha256": "a" * 63},
        {"selection_sha256": "A" * 64},
        {"context_predictions": "unused"},
        {"predictions_sha256": "a" * 64},
        {"context_predictions": "unused", "predictions_sha256": "a" * 64},
    ],
)
def test_invocation_boundaries(panel, monkeypatch, change):
    settings = select(panel, monkeypatch)
    settings.update(change)
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "change",
    [
        {"context_predictions": None},
        {"predictions_sha256": None},
        {"predictions_sha256": "bad"},
    ],
)
def test_energy_requires_explicit_cache(panel, monkeypatch, change):
    settings = select(panel, monkeypatch, native.KINDS[1])
    settings.update(change)
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "name", ["model_path", "selection", "source", "splits", "context_predictions"]
)
def test_exact_byte_pins(panel, monkeypatch, name):
    settings = select(panel, monkeypatch, native.KINDS[1])
    settings[name].write_text("{}")
    assert_rejected(settings, monkeypatch, "hash mismatch")


@pytest.mark.parametrize("name", ["model_path", "selection"])
@pytest.mark.parametrize("value", [[], {}, {"schema_version": "wrong"}])
def test_malformed_pinned_artifacts(panel, monkeypatch, name, value):
    settings = select(panel, monkeypatch)
    write(settings[name], value)
    settings["model_sha256" if name == "model_path" else "selection_sha256"] = digest(
        settings[name]
    )
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "other"),
        ("data_role", "final"),
        ("source_sha256", "a" * 64),
        ("split_sha256", "a" * 64),
        ("feature_kind", native.KINDS[1]),
        ("dataset_id", "foreign"),
        ("artifact_sha256", "a" * 64),
        ("selected_artifact_sha256", "a" * 64),
        ("code_commit", "c" * 40),
        ("data_commit", "c" * 40),
        ("train_ids", ["synthetic:6"]),
        ("validation_ids", ["synthetic:6"]),
        ("train_groups", []),
        ("validation_groups", []),
        ("declared_source_total", 8),
        ("development_total", 6),
        ("failures", [{"id": "synthetic:0"}]),
        ("excluded_development_ids", ["synthetic:0"]),
        ("coverage", {}),
        ("weights", "refit"),
        ("calibration", "validation residual"),
        ("selection", "minimum training error"),
        ("configurations", []),
        ("configurations", None),
        ("selected_index", True),
        ("selected_index", -1),
        ("selected_index", 4),
        ("selected_index", None),
        ("selected_calibration_log2", None),
        ("selected_calibration_log2", True),
        ("selected_calibration_log2", 1e10),
        ("admitted_cache_sha256", "a" * 64),
    ],
)
def test_report_identity_and_shape(panel, monkeypatch, key, value):
    settings = select(panel, monkeypatch)
    edit(settings, "selection", lambda data: data.update({key: value}))
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "field,value",
    [
        ("penalty_per_observation", True),
        ("penalty_per_observation", 0.02),
        ("calibration_log2", None),
        ("calibration_log2", float("nan")),
        ("validation_predictions_log2", []),
        ("validation_predictions_log2", None),
        ("validation_predictions_log2", [False, 1]),
        ("validation_predictions_log2", [float("inf"), 1]),
        ("validation_mae_log2", float("nan")),
        ("validation_mae_log2", -1),
        ("validation_rmse_log2", True),
        ("validation_rmse_log2", -1),
    ],
)
def test_report_configuration_boundaries(panel, monkeypatch, field, value):
    settings = select(panel, monkeypatch)
    edit(
        settings,
        "selection",
        lambda data: data["configurations"][0].update({field: value}),
    )
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "change", ["nonobject", "reorder", "wrong_selected", "wrong_calibration"]
)
def test_report_semantic_mismatches(panel, monkeypatch, change):
    settings = select(panel, monkeypatch)

    def mutate(data):
        if change == "nonobject":
            data["configurations"][0] = None
        elif change == "reorder":
            data["train_ids"].reverse()
        elif change == "wrong_selected":
            data["selected_index"] = (data["selected_index"] + 1) % 4
        else:
            data["configurations"][data["selected_index"]]["calibration_log2"] += 1

    edit(settings, "selection", mutate)
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "field,value",
    [
        ("dataset_id", "foreign"),
        ("split_id", "a" * 64),
        ("data_role", "final"),
        ("feature_kind", native.KINDS[1]),
        ("target_name", "rate"),
        ("target_units", "rate"),
        ("code_commit", "main"),
        ("data_commit", "main"),
        ("context_results_sha256", "a" * 64),
        (
            "training_domain",
            json.dumps(
                {"hosts": ["other"], "anti_sd": ["ACCUCCUUU"], "temperatures_c": [30]}
            ),
        ),
    ],
)
def test_selected_provenance_mismatch(panel, monkeypatch, field, value):
    settings = select(panel, monkeypatch)
    edit(settings, "model_path", lambda data: data["provenance"].update({field: value}))
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "change",
    [
        "checksum",
        "features",
        "penalty",
        "fingerprint",
        "scores",
        "domain",
        "missing_provenance",
    ],
)
def test_selected_model_integrity(panel, monkeypatch, change):
    settings = select(panel, monkeypatch)

    def mutate(data):
        if change == "features":
            data["feature_names"][0] = "foreign"
        elif change == "penalty":
            data["penalty"] *= 2
        elif change == "fingerprint":
            data["training_sha256"] = "a" * 64
        elif change in ("scores", "checksum"):
            data["intercept"] += 1
        elif change == "domain":
            data["provenance"]["training_domain"] = "{}"
        else:
            data["provenance"].pop("target_name")

    edit(settings, "model_path", mutate)
    if change == "checksum":
        data = json.loads(settings["model_path"].read_bytes())
        data["intercept"] += 1
        write(settings["model_path"], data)
        settings["model_sha256"] = digest(settings["model_path"])
    else:
        artifact = json.loads(settings["model_path"].read_bytes())["artifact_sha256"]
        edit(
            settings,
            "selection",
            lambda data: data.update(
                artifact_sha256=artifact, selected_artifact_sha256=artifact
            ),
        )
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize(
    "change",
    ["wrong_hash", "backend", "features", "context", "coverage", "selected_cores"],
)
def test_energy_cache_must_match_original_selection(panel, monkeypatch, change):
    settings = select(panel, monkeypatch, native.KINDS[1])

    def mutate(data):
        if change == "backend":
            for row in data["results"]:
                row["prediction"]["backend"]["foreign"] = True
        elif change in ("features", "selected_cores"):
            key = "dG_total" if change == "features" else "dG_spacing"
            data["results"][0]["prediction"]["sites"][0]["energies"][key] += 1
        elif change == "context":
            data["results"][0]["prediction"]["input"]["host"] = "other"
        elif change == "coverage":
            data["results"][0].update(status="failed", prediction=None)

    edit(settings, "context_predictions", mutate)
    if change != "wrong_hash":
        edit(
            settings,
            "selection",
            lambda data: data.update(
                admitted_cache_sha256=settings["predictions_sha256"]
            ),
        )
    else:
        edit(
            settings,
            "selection",
            lambda data: data.update(admitted_cache_sha256="a" * 64),
        )
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize("kind", native.KINDS)
def test_original_exclusions_preserved(panel, monkeypatch, kind):
    if kind == native.KINDS[1]:
        cache = json.loads(panel[2].read_bytes())
        cache["results"][4].update(
            status="unsupported", prediction=None, reason="synthetic unavailable"
        )
        write(panel[2], cache)
    else:
        data = json.loads(panel[0].read_bytes())
        data["records"][4]["start"] = 0
        write(panel[0], data)
        panel[4]()
    settings = select(panel, monkeypatch, kind)
    result = recipe.diagnose(**settings)
    original = json.loads(settings["selection"].read_bytes())
    assert result["excluded_development_ids"] == ["synthetic:4"]
    assert result["validation_ids"] == ["synthetic:5"]
    assert result["failures"] == original["failures"]
    assert result["coverage"] == original["coverage"]


def test_energy_failure_fallback_and_failed_core_preserved(panel, monkeypatch):
    cache = json.loads(panel[2].read_bytes())
    for i in (4, 5):
        cache["results"][i]["status"] = "unsupported"
        cache["results"][i]["prediction"]["status"] = "unsupported"
    # Retain one validation row, and exercise failed-core matching and fallback.
    cache["results"][5]["status"] = "ok"
    cache["results"][5]["prediction"]["status"] = "ok"
    write(panel[2], cache)
    settings = select(panel, monkeypatch, native.KINDS[1])
    assert (
        recipe.diagnose(**settings)["failures"][0]["reason"]
        == "native_prediction_unsuccessful"
    )


def test_insufficient_groups_rejected(panel, monkeypatch):
    data, frozen = (json.loads(path.read_bytes()) for path in panel[:2])
    for row in data["records"] + frozen["records"]:
        if row["group"] == "train:3":
            row["group"] = "train:2"
    write(panel[0], data)
    write(panel[1], frozen)
    panel[4]()
    settings = select(panel, monkeypatch)
    assert_rejected(settings, monkeypatch, "at least four")


@pytest.mark.parametrize(
    "name", ["source", "splits", "model_path", "selection", "context_predictions"]
)
def test_output_cannot_replace_input(panel, monkeypatch, name):
    settings = select(panel, monkeypatch, native.KINDS[1])
    before = settings[name].read_bytes()
    settings["output"] = settings[name]
    with pytest.raises(ValueError, match="overwrite"):
        recipe.diagnose(**settings)
    assert settings[name].read_bytes() == before


@pytest.mark.parametrize("failure_call", [1, 2, 3])
@pytest.mark.parametrize("existing", [False, True])
def test_fitting_failure_never_publishes(panel, monkeypatch, failure_call, existing):
    settings = select(panel, monkeypatch)
    if existing:
        settings["output"].write_bytes(b"previous diagnostic")
    fit, calls = recipe.fit_partitioned, []

    def fail(*args, **kwargs):
        calls.append(1)
        if len(calls) == failure_call:
            raise ValueError("synthetic failure")
        return fit(*args, **kwargs)

    monkeypatch.setattr(recipe, "fit_partitioned", fail)
    with pytest.raises(ValueError, match="synthetic failure"):
        recipe.diagnose(**settings)
    assert len(calls) == failure_call
    if existing:
        assert settings["output"].read_bytes() == b"previous diagnostic"
    else:
        assert not settings["output"].exists()


def test_all_features_validated_before_first_fit(panel, monkeypatch):
    settings = select(panel, monkeypatch, native.KINDS[1])
    # An ok core with missing features is corruption, never an extra exclusion.
    cache = json.loads(panel[2].read_bytes())
    cache["results"][-1]["prediction"]["sites"][0]["energies"]["dG_total"] = math.nan
    write(panel[2], cache)
    settings["predictions_sha256"] = digest(panel[2])
    edit(
        settings,
        "selection",
        lambda data: data.update(admitted_cache_sha256=settings["predictions_sha256"]),
    )
    assert_rejected(settings, monkeypatch)


@pytest.mark.parametrize("partition", ["development_train", "development_validation"])
def test_empty_reconstructed_partition_rejected(panel, monkeypatch, partition):
    settings = select(panel, monkeypatch)
    records = {row["id"]: row for row in json.loads(panel[0].read_bytes())["records"]}
    extract = recipe.extract_features

    def unavailable(request, **kwargs):
        if records[request.id]["partition"] == partition:
            raise recipe.FeatureError("synthetic unsupported context")
        return extract(request, **kwargs)

    monkeypatch.setattr(recipe, "extract_features", unavailable)
    assert_rejected(settings, monkeypatch, "nonempty train/validation")


def test_fraction_counts_round_down_for_five_groups(panel, monkeypatch):
    data, frozen = (json.loads(path.read_bytes()) for path in panel[:2])
    data["records"][-1]["group"] = frozen["records"][-1]["group"] = "train:4"
    write(panel[0], data)
    write(panel[1], frozen)
    panel[4]()
    settings = select(panel, monkeypatch)
    result = recipe.diagnose(**settings)
    assert len(result["ordered_training_groups"]) == 5
    assert [point["group_count"] for point in result["points"]] == [1, 2, 3]


def test_group_hash_ties_are_lexicographic(panel, monkeypatch):
    settings = select(panel, monkeypatch)
    sha256 = hashlib.sha256

    def tied_hash(contents):
        if contents.startswith(recipe.GROUP_PREFIX.encode()):
            return sha256(b"synthetic tie")
        return sha256(contents)

    monkeypatch.setattr(recipe.hashlib, "sha256", tied_hash)
    result = recipe.diagnose(**settings)
    assert result["ordered_training_groups"] == [f"train:{i}" for i in range(4)]


def test_unselected_cache_inputs_do_not_change_diagnostics(panel, monkeypatch):
    settings = select(panel, monkeypatch, native.KINDS[1])
    before = recipe.diagnose(**settings)

    def mutate(data):
        # Final input-only entries contain no outcomes. Their energies cannot
        # become training features or losses; the global backend remains pinned.
        data["results"][6]["prediction"]["sites"][0]["energies"]["dG_total"] += 50
        data["results"].reverse()

    edit(settings, "context_predictions", mutate)
    edit(
        settings,
        "selection",
        lambda data: data.update(admitted_cache_sha256=settings["predictions_sha256"]),
    )
    after = recipe.diagnose(**settings)
    for result in (before, after):
        result.pop("admitted_cache_sha256")
        result.pop("selection_report_sha256")
    assert before == after
