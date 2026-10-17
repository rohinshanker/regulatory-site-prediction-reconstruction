# Secondary native expression studies

- Purpose: Freeze independent cross-study challenges and distinguish measured/derived quantities and unavailable evidence.
- Scope: PCC6803 diurnal and photosynthesis-stress studies published in2021; no UTEX calibration claim.
- Last verified: 2026-10-17
- Owner: Session B.

## Diurnal study: admitted secondary geometric-mean ratio

[Karlsen et al.2021](https://doi.org/10.3389/fmicb.2021.657379),
PMC8237939.1, supplemental Table1 is CC BY4.0. Workbook SHA-256
`38b907068044f28030d7e7e029e9bc35441a18548ae3ebc0ff56c45c956a54c4`
is extracted from the pinned 4.31MB EuropePMC supplemental archive. The author
repository commit `J-Karlsen/diurnal-gene-expression@5baf8fc148b511478cf89569e6a6ce167dcd5428`
provides source-coordinate facts and processed abundance tables. No separate
repository code/data licence was recovered; those originals stay outside Git.
Our parser is independent code. Supplemental-workbook permissions are not silently
extended to all repository artifacts. Every source byte identity is in the ledger.

Host is PCC6803 (exact substrain unreported), BG11 pH7.8,30°C,7%CO2, turbidostat,
sinusoidal light/dark with peak500 µmol photons m−2 s−1. Five phases BRISE/ARISE/
MDAY/BSET/ASET occur −1/+1/+6/+11/+13h relative to sunrise. ENA PRJEB42778 has21
runs. RNA samples are from cultivation1; labels1/2 are repeated samples within
that cultivation, while RPF label3 is from cultivation2. Retained RPF counts per
phase are2/3/2/2/2 after the author's A2 exclusion. These are not independent RNA
cultures per phase, and there is no justified paired-replicate TE variance.

Independent source arithmetic reproduces all79,068 deposited RPKM rows using
CDS-mapped read totals. The author analysis then rescales every sample's RPKM
vector to sum to one million **before filtering**. Every one of the11,260
published RNA/RPF mean cells agrees with mean(log2(rescaled abundance)) at1e−8;
none agrees with mean(log2(original RPKM)). Thus the workbook's `Mean_log2RPKM`
headers omit a material additional normalization. The derived target here is
`2**(published mean_log2_RPF − published mean_log2_RNA)`: a ratio of geometric
means on that compositional scale. It is not a ratio of arithmetic means, a mean
of paired ratios, an author-published TE column or absolute initiation rate.
All5,630 derived condition ratios independently match the source audit at machine
precision (maximum absolute and relative difference2.22e−16; eight values differ
by floating-point exponentiation rounding across Python/libm versions).

Source code retains counts strictly>30RNA/>60RPF, whereas Methods says to remove
less than those thresholds; six RNA rows equal30. The implementation also requires
log2 rescaled abundance≥0 and excludes an RPF sample. These source filters are
not optimized here. The workbook's1,126 genes are further selected by the study's
three-omics/proteomics coverage. High-abundance/protein-detected selection and
zero filtering limit generalization. Raw-source zeros remain zeros; no pseudocount
or missing-value imputation is introduced.

The source coordinates refer to eight sequence accessions; our five-replicon
reference does not silently acquire the three extra small plasmids. Exact original
source ID plus replicon/strand/CDS-boundary agreement with current annotation
admits1,014 genes, of which **1,000 chromosomal genes** form this quantitative
challenge and14 plasmid genes remain secondary.109 source/current boundary
conflicts and three unjoined identifiers remain explicit. Negative origin-style
source starts are not guessed into current coordinates. Inputs use the same
explicit100nt genomic flank assumption and annotated aSD scenario as Karlsen2018.

The existing full-annotation homology components are inherited unchanged:
**581train /206validation /213final genes**. All five phases of a gene remain
together.986 of the1,000 primary contexts exactly match an existing Karlsen2018
sequence/start/aSD/temperature request; deterministic predictions may be reused
with an explicit source-output identity. No new family assignment or model fit
uses diurnal outcomes. Corrected input-only envelope SHA-256:
`c4a049cc1374d3db304a42efad596ee973f2eb05d1d1e53659fd059b21a246c4`.
Its contract is `rbs-diurnal-contexts-1`, not the complete native evidence schema.
Sequences/starts are transcript-oriented with scoring `strand: "+"`;
`genomic_strand` retains source direction. Use the supplied-start core adapter.
The earlier envelope `e17c2993a51d3585b622e5647ef2cf9099ef951f9de5b25c38089c0cc8b557be`
was mislabelled as the full native schema and used genomic `strand`; it is retained
as superseded evidence, not overwritten. This input-only correction changes no
identities, sequences, start positions, admissions, partitions or outcome bytes.
`diurnal2021-admission-audit.json` retains counts and frozen-split identity.

Predeclared secondary analysis: freeze champion/weights on the primary HC task;
report each phase separately on existing final gene families. Zero-shot HC-transfer
rank/error results remain distinct from a **per-phase intercept-only assay-scale
adaptation**, fitted on that phase's frozen training genes. No feature fitting or
model selection uses these outcomes. Phases reuse genes and are not independent
studies; homology-group intervals do not estimate biological-repeat uncertainty.
Identical sequence-only inputs cannot represent every condition-specific change.
This challenge cannot establish UTEX2973 accuracy or universal superiority.

```sh
python -m benchmarks.rbs.native fetch "$RAW"
python -m benchmarks.rbs.diurnal "$RAW" "$BLINDED_NATIVE_INPUTS" benchmarks/rbs/native-splits.json "$PRIVATE"
python -m unittest discover -s tests/benchmarks -p 'test_diurnal.py'
```

Extraction uses isolated openpyxl, checks workbook/member/genome identities,
retains all source rows, and writes outcomes only to an external0700 directory
with0600 files. Scoring inputs are sorted by ID and contain no assay values.

## Photosynthesis-stress study: TE not admitted

[Cho et al.2021](https://doi.org/10.1128/mSystems.00943-21), PMC8651088.1,
uses glucose-tolerant PCC6803, BG11/1%CO2: control30°C/50µmol light,
high light30°C/400, low temperature20°C/50, one-hour stress. RPF harvest follows
five minutes of chloramphenicol. RPF duplicates are described as biological;
RNA/RPF aliquot pairing and RNA biological independence are not fully resolved.
ENA PRJNA666973 has14runs. Whole-CDS and torso-only RPF counts are distinct.

The article-linked S2 RNA workbook was recovered (3,251 IDs, three normalized
condition columns, one zero; exactly3,219 genes≥10 in all conditions, versus
“more than3,219” wording). The source S3 RPF link repeatedly returned empty202
responses and no usable numerical artifact was found in bounded primary-source
retrieval. Without it, exact TE recomputation and torso/whole-CDS semantics cannot
be verified. DESeq2-normalized counts must not be substituted for RPKM/TPM. The
RNA zero gives an undefined unmodified ratio; no pseudocount is invented.

Article and PMC supplement notices state CC BY4.0; the publisher also supplies a
generic supplemental reuse notice. Individual S3 terms were not recovered.
No raw table is bundled, and no final stress accuracy claim is made. Source S5
translation-efficiency profiles and S6 transcription units are not substitute
per-gene TE or measured TIS labels. Exact unavailable artifact: the article's
[TableS3 share link](https://figshare.com/s/49e6c440505b0957b50d).
