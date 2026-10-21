# Intrinsic-termination benchmark admission

This is a provisional feasibility contract, not an evaluation result. Independent
dossier review has not completed; source pins and structural checks alone do not
constitute scientific acceptance. No predictor, folding
engine, fit or threshold search was run. None of the inspected studies establishes
UTEX 2973 accuracy. The smallest plausible next study is a fixed-model,
construct-level association audit; an unrestricted, context-complete benchmark is
not yet admitted.

## Source and runtime boundary

The source-admission dependency is C's immutable
[f4ff5e3](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/f4ff5e3a2ab0a8897cd10cb727a853683a61ce02/docs/validation/intrinsic-termination-source.md)
and its
[source manifest](https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/blob/f4ff5e3a2ab0a8897cd10cb727a853683a61ce02/benchmarks/termination/source-manifest.json).
It admits TransTermHP 2.09 source/math/terms for a separately verified build and
synthetic smoke; it does not admit a runtime or an empirical benchmark. This
dossier reuses that review and its paper hash. It does not re-audit the source.

TransTermHP's heuristic candidate quality is neither termination efficiency (TE)
nor a calibrated probability of termination. Retain candidate absence, native
pruning, strand, boundary support and failures. The frozen fragment contract has
context-sensitive background scoring and restricted anchor ranges; short inserts
cannot be made valid by invented padding. Exact tested context must precede an
experimental comparison. Later runtime receipts must be bound explicitly rather
than inferred from this source freeze.

## Evidence inventory

The companion [manifest](../../benchmarks/termination/evaluation-sources.json)
pins originals and records admission decisions. Raw papers, supplementary tables,
sequences and outcomes remain external. The bounded census contains the primary
TransTermHP study, its cited experimental validation and exactly two later
libraries. Public availability, article licence, data reuse permission and
scientific admissibility are separate fields.

| Study | Measurement and denominator | Permissible interpretation |
| --- | --- | --- |
| Kingsford 2007 / de Hoon 2005 | Operon-associated terminating versus internal nonterminating regions in *B. subtilis*. Published label counts differ: 458/562 versus 463/567. | Historical regional detection, after annotation reconciliation; not an independent held-out test or base-resolution endpoint. |
| Cambray 2013, corrected 2016 | Dual-fluorescence TE in *E. coli* BW25113; 61 elements, including 54 single and 7 double elements. | Conditional construct association and context sensitivity; not native-genome specificity or TE calibration of TransTermHP. |
| Chen 2013 | Natural, reversed and synthetic reporter constructs; source-specific versions and exclusions require explicit reconciliation. | A separate reporter study, never pooled with Cambray without assay and context harmonization. |

### Historical regional evidence

[Kingsford et al.](https://doi.org/10.1186/gb-2007-8-2-r22), “Evaluating accuracy,”
uses experimental operon annotations from
[de Hoon et al.](https://doi.org/10.1371/journal.pcbi.0010025). Its updated GenBank
annotation changes the counts from 463/567 to 458/562. Hairpin costs are inherited
from an earlier model trained on 70 known *E. coli* terminators; the published
B. subtilis operating threshold was selected using these regional labels.
Neither the historical dataset nor its threshold is newly held out.

The retrieved de Hoon S1 has 995 literature/operon rows; S2 has 4,227 gene rows.
These are not 995 independent verified termination events or the final 1,030
classification rows. S1 mixes evidence types and missing/proposed structures;
S2 marks transcript ends and readthrough. The paper's 425 structures were found
within 463 terminating regions. A predicted stem coordinate is not automatically
an experimentally mapped RNA end. Negative internal regions are conditional on
the source operon evidence, not universal nonterminators.

The available paper grants attribution-based reuse; its XML does not specify a
CC version, so this manifest does not invent one. Reproduction still needs the
exact historical genome/annotation and a reviewed rule rebuilding each positive
and negative region. Neither was retrieved here. The paper's cross-species
convergent-gene proxy, including its PCC6803 percentage, cannot establish measured
cyanobacterial sensitivity. Mixed literature conditions and RNA processing also
prevent treating all reported transcript ends as matched termination-efficiency
measurements.

### Cambray: corrected measurements and recoverable context

Use the [2016 correction](https://doi.org/10.1093/nar/gkw379) with the
[2013 paper](https://doi.org/10.1093/nar/gkt163). The correction replaces legacy
model calculations in the final two columns of Supplementary Table 1. Those
predictions and residuals are not experimental labels. The corrected workbook
has no formulas; its observed-label field is `Mean TE Cell`, column I.
The original XLS is pinned but was not parsed or compared cell by cell here.

Read-only inspection of corrected Table 1 reconciles 74 rows: 61 terminators
(rows 5–65), four mutant controls with missing TE, one normalized reference, and
eight spacers with missing TE. Do not enlarge the measured sample to 74 or turn
missing controls into negative labels. All 61 have numeric TE and insert strings;
24 inserts are shorter than 75 bases. Cell G45 contains an ASCII space. Preserve
raw bytes and record any explicit whitespace normalization in a future parser.
Table 2 supplies RIIIG pFAB763 sequence; Table 3 links test plasmids. This makes
context reconstruction plausible, not yet verified: join geometry, orientation,
scar treatment, insert coordinates and sufficient authentic flanks still need an
input-only audit.

The paper's “TE measurements” section reports triplicate, mid-exponential,
rich-medium/kanamycin assays using a Guava EasyCyte instrument. RIIIG normalizes a
downstream/upstream fluorescence ratio to a parallel reference. Multimodal
populations were revalidated and rerun. Figure 3 error bars describe cell-to-cell
spread, not automatically biological-replicate standard errors. The retrieved
workbook lacks replicate-level TE/FCS observations; culture temperature, exact
medium formulation and replicate hierarchy were not independently established
from the inspected methods and supplement. Do not invent them or calculate a
measurement-noise ceiling from a single mean.

Supplement page 5 visually confirms eight groups of related elements. Full/minimal,
mutant and tandem constructs cannot be randomized independently. Link documented
parents, exact/related cores and double-element components into connected groups
before any split. Supplement page 3 also says TransTermHP was used when selecting
initial nonterminating reference candidates. The study's sequence model includes
TransTermHP-derived features. Thus canonical-motif ascertainment and historical
family overlap remain even though these measurements postdate TransTermHP.

The 31-element curated analysis excludes low-TE and structure-confounded classes;
its accuracy is not an all-61 result. Do not copy outcome-based exclusions into a
primary endpoint. The 2013 article carries CC BY-NC 3.0; the correction carries
CC BY-NC 4.0. No separate unrestricted data waiver was established. These assets
are retained externally and are not admitted for unrestricted package/test-data
redistribution. Public download does not remove the noncommercial condition.

### Chen: reporter strength with explicit exclusions and version differences

The [publisher's public supplements](https://www.nature.com/articles/nmeth.2515)
and [author-deposited tables](https://www.addgene.org/browse/article/6862/) were
retrieved. The main article was subscription-only; full Methods and a cohort-wide
strain/medium/temperature assignment remain unverified. A supplement figure
identifies a DH5alpha no-plasmid control, which does not establish every assay's
strain. No access restriction was bypassed. The inspected landing page had no
correction link; absence of a correction is not established.

Supplementary Note 1 defines TS as induced GFP/RFP normalized to an empty-reporter
control. The stated relation `TE = 1 - 1/TS` depends on reporter assumptions;
no TE values were derived here. Note 2 identifies RNA stability, cryptic
transcription, translation and coupling as confounders. The independent Astra
evidence pass reconciled the supplement and workbook rows:

| Orientation/library | Measured | Source-excluded | Retained |
| --- | ---: | ---: | ---: |
| Natural forward | 248 | 21 | 227 |
| Reverse | 93 | 3 | 90 |
| Synthetic | 265 | 0 | 265 |
| Total | 606 | 24 | 582 |

The 24 exclusions comprise 22 high uninduced/induced RFP cases and two low-induced
GFP cases. They are assay-confounded records, not motif-negative ground truth.
The first note's “22 removed” is incomplete; Note 2 and Table 4 reconcile 24.
Keep nominated, attempted-cloning, measured and retained rosters distinct. The
94/96/75 synthetic-library counts include two unmeasured positions in the first
nominal 96-member grid; those are separate from assay exclusions.

All 606 stored records have insert sequences and mean/ratio/TS fields. Table 2
F28 contains an ASCII space. Some uncertainty fields are absent; raw per-day
observations, row-specific replicate counts and a complete matched-control roster
are unavailable. The dictionary reports measurements across days and partly
shared reference normalization. Do not infer standard errors or independent
noise from the stored SD alone. Supplement Note 11 supplies annotated reporter
sequence, but tested-junction reconstruction remains necessary. Predicted
hairpins, energies and TS columns are not experimental motif labels.

Publisher and Addgene workbooks must remain separately pinned. Natural cell A10
has an orientation-label difference (`BBa_B0062-R` versus `BBa_B0062`); synthetic
stored cells match; removed-table differences are in calculated columns. The
reported 80 forward/reverse comparisons do not equal the 75 literal retained-name
pairs. Family/orientation aliases require reconciliation before grouping. Never
use the source-selected strongest subsets as an unbiased test. The Chen model
was fitted on all 582 retained records; its predictions are not independent
outcomes, and overlap with older TransTermHP parameter families remains unresolved.

No unrestricted data licence was established in the inspected supplement,
[Nature terms](https://www.nature.com/info/terms-and-conditions) or
[Addgene terms](https://www.addgene.org/terms-of-use/). Retain external originals;
public download or plasmid deposit is not open-data redistribution permission.
This is a secondary conditional reporter-association option, with more assay,
alias and context dependencies than Cambray. It is not an admitted packaged
benchmark, a direct efficiency calibration or a cyanobacterial validation set.

## Next-stage protocol proposal

This proposal is not an executed freeze. It requires A's agreement after the
listed dependencies are satisfied. No new evaluation may silently inherit the
historical score threshold or the paper's curated exclusions.

1. **Input admission first.** Reconcile all 61 Cambray panel IDs with the corrected
   workbook, reporter backbone and test-plasmid links. Keep the 13 extra rows in
   an availability ledger, not the measurement denominator. Record raw sequence
   and normalized sequence hashes, exact cloning junctions, transcript orientation,
   insert interval and authentic context. Independently verify this input-only
   preparation before revealing outcomes to runtime developers. Do not use
   predicted structures or TE to select window size. A future fixed window must
   meet the admitted runtime's complete-context bounds for the entire declared
   insert, with no synthetic padding; otherwise retain an explicit unavailable
   input. No runtime exists in this dossier to certify such windows.
2. **Freeze identity and groups.** Bind an admitted executable, table, source,
   settings, resource receipt, input records, group map, candidate-to-insert rule
   and evaluator hash before execution. Keep all 61 constructs in accounting;
   analyze the source-defined 54 single components and 7 doubles separately.
   Construct families are connected components of documented derivation,
   homologous/identical cores, reversed/context variants and shared components
   of tandems. Resolve ambiguous links conservatively before outcomes are used.
   Record overlap with historical parameter families and Chen; a post-2007 paper
   date alone does not establish sequence independence.
3. **Task-matched endpoints.** The proposed experiment asks whether an unchanged
   heuristic ranks reporter TE within the eligible single-component panel. It
   does not estimate TE. Predeclare one target summary: maximum native quality
   among retained candidates in the assayed orientation whose reference anchor
   lies in the tested insert and whose stem/tail stays within that insert; ties
   remain ties. Report insert-boundary crossing candidates separately. No
   candidate, null quality, invalid input and execution failure remain distinct.
   Do not select a candidate by closeness to a known outcome. This rule tests
   insert-contained motifs; it can miss context-dependent termination and must
   be labelled accordingly.
4. **Denominators and missingness.** First report valid-input, successful-run,
   supported-context, retained-target and finite-summary counts over all 61 and
   separately over 54/7. Report Spearman association only on the explicitly
   counted successful finite single-component subset, alongside its full
   missingness breakdown. It is a conditional endpoint, never an all-case
   performance claim. Also report an all-54 pair accounting: of the 1,431 pairs,
   how many have two finite summaries, how many tie in score or TE, and how many
   are unavailable. Give concordance bounds by assigning unavailable non-TE-tied
   pairs either zero or full credit, with score ties half credit. TE-tied pairs
   are excluded from the concordance denominator and counted explicitly. Bounds
   are descriptive missingness bounds, not calibrated uncertainty intervals.
   If all TE values tie or too few independent families remain, the corresponding
   association/interval is unavailable rather than zero.
5. **Uncertainty without fitting.** Freeze a family-cluster resampling rule and
   seed before any execution. A proposed rule is 2,000 whole-family bootstrap
   draws with replacement and percentile 95% intervals; report undefined draws
   and the exact interval denominator. Do not resample individual cells or treat
   published cell spread as independent replicate noise. Raw biological repeats
   would be needed for a measurement-noise analysis. Do not exclude weak TE,
   unusual structures, failures or outliers based on model residuals. No
   regression calibration, new threshold, model selection or held-out tuning is
   authorized. Any conditional ranking, context contrast or double-element result
   is separate from regional detection/specificity.
6. **Do not manufacture a final cohort.** These public outcomes and figures have
   been inspected for feasibility. Their use is an exposed exploratory audit.
   Synthetic implementation fixtures must remain label-free. A future untouched
   final test requires separately admitted measurements, input-only family/study
   allocation and evaluator custody before tuning. Randomly repartitioning this
   already examined library does not create an untouched final test.

The smallest next authorized proposal is therefore an input-only reconstruction
and grouping receipt for these 61 IDs, followed by a separately reviewed frozen
single-pass audit if terms and runtime admission allow it. No new download,
execution or wet-lab work is authorized by the proposal itself. The open Bacillus
alternative additionally needs the historical genome/annotation and reviewed
label reconstruction; its proper metrics would be region-level sensitivity and
specificity with separate positive and negative denominators, not RNA-end
localization error.

## Transfer questions that remain falsifiable

These are hypotheses to test with future task-matched evidence, not conclusions
from the current dossier:

- Canonical hairpin/U-tail detection may miss organism-specific termination
  mechanisms. Matched, independently measured native positives and negatives
  would distinguish motif coverage from false-positive performance.
- Reporter-normalized strength may change with transcript context, polymerase,
  processing and growth condition. The same exact constructs measured across
  hosts would test rank preservation separately from shifts in absolute TE.
- Native fragment background, candidate pruning and insufficient supplied
  context may change reported candidates without any biological change. Fixed
  sequence/context controls and complete failure accounting can isolate this
  computational contribution.

No source here provides matched UTEX/E. coli measurements or a quantified UTEX
transfer coefficient. Missing peaks, a convergent-gene proxy, synthetic smoke and
source fidelity cannot substitute for that evidence.

## Rechecking source integrity

The manifest is a reviewed trust input; never regenerate expected hashes from
files under test. Supply the external cache root explicitly. Only listed files
are needed; no private outcome path or scorer is resolved.

```sh
python3 - /absolute/path/to/regsite-termination-evidence-20261021 <<'PY'
import hashlib, json, pathlib, sys
manifest = json.loads(pathlib.Path(
    'benchmarks/termination/evaluation-sources.json').read_text())
root = pathlib.Path(sys.argv[1])
for item in manifest['artifacts']:
    path = root / item['cache_relative_path']
    data = path.read_bytes()
    assert len(data) == item['bytes'], item['id']
    assert hashlib.sha256(data).hexdigest() == item['sha256'], item['id']
print('All explicitly listed external source bytes match.')
PY
```

This verifies bytes only. The manifest's locations support finite semantic
review of assay, counts and permissions. Missing external files fail; original
sources are not repaired, replaced with current versions or embedded in Git.
Download totals count saved public response payloads, not archive extraction or
reuse of C's existing paper. Runtime/source/parameter files beyond C's explicit
admission receipt were not opened by B. No benchmark metrics were reproduced
because neither an empirical runtime candidate nor execution protocol was
admitted in this slice.
