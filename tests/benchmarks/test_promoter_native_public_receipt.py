"""Synthetic arithmetic, adversarial I/O, and a separate immutable public-pin test."""

import copy
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path
from unittest import mock

import pytest

from benchmarks.promoter import native_public_receipt as c

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "benchmarks/promoter/native-public-receipt-manifest.json"
H = "a" * 64


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rank(n):
    return {
        "n_ranked": n,
        "n_tied_with_other_candidates": 0,
        "rank_sum_optimistic": n,
        "rank_sum_midrank": n,
        "rank_sum_pessimistic": n,
        "mean_optimistic": 1.0 if n else None,
        "mean_midrank": 1.0 if n else None,
        "mean_pessimistic": 1.0 if n else None,
        "median_midrank": 1.0 if n else None,
        "mean_ranked_window_size": 2.0 if n else None,
    }


def summary(n=30, inside=20, complete=20, scored=20):
    # Independent hand-checkable boundary: 20/30 = 2/3 versus 20/20 = 1.
    r = {
        "n_labels": n,
        "n_in_window": inside,
        "n_out_of_window": n - inside,
        "n_in_complete_query": complete,
        "n_label_candidate_scored": scored,
        "conditional_rank": rank(complete),
        "recovery": [],
        "exact_rank_tie_bounds": [],
    }
    cond = {
        "conditional_rank": rank(scored),
        "recovery": [],
        "exact_rank_tie_bounds": [],
        "scope": "synthetic successful-position endpoint",
    }
    for k in (1, 5, 10):
        for t in (0, 3):
            r["recovery"].append(
                {
                    "top_k": k,
                    "tolerance_nt": t,
                    "matched": complete,
                    "fraction_of_all_labels": complete / n if n else None,
                    "fraction_of_in_window_labels": complete / inside
                    if inside
                    else None,
                }
            )
            cond["recovery"].append(
                {
                    "top_k": k,
                    "tolerance_nt": t,
                    "matched": scored,
                    "fraction_of_scored_labels": 1.0 if scored else None,
                }
            )
        row = {"top_k": k}
        conditional_row = {"top_k": k}
        for side in ("optimistic", "pessimistic"):
            row.update(
                {
                    f"{side}_rank_within_k": complete,
                    f"{side}_fraction_of_all_labels": complete / n if n else None,
                    f"{side}_fraction_of_in_window_labels": complete / inside
                    if inside
                    else None,
                }
            )
            conditional_row.update(
                {
                    f"{side}_rank_within_k": scored,
                    f"{side}_fraction_of_scored_labels": 1.0 if scored else None,
                }
            )
        r["exact_rank_tie_bounds"].append(row)
        cond["exact_rank_tie_bounds"].append(conditional_row)
    r["conditional_successful_positions"] = cond
    return r


def fixture():
    settings = {
        "lower_is_better": True,
        "matching": "synthetic matching",
        "tie_rule": "synthetic tie order",
        "tolerances_nt": [0, 3],
        "top_k": [1, 5, 10],
    }
    uncertainty_settings = {"resamples": 100, "min_eligible_groups": 20}
    freeze = {
        "schema_version": "promoter-native-evaluation-freeze-1",
        "candidate_commit": "b" * 40,
        "metric_settings": settings,
        "uncertainty_settings": uncertainty_settings,
        "native_groups_sha256": H,
        "native_labels_sha256": H,
        "native_queries_sha256": H,
        "tool_and_protocol_sha256": {
            "benchmarks/promoter/native_metrics.py": H,
            "benchmarks/promoter/native_uncertainty.py": H,
        },
    }
    totals = {"n_bases": 120, "n_batches": 2, "n_requests": 30, "n_sites": 60}
    status = {k: 0 for k in c.STATUSES}
    runtime = {k: 0 for k in c.RUNTIME_STATUSES}
    status["ok"] = runtime["ok"] = 30
    candidates = dict(status, ok=60)
    adapter = {
        "batch_status": {
            "completed": 2,
            "execution_failed": 0,
            "not_run": 0,
            "setup_failed": 0,
        },
        "candidate_status": candidates,
        "n_complete_requests": 30,
        "n_incomplete_ok_requests": 0,
        "n_non_ok_requests_with_scored_candidates": 0,
        "n_partial_state_sites": 0,
        "n_tied_selected_sites": 0,
        "n_unattempted_sites": 0,
        "request_status": status,
        "runtime_status": runtime,
        "selected_score_status": {"ok": 60, "overflow": 0, "underflow": 0},
        "site_reason": {
            "deadline_exceeded": 0,
            "insufficient_context": 0,
            "nonfinite_arithmetic": 0,
        },
    }
    ack = {
        "schema_version": "promoter-native-protocol-acknowledgement-1",
        "candidate_commit": "b" * 40,
        "totals": totals,
        "execution": {"stage_seconds": 100.0},
        "wheel_sha256": H,
    }
    metrics = {
        "coverage": {
            "candidate_status_all_requests": dict(candidates),
            "candidate_status_in_ok_requests": dict(candidates),
            "n_candidates": 60,
            "n_complete_queries": 30,
            "n_incomplete_ok_queries": 0,
            "n_non_ok_queries_with_scored_candidates": 0,
            "n_queries": 30,
            "n_queries_with_labels": 20,
            "n_queries_with_labels_ok": 20,
            "request_status": status,
            "runtime_status": runtime,
            "score_schema": "promoter-native-scores-2",
        },
        "inputs": {
            "groups_sha256": H,
            "labels_sha256": H,
            "query_document_sha256": H,
            "scores_sha256": H,
        },
        "n_groups": 30,
        "overall": summary(),
        "settings": settings,
        "tool_sha256": H,
        "subgroups": {
            "labels_with_multiple_source_categories": 20,
            "replicons": {
                "NZ_CP006471.1": summary(),
                "NZ_CP006472.1": summary(0, 0, 0, 0),
                "NZ_CP006473.1": summary(0, 0, 0, 0),
            },
            # Deliberate overlap: these cannot be summed as a partition.
            "source_categories": {
                k: summary() for k in ("aTSS", "gTSS", "iTSS", "nTSS", "unclassified")
            },
            "scope": "overlapping synthetic categories",
        },
    }
    u = {
        "denominators": {
            "all_labels": {
                "n_eligible_groups": 30,
                "n_labels": 30,
                "n_zero_denominator_groups": 0,
                "status": "interval",
            },
            "in_window_labels": {
                "n_eligible_groups": 20,
                "n_labels": 20,
                "n_zero_denominator_groups": 10,
                "status": "interval",
            },
        },
        "endpoints": [],
        "inputs": {
            "metrics_document_sha256": H,
            "metrics_inputs": metrics["inputs"],
            "metrics_settings_sha256": sha(encode(settings)),
            "metrics_tool_sha256": H,
        },
        "n_groups": 30,
        "python": {"implementation": "synthetic", "version": "1"},
        "schema_version": "promoter-native-uncertainty-1",
        "scope": "synthetic",
        "settings": uncertainty_settings,
        "settings_sha256": sha(encode(uncertainty_settings)),
        "tool_sha256": H,
    }
    for denominator, n, eligible, point in (
        ("all_labels", 30, 30, 2 / 3),
        ("in_window_labels", 20, 20, 1.0),
    ):
        for k in (1, 5, 10):
            for t in (0, 3):
                u["endpoints"].append(
                    {
                        "denominator": denominator,
                        "denominator_labels": n,
                        "matched": 20,
                        "point": point,
                        "n_defined_resamples": 99,
                        "n_undefined_resamples": 1,
                        "n_eligible_groups": eligible,
                        "n_resamples": 100,
                        "status": "interval",
                        "top_k": k,
                        "tolerance_nt": t,
                        "interval": {"level": 0.95, "lower": 0.5, "upper": 1.0},
                    }
                )
    metrics["uncertainty"] = u
    aggregate = {
        "schema_version": "promoter-native-aggregate-report-1",
        "candidate_commit": "b" * 40,
        "scope": "synthetic",
        "collection_sha256": H,
        "execution_receipt_sha256": H,
        "journal_sha256": H,
        "collection": {
            "adapter_counts": adapter,
            "duration_seconds": 2.0,
            "stage_seconds": 100.0,
            "stop_reason": None,
            "totals": totals,
            "validation_failure_present": False,
        },
        "results": {
            "native": copy.deepcopy(metrics),
            "constant-control": copy.deepcopy(metrics),
        },
        "artifact_hashes": {
            k: {"metrics_sha256": H, "scores_sha256": H, "uncertainty_sha256": H}
            for k in ("native", "constant-control")
        },
    }
    return copy.deepcopy({c.FREEZE: freeze, c.ACK: ack, c.AGGREGATE: aggregate})


def write_fixture(root, docs):
    """Rebind synthetic digests, never real public pins, after a semantic mutation."""
    root = root.resolve()
    raw = {c.REPORT: b"opaque synthetic report\n", c.FREEZE: encode(docs[c.FREEZE])}
    docs[c.ACK]["evaluation_freeze_sha256"] = sha(raw[c.FREEZE])
    raw[c.ACK] = encode(docs[c.ACK])
    docs[c.AGGREGATE].update(
        evaluation_freeze_sha256=sha(raw[c.FREEZE]),
        protocol_acknowledgement_sha256=sha(raw[c.ACK]),
    )
    raw[c.AGGREGATE] = encode(docs[c.AGGREGATE])
    manifest = {
        "schema_version": "promoter-public-receipt-manifest-1",
        "scope": c.SCOPE,
        "candidate_commit": "b" * 40,
        "artifacts": {p: sha(b) for p, b in raw.items()},
        "metadata_contracts": {
            p: {k: v for k, v in docs[p].items() if k != "evaluation_freeze_sha256"}
            for p in (c.FREEZE, c.ACK)
        },
        "referenced_only": {
            p: [
                r
                for r in c.references(v)
                if r["location"]
                not in [
                    ["evaluation_freeze_sha256"],
                    ["protocol_acknowledgement_sha256"],
                ]
            ]
            for p, v in docs.items()
        },
    }
    for p, data in raw.items():
        target = root / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    target = root / "manifest.json"
    target.write_bytes(encode(manifest))
    return root, target


def test_exact_public_pins_and_allowlist():
    original = c.read_regular
    seen = []

    def guarded(path):
        seen.append(Path(path))
        assert Path(path) in {MANIFEST, *(ROOT / p for p in c.INPUTS)}
        return original(path)

    with mock.patch.object(c, "read_regular", guarded):
        result = c.check(ROOT, MANIFEST)
    assert set(seen) == {MANIFEST, *(ROOT / p for p in c.INPUTS)}
    assert result["candidate_commit"] == "2dff23cb5697507281f7ffa73fc617d56989b40c"
    assert result["checked_bytes"][c.AGGREGATE] == (
        "1b115087f52ecb1a7d9f42d6d402c4698315395cf00885b778a5493e38f70268"
    )
    assert result["referenced_only"]["status"] == "not_checked"
    assert result["scope"]["cohort"] == "consumed"
    assert c.canonical(result) == c.canonical(c.check(ROOT, MANIFEST))


def test_synthetic_success_and_cli(tmp_path, capsys):
    root, manifest = write_fixture(tmp_path, fixture())
    result = c.check(root, manifest)
    assert result["status"] == "consistent"
    assert c.main(["--root", str(root), "--manifest", str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out) == result
    with mock.patch.object(
        sys, "argv", ["receipt", "--root", str(root), "--manifest", str(manifest)]
    ):
        with pytest.warns(RuntimeWarning), pytest.raises(SystemExit, match="0"):
            runpy.run_module(c.__name__, run_name="__main__")
    with pytest.raises(SystemExit, match="2"):
        c.main([])


# Mutations reach semantic validation because write_fixture repairs all byte pins.
@pytest.mark.parametrize(
    "path,value,error",
    [
        (("overall", "n_labels"), 31, "label partition"),
        (("overall", "n_labels"), True, "integer"),
        (("overall", "n_labels"), -1, "integer"),
        (("overall", "n_labels"), 30.0, "integer"),
        (("overall", "n_labels"), 10**13, "integer"),
        (("overall", "n_in_complete_query"), 21, "label partition"),
        (("overall", "recovery", 0, "fraction_of_all_labels"), 1.0, "fraction"),
        (("overall", "recovery", 0, "matched"), 21, "eligible labels"),
        (("overall", "recovery", 0, "top_k"), True, "endpoint roster"),
        (("overall", "recovery"), [], "endpoint roster"),
        (("overall", "recovery"), {}, "endpoint list"),
        (("overall", "recovery", 0), None, "endpoint object"),
        (("overall", "conditional_rank", "rank_sum_midrank"), 21, "rank ordering"),
        (("overall", "conditional_rank", "rank_sum_pessimistic"), 22, "midpoint"),
        (("overall", "conditional_rank", "mean_optimistic"), 0.5, "rank mean"),
        (
            ("overall", "conditional_rank", "n_tied_with_other_candidates"),
            21,
            "tied count",
        ),
        (("overall", "conditional_rank", "median_midrank"), 0, "rank/window"),
        (
            ("overall", "conditional_rank", "mean_ranked_window_size"),
            0.5,
            "rank/window",
        ),
        (
            ("overall", "conditional_successful_positions", "scope"),
            9,
            "conditional scope",
        ),
        (
            ("overall", "exact_rank_tie_bounds", 0, "optimistic_rank_within_k"),
            19,
            "tie bounds",
        ),
        (
            ("overall", "exact_rank_tie_bounds", 0, "pessimistic_rank_within_k"),
            19,
            "fraction",
        ),
        (("inputs", "labels_sha256"), "b" * 64, "metric inputs"),
        (("settings", "lower_is_better"), False, "metric settings"),
        (("tool_sha256",), "b" * 64, "metric tool"),
        (("n_groups",), 31, "mismatch"),
        (("coverage", "n_candidates"), 61, "coverage"),
        (("coverage", "n_queries_with_labels_ok"), 21, "labelled query"),
        (("coverage", "candidate_status_in_ok_requests", "ok"), 61, "scored status"),
        (("coverage", "candidate_status_in_ok_requests", "ok"), 59, "mismatch"),
        (("subgroups", "labels_with_multiple_source_categories"), 31, "metadata"),
        (("subgroups", "source_categories", "aTSS", "n_labels"), 31, "label partition"),
        (("subgroups", "replicons", "NZ_CP006473.1"), summary(), "replicon partition"),
        (("uncertainty", "schema_version"), "future", "mismatch"),
        (("uncertainty", "settings", "resamples"), 101, "settings"),
        (("uncertainty", "settings_sha256"), "b" * 64, "mismatch"),
        (("uncertainty", "tool_sha256"), "b" * 64, "mismatch"),
        (
            ("uncertainty", "inputs", "metrics_document_sha256"),
            "b" * 64,
            "input references",
        ),
        (("uncertainty", "python", "version"), 3, "metadata types"),
        (
            ("uncertainty", "denominators", "all_labels", "n_eligible_groups"),
            31,
            "eligible",
        ),
        (
            ("uncertainty", "denominators", "all_labels", "n_zero_denominator_groups"),
            1,
            "mismatch",
        ),
        (
            ("uncertainty", "denominators", "in_window_labels", "n_eligible_groups"),
            19,
            "mismatch",
        ),
        (("uncertainty", "endpoints", 0, "n_resamples"), 101, "mismatch"),
        (("uncertainty", "endpoints", 0, "n_undefined_resamples"), 0, "mismatch"),
        (("uncertainty", "endpoints", 0, "matched"), 19, "mismatch"),
        (("uncertainty", "endpoints", 0, "point"), 1, "fraction"),
        (("uncertainty", "endpoints", 0, "interval", "lower"), 1.1, "interval bounds"),
        (("uncertainty", "endpoints", 0, "interval", "upper"), "x", "finite number"),
    ],
)
def test_semantic_failures(tmp_path, path, value, error):
    docs = fixture()
    target = docs[c.AGGREGATE]["results"]["native"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(c.ReceiptError, match=error):
        c.check(*write_fixture(tmp_path, docs))


@pytest.mark.parametrize(
    "data",
    [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":1e999}',
        b"\xff",
        b"{",
        b"[" * 1100,
    ],
)
def test_strict_json(data):
    with pytest.raises(c.ReceiptError, match="JSON"):
        c.parse(data)


@pytest.mark.parametrize(
    "kind", ["missing", "oversize", "directory", "symlink", "parent", "fifo"]
)
def test_input_failures(tmp_path, kind):
    root, manifest = write_fixture(tmp_path, fixture())
    path = root / c.REPORT
    path.unlink()
    if kind == "oversize":
        path.write_bytes(b"x" * (c.MAX_BYTES + 1))
    elif kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        path.symlink_to(manifest)
    elif kind == "parent":
        parent = path.parent
        parent.rmdir()
        parent.symlink_to(manifest.parent, target_is_directory=True)
    elif kind == "fifo":
        os.mkfifo(path)
    with pytest.raises(c.ReceiptError, match="input"):
        c.check(root, manifest)


def test_io_cli_and_bounded_growth(tmp_path, capsys):
    root, manifest = write_fixture(tmp_path, fixture())
    with mock.patch.object(
        c.os, "fstat", return_value=mock.Mock(st_mode=stat_mode(), st_size=0)
    ):
        (root / c.REPORT).write_bytes(b"x" * (c.MAX_BYTES + 1))
        with pytest.raises(c.ReceiptError, match="byte limit"):
            c.check(root, manifest)
    assert c.main(["--root", str(root), "--manifest", str(manifest)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    with mock.patch.object(c.os, "open", side_effect=PermissionError(13, "denied")):
        with pytest.raises(c.ReceiptError, match="I/O failure"):
            c.check(root, manifest)


def stat_mode():
    return 0o100644


def test_hash_mismatch_and_manifest_boundary(tmp_path):
    root, manifest = write_fixture(tmp_path, fixture())
    (root / c.REPORT).write_bytes(b"changed")
    with pytest.raises(c.ReceiptError, match="SHA-256"):
        c.check(root, manifest)
    root, manifest = write_fixture(tmp_path, fixture())
    obj = json.loads(manifest.read_bytes())
    obj["artifacts"]["private.json"] = H
    manifest.write_bytes(encode(obj))
    with pytest.raises(c.ReceiptError, match="allowlist"):
        c.check(root, manifest)


def test_opaque_present_references_never_opened(tmp_path):
    docs = fixture()
    # A real-looking path is a map key in the receipt, never a traversal target.
    docs[c.FREEZE]["tool_and_protocol_sha256"]["../private/scores.json"] = H
    docs[c.FREEZE]["tool_and_protocol_sha256"]["synthetic-reference.bin"] = H
    root, manifest = write_fixture(tmp_path, docs)
    (root / "synthetic-reference.bin").write_bytes(b"present but never opened")
    original = c.read_regular
    with mock.patch.object(c, "read_regular", wraps=original) as reader:
        assert c.check(root, manifest)["status"] == "consistent"
    assert reader.call_count == 5
    assert {Path(call.args[0]) for call in reader.call_args_list} == {
        manifest,
        *(root / p for p in c.INPUTS),
    }


def test_independent_denominators_and_partial_success():
    settings = {"top_k": [1, 5, 10], "tolerances_nt": [0, 3]}
    value = summary(30, 20, 10, 15)
    c.summary(value, settings, "partial")
    assert value["recovery"][0]["fraction_of_all_labels"] == 1 / 3
    assert value["recovery"][0]["fraction_of_in_window_labels"] == 0.5
    assert (
        value["conditional_successful_positions"]["recovery"][0][
            "fraction_of_scored_labels"
        ]
        == 1
    )
    c.summary(summary(0, 0, 0, 0), settings, "empty")
    with pytest.raises(c.ReceiptError, match="null"):
        c.fraction(0, 0, 0, "zero")
    with pytest.raises(c.ReceiptError, match="out of range"):
        c.fraction(2, 2, 1, "bound")


def test_reference_types_and_recursive_finite():
    assert c.parse(b'{"a":[1.25,null,true]}') == {"a": [1.25, None, True]}
    assert c.references([{"hash_sha256": H}])[0]["location"] == [0, "hash_sha256"]
    with pytest.raises(c.ReceiptError, match="invalid SHA"):
        c.references({"hash_sha256": "no"})
    with pytest.raises(c.ReceiptError, match="invalid SHA"):
        c.references({"map_sha256": {"x": 1}})
    with pytest.raises(c.ReceiptError, match="non-finite"):
        c._finite(float("inf"))


def test_unsupported_types_and_platform(tmp_path):
    root, manifest = write_fixture(tmp_path, fixture())
    obj = json.loads(manifest.read_bytes())
    obj["metadata_contracts"][c.ACK] = None
    manifest.write_bytes(encode(obj))
    with pytest.raises(c.ReceiptError, match="metadata"):
        c.check(root, manifest)
    root, manifest = write_fixture(tmp_path, fixture())
    docs = fixture()
    docs[c.ACK].pop("totals")
    root, manifest = write_fixture(tmp_path, docs)
    with pytest.raises(c.ReceiptError, match="unsupported schema/type"):
        c.check(root, manifest)
    with mock.patch.object(c.os, "open", side_effect=NotImplementedError):
        with pytest.raises(c.ReceiptError, match="unsupported schema/type"):
            c.check(root, manifest)


def test_partially_completed_collection(tmp_path):
    docs = fixture()
    adapter = docs[c.AGGREGATE]["collection"]["adapter_counts"]
    adapter["request_status"].update(ok=29, failed=1)
    adapter["runtime_status"].update(ok=29, failed=1)
    adapter["n_complete_requests"] = 29
    for metrics in docs[c.AGGREGATE]["results"].values():
        cov = metrics["coverage"]
        cov["request_status"] = copy.deepcopy(adapter["request_status"])
        cov["runtime_status"] = copy.deepcopy(adapter["runtime_status"])
        cov["n_complete_queries"] = 29
        cov["candidate_status_in_ok_requests"]["ok"] = 58
    assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"


@pytest.mark.parametrize(
    "kind,error",
    [
        ("candidate", "candidate"),
        ("schema", "schema"),
        ("not_object", "expected object"),
        ("total_bool", "integer"),
        ("status", "status total"),
        ("duration", "duration"),
        ("batch_roster", "schema/keys"),
        ("extra", "schema/keys"),
        ("uncertainty_groups", "insufficient groups"),
    ],
)
def test_stage_failures_after_rebinding(tmp_path, kind, error):
    docs = fixture()
    a = docs[c.AGGREGATE]
    if kind == "candidate":
        a["candidate_commit"] = "c" * 40
    elif kind == "schema":
        docs[c.FREEZE]["schema_version"] = "future"
    elif kind == "not_object":
        docs[c.FREEZE] = []
    elif kind == "total_bool":
        docs[c.ACK]["totals"]["n_bases"] = True
    elif kind == "status":
        a["collection"]["adapter_counts"]["candidate_status"]["ok"] = 59
    elif kind == "duration":
        a["collection"]["duration_seconds"] = 101
    elif kind == "batch_roster":
        a["collection"]["adapter_counts"]["batch_status"]["unknown"] = 0
    elif kind == "extra":
        a["extra"] = 0
    elif kind == "uncertainty_groups":
        d = a["results"]["native"]["uncertainty"]["denominators"]["in_window_labels"]
        d.update(n_eligible_groups=19, n_zero_denominator_groups=11)
    if kind == "not_object":
        # The trust metadata is JSON, but need not be an object: reject input first.
        docs[c.FREEZE] = {}
        root, manifest = write_fixture(tmp_path, docs)
        (root / c.FREEZE).write_bytes(b"[]")
        obj = json.loads(manifest.read_bytes())
        obj["artifacts"][c.FREEZE] = sha(b"[]")
        manifest.write_bytes(encode(obj))
    else:
        root, manifest = write_fixture(tmp_path, docs)
    with pytest.raises(c.ReceiptError, match=error):
        c.check(root, manifest)


@pytest.mark.parametrize("path", c.INPUTS)
def test_each_required_input_missing(tmp_path, path):
    root, manifest = write_fixture(tmp_path, fixture())
    (root / path).unlink()
    with pytest.raises(c.ReceiptError, match="I/O failure"):
        c.check(root, manifest)


def test_explicit_reference_inventory():
    result = c.check(ROOT, MANIFEST)
    refs = result["referenced_only"]["artifacts"]
    assert {p: len(rows) for p, rows in refs.items()} == {
        c.FREEZE: 12,
        c.ACK: 10,
        c.AGGREGATE: 37,
    }
    ack = {tuple(r["location"]): r["sha256"] for r in refs[c.ACK]}
    assert ack[("wheel_sha256",)] == (
        "4443e3558c6c689373fe09af4eabc1530b4af2a166391773056a69053939b1ff"
    )
    assert ("verified_artifact_sha256", "candidate.json") in ack
    assert all(r["location"] != ["evaluation_freeze_sha256"] for r in refs[c.AGGREGATE])
    assert result["scope"] == {
        "check": "public_receipt_consistency",
        "cohort": "consumed",
        "endpoint": "positive_TSS_localization",
        "independent_biological_recomputation": False,
        "markdown_semantics_checked": False,
        "release_or_calibration_approval": False,
    }


@pytest.mark.parametrize(
    "field,error",
    [
        ("evaluation_freeze_sha256", "aggregate freeze hash"),
        ("protocol_acknowledgement_sha256", "aggregate ack hash"),
    ],
)
def test_crossfile_byte_bindings(tmp_path, field, error):
    root, manifest = write_fixture(tmp_path, fixture())
    doc = json.loads((root / c.AGGREGATE).read_bytes())
    doc[field] = H
    raw = encode(doc)
    (root / c.AGGREGATE).write_bytes(raw)
    trust = json.loads(manifest.read_bytes())
    trust["artifacts"][c.AGGREGATE] = sha(raw)
    manifest.write_bytes(encode(trust))
    with pytest.raises(c.ReceiptError, match=error):
        c.check(root, manifest)


def test_inventory_not_silently_omitted(tmp_path):
    root, manifest = write_fixture(tmp_path, fixture())
    trust = json.loads(manifest.read_bytes())
    trust["referenced_only"][c.AGGREGATE].pop()
    manifest.write_bytes(encode(trust))
    with pytest.raises(c.ReceiptError, match="reference inventory"):
        c.check(root, manifest)
