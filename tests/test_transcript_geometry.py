"""Hand-checkable interval exports and rejection of contradictory native geometry."""

import pytest

from regsite import transcript_geometry as g


@pytest.mark.parametrize(
    "bounds", [None, [], [1], [1, 2, 3], [True, 2], [-1, 2], [3, 2], [0, 11]]
)
def test_invalid_interval(bounds):
    with pytest.raises(g.GeometryError):
        g.interval(bounds, 10)


def test_null_and_empty_boundary_intervals():
    projection = {
        "contig": "c",
        "origin": 0,
        "contig_length": 10,
        "sequence_strand": "+",
    }
    missing = g.feature(None, length=10, offset=0, strand="+", projection=projection)
    assert missing["reason"] == "feature_unavailable" and missing["genomic"] is None
    empty = g.feature([10, 10], length=10, offset=0, strand="+", projection=projection)
    assert empty["native_interval"] == empty["construct_interval"] == [10, 10]
    assert empty["genomic"]["runs"] == []


@pytest.mark.parametrize(
    "raw", [{}, {"start": 0, "end": 1}, {"start": 0, "end": 1, "strand": "-"}, []]
)
def test_invalid_native_rbs_interval(raw):
    with pytest.raises(g.GeometryError):
        g.rbs_features({"start_codon": raw}, 10, 0, None)


def test_downstream_hairpin_and_empty_standby_are_preserved():
    raw = {"start": 0, "end": 0, "strand": "+"}
    site = {
        "start_codon": {"start": 1, "end": 4, "strand": "+"},
        "window": {"input_interval": {"start": 0, "end": 10, "strand": "+"}},
        "standby": {"distal": raw, "downstream_hairpins": [{"interval": raw}]},
    }
    features = g.rbs_features(site, 10, 5, None)
    assert features["standby.distal"]["construct_interval"] == [5, 5]
    assert features["standby.downstream_hairpins.0"]["native_interval"] == [0, 0]
    for window in (None, {}):
        site["window"] = window
        with pytest.raises(g.GeometryError, match="window"):
            g.rbs_features(site, 10, 0, None)


@pytest.mark.parametrize(
    "local_strand,sequence_strand,expected",
    [
        ("+", "+", [[8, 10], [0, 2]]),
        ("-", "+", [[0, 2], [8, 10]]),
        ("+", "-", [[0, 2], [8, 10]]),
        ("-", "-", [[8, 10], [0, 2]]),
    ],
)
def test_circular_runs_follow_site_direction(local_strand, sequence_strand, expected):
    projection = {
        "contig": "c",
        "origin": 8 if sequence_strand == "+" else 1,
        "contig_length": 10,
        "sequence_strand": sequence_strand,
    }
    mapped = g.feature(
        [0, 4], length=4, offset=0, strand=local_strand, projection=projection
    )
    assert mapped["genomic"]["runs"] == expected
