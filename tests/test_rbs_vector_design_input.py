"""Strict input, coordinate, roster and complete-neighborhood admission."""

import copy

import pytest
from test_rbs_vector_design import Backend, example

from regsite import rbs_vector_design as module


@pytest.mark.parametrize("key", sorted(module.FIELDS))
def test_every_wrapper_field_required(key):
    value = example()
    del value[key]
    assert module.design(value, Backend())["reason"] == "request_fields"


@pytest.mark.parametrize(
    "path,bad",
    [
        (("schema_version",), "wrong"),
        (("profile",), "unknown"),
        (("profile",), {}),
        (("rbs",), None),
        (("rbs", "anti_sd"), "A"),
        (("rbs", "sequence"), "acgt"),
        (("rbs", "sequence"), "A" * 10001),
        (("rbs", "sequence"), " A" * 50),
        (("rbs", "sequence"), "U" * 98),
        (("rbs", "temperature_c"), True),
        (("cds",), None),
        (("cds",), []),
        (("cds",), [{}] * 11),
        (("cds", 0), None),
        (("cds", 0, "id"), ""),
        (("cds", 0, "id"), True),
        (("cds", 0, "id"), "a" * 129),
        (("cds", 0, "id"), "bad\x00"),
        (("cds", 0, "id"), "bad\x7f"),
        (("cds", 1, "id"), "first"),
        (("cds", 0, "start"), True),
        (("cds", 0, "start"), 30.0),
        (("cds", 0, "start"), 0),
        (("cds", 0, "start"), -1),
        (("cds", 0, "end"), True),
        (("cds", 0, "end"), 48.0),
        (("cds", 0, "end"), 31),
        (("cds", 0, "end"), 97),
        (("cds", 0, "end"), 10002),
        (("rbs", "start_positions"), None),
        (("rbs", "start_positions"), []),
        (("rbs", "start_positions"), [30]),
        (("rbs", "start_positions"), [65, 30]),
        (("rbs", "start_positions"), [30.0, 65]),
        (("rbs", "start_positions"), [True, 65]),
        (("target_tirs",), None),
        (("target_tirs",), []),
        (("target_tirs",), [1]),
        (("target_tirs",), [1, 2, 3]),
        (("target_tirs", 0), True),
        (("target_tirs", 0), 0),
        (("target_tirs", 0), -1),
        (("target_tirs", 0), "1"),
        (("target_tirs", 0), float("inf")),
        (("target_tirs", 0), float("nan")),
        (("target_tirs", 0), 10**400),
        (("editable_positions",), None),
        (("editable_positions",), [True]),
        (("editable_positions",), [55.0]),
        (("editable_positions",), [55, 55]),
        (("editable_positions",), [-1]),
        (("editable_positions",), [98]),
        (("editable_positions",), [95]),
        (("editable_positions",), [30]),
        (("editable_positions",), [47]),
        (("editable_positions",), [65]),
        (("max_changes",), True),
        (("max_changes",), 1.0),
        (("max_changes",), -1),
        (("max_changes",), 3),
        (("max_changes",), 2),
        (("limits",), {}),
        (("limits",), None),
        (("limits", "max_candidates"), True),
        (("limits", "max_candidates"), 4.0),
        (("limits", "max_candidates"), 0),
        (("limits", "max_candidates"), 65),
        (("limits", "max_candidates"), 3),
        (("limits", "seconds_per_score"), True),
        (("limits", "seconds_per_score"), 0),
        (("limits", "seconds_per_score"), 30.1),
        (("limits", "seconds_per_score"), "20"),
        (("limits", "seconds_total"), False),
        (("limits", "seconds_total"), -1),
        (("limits", "seconds_total"), 600.1),
        (("limits", "seconds_total"), float("nan")),
    ],
    ids=lambda value: str(value)[:80],
)
def test_bad_controls_never_open_or_score(path, bad, monkeypatch):
    value = example()
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = copy.deepcopy(bad)
    monkeypatch.setattr(
        module.rbs, "predict", lambda *a, **kw: pytest.fail("scored invalid input")
    )
    result = module.design(value, Backend())
    assert result["status"] == "invalid_input" and result["reason"]
    assert result["candidates"] == result["targets"] == []
    assert result["model"] is None and result["coverage"] is None


def test_extra_fields_start_order_and_unsupported_codon():
    for scope in ((), ("rbs",), ("cds", 0), ("limits",)):
        value = example()
        target = value
        for key in scope:
            target = target[key]
        target["extra"] = 1
        assert module.design(value, Backend())["status"] == "invalid_input"
    value = example()
    value["cds"] = value["cds"][::-1]
    assert module.design(value, Backend())["reason"] == "cds_order"
    value = example()
    value["cds"][1] = dict(value["cds"][0], id="another")
    assert module.design(value, Backend())["reason"] == "cds_order"
    value = example()
    s = value["rbs"]["sequence"]
    value["rbs"]["sequence"] = s[:30] + "AAA" + s[33:]
    assert module.design(value, Backend())["reason"] == "supported_start_required"
    assert module.design(None, Backend())["status"] == "invalid_input"


def test_half_open_end_and_maximum_sequence_length():
    value = example()
    value["editable_positions"] = [48]
    assert module.parse_request(value).positions == (48,)
    value["rbs"]["sequence"] += "A" * (10000 - len(value["rbs"]["sequence"]))
    assert len(module.parse_request(value).native.sequence) == 10000
