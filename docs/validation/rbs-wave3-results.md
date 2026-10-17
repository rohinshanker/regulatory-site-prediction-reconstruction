# RBS standby and traceback validation

- Purpose: Separate structural correctness, software reliability and experimental predictive accuracy.
- Scope: Published standby reconstruction and the separately installed RNAstructure traceback repair.
- Scientific candidate: 75d127cc350bcc4dc54be5b980db893da3c41e92.
- Last verified: 2026-10-17.

## Structural and software evidence

The new `standby2014` profile models the space available for ribosome binding
upstream of a start, the energy cost of opening RNA hairpins, and sliding across
downstream structures. Its [contract](rbs-standby.md) distinguishes published
relationships from reconstructed geometric and search conventions. It does not
replace historical, footprint or context profiles, or retrain frozen models.

The separate [backend repair](rbs-backend-repair.md) corrects tied traceback
choices and state confusion in RNAstructure 6.6. Changing the folding engine can
change a model's predictions even when its equations are unchanged. The runtime
therefore returns explicit model, backend, source/parameter and implementation
identities, and retains failure and missingness semantics.

| Independent or reproducible check | Original engine | Repaired engine |
| --- | ---: | ---: |
| B's fixed structural panel | 11/14 valid | 14/14 valid |
| Deterministic 60-input synthetic panel | 54/60 valid | 60/60 valid |
| Twelve public development leaders | 11/12 valid | 12/12 valid |
| Reviewer’s separate 70-input synthetic probe | 66/70 valid | 69/70 valid |
| Two targeted native-leader reproductions | malformed or absent CT | 100 valid structures each |

All eleven previously valid outputs in B's panel remain identical, including
ordered pairings and energies. The larger synthetic panel changes ten previously
valid outputs and preserves 44; the development panel changes one valid output.
Thus the repair is a new scientific backend variant, not a byte-compatible
replacement. No invalid candidate is silently dropped.

The final separate component gate passes all 19 checks. It binds the tested
executables/source to the build receipt and rejects a deliberate wrong-coordinate
energy-call mutation. An extracted-source C++ harness
checks 12,000 W2 and 2,000 WMB2 states, including boundaries, ties, modified-base
predicates and failures, with undefined-behavior sanitization. Its synthetic
energy functions test recurrence correspondence; the real executables and
independent fixtures test actual structures and energies. These are distinct
forms of evidence.

The standby implementation passed an independent exact-patch review covering
159 focused tests, 2,291 independently generated structures, 5,761 fixed-state
opening evaluations and 162 legacy comparisons. B's independent analytic fixtures
also exercise geometry, uncapped sliding and a synthetic opening tradeoff in the
installed runtime. Synthetic oracle energies are never represented as measured
biological outcomes.

At the scientific candidate, the full application suite passes 1,461 tests with
each engine, with 100% coverage of 4,563 statements and 1,902 branches. Ruff and
mypy pass. All four [CI configurations](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39069703442)
pass on Linux/macOS with Python 3.11/3.14, building both engines and running the
component, runtime and fresh-wheel gates. The fresh wheel runs single/batch,
refined, standby, native JSON/GFF3 and learned examples offline. The source archive
preserves all 126 component/raw-structural-fixture files byte-for-byte, including
the separate GPL-2.0-only licence; the wheel contains no backend source or binary.
The complete integration with B's reviewed evidence through
`87d6dd8646b1536339bdeceeba8c16db195af7ba` passes 1,481 tests with each
engine and 100% coverage of 4,927 statements and 2,058 branches. This includes
the new-data freeze and Promoter audit tools. Fresh offline wheel checks also
exercise standby CSV and both-strand native JSON. The final integrated CI
identity and packaging checks are recorded in [PR25](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/pull/25).

## Public 2014 development comparison

**The standby reconstruction substantially improves this development panel, but
it is not an independent generalization result.** The 136 constructs come from
the study that established the standby relationships and fitted coefficients.
All five configurations were declared before predictions. No coefficient,
geometry convention, threshold, scale, slope or intercept was fitted or selected
using these outcomes. Historical scoring remains the default; this comparison
does not promote a native-host model or consume the reserved Cambray final panel.

All configurations use the complete source dataset, E. coli aSD `ACCUCCUUA`,
37 °C and the supplied start positions. Host is a descriptive DH10B configuration,
not a calibration switch. The existing independently prepared evaluator normalizes
both measurements and predictions to the predeclared control
`standby2014:5'UTR_136`. It retains every eligible case and reports failure coverage.

| Configuration | Success /136 | MAE log2 | RMSE log2 | Spearman rho | Within2× /136 | Within5× /136 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| historical-original | 136 | 1.555669 | 1.932227 | 0.507568 | 52 | 113 |
| context-original | 136 | 1.597577 | 2.084651 | 0.413047 | 58 | 103 |
| context-repaired | 136 | 1.597577 | 2.084651 | 0.413047 | 58 | 103 |
| standby-original | 136 | 0.659250 | 0.919988 | 0.841458 | 106 | 135 |
| standby-repaired | 136 | 0.659250 | 0.919988 | 0.841458 | 106 | 135 |

Lower error is better; higher rank correlation and within-fold counts are better.
For intuition, a log2 error of 1 is a factor-of-two discrepancy. The fixed
relative-rate 1 baseline has MAE 2.104345. Family-bootstrap descriptive MAE
intervals are [1.268183,1.840697] for historical, [1.334671,1.936534] for context,
and [0.535500,0.828774] for standby. These do not account for reuse of the
mechanism-development study and do not establish across-study uncertainty.

Original and repaired engines produce byte-identical simple prediction records
for each context/standby pair on this panel. The improvement is associated with
the new standby calculation, while the backend repair addresses structural
reliability on other inputs. These two effects must not be conflated. The standby
search evaluates 1–222 states per case and selects an opened hairpin in 30/136
cases; at most three original modules occur. The complete 680-prediction collection
took 550.385 seconds on this local machine, including subprocess overhead. This is
a measured batch duration, not a portable performance guarantee.

### Freeze and reproduction

Scientific code is `75d127cc350bcc4dc54be5b980db893da3c41e92`; execution checkout was
`b32eae3405ba4d23365fd3054832080d5feb722d`, with identical runtime, source patch,
builder and parameter identities. Later commits add evidence, tests and docs.
The [predeclaration](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/22#issuecomment-6241168476)
preceded collection, and the [freeze handoff](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/22#issuecomment-6241350119)
records its boundary. Source dataset SHA-256:
`d74967eb964f1797138076ed12a35ef5f44c0ac3e87241e5186505503fd698f4`.
The prediction freeze SHA-256 is
`f0a954a34fef37e1a031e29a40419781e3e650f845d8a402f9ff40ed35713550`.
Both engines use parameter-manifest SHA-256
`ece4c4b535783cb4e03c7ce8f243d09be84a165ecd113b1d20941b5ed8b69501`.
The repaired source/patch pins are in the [admission contract](rbs-backend-repair.md).

| Engine | Executable | SHA-256 |
| --- | --- | --- |
| original | Fold | `803a5322799779df276282601a393b3d31ea35fffc4359f6d609134643ade0f6` |
| original | bifold | `2fdd2fa46ab54924fd630225cf53c35a8e78aee836fd164972bd572b9d867385` |
| original | efn2 | `1084934450523428af0ef15258f16c3f1fa174cb4949cf62e78b4581190dd8aa` |
| repaired | Fold | `22950e05e608440427942c46a1755496bd208ae433099390f9b6ebe4ce0fa30c` |
| repaired | bifold | `397f92eb38d0c8db06bcd56aa02547e017fe3f912c4062311ba18be6ccb1f2f5` |
| repaired | efn2 | `c9a23ed0e9b7416f8c06d8413f0a736e286e497e4c71a339ec3204abf7373b05` |

The repaired build-receipt byte hash is
`a88ca5647b1446c5900aced0b73515932c6457a19b3eaf7d651900a858979266`.
Different compiler/architecture builds have different binary/receipt identities;
record them instead of reusing these identifiers.

Simple prediction-file SHA-256 values, with JSON formatting as in the collector:

- historical-original: `5416806a5df38868baf1cacda32dfb6901814a72c04f85c838a000471c9f26ae`.
- context-original: `f8aa46566cfb952858ca73475c254f84e89ce12f11c0453dbfb708c6942724f2`.
- standby-original: `08ba560357307ba299dab272854ffba0842d2b6ac9533da13f5f96b732eb257d`.

The corresponding repaired context/standby files have the same hashes. Full
predictions, the pre-prediction freeze and all five evaluation JSONs are retained
in `.cache/wave3/development/` in the coordinator worktree. They contain public
development inputs and model outputs, not the reserved independent outcomes.
To reproduce without those cached artifacts, use a separate checkout whose
scientific files match the freeze, the pinned dataset and two admitted engines.
Set `REGSITE_ORIGINAL_ROOT` and `REGSITE_PATCHED_ROOT` to their installation roots,
then run the existing API and evaluator:

```python
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from regsite.backend import RnaStructure
from regsite.rbs import predict

out = Path(".cache/standby-development-reproduction")
out.mkdir(parents=True, exist_ok=False)
source = Path("benchmarks/rbs/standby2014.json")
assert hashlib.sha256(source.read_bytes()).hexdigest() == (
    "d74967eb964f1797138076ed12a35ef5f44c0ac3e87241e5186505503fd698f4"
)
records = json.loads(source.read_text())["records"]
assert len(records) == 136
subprocess.run([
    "git", "diff", "--exit-code",
    "75d127cc350bcc4dc54be5b980db893da3c41e92", "--", "src",
    "backends/rnastructure66/build.py", "backends/rnastructure66/manifest.json",
    "backends/rnastructure66/traceback.patch",
], check=True)
engines = {
    "original": RnaStructure.open(os.environ["REGSITE_ORIGINAL_ROOT"]),
    "repaired": RnaStructure.open(os.environ["REGSITE_PATCHED_ROOT"]),
}
assert engines["repaired"].identity["variant"] == "rnastructure-6.6-traceback-2"
configs = [
    ("historical-original", "historical", "original"),
    ("context-original", "context2017", "original"),
    ("context-repaired", "context2017", "repaired"),
    ("standby-original", "standby2014", "original"),
    ("standby-repaired", "standby2014", "repaired"),
]
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
(out / "freeze.json").write_text(json.dumps({
    "commit": commit, "configurations": configs,
    "backends": {key: value.identity for key, value in engines.items()},
    "aSD": "ACCUCCUUA", "temperature_c": 37, "seconds_per_record": 60,
}, indent=2) + "\n")
started = time.monotonic()
for name, profile, engine in configs:
    rows = []
    for row in records:
        if time.monotonic() - started >= 3600:
            raise RuntimeError("Collection limit reached; do not score partial output")
        result = predict({
            "id": row["id"], "sequence": row["sequence"],
            "start_positions": [row["start"]], "anti_sd": "ACCUCCUUA",
            "temperature_c": 37,
            "host": "Escherichia coli DH10B (configuration only)",
        }, engines[engine], profile=profile, seconds=60)
        site = result["sites"][0] if result["sites"] else {}
        rows.append({"id": row["id"], "status": result["status"],
                     "predicted": site.get("tir"),
                     "reason": site.get("reason", result.get("reason"))})
    predictions = out / (name + ".json")
    predictions.write_text(json.dumps({"records": rows}, indent=2, allow_nan=False) + "\n")
    subprocess.run([
        ".venv/bin/python", "-m", "benchmarks.rbs", "score", str(source),
        str(predictions), str(out / (name + "-evaluation.json")),
        "--comparison", "reconstruction-versus-experiment",
        "--prediction-identity", commit + "-" + name + "-ACCUCCUUA-37C-60s",
        "--reference", "standby2014:5'UTR_136",
    ], check=True)
```

## Limits that remain

B's exhaustive tiny oracle finds 70 possible noncrossing topologies for a
four-base duplex. Native bifold omits two valid topologies within 3 kcal/mol of
the independently evaluated minimum. Repairing malformed output does not make
this heuristic search exhaustive. Standby optimization is exhaustive only over
its declared ancestor-closed openings of one selected module, capped at 512
states; it does not jointly optimize every alternative binding site or refolding.

One synthetic input still produces no CT in the original and both repaired
engines. Review traced it to an unchanged ordinary-W fragment containing the
intermolecular linker, not the new W2/WMB2 states. The runtime returns an explicit
failed result with null score/energies on both strands. [Issue26](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/26)
tracks the remaining source diagnosis. This corrects an early reviewer claim of
40/40 valid fresh searches: that subset was 39/40. The final broader count is
69/70, and none of its failures was dropped from the denominator.

Native DP and fixed-state efn2 energies can disagree. Disconnected initiation,
coax/dangle choices and unresolved small upstream differences are classified in
the component contract. The runtime reevaluates returned structures and exposes
warnings. No NUPACK, current hosted-version or global-energy-optimality claim
follows from these tests.

Published relationships and complete test coverage do not establish predictive
accuracy in cells. The consumed Wave 2 final cohorts stay consumed, their models
stay frozen, and native UTEX calibration remains unestablished. New Cambray final
outcomes remain with the independent evaluator. Website jobs and coin purchases
are deferred.
