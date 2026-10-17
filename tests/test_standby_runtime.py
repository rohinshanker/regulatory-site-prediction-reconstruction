"""Versioned standby integration, physical algebra, projection and failures."""

import json
import math
from pathlib import Path

import jsonschema
import pytest
from test_rbs import AlgebraBackend, request
from test_standby import structure

from regsite.cli import main
from regsite.genome import GenomicPath
from regsite.native import _project_sites, predict_native
from regsite.rbs import predict
from regsite.sequence import reverse_complement
from regsite.structures import Structure

SCHEMA = json.loads(Path("schemas/rbs-result-1.2.schema.json").read_text())
PREFIX = ".." + "(" * 12 + "......" + ")" * 12 + ".."


class OpeningBackend(AlgebraBackend):
    """An independent fixed-state energy oracle; not a biological predictor."""

    def __init__(self, *, negative=False):
        super().__init__(paired=len(PREFIX))
        self.negative = negative

    def fold(self, sequence):
        if len(sequence) == len(PREFIX):
            return Structure(sequence, structure(PREFIX).pairs, -20)
        return Structure(sequence, (-1,) * len(sequence), -4)

    def evaluate(self, sequence, pairs):
        removed = 12 - sum(j > i for i, j in enumerate(pairs[: len(PREFIX)]))
        penalty = 0.9 * min(3, removed) + 4 * max(0, removed - 3)
        if self.negative and removed:
            penalty = -1
        return Structure(sequence, pairs, -20 + penalty)


def value(strand="+"):
    sequence = "A" * len(PREFIX) + "GGAGGAAAAAA" + "AUG" + "A" * 30
    return request(
        sequence=sequence if strand == "+" else reverse_complement(sequence),
        start_positions=[len(PREFIX) + 11],
        strand=strand,
    )


@pytest.mark.parametrize("strand", ["+", "-"])
def test_positive_standby_algebra_and_coordinate_contract(strand):
    result = predict(value(strand), OpeningBackend(), profile="standby2014")
    jsonschema.validate({"schema_version": "1.2", "results": [result]}, SCHEMA)
    assert result["status"] == "ok"
    site = result["sites"][0]
    energy = site["energies"]
    assert energy["dG_unfolding"] == pytest.approx(2.7)
    assert energy["dG_distortion"] == pytest.approx(2.604)
    assert energy["dG_sliding"] == 0
    assert energy["dG_standby"] == pytest.approx(5.304)
    assert energy["dG_accessible_complex"] == pytest.approx(-17.3)
    assert energy["dG_total"] == pytest.approx(
        -20 + energy["dG_spacing"] - 1.194 + 4 + 5.304
    )
    assert site["tir"] == pytest.approx(2500 * math.exp(-energy["dG_total"] / 2.222))
    assert "dG_standby_signed" not in energy
    assert site["standby_interval"] is None
    standby = site["standby"]
    assert standby["opened_pairs"] == [[2, 31], [3, 30], [4, 29]]
    assert standby["evaluated_states"] == 13
    n = len(value()["sequence"])
    spans = {
        "original_hairpin": (2, 32),
        "hairpin": (5, 29),
        "distal": (0, 5),
        "proximal": (29, 34),
    }
    for key, (start, end) in spans.items():
        assert standby[key] == {
            "start": start if strand == "+" else n - end,
            "end": end if strand == "+" else n - start,
            "strand": strand,
        }
    assert site["structures"]["bound_after_standby"]["mrna_intramolecular_pairs"] == [
        [i, 33 - i] for i in range(5, 14)
    ]
    params = result["model"]["parameters"]
    assert "standby_nt" not in params
    assert params["standby_model"]["maximum_unique_states"] == 512
    assert (
        "later_standby_geometry_sliding_drafting_stacking_not_implemented"
        not in result["warnings"]
    )


def test_schema_rejects_fabricated_missingness_and_negative_penalties():
    cases = [
        predict(None, AlgebraBackend(), profile="standby2014"),
        predict(request(start_positions=[0]), AlgebraBackend(), profile="standby2014"),
        predict(request(), AlgebraBackend(fail=True), profile="standby2014"),
        predict(request(), AlgebraBackend(paired=None), profile="standby2014"),
        predict(request(start_positions=[]), AlgebraBackend(), profile="standby2014"),
    ]
    jsonschema.validate({"schema_version": "1.2", "results": cases}, SCHEMA)
    assert all(site["standby"] is None for case in cases for site in case["sites"])
    result = predict(value(), OpeningBackend(), profile="standby2014")
    result["sites"][0]["energies"]["dG_unfolding"] = -1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"schema_version": "1.2", "results": [result]}, SCHEMA)


def test_negative_unfolding_warning_and_no_available_context():
    result = predict(value(), OpeningBackend(negative=True), profile="standby2014")
    site = result["sites"][0]
    assert "negative_fixed_state_unfolding_cost_clamped_to_zero" in site["warnings"]
    assert site["energies"]["dG_unfolding"] == 0
    assert site["energies"]["dG_unfolding_raw"] == -1
    assert site["standby"]["hairpin"] == {"start": 8, "end": 26, "strand": "+"}
    site = predict(request(), AlgebraBackend(paired=0), profile="standby2014")["sites"][
        0
    ]
    assert site["standby"]["hairpin"] is None
    assert "no_upstream_standby_context_available" in site["warnings"]
    assert site["standby"]["proximal"] == {"start": 0, "end": 0, "strand": "+"}


def test_runtime_rejects_incomplete_standby_search():
    class TooMany(AlgebraBackend):
        def fold(self, sequence):
            if len(sequence) == 47:
                return Structure(
                    sequence, structure("(" + "(...)" * 9 + ")").pairs, -20
                )
            return super().fold(sequence)

    result = predict(
        request(sequence="A" * 60 + "AUGAAA", start_positions=[60]),
        TooMany(paired=47),
        profile="standby2014",
    )
    assert result["status"] == "unsupported"
    assert "512 states" in result["sites"][0]["reason"]
    assert result["sites"][0]["standby"] is None


def test_cli_uses_new_schema_without_changing_legacy(monkeypatch, capsys):
    monkeypatch.setattr("regsite.cli.RnaStructure.open", lambda root: OpeningBackend())
    from io import StringIO

    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(value())))
    assert main(["-", "--backend-root", "test", "--profile", "standby2014"]) == 0
    result = json.loads(capsys.readouterr().out)
    jsonschema.validate(result, SCHEMA)
    assert result["schema_version"] == "1.2"


def test_real_offline_standby_profile_and_term_identities(real_backend):
    request_value = json.loads(Path("examples/rbs-single.json").read_text())
    result = predict(request_value, real_backend, profile="standby2014")
    assert result["status"] == "ok"
    jsonschema.validate({"schema_version": "1.2", "results": [result]}, SCHEMA)
    for site in result["sites"]:
        energy = site["energies"]
        assert energy["dG_standby"] == pytest.approx(
            energy["dG_unfolding"] + energy["dG_distortion"] + energy["dG_sliding"]
        )
        assert energy["dG_unfolding_raw"] == pytest.approx(
            energy["dG_accessible_complex"] - energy["dG_complex"]
        )
        assert energy["dG_total"] == pytest.approx(
            energy["dG_complex"]
            + energy["dG_spacing"]
            + energy["dG_start"]
            - energy["dG_mRNA"]
            + energy["dG_standby"]
        )


@pytest.mark.parametrize("strand", ["+", "-"])
def test_native_projection_including_origin_crossing_and_missing_modules(strand):
    prediction = predict(value(), OpeningBackend(), profile="standby2014")
    path = GenomicPath(
        200, 198 if strand == "+" else 2, len(value()["sequence"]), strand, True
    )
    # Inject a downstream interval only to exercise projection, not the scorer.
    prediction["sites"][0]["standby"]["downstream_hairpins"] = [
        {"interval": {"start": 1, "end": 5, "strand": "+"}, "height_nt": 2}
    ]
    mapped = _project_sites(prediction, path)[0]["standby_module"]
    if strand == "+":
        assert mapped["distal"] == [
            {"start": 198, "end": 200, "strand": "+"},
            {"start": 0, "end": 3, "strand": "+"},
        ]
        assert mapped["hairpin"] == [{"start": 3, "end": 27, "strand": "+"}]
        assert mapped["downstream_hairpins"] == [
            [
                {"start": 199, "end": 200, "strand": "+"},
                {"start": 0, "end": 3, "strand": "+"},
            ]
        ]
    else:
        assert mapped["distal"] == [
            {"start": 0, "end": 3, "strand": "-"},
            {"start": 198, "end": 200, "strand": "-"},
        ]
        assert mapped["hairpin"] == [{"start": 174, "end": 198, "strand": "-"}]
        assert mapped["downstream_hairpins"] == [
            [
                {"start": 0, "end": 2, "strand": "-"},
                {"start": 198, "end": 200, "strand": "-"},
            ]
        ]
    batch = json.loads(Path("benchmarks/rbs/native-input-example.json").read_text())
    result = predict_native(batch, AlgebraBackend(paired=0), profile="standby2014")
    schema = json.loads(Path("schemas/native-rbs-result-1.schema.json").read_text())
    jsonschema.validate(result, schema)
    assert result["results"][0]["genomic_sites"][0]["standby_module"]["hairpin"] is None
    assert result["results"][5]["genomic_sites"][0]["standby_module"] is None
