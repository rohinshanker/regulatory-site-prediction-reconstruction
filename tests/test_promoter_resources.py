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


def test_exact_ceiling_preflights_without_scoring():
    limits = tool.pio.LIMITS
    plans = {}
    for name, setting in tool.scenarios(limits).items():
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
    result = tool.recommend([row(size=1), row(mode="all", size=1)], tool.pio.LIMITS)[
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
    settings = tool.scenarios(tool.pio.LIMITS)
    scan = tool.generate(settings["scan-record"], tool.pio.LIMITS)
    assert scan["records"][0]["scan"] == {
        "mode": "scan",
        "range": [1250, 3750],
        "strands": ["+", "-"],
    }
    ceiling = tool.preflight(
        tool.generate(settings["mixed-ceiling"], tool.pio.LIMITS), tool.pio.LIMITS
    )
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
            plan = tool.preflight(
                tool.generate(settings[name], tool.pio.LIMITS), tool.pio.LIMITS
            )
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
