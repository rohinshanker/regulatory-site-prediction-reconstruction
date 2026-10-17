"""Synthetic-only frozen inference admission, missingness and provenance checks."""

import hashlib
import json
import math
import os
import runpy
import sys
from dataclasses import replace

import pytest
from test_rbs import AlgebraBackend, request

from experiments.rbs import inference
from regsite.contracts import RbsRequest
from regsite.features import extract_features, feature_names
from regsite.learned import predict_learned
from regsite.learning import RidgeModel
from regsite.provenance import canonical_hash, energy_signature
from regsite.rbs import predict
from regsite.sequence import reverse_complement

KIND = inference.ENERGY_KIND
DOMAIN = {"hosts": ["synthetic"], "anti_sd": ["ACCUCCUUA"], "temperatures_c": [37]}


def artifact(kind="sequence-v1", **changes):
    names = feature_names(kind)
    signature = energy_signature(core()) if kind == KIND else {}
    model = RidgeModel(
        feature_names=names,
        means=(0,) * len(names),
        scales=(0,) * len(names),
        coefficients=(0,) * len(names),
        intercept=3,
        penalty=1,
        training_sha256="a" * 64,
        provenance={
            "dataset_id": "synthetic",
            "split_id": "synthetic-train",
            "feature_kind": kind,
            "target_name": "synthetic assay",
            "target_units": "log2 arbitrary units",
            "training_domain": json.dumps(DOMAIN),
            **signature,
        },
    )
    return replace(model, **changes).to_dict()


def core(**changes):
    return predict(
        request(host="synthetic", **changes), AlgebraBackend(), profile="context2017"
    )


def source_row(identifier="algebra", **changes):
    return {
        "id": identifier,
        "input": request(**{"id": identifier, "host": "synthetic", **changes}),
        "status": "ok",
        "reason": None,
    }


def unsupported():
    return {
        "id": "missing",
        "input": None,
        "status": "unsupported",
        "reason": "no input",
    }


class Files:
    def __init__(self, root, kind="sequence-v1"):
        self.source = root / "source.json"
        self.model = root / "model.json"
        self.cache = root / "cache.json" if kind == KIND else None
        self.output = root / "output.json"
        self.data = {
            "schema_version": inference.INPUT_VERSION,
            "records": [source_row()],
        }
        self.weights = artifact(kind)
        self.cached = {
            "schema_version": inference.CACHE_VERSION,
            "records": [{"id": "algebra", "prediction": core()}],
        }

    def write(self):
        self.source.write_text(json.dumps(self.data))
        self.model.write_text(json.dumps(self.weights))
        if self.cache is not None:
            self.cache.write_text(json.dumps(self.cached))

    def pins(self):
        return {
            "source_sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
            "model_sha256": hashlib.sha256(self.model.read_bytes()).hexdigest(),
            "code_commit": "b" * 40,
            "cache": self.cache,
            "cache_sha256": (
                hashlib.sha256(self.cache.read_bytes()).hexdigest()
                if self.cache is not None
                else None
            ),
        }

    def infer(self, **changes):
        self.write()
        return inference.infer(self.source, self.model, **{**self.pins(), **changes})

    def argv(self):
        self.write()
        pins = self.pins()
        args = [str(self.source), str(self.model), str(self.output)]
        for key in (
            "source_sha256",
            "model_sha256",
            "code_commit",
            "cache",
            "cache_sha256",
        ):
            if pins[key] is not None:
                args += ["--" + key.replace("_", "-"), str(pins[key])]
        return args


@pytest.mark.parametrize("kind", ["sequence-v1", KIND])
def test_exact_runtime_scores_features_warnings_and_reproducible_identity(
    tmp_path, kind
):
    files = Files(tmp_path, kind)
    result = files.infer()
    assert result == files.infer()
    row = result["records"][0]
    live = predict_learned(
        files.data["records"][0]["input"],
        RidgeModel.from_dict(files.weights),
        AlgebraBackend() if kind == KIND else None,
    )
    assert row["status"] == "ok" and row["score_log2"] == 3 and row["score"] == 8
    for key in ("features", "warnings", "unlearned_feature_changes"):
        assert row[key] == live[key]
    assert result["artifact_sha256"] == files.weights["artifact_sha256"]
    assert result["rawscore_scale"] == "log2_assay_response"
    assert result["calibration_applied"] is False
    assert result["training_domain"] == DOMAIN
    assert result["training_provenance"] == files.weights["provenance"]
    assert result["target"]["units"] == "log2 arbitrary units"
    identity = result.pop("collection_sha256")
    assert identity == canonical_hash(result)
    assert result["source_sha256"] == files.pins()["source_sha256"]
    assert result["model_sha256"] == files.pins()["model_sha256"]
    assert result["cache_sha256"] == files.pins()["cache_sha256"]


def test_no_folding_or_fitting_and_only_cli_summary(tmp_path, monkeypatch, capsys):
    files = Files(tmp_path, KIND)
    args = files.argv()

    def forbidden(*args, **kwargs):
        pytest.fail("inference invoked folding or fitting")

    monkeypatch.setattr("regsite.backend.RnaStructure.open", forbidden)
    monkeypatch.setattr("regsite.rbs.predict", forbidden)
    monkeypatch.setattr("regsite.learning.fit_ridge", forbidden)
    monkeypatch.delenv("REGSITE_RNASTRUCTURE", raising=False)
    assert inference.main(args) == 0
    summary = json.loads(capsys.readouterr().out)
    result = json.loads(files.output.read_text())
    assert summary == {
        "n_records": 1,
        "n_unsuccessful": 0,
        "collection_sha256": result["collection_sha256"],
    }


@pytest.mark.parametrize("kind", ["sequence-v1", KIND])
def test_nonconstant_weights_use_frozen_training_scaling(tmp_path, kind):
    files = Files(tmp_path, kind)
    size = len(feature_names(kind))
    files.weights = artifact(
        kind,
        means=(10,) + (0,) * (size - 1),
        scales=(5,) + (0,) * (size - 1),
        coefficients=(2,) + (0,) * (size - 1),
    )
    row = files.infer()["records"][0]
    # The 20 nt leader is two training standard deviations above the mean.
    assert row["score_log2"] == 7 and row["score"] == 128
    assert row["features"]["values"][0] == 20


def test_private_core_validation_also_rejects_nonfinite_feature_terms():
    parent = core()
    parent["sites"][0]["energies"]["dG_total"] = math.nan
    parent["input"]["start_positions"] = [20]
    with pytest.raises(ValueError, match="finite"):
        inference._core(parent, RbsRequest.from_dict(request()))


@pytest.mark.parametrize("change", ["units", "missing", "extra"])
def test_closed_energy_admission_precedes_all_output(tmp_path, change):
    files = Files(tmp_path, KIND)
    files.data["records"].append(source_row("last"))
    final = core(id="last")
    energies = final["sites"][0]["energies"]
    if change == "units":
        energies["units"] = "kJ/mol"
        for key in inference._ENERGY_NUMBERS:
            energies[key] *= 4.184
    elif change == "missing":
        del energies["dG_start"]
    else:
        energies["observed"] = {"assay": 1}
    files.cached["records"].append({"id": "last", "prediction": final})
    files.output.write_text("existing output")
    assert inference.main(files.argv()) == 2
    assert files.output.read_text() == "existing output"


@pytest.mark.parametrize(
    "field", sorted(inference._ENERGY_NUMBERS | inference._ENERGY_NULLABLE)
)
@pytest.mark.parametrize("bad", [True, "0", 10**400])
def test_all_energy_fields_are_finite_numbers(tmp_path, field, bad):
    files = Files(tmp_path, KIND)
    files.cached["records"][0]["prediction"]["sites"][0]["energies"][field] = bad
    with pytest.raises(ValueError, match="energy"):
        files.infer()


def test_energy_contract_matches_shipped_schema():
    from pathlib import Path

    schema = json.loads(Path("schemas/rbs-result-1.1.schema.json").read_text())
    contract = schema["$defs"]["energies"]
    assert set(contract["required"]) == (
        inference._ENERGY_NUMBERS | inference._ENERGY_NULLABLE | {"units"}
    )
    assert set(contract["properties"]) == set(contract["required"])
    assert contract["properties"]["units"] == {"const": "kcal/mol"}


@pytest.mark.parametrize("kind", ["sequence-v1", KIND])
def test_all_unsupported_and_empty_collections(tmp_path, kind):
    files = Files(tmp_path, kind)
    files.cached["records"] = []
    files.data["records"] = [unsupported()]
    row = files.infer()["records"][0]
    assert row["id"] == "missing" and row["reason"] == "no input"
    assert row["score"] is None and row["status"] == "unsupported"
    files.data["records"] = []
    assert files.infer()["records"] == []


def test_preserve_source_order_and_failed_cache_reason(tmp_path):
    files = Files(tmp_path, KIND)
    failed = predict(
        request(id="parent"), AlgebraBackend(fail=True), profile="context2017"
    )
    assert failed["status"] == "failed"
    files.data["records"] = [source_row("z"), unsupported(), source_row("a")]
    files.cached["records"] = [
        {"id": "a", "prediction": failed},
        {"id": "z", "prediction": core()},
    ]
    rows = files.infer()["records"]
    assert [row["id"] for row in rows] == ["z", "missing", "a"]
    assert rows[-1]["status"] == failed["status"]
    assert failed["reason"] is None
    assert rows[-1]["reason"] == "deliberate folding failure"
    assert rows[-1]["score"] is None and rows[-1]["features"] is None
    assert rows[-1]["parent_provenance"]["prediction_id"] == failed["prediction_id"]


@pytest.mark.parametrize("site_reason", ["CT pairs are not reciprocal", None])
def test_failed_core_preserves_site_reason_or_explicit_missingness(
    tmp_path, site_reason
):
    files = Files(tmp_path, KIND)
    parent = files.cached["records"][0]["prediction"]
    parent.update(status="failed", reason=None)
    parent["sites"][0].update(status="failed", reason=site_reason)
    row = files.infer()["records"][0]
    assert row["reason"] == (site_reason or "mechanistic_feature_unavailable")
    assert row["score"] is None and row["status"] == "failed"


@pytest.mark.parametrize("status", ["no_candidate", "unsupported", "invalid_input"])
def test_failed_core_null_or_text_reason_is_preserved(tmp_path, status):
    files = Files(tmp_path, KIND)
    parent = files.cached["records"][0]["prediction"]
    parent.update(status=status, reason="original missingness", sites=[])
    row = files.infer()["records"][0]
    assert row["status"] == status and row["reason"] == "original missingness"


def test_dna_rna_and_cross_dataset_parent_reuse_without_rewriting(tmp_path):
    files = Files(tmp_path, KIND)
    files.data["records"] = [source_row("external", host="synthetic alias")]
    parent = core(id="original", sequence=request()["sequence"].replace("T", "U"))
    original = json.loads(json.dumps(parent))
    files.cached["records"] = [{"id": "external", "prediction": parent}]
    row = files.infer()["records"][0]
    assert row["status"] == "ok"
    assert row["mechanistic_reference"] == original
    assert row["parent_provenance"] == {
        "id": "original",
        "prediction_id": original["prediction_id"],
        "canonical_parent_sha256": canonical_hash(original),
        "host": "synthetic",
    }
    assert "host_difference" in row["warnings"]
    assert "outside_declared_training_host_or_settings" in row["warnings"]
    assert json.loads(json.dumps(parent)) == original


@pytest.mark.parametrize(
    "changes",
    [
        {"host": None},
        {"host": "Synthetic"},
        {"anti_sd": "ACCUCCUUU"},
        {"temperature_c": 30},
    ],
)
def test_exact_domain_mismatch(tmp_path, changes):
    files = Files(tmp_path)
    files.data["records"][0]["input"].update(changes)
    assert (
        "outside_declared_training_host_or_settings"
        in files.infer()["records"][0]["warnings"]
    )


def test_reverse_strand_and_inactive_features(tmp_path):
    files = Files(tmp_path, KIND)
    changes = {
        "strand": "-",
        "sequence": reverse_complement(request()["sequence"].replace("T", "U")),
    }
    files.data["records"][0]["input"].update(changes)
    files.cached["records"][0]["prediction"] = core(**changes)
    values = extract_features(
        RbsRequest.from_dict(files.data["records"][0]["input"]),
        kind=KIND,
        prediction=files.cached["records"][0]["prediction"],
    )
    model = replace(RidgeModel.from_dict(files.weights), means=values)
    files.weights = model.to_dict()
    row = files.infer()["records"][0]
    assert row["unlearned_feature_changes"] == []
    assert (
        "changed_constant_training_features_have_no_learned_effect"
        not in row["warnings"]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"start_positions": None},
        {"start_positions": []},
        {"start_positions": [0]},
        {"sequence": "AAAAAA", "start_positions": [2]},
        {"start_positions": [20, 21]},
    ],
)
def test_feature_unsupported_is_a_row(tmp_path, changes):
    files = Files(tmp_path)
    files.data["records"][0]["input"].update(changes)
    row = files.infer()["records"][0]
    assert row["status"] == "unsupported" and row["reason"]
    assert row["score_log2"] is None and row["score"] is None


def test_energy_footprint_unsupported_is_a_row(tmp_path):
    files = Files(tmp_path, KIND)
    changes = {"sequence": "A" * 20 + "ATG", "start_positions": [20]}
    files.data["records"][0]["input"].update(changes)
    files.cached["records"][0]["prediction"] = core(**changes)
    row = files.infer()["records"][0]
    assert row["status"] == "unsupported" and "truncated" in row["reason"]


@pytest.mark.parametrize("intercept", [1024, -1075, 1e308, -1e308])
def test_positive_scale_overflow_and_underflow_are_explicit(tmp_path, intercept):
    files = Files(tmp_path)
    files.weights = artifact(intercept=intercept)
    row = files.infer()["records"][0]
    assert row["status"] == "failed" and row["reason"]
    assert row["score"] is None and row["score_log2"] is None


def test_model_numeric_failure_and_nonfinite_defense(tmp_path, monkeypatch):
    files = Files(tmp_path)
    n = len(feature_names("sequence-v1"))
    files.weights = artifact(scales=(1e-308,) * n, coefficients=(1e308,) * n)
    row = files.infer()["records"][0]
    assert row["status"] == "failed" and "overflow" in row["reason"]
    for raw in (math.nan, math.inf):
        monkeypatch.setattr(RidgeModel, "predict", lambda self, values, raw=raw: (raw,))
        row = files.infer()["records"][0]
        assert row["status"] == "failed" and row["score"] is None


@pytest.mark.parametrize(
    "pin", ["source_sha256", "model_sha256", "code_commit", "cache_sha256"]
)
@pytest.mark.parametrize("value", [None, "", "A" * 64, "no pin", "a" * 63])
def test_bad_pin_shapes(tmp_path, pin, value):
    files = Files(tmp_path, KIND)
    with pytest.raises(ValueError):
        files.infer(**{pin: value})


@pytest.mark.parametrize("pin", ["source_sha256", "model_sha256", "cache_sha256"])
def test_file_pin_mismatch(tmp_path, pin):
    files = Files(tmp_path, KIND)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        files.infer(**{pin: "f" * 64})


@pytest.mark.parametrize("cache,pin", [(None, None), (None, "a" * 64), ("path", None)])
def test_energy_requires_cache_and_pin(tmp_path, cache, pin):
    files = Files(tmp_path, KIND)
    with pytest.raises(ValueError, match="requires"):
        files.infer(cache=tmp_path / cache if cache else None, cache_sha256=pin)


@pytest.mark.parametrize("changes", [{"cache": "cache"}, {"cache_sha256": "a" * 64}])
def test_sequence_rejects_cache(tmp_path, changes):
    with pytest.raises(ValueError, match="rejects"):
        Files(tmp_path).infer(**changes)


@pytest.mark.parametrize(
    "envelope",
    [
        None,
        [],
        {},
        {"schema_version": "wrong", "records": []},
        {"schema_version": inference.INPUT_VERSION, "records": None},
        {"schema_version": inference.INPUT_VERSION, "records": [], "labels": []},
    ],
)
def test_closed_source_envelope(tmp_path, envelope):
    files = Files(tmp_path)
    files.data = envelope
    with pytest.raises(ValueError, match="envelope"):
        files.infer()


@pytest.mark.parametrize(
    "rows",
    [
        [None],
        [{"id": None}],
        [{"id": ""}],
        [{"id": " "}],
        [source_row(), source_row()],
        [{**source_row(), "label": 5}],
        [{"id": "x"}],
        [{**unsupported(), "input": {}}],
        [{**unsupported(), "reason": None}],
        [{**source_row(), "status": "failed"}],
        [{**source_row(), "reason": "why"}],
        [{**source_row(), "input": None}],
        [{**source_row(), "input": request(id="different")}],
        [{**source_row(), "input": {k: v for k, v in request().items() if k != "id"}}],
        [source_row("x", observed=2)],
        [source_row("x", anti_sd="bad")],
    ],
)
def test_closed_input_records_and_matching_ids(tmp_path, rows):
    files = Files(tmp_path)
    files.data["records"] = rows
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize(
    "change",
    ["version", "extra", "row_extra", "missing", "extra_id", "duplicate", "null"],
)
def test_closed_cache_and_exact_coverage(tmp_path, change):
    files = Files(tmp_path, KIND)
    if change == "version":
        files.cached["schema_version"] = "wrong"
    elif change == "extra":
        files.cached["observed"] = 1
    elif change == "row_extra":
        files.cached["records"][0]["label"] = 2
    elif change == "missing":
        files.cached["records"] = []
    elif change == "extra_id":
        files.cached["records"].append({"id": "extra", "prediction": core()})
    elif change == "duplicate":
        files.cached["records"] *= 2
    else:
        files.cached["records"][0]["prediction"] = None
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize("status", ["ok", "failed"])
@pytest.mark.parametrize(
    "key,value",
    [
        ("sequence", "AUG"),
        ("oriented_sequence", "AUG"),
        ("normalized_sha256", "f" * 64),
        ("oriented_sha256", "f" * 64),
        ("anti_sd", "ACCUCCUUU"),
        ("strand", "-"),
        ("temperature_c", 30),
        ("temperature_c", True),
        ("start_positions", None),
        ("start_positions", []),
        ("start_positions", [21]),
        ("start_positions", [20.0]),
        ("start_positions", [20, 21]),
        ("id", "different"),
        ("host", 4),
        ("input_sha256", "bad"),
    ],
)
def test_all_parent_identity_fields_checked_even_on_failure(
    tmp_path, status, key, value
):
    files = Files(tmp_path, KIND)
    parent = files.cached["records"][0]["prediction"]
    parent["status"] = status
    parent["input"][key] = value
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize("starts", [None, [], [20, 21]])
def test_cache_requires_explicit_single_source_start_even_on_failure(tmp_path, starts):
    files = Files(tmp_path, KIND)
    files.data["records"][0]["input"]["start_positions"] = starts
    files.cached["records"][0]["prediction"]["status"] = "failed"
    with pytest.raises(ValueError, match="explicit start"):
        files.infer()


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "1.0"),
        ("status", "unknown"),
        ("id", ""),
        ("sites", None),
        ("warnings", None),
        ("warnings", [3]),
        ("reason", 2),
        ("prediction_id", None),
        ("input", None),
        ("input", {}),
        ("sites", [None]),
        ("sites", [{}]),
    ],
)
def test_complete_core_shape(tmp_path, key, value):
    files = Files(tmp_path, KIND)
    files.cached["records"][0]["prediction"][key] = value
    with pytest.raises(ValueError):
        files.infer()


def test_missing_core_field_and_site_field(tmp_path):
    files = Files(tmp_path, KIND)
    del files.cached["records"][0]["prediction"]["reason"]
    with pytest.raises(ValueError):
        files.infer()
    files.cached["records"][0]["prediction"] = core()
    del files.cached["records"][0]["prediction"]["sites"][0]["energies"]
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize(
    "key,value",
    [
        ("status", "failed"),
        ("status", "unknown"),
        ("oriented_start", 21),
        ("oriented_start", 20.0),
        ("codon", "GUG"),
        ("energies", None),
    ],
)
def test_successful_cache_feature_corruption_is_admission_failure(tmp_path, key, value):
    files = Files(tmp_path, KIND)
    files.cached["records"][0]["prediction"]["sites"][0][key] = value
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize("sites", [[], "duplicate"])
def test_successful_cache_requires_one_site(tmp_path, sites):
    files = Files(tmp_path, KIND)
    parent = files.cached["records"][0]["prediction"]
    parent["sites"] = parent["sites"] * 2 if sites == "duplicate" else sites
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize("change", ["start", "codon", "multiple"])
def test_failed_sites_also_match_explicit_start(tmp_path, change):
    files = Files(tmp_path, KIND)
    parent = files.cached["records"][0]["prediction"]
    parent["status"] = "failed"
    if change == "multiple":
        parent["sites"] *= 2
    elif change == "start":
        parent["sites"][0]["oriented_start"] = 21
    else:
        parent["sites"][0]["codon"] = "GUG"
    with pytest.raises(ValueError, match="start mismatch|one explicit start"):
        files.infer()


@pytest.mark.parametrize("term", [None, True, "0", 10**400, math.inf, math.nan])
def test_nonfinite_or_missing_energy_fails_admission(tmp_path, term):
    files = Files(tmp_path, KIND)
    files.cached["records"][0]["prediction"]["sites"][0]["energies"]["dG_total"] = term
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize(
    "change", ["model", "backend", "source", "implementation", "parameters"]
)
def test_wrong_model_and_provenance_rejected_even_failed(tmp_path, change):
    files = Files(tmp_path, KIND)
    parent = files.cached["records"][0]["prediction"]
    parent["status"] = "failed"
    if change == "backend":
        parent["backend"] = {}
    else:
        key, value = {
            "model": ("id", "wrong"),
            "source": ("source_commit", "f" * 40),
            "implementation": ("implementation_version", "wrong"),
            "parameters": ("parameters", None),
        }[change]
        parent["model"][key] = value
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize("field", ["model", "backend"])
def test_cache_mixture_rejected_but_training_difference_warned(tmp_path, field):
    files = Files(tmp_path, KIND)
    parent = files.cached["records"][0]["prediction"]
    if field == "model":
        parent["model"]["parameters"]["upstream_nt"] += 1
    else:
        parent["backend"]["different_build"] = True
    row = files.infer()["records"][0]
    assert "energy_backend_or_model_differs_from_training" in row["warnings"]
    files.data["records"].append(source_row("other"))
    other = core()
    other["status"] = "failed"
    files.cached["records"].append({"id": "other", "prediction": other})
    with pytest.raises(ValueError, match="mixes"):
        files.infer()


@pytest.mark.parametrize("change", ["checksum", "domain", "features", "required"])
def test_artifact_verification_and_validation(tmp_path, change):
    files = Files(tmp_path)
    if change == "checksum":
        files.weights["intercept"] += 1
    else:
        model = RidgeModel.from_dict(files.weights)
        metadata = dict(model.provenance)
        if change == "domain":
            metadata["training_domain"] = "{}"
        elif change == "features":
            metadata["feature_kind"] = KIND
        else:
            del metadata["training_domain"]
        files.weights = replace(model, provenance=metadata).to_dict()
    with pytest.raises(ValueError):
        files.infer()


@pytest.mark.parametrize("which", ["source", "model", "cache"])
@pytest.mark.parametrize(
    "raw", ['{"schema_version":1,"schema_version":2}', "{", '{"unused":NaN}']
)
def test_strict_json_even_for_pinned_bytes(tmp_path, which, raw):
    files = Files(tmp_path, KIND)
    files.write()
    getattr(files, which).write_text(raw)
    with pytest.raises(ValueError):
        inference.infer(files.source, files.model, **files.pins())


@pytest.mark.parametrize("which", ["source", "model", "cache"])
@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_output_alias_rejected_without_mutation(tmp_path, which, alias, capsys):
    files = Files(tmp_path, KIND)
    args = files.argv()
    path = getattr(files, which)
    original = path.read_bytes()
    if alias == "same":
        args[2] = str(path)
    elif alias == "symlink":
        files.output.symlink_to(path)
    else:
        os.link(path, files.output)
    assert inference.main(args) == 2
    assert "overwrite" in capsys.readouterr().err
    assert path.read_bytes() == original


def test_cli_errors_leave_output_untouched_and_failures_exit_one(tmp_path, capsys):
    files = Files(tmp_path)
    files.data["records"].append(unsupported())
    assert inference.main(files.argv()) == 1
    assert json.loads(capsys.readouterr().out)["n_unsuccessful"] == 1
    before = files.output.read_bytes()
    files.data["records"].append({**source_row("bad"), "observed": 1})
    assert inference.main(files.argv()) == 2
    assert files.output.read_bytes() == before
    assert "fields" in capsys.readouterr().err
    args = files.argv()
    files.source.unlink()
    assert inference.main(args) == 2
    assert "rbs-inference" in capsys.readouterr().err


def test_cli_new_output_directory_and_io_error(tmp_path, capsys):
    files = Files(tmp_path)
    files.output = tmp_path / "nested" / "output.json"
    assert inference.main(files.argv()) == 0
    capsys.readouterr()
    files.output = tmp_path
    assert inference.main(files.argv()) == 2
    assert "rbs-inference" in capsys.readouterr().err


def test_module_entrypoint_help(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["inference", "--help"])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as exc:
        runpy.run_module("experiments.rbs.inference", run_name="__main__")
    assert exc.value.code == 0
