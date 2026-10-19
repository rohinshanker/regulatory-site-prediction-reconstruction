# Regulatory site prediction reconstruction

Build fully open-source, locally usable RBS, Promoter, Operon, and Riboswitch
calculators, pursuing the closest demonstrable behavior to the production
[De Novo DNA tools](https://www.denovodna.com/software/).

**The RBS release candidate, 0.4.0rc1, runs locally.** It includes the historical
Salis v1 reconstruction, footprint/context/standby refinements, joint binding and
standby selection, a native genome/transcript adapter, and experimental sequence
and energy/sequence models.
The mechanistic profiles use separately installed RNAstructure 6.6 executables
and return energy terms, relative initiation scores, structures, coordinates and
explicit failure/missingness. Sequence-only inference needs no folding backend.

**The standby reconstruction improves the public 2014 development panel:**
106/136 predictions are within twofold of measured expression, versus 52/136
for historical scoring; mean absolute log2 error falls from 1.56 to 0.66. This
E. coli dataset helped establish the published model, so the result does not
establish performance on new studies or cyanobacteria. See the
[Wave 3 validation and reproduction](docs/validation/rbs-wave3-results.md).

**The independent Wave 4 test did not improve ranking accuracy.** On 335
reserved E. coli inputs, joint and standby scoring both covered every input.
Against the 332 measured protein-output means, their Spearman correlations were
0.43608 and 0.43625. The paired difference was -0.00017, with a 95% seed-block
interval spanning zero; the predeclared advancement gate failed. Joint selection
remains an opt-in research profile. See the
[independent report](docs/validation/rbs-wave4-results.md) and
[joint model card](docs/validation/rbs-joint-selection.md).

On that same independent panel, the historical default ranked descriptively
higher (Spearman 0.50189) than standby or joint. The historical-minus-standby
difference was 0.06564, with a 95% interval of [-0.07807, 0.20110]; this does
not establish superiority. The development-panel standby gain did not establish
an advantage on this new study.

**The independent Wave 2 comparison did not establish a superior model.** On
468 held-out PCC 6803 genes, the sequence model's mean absolute log2 error was
0.957 versus 0.990 for a constant baseline; its paired advantage over a
scale-adapted OSTIR comparator was uncertain. The predeclared promotion criteria
failed. These are experimental models with measured limitations, independent of
De Novo DNA/Salis Lab. Production equivalence and native UTEX 2973 calibration
remain unestablished.

**The historical Promoter model also runs locally.**
It scores explicitly requested transcription-start candidates on either strand,
returns the model's sequence windows and score contributions, and exports JSON,
CSV or projected GFF3. It requires only Python's standard library. Its
arithmetic reproduces the pinned historical source on synthetic states; that is
fidelity. In the independently reviewed Tan 2018 UTEX 2973 fixed-grid evaluation,
the top ten predictions recovered 36/292 in-window TSS positives exactly (12.33%)
and 47/292 within three bases (16.10%). All 364,416 requested positions completed.
The model localizes a minority of source positives; these positive-only labels
cannot establish specificity or promoter strength. Calibration remains *E. coli*.
See the [full native evaluation](docs/validation/promoter-wave5-results.md) for
confidence intervals, all 4,808 source-positive denominators and sampling limits.
This is not a released or cyanobacteria-calibrated predictor. See the
[Promoter model card](docs/validation/promoter-model-card.md). Operon integration remains in preparation. The conditional Riboswitch component
below has bounded structural and supplied-energy profiles; complete
sequence-to-switch prediction remains unavailable.

See the [independent results](docs/validation/rbs-wave2-results.md),
[native validation](docs/validation/rbs-native-validation.md) and
[comparator roster](docs/validation/rbs-comparator-landscape.md).
Tan 2018 supplies transcription starts and RNA context, not measured translation
starts or RBS strengths. Native site localization and strength prediction have
separate validation gates.

Register complete files in explicit external storage and check their byte identity
with the [offline artifact manifest tool](docs/validation/calculator-artifact-storage.md).

## Run the RBS calculator

Follow the [installation and validation contract](docs/validation/rbs-runtime.md)
and [0.4.0rc1 release/upgrade guide](docs/validation/rbs-0.4-release.md)
to install the Python package and pinned open folding backend. Inference is
local and needs no accounts, coins or network access after installation.
The optional [traceback/linker-repaired backends](docs/validation/rbs-backend-repair.md)
fix known malformed/missing folding results and each identify themselves separately.

```sh
export REGSITE_RNASTRUCTURE="/absolute/path/to/RNAstructure"
.venv/bin/regsite examples/rbs-single.json
.venv/bin/regsite examples/rbs-batch.json --format csv
.venv/bin/regsite examples/rbs-footprint.json --profile footprint2017
.venv/bin/regsite examples/rbs-standby-hairpin.json --profile standby2014
.venv/bin/regsite examples/rbs-standby-hairpin.json --profile joint_standby
```

A request supplies `sequence` and a 9-nt `anti_sd`; optional `start_positions`
selects starts in transcript orientation. The default scans AUG/GUG/UUG. Host
labels do not select hidden defaults. See the [input schema](schemas/rbs-request-1.0.schema.json),
[result schema](schemas/rbs-result-1.0.schema.json), and [model deviations](docs/validation/rbs-runtime.md).

The default historical profile is preserved. The distinct `footprint2017` and
`context2017` profiles permit RNA beyond the published coding footprint to refold;
the latter also expands the context window. See their [mechanism contract](docs/validation/rbs-mechanisms.md)
and [result schema 1.1](schemas/rbs-result-1.1.schema.json). These are explicit
partial reconstructions of later mechanisms. The [mechanism contract](docs/validation/rbs-mechanisms.md)
records reproducible folding-backend failures; longer context does not guarantee
better coverage or accuracy.

The `standby2014` profile calculates accessibility, selective RNA unfolding
and sliding using the published 2014 relationships. It returns separate penalties,
selected structures and explicit search limits in [schema 1.2](schemas/rbs-result-1.2.schema.json).
Read the [standby contract](docs/validation/rbs-standby.md) for source pins and
reconstruction choices. This implements additional mechanisms; it does not by
itself establish better experimental accuracy.

The opt-in `joint_standby` profile evaluates that full cost for every eligible
returned binding candidate before choosing one. It reports the selected candidate,
the old selection's complete energy and search progress in
[schema 1.3](schemas/rbs-result-1.3.schema.json). Any candidate failure or exhausted
search budget prevents a winning score. This improves the completeness of the
declared optimization; the frozen independent study did not establish a
biological improvement.
Read the [joint-selection contract](docs/validation/rbs-joint-selection.md).

The transcript-aware adapter accepts pinned genomes and explicit TSS/CDS scenarios:

```sh
.venv/bin/regsite-native benchmarks/rbs/native-input-example.json
.venv/bin/regsite-native benchmarks/rbs/native-input-example.json --format gff3
.venv/bin/regsite-native examples/rbs-native-karlsen.json --format gff3
```

It preserves source evidence and unsupported cases, handles both strands and
circular origins, and separates supplied-start scoring from conditional candidate
ranking. See the [native runtime contract](docs/validation/rbs-native-runtime.md).
The small example validates coordinates; it is not a native accuracy benchmark.
The Karlsen example contains two real PCC 6803 genes, one on each strand, and
their full pinned reference chromosome. It assumes 100-nt genomic flanks;
neither transcript boundaries nor translation strengths are measured by this example.

Experimental sequence-only and energy/sequence ridge models use a separate
`regsite-learned` command and explicit frozen JSON weights. Their outputs are
log2 assay responses, with training-domain warnings and no invented energies.
See the [reproducible training and inference contract](docs/validation/rbs-learning-runtime.md).

```sh
.venv/bin/regsite-learned models/rbs/karlsen2018/sequence-v1.json examples/rbs-karlsen-native.json
```

The [PCC 6803 model card](models/rbs/karlsen2018/README.md) reports the frozen
development and final results, including weak gene-to-gene ranking.
The energy/sequence variant loses too many cases to pass the coverage gate.
These models are experimental; neither establishes native UTEX 2973 accuracy.
The [public reporter model card](models/rbs/standby2014/README.md) describes the
separate E. coli experiment and its limited sequence diversity.

## Run the Promoter calculator

```sh
.venv/bin/regsite-promoter examples/promoter-contract-single.json
.venv/bin/regsite-promoter examples/promoter-contract-batch.json
.venv/bin/regsite-promoter examples/promoter-projected.json --format csv
.venv/bin/regsite-promoter examples/promoter-projected.json --format gff3
```

Supply a sequence, explicit candidate positions or range, and either the
`ecoli_mg1655` or `in_vitro` calibration profile. Host labels describe applicability;
they do not calibrate the model. A supplied cyanobacterial host label retains
the explicitly selected profile and adds an extrapolation warning. Every
requested position is retained,
including positions lacking enough flanking sequence and unfinished computations.
Predicted windows are model features, not experimentally measured regulatory
boundaries. A score difference between current and recoded sequences is a model
difference at supplied positions, not measured site gain or loss. See the
[model card](docs/validation/promoter-model-card.md),
[runtime contract](docs/validation/promoter-runtime.md),
[request schema](schemas/promoter-request-1.0.schema.json) and
[result schema](schemas/promoter-result-1.0.schema.json).

The [executed Promoter reference](docs/validation/promoter-executed-reference.md)
checks 212 synthetic states against two pinned upstream versions and an independent
numerical oracle. This checks reconstruction fidelity separately from experimental
accuracy. The relative transcription score is not a probability or an absolute
transcription rate. No native cyanobacterial accuracy or hosted parity is claimed.

## Compare current and recoded sequences

The 0.6.0rc1 paired development runtime executes both supplied sequences with the existing
RBS or Promoter calculator and compares candidates through an explicit edit map:

```sh
.venv/bin/regsite-compare examples/paired-promoter-unchanged.json
.venv/bin/regsite-compare examples/paired-promoter-indel.json --format csv
.venv/bin/regsite-compare examples/paired-rbs-substitution.json
```

RBS uses the separately installed backend above. The synthetic examples exercise
unchanged scores, substitutions and an insertion; they are not validated designs.
JSON retains both full predictions, mapped features, settings, missing values and
coverage. CSV provides scalar comparisons bound to the full JSON hash. Differences
are calculated only for successful candidates with compatible scientific settings.
An interrupted start codon or unmatched position stays explicit, without a claim
of biological site gain or loss. See the [paired contract](docs/validation/paired-regulatory-runtime.md).
The core and transport passed independent review. Package/resource admission and
the frozen producer comparison remain in progress; no canonical cyano integration
or release is implied.
The separate [0.5.0rc1 Promoter evaluation candidate](docs/validation/promoter-0.5-candidate.md)
remains immutable. Package versions and result identities stay explicit even where
the underlying calculator equations and parameter files are unchanged.

The [continuing delivery program](docs/validation/calculator-delivery-program.md)
then adds admitted supplied-operon and specified-aptamer components. The visualizer
remains a downstream consumer of versioned predictions.

## Conditional aptamer components

The 0.7.0rc1 development runtime provides two explicit components:

```sh
.venv/bin/regsite-conditional examples/conditional-supplied-half-occupancy.json
.venv/bin/regsite-conditional examples/conditional-supplied-volume-fifth.json
.venv/bin/regsite-conditional examples/conditional-hairpin-structure-control.json \
  --backend-root /path/to/admitted/original/RNAstructure
```

The supplied-energy profile computes response ratios from caller-supplied RNA and
ribosome energies, affinity, and either an occupancy fraction or explicit
concentrations and relative volumes. It needs only Python. The structural profile
folds unconstrained RNA and RNA compatible with a supplied canonical aptamer
structure. Its initial admission is limited to the recorded original macOS arm64
RNAstructure binaries; repaired RBS engines are refused. Other builds require
separate fixture validation.

These examples are synthetic checks. The structural energies do not supply the
missing ligand-constrained ribosome model, and the scalar calculation does not
infer an aptamer or physiological concentrations. Every result retains source,
parameter and backend identities, warnings, partial states and explicit failures.
Review and package validation remain in progress. See the
[conditional contract](docs/validation/conditional-aptamer-runtime.md).

## Start a new implementation session

Read the [current release guide](docs/validation/rbs-0.4-release.md),
[independent Wave 4 result](docs/validation/rbs-wave4-results.md) and live ticket
queue before starting work. Wave 4's scoped implementation/evaluation is complete;
the public-release milestone remains under ticket 06. Its
[Session A](docs/prompts/wave4-session-a.md) and
[Session B](docs/prompts/wave4-session-b.md) prompts preserve the assignment and
freeze boundaries; do not replay the consumed experiment as a new untouched test.
Future model changes require a new development/evaluation protocol and suitable
reserved evidence. Preserve newer work, immutable candidate identities and ownership.

1. Read [AGENTS.md](AGENTS.md), the [live ticket queue](docs/notes/tickets/INDEX.md)
   and the [Wave 4 validation](docs/validation/rbs-wave4-results.md). Check current
   owners and preserve newer branches/worktrees before claiming work.
2. Read the [source map](docs/validation/source-map.md),
   [reconstruction contract](docs/validation/reconstruction-contract.md), and
   [benchmark-quality assessment](docs/validation/benchmark-quality.md).
3. Foundation 02, historical scoring 03 and portable native adapter 18 are
   complete. Tickets 04/06/13 retain remaining mechanisms, release work and
   experimentally justified improvements. Source recovery for other calculators
   can proceed independently. The owner authorizes isolated calculator implementation
   alongside RBS release preparation; publication and consumer admission stay separate.
4. The Wave 2 models, offsets and final comparison are frozen. Any new scientific
   change needs a new development cycle and untouched evaluation data. Do not
   tune against these exposed final outcomes. The original
   [Session A](docs/prompts/wave2-session-a.md) and
   [Session B](docs/prompts/wave2-session-b.md) prompts document the completed
   assignment; do not replay them as a new experiment.
5. Preserve separate historical, reconstructed and hosted-reference identities.
   Coordinate consumer admission through ticket 10; implement Promoter, Operon
   and Riboswitch under 07–09, then design modes and suite delivery under 11.
   The [prospective UTEX proposal](docs/validation/rbs-utex-measurement-proposal.md)
   describes the new measurement dependency for stronger native claims.

| Calculator | First usable scope | Completion target |
| --- | --- | --- |
| RBS | Start-associated initiation scoring, energy breakdown, structures and coordinates | Historical reference, documented refinements, batch prediction and target-rate design |
| Promoter | DNA-to-TSS/promoter profiles with explicit sigma-factor and calibration identity | Both-strand prediction, feature intervals, and constrained promoter design |
| Operon | Expression and internal-element prediction for explicitly supplied operon organization | Integrated submodels, annotated export, and constrained operon design |
| Riboswitch | Conditional prediction for a specified aptamer, ligand and bound structure | Bound/unbound regulation profiles and constrained switch design |

The [cyano gene-selection repository](https://github.com/rohinshanker/isaacs-cyano-gene-selection)
is a downstream consumer, not the home for reconstructed model internals.
Its release/admission rules still govern any displayed prediction. See the
[consumer boundary](docs/validation/cyano-integration.md).

New website collection and coin purchases are deferred for this wave.
Live-reference validation uses coin-funded website runs under ticket 05. The owner
can supply additional authorized lab logins if coins are exhausted and can request
lab funding for a justified larger panel. Reference spending is separate from the
public software: anyone must be able to run the released calculators offline
without accounts or coins.

## Meaning of complete

A fresh checkout must build and run the released calculator without private
packages, bytecode-only modules, De Novo DNA credentials, or mandatory paid
services. Code, required parameters, permitted benchmark fixtures, dependency
pins, installation instructions, tests, and examples ship together. Agreement
with a hosted implementation and accuracy against experiments are evaluated
separately. Unverified equivalence remains unverified; a partial model is never
silently labeled a complete production equivalent.

Original contributions are licensed under **GPL-3.0-or-later**; see [LICENSE](LICENSE).
This choice accommodates the GPL source candidates already identified. Upstream
notices and per-component terms must be retained and reviewed before reuse.
Public availability alone does not establish an open-source licence.

The Markdown tickets are the implementation source of truth; linked GitHub
issues provide discoverability and discussion. Update both when work is claimed
or completed. Durable specifications live in `docs/validation/`, not closed-ticket
histories. The canonical local checkout is
`/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/regulatory-site-prediction-reconstruction`.
