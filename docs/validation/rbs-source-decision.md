# RBS source and open-backend decision

- Purpose: Select reusable RBS components without requiring restrictive software.
- Scope: Wave 1 source recovery; source-equation fixtures are independent of the reconstruction.
- Last verified: 2026-10-16

## Decision for tickets 02–04

Reuse the **Salis v1 equations and explicit scalar parameters** under its
GPL-3.0-or-later file notice. Preserve a named historical specification, but call
an implementation with a different folding engine a reconstruction. Use iDOG
as a contrasting algorithm, not as a drop-in historical port.

**Do not require ViennaRNA to satisfy the entirely open release contract.**
Its v2.7.2 `COPYING` permits research, educational and commercial use but prohibits
redistribution for a fee other than media costs. The
[official licence](https://www.tbi.univie.ac.at/RNA/ViennaRNA/refman/license.html)
has the same restriction. Source availability and free academic use do not remove
it. NUPACK 2.0 is also not an accepted required dependency; the public Salis code
includes a wrapper, not that engine.

The recommended open candidate is **RNAstructure 6.6 as separately installed,
unmodified command-line tools** (`Fold`, `bifold`, `AllSub`, `efn2`, `ct2dot`),
using its included RNA energy tables. The source archive's `ReadMe.txt` and
`gpl.txt` specify GPL version 2; treat it as GPL-2.0-only. Do not copy/link that
code into GPL-3.0-or-later calculator code. Use independent executables and
ordinary sequence/CT files, and preserve their licence/source distribution
separately. A binary distribution needs corresponding source and notices.
This is a dependency architecture recommendation, not a legal clearance of
arbitrary combined packaging.

RNAstructure supplies single-strand folding, bimolecular folding with optional
intramolecular pairing, suboptimal structures and fixed-structure energy
evaluation. Its enumeration, multiloop/dangle treatment, temperature units and
energy tables differ from NUPACK. No numerical equivalence has been established.
`bifold` returns a bounded number of tracebacks, not an automatic equivalent of
NUPACK's exhaustive 3 kcal/mol suboptimal band. Report truncation explicitly.
Pass every setting rather than relying on help defaults: the 6.6 `bifold.cpp`
constructor sets `percent = 50.0` while help describes 10 percent.

The official `/Releases/6.6/` URL returned 404. The versioned source at
[`/Releases/rnastructure-6.6/RNAstructureSource.tgz`](https://rna.urmc.rochester.edu/Releases/rnastructure-6.6/RNAstructureSource.tgz)
has SHA-256 `1bedc62aaab984279055caaa6234d48fca113f4b8e17a8060e0b3784d5a397c3`
(30,765,790 bytes), matching the 6.6 Bioconda recipe. The archive hash, not the
URL, is the identity. A fresh download of this versioned URL matched the initial
`current` download byte-for-byte. Runtime smoke results are recorded below. Installation remains ticket 02's
responsibility.

## Recovered candidates

All retrieved file hashes, byte lengths, URLs and licence dispositions are in
[`benchmarks/rbs/sources.json`](../../benchmarks/rbs/sources.json). No third-party
engine or source archive is vendored by this evidence slice.

| Component | Pin and reusable material | Terms and gaps |
| --- | --- | --- |
| [Salis v1](https://github.com/hsalis/Ribosome-Binding-Site-Calculator-v1.0/tree/8a9c1de1bdd847bb90d2ab6ceaa3c20feceda307) | `8a9c1de1bdd847bb90d2ab6ceaa3c20feceda307`; `RBS_Calculator.py`, `NuPACK.py`, designer and CLI sources | GPL-3.0-or-later in scorer/wrapper headers; University of California Regents, 2008–2009. Python 2; requires external NUPACK 2.0 executables. Preserve notice on adapted code. `ViennaRNA.py` exists but the scorer imports `NuPACK`. |
| [Jaymin/iDOG](https://github.com/jayman1466/iDOG/tree/9d71187f0b2eb27ee681918927e12850470a0688) | `9d71187f0b2eb27ee681918927e12850470a0688`; real `dG_tot_calc.py`, `create_RBS.py`, `RNAfold_wrapper.py` | MIT, copyright 2020 jayman1466. Scorer imports Biopython and wrapper; needs RNAfold/RNAduplex; optional Kinfold. Wrapper attributes RNAfold/RNAsubopt portions to cathalgarvey/RNAfoldWrap.py, whose original licence was not recovered in bounded search. Do not copy that wrapper until resolved; use an original adapter. Other `.pyc` modules are not recovered sources. |
| [SalisLabCode](https://github.com/hsalis/SalisLabCode/tree/46da9132740bce30bccd107f02808adf2215e2f0) | `46da9132740bce30bccd107f02808adf2215e2f0`; ModelTestSystem code and source measurements | ModelTestSystem GPL-3.0. `TranslationRateModels.py:27` explicitly imports private `DNAc`; no current RBS implementation recovered. Master and r2022 tag/release inventoried; wrappers are not a complete model. |
| [Independent Go model](https://github.com/allyourbasepair/rbscalculator/tree/e8a583a2c64960babe117908af7eeb854b817b6d) | `e8a583a2c64960babe117908af7eeb854b817b6d`; conceptual comparison and mechanism tests | Repository MIT, embedded folding/statistics components require separate audit before adoption. Uses LinearFold and a duplex lookup table rather than the original cofolding procedure. README explicitly disclaims agreement. Do not adopt its benchmark table as a primary published-model score. |
| [SynBioMTS](https://github.com/reisalex/SynBioMTS/tree/d7d46af7981f90d2147cbc0463c5254b16c5c92c) | `d7d46af7981f90d2147cbc0463c5254b16c5c92c`; database import and statistics audit | GPL-3.0 code. Data terms traced separately to original supplements. Python 2/pandas/scipy dependencies; fitted normalizations and outlier filtering need independent reproduction. Not a current RBS engine. |
| [ViennaRNA](https://github.com/ViennaRNA/ViennaRNA/tree/1ffec79f5e258896160f7362ced8263450f371dc) | v2.7.2, `1ffec79f5e258896160f7362ced8263450f371dc` | Custom fee restriction, plus component-specific notices. Optional comparison only; no required runtime adoption. |
| [seqfold](https://github.com/Lattice-Automation/seqfold) | Secondary candidate only | MIT repository; upstream explicitly says no heterodimers. Single-strand MFE alone cannot replace the required mRNA–rRNA calculations. Not adopted or pinned for runtime. |

## Algorithm differences that must remain visible

Located symbols below refer to the pinned scorer files, not Session A's code.

| Mechanism | Salis v1 | iDOG |
| --- | --- | --- |
| Unbound window | `cutoff = 35`; `[max(0,start−35):min(n,start+35)]` | Core folds supplied leader+ORF; `relevant_mRNA` clips upstream to 35 but its downstream condition uses `>38`, leaving 36–38 nt untrimmed. |
| aSD | `acctcctta` (DNA spelling), 5′→3′ | Supplied argument; common default ACCUCCUUA. Keep ACCUCCUUU separate. |
| Candidate binding | Cofold entire upstream window with rRNA; NUPACK `subopt` within 3 kcal/mol, intramolecular pairing permitted | `RNAduplex` on last `13+len(rRNA)` leader nt, excluding last 2; 1.5 kcal/mol band. No intramolecular structures in duplex search. |
| Candidate ranking | Minimize cofold energy + spacing before standby correction | Minimize duplex + residual upstream/downstream folds + spacing + start energy. |
| Spacing | Continuous push/pull functions, optimal aligned spacing 5 | Rounded lookup; accepts 3–13 only. Short-leader spacing still uses nominal truncated size, a source-audit concern. |
| Bound downstream region | `footprint = 1000`, effectively all downstream sequence unfolded in this window | `orf_sequence[16:]` can refold, despite comments mentioning 15 nt. |
| Standby | Four bases upstream; compute signed correction `before−after ≤ 0`, then subtract it in total | Reserve four bases before upstream folding, no separately returned standby term. |
| Dangles | `auto_dangles`: none if start >35, all otherwise | RNAfold/RNAduplex defaults; no explicit engine version/temperature/dangle settings. |
| Start energy | ATG −1.194; GTG −0.0748; TTG −0.0435; CTG −0.03406 kcal/mol; scanner excludes CTG | Same table; caller determines starts. |
| Rate | `2500 * exp(−dG/2.222)` | `2500 * exp(−0.45*dG)`; close but not identical. |
| Failure handling | CalcError for leaderless/no binding, legacy large-energy sentinels | `[100,…,TIR=0,…]` sentinel if no selected candidate. Do not translate sentinel to successful numeric prediction. |
| Kinetics | Diagnostic kinetic score, not later drafting correction | Optional Kinfold warning path contains undefined `residuemRNA_bind_indexs_in_hairpin`; wrapper raises undefined `RNAFoldErr`. Static findings, not executed claims. |

The source's total is `complex_with_spacing + start − unbound_mRNA − standby`.
Its comment mentions rRNA subtraction, but the executable equation does not
subtract a separate rRNA energy there. Preserve the executable specification
and document differences from paper conventions.

## Independent scalar fixtures

[`scalar-fixtures.json`](../../benchmarks/rbs/scalar-fixtures.json) is a frozen
development fixture set, constructed from the upstream equations without
examining reconstruction scoring internals. Values are kcal/mol unless noted.
It is **not** a historical whole-calculator output corpus.

- Spacing 3: `12.2 / (1 + exp(0))³ = 1.525`.
- Spacing 5: 0; spacing 6: `0.048 + 0.24 = 0.288`; spacing 13: 4.992.
- Spacing 4: 0.005325582140839866, unlike iDOG's rounded 0.01.
- At total energy 0, both conversions give 2500. At +10, Salis v1 gives
  27.759995286718496 while iDOG gives 27.772491345605765.
- Synthetic algebra check: complex −8, start −1.194, unbound −4, signed standby
  −2 gives total −3.194. This checks the sign; no structure was predicted.
- With 20 upstream bases, zero-based start 20 and one-based pair `(7,29)`
  linking to the ninth rRNA base, aligned spacing is `20−7+1−9 = 5`.

Tests should consume these fixed expectations independently. Backend numerical
fixtures require their own version/table/settings identity and cannot establish
NUPACK or hosted equivalence.

## Verified backend smoke and build

On macOS arm64, unmodified 6.6 source compiled with the existing command-line
SDK. Default clang could not locate C++ headers; specifying the installed SDK
fixed this environment issue without installing tools or requesting privileges:

```sh
make -j4 Fold bifold AllSub efn2 ct2dot CXX='clang++ -isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk -isystem /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/c++/v1'
```

Set `DATAPATH` to the archive's `data_tables` directory and use absolute executable
paths (macOS `/usr/bin/fold` is an unrelated text utility). The exact smoke inputs,
commands, CT hashes and base pairs are in
[`rnastructure-smoke-fixtures.json`](../../benchmarks/rbs/rnastructure-smoke-fixtures.json),
with 45 RNA/autodetect table hashes in
[`rnastructure-tables.json`](../../benchmarks/rbs/rnastructure-tables.json).

- `GGGAAACCC`: Fold MFE −1.2 kcal/mol; pairs (1,9), (2,8), (3,7);
  independent `efn2` reevaluation agrees.
- Twelve A bases: no base pairs; CT header omits the ENERGY field. An adapter
  must handle this format explicitly, not infer that all missing energies are 0.
- `AAAGGAGGAAAAAA` plus `ACCUCCUUA`: first bifold structure −11.6 kcal/mol.
  The CT concatenation contains **three `I` linker bases** before the rRNA;
  remove/map them explicitly when reporting biological coordinates.
- `efn2 --simple` selects the energy model used during dynamic programming.
  Its default uses a different multibranch-loop evaluation. The hairpin above
  has no multibranch loop, so it does not test that difference.

All four executed smoke commands exited 0. `AllSub` and `ct2dot` compiled and
showed help; their scientific behavior is not certified by this smoke check.
The source archive and all 30 initial ledger entries were locally rehashed.
