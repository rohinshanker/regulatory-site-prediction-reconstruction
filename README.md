# Regulatory site prediction reconstruction

Build fully open-source, locally usable RBS, Promoter, Operon, and Riboswitch
calculators, pursuing the closest demonstrable behavior to the production
[De Novo DNA tools](https://www.denovodna.com/software/).

**The RBS release candidate, 0.3.0rc1, runs locally.** It includes the historical
Salis v1 reconstruction, separately named footprint/context/standby refinements, a native
genome/transcript adapter, and experimental sequence and energy/sequence models.
The mechanistic profiles use separately installed RNAstructure 6.6 executables
and return energy terms, relative initiation scores, structures, coordinates and
explicit failure/missingness. Sequence-only inference needs no folding backend.

**The independent Wave 2 comparison did not establish a superior model.** On
468 held-out PCC 6803 genes, the sequence model's mean absolute log2 error was
0.957 versus 0.990 for a constant baseline; its paired advantage over a
scale-adapted OSTIR comparator was uncertain. The predeclared promotion criteria
failed. These are experimental models with measured limitations, independent of
De Novo DNA/Salis Lab. Production equivalence and native UTEX 2973 calibration
remain unestablished; the other calculators remain planned.

See the [independent results](docs/validation/rbs-wave2-results.md),
[native validation](docs/validation/rbs-native-validation.md) and
[comparator roster](docs/validation/rbs-comparator-landscape.md).
Tan 2018 supplies transcription starts and RNA context, not measured translation
starts or RBS strengths. Native site localization and strength prediction have
separate validation gates.

## Run the RBS calculator

Follow the [installation and validation contract](docs/validation/rbs-runtime.md)
to install the Python package and pinned open folding backend. Inference is
local and needs no accounts, coins or network access after installation.
The optional [traceback-repaired backend](docs/validation/rbs-backend-repair.md)
fixes known malformed/missing folding results and identifies itself separately.

```sh
export REGSITE_RNASTRUCTURE="/absolute/path/to/RNAstructure"
.venv/bin/regsite examples/rbs-single.json
.venv/bin/regsite examples/rbs-batch.json --format csv
.venv/bin/regsite examples/rbs-footprint.json --profile footprint2017
.venv/bin/regsite examples/rbs-standby-hairpin.json --profile standby2014
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

The new `standby2014` profile calculates accessibility, selective RNA unfolding
and sliding using the published 2014 relationships. It returns separate penalties,
selected structures and explicit search limits in [schema 1.2](schemas/rbs-result-1.2.schema.json).
Read the [standby contract](docs/validation/rbs-standby.md) for source pins and
reconstruction choices. This implements additional mechanisms; it does not by
itself establish better experimental accuracy.

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

## Start a new implementation session

1. Read [AGENTS.md](AGENTS.md), the [live ticket queue](docs/notes/tickets/INDEX.md)
   and the [independent results](docs/validation/rbs-wave2-results.md). Check current
   owners and preserve newer branches/worktrees before claiming work.
2. Read the [source map](docs/validation/source-map.md),
   [reconstruction contract](docs/validation/reconstruction-contract.md), and
   [benchmark-quality assessment](docs/validation/benchmark-quality.md).
3. Foundation 02, historical scoring 03 and portable native adapter 18 are
   complete. Tickets 04/06/13 retain remaining mechanisms, release work and
   experimentally justified improvements. Source recovery for other calculators
   can proceed independently; implement those calculators after the RBS release.
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
