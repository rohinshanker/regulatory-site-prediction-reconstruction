# Reconstruction and release contract

- Purpose: Define reproducible, fully open calculator reconstruction and release requirements.
- Scope: All four calculators; RBS runtime gates are defined in rbs-runtime.md.
- Last verified: 2026-10-17

## Target and implementation identity

Recover or reconstruct the best fully open-source implementation feasible for
RBS, Promoter, Operon and Riboswitch calculators, with the closest demonstrated
agreement to De Novo DNA production behavior. Prediction and design are both
suite targets; RBS prediction is the first release milestone.

Maintain three explicit identities where applicable:

- **Historical reference:** a named public version, exact upstream commit and
  dependency/energy parameters. Porting a language must not silently change math.
- **Reconstructed model:** named equations, implementation and parameter revision,
  open folding engine, supported mechanisms, and declared deviations.
- **Hosted reference:** observation date, tool/mode, requested and returned
  versions, input/settings, export hashes and unknown server settings. A form's
  version string is not proof of the executed server version.

An accessible but restrictive upstream distribution may be inspected as allowed
or used as an optional reference. The released core cannot require it. Missing
private source triggers independent reconstruction or a documented remaining
capability gap; do not fill that gap with an unlabelled heuristic.

## Common result and coordinate requirements

Specify a versioned result schema before adapters proliferate. Include:

- Exact input identity/checksum; DNA/RNA normalization policy; full context/window
  bounds; transcript/operon identity and assumptions; host/anti-SD/sigma-factor
  settings; temperature, units and parameter set; model/code/dependency versions.
- Raw scores, defined scale, energy/feature breakdowns, structures where supported,
  warnings and uncertainty/applicability statements. No generic calibrated
  probability or absolute rate unless the underlying model establishes it.
- Explicit `ok`, `no_candidate`, `unsupported`, `invalid_input` and `failed`
  outcomes, with documented semantics. Not evaluated and no detected hit cannot
  become numeric zero or an empty successful result by accident.
- Internal sequence coordinates: zero-based, half-open intervals, explicit
  strand and orientation. Define start-codon/TSS point semantics. Separate
  sequence-relative from genomic coordinates. GenBank/GFF exports perform named,
  tested conversions; never infer boundaries from a display renderer alone.
- Multiple plausible states/sites where the model supports them; deterministic
  selection/tie policies. Stable IDs carry input/model/parameter identity.

Test reverse complements, windows touching boundaries, circular-origin spans
where supported, overlapping/alternative starts, ambiguous sequence handling,
invalid structure constraints, overflow/underflow and empty/no-hit results.

## Evaluation has three independent questions

1. **Does the implementation reproduce its specified equations?** Unit tests for
   each term, paper examples, manually checkable cases and preserved historical
   fixtures. Pin folding engines, energy tables, temperature, dangles, constraints,
   suboptimal enumeration and numerical tolerances. Substituting an open folding backend for
   NUPACK is a model change until equivalence is demonstrated.
2. **How close is it to the hosted calculator?** Freeze a held-out panel before
   tuning. Compare matching sites/states, per-term energies, log-rate errors,
   ranks, structures, warnings and coordinate/export semantics. Separate model
   and host settings, evaluation failures and missing results. Declare thresholds
   before looking at held-out results; report the full error distribution and
   coverage, not a selected example or correlation alone.
3. **How well does it predict experiments?** Use permitted primary datasets with
   exact construct/host/condition mappings, leakage-resistant splits by sequence
   family or study, and appropriate baselines. Report performance by domain,
   uncertainty, denominators and limitations. A reporter ranking, a browser host
   entry and genome-wide native calibration are different evidence levels.

Include benchmark input manifests, split identities, licences, settings and
reproducible commands. Keep calibration separate from evaluation. Prediction
and sequence-design modes need separate tests; designed candidates are rescored
and checked against every stated sequence/structure constraint.

## Fully usable release

For the RBS wave, apply [native validation](rbs-native-validation.md) and
[comparator selection](rbs-comparator-landscape.md) in addition to the three
questions above. Real experimental TSS context, TIS localization and translation
strength are separate evidence types and require separate claims/metrics.
Compare suitable mechanistic and learned methods; record pretrained-data overlap,
code/weight/data permissions and coverage. Preserve the compatibility profile
when developing a cyanobacterial specialist. A narrowly scoped, independently
demonstrated improvement is the promotion target; universal superiority cannot
be inferred from one reporter panel or website agreement.


- Source and required model parameters are available under compatible open terms;
  preserve notices and supply a component/dependency inventory. No private
  `DNAc`, required NUPACK research licence, `.pyc`-only module, or account dependency.
- A clean supported environment can install and run library/CLI examples with
  pinned dependencies. Standard inference and CI work without network access.
- Single and batch modes have bounded time/memory behavior, deterministic seeds
  where appropriate, actionable errors and tested result/export schemas.
- Run all unit/integration tests and branch coverage; exercise every new path.
  Check supported Python/platform combinations in CI. Include an end-to-end
  fresh-install smoke test and scientifically meaningful regression benchmarks.
- Document supported/unsupported mechanisms, model versions, input domains,
  measured runtime envelopes and hosted differences. A release may honestly be
  a useful reconstruction with quantified discrepancies; exact equivalence is
  only claimed after the relevant comparisons pass.
- No calculator ticket is closed merely because source hunting ended. Its
  functional acceptance criteria must pass, or the owner must explicitly change
  its scope. Unknowns remain tracked while independent work continues.

## RBS 0.4.0rc1 applicability

The candidate includes historical, footprint/context, published-standby and
[joint binding/standby](rbs-joint-selection.md) profiles, a transcript-aware native
adapter, versioned JSON/CSV/GFF3 exports and frozen experimental learned models. The [runtime](rbs-runtime.md),
[native adapter](rbs-native-runtime.md) and [learned runtime](rbs-learning-runtime.md)
contracts define their inputs, limits and reproduction commands. Single/batch
examples and the two-strand PCC 6803 genome example ship with the source release.

The [independent Wave 2 result card](rbs-wave2-results.md) records the original
learned-model scientific gate. It reports a failed model-promotion decision, restricted comparator
roles, backend failure coverage and limits on native transfer. Learned models
remain experimental; release availability does not imply superiority. The
immutable [freeze](../../models/rbs/wave2-freeze.json) and
[prediction receipt](../../models/rbs/wave2-prediction-receipt.json) identify the
evaluated code, weights, inputs and controls. New scientific changes require a
new development cycle and untouched evaluation.

The [standby contract](rbs-standby.md) defines schema 1.2, source equations,
structural optimization and declared reconstruction choices. The optional
[traceback repair](rbs-backend-repair.md) is a separately identified GPL-2.0-only
component, built outside the GPL-3.0-or-later Python runtime and communicated with
through files/processes. The source distribution preserves its separate licence;
the wheel contains no backend code or executable. Original profiles, installations
and Wave 2 artifacts remain available. The separate linker-3 component corrects
ordinary WMB linker handling and retains its own source/patch/build identity.
Joint selection uses schema 1.3 with complete-search diagnostics, explicit limits
and null-score incomplete searches. Its scientific gate is the frozen
[Wave 4 independent protocol](rbs-wave4-evaluation.md): Cambray ordinary protein
output is primary, Kuo is exposed secondary, and no native calibration follows.
The [completed joint-model result](rbs-joint-selection.md#frozen-independent-experimental-result)
failed that advancement gate: both primary profiles covered 335/335 inputs,
but the paired rank gain was -0.000166 with a 95% interval spanning zero.
The selected Cambray panel and earlier final cohorts are now consumed. Joint
selection remains an opt-in research profile, with no new native-calibration or
biological superiority claim. A lower optimized energy or repaired folding
failure alone cannot satisfy the experimental advancement gate.

Remaining scope includes drafting, kinetics and distinct production stacking,
backend enumeration differences, design modes, the other three calculators and
native UTEX calibration. A draft release candidate does not close those tickets.
Main merge, a public tag/package and downstream consumer admission are separate
release actions.

## Hosted access

The owner previously signed into an isolated Chrome session; that session was
closed. Ask for another login only when an actual gated inspection or benchmark
requires it. Public source retrieval, implementation and offline tests need no
login. Never commit account screenshots, cookies, credentials or private jobs.
The owner explicitly authorizes planning and using coins for live-reference
validation. Start with a small diagnostic panel, then propose a larger frozen,
stratified panel when its expected evidential gain warrants the cost. Publish
job counts, observed coin pricing, total estimate and stop conditions before
each stage. The owner can request lab funding to buy more coins; prepare a
reviewable sample-size/rationale/budget proposal, without purchasing credits
until instructed.

If coins are exhausted, the owner can provide another lab member's authorized
login, subject to that account holder's authorization and provider rules. Pause
the exhausted account, reconcile completed/pending jobs and resume in the new
secure browser session; never obtain credentials from others or create accounts
on their behalf. Maintain a private job/coin ledger and immutable output hashes
to avoid duplicate paid submissions. Use nonidentifying account-session labels
in benchmark provenance and keep sessions/settings distinguishable.

Use public/permitted benchmark inputs. Record actual output versions and
coordinate behavior; public UI code establishes a contract hypothesis, not
successful model execution. Coin-funded reference collection must not become
a dependency for anyone running the released open-source calculators.
