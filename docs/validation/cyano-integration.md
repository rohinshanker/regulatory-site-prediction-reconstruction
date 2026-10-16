# Cyano consumer boundary

- Purpose: Separate reconstructed engines from downstream native-data admission and UI.
- Scope: Versioned producer/consumer boundaries and conditional dependencies.
- Last verified: 2026-10-16

The canonical consumer is
[isaacs-cyano-gene-selection](https://github.com/rohinshanker/isaacs-cyano-gene-selection),
locally `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/isaacs-cyano-gene-selection`.
Its inspected baseline was `62c7fe2c632b14a9e1d22d74bbffdc0607b02e25` plus local
calculator-assessment documentation. Read its current instructions and queue
before touching it; baseline findings are not permission to overwrite later work.

This repository owns calculator source, model parameters, dependency pins,
reconstruction benchmarks and release artifacts. The consumer owns native
sequence extraction, organism/assembly mapping, data admission, rendering and
recoding comparisons. Integrate through a versioned package/CLI/result schema;
do not copy model internals or point production at a mutable sibling directory.

| Consumer ticket | Dependency on this repository |
| --- | --- |
| `O_rbs-calculator-gene-visualizer__20260930` | RBS release (06) and adapter (10) before the new reconstructed RBS layer is admitted; existing claim-specific validity checks remain |
| `O_idog-promoter-prediction__20260930` | Promoter reconstruction (07) and adapter (10) if selected as the scoring/comparison engine for the owner-authorized locator around iDOG; its locator scope and existing compatibility evidence remain separate |
| `O_recoding-regulatory-site-change__20260930` | Adapter (10) plus the relevant released calculator for model-based original/recoded changes; measured-site comparisons continue independently |
| `O_folding-compute-backend__20260930` | Conditional interface/performance input from 02/10/11 if these calculators are selected as remote workloads; not a prerequisite for existing local folding |

The current Tan-TSS edit-count work, Rfam family annotation and native RNA folding
do not acquire a new hard dependency merely because this repository exists.
Operon and Riboswitch consumers must retain explicit transcript/aptamer evidence;
their future layers are handled by ticket 10 rather than inferred from gene names.

## Adapter requirements

- Pin a released model/package version and result-schema version. Preserve
  upstream method identity and all reconstruction deviations in exported metadata.
- Extract unchanged/recoded sequences under the same window, host, temperature,
  structure and threshold policy. Record exact input hashes and recoding identity.
- Map verified model intervals to versioned replicons with explicit coordinate
  and strand conversions. Current UTEX assembly is `GCF_000817325.1`; never join
  an unversioned host-page accession by assumption.
- Separate native measurements, transferred evidence and predictions. Display
  model-origin host and calibration limitations. Preserve unavailable/not evaluated,
  unsupported, failed and evaluated-no-hit outcomes separately from zero changes.
- A changed score or sequence does not by itself prove disrupted regulation.
  Define added/lost/changed-site matching and thresholds before counting changes.
- No hosted credentials in a browser app or committed artifact. Runtime placement
  and sequence-transfer policy are consumer decisions, not implied by library use.
- Consumer acceptance still requires its own tests, admission contract and any
  rendered UI validation. A successful calculator benchmark does not close a
  consumer integration or scientific-validity ticket automatically.
