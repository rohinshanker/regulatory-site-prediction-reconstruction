"""Native JSON/GFF3 round trips, origin coordinates, and executable CLI paths."""

import io
import json
import sys
from copy import deepcopy
from urllib.parse import unquote

import pytest
from test_native_runtime import EXAMPLE
from test_rbs import AlgebraBackend

from regsite import native_io
from regsite.backend import RnaStructure
from regsite.native import predict_native
from regsite.native_cli import main
from regsite.native_io import gff_bounds, load_native, write_gff3
from regsite.sequence import InputError, sequence_hash
from regsite.structures import BackendError


def test_bounded_strict_json(monkeypatch):
    assert load_native(io.StringIO(json.dumps(EXAMPLE))) == EXAMPLE
    for text in ('{"a":1,"a":2}', '{"bad":NaN}', "[", "[" * 2000):
        with pytest.raises(InputError, match="JSON"):
            load_native(io.StringIO(text))
    monkeypatch.setattr(native_io, "MAX_NATIVE_CHARACTERS", 10)
    with pytest.raises(InputError, match="exceeds"):
        load_native(io.StringIO(" " * 11))


def test_named_gff_coordinate_transform():
    assert gff_bounds([], 20) is None
    assert gff_bounds([{"start": 7, "end": 10}], 20) == (8, 10)
    assert gff_bounds([{"start": 19, "end": 20}, {"start": 0, "end": 2}], 20) == (
        20,
        22,
    )
    assert gff_bounds([{"start": 0, "end": 1}, {"start": 18, "end": 20}], 20) == (
        19,
        21,
    )


def test_gff_retains_missingness_and_escapes_attributes():
    batch = deepcopy(EXAMPLE)
    batch["records"][0]["id"] = "gene;name=one&two,%quoted"
    source = batch["genomes"][batch["records"][0]["genome_id"]]
    source["accession"] = "replicon with space"
    old_key = batch["records"][0]["genome_id"]
    batch["genomes"]["replicon with space~"] = batch["genomes"].pop(old_key)
    for record in batch["records"]:
        if record["genome_id"] == old_key:
            record["genome_id"] = "replicon with space~"
    result = predict_native(batch, AlgebraBackend(paired=0))
    output = io.StringIO()
    write_gff3(result, output)
    text = output.getvalue()
    assert text.startswith("##gff-version 3\n")
    assert "record=internal-tss;status=unsupported" in text
    lines = [
        x.split("\t")
        for x in text.splitlines()
        if not x.startswith("#") and "\tregion\t" not in x
    ]
    assert all(len(line) == 9 for line in lines)
    assert lines[0][0] == "replicon%20with%20space%7E"
    assert "##sequence-region replicon%20with%20space%7E 1 20" in text
    assert "Is_circular=true" in text and "Is_circular=false" in text
    assert "reason=leaderless_initiation_not_modeled" in text
    assert "reason=None" not in text
    attributes = dict(item.split("=", 1) for item in lines[0][8].split(";"))
    assert unquote(attributes["Name"]) == batch["records"][0]["id"]
    assert lines[0][3:8] == ["8", "10", ".", "+", "."]
    assert "relative_tir" in attributes
    assert len({line[8].split(";", 1)[0] for line in lines}) == len(lines)
    with pytest.raises(InputError, match="requires"):
        write_gff3({}, io.StringIO())
    assert native_io._attribute("a\n\t\x7fb") == "a%0A%09%7Fb"


def test_origin_start_codon_export_uses_unrolled_gff_end():
    batch = deepcopy(EXAMPLE)
    row = dict(
        batch["records"][0],
        id="origin-start",
        origin_crossing=True,
        tss_zero_based=14,
        cds_start_zero_based=19,
        leader_length_nt=5,
        upstream_limit_nt=5,
        downstream_length_nt=3,
    )
    dna = "TG" + "A" * 17 + "A"
    source = batch["genomes"][row["genome_id"]]
    source.update(sequence=dna, sequence_sha256=sequence_hash(dna), topology="circular")
    batch["records"] = [row]
    result = predict_native(batch, AlgebraBackend(paired=0))
    assert result["results"][0]["prediction"]["sites"][0]["codon"] == "AUG"
    output = io.StringIO()
    write_gff3(result, output)
    first = next(x for x in output.getvalue().splitlines() if "\tstart_codon\t" in x)
    assert first.split("\t")[3:5] == ["20", "22"]


def test_native_cli_json_gff_stdin_and_failed_rows(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(RnaStructure, "open", lambda root: AlgebraBackend(paired=0))
    path = tmp_path / "input.json"
    path.write_text(json.dumps(EXAMPLE))
    assert main([str(path), "--backend-root", "/unused"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == "native-rbs-result-1"
    assert main([str(path), "--backend-root", "/unused", "--format", "gff3"]) == 0
    assert capsys.readouterr().out.startswith("##gff-version 3")
    monkeypatch.setenv("REGSITE_RNASTRUCTURE", "/unused")
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps(dict(EXAMPLE, records=[None])))
    )
    assert main(["-"]) == 1
    assert (
        json.loads(capsys.readouterr().out)["results"][0]["status"] == "invalid_input"
    )


def test_native_cli_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    assert main(["-"]) == 2
    assert "backend-root" in capsys.readouterr().err
    assert main([str(tmp_path / "absent"), "--backend-root", "/unused"]) == 2
    assert "No such file" in capsys.readouterr().err
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    def fail(root):
        raise BackendError("broken backend")

    monkeypatch.setattr(RnaStructure, "open", fail)
    assert main(["-", "--backend-root", "/unused"]) == 2
    assert "broken backend" in capsys.readouterr().err


def test_real_native_cli_execution(real_backend, tmp_path, capsys):
    path = tmp_path / "native.json"
    path.write_text(json.dumps(EXAMPLE))
    assert main([str(path), "--backend-root", str(real_backend.root)]) == 0
    assert len(json.loads(capsys.readouterr().out)["results"]) == 7
