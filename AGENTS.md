# Reconstruction project instructions

## Scope and order

- Read `README.md`, `docs/notes/tickets/INDEX.md`, and applicable validation
  contracts before significant work. The user authorized the complete four-tool
  reconstruction program; this initial repository only records its plan.
- RBS is the first implemented and released calculator. Discovery for other
  calculators can run in parallel; do not let a suite-wide audit block a ready
  RBS slice. Avoid duplicate implementations in the cyano consumer repository.
- Search for a complete, usable, openly licensed implementation before writing
  a replacement. A wrapper, public form, directory listing, or `.pyc` file is not
  proof of a complete source implementation.
- Favor a small Python library and CLI initially, unless source/runtime evidence
  justifies another choice. Keep model equations independent of folding engines,
  file formats, browser rendering, and orchestration. No speculative service or
  web UI is required for the first release.

## Source, evidence, and access

- Every adopted equation, parameter, code component, model weight and fixture
  needs a pinned source, retrieval identity, applicable licence, and provenance.
  Record short located passages for scientific claims. Read primary papers and
  supplements directly; source leads are not verified implementation evidence.
- Distribute only components with compatible open-source/data terms. Keep
  proprietary or research-only runtime dependencies out of the required release.
  An optional historical oracle must not become necessary for users or CI.
- Do not claim to have recovered `DNAc`, matched a hosted version, or validated
  cyanobacterial accuracy without the corresponding evidence. Record model
  differences rather than tuning hidden behavior into unexplained constants.
- The owner can log in through an isolated Chrome session if needed. Keep
  passwords and session credentials in that browser. Inspect normally available
  pages/assets/downloads; do not bypass access controls, extract tokens, or
  treat paid access as permission to redistribute code or outputs.
- Before an action needing a new credential, administrator password, macOS
  permission, or other privileged access, state the exact action, resource and
  reason in chat and wait for the user's decision. Forward this rule in handoffs.
- The owner authorizes coin-funded live-reference validation. Before executing a
  benchmark stage, publish its bounded example count, estimated cost and stop
  conditions. The owner can provide another authorized lab login if coins run out,
  and can request lab funding for a justified larger panel. Purchasing credits
  requires a separate purchase instruction. Offline implementation stays independent.
- Predictions are not measurements. Distinguish host configuration from host
  calibration, start scoring from site discovery, and aptamer identification
  from conditional riboswitch scoring.

## Work and verification

- One owner per ticket and one writer per worktree. Follow the user's Multica-first
  routing policy where available; handoffs name scope, canonical checkout,
  baseline/result target, acceptance criteria and allowed child work. Workers
  must not reroute the same assignment or initiate an unrequested review chain.
- Keep source pins and test fixtures immutable. Tests ship with code; cover every
  new path, failures, boundaries, strand/coordinate conversions and reproducibility.
  Use Google style for the chosen language. No stubs, invented outputs, silent
  fallback models, or placeholder returns in a claimed implementation.
- Ticket 02 establishes exact CI/test commands. Before that, documentation-only
  changes require ticket-field/index consistency, link checks and
  `git diff --check`. Do not claim unavailable runtime tests passed.
- Each release needs fresh-install/offline smoke tests, unit and integration
  tests, scientific benchmarks, dependency/licence inventory and measured resource
  limits. Follow `docs/validation/reconstruction-contract.md`.
- Visible UI work, if later added, requires the `ui-render-inspect-repair` skill
  and rendered validation; source inspection alone is insufficient.

## Ticket lifecycle

Use `docs/notes/tickets/S_short-name__YYYYMMDD.md` with matching H1 and status.
Start with Scope, Status, Opened, Updated, Current State, Verification and Cleanup.
The live index contains only open/active tickets. GitHub issues mirror these
tickets; reconcile substantive issue discussion into the canonical Markdown.

The owning session alone closes a ticket: name itself, list unresolved findings,
record final validation, rename file/H1 to `R_...`, distill reusable contracts
into `docs/validation/` and its index, then delete the resolved ticket and remove
its queue row. Close the linked GitHub issue with the result commit and durable
contract link. Never close unfinished work or another session's ticket.
