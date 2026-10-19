"""Independent constraint/CT corruption checks and bounded process integration."""

import copy
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import conditional as c
from regsite import conditional_backend as cb
from regsite.conditional_math import ConditionalError

ROOT = Path(__file__).resolve().parents[1]
SEQUENCE = "GGGAGCGAAAGCUCCC"
PAIRS = [[i, 15 - i] for i in range(6)]
PARAMETERS = json.loads(
    (ROOT / "src/regsite/data/conditional-parameters-1.json").read_bytes()
)
CANONICAL = json.loads(
    (ROOT / "benchmarks/riboswitch/canonical-fixtures.json").read_bytes()
)


def ct_bytes(sequence=SEQUENCE, pairs=None, energy=-11.2):
    pairs = PAIRS if pairs is None else pairs
    partners = {}
    for left, right in pairs:
        partners[left + 1], partners[right + 1] = right + 1, left + 1
    header = f"{len(sequence)}" + (
        " id" if energy is None else f" ENERGY = {energy} id"
    )
    rows = [
        f"{i} {base} {i - 1} {i + 1 if i < len(sequence) else 0} "
        f"{partners.get(i, 0)} {i}"
        for i, base in enumerate(sequence, 1)
    ]
    return ("\n".join([header, *rows]) + "\n").encode()


@pytest.mark.parametrize(
    "pairs,unpaired,code",
    [
        ([[0]], [], "invalid_pair"),
        ([[False, 15]], [], "invalid_position"),
        ([[0, 16]], [], "position_out_of_range"),
        ([[15, 0]], [], "pair_not_5prime_first"),
        ([[0, 15], [0, 15]], [], "duplicate_pair"),
        ([[0, 15], [0, 14]], [], "position_in_multiple_pairs"),
        ([[5, 6]], [], "hairpin_too_short"),
        ([[3, 9]], [], "noncanonical_pair"),
        ([[0, 15]], [15], "paired_and_unpaired"),
        ([], [3, 3], "duplicate_unpaired"),
    ],
)
def test_invalid_demands(pairs, unpaired, code):
    with pytest.raises(ConditionalError) as caught:
        cb.validate_demands(SEQUENCE, pairs, unpaired)
    assert caught.value.code == code


def test_crossings_adjacent_nested_and_file_boundary():
    sequence = "GGGAGCGAAAGCUCCCAAAAAAAAGCUCCC"
    with pytest.raises(ConditionalError) as caught:
        cb.validate_demands(sequence, [[0, 15], [10, 29]], [])
    assert caught.value.code == "crossing_pairs"
    assert cb.validate_demands("GAAACGAAAC", [[0, 4], [5, 9]], [])["pairs"] == [
        [0, 4],
        [5, 9],
    ]
    demand = cb.validate_demands(SEQUENCE, PAIRS[::-1], [9, 7, 8, 6])
    assert demand == dict(pairs=PAIRS, unpaired=[6, 7, 8, 9])
    assert "Pairs:\n1 16\n2 15\n" in cb.constraint_text(demand)
    assert "SS:\n7\n8\n9\n10\n-1" in cb.constraint_text(demand)
    assert (
        cb.constraint_text(dict(pairs=[], unpaired=[]))
        == "DS:\n-1\nSS:\n-1\nMod:\n-1\nPairs:\n-1 -1\nFMN:\n-1\nForbids:\n-1 -1\n"
    )


@pytest.mark.parametrize(
    "transform",
    [
        lambda s: "",
        lambda s: s.replace("16 ENERGY", "15 ENERGY"),
        lambda s: s.replace("-11.2", "nan"),
        lambda s: s.replace("-11.2", "bad"),
        lambda s: s.replace("16 ENERGY", "x ENERGY"),
        lambda s: s + "junk\n",
        lambda s: s.rsplit("\n", 2)[0],
        lambda s: s.replace("1 G 0 2 16 1", "1 G 0 2 16"),
        lambda s: s.replace("1 G 0 2 16 1", "1 G 0 2 16 x"),
        lambda s: s.replace("1 G 0 2 16 1", "2 G 0 2 16 1"),
        lambda s: s.replace("1 G 0 2 16 1", "1 g 0 2 16 1"),
        lambda s: s.replace("1 G 0 2 16 1", "1 G 1 2 16 1"),
        lambda s: s.replace("1 G 0 2 16 1", "1 G 0 0 16 1"),
        lambda s: s.replace("1 G 0 2 16 1", "1 G 0 2 17 1"),
        lambda s: s.replace("1 G 0 2 16 1", "1 G 0 2 1 1"),
        lambda s: s.replace("16 C 15 0 1 16", "16 C 15 0 0 16"),
    ],
)
def test_ct_corruption(transform):
    with pytest.raises(ConditionalError) as caught:
        cb.parse_ct(transform(ct_bytes().decode()).encode(), SEQUENCE, None)
    assert caught.value.code == "invalid_ct"


def test_ct_complete_validation():
    good = cb.parse_ct(ct_bytes(), SEQUENCE, dict(pairs=PAIRS, unpaired=[6, 7, 8, 9]))
    assert good == dict(
        structure="((((((....))))))", pairs=PAIRS, fold_energy_kcal_mol=-11.2
    )
    empty = cb.parse_ct(ct_bytes(pairs=[], energy=None), SEQUENCE, None)
    assert empty["fold_energy_kcal_mol"] is None and empty["pairs"] == []
    for demands in (dict(pairs=[[0, 15]], unpaired=[]), dict(pairs=[], unpaired=[0])):
        raw = ct_bytes(pairs=[]) if demands["pairs"] else ct_bytes()
        with pytest.raises(ConditionalError) as caught:
            cb.parse_ct(raw, SEQUENCE, demands)
        assert caught.value.code == "constraint_violated"
    for raw in (b"\xff", ct_bytes(pairs=[[0, 4]])):
        with pytest.raises(ConditionalError, match="invalid canonical CT"):
            cb.parse_ct(raw, SEQUENCE, None)
    # An integer natural-numbering column is accepted but never used as a map.
    assert (
        cb.parse_ct(
            ct_bytes().replace(b"1 G 0 2 16 1", b"1 G 0 2 16 -50"), SEQUENCE, None
        )
        == good
    )


def installation(tmp_path, monkeypatch):
    params = copy.deepcopy(PARAMETERS)
    for filename, key in (
        ("exe/Fold", "fold_sha256"),
        ("exe/efn2", "efn2_sha256"),
        ("src/algorithm.cpp", "algorithm_cpp_sha256"),
        ("ReadMe.txt", "readme_sha256"),
        ("gpl.txt", "gpl_sha256"),
    ):
        path = tmp_path / filename
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(filename.encode())
        params["backend_pins"][key] = cb.digest(path.read_bytes())
    table_dir = tmp_path / "data_tables"
    table_dir.mkdir()
    (table_dir / "rna.test").write_bytes(b"table")
    tables = {"rna.test": cb.digest(b"table")}
    manifest = tmp_path / "manifest"
    manifest.mkdir()
    (manifest / "data").mkdir()
    (manifest / "data/rnastructure-tables.json").write_bytes(cb.canonical_bytes(tables))
    monkeypatch.setattr(cb, "files", lambda _: manifest)
    params["backend_pins"]["table_manifest_sha256"] = cb.digest(
        cb.canonical_bytes(tables)
    )
    return params, manifest


def test_verify_identity_and_all_refusals(tmp_path, monkeypatch):
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    with pytest.raises(ConditionalError, match="Supply the original"):
        cb.verify_backend(None, PARAMETERS, time.monotonic() + 5)
    params, manifest = installation(tmp_path, monkeypatch)
    monkeypatch.setenv("REGSITE_RNASTRUCTURE", str(tmp_path))
    root, identity = cb.verify_backend(None, params, time.monotonic() + 5)
    assert root == tmp_path
    assert identity == {
        key: params["backend_pins"][key]
        for key in ("fold_sha256", "efn2_sha256", "table_manifest_sha256")
    }
    (tmp_path / "traceback-build.json").touch()
    with pytest.raises(ConditionalError, match="Patched"):
        cb.verify_backend(tmp_path, params, time.monotonic() + 5)
    (tmp_path / "traceback-build.json").unlink()
    (tmp_path / "exe/Fold").write_bytes(b"changed")
    with pytest.raises(ConditionalError, match="Original backend"):
        cb.verify_backend(tmp_path, params, time.monotonic() + 5)
    (tmp_path / "exe/Fold").write_bytes(b"exe/Fold")
    params["backend_pins"]["table_manifest_sha256"] = "0" * 64
    with pytest.raises(ConditionalError, match="Table manifest"):
        cb.verify_backend(tmp_path, params, time.monotonic() + 5)
    params["backend_pins"]["table_manifest_sha256"] = cb.digest(
        (manifest / "data/rnastructure-tables.json").read_bytes()
    )
    (tmp_path / "data_tables/rna.test").write_bytes(b"changed")
    with pytest.raises(ConditionalError, match="RNA table"):
        cb.verify_backend(tmp_path, params, time.monotonic() + 5)
    bounded = tmp_path / "bounded"
    bounded.write_bytes(b"1234")
    assert cb.read_bounded(bounded, 4) == b"1234"
    with pytest.raises(ConditionalError, match="byte limit"):
        cb.read_bounded(bounded, 3)


def job():
    return dict(
        program="test",
        status="failed",
        exit_code=None,
        timed_out=False,
        stdout_sha256=None,
        stderr_sha256=None,
    )


@pytest.mark.parametrize(
    "script,exit_code,code",
    [
        ("import sys; print('stdout'); print('stderr', file=sys.stderr)", 0, None),
        ("import sys; print('bad'); sys.exit(4)", 4, "backend_failed"),
        ("import os; os.write(1, b'x'*1100000)", None, "resource_limit"),
    ],
)
def test_real_process_capture(tmp_path, script, exit_code, code):
    receipt = job()
    if code is None:
        cb.run_job(Path(sys.executable), ["-c", script], tmp_path, 5, receipt)
        assert receipt["status"] == "ok"
        assert receipt["stdout_sha256"] == cb.digest(b"stdout\n")
        assert receipt["stderr_sha256"] == cb.digest(b"stderr\n")
    else:
        with pytest.raises(ConditionalError) as caught:
            cb.run_job(Path(sys.executable), ["-c", script], tmp_path, 5, receipt)
        assert caught.value.code == code
    if exit_code is not None:
        assert receipt["exit_code"] == exit_code
    assert len(receipt["stdout_sha256"]) == len(receipt["stderr_sha256"]) == 64
    assert receipt["timed_out"] is False


@pytest.mark.parametrize(
    "script",
    ["while True: pass", "import os; os.close(1); os.close(2)\nwhile True: pass"],
)
def test_process_deadline_reaps_child(tmp_path, script):
    receipt = job()
    with pytest.raises(ConditionalError) as caught:
        cb.run_job(Path(sys.executable), ["-c", script], tmp_path, 0.1, receipt)
    assert caught.value.code == "backend_timeout"
    assert receipt["timed_out"] and receipt["exit_code"] is not None
    receipt = job()
    with pytest.raises(ConditionalError, match="unavailable"):
        cb.run_job(tmp_path / "absent", [], tmp_path, 5, receipt)
    assert receipt["exit_code"] is None
    assert receipt["stdout_sha256"] == receipt["stderr_sha256"] == cb.digest(b"")


def fake_jobs(monkeypatch, energy=b"Structure: 1 Energy = -11.2\n", ct=None):
    calls = []

    def run(executable, args, root, timeout, receipt):
        calls.append((executable.name, args, timeout))
        assert 0 < timeout <= 1
        if executable.name == "Fold":
            assert Path(args[0]).read_bytes() == b">id\n" + SEQUENCE.encode() + b"\n"
            if "--constraint" in args:
                assert Path(
                    args[args.index("--constraint") + 1]
                ).read_text() == cb.constraint_text(
                    dict(pairs=PAIRS, unpaired=[6, 7, 8, 9])
                )
            Path(args[1]).write_bytes(ct_bytes() if ct is None else ct)
        else:
            Path(args[1]).write_bytes(energy)
        receipt.update(
            status="ok",
            exit_code=0,
            stdout_sha256=cb.digest(b""),
            stderr_sha256=cb.digest(b""),
        )

    monkeypatch.setattr(cb, "run_job", run)
    return calls


def test_state_flags_temp_cleanup_and_partial_energy(tmp_path, monkeypatch):
    calls = fake_jobs(monkeypatch)
    demands = dict(pairs=PAIRS, unpaired=[6, 7, 8, 9])
    state = cb.new_state("constraint_compatible", SEQUENCE, demands)
    cb.fold_state(
        tmp_path,
        SEQUENCE,
        demands,
        state,
        dict(seconds_per_job=1),
        time.monotonic() + 5,
    )
    assert state["status"] == "ok" and state["efn2_energy_kcal_mol"] == -11.2
    assert len(state["jobs"]) == 2
    assert state["constraint_sha256"] == cb.digest(cb.canonical_bytes(demands))
    assert calls[0][1][2:6] == ["--MFE", "--loop", "30", "--constraint"]
    assert calls[1][1][2:] == [
        "--simple",
        "--ne",
        "--temperature",
        "310.15",
        "--alphabet",
        "rna",
    ]
    assert not Path(calls[0][1][0]).exists()
    fake_jobs(
        monkeypatch,
        ct=ct_bytes(energy=None, pairs=[]),
        energy=b"Structure: 1 Energy = 0\n",
    )
    empty = cb.new_state("unconstrained", SEQUENCE, None)
    cb.fold_state(
        tmp_path, SEQUENCE, None, empty, dict(seconds_per_job=1), time.monotonic() + 5
    )
    assert empty["fold_energy_kcal_mol"] is None and empty["efn2_energy_kcal_mol"] == 0


@pytest.mark.parametrize(
    "energy",
    [
        b"junk",
        b"Structure: 1 Energy = nan",
        b"Structure: 1 Energy = bad",
        b"Structure: 1 Energy = 0\nStructure: 2 Energy = 0",
        b"\xff",
    ],
)
def test_bad_efn_preserves_ct(tmp_path, monkeypatch, energy):
    fake_jobs(monkeypatch, energy=energy)
    state = cb.new_state("unconstrained", SEQUENCE, None)
    with pytest.raises((ConditionalError, ValueError, UnicodeError)):
        cb.fold_state(
            tmp_path,
            SEQUENCE,
            None,
            state,
            dict(seconds_per_job=1),
            time.monotonic() + 5,
        )
    assert state["structure"] == "((((((....))))))"
    assert state["efn2_energy_kcal_mol"] is None
    assert len(state["jobs"]) == 2


def test_state_deadline_and_lock_failure(tmp_path, monkeypatch):
    state = cb.new_state("unconstrained", SEQUENCE, None)
    for deadline in (0, time.monotonic() + 5):
        monkeypatch.setattr(
            cb, "PROCESS_LOCK", SimpleNamespace(acquire=lambda **_: False)
        )
        with pytest.raises(ConditionalError, match="waiting for backend"):
            cb.fold_state(
                tmp_path, SEQUENCE, None, state, dict(seconds_per_job=1), deadline
            )
    assert state["jobs"] == []


def test_real_original_all_canonical_fixtures():
    root = os.environ.get("REGSITE_CONDITIONAL_TEST_BACKEND")
    if not root:
        pytest.skip("Set the admitted original backend for the bounded real run")
    deadline = time.monotonic() + 300
    path, identity = cb.verify_backend(root, PARAMETERS, deadline)
    assert identity == {
        key: PARAMETERS["backend_pins"][key]
        for key in ("fold_sha256", "efn2_sha256", "table_manifest_sha256")
    }
    states = {}
    expected = {
        "hairpin_unconstrained": -11.2,
        "hairpin_noop": -11.2,
        "hairpin_full": -11.2,
        "hairpin_forced_open": 0,
        "poly_a_unconstrained": 0,
        "switch_unconstrained": -12.9,
        "switch_forced_pair": -9.7,
        "switch_forced_unpaired": -9.7,
    }
    for fixture in CANONICAL["executed"]:
        sequence = fixture["sequence"]
        demands = None
        if fixture["mode"] == "full":
            data = dict(
                sequence=sequence,
                temperature_kelvin=310.15,
                aptamer=dict(
                    id="synthetic",
                    range=[0, len(sequence)],
                    constraint=dict(mode="full", structure=fixture["structure"]),
                ),
            )
            _, demands = c._structural_input(data)
        elif fixture["mode"] == "partial":
            demands = cb.validate_demands(
                sequence,
                [[p - 1 for p in pair] for pair in fixture.get("forced_pairs", [])],
                [p - 1 for p in fixture.get("forced_unpaired", [])],
            )
        state = cb.new_state("fixture", sequence, demands)
        states[fixture["id"]] = state
        if fixture["expected_status"] == "not_ok":
            with pytest.raises(ConditionalError) as caught:
                cb.fold_state(
                    path, sequence, demands, state, dict(seconds_per_job=30), deadline
                )
            assert caught.value.code == "backend_failed"
            assert state["structure"] is None
        else:
            cb.fold_state(
                path, sequence, demands, state, dict(seconds_per_job=30), deadline
            )
            assert state["efn2_energy_kcal_mol"] == expected[fixture["id"]]
            if "expected_pairs" in fixture:
                assert state["pairs"] == [
                    [p - 1 for p in pair] for pair in fixture["expected_pairs"]
                ]
    assert sum(len(state["jobs"]) for state in states.values()) <= 19
    assert states["hairpin_forced_open"]["fold_energy_kcal_mol"] is None
    for relation in CANONICAL["relations"]:
        left, right = (states[name] for name in relation["cases"])
        if relation["kind"] == "same_structure_and_energy":
            assert (left["structure"], left["efn2_energy_kcal_mol"]) == (
                right["structure"],
                right["efn2_energy_kcal_mol"],
            )
        elif relation["kind"] == "different_pairs":
            assert left["pairs"] != right["pairs"]
        else:
            assert left["efn2_energy_kcal_mol"] >= right["efn2_energy_kcal_mol"]
    examples = json.loads(
        (ROOT / "benchmarks/riboswitch/conditional-request-examples.json").read_bytes()
    )
    request = examples["cases"][0]["request"]
    request["settings"] = dict(seconds_per_job=30, seconds_total=120)
    result = c.predict_conditional(request, root)
    assert result["status"] == "ok" and result["complete"]
    assert result["structural_cost_kcal_mol"] == 0
    assert result["response"] is None
    assert len(result["states"]) == 2
    assert sum(len(state["jobs"]) for state in result["states"]) == 4


def test_no_process_after_deadline(tmp_path):
    receipt = job()
    with pytest.raises(ConditionalError, match="No time remains"):
        cb.run_job(Path(sys.executable), [], tmp_path, 0, receipt)
    assert receipt["exit_code"] is None


@pytest.mark.parametrize("fixture", CANONICAL["rejected"], ids=lambda f: f["id"])
def test_frozen_canonical_refusals(fixture):
    examples = json.loads(
        (ROOT / "benchmarks/riboswitch/conditional-request-examples.json").read_bytes()
    )
    document = examples["cases"][0]["request"]
    sequence = fixture["sequence"]
    mode = fixture["mode"]
    if mode == "full":
        constraint = dict(mode=mode, structure=fixture["structure"])
    elif mode in ("partial", "unconstrained"):

        def point(value):
            return value if type(value) is bool else value - 1

        constraint = dict(
            mode="partial",
            pairs=[
                [point(p) for p in pair] for pair in fixture.get("forced_pairs", [])
            ],
            unpaired=[point(p) for p in fixture.get("forced_unpaired", [])],
        )
        if fixture["id"] == "constraint_on_unconstrained":
            constraint["forced_pairs"] = fixture["forced_pairs"]
    else:
        constraint = dict(mode=mode)
    document["input"] = dict(
        sequence=sequence,
        temperature_kelvin=310.15,
        aptamer=dict(id="synthetic", range=[0, len(sequence)], constraint=constraint),
    )
    result = c.predict_conditional(document)
    assert result["reasons"] == [fixture["expected_error"]]
    assert not result["complete"] and result["states"] == []
