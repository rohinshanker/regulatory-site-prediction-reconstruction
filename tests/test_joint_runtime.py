"""Independent finite-state selection cases and real joint-profile execution."""

import io
import json
import math
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest
from test_rbs import AlgebraBackend, request
from test_standby import structure
from test_standby_runtime import OpeningBackend, value

from regsite import backend as backend_module
from regsite import rbs
from regsite.cli import main
from regsite.genome import GenomicPath
from regsite.native import _project_sites, predict_native
from regsite.profiles import get_profile
from regsite.rbs import predict
from regsite.sequence import reverse_complement
from regsite.structures import BackendError, Structure

SCHEMA = json.loads(Path("schemas/rbs-result-1.3.schema.json").read_text())


class FiniteBackend:
    """Two synthetic bindings with equal spacing and different accessible surface.

    These fixed energies are an algebraic oracle, never thermodynamic references.
    At start14, (mRNA0,aSD8) and (mRNA5,aSD3) both have spacing5. The first
    prefix has area15 and distortion1.474; the second area20 and distortion0.
    Unbound=-4 and assembled=-8 for both. Thus totals are -3.720 and -5.194,
    despite preliminary cofold energies -10 and -9 preferring the first.
    """

    identity = {"name": "independent-finite-joint-oracle"}

    def __init__(self, candidates=((0, 8, -10), (5, 3, -9)), failure=None):
        self.candidates = candidates
        self.failure = failure
        self.calls = 0

    def session(self, temperature, seconds):
        return self

    def fold(self, sequence):
        return Structure(sequence, (-1,) * len(sequence), -4 if sequence else 0)

    def cofold(self, leader, anti_sd):
        result = []
        for mrna, rrna, energy in self.candidates:
            sequence = leader + "III" + anti_sd
            pairs = [-1] * len(sequence)
            if mrna is not None:
                target = len(leader) + 3 + rrna
                pairs[mrna], pairs[target] = target, mrna
            result.append(Structure(sequence, tuple(pairs), energy))
        return tuple(result)

    def evaluate(self, sequence, pairs):
        self.calls += 1
        if self.failure is not None and self.calls == 2:
            raise self.failure
        return Structure(sequence, pairs, -8)


def finite_request(strand="+"):
    sequence = "A" * 14 + "AUG" + "A" * 30
    return request(
        sequence=sequence if strand == "+" else reverse_complement(sequence),
        start_positions=[14],
        strand=strand,
    )


def validate(result):
    jsonschema.validate({"schema_version": "1.3", "results": [result]}, SCHEMA)
    return result["sites"][0] if result["sites"] else None


@pytest.mark.parametrize("strand", ["+", "-"])
def test_full_objective_changes_winner_and_preserves_coordinates(strand):
    result = predict(finite_request(strand), FiniteBackend(), profile="joint_standby")
    site = validate(result)
    assert result["status"] == "ok"
    assert site["energies"]["dG_total"] == pytest.approx(-5.194)
    assert site["tir"] == pytest.approx(2500 * math.exp(5.194 / 2.222))
    search = site["joint_search"]
    assert search["complete"]
    assert search["returned"] == search["connected"] == search["eligible"] == 2
    assert (
        search["evaluated"]
        == search["state_attempts"]
        == search["states_evaluated"]
        == 2
    )
    assert search["failed"] == search["not_evaluated"] == 0
    assert search["selected_index"] == 1
    assert search["greedy_index"] == 0
    assert search["greedy_total_energy"] == pytest.approx(-3.720)
    assert [row["standby_energy"] for row in search["candidates"]] == pytest.approx(
        [1.474, 0]
    )
    assert search["selected_candidate_id"] == search["candidates"][1]["candidate_id"]
    assert search["greedy_candidate_id"] == search["candidates"][0]["candidate_id"]
    assert site["candidate_search"]["selected_index"] == 1
    n = len(finite_request()["sequence"])
    assert site["binding_interval"] == {
        "start": 5 if strand == "+" else n - 6,
        "end": 6 if strand == "+" else n - 5,
        "strand": strand,
    }
    assert site["standby"]["proximal"] == {
        "start": 0 if strand == "+" else n - 5,
        "end": 5 if strand == "+" else n,
        "strand": strand,
    }
    assert site["structures"]["bound_before_standby"]["mrna_anti_sd_pairs"] == [[5, 3]]
    assert (
        "binding_candidate_selected_before_standby_optimization"
        not in result["warnings"]
    )
    assert (
        result["model"]["parameters"]["joint_search"][
            "maximum_bound_state_attempts_per_site"
        ]
        == 4096
    )
    # The old profile remains greedy and carries its original warning/shape.
    old = predict(finite_request(strand), FiniteBackend(), profile="standby2014")
    assert old["sites"][0]["energies"]["dG_total"] == pytest.approx(-3.720)
    assert "joint_search" not in old["sites"][0]
    assert "binding_candidate_selected_before_standby_optimization" in old["warnings"]


@pytest.mark.parametrize(
    "backend_factory,request_factory",
    [(FiniteBackend, finite_request), (OpeningBackend, value)],
)
def test_single_candidate_matches_complete_standby(backend_factory, request_factory):
    backend = backend_factory()
    if isinstance(backend, FiniteBackend):
        backend.candidates = backend.candidates[:1]
    joint = validate(predict(request_factory(), backend, profile="joint_standby"))
    previous = backend_factory()
    if isinstance(previous, FiniteBackend):
        previous.candidates = previous.candidates[:1]
    old = predict(request_factory(), previous, profile="standby2014")["sites"][0]
    search = joint.pop("joint_search")
    # The new five-term compensated sum may differ in the last binary digits;
    # all structural choices and individual energy terms remain exactly equal.
    for key in ("tir", "log_tir"):
        assert joint.pop(key) == pytest.approx(old.pop(key), rel=1e-12)
    assert joint["energies"].pop("dG_total") == pytest.approx(
        old["energies"].pop("dG_total"), abs=1e-12
    )
    assert joint == old
    assert search["selected_index"] == search["greedy_index"] == 0
    assert search["states_evaluated"] == old["standby"]["evaluated_states"]


def test_duplicate_states_keep_indices_and_exact_tie_order():
    result = predict(
        finite_request(),
        FiniteBackend(((5, 3, -9), (5, 3, -10))),
        profile="joint_standby",
    )
    search = validate(result)["joint_search"]
    assert search["selected_index"] == 0
    assert search["greedy_index"] == 1
    assert search["state_attempts"] == 2  # No hidden cross-candidate deduplication.
    assert (
        search["candidates"][0]["candidate_id"]
        != search["candidates"][1]["candidate_id"]
    )
    assert (
        search["candidates"][0]["candidate_id"].split("-", 2)[2]
        == search["candidates"][1]["candidate_id"].split("-", 2)[2]
    )
    repeated = validate(
        predict(
            finite_request(),
            FiniteBackend(((5, 3, -9), (5, 3, -10))),
            profile="joint_standby",
        )
    )
    assert repeated["joint_search"] == search


@pytest.mark.parametrize(
    "candidates,connected,eligible",
    [
        (((None, 0, -40), (0, 8, -10), (5, 3, -6)), 2, 1),
        (((None, 0, -40),), 0, 0),
        (((13, 0, -10),), 1, 0),
    ],
)
def test_same_connected_band_and_spacing_eligibility(candidates, connected, eligible):
    result = predict(
        finite_request(), FiniteBackend(candidates), profile="joint_standby"
    )
    site = validate(result)
    search = site["joint_search"]
    assert search["returned"] == len(candidates)
    assert search["connected"] == connected
    assert search["eligible"] == eligible
    assert search["complete"]
    assert result["status"] == ("ok" if eligible else "no_candidate")
    if not eligible:
        assert search["selected_index"] is None
        assert search["candidates"] == []


@pytest.mark.parametrize(
    "error",
    [
        BackendError("candidate deadline exhausted"),
        OSError("missing file"),
        UnicodeError("invalid text"),
    ],
)
def test_candidate_failure_preserves_complete_denominators_and_no_winner(error):
    backend = FiniteBackend(((0, 8, -10), (5, 3, -9), (6, 2, -9)), failure=error)
    result = predict(finite_request(), backend, profile="joint_standby")
    site = validate(result)
    assert result["status"] == "failed"
    assert site["tir"] is site["energies"] is site["structures"] is None
    search = site["joint_search"]
    assert not search["complete"]
    assert search["evaluated"] == search["failed"] == search["not_evaluated"] == 1
    assert search["state_attempts"] == 2
    assert search["states_evaluated"] == 1
    assert search["selected_index"] is search["greedy_total_energy"] is None
    assert [row["status"] for row in search["candidates"]] == [
        "ok",
        "failed",
        "not_evaluated",
    ]
    assert backend.calls == 2


def test_global_state_bound_is_enforced_before_4097th_call():
    class Branches(AlgebraBackend):
        def fold(self, sequence):
            if len(sequence) == 42:
                return Structure(
                    sequence, structure("(" + "(...)" * 8 + ")").pairs, -20
                )
            return super().fold(sequence)

    backend = Branches(paired=42, count=100, before=-8, after=-8)
    result = predict(
        request(sequence="A" * 60 + "AUGAAA", start_positions=[60]),
        backend,
        profile="joint_standby",
    )
    site = validate(result)
    assert result["status"] == "unsupported"
    assert "4096 bound states" in site["reason"]
    search = site["joint_search"]
    assert (
        backend.evaluations
        == search["state_attempts"]
        == search["states_evaluated"]
        == 4096
    )
    assert search["evaluated"] == 15  # 257 states each; the next is incomplete.
    assert search["failed"] == 1
    assert search["not_evaluated"] == 84
    assert site["tir"] is search["selected_index"] is None


def test_per_candidate_cap_retains_missingness():
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
        profile="joint_standby",
    )
    site = validate(result)
    assert result["status"] == "unsupported"
    assert "512 states" in site["reason"]
    assert site["joint_search"]["failed"] == 1
    assert site["joint_search"]["states_evaluated"] == 1


@pytest.mark.parametrize("energy", [None, float("nan"), float("inf")])
def test_nonfinite_bound_state_rejected(energy):
    class Invalid(FiniteBackend):
        def evaluate(self, sequence, pairs):
            return Structure(sequence, pairs, energy)

    result = predict(finite_request(), Invalid(), profile="joint_standby")
    site = validate(result)
    assert result["status"] == "failed"
    assert site["joint_search"]["state_attempts"] == 1
    assert site["joint_search"]["states_evaluated"] == 0


def test_nonfinite_total_and_score_overflow_are_explicit():
    class InvalidUnbound(FiniteBackend):
        def fold(self, sequence):
            result = super().fold(sequence)
            return Structure(result.sequence, result.pairs, float("inf"))

    site = validate(
        predict(finite_request(), InvalidUnbound(), profile="joint_standby")
    )
    assert site["status"] == "failed"
    assert site["reason"] == "nonfinite joint candidate total energy"
    assert not site["joint_search"]["complete"]

    class Overflow(FiniteBackend):
        def evaluate(self, sequence, pairs):
            return Structure(sequence, pairs, -1e10)

    site = validate(predict(finite_request(), Overflow(), profile="joint_standby"))
    assert site["status"] == "failed"
    assert site["joint_search"][
        "complete"
    ]  # Selection completed; rate cannot be represented.
    assert site["energies"] is site["tir"] is None


def test_no_search_and_invalid_inputs_remain_null():
    for result in (
        predict(None, FiniteBackend(), profile="joint_standby"),
        predict(request(start_positions=[]), FiniteBackend(), profile="joint_standby"),
        predict(request(start_positions=[0]), FiniteBackend(), profile="joint_standby"),
        predict(request(), AlgebraBackend(fail=True), profile="joint_standby"),
    ):
        site = validate(result)
        if site:
            assert site["joint_search"] is None


@pytest.mark.parametrize("strand", ["+", "-"])
def test_native_circular_projection_uses_selected_module(strand):
    prediction = predict(finite_request(), FiniteBackend(), profile="joint_standby")
    path = GenomicPath(
        200,
        198 if strand == "+" else 2,
        len(finite_request()["sequence"]),
        strand,
        True,
    )
    mapped = _project_sites(prediction, path)[0]
    assert mapped["standby_module"]["proximal"] == (
        [
            {"start": 198, "end": 200, "strand": "+"},
            {"start": 0, "end": 3, "strand": "+"},
        ]
        if strand == "+"
        else [
            {"start": 0, "end": 3, "strand": "-"},
            {"start": 198, "end": 200, "strand": "-"},
        ]
    )
    batch = json.loads(Path("benchmarks/rbs/native-input-example.json").read_text())
    result = predict_native(batch, AlgebraBackend(paired=0), profile="joint_standby")
    schema = json.loads(Path("schemas/native-rbs-result-1.schema.json").read_text())
    jsonschema.validate(result, schema)


@pytest.mark.parametrize("format_name", ["json", "csv"])
def test_cli_single_and_batch_exports(monkeypatch, capsys, format_name):
    monkeypatch.setattr("regsite.cli.RnaStructure.open", lambda root: FiniteBackend())
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps([finite_request(), None])))
    assert (
        main(
            [
                "-",
                "--backend-root",
                "test",
                "--profile",
                "joint_standby",
                "--format",
                format_name,
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    if format_name == "json":
        jsonschema.validate(json.loads(output), SCHEMA)
    else:
        import csv

        rows = list(csv.DictReader(io.StringIO(output)))
        assert rows[0]["schema_version"] == "1.3"
        assert rows[0]["model_id"] == get_profile("joint_standby").model_id
        assert float(rows[0]["dG_total"]) == pytest.approx(-5.194)
        assert rows[1]["status"] == "invalid_input"


def test_schema_rejects_a_partial_winner_or_missing_search():
    result = predict(finite_request(), FiniteBackend(), profile="joint_standby")
    for mutation in ("incomplete", "missing", "negative_count"):
        changed = deepcopy(result)
        search = changed["sites"][0]["joint_search"]
        if mutation == "incomplete":
            search["complete"] = False
        elif mutation == "missing":
            del changed["sites"][0]["joint_search"]
        else:
            search["failed"] = -1
        with pytest.raises(jsonschema.ValidationError):
            validate(changed)


@pytest.mark.parametrize("example", ["rbs-single", "rbs-standby-hairpin"])
def test_real_backend_joint_objective_and_selected_state(real_backend, example):
    data = json.loads(Path(f"examples/{example}.json").read_text())
    site = validate(predict(data, real_backend, profile="joint_standby"))
    assert site["status"] == "ok"
    search = site["joint_search"]
    assert search["complete"]
    assert search["eligible"] == search["evaluated"]
    assert site["energies"]["dG_total"] <= search["greedy_total_energy"] + 1e-9
    selected = next(
        row for row in search["candidates"] if row["index"] == search["selected_index"]
    )
    assert selected["total_energy"] == site["energies"]["dG_total"]
    assert search["state_attempts"] == sum(
        row["state_attempts"] for row in search["candidates"]
    )
    assert search["states_evaluated"] <= 4096


def test_nonselected_negative_unfolding_is_still_disclosed():
    class NegativeAlternative(OpeningBackend):
        def cofold(self, leader, anti_sd):
            return (
                *AlgebraBackend(paired=self.paired).cofold(leader, anti_sd),
                *AlgebraBackend(paired=self.paired + 1).cofold(leader, anti_sd),
            )

        def evaluate(self, sequence, pairs):
            if pairs[self.paired + 1] >= len(value()["sequence"]):
                return Structure(sequence, pairs, -100)
            return super().evaluate(sequence, pairs)

    site = validate(
        predict(value(), NegativeAlternative(negative=True), profile="joint_standby")
    )
    search = site["joint_search"]
    assert search["selected_index"] == 1
    assert [c["negative_unfolding_seen"] for c in search["candidates"]] == [True, False]
    assert site["energies"]["dG_unfolding_raw"] == 0
    assert "negative_fixed_state_unfolding_cost_clamped_to_zero" in site["warnings"]


def test_real_candidates_share_whole_record_deadline(real_backend, monkeypatch):
    # Advance only the folding adapter's clock after a completed candidate.
    # Subprocess timing uses the real clock; no wall-clock sleep is required.
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(
        backend_module, "time", SimpleNamespace(monotonic=lambda: clock.now)
    )
    original = rbs._bound_state
    deadlines = []

    def expire_after_first(
        window, leader, anti_sd, binding, folding, profile, evaluate
    ):
        deadlines.append(folding.deadline)
        result = original(window, leader, anti_sd, binding, folding, profile, evaluate)
        clock.now = 161.0
        return result

    monkeypatch.setattr(rbs, "_bound_state", expire_after_first)
    data = json.loads(Path("examples/rbs-standby-hairpin.json").read_text())
    site = validate(predict(data, real_backend, profile="joint_standby", seconds=60))
    assert deadlines == [160.0, 160.0]
    assert site["status"] == "failed"
    assert site["reason"] == "request folding time budget exhausted"
    search = site["joint_search"]
    assert search["evaluated"] == search["failed"] == 1
    assert search["not_evaluated"] == search["eligible"] - 2
    assert search["candidates"][1]["state_attempts"] == 0
    assert search["selected_index"] is search["greedy_total_energy"] is None
    assert site["tir"] is site["structures"] is None


@pytest.mark.parametrize(
    "terms", [(1e308, 1e308, 0, 0, 0), (math.inf, -math.inf, 0, 0, 0)]
)
def test_compensated_sum_failure_is_explicit(terms):
    with pytest.raises(BackendError, match="nonfinite joint candidate total energy"):
        rbs._joint_total_energy(*terms)


def test_independent_decimal_tie_survives_intermediate_rounding():
    # B's unmodified fixture at2e252bf supplies these terms. Ordinary chained
    # addition orders the mathematical tie differently by about1e-15.
    a = rbs._joint_total_energy(-9, 2.5, -1.194, -4, -0.5)
    b = rbs._joint_total_energy(-10, 0, -1.194, -4, -4)
    assert a == b == -3.194
    # A representable unequal total is not rounded into the same tie bin.
    assert rbs._joint_total_energy(math.nextafter(-10, math.inf), 0, -1.194, -4, -4) > b
