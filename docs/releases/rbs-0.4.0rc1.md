# RBS 0.4.0rc1 — provisional pre-release

This provisional package adds an opt-in RBS model that selects a ribosome-binding configuration only after evaluating its complete binding and RNA-opening energy. It also repairs a separately installed RNAstructure folding failure. The independent experiment did **not** demonstrate better biological prediction, so the new model remains experimental and the historical default is unchanged.

This is a provisional research package, not a production-equivalent De Novo DNA calculator. The exact source/wheel below correspond to integration commit `9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923`. Documentation added after that archive was built clarifies interpretation and publication; it does not change those packaged runtime bytes.

## Changes

- `joint_standby` evaluates each eligible returned binding candidate with its own assembled-complex and optimized standby cost. Schema 1.3 records stable candidate identities, complete-search counts, selected structures and the former greedy choice's complete energy. An incomplete candidate prevents a definitive winning score.
- The independent GPL-2.0-only `rnastructure-6.6-linker-3` component fixes two ordinary-WMB linker-marker omissions that caused a reproducible zero-exit/no-structure failure. Source, patch, build and runtime identities are explicit. Existing engine installations are preserved.
- Historical, footprint, context and standby profiles retain their behavior on the same engine. Frozen learned weights are unchanged. The GPL-3.0-or-later Python runtime requires Python 3.11 or newer and no third-party Python runtime packages.
- Reviewed Promoter reference artifacts supply 212 independently checked synthetic states and explicit historical-wrapper discrepancies. They prepare the later Promoter implementation; they are not a project Promoter runtime or experimental-accuracy result.

## Independent finding

Both joint and standby profiles scored all 335 primary Cambray inputs, including all 332 measured means. Joint/standby Spearman correlation was 0.436083/0.436250. The paired gain was -0.000166, with 95% seed-block interval [-0.000905, 0.000205]. All 10,000 resamples were usable; the prespecified gain-of-0.05 and positive-interval gates failed. This does not establish equivalence or significant degradation.

On the same panel the historical default had a descriptively higher Spearman correlation of 0.501889, versus 0.436250 for standby and 0.436083 for joint. The historical-minus-standby difference was 0.065640, with 95% interval [-0.078068, 0.201101]. This does not establish superiority; the standby gain on the earlier public development panel did not establish an advantage on this independent study.

Joint's median time was 5.082 seconds versus 1.473 seconds for standby, about 3.45 times longer under the two-worker collection protocol. Across 11 configurations and 596 inputs, all 6,556 attempts were accounted for: 6,520 successful and 36 explicit no-candidate results, with no other statuses, retries or artifact changes. The selected Cambray panel is consumed and cannot be reused as untouched validation. Kuo remains exposed secondary evidence; training overlap and its unknown measurement logarithm base constrain interpretation.

The [complete independent report](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923/docs/validation/rbs-wave4-results.md) includes all comparisons, uncertainty, coverage and assay limitations. Protein fluorescence is not a direct measurement of translation initiation or RNA-normalized translation efficiency. No hosted equivalence, native cyanobacterial calibration or universal superiority is claimed.

## Exact candidate and validation

- Scientific execution commit: `a11cb5bd13d3c021eedc98cf451609eb4710bb6a`.
- Final integration commit: `9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923`.
- Independently reviewed Session B result: `c1c820c47974e934714685f829317c3f44bcf4e2`, integrated without changing its report or aggregate bytes.
- Final local real-backend suite: 1,624 passed in 234.20 seconds, with 100% measured coverage of 5,812 Python statements and 2,390 branches. Five inherited runpy warnings remain. The separate original/traceback-2/linker-3 component suite passed 35 checks. Ruff, format, mypy, dependency, ticket and local-link checks passed.
- Final wheel fresh installation used `pip install --no-index --no-deps`. All single/batch/native, JSON/CSV/GFF3, joint/legacy and learned-model example assertions passed with the three separately installed engines.
- [Final integration CI39088709792](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/actions/runs/39088709792) and its final status are recorded in `artifact-manifest.json`. Its four jobs cover Ubuntu 24.04/macOS 14 and Python 3.11/3.14, all three engines and fresh offline examples. Windows is unverified.

Run the combined suite from the source checkout with the selected real engine:

```sh
REGSITE_RNASTRUCTURE=/path/to/linker-3/RNAstructure \
  .venv/bin/python -m pytest --cov=regsite --cov=benchmarks.rbs \
  --cov=benchmarks.promoter --cov=experiments.rbs --cov-report=term-missing
```

The [release and upgrade guide](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/9edb989fbfa6d252d0c1b7b12c1a4d0a7d0ce923/docs/validation/rbs-0.4-release.md) provides the pinned backend build, offline installation, examples, validation recipes and component licence inventory. `SHA256SUMS` verifies the distributed files. A wheel rebuilt from the exact source archive with the locked build tools and `SOURCE_DATE_EPOCH=1792289003` reproduced the distributed wheel hash in independent review; an ordinary rebuild can differ. Use a fresh environment or force-reinstall the exact wheel if an earlier development build already has the same `0.4.0rc1` version string.

## Artifacts and remaining boundaries

| Artifact | SHA-256 |
| --- | --- |
| `regulatory_site_prediction_reconstruction-0.4.0rc1.tar.gz` | `13b4975f01a4cc8472975f90531908badcc55a654f14df673c5d44539311e7f4` |
| `regulatory_site_prediction_reconstruction-0.4.0rc1-py3-none-any.whl` | `f6ef1dd8f38157dc7367ebcb0465c37dd0c2f5910825c06f94a8c9f8b99f9c94` |

The source archive contains 430 files, limited to tracked source and generated package metadata. All 23 wheel runtime files match the frozen scientific checkout. Required notices and separately licensed backend patches are included; backend binaries/tables, optional restrictive research environments, private outcomes and credentials are absent. Exact archive hashes identify these builds; no bit-for-bit source-archive reproducibility claim is made.

The model searches a bounded returned candidate set, with defaults of 100 returned candidates, 512 opening states per candidate, 4,096 attempted bound evaluations per site and a 60-second record deadline. Exhaustion remains an explicit null-score result. This is not exhaustive folding, NUPACK parity or a calibrated absolute initiation rate. Kinetic/coupling extensions, leaderless initiation, sequence design and the remaining calculator runtimes are outside this candidate.

Further RBS accuracy work needs a new development/evaluation cycle and independent data; the completed negative result must not be tuned into a retrospective success. Promoter, Operon, Riboswitch and downstream cyano admission have separate implementation and validation milestones. The bundled artifact manifest records a preparation snapshot, not a live publication-status feed. PyPI distribution is outside this release handoff: its metadata needs a separate mixed-component licence and long-description review.
