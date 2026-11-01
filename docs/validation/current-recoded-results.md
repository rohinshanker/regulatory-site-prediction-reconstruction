# Independent current/recoded prediction validation

- Purpose: Validate paired prediction accounting, coordinates and source arithmetic on frozen synthetic inputs.
- Scope: Independent #39 producer validation; no measured regulatory-effect or cyanobacterial accuracy claim.
- Last verified: 2026-10-19

The frozen paired runtime retained all 4,125 requested candidates across 36 jobs
and passed the independent public-result checks. All 4,108 Promoter positions
matched independently frozen source arithmetic. RBS returned all 17 requested
starts, with 15 successful scores and two no-candidate results. These are software
and model-fidelity checks on synthetic sequences, not measurements of the effects
of recoding a cyanobacterial genome.

## Inputs and candidate

The [independent edit/coordinate contract](current-recoded-validation.md) fixes
nine sequence pairs, both local strands and both calculators. Inputs cover
unchanged sequences, declared equal replacements, substitutions, insertions,
deletions, unequal replacements, empty candidate rosters and reverse/circular
projection. Candidate universes remain explicit on both sides; an edit map matches
positions without converting an unmatched computational candidate into a
biologically gained or lost regulatory site.

Candidate `920215602a837b0fd2fed403512f3b3ed59bfda2`, wheel
`b87e7a34e09f1163e03dd69d5112307bc4cb3013e75b5ade0812cf7098ab449a`, uses the
admitted historical Promoter and historical RBS profiles. RBS uses the separately
installed RNAstructure 6.6 linker-3 backend. The [stage acknowledgement](../../benchmarks/recoding/wave5-paired-collection-ack.json)
binds the exact plan, all 36 request files, installed artifacts, complete model
identities, schemas, limits and independent source expectations before collection.
No scientific settings or candidate requests changed after outputs were seen.

All jobs ran once, serially, within a 3,600-second stage ceiling. Promoter used
30 seconds per side and RBS 60, with 30 seconds of outer exit grace inside the
whole-stage limit. Both side budgets were explicit; there was no retry, fallback,
additional job or fitted threshold. Every actual job exited 0 and its child group
was cleaned up. The private journal and read-only recovery reconciled all inputs,
observations, raw outputs, audits and final receipt.

## Complete accounting

| Calculator | Jobs | Requested / returned candidates | Scored | Matched comparable pairs | Unmatched candidates |
| --- | ---: | ---: | ---: | ---: | ---: |
| Promoter | 18 | 4,108 / 4,108 | 4,108 | 2,040 | 28 |
| Historical RBS | 18 | 17 / 17 | 15 | 5 | 7 |

Each matched pair consumes one candidate from each side: `2*2040+28=4108`
and `2*5+7=17`. All 36 wrapper results are complete in the declared accounting
sense. This does not mean every candidate received a score. The 72 native
payloads comprise 36 successful Promoter records, 14 successful RBS records and
22 no-candidate RBS records, including explicit empty requests. Missing scores
stay null; no-candidate results are neither dropped nor converted to zero.

All full paired/native JSON schemas pass. The independent checker verifies raw
and authoritative byte caps, hashes, model/settings identity relationships,
explicit candidate rosters, three-base RBS correspondence, transcript-order feature
paths, strand/circular projection, scalar extraction, delta arithmetic and coverage.
Full native model/backend objects match the admitted candidate separately.
No predictor implementation was imported to construct the expected comparisons.

## Source and unchanged-sequence controls

Before runtime collection, the independent Promoter oracle enumerated 123,240
finite states at all 4,108 synthetic positions. Selected discriminator/spacer
lengths, tie counts, all learned terms, relative scores and natural-log scores
match at the predeclared 1e-12 absolute/relative tolerance. The numerical check
includes 53,404 scalar comparisons. Promoter record/site/state identity payloads
were checked against the explicit input/model contract. This is fidelity to the
historical equations, not experimental promoter-strength validation.

The 12 unchanged-sequence jobs were selected by exact input DNA equality,
including declared equal replacements and circular/reverse controls. Six
Promoter jobs contain 684 matched comparisons and 8,208 finite scalar deltas;
six RBS jobs contain three matched comparisons and 36 finite scalar deltas.
Every finite control delta is exactly zero. Three RBS control jobs have empty
comparison lists; those remain empty rather than becoming fabricated zero-score
sites. No control was selected by observed score agreement.

Artificial result-mutation tests separately cover partial failures, missing
fields and retained nulls. The actual frozen stage had no failed job; it does
not demonstrate real backend fault-injection coverage. New helper/checker tests
cover deadline, signal, persistence and recovery behavior using harmless
executables, without a second scientific collection.

## Reproduction and limits

Use `build_requests()` in `benchmarks.recoding.runtime_check` with the frozen
fixture, then the documented collector planning/preflight API. For existing
outputs, run read-only recovery and `check_result(original_request, bytes, limits)`;
validate the full local schemas, pinned native identities and independently frozen
source expectations separately. [Current/recoded validation](current-recoded-validation.md)
describes the source-state enumeration and the distinction between these checks.
This consumed stage must not be rerun as an untouched benchmark or used to fit a
threshold. Raw/per-case outputs stay with the independent evaluator.

The synthetic panel tests the stated cases, not all possible genomes, edits,
hosts, operons or regulatory mechanisms. No RBS expression measurements or native
Promoter-strength labels are present. Model score differences have their declared
units and are not probabilities, absolute expression or causal recoding effects.
The complete JSON retains coordinate/provenance information for a future consumer;
this result does not establish cyano visualizer integration or package publication.

Artifact SHA256 values:

- Request-list canonical identity: `035ff8875ef9bca9c158a7b6ad7c72db15ef52fb242ce3247c7d7b8aa412ed8d`.
- Execution plan: `5df11c70e9b963b93406cde6ab2d82249e241177ee86cceb0f69be4e6ce9579e`.
- Independent source expectations: `9375d1a8ccd7f12ba4b661c9e798b52933e26b15724ebcdda33382283c87eb5e`.
- Private receipt: `952b596f5f9cb4db3ebc3f6458f23e8cd13623fd74f7b0664b94d6206e8d0074`.
- Private journal: `d4340270bc80e205dfc74c6739879d50a15a4d889ec770b7ffefa2c905a23132`.
- Aggregate validation: `8cc3b38c5aba4c11941147d7a38074011f004739b9634f8fa08939105d9629b4`.
- Unchanged controls: `832834d7a36b908531fdf1951242698dd200086037b7c70fa3650cf2b27b0ede`.
