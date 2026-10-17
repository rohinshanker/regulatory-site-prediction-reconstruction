# Independent Wave 4 evaluation protocol

- Purpose: Freeze rank-based experimental evaluation before candidate predictions meet reserved labels.
- Scope: Cambray ordinary protein output; Kuo exposed secondary; bounded fixed comparators and controls.
- Last verified: 2026-10-17

Verification covers synthetic arithmetic and input integrity, not a new experimental comparison.

The executable [protocol](../../benchmarks/rbs/wave4-protocol.json) binds the
Wave 3 input, split and private-outcome hashes. Selection freeze
`55da050fc3543cf9ff61e41eb269c3071d92b9fc` predates source extraction. The
[source/data contract](rbs-new-evaluation-data.md) remains authoritative for
sequence recipes, conditions, licences, exposure and missing measurements.
No final measurements or per-case residuals may be transmitted to A or committed.

## Endpoint and contrasts

The primary endpoint is the deposited ordinary `clean.lin.prot.mean` protein
fluorescence for the fixed 335 Cambray inputs, including three missing means.
It is neither measured initiation rate nor RNA-normalized TE. Prediction coverage
uses all 335 inputs; rank uses finite measured/predicted pairs and reports that
count. A failed prediction never becomes zero, and missing observations never
become negatives. No scale fit, logarithmic/fold error, outlier removal or
success-dependent panel selection is performed.

One confirmatory contrast is **joint_standby minus standby2014 Spearman rho on
the same backend**, using a new independently reviewed backend if admitted before
the freeze, otherwise traceback-2. If joint scoring is not review-ready, only A's
explicit fallback freeze and acknowledgement that the panel will be consumed can
activate standby2014 minus historical on traceback-2. No early outcome peek is a
backend-admission or fallback-selection criterion.

The bounded roster contains historical/standby/joint on traceback-2, optionally
the same three on the newly admitted backend, and admitted OSTIR 1.1.3,
public 2014 sequence-v1 and rebeca exp67_true: at most nine non-control entries.
All entries must be identified before collection. Other model/engine contrasts
are descriptive; no multiplicity-adjusted superiority claim follows from them.
Two fixed controls are constant 1 and GC fraction in the common available
`[max(0,start-35), min(length,start+70))` window. Higher GC has higher score;
its sign and scale cannot be chosen after observing performance.

Kuo's 261 inputs remain exposed secondary, analyzed as three separate 87-input
contexts. Missing means remain explicit. Their log base is unresolved; no
exponentiation, log2/fold-error conversion or cross-context pooling is permitted.
The nine-mer universe is one connected sequence family, so no independent-family
uncertainty or promotion test is claimed for Kuo. rebeca's Kuo training exposure
precludes an independent Kuo superiority claim. Facilitated Cambray outcomes are
outside this wave's endpoint roster and will not be joined.

## Paired block uncertainty and decision

Average ranks preserve exact ties. Undefined correlation (fewer than two pairs
or a constant vector) is JSON null, never zero. The primary contrast uses the
**same measured common-success rows** for both correlations; differences of two
all-success correlations with different membership are not the primary effect.
All-case baseline-success preservation is evaluated separately, including inputs
with absent measurements.

Resample all 56 original seed blocks with replacement, retaining every member,
both selected design families, repeated blocks and blocks without common usable
pairs. Filter to common finite measured successes only after drawing. Recompute
ranks with the resulting multiplicities in each draw; do not reuse original
ranks or resample nearby design rows as independent. Use 10,000 paired draws,
seed 20261018. Point/interval estimation requires at least 30 common measured rows
and 10 represented common-success blocks. Undefined draws are counted explicitly.
At least 9,900 usable draws are required. The 95% interval selects sorted usable
draws at `floor(.025*(n-1))` and `ceil(.975*(n-1))`, without interpolation.
An undefined point or insufficient support/usable draws makes advancement
ineligible; do not alter the rule after results.

Advance only when **all** conditions hold:

- At least 95% candidate coverage over the full primary panel (319/335 or more).
- No baseline-success input is lost, whether or not its measurement is available.
- Paired point gain at least 0.05, with the 95% block interval strictly above zero.
- Complete collection and the acknowledged software/resource gates.

The 0.05 threshold is an engineering requirement for added complexity. The
[synthetic feasibility artifact](../../benchmarks/rbs/wave4-synthetic-feasibility.json)
uses invented correlated labels/noise and the frozen input grouping to exercise
null, constant, modest and large improvements. It is not estimated biological
power, a minimum detectable biological effect or a noise ceiling. Block intervals
condition on one study and do not estimate between-study or assay-replicate noise.

Predeclared descriptive Cambray strata use GC of available coding sequence after
`start+3`: below 0.4, [0.4,0.6), and at least 0.6. Their input-only counts are 31,
303 and1. Retain all strata in coverage tables; only display a subgroup paired
rank difference with at least 30 measured common successes. There is no subgroup
promotion gate or post-result subgroup creation. Kuo contexts are its only strata.

## Candidate receipt and collection boundary

A supplies an immutable receipt, followed by B's explicit acknowledgement:

- Exact scientific/execution commits; model/profile/schema names; source, weight,
  parameter and engine-source/patch/table/binary/build-receipt hashes.
- Exact input/split hashes, native units, temperature 37 C, aSD `ACCUCCUUA`, host
  metadata, declared training/development exposure, all state/work/deadline caps.
- Executable commands, independent review identity, completed software/resource
  gates and backend-admission decision. Any fallback requires explicit consent
  to consumption of the final panel.

B will call the frozen public prediction boundary in isolated subprocesses,
without inspecting model-scoring internals. Requests preserve exact supplied
sequence and zero-based start, transcript orientation `+`, anti-SD and temperature.
Cambray host metadata is E. coli MDS42 delta-recA; Kuo is MG1655, both configuration
labels rather than inferred calibrations. Per-record normalized results contain
`id`, `input_sha256`, `configuration_sha256`, `status`, `predicted`, categorical
`reason`, elapsed `seconds` and raw-output hash. A successful score must be finite;
failed/unsupported/no-candidate/invalid/timeout/not-run records have null scores.
Native mechanistic/OSTIR positive scales and learned native scales are retained;
no final-set calibration is applied.

Collection allows at most two scoring processes, 60 seconds per record and four
hours total. Submit Cambray before Kuo, sorted input IDs within study, with sorted
model IDs cyclically rotated by input index in deterministic record-major order.
Controls are deterministic input calculations. A per-record timeout terminates
its process group and is not retried. At the global cap stop scheduling, terminate
running work, retain all remaining rows as not_run, mark collection incomplete
and prohibit advancement. Preserve raw stdout/stderr and immutable per-record
receipts in a new 0700 private directory with 0600 files. Do not overwrite an
existing collection or silently resume/retry a failed attempt.

All admitted model collections and their hashes must be finalized before the
first real-label join. Reports preserve each failure category, all-case coverage,
shared-success counts and elapsed-time median/p95/max over executed records,
including failures. No success-only runtime denominator replaces attempted work.
If a genuine scoring bug invalidates a candidate, retain its attempted artifacts
and label any correction/rerun as a consumed-panel reanalysis. Do not re-label it
an untouched test.

## Independent implementation checks

[Rank metrics](../../benchmarks/rbs/wave4_metrics.py) import no reconstruction
model. Hand-checked tie fixtures, exact gate boundaries, identity/metadata guards,
empty blocks, constant vectors, missing labels, lost successes and undefined
resamples exercise the calculation. The separate finite-state
[joint oracle](../../benchmarks/rbs/joint-selection-fixtures.json) uses invented
energies and Decimal arithmetic, without reading A's scoring implementation.
It includes a greedy loser, a singleton, exact candidate/state ties and forward,
reverse and circular interval mappings. These are mathematical controls, not
measured sequences or a new folding implementation.

```sh
python -m unittest discover -s tests/benchmarks -p 'test_wave4_*.py'
python -m unittest discover -s tests/benchmarks -p test_joint_selection_oracle.py
python -m benchmarks.rbs.wave4_feasibility INPUT_ONLY.json benchmarks/rbs/wave4-protocol.json NEW_SYNTHETIC_AGGREGATE.json
```

The feasibility command checks the exact frozen input hash and exclusively creates
its output. Use the existing input-only export; it does not need raw source tables
or private measurements. Optional comparator environments remain outside required
runtime/package dependencies. No website jobs, coins or release actions belong to
this experiment. A acknowledges this protocol before final candidate execution;
review corrections must be visibly committed before any real-label join.
