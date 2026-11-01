"""Required release checks against an explicit separately built native backend."""

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
from test_termination import assert_identity, request

from regsite.termination import predict_termination
from regsite.termination_backend import load_backend

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "benchmarks/termination/native-smoke-manifest.json").read_text()
)["cases"] + [
    json.loads((ROOT / "benchmarks/termination/native-tie-control.json").read_text())
]
RESULT_SCHEMA = json.loads(
    (ROOT / "schemas/termination-result-1.schema.json").read_text()
)


@pytest.fixture(scope="module")
def native_backend():
    configured = os.environ.get("REGSITE_TERMINATION_TEST_BACKEND")
    if not configured:
        pytest.skip(
            "set REGSITE_TERMINATION_TEST_BACKEND for required native release checks"
        )
    path = Path(configured).resolve()
    return path, load_backend(path)


def projected(case):
    result = []
    for candidate in case["native_candidates"]:
        start = min(candidate["start_1based"], candidate["end_1based"]) - 1
        end = max(candidate["start_1based"], candidate["end_1based"])
        boundary = candidate["strand"] == "+" and start == 1
        result.append(
            (
                start,
                end,
                candidate["strand"],
                candidate["hairpin_score"],
                candidate["tail_score"],
                None if boundary else candidate["confidence"],
                candidate["context"],
                candidate["notes"],
            )
        )
    return sorted(result, key=lambda row: row[:3])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case"])
def test_exact_original_synthetic_roster(native_backend, case):
    _, backend = native_backend
    result = predict_termination(
        request({"id": case["case"], "sequence": case["sequence"]}), backend=backend
    )
    jsonschema.Draft202012Validator(RESULT_SCHEMA).validate(result)
    assert_identity(result)
    record = result["records"][0]
    unsupported = {
        "length74": "sequence_length_outside_domain",
        "length75": "no_search_positions",
        "boundary_uniform_gc": "uniform_background",
    }
    if case["case"] in unsupported:
        assert record["reason"] == unsupported[case["case"]]
        assert record["candidates"] is None
        assert record["execution"] is None
        assert record["attempted"] is False
        return
    assert result["status"] == "complete"
    assert record["execution"]["returncode"] == 0
    assert record["execution"]["stdout_complete"] is True
    assert record["execution"]["stderr_complete"] is True
    actual = [
        (
            item["hairpin"]["start"],
            item["hairpin"]["end"],
            item["strand"],
            item["hairpin_score"],
            item["tail_score"],
            item["confidence"],
            item["native"]["context"],
            item["native"]["notes"],
        )
        for item in record["candidates"]
    ]
    assert actual == projected(case)
    assert [item["candidate_id"] for item in record["candidates"]] == [
        f"candidate-{index:04d}" for index in range(1, len(actual) + 1)
    ]
    for item in record["candidates"]:
        assert item["native"]["printed_confidence"] == item["confidence"]
        interval = item["hairpin"]
        expected = (
            {"start": interval["end"], "end": interval["end"] + 15}
            if item["strand"] == "+"
            else {"start": interval["start"] - 15, "end": interval["start"]}
        )
        assert item["tail"] == expected
    if case["case"] == "tie27_nonsaturated":
        assert record["backgrounds"]["interior"]["selected_at_percent"] == 26
        assert record["backgrounds"]["interior"]["exact_table_tie"] is True
        assert record["candidates"][0]["confidence"] == 78


def test_repeat_prediction_identity(native_backend):
    _, backend = native_backend
    value = request({"id": "repeat", "sequence": CASES[-1]["sequence"]})
    first = predict_termination(value, backend=backend)
    second = predict_termination(value, backend=backend)
    assert first["status"] == second["status"] == "complete"
    assert first["prediction_sha256"] == second["prediction_sha256"]
    assert_identity(first)
    assert_identity(second)


@pytest.mark.parametrize(
    "name,exit_code", [("single", 0), ("batch", 0), ("unsupported", 1)]
)
def test_real_module_cli_outside_checkout(native_backend, tmp_path, name, exit_code):
    manifest, _ = native_backend
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    environment.pop("PYTHONHOME", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "regsite.termination_cli",
            str(ROOT / f"examples/termination-{name}.json"),
            "--backend-manifest",
            str(manifest),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == exit_code, completed.stderr.decode()
    assert completed.stderr == b""
    result = json.loads(completed.stdout)
    jsonschema.Draft202012Validator(RESULT_SCHEMA).validate(result)
    assert_identity(result)


def test_real_cli_duplicate_key_refusal(native_backend, tmp_path):
    manifest, _ = native_backend
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "regsite.termination_cli",
            "-",
            "--backend-manifest",
            str(manifest),
        ],
        input=b'{"records":[],"records":[]}',
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 2
    result = json.loads(completed.stdout)
    assert result["status"] == "invalid_input"
    assert result["records"] == []
