"""Independent scalar equations, structural state transitions and full predictions."""

import json
import math
from pathlib import Path

import pytest

from regsite import rbs
from regsite.backend import FoldingSession
from regsite.rbs import (
    aligned_spacing,
    initiation_rate,
    predict,
    spacing_energy,
    total_energy,
)
from regsite.sequence import reverse_complement
from regsite.structures import BackendError, Structure

FIXTURES = json.loads(Path("benchmarks/rbs/scalar-fixtures.json").read_text())


def test_independent_source_scalar_fixtures():
    for row in FIXTURES["spacing"]:
        assert spacing_energy(row["aligned_spacing"]) == pytest.approx(
            row["expected_kcal_mol"], abs=1e-10
        )
    for row in FIXTURES["rates"]:
        assert initiation_rate(row["total_energy_kcal_mol"]) == pytest.approx(
            row["salis_v1_expected"], abs=1e-10
        )
    for row in FIXTURES["alignment"]:
        pairs = [
            (x - 1, y - row["mrna_length"] - 1)
            for x, y in zip(row["bp_x"], row["bp_y"], strict=True)
        ]
        assert (
            aligned_spacing(pairs, row["start_pos"]) == row["expected_aligned_spacing"]
        )
    for row in FIXTURES["assembly"]:
        assert total_energy(
            row["complex_with_spacing"],
            row["start"],
            row["unbound_mrna"],
            row["standby_upstream_signed"],
        ) == pytest.approx(row["expected_total"])
    assert {k.replace("U", "T"): v for k, v in rbs.START_ENERGIES.items()} == FIXTURES[
        "start_codon_kcal_mol"
    ]
    assert {k.replace("U", "T") for k in rbs.SCAN_CODONS} == set(
        FIXTURES["scan_start_codons"]
    )
    assert aligned_spacing([], 20) is None
    assert aligned_spacing([(19, 8)], 20) is None
    assert aligned_spacing([(1, 2), (6, 8)], 20) == 5


@pytest.mark.parametrize("energy", [float("nan"), float("inf"), -1e6, -1570, 1e6])
def test_rate_numeric_failures_not_zero_scores(energy):
    with pytest.raises(BackendError):
        initiation_rate(energy)


class AlgebraBackend:
    """Synthetic backend for source-algebra tests, not scientific reference output."""

    identity = {"name": "test-algebra-only"}

    def __init__(self, *, paired=6, count=1, before=-8, after=-6, fail=False):
        self.paired, self.count, self.before, self.after = paired, count, before, after
        self.fail = fail
        self.evaluations = 0
        self.folded = []

    def session(self, temperature, seconds):
        if seconds == 0:
            raise BackendError("invalid budget")
        return self

    def fold(self, sequence):
        if self.fail:
            raise BackendError("deliberate folding failure")
        self.folded.append(sequence)
        return Structure(sequence, (-1,) * len(sequence), -4.0)

    def cofold(self, leader, anti_sd):
        sequence = leader + "III" + anti_sd
        pairs = [-1] * len(sequence)
        if self.paired is not None:
            target = len(leader) + 3 + 8
            pairs[self.paired], pairs[target] = target, self.paired
        return tuple(Structure(sequence, tuple(pairs), -8) for _ in range(self.count))

    def evaluate(self, sequence, pairs):
        self.evaluations += 1
        return Structure(
            sequence, pairs, self.before if self.evaluations % 2 else self.after
        )

    def evaluate_many(self, structures):
        return tuple(self.evaluate(s.sequence, s.pairs) for s in structures)


def request(**changes):
    return dict(
        {
            "id": "algebra",
            "sequence": "A" * 20 + "ATG" + "A" * 50,
            "anti_sd": "ACCUCCUUA",
            "start_positions": [20],
        },
        **changes,
    )


def test_full_algebra_and_standby_clamping():
    backend = AlgebraBackend()
    result = predict(request(), backend)
    site = result["sites"][0]
    assert result["status"] == "ok"
    assert site["energies"]["dG_total"] == pytest.approx(-3.194)
    assert site["energies"]["dG_standby_signed"] == -2
    assert site["tir"] == pytest.approx(2500 * math.exp(3.194 / 2.222))
    assert site["window"]["oriented_end"] == 55
    assert [len(x) for x in backend.folded] == [55, 6, 2]
    assert site["binding_interval"] == {"start": 6, "end": 7, "strand": "+"}
    assert site["standby_interval"] == {"start": 2, "end": 6, "strand": "+"}
    assert site["structures"]["bound_before_standby"]["mrna_anti_sd_pairs"] == [[6, 8]]
    clamped = predict(request(), AlgebraBackend(before=-6, after=-8))["sites"][0]
    assert clamped["energies"]["dG_standby_signed"] == 0
    assert clamped["energies"]["dG_total"] == pytest.approx(-3.194)


def test_warning_limits_ties_and_no_extra_post_start_folding():
    backend = AlgebraBackend(paired=0, count=100)
    site = predict(request(temperature_c=30), backend)["sites"][0]
    assert site["candidate_search"]["selected_index"] == 0
    assert site["aligned_spacing"] == 11
    assert {
        "bifold_traceback_count_reached_limit",
        "standby_region_truncated_at_window_boundary",
        "historical_scalar_parameters_not_recalibrated_for_temperature",
    } <= set(site["warnings"])
    assert backend.folded[-2:] == ["", ""]
    site = predict(
        request(sequence="A" * 40 + "ATG" + "A" * 50, start_positions=[40]),
        AlgebraBackend(paired=6),
    )["sites"][0]
    assert site["window"]["oriented_start"] == 5
    assert "folding_window_touches_supplied_sequence_boundary" not in site["warnings"]
    assert "spacing_penalty_exceeds_suboptimal_energy_band" in site["warnings"]


def test_band_reference_excludes_disconnected_states():
    class Candidates(AlgebraBackend):
        def cofold(self, leader, anti_sd):
            valid = super().cofold(leader, anti_sd)[0]
            return (Structure(valid.sequence, (-1,) * len(valid.sequence), -20), valid)

    assert predict(request(), Candidates())["status"] == "ok"
    assert predict(request(), AlgebraBackend(paired=None))["status"] == "no_candidate"
    assert predict(request(), AlgebraBackend(paired=19))["status"] == "no_candidate"


def test_failure_and_missingness_are_explicit():
    assert predict(None, AlgebraBackend())["status"] == "invalid_input"
    assert predict(request(), AlgebraBackend(), seconds=0)["status"] == "failed"
    result = predict(request(), AlgebraBackend(fail=True))
    assert result["status"] == "failed"
    assert result["sites"][0]["tir"] is None
    assert result["sites"][0]["energies"] is None
    assert (
        predict(request(sequence="AUGAAA", start_positions=[0]), AlgebraBackend())[
            "status"
        ]
        == "unsupported"
    )
    assert (
        predict(request(start_positions=[0]), AlgebraBackend())["sites"][0]["reason"]
        == "unsupported_start_codon"
    )
    assert (
        predict(request(start_positions=[]), AlgebraBackend())["reason"]
        == "no_selected_start_codons"
    )
    assert (
        predict(request(sequence="A" * 100, start_positions=None), AlgebraBackend())[
            "status"
        ]
        == "no_candidate"
    )
    assert (
        predict(request(sequence="ATG" * 1001, start_positions=None), AlgebraBackend())[
            "status"
        ]
        == "unsupported"
    )


def test_partial_results_scanning_and_explicit_cug():
    value = request(
        sequence="AUG" + "A" * 20 + "CUG" + "GUG" + "UUG", start_positions=None
    )
    result = predict(value, AlgebraBackend())
    assert [s["codon"] for s in result["sites"]] == ["AUG", "GUG", "UUG"]
    assert result["status"] == "unsupported"
    explicit = predict(dict(value, start_positions=[23]), AlgebraBackend())
    assert explicit["status"] == "ok"
    assert explicit["sites"][0]["codon"] == "CUG"
    assert explicit["sites"][0]["energies"]["dG_start"] == -0.03406


def test_reverse_strand_preserves_energy_and_maps_each_interval():
    value = request()
    forward = predict(value, AlgebraBackend())
    reverse = predict(
        dict(
            value,
            sequence=reverse_complement(value["sequence"].replace("T", "U")),
            strand="-",
        ),
        AlgebraBackend(),
    )
    a, b = forward["sites"][0], reverse["sites"][0]
    assert a["energies"] == b["energies"]
    length = len(value["sequence"])
    for field in ("start_codon", "binding_interval", "standby_interval"):
        assert b[field] == {
            "start": length - a[field]["end"],
            "end": length - a[field]["start"],
            "strand": "-",
        }
    assert a["structures"] == b["structures"]
    assert forward["prediction_id"] != reverse["prediction_id"]
    assert predict(value, AlgebraBackend())["prediction_id"] == forward["prediction_id"]


def test_real_scoring_strands_and_no_binding(real_backend):
    value = {"sequence": "AAAGGAGGAAAAAA" + "AUG" + "A" * 35, "anti_sd": "ACCUCCUUA"}
    result = predict(value, real_backend)
    site = result["sites"][0]
    assert result["status"] == "ok"
    # Derived from the independently observed -11.6 duplex + source AUG energy.
    assert site["energies"]["dG_total"] == pytest.approx(-12.794)
    assert site["tir"] == pytest.approx(791687.3228275315)
    reverse = predict(
        dict(value, sequence=reverse_complement(value["sequence"]), strand="-"),
        real_backend,
    )
    assert reverse["sites"][0]["energies"] == site["energies"]
    assert (
        predict(
            {"sequence": "C" * 20 + "ATGAAA", "anti_sd": "CCCCCCCCC"}, real_backend
        )["status"]
        == "no_candidate"
    )


def test_real_backend_timeout_does_not_report_no_binding(real_backend, monkeypatch):
    def call(*args):
        raise BackendError("request folding time budget exhausted")

    monkeypatch.setattr(FoldingSession, "_call", call)
    assert predict(request(), real_backend)["status"] == "failed"


def test_result_metadata_does_not_mutate_model_or_backend():
    backend = AlgebraBackend()
    result = predict(request(), backend)
    result["model"]["parameters"]["start_energies_kcal_mol"]["AUG"] = 0
    result["backend"]["name"] = "changed"
    assert rbs.START_ENERGIES["AUG"] == -1.194
    assert backend.identity["name"] == "test-algebra-only"


def test_scratch_io_failure_is_isolated_per_record():
    class Unwritable(AlgebraBackend):
        def fold(self, sequence):
            raise OSError("scratch directory unavailable")

    result = predict(request(), Unwritable())
    assert result["status"] == "failed"
    assert result["sites"][0]["tir"] is None


def test_real_standby_opens_a_folded_upstream_prefix(real_backend):
    # Synthetic mechanism check, not an independent whole-calculator benchmark.
    leader = "GGGAAACCC" + "AAAGGAGGAAAAAA"
    sequence = leader + "ATG" + "GGGAAACCC" * 4
    result = predict(
        {
            "sequence": sequence,
            "anti_sd": "ACCUCCUUA",
            "start_positions": [len(leader)],
        },
        real_backend,
    )
    site = result["sites"][0]
    assert result["status"] == "ok"
    assert site["energies"]["dG_standby_signed"] < 0
    before = site["structures"]["bound_before_standby"]
    after = site["structures"]["bound_after_standby"]
    assert before["mrna_intramolecular_pairs"]
    standby = site["standby_interval"]
    begin = site["window"]["oriented_start"]
    for i, j in after["mrna_intramolecular_pairs"]:
        assert not standby["start"] <= i + begin < standby["end"]
        assert not standby["start"] <= j + begin < standby["end"]
    assert after["mrna_anti_sd_pairs"] == before["mrna_anti_sd_pairs"]
    assert all(j < len(leader) for i, j in before["mrna_intramolecular_pairs"])
    assert after["energy_kcal_mol"] > before["energy_kcal_mol"]


@pytest.mark.parametrize(
    "candidate_energy,expected", [(0.9, "ok"), (0.90001, "no_candidate")]
)
def test_three_kcal_boundary_uses_numeric_tolerance(candidate_energy, expected):
    class Boundary(AlgebraBackend):
        def cofold(self, leader, anti_sd):
            paired = super().cofold(leader, anti_sd)[0]
            terminal = [-1] * len(paired.sequence)
            terminal[len(leader) - 1] = len(leader) + 3 + 8
            terminal[len(leader) + 3 + 8] = len(leader) - 1
            return (
                Structure(paired.sequence, tuple(terminal), -2.1),
                Structure(paired.sequence, paired.pairs, candidate_energy),
            )

    assert predict(request(), Boundary())["status"] == expected


def test_equivalent_budget_representations_have_same_identity():
    assert (
        predict(request(), AlgebraBackend(), seconds=60)["prediction_id"]
        == predict(request(), AlgebraBackend(), seconds=60.0)["prediction_id"]
    )


@pytest.mark.parametrize("allowance", [0, 61, True, float("nan")])
def test_invalid_enclosing_execution_allowance(allowance):
    result = predict(request(), AlgebraBackend(), execution_seconds=allowance)
    assert result["status"] == "failed"
    assert result["reason"] == "invalid enclosing execution budget"


def test_real_connected_energy_band_regression(real_backend):
    # Review reproducer: unbound structures lack bimolecular initiation energy
    # and must not set the suboptimal band for connected complexes.
    leader = "CAACCUGGACUGCCGGGAGGGCAGUUAUCAGGUUA"
    result = predict(
        {
            "sequence": leader + "ATG" + "A" * 35,
            "anti_sd": "ACCUCCUUA",
            "start_positions": [len(leader)],
        },
        real_backend,
    )
    assert result["status"] == "ok"
    search = result["sites"][0]["candidate_search"]
    assert search["returned"] >= search["connected_returned"] > 0
    assert (
        result["sites"][0]["energies"]["dG_cofold_search"]
        <= search["band_reference_kcal_mol"] + 3 + 1e-9
    )
