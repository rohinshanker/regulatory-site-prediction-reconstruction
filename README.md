# Regulatory site prediction reconstruction

Build fully open-source, locally usable RBS, Promoter, Operon, and Riboswitch
calculators, pursuing the closest demonstrable behavior to the production
[De Novo DNA tools](https://www.denovodna.com/software/).

**Wave 1: a locally runnable RBS reconstruction is implemented.** The Python
library/CLI uses published Salis v1 equations and separately installed
RNAstructure 6.6 executables. It returns energy terms, relative initiation
scores, structures, coordinates and explicit failure/missingness. It is
independent of De Novo DNA/Salis Lab; production equivalence and cyanobacterial
calibration have not been established. The other calculators remain planned.

**Wave 2 expands the RBS research goal beyond reconstruction.** Compare strong
mechanistic and ML methods against experimental measurements, reconstruct native
transcript context, and test whether a cyanobacterial specialist can outperform
the strongest applicable baselines. “Best available” remains a hypothesis until
independent evaluation supports it. See the [two-session program](docs/validation/rbs-wave2-program.md),
[native validation](docs/validation/rbs-native-validation.md) and
[comparator roster](docs/validation/rbs-comparator-landscape.md).
Tan 2018 supplies transcription starts and RNA context, not measured translation
starts or RBS strengths. Native site localization and strength prediction have
separate validation gates.

## Run the RBS calculator

Follow the [installation and validation contract](docs/validation/rbs-runtime.md)
to install the Python package and pinned open folding backend. Inference is
local and needs no accounts, coins or network access after installation.

```sh
export REGSITE_RNASTRUCTURE="/absolute/path/to/RNAstructure"
.venv/bin/regsite examples/rbs-single.json
.venv/bin/regsite examples/rbs-batch.json --format csv
.venv/bin/regsite examples/rbs-footprint.json --profile footprint2017
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

The [PCC 6803 model card](models/rbs/karlsen2018/README.md) reports a small
development gain over a constant predictor and weak gene-to-gene ranking.
The energy/sequence variant loses too many cases to pass the coverage gate.
These models are experimental; neither establishes native UTEX 2973 accuracy.
The [public reporter model card](models/rbs/standby2014/README.md) describes the
separate E. coli experiment and its limited sequence diversity.

## Start a new implementation session

For the next parallel wave, use the complete [Session A prompt](docs/prompts/wave2-session-a.md)
and [Session B prompt](docs/prompts/wave2-session-b.md). Both start from the same
final planning commit and create separate Wave 2 worktrees. The fourteen-hour
budget includes integration and verification; the prompts do not launch themselves.

1. Read [AGENTS.md](AGENTS.md) and the [live ticket queue](docs/notes/tickets/INDEX.md).
2. Read the [source map](docs/validation/source-map.md),
   [reconstruction contract](docs/validation/reconstruction-contract.md), and
   [benchmark-quality assessment](docs/validation/benchmark-quality.md).
3. Foundation 02 and reconstructed RBS baseline 03 are complete. Wave 2 assigns
   04/06/13/18 to Session A and the RBS slices of 01/05/12 plus 16/17 to Session B;
   check current owners before claiming work. Rename a claimed ticket from `O_` to `A_`, update its H1/status and index, and identify
   the owning session. Work through RBS tickets 03–06 before implementing the
   other three calculators. Source discovery for those calculators may proceed
   independently; their incomplete discovery must not block RBS work.
4. Reuse licensed, complete public implementations where possible; reconstruct
   missing behavior from primary papers and supplements. Preserve separate
   historical, reconstructed, and hosted-reference identities.
5. Ship a reproducible RBS release and coordinate the consumer adapter under
   ticket 10. Then implement Promoter, Operon, and Riboswitch tickets 07–09 and
   complete design modes and the suite release under ticket 11.
6. Run benchmark audit 12 and native/comparator validation 16/17 alongside RBS
   implementation; 18 adds portable transcript-aware native scoring. Use ticket 13 to test and release
   improvements against experimental ground truth, while preserving the separately
   versioned production-compatibility profile.

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
