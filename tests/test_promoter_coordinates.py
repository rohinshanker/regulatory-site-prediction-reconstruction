"""Coordinate properties checked against independent per-base enumeration."""

import itertools

import pytest

from regsite import promoter as p


@pytest.mark.parametrize(
    "topology,seq_strand,origin,site,f,interval,base,gstrand,runs",
    [
        ("linear", "+", 500, "+", 100, (65, 71), 600, "+", [(565, 571)]),
        ("linear", "+", 500, "-", 129, (166, 190), 629, "-", [(666, 690)]),
        ("linear", "-", 700, "+", 100, (65, 71), 600, "-", [(630, 636)]),
        ("linear", "-", 700, "-", 129, (166, 190), 571, "+", [(511, 535)]),
        ("circular", "+", 950, "+", 100, (40, 64), 50, "+", [(990, 1000), (0, 14)]),
        ("circular", "+", 830, "-", 129, (166, 190), 959, "-", [(0, 20), (996, 1000)]),
        ("circular", "-", 50, "+", 100, (40, 64), 950, "-", [(0, 11), (987, 1000)]),
        ("circular", "-", 180, "-", 129, (166, 190), 51, "+", [(991, 1000), (0, 15)]),
    ],
)
def test_eight_worked_projections(
    topology, seq_strand, origin, site, f, interval, base, gstrand, runs
):
    projection = p.check_projection(
        dict(
            contig="x",
            contig_length=1000,
            origin=origin,
            sequence_strand=seq_strand,
            topology=topology,
            origin_crossing=topology == "circular",
        ),
        200,
    )
    assert p.project_base(projection, f) == base
    assert p.project_interval(projection, site, interval) == (gstrand, runs)
    params = p.load_parameters()
    result = p.score_site(
        "ACGT" * 50,
        site,
        f,
        params,
        p.resolve_calibration("in_vitro"),
        keep_states=True,
    )
    data = result.to_dict(projection=projection)
    assert data["genomic"] == dict(
        contig="x", base=base, strand=gstrand, sequence_strand=seq_strand
    )
    for state in [data["selected"], *data["states"]]:
        for name, bounds in state["intervals"].items():
            assert state["genomic_intervals"][name] == [
                list(r) for r in p.project_interval(projection, site, tuple(bounds))[1]
            ]


def test_brute_force_small_contig_projection():
    for size in range(1, 13):
        for length in range(1, min(size, 8) + 1):
            for origin, sequence_strand, site_strand in itertools.product(
                range(size), "+-", "+-"
            ):
                direction = 1 if sequence_strand == "+" else -1
                crosses = origin + direction * (length - 1) not in range(size)
                projection = p.check_projection(
                    dict(
                        contig="x",
                        contig_length=size,
                        origin=origin,
                        sequence_strand=sequence_strand,
                        topology="circular",
                        origin_crossing=crosses,
                    ),
                    length,
                )
                for f in range(length):
                    assert (
                        p.project_base(projection, f) == (origin + direction * f) % size
                    )
                for a in range(length):
                    for b in range(a + 1, length + 1):
                        strand, runs = p.project_interval(
                            projection, site_strand, (a, b)
                        )
                        expected_strand = (
                            "+"
                            if direction * (1 if site_strand == "+" else -1) == 1
                            else "-"
                        )
                        assert strand == expected_strand
                        local_order = (
                            range(a, b)
                            if site_strand == "+"
                            else range(b - 1, a - 1, -1)
                        )
                        expected = [
                            (origin + direction * f) % size for f in local_order
                        ]
                        actual = []
                        for start, end in runs:
                            assert 0 <= start < end <= size
                            actual.extend(
                                range(start, end)
                                if strand == "+"
                                else range(end - 1, start - 1, -1)
                            )
                        assert actual == expected
                if not crosses:
                    linear = p.check_projection(
                        {**projection, "topology": "linear"}, length
                    )
                    assert p.project_interval(
                        linear, site_strand, (0, length)
                    ) == p.project_interval(projection, site_strand, (0, length))


def test_reference_windows_and_legacy_key():
    expected = {
        "UP": (40, 64),
        "gap": (64, 65),
        "hex35": (65, 71),
        "spacer": (71, 88),
        "extended10": (85, 87),
        "hex10": (88, 94),
        "discriminator": (94, 100),
        "itr": (100, 120),
    }
    assert p.state_windows(100, 6, 17) == expected
    assert p.oriented_to_local_base(200, "-", 70) == 129
    assert p.legacy_source_key(200, "-", 70) == 130
    assert p.legacy_source_key(200, "+", 70) == 70
    assert p.oriented_to_local_interval(200, "-", (10, 34)) == (166, 190)
    assert p.oriented_to_local_base(200, "-", 99) == 100
    assert p.legacy_source_key(200, "-", 99) == 101


def test_lengths_edges_and_reverse_complement_properties():
    params = p.load_parameters()
    calibration = p.resolve_calibration("in_vitro")
    for length in [*range(78, 121), 200]:
        sequence = ("ACGTAGCAATGTCGGT" * 13)[:length]
        reverse = p.orient(sequence, "-")
        eligible = {"+": [], "-": []}
        for f in range(length):
            plus = p.score_site(
                reverse, "+", length - 1 - f, params, calibration, keep_states=True
            )
            minus = p.score_site(
                sequence, "-", f, params, calibration, keep_states=True
            )
            assert plus.selected == minus.selected and plus.states == minus.states
            assert minus.oriented_base == length - 1 - f
            for strand in "+-":
                t = f if strand == "+" else length - 1 - f
                states = p.eligible_states(length, t)
                if states:
                    eligible[strand].append(f)
                assert (len(states) == 30) == (67 <= t <= length - 20)
                if states:
                    d, s = states[-1]
                    w = p.state_windows(t, d, s)
                    assert w["UP"][0] >= 0 and w["itr"][1] <= length
                    assert w["gap"][1] - w["gap"][0] == 1
        assert eligible["+"] == list(range(58, length - 19))
        assert eligible["-"] == list(range(19, length - 58))
        if length == 200:
            assert len(eligible["+"]) == len(eligible["-"]) == 123
        for a in range(length + 1):
            for b in range(a, length + 1):
                mapped = p.oriented_to_local_interval(length, "-", (a, b))
                assert p.oriented_to_local_interval(length, "-", mapped) == (a, b)
                assert p.oriented_to_local_interval(length, "+", (a, b)) == (a, b)
    assert [len(p.eligible_states(200, t)) for t in range(56, 60)] == [0, 0, 1, 3]
    assert len(p.eligible_states(77, 57)) == 0
    assert len(p.eligible_states(78, 58)) == 1
    assert len(p.eligible_states(87, 67)) == 30
    assert len(p.eligible_states(200, 180)) == 30
    assert len(p.eligible_states(200, 181)) == 0
    for count in (1, 4, 17, 100):
        assert all(
            len(p.eligible_states(count + 86, t)) == 30 for t in range(67, 67 + count)
        )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"unknown": 1}, "invalid_projection"),
        ({"contig": ""}, "invalid_projection"),
        ({"contig": 4}, "invalid_projection"),
        ({"contig": "x" * 129}, "invalid_projection"),
        ({"sequence_strand": "?"}, "invalid_projection"),
        ({"topology": "x"}, "invalid_projection"),
        ({"origin_crossing": 1}, "invalid_projection"),
        ({"contig_length": None}, "invalid_projection"),
        ({"contig_length": 0}, "invalid_projection"),
        ({"origin": True}, "invalid_projection"),
        ({"origin": 100}, "invalid_projection"),
        ({"origin": -1}, "invalid_projection"),
        ({"origin": 90}, "invalid_projection"),
        ({"sequence_strand": "-", "origin": 5}, "invalid_projection"),
        ({"origin_crossing": True}, "invalid_projection"),
        ({"topology": "circular", "origin": 90}, "undeclared_origin_crossing"),
        ({"topology": "circular", "origin_crossing": True}, "origin_crossing_mismatch"),
        ({"contig_length": 19, "topology": "circular"}, "invalid_projection"),
    ],
)
def test_projection_failures(changes, code):
    projection = dict(contig="x", contig_length=100, origin=10, topology="linear")
    with pytest.raises(p.InputError, match=code):
        p.check_projection({**projection, **changes}, 20)


def test_projection_direct_boundaries():
    with pytest.raises(p.InputError, match="invalid_projection"):
        p.check_projection(None, 20)
    for interval in ((4, 3), (0, 11), (-1, 2)):
        with pytest.raises(p.InputError):
            p.oriented_to_local_interval(10, "+", interval)
    for point in (-1, 10, True):
        with pytest.raises(p.InputError):
            p.oriented_to_local_base(10, "+", point)
    assert p.oriented_to_local_base(10, "+", 0) == 0
    projection = p.check_projection(
        dict(contig="x", contig_length=100.0, origin=0.0, topology="linear"), 20
    )
    assert (
        type(projection["origin"]) is int and type(projection["contig_length"]) is int
    )
    assert (
        projection["sequence_strand"] == "+" and projection["origin_crossing"] is False
    )
    assert p.project_base(projection, 0) == 0
    assert p.project_interval(projection, "+", (0, 0)) == ("+", [(0, 0)])
