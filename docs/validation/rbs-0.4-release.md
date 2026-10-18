# RBS 0.4.0rc1 release candidate

- Purpose: Define the installable candidate, upgrade procedure and publication boundary.
- Scope: Local RBS prediction; independently installed folding executables.
- Last verified: 2026-10-18

## Candidate and compatibility

This is a release candidate for review, not a published package or release tag.
[PR31](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/pull/31)
contains the integration. The [scientific receipt](../../models/rbs/wave4-candidate.json)
pins execution commit `a11cb5bd13d3c021eedc98cf451609eb4710bb6a`; later
integration commits may add documentation, reference artifacts and packaging
notices without changing those frozen scoring files. Archive hashes belong in
an external `SHA256SUMS` file, so the archive need not contain its own hash.

The new opt-in `joint_standby` model compares complete initiation energies across
all eligible returned binding candidates. Each candidate includes its own RNA
opening and standby search. A failed or unfinished candidate prevents a winning
score for that site. Schema 1.3 reports the selected candidate, the former greedy
choice's complete energy and explicit search counts. The
[model card](rbs-joint-selection.md) defines the objective, numerical tie policy,
limits and measured resource costs.

The separate `rnastructure-6.6-linker-3` component repairs ordinary-WMB linker
handling and retains the earlier traceback repair. Its source invariant and
limitations are in the [backend contract](rbs-backend-repair.md). It must use a
new installation directory and backend identity. An executable that produces a
valid structure is not thereby experimentally calibrated.

The historical default and schemas 1.0–1.2 remain available. Earlier profiles
preserve their behavior on the same engine, and frozen learned weights are
unchanged. Backend changes can alter structures and scores, so compare results
only with their explicit engine identities. Upgrading the package changes
`implementation_version` and its derived prediction IDs even when numerical
results are unchanged. JSON readers must select the schema recorded in each
result; CSV is a compact summary, and full search diagnostics require JSON.

## Install and upgrade

Python 3.11 or newer is required. CI verifies Python 3.11 and 3.14 on Ubuntu
24.04 and macOS 14; Windows is unverified. Choose an interpreter that meets this
requirement explicitly: some Macs have an older `python3` earlier on PATH.

From the extracted source distribution, prepare the locked build tools and
build the source and wheel locally:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m build --no-isolation
```

This preparation can use the network. The wheel has no required third-party
Python dependencies. A fresh installation from an already built wheel is offline:

```sh
python3.14 -m venv .cache/fresh
.cache/fresh/bin/python -m pip install --no-index --no-deps dist/*.whl
```

For an existing environment, use its Python executable with
`pip install --no-index --no-deps --upgrade PATH_TO_WHEEL`. If it already has an
earlier unpublished `0.4.0rc1` development build, use a fresh environment or add
`--force-reinstall` with the exact reviewed wheel: equal version strings do not
identify equal development artifacts. Verify the wheel against its accompanying
`SHA256SUMS`. Those checksums identify the distributed archives; an ordinary
local rebuild need not have identical bytes. To reproduce the reviewed wheel
from the exact `9edb989` source distribution using its locked build tools, run
`SOURCE_DATE_EPOCH=1792289003 .venv/bin/python -m build --no-isolation --wheel`.
This reproduced wheel SHA256
`f6ef1dd8f38157dc7367ebcb0465c37dd0c2f5910825c06f94a8c9f8b99f9c94`
in independent review. Source-archive byte reproducibility is not claimed.
Keep any prior engine installation intact.
Follow the [backend source recipe](rbs-backend-repair.md)
to build linker-3 from the pinned archive into a separate user-writable directory:

```sh
.venv/bin/python backends/rnastructure66/build.py \
  --archive /path/to/RNAstructureSource.tgz \
  --destination /path/to/new-linker3-installation \
  --component rnastructure-6.6-linker-3 --jobs 2
export REGSITE_RNASTRUCTURE="/path/to/new-linker3-installation/RNAstructure"
.cache/fresh/bin/regsite examples/rbs-single.json --profile joint_standby
.cache/fresh/bin/regsite examples/rbs-batch.json --profile joint_standby --format csv
.cache/fresh/bin/regsite-native examples/rbs-native-karlsen.json --profile joint_standby
```

The source archive SHA-256 must be
`1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3`.
The builder checks it and refuses an existing destination. A C++ compiler and,
on macOS, the already installed command-line SDK are needed for the build.
Neither installed inference nor the offline wheel installation uses accounts,
website coins or paid services. Preserve the JSON output's model, host settings,
backend binaries/table identities and warnings with downstream analyses.

## Distributed components

| Component | Distribution and terms |
| --- | --- |
| Python runtime and model parameters | Wheel/source; GPL-3.0-or-later, with Salis equation attribution in NOTICE. Required runtime dependencies: Python standard library only. |
| Backend patches, builder and structural fixtures | Source distribution only, separate GPL-2.0-only component and LICENSE. No backend library is linked into the Python runtime. |
| RNAstructure executables and thermodynamic tables | Independently obtained/built; absent from both project wheel and source archive. Preserve upstream source and notices when distributing them separately. |
| Schemas, examples, admitted fixtures and frozen experimental models | Source distribution; per-source provenance and model cards govern interpretation and admitted data use. The wheel includes its small pinned table-hash manifests, not the tables. |
| Promoter reference tooling and parameter conversions | Source distribution only; GPL-3.0-or-later, with COPYING, NOTICE, ORIGINAL-NOTICE and the explicit compatibility patch. This is reference preparation, not a project Promoter calculator. |
| Build/test tools | Hash-locked development dependencies; not required or bundled at inference. |
| OSTIR/ViennaRNA and rebeca comparison environments | Optional research environments only; not bundled or required by this release. Their restrictions/exposure remain in the comparator contracts. |

The archives contain no private outcomes, individual residuals, credentials,
website job exports or optional comparator installations. See [NOTICE](../../NOTICE),
the [source decision](rbs-source-decision.md) and
[Promoter reference provenance](promoter-executed-reference.md).

## Verification and scientific limits

The frozen candidate passed all four jobs in
[CI run 39080285855](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39080285855),
including full real-engine checks and fresh offline examples. Its local combined
suite passed 1,614 tests at 100% measured Python statement/branch coverage;
the separate three-engine component suite passed 35 checks. After integrating
Promoter reference tests, the combined suite passed 1,624 tests at 100% coverage
of 5,812 statements and 2,390 branches. This is test coverage of the included
Python scopes, not a claim of complete upstream C++ or biological validation.
All four jobs in [integration CI39082135334](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39082135334)
also passed at `1d4b6225232a7febeba039b8ca2fe8871e4c5204`, including the
Promoter references. Exact-patch runtime and backend reviews are recorded in
the candidate receipt. Final artifact manifests and the draft PR identify the
subsequent documentation/evidence integration and its CI without modifying the
frozen scientific code.
Use the [runtime validation commands](rbs-runtime.md) and backend three-engine
commands to reproduce these gates with real installed engines.

All 136 public 2014 development inputs completed on both repaired backends and
produced identical site outputs. With linker-3 the median/p95/maximum per-record
times were 0.870/1.920/2.500 seconds on the measured arm64 host. These are
shared-host observations, not service guarantees. The default per-record budget
is 60 seconds, with at most 100 returned candidates, 512 opening states per
candidate and 4,096 attempted bound-state evaluations per joint site. Budget
exhaustion remains an explicit null-score failure. There is no OS memory quota.

The [frozen Wave 4 experiment](rbs-joint-selection.md#frozen-independent-experimental-result)
did not advance joint selection. Both primary profiles scored all 335 Cambray
inputs, with 332 measured common-success rows. Joint/standby Spearman rho was
0.436083/0.436250; the paired gain was -0.000166, with 95% seed-block interval
[-0.000905, 0.000205]. The gain-of-0.05 and interval-above-zero gates failed.
All 10,000 paired draws were usable. This is a completed negative advancement
result; no model/settings change or additional study inference followed it.

The historical default scored descriptively higher on that same panel:
Spearman 0.501889 versus 0.436250 for standby. The historical-minus-standby
difference was 0.065640, with 95% interval [-0.078068, 0.201101]. That interval
spans zero, so this comparison establishes no superiority. The public 2014
development-panel gain is not proof of a gain on this independent study.

The complete 11-configuration, 596-input collection took 64.4 minutes and
accounted for all 6,556 attempts: 6,520 successful and 36 explicit no-candidate
results, with no other statuses. All missing candidates belonged to the six
mechanistic configurations on six Kuo fepB inputs. Kuo is exposed secondary;
its unknown logarithm base prohibits log2/fold-error conversion, and rebeca's
training overlap precludes independent Kuo validation. Constant Cambray UTR-only
ML predictions retain undefined rank correlation. Software success and lower
computed energy do not establish better experimental prediction. The panel is
consumed; further models require a new evaluation cycle. Primary median times
were 5.082 seconds for joint and 1.473 seconds for standby, about a 3.45-fold
cost increase. Read the [complete independent report](rbs-wave4-results.md)
for all descriptive comparisons, uncertainty and source limitations.

The calculation remains a bounded equilibrium reconstruction. It cannot promise
exhaustive cofold enumeration, NUPACK equivalence, current hosted behavior,
absolute initiation rates or native UTEX calibration. Leaderless initiation,
kinetic and coupling extensions, sequence design and the other three calculator
runtimes remain outside this release. Tan 2018 transcription starts do not supply
translation-initiation labels. Existing experimental learned models retain their
failed/limited promotion findings.

## Publication boundary

The branch, draft PR and local source/wheel are authorized review artifacts.
An approved main merge, version tag and package/release publication remain
separate actions under ticket 06. Do not imply that a candidate artifact clears
that milestone. Promoter runtime ticket 07 and consumer admission ticket 10
retain their release dependencies; no cyano checkout changes are included here.

The [publication handoff](rbs-publication.md) defines the cumulative review,
immutable archive identities, corrected release-body staging and exact
SHA-preserving integration procedure. Its preparation does not publish anything.

PR31 is an incremental Wave 4 review against `planning/wave4`, which already
contains the earlier implementation waves. The default `main` branch remains
at planning commit `b77982875f3823fc50fbe918a129a4a4ada2e9d1`. Before publication,
review and reconcile the complete candidate tree against the then-current main,
including the integrated evidence commits. This cumulative integration is part
of ticket 06; the incremental Wave 4 diff alone is not the complete calculator.
