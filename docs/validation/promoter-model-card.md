# Promoter model card

- Purpose: State what the implemented historical Promoter model is, what its checks establish and what it cannot support.
- Scope: `promoter-lafleur2022-historical-1` in package 0.5.0rc1 (`regsite-promoter`); documentation only, no new measurement or model change. Tickets #33 and #7 remain open.
- Last verified: 2026-10-18
- Source candidate: `2dff23cb5697507281f7ffa73fc617d56989b40c`

Normative detail is in the [runtime contract](promoter-runtime.md). This card
summarizes meaning and limits; where they differ, the runtime contract and the
[result schema](../../schemas/promoter-result-1.0.schema.json) govern.

## Summary

The calculator is a standard-library, offline reconstruction of the published
La Fleur et al. 2022 Promoter Calculator inference. For each **explicitly
requested** transcription-start candidate it enumerates 30 spacer/discriminator
states, scores each with fixed learned coefficients, and returns the lowest-score
state with its sequence windows and score contributions. It scores candidates; it
does not find promoters. It reproduces the historical equations, not a measured
cyanobacterial, hosted-service or design capability.

| Question | Answer |
| --- | --- |
| Is it a runnable local predictor? | Yes. Offline, no accounts or network, Python 3.11+ standard library only. |
| Does it match the admitted historical source? | Yes, on 212 synthetic states (below). That is fidelity, not accuracy. |
| Is its biological accuracy measured here? | No. No new native or measured-strength result exists yet. |
| Is it calibrated for cyanobacteria? | No. Calibration is *E. coli* MG1655 or *in vitro* *E. coli* RNAP only. |
| Does it match the hosted De Novo DNA tool? | Unestablished. |
| Is it released? | No. 0.5.0rc1 is a development candidate. |

## Source, licence and parameter pins

| Item | Pin |
| --- | --- |
| Model ID | `promoter-lafleur2022-historical-1` (kind `historical_equation_reconstruction`) |
| Historical source | SalisLabCode `46da9132740bce30bccd107f02808adf2215e2f0`, `Promoter_Calculator`; identical at tag `r2022`, `561990e2278f8da80207f721f05b0c1b935c7a97` |
| Cross-check (not imported) | Barrick fork v1.2.4, `0fe5f6f0fb2befc087556afa575f7241afd98fbf` |
| Coefficients | 343 float64, array SHA256 `fddf16b38bf29799481e8a45890b669111e16cf2e3448e99d1934d19a8f0b8e9`; entries 336..338 unused |
| Intercept | `-0.9583584537583338`, array SHA256 `f7c66a8d838da71a6b2ab17936cd6ff2564e446af8c0676fba95de2116e99a7b` |
| Runtime parameters | `src/regsite/data/promoter-parameters-1.json`, `parameter_json_sha256` `e2957d4687a5d5a2a20bcce231b4ea1446f269b383bbae94eed72860efa360dc`; a failed integrity check is a setup error |
| Licence | GPL-3.0-or-later; original 2021 La Fleur/Hossain/Salis notice ships with the wheel ([notice](../../benchmarks/promoter/ORIGINAL-NOTICE)) |
| Paper | [La Fleur et al. 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9440211/), DOI `10.1038/s41467-022-32829-5` |

Source and rights evidence: [source and benchmark audit](promoter-source-and-benchmarks.md),
[source manifest](../../benchmarks/promoter/source-manifest.json). No fitting
script, training identifiers or measurement workbook is recovered or shipped, so
the model is usable historical inference, not reproducible training. Names of
reproducible source differences (reverse-key convention, arbitrary-scan gap,
ignored sigma metadata, unknown-organism fallback, UP length and discriminator
range in code versus text) are listed in `model.source_quirks`; the runtime
follows the source **code**.

## Task, candidate and context semantics

- **Task.** Given a DNA sequence, score each explicitly requested point as a
  transcription start site (TSS): the first transcribed base.
- **Candidates.** `scan` is required and has no default. Either
  `{"mode":"scan","range":[a,b],"strands":[...]}` or an exact list of
  `{"strand","tss"}` positions. Every candidate is retained in the output, including
  those lacking context or not attempted. Nothing is sampled, deduplicated or
  dropped. Padding is context only; it is a candidate only when the range includes it.
- **States.** A state is a discriminator length 6..10 and spacer length 15..20,
  with fixed UP (24 nt), one-base gap, -35, -10 hexamers and a 20-nt initially
  transcribed region (ITR). A full interior candidate has 30 states and needs 67
  bases upstream and 19 downstream (87-base footprint); the minimum is 78 bases.
  Candidates nearer an end have 0..29 states, reported as `state_count` and
  `complete_state_set`. The runtime never extends, pads or wraps the sequence.
- **Strand and coordinates.** Coordinates are zero-based half-open on the
  **supplied local reference**. Local `+` scores the sequence as given; local `-`
  scores its reverse complement, and `forward_base` is then the local base `L-1-t`.
  Local `strand` and `forward_base` are never genomic. Genomic contig, base and
  strand appear only with an explicit `projection` (origin, `sequence_strand`,
  topology, circular origin crossing). For transcript-oriented input scan local `+` only.
- **Windows.** Returned intervals and element strings are the *model's* windows
  for the selected state. They are not experimentally observed promoter boundaries.
  GFF3 export uses the generic `region` type, only with a projection.

## Calibration and host transfer

`calibration` is required for every record; there is no default and no custom
K, beta, temperature or sigma control (recognized controls return `unsupported`).

| Profile | K | beta | Provenance |
| --- | ---: | ---: | --- |
| `ecoli_mg1655` | 42 | 1.636217004872062 | The source default; exact host string `Escherichia coli str. K-12 substr. MG1655` is the native host |
| `in_vitro` | 42 | 0.81632623 | The source's exact `in vitro` organism string |

The paper's calibration is three-hour, 37 °C *in vitro* *E. coli* RNA polymerase
holoenzyme measurement. `host` is metadata and never selects a profile. Result
`calibration.host_status` is `calibration_native`, `in_vitro_reference`,
`unspecified` (warning `host_unspecified`) or `extrapolated` (warning
`host_extrapolation`). Any other host, including a cyanobacterium, retains the
explicitly selected profile with an extrapolation warning: no host-specific
calibration, sigma factor, temperature, growth condition or in vivo context is
modelled (`model.not_modeled`). The `claims` object in every result keeps
`native_accuracy_evaluated` and `hosted_parity` false.

## Score units and selection

Per state, `total` is the sum of eight learned contributions (`hex10`, `hex35`,
`discriminator`, `extended10`, `itr`, `up`, `spacer`, `intercept`). They carry the
source's `dG_*` names but are regression terms, not independently established
free energies (`terms_unit: source_dG_units`). The primary output is

`log_relative_transcription_score = ln(42) - beta * total`

with `relative_transcription_score = exp(log score)` when finite in binary64 and
otherwise `null` with `score_status` `overflow` or `underflow` (the log score is
always kept). Scores are relative values on the source scale; they are not
probabilities, absolute transcripts per second, kcal/mol, or calibrated
site-probabilities. `source_apparent` repeats the source's fixed rescaling and is
independent of the calibration profile.

Selection keeps the finite state with the strictly smallest `total`, visiting
discriminator ascending then spacer ascending; the first of equal states wins and
`tie_count` reports exact ties. Selection among the available finite states is deterministic. Ranking candidates uses the log score (a lower `total` gives a higher score).

Scores are comparable across candidates and sequences only under the same
calibration profile and model identity. An *in vitro* and an *E. coli* result for
the same state differ only by beta.

## Native projection and unsupported mechanisms

Projection only relabels coordinates (linear or circular, either sequence
strand; at most one traversal). It cannot add context beyond the supplied
sequence. Not modelled, and never silently approximated: sigma factors and
promoter classes other than the single historical model, temperature, transcription
factors and regulators, DNA supercoiling and chromatin context, promoter
interference, transcript stability or translation, RNA polymerase pausing and
termination, antisense effects, host-specific calibration, site discovery, false-
discovery or genome-wide probability, and promoter design or optimization. Where
the source's own behavior is mislabeled or buggy (above), the card and the result's
`source_quirks` say so rather than hiding it.

## Fidelity versus biological accuracy

Three kinds of evidence are kept separate.

1. **Reconstruction fidelity (measured).** The pinned historical source and the
   Barrick fork were executed in an isolated legacy environment and agree with an
   independent oracle on 212 synthetic states in 11 cases at 1e-12 absolute and
   relative tolerance ([executed reference](promoter-executed-reference.md)). The
   source and fork baseline were independently re-executed on the same 212 states.
   The 0.5.0rc1 candidate reproduces them, and its installed offline wheel passes
   the independent public-interface checker on 22 requests and 424 states,
   including 4 no-candidate records, at the same tolerances. This shows the
   arithmetic and coordinates were reproduced. It says nothing about expression.
2. **Historical published-column audit (exposed replication).** Recomputed
   correlations of the *supplied* measured and predicted columns of the published
   worksheets ([audit](promoter-source-and-benchmarks.md#published-column-reproduction)).
   These columns come from cohorts that include the study's development data,
   benchmark-specific fitted calibration and non-independent splits. They replicate
   a published table; they are **not** a new runtime strength validation and are not
   restated here as accuracy for the shipped code or any new sequence.
3. **Independent biological evaluation (not yet measured).** Native localization
   on pinned Tan 2018 UTEX 2973 transcription starts, a measured-strength challenge
   and context sensitivity are defined in the [Wave 5 evaluation protocol](promoter-wave5-evaluation.md).
   Collection has not started and no result is reported. Tan 2018 starts are
   transcription-start evidence for conditional localization, not promoter-bound,
   translation-strength or labelled-negative evidence.

Hosted-service equivalence is a fourth, unestablished question. The runtime's
explicit calibration, corrected local coordinates and visible source quirks are
deliberate choices that may differ from hosted behavior.

## Reproducible examples

Install the wheel and run offline (see the [runtime contract](promoter-runtime.md)):

```sh
.venv/bin/regsite-promoter examples/promoter-contract-single.json
.venv/bin/regsite-promoter examples/promoter-contract-batch.json
.venv/bin/regsite-promoter examples/promoter-projected.json --format csv
.venv/bin/regsite-promoter examples/promoter-projected.json --format gff3
.venv/bin/regsite-promoter examples/promoter-invalid-mix.json   # exit 1: an invalid record is retained beside valid and unsupported ones
```

Score four consecutive candidates on a 90-base transcript-oriented reference
(67 upstream bases + 4 candidates + 19 downstream); each retains all 30 states:

```sh
.venv/bin/python -c 'import json; print(json.dumps({"id": "grid", "sequence": "ACGT" * 22 + "AC", "calibration": "in_vitro", "scan": {"mode": "scan", "range": [67, 71], "strands": ["+"]}}))' \
  | .venv/bin/regsite-promoter - --format csv
```

The example sequences are synthetic repeats that exercise the contract; their
scores carry no biological meaning. Input and output schemas:
[request](../../schemas/promoter-request-1.0.schema.json),
[result](../../schemas/promoter-result-1.0.schema.json).

## Resources, deadlines and missingness

Single-thread, offline, no subprocess. Effective caps (echoed in `batch.limits`):

| Limit | Cap |
| --- | ---: |
| Input JSON / result JSON | 4,000,000 bytes / 64 MiB |
| Records per batch | 100 |
| Normalized bases per record / batch | 5,000 / 100,000 |
| Planned sites per record / batch | 1,000 / 4,000 |
| `states:"all"` (sites per record; emitted states per record and per batch) | 100; 2,000 and 2,000 |
| Seconds per record / batch, default | 30.0 / 300.0 |
| Seconds per record / batch, maximum | 120.0 / 3600.0 |

These are enforced caps, not measured capacities or throughput. Measured
cross-platform maxima and the frozen transport limitation are recorded in the
[candidate verification](promoter-0.5-candidate.md).
Exceeding a record limit is `invalid_input` / `limit_exceeded`; an over-limit
whole input or batch size is a setup error (exit 2). Scans are never truncated.

Missingness is explicit and never filled with zero:

- Site status `ok`, `no_candidate` (`insufficient_context`) or `failed`
  (`deadline_exceeded`, `nonfinite_arithmetic`); an unattempted site is
  `failed` with `attempted: false`. A candidate with 1..29 states is scored from
  that partial set (`complete_state_set: false`).
- Record status precedence `invalid_input` > `unsupported` > `failed` > `ok` >
  `no_candidate`. `no_candidate` is not evidence of no promoter. A record that
  is `ok` may still contain unscored sites: check `coverage` (`complete_context`,
  `insufficient_context_sites`, `failed_sites`, `unattempted_sites`).
- Deadlines are checked between sites. A tight deadline yields `failed` with
  every unfinished site listed, never a partial `ok`. Deadline outcomes are not
  byte-identical guarantees; identical complete runs are byte-identical on one
  platform, with numeric parity (1e-12) across platforms.
- Exit codes: `0` all records completed, `1` any `failed` or `invalid_input`
  record (results still written), `2` setup/integrity error with no output.

## Meaning for current and recoded cyano sequences

A cyano gene or construct is supplied as a DNA sequence with explicit candidate
positions. For one such sequence the output answers: *under the historical
E. coli model, what is the lowest-score promoter-like state at each requested
position, and what are its contributions?* It does not answer where the real
promoters are.

For a current sequence and a recoded sequence:

- Each side is scored independently under explicit model and calibration
  settings and its own candidate rules. Compatible model/calibration identities
  are required for numerical differences. A score difference is a difference in model score for
  corresponding supplied positions, not a measured change in expression or
  transcription.
- Correspondence between current and recoded candidates comes from an explicit
  edit map ([paired contract](paired-regulatory-runtime.md),
  [independent geometry rules](current-recoded-validation.md)); position or
  sequence similarity is never used to match them.
- A candidate's score depends only on the oriented 87-base footprint
  `[t-67, t+20)` of its state windows. Edits wholly outside every candidate's
  footprint cannot change its score; an edit inside can change the selected
  state, so the score, and windows, move together.
- A candidate present in one side and absent, truncated or out of range in the
  other is reported as such. A lower score, a different selected state, or a
  `no_candidate` result is **not** biological site loss, and a higher score or
  new candidate is not biological site gain. The model does not discover sites,
  so a site "appearing" only means a requested candidate scored differently.
- A cyanobacterial host label, UTEX 2973 or otherwise, selects no calibration.
  Absolute scores are not calibrated cyano expression. Treat any difference as
  a model-based prioritization signal pending independent native evidence and
  the consumer's own admission rules ([consumer boundary](cyano-integration.md)).
- No recoding optimizer or design mode exists; this model does not propose edits.

## Evaluated and not evaluated

| Question | Status |
| --- | --- |
| Historical equation, parameter and coordinate fidelity (212 synthetic states) | Evaluated, passes at 1e-12 |
| Installed offline wheel through the public interface (22 requests / 424 states) | Evaluated by an independent checker, passes |
| Resource/full-runtime CI (Ubuntu 24.04 and macOS 14, Python 3.11 and 3.14) | All eight jobs passed at the frozen candidate; software checks are not biological accuracy |
| Final candidate receipt and measured resource maxima | Available in the [candidate verification](promoter-0.5-candidate.md); known text-mode transport limitation restricts native collection to verified UTF-8/LF files |
| Native localization of Tan transcription starts, fixed-grid | Not evaluated |
| Measured promoter-strength challenge (GSE144621 lead) | Not admitted; rights and construct identity unresolved |
| Context sensitivity of unchanged RBS (companion diagnostic) | Not evaluated |
| Cyanobacterial calibration or accuracy | Not evaluated, not claimed |
| Hosted-tool equivalence | Not evaluated, not claimed |
| New optimizer, site discovery, probability of a site | Not implemented, out of scope |

Update this table only from reviewed, independently reproduced artifacts. Do not
repair or tune against an exposed final outcome and describe the rerun as
held out.
