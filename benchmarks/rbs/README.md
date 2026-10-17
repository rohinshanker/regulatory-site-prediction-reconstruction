# Independent RBS evidence and evaluation

These tools do not import the reconstructed calculator. Python 3.11+ and the
standard library suffice for public tests and scoring. Spreadsheet ingestion
alone needs `xlrd==2.0.2` and `openpyxl==3.1.5`; install them in a separate analysis
environment, not the calculator's required dependencies.
The inspected analysis environment also used `et_xmlfile==2.0.0` (MIT). openpyxl
is MIT; xlrd's actual notice contains both BSD-3-Clause text and older advertising/
acknowledgment conditions. The manifest pins those notices. None is vendored;
do not bundle xlrd with GPL code based only on its generic “BSD” metadata.

| Artifact | Identity and use |
| --- | --- |
| `sources.json` | Component source pins, licences and disposition |
| `scalar-fixtures.json` | Independently calculated source equations, not experimental outcomes |
| `rnastructure-smoke-fixtures.json`, `rnastructure-tables.json` | Open backend observations and table hashes |
| `dataset-manifest.json` | Primary source identities, assay context, licence and exact row mappings |
| `standby2014.json` | 136 CC-BY-3.0 development constructs and measurements |
| `experimental-split.json` | Frozen identities for 136 development and 27 held-out constructs; no held-out outcomes |
| `historical-audit.json` | Independently recomputed historical statistics, never current-server accuracy |
| `live-diagnostic-panel.json` | Twelve exact inputs, declared starts/settings and spending cap |

Read the [protocol](../../docs/validation/rbs-evaluation-protocol.md),
[quality card](../../docs/validation/rbs-benchmark-card.md),
[source decision](../../docs/validation/rbs-source-decision.md) and
[live runbook](../../docs/validation/rbs-live-reference.md) before evaluation.

## Offline checks

From the worktree root:

```sh
python -m unittest discover -s tests/benchmarks -v
```

All fixtures and unit tests are offline. No calculator, folding executable,
account, private measurement file or paid oracle is required.

## Reproduce source extraction and historical statistics

The fetch command downloads only the declared archive members, verifies SHA-256
before saving, rejects changed cached files and refuses a source cache inside this
repository. Restricted supplements must remain outside Git. It does not execute
any downloaded code. Europe PMC's enclosing ZIP timestamps can change; the
extracted scientific files, not the enclosing ZIP, are the pinned identity.

```sh
RBS_CACHE=/tmp/rbs-source-cache
RBS_PRIVATE=/tmp/rbs-private-evaluation
mkdir -p "$RBS_CACHE" "$RBS_PRIVATE"
chmod 700 "$RBS_CACHE" "$RBS_PRIVATE"
python -m venv "$RBS_CACHE/analysis-venv"
"$RBS_CACHE/analysis-venv/bin/pip" install xlrd==2.0.2 openpyxl==3.1.5 et_xmlfile==2.0.0
"$RBS_CACHE/analysis-venv/bin/python" -m benchmarks.rbs fetch "$RBS_CACHE"
"$RBS_CACHE/analysis-venv/bin/python" -m benchmarks.rbs prepare "$RBS_CACHE" benchmarks/rbs "$RBS_PRIVATE"
"$RBS_CACHE/analysis-venv/bin/python" -m benchmarks.rbs audit "$RBS_CACHE" "$RBS_PRIVATE/historical-audit.json"
cmp benchmarks/rbs/historical-audit.json "$RBS_PRIVATE/historical-audit.json"
```

`openpyxl` warns about an unsupported extension while reading the 2017 workbook.
The original is opened read-only and never saved; its pinned bytes remain intact.
The split SHA-256 must remain
`2e07f821019e1e295b39bf8c70bd123b80d3b4625639b762cbf9a6474af02e93`.
Stop and investigate any source/hash/schema change; do not update a pin merely to
make an extraction pass.

The 2009 source is an author-curated copy in pinned SynBioMTS; its equality to
the inaccessible publisher supplement is unproven. The 2014/2017 sources are
publisher supplements delivered through Europe PMC. The 2020 sources are primary
ACS Figshare supplements. Raw 2017 and 2020 data have noncommercial terms and are
not redistributed here. The 2014 derivative preserves attribution under
[CC-BY-3.0](https://creativecommons.org/licenses/by/3.0/); modifications are DNA
case/U normalization, start/sequence reconstruction and schema extraction.

## Evaluate frozen predictions

Prediction JSON is `{"records": [{"id": "…", "status": "ok", "predicted": 123.4}]}`.
Use exact dataset IDs. Other statuses: `failed`, `no_candidate`, `unsupported`,
`invalid_input`, `not_evaluated`. Missing IDs count as not evaluated; duplicate or
unknown IDs and nonpositive successful predictions fail closed. No slope,
intercept, residual trimming or hidden normalization is fitted.

```sh
python -m benchmarks.rbs score benchmarks/rbs/standby2014.json predictions.json evaluation.json \
  --comparison reconstruction-versus-experiment \
  --prediction-identity COMMIT_AND_SETTINGS_DIGEST \
  --reference "standby2014:5'UTR_136"
```

For final held-out evaluation use the private `footprint2017.json` and reference
`footprint2017:AEB-1`, after freezing model commits/settings. That file explicitly
marks nine missing translation measurements; output reports 27 constructs,
18 eligible measurements, and nine exclusions. Prediction failures among the
18 still count against coverage/fold fractions. Keep final outcomes and reports
with the independent evaluator until the agreed evaluation, not in tuning feeds.

For the separate fluorescence sensitivity, copy records in memory with `observed`
set to `fluorescence_mean` and `measurement_status` to `available`; all 27 qualify.
Record that outcome transformation and input hash. Do not call fluorescence an
mRNA-normalized initiation measurement. `live-versus-experiment` requires the same
control. `reconstruction-versus-live` accepts matching positive raw rates without
experimental normalization; source identity and comparison label are mandatory.

The CLI records file hashes and a caller-supplied prediction identity. It cannot
verify that a caller actually froze a model, kept a holdout secret, or used correct
coordinates; those remain evaluator responsibilities. Family bootstrap returns
null for the one-family 2017 panel. A constant-relative-rate baseline is included
for reference-normalized comparisons.

## Verify private live CSVs

For a completed job with a supported CSV export:

```sh
python -m benchmarks.rbs.live benchmarks/rbs/live-diagnostic-panel.json w1-atg \
  "$RBS_PRIVATE/w1-atg.csv"
```

This validates the exact CSV schema, frozen input hash, unique zero-based start
coordinates, finite energies, positive rates and component sums. It reports target
coverage, warnings and the byte-preserving CSV hash; it does not assess biological
accuracy. A header-only CSV is a valid empty result. A form rejection or server
failure is recorded separately and is never converted into an invented empty CSV
or a zero translation rate. An empty candidate set cannot verify energy arithmetic.

## Wave 2 native interface

The [native input contract](../../docs/validation/rbs-native-input-contract.md)
provides a genome-once batch example, independent strand/origin fixtures and
primary-source pins. Native translation outcomes remain private until eligibility
and grouped partitions are frozen; Tan TSS evidence is context only.
