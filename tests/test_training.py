"""Grouped training isolation, selection, reproducibility and bounded failures."""

import math

import pytest

from regsite import training
from regsite.learning import fit_ridge
from regsite.training import fit_grouped, grouped_losses


def fit(**changes):
    settings = {
        "rows": [[0], [1], [2], [3], [4], [5]],
        "responses_log2": [0, 2, 4, 6, 8, 10],
        "feature_names": ("x",),
        "record_ids": list("abcdef"),
        "groups": ["one", "one", "two", "two", "three", "three"],
        "provenance": {
            "dataset_id": "synthetic",
            "split_id": "all-development",
            "data_role": "development",
        },
    }
    settings.update(changes)
    return fit_grouped(**settings)


def test_training_folds_are_isolated_and_match_independent_fits(monkeypatch):
    calls = []
    original = training.fit_ridge

    def spy(rows, targets, **kwargs):
        calls.append((rows, targets, kwargs))
        return original(rows, targets, **kwargs)

    monkeypatch.setattr(training, "fit_ridge", spy)
    model, report = fit(penalties=(0.1,))
    assert len(calls) == 4
    assert model.penalty == pytest.approx(0.6)
    for rows, targets, kwargs in calls[1:]:
        group = kwargs["provenance"]["split_id"].split(":")[1]
        assert len(rows) == len(targets) == 4
        assert kwargs["penalty"] == 0.4
        held_indices = [i for i, g in enumerate(report["groups"]) if g == group]
        assert not set(kwargs["record_ids"]) & {"abcdef"[i] for i in held_indices}
        expected = fit_ridge(rows, targets, **kwargs).predict(
            [[i] for i in held_indices]
        )
        actual = [
            report["configurations"][0]["out_of_fold_log2"][i] for i in held_indices
        ]
        assert actual == list(expected)
    assert report["n_records"] == 6 and report["n_groups"] == 3
    assert report["data_role"] == "development"
    assert report["warnings"] == ["selection_diagnostics_not_independent_final_test"]


def test_selection_and_json_artifact_are_deterministic():
    model, result = fit()
    repeat, again = fit()
    assert model.to_dict() == repeat.to_dict()
    assert result == again
    assert result["selected_index"] == 0
    assert len(result["configurations"]) == 4
    assert model.penalty == pytest.approx(0.06)
    for row in result["configurations"]:
        assert row["family_mae_log2"] >= 0
        assert row["row_rmse_log2"] >= 0


def test_exact_tie_prefers_stronger_penalty_and_group_loss_is_balanced():
    model, result = fit(responses_log2=[3] * 6, penalties=(0.1, 1.0))
    assert result["selected_index"] == 1
    assert model.intercept == 3 and model.coefficients == (0,)
    mae, rmse = grouped_losses([0, 0, 0], [0, 0, 6], ["a", "a", "b"])
    assert mae == 3
    assert rmse == pytest.approx(math.sqrt(12))
    with pytest.raises(ValueError, match="numeric range"):
        grouped_losses([1e308], [-1e308], ["a"])


@pytest.mark.parametrize(
    "changes",
    [
        {"provenance": None},
        {"provenance": {"data_role": "final"}},
        {"penalties": [1]},
        {"penalties": ()},
        {"penalties": (1, 2, 3, 4, 5)},
        {"penalties": (1, 1)},
        {"penalties": (True,)},
        {"penalties": (0,)},
        {"penalties": (float("inf"),)},
        {"penalties": ("1",)},
        {"groups": None},
        {"rows": ()},
        {"groups": []},
        {"groups": ["a"] * 6},
        {"groups": [None, "a", "b", "c", "d", "e"]},
        {"groups": [" ", "a", "b", "c", "d", "e"]},
        {"groups": ["x" * 257, "a", "b", "c", "d", "e"]},
        {"responses_log2": [True] * 6},
        {"record_ids": ["same"] * 6},
        {"rows": [[0]] * 101, "groups": [str(i) for i in range(101)]},
    ],
)
def test_invalid_configuration_fails_closed(changes):
    with pytest.raises(ValueError):
        fit(**changes)
