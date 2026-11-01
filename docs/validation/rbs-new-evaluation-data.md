# New RBS evaluation data

- Purpose: Reproduce source inputs and preserve independent experimental evaluation boundaries.
- Scope: Cambray2018 bounded-context panel consumed in Wave 4; Kuo2020 exposed secondary audit.
- Last verified: 2026-10-18

The [source manifest](../../benchmarks/rbs/new-data-manifest.json),
[source ledger](../../benchmarks/rbs/new-data-sources.json) and
[frozen split](../../benchmarks/rbs/new-evaluation-split.json) identify the sources,
sequence recipes, study conditions, rights and all selected records. The selected
335-input Cambray panel was consumed by the single frozen Wave 4 evaluation after
all configurations completed. No labels or per-case residuals were supplied to A.
Frozen manifests retain their original `reserved_final` fields and hashes as
selection provenance; those fields do not describe current exposure. The prior
Wave 2 final datasets also remain consumed.

## Cambray2018: frozen final panel, now consumed

[Cambray, Guimaraes and Arkin](https://doi.org/10.1038/nbt.4238), deposit
[OSF A56VU](https://osf.io/a56vu/), DOI `10.17605/OSF.IO/A56VU`, SRA `SRP086076`.
Supplementary Data15 ZIP is 130,122,456 bytes, SHA256
`2758ed63e469c77b42c01e3c022452ef52ebf8d1bd4a86bd4c5b502e44b7bbc0`.
The named CSV contains **244,000 unique IDs and unique 96-base designed sequences**,
in 56 factorial seed series. Source field `rep` means three nearby designs
(1–4 mutations), not the four biological measurement replicates.

**Exact local input:** the 92-base `five_utr` literal from author Code15 plus
`gs.sequence`, uppercase, without another ATG. Reporter start is zero-based 89;
the design occupies [92,188). The same prefix and coordinates are independently
present in `TIPDesigner.py` at commit
`7ea83bcf7a2cda21eb8727575ff2b20ac8b49606`. Primer evidence supports the local
junction. The prefix includes a translated leader, with ATGs at 33/67/89, an
amber at [45,48) and overlapping terminal TAA [87,90). Calling all 92 bases a UTR
would misdescribe the construct.

The longer design example contains an extra downstream `GCA` before the
primer-backed linker, unlike the oligonucleotide description. Its full suffix
is therefore not silently added. Complete actual-clone/plasmid sequence and the
transcription boundary remain unverified. This is a **188-base local-context
benchmark**, not a recovered full transcript.

The host is E. coli MDS42 delta-recA; the reported assay uses 5 mL Rich MOPS,
overnight 37 C, with kanamycin/chloramphenicol/IPTG/aTc. Exact doses are incomplete.
Ordinary and facilitated initiation use the same DNA; arabinose/pAcF-enabled
amber suppression activates upstream translation coupling. Supplementary FigS5
panel A says pAcF 2.5 **mM**, while panel B / caption C and the assay passage say 2.5
**nM**. The million-fold conflict is unresolved. Accessory-system concentrations
are not substituted for assay doses.

Primary outcome `clean.lin.prot.mean` is ordinary/normal protein production,
the mean of available cleaned FACS-seq biological replicates on the authors'
1–100 scale. `clean.lin.prot.acf.mean` is a separate facilitated condition.
Neither is protein/mRNA TE or an absolute initiation rate. `log.prot.*` are bin
units; model-derived `ds.*`/`gs.*` energies are not experimental labels.

Author Code6 processes the two conditions separately: mode-window filtering,
replicate normalization, exponential transformation and clipping. Ordinary uses
three bins; facilitated uses four. Its ordinary minimum-depth call is0, whereas
the reporting summary describes requiring a mode bin with at least 5 reads.
These are source processing ambiguities, not a claim that the deposited values
are wrong. The importer preserves deposited means and replicate missingness;
it does not rerun or repair the original FACS pipeline. Data9's count audit
reproduced 745,595,539 reads over 166 samples; raw read processing was not repeated.

OSF declares BSD-3-Clause for its data/scripts, copyright 2018 Guillaume Cambray.
This is a node-level declaration, not a blanket licence for the Nature article,
Addgene records, external services or dependencies. This preparation publishes
identities/hashes and source recipes; raw measurements and full scoring inputs
stay outside Git. Source fragments are attributed here and in the ledger.

## Kuo2020: exposed secondary

[Kuo et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7263185/), DOI
`10.1101/gr.260182.119`, BioProject `PRJNA516114`. Supplementary FilesS2/S3/S4
each enumerate all 262,144 RNA9-mers in fepB/arti/dmsC GFP contexts, respectively.
There are 761,787 populated context–genotype means. Full-file hashes and exact
archive members are in the manifest; Europe PMC ZIP hashes are acquisition
provenance because regenerated ZIP metadata can change without member changes.

The importer validates every genotype, unique universe, replicate/mean
missingness and arithmetic mean within 0.001 (the source's rounding precision).
It preserves blanks rather than treating them as zero. Source attribution of
blanks to fewer than 25 reads has not been independently reproduced from raw
reads. The 109 public FASTQs total 15.199 GB and were not downloaded. The separate
YFP S5 has 9,463 literal `#VALUE!` cells and is outside the GFP panel.

TableS2 plus primers/read-filter evidence give these exact 30-base leaders:

| Context | Prefix length | Variable interval | Spacer length | Source plasmid |
| --- | ---: | --- | ---: | --- |
| fepB | 15 | [15,24) | 6 | pYC09 |
| arti | 16 | [16,25) | 5 | pYC08 |
| dmsC | 17 | [17,26) | 4 | pYC20 |

The article's fepB/dmsC positional prose disagrees with those agreeing construct
sources. Reverse-complement trimmed YC04p2 and append YC04p1; the ATG after the
arti spacer begins a 43-base GFP prefix, independently checked against ILp6.
Its SHA256 is `5bd7080e1406a40322afe3adeddd440db5af02a443bdb7731de6098cfa85fe83`.
The resulting input is 73 bases, start 30. It is not a full reporter/transcript;
do not append generic GFP or pad an unavailable window.

Host/condition: MG1655, LBKG (50 mg/L kanamycin, 10 g/L glucose), 37 C, 225 rpm,
OD600 0.55–0.65. Three FACS/NGS experiments use eight bins, except fepB replicate 3
uses 15, with spike-in calibration. Quantity is the source's **Log(GFP)**
fluorescence-derived fitness, not growth fitness or RNA-normalized TE. The
numerical log base remains unresolved: no exponentiation, fold-error or log2
conversion is authorized by these data. Source scripts also contain a context
writer-name inconsistency; they were inspected, not executed or silently fixed.

Article terms are CC-BY-NC-4.0; no separate permissive data/code grant was located.
Raw outcome tables remain outside the repository and required open runtime.
During a header probe, a CR-only CSV caused `head` to print measurement rows in
B's tool output. This was disclosed immediately; they were not sent to A.
**Kuo is explicitly exposed secondary data, not an untouched final set.**
Use a newline-aware CSV reader and print only selected metadata, never `head`
on unknown line endings in experimental files.

## Frozen selection and independent evaluation

Seed: `wave3-rbs-20261017-v1`. Selection uses sequence/identity fields only.

- **Cambray:** hash-rank `seed:combi` families, retain two per seed and every
  actual member. This selects 335 inputs from 112 families / 56 seed blocks; one
  family has only two actual design members. Before Wave 4 the entire Cambray
  study was reserved, including unselected sequences. The selected panel is now
  consumed; unselected labels remain unreleased for training. They do not become
  a new independent-study confirmation after the selected aggregate is known.
  No Cambray development labels are released. A row-random split would leak the
  deliberately nearby designs.
- **Kuo:** generate the full DNA9-mer universe; hash-select eight per GC count
  (0..9), plus four homopolymers and three parental genotypes. The 87 genotypes
  appear in all three contexts, yielding 261 inputs. All remain exposed secondary.
  The full universe is connected by single-base substitutions, so arbitrary
  row partitions cannot establish remote-family generalization.

Keep every selected input in the panel denominator, and report a separate
measured-outcome denominator. Prediction coverage uses the full panel; correlation
uses finite measured/predicted pairs with its paired count disclosed. Unmeasured
cases are not negatives or model failures. A missing prediction still counts
against coverage and any calibrated all-measured-case accuracy fraction. Do not
select on available outcomes or backend success, trim outliers, fit scale on
final measurements, or pool studies/conditions into one correlation. Primary
comparison is rank and prediction coverage within study. A final log-error claim
would additionally need an independently frozen, assay-compatible calibration;
source 1–100 fluorescence is not the runtime's arbitrary initiation-rate unit.
Use Cambray seed blocks for clustered uncertainty, and identify that all blocks
come from one experiment. Kuo is one study, not three independent replications.

Before scoring, A supplies immutable candidate commits/artifacts, named profiles,
folding/settings, resource limits and development/training exposure. Use 37 C;
Code15's E. coli aSD default is ACCUCCUUA, a model configuration rather than a
measured host calibration. Outcomes stay with B; no score-dependent retuning is
allowed after the final panel is evaluated. Keep reconstruction-versus-experiment,
live-versus-experiment and reconstruction-versus-live separate. No coins or
live jobs are part of this preparation.

Published learned models already use these sources: Cambray is used by
Nikolados2022 (`10.1038/s41467-022-34902-5`) and others; Kuo by CNN/CNN-LSTM work
`10.1093/nar/gkae491`. The panel is not automatically independent for such models.
Known-source declarations and near-duplicate checks are necessary per candidate;
new to this project is not new to the literature.

## Overlap and reproduction

[Previous-input pins](../../benchmarks/rbs/new-overlap-sources.json) cover
standby2014, footprint2017, Karlsen2018, diurnal2021 and the declared Hadjeras TIS
contexts. `new_data.previous_inputs` reads only IDs/sequences/coordinates from
these inputs. `new_data.overlap` compares both sequences over the same available
portion of [-35,+70), at exact threshold 1−edit_distance/length>=0.85. Thus Kuo's
shorter input is compared over [-30,+43) on both sides, preventing truncation from
creating artificial separation. Its bit-vector recurrence is independently
checked against a matrix implementation on 7,225 short-string pairs and longer
64/65/105/188/257-base cases. Similarity flags are sequence proxies, not proof of
all ancestral/model-training independence.

Place the pinned Cambray ZIP and three Kuo CSV members under an evaluator-owned
`SOURCE_ROOT` outside Git. Verify member hashes and original notices. Freeze
before outcome extraction, using a private parent directory:

```sh
python -m benchmarks.rbs.new_data freeze SOURCE_ROOT benchmarks/rbs/new-data-manifest.json PRIVATE_INPUTS.json --split-output SPLIT.json
python -m benchmarks.rbs.new_data extract SOURCE_ROOT benchmarks/rbs/new-data-manifest.json PRIVATE_INPUTS.json --private-output NEW_PRIVATE_DIRECTORY
python -m unittest discover -s tests/benchmarks -p test_new_data.py
```

The freeze command reserves both output files exclusively before writing. It
rejects existing files and filesystem aliases, including case-only aliases on
case-insensitive volumes. A write or buffered-close failure removes only files
created by that invocation; existing artifacts are preserved.

The extractor rederives the entire input envelope and rejects any changed
manifest/selection/source. Its output directory must not exist; it is created
0700, with outcomes and source-completeness audit 0600. It prints no outcomes.
Public split records contain identities, groups and sequence hashes, not labels
or full source sequences. The stdlib importer needs no new package dependencies.
For overlap reproduction, load each pinned prior input with
`previous_inputs(root, asset)`, then call `overlap(frozen['records'], prior)`;
record missing-source-input counts and every returned hit without filtering on
outcomes. Input-only scoring exports may be shared with A; final outcomes may not.

The [admission audit](../../benchmarks/rbs/new-data-admission-audit.json) records
freeze commit `55da050fc3543cf9ff61e41eb269c3071d92b9fc`, followed by private
extraction. Cambray has 332 observed means and three missing among 335 selected
inputs; Kuo has 253 observed and eight missing among 261. All remain in the
frozen panels. Selected means agree with available replicates within 0.001 for
Kuo rounded values and a numerical audit tolerance of 1e-6 for Cambray; none is
nonpositive.
`new_data.selected_completeness(private_outcomes, frozen_inputs)` reproduces
these counts without returning individual outcomes or changing observations.
The full Cambray table has 229,044 rows with all four cleaned replicates and
1,731 with none. These are source-quality
counts, not model performance. Private output hashes and actual 0700/0600 modes
are recorded without publishing measurements.

The [overlap audit](../../benchmarks/rbs/new-data-overlap-audit.json) finds no
threshold hits across **2,800,008 pair comparisons** against 4,698 usable prior
inputs. Another 139 prior records lack sequence (27 Karlsen, 112 diurnal) and
cannot be compared. Multiple source records can represent the same biological
context; comparison counts are not independent sample counts. Unknown upstream
training exposure and more distant homology remain outside this check.

The following hypotheses were recorded before Wave 4; they are not authority to
retune or repeat an untouched test on the now-consumed panel:

1. **Backend validity:** the archived malformed/native-failure cases and exhaustive
   tiny controls should pass after #21 repairs; failure coverage must improve
   without silently deleting structures. Falsified by persistent invalid CTs,
   missed declared tiny states, or poorer all-case coverage on the frozen panel.
2. **Explicit standby geometry:** orientation-averaged branched height and joint
   unfolding/occlusion selection should reproduce the analytic fixtures, then
   improve ordinary-protein ranking versus an otherwise identical ablation.
   Falsified by unchanged/worse paired ranking under seed-block uncertainty.
   The Cambray panel changes coding structures, so it is not a universal test of
   long upstream standby-site behavior.
3. **Assay/mechanism separation:** facilitated upstream translation coupling may
   alter performance differently from ordinary initiation. Treat facilitated
   outcomes as a separate predeclared mechanistic challenge, never as another
   replicate of ordinary protein output. Falsified by absence of a reproducible
   condition-specific advantage after candidate settings are frozen. No native
   cyanobacterial improvement follows from either condition.

Additional cyanobacterial candidates remain honestly incomplete: Lin2021 UTEX
and Sebesta2020 PCC6803 have useful construct/condition evidence but no recovered
complete numerical sequence–measurement panel; published predicted rates are
not experimental labels. Kosuri2013's linked workbooks were inaccessible through
the attempted ordinary public routes. These gaps do not turn the new E. coli
panels into evidence of cyanobacterial accuracy.

The [bounded native-source clarification](../../benchmarks/rbs/native-source-admission-update.json)
checks the primary article title and strain/cultivation methods: Sebesta and
Peebles used Synechocystis PCC 6803. The earlier PCC7942 summary was incorrect;
no frozen input, model, source ledger or evaluation membership changes. Lin
remains an UTEX2973 reporter lead. Neither source is admitted as a complete
new numerical sequence–measurement benchmark.
