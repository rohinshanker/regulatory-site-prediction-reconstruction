"""Supplied organization, real public predictors and deterministic fault injection."""

import copy
import hashlib
from pathlib import Path

import pytest

from regsite import transcript as t
from regsite.backend import FoldingSession, RnaStructure
from regsite.structures import BackendError, Structure


def annotation(identifier, start, end):
    return {
        "id": identifier,
        "range": [start, end],
        "provenance": {"kind": "synthetic", "reference": "hand-built control"},
    }


def document():
    return {
        "schema_version": "supplied-transcript-request-1",
        "id": "test α",
        "sequence": "A" * 40 + "ATG" + "A" * 157,
        "transcript": annotation("rna", 20, 180),
        "cds": [annotation("gene", 40, 100)],
        "rbs": {
            "profile": "historical",
            "anti_sd": "ACCUCCUUA",
            "temperature_c": 37,
            "host": None,
        },
        "promoter": {
            "calibration": "in_vitro",
            "host": None,
            "scan": {
                "mode": "positions",
                "positions": [{"strand": "+", "tss": 100}, {"strand": "-", "tss": 100}],
            },
        },
        "projection": None,
        "settings": {
            "seconds_per_rbs_record": 30,
            "seconds_per_promoter_record": 30,
            "seconds_total": 100,
        },
    }


class SyntheticSession(FoldingSession):
    """Deterministic structures for orchestration tests, not biological evidence."""

    def fold(self, sequence):
        return Structure(sequence, (-1,) * len(sequence), -4.0)

    def cofold(self, leader, anti_sd):
        sequence = leader + "III" + anti_sd
        pairs = [-1] * len(sequence)
        pairs[6], pairs[-1] = len(sequence) - 1, 6
        return (Structure(sequence, tuple(pairs), -8.0),)

    def evaluate(self, sequence, pairs):
        return Structure(sequence, pairs, -6.0)

    def evaluate_many(self, structures):
        return tuple(Structure(s.sequence, s.pairs, -6.0) for s in structures)


@pytest.fixture
def backend(monkeypatch):
    value = RnaStructure(Path("."), {"name": "synthetic-structure-test-only"})
    monkeypatch.setattr(
        RnaStructure,
        "session",
        lambda *args: SyntheticSession(Path("."), 310.15, float("inf")),
    )
    return value


def projection(strand="+", crossing=False):
    return {
        "contig": "synthetic",
        "origin": (980 if strand == "+" else 10)
        if crossing
        else (10 if strand == "+" else 980),
        "contig_length": 1000,
        "sequence_strand": strand,
        "topology": "circular" if crossing else "linear",
        "origin_crossing": crossing,
    }


def test_public_predictors_organization_identity_and_scalars(backend):
    request = document()
    before = copy.deepcopy(request)
    result = t.predict_transcript(request, backend)
    assert request == before
    assert result == t.predict_transcript(request, backend)
    assert result["status"] == "complete"
    assert result["request"] == request
    assert (
        result["request_sha256"]
        == hashlib.sha256(t.canonical_bytes(request)).hexdigest()
    )
    without = {key: val for key, val in result.items() if key != "prediction_sha256"}
    assert (
        result["prediction_sha256"]
        == hashlib.sha256(t.canonical_bytes(without)).hexdigest()
    )
    assert t.result_bytes(result).endswith(b"\n")
    assert b"\\u03b1" in t.result_bytes(result)
    rb = result["components"]["rbs"]
    assert rb["request"]["sequence"] == request["sequence"][20:180]
    assert rb["roster"] == [20]
    site = rb["prediction"]["sites"][0]
    cds = result["cds"][0]
    assert cds["site_index"] == 0
    assert cds["scalars"]["tir"]["value"] == site["tir"]
    assert cds["features"]["start_codon"]["native_interval"] == [20, 23]
    assert cds["features"]["start_codon"]["construct_interval"] == [40, 43]
    assert result["settings"]["seconds_total"] == 100.0
    assert type(result["settings"]["seconds_total"]) is float
    assert result["identities"]["rbs"]["backend"] == backend.identity
    assert (
        result["components"]["promoter"]["prediction"]["model"]["claims"][
            "physical_free_energy"
        ]
        is False
    )
    request["cds"][0]["id"] = "changed"
    backend.identity["name"] = "changed"
    assert result["cds"][0]["annotation"]["id"] == "gene"
    assert result["identities"]["rbs"]["backend"]["name"] != "changed"


@pytest.mark.parametrize("strand", ["+", "-"])
@pytest.mark.parametrize("crossing", [False, True])
def test_public_projection_context_and_multiple_overlapping_cds(
    backend, strand, crossing
):
    request = document()
    request["projection"] = projection(strand, crossing)
    request["cds"] += [annotation("overlap", 60, 110), annotation("clipped", 170, 200)]
    result = t.predict_transcript(request, backend)
    assert result["components"]["rbs"]["roster"] == [20, 40, 150]
    assert result["cds"][-1]["warnings"] == ["downstream_clipped"]
    assert result["components"]["rbs"]["coverage"]["returned"] == 3
    for item in result["cds"]:
        assert item["features"]["window"]["construct_interval"][1] <= 180
    for candidate in result["promoter_candidates"]:
        for f in candidate["features"].values():
            genomic = f["genomic"]
            if genomic is not None:
                assert genomic["strand"] == (
                    "+" if candidate["strand"] == strand else "-"
                )
    assert result["transcript"]["sequence"] == request["sequence"][20:180]


def test_incompatible_first_three_base_reasons_and_no_backend():
    request = document()
    request["transcript"]["range"] = [50, 80]
    request["cds"] = [
        annotation("internal-tss", 40, 100),
        annotation("edge", 78, 90),
        annotation("after", 80, 100),
    ]
    result = t.predict_transcript(request)
    assert [c["transcript_offset"] for c in result["cds"]] == [-10, 28, 30]
    assert [c["reason"] for c in result["cds"]] == [
        "start_before_transcript",
        "start_codon_after_transcript",
        "start_after_transcript",
    ]
    assert all(c["status"] == "incompatible_transcript" for c in result["cds"])
    assert result["components"]["rbs"]["status"] == "not_applicable"
    assert result["coverage"]["incompatible_cds"] == 3
    assert result["components"]["rbs"]["prediction"] is None


@pytest.mark.parametrize("start", [20, 21, 177])
def test_leaderless_short_and_exact_end_codon(backend, start):
    request = document()
    request["sequence"] = "A" * start + "ATG" + "A" * (197 - start)
    request["cds"] = [annotation("test", start, start + 3)]
    result = t.predict_transcript(request, backend)
    assert result["cds"][0]["eligible"] is True
    assert result["cds"][0]["transcript_offset"] == start - 20
    if start == 20:
        assert result["cds"][0]["reason"] == "leaderless_initiation_not_modeled"
        assert result["cds"][0]["scalars"]["tir"]["value"] is None


def test_mixed_unsupported_codon_sibling_retained(backend):
    request = document()
    request["cds"] += [annotation("unsupported", 70, 100)]
    result = t.predict_transcript(request, backend)
    assert result["components"]["rbs"]["status"] == "unsupported"
    assert [c["status"] for c in result["cds"]] == ["ok", "unsupported"]
    assert result["cds"][1]["reason"] == "unsupported_start_codon"
    assert result["status"] == "partial"
    assert result["components"]["rbs"]["coverage"]["scored"] == 1


def test_session_failure_keeps_missing_sites_and_promoter(backend, monkeypatch):
    def fail(*args):
        raise BackendError("injected session failure")

    monkeypatch.setattr(RnaStructure, "session", fail)
    result = t.predict_transcript(document(), backend)
    assert result["components"]["rbs"]["status"] == "failed"
    assert result["cds"][0]["reason"] == "missing_native_site"
    assert result["cds"][0]["scalars"]["tir"]["value"] is None
    assert result["components"]["rbs"]["coverage"]["missing"] == 1
    assert result["components"]["promoter"]["coverage"]["scored"] == 2


@pytest.mark.parametrize(
    "scan",
    [
        {"mode": "positions", "positions": []},
        {"mode": "scan", "range": [200, 200], "strands": ["-", "+"]},
    ],
)
def test_empty_scan_preserved_when_started(backend, scan):
    request = document()
    request["promoter"]["scan"] = scan
    result = t.predict_transcript(request, backend)
    component = result["components"]["promoter"]
    assert component["status"] == "no_candidate"
    assert component["prediction"] is not None
    assert component["request"]["scan"] == scan
    assert result["promoter_candidates"] == []


@pytest.mark.parametrize("empty", [False, True])
def test_whole_deadline_precedence_and_no_execution(backend, monkeypatch, empty):
    request = document()
    if empty:
        request["promoter"]["scan"] = {"mode": "positions", "positions": []}
    ticks = iter([0.0, 101.0, 102.0])
    monkeypatch.setattr(t.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        t.rbs, "predict", lambda *a, **k: pytest.fail("unstarted RBS called")
    )
    monkeypatch.setattr(
        t.promoter_io,
        "predict_batch",
        lambda *a, **k: pytest.fail("unstarted Promoter called"),
    )
    result = t.predict_transcript(request, backend)
    assert result["status"] == "unavailable"
    for component in result["components"].values():
        assert component["status"] == "not_evaluated"
        assert component["reason"] == "deadline_exceeded"
        assert component["prediction"] is None
    assert result["cds"][0]["reason"] == "deadline_exceeded"


def test_remaining_budget_and_serial_order(backend, monkeypatch):
    request = document()
    request["settings"]["seconds_total"] = 15
    native_rb, native_pm = t.rbs.predict, t.promoter_io.predict_batch
    calls = []

    def rb(*a, **kw):
        calls.append("rbs")
        assert kw["seconds"] == 30.0
        assert kw["execution_seconds"] == 14.0
        return native_rb(*a, **kw)

    def pm(*a, **kw):
        calls.append("promoter")
        assert kw["seconds_per_record"] == kw["seconds_per_batch"] == 5.0
        return native_pm(*a, **kw)

    ticks = iter([0.0, 1.0, 10.0])
    monkeypatch.setattr(t.time, "monotonic", lambda: next(ticks, 10.0))
    monkeypatch.setattr(t.rbs, "predict", rb)
    monkeypatch.setattr(t.promoter_io, "predict_batch", pm)
    result = t.predict_transcript(request, backend)
    assert calls == ["rbs", "promoter"]
    assert result["components"]["rbs"]["execution_seconds"] == 14.0


def set_path(value, path, replacement):
    pieces = path.split(".")
    for key in pieces[:-1]:
        value = value[int(key)] if isinstance(value, list) else value[key]
    key = pieces[-1]
    if isinstance(value, list):
        value[int(key)] = replacement
    else:
        value[key] = replacement


@pytest.mark.parametrize(
    "path,bad",
    [
        ("schema_version", "1"),
        ("id", ""),
        ("id", "a\n"),
        ("id", 1),
        ("sequence", "a"),
        ("sequence", ""),
        ("sequence", "A" * 5001),
        ("sequence", []),
        ("transcript", {}),
        ("transcript.range", [20, 20]),
        ("transcript.range", [True, 100]),
        ("transcript.range", [0, 201]),
        ("transcript.range", [1]),
        ("transcript.range", "0:1"),
        ("transcript.provenance.kind", "invented"),
        ("transcript.provenance.reference", ""),
        ("cds", []),
        ("cds", {}),
        ("cds", [annotation(str(i), i, i + 3) for i in range(11)]),
        ("cds.0.range", [40, 42]),
        ("cds.0.id", "\x7f"),
        ("rbs.profile", "unknown"),
        ("rbs.anti_sd", "acctcctta"),
        ("rbs.anti_sd", []),
        ("rbs.anti_sd", "ACGU"),
        ("rbs.temperature_c", True),
        ("rbs.temperature_c", 101),
        ("rbs.host", {}),
        ("promoter.calibration", "unknown"),
        ("promoter.host", {"name": ""}),
        ("projection", {}),
        ("projection", projection("-", False) | {"origin": 0}),
        ("settings.seconds_total", 0),
        ("settings.seconds_total", 241),
        ("settings.seconds_per_rbs_record", True),
        ("settings.seconds_per_promoter_record", 121),
        ("settings.seconds_total", "10"),
        ("promoter.scan", []),
        ("promoter.scan", {"mode": "bad", "positions": []}),
        ("promoter.scan", {"mode": "positions", "positions": None}),
        (
            "promoter.scan",
            {"mode": "positions", "positions": [{"strand": "+", "tss": True}]},
        ),
        (
            "promoter.scan",
            {"mode": "positions", "positions": [{"strand": "?", "tss": 1}]},
        ),
        (
            "promoter.scan",
            {"mode": "positions", "positions": [{"strand": "+", "tss": 200}]},
        ),
        (
            "promoter.scan",
            {"mode": "positions", "positions": [{"strand": "+", "tss": 1}] * 2},
        ),
        ("promoter.scan", {"mode": "scan", "range": [0, 200], "strands": []}),
        ("promoter.scan", {"mode": "scan", "range": [0, 200], "strands": ["+", "+"]}),
        ("promoter.scan", {"mode": "scan", "range": [0, 200], "strands": ["bad"]}),
        ("promoter.scan", {"mode": "scan", "range": [0, 201], "strands": ["+"]}),
        ("promoter.scan", {"mode": "scan", "range": [0, False], "strands": ["+"]}),
        ("promoter.scan", {"mode": "scan", "range": [0], "strands": ["+"]}),
        ("promoter.scan", {"mode": "scan", "range": None, "strands": ["+"]}),
    ],
)
def test_invalid_input_is_atomic_before_predictors(backend, monkeypatch, path, bad):
    request = document()
    set_path(request, path, bad)
    monkeypatch.setattr(
        t.rbs, "predict", lambda *a, **k: pytest.fail("scored invalid input")
    )
    monkeypatch.setattr(
        t.promoter_io,
        "predict_batch",
        lambda *a, **k: pytest.fail("scored invalid input"),
    )
    with pytest.raises(t.TranscriptError):
        t.predict_transcript(request, backend)


@pytest.mark.parametrize("change", ["order", "start", "id", "unknown", "backend"])
def test_duplicates_unknown_fields_and_backend(backend, change):
    request = document()
    if change in ("order", "start", "id"):
        request["cds"].append(annotation("gene2", 60, 100))
        if change == "order":
            request["cds"].reverse()
        elif change == "start":
            request["cds"][1]["range"][0] = 40
        else:
            request["cds"][1]["id"] = "gene"
    elif change == "unknown":
        request["promoter"]["extra"] = True
    else:
        backend = None
    with pytest.raises(t.TranscriptError):
        t.predict_transcript(request, backend)


@pytest.mark.parametrize(
    "bad",
    [{1: "value"}, {"bad": object()}, {"bad": "\ud800"}, {"bad": float("inf")}, (1, 2)],
)
def test_non_json_values_rejected(bad):
    with pytest.raises(t.TranscriptError):
        t.predict_transcript(bad)


def test_input_resource_limits(backend, monkeypatch):
    for name, limit in [
        ("max_json_depth", 1),
        ("max_json_nodes", 2),
        ("max_input_json_bytes", 10),
        ("max_promoter_sites", 1),
    ]:
        with monkeypatch.context() as patch:
            patch.setitem(t.LIMITS, name, limit)
            with pytest.raises(t.TranscriptError):
                t.predict_transcript(document(), backend)


def test_promoter_host_and_scan_modes(backend):
    request = document()
    request["promoter"]["host"] = {"name": "other host"}
    request["promoter"]["scan"] = {
        "mode": "scan",
        "range": [0, 2],
        "strands": ["+", "-"],
    }
    result = t.predict_transcript(request, backend)
    assert result["components"]["promoter"]["roster"] == [
        ("+", 0),
        ("+", 1),
        ("-", 0),
        ("-", 1),
    ]
    assert result["components"]["promoter"]["request"]["host"] == {"name": "other host"}
    assert all(
        c["scalars"]["relative_transcription_score"]["value"] is None
        for c in result["promoter_candidates"]
    )


def test_exact_roster_limit_and_over(backend):
    request = document()
    request["sequence"] += "A" * 400
    request["promoter"]["scan"] = {
        "mode": "scan",
        "range": [0, 256],
        "strands": ["+", "-"],
    }
    assert len(t._preflight(request, backend)[3]) == 512
    request["promoter"]["scan"]["range"][1] = 257
    with pytest.raises(t.TranscriptError, match="max_promoter_sites"):
        t.predict_transcript(request, backend)


def test_output_cap_and_setup_errors(backend, monkeypatch):
    monkeypatch.setitem(t.LIMITS, "max_result_json_bytes", 1)
    with pytest.raises(t.TranscriptError, match="max_result_json_bytes"):
        t.predict_transcript(document(), backend)
    monkeypatch.setattr(
        t.promoter,
        "load_parameters",
        lambda: (_ for _ in ()).throw(t.promoter.ParameterError("bad pin")),
    )
    with pytest.raises(t.TranscriptError, match="bad pin"):
        t.predict_transcript(document(), backend)


@pytest.mark.parametrize(
    "calculator,mutation",
    [
        ("rbs", lambda p: p.pop("model")),
        ("rbs", lambda p: p.update(status="invalid_input")),
        ("rbs", lambda p: p["sites"][0].pop("window")),
        ("rbs", lambda p: p["sites"].append(copy.deepcopy(p["sites"][0]))),
        ("rbs", lambda p: p["sites"][0].update(oriented_start=21)),
        ("rbs", lambda p: p["sites"][0]["start_codon"].update(end=24)),
        ("rbs", lambda p: p["sites"][0].update(tir=None)),
        ("rbs", lambda p: p["sites"][0].update(log_tir=None)),
        ("rbs", lambda p: p["sites"][0].update(energies=None)),
        ("rbs", lambda p: p["sites"].clear()),
        ("rbs", lambda p: p["sites"][0].update(tir="bad")),
        ("rbs", lambda p: p["sites"][0].update(tir=float("nan"))),
        ("rbs", lambda p: p["input"].update(oriented_sequence="A")),
        ("rbs", lambda p: p.update(backend={"name": "wrong"})),
        ("rbs", lambda p: p["model"].update(id="wrong")),
        ("promoter", lambda p: p["model"].update(id="wrong")),
        ("promoter", lambda p: p["results"][0]["input"].update(length=1)),
        (
            "promoter",
            lambda p: p["results"][0]["input"].update(normalized_dna_sha256="wrong"),
        ),
        (
            "promoter",
            lambda p: p["results"][0].update(
                scan={"mode": "positions", "positions": []}
            ),
        ),
        ("promoter", lambda p: p["results"][0].update(projection={})),
        ("promoter", lambda p: p["results"][0].update(calibration={})),
        (
            "promoter",
            lambda p: p["results"][0]["sites"][0]["tss"].update(oriented_base=0),
        ),
        (
            "promoter",
            lambda p: p["results"][0]["sites"][0]["selected"]["intervals"].update(
                hex10=[1, 4]
            ),
        ),
        ("promoter", lambda p: p.pop("batch")),
        ("promoter", lambda p: p["results"].clear()),
        ("promoter", lambda p: p["results"][0]["sites"][0].update(selected=None)),
        ("promoter", lambda p: p["results"][0]["sites"][0].pop("tss")),
        (
            "promoter",
            lambda p: p["results"][0]["sites"][0]["selected"].pop("intervals"),
        ),
        (
            "promoter",
            lambda p: p["results"][0]["sites"][0]["selected"]["intervals"].update(
                hex10=[-1, 4]
            ),
        ),
    ],
)
def test_native_corruption_is_atomic(backend, monkeypatch, calculator, mutation):
    module = t.rbs if calculator == "rbs" else t.promoter_io
    name = "predict" if calculator == "rbs" else "predict_batch"
    original = getattr(module, name)

    def corrupt(*args, **kwargs):
        prediction = original(*args, **kwargs)
        mutation(prediction)
        return prediction

    monkeypatch.setattr(module, name, corrupt)
    with pytest.raises(t.TranscriptError):
        t.predict_transcript(document(), backend)


def test_native_unattempted_promoter_retained(backend, monkeypatch):
    original = t.promoter_io.predict_batch

    def expired(*args, **kwargs):
        kwargs["seconds_per_record"] = kwargs["seconds_per_batch"] = 1
        ticks = iter([0, 0, 2, 2])
        kwargs["clock"] = lambda: next(ticks)
        return original(*args, **kwargs)

    monkeypatch.setattr(t.promoter_io, "predict_batch", expired)
    result = t.predict_transcript(document(), backend)
    assert result["components"]["promoter"]["status"] == "failed"
    assert result["components"]["promoter"]["coverage"]["not_evaluated"] == 2
    assert all(
        c["status"] == "not_evaluated" and c["reason"] == "deadline_exceeded"
        for c in result["promoter_candidates"]
    )


def test_bounded_real_engine_integration(real_backend):
    """One real RBS request; no folding concurrency and no biological accuracy claim."""
    request = document()
    request["sequence"] = "A" * 20 + "AGGAGG" + "A" * 8 + "ATG" + "A" * 163
    request["transcript"]["range"] = [10, 150]
    request["cds"] = [annotation("real-control", 34, 120)]
    request["settings"]["seconds_per_rbs_record"] = 60
    result = t.predict_transcript(request, real_backend)
    native = result["components"]["rbs"]["prediction"]
    assert native["status"] == "ok", native
    assert native["sites"][0]["tir"] > 0
    assert result["status"] == "complete"
    assert native["backend"] == real_backend.identity
    assert result["components"]["promoter"]["coverage"]["scored"] == 2


def test_absolute_rbs_session_deadline_blocks_new_subprocess(monkeypatch):
    import subprocess

    backend = RnaStructure(Path("."), {"name": "deadline-test"})
    bounded = t._DeadlineBackend(backend.root, backend.identity, backend, -1.0)
    session = bounded.session(37.0, 30.0)
    assert session.deadline == -1.0
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: pytest.fail("started after deadline")
    )
    with pytest.raises(BackendError, match="folding time budget exhausted"):
        session.fold("A")


def test_rbs_finishes_then_promoter_is_deadline_skipped(backend, monkeypatch):
    ticks = iter([0.0, 1.0, 101.0])
    monkeypatch.setattr(t.time, "monotonic", lambda: next(ticks))
    result = t.predict_transcript(document(), backend)
    assert result["components"]["rbs"]["status"] == "ok"
    assert result["components"]["promoter"]["status"] == "not_evaluated"
    assert result["components"]["promoter"]["prediction"] is None
    assert result["status"] == "partial"


def test_all_incompatible_not_applicable_precedes_deadline(monkeypatch):
    request = document()
    request["transcript"]["range"] = [0, 1]
    ticks = iter([0.0, 101.0])
    monkeypatch.setattr(t.time, "monotonic", lambda: next(ticks))
    result = t.predict_transcript(request)
    assert result["components"]["rbs"]["status"] == "not_applicable"
    assert result["components"]["promoter"]["status"] == "not_evaluated"
    assert result["status"] == "unavailable"


def test_promoter_preparation_consumes_enclosing_budget(backend, monkeypatch):
    original = t.promoter_io.predict_batch

    def prepare_then_expire(*args, **kwargs):
        # The wrapper's initial clock read is the call's start, rather than
        # the later time at which the native batch finishes preparation.
        return original(*args, **kwargs)

    ticks = iter([0.0, 1.0, 10.0, 101.0, 101.0, 101.0])
    monkeypatch.setattr(t.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(t.promoter_io, "predict_batch", prepare_then_expire)
    result = t.predict_transcript(document(), backend)
    assert result["components"]["promoter"]["coverage"]["not_evaluated"] == 2


def test_no_binding_is_honestly_no_candidate(backend, monkeypatch):
    monkeypatch.setattr(SyntheticSession, "cofold", lambda *a: ())
    request = document()
    request["promoter"]["scan"] = {"mode": "positions", "positions": []}
    result = t.predict_transcript(request, backend)
    assert result["components"]["rbs"]["status"] == "no_candidate"
    assert result["components"]["rbs"]["coverage"]["scored"] == 0
    assert result["cds"][0]["scalars"]["tir"]["value"] is None


@pytest.mark.parametrize(
    "profile",
    ["historical", "footprint2017", "context2017", "standby2014", "joint_standby"],
)
def test_all_admitted_profiles_are_explicit_and_preserve_native_identity(
    backend, monkeypatch, profile
):
    monkeypatch.setattr(SyntheticSession, "cofold", lambda *a: ())
    request = document()
    request["rbs"]["profile"] = profile
    result = t.predict_transcript(request, backend)
    assert result["identities"]["rbs"]["profile"]["name"] == profile
    assert (
        result["components"]["rbs"]["prediction"]["model"]["id"]
        == t.get_profile(profile).model_id
    )


def test_maximum_cds_roster_shares_one_record(backend, monkeypatch):
    request = document()
    request["cds"] = [annotation(str(i), 30 + 3 * i, 100) for i in range(10)]
    original = t.rbs.predict
    calls = []

    def record(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(t.rbs, "predict", record)
    result = t.predict_transcript(request, backend)
    assert len(calls) == 1
    assert calls[0]["start_positions"] == list(range(10, 40, 3))
    assert result["components"]["rbs"]["coverage"]["returned"] == 10


def test_execution_failure_retains_successful_sibling(backend, monkeypatch):
    request = document()
    request["sequence"] = request["sequence"][:80] + "ATG" + request["sequence"][83:]
    request["cds"].append(annotation("failing-sibling", 80, 130))
    original = SyntheticSession.fold

    def fail_second_window(self, sequence):
        if len(sequence) == 70:
            raise BackendError("injected second-site execution failure")
        return original(self, sequence)

    monkeypatch.setattr(SyntheticSession, "fold", fail_second_window)
    result = t.predict_transcript(request, backend)
    assert result["components"]["rbs"]["status"] == "failed"
    assert [c["status"] for c in result["cds"]] == ["ok", "failed"]
    assert result["cds"][0]["scalars"]["tir"]["value"] > 0
    assert result["cds"][1]["reason"] == "injected second-site execution failure"
    assert result["cds"][1]["scalars"]["tir"]["value"] is None
    assert result["components"]["rbs"]["coverage"]["returned"] == 2
    assert result["components"]["rbs"]["coverage"]["scored"] == 1
    assert result["status"] == "partial"
