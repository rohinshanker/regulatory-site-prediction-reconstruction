"""Published footprint geometry, profile separation and genuine engine ablations."""

import json
from pathlib import Path

import jsonschema
import pytest
from test_rbs import AlgebraBackend, request

from regsite.profiles import get_profile
from regsite.rbs import predict
from regsite.sequence import InputError, reverse_complement
from regsite.structures import Structure


def test_profile_resolution_and_separation():
    profile = get_profile("footprint2017")
    assert get_profile(profile.model_id) == profile
    with pytest.raises(InputError, match="unknown RBS profile"):
        get_profile("typo")
    historical = predict(request(), AlgebraBackend())
    refined = predict(request(), AlgebraBackend(), profile="footprint2017")
    assert historical["model"]["id"] != refined["model"]["id"]
    assert historical["prediction_id"] != refined["prediction_id"]
    assert historical["schema_version"] == "1.0"
    assert refined["schema_version"] == "1.1"
    assert historical["model"]["parameters"]["historical_footprint_nt"] == 1000
    assert refined["model"]["parameters"]["coding_footprint_nt"] == 13
    assert "later_standby" in refined["warnings"][-1]


def test_long_context_and_precise_post_footprint_pair_projection():
    class PairedSuffix(AlgebraBackend):
        def fold(self, sequence):
            result = super().fold(sequence)
            if len(sequence) == 87:
                pairs = [86, *([-1] * 85), 0]
                return Structure(sequence, tuple(pairs), -1.2, -1.1)
            return result

    backend = PairedSuffix()
    sequence = "A" * 105 + "ATG" + "A" * 120
    value = request(sequence=sequence, start_positions=[105])
    result = predict(value, backend, profile="context2017")
    site = result["sites"][0]
    assert result["status"] == "ok"
    assert site["window"]["oriented_start"] == 5
    assert site["window"]["oriented_end"] == 205
    assert [len(x) for x in backend.folded] == [200, 6, 87, 2]
    assert site["coding_footprint"] == {"start": 105, "end": 118, "strand": "+"}
    assert site["energies"]["dG_post_footprint"] == -1.2
    assert site["post_footprint"]["mrna_intramolecular_pairs"] == [[0, 86]]
    assert site["structures"]["bound_after_standby"]["mrna_intramolecular_pairs"] == [
        [113, 199]
    ]
    assert "post_footprint_native_energy_differs_from_efn2" in site["warnings"]
    reverse = predict(
        dict(
            value, sequence=reverse_complement(sequence.replace("T", "U")), strand="-"
        ),
        PairedSuffix(),
        profile="context2017",
    )["sites"][0]
    assert reverse["energies"] == site["energies"]
    assert reverse["coding_footprint"] == {
        "start": len(sequence) - 118,
        "end": len(sequence) - 105,
        "strand": "-",
    }


@pytest.mark.parametrize("extra", [0, 10, 11])
@pytest.mark.parametrize("strand", ["+", "-"])
def test_short_coding_context_and_exact_footprint_boundary(extra, strand):
    value = request(sequence="A" * 20 + "ATG" + "A" * extra)
    if strand == "-":
        value.update(
            sequence=reverse_complement(value["sequence"].replace("T", "U")), strand="-"
        )
    backend = AlgebraBackend()
    result = predict(value, backend, profile="footprint2017")
    site = result["sites"][0]
    assert site["status"] == "ok"
    if strand == "+":
        assert site["coding_footprint"]["end"] == min(33, 23 + extra)
    else:
        assert site["coding_footprint"] == {
            "start": max(0, extra - 10),
            "end": 3 + extra,
            "strand": "-",
        }
    assert len(backend.folded[2]) == max(0, extra - 10)
    assert ("coding_footprint_truncated_at_sequence_boundary" in site["warnings"]) == (
        extra < 10
    )
    schema = json.loads(Path("schemas/rbs-result-1.1.schema.json").read_text())
    jsonschema.validate({"schema_version": "1.1", "results": [result]}, schema)


def test_refined_missingness_and_schema():
    schema = json.loads(Path("schemas/rbs-result-1.1.schema.json").read_text())
    results = [
        predict(request(), AlgebraBackend(), profile="footprint2017"),
        predict(request(start_positions=[0]), AlgebraBackend(), profile="context2017"),
        predict(None, AlgebraBackend(), profile="footprint2017"),
        predict(request(), AlgebraBackend(fail=True), profile="context2017"),
    ]
    jsonschema.validate({"schema_version": "1.1", "results": results}, schema)
    for result in (results[1], results[3]):
        assert result["sites"][0]["coding_footprint"] is None
        assert result["sites"][0]["post_footprint"] is None
    results[0]["sites"][0]["energies"]["dG_post_footprint"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"schema_version": "1.1", "results": results}, schema)


def test_real_footprint_ablation_preserves_downstream_hairpin(real_backend):
    # First coding base is +1; the independently known nine-base hairpin begins
    # at +14, immediately outside [start,start+13). No fitted assay outcomes.
    leader = "AAAGGAGGAAAAAA"
    value = {
        "sequence": leader + "AUG" + "A" * 10 + "GGGAAACCC",
        "anti_sd": "ACCUCCUUA",
        "start_positions": [len(leader)],
    }
    old = predict(value, real_backend)["sites"][0]
    new = predict(value, real_backend, profile="footprint2017")["sites"][0]
    assert old["status"] == new["status"] == "ok"
    assert old["energies"]["dG_mRNA"] == new["energies"]["dG_mRNA"]
    assert new["energies"]["dG_post_footprint"] == pytest.approx(-1.2)
    assert new["energies"]["dG_total"] < old["energies"]["dG_total"]
    terms = new["energies"]
    assert terms["dG_total"] == pytest.approx(
        terms["dG_complex"]
        + terms["dG_spacing"]
        + terms["dG_start"]
        - terms["dG_mRNA"]
        - terms["dG_standby_signed"]
    )
    # Isolated suffix -1.2 is already included; whole-state dangles yield -1.4.
    assert new["energies"]["dG_total"] - old["energies"]["dG_total"] == pytest.approx(
        -1.4
    )
    assert new["tir"] > old["tir"]
    pairs = new["structures"]["bound_after_standby"]["mrna_intramolecular_pairs"]
    assert pairs == [[27, 35], [28, 34], [29, 33]]
    assert old["structures"]["bound_after_standby"]["mrna_intramolecular_pairs"] == []
    # A longer real context exercises the expanded adapter bounds, not a mock.
    longer = predict(
        dict(value, sequence="A" * 90 + value["sequence"], start_positions=[104]),
        real_backend,
        profile="context2017",
    )
    assert longer["status"] == "ok"
    assert longer["sites"][0]["window"]["oriented_start"] == 4
