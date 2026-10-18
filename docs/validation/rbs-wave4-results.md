# Frozen Wave 4 experimental results

- Purpose: Preserve the independent experimental decision for one immutable RBS candidate.
- Scope: Cambray ordinary protein-output ranking; Kuo exposed secondary; no tuning or hosted/native accuracy claim.
- Last verified: 2026-10-18

## Decision and fixed endpoint

**Do not advance joint selection on this experiment.** On the 332 observed
Cambray ordinary-protein means, joint/linker-3 Spearman rho is **0.4360834392**
versus **0.4362495746** for standby/linker-3. The paired gain is
**−0.0001661354**, with a 95% seed-block interval
**[−0.0009046436, 0.0002051548]**. All 10,000 draws were usable; none was undefined.
All 335 inputs succeeded for both profiles, all 56 seed blocks contributed, and
no baseline success was lost. Collection/integrity/software gates passed.
The prespecified gain of at least 0.05 and interval strictly above zero both
failed. This is a completed negative advancement test, not a failed collection.
It does not prove exact equivalence or justify changing the threshold afterward.

The [protocol](rbs-wave4-evaluation.md) was committed and independently reviewed
before predictions met labels. The [acknowledged freeze](../../benchmarks/rbs/results/wave4-freeze.json)
pins scientific candidate `a11cb5bd13d3c021eedc98cf451609eb4710bb6a`, both backend
installations, all 11 configurations, code/parameters/weights, native settings,
18,481 unique artifact pins and completed software gates. A's
[explicit execution confirmation](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/28#issuecomment-6243651142)
authorized exactly one collection. B collected every configuration before joining
any outcome. There were no study retries, parameter changes, calibration fits,
post-result filters or new confirmatory contrasts.

The [aggregate JSON](../../benchmarks/rbs/results/wave4-aggregate.json) retains
unrounded metrics, every denominator/failure category, all model/context runtime
distributions, GC strata, descriptive contrasts, gate reasons and provenance.
This report rounds values for display; JSON is authoritative. Publication adds
only a `publication_context` object carrying source units, Kuo unknown-log-base
and rebeca training caveats. Every original evaluator field is unchanged. The
original private aggregate is retained with its own hash; remove that one added
object and reserialize as documented to recover its exact bytes.

## Primary panel and resource costs

Cambray selection is fixed at 335 inputs /112 design families /56 seed blocks,
with 332 ordinary means and 3 missing means. Coverage uses 335; correlations use
332 finite pairs. Missing means do not disappear from coverage. All11
configurations produced successful primary predictions; there were no primary
failures/timeouts/unstarted records. With complete prediction coverage, each
model's own measured-success set and the primary common set are identical here.

| Configuration | Success / inputs | Measured pairs | Spearman rho | Median / p95 / max seconds |
| --- | ---: | ---: | ---: | ---: |
| historical-traceback2 | 335/335 | 332 | 0.501889 | 0.592152 / 0.760707 / 1.156461 |
| historical-linker3 | 335/335 | 332 | 0.501889 | 0.591154 / 0.724049 / 1.043052 |
| standby2014-traceback2 | 335/335 | 332 | 0.436250 | 1.485312 / 1.879649 / 2.721225 |
| standby2014-linker3 | 335/335 | 332 | 0.436250 | 1.472979 / 1.890613 / 3.920416 |
| joint_standby-traceback2 | 335/335 | 332 | 0.436083 | 5.069362 / 5.826302 / 7.732283 |
| joint_standby-linker3 | 335/335 | 332 | 0.436083 | 5.082442 / 5.857446 / 7.742968 |
| ostir-1.1.3 | 335/335 | 332 | 0.476765 | 0.203050 / 0.286214 / 0.594260 |
| public2014-sequence-v1 | 335/335 | 332 | undefined | 0.103187 / 0.147274 / 0.316094 |
| rebeca-exp67-true | 335/335 | 332 | undefined | 2.456600 / 3.716781 / 5.158680 |
| control-constant | 335/335 | 332 | undefined | 0.000042 / 0.000071 / 0.000858 |
| control-gc-content | 335/335 | 332 | 0.028660 | 0.000038 / 0.000067 / 0.000805 |

Times include the per-record subprocess/adapter overhead on this local machine
under the frozen two-worker/single-numeric-thread schedule. They are not an
isolated engine microbenchmark or a cross-platform speed guarantee. The joint
profile's primary median is about 3.45 times standby's on linker-3 without a
measured rank gain. Control timings are interpreter-level bookkeeping, not
comparable folding costs. All executed records, including unsuccessful records
in secondary contexts, remain in the corresponding runtime denominator.

Historical's rho is 0.501889 and OSTIR's is 0.476765. Their descriptive differences
against standby/linker-3 are respectively 0.065640, interval [−0.078068,0.201101],
and 0.040515, interval [−0.096075,0.171858]. Both intervals cross zero. These are
prespecified descriptive comparisons, not additional promotion tests or
multiplicity-corrected superiority claims. The two backend variants have the
same reported primary rho and coverage for each profile. This panel consequently
does not demonstrate a biological accuracy or coverage advantage for linker-3;
its separate source/structural repair evidence remains a different claim.

Public2014 sequence-v1, rebeca and the constant control have undefined Cambray
correlation because their predictions are constant. The shared leader and last 30
feature degeneracy was identified before outcomes. Zero attempted bootstrap
draws for these contrasts means the point correlation was undefined; it does not
mean 10,000 failed draws or zero correlation. No CDS features were added to the
unchanged UTR-only models. The [comparator admission](../../benchmarks/rbs/wave4-comparator-admission.json)
keeps OSTIR 1.1.3/ViennaRNA 2.7.2 and rebeca in optional isolated research
environments. OSTIR's upstream 2.6.4 environment parity and rebeca's complete
archive/training-row identity remain unverified. Their separate source, weight,
data and dependency terms do not become required open-runtime dependencies.

Predeclared coding-GC strata contain 31/303/1 inputs and 29/302/1 measured pairs.
Only the middle stratum meets the 30-pair display rule; its paired gain is
0.0000282943, without an interval or advancement test. Low/high gains remain
null. There was no outcome-driven subgroup selection.

## Kuo exposed secondary

Each context retains 87 input genotypes. Observed means are 87 arti, 84 dmsC and 82
fepB (253 of 261 total). All configurations succeed on arti/dmsC. Each of the six
mechanistic configurations returns 81/87 fepB successes, with 77 measured pairs;
all six remaining inputs have explicit `no_candidate` status and categorical
reason `no_interstrand_candidate_in_bounded_search`. The other five
configurations succeed on all 87 fepB inputs and use 82 measured pairs.
These per-model correlations therefore do not share a common sample between
mechanistic and nonmechanistic fepB models. Do not interpret their simple
difference as a paired performance comparison.

| Configuration | arti rho (pairs) | dmsC rho (pairs) | fepB rho (pairs) |
| --- | ---: | ---: | ---: |
| historical-traceback2 | 0.391630 (87) | 0.580182 (84) | 0.507007 (77) |
| historical-linker3 | 0.391630 (87) | 0.580182 (84) | 0.507007 (77) |
| standby2014-traceback2 | 0.395175 (87) | 0.496492 (84) | 0.460696 (77) |
| standby2014-linker3 | 0.395175 (87) | 0.496492 (84) | 0.460696 (77) |
| joint_standby-traceback2 | 0.391347 (87) | 0.490224 (84) | 0.473095 (77) |
| joint_standby-linker3 | 0.391347 (87) | 0.490224 (84) | 0.473095 (77) |
| ostir-1.1.3 | 0.422106 (87) | 0.508419 (84) | 0.610096 (82) |
| public2014-sequence-v1 | 0.246249 (87) | 0.385117 (84) | 0.137919 (82) |
| rebeca-exp67-true | 0.819241 (87) | 0.573704 (84) | 0.937794 (82) |
| control-constant | undefined (87) | undefined (84) | undefined (82) |
| control-gc-content | -0.117664 (87) | -0.367949 (84) | 0.023653 (82) |

The primary pair's descriptive gains are −0.003827804 arti, −0.006267339 dmsC and
0.012399004 fepB, using 87/84/77 identical measured successes within each context.
Kuo is one connected nine-mer sequence family and an already exposed source;
there is no independent-family interval, pooled correlation or promotion test.
rebeca was trained on Kuo-related data, including fepB/data4; exact training rows
and publication-to-checkpoint mapping remain unverified. Its high fepB rho is
not independent validation. The source's Log(GFP) base is unknown; no log2,
exponentiated observation or fold-error interpretation is made.

## Source identities and limits

The [source/data contract](rbs-new-evaluation-data.md),
[manifest](../../benchmarks/rbs/new-data-manifest.json),
[source ledger](../../benchmarks/rbs/new-data-sources.json) and
[admission audit](../../benchmarks/rbs/new-data-admission-audit.json) retain exact
construct recipes, source processing, licences, conditions, exclusions and
replicate completeness. Selection commit `55da050fc3543cf9ff61e41eb269c3071d92b9fc`
predates extraction. No panel membership was selected on model success or labels.

- **Cambray2018**, DOI 10.1038/nbt.4238; OSF A56VU/10.17605/OSF.IO/A56VU;
  Data15 ZIP SHA256 `2758ed63e469c77b42c01e3c022452ef52ebf8d1bd4a86bd4c5b502e44b7bbc0`.
  E. coli MDS42 delta-recA, Rich MOPS 37 C; ordinary cleaned/normalized FACS
  fluorescence, not measured TIR or RNA-normalized TE. Inputs are exact 188-base
  local contexts/start 89, with a translated upstream leader; full clone/transcript
  boundaries remain unavailable. Deposited mean/replicate cleaning, normalization,
  exponentiation and clipping were preserved. The original depth-filter and pAcF
  unit discrepancies remain unresolved; facilitated outcomes were not evaluated.
  OSF's BSD-3-Clause node declaration applies to its deposited material, not all
  associated articles/services. Raw data are not redistributed here.
- **Kuo2020**, DOI 10.1101/gr.260182.119, PMC7263185, PRJNA516114;
  fepB/arti/dmsC member hashes respectively
  `3649ee0bb41492c1eded620dc0ebb2a2dd2c4292b91135048d0bf1b6ca680d20`,
  `4c0ef99d7111b207f73c5f2e7f6fbbb690eb5b1bcfc9b7866b3b2506f4455951`,
  `fd85858aea96dd53c6f23c50e005df21fb32faec226c45591b1c353d310c4aac`.
  MG1655, LBKG 37 C, OD600 0.55–0.65; exact 73-base local inputs/start 30,
  incomplete reporter context. CC-BY-NC-4.0 article with no separate permissive
  dataset grant located. Raw measurements remain private and outside the runtime.

No overlap flags were found in 2,800,008 comparisons against 4,698 available prior
inputs at the frozen 85% local-window threshold; 139 prior records lacked sequence.
That audit does not establish all training-set or distant-homology independence.
The paired intervals condition on this one processed study and its seed blocks;
they do not propagate assay replicate noise, normalization uncertainty or
between-study/host heterogeneity. The much narrower joint-versus-standby interval
is for the correlated difference, not an interval for either absolute rho.
No native cyanobacterial, genome-wide site-discovery, absolute initiation-rate,
current hosted-version or universal-accuracy claim follows from this experiment.
Live-versus-experiment and reconstruction-versus-live were not measured in Wave 4.

The selected 335-row Cambray panel is now **consumed**. Keep all private outcomes
and per-case residuals with B. Do not tune a corrected candidate against it and
call a rerun untouched. Unselected Cambray labels have not been released for
training; being unselected does not create a new independent-study test after
these aggregate results. A future confirmatory improvement needs a new protocol
and suitably independent reserved evidence. Frozen source/split files retain
historical `reserved_final` labels to preserve their hashes; this result records
the subsequent consumption event without mutating those identities.

## Reproduction and verification

The collection began 2026-10-18T00:20:22.818090Z and finished all 6,556 jobs in
3,864.265575 seconds, below the 14,400-second cap. It retained 11×596 JSON receipts,
raw stdout/stderr, the original receipt and protocol in a private 0700 directory;
all input/outcome/raw prediction files are 0600. Collection reports
`complete=true` and `artifacts_unchanged=true`. The evaluator verified every
request/configuration/raw-output/per-job identity before its one ordinary-label
load. No model was rerun for verification.

| Artifact | SHA256 |
| --- | --- |
| Frozen protocol | `d8eb48c4d019e7e3a6da1ed826ec9f4b43232baf03129fbf37822e9057b474ab` |
| Frozen input file | `c96399ddf396bbce4eb56802579f703c92dc46569ebcfee28db94a4001354271` |
| Frozen split | `dcccc24f43993e82c71b23dba602ceb41b81404c34c04459c297d2149028ce9a` |
| Private ordinary/facilitated source envelope | `443bc60476d79d2d1690b016d8acedd86eef05fdd5b49f4d10d5a6db6dc6015b` |
| Exact authorized collector receipt | `eba048f52132ebb1d52d812c49316de4397afb0502c39cfb895f0eaef6565591` |
| Collection | `816650a8b16dac25c3c767790533e2b437d7b62c9a960aa32b8eb3e15fd1ed2f` |
| Six-file evaluation manifest | `8cfd6d2e731a03417da405c71f7dfeb55e9018f47bbb67db1305e35a9da84eb2` |
| Original evaluator aggregate | `dcf165f06a8e97d69bb9a087ed9cc85cade939b6917fd42a84382922edea2080` |
| Published aggregate with interpretation metadata | `b3344b2c539de19b58c53675cdf8d6ac96b26dd51fa56cf1df986b44160b9935` |

Reproduction requires the evaluator-owned source/receipt artifacts. Absolute
paths in a relocated manifest may change its byte hash; every underlying pinned
artifact must still match. Do not weaken hash checks or regenerate labels to
accommodate a changed source. Recompute aggregate arithmetic from the preserved
collection into a new output; rerunning predictions is a distinct consumed-panel
replication and must be labelled accordingly. Preserve originals/exclusive output
creation and use a private parent plus restrictive umask:

```sh
umask 077
PYTHONPATH=. python -m benchmarks.rbs.wave4_evaluate EVALUATION_MANIFEST.json NEW_AGGREGATE.json
PYTHONPATH=src:. python -m pytest tests/benchmarks --cov=benchmarks.rbs --cov=benchmarks.promoter --cov-branch --cov-report=term-missing
```

The actual evaluator/collector used Python 3.14.7 from the existing Wave 2 validation
environment; external model commands and environment file pins are in the
execution freeze. The full benchmark suite passed 235 tests, with 100% coverage
of 3,462 statements and 1,436 branches. Protocol, comparator admission, synthetic joint
fixtures and collector/evaluator implementation received separate independent
reviews before final labels. The actual aggregate has no individual source IDs,
sequences, measurements, residuals or private paths.

Independent audit DEM-516 recomputed all summaries, the primary and descriptive
10,000-draw contrasts, GC/context metrics, raw-output joins and gate without
calling the production metric functions. It matched 659 exact fields and 464
floating fields, with maximum absolute numerical difference 0.0. The census is
6,520 successful jobs plus 36 explicit no-candidate results, no missing jobs.
The private audit script SHA256 is
`45539f846447f1b0fd3a18232c9c420fbf871bc22b03df3c1c2446108e04818e`;
its verification report SHA256 is
`71754dacdf8ea7fa627da126c690ab1d16a6c286188fe5dec1cce569955b5d04`.
The audit verifies arithmetic and saved evidence, not raw assay correctness,
unknown training provenance or independently timed historical execution.
Two reporting findings required dating the consumed-panel boundary and carrying
Kuo's unknown log base/rebeca training exposure in the standalone publication.
The source contract and added publication metadata address those findings;
no frozen code, prediction, original aggregate field or protocol changed.

B CI run 39082811436 on code-identical evidence head 1d7175d finished with all four
jobs passing. Its initial macOS 3.11 attempt had one subprocess-test mismatch:
`test_deadline_stops_descendant_work` expected `record_deadline` but observed
`process_start`; the underlying OS error was not captured, so its cause is
unknown. The other 1,527 tests and coverage passed. One rerun of only that failed
software job passed on the unchanged commit. The original log was retained;
there was no study retry or scoring/test/environment change. A's frozen scientific
candidate separately passed all four CI jobs before final collection.

## Ranked next-cycle hypotheses for #13

These are falsifiable future experiments, not authority to tune the consumed
panel or amend this negative result.

1. **Include verified coding-context features in a future learned model.** The
   two unchanged UTR-only comparators are constant on the common leader. Train
   coding/accessibility features on a separate development source, grouped by
   study/family, then freeze them before a new independent-context challenge.
   Falsify the proposed gain if paired ranking/coverage fails the new predeclared
   gate. Engineering cost is moderate; acquiring a genuinely independent labelled
   study is the main dependency. Do not fit current Cambray labels or silently
   change the identity of sequence-v1/rebeca.
2. **Test assay-matched mechanism/context ablations.** Historical has a higher
   descriptive rho here, but its difference interval crosses zero; this does not
   identify a beneficial term to remove. Recover complete transcript/clone
   contexts and use separate development data to freeze term/window ablations
   before evaluating a new matched ordinary-protein or paired RNA/protein assay.
   Falsify a context/mechanism benefit if it does not reproduce with preserved
   failure denominators. Source recovery is low-to-moderate cost; new matched
   measurement is a separately authorized lab/data-acquisition dependency.
3. **Test when joint candidate ordering changes useful predictions.** Synthetic
   correctness and a lower selected energy did not produce the required gain
   here, while median cost increased about 3.45-fold. Use synthetic and authorized
   development inputs to characterize candidate/standby regimes, then freeze a
   new independent challenge before seeing its outcomes. Falsify a proposed
   benefit if rank gain remains below the predeclared threshold or runtime/coverage
   worsens. No final-data-guided candidate pruning, energy refit or threshold change.

A can integrate the negative result and reviewed engineering artifacts under
#6/#13 without promoting joint selection as an accuracy improvement. The separate
[executed Promoter reference](promoter-executed-reference.md) supplies 212 states
across 11 synthetic cases, notices and compatibility/coordinate distinctions for
#7; it does not implement Promoter or waive the first-RBS-release dependency.
Native numerical panels and GSE144621 rights/full-construct admission remain
explicit gaps. No main merge, tag, package publication, browser job or coin charge
is part of this handoff.
