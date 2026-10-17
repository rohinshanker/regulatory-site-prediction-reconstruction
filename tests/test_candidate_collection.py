"""Input-only candidate collection preserves every query, start and failure."""

import hashlib
import json
import runpy
import sys

import pytest
from test_rbs import AlgebraBackend, request

from experiments.rbs import candidates


def source(tmp_path):
    row = {
        **request(),
        "strand": "+",
        "temperature_c": 30,
        "host": "synthetic",
        "admission_status": "extractable",
        "start_positions": [20, 35],
    }
    rows = [
        row,
        {
            "id": "unmapped",
            "admission_status": "unsupported_anchor",
            "sequence": None,
            "start_positions": [],
        },
    ]
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps({"records": rows}))
    return path


def run(path, backend=None, **changes):
    settings = {
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "code_commit": "a" * 40,
        "profile": "context2017",
    }
    settings.update(changes)
    return candidates.collect(path, backend or AlgebraBackend(), **settings)


def test_retains_all_candidates_and_unsupported_queries(tmp_path):
    path = source(tmp_path)
    result = run(path)
    assert result == run(path)
    rows = result["records"]
    assert len(rows) == 2 and rows[1]["status"] == "unsupported"
    assert rows[1]["candidates"] == []
    assert [r["start"] for r in rows[0]["candidates"]] == [20, 35]
    first, second = rows[0]["candidates"]
    assert first["status"] == "ok" and first["score"] > 0
    assert second["status"] == "unsupported" and second["score"] is None
    assert first["prediction"]["input"]["start_positions"] == (20,)
    failed = run(path, AlgebraBackend(fail=True))
    assert failed["records"][0]["candidates"][0]["status"] == "failed"


def test_invalid_request_becomes_explicit_failed_candidate(tmp_path):
    path = source(tmp_path)
    data = json.loads(path.read_text())
    data["records"][0]["sequence"] = "N"
    path.write_text(json.dumps(data))
    row = run(path)["records"][0]["candidates"][0]
    assert row["status"] == "failed" and row["score"] is None
    assert row["prediction"]["status"] == "invalid_input"


def test_expiration_retains_all_later_candidates(tmp_path, monkeypatch):
    path = source(tmp_path)
    clock = iter([0, 3601, 3602])
    monkeypatch.setattr(candidates.time, "monotonic", lambda: next(clock))
    rows = run(path)["records"][0]["candidates"]
    assert len(rows) == 2
    assert all(r["reason"] == "collection_budget_exhausted" for r in rows)
    assert all(r["prediction"] is None for r in rows)


@pytest.mark.parametrize(
    "changes",
    [
        {"seconds": 0},
        {"seconds": True},
        {"seconds": float("nan")},
        {"seconds": 3601},
        {"code_commit": "main"},
        {"input_sha256": "wrong"},
        {"profile": "unknown"},
    ],
)
def test_invalid_collection_parameters(tmp_path, changes):
    with pytest.raises(ValueError):
        run(source(tmp_path), **changes)


def test_cli(tmp_path, monkeypatch, capsys):
    path = source(tmp_path)
    monkeypatch.setattr(candidates.RnaStructure, "open", lambda root: AlgebraBackend())
    output = tmp_path / "new" / "predictions.json"
    candidates.main(
        [
            str(path),
            "/unused",
            str(output),
            "--input-sha256",
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "--code-commit",
            "a" * 40,
            "--profile",
            "context2017",
        ]
    )
    assert json.loads(capsys.readouterr().out)["queries"] == 2
    assert len(json.loads(output.read_text())["records"]) == 2
    monkeypatch.setattr(sys, "argv", ["candidates", "--help"])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit):
        runpy.run_module("experiments.rbs.candidates", run_name="__main__")
