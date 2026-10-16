# Starting source map

- Purpose: Preserve pinned starting sources and known recovery gaps.
- Scope: Public-source and hosted-contract observations; not a runtime or accuracy certification.
- Last verified: 2026-10-16

This is the handoff from direct source and website inspection on 2026-10-16.
Pinned code observations below are starting evidence; completeness, dependency
terms, execution and production parity still require ticket 01 and benchmarks.
No third-party model code is vendored in this initial repository.

## RBS: implement first

| Source | Known value and remaining check |
| --- | --- |
| [Salis v1](https://github.com/hsalis/Ribosome-Binding-Site-Calculator-v1.0/tree/8a9c1de1bdd847bb90d2ab6ceaa3c20feceda307) | Public Python 2 model; GPL v3-or-later notice in `RBS_Calculator.py`; `NuPACK.py` expects external NUPACK 2.0. Establish an open runtime path and preserve reference identity. |
| [Jaymin's iDOG](https://github.com/jayman1466/iDOG/tree/9d71187f0b2eb27ee681918927e12850470a0688) | `dG_tot_calc.py`, `RNAfold_wrapper.py`, `create_RBS.py` provide a real scorer/designer using ViennaRNA. Repository MIT notice; verify component/dependency terms. |
| [SalisLabCode](https://github.com/hsalis/SalisLabCode) | Modern model-test harness imports private `DNAc`; a harness alone is not a runnable current model. Audit branches/tags/releases and named supplementary software. |
| [Independent Go reconstruction](https://github.com/allyourbasepair/rbscalculator) | Authors say they reconstructed from papers and document output differences from folding/cofolding choices. Candidate implementation/comparison, not certified equivalence. Pin and audit before reuse. |
| [Current energy model](https://docs.denovodna.com/docs/rbs-calculator/rbs-calculator-free-energy-model) | Equations and mechanism descriptions; map each term to paper, implementation, parameters and fixtures. |

Jaymin's scorer calculates initial RNA folding, candidate RNA–rRNA duplexes,
upstream/downstream folding, spacing and start-codon energies, then
`TIR = 2500 * exp(-0.45 * dG_tot)`. The generator calls it with kinetics disabled.
Its fixed four-base standby treatment and search/window choices need comparison
to later models. Static inspection found an apparently undefined variable
`residuemRNA_bind_indexs_in_hairpin` in its optional kinetic path and an
`RNAFoldErr`/`RNAFoldError` mismatch in the wrapper. These are audit leads, not
runtime-tested diagnoses. Do not confuse its working RBS source with its separate
bytecode-only operon/web modules or absent genomic promoter locator.

Core papers, to read with supplements:

- [2009 original model](https://pmc.ncbi.nlm.nih.gov/articles/PMC2782888/),
  DOI `10.1038/nbt.1568`.
- [2014 standby accessibility/unfolding/sliding](https://pmc.ncbi.nlm.nih.gov/articles/PMC3936740/),
  DOI `10.1093/nar/gkt1139`.
- [2016 ribosome drafting and folding kinetics](https://pubs.acs.org/doi/10.1021/jacs.6b01453),
  DOI `10.1021/jacs.6b01453`; supplementary model/data require direct review.
- [2017 coding-region footprint](https://pmc.ncbi.nlm.nih.gov/articles/PMC5435973/),
  DOI `10.1093/nar/gkx061`.
- [2020 Model Test System](https://doi.org/10.1021/acssynbio.0c00394) and
  [SynBioMTS](https://github.com/reisalex/SynBioMTS): benchmark leads. The publisher
  full text was inaccessible during the prior pass; do not imply it was read.

The hosted RBS form displayed “Version 2020” and requested `v2.1.1` through
`ReverseRBS`/`ReverseRBS_BulkMode`. It submitted to a server and consumed
`output.ReverseRBS.RBS_list`. Normally served JavaScript contained forms/results,
not a complete model or recovered `DNAc`. No jobs or exports were run. Field
names and renderer-derived intervals still require actual output checks.

The host browser lists UTEX 2973 (`NZ_CP006471`) with `ACCUCCUUU`; iDOG and v1
default to `ACCUCCUUA`. Preserve these as explicit parameter scenarios. Vendor
configuration and annotated genomic boundaries do not prove mature-rRNA
processing or host calibration.

## Promoter

Start with the public [Promoter_Calculator source](https://github.com/hsalis/SalisLabCode/tree/46da9132740bce30bccd107f02808adf2215e2f0/Promoter_Calculator)
and [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9440211/).
The cyano project already has a compatibility preparation tool and native-sequence
runtime/coordinate checks: `tools/prepare_promoter_calculator.py` and
`docs/validation/regulatory-promoter.md` in the
[consumer repository](https://github.com/rohinshanker/isaacs-cyano-gene-selection).

Its six pinned inputs are `Promoter_Calculator_v1_0.py`, `util.py`,
`free_energy_coeffs.npy`, `model_intercept.npy`, `LICENSE`, `README.md`.
Preparation updates Python 2 print syntax and scikit-learn encoder arguments;
arrays are preserved. Reuse verified work after checking its licence and current
commit, rather than repeating the port. The source uses E. coli calibration;
unknown host names fall through to it. Do not silently call that a cyano model.
Jaymin's iDOG yeast promoter library is not a genomic promoter locator.

## Operon

Start with [official Operon documentation](https://docs.denovodna.com/docs/operon-calculator)
and the public SalisLabCode directories, including
[mRNA_Stability_Calculator](https://github.com/hsalis/SalisLabCode/tree/master/mRNA_Stability_Calculator).
Trace cited papers and supplementary code for each submodel. No complete current
standalone Operon implementation was established in the prior inspection.

The hosted documentation takes a specified promoter, 1–10 RBS/CDS pairs, a
terminator and host. It describes initiation/elongation, stability, internal
promoters/terminators/translation starts and annotated GenBank output. Verify
actual modes, versions, equations, parameters, outputs and coordinate conventions
before designing the integrated implementation. iDOG's construct generator is
not evidence that it reproduces this calculator. Do not invent native operons by
concatenating adjacent genes.

## Riboswitch

Start with the [original model](https://pmc.ncbi.nlm.nih.gov/articles/PMC4705656/)
(DOI `10.1093/nar/gkv1289`) and
[later protein-sensing extension](https://pmc.ncbi.nlm.nih.gov/articles/PMC10140043/),
their supplements, linked repositories and the hosted prediction/design forms.
No complete current open implementation was established in the prior pass.

This model requires a specified aptamer and ligand-bound structure, transcript
context, binding and concentration assumptions. Separate bound/unbound
translation, occupancy and switching metrics. It is not a generic genome-wide
riboswitch finder; a native annotation workflow needs independent aptamer evidence.
Determine which later extensions belong to the production target rather than
assuming that every publication is deployed there.

## Evidence identities and retrieval

The following SHA-256 values identify original bytes previously fetched. Re-fetch
and check them when adopting evidence; cite a located passage or code symbol.
They do not grant redistribution permission or establish algorithm accuracy.

| Source at the pinned commit, or Europe PMC full-text XML | SHA-256 |
| --- | --- |
| Salis v1 `RBS_Calculator.py` | `a54f94bbe3917ad564e5808ad150311170b57c9b86e5f88c5539a2e0002354b9` |
| iDOG `dG_tot_calc.py` | `9bcb8c9e3976eedf32b4c2b8d5aebbd1891b938665eff329257a5cf36646e222` |
| iDOG `RNAfold_wrapper.py` | `baa9e3ac9508ac0808d772f19b30fecc4262625ad280e70a06ad91df7086f7eb` |
| iDOG `create_RBS.py` | `f70504e64f62e12cbc98b8fd74402ef438e5bb9be82b973c6887f2e9ba1a133e` |
| PMC2782888 | `5f14ce4456acb3d888bbfabee3d8e90248cacfbb0e34ce12e801de6f904ce964` |
| PMC3936740 | `3410c14d94f74845fe5ffa8d879bd33144909c0fc72e439bc91e9ca032333a39` |
| PMC5435973 | `63d10d9b55eb9d98430c88d1c2748e95fec8a6d8fe3b96af52bf228c0df3b3aa` |
| PMC4705656 | `fa0d7350adf4b07bcdb2b818c779ffabf135c50a72318569232a725f0d1868a6` |

Europe PMC XML route: `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC_ID/fullTextXML`
(substitute the actual PMC identifier). Prefer primary pages, repositories and
legitimate full-text mirrors; record inaccessible sources as such.

For cyanobacterial interpretation, [Lin et al. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC7890178/)
used calculator-designed synthetic RBSs in UTEX 2973 with reporter measurements;
[Sebesta and Peebles 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC6940699/)
reported poor prediction for their PCC 6803 construct context. Neither settles
native UTEX genome-wide calibration. Preserve exact host/construct/model scope.
