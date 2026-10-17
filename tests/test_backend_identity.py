"""The repaired executable installation cannot silently identify as upstream."""

import json
from pathlib import Path

import pytest
from test_rbs import AlgebraBackend, request

from regsite import backend
from regsite.rbs import predict
from regsite.sequence import reverse_complement
from regsite.structures import BackendError


@pytest.fixture(params=[backend.TRACEBACK_COMPONENT, backend.LINKER_COMPONENT])
def installation(tmp_path, monkeypatch, request):
    component = request.param
    patch_hash, source_hash = backend.PATCHED_COMPONENTS[component]
    tables = json.loads(Path("src/regsite/data/rnastructure-tables.json").read_text())
    binaries = {name: name + "-digest" for name in ("Fold", "bifold", "efn2")}
    receipt = {
        "component": component,
        "license": "GPL-2.0-only",
        "source_archive_sha256": backend.SOURCE_SHA256,
        "patch_sha256": patch_hash,
        "patched_source_sha256": source_hash,
        "executable_sha256": binaries,
        "table_sha256": tables,
    }
    hashes = dict(tables, **binaries, **{"algorithm.cpp": source_hash})
    monkeypatch.setattr(backend, "_sha256", lambda path: hashes[path.name])
    monkeypatch.setattr(backend, "_run", lambda *args: "Version 6.6 (test)")
    return tmp_path, receipt, hashes


def test_verified_receipt_is_explicit_and_changes_prediction_identity(installation):
    root, receipt, _ = installation
    original = backend.RnaStructure.open(root)
    assert "variant" not in original.identity
    (root / "traceback-build.json").write_text(json.dumps(receipt))
    patched = backend.RnaStructure.open(root)
    assert patched.identity["variant"] == receipt["component"]
    assert (
        patched.identity["build_provenance"]["patch_sha256"] == receipt["patch_sha256"]
    )
    assert len(patched.identity["build_receipt_sha256"]) == 64
    old = AlgebraBackend()
    old.identity = original.identity
    new = AlgebraBackend()
    new.identity = patched.identity
    a, b = predict(request(), old), predict(request(), new)
    assert a["prediction_id"] != b["prediction_id"]
    assert a["sites"] == b["sites"]  # Identity alone does not silently alter equations.
    assert "patched_traceback_changes_candidate_search_results" in b["warnings"]


@pytest.mark.parametrize(
    "field",
    [
        "component",
        "license",
        "source_archive_sha256",
        "patch_sha256",
        "patched_source_sha256",
        "executable_sha256",
    ],
)
def test_mismatched_receipt_fields_fail_before_admission(installation, field):
    root, receipt, _ = installation
    receipt[field] = "different"
    (root / "traceback-build.json").write_text(json.dumps(receipt))
    with pytest.raises(BackendError, match="identity/hash mismatch"):
        backend.RnaStructure.open(root)


@pytest.mark.parametrize("text", ["[]", "null", "{", "\ud800", "x" * 500_001])
def test_malformed_receipts_never_fall_back_to_upstream(installation, text):
    root, _, _ = installation
    (root / "traceback-build.json").write_bytes(
        text.encode("utf-8", errors="surrogatepass")
    )
    with pytest.raises(BackendError, match="build receipt"):
        backend.RnaStructure.open(root)


def test_receipt_table_and_source_integrity(installation):
    root, receipt, hashes = installation
    path = root / "traceback-build.json"
    original_tables = receipt["table_sha256"]
    for bad in (None, {}):
        receipt["table_sha256"] = bad
        path.write_text(json.dumps(receipt))
        with pytest.raises(BackendError, match="table mismatch"):
            backend.RnaStructure.open(root)
    receipt["table_sha256"] = original_tables
    path.write_text(json.dumps(receipt))
    hashes["algorithm.cpp"] = "changed-source"
    with pytest.raises(BackendError, match="patched source"):
        backend.RnaStructure.open(root)
    path.unlink()
    path.mkdir()
    with pytest.raises(BackendError, match="unreadable"):
        backend.RnaStructure.open(root)


@pytest.mark.parametrize("case", ["karlsen2018:SGL_RS10810", "karlsen2018:sll0085"])
@pytest.mark.parametrize("profile", ["context2017", "standby2014", "joint_standby"])
def test_known_development_failures_are_repaired_without_dropping_states(
    real_backend, case, profile
):
    # Read only public development sequence/settings, never experimental labels.
    records = json.loads(
        Path("benchmarks/rbs/karlsen2018-development.json").read_text()
    )["records"]
    row = next(record for record in records if record["id"] == case)
    result = predict(
        {
            "id": case,
            "sequence": row["sequence"],
            "start_positions": [row["start"]],
            "anti_sd": "ACCUCCUUU",
            "temperature_c": 30,
        },
        real_backend,
        profile=profile,
    )
    site = result["sites"][0]
    if real_backend.identity.get("variant"):
        assert site["status"] == result["status"] == "ok"
        assert site["candidate_search"]["returned"] == 100
        assert site["tir"] > 0
    else:
        assert site["status"] == result["status"] == "failed"
        assert site["tir"] is None and site["energies"] is None
        assert any(word in site["reason"] for word in ("reciprocal", "missing"))


@pytest.mark.parametrize("profile", ["context2017", "standby2014", "joint_standby"])
@pytest.mark.parametrize("strand", ["+", "-"])
def test_ordinary_w_failure_requires_the_explicit_linker_repair(
    real_backend, profile, strand
):
    # Independent review seed 484/index 17; no assay measurements were used.
    # Original and traceback-2 exit zero without CT; only linker-3 repairs this.
    leader = "GGAGGGUAUAACAGUGAGUCACCUGAGGUGGUAAGGUUUGGAUAACUGCGUCUUAGCAGU"
    sequence = leader + "AUG" + "A" * 35
    result = predict(
        {
            "id": "synthetic-ordinary-w-linker-failure",
            "sequence": sequence if strand == "+" else reverse_complement(sequence),
            "strand": strand,
            "start_positions": [len(leader)],
            "anti_sd": "ACCUCCUUU",
            "temperature_c": 30,
        },
        real_backend,
        profile=profile,
    )
    site = result["sites"][0]
    if real_backend.identity.get("variant") == backend.LINKER_COMPONENT:
        assert result["status"] == site["status"] == "ok"
        assert site["candidate_search"]["returned"] == 100
        assert site["tir"] > 0 and site["energies"] is not None
        if profile == "joint_standby":
            assert site["joint_search"]["complete"]
    else:
        assert result["status"] == site["status"] == "failed"
        assert site["tir"] is None and site["energies"] is None
        assert "missing" in site["reason"]


@pytest.mark.parametrize("component", [None, True, 3, [], {}, "unknown"])
def test_unknown_component_types_fail_closed(installation, component):
    root, receipt, _ = installation
    receipt["component"] = component
    (root / "traceback-build.json").write_text(json.dumps(receipt))
    with pytest.raises(BackendError, match="identity/hash mismatch"):
        backend.RnaStructure.open(root)


def test_component_name_cannot_relabel_another_patch(installation):
    root, receipt, _ = installation
    receipt["component"] = next(
        component
        for component in backend.PATCHED_COMPONENTS
        if component != receipt["component"]
    )
    (root / "traceback-build.json").write_text(json.dumps(receipt))
    with pytest.raises(BackendError, match="identity/hash mismatch"):
        backend.RnaStructure.open(root)


@pytest.mark.parametrize(
    ("component", "manifest"),
    [
        ("rnastructure-6.6-traceback-2", "manifest.json"),
        ("rnastructure-6.6-linker-3", "manifest-linker-3.json"),
    ],
)
def test_runtime_pins_match_the_separate_component(component, manifest):
    source = json.loads((Path("backends/rnastructure66") / manifest).read_text())
    assert source["component"] == component
    assert source["license"] == "GPL-2.0-only"
    assert source["upstream"]["archive_sha256"] == backend.SOURCE_SHA256
    assert source["upstream"]["source_sha256"] == backend.UPSTREAM_SOURCE_SHA256
    assert backend.PATCHED_COMPONENTS[component] == (
        source["patch"]["sha256"],
        source["patch"]["patched_source_sha256"],
    )


@pytest.mark.parametrize("source_kind", ["upstream", "patched", "unknown"])
def test_receiptless_source_cannot_hide_a_patch(installation, source_kind):
    root, _, hashes = installation
    source = root / "src/algorithm.cpp"
    source.parent.mkdir()
    source.touch()
    if source_kind == "upstream":
        hashes["algorithm.cpp"] = backend.UPSTREAM_SOURCE_SHA256
        assert "variant" not in backend.RnaStructure.open(root).identity
    else:
        if source_kind == "unknown":
            hashes["algorithm.cpp"] = "unknown-source"
        with pytest.raises(BackendError, match="requires a recognized build receipt"):
            backend.RnaStructure.open(root)


def test_unreadable_receiptless_source_is_an_installation_failure(
    installation, monkeypatch
):
    root, _, hashes = installation
    source = root / "src/algorithm.cpp"
    source.parent.mkdir()
    source.touch()

    def unreadable(path):
        if path == source:
            raise PermissionError("source unavailable")
        return hashes[path.name]

    monkeypatch.setattr(backend, "_sha256", unreadable)
    with pytest.raises(BackendError, match="installation is incomplete"):
        backend.RnaStructure.open(root)
