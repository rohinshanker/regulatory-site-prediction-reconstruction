"""Fixed native train/validation separation and train-only calibration."""

import pytest

from regsite import partitioned_training as module
from regsite.partitioned_training import fit_partitioned


def fit(**changes):
    settings = {
        "train_rows": [[0], [1], [2], [3]],
        "train_log2": [0, 2, 4, 7],
        "validation_rows": [[4], [5]],
        "validation_log2": [8, 10],
        "feature_names": ("x",),
        "train_ids": list("abcd"),
        "validation_ids": list("ef"),
        "train_groups": ["one", "one", "two", "two"],
        "validation_groups": ["three", "four"],
        "provenance": {
            "dataset_id": "synthetic",
            "split_id": "fixed",
            "data_role": "development",
        },
    }
    settings.update(changes)
    return fit_partitioned(**settings)


def test_validation_labels_never_fit_weights_or_calibration(monkeypatch):
    calls = []
    original = module.fit_ridge

    def spy(rows, targets, **kwargs):
        calls.append((rows, targets, kwargs))
        return original(rows, targets, **kwargs)

    monkeypatch.setattr(module, "fit_ridge", spy)
    first, report = fit(penalties=(0.1,))
    changed, altered = fit(penalties=(0.1,), validation_log2=[100, -100])
    assert first.to_dict() == changed.to_dict()
    a, b = report["configurations"][0], altered["configurations"][0]
    assert a["calibration_log2"] == b["calibration_log2"]
    assert a["validation_predictions_log2"] == b["validation_predictions_log2"]
    assert a["validation_mae_log2"] != b["validation_mae_log2"]
    assert len(calls) == 2
    assert all(call[2]["record_ids"] == list("abcd") for call in calls)
    assert all(call[2]["penalty"] == 0.4 for call in calls)
    assert report["selected_artifact_sha256"] == first.to_dict()["artifact_sha256"]
    assert report["selected_calibration_log2"] == a["calibration_log2"]
    assert first.means == (1.5,)
    # Raw-x slope 23/11 and intercept 5/44 give residuals
    # [-5,-9,-13,27]/44, whose median is -7/44.
    assert a["calibration_log2"] == pytest.approx(-7 / 44)
    assert report["weights"] == "train-only; no post-selection refit"


def test_deterministic_selection_and_exact_tie():
    model, report = fit()
    again, repeated = fit()
    assert model.to_dict() == again.to_dict() and report == repeated
    assert len(report["configurations"]) == 4
    model, report = fit(train_log2=[3] * 4, validation_log2=[3] * 2, penalties=(0.1, 1))
    assert report["selected_index"] == 1
    assert model.intercept == 3
    assert report["configurations"][1]["validation_mae_log2"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"penalties": []},
        {"penalties": ()},
        {"penalties": (1, 2, 3, 4, 5)},
        {"penalties": (1, 1)},
        {"penalties": (True,)},
        {"penalties": (0,)},
        {"penalties": (float("inf"),)},
        {"penalties": (10**400,)},
        {"penalties": ("1",)},
        {"provenance": None},
        {"provenance": {"data_role": "final"}},
        {"train_rows": None},
        {"train_rows": []},
        {"train_ids": None},
        {"validation_groups": None},
        {"train_ids": ["a"]},
        {"train_groups": []},
        {"train_ids": ["a"] * 4},
        {"train_groups": [1] * 4},
        {"train_groups": [" "] * 4},
        {"train_groups": ["a" * 257] * 4},
        {"validation_ids": ["a", "f"]},
        {"validation_groups": ["one", "three"]},
        {"validation_log2": None},
        {"validation_log2": [1]},
        {"validation_log2": [True, 2]},
        {"validation_log2": [float("nan"), 2]},
        {"validation_log2": [10**400, 2]},
        {"train_log2": [False] * 4},
    ],
)
def test_invalid_or_overlapping_partitions(changes):
    with pytest.raises(ValueError):
        fit(**changes)


def test_nonfinite_training_calibration_fails_closed(monkeypatch):
    monkeypatch.setattr(module, "median", lambda values: float("inf"))
    with pytest.raises(ValueError, match="calibration"):
        fit()
