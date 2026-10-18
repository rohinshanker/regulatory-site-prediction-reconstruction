"""Optional executed-source audit; requires the separately pinned research env.

GPL-3.0-or-later; see NOTICE. No experimental labels or hosted services are used.
The original source is checked then adapted in memory only for Python syntax and
the renamed sklearn encoder argument. The Barrick installed source is unmodified.
"""

import argparse
import contextlib
import hashlib
import importlib
import importlib.metadata
import io
import json
import math
import os
import sys
import types
from pathlib import Path

from benchmarks.promoter import reference_oracle as oracle

PRINT_REPLACEMENTS = (
    (
        'print "best: ", min(seq_query.items(), key=operator.itemgetter(0))',
        'print("best: ", min(seq_query.items(), key=operator.itemgetter(0)))',
    ),
    (
        'print "Fwd TSS: %s. TX Rate: %s. Calcs: %s" '
        "% (TSS, result['Tx_rate'], str(result) )",
        'print("Fwd TSS: %s. TX Rate: %s. Calcs: %s" '
        "% (TSS, result['Tx_rate'], str(result) ))",
    ),
    (
        'print "Rev TSS: %s. TX Rate: %s. Calcs: %s" '
        "% (TSS, result['Tx_rate'], str(result) )",
        'print("Rev TSS: %s. TX Rate: %s. Calcs: %s" '
        "% (TSS, result['Tx_rate'], str(result) ))",
    ),
    (
        'print "Elapsed Time: ", time.time() - begin, " seconds."',
        'print("Elapsed Time: ", time.time() - begin, " seconds.")',
    ),
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compatibility_sources(root, manifest):
    """Check every historical inference asset before the explicit minimal patch."""
    for item in manifest["sources"]:
        if sha((root / item["path"]).read_bytes()) != item["sha256"]:
            raise ValueError("Historical source asset differs from pin")
    directory = root / "upstream/Promoter_Calculator"
    source = (directory / "Promoter_Calculator_v1_0.py").read_text()
    for before, after in PRINT_REPLACEMENTS:
        if source.count(before) != 1:
            raise ValueError("Historical print compatibility preimage changed")
        source = source.replace(before, after)
    util = (directory / "util.py").read_text()
    if util.count("OneHotEncoder(sparse=False)") != 2:
        raise ValueError("Historical encoder compatibility preimage changed")
    util = util.replace(
        "OneHotEncoder(sparse=False)", "OneHotEncoder(sparse_output=False)"
    )
    return {"Promoter_Calculator_v1_0.py": source, "util.py": util}


def historical_module(root, sources):
    """Import hash-checked adapted code without editing the original tree."""
    directory = root / "upstream/Promoter_Calculator"
    utility = types.ModuleType("util")
    exec(
        compile(sources["util.py"], str(directory / "util.py"), "exec"),
        utility.__dict__,
    )
    prior = sys.modules.get("util")
    sys.modules["util"] = utility
    module = types.ModuleType("wave4_historical_promoter")
    module.__file__ = str(directory / "Promoter_Calculator_v1_0.py")
    try:
        exec(
            compile(sources["Promoter_Calculator_v1_0.py"], module.__file__, "exec"),
            module.__dict__,
        )
    finally:
        if prior is None:
            del sys.modules["util"]
        else:
            sys.modules["util"] = prior
    return module


def equal_number(actual, expected):
    """Tolerance is fixed before execution; independently summed terms can differ."""
    if not math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("Executed numerical result differs from independent oracle")


def check_state(actual, expected):
    """Verify all source terms, rate, sequence slices and forward intervals."""
    for key, value in expected["terms"].items():
        if key != "dG_apparent":  # State APIs omit it; scalar model checks it below.
            equal_number(actual[key], value)
    equal_number(actual["Tx_rate"], expected["Tx_rate"])
    if actual["TSS"] != expected["tss"]:
        raise ValueError("Executed TSS differs from requested coordinate")
    for key in ("UP", "hex35", "spacer", "hex10", "disc", "ITR"):
        if actual[key] != expected["features"][key]:
            raise ValueError("Executed sequence slice differs from oracle")
        if key != "ITR" and actual[key + "_position"] != expected["intervals"][key]:
            raise ValueError("Executed feature interval differs from oracle")


def model_parameters(model):
    names = (
        "dg10_0",
        "dg10_3",
        "dg35_0",
        "dg35_3",
        "dmers",
        "x10mers",
        "spacers",
        "model",
        "inters",
        "K",
        "BETA",
    )
    return {name: getattr(model, name) for name in names}


def verify_environment(fork, manifest):
    """Bind installed inference bytes and exact dependency versions to admission."""
    directory = Path(fork.__file__).parent
    for entry in manifest["fork_files"]:
        if sha((directory / entry["path"]).read_bytes()) != entry["sha256"]:
            raise ValueError("Installed fork differs from source pin")
    for entry in manifest["distributions"]:
        distribution = importlib.metadata.distribution(entry["name"])
        if (
            distribution.version != entry["version"]
            or sha(distribution.read_text("METADATA").encode())
            != entry["metadata_sha256"]
        ):
            raise ValueError("Optional reference dependency version/metadata changed")


def verify_parameters(historical, fork, parameters):
    """Check the complete converted arrays/tables, including unused coefficients."""
    for module in (historical, fork):
        model = module.Promoter_Calculator()
        if model.model.tolist() != parameters[
            "coefficients"
        ] or model.inters.tolist() != [parameters["intercept"]]:
            raise ValueError("Converted reference arrays differ from source")
    for name, table in parameters["tables"].items():
        if getattr(historical.util, name) != table:
            raise ValueError("Converted reference utility table differs from source")


def source_behavior_checks(historical, fork):
    """Execute legacy key/gap conventions separately from corrected projections."""
    outputs = {}
    for name, module in (
        ("historical_compat", historical),
        ("barrick_unmodified", fork),
    ):
        model = module.Promoter_Calculator()
        model.run("ACGT" * 50, [100, 101])
        output = model.output()
        forward = output["Forward_Predictions_per_TSS"]
        reverse = output["Reverse_Predictions_per_TSS"]
        if (
            list(forward) != [100]
            or list(reverse) != [101]
            or reverse[101]["TSS"] != 99
        ):
            raise ValueError("Historical reverse range/key behavior changed")
        zero_sigma = module.Promoter_Calculator(sigmaLevels={"70": 0})
        zero_sigma.run("ACGT" * 50, [100, 101])
        equal_number(
            zero_sigma.output()["Forward_Predictions_per_TSS"][100]["Tx_rate"],
            forward[100]["Tx_rate"],
        )
        kwargs = dict(
            inputSequence="A" * 78,
            model=model.model,
            inters=model.inters,
            constraints=("", ""),
        )
        kwargs.update(
            {
                key: getattr(model, key)
                for key in (
                    "dg10_0",
                    "dg10_3",
                    "dg35_0",
                    "dg35_3",
                    "dmers",
                    "x10mers",
                    "spacers",
                )
            }
        )
        if name == "historical_compat":
            kwargs.update(
                two_mer_encoder=model.two_mer_encoder,
                three_mer_encoder=model.three_mer_encoder,
            )
        _, query = module.scan_arbitrary(**kwargs)
        if len(query) != 1 or next(iter(query))[2] != 57:
            raise ValueError("Historical arbitrary-scan missing-gap behavior changed")
        outputs[name] = {
            "forward_key": 100,
            "reverse_legacy_key": 101,
            "reverse_oriented_tss": 99,
            "corrected_forward_base": 100,
            "arbitrary_legacy_tss": 57,
            "arbitrary_corrected_tss": 58,
            "sigma_zero_ignored": True,
        }
    return outputs


def execute_fixtures(historical, fork, fixtures, parameters):
    """Compare complete declared states, selection and documented source bugs."""
    results = []
    for case in fixtures["cases"]:
        sequence, tss, organism = (case[k] for k in ("sequence", "tss", "organism"))
        expected = oracle.states(sequence, tss, parameters, organism)
        frozen = [
            {
                "discriminator": r["discriminator"],
                "spacer": r["spacer"],
                "terms": r["terms"],
                "Tx_rate": r["Tx_rate"],
            }
            for r in expected
        ]
        if frozen != case["expected_states"]:
            raise ValueError("Independent fixture bytes/parameters have changed")
        old = historical.Promoter_Calculator(organism=organism)
        new = fork.Promoter_Calculator(organism=organism, threads=1, verbosity=0)
        minima, all_states = old.predict(sequence, [tss, tss + 1])
        fork_states = new.worker(
            sequence, tss, model_parameters(new), tss, min_only=False
        )
        if len(all_states[tss]) != len(expected) or len(fork_states) != len(expected):
            raise ValueError("Source state denominator differs from oracle")
        for index, state in enumerate(expected):
            _, disc, spacer, actual = fork_states[index]
            if [disc, spacer] != [state["discriminator"], state["spacer"]]:
                raise ValueError("Fork visitation order differs from oracle")
            check_state(actual, state)
            check_state(all_states[tss][(disc, spacer)], state)
            features = state["features"]
            inputs = [
                features[k] for k in ("UP", "hex35", "spacer", "hex10", "disc", "ITR")
            ]
            args = [
                getattr(old, name)
                for name in (
                    "dg10_0",
                    "dg10_3",
                    "dg35_0",
                    "dg35_3",
                    "dmers",
                    "x10mers",
                    "spacers",
                    "model",
                    "inters",
                )
            ]
            equal_number(
                historical.linear_free_energy_model(*inputs, *args)[1],
                state["terms"]["dG_apparent"],
            )
            equal_number(
                fork.linear_free_energy_model(*inputs, *args).dg_apparent,
                state["terms"]["dG_apparent"],
            )
        chosen = oracle.winner(expected)
        fork_min, fork_all = new.predict(
            sequence, [tss, tss + 1], callback=lambda: None, min_only=False
        )
        if chosen is None:
            if minima or fork_min or fork_all:
                raise ValueError("Incomplete window unexpectedly produced a state")
        else:
            check_state(minima[tss], chosen)
            check_state(fork_min[tss], chosen)
            # Fork's parallelizer does not forward min_only; public All_States
            # retains only one state, even when min_only=False was requested.
            if len(fork_all[tss]) != 1:
                raise ValueError("Pinned fork All_States behavior changed")
        results.append(
            {
                "id": case["id"],
                "states_checked": len(expected),
                "winner": None
                if chosen is None
                else [chosen["discriminator"], chosen["spacer"]],
                "fork_public_all_states": len(fork_all.get(tss, {})),
            }
        )
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historical_root", type=Path)
    parser.add_argument("new_output", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).parent
    manifest = json.loads((root / "source-manifest.json").read_text())
    parameters = json.loads((root / "reference-parameters.json").read_text())
    fixtures = json.loads((root / "reference-fixtures.json").read_text())
    environment = json.loads((root / "reference-environment.json").read_text())
    sources = compatibility_sources(args.historical_root, manifest)
    old = historical_module(args.historical_root, sources)
    fork = importlib.import_module("promoter_calculator.promoter_calculator")
    verify_environment(fork, environment)
    verify_parameters(old, fork, parameters)
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        results = execute_fixtures(old, fork, fixtures, parameters)
        behavior = source_behavior_checks(old, fork)
    result = {
        "schema_version": "promoter-executed-reference-1",
        "cases": results,
        "source_behaviors": behavior,
        "compatibility_sha256": {k: sha(v.encode()) for k, v in sources.items()},
        "fixture_sha256": sha((root / "reference-fixtures.json").read_bytes()),
        "parameter_sha256": sha((root / "reference-parameters.json").read_bytes()),
        "environment_sha256": sha((root / "reference-environment.json").read_bytes()),
        "stdout_sha256": sha(capture.getvalue().encode()),
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "biological_accuracy_evaluated": False,
    }
    with os.fdopen(
        os.open(args.new_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {"cases": len(results), "states": sum(r["states_checked"] for r in results)}
        )
    )


if __name__ == "__main__":
    main()
