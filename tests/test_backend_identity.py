"""The repaired executable installation cannot silently identify as upstream."""

import json
from pathlib import Path

import pytest
from test_rbs import AlgebraBackend, request

from regsite import backend
from regsite.rbs import predict
from regsite.sequence import reverse_complement
from regsite.structures import BackendError


@pytest.fixture
def installation(tmp_path, monkeypatch):
    tables = json.loads(Path("src/regsite/data/rnastructure-tables.json").read_text())
    binaries = {name: name + "-digest" for name in ("Fold", "bifold", "efn2")}
    receipt = {
        "component": backend.TRACEBACK_COMPONENT,
        "license": "GPL-2.0-only",
        "source_archive_sha256": backend.SOURCE_SHA256,
        "patch_sha256": backend.TRACEBACK_PATCH_SHA256,
        "patched_source_sha256": backend.TRACEBACK_SOURCE_SHA256,
        "executable_sha256": binaries,
        "table_sha256": tables,
    }
    hashes = dict(
        tables, **binaries, **{"algorithm.cpp": backend.TRACEBACK_SOURCE_SHA256}
    )
    monkeypatch.setattr(backend, "_sha256", lambda path: hashes[path.name])
    monkeypatch.setattr(backend, "_run", lambda *args: "Version 6.6 (test)")
    return tmp_path, receipt, hashes


def test_verified_receipt_is_explicit_and_changes_prediction_identity(installation):
    root, receipt, _ = installation
    original = backend.RnaStructure.open(root)
    assert "variant" not in original.identity
    (root / "traceback-build.json").write_text(json.dumps(receipt))
    patched = backend.RnaStructure.open(root)
    assert patched.identity["variant"] == "rnastructure-6.6-traceback-2"
    assert (
        patched.identity["build_provenance"]["patch_sha256"]
        == backend.TRACEBACK_PATCH_SHA256
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
@pytest.mark.parametrize("profile", ["context2017", "standby2014"])
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


@pytest.mark.parametrize("profile", ["context2017", "standby2014"])
@pytest.mark.parametrize("strand", ["+", "-"])
def test_unrepaired_ordinary_w_failure_never_becomes_a_prediction(
    real_backend, profile, strand
):
    # Independent review seed 484/index 17; no assay measurements were used.
    # Original and repaired engines both exit zero without writing a CT here.
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
    assert result["status"] == "failed"
    site = result["sites"][0]
    assert site["status"] == "failed"
    assert site["tir"] is None and site["energies"] is None
    assert "missing" in site["reason"]
