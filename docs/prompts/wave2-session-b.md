# Wave 2 Session B prompt

Begin Wave 2 as Session B: independent native-data, comparator and evaluation lead.
Use the selected GPT-6-Astra model. Work autonomously for up to fourteen hours
if necessary, finishing concrete reproducible evidence, executable benchmarks
and a reviewable handoff. Stop earlier when the wave acceptance criteria are met.
Do not promise that agent runtime alone can supply missing experimental biology.

Repository:
`/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/regulatory-site-prediction-reconstruction`
GitHub: `https://github.com/rohinshanker/regulatory-site-prediction-reconstruction`
Planning checkout:
`/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-rbs-runtime`
Planning branch: `wave1/rbs-runtime`, draft PR #15.
Required integrated-code ancestor: `af2c36f8f2e208b4fb4f320f9866a62aed01ce0f`.
The actual starting baseline is the final planning commit supplied with this
prompt; if omitted, fetch and resolve `origin/wave1/rbs-runtime` once, record its
full SHA, verify it contains this ancestor and all Wave 2 contracts, and agree
that exact SHA with Session A. Preserve newer work. Your previous live-panel
commit `802335dba23f9e532f1cfb2182d952c0f54eb5bd` is already integrated; do not
cherry-pick it again or continue from the old evidence branch by accident.

Read AGENTS.md, README.md, the ticket index and these contracts before edits:
- docs/validation/rbs-wave2-program.md
- docs/validation/rbs-native-validation.md
- docs/validation/rbs-comparator-landscape.md
- docs/validation/rbs-source-decision.md
- docs/validation/rbs-evaluation-protocol.md
- docs/validation/rbs-benchmark-card.md
- docs/validation/rbs-live-reference.md
- docs/validation/reconstruction-contract.md
Read the runtime's public input/result interface as needed; preserve independent
fixture/evaluator preparation and do not duplicate Session A's scoring internals.

Create or safely reuse your assignment-owned worktree:
branch `wave2/rbs-validation`
path `/Users/Rohin/Desktop/coding_stuff/ISAACS-LAB/worktrees/reconstruction-rbs-wave2-validation`.
Inspect Git/GitHub/worktree state and existing owners before writing. Never reset
newer work, implement in canonical main, or modify the cyano checkout.

You own the RBS slices of #1/#5/#12 and new #16/#17. Session A owns #4/#18, the RBS
slice of #13, runtime release integration #6, and final integration of your reviewed
commits. Claim your tickets/index rows and mirror ownership on GitHub. You own
source/evidence documents, source-specific extraction and mapping, datasets and
manifests, benchmark/comparator runners and their tests. A owns runtime/model/
training source/tests, schemas, package/locks/CI and README/AGENTS. Ask A to apply
any shared package/CI change. Explicitly accept ownership of the new native and
comparator evidence contracts in your first handshake; avoid concurrent edits.

Coordinate directly with verified identities: A was `baf5b738-1792172297`, B was
`9677689a-1792176763`. Use agent-deck if available. If a durable submission marker
blocks delivery, do not bypass or clear it; existing GitHub issue comments are
the authorized fallback. Send concise handoffs with exact commit/base, changed
paths, decisions, tests and remaining gaps. Do not launch another coordinator,
resubmit either assignment or operate a competing browser session.

Send A an early input/manifest contract, independent strand/coordinate fixtures,
development-data availability and a usable code/weight/backend recommendation.
Do not hold up implementation while completing a broad literature inventory.

Evidence priorities:
1. #16 native evidence: pin Tan 2018 publisher S1/S2 and exact UTEX genome/annotation
   as transcript-context evidence. Tan measures transcription starts, not translation
   starts or RBS strength. Preserve alternate TSSs, source/current CDS disagreements,
   conditions and unjoined cases. Inspect existing consumer provenance read-only,
   then create a portable primary-source pipeline here. Do not make a sibling
   checkout necessary for public reproduction.
2. Admit a native RNA/Ribo-seq TE dataset and an independent cyanobacterial
   reporter/context study, prioritizing Karlsen 2018 and Thiel 2018. Evaluate the
   2021 diurnal/stress studies and UTEX reporter leads as appropriate. Investigate
   the recent Synechocystis TIS-Ribo-seq/proteogenomics study for direct start labels:
   pin its actual accessible version, accession, assembly, offsets, controls and
   evidence tiers. Preprint versions are one study, and a located paper is not an
   admitted dataset. If direct positional data are unavailable, retain that exact
   gap instead of replacing it with TSSs or unverified annotation.
3. #17 comparators: audit and smoke the prioritized mechanistic/empirical and ML
   candidates. Start with the existing baseline, OSTIR, rebeca, SAPIENs, EMOPEC and
   Solaris as justified. Inspect recent GARDN–SANDSTORM and other strong applicable
   candidates; separate Prodigal/GeneLM localization from strength prediction.
   Check code, pretrained weights, original data and dependencies independently.
   Known restrictions are in the comparator contract. Keep restricted artifacts
   outside the open release; never silently substitute a different algorithm under
   an upstream name. Prefer small inference artifacts before multi-GB archives.
4. #12 evaluation: freeze eligibility, study/family/orthogroup/context partitions,
   source hashes, reference normalization, negative/unlabelled policy and metrics
   before exposing native outcomes to A. Preserve the earlier 2017 heldout. Build
   independent strength and positional evaluators, with real eligible comparator
   predictions, complete coverage/failures and scientific interpretation.

Keep raw final outcomes and per-case final errors outside public Git and away
from A while it tunes. A receives inputs, development labels and aggregate overlap
diagnostics. Audit repeated constructs, shared reporters, orthologs, conditions,
training/pretraining exposure and shared studies across models. An E. coli model's
published random split is not a native-cyano test, and a study holdout with repeated
genes is not automatically sequence-independent.

Positional evaluation must define observable candidate universes independently
of the hidden true start. Separate conditional start selection from genome-wide
discovery, exact recovery from ±3-nt sensitivity, and TIS points from SD intervals.
Unknown/undetected sites are unlabelled. Use precision/PR-AUC only with justified
negatives; otherwise report positive recall and conditional top-1/MRR with limits.
Rate evaluation reports log errors, genuine Spearman, inclusive 2×/5× thresholds,
predeclared calibration, uncertainty, all-case denominators and domain coverage.
Ribo-seq/RNA-seq is a qualified TE proxy; neither ribosome peak height nor product
yield becomes absolute initiation. Correct the known boolean-as-number input
validation gap in the benchmark metrics and test assay-specific zero/missingness.

Use the completed live panel before spending more coins. Nine CSVs contain 17
candidates; two accepted jobs explicitly returned no candidates; one 99-base
input was rejected before execution. The private ledger reserves eleven coins
at the displayed price, although actual debit remained unreconciled. Verify
artifact hashes and reuse matching jobs; do not duplicate them. You alone own
live browser access. New stages need a declared count, estimate/cap and stop
conditions under the owner's existing authorization; do not exceed an explicit
spending cap without authorization. Prepare a justified larger panel or coin
purchase proposal when necessary, but do not purchase credits. Keep live-versus-
experiment and reconstruction-versus-live results distinct. The exposed diagnostic
panel is development evidence; final compatibility claims need a fresh frozen panel.

The Keychain item `denovodna-login` was verified. Read the local procedure at
`/Users/Rohin/docs/validation/denovodna-keychain-access.md` if access is needed.
Before any action needing a new credential, administrator password or macOS
permission, disclose the exact action, resource and reason, honor existing
authorization, and await any required decision. Never bypass denied/pending
approval. No passwords, tokens, account identifiers, private exports or restricted
data in commits, issue comments, prompts or tool output.

Before final evaluation, agree with A on a finite contender roster, tuning budget,
primary endpoint, worthwhile gain, subgroup/coverage tolerances and uncertainty.
The default experiment budget is six profiles/24 configurations and three fixed
seeds for selected stochastic finalists. Select the champion on development
validation. Lock commits/weights/settings and evaluate the final predeclared
contrasts once, accounting for multiple comparisons where applicable. Do not
provide iterative final-test feedback for tuning. A negative or inconclusive
result must remain negative/inconclusive.

Assess whether specializing to cyanobacteria is supported by usable independent
labels. PCC 6803 and UTEX 2973 remain distinct host domains. Prepare a concrete
optional UTEX measurement proposal if data are insufficient: diverse leaders/CDSs,
matched RNA/protein outcomes, independent biological replication, day/batch
randomization, blinded controls, model-disagreement sampling, power and cost.
Do not execute wet-lab work, contact authors/lab members, or purchase resources.
Website coins cannot replace missing experimental ground truth.

Checkpoints: roughly 0–2 h admission/interface/early recommendation; 2–6 h frozen
datasets and runnable comparators; 6–10 h real benchmark/live comparisons; 10–12 h
final locked evaluation; 12–14 h evidence review, tests and integration handoff.
Provide useful small commits early. Keep long operations pollable; coordinate
CPU/RAM/disk with A. Stop bounded failed environment recovery and record the gap
while advancing independent work. No mandatory paid services or large downloads
without checking size/resources and necessity.

Tests must exercise every implemented evaluator/adapter path and all boundaries.
Use independent hand-checkable metric/coordinate fixtures and actual comparator
smokes; don't fabricate output to make an unavailable model appear usable. Keep
heavy optional model environments separate from ordinary offline tests and the
required runtime. Follow the user's Multica/model-routing policy only for a
worthwhile narrowly scoped subtask; no rerouting or duplicate implementation.

You may commit/push and open/update a draft PR, initially targeting
`wave1/rbs-runtime` if PR #15 remains unmerged. Do not merge PRs or push main.
Send A reviewed, integration-ready commits and explicit unresolved findings;
each owner closes only completed scope. Suite-wide #1/#5/#12 remain open if their
other calculator slices are unfinished.

Finish with exact commits/PRs, source/model/data identities and licence decisions,
commands/test results, admitted versus excluded datasets, baseline/comparator
performance with uncertainty, private artifact locations without secrets,
scientific limits, proposed next experiment and the next dependency for A.
