# Riboswitch canonical constrained-structure reference

- Purpose: Establish exact forced-pair and forced-unpaired Fold constraints for a future specified-aptamer state model.
- Scope: Original RNAstructure 6.6 Fold/efn2, hand-designed synthetic fixtures; no ligand, occupancy, kinetics, pseudoknot, discovery or accuracy claim.
- Last verified: 2026-10-18

## Identity

The [runner/auditor](../../benchmarks/riboswitch/constrained_reference.py)
reaches RNAstructure only through files and separate processes; it imports no
`regsite` code. Before any process starts it refuses an installation whose bytes
differ from the [fixture pins](../../benchmarks/riboswitch/canonical-fixtures.json):

| Item | SHA-256 |
| --- | --- |
| `exe/Fold` (`Fold: Version 6.6 (April 2, 2026).`) | `803a5322799779df276282601a393b3d31ea35fffc4359f6d609134643ade0f6` |
| `exe/efn2` (`efn2: Version 6.6 (April 2, 2026).`) | `1084934450523428af0ef15258f16c3f1fa174cb4949cf62e78b4581190dd8aa` |
| 45 `data_tables/rna.*` tables, compact sorted name→hash JSON | `5ff86be816a614c729a3d0a6e0ce50dcc277b3f156439e5aecf762d41f59fa0a` |
| `RNAstructureSource.tgz` | `1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3` |
| Pristine `src/algorithm.cpp` | `c024b600aabfad624fa0d4dbcd2297b9aacdb654ad2e491686847b705fa343d8` |
| `ReadMe.txt` / `gpl.txt` | `68fd4a4e…aadb88` / `e6d6a009…2cb4` (full values in the pins) |

The table map equals the runtime's pinned
[45-table manifest](../../src/regsite/data/rnastructure-tables.json). `ReadMe.txt`
states the program "is covered by the GNU GENERAL PUBLIC LICENSE Version 2";
it remains a separate GPL-2.0-only installation. The archive hash is an
installation pin, not proof of binary ancestry. The original and the evidence
installations have identical Fold/efn2 bytes; neither was modified.

## Constraint semantics

Inspected source: `src/outputconstraints.cpp` (`readconstraints`) and
`src/forceclass.cpp` (`force`, `forcesingle`, `forcepair`), plus the local
`manual/Text/File_Formats.html`. Positions are one-based; pairs list the 5′
base first. Sections DS, SS, Mod, Pairs, FMN and Forbids appear in that order,
each terminated by `-1` or `-1 -1`. This component writes only SS (forced
unpaired) and Pairs (forced pairs); the other sections are empty.

The reader performs no validation and always reports success. `force` silently
skips out-of-range positions, and a truncated file can leave the reader looping
on a failed extraction. Therefore every demand is validated before bytes are
written. Refusal codes include `crossing_pairs`,
`unsupported_structure_symbol` (any `[]{}<>` pseudoknot notation),
`duplicate_pair`, `position_in_multiple_pairs`, `paired_and_unpaired`,
`duplicate_unpaired`, `noncanonical_pair` (only AU/UA/GC/CG/GU/UG),
`hairpin_too_short` (fewer than three enclosed bases), `position_out_of_range`,
`pair_not_5prime_first`, `invalid_position` (booleans and fractions) and
`unsupported_base` (only uppercase ACGU; T, N and lowercase are not normalized).

`SS` sets the engine's SINGLE flag on every pairing cell of that base: it is a
hard exclusion. Omitting a pair leaves the base free to pair. They are not
equivalent and are recorded as separate cases. `Pairs` sets PAIR and blocks
crossing or competing partners. A `full` request is a dot-bracket string:
every `(`/`)` becomes a forced pair and every `.` a forced-unpaired base, and
the returned CT must match exactly. A `partial` request only requires inclusion
of its demands. An empty partial file is passed with `--constraint` as a no-op
control. The empty no-op file bytes are
`DS:\n-1\nSS:\n-1\nMod:\n-1\nPairs:\n-1 -1\nFMN:\n-1\nForbids:\n-1 -1\n`.
Each case's exact constraint text and hash are in the receipt.

## Execution contract

```text
Fold input.fa output.ct --MFE --loop 30 --temperature 310.15 --alphabet rna [--constraint constraint.con]
efn2 output.ct energy.txt --simple --ne --temperature 310.15 --alphabet rna
```

The environment contains only `DATAPATH=<installation>/data_tables`,
`OMP_NUM_THREADS=1` and `LC_ALL=C`; no shell is used. Isolated-pair
heuristics, dangles and coaxial stacking stay at RNAstructure 6.6 defaults.
Jobs run one at a time, each with at most 120 s, at most 30 processes and 900 s
in total, and no retries. The output directory must be new. Fold must exit 0
and write exactly one reciprocal, noncrossing, canonical CT for the submitted
sequence. Any other outcome is `backend_failed`, never repaired. A valid CT
missing a demand is `constraint_violated`. efn2 then evaluates that same CT.
`--MFE` returns one deterministic traceback; among equal minima the returned
structure is recorded, not proven unique.

Fold's CT energy compared with efn2 `--simple` on the same CT checks only
internal consistency within one engine and parameter set. It is not
independent thermodynamic validation. Fold omits the header energy for a
zero-pair structure (`fold_energy_absent`); it is never assumed to be zero.

## Executed synthetic receipt

The [real-backend receipt](../../benchmarks/riboswitch/canonical-receipt.json)
(SHA-256 `7c474565160ba5fad4011769c3dad56018241e92e2bf9212f5855a172a99ef20`)
ran the fixtures at `6a0307eec52f70f3e8bea6f2f8b757e79c8ed8b1d90d32b02e2a3ce461be7059`
with runner bytes `7ce2de5e4cce6d0b9276c4d59be1c63d8ee78cc4d6d09237ba861802cfd0b9f2`.
It used 19 processes on Python 3.14.7 on Darwin arm64. The receipt records the
`__main__.execute` executor label from that CLI run. The offline tests use
synthetic executors and are not backend verification.
Energies are in kcal/mol at 310.15 K.

| Case | Demand | Returned structure | Fold / efn2 |
| --- | --- | --- | --- |
| `hairpin_unconstrained` | none | `((((((....))))))`, the declared six-pair hairpin | −11.2 / −11.2 |
| `hairpin_noop` | empty file | identical | −11.2 / −11.2 |
| `hairpin_full` | full hairpin | identical, exact match | −11.2 / −11.2 |
| `hairpin_forced_open` | all 16 bases unpaired | no pairs | absent / 0.0 |
| `poly_a_unconstrained` | none; no canonical pair exists | no pairs | absent / 0.0 |
| `switch_unconstrained` | none | 5′ arm with first 3′ arm | −12.9 / −12.9 |
| `switch_forced_pair` | partial: pair 1–30 | 5′ arm with second 3′ arm | −9.7 / −9.7 |
| `switch_forced_unpaired` | partial: 11–16 unpaired | 5′ arm with second 3′ arm | −9.7 / −9.7 |
| `bulge_over_loop_cap` | full: needs a 32-nt bulge | Fold exit 1, `A traceback error occurred.`, no CT | `backend_failed` |

All seven declared relations hold. The no-op and full hairpin match the
unconstrained result. Both switch demands differ from the unconstrained pairs
and are not lower in efn2 energy. The open state is not below the hairpin.
All 17 contract-invalid fixtures were refused with their declared codes before
execution. The two switch demands returned the same pairs here. Neither result
is asserted from the other. The impossible case is contract-valid, but the fixed
`--loop 30` cap makes it infeasible. Feasibility under loop caps is
deliberately left to the engine, and its failure propagates without a guessed
structure.

## Supported use and remaining gates

This supports one bounded component: exact canonical, nested, fixed-state
demands, such as a supplied aptamer's bound-state pairs and unpaired bases, on
at most 200 nt with original RNAstructure 6.6. It returns an audited MFE
structure and its efn2 energy, or an explicit failure.

It does not establish the published model's backend: the 2015 supplement's
pseudoknot section cites ViennaRNA 1.8.5 canonical-stem energies, and the 2023
study's aptamer constraints used ViennaRNA 2.5/Turner 2004 without dangles. RNAstructure 6.6 differs in parameters,
dangles, coaxial stacking, isolated-pair heuristics and traceback. The
following remain separate gates: ligand binding energy and occupancy, volume
conservation, metastability and kinetic corrections, intermolecular RBS/aSD
constrained cofolding, partition functions, and SHAPE or other restraint
types. General pseudoknots and protein-steric effects also remain separate,
with no hosted-calculator equivalence and no native aptamer discovery. Session
A retains runtime implementation ownership; nothing here was trained or fitted.

## Reproduction

Use Python 3.11 or newer from the repository root, with a new output path inside
an existing directory. Do not repeat a real run merely to change its result;
fixture changes need a new fixture identity.

```sh
python -m benchmarks.riboswitch.constrained_reference run \
  --rnastructure /path/to/original/RNAstructure \
  --source-archive /path/to/RNAstructureSource.tgz \
  --output /new/private/run
python -m benchmarks.riboswitch.constrained_reference reaudit --output /new/private/run
PYTHONPATH=src python -m pytest tests/benchmarks/test_riboswitch_constrained_reference.py \
  --cov=benchmarks.riboswitch --cov-branch --cov-report=term-missing
```

`run` exits 0 when every expectation is met, 1 otherwise, and 2 on a fixture,
pin, version or output-directory refusal. `reaudit` makes no backend call; it
rechecks stored stdout/stderr, CT and energy hashes, the recorded arguments,
and every derived conclusion.
