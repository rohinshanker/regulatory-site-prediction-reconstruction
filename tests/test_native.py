"""Native source boundary, independent B mappings, missingness and real scoring."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_rbs import AlgebraBackend

from regsite import native
from regsite.native import Genome, UnsupportedContext, predict_native, prepare_context
from regsite.sequence import InputError, sequence_hash

EXAMPLE = json.loads(Path("benchmarks/rbs/native-input-example.json").read_text())
FIXTURES = json.loads(
    Path("benchmarks/rbs/native-coordinate-fixtures.json").read_text()
)


def inputs(index=0):
    record = deepcopy(EXAMPLE["records"][index])
    genome = Genome.from_dict(EXAMPLE["genomes"][record["genome_id"]])
    return record, genome


def test_independently_prepared_coordinates_and_context():
    for record, expected in zip(EXAMPLE["records"], FIXTURES["records"], strict=True):
        genome = Genome.from_dict(EXAMPLE["genomes"][record["genome_id"]])
        if expected["expected_sequence"] is None:
            with pytest.raises(UnsupportedContext, match="tss_inside_current_cds"):
                prepare_context(record, genome)
            continue
        context = prepare_context(record, genome)
        result = context.describe()
        assert context.sequence == expected["expected_sequence"].replace("T", "U")
        assert context.start == expected["expected_start"]
        assert [[p["start"], p["end"]] for p in result["genomic_segments"]] == expected[
            "expected_segments"
        ]
        assert [[p["start"], p["end"]] for p in result["genomic_start_segments"]] == [
            expected["expected_start_interval"]
        ]
        assert context.request["anti_sd"] == "ACCUCCUUA"
        assert result["genome"]["sequence_sha256"] == genome.sha256
        assert result["sequence_sha256"] == sequence_hash(context.sequence)
        assert result["path"]["circular"] == (expected["topology"] == "circular")


def test_unmeasured_flank_clipping_and_preserved_evidence():
    record, genome = inputs()
    record.update(tss_zero_based=None, leader_length_nt=None, downstream_length_nt=100)
    result = prepare_context(record, genome)
    assert result.start == 7
    assert result.sequence == genome.rna
    assert {
        "unmeasured_transcript_context_assumed_genomic_flank",
        "leader_clipped_by_context_limit_or_contig_boundary",
        "downstream_context_clipped_at_contig_boundary",
    } <= set(result.warnings)
    reverse, rev_genome = inputs(1)
    reverse.update(tss_zero_based=None, leader_length_nt=None, downstream_length_nt=100)
    assert prepare_context(reverse, rev_genome).sequence == result.sequence
    record.update(source_current_start_delta_nt=3, source_flags=["disagreement"])
    batch = dict(EXAMPLE, records=[record])
    output = predict_native(batch, AlgebraBackend(paired=0))
    assert output["results"][0]["evidence"]["source_flags"] == ["disagreement"]
    output["results"][0]["evidence"]["source_flags"].clear()
    assert record["source_flags"] == ["disagreement"]


@pytest.mark.parametrize(
    "change",
    [
        {"id": None},
        {"id": ""},
        {"id": "x" * 129},
        {"id": "bad\n"},
        {"genome_id": ""},
        {"host": None},
        {"mapping_status": None},
        {"transcript_start_evidence": None},
        {"translation_start_evidence": None},
        {"anti_sd_provenance": None},
        {"conditions": None},
        {"warnings": None},
        {"warnings": [1]},
        {"assembly": "wrong"},
        {"annotation": "wrong"},
        {"replicon": "wrong"},
        {"genome_sha256": "wrong"},
        {"strand": "?"},
        {"origin_crossing": 1},
        {"origin_crossing": True},
        {"upstream_limit_nt": -1},
        {"downstream_length_nt": 2},
        {"upstream_limit_nt": True},
        {"downstream_length_nt": 101},
        {"tss_zero_based": True},
        {"cds_start_zero_based": 20},
        {"leader_length_nt": 5},
        {"leader_length_nt": False},
        {"tss_zero_based": None, "leader_length_nt": 4},
        {"anti_sd": "bad"},
        {"temperature_c": float("nan")},
    ],
)
def test_invalid_record_contract(change):
    record, genome = inputs()
    with pytest.raises(InputError):
        prepare_context(dict(record, **change), genome)


def test_missing_and_unsupported_contexts():
    record, genome = inputs()
    with pytest.raises(InputError, match="object"):
        prepare_context(None, genome)
    for key in ("tss_zero_based", "cds_start_zero_based", "leader_length_nt"):
        missing = dict(record)
        del missing[key]
        with pytest.raises(InputError, match="missing explicit"):
            prepare_context(missing, genome)
    with pytest.raises(UnsupportedContext, match="unresolved"):
        prepare_context(dict(record, cds_start_zero_based=None), genome)
    with pytest.raises(UnsupportedContext, match="boundary"):
        prepare_context(
            dict(record, cds_start_zero_based=19, leader_length_nt=16), genome
        )
    record, genome = inputs(2)
    with pytest.raises(InputError, match="more than once"):
        prepare_context(dict(record, downstream_length_nt=100), genome)
    with pytest.raises(InputError, match="disagrees"):
        prepare_context(dict(record, tss_zero_based=8, leader_length_nt=-1), genome)


@pytest.mark.parametrize(
    "change",
    [
        {"sequence": None},
        {"sequence": ""},
        {"sequence": "acgt"},
        {"sequence": "ACGU"},
        {"sequence": "ACNT"},
        {"sequence_sha256": "0" * 64},
        {"topology": None},
        {"accession": None},
        {"assembly": None},
        {"annotation": None},
    ],
)
def test_invalid_genome_contract(change):
    source = next(iter(EXAMPLE["genomes"].values()))
    with pytest.raises(InputError):
        Genome.from_dict(dict(source, **change))


def test_genome_requires_object():
    with pytest.raises(InputError, match="object"):
        Genome.from_dict([])


def test_native_resource_limits():
    batch = deepcopy(EXAMPLE)
    batch["genomes"]["oversized"] = {"sequence": "A" * 20_000_001}
    with pytest.raises(InputError, match="total genome"):
        predict_native(batch, AlgebraBackend())
    with pytest.raises(InputError, match="encoded bytes"):
        predict_native(dict(EXAMPLE, extra="x" * 40_000_000), AlgebraBackend())


def test_batch_missingness_duplicate_unknown_and_invalid_genomes():
    batch = deepcopy(EXAMPLE)
    batch["records"] += [
        None,
        dict(batch["records"][0]),
        dict(batch["records"][0], id="unknown", genome_id="absent"),
    ]
    batch["genomes"]["bad"] = {}
    batch["records"].append(dict(batch["records"][0], id="bad-genome", genome_id="bad"))
    result = predict_native(batch, AlgebraBackend(paired=0))
    rows = result["results"]
    assert rows[0]["status"] == "ok"
    assert rows[5]["status"] == rows[6]["status"] == "unsupported"
    assert rows[6]["prediction"] is None
    assert [r["status"] for r in rows[7:]] == ["invalid_input"] * 4
    assert "duplicate" in rows[8]["reason"]
    assert rows[7]["id"] is None
    projected = rows[1]["genomic_sites"][0]
    assert projected["start_point"] == 12
    assert projected["start_codon"] == [{"start": 10, "end": 13, "strand": "-"}]
    assert projected["rank_among_successful_candidates"] == 1
    assert rows[5]["genomic_sites"][0]["rank_among_successful_candidates"] is None
    assert rows[0]["prediction"]["schema_version"] == "1.1"
    assert (
        result["batch_id"]
        == predict_native(batch, AlgebraBackend(paired=0))["batch_id"]
    )
    assert (
        result["batch_id"]
        != predict_native(batch, AlgebraBackend(paired=0), profile="historical")[
            "batch_id"
        ]
    )


def test_conditional_scan_and_failure_projection():
    batch = dict(EXAMPLE, records=EXAMPLE["records"][:1])
    result = predict_native(batch, AlgebraBackend(paired=0), mode="conditional_scan")
    assert "not genome discovery" in result["task_scope"]
    assert result["results"][0]["prediction"]["input"]["start_positions"] is None
    result = predict_native(batch, AlgebraBackend(fail=True))
    assert result["results"][0]["status"] == "failed"
    assert result["results"][0]["genomic_sites"][0]["binding_interval"] is None


def test_total_batch_budget_expiry(monkeypatch):
    clock = iter((0.0, 301.0, 302.0))
    monkeypatch.setattr(native.time, "monotonic", lambda: next(clock))
    result = predict_native(
        dict(EXAMPLE, records=EXAMPLE["records"][:2]), AlgebraBackend()
    )
    assert all(
        r["reason"] == "native_batch_time_budget_exhausted" for r in result["results"]
    )
    assert all(r["context"] and r["prediction"] is None for r in result["results"])


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        dict(EXAMPLE, records=[]),
        dict(EXAMPLE, records=None),
        dict(EXAMPLE, records=[None] * 10001),
        dict(EXAMPLE, genomes={}),
        dict(EXAMPLE, genomes=[]),
        dict(EXAMPLE, genomes={str(i): {} for i in range(101)}),
        dict(EXAMPLE, genomes={"": {}}),
        dict(EXAMPLE, extra=float("nan")),
        dict(EXAMPLE, extra={1, 2}),
    ],
)
def test_invalid_batch_setup(value):
    with pytest.raises(InputError):
        predict_native(value, AlgebraBackend())


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "genome_discovery"},
        {"seconds_per_record": True},
        {"seconds_per_record": 121},
        {"seconds_per_batch": 0},
        {"seconds_per_batch": 3601},
        {"seconds_per_batch": float("nan")},
    ],
)
def test_invalid_execution_policy(changes):
    with pytest.raises(InputError):
        predict_native(EXAMPLE, AlgebraBackend(), **changes)


def test_real_native_fixture_batch(real_backend):
    result = predict_native(EXAMPLE, real_backend)
    assert len(result["results"]) == 7
    assert result["results"][5]["status"] == "unsupported"
    assert result["results"][6]["status"] == "unsupported"
    assert all(
        r["status"] in ("ok", "no_candidate", "unsupported") for r in result["results"]
    )
    plus, minus = result["results"][:2]
    assert (
        plus["prediction"]["sites"][0]["energies"]
        == minus["prediction"]["sites"][0]["energies"]
    )
