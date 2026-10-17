# Native experimental validation for RBS prediction

- Purpose: Evaluate native transcript context, translation-start localization and translation strength as separate tasks.
- Scope: Wave 2 RBS evidence and evaluation, with cyanobacteria prioritized; no native accuracy has yet been established.
- Last verified: 2026-10-16

## What counts as a measurement

The owner's request for live datasets means experimentally observed biology,
including public native-genome datasets. Coin-funded website outputs remain a
separate computational reference. Neither a genome annotation nor another
predictor's output becomes experimental ground truth.

**Tan 2018 measures transcription start sites (TSS), not translation initiation
sites (TIS).** Its 4,808 sites locate RNA beginnings. They inform transcript
leaders and future promoter validation, but their read counts cannot label RBS
strength or prove ribosome initiation. TIS evidence locates a start codon; even
that does not directly establish the upstream SD pairing interval.

| Task | Admissible target | Primary evaluation | Invalid substitution |
| --- | --- | --- | --- |
| Transcript/context reconstruction | Measured TSS, versioned assembly and independently pinned CDS/start evidence | Mapping coverage, exact sequence/strand/coordinate checks, unresolved associations and context sensitivity | Calling successful TSS mapping RBS accuracy |
| Translation-start localization | Initiation-enriched Ribo-seq with validated offsets/controls, or appropriate N-terminal proteomics | Exact start recovery, recall, conditional top-1/MRR; precision/PR-AUC only with an admissible negative/label universe | Treating all annotated starts as experimental TIS, or all unobserved starts as negatives |
| Relative translation strength | Matched protein/mRNA reporter assays or qualified Ribo-seq/RNA-seq TE proxies | Log errors, true rank correlation, twofold/fivefold fractions, calibration, coverage | Using TSS counts, mRNA abundance alone or product yield as initiation rates |
| Prospective sequence design | New blinded measurements of selected and control constructs | Target error, usable-design yield, ranking and uncertainty, with all failures counted | Rescoring generated sequences with the generating model as proof of improvement |

TE from Ribo-seq/RNA-seq is affected by elongation, pausing and assay choices;
protein/mRNA ratios also reflect protein lifetime. Retapamulin peak height is
not an absolute initiation-rate assay. Preserve the measured quantity and limits.

## Dataset admission queue

Sources below were located in primary papers or author deposits. Admission still
requires file-level checks, rights, exact sequences and frozen splits. Do not
describe a located source as an already runnable benchmark.

| Priority/source | Host and evidence | Intended use and admission checks |
| --- | --- | --- |
| P0: [Tan et al. 2018](https://doi.org/10.1186/s13068-018-1215-8), Additional file 1 Tables S1/S2; BioProject PRJNA420395 | UTEX 2973 dRNA-seq, four conditions; TSS and leaderless/reannotation candidates | Context reconstruction and promoter-positive evidence only. Pin publisher Table S1 separately from Figshare's historical feature list. Preserve alternate TSSs and paper/current annotation disagreements. |
| P0: [Karlsen et al. 2018](https://doi.org/10.1128/mSystems.00126-18), [author Figshare deposit](https://doi.org/10.6084/m9.figshare.6743276.v1) | PCC 6803 matched transcriptome/translatome before and after carbon starvation | Table S2 RNA/RPF/TE plus full context can support a native TE benchmark. Repository metadata lists CC BY 4.0 and downloadable tables; verify replicate/QC definitions, strain/assembly and original processing before admission. Standard Ribo-seq is not an initiation-specific map. |
| P0: [Thiel et al. 2018](https://doi.org/10.1186/s12934-018-0882-2) | PCC 6803, 13 selected RBSs with different reporters | Small context-transfer challenge; reconstruct complete UTR/CDS junctions and measure dependence across RBS/reporter families. Do not count repeated reporters/conditions as independent RBS sequences. |
| P1: [Diurnal multi-omics, 2021](https://doi.org/10.3389/fmicb.2021.657379), PRJEB42778 / PXD023812 | PCC 6803 RNA-seq, Ribo-seq and proteomics | Independent study/condition challenge and protein-lifetime confounding check. Same-gene time points stay together; sequence-only scores cannot explain condition changes without condition inputs. |
| P1: [Photosynthesis stress multi-omics, 2021](https://doi.org/10.1128/mSystems.00943-21), PRJNA666973 | PCC 6803 RNA-seq, Ribo-seq, transcript-unit architecture under stress | External-study TE/context validation. Audit shared genes, strain substrains, assays and prior-model exposure; do not pool raw scales across studies. |
| P1: [Start/stop-enriched Ribo-seq and proteogenomics preprint](https://www.biorxiv.org/content/10.64898/2025.12.20.695498v3.full); [Research Square version](https://doi.org/10.21203/rs.3.rs-8767029/v1) | PCC 6803, retapamulin TIS profiling and orthogonal proteomic evidence | Best newly located direct positional lead. These are versions of one study, not independent datasets. Verify latest publication status, accessible processed start calls, accession, assembly, replicates and read-offset evidence. Search-visible methods describe different peak offsets: do not apply one guessed offset to all reads. Preprint status and inaccessible artifacts must remain explicit. |
| P1: [Englund et al. 2016](https://doi.org/10.1038/srep36640) | 11 RBSs tested in PCC 6803 and E. coli | Small cross-host reporter challenge; preserve shared constructs across splits and fluorescence normalization. |
| P1: [Lin et al. 2021](https://doi.org/10.1016/j.mec.2021.e00164), Figure 4 and supplements | UTEX 2973 GPPS–EYFP synthetic RBS series | Direct target-host reporter lead, not native-genome calibration. Article is CC BY-NC-ND: determine distinct data permissions before redistribution/training. Product yield is not the prediction target. |
| P2: [Edinburgh CyanOperon thesis](https://era.ed.ac.uk/items/a4bb4f3a-d175-4eaa-bbc6-0c70fb5f659b) | RBS library compared across E. coli, PCC 6803 and UTEX 2973 | Locate underlying numerical tables, exact construct sequences and any later paper; assess rights and duplicate experiments. Do not train from approximate figure readings when exact data are absent. |

## Transcript and coordinate contract

- Pin genome FASTA/annotation accessions, versions, hashes and paper-era mapping.
  UTEX target assembly is `GCF_000817325.1`; verify the current intended version
  before joining. Strain transfer is not an exact-coordinate join.
- Preserve original one-based positions and convert through tested, named
  transforms to zero-based half-open intervals, including reverse strand and
  origin-spanning sequence. A TIS point is the first translated nucleotide in
  transcript orientation, not always the genomic left endpoint.
- Preserve alternate TSSs as separate contexts. Never select a TSS because it
  produces the best prediction. Condition/read-based choices require a rule
  frozen without translation outcomes; raw TSS counts are not calibrated isoform
  mixture weights. Report unweighted scenarios when weights are unsupported.
- Clip modeled leaders to measured transcript boundaries. Distinguish leaderless,
  short-leader, internal-operon, overlapping-ORF and ambiguous-start cases.
  Unsupported biology must be counted, never silently rescued with invented RNA.
- For each input carry locus/transcript IDs, source confidence, start evidence
  type, host/condition, explicit aSD provenance, window, feature hashes and mapping
  status. An aSD sequence match alone does not establish host calibration.
- Consumer repository files may be inspected read-only. Re-fetch permitted
  primary sources for this repository's portable pipeline; no required sibling
  checkout, no copied application internals, and no changes to the cyano checkout.

Existing consumer provenance identifies publisher S1 workbook SHA-256
`098ecbd204cd1042a6edee1d2a500eaeca4efe034c503e2ade3db1c605e79b00`
and gTSS TSV SHA-256
`d06524cf492aa8f009bf004c596a5d305ac54acbe7537ec98bbc7992ce164bff`.
These are verification leads, not permission to overwrite consumer artifacts.
Historical CDS boundaries differ for some mapped genes; nearest-name or nearest-
coordinate matching is not an accepted silent repair.

## Leakage, positional tests and denominators

Before exposing new outcomes to Session A, Session B freezes data identities,
eligibility, confidence tiers, negative/unlabelled policy and partitions. Keep
related leaders, ORFs, orthologs, repeated conditions and construct families
together. Audit cross-study and pretraining overlap for every comparator.
Distinguish unseen-host, unseen-CDS, unseen-leader and repeated-gene/new-condition
generalization. Leave-one-study-out alone does not remove shared-sequence leakage.

For localization, define the candidate universe from observable sequence/context,
not a window centered on a hidden correct start. Report conditional start
selection within independently defined ORFs separately from transcript/genome
discovery. Exact start matching is primary; ±3-nt sensitivity is secondary and
cannot be used to hide systematic offsets. Use one-to-one matching while retaining
verified alternative starts. Freeze codon support and tie rules before scoring.

Unknown sites are unlabelled. If negatives are not supported, report positive
recall and conditional ranking; unmatched calls per kilobase are not a measured
false-positive rate. Any decoy challenge needs start-codon/GC/context matching,
assay coverage criteria and an explicit artificial-negative limitation. Report
precision/PR-AUC/FDR only for a defensible labelled universe, not all absent peaks.

For strength, retain the existing [evaluation protocol](rbs-evaluation-protocol.md):
predeclared reference normalization, no test refit, failed/unsupported coverage,
all-case and successful-pair metrics, family/study uncertainty, subgroup errors
and measurement noise. Count low/no expression and censored data according to
assay semantics; do not blanket-delete zeros or turn missing values into zeros.

The 2017 reserved outcomes remain blinded. The exposed Wave 1 live diagnostic
panel is development evidence, not a newly untouched final test. Freeze any new
final live panel separately and do not repeatedly tune on final results.

## Evidence sufficient for a cyanobacterial claim

A useful first endpoint is better relative translation prediction at supplied
starts in a declared cyanobacterial host/context. A second, independent endpoint
is improved start localization. Neither proves the other. Target-host UTEX
performance requires UTEX measurements; PCC 6803 results are transfer evidence.

Before promoting “better,” freeze the candidate and strongest eligible comparator,
primary endpoint, practically meaningful gain, uncertainty method and subgroup
noninferiority bounds. Use grouped development variance/power calculations to
choose sample size. If independent studies/families are insufficient, label the
result exploratory and propose prospective measurements rather than asserting
superiority. A broad state-of-the-art claim additionally requires a dated,
reproducible comparator search and coverage of strong applicable methods.

Prepare an optional prospective UTEX study with multiple CDS contexts, diverse
native/synthetic leaders, matched RNA/protein measurements, independent biological
replicates, day/batch randomization, blinded controls, and model-disagreement
sampling. Keep adaptive development measurements separate from a locked final
panel. Price the assay and use pilot variance to size it; more website coins do
not supply missing biological measurements. No purchases or laboratory execution
are authorized by this planning document.
