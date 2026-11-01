"""Independent parameter conversion, corruption, and safe-parser checks."""

import hashlib
import itertools
import json
import math
import runpy
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from regsite import promoter as p
from tools import derive_promoter_parameters as derivation

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "benchmarks/promoter/source-manifest.json"
PARAMS = ROOT / "src/regsite/data/promoter-parameters-1.json"


def test_frozen_parameters_bit_equal_independent_oracle():
    actual = json.loads(PARAMS.read_text())
    expected = json.loads(
        (ROOT / "benchmarks/promoter/reference-parameters.json").read_text()
    )
    assert actual == expected
    for a, b in zip(actual["coefficients"], expected["coefficients"], strict=True):
        assert struct.pack("<d", a) == struct.pack("<d", b)
    assert (
        hashlib.sha256(derivation.canonical_bytes(actual)).hexdigest()
        == p.PARAMETER_JSON_SHA256
    )
    assert p.load_parameters().unused_indices == (336, 337, 338)
    with pytest.raises(TypeError):
        p.load_parameters().tables["persistence"]["AA"] = 1
    assert (ROOT / "src/regsite/data/promoter-ORIGINAL-NOTICE.txt").read_bytes() == (
        ROOT / "benchmarks/promoter/ORIGINAL-NOTICE"
    ).read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    assert {
        Path(e["path"]).name: e["sha256"] for e in manifest["sources"]
    } == derivation.SOURCE_HASHES
    assert manifest["historical_commit"] == derivation.SOURCE_COMMIT == p.SOURCE_COMMIT


BAD_PARAMETERS = [
    None,
    [],
    {},
    {"extra": 1},
    ("coefficients", None),
    ("coefficients", [0] * 342),
    ("coefficients", [0] * 342 + [None]),
    ("coefficients", [0] * 342 + [True]),
    ("coefficients", [0] * 342 + [math.nan]),
    ("normalizers", [0] * 4),
    ("normalizers", [1, 2, 3]),
    ("intercept", "bad"),
    ("intercept", math.inf),
    ("tables", None),
    ("tables", {}),
    ("array_sha256", {}),
    ("source_commit", "bad"),
    ("license", "bad"),
    ("intercept", 0.0),
]


@pytest.mark.parametrize("mutation", BAD_PARAMETERS)
def test_bad_parameter_shapes_and_identity(tmp_path, mutation):
    data = json.loads(PARAMS.read_text())
    if isinstance(mutation, tuple):
        data[mutation[0]] = mutation[1]
    else:
        data = mutation
    package = tmp_path / "data"
    package.mkdir()
    (package / PARAMS.name).write_text(json.dumps(data))
    with patch.object(p, "files", return_value=tmp_path):
        with pytest.raises(p.ParameterError):
            p.load_parameters()


@pytest.mark.parametrize("mutation", [None, {}, {"ZZ": 2}, "nan", "bool"])
def test_bad_parameter_tables(tmp_path, mutation):
    data = json.loads(PARAMS.read_text())
    table = data["tables"]["groove_access"]
    if mutation == "nan":
        table["AA"] = math.nan
    elif mutation == "bool":
        table["AA"] = True
    else:
        data["tables"]["groove_access"] = mutation
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / PARAMS.name).write_text(json.dumps(data))
    with patch.object(p, "files", return_value=tmp_path):
        with pytest.raises(p.ParameterError):
            p.load_parameters()


@pytest.mark.parametrize("raw", [None, "{", '{"x":1,"x":2}', "\ud800"])
def test_parameter_read_errors(tmp_path, raw):
    (tmp_path / "data").mkdir()
    if raw is not None:
        (tmp_path / "data" / PARAMS.name).write_text(
            raw, encoding="utf-8", errors="surrogatepass"
        )
    with patch.object(p, "files", return_value=tmp_path):
        with pytest.raises(p.ParameterError):
            p.load_parameters()


def npy(values, header=None, version=b"\x01\x00"):
    if header is None:
        header = {"descr": "<f8", "fortran_order": False, "shape": (len(values),)}
    header = (repr(header) + "\n").encode("ascii")
    return (
        b"\x93NUMPY"
        + version
        + struct.pack("<H", len(header))
        + header
        + struct.pack(f"<{len(values)}d", *values)
    )


@pytest.mark.parametrize(
    "data,count,match",
    [
        (b"", 1, "version"),
        (b"\x00" * 10, 1, "version"),
        (npy([1], version=b"\x02\x00"), 1, "version"),
        (b"\x93NUMPY\x01\x00\xff\xff", 1, "Truncated"),
        (
            npy([1], header={"descr": ">f8", "fortran_order": False, "shape": (1,)}),
            1,
            "layout",
        ),
        (npy([1]), 2, "layout"),
        (npy([1]) + b"x", 1, "payload"),
        (npy([1])[:-1], 1, "payload"),
        (npy([math.inf]), 1, "Nonfinite"),
    ],
)
def test_npy_rejects(data, count, match):
    with pytest.raises(ValueError, match=match):
        derivation.read_npy(data, count)


def test_npy_bit_identity():
    values = [0.0, -0.0, math.nextafter(1.0, 2.0), -0.9583584537583338]
    result = derivation.read_npy(npy(values), 4)
    assert struct.pack("<4d", *result) == struct.pack("<4d", *values)


def table_source():
    dimers = {"".join(k): i for i, k in enumerate(itertools.product("ACGT", repeat=2))}
    return "\n".join(f"{name} = {dimers!r}" for name in derivation.TABLE_NAMES)


def test_literal_extraction_does_not_execute():
    source = (
        "import nonexistent\nraise RuntimeError('do not execute')\n"
        "ignored=0\na,b=(1,2)\n" + table_source()
    )
    tables = derivation.literal_tables(source)
    assert (
        len(tables) == 4
        and tables["groove_access"]["AA"] == 0
        and tables["persistence"]["TT"] == 15
    )
    assert derivation.literal_normalizers(
        "print x\n    normalizing_values = [1.0, 2.0, 3.0, 4.0]"
    ) == [1.0, 2.0, 3.0, 4.0]
    with pytest.raises(ValueError):
        derivation.literal_tables("groove_access = __import__('os').environ")


@pytest.mark.parametrize(
    "source,match",
    [
        ("", "Missing"),
        (table_source() + "\ngroove_access = {}", "Duplicate"),
        (table_source().replace("'AA': 0", "'ZZ': 0"), "Invalid dimer"),
        (table_source().replace("'AA': 0", "'AA': None"), "Invalid table number"),
        (table_source().replace("'AA': 0", "'AA': True"), "Invalid table number"),
        (table_source() + "\ngroove_access = 1", "Duplicate"),
    ],
)
def test_literal_tables_reject(source, match):
    with pytest.raises(ValueError, match=match):
        derivation.literal_tables(source)


@pytest.mark.parametrize(
    "source",
    [
        "",
        "normalizing_values = [1.0,2.0,3.0,4.0]\nnormalizing_values = [1.0]",
        "normalizing_values = [1.0,2.0,3.0]",
        "normalizing_values = [1.0,2.0,3.0,0.0]",
        "normalizing_values = [1.0,2.0,3.0,4]",
        "normalizing_values = [1.0,2.0,3.0,True]",
        "normalizing_values = [1.0,2.0,3.0,1e309]",
    ],
)
def test_normalizers_reject(source):
    with pytest.raises(ValueError):
        derivation.literal_normalizers(source)


@pytest.fixture
def synthetic_source(tmp_path):
    assets = {name: b"synthetic" for name in derivation.SOURCE_HASHES}
    assets["util.py"] = table_source().encode()
    assets["free_energy_coeffs.npy"] = npy([float(i) for i in range(343)])
    assets["model_intercept.npy"] = npy([-0.5])
    assets["Promoter_Calculator_v1_0.py"] = (
        b"    normalizing_values = [1.0, 2.0, 3.0, 4.0]\n"
    )
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in assets.items()}
    for name, data in assets.items():
        (tmp_path / name).write_bytes(data)
    manifest = {
        "historical_commit": derivation.SOURCE_COMMIT,
        "sources": [{"path": name, "sha256": sha} for name, sha in hashes.items()],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return tmp_path, path, hashes


def test_complete_derivation_and_cli(synthetic_source, capsys):
    root, manifest, hashes = synthetic_source
    with patch.object(derivation, "SOURCE_HASHES", hashes):
        actual = derivation.derive(root, manifest)
        assert actual["coefficients"] == [float(i) for i in range(343)]
        assert actual["intercept"] == -0.5
        assert actual["normalizers"] == [1.0, 2.0, 3.0, 4.0]
        output = root / "result.json"
        assert (
            derivation.main([str(root), str(output), "--manifest", str(manifest)]) == 0
        )
        assert json.loads(output.read_text()) == actual
        assert (
            capsys.readouterr().out.strip()
            == hashlib.sha256(derivation.canonical_bytes(actual)).hexdigest()
        )
        first = output.read_bytes()
        derivation.main([str(root), str(output), "--manifest", str(manifest)])
        assert output.read_bytes() == first
        (root / "LICENSE").write_bytes(b"changed")
        with pytest.raises(ValueError, match="Source hash"):
            derivation.derive(root, manifest)


@pytest.mark.parametrize("which", ["commit", "pin"])
def test_manifest_mismatch(synthetic_source, which):
    root, path, hashes = synthetic_source
    manifest = json.loads(path.read_text())
    if which == "commit":
        manifest["historical_commit"] = "wrong"
    else:
        manifest["sources"][0]["sha256"] = "wrong"
    path.write_text(json.dumps(manifest))
    with patch.object(derivation, "SOURCE_HASHES", hashes):
        with pytest.raises(ValueError, match="manifest identity"):
            derivation.derive(root, path)


def test_script_entrypoint_has_no_import_side_effects(tmp_path):
    with patch("sys.argv", ["derive", str(tmp_path), str(tmp_path / "out.json")]):
        with pytest.raises(FileNotFoundError):
            runpy.run_path(
                str(ROOT / "tools/derive_promoter_parameters.py"), run_name="__main__"
            )
