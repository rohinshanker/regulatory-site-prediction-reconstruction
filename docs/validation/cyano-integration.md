# Cyano consumer boundary

- Purpose: Separate reconstructed engines from downstream native-data admission and UI.
- Scope: Versioned producer/consumer boundaries and conditional dependencies.
- Last verified: 2026-10-18

This verification date covers the ownership/implementation boundary; the consumer
baseline below remains historical.

The canonical consumer is
[isaacs-cyano-gene-selection](https://github.com/rohinshanker/isaacs-cyano-gene-selection),
locally `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/isaacs-cyano-gene-selection`.
Its inspected baseline was `62c7fe2c632b14a9e1d22d74bbffdc0607b02e25` plus local
calculator-assessment documentation. Read its current instructions and queue
before touching it; baseline findings are not permission to overwrite later work.

This repository owns calculator source, model parameters, dependency pins,
reconstruction benchmarks and release artifacts, including paired prediction
and coordinate comparison of caller-supplied current/recoded sequences under
[the continuing program](calculator-delivery-program.md) and ticket #41. The
consumer owns native sequence extraction, organism/assembly mapping, data
admission, rendering and the presentation/interpretation of recoding comparisons.
Producer work does not authorize canonical consumer edits or admit a UI layer.
Integrate through a versioned package/CLI/result schema;
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

## Available producer interfaces

| Task in the visualizer | Producer interface | Interpretation boundary |
| --- | --- | --- |
| Score an annotated translation start under an explicit transcript context | `regsite-native`, `native-rbs-result-1` | Supplied-start score; transcript/annotation alternatives stay separate. Tan transcription starts are context evidence, not measured translation starts. |
| Score explicit transcription-start candidates | `regsite-promoter`, schema `1.0` | Historical E. coli calibration; predicted windows and score terms remain separate from measured Tan TSS labels. |
| Compare an existing sequence with a supplied recoded sequence | `regsite-compare`, `paired-regulatory-result-1` | Exact caller-supplied edits establish correspondence. Score differences require successful compatible predictions; unmatched positions do not establish biological site gain/loss. |
| Inspect a supplied aptamer state or energy scenario | `regsite-conditional`, `conditional-aptamer-result-1` | Conditional components only. Neither an Rfam family hit nor a gene name supplies ligand affinity, a bound structure or constrained ribosome energies. |
| Score supplied CDSs sharing an explicit transcript and scan supplied Promoter candidates | `regsite-transcript`, `supplied-transcript-result-1` | Independent RBS/Promoter components with caller-supplied organization; no operon discovery, coupling or joint protein-output prediction. |

The paired [request/result contract](paired-regulatory-runtime.md) is the first
producer interface designed directly for the current/recoded comparison. Store
its full JSON and `prediction_sha256`; the CSV is a scalar summary bound to that
JSON, not a replacement for its coordinate paths or structures. Use
`coverage.current`, `coverage.recoded`, `coverage.paired`, `coverage.unmatched`
and `coverage.comparable` separately. `roster_status=unknown` differs from a
known empty list. Null deltas and their reasons must survive caching and display.
A changed input, backend, profile, calibration or effective setting requires its
own identity; do not cache only by gene name.

Each side retains its own native prediction and coordinate frame. Use the emitted
feature paths and split genomic segments for rendering, including reverse strands
and circular-origin crossings. Never draw a bounding interval across an unmapped
edit, reinterpret an empty interval as an origin base, or move a native structure
into another frame without an established mapping. An interrupted start codon
retains both unmatched candidate observations. Sequence-only positional
correspondence does not establish unchanged protein or transcript identity.

For supplied transcripts, retain the full native predictions, component rosters,
per-CDS compatibility reasons and the complete JSON hash. The
[transcript contract](supplied-transcript-runtime.md) distinguishes component
`missing` from `not_evaluated`; an incompatible CDS remains in the annotation
roster even though it has no native RBS site. A deadline can leave a component
unstarted with a null prediction. `coverage.scored` counts successful sites
across both components and is never a combined expression score. Complete
accounting does not imply every candidate scored.

Each transcript isoform and recoded construct needs its own explicit RNA/CDS
coordinates. The transcript wrapper does not infer alignment between constructs;
use the paired edit-map contract for current/recoded correspondence. An old
chromosome projection does not establish genomic correspondence across an indel.

The [paired 0.6](paired-0.6-candidate.md),
[conditional 0.7](conditional-0.7-candidate.md) and
[transcript 0.8](transcript-0.8-candidate.md) guides record immutable package
identities, resource evidence and their separate admission gates. Select the
reviewed artifact named by the guide, not a mutable branch or worktree head.
Candidate validation can support consumer development, but
production admission still requires the released artifact and consumer-owned
checks above. No consumer files were changed as part of these producer contracts.
