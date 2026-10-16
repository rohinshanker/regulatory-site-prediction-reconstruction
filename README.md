# Regulatory site prediction reconstruction

Build fully open-source, locally usable RBS, Promoter, Operon, and Riboswitch
calculators, pursuing the closest demonstrable behavior to the production
[De Novo DNA tools](https://www.denovodna.com/software/).

**Status: implementation is planned, not shipped. RBS is the first implementation.**
This repository currently contains implementation tickets, source leads, and
validation contracts. It contains no calculator, downloaded model, or generated
biological predictions yet. The project is independent of De Novo DNA/Salis Lab.

## Start a new implementation session

1. Read [AGENTS.md](AGENTS.md) and the [live ticket queue](docs/notes/tickets/INDEX.md).
2. Read the [source map](docs/validation/source-map.md),
   [reconstruction contract](docs/validation/reconstruction-contract.md), and
   [benchmark-quality assessment](docs/validation/benchmark-quality.md).
3. Claim the RBS slice of ticket 01 and the core runtime ticket 02. Rename a
   claimed ticket from `O_` to `A_`, update its H1/status and index, and identify
   the owning session. Work through RBS tickets 03–06 before implementing the
   other three calculators. Source discovery for those calculators may proceed
   independently; their incomplete discovery must not block RBS work.
4. Reuse licensed, complete public implementations where possible; reconstruct
   missing behavior from primary papers and supplements. Preserve separate
   historical, reconstructed, and hosted-reference identities.
5. Ship a reproducible RBS release and coordinate the consumer adapter under
   ticket 10. Then implement Promoter, Operon, and Riboswitch tickets 07–09 and
   complete design modes and the suite release under ticket 11.
6. Run benchmark audit 12 alongside the RBS work. Use ticket 13 to test and release
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
