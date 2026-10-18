# Promoter runtime contract

- Purpose: Fix the public request, result, coordinate, calibration, limit and acceptance contract for the local Promoter runtime before independent writers start.
- Scope: Ticket #33 (parent #7). Specified implementation contract for `regsite-promoter`; not an executed runtime, a hosted-parity claim or a scientific accuracy claim.
- Last verified: 2026-10-18

**Status.** Nothing here is implemented. The owner decision on parallel Promoter
development is pending; this document authorizes no runtime code. Equations,
parameters and 212-state expectations come from the pinned
[source and benchmark audit](promoter-source-and-benchmarks.md) and
[executed reference](promoter-executed-reference.md). Ownership follows the
[Wave 5 program](wave5-program.md): A implements and freezes; B's fixtures,
oracle and native/strength evaluation stay independent. General rules come from
the [reconstruction contract](reconstruction-contract.md); conventions mirror
the [RBS runtime](rbs-runtime.md) and [native adapter](rbs-native-runtime.md).

## Decisions

| Topic | Decision |
| --- | --- |
| Model | Prospective identity `promoter-lafleur2022-historical-1`: the admitted historical equations with the fixed GPL-3.0-or-later arrays. Not the hosted tool, not a retrained model. |
| Engine | Standard-library direct inference in the existing `regsite` package; no NumPy, SciPy, scikit-learn or Biopython. Adoption requires independent source parity (see acceptance checks); on failure stop and report, never add the legacy stack to required dependencies. |
| Interface | Console script `regsite-promoter`; JSON single/batch input; JSON or compact CSV output; optional GFF3 only with explicit projection metadata. Same wheel as RBS. |
| Scores | Learned regression score terms (source `dG_*` notation), never new kcal/mol. Primary output is `log_relative_transcription_score`. |
| Calibration | Explicit and required per record: `ecoli_mg1655` or `in_vitro`. Host is metadata. Unknown host plus E. coli profile is allowed only with an extrapolation warning. |
| Controls | No sigma, temperature, design or custom K/beta controls. Recognized-but-unmodeled controls yield `unsupported`. |
| Coordinates | Sequence-relative, zero-based, forward-reference; half-open feature intervals; TSS is a base index. Genomic coordinates only through explicit `projection`. |

## Model identity and parameters

| Item | Value |
| --- | --- |
| `model.id` | `promoter-lafleur2022-historical-1` |
| Historical source | SalisLabCode `46da9132740bce30bccd107f02808adf2215e2f0` (identical at tag `r2022`, `561990e2278f8da80207f721f05b0c1b935c7a97`), `Promoter_Calculator` directory |
| Fork cross-check | Barrick v1.2.4, `0fe5f6f0fb2befc087556afa575f7241afd98fbf` (reference only; not imported) |
| Coefficients | 343 little-endian float64, array SHA256 `fddf16b38bf29799481e8a45890b669111e16cf2e3448e99d1934d19a8f0b8e9`; entries 0..335 categorical, 339..342 numeric; 336..338 unused historical spacer entries retained and reported as unused |
| Intercept | one float64, array SHA256 `f7c66a8d838da71a6b2ab17936cd6ff2564e446af8c0676fba95de2116e99a7b`, value `-0.9583584537583338` |
| Utility tables | `groove_access`, `persistence`, `DNA_DNA_hybrids`, `RNA_DNA_hybrids` dimer tables and the four numeric normalizers from the pinned `util.py` and source module |
| Licence | GPL-3.0-or-later; the original 2021 La Fleur/Hossain/Salis copyright line (see `benchmarks/promoter/ORIGINAL-NOTICE`) must ship with the wheel, not only the fork's short notice |

Runtime parameter data is `src/regsite/data/promoter-parameters-1.json`. A derives it
by a committed deterministic script from the two hash-verified `.npy` arrays
(stdlib reader: verify hash, parse header, read little-endian float64) and the
utility tables parsed with `ast.literal_eval` from the hash-verified pinned
`util.py`/module source, never executed. The derivation must not copy B's
`benchmarks/promoter/reference-parameters.json`; equality with that file
(bit-exact floats) is a parity test, so the conversion is independently checked.
Loading verifies array hashes recorded in the file, entry counts, finiteness, and
a pinned canonical SHA256 of the whole parameter object (`parameter_json_sha256`,
recorded at freeze). A failed integrity check is a setup error (exit 2), never
a per-record result. No fitting script or training data is recovered, so none is shipped.

Source differences that stay visible in `model.source_quirks` (static list of
`{id, behavior}`; the runtime follows the **code**, not the mislabeled outputs):

| id | Source behavior | Runtime behavior |
| --- | --- | --- |
| `reverse_key_l_minus_t` | Reverse output keyed `L-t` with reverse-oriented nested TSS/intervals | Reports corrected forward base `L-1-t`; legacy key only on request |
| `arbitrary_scan_gap_omitted` | `scan_arbitrary` omits the one-base UP/hex35 gap in its TSS distance sum | Not reproduced; the gap is always present |
| `sigma_levels_ignored` | `sigmaLevels` metadata never changes the score | No sigma field accepted or emitted |
| `unknown_organism_default_beta` | Any unrecognized organism string uses the E. coli beta | Never inferred; calibration is explicit |
| `one_state_per_tss_public` | Public fork `predict(min_only=False)` still returns one state per TSS | All states available on request |
| `unused_spacer_coefficients` | Array entries 336..338 are unused; spacer uses the quadratic | Same quadratic; entries preserved |
| `paper_code_difference` | Paper text discusses UP=20 and discriminator scans from 5 | Code values used: UP=24, discriminators 6..10 |

## State definition and arithmetic

All arithmetic is on the **oriented DNA sequence** (the forward reference for
`+`; its reverse complement for `-`) with zero-based half-open slices. A *state*
is an oriented TSS `t` with discriminator length `d` in 6..10 and spacer length
`s` in 15..20. Windows derive backward from the first ITR base:

```
disc  = [t-d, t)         hex10 = [disc.start-6, disc.start)
spacer= [hex10.start-s, hex10.start)       hex35 = [spacer.start-6, spacer.start)
gap   = [hex35.start-1, hex35.start)       UP    = [gap.start-24, gap.start)
ITR   = [t, t+20)        extended10 = [spacer.end-3, spacer.end-1)
```

A state is **complete** iff `UP.start >= 0` and `ITR.end <= L`. A TSS is
*evaluable* iff it has at least one complete state. Minimum context is 78 bases
(`t=58`), maximum 87; a full interior TSS has 30 states. Edge TSSs have 1..29.

Score terms (`c` = coefficients, `idx` = A,C,G,T → 0..3 read as a base-four
number, most significant base first):

| Runtime term | Source name | Expression |
| --- | --- | --- |
| `hex10` | `dG_10` | `c[idx(hex10[0:3])] + c[64+idx(hex10[3:6])]` |
| `hex35` | `dG_35` | `c[128+idx(hex35[0:3])] + c[192+idx(hex35[3:6])]` |
| `discriminator` | `dG_disc` | `c[256+idx(disc[0:3])]` |
| `extended10` | `dG_ext10` | `c[320+idx(extended10)]` (2 bases) |
| `itr` | `dG_ITR` | `n2` |
| `up` | `dG_UP` | `fsum(n0, n1, n3)` |
| `spacer` | `dG_spacer` | `0.1463*s**2 - 4.9113*s + 41.119` |
| `intercept` | intercept | `-0.9583584537583338` |
| `total` | `dG_total` | `fsum` of the eight rows above |
| `binding` | `dG_bind` | `fsum(hex10, hex35, extended10, up, spacer)` |
| `source_apparent` | `dG_apparent` | `(total + 2.80271176) / 0.81632623`; fixed constants, independent of calibration profile |

Numeric features use **non-overlapping stride-two dimers** (`seq[i:i+2]`,
`i = 0,2,4,…`) with the pinned tables: `r0` = groove sum over `UP[0:12]`; `r1` =
groove sum over `UP[12:24]`; `r2` = DNA_DNA sum minus RNA_DNA sum over `ITR[0:14]`
(seven dimers); `r3` = persistence sum over `UP + hex35 + spacer[0:14]` (22
dimers) divided by 44. Then `n_i = r_i / normalizer_i * c[339+i]`. All sums use
`math.fsum`, so totals are order-independent and exactly rounded; ties are
evaluated on these floats. The scalar fixtures (spacer 17 = -0.0924, A12 groove =
30, A44 rigidity = 25.2, A20 hybrid difference = -5.6) pin the helpers.

**Naming.** Runtime term keys are *learned scores in source-dG units*. Results
declare `terms_unit: "source_dG_units"` and `terms_semantics: "learned regression
score contributions; not independently established free energies"`. Source names
are listed once in `model.term_source_names`, not repeated per state.

**Selection and ties.** Visit states discriminator ascending (outer) then spacer
ascending (inner); keep the first state with the strictly smallest `total`. A later
equal state never replaces it. `tie_count` is the number of complete states whose
`total` equals the selected total exactly (always ≥1), so a tie is visible, not silent.
Floats differing by one ulp are not ties. Frozen expectations: `A200` has five
states exactly equal to its minimum (spacer 17, discriminators 6..10; winner 6/17);
every other non-empty fixture has a unique minimum with a margin ≥ 0.09, so
selection parity is unambiguous.

## Calibration, host and scores

| Profile | K | beta | Native host string | Source organism argument |
| --- | ---: | ---: | --- | --- |
| `ecoli_mg1655` | 42 | 1.636217004872062 | `Escherichia coli str. K-12 substr. MG1655` | that string (also the source's default for any unrecognized string) |
| `in_vitro` | 42 | 0.81632623 | none | `in vitro` |

No other profile, no custom K/beta, no temperature. `calibration` has no default;
omitting it everywhere (record, `defaults`, CLI) is `invalid_input` /
`calibration_required`. Calibration provenance is the paper's three-hour 37 °C
in vitro E. coli RNAP measurements; it says nothing about cyanobacteria, other
hosts, sigma factors or in vivo expression.

`host` is optional metadata `{ "name": string(1..200), "taxon_id": int>0 optional }`
and never selects a profile. Result `calibration.host_status`:

| Value | Condition | Warning |
| --- | --- | --- |
| `calibration_native` | profile `ecoli_mg1655`, host name exactly the native string | none |
| `in_vitro_reference` | profile `in_vitro`, host absent or exactly `in vitro` | none |
| `unspecified` | host absent, profile `ecoli_mg1655` | `host_unspecified` |
| `extrapolated` | any other host name | `host_extrapolation`: profile applied to a host without host-specific calibration or native validation; host metadata does not change the model |

The comparison is an exact string match after Unicode NFC; it is a registry lookup
of one declared string, not name inference.

Per state, with `log_relative_transcription_score = ln(K) - beta*total`
(`math.log(K) - beta*total`, finite for every complete state):

- `relative_transcription_score = math.exp(log_score)` when `log_score` is within
  `[math.log(sys.float_info.min), math.log(sys.float_info.max)]`
  (`-708.3964185322641` .. `709.782712893384` on IEEE-754 binary64), with
  `score_status: "ok"`.
- Above the upper bound: value `null`, `score_status: "overflow"`. Below the lower
  bound: value `null`, `score_status: "underflow"`. Never `inf`, `0.0` or a subnormal
  surrogate; the log score always remains.
- A nonfinite log score or term makes the site `failed` (`nonfinite_arithmetic`).
- Ranks, selection and ties use `total`/log, never the clipped value.

Scores are relative transcription scores on the source's scale. They are not
absolute transcripts per second, probabilities, calibrated site probabilities or
kcal/mol. Scanning scores candidate positions; it is not site discovery.

## Request contract (`promoter-request-1.0`)

Input is one JSON value: a single record object, or an envelope
`{"schema_version":"1.0","defaults":{…},"records":[…]}`. A bare array is rejected.
`schema_version` defaults to `"1.0"`; any other value is a setup error (exit 2).
Duplicate JSON keys and `NaN`/`Infinity` are setup errors. Unknown keys are
`invalid_input`/`unknown_field`. `defaults` may hold only `calibration`, `host` and
`output`; precedence is record > `defaults`; a conflicting CLI flag (below) is a
setup error rather than an override.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Required. 1..128 chars `[A-Za-z0-9][A-Za-z0-9._:-]*`; unique in the batch (second occurrence is `invalid_input`/`duplicate_id`). |
| `sequence` | string | Required. Forward-reference DNA (or RNA) text. |
| `calibration` | string | Required (record, `defaults` or CLI): `ecoli_mg1655` or `in_vitro`. |
| `host` | object | Optional metadata as above. |
| `scan` | object | Optional; default `{"mode":"scan"}`. |
| `projection` | object | Optional genomic metadata (below). |
| `output` | object | Optional `{"states":"selected"\|"all","legacy_keys":bool,"elements":bool}`; defaults `selected`, `false`, `true`. |
| `model` | object | Optional pin `{"id":…,"parameter_json_sha256":…}`; mismatch is `unsupported`/`model_unavailable`. |
| `metadata` | object | Optional ≤4096 canonical-JSON bytes, depth ≤4; echoed verbatim, excluded from identity and computation. |

**Normalization.** Keep only characters after removing ASCII whitespace
(`space`, `\t`, `\n`, `\v`, `\f`, `\r`); uppercase; map `U`→`T`. Text containing
both `T` and `U` is `mixed_dna_rna`. Any remaining character outside `ACGT`
(IUPAC ambiguity, digits, FASTA headers, non-ASCII) is `invalid_input`
(`ambiguous_base` for IUPAC letters, otherwise `invalid_character`) with the first
offending raw-text index and character in the error. Empty is `empty_sequence`.
Coordinates always count normalized bases. Record raw-text and normalized-DNA
SHA256 (hash UTF-8 bytes; the normalization is named in `input.normalization`).

**Scan.** Two modes, both in forward-reference TSS bases:

- `{"mode":"scan","range":[a,b],"strands":["+","-"]}`: every TSS base `a <= f < b`
  on each listed strand; defaults `[0,L]` and both strands; `0<=a<=b<=L`.
- `{"mode":"positions","positions":[{"strand":"+","tss":100},…]}`: exactly the
  requested points; `strand` is required per item; duplicates are
  `duplicate_position`; out-of-range is `position_out_of_range` (no clipping).

Integers must be JSON integers or integral floats (`20.0`); booleans and
fractions fail. Planned sites are counted before eligibility and checked against
limits.

**Projection** (optional; required for genomic coordinates and GFF3):

```json
{"contig":"NC_000911.1","origin":383000,"contig_length":3573470,
 "topology":"linear","origin_crossing":false}
```

`sequence[0]` is forward-strand contig base `origin` (zero-based); the supplied
sequence is always contig-forward. `contig` is 1..128 characters; `0<=origin<contig_length`;
`topology` is `linear` or `circular`. Linear requires `origin+L <= contig_length`.
Circular requires `L <= contig_length` (no double traversal); the extract may cross
the origin only when `origin_crossing` is `true`, and `origin+L > contig_length`
must hold exactly then (`undeclared_origin_crossing` / `origin_crossing_mismatch`).
Scan windows never wrap beyond the supplied extract; projection only maps
coordinates. Two records sharing a `contig` with different `contig_length` or
`topology` make the later record `invalid_input`/`contig_metadata_conflict`.

Unsupported controls: keys `sigma`, `sigma_factor`, `sigma_levels`, `temperature`,
`temperature_c`, `design`, `optimize`, `k`, `beta` at record level yield
`unsupported`/`unsupported_control` (no sites, null scores). They are never
accepted, ignored or echoed as active settings.

## Coordinates

- All internal and exported sequence coordinates are zero-based; intervals are
  half-open `[start,end)`, ascending in forward-reference coordinates.
- TSS is a **point**: the first transcribed base, i.e. the first ITR base. On `+`,
  `tss.forward_base = tss.oriented_base = t`. On `-`, the transcript runs toward
  lower forward coordinates and the forward base is `f = L-1-t`.
- Oriented interval `[a,b)` maps to forward `[L-b, L-a)` on `-`; `[a,b)` on `+`.
  Worked check from the frozen source fixture: `L=200`, oriented TSS 70 → forward
  base 129 (legacy key 130); oriented `[10,34)` → forward `[166,190)`. For
  requested forward base 100 on `-`, oriented TSS is 99 (executed source: key 101).
- `legacy_source_key = t` on `+` and `L-t` on `-`. It appears only as
  `site.legacy_source_key` when `output.legacy_keys` is true, with warning
  `legacy_key_not_coordinate`; it is never a base or interval endpoint.
- Interval names: `UP`, `gap` (always one base), `hex35`, `spacer`, `extended10`,
  `hex10`, `discriminator`, `itr`. Both `intervals` (forward-reference) and
  `oriented_intervals` are returned per selected or listed state.
- With `projection`, `genomic_base = (origin + f) mod contig_length` and every
  interval gains `genomic_segments`: ascending `[start,end)` runs on the contig,
  at most two, ordered along transcription (so a `-` crossing lists the post-origin
  run first). Intervals never exceed one contig traversal.
- Elements (`UP`, `hex35`, `spacer`, `hex10`, `discriminator`, `itr`) are the
  oriented DNA strings (5′→3′ along the promoter strand), included by default for
  selected states only.

## Result contract (`promoter-result-1.0`)

JSON is authoritative: `{"schema_version":"1.0","model":{…},"batch":{…},"results":[…]}`
with fixed field order, 2-space indent, `allow_nan=False`, trailing newline, no
timestamps, paths or elapsed times (identical input and settings give identical bytes).

`model`: `id`, `implementation_version`, `kind: "historical_equation_reconstruction"`,
`source` (commits above), `licence`, `parameters` (array hashes, entry counts,
unused indices, `parameter_json_sha256`), `term_source_names`, `terms_unit`,
`terms_semantics`, `source_quirks`, `not_modeled` (`["sigma_factor","temperature",
"host_specific_calibration","probability","absolute_rate","free_energy"]`) and
`claims` (`{"physical_free_energy":false,"absolute_rate":false,"probability":false,
"native_accuracy_evaluated":false,"hosted_parity":false}`). Statements in
`claims` must stay false in v1.

`batch`: `batch_id`, `record_count`, `status_counts`, `complete` (false if any record
failed on a deadline), effective `limits` and `seconds_per_record`/`seconds_per_batch`.

Per record: `id`, `status`, `reasons` (stable codes), `prediction_id`, `input`
(`raw_sha256`, `normalized_dna_sha256`, `length`, `normalization`), `calibration`
(`profile`, `K`, `beta`, `native_host`, `host`, `host_status`), `scan` (resolved),
`coverage`, `sites`, `projection`, `warnings`, `errors`, `metadata`.

`coverage`: `planned_sites`, `evaluable_sites`, `insufficient_context_sites`,
`scored_sites`, `complete` (bool) and `truncation` (`null` or
`{reason, completed_sites, planned_sites}`). In `positions` mode every request is
a listed site (ineligible ones are `no_candidate`). In `scan` mode ineligible
positions are counted, not listed.

Site: `site_id`, `strand`, `tss` (`forward_base`, `oriented_base`, `genomic_base`
when projected), `status` (`ok`|`no_candidate`|`failed`), `reason`
(`null`|`insufficient_context`|…), `state_count`, `tie_count`, `selected`,
`states` (present only for `output.states:"all"`), `legacy_source_key` (opt-in).
Non-ok sites have `selected: null`, never zero scores.

State (`selected` or an entry in `states`): `state_id`, `discriminator_length`,
`spacer_length`, `terms` (rows in the table above), `log_relative_transcription_score`,
`relative_transcription_score`, `score_status`, `intervals`, `oriented_intervals`,
`elements` (selected only, unless disabled). `states` lists every complete state
in visit order and marks `selected: true` on exactly one.

**Stable IDs.** `scope_id` = SHA256 of canonical JSON (sorted keys, compact
separators, `allow_nan=False`, as in the RBS provenance helper) of: result
schema version, model identity (`id`, `implementation_version`,
`parameter_json_sha256`, array hashes, source commit), calibration (`profile`,
`host` name/taxon), normalized-DNA SHA256, and `projection`. Then
`prediction_id` = SHA256 of the scope plus resolved `scan` and `output`.
`site_id` = `psite1:` + first 32 hex of `scope_id` + `:` + strand + `:` + forward
base; `state_id` = `site_id` + `:d` + discriminator + `s` + spacer. Record `id`,
`metadata`, limits and deadlines are excluded, so identical sequences share IDs
across records and scan modes. IDs name the requested calculation, not its
completeness: always check `status`/`coverage`. A package version change changes
every ID; any equation or parameter change requires a new `model.id`.

Illustrative single-record shape, with the numeric state copied from the
pre-existing frozen fixture `A200` (winner discriminator 6, spacer 17; K 42,
beta 1.636217004872062; log score and value derived by the stated formulas from
that fixture total) and hashes elided. It is not runtime output:

```json
{"id":"A200","status":"ok","reasons":[],"prediction_id":"…","calibration":{"profile":"ecoli_mg1655","K":42,"beta":1.636217004872062,"native_host":"Escherichia coli str. K-12 substr. MG1655","host":{"name":"Escherichia coli str. K-12 substr. MG1655","taxon_id":null},"host_status":"calibration_native"},
 "scan":{"mode":"positions","positions":[{"strand":"+","tss":100}]},
 "coverage":{"planned_sites":1,"evaluable_sites":1,"insufficient_context_sites":0,"scored_sites":1,"complete":true,"truncation":null},
 "sites":[{"site_id":"psite1:…:+:100","strand":"+","tss":{"forward_base":100,"oriented_base":100},"status":"ok","reason":null,"state_count":30,"tie_count":5,
  "selected":{"state_id":"…:d6s17","discriminator_length":6,"spacer_length":17,
   "terms":{"hex10":-0.045518549465389205,"hex35":-0.16908705233531682,"discriminator":-0.04487847301375619,"extended10":0.0610364204005321,"itr":-0.21111731757486488,"up":0.11560097243172428,"spacer":-0.09239999999999071,"intercept":-0.9583584537583338,"total":-1.3447224533153952,"binding":-0.13036820896844037,"source_apparent":1.7860375583969719},
   "log_relative_transcription_score":5.937927363231296,"relative_transcription_score":379.14827793659254,"score_status":"ok",
   "intervals":{"UP":[40,64],"gap":[64,65],"hex35":[65,71],"spacer":[71,88],"extended10":[85,87],"hex10":[88,94],"discriminator":[94,100],"itr":[100,120]}}}],
 "warnings":[],"errors":[]}
```

The intervals are the `source-fixtures.json` forward case (TSS 100,
discriminator 6, spacer 17). The value `379.148…` differs in the last digits from
the fixture's `Tx_rate` because it is `exp(ln K - beta*total)`; parity is at
1e-12 relative.

## Statuses, errors and batch behavior

| Status | Meaning |
| --- | --- |
| `ok` | Scan mode: ≥1 site scored and none failed. Positions mode: every requested site scored. |
| `no_candidate` | Scan mode: zero evaluable positions (including empty range). Positions mode: ≥1 requested site lacks a complete state (`insufficient_context`). Scored sites remain listed. Not evidence of no promoter. |
| `unsupported` | Recognized control or model pin the runtime cannot honor. No sites. |
| `invalid_input` | Validation failed; no sites, `prediction_id: null`. |
| `failed` | Computation incomplete or invalid: `deadline_exceeded`, `nonfinite_arithmetic`. Completed sites remain, `coverage.complete:false`, `truncation` set. |

Precedence across sites in positions mode: failed → no_candidate → ok. Whole-record
precedence: invalid_input → unsupported → computation outcomes.

Stable error/reason codes: `schema_version_unsupported`, `invalid_type`,
`missing_field`, `unknown_field`, `invalid_id`, `duplicate_id`, `empty_sequence`,
`sequence_too_long`, `invalid_character`, `ambiguous_base`, `mixed_dna_rna`,
`calibration_required`, `invalid_calibration`, `invalid_host`, `invalid_scan`,
`invalid_strand`, `range_out_of_bounds`, `position_out_of_range`,
`duplicate_position`, `invalid_projection`, `undeclared_origin_crossing`,
`origin_crossing_mismatch`, `contig_metadata_conflict`, `invalid_output_option`,
`limit_exceeded` (names the limit and observed value), `unsupported_control`,
`model_unavailable`, `insufficient_context`, `empty_scan`, `deadline_exceeded`,
`nonfinite_arithmetic`. Each error carries `code`, `field` (JSON path) and a
message; messages are not part of the contract.

Batch rules: validate every record first (all `invalid_input`/`unsupported`
results exist even if scoring later times out), then score in input order,
single-threaded, one record at a time. One bad record never discards another.
Deadlines are checked between sites with an injectable monotonic clock; a record
that exceeds `seconds_per_record`, or any record not started when
`seconds_per_batch` ends, is `failed`/`deadline_exceeded` (unstarted ones list no
sites). Exceeding a count/size limit is a pre-flight `invalid_input`/`limit_exceeded`
for that record; a limit on the whole input (bytes, records) is a setup error.
Never silently truncate, subsample or clip a scan.

Exit codes: `0` all records completed (including `no_candidate`/`unsupported`);
`1` any `failed` or `invalid_input` record, with all results still written; `2`
setup, malformed/oversized JSON, parameter-integrity or conflicting-option errors
with no result on stdout. Stdout carries only the requested format; diagnostics go
to stderr.

## CLI and exports

```sh
regsite-promoter INPUT [--format json|csv|gff3] [--calibration ecoli_mg1655|in_vitro]
                 [--states selected|all] [--seconds-per-record S] [--seconds-per-batch S]
```

`INPUT` is a path or `-` for stdin. `--calibration`/`--states` set a value only where
the file leaves it unspecified and exit 2 if any file value differs. Defaults 30
and 300 seconds; maximums 120 and 3600. No network, no environment backend, no
subprocess. `--format csv` rejects `--states all`; `--format gff3` requires every
record to have a `projection` (records without one are listed as GFF comment
lines and counted, never guessed) and only emits sites with status `ok`.

**CSV (`promoter-csv-1.0`)**: one header line, then one row per site's selected
state; records with no site (invalid, unsupported, empty, failed before any site)
get one row with empty site columns. Columns, in order: `record_id`, `record_status`,
`prediction_id`, `site_id`, `strand`, `forward_base`, `oriented_base`,
`genomic_contig`, `genomic_base`, `site_status`, `reason`, `state_count`,
`tie_count`, `discriminator_length`, `spacer_length`, `score_hex10`, `score_hex35`,
`score_discriminator`, `score_extended10`, `score_itr`, `score_up`, `score_spacer`,
`score_intercept`, `score_total`, `score_binding`, `log_relative_transcription_score`,
`relative_transcription_score`, `score_status`, `calibration_profile`, `host_status`,
`warning_codes` (`;`-joined). Null is an empty cell, never `0`; floats use shortest
round-trip `repr`. IDs begin with an alphanumeric, so cells cannot start a
spreadsheet formula.

**GFF3**: one-based inclusive, `seqid` = `contig`, `source` = `regsite-promoter`,
`sequence-region` and landmark `region` per contig with `Is_circular` and
`contig_length`, scores and phase `.`, attributes percent-escaped per the GFF3
specification, circular features with unwrapped `end` greater than the contig length
(the [native adapter](rbs-native-runtime.md) convention). Feature `ID`s derive
from `site_id`. Per ok site, strand-aware features for the selected state:
`transcription_start_site` (single base), `minus_35_signal` (`hex35`),
`minus_10_signal` (`hex10`), and `region` with `Name` for `UP`, `spacer`,
`discriminator`, `itr`; `log_relative_transcription_score` is an attribute, not
the score column. They are model windows, not experimentally observed
boundaries, and no span is typed `promoter`. The one-base gap and
`extended10` stay JSON-only. Sequence Ontology term names are listed to be
verified (see unresolved questions).

## Limits and refinement before freeze

Ceilings, not measured capacities. A may lower any value freely; raising one, or
changing semantics, requires measurements below and an amendment to this document.

| Limit | Ceiling | On breach |
| --- | ---: | --- |
| Input JSON bytes | 4,000,000 | setup error |
| Records per batch | 100 | setup error |
| Raw sequence text chars | 50,000 | record `limit_exceeded` |
| Normalized bases per record | 5,000 | record `limit_exceeded` |
| Normalized bases per batch | 100,000 | later records `limit_exceeded` |
| Planned sites per record | 5,000 | record `limit_exceeded` |
| Planned sites per batch | 20,000 | later records `limit_exceeded` |
| `states:"all"` planned sites per record / emitted states per record / per batch | 100 / 3,000 / 10,000 | record `limit_exceeded` |
| Serialized result JSON | 64 MiB | setup error (exit 2), nothing written |
| `metadata` | 4,096 bytes, depth 4 | record `limit_exceeded` |
| `seconds_per_record` default / max | 30 / 120 | option error |
| `seconds_per_batch` default / max | 300 / 3600 | option error |

Single thread; no operating-system memory quota is claimed. Effective limits are
echoed in `batch.limits`.

**Synthetic validation procedure (A, before the candidate freeze).** Use only
generated sequences: homopolymers A/C/G/T, repeats of the fixture motifs, and a
documented fixed-seed pseudo-random generator at several GC fractions. No native, Tan, GSE144621, published-cohort or private B data may
inform any limit.

1. Build the worst-case inputs at every ceiling: a 5,000-base both-strand scan
   whose range plans exactly the per-record site ceiling, the largest permitted
   batch, and `states:"all"` at its ceilings.
2. On each CI platform/Python combination run three timed repetitions per input;
   record wall time, peak RSS (`/usr/bin/time -l` on macOS, `-v` on Linux) and
   serialized bytes. Take the maximum per-site wall time `c`.
3. Admit a site/record/batch limit `N` only if `N·c` is at most half of the
   corresponding default deadline on the slowest platform and the worst-case
   serialized result is at most half of the 64 MiB ceiling; otherwise lower `N`.
4. Verify truncation behavior with an injected clock and with a real tight
   deadline: statuses, `coverage`, no partial `ok`.
5. Put the numbers, commands, commit and hashes in the freeze receipt (not in this
   file). Measured values enter documentation only from that receipt.
6. After B acknowledges the frozen protocol, any limit or deadline change needs a
   new candidate identity.

## Packaging and licence

- Ship in the existing `regsite` package; add `regsite-promoter` to
  `[project.scripts]` and package data for the parameter JSON and the original
  notice text. Python ≥3.11; no new runtime dependencies; no `benchmarks`
  import at runtime. The runtime may not import B's `reference_oracle` or read the
  expected fixtures at runtime; tests may read the pre-existing JSON fixtures.
- Update `NOTICE`, which currently states the Promoter artifacts are not in the
  wheel, to describe the derived runtime parameters, and ship the complete GPLv3
  text and original 2021 copyright line. The wheel must contain no experimental
  measurement table.
- Preserve every RBS profile, schema, model and frozen artifact byte-for-byte.

## Public Python surface and writer partition

Pure core (`regsite.promoter`, standard library only; Google style, typed):

| Callable | Contract |
| --- | --- |
| `load_parameters() -> PromoterParameters` | Verifies hashes/counts/finiteness; raises `ParameterError`. |
| `normalize_dna(value, *, max_length) -> str` | Returns uppercase ACGT or raises `InputError(code, field, index)`. |
| `orient(forward, strand) -> str` | Identity for `+`, reverse complement for `-`. |
| `state_windows(t, d, s) -> dict[str, tuple[int,int]]` | Oriented intervals as defined above. |
| `to_forward(length, strand, interval) -> tuple[int,int]` / `forward_base(length, strand, oriented_t) -> int` | The only coordinate converters. |
| `legacy_source_key(length, strand, oriented_t) -> int` | `t` or `L-t`; not usable as a coordinate. |
| `score_state(oriented, t, d, s, params) -> StateScore` | Terms as tabulated; no calibration. |
| `relative_score(log_score) -> tuple[float \| None, str]` | Overflow/underflow policy. |
| `score_site(forward, strand, forward_base, params, calibration, *, keep_states) -> SiteResult` | Visit order, strict-less selection, `tie_count`, `no_candidate`. |
| `predict(request, params, *, seconds, clock) -> dict` | One validated record → record result. |

I/O layer (`regsite.promoter_io`, `regsite.promoter_cli`): `load_requests`,
`predict_batch`, `write_json`, `write_csv`, `write_gff3`, `project_interval`,
`main`. Disjoint ownership proposal for A's writers, freezing the core signatures
first: **core** `src/regsite/promoter.py`, the parameter JSON and derivation script,
`tests/test_promoter_core.py`, `tests/test_promoter_parity.py`; **interface**
`src/regsite/promoter_io.py`, `src/regsite/promoter_cli.py`,
`schemas/promoter-request-1.0.schema.json`, `schemas/promoter-result-1.0.schema.json`,
`examples/promoter-*.json`, I/O/CLI/schema tests; **A only** `pyproject.toml`,
`NOTICE`, README, indexes and CI. Examples are one single record, one batch
with `defaults`, one projected scan with a circular origin-crossing case, and an
invalid/unsupported mix; all offline and synthetic.

## Acceptance checks

All gates in the [RBS runtime](rbs-runtime.md) apply (ruff, format, mypy, pytest
with 100% statement and branch coverage on the new modules, build, fresh wheel).
In addition, the Promoter candidate passes the following before freeze.

| # | Check | Pass criterion |
| --- | --- | --- |
| 1 | Parameter identity | Array/object hashes match; 343 coefficients and four tables bit-equal to `benchmarks/promoter/reference-parameters.json`; derivation independent of that file. |
| 2 | 212-state parity | Against `reference-fixtures.json`: same state set and visit order for all 11 cases (30,30,0,1,30,1,30,0,30,30,30); terms and score within absolute+relative 1e-12 (fixture `Tx_rate` vs `relative_transcription_score`); selected state equals fixture winner (A200: 6/17 with `tie_count` 5); `unknown-host` and `in-vitro` map to explicit profiles with the stated beta and warnings. |
| 3 | Terms | Every row of the term table, the four numeric features and the spacer value against `source-fixtures.json` (-0.0924, 30, 25.2, -5.6); all 64/16-entry index offsets exercised; unused entries 336..338 provably unread. |
| 4 | Coordinates | Forward windows fixture; reverse fixture (129, 130, `[166,190)`); exhaustive property test for every `L` in 78..120 and the 200 cases: reverse-strand site equals forward evaluation of the reverse complement mapped back, interval map is an involution; evaluable counts 123 per strand for `L=200`, `+` oriented `[58,180]`, `-` forward `[19,141]`; the one-base gap present; legacy key never used as a base. |
| 5 | Ties | Exact-tie fixture, first visited wins; strictly-lower later state replaces; ulp-different states are not ties; `tie_count` correct; no host or sigma input changes selection. |
| 6 | Boundaries | Lengths 77/78/87, left 57/58, right 180/181, edge states 1..29, empty range, range at 0 and `L`, positions at both ends, minimum and maximum limits and one past each. |
| 7 | Errors | Every code in the code list has a test; each status; precedence; mixed batch continuity; duplicate IDs and positions; deadline with injected clock and a real tight deadline; unsupported controls; exit codes 0/1/2; no partial `ok` on truncation. |
| 8 | Numerics | `relative_score` at the exact log bounds and ±1 ulp, overflow/underflow nulls with finite logs, no `inf`/`0.0`/NaN anywhere in output (`allow_nan=False`). |
| 9 | Calibration | Required, no silent default; profiles K/beta; `host_status` matrix; extrapolation warning text present; no `sigma`/temperature field accepted or emitted; `claims` all false. |
| 10 | Projection | Linear, circular without crossing, declared crossing with two segments (both strands), undeclared/mismatched crossing, contig conflict, GFF3 one-based inclusive and unwrapped circular end, escaping, strand and order along transcription. |
| 11 | Exports | JSON deterministic bytes across repeated runs and platforms; CSV header and null cells; schemas validate every example and test output; `states:"all"` bounded as limits state. |
| 12 | RBS preservation | `git diff` against the baseline shows no change to RBS modules, schemas, models, examples or frozen artifacts; the unchanged RBS suite passes in A's single final full matrix. |
| 13 | Fresh offline | Wheel installed with `--no-index --no-deps` into a new venv; `regsite-promoter` runs the single, batch, CSV and GFF3 examples; importing and running loads no `numpy`, `scipy`, `sklearn` or `Bio`; a test that blocks sockets and subprocess passes. |
| 14 | Source parity adoption | Independent source parity (2, plus B's separately executed pinned historical/fork inference on a B-frozen synthetic panel, compared through the public CLI/JSON only) passes before the stdlib engine is adopted. No expected values are copied from runtime output. |
| 15 | Freeze receipt | Exact commit, wheel and parameter hashes, effective limits and measurements, settings and CLI invocations, input manifest hash, test receipts; B acknowledges the frozen protocol before final collection. Never repair against final outcomes and call the rerun held out. |

Native Tan checks (B) are conditional localization and transcript-context
diagnostics: windows and grids are declared before scoring, positives are
grouped, and no TSS result is read as a promoter-bound, translation-strength or
precision label. B's strength replication uses only admitted sequence/condition/rights;
none of these results are runtime acceptance checks or supply tuning data.

## Out of scope

Design modes and optimizers, new fitting or retraining, alternate sigma or
temperature models, host-specific calibration, genome-wide calibrated
probabilities or site discovery, circular wrapping beyond the supplied extract,
Operon/Riboswitch coupling, hosted-service parity, native cyanobacterial accuracy
claims and cyano admission. No stub or placeholder satisfies this contract.

## Unresolved choices for A

1. **Sequence Ontology names.** `transcription_start_site`, `minus_35_signal` and
   `minus_10_signal` were not checked against a Sequence Ontology release in this
   contract-only pass; verify them (or substitute `region` with a `Note`) before
   freezing the GFF3 schema.
2. **Pinned values.** `parameter_json_sha256`, the final limit numbers and the
   `implementation_version` are produced only by the implementation and freeze
   receipt; this contract sets formats and ceilings, not those values.
3. **Derivation script home.** Choose its repository path and whether it is
   included in the sdist; it must be deterministic and hash-gated as specified.
