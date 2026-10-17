"""Backend boundaries plus independently prepared real-engine smoke fixtures."""

import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from regsite import backend
from regsite.backend import FoldingSession, RnaStructure
from regsite.structures import BackendError, parse_ct, to_ct


@pytest.fixture
def folding(tmp_path):
    return FoldingSession(tmp_path, 310.15, time.monotonic() + 60)


def test_run_environment_and_version_exit(monkeypatch, tmp_path):
    def run(command, **kwargs):
        assert command == [str(tmp_path / "Fold"), "--version"]
        assert kwargs["env"]["DATAPATH"] == str(tmp_path)
        assert kwargs["env"]["OMP_NUM_THREADS"] == "1"
        assert kwargs["timeout"] == 5
        return SimpleNamespace(returncode=1, stdout="version")

    monkeypatch.setattr(subprocess, "run", run)
    assert backend._run(tmp_path / "Fold", ["--version"], tmp_path, 5) == "version"


@pytest.mark.parametrize(
    "error", [OSError(), subprocess.TimeoutExpired("Fold", 1), UnicodeError()]
)
def test_process_errors(monkeypatch, tmp_path, error):
    def run(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(BackendError, match="unavailable or timed out"):
        backend._run(tmp_path / "Fold", [], tmp_path, 1)


def test_exit_and_exhausted_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=2)
    )
    with pytest.raises(BackendError, match="exit 2"):
        backend._run(tmp_path / "Fold", [], tmp_path, 1)
    with pytest.raises(BackendError, match="budget exhausted"):
        backend._run(tmp_path / "Fold", [], tmp_path, 0)


def test_open_verifies_all_tables_and_tools(monkeypatch, tmp_path):
    manifest = json.loads(Path("src/regsite/data/rnastructure-tables.json").read_text())
    monkeypatch.setattr(
        backend, "_sha256", lambda p: manifest.get(p.name, "binary-hash")
    )
    monkeypatch.setattr(backend, "_run", lambda *a: "Fold: Version 6.6 (date).")
    opened = RnaStructure.open(tmp_path)
    assert set(opened.identity["binary_sha256"]) == {"Fold", "bifold", "efn2"}
    assert (
        opened.identity["table_manifest_sha256"]
        == "ece4c4b535783cb4e03c7ce8f243d09be84a165ecd113b1d20941b5ed8b69501"
    )
    assert opened.session(37).kelvin == 310.15
    for seconds, temp in [(0, 37), (121, 37), (float("nan"), 37), (1, 101)]:
        with pytest.raises(BackendError, match="invalid folding"):
            opened.session(temp, seconds)
    monkeypatch.setattr(backend, "_run", lambda *a: "Version 6.5")
    with pytest.raises(BackendError, match="not RNAstructure 6.6"):
        RnaStructure.open(tmp_path)
    monkeypatch.setattr(backend, "_sha256", lambda p: "wrong")
    with pytest.raises(BackendError, match="hash mismatch"):
        RnaStructure.open(tmp_path)
    monkeypatch.undo()
    with pytest.raises(BackendError, match="incomplete"):
        RnaStructure.open(tmp_path)


def test_output_checks(folding, tmp_path):
    path = tmp_path / "result"
    with pytest.raises(BackendError, match="missing or unreadable"):
        folding._read(path)
    path.write_text("x" * 2_000_001)
    with pytest.raises(BackendError, match="resource limit"):
        folding._read(path)
    path.write_bytes(b"\xff")
    with pytest.raises(BackendError, match="missing or unreadable"):
        folding._read(path)


def test_evaluate_fixed_structure(monkeypatch, folding):
    def call(self, program, args):
        assert program == "efn2"
        assert "--simple" in args and "--ne" in args
        assert parse_ct(Path(args[0]).read_text(), "ACGU")[0].pairs == (3, 2, 1, 0)
        Path(args[1]).write_text("Structure: 1 Energy = -2.5\n")

    monkeypatch.setattr(FoldingSession, "_call", call)
    assert folding.evaluate("ACGU", (3, 2, 1, 0)).energy == -2.5
    for seq in ["", "A" * 213]:
        with pytest.raises(BackendError, match="supported window"):
            folding.evaluate(seq, (-1,) * len(seq))


@pytest.mark.parametrize(
    "output", ["garbage", "Structure: 1 Energy = nan", "Structure: 1 Energy = wrong"]
)
def test_bad_energy_is_not_zero(monkeypatch, folding, output):
    monkeypatch.setattr(
        FoldingSession, "_call", lambda self, p, a: Path(a[1]).write_text(output)
    )
    with pytest.raises(BackendError, match="efn2 energy"):
        folding.evaluate("AAAA", (-1,) * 4)


def test_fold_missing_energy_reevaluated(monkeypatch, folding):
    def call(self, program, args):
        output = (
            to_ct("AAAA", (-1,) * 4) if program == "Fold" else "Structure: 1 Energy = 0"
        )
        Path(args[1]).write_text(output)

    monkeypatch.setattr(FoldingSession, "_call", call)
    assert folding.fold("").energy == 0
    assert folding.fold("AAAA").energy == 0
    for sequence in ["N", "A" * 201]:
        with pytest.raises(BackendError, match="normalized RNA"):
            folding.fold(sequence)
    monkeypatch.setattr(
        FoldingSession,
        "_call",
        lambda self, p, a: Path(a[1]).write_text(to_ct("AAAA", (-1,) * 4) * 2),
    )
    with pytest.raises(BackendError, match="more than one"):
        folding.fold("AAAA")


def test_cofold_missing_energy_and_limits(monkeypatch, folding):
    def call(self, program, args):
        if program == "bifold":
            assert (
                "--intramolecular" not in args
            )  # This flag would DISABLE intramolecular pairs.
            Path(args[2]).write_text(to_ct("AAAAIIIACCUCCUUA", (-1,) * 16))
        else:
            Path(args[1]).write_text("Structure: 1 Energy = 0")

    monkeypatch.setattr(FoldingSession, "_call", call)
    assert folding.cofold("AAAA", "ACCUCCUUA")[0].energy == 0
    for leader, asd in [
        ("", "ACCUCCUUA"),
        ("A" * 101, "ACCUCCUUA"),
        ("AAAA", "A"),
        ("N", "ACCUCCUUA"),
    ]:
        with pytest.raises(BackendError, match="cofold expects"):
            folding.cofold(leader, asd)


def test_call_total_budget(monkeypatch, folding):
    calls = []
    monkeypatch.setattr(backend, "_run", lambda *args: calls.append(args))
    replace(folding, deadline=time.monotonic() + 1)._call("Fold", ["a", "b"])
    assert 0 < calls[0][-1] <= 1
    assert calls[0][1][-4:] == ["--temperature", "310.15", "--alphabet", "rna"]


def test_independent_engine_fixtures(real_backend):
    fixture = json.loads(
        Path("benchmarks/rbs/rnastructure-smoke-fixtures.json").read_text()
    )
    session = real_backend.session(37)
    hairpin = session.fold(fixture["inputs"]["hairpin"])
    assert hairpin.energy == -1.2
    assert [[i + 1, j + 1] for i, j in enumerate(hairpin.pairs) if i < j] == fixture[
        "observations"
    ][0]["base_pairs_1based"]
    assert (
        session.evaluate(hairpin.sequence, hairpin.pairs).energy
        == fixture["hairpin_efn2_kcal_mol"]
    )
    poly_a = session.fold(fixture["inputs"]["poly_a"])
    assert poly_a.energy == 0 and set(poly_a.pairs) == {-1}
    duplex = session.cofold(fixture["inputs"]["sd"], fixture["inputs"]["asd"])[0]
    assert duplex.energy == -11.6
    assert [[i + 1, j + 1] for i, j in enumerate(duplex.pairs) if i < j] == fixture[
        "observations"
    ][2]["base_pairs_1based"]
    assert session.evaluate(duplex.sequence, duplex.pairs).energy == duplex.energy


def test_batch_energy_rejects_count_and_index_corruption(monkeypatch, folding):
    from regsite.structures import Structure

    with pytest.raises(BackendError, match="structure count"):
        folding._evaluate_many(())
    monkeypatch.setattr(
        FoldingSession, "_call", lambda self, p, a: Path(a[1]).write_text("")
    )
    with pytest.raises(BackendError, match="count mismatch"):
        folding.evaluate("AAAA", (-1,) * 4)
    monkeypatch.setattr(
        FoldingSession,
        "_call",
        lambda self, p, a: Path(a[1]).write_text("Structure: 2 Energy = -1"),
    )
    with pytest.raises(BackendError, match="efn2 energy"):
        folding.evaluate("AAAA", (-1,) * 4)
    monkeypatch.setattr(
        FoldingSession,
        "_call",
        lambda self, p, a: Path(a[1]).write_text(
            "Structure: 1 Energy = -1\nStructure: 2 Energy = -3\n"
        ),
    )
    structures = (Structure("AAAA", (-1,) * 4, -2), Structure("CCCC", (-1,) * 4, -4))
    results = folding._evaluate_many(structures)
    assert [s.energy for s in results] == [-1, -3]
    assert [s.prediction_energy for s in results] == [-2, -4]


def test_real_mfe_only_short_prefix_regression(real_backend):
    # With --maximum 1 --window 0, 6.6 emits BOTH an unpaired structure and a
    # positive-energy paired structure. --MFE emits only the actual minimum.
    structure = real_backend.session(37).fold("UUAAGUUCUUUGCAAG")
    assert structure.energy == 0
    assert set(structure.pairs) == {-1}


def test_real_expanded_window_exact_limits(real_backend):
    session = real_backend.session(37)
    folded = session.fold("A" * 200)
    assert folded.energy == 0
    assert len(folded.pairs) == 200
    joined = "A" * 200 + "III" + "ACCUCCUUA"
    evaluated = session.evaluate(joined, (-1,) * 212)
    assert len(evaluated.pairs) == 212
    assert evaluated.energy is not None
