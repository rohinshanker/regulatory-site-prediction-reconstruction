"""Tiny synthetic resource-tool tests; no expensive ceiling scoring in unit tests."""

import io
import json
import runpy
import subprocess
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tools import measure_promoter_resources as tool


def spec(**changes):
    return {
        "lengths": [200],
        "sites": [2],
        "dna": "gc50",
        "states": "selected",
        "verbose": False,
        "seed": 1729,
        "edge_tss": None,
        **changes,
    }


def request(**changes):
    return tool.generate(spec(**changes), tool.pio.LIMITS)


def test_deterministic_generator_and_public_api():
    first = request()
    assert first == request()
    assert first != request(seed=1730)
    assert (
        tool.digest(b"abc")
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    row = tool.measure(first)
    assert row["status"] == "ok" and row["complete"]
    result = tool.pio.predict_batch(first)
    assert row["authoritative_bytes"] == len(tool.pio.result_bytes(result))
    assert row["authoritative_sha256"] == tool.digest(tool.pio.result_bytes(result))
    assert row["coverage"]["scored_sites"] == 2
    assert row["emitted_states"] == 0
    assert row["worker_seconds"] >= row["api_seconds"] > 0
    assert row["serialization_seconds"] > 0
    assert row["peak_rss"]["bytes"] > 0
    assert row["batch"]["limits"] == tool.pio.LIMITS
    assert tool.measure(request(states="all"))["emitted_states"] == 60
    assert len(tool.sequence("gc50", 100, 1729)) == 100
    for kind in ("A", "C", "G", "T"):
        assert tool.sequence(kind, 10, 0) == kind * 10
    for kind in ("gc20", "gc50", "gc80"):
        assert set(tool.sequence(kind, 1000, 1729)) == set("ACGT")
    with pytest.raises(KeyError):
        tool.sequence("private", 5, 0)


def original_limits():
    """The original diagnostic contract, never installed into the runtime."""
    return dict(
        tool.pio.LIMITS,
        max_planned_sites_per_record=5000,
        max_planned_sites_per_batch=20000,
        max_all_states_per_record=3000,
        max_all_states_per_batch=10000,
    )


def test_exact_ceiling_preflights_without_scoring():
    limits = original_limits()
    plans = {}
    for name in tool.ORIGINAL_SCENARIOS:
        setting = tool.scenarios(limits)[name]
        value = tool.generate(setting, limits)
        plans[name] = tool.preflight(value, limits)
        assert plans[name]["admitted_dimensions"]
        assert plans[name]["planned_sites"] == sum(setting["sites"])
        assert all(
            p["strand"] in ("+", "-")
            for r in value["records"]
            for p in r["scan"].get(
                "positions", [{"strand": s} for s in r["scan"].get("strands", [])]
            )
        )
    for name in (
        "record-A",
        "record-C",
        "record-G",
        "record-T",
        "record-gc20",
        "record-gc50",
        "record-gc80",
    ):
        assert {
            "max_normalized_bases_per_record",
            "max_planned_sites_per_record",
        } <= set(plans[name]["equalities"])
    assert {"max_records_per_batch", "max_normalized_bases_per_batch"} <= set(
        plans["batch-records-bases"]["equalities"]
    )
    assert "max_planned_sites_per_batch" in plans["verbose-20000"]["equalities"]
    assert {"max_all_state_sites_per_record", "max_all_states_per_record"} <= set(
        plans["all-record"]["equalities"]
    )
    assert plans["all-batch"]["planned_emitted_states"] == 10000
    assert "max_all_states_per_batch" in plans["all-batch"]["equalities"]


def test_verbose_inflation_uses_public_fields_and_exact_metadata_cap():
    value = request(verbose=True)
    r = value["records"][0]
    assert len(r["id"]) == tool.pio.LIMITS["max_id_chars"]
    assert len(r["host"]["name"]) == tool.pio.LIMITS["max_host_name_chars"]
    assert len(r["projection"]["contig"]) == tool.pio.LIMITS["max_contig_chars"]
    assert (
        len(tool.pio.canonical_bytes(r["metadata"]))
        == tool.pio.LIMITS["max_metadata_json_bytes"]
    )
    assert tool.measure(value)["status"] == "ok"
    assert (
        tool.measure(value)["authoritative_bytes"]
        > tool.measure(request())["authoritative_bytes"]
    )


def test_revised_limits_preserve_ceiling_identity_and_effective_probe():
    limits = dict(
        tool.pio.LIMITS,
        max_normalized_bases_per_record=200,
        max_planned_sites_per_record=3,
    )
    settings = tool.scenarios(limits)
    assert settings["record-A"]["sites"] == [5000]
    rejected = tool.preflight(tool.generate(settings["record-A"], limits), limits)
    assert not rejected["admitted_dimensions"] and rejected["violations"]
    assert tool.preflight(tool.generate(settings["effective-record"], limits), limits)[
        "admitted_dimensions"
    ]
    limits["max_planned_sites_per_record"] = 5000
    assert tool.scenarios(limits)["effective-record"]["sites"] == [400]


def test_incomplete_invalid_empty_and_size_cap_are_receipted(monkeypatch):
    bad = request()
    bad["records"][0]["calibration"] = "unavailable"
    result = tool.measure(bad)
    assert result["status"] == "incomplete" and not result["complete"]
    assert result["coverage"]["scored_sites"] == 0
    assert result["record_statuses"] == ["invalid_input"]
    assert tool.measure({"records": []})["status"] == "ok"
    assert tool.measure(request(sites=[0]))["status"] == "ok"
    monkeypatch.setitem(tool.pio.LIMITS, "max_result_json_bytes", 1)
    failure = tool.measure(request())
    assert failure["status"] == "setup_error"
    assert failure["error"] == {
        "type": "SetupError",
        "message": "max_result_json_bytes exceeded",
    }
    assert failure["coverage"] is None and failure["authoritative_bytes"] is None
    assert failure["api_seconds"] is None and not failure["complete"]
    assert failure["peak_rss"]["bytes"] > 0


@pytest.mark.parametrize(
    "system,multiplier,unit",
    [
        ("Darwin", 1, "bytes"),
        ("Linux", 1024, "KiB"),
        ("Other", None, "platform-dependent"),
    ],
)
def test_rss_units(monkeypatch, system, multiplier, unit):
    monkeypatch.setattr(tool.platform, "system", lambda: system)
    monkeypatch.setattr(
        tool.resource, "getrusage", lambda who: SimpleNamespace(ru_maxrss=7)
    )
    result = tool.peak_rss()
    assert result["raw"] == 7 and result["unit"] == unit
    assert result["bytes"] == (None if multiplier is None else 7 * multiplier)


def test_runtime_identity_pins_exact_files_and_model():
    identity = tool.runtime_identity()
    assert len(identity["git_head"]) == 40
    assert (identity["model"], identity["identity_model"]) == tool.pio.model_identity(
        tool.promoter.load_parameters()
    )
    assert identity["limits"] == tool.pio.LIMITS
    assert len(identity["source_sha256"]) == 4
    for path, digest in identity["source_sha256"].items():
        assert digest == tool.digest((tool.ROOT / path).read_bytes())
    assert (
        identity["api_call"]["seconds_per_record"]
        == tool.pio.LIMITS["default_seconds_per_record"]
    )


def payload():
    return {
        "request": request(),
        "limits": dict(tool.pio.LIMITS),
        "identity_model": tool.pio.model_identity(tool.promoter.load_parameters())[1],
    }


def test_real_child_process_isolation():
    first, second = tool.run_child(payload(), 20), tool.run_child(payload(), 20)
    assert first["status"] == second["status"] == "ok"
    assert first["authoritative_sha256"] == second["authoritative_sha256"]
    assert first["wall_seconds"] >= first["worker_seconds"]
    assert first["command"][0] == sys.executable


@pytest.mark.parametrize(
    "outcome,status",
    [
        (SimpleNamespace(returncode=2, stderr=b"bad", stdout=b""), "process_error"),
        (SimpleNamespace(returncode=0, stdout=b"bad"), "execution_error"),
        (subprocess.TimeoutExpired("worker", 1), "process_timeout"),
        (OSError("cannot spawn"), "execution_error"),
    ],
)
def test_child_failure_accounting(monkeypatch, outcome, status):
    def run(*args, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(tool.subprocess, "run", run)
    result = tool.run_child({}, 1)
    assert result["status"] == status and not result["complete"]
    assert result["peak_rss"] is None and result["coverage"] is None
    assert result["authoritative_bytes"] is None


def row(mode="selected", count=10, wall=1, size=1000, status="ok"):
    return {
        "settings": {"states": mode},
        "preflight": {"planned_sites": count},
        "wall_seconds": wall,
        "authoritative_bytes": size,
        "status": status,
    }


def test_recommendation_uses_worst_observed_cost_and_both_half_budgets():
    limits = dict(tool.pio.LIMITS, max_result_json_bytes=2000)
    result = tool.recommend(
        [row(), row(wall=2), row(status="setup_error"), row(count=0), row(mode="all")],
        limits,
    )["candidates"]
    assert result["selected"]["worst_measured_wall_seconds_per_site"] == 0.2
    assert result["selected"]["candidate_sites_per_record"] == 10
    assert result["selected"]["candidate_sites_per_batch"] == 10
    result = tool.recommend([row(size=1), row(mode="all", size=1)], original_limits())[
        "candidates"
    ]
    assert result["selected"]["candidate_sites_per_record"] == 150
    assert result["selected"]["candidate_sites_per_batch"] == 1500
    assert result["all"]["candidate_sites_per_record"] == 100
    assert result["all"]["candidate_sites_per_batch"] == 333
    assert tool.recommend([], limits)["candidates"] == {"selected": None, "all": None}


def test_collection_budget_hashes_and_failures(monkeypatch):
    monkeypatch.setattr(
        tool,
        "runtime_identity",
        lambda: {"limits": tool.pio.LIMITS, "identity_model": {}},
    )
    monkeypatch.setattr(tool, "scenarios", lambda _: {"tiny": spec()})
    times = iter([0, 0, 0.5, 2, 2])
    monkeypatch.setattr(tool.time, "monotonic", lambda: next(times))
    results = iter(
        [
            {"status": "setup_error", "complete": False},
            {
                "status": "ok",
                "complete": True,
                "wall_seconds": 0.1,
                "authoritative_bytes": 100,
            },
        ]
    )
    monkeypatch.setattr(tool, "run_child", lambda value, remaining: next(results))
    receipt = tool.collect(["tiny"], 3, 1)
    assert [r["status"] for r in receipt["measurements"]] == [
        "setup_error",
        "ok",
        "budget_exhausted",
    ]
    assert receipt["measurements"][0]["input_sha256"] == tool.pio.canonical_hash(
        request()
    )
    assert receipt["generator"] == tool.GENERATOR and receipt["repetitions"] == 3
    assert receipt["elapsed_seconds"] == 2


def test_main_worker_and_runtime_mismatch(monkeypatch, capsys):
    value = payload()
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(value)))
    assert tool.main(["--worker"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    for key in ("limits", "identity_model"):
        different = deepcopy(value)
        different[key] = {}
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(different)))
        with pytest.raises(ValueError, match="identity differs"):
            tool.main(["--worker"])


def test_main_writes_only_cache_and_preserves_repetitions(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    receipt = {
        "measurements": [{"scenario": "tiny", "repetition": 1, "status": "setup_error"}]
    }
    calls = []

    def collect(names, repetitions, budget):
        calls.append((names, repetitions, budget))
        return receipt

    monkeypatch.setattr(tool, "collect", collect)
    assert tool.main([]) == 0
    output = tmp_path / ".cache/promoter-resources/receipt.json"
    assert json.loads(output.read_bytes()) == receipt
    assert calls[0] == (list(tool.scenarios(tool.pio.LIMITS)), 3, 1800)
    assert "setup_error" in capsys.readouterr().out
    assert (
        tool.main(
            ["--scenario", "record-A", "--repetitions", "1", "--output", str(output)]
        )
        == 0
    )
    assert calls[-1][0] == ["record-A"]
    for args in (
        ["--output", str(tmp_path / "outside.json")],
        ["--repetitions", "0"],
        ["--repetitions", "11"],
        ["--budget-seconds", "0"],
        ["--budget-seconds", "1801"],
        ["--budget-seconds", "nan"],
        ["--scenario", "unknown"],
    ):
        with pytest.raises(SystemExit) as error:
            tool.main(args)
        assert error.value.code == 2


def test_script_entry_point(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [str(tool.ROOT / "tools/measure_promoter_resources.py"), "--worker"],
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload())))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(
            str(tool.ROOT / "tools/measure_promoter_resources.py"), run_name="__main__"
        )
    assert result.value.code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"


def test_scan_and_mixed_exact_counts_and_tiny_execution():
    limits = original_limits()
    settings = tool.scenarios(limits)
    scan = tool.generate(settings["scan-record"], limits)
    assert scan["records"][0]["scan"] == {
        "mode": "scan",
        "range": [1250, 3750],
        "strands": ["+", "-"],
    }
    ceiling = tool.preflight(tool.generate(settings["mixed-ceiling"], limits), limits)
    assert ceiling["planned_sites"] == 20000
    assert ceiling["planned_emitted_states"] == 10000
    assert {
        "max_records_per_batch",
        "max_normalized_bases_per_batch",
        "max_planned_sites_per_batch",
        "max_all_states_per_batch",
    } <= set(ceiling["equalities"])
    for states in (1000, 2000, 3000):
        for name in (f"all-{states}", f"mixed-4000-{states}"):
            plan = tool.preflight(tool.generate(settings[name], limits), limits)
            assert plan["planned_emitted_states"] == states
            assert plan["admitted_dimensions"]
            if name.startswith("mixed"):
                assert plan["planned_sites"] == 4000
    assert tool.measure(request(scan_mode="scan"))["coverage"]["scored_sites"] == 2
    tiny = request(
        lengths=[200, 200],
        sites=[2, 2],
        states="mixed",
        output_modes=["selected", "all"],
    )
    assert tool.measure(tiny)["emitted_states"] == 60


def test_mixed_recommendations_are_joint_evidence_not_independent_admission():
    mixed = row(mode="mixed")
    mixed.update(scenario="mixed", repetition=1)
    mixed["preflight"]["planned_emitted_states"] = 30
    result = tool.recommend([mixed], tool.pio.LIMITS)
    assert result["candidates"] == {"selected": None, "all": None}
    assert result["joint_samples"][0]["half_output_compliant"]
    mixed["authoritative_bytes"] = tool.pio.LIMITS["max_result_json_bytes"] // 2 + 1
    assert not tool.recommend([mixed], tool.pio.LIMITS)["joint_samples"][0][
        "half_output_compliant"
    ]
    mixed["status"] = "setup_error"
    mixed["authoritative_bytes"] = None
    assert not tool.recommend([mixed], tool.pio.LIMITS)["joint_samples"][0][
        "half_output_compliant"
    ]


def gate_receipt(names=("tiny",)):
    """Fabricated timing/RSS evidence around the real public model identity."""
    limits = dict(tool.pio.LIMITS)
    model, identity_model = tool.pio.model_identity(tool.promoter.load_parameters())
    identity = {
        "limits": limits,
        "model": model,
        "identity_model": identity_model,
        "api_call": tool.api_call(limits),
        "source_sha256": dict.fromkeys(tool.SOURCE_PATHS, "0" * 64),
        "git_head": "a" * 40,
        "python": "mock Python",
        "platform": "mock platform",
        "executable": "mock python",
    }
    rows = []
    for name in names:
        for rep in (1, 2, 3):
            rows.append(
                {
                    "scenario": name,
                    "repetition": rep,
                    "status": "ok",
                    "complete": True,
                    "settings": {"states": "selected"},
                    "preflight": {
                        "planned_sites": 10,
                        "planned_emitted_states": 0,
                        "admitted_dimensions": True,
                        "violations": [],
                        "records": [{}],
                    },
                    "coverage": {
                        "planned_sites": 10,
                        "scored_sites": 10,
                        "failed_sites": 0,
                        "unattempted_sites": 0,
                        "insufficient_context_sites": 0,
                    },
                    "peak_rss": {"raw": 10, "bytes": 10240, "unit": "KiB"},
                    "authoritative_bytes": 1000,
                    "wall_seconds": 0.001,
                    "api_call": deepcopy(identity["api_call"]),
                    "model": deepcopy(model),
                    "batch": {
                        "limits": deepcopy(limits),
                        "seconds_per_record": limits["default_seconds_per_record"],
                        "seconds_per_batch": limits["default_seconds_per_batch"],
                        "record_count": 1,
                        "complete": True,
                    },
                    "emitted_states": 0,
                    "record_statuses": ["ok"],
                }
            )
    return {
        "runtime": identity,
        "repetitions": 3,
        "measurements": rows,
        "elapsed_seconds": 1,
        "budget_seconds": 1200,
    }


def checked(receipt, **kwargs):
    return tool.check_receipt(receipt, required_scenarios=("tiny",), **kwargs)


def test_gate_is_separate_from_generation_and_pins_expected_build(monkeypatch):
    receipt = gate_receipt()

    def forbidden(*args, **kwargs):
        pytest.fail("receipt admission must not generate or score requests")

    monkeypatch.setattr(tool, "generate", forbidden)
    monkeypatch.setattr(tool, "measure", forbidden)
    result = checked(receipt, expected_runtime=deepcopy(receipt["runtime"]))
    assert result["passed"] and result["failures"] == []
    assert (
        result["time_safety"]["worst_complete_nonmixed_wall_seconds_per_site"] == 0.0001
    )
    assert result["time_safety"]["record"]["scaled_seconds"] == 0.1
    assert result["time_safety"]["batch"]["scaled_seconds"] == 0.4
    expected = deepcopy(receipt["runtime"])
    expected["source_sha256"][tool.SOURCE_PATHS[0]] = "1" * 64
    assert "differs from expected build" in str(
        checked(receipt, expected_runtime=expected)["failures"]
    )


@pytest.mark.parametrize(
    "path,value,message",
    [
        (("repetitions",), 2, "receipt repetitions"),
        (("repetitions",), True, "receipt repetitions"),
        (("measurements", 0, "repetition"), 2, "repetitions must be exactly"),
        (("measurements", 0, "repetition"), "1", "repetitions must be exactly"),
        (("measurements", 0, "status"), "incomplete", "incomplete/rejected"),
        (("measurements", 0, "complete"), False, "incomplete/rejected"),
        (("measurements", 0, "elapsed_overrun"), True, "incomplete/rejected"),
        (("measurements", 0, "coverage"), None, "incomplete/rejected"),
        (("measurements", 0, "coverage", "failed_sites"), 1, "incomplete/rejected"),
        (
            ("measurements", 0, "coverage", "unattempted_sites"),
            1,
            "incomplete/rejected",
        ),
        (("measurements", 0, "coverage", "scored_sites"), 9, "incomplete/rejected"),
        (
            ("measurements", 0, "preflight", "admitted_dimensions"),
            False,
            "preflight rejected",
        ),
        (("measurements", 0, "preflight", "violations"), ["cap"], "preflight rejected"),
        (("measurements", 0, "peak_rss"), None, "RSS not measured"),
        (("measurements", 0, "peak_rss", "raw"), None, "RSS not measured"),
        (("measurements", 0, "peak_rss", "unit"), "unknown", "RSS not measured"),
        (("measurements", 0, "peak_rss", "bytes"), 123, "RSS not measured"),
        (("measurements", 0, "authoritative_bytes"), None, "half output cap"),
        (("measurements", 0, "authoritative_bytes"), 33554433, "half output cap"),
        (("measurements", 0, "wall_seconds"), float("nan"), "wall time"),
        (("measurements", 0, "wall_seconds"), 0, "wall time"),
        (("measurements", 0, "api_call"), {}, "actual API deadlines/options"),
        (
            ("measurements", 0, "batch", "seconds_per_record"),
            1,
            "emitted runtime identity",
        ),
        (
            ("measurements", 0, "batch", "seconds_per_batch"),
            1,
            "emitted runtime identity",
        ),
        (("measurements", 0, "model"), {}, "emitted runtime identity"),
        (("measurements", 0, "batch", "limits"), {}, "emitted runtime identity"),
        (("measurements", 0, "emitted_states"), 1, "missing planned result counts"),
        (("measurements", 0, "record_statuses"), ["unsupported"], "rejected records"),
        (("measurements", 0, "record_statuses"), [], "missing planned result counts"),
        (
            ("measurements", 0, "batch", "record_count"),
            2,
            "missing planned result counts",
        ),
        (
            ("measurements", 0, "batch", "complete"),
            False,
            "missing planned result counts",
        ),
        (("runtime", "identity_model"), {}, "six-key identity"),
        (("runtime", "api_call"), {}, "actual API options"),
        (("runtime", "source_sha256"), {}, "source SHA256"),
        (
            ("runtime", "source_sha256", tool.SOURCE_PATHS[0]),
            "no-hash",
            "source SHA256",
        ),
        (("runtime", "source_sha256", tool.SOURCE_PATHS[0]), None, "source SHA256"),
        (("runtime", "python"), "", "missing runtime python"),
        (("runtime", "platform"), 1, "missing runtime platform"),
        (
            ("runtime", "limits", "max_planned_sites_per_record"),
            1000.5,
            "20 finite positive",
        ),
        (
            ("runtime", "limits", "max_planned_sites_per_record"),
            -1,
            "20 finite positive",
        ),
        (("elapsed_seconds",), 1201, "elapsed time exceeds budget"),
        (("elapsed_seconds",), None, "elapsed time exceeds budget"),
        (("budget_seconds",), None, "elapsed time exceeds budget"),
    ],
)
def test_gate_failures_are_concrete(path, value, message):
    receipt = gate_receipt()
    target = receipt
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    result = checked(receipt)
    assert not result["passed"]
    assert message in str(result["failures"])


@pytest.mark.parametrize(
    "receipt", [None, {}, {"runtime": None}, {"runtime": {"limits": {}}}]
)
def test_gate_rejects_malformed_receipts(receipt):
    result = checked(receipt)
    assert not result["passed"] and "malformed receipt" in str(result["failures"])


def test_gate_requires_names_repetitions_complete_model_and_timing_evidence():
    receipt = gate_receipt()
    assert not tool.check_receipt(receipt)["passed"]  # missing candidate roster
    del receipt["runtime"]["model"]["claims"]
    assert "complete emitted model fields" in str(checked(receipt)["failures"])
    receipt = gate_receipt()
    receipt["measurements"].pop()
    assert not checked(receipt)["passed"]
    receipt["measurements"] = []
    result = checked(receipt)
    assert "missing required scenario: tiny" in result["failures"]
    assert "no complete nonmixed" in str(result["failures"])
    receipt = gate_receipt()
    for row in receipt["measurements"]:
        row["settings"]["states"] = "mixed"
    assert "no complete nonmixed" in str(checked(receipt)["failures"])


def test_gate_empty_coverage_and_zero_context_sites():
    receipt = gate_receipt()
    for row in receipt["measurements"]:
        row["coverage"]["scored_sites"] = 8
        row["coverage"]["insufficient_context_sites"] = 2
    assert checked(receipt)["passed"]
    for row in receipt["measurements"]:
        row["coverage"] = dict.fromkeys(row["coverage"], 0)
        row["preflight"]["planned_sites"] = 0
    result = checked(receipt)
    assert not result["passed"] and "no complete nonmixed" in str(result["failures"])


def test_gate_half_size_and_time_equalities_global_cost_and_elapsed_overruns():
    receipt = gate_receipt()
    for row in receipt["measurements"]:
        row["authoritative_bytes"] = 33554432
        row["wall_seconds"] = 0.15  # N*c exactly 15 seconds for 1000 sites.
    assert checked(receipt)["passed"]
    for row in receipt["measurements"]:
        row["wall_seconds"] = 5
    result = checked(receipt)
    assert "record: N*c" in str(result["failures"])
    assert "batch: N*c" in str(result["failures"])
    receipt = gate_receipt()
    for row in receipt["measurements"]:
        row["wall_seconds"] = 31
    assert "elapsed wall time exceeds" in str(checked(receipt)["failures"])
    for row in receipt["measurements"]:
        row["preflight"]["records"] = [{}, {}]
        row["record_statuses"] = ["ok", "ok"]
        row["batch"]["record_count"] = 2
        row["wall_seconds"] = 301
    assert "elapsed wall time exceeds" in str(checked(receipt)["failures"])
    receipt = gate_receipt(("tiny", "mixed"))
    for row in receipt["measurements"][3:]:
        row["settings"]["states"] = "mixed"
        row["wall_seconds"] = 20
    assert checked(receipt)["passed"]  # mixed cost does not replace nonmixed c
    receipt = gate_receipt()
    receipt["runtime"]["limits"]["default_seconds_per_record"] = 100.0
    for row in receipt["measurements"]:
        row["api_call"]["seconds_per_record"] = 100.0
        row["batch"]["seconds_per_record"] = 100.0
        row["batch"]["limits"]["default_seconds_per_record"] = 100.0
        row["wall_seconds"] = 0.375
    receipt["runtime"]["api_call"]["seconds_per_record"] = 100.0
    assert checked(receipt)["passed"]  # batch N*c exactly 150 seconds


@pytest.mark.parametrize("value", [None, True, "1", float("nan"), float("inf"), 0, -1])
def test_nonpositive_measurement_numbers(value):
    assert not tool.positive(value)


def test_effective_suite_preflights_changed_caps_and_immutable_input_hashes():
    limits = tool.pio.LIMITS
    settings = tool.scenarios(limits)
    for name in tool.CANDIDATE_SCENARIOS:
        request = tool.generate(settings[name], limits)
        plan = tool.preflight(request, limits)
        assert plan["admitted_dimensions"], (name, plan["violations"])
        if name.startswith("effective-record-") or name == "effective-scan":
            assert plan["planned_sites"] == limits["max_planned_sites_per_record"]
            assert plan["observed"]["max_normalized_bases_per_record"] == 5000
    for name, expected in (
        (
            "all-2000",
            "7c345e731e58747aa08de5c0d6314896005cb4889c6b0d9b68cc3ff507e410e5",
        ),
        (
            "mixed-4000-2000",
            "d52819a1f3684d7020515aadb1a2017af5e929e11cb5dde2e73133194b5c6b7b",
        ),
    ):
        assert (
            tool.pio.canonical_hash(tool.generate(settings[name], limits)) == expected
        )
    all_plan = tool.preflight(
        tool.generate(settings["effective-all-sites"], limits), limits
    )
    assert all_plan["planned_sites"] == 100
    assert all_plan["planned_emitted_states"] == 2000
    mixed = tool.preflight(tool.generate(settings["effective-mixed"], limits), limits)
    assert mixed["planned_sites"] == 4000 and mixed["planned_emitted_states"] == 2000
    tiny = tool.generate(
        spec(states="all", partial_positions=[], extra_empty_sites=1), limits
    )
    result = tool.measure(tiny)
    assert result["complete"] and result["coverage"]["insufficient_context_sites"] == 1
    revised = dict(
        limits,
        max_normalized_bases_per_record=200,
        max_planned_sites_per_record=3,
        max_planned_sites_per_batch=12,
        max_all_states_per_record=5,
        max_all_states_per_batch=5,
        max_all_state_sites_per_record=3,
    )
    generated = tool.scenarios(revised)
    assert generated["effective-scan"]["sites"] == [2]  # explicit odd-count adjustment
    plan = tool.preflight(
        tool.generate(generated["effective-all-sites"], revised), revised
    )
    assert plan["planned_emitted_states"] == 5 and plan["admitted_dimensions"]
    even = dict(revised, max_all_states_per_record=30, max_all_states_per_batch=30)
    assert tool.scenarios(even)["effective-all-sites"]["partial_positions"] == []


def test_real_tight_deadline_and_completed_elapsed_overrun(monkeypatch):
    result = tool.measure(request(), seconds_per_record=1e-9, seconds_per_batch=1e-9)
    assert not result["complete"] and result["status"] == "incomplete"
    assert result["api_call"]["seconds_per_record"] == 1e-9
    assert result["batch"]["seconds_per_batch"] == 1e-9
    assert result["coverage"]["unattempted_sites"] == 2
    assert result["elapsed_overrun"]
    # An API returning a complete result after its budget is still a failure.
    completed = tool.pio.predict_batch(request())
    monkeypatch.setattr(tool.pio, "predict_batch", lambda *a, **kw: completed)
    result = tool.measure(request(), seconds_per_batch=1e-12)
    assert result["status"] == "elapsed_overrun" and not result["complete"]
    result = tool.measure(request(), seconds_per_record=1e-12)
    assert result["status"] == "elapsed_overrun" and not result["complete"]


def test_cli_admission_and_recheck_exit_codes(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    sample = gate_receipt(tool.CANDIDATE_SCENARIOS)
    monkeypatch.setattr(tool, "collect", lambda *a: deepcopy(sample))
    monkeypatch.setattr(tool, "runtime_identity", lambda: deepcopy(sample["runtime"]))
    assert tool.main(["--suite", "candidate", "--admit"]) == 0
    artifact = tmp_path / ".cache/promoter-resources/receipt.json"
    assert json.loads(artifact.read_bytes())["admission"]["passed"]
    assert tool.main(["--check-receipt", str(artifact)]) == 0
    sample["measurements"].pop()
    assert tool.main(["--suite", "candidate", "--admit"]) == 1
    assert tool.main(["--check-receipt", str(artifact)]) == 1
    assert "repetitions must be exactly" in capsys.readouterr().out
    assert tool.main(["--suite", "diagnostic"]) == 0
