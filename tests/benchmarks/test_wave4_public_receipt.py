"""Independent public pins, synthetic semantics and adversarial input boundaries."""

import copy
import hashlib
import json
import os
import runpy
import sys
from pathlib import Path
from unittest import mock

import pytest

from benchmarks.rbs import wave4_public_receipt as c

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "benchmarks/rbs/wave4-public-receipt-manifest.json"
H = "a" * 64
PINS = {
    c.PROTOCOL: (
        4381,
        "d8eb48c4d019e7e3a6da1ed826ec9f4b43232baf03129fbf37822e9057b474ab",
    ),
    c.FREEZE: (
        29476,
        "e79e5efebea018d501376f9aab8bcccfb15e4633f987b7c91ba92abc58049694",
    ),
    c.AGGREGATE: (
        54606,
        "b3344b2c539de19b58c53675cdf8d6ac96b26dd51fa56cf1df986b44160b9935",
    ),
    c.REVIEW: (
        1977,
        "39e8d8983871b4f9db9ded49a07a3012ab496b3c65edec86757fe8f3b5a73b61",
    ),
    c.REPORT: (
        18870,
        "e14d73d63abd078c2470e0ec41ca092236ea5f69f242db600b12210d55c3948d",
    ),
}


def encode(value):
    return (
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def summary(n=335, observed=332, success=None, paired=None, rho=0.2, not_run=0):
    success = n if success is None else success
    paired = observed if paired is None else paired
    executed = n - not_run
    statuses = {
        k: v
        for k, v in {
            "ok": success,
            "not_run": not_run,
            "failed": n - success - not_run,
        }.items()
        if v
    }
    return {
        "n_inputs": n,
        "n_observed": observed,
        "n_success": success,
        "n_paired": paired,
        "coverage": success / n if n else None,
        "spearman_rho": rho if paired >= 2 else None,
        "status_counts": statuses,
        "failure_reasons": {"synthetic failure": n - success} if n - success else {},
        "runtime_seconds": {
            "n_executed": executed,
            "sum": executed,
            "median": 1 if executed else None,
            "p95_nearest_rank": 1 if executed else None,
            "maximum": 1 if executed else None,
        },
    }


def model_set(n, observed):
    return {
        name: summary(n, observed, rho=0.2 if name == "standby2014-linker3" else 0.3)
        for name in c.ROSTER
    }


def comparison(n=335, observed=332, gain=0.1):
    return {
        "n_inputs": n,
        "n_common_success": n,
        "n_common_measured": observed,
        "n_blocks": 56,
        "n_common_blocks": 56,
        "lost_reference_successes": 0,
        "rank_gain": gain,
        "requested_draws": 10000,
        "attempted_draws": 10000,
        "usable_draws": 10000,
        "undefined_draws": 0,
        "interval95": [0.05, 0.15],
        "interval_status": "ok",
    }


def group(n, observed, secondary=False):
    result = {
        "models": model_set(n, observed),
        "primary_pair": {
            "n_common_measured": observed,
            "rank_gain": 0.1 if observed >= 30 else None,
            "interval95": None,
            "role": "descriptive subgroup point only",
        },
    }
    if secondary:
        result["role"] = c.SECONDARY_ROLE
    return result


def fixture():
    """Use fixed metadata as trust inputs, independently synthesize all metrics."""
    trust = json.loads(MANIFEST.read_bytes())
    contracts = trust["metadata_contracts"]
    protocol, freeze = (copy.deepcopy(contracts[p]) for p in (c.PROTOCOL, c.FREEZE))
    aggregate = {
        "schema_version": "rbs-wave4-aggregate-1",
        "panel_consumed": True,
        "collection_complete": True,
        "artifacts_unchanged": True,
        "primary": {
            "endpoint": contracts["primary_endpoint"],
            "models": model_set(335, 332),
            "contrast": copy.deepcopy(freeze["primary"]),
            "comparison": comparison(),
            "advancement": {"advance": True, "reasons": []},
        },
        "descriptive_against_primary_reference": {
            name: comparison()
            for name in c.ROSTER
            if name not in ("standby2014-linker3", "joint_standby-linker3")
        },
        "descriptive_coding_gc_strata": {
            "low": group(31, 29),
            "middle": group(303, 302),
            "high": group(1, 1),
        },
        "Kuo2020_secondary": {
            ctx: group(87, obs, True)
            for ctx, obs in (("arti", 87), ("dmsC", 84), ("fepB", 82))
        },
        "facilitated_cambray_evaluated": False,
        "calibration_fitted": False,
        "outliers_removed": False,
        "scope": contracts["aggregate_scope"],
        "identities": {
            "collection": H,
            "inputs": protocol["input_file_sha256"],
            "outcomes": protocol["private_outcomes_sha256"],
            "protocol": H,
            "receipt": freeze["collector_receipt_sha256"],
            "split": protocol["split_file_sha256"],
        },
        "evaluator_sha256": freeze["benchmark_code_sha256"][
            "benchmarks/rbs/wave4_evaluate.py"
        ],
        "metric_code_sha256": freeze["benchmark_code_sha256"][
            "benchmarks/rbs/wave4_metrics.py"
        ],
        "publication_context": copy.deepcopy(contracts["publication_context"]),
    }
    review = copy.deepcopy(contracts["review"])
    review["artifacts"] = {
        c.REPORT: H,
        c.AGGREGATE: H,
        "docs/validation/rbs-new-evaluation-data.md": H,
    }
    review["independent_recomputation"] = {
        "exact_fields_matched": 2,
        "floating_fields_matched": 3,
        "maximum_absolute_float_difference": 0.0,
        "jobs_audited": 6556,
        "primary_draws": 10000,
        "primary_usable_draws": 10000,
        "primary_undefined_draws": 0,
        "advance": True,
    }
    return {
        c.REPORT: b"Opaque synthetic caf\xc3\xa9 report\n",
        c.PROTOCOL: protocol,
        c.FREEZE: freeze,
        c.AGGREGATE: aggregate,
        c.REVIEW: review,
    }


def fixture_inventory(docs):
    """Build expected trust inventory without calling the production validator."""
    excluded = {
        c.PROTOCOL: set(),
        c.FREEZE: {("identities", "protocol_sha256")},
        c.AGGREGATE: {("identities", "protocol")},
        c.REVIEW: {("artifacts", c.REPORT), ("artifacts", c.AGGREGATE)},
    }

    def walk(value, location=()):
        rows = []
        if location == ("configurations", 6, "command", 7):
            rows.append({"location": list(location), "sha256": value})
        elif isinstance(value, dict):
            for key, child in sorted(value.items()):
                path = (*location, key)
                if key.endswith("sha256") or path in (("identities",), ("artifacts",)):
                    entries = (
                        child.items() if isinstance(child, dict) else [(None, child)]
                    )
                    for name, hashed in sorted(entries):
                        rows.append(
                            {
                                "location": list(
                                    path if name is None else (*path, name)
                                ),
                                "sha256": hashed,
                            }
                        )
                else:
                    rows.extend(walk(child, path))
        elif isinstance(value, list):
            for i, child in enumerate(value):
                rows.extend(walk(child, (*location, i)))
        return rows

    return {
        p: [row for row in walk(docs[p]) if tuple(row["location"]) not in locations]
        for p, locations in excluded.items()
    }


def write_fixture(tmp_path, docs):
    """Refresh every synthetic byte chain before reaching semantic validators."""
    root = tmp_path.resolve() / "public"
    f, a, r = (docs[p] for p in (c.FREEZE, c.AGGREGATE, c.REVIEW))
    protocol_hash = sha(encode(docs[c.PROTOCOL]))
    f["identities"]["protocol_sha256"] = protocol_hash
    a["identities"]["protocol"] = protocol_hash
    original = {k: v for k, v in a.items() if k != "publication_context"}
    recovered = sha(encode(original))
    a["publication_context"]["original_evaluator_aggregate_sha256"] = recovered
    r["private_original_aggregate_sha256"] = recovered
    r["artifacts"][c.REPORT] = sha(docs[c.REPORT])
    r["artifacts"][c.AGGREGATE] = sha(encode(a))
    trust = json.loads(MANIFEST.read_bytes())
    trust["metadata_contracts"] = {
        c.PROTOCOL: docs[c.PROTOCOL],
        c.FREEZE: f,
        "publication_context": {
            k: v
            for k, v in a["publication_context"].items()
            if k != "original_evaluator_aggregate_sha256"
        },
        "review": {
            k: v
            for k, v in r.items()
            if k
            not in (
                "artifacts",
                "private_original_aggregate_sha256",
                "independent_recomputation",
            )
        },
        "aggregate_scope": a["scope"],
        "primary_endpoint": a["primary"]["endpoint"],
    }
    trust["referenced_only"] = fixture_inventory(docs)
    trust["artifacts"] = {}
    for path, value in docs.items():
        data = value if path == c.REPORT else encode(value)
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        trust["artifacts"][path] = sha(data)
    manifest = root / "manifest.json"
    manifest.write_bytes(encode(trust))
    return root, manifest


def set_path(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


def rewrite(root, manifest, path, mutate):
    """Change one binding after fixture refresh, preserving outer public pins."""
    value = json.loads((root / path).read_bytes())
    mutate(value)
    data = encode(value)
    (root / path).write_bytes(data)
    trust = json.loads(manifest.read_bytes())
    trust["artifacts"][path] = sha(data)
    manifest.write_bytes(encode(trust))


def test_immutable_public_pins():
    trust = json.loads(MANIFEST.read_bytes())
    for path, (size, expected) in PINS.items():
        raw = (ROOT / path).read_bytes()
        assert len(raw) == size
        assert sha(raw) == expected == trust["artifacts"][path]
    result = c.check(ROOT, MANIFEST)
    assert result["checked_bytes"] == {p: pin for p, (_, pin) in PINS.items()}
    assert (
        result["recovered_original_digest"]
        == "dcf165f06a8e97d69bb9a087ed9cc85cade939b6917fd42a84382922edea2080"
    )
    assert result["scope"] == c.SCOPE
    assert result["review_numerical_agreement"] == "reported_only"


def test_exactly_five_artifact_reads_and_opaque_references(tmp_path):
    docs = fixture()
    docs[c.FREEZE]["configurations"][0]["cwd"] = "/private/never/open"
    docs[c.FREEZE]["configurations"][0]["command"] = ["do-not-execute"]
    docs[c.FREEZE]["benchmark_code_sha256"]["../private/outcomes.json"] = H
    docs[c.FREEZE]["benchmark_code_sha256"]["present-reference.bin"] = H
    root, manifest = write_fixture(tmp_path, docs)
    (root / "present-reference.bin").write_bytes(b"never read")
    with mock.patch.object(c, "read_regular", wraps=c.read_regular) as reader:
        result = c.check(root, manifest)
    assert result["status"] == "consistent"
    assert reader.call_count == 6
    assert {Path(call.args[0]) for call in reader.call_args_list} == {
        manifest,
        *(root / p for p in c.INPUTS),
    }
    refs = result["referenced_only"]["artifacts"]
    assert result["referenced_only"]["status"] == "not_checked"
    assert {
        "location": ["benchmark_code_sha256", "../private/outcomes.json"],
        "sha256": H,
    } in refs[c.FREEZE]
    assert {
        "location": ["artifacts", "docs/validation/rbs-new-evaluation-data.md"],
        "sha256": H,
    } in refs[c.REVIEW]
    assert all(
        row["location"] != ["identities", "protocol"] for row in refs[c.AGGREGATE]
    )
    assert any(
        row["location"][-2:] == ["binary_sha256", "Fold"] for row in refs[c.FREEZE]
    )


def test_cli_deterministic_and_entrypoint(tmp_path, capsys):
    root, manifest = write_fixture(tmp_path, fixture())
    args = ["--root", str(root), "--manifest", str(manifest)]
    assert c.main(args) == 0
    first = capsys.readouterr().out
    assert c.main(args) == 0
    assert capsys.readouterr().out == first
    assert first == c.canonical(c.check(root, manifest)).decode()
    with (
        mock.patch.object(sys, "argv", ["wave4_public_receipt", *args]),
        mock.patch.dict(sys.modules),
    ):
        sys.modules.pop("benchmarks.rbs.wave4_public_receipt")
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_module("benchmarks.rbs.wave4_public_receipt", run_name="__main__")
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == first
    (root / c.REPORT).unlink()
    assert c.main(args) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "failed"
    assert str(root) not in output
    with pytest.raises(SystemExit) as exit_info:
        c.main([])
    assert exit_info.value.code == 2
    assert not capsys.readouterr().out
    with pytest.raises(SystemExit) as exit_info:
        c.main([*args, "--output", str(root / "forbidden-output.json")])
    assert exit_info.value.code == 2
    assert not (root / "forbidden-output.json").exists()
    assert not capsys.readouterr().out


@pytest.mark.parametrize(
    "path,value,error",
    [
        (("n_inputs",), True, "integer"),
        (("n_observed",), 336, "marginal"),
        (("n_success",), -1, "integer"),
        (("n_paired",), 331, "intersection"),
        (("coverage",), 0.5, "coverage"),
        (("spearman_rho",), 1.1, "correlation"),
        (("status_counts",), {"alien": 335}, "unsupported status"),
        (("status_counts",), {"ok": 335, "failed": 0}, "positive"),
        (("status_counts",), {"ok": 334}, "count total"),
        (("failure_reasons",), {"failed": 1}, "count total"),
        (("runtime_seconds", "n_executed"), 334, "runtime accounting"),
        (("runtime_seconds", "sum"), 400, "sum bounds"),
        (("runtime_seconds", "median"), 2, "ordering"),
        (("extra",), 1, "schema/keys"),
    ],
)
def test_summary_semantic_failures_after_hash_refresh(tmp_path, path, value, error):
    docs = fixture()
    set_path(docs[c.AGGREGATE]["primary"]["models"]["control-constant"], path, value)
    with pytest.raises(c.ReceiptError, match=error):
        c.check(*write_fixture(tmp_path, docs))


@pytest.mark.parametrize(
    "path,value,error",
    [
        (("n_inputs",), 334, "comparison inputs"),
        (("n_common_success",), 334, "common success"),
        (("n_common_measured",), 331, "measured subset"),
        (("n_common_measured",), 336, "measured subset"),
        (("lost_reference_successes",), 1, "lost successes"),
        (("n_blocks",), 55, "blocks"),
        (("n_common_blocks",), 57, "common blocks"),
        (("rank_gain",), 0.2, "common-cohort"),
        (("requested_draws",), 9999, "requested draws"),
        (("attempted_draws",), 9999, "draw accounting"),
        (("usable_draws",), 9999, "draw accounting"),
        (("interval_status",), "future", "interval status"),
        (("interval95",), [0.1], "expected pair"),
        (("interval95",), [0.2, 0.1], "bounds/order"),
        (("interval95",), [-3, 0.1], "bounds/order"),
    ],
)
def test_comparison_semantic_failures_after_hash_refresh(tmp_path, path, value, error):
    docs = fixture()
    set_path(docs[c.AGGREGATE]["primary"]["comparison"], path, value)
    with pytest.raises(c.ReceiptError, match=error):
        c.check(*write_fixture(tmp_path, docs))


@pytest.mark.parametrize(
    "kind,error",
    [
        ("roster", "model roster"),
        ("descriptive", "descriptive roster"),
        ("gc", "GC partition n_inputs"),
        ("runtime", "GC partition runtime"),
        ("status", "GC partition n_success"),
        ("reason", "GC partition failure"),
        ("secondary", "secondary observations"),
        ("shared", "shared source"),
        ("secondary_interval", "point-only interval"),
        ("small_point", "unsupported point"),
        ("scheduled", "scheduled_jobs"),
        ("controls", "controls"),
        ("external", "external_jobs"),
        ("candidate", "candidate identity"),
        ("duplicate", "configuration roster"),
        ("config_kind", "configuration roster"),
        ("contrast", "contrast roster"),
        ("advancement", "advancement"),
        ("audit_jobs", "jobs audited"),
        ("audit_draws", "primary_draws"),
        ("audit_advance", "review advance"),
        ("audit_type", "integer"),
        ("audit_difference", "negative"),
        ("flag", "panel_consumed"),
        ("collection_type", "expected boolean"),
    ],
)
def test_cross_scope_semantic_failures(tmp_path, kind, error):
    docs = fixture()
    a, f, r = (docs[p] for p in (c.AGGREGATE, c.FREEZE, c.REVIEW))
    primary = a["primary"]
    if kind == "roster":
        primary["models"].pop("control-constant")
    elif kind == "descriptive":
        a["descriptive_against_primary_reference"].pop("control-constant")
    elif kind == "gc":
        a["descriptive_coding_gc_strata"]["high"]["models"] = model_set(2, 1)
    elif kind == "runtime":
        for row in a["descriptive_coding_gc_strata"]["high"]["models"].values():
            row["runtime_seconds"].update(
                sum=2, median=2, p95_nearest_rank=2, maximum=2
            )
    elif kind in ("status", "reason"):
        row = primary["models"]["control-constant"]
        row.update(
            n_success=334,
            coverage=334 / 335,
            status_counts={"ok": 334, "failed": 1},
            failure_reasons={"x": 1},
        )
        row["n_paired"] = 332
        pair = a["descriptive_against_primary_reference"]["control-constant"]
        pair.update(n_common_success=334, lost_reference_successes=1)
        if kind == "reason":
            for g in a["descriptive_coding_gc_strata"].values():
                if g["models"]["control-constant"]["n_inputs"] == 303:
                    row = g["models"]["control-constant"]
                    row.update(
                        n_success=302,
                        coverage=302 / 303,
                        status_counts={"ok": 302, "failed": 1},
                        failure_reasons={"y": 1},
                    )
    elif kind == "secondary":
        for row in a["Kuo2020_secondary"]["fepB"]["models"].values():
            row.update(n_observed=83, n_paired=83)
        a["Kuo2020_secondary"]["fepB"]["primary_pair"]["n_common_measured"] = 83
    elif kind == "shared":
        a["descriptive_coding_gc_strata"]["low"]["models"]["control-constant"] = (
            summary(32, 29)
        )
    elif kind == "secondary_interval":
        a["Kuo2020_secondary"]["arti"]["primary_pair"]["interval95"] = [0, 1]
    elif kind == "small_point":
        a["descriptive_coding_gc_strata"]["low"]["primary_pair"]["rank_gain"] = 0
    elif kind in ("scheduled", "controls", "external"):
        f[
            {
                "scheduled": "scheduled_jobs",
                "controls": "controls",
                "external": "external_jobs",
            }[kind]
        ] += 1
    elif kind == "candidate":
        f["scientific_execution_commit"] = "b" * 40
    elif kind == "duplicate":
        f["configurations"][-1] = copy.deepcopy(f["configurations"][0])
    elif kind == "config_kind":
        f["configurations"][0]["kind"] = "other"
    elif kind == "contrast":
        primary["contrast"]["contender"] = primary["contrast"]["reference"]
        f["primary"] = primary["contrast"]
    elif kind == "advancement":
        primary["advancement"]["advance"] = False
    elif kind == "audit_jobs":
        r["independent_recomputation"]["jobs_audited"] -= 1
    elif kind == "audit_draws":
        r["independent_recomputation"]["primary_draws"] -= 1
    elif kind == "audit_advance":
        r["independent_recomputation"]["advance"] = False
    elif kind == "audit_type":
        r["independent_recomputation"]["exact_fields_matched"] = True
    elif kind == "audit_difference":
        r["independent_recomputation"]["maximum_absolute_float_difference"] = -1
    elif kind == "flag":
        a["panel_consumed"] = False
    elif kind == "collection_type":
        a["collection_complete"] = 1
    with pytest.raises(c.ReceiptError, match=error):
        c.check(*write_fixture(tmp_path, docs))


@pytest.mark.parametrize(
    "data",
    [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":-Infinity}',
        b'{"a":1e999}',
        b"\xff",
        b"{",
        b"1e",
        b"01",
        b'"\\ud800"',
        b"[" * 1100,
        b"[" * 65 + b"0" + b"]" * 65,
        b"[" + b"0," * 100000 + b"0]",
    ],
)
def test_strict_json(data):
    with pytest.raises(c.ReceiptError, match="JSON"):
        c.parse(data)


def test_valid_json_unicode_and_order_sensitive_recovery():
    assert c.parse(b'{"a":[1.25,null,true,"caf\xc3\xa9"]}') == {
        "a": [1.25, None, True, "café"]
    }
    assert c.canonical({"b": 1, "a": 2}) == b'{"a":2,"b":1}\n'
    assert (
        c.original_bytes({"b": "café", "publication_context": {}, "a": 1})
        == '{\n  "b": "café",\n  "a": 1\n}\n'.encode()
    )
    assert c.original_bytes({"a": 1, "b": 2}) != c.original_bytes({"b": 2, "a": 1})
    assert c.references([{"some_sha256": H}]) == [
        {"location": [0, "some_sha256"], "sha256": H}
    ]


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "oversize",
        "directory",
        "symlink",
        "parent",
        "fifo",
        "growth",
        "manifest_symlink",
        "manifest_oversize",
        "root_symlink",
    ],
)
def test_input_boundaries(tmp_path, kind):
    root, manifest = write_fixture(tmp_path, fixture())
    path = root / c.REPORT
    if kind == "manifest_symlink":
        linked = root / "link.json"
        linked.symlink_to(manifest)
        manifest = linked
    elif kind == "manifest_oversize":
        manifest.write_bytes(b"x" * (c.MAX_BYTES + 1))
    elif kind == "root_symlink":
        linked = root.parent / "link"
        linked.symlink_to(root, target_is_directory=True)
        root = linked
    else:
        path.unlink()
        if kind in ("oversize", "growth"):
            path.write_bytes(b"x" * (c.MAX_BYTES + 1))
        elif kind == "directory":
            path.mkdir()
        elif kind == "symlink":
            path.symlink_to(manifest)
        elif kind == "parent":
            path.parent.rmdir()
            path.parent.symlink_to(manifest.parent, target_is_directory=True)
        elif kind == "fifo":
            os.mkfifo(path)
    with mock.patch.object(c.os, "fstat", wraps=c.os.fstat) as info:
        if kind == "growth":
            info.return_value = mock.Mock(st_mode=0o100644, st_size=0)
        with pytest.raises(c.ReceiptError, match="input"):
            c.check(root, manifest)


@pytest.mark.parametrize("path", c.INPUTS)
def test_each_required_input_missing(tmp_path, path):
    root, manifest = write_fixture(tmp_path, fixture())
    (root / path).unlink()
    with pytest.raises(c.ReceiptError, match="I/O failure"):
        c.check(root, manifest)


def test_permission_platform_and_traversal_failures(tmp_path):
    root, manifest = write_fixture(tmp_path, fixture())
    for exc, error in (
        (PermissionError(13, "private-path"), "I/O failure"),
        (NotImplementedError(), "unsupported schema/type"),
    ):
        with mock.patch.object(c.os, "open", side_effect=exc):
            with pytest.raises(c.ReceiptError, match=error):
                c.check(root, manifest)
    with pytest.raises(c.ReceiptError, match="traversal"):
        c.check(root, root / ".." / "manifest.json")


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("candidate_commit", True, "candidate"),
        ("scope", {}, "manifest scope"),
        ("schema_version", "future", "manifest schema"),
        ("artifacts", {}, "allowlist"),
        ("metadata_contracts", {}, "trusted metadata"),
        ("referenced_only", {}, "reference inventory"),
    ],
)
def test_manifest_boundaries(tmp_path, field, value, error):
    root, manifest = write_fixture(tmp_path, fixture())
    trust = json.loads(manifest.read_bytes())
    trust[field] = value
    manifest.write_bytes(encode(trust))
    with pytest.raises(c.ReceiptError, match=error):
        c.check(root, manifest)


def test_opaque_report_and_bad_artifact_json(tmp_path):
    root, manifest = write_fixture(tmp_path, fixture())
    (root / c.REPORT).write_bytes(b"changed")
    with pytest.raises(c.ReceiptError, match="input SHA-256"):
        c.check(root, manifest)
    for value, error in (([], "expected object"), ({}, "unsupported schema/type")):
        root, manifest = write_fixture(tmp_path, fixture())
        rewrite(root, manifest, c.AGGREGATE, lambda a: None)
        raw = encode(value)
        (root / c.AGGREGATE).write_bytes(raw)
        m = json.loads(manifest.read_bytes())
        m["artifacts"][c.AGGREGATE] = sha(raw)
        manifest.write_bytes(encode(m))
        with pytest.raises(c.ReceiptError, match=error):
            c.check(root, manifest)


@pytest.mark.parametrize(
    "path,field,value,error",
    [
        (c.FREEZE, ("identities", "protocol_sha256"), H, "trusted metadata"),
        (c.AGGREGATE, ("identities", "inputs"), H, "aggregate identity inputs"),
        (c.AGGREGATE, ("identities", "outcomes"), H, "aggregate identity outcomes"),
        (c.AGGREGATE, ("identities", "split"), H, "aggregate identity split"),
        (c.AGGREGATE, ("identities", "protocol"), H, "aggregate identity protocol"),
        (c.AGGREGATE, ("identities", "receipt"), H, "aggregate identity receipt"),
        (c.AGGREGATE, ("evaluator_sha256",), H, "code reference agreement"),
        (c.REVIEW, ("artifacts", c.REPORT), H, "review public artifact"),
        (c.REVIEW, ("artifacts", c.AGGREGATE), H, "review public artifact"),
        (c.REVIEW, ("private_original_aggregate_sha256",), H, "review original hash"),
    ],
)
def test_cross_file_bindings(tmp_path, path, field, value, error):
    root, manifest = write_fixture(tmp_path, fixture())
    rewrite(root, manifest, path, lambda d: set_path(d, field, value))
    with pytest.raises(c.ReceiptError, match=error):
        c.check(root, manifest)


def set_sparse_model(docs, name, measured, not_run=False):
    """Put all synthetic successes in middle GC; retain all attempted inputs."""
    a = docs[c.AGGREGATE]
    for label, (n, obs) in {
        "low": (31, 29),
        "middle": (303, 302),
        "high": (1, 1),
    }.items():
        successes = measured if label == "middle" else 0
        a["descriptive_coding_gc_strata"][label]["models"][name] = summary(
            n,
            obs,
            successes,
            successes,
            rho=0.3,
            not_run=n - successes if not_run else 0,
        )
    a["primary"]["models"][name] = summary(
        335, 332, measured, measured, rho=0.3, not_run=335 - measured if not_run else 0
    )


def unsupported_comparison(measured, blocks):
    result = comparison()
    result.update(
        n_common_success=measured,
        n_common_measured=measured,
        n_common_blocks=blocks,
        lost_reference_successes=335 - measured,
        rank_gain=None,
        attempted_draws=0,
        usable_draws=0,
        undefined_draws=0,
        interval95=None,
        interval_status="insufficient_support",
    )
    return result


@pytest.mark.parametrize(
    "status",
    [
        "insufficient_support",
        "undefined_point_correlation",
        "insufficient_usable_draws",
        "ok",
    ],
)
@pytest.mark.parametrize("corrupt", [False, True])
def test_interval_states_after_all_hash_chains_refreshed(tmp_path, status, corrupt):
    docs = fixture()
    a = docs[c.AGGREGATE]
    name = "control-constant"
    pair = a["descriptive_against_primary_reference"][name]
    if status == "insufficient_support":
        set_sparse_model(docs, name, 10)
        pair = unsupported_comparison(10, 10)
        a["descriptive_against_primary_reference"][name] = pair
    elif status == "undefined_point_correlation":
        a["primary"]["models"][name]["spearman_rho"] = None
        pair.update(
            rank_gain=None,
            interval95=None,
            attempted_draws=0,
            usable_draws=0,
            interval_status=status,
        )
    elif status == "insufficient_usable_draws":
        pair.update(
            usable_draws=9899,
            undefined_draws=101,
            interval95=None,
            interval_status=status,
        )
    else:
        # Exactly the acceptance threshold; the interval need not contain point.
        pair.update(usable_draws=9900, undefined_draws=100, interval95=[-0.9, -0.8])
    if corrupt:
        pair["interval_status"] = "unknown"
        with pytest.raises(c.ReceiptError, match="interval status"):
            c.check(*write_fixture(tmp_path, docs))
    else:
        assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"


@pytest.mark.parametrize("measured,blocks", [(0, 0), (29, 10), (30, 9), (30, 10)])
def test_support_thresholds_and_requested_versus_attempted(tmp_path, measured, blocks):
    docs = fixture()
    name = "control-constant"
    set_sparse_model(docs, name, measured)
    pair = unsupported_comparison(measured, blocks)
    if measured >= 30 and blocks >= 10:
        pair.update(
            rank_gain=0.1,
            interval_status="ok",
            attempted_draws=10000,
            usable_draws=10000,
            interval95=[0, 0.2],
        )
    docs[c.AGGREGATE]["descriptive_against_primary_reference"][name] = pair
    assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"
    pair["attempted_draws"] = 1
    pair["usable_draws"] = 1
    pair["interval_status"] = (
        "insufficient_usable_draws"
        if measured >= 30 and blocks >= 10
        else "insufficient_support"
    )
    pair["interval95"] = None
    with pytest.raises(c.ReceiptError, match="attempted draws"):
        c.check(*write_fixture(tmp_path, docs))


def test_runtime_empty_and_tiny_execution_boundaries():
    for n, obs, success, paired, not_run in (
        (0, 0, 0, 0, 0),
        (3, 2, 0, 0, 3),
        (3, 2, 1, 1, 2),
        (2, 2, 2, 2, 0),
    ):
        c.summary(summary(n, obs, success, paired, not_run=not_run))
    value = summary(2, 2)
    value["runtime_seconds"].update(sum=4, median=2, p95_nearest_rank=3, maximum=3)
    c.summary(value)
    # Nonnegative values and averaging the two middle times imply median2.
    value["runtime_seconds"]["median"] = 1
    with pytest.raises(c.ReceiptError, match="two-execution median"):
        c.summary(value)
    value = summary(3, 2, 0, 0, not_run=3)
    value["runtime_seconds"]["median"] = 0
    with pytest.raises(c.ReceiptError, match="empty runtime quantile"):
        c.summary(value)
    value = summary(0, 0)
    value["coverage"] = 0
    with pytest.raises(c.ReceiptError, match="empty coverage"):
        c.summary(value)


@pytest.mark.parametrize(
    "kind",
    [
        "incomplete",
        "integrity",
        "software",
        "coverage_and_loss",
        "null_gain",
        "null_interval",
        "thresholds",
        "all",
    ],
)
def test_gate_reasons_after_hash_refresh(tmp_path, kind):
    docs = fixture()
    a = docs[c.AGGREGATE]
    f = docs[c.FREEZE]
    p = a["primary"]
    pair = p["comparison"]
    expected = []
    if kind in ("incomplete", "all"):
        a["collection_complete"] = False
        expected.append("collection_incomplete")
    if kind == "integrity":
        a["artifacts_unchanged"] = False
        expected.append("collection_incomplete")
    if kind in ("software", "all"):
        f["software_resource_gates"]["complete"] = False
        expected.append("software_resource_gate_unmet")
    if kind in ("coverage_and_loss", "all"):
        set_sparse_model(docs, "joint_standby-linker3", 10)
        pair = unsupported_comparison(10, 10)
        p["comparison"] = pair
        for g in a["descriptive_coding_gc_strata"].values():
            count_ = g["models"]["joint_standby-linker3"]["n_paired"]
            g["primary_pair"].update(n_common_measured=count_, rank_gain=None)
        expected.extend(
            [
                "coverage_below_threshold",
                "lost_reference_successes",
                "rank_gain_below_threshold_or_undefined",
                "interval_not_above_zero_or_undefined",
            ]
        )
    if kind == "null_gain":
        p["models"]["joint_standby-linker3"]["spearman_rho"] = None
        pair.update(
            rank_gain=None,
            interval95=None,
            interval_status="undefined_point_correlation",
            attempted_draws=0,
            usable_draws=0,
        )
        expected.extend(
            [
                "rank_gain_below_threshold_or_undefined",
                "interval_not_above_zero_or_undefined",
            ]
        )
    if kind == "null_interval":
        pair.update(
            interval95=None,
            interval_status="insufficient_usable_draws",
            usable_draws=9899,
            undefined_draws=101,
        )
        expected.append("interval_not_above_zero_or_undefined")
    if kind == "thresholds":
        # Inclusive .05 point threshold and strict zero lower bound.
        p["models"]["joint_standby-linker3"]["spearman_rho"] = 0.25
        pair.update(rank_gain=0.05, interval95=[0, 0.1])
        expected.append("interval_not_above_zero_or_undefined")
    p["advancement"] = {"advance": not expected, "reasons": expected}
    audit = docs[c.REVIEW]["independent_recomputation"]
    audit.update(
        advance=not expected,
        primary_usable_draws=pair["usable_draws"],
        primary_undefined_draws=pair["undefined_draws"],
    )
    assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"
    p["advancement"]["reasons"] = (
        list(reversed(expected)) if len(expected) > 1 else ["wrong_reason"]
    )
    with pytest.raises(c.ReceiptError, match="advancement"):
        c.check(*write_fixture(tmp_path, docs))


def test_partial_equal_counts_do_not_establish_common_cohorts(tmp_path):
    docs = fixture()
    a = docs[c.AGGREGATE]
    # Equal marginal sizes331; public intersection330 does not identify equal sets.
    for name in ("standby2014-linker3", "joint_standby-linker3"):
        a["primary"]["models"][name] = summary(335, 332, 334, 331, rho=0.2)
        a["descriptive_coding_gc_strata"]["middle"]["models"][name] = summary(
            303, 302, 302, 301, rho=0.2
        )
    a["primary"]["comparison"].update(
        n_common_success=333,
        n_common_measured=330,
        lost_reference_successes=1,
        rank_gain=0.8,
    )
    for g in a["descriptive_coding_gc_strata"].values():
        g["primary_pair"]["rank_gain"] = (
            None if g["primary_pair"]["n_common_measured"] < 30 else 0.8
        )
    a["descriptive_coding_gc_strata"]["middle"]["primary_pair"]["n_common_measured"] = (
        300
    )
    for pair in a["descriptive_against_primary_reference"].values():
        pair.update(n_common_success=334, n_common_measured=331)
    a["primary"]["advancement"] = {
        "advance": False,
        "reasons": ["lost_reference_successes"],
    }
    docs[c.REVIEW]["independent_recomputation"]["advance"] = False
    assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"
    a["primary"]["comparison"]["n_common_measured"] = 329
    with pytest.raises(c.ReceiptError, match="measured subset"):
        c.check(*write_fixture(tmp_path, docs))


@pytest.mark.parametrize("value", [True, None, [], {}, "bad", "A" * 64, "a" * 63])
def test_invalid_hash_references(value):
    with pytest.raises(c.ReceiptError, match="invalid SHA-256"):
        c.sha(value)
    with pytest.raises(c.ReceiptError, match="invalid SHA-256"):
        c.references({"map_sha256": {"opaque": value}})


def test_hash_identity_and_schema_paths_after_trust_refresh(tmp_path):
    cases = [
        (c.FREEZE, ("schema_version",), "future", "freeze schema"),
        (c.PROTOCOL, ("schema_version",), "future", "protocol schema"),
        (c.REVIEW, ("schema_version",), "future", "review schema"),
        (c.AGGREGATE, ("schema_version",), "future", "aggregate schema"),
        (c.FREEZE, ("identities", "input_file_sha256"), H, "freeze input identity"),
        (c.AGGREGATE, ("identities", "collection"), True, "invalid SHA-256"),
        (c.FREEZE, ("software_resource_gates", "complete"), 1, "software gate"),
        (c.FREEZE, ("panels", "Cambray2018", "seed_blocks"), 55, "frozen blocks"),
    ]
    for doc, path, value, error in cases:
        docs = fixture()
        set_path(docs[doc], path, value)
        with pytest.raises(c.ReceiptError, match=error):
            c.check(*write_fixture(tmp_path, docs))


def test_recovery_binding_does_not_sort_or_remove_other_fields(tmp_path):
    root, manifest = write_fixture(tmp_path, fixture())
    a = json.loads((root / c.AGGREGATE).read_bytes())
    a["publication_context"]["original_evaluator_aggregate_sha256"] = H
    raw = encode(a)
    (root / c.AGGREGATE).write_bytes(raw)
    r = json.loads((root / c.REVIEW).read_bytes())
    r["artifacts"][c.AGGREGATE] = sha(raw)
    (root / c.REVIEW).write_bytes(encode(r))
    m = json.loads(manifest.read_bytes())
    m["artifacts"].update({c.AGGREGATE: sha(raw), c.REVIEW: sha(encode(r))})
    manifest.write_bytes(encode(m))
    with pytest.raises(c.ReceiptError, match="recovered aggregate hash"):
        c.check(root, manifest)


def test_strict_key_unicode_and_counts():
    with pytest.raises(c.ReceiptError, match="JSON"):
        c.parse(b'{"\\ud800":1}')
    for value in (True, "1", None, float("nan"), float("inf")):
        with pytest.raises(c.ReceiptError, match="finite number"):
            c.number(value, "test")
    for value in (-1, True, 1.0, 10**12 + 1):
        with pytest.raises(c.ReceiptError, match="integer"):
            c.count(value, "test")
    for counts in ([], {"": 1}, {"x": 0}):
        with pytest.raises(c.ReceiptError):
            c.frequencies(counts, 1, "test")


@pytest.mark.parametrize("complete", [True, False])
def test_unexecuted_requests_retained_in_public_accounting(tmp_path, complete):
    docs = fixture()
    a = docs[c.AGGREGATE]
    name = "control-constant"
    set_sparse_model(docs, name, 0, not_run=True)
    a["descriptive_against_primary_reference"][name] = unsupported_comparison(0, 0)
    a["collection_complete"] = complete
    a["primary"]["advancement"] = {
        "advance": complete,
        "reasons": [] if complete else ["collection_incomplete"],
    }
    docs[c.REVIEW]["independent_recomputation"]["advance"] = complete
    if complete:
        with pytest.raises(
            c.ReceiptError, match="complete collection contains not_run"
        ):
            c.check(*write_fixture(tmp_path, docs))
    else:
        assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"


@pytest.mark.parametrize("status", sorted(c.STATUSES - {"ok", "not_run"}))
def test_all_published_failure_statuses(tmp_path, status):
    docs = fixture()
    name = "control-constant"
    set_sparse_model(docs, name, 10)
    a = docs[c.AGGREGATE]
    for panel in (a["primary"], *a["descriptive_coding_gc_strata"].values()):
        counts = panel["models"][name]["status_counts"]
        counts[status] = counts.pop("failed")
    a["descriptive_against_primary_reference"][name] = unsupported_comparison(10, 10)
    assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"


@pytest.mark.parametrize("path", [c.PROTOCOL, c.FREEZE, c.AGGREGATE, c.REVIEW])
@pytest.mark.parametrize("data", [b"\xff", b'{"a":1,"a":2}', b'{"n":1e999}'])
def test_malformed_artifact_json_through_public_api(tmp_path, path, data):
    root, manifest = write_fixture(tmp_path, fixture())
    (root / path).write_bytes(data)
    m = json.loads(manifest.read_bytes())
    m["artifacts"][path] = sha(data)
    manifest.write_bytes(encode(m))
    with pytest.raises(c.ReceiptError, match="JSON"):
        c.check(root, manifest)


def test_all_known_real_digest_locations_are_inventoried():
    result = c.check(ROOT, MANIFEST)
    refs = result["referenced_only"]["artifacts"]
    assert {p: len(rows) for p, rows in refs.items()} == {
        c.PROTOCOL: 4,
        c.FREEZE: 53,
        c.AGGREGATE: 8,
        c.REVIEW: 4,
    }
    assert {
        "location": ["configurations", 6, "command", 7],
        "sha256": "5af48fafd7b8bb5c992c26a06b928da5e8a31c3594e96d108a66f0c4777edf2b",
    } in refs[c.FREEZE]

    # An independent audit of every digest-valued string catches positional fields.
    def locations(value, pointer=()):
        if isinstance(value, dict):
            return [p for k, v in value.items() for p in locations(v, (*pointer, k))]
        if isinstance(value, list):
            return [p for i, v in enumerate(value) for p in locations(v, (*pointer, i))]
        return (
            [pointer]
            if isinstance(value, str)
            and len(value) == 64
            and set(value) <= set("0123456789abcdef")
            else []
        )

    checked = {
        c.PROTOCOL: set(),
        c.FREEZE: {("identities", "protocol_sha256")},
        c.AGGREGATE: {("identities", "protocol")},
        c.REVIEW: {("artifacts", c.REPORT), ("artifacts", c.AGGREGATE)},
    }
    for path, rows in refs.items():
        assert (
            set(locations(json.loads((ROOT / path).read_bytes())))
            == {tuple(r["location"]) for r in rows} | checked[path]
        )


@pytest.mark.parametrize("kind", ["aggregate_collection", "review_external_artifact"])
def test_malformed_scalar_hash_cannot_be_omitted(tmp_path, kind):
    docs = fixture()
    if kind == "aggregate_collection":
        set_path(docs[c.AGGREGATE], ("identities", "collection"), True)
        with pytest.raises(c.ReceiptError, match="invalid SHA-256"):
            c.check(*write_fixture(tmp_path, docs))
    else:
        root, manifest = write_fixture(tmp_path, docs)
        rewrite(
            root,
            manifest,
            c.REVIEW,
            lambda r: r["artifacts"].update(
                {"docs/validation/rbs-new-evaluation-data.md": True}
            ),
        )
        with pytest.raises(c.ReceiptError, match="invalid SHA-256"):
            c.check(root, manifest)


@pytest.mark.parametrize("measured", [60, 70])
def test_observed_unobserved_feasibility_exact_coordinator_example(measured):
    protocol = fixture()[c.PROTOCOL]
    left = summary(100, 80, 80, 60)
    right = summary(100, 80, 80, 80)
    pair = comparison(100, measured)
    pair.update(n_common_success=70, lost_reference_successes=10)
    # The supplied formula makes this entire example infeasible: M<=Pl60,
    # but zero right unobserved successes require M=S70.
    with pytest.raises(c.ReceiptError, match="observed/unobserved intersection"):
        c.comparison(pair, left, right, protocol)


def test_stratified_count_negative_after_all_hashes_refreshed(tmp_path):
    docs = fixture()
    p = docs[c.AGGREGATE]["primary"]
    p["models"]["standby2014-linker3"] = summary(335, 332, 320, 317)
    p["models"]["joint_standby-linker3"] = summary(335, 332, 320, 320)
    # All earlier marginal constraints allow M307. No unobserved right successes
    # means every one of the310 shared successes must be measured.
    p["comparison"].update(
        n_common_success=310, n_common_measured=307, lost_reference_successes=10
    )
    with pytest.raises(c.ReceiptError, match="observed/unobserved intersection"):
        c.check(*write_fixture(tmp_path, docs))


@pytest.mark.parametrize(
    "section,field,value,error",
    [
        ("bootstrap", "draws", True, "integer"),
        ("bootstrap", "minimum_usable_draws", 9900.0, "integer"),
        ("bootstrap", "minimum_common_rows", 29, "frozen bootstrap setting"),
        ("bootstrap", "minimum_common_blocks", 9, "frozen bootstrap setting"),
        ("advancement", "minimum_coverage", True, "finite number"),
        ("advancement", "minimum_rank_gain", 0.04, "frozen gate threshold"),
        ("advancement", "lost_baseline_successes_allowed", True, "integer"),
        ("primary_endpoint", "n_inputs", True, "integer"),
    ],
)
def test_frozen_numerical_settings_after_trust_refresh(
    tmp_path, section, field, value, error
):
    docs = fixture()
    docs[c.PROTOCOL][section][field] = value
    with pytest.raises(c.ReceiptError, match=error):
        c.check(*write_fixture(tmp_path, docs))


@pytest.mark.parametrize(
    "paired_left,paired_right,measured,valid",
    [(70, 80, 70, True), (60, 60, 50, True), (60, 60, 60, False)],
)
def test_both_stratified_intersection_bounds(
    paired_left, paired_right, measured, valid
):
    left = summary(100, 80, 80, paired_left)
    right = summary(100, 80, 80, paired_right)
    pair = comparison(100, measured)
    pair.update(
        n_common_success=70,
        lost_reference_successes=10,
        n_common_blocks=min(56, measured),
    )
    if valid:
        c.comparison(pair, left, right, fixture()[c.PROTOCOL])
    else:
        with pytest.raises(c.ReceiptError, match="observed/unobserved intersection"):
            c.comparison(pair, left, right, fixture()[c.PROTOCOL])


@pytest.mark.parametrize("blocks", [1, 52])
def test_impossible_common_block_count_after_hash_refresh(tmp_path, blocks):
    docs = fixture()
    primary = docs[c.AGGREGATE]["primary"]
    pair = primary["comparison"]
    pair["n_common_blocks"] = blocks
    if blocks == 1:
        pair.update(
            rank_gain=None,
            attempted_draws=0,
            usable_draws=0,
            undefined_draws=0,
            interval95=None,
            interval_status="insufficient_support",
        )
        primary["advancement"] = {
            "advance": False,
            "reasons": [
                "rank_gain_below_threshold_or_undefined",
                "interval_not_above_zero_or_undefined",
            ],
        }
        docs[c.REVIEW]["independent_recomputation"].update(
            primary_usable_draws=0, advance=False
        )
    # At most three of the 56 nonempty input blocks can lack any of 332
    # measured rows among 335 inputs. A count below 53 cannot be realized.
    with pytest.raises(c.ReceiptError, match="comparison: common blocks"):
        c.check(*write_fixture(tmp_path, docs))


def test_identical_complete_cohorts_require_same_block_count(tmp_path):
    docs = fixture()
    docs[c.AGGREGATE]["primary"]["comparison"]["n_common_blocks"] = 54
    # Both 54 and 56 are individually feasible; they cannot describe the same
    # complete observed cohort in two comparisons over the same grouping.
    with pytest.raises(c.ReceiptError, match="complete measured cohort blocks"):
        c.check(*write_fixture(tmp_path, docs))


def test_common_block_lower_boundary_is_feasible(tmp_path):
    docs = fixture()
    a = docs[c.AGGREGATE]
    for pair in (
        a["primary"]["comparison"],
        *a["descriptive_against_primary_reference"].values(),
    ):
        pair["n_common_blocks"] = 53
    assert c.check(*write_fixture(tmp_path, docs))["status"] == "consistent"


@pytest.mark.parametrize("low_common,valid", [(27, False), (28, True)])
def test_gc_common_measured_partition_after_hash_refresh(tmp_path, low_common, valid):
    docs = fixture()
    a = docs[c.AGGREGATE]
    primary = a["primary"]
    strata = a["descriptive_coding_gc_strata"]
    for name in ("standby2014-linker3", "joint_standby-linker3"):
        rho = 0.2 if name == "standby2014-linker3" else 0.3
        primary["models"][name] = summary(335, 332, 333, 330, rho=rho)
        strata["low"]["models"][name] = summary(31, 29, 30, 28, rho=rho)
        strata["middle"]["models"][name] = summary(303, 302, 302, 301, rho=rho)
    primary["comparison"].update(
        n_common_success=332, n_common_measured=329, lost_reference_successes=1
    )
    primary["advancement"] = {
        "advance": False,
        "reasons": ["lost_reference_successes"],
    }
    docs[c.REVIEW]["independent_recomputation"]["advance"] = False
    for pair in a["descriptive_against_primary_reference"].values():
        pair.update(n_common_success=333, n_common_measured=330)
    strata["low"]["primary_pair"]["n_common_measured"] = low_common
    strata["middle"]["primary_pair"]["n_common_measured"] = 300
    # Per-model counts and each paired intersection are feasible in both cases;
    # only 28+300+1 partitions the primary 329 common measured rows.
    args = write_fixture(tmp_path, docs)
    if valid:
        assert c.check(*args)["status"] == "consistent"
    else:
        with pytest.raises(c.ReceiptError, match="GC partition common measured"):
            c.check(*args)


@pytest.mark.parametrize("success,coverage", [(335, 1 + 5e-13), (0, -1e-16)])
def test_coverage_range_is_strict_despite_arithmetic_tolerance(success, coverage):
    row = summary(success=success, paired=332 if success else 0)
    row["coverage"] = coverage
    with pytest.raises(c.ReceiptError, match="coverage: bounds"):
        c.summary(row)


def test_runtime_sum_cannot_be_negative_within_roundoff_allowance():
    row = summary(1, 1)
    row["runtime_seconds"].update(sum=-1e-13, median=0, p95_nearest_rank=0, maximum=0)
    with pytest.raises(c.ReceiptError, match="runtime: negative sum"):
        c.summary(row)
