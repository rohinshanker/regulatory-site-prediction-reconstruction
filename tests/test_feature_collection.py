"""Pinned development feature acquisition preserves identities and failures."""

import hashlib
import json
import runpy
import sys

import pytest
from test_rbs import AlgebraBackend, request

from experiments.rbs import collect, standby


def source(tmp_path, monkeypatch):
    path = tmp_path / "source.json"
    path.write_text(
        json.dumps(
            {"records": [{"id": "one", "sequence": request()["sequence"], "start": 20}]}
        )
    )
    monkeypatch.setattr(
        standby, "SOURCE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    return path


def test_collection_repeatability_and_failed_rows(tmp_path, monkeypatch):
    path = source(tmp_path, monkeypatch)
    options = {"profile": "context2017", "code_commit": "a" * 40, "seconds": 1800}
    first = collect.collect(path, AlgebraBackend(), **options)
    assert first == collect.collect(path, AlgebraBackend(), **options)
    assert first["results"][0]["status"] == "ok"
    failed = collect.collect(path, AlgebraBackend(fail=True), **options)
    assert failed["results"][0]["status"] == "failed"
    assert len(failed["results"]) == 1


def test_collection_bounds_and_expiration(tmp_path, monkeypatch):
    path = source(tmp_path, monkeypatch)
    for seconds in (0, True, float("nan"), 3601):
        with pytest.raises(ValueError, match="budget"):
            collect.collect(
                path,
                AlgebraBackend(),
                profile="historical",
                code_commit="a" * 40,
                seconds=seconds,
            )
    with pytest.raises(ValueError, match="Git SHA"):
        collect.collect(
            path, AlgebraBackend(), profile="historical", code_commit="main"
        )
    clock = iter((0.0, 1801.0))
    monkeypatch.setattr(collect.time, "monotonic", lambda: next(clock))
    with pytest.raises(ValueError, match="exhausted"):
        collect.collect(
            path, AlgebraBackend(), profile="historical", code_commit="a" * 40
        )
    path.write_text("{}")
    with pytest.raises(ValueError, match="source hash"):
        collect.collect(
            path, AlgebraBackend(), profile="historical", code_commit="a" * 40
        )


def test_collection_cli(tmp_path, monkeypatch, capsys):
    path = source(tmp_path, monkeypatch)
    monkeypatch.setattr(collect.RnaStructure, "open", lambda root: AlgebraBackend())
    output = tmp_path / "results.json"
    collect.main([str(path), "/unused", str(output), "--code-commit", "a" * 40])
    assert json.loads(capsys.readouterr().out)["n_records"] == 1
    assert json.loads(output.read_text())["profile"] == "context2017"
    monkeypatch.setattr(sys, "argv", ["collect", "--help"])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit):
        runpy.run_module("experiments.rbs.collect", run_name="__main__")
